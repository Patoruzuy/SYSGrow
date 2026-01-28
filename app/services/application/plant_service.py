"""
Plant Service
=============
Application-level service for managing plants and their sensor relationships.

This service provides plant-specific operations including:
- Plant CRUD operations (direct access to unit runtimes)
- Plant-sensor linking with validation
- Available sensors discovery with friendly names
- Plant status and monitoring

Responsibilities:
- Own plant/sensor linking and in-memory plant state (single source of truth)
- Delegate unit-level lifecycle persistence (add/remove) to GrowthService for consistency
- Access unit runtimes via GrowthService.get_unit_runtime() when needed
- Coordinate with SensorManagementService for sensor information
- Generate friendly sensor names for UI
- Validate plant-sensor compatibility
"""
from __future__ import annotations

import threading
from typing import Any, Dict, List, Optional, TYPE_CHECKING
import logging

from app.domain.plant_profile import PlantProfile

if TYPE_CHECKING:
    from app.services.application.growth_service import GrowthService
    from app.services.application.activity_logger import ActivityLogger
    from app.services.application.threshold_service import ThresholdService
    from app.services.application.notifications_service import NotificationsService
    from app.services.hardware import SensorManagementService
    from app.utils.plant_json_handler import PlantJsonHandler

from app.utils.event_bus import EventBus
from app.enums.events import PlantEvent, SensorEvent
from app.enums.common import ConditionProfileMode, ConditionProfileTarget
from app.domain.actuators import ActuatorType
from app.hardware.compat.enums import app_to_infra_actuator_type
from app.schemas.events import PlantStageUpdatePayload, PlantLifecyclePayload
from app.constants import THRESHOLD_UPDATE_TOLERANCE
from app.services.application.threshold_service import THRESHOLD_KEYS

logger = logging.getLogger(__name__)


def _row_to_dict(row) -> Dict[str, Any]:
    """Convert database row to dictionary."""
    if row is None:
        return {}
    if isinstance(row, dict):
        return row
    return {k: row[k] for k in row.keys()}


class PlantViewService:
    """
    Application service for plant management and viewing.

    This service owns plant read/update operations and accesses unit runtimes directly.
    It does NOT delegate plant operations to GrowthService.

    Renamed from PlantService to PlantViewService to clarify its role:
    - Views: list_plants, get_plant, get_plant_sensors
    - Updates: update_plant, update_plant_stage, link/unlink sensors
    - Lifecycle (create/remove) via GrowthService delegation
    """
    
    def __init__(
        self,
        growth_service: 'GrowthService',
        sensor_service: 'SensorManagementService',
        plant_repo: Optional[Any] = None,
        unit_repo: Optional[Any] = None,
        event_bus: Optional[EventBus] = None,
        activity_logger: Optional['ActivityLogger'] = None,
        plant_json_handler: Optional['PlantJsonHandler'] = None,
        threshold_service: Optional['ThresholdService'] = None,
        notifications_service: Optional['NotificationsService'] = None,
    ):
        """
        Initialize plant service.
        
        Args:
            growth_service: Service for accessing unit runtimes
            sensor_service: Service for sensor operations
            plant_repo: Repository for plant operations (required)
            unit_repo: Repository for unit operations (required for fallback context resolution)
            event_bus: EventBus for publishing plant events
            activity_logger: Activity logger for tracking plant operations
            plant_json_handler: Handler for plant growth stage definitions
            threshold_service: Optional threshold service for stage transition proposals
            notifications_service: Optional notifications service for threshold proposals
        """
        self.growth_service = growth_service
        self.sensor_service = sensor_service
        self.event_bus = event_bus or EventBus.get_instance()
        self.activity_logger = activity_logger
        self.threshold_service = threshold_service
        self.notifications_service = notifications_service
        
        # Plant JSON handler for growth stages (lazy init if not provided)
        self._plant_json_handler = plant_json_handler
        
        # Direct access to repositories for plant operations
        # PlantRepository must be provided (no fallback)
        if plant_repo is None:
            raise ValueError("plant_repo is required - PlantRepository must be provided")
        if unit_repo is None:
            raise ValueError("unit_repo is required - UnitRepository must be provided")
        
        self.plant_repo = plant_repo
        self.unit_repo = unit_repo
        self.analytics_repo = growth_service.analytics_repo
        self.audit_logger = growth_service.audit_logger
        self.devices_repo = growth_service.devices_repo
        
        # ==================== In-Memory Plant Storage ====================
        # Primary plant storage: unit_id -> {plant_id: PlantProfile}
        # This is the single source of truth for plant state
        self._plants: Dict[int, Dict[int, PlantProfile]] = {}
        self._plants_lock = threading.Lock()
        
        # Track active plant per unit: unit_id -> plant_id
        self._active_plants: Dict[int, int] = {}
        
        self.event_bus.subscribe(SensorEvent.SOIL_MOISTURE_UPDATE, self._handle_soil_moisture_update)

        logger.info("PlantViewService initialized with in-memory plant storage")

    # ==================== Plant JSON Handler ====================
    
    @property
    def plant_json_handler(self) -> 'PlantJsonHandler':
        """Lazy-load PlantJsonHandler if not provided at init."""
        if self._plant_json_handler is None:
            from app.utils.plant_json_handler import PlantJsonHandler
            self._plant_json_handler = PlantJsonHandler()
        return self._plant_json_handler

    # ==================== In-Memory Plant Management ====================
    
    def _get_unit_plants(self, unit_id: int) -> Dict[int, PlantProfile]:
        """
        Get or initialize plant collection for a unit.
        
        Thread-safe access to the unit's plant dictionary.
        
        Args:
            unit_id: Unit identifier
            
        Returns:
            Dictionary of plant_id -> PlantProfile for the unit
        """
        with self._plants_lock:
            if unit_id not in self._plants:
                self._plants[unit_id] = {}
            return self._plants[unit_id]
    
    def get_active_plant(self, unit_id: int) -> Optional[PlantProfile]:
        """
        Get the active plant for a unit.
        
        Args:
            unit_id: Unit identifier
            
        Returns:
            Active PlantProfile or None
        """
        with self._plants_lock:
            active_plant_id = self._active_plants.get(unit_id)
            if active_plant_id is None:
                return None
            unit_plants = self._plants.get(unit_id, {})
            return unit_plants.get(active_plant_id)
    
    def clear_unit_plants(self, unit_id: int) -> None:
        """
        Clear all plants for a unit from memory.
        
        Called when a unit is stopped or deleted.
        
        Args:
            unit_id: Unit identifier
        """
        with self._plants_lock:
            removed_count = len(self._plants.pop(unit_id, {}))
            self._active_plants.pop(unit_id, None)
            if removed_count > 0:
                logger.debug("Cleared %d plants from memory for unit %s", removed_count, unit_id)
    
    def is_unit_loaded(self, unit_id: int) -> bool:
        """
        Check if plants for a unit are loaded in memory.
        
        Args:
            unit_id: Unit identifier
            
        Returns:
            True if unit has been loaded (even if empty)
        """
        with self._plants_lock:
            return unit_id in self._plants

    # ==================== PlantProfile Creation ====================
    
    def _create_plant_profile(
        self,
        plant_id: int,
        plant_name: str,
        plant_type: str,
        current_stage: str,
        plant_species: Optional[str] = None,
        plant_variety: Optional[str] = None,
        days_in_stage: int = 0,
        moisture_level: float = 0.0,
        growth_stages: Optional[Any] = None,
        lighting_schedule: Optional[Dict[str, Dict[str, Any]]] = None,
        pot_size_liters: float = 0.0,
        pot_material: str = "plastic",
        growing_medium: str = "soil",
        medium_ph: float = 7.0,
        strain_variety: Optional[str] = None,
        expected_yield_grams: float = 0.0,
        light_distance_cm: float = 0.0,
        gdd_base_temp_c: Optional[float] = None,
        soil_moisture_threshold_override: Optional[float] = None,
        condition_profile_id: Optional[str] = None,
        condition_profile_mode: Optional[ConditionProfileMode] = None,
        **kwargs: Any,  # Added to prevent TypeError if legacy keys like aqi_threshold_override are passed
    ) -> PlantProfile:
        """
        Create a PlantProfile domain object.
        
        This is the ONLY method that creates PlantProfile instances.
        Centralizes growth stage resolution, lighting schedule, and plant metadata.
        
        Args:
            plant_id: Database ID of the plant
            plant_name: Name of the plant
            plant_type: Type/species of plant
            plant_species: Species of the plant
            plant_variety: Variety/cultivar of the plant
            current_stage: Current growth stage
            days_in_stage: Days in current stage
            moisture_level: Current moisture level
            growth_stages: Optional growth stages (loaded if not provided)
            lighting_schedule: Optional lighting schedule per stage (loaded if not provided)
            pot_size_liters: Container size in liters
            pot_material: Container material
            growing_medium: Growing medium type
            medium_ph: pH level of medium
            strain_variety: Specific cultivar/strain
            expected_yield_grams: Target harvest amount
            light_distance_cm: Light distance
            gdd_base_temp_c: GDD base temperature
            soil_moisture_threshold_override: Soil moisture threshold override
            
        Returns:
            PlantProfile instance
        """
        # Load growth stages if not provided
        if growth_stages is None:
            try:
                growth_stages = self.plant_json_handler.get_growth_stages(plant_type)
            except Exception as e:
                logger.warning(
                    "Could not load growth stages for %s: %s",
                    plant_type,
                    e,
                )
                growth_stages = []
        
        # Load lighting schedule if not provided
        if lighting_schedule is None:
            try:
                lighting_schedule = self.plant_json_handler.get_lighting_schedule(plant_type)
            except Exception as e:
                logger.debug(
                    "Could not load lighting schedule for %s: %s",
                    plant_type,
                    e,
                )
                lighting_schedule = {}
        
        # Load GDD base temperature if not provided
        if gdd_base_temp_c is None:
            try:
                gdd_base_temp_c = self.plant_json_handler.get_gdd_base_temp_c(plant_type)
            except Exception as e:
                logger.debug(
                    "Could not load gdd_base_temp_c for %s: %s",
                    plant_type,
                    e,
                )
        
        return PlantProfile(
            plant_id=plant_id,
            plant_name=plant_name,
            plant_type=plant_type,
            plant_species=plant_species,
            plant_variety=plant_variety,
            gdd_base_temp_c=gdd_base_temp_c,
            current_stage=current_stage,
            growth_stages=growth_stages,
            lighting_schedule=lighting_schedule,
            days_in_stage=days_in_stage,
            moisture_level=moisture_level,
            pot_size_liters=pot_size_liters,
            pot_material=pot_material,
            growing_medium=growing_medium,
            medium_ph=medium_ph,
            strain_variety=strain_variety,
            expected_yield_grams=expected_yield_grams,
            light_distance_cm=light_distance_cm,
            soil_moisture_threshold_override=soil_moisture_threshold_override,
            condition_profile_id=condition_profile_id,
            condition_profile_mode=condition_profile_mode,
        )

    def create_plant_profile(self, **kwargs: Any) -> PlantProfile:
        """
        Public factory method for creating PlantProfile instances.
        
        This is the ONLY public entry point for creating PlantProfile objects.
        Used by UnitRuntimeFactory and other services that need to create plants.
        
        Automatically loads growth stages, lighting schedule, and GDD base temperature
        from PlantJsonHandler if not provided.
        
        Args:
            **kwargs: All PlantProfile constructor arguments. Required:
                - plant_id: int
                - plant_name: str
                - plant_type: str
                - current_stage: str
            Optional (loaded from PlantJsonHandler if not provided):
                - growth_stages: List[Dict]
                - lighting_schedule: Dict[str, Dict[str, Any]]
                - gdd_base_temp_c: float
            
        Returns:
            PlantProfile instance with all metadata populated
        """
        return self._create_plant_profile(**kwargs)
    
    def load_plants_for_unit(self, unit_id: int, active_plant_id: Optional[int] = None) -> int:
        """
        Load all plants for a unit from database into memory.
        
        Called by GrowthService when starting a unit runtime.
        Uses memory-first pattern: clears existing and reloads from DB.
        
        Args:
            unit_id: Unit identifier
            active_plant_id: Optional plant ID to set as active
            
        Returns:
            Number of plants loaded
        """
        try:
            # Clear existing plants for this unit
            self.clear_unit_plants(unit_id)
            
            # Load from database
            plant_data_list = self.plant_repo.get_plants_in_unit(unit_id)
            
            loaded_count = 0
            for plant_data in plant_data_list:
                plant_id = plant_data.get("plant_id")
                if plant_id is None:
                    logger.warning(
                        "Skipping plant record without plant_id for unit %s: %s",
                        unit_id,
                        plant_data,
                    )
                    continue
                
                # Create PlantProfile using our factory method
                plant = self._create_plant_profile(
                    plant_id=plant_id,
                    plant_name=plant_data.get("plant_name") or plant_data.get("name") or "Unknown Plant",
                    plant_type=plant_data.get("plant_type") or "unknown",
                    plant_species=plant_data.get("plant_species") or "unknown",
                    plant_variety=plant_data.get("plant_variety") or "unknown",
                    current_stage=plant_data.get("current_stage") or "Unknown",
                    days_in_stage=plant_data.get("days_in_stage", 0),
                    moisture_level=plant_data.get("moisture_level", 0.0),
                    pot_size_liters=plant_data.get("pot_size_liters", 0.0),
                    pot_material=plant_data.get("pot_material", "plastic"),
                    growing_medium=plant_data.get("growing_medium", "soil"),
                    medium_ph=plant_data.get("medium_ph", 7.0),
                    strain_variety=plant_data.get("strain_variety"),
                    expected_yield_grams=plant_data.get("expected_yield_grams", 0.0),
                    light_distance_cm=plant_data.get("light_distance_cm", 0.0),
                    soil_moisture_threshold_override=plant_data.get("soil_moisture_threshold_override"),
                )
                
                # Add to memory
                with self._plants_lock:
                    if unit_id not in self._plants:
                        self._plants[unit_id] = {}
                    self._plants[unit_id][plant.plant_id] = plant
                    logger.debug(
                        "Loaded plant %s (%s) for unit %s",
                        plant.plant_name,
                        plant_id,
                        unit_id,
                    )
                loaded_count += 1
            
            # Set active plant if specified
            if active_plant_id is not None:
                with self._plants_lock:
                    unit_plants = self._plants.get(unit_id, {})
                    if active_plant_id in unit_plants:
                        self._active_plants[unit_id] = active_plant_id
                        logger.debug("Set active plant to %s for unit %s", active_plant_id, unit_id)
                    else:
                        logger.warning(
                            "Cannot set active plant %s for unit %s: not in memory",
                            active_plant_id,
                            unit_id,
                        )
            
            logger.info("Loaded %d plants for unit %s", loaded_count, unit_id)
            return loaded_count
            
        except Exception as e:
            logger.error("Error loading plants for unit %s: %s", unit_id, e, exc_info=True)
            return 0


    # ==================== Plant CRUD Operations ====================
    
    def list_plants(self, unit_id: int) -> List[PlantProfile]:
        """
        List all plants in a unit using memory-first pattern.
        
        Args:
            unit_id: Unit identifier
            
        Returns:
            List of PlantProfile objects
        """
        try:
            # Fast path: check our in-memory collection first
            if self.is_unit_loaded(unit_id):
                with self._plants_lock:
                    unit_plants = self._plants.get(unit_id, {})
                    return list(unit_plants.values())
            
            # Fallback: load from database
            logger.debug("Plants for unit %s not in memory, loading from database", unit_id)
            self.load_plants_for_unit(unit_id)
            with self._plants_lock:
                unit_plants = self._plants.get(unit_id, {})
                return list(unit_plants.values())
            
        except Exception as e:
            logger.error(f"Error listing plants for unit {unit_id}: {e}", exc_info=True)
            return []

    def list_plants_as_dicts(self, unit_id: int) -> List[Dict[str, Any]]:
        """
        List all plants in a unit as dictionaries with metadata.
        
        Compatibility method for API endpoints that expect dicts.
        
        Args:
            unit_id: Unit identifier
            
        Returns:
            List of plant dictionaries with linked sensor information
        """
        try:
            plants = self.list_plants(unit_id)
            result: List[Dict[str, Any]] = []
            
            runtime = self.growth_service.get_unit_runtime(unit_id)
            unit_name = getattr(runtime, "unit_name", None) if runtime else None
            
            for plant_obj in plants:
                plant = plant_obj.to_dict()
                plant["unit_id"] = unit_id
                if unit_name:
                    plant["unit_name"] = unit_name
                
                # Normalize legacy field names
                if plant.get("name") in (None, "") and plant.get("plant_name") not in (None, ""):
                    plant["name"] = plant.get("plant_name")
                if plant.get("plant_name") in (None, "") and plant.get("name"):
                    plant["plant_name"] = plant.get("name")
                
                # Add linked sensor IDs
                sensor_ids = self.get_plant_sensor_ids(plant_obj.plant_id)
                plant["linked_sensor_ids"] = sensor_ids
                plant["sensor_count"] = len(sensor_ids)
                
                result.append(plant)
            
            return result
            
        except Exception as e:
            logger.error(f"Error listing plants as dicts for unit {unit_id}: {e}", exc_info=True)
            return []

    def _resolve_initial_soil_moisture_threshold(
        self,
        *,
        plant_type: str,
        plant_name: str,
    ) -> Optional[float]:
        """Resolve a starting soil moisture trigger for a new plant."""
        for name in (plant_type, plant_name):
            if not name:
                continue
            try:
                value = self.plant_json_handler.get_soil_moisture_trigger(name)
            except Exception as exc:
                logger.debug("Failed to resolve soil moisture trigger for %s: %s", name, exc, exc_info=True)
                continue
            if value is None:
                continue
            try:
                value = float(value)
            except (TypeError, ValueError):
                logger.debug("Invalid soil moisture trigger for %s: %r", name, value)
                continue
            if 0 <= value <= 100:
                return value
        return None

    def _resolve_historical_threshold_overrides(
        self,
        *,
        unit_id: int,
        plant_type: str,
        growth_stage: str,
        plant_variety: Optional[str],
        strain_variety: Optional[str],
        pot_size_liters: Optional[float],
    ) -> Dict[str, float]:
        """Fetch the latest stored overrides for a matching plant context."""
        user_id = self._get_unit_owner(unit_id)
        if not user_id:
            return {}
        try:
            row = self.plant_repo.get_latest_threshold_overrides(
                user_id=user_id,
                plant_type=plant_type,
                growth_stage=growth_stage,
                plant_variety=plant_variety,
                strain_variety=strain_variety,
                pot_size_liters=pot_size_liters,
            )
        except Exception as exc:
            logger.debug("Failed to load historical threshold overrides: %s", exc)
            return {}
        if not row:
            return {}
        mapping = {
            "temperature_threshold": row.get("temperature_threshold_override"),
            "humidity_threshold": row.get("humidity_threshold_override"),
            "co2_threshold": row.get("co2_threshold_override"),
            "voc_threshold": row.get("voc_threshold_override"),
            "lux_threshold": row.get("lux_threshold_override"),
            "air_quality_threshold": row.get("air_quality_threshold_override"),
            "soil_moisture_threshold": row.get("soil_moisture_threshold_override"),
        }
        overrides: Dict[str, float] = {}
        for key, value in mapping.items():
            if value is None:
                continue
            try:
                overrides[key] = float(value)
            except (TypeError, ValueError):
                continue
        return overrides
    
    def create_plant(
        self,
        unit_id: int,
        plant_name: str,
        plant_type: str,
        current_stage: str,
        plant_species: Optional[str] = None,
        plant_variety: Optional[str] = None,
        days_in_stage: int = 0,
        moisture_level: float = 0.0,
        sensor_ids: Optional[List[int]] = None,
        soil_moisture_threshold_override: Optional[float] = None,
        condition_profile_id: Optional[str] = None,
        condition_profile_mode: Optional[ConditionProfileMode] = None,
        condition_profile_name: Optional[str] = None,
        # Creation-time fields
        pot_size_liters: float = 0.0,
        pot_material: str = "plastic",
        growing_medium: str = "soil",
        medium_ph: float = 7.0,
        strain_variety: Optional[str] = None,
        expected_yield_grams: float = 0.0,
        light_distance_cm: float = 0.0,
    ) -> Optional[Dict[str, Any]]:
        """
        Create a new plant and optionally link sensors.
        
        Owns the complete plant lifecycle: DB persistence, in-memory state, events.
        GrowthService.add_plant_to_unit() is now a thin wrapper that calls this method.
        
        Args:
            unit_id: Unit identifier
            plant_name: Plant name
            plant_type: Plant type/species
            plant_species: Species of the plant
            plant_variety: Variety/cultivar of the plant
            current_stage: Initial growth stage
            days_in_stage: Days in current stage
            sensor_ids: Optional list of sensor IDs to link
            soil_moisture_threshold_override: Optional per-plant soil moisture trigger
            condition_profile_id: Optional condition profile id to seed thresholds
            condition_profile_mode: Optional profile mode (active/template)
            condition_profile_name: Optional name for cloned profile
            pot_size_liters: Container size in liters
            pot_material: Container material (plastic, ceramic, fabric, etc.)
            growing_medium: Growing medium (soil, coco_coir, hydroponics, etc.)
            medium_ph: Starting pH level
            strain_variety: Specific cultivar/strain name
            expected_yield_grams: Target harvest amount
            light_distance_cm: Initial light distance
            
        Returns:
            Plant dictionary with linked sensors or None

        Raises:
            ValueError: If validation fails (pH out of range, negative values)
        """
        try:
            # Validate inputs
            if not (0 <= medium_ph <= 14):
                raise ValueError(f"pH {medium_ph} outside valid range 0-14")
            if pot_size_liters < 0:
                raise ValueError(f"Pot size {pot_size_liters} must be >= 0")
            if expected_yield_grams < 0:
                raise ValueError(f"Expected yield {expected_yield_grams} must be >= 0")
            if light_distance_cm < 0:
                raise ValueError(f"Light distance {light_distance_cm} must be >= 0")

            if condition_profile_mode and not isinstance(condition_profile_mode, ConditionProfileMode):
                try:
                    condition_profile_mode = ConditionProfileMode(str(condition_profile_mode))
                except ValueError:
                    raise ValueError("Invalid condition profile mode")

            historical_overrides = self._resolve_historical_threshold_overrides(
                unit_id=unit_id,
                plant_type=plant_type,
                growth_stage=current_stage,
                plant_variety=plant_variety,
                strain_variety=strain_variety,
                pot_size_liters=pot_size_liters if pot_size_liters > 0 else None,
            )
            profile_override = None
            profile_present = False
            selected_profile_id = None
            selected_profile_mode = None
            profile_service = None
            user_id = self._get_unit_owner(unit_id)
            if self.threshold_service and user_id:
                profile_service = getattr(self.threshold_service, "personalized_learning", None)
                if condition_profile_id and not profile_service:
                    raise ValueError("Condition profile service not available")
                if condition_profile_id and profile_service:
                    profile = profile_service.get_condition_profile_by_id(
                        user_id=user_id,
                        profile_id=condition_profile_id,
                    )
                    if not profile:
                        raise ValueError("Condition profile not found")
                    desired_mode = condition_profile_mode or profile.mode
                    if profile.mode == ConditionProfileMode.TEMPLATE and desired_mode == ConditionProfileMode.ACTIVE:
                        cloned = profile_service.clone_condition_profile(
                            user_id=user_id,
                            source_profile_id=profile.profile_id,
                            name=condition_profile_name,
                            mode=ConditionProfileMode.ACTIVE,
                        )
                        if cloned:
                            profile = cloned
                            desired_mode = ConditionProfileMode.ACTIVE
                    profile_present = True
                    profile_override = profile.soil_moisture_threshold
                    selected_profile_id = profile.profile_id
                    selected_profile_mode = desired_mode
                else:
                    if profile_service:
                        link = profile_service.get_condition_profile_link(
                            user_id=user_id,
                            target_type=ConditionProfileTarget.UNIT,
                            target_id=int(unit_id),
                        )
                        if link:
                            unit_profile = profile_service.get_condition_profile_by_id(
                                user_id=user_id,
                                profile_id=link.profile_id,
                            )
                            if unit_profile:
                                if (
                                    str(unit_profile.plant_type or "").strip().lower()
                                    == str(plant_type or "").strip().lower()
                                    and str(unit_profile.growth_stage or "").strip().lower()
                                    == str(current_stage or "").strip().lower()
                                ):
                                    profile_present = True
                                    profile_override = unit_profile.soil_moisture_threshold
                                    selected_profile_id = unit_profile.profile_id
                                    selected_profile_mode = link.mode

                    if not profile_present:
                        profile = self.threshold_service.get_condition_profile(
                            user_id=user_id,
                            plant_type=plant_type,
                            growth_stage=current_stage,
                            plant_variety=plant_variety,
                            strain_variety=strain_variety,
                            pot_size_liters=pot_size_liters if pot_size_liters > 0 else None,
                        )
                        if profile:
                            profile_present = True
                            profile_override = profile.get("soil_moisture_threshold")

            if soil_moisture_threshold_override is None:
                if profile_override is not None:
                    soil_moisture_threshold_override = profile_override
                else:
                    soil_moisture_threshold_override = historical_overrides.get("soil_moisture_threshold")
                if soil_moisture_threshold_override is None:
                    soil_moisture_threshold_override = self._resolve_initial_soil_moisture_threshold(
                        plant_type=plant_type,
                        plant_name=plant_name,
                    )

            # Create plant in DB
            from datetime import datetime, timedelta
            now = datetime.now()
            plant_id = self.plant_repo.create_plant(
                plant_name=plant_name,
                plant_type=plant_type,
                plant_species=plant_species,
                plant_variety=plant_variety,
                current_stage=current_stage,
                days_in_stage=days_in_stage,
                moisture_level=moisture_level,
                planted_date=(now - timedelta(days=days_in_stage)).strftime("%Y-%m-%d"),
                created_at=now.strftime("%Y-%m-%d %H:%M:%S"),
                unit_id=unit_id,
                pot_size_liters=pot_size_liters,
                pot_material=pot_material,
                growing_medium=growing_medium,
                medium_ph=medium_ph,
                strain_variety=strain_variety,
                expected_yield_grams=expected_yield_grams,
                light_distance_cm=light_distance_cm,
                soil_moisture_threshold_override=soil_moisture_threshold_override,
            )
            
            if not plant_id:
                logger.error(f"Failed to create plant '{plant_name}' in DB")
                return None

            if selected_profile_id and user_id and profile_service:
                profile_service.link_condition_profile(
                    user_id=user_id,
                    target_type=ConditionProfileTarget.PLANT,
                    target_id=int(plant_id),
                    profile_id=selected_profile_id,
                    mode=selected_profile_mode or ConditionProfileMode.ACTIVE,
                )

            # Assign plant to unit
            try:
                self.plant_repo.assign_plant_to_unit(unit_id, plant_id)
            except Exception as exc:
                logger.debug(f"Failed to assign plant {plant_id} to unit {unit_id}: {exc}", exc_info=True)

            # Create PlantProfile in memory
            plant_profile = self.create_plant_profile(
                plant_id=plant_id,
                plant_name=plant_name,
                plant_type=plant_type,
                plant_species=plant_species,
                plant_variety=plant_variety,
                current_stage=current_stage,
                days_in_stage=days_in_stage,
                moisture_level=moisture_level,
                pot_size_liters=pot_size_liters,
                pot_material=pot_material,
                growing_medium=growing_medium,
                medium_ph=medium_ph,
                strain_variety=strain_variety,
                expected_yield_grams=expected_yield_grams,
                light_distance_cm=light_distance_cm,
                soil_moisture_threshold_override=soil_moisture_threshold_override,
                condition_profile_id=selected_profile_id,
                condition_profile_mode=selected_profile_mode,
            )
            
            # Add to in-memory collection
            with self._plants_lock:
                if unit_id not in self._plants:
                    self._plants[unit_id] = {}
                self._plants[unit_id][plant_profile.plant_id] = plant_profile
                logger.debug(
                    "Added plant %s (%s) to memory for unit %s",
                    plant_profile.plant_id,
                    plant_profile.plant_name,
                    unit_id,
                )
            
            # Emit event (GrowthService may subscribe for cache invalidation)
            self.event_bus.publish(
                PlantEvent.PLANT_ADDED,
                PlantLifecyclePayload(unit_id=unit_id, plant_id=plant_id),
            )

            if historical_overrides or profile_present:
                self._propose_stage_thresholds(
                    plant=plant_profile,
                    old_stage="initial",
                    new_stage=current_stage,
                    seed_overrides=historical_overrides,
                )
            
            # Audit logging
            self.audit_logger.log_event(
                actor="system",
                action="create",
                resource=f"plant:{plant_id}",
                outcome="success",
                unit=unit_id,
                plant_type=plant_type,
                stage=current_stage,
            )

            logger.info(f"Created plant {plant_id}: '{plant_name}' in unit {unit_id}")

            # Activity logging
            if self.activity_logger:
                from app.services.application.activity_logger import ActivityLogger
                self.activity_logger.log_activity(
                    activity_type=ActivityLogger.PLANT_ADDED,
                    description=f"Created plant {plant_id} ('{plant_name}') in unit {unit_id}",
                    severity=ActivityLogger.INFO,
                    entity_type="plant",
                    entity_id=plant_id,
                    metadata={
                        "plant_type": plant_type,
                        "current_stage": current_stage,
                    }
                )
            # Link sensors if provided
            linked_sensors = []
            if sensor_ids:
                for sensor_id in sensor_ids:
                    if self.link_plant_sensor(plant_id, sensor_id):
                        linked_sensors.append(sensor_id)
                        logger.info(f"Linked sensor {sensor_id} to plant {plant_id}")
                    else:
                        logger.warning(f"  x Failed to link sensor {sensor_id} to plant {plant_id}")
            
            # Return the newly created plant as dict with additional data
            plant_dict = self.get_plant_as_dict(plant_id, unit_id=unit_id)
            if plant_dict:
                if plant_dict.get("name") in (None, "") and plant_dict.get("plant_name") not in (None, ""):
                    plant_dict["name"] = plant_dict.get("plant_name")
                if plant_dict.get("plant_name") in (None, "") and plant_dict.get("name") not in (None, ""):
                    plant_dict["plant_name"] = plant_dict.get("name")
                plant_dict["linked_sensors"] = linked_sensors
                plant_dict["linked_sensor_ids"] = linked_sensors
                return plant_dict

            return None
            
        except Exception as e:
            logger.error(f"Error creating plant '{plant_name}': {e}", exc_info=True)
            return None

    def update_plant(
        self,
        plant_id: int,
        plant_name: Optional[str] = None,
        plant_type: Optional[str] = None,
        plant_species: Optional[str] = None,
        plant_variety: Optional[str] = None,
        pot_size_liters: Optional[float] = None,
        medium_ph: Optional[float] = None,
        strain_variety: Optional[str] = None,
        expected_yield_grams: Optional[float] = None,
        light_distance_cm: Optional[float] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Update plant fields (partial update supported).

        Args:
            plant_id: Plant identifier
            plant_name: Updated plant name
            plant_type: Updated plant type
            plant_species: Updated plant species
            plant_variety: Updated plant variety
            pot_size_liters: Updated pot size in liters
            medium_ph: Updated growing medium pH
            strain_variety: Updated strain/variety
            expected_yield_grams: Updated expected yield in grams
            light_distance_cm: Updated light distance in cm

        Returns:
            Updated plant dictionary or None if plant not found

        Raises:
            ValueError: If validation fails (pH out of range, negative values)
        """
        try:
            # 1. Validate plant exists
            plant = self.get_plant(plant_id)
            if not plant:
                logger.error(f"Plant {plant_id} not found")
                return None

            # 2. Validate inputs
            if medium_ph is not None and not (0 <= medium_ph <= 14):
                raise ValueError(f"pH {medium_ph} outside valid range 0-14")
            if pot_size_liters is not None and pot_size_liters < 0:
                raise ValueError(f"Pot size {pot_size_liters} must be >= 0")
            if expected_yield_grams is not None and expected_yield_grams < 0:
                raise ValueError(f"Expected yield {expected_yield_grams} must be >= 0")
            if light_distance_cm is not None and light_distance_cm < 0:
                raise ValueError(f"Light distance {light_distance_cm} must be >= 0")

            # 3. Build update dict (only non-None values)
            update_fields = {}
            if plant_name is not None:
                update_fields["name"] = plant_name
            if plant_type is not None:
                update_fields["plant_type"] = plant_type
            if plant_species is not None:
                update_fields["plant_species"] = plant_species
            if plant_variety is not None:
                update_fields["plant_variety"] = plant_variety
            if pot_size_liters is not None:
                update_fields["pot_size_liters"] = pot_size_liters
            if medium_ph is not None:
                update_fields["medium_ph"] = medium_ph
            if strain_variety is not None:
                update_fields["strain_variety"] = strain_variety
            if expected_yield_grams is not None:
                update_fields["expected_yield_grams"] = expected_yield_grams
            if light_distance_cm is not None:
                update_fields["light_distance_cm"] = light_distance_cm

            # 4. Update database
            if update_fields:
                self.plant_repo.update_plant(plant_id, **update_fields)

                # 5. Keep our in-memory plant in sync
                # Update the PlantProfile object directly (it's the same reference)
                if plant_name is not None:
                    plant.plant_name = plant_name
                if plant_type is not None:
                    plant.plant_type = plant_type
                    try:
                        plant.growth_stages = self.plant_json_handler.get_growth_stages(plant_type)
                        plant.refresh_growth_metadata()
                    except Exception as exc:
                        logger.warning(
                            "Failed to refresh growth stages for plant %s (%s): %s",
                            plant_id,
                            plant_type,
                            exc,
                        )
                if pot_size_liters is not None:
                    plant.pot_size_liters = pot_size_liters
                if medium_ph is not None:
                    plant.medium_ph = medium_ph
                if strain_variety is not None:
                    plant.strain_variety = strain_variety
                if expected_yield_grams is not None:
                    plant.expected_yield_grams = expected_yield_grams
                if light_distance_cm is not None:
                    plant.light_distance_cm = light_distance_cm

                # 6. Log activity
                if self.activity_logger:
                    from app.services.application.activity_logger import ActivityLogger
                    self.activity_logger.log_activity(
                        activity_type=ActivityLogger.PLANT_UPDATED,
                        description=f"Updated plant {plant_id}",
                        severity=ActivityLogger.INFO,
                        entity_type="plant",
                        entity_id=plant_id,
                        metadata=update_fields
                    )

                logger.info(f"Updated plant {plant_id}: {update_fields}")

            # 7. Return updated plant as dict (for API compatibility)
            # Find unit_id for the plant
            resolved_unit_id = None
            with self._plants_lock:
                for uid, unit_plants in self._plants.items():
                    if plant_id in unit_plants:
                        resolved_unit_id = uid
                        break
            
            return self.get_plant_as_dict(plant_id, unit_id=resolved_unit_id)

        except ValueError:
            # Re-raise validation errors
            raise
        except Exception as e:
            logger.error(f"Error updating plant {plant_id}: {e}", exc_info=True)
            return None

    def update_soil_moisture_threshold(
        self,
        plant_id: int,
        threshold: float,
        unit_id: Optional[int] = None,
    ) -> bool:
        """
        Update the per-plant soil moisture threshold override.

        Args:
            plant_id: Plant identifier
            threshold: New soil moisture threshold (0-100)
            unit_id: Optional unit identifier (speeds up in-memory update)

        Returns:
            True if updated, False otherwise
        """
        try:
            value = float(threshold)
        except (TypeError, ValueError):
            logger.error("Invalid soil moisture threshold for plant %s: %s", plant_id, threshold)
            return False

        value = max(0.0, min(100.0, value))

        try:
            self.plant_repo.update_plant(plant_id, soil_moisture_threshold_override=value)
        except Exception as exc:
            logger.error(
                "Failed to persist soil moisture threshold override for plant %s: %s",
                plant_id,
                exc,
                exc_info=True,
            )
            return False

        plant = self.get_plant(plant_id, unit_id=unit_id)
        if plant:
            plant.soil_moisture_threshold_override = value

        resolved_unit_id = unit_id
        if resolved_unit_id is None:
            with self._plants_lock:
                for uid, unit_plants in self._plants.items():
                    if plant_id in unit_plants:
                        resolved_unit_id = uid
                        break

        if (
            plant
            and resolved_unit_id is not None
            and self.threshold_service
            and plant.condition_profile_id
            and plant.condition_profile_mode == ConditionProfileMode.ACTIVE
        ):
            profile_service = getattr(self.threshold_service, "personalized_learning", None)
            user_id = self._get_unit_owner(resolved_unit_id)
            if profile_service and user_id:
                profile_service.upsert_condition_profile(
                    user_id=user_id,
                    profile_id=plant.condition_profile_id,
                    plant_type=plant.plant_type or "unknown",
                    growth_stage=plant.current_stage or "Unknown",
                    soil_moisture_threshold=value,
                    plant_variety=plant.plant_variety,
                    strain_variety=plant.strain_variety,
                    pot_size_liters=plant.pot_size_liters if plant.pot_size_liters > 0 else None,
                )

        logger.info(
            "Updated soil moisture threshold override for plant %s to %.1f",
            plant_id,
            value,
        )
        return True

    def get_plant(self, plant_id: int, unit_id: Optional[int] = None) -> Optional[PlantProfile]:
        """
        Get plant as PlantProfile object using memory-first pattern.
        
        Args:
            plant_id: Plant identifier
            unit_id: Optional unit identifier (speeds up lookup)
             
        Returns:
            PlantProfile object or None
        """
        try:
            with self._plants_lock:
                if unit_id is not None:
                    unit_plants = self._plants.get(unit_id, {})
                    if plant_id in unit_plants:
                        return unit_plants.get(plant_id)
                else:
                    # Search all units for the plant
                    for uid, unit_plants in self._plants.items():
                        if plant_id in unit_plants:
                            return unit_plants.get(plant_id)
            
            # Fallback: load from database and hydrate into memory
            plant_data = self.plant_repo.get_plant(plant_id)
            if not plant_data:
                return None
            
            plant_dict = _row_to_dict(plant_data)
            resolved_unit_id = plant_dict.get("unit_id") or unit_id
            
            # Create PlantProfile from database data
            condition_profile_id = None
            condition_profile_mode = None
            if resolved_unit_id is not None and self.threshold_service:
                profile_service = getattr(self.threshold_service, "personalized_learning", None)
                user_id = self._get_unit_owner(resolved_unit_id)
                if profile_service and user_id:
                    link = profile_service.get_condition_profile_link(
                        user_id=user_id,
                        target_type=ConditionProfileTarget.PLANT,
                        target_id=int(plant_id),
                    )
                    if link:
                        condition_profile_id = link.profile_id
                        condition_profile_mode = link.mode

            plant = self._create_plant_profile(
                plant_id=plant_id,
                plant_name=plant_dict.get("plant_name") or plant_dict.get("name") or "Unknown Plant",
                plant_type=plant_dict.get("plant_type") or "unknown",
                plant_species=plant_dict.get("plant_species") or "unknown",
                plant_variety=plant_dict.get("plant_variety") or "unknown",
                current_stage=plant_dict.get("current_stage") or "Unknown",
                days_in_stage=plant_dict.get("days_in_stage", 0),
                moisture_level=plant_dict.get("moisture_level", 0.0),
                pot_size_liters=plant_dict.get("pot_size_liters", 0.0),
                pot_material=plant_dict.get("pot_material", "plastic"),
                growing_medium=plant_dict.get("growing_medium", "soil"),
                medium_ph=plant_dict.get("medium_ph", 7.0),
                strain_variety=plant_dict.get("strain_variety"),
                expected_yield_grams=plant_dict.get("expected_yield_grams", 0.0),
                light_distance_cm=plant_dict.get("light_distance_cm", 0.0),
                soil_moisture_threshold_override=plant_dict.get("soil_moisture_threshold_override"),
                condition_profile_id=condition_profile_id,
                condition_profile_mode=condition_profile_mode,
            )
            
            if resolved_unit_id is None:
                logger.warning("Plant %s has no unit_id, returning transient profile", plant_id)
                return plant
            
            # Store in memory for future fast lookups
            with self._plants_lock:
                if resolved_unit_id not in self._plants:
                    self._plants[resolved_unit_id] = {}
                self._plants[resolved_unit_id][plant.plant_id] = plant
                logger.debug(
                    "Hydrated plant %s into memory for unit %s",
                    plant.plant_id,
                    resolved_unit_id,
                )
            
            return plant
            
        except Exception as e:
            logger.error(f"Error getting plant {plant_id}: {e}", exc_info=True)
            return None

    def get_plant_as_dict(self, plant_id: int, unit_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """
        Get plant details as dictionary with linked sensor information.
        
        Compatibility method for API endpoints that expect a dict.
        
        Args:
            plant_id: Plant identifier
            unit_id: Optional unit identifier (enables runtime lookup)
             
        Returns:
            Plant dictionary or None
        """
        try:
            plant = self.get_plant(plant_id, unit_id=unit_id)
            if not plant:
                return None
            
            # Convert to dict and add metadata
            plant_dict = plant.to_dict()
            
            # Add unit context
            if unit_id is not None:
                plant_dict["unit_id"] = unit_id
                runtime = self.growth_service.get_unit_runtime(unit_id)
                if runtime:
                    plant_dict["unit_name"] = getattr(runtime, "unit_name", None)
            else:
                # Try to resolve unit_id
                with self._plants_lock:
                    for uid, unit_plants in self._plants.items():
                        if plant_id in unit_plants:
                            plant_dict["unit_id"] = uid
                            runtime = self.growth_service.get_unit_runtime(uid)
                            if runtime:
                                plant_dict["unit_name"] = getattr(runtime, "unit_name", None)
                            break
            
            # Normalize legacy field names
            if plant_dict.get("name") in (None, "") and plant_dict.get("plant_name") not in (None, ""):
                plant_dict["name"] = plant_dict.get("plant_name")
            if plant_dict.get("plant_name") in (None, "") and plant_dict.get("name"):
                plant_dict["plant_name"] = plant_dict.get("name")
            
            # Add linked sensor IDs
            plant_dict["linked_sensor_ids"] = self.get_plant_sensor_ids(plant_id)
            
            return plant_dict
            
        except Exception as e:
            logger.error(f"Error getting plant {plant_id} as dict: {e}", exc_info=True)
            return None
    
    def remove_plant(self, unit_id: int, plant_id: int) -> bool:
        """
        Remove a plant from a unit.

        Owns the complete plant lifecycle: memory removal first, then DB removal, then events.
        GrowthService.remove_plant_from_unit() is now a thin wrapper that calls this method.

        Args:
            unit_id: Unit identifier
            plant_id: Plant identifier

        Returns:
            True if the plant was removed from memory and/or DB. False otherwise.
        """
        try:
            # Get plant info before removal
            plant = self.get_plant(unit_id, plant_id)
            plant_name: Optional[str] = None
            plant_type: Optional[str] = None
            
            if plant:
                plant_name = plant.plant_name
                plant_type = plant.plant_type

            # 1. Remove from memory first (thread-safe)
            removed_from_memory = False
            with self._plants_lock:
                unit_plants = self._plants.get(unit_id, {})
                removed_plant = unit_plants.pop(plant_id, None)
                
                # Clear active plant if removing it
                if self._active_plants.get(unit_id) == plant_id:
                    del self._active_plants[unit_id]
                    logger.debug("Cleared active plant for unit %s (removed plant %s)", unit_id, plant_id)
                
                if removed_plant:
                    logger.debug("Removed plant %s from memory for unit %s", plant_id, unit_id)
                    removed_from_memory = True

            # 2. Remove from DB
            db_removed = False
            try:
                if hasattr(self.plant_repo, "remove_plant_from_unit"):
                    self.plant_repo.remove_plant_from_unit(unit_id, plant_id)
                self.plant_repo.remove_plant(plant_id)
                db_removed = True
            except Exception as exc:
                logger.debug(f"Failed to remove plant {plant_id} from DB: {exc}", exc_info=True)

            success = removed_from_memory or db_removed
            
            if success:
                try:
                    user_id = self._get_unit_owner(unit_id)
                    profile_service = getattr(self.threshold_service, "personalized_learning", None) if self.threshold_service else None
                    if user_id and profile_service:
                        profile_service.unlink_condition_profile(
                            user_id=user_id,
                            target_type=ConditionProfileTarget.PLANT,
                            target_id=int(plant_id),
                        )
                except Exception:
                    logger.debug("Failed to unlink condition profile for plant %s", plant_id, exc_info=True)
                # Emit event (GrowthService may subscribe for cache invalidation)
                self.event_bus.publish(
                    PlantEvent.PLANT_REMOVED,
                    PlantLifecyclePayload(unit_id=unit_id, plant_id=plant_id),
                )
                
                # Activity logging
                if self.activity_logger:
                    from app.services.application.activity_logger import ActivityLogger
                    resolved_name = plant_name or f"plant #{plant_id}"
                    resolved_type = plant_type or "Unknown"
                    self.activity_logger.log_activity(
                        activity_type=ActivityLogger.PLANT_REMOVED,
                        description=f"Removed {resolved_type} '{resolved_name}' from unit {unit_id}",
                        severity=ActivityLogger.INFO,
                        entity_type="plant",
                        entity_id=plant_id,
                        metadata={"plant_type": resolved_type, "unit_id": unit_id},
                    )
            
            return success
            
        except Exception as exc:
            logger.error(
                f"Failed to remove plant {plant_id} from unit {unit_id}: {exc}",
                exc_info=True,
            )
            return False


    def link_plant_sensor(self, plant_id: int, sensor_id: int) -> bool:
        """
        Link a sensor to a plant with validation.
        
        Args:
            plant_id: Plant identifier
            sensor_id: Sensor identifier
            
        Returns:
            True if successful
        """
        try:
            # Validate sensor exists and get details
            sensor = self.sensor_service.get_sensor(sensor_id)
            if not sensor:
                logger.error(f"Sensor {sensor_id} not found")
                return False
            
            # Validate sensor type (only soil moisture and plant sensors can be linked to plants)
            sensor_type = str(sensor.get('sensor_type') or '').strip().lower()
            allowed_types = {'soil_moisture', 'plant_sensor'}
            if sensor_type not in allowed_types:
                logger.error(f"Sensor type '{sensor_type}' cannot be linked to plants. Allowed: {sorted(allowed_types)}")
                return False
            
            # Link in database
            self.plant_repo.link_sensor_to_plant(plant_id, sensor_id)
            
            # Update PlantProfile in memory if available
            plant = self.get_plant(plant_id)
            if plant:
                plant.link_sensor(sensor_id)
                logger.info(f"Linked sensor {sensor_id} to plant {plant_id} in memory")
            
            self.audit_logger.log_event(
                actor="system",
                action="link",
                resource=f"plant:{plant_id}",
                outcome="success",
                sensor_id=sensor_id,
            )
            
            logger.info(f"Linked sensor {sensor_id} ({sensor_type}) to plant {plant_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error linking sensor {sensor_id} to plant {plant_id}: {e}", exc_info=True)
            return False
    
    def unlink_plant_sensor(self, plant_id: int, sensor_id: int) -> bool:
        """
        Unlink a sensor from a plant.
        
        Args:
            plant_id: Plant identifier
            sensor_id: Sensor identifier
            
        Returns:
            True if successful
        """
        try:
            # Unlink in database
            self.plant_repo.unlink_sensor_from_plant(plant_id, sensor_id)
            
            # Update PlantProfile in memory if available
            plant = self.get_plant(plant_id)
            if plant:
                # Update in-memory PlantProfile
                plant = self.get_plant(plant_id)
                if plant and plant.get_sensor_id() == sensor_id:
                    plant.link_sensor(None)  # Clear sensor
                    logger.info(f"Unlinked sensor {sensor_id} from plant {plant_id} in memory")
            
            self.audit_logger.log_event(
                actor="system",
                action="unlink",
                resource=f"plant:{plant_id}",
                outcome="success",
                sensor_id=sensor_id,
            )
            
            logger.info(f"Unlinked sensor {sensor_id} from plant {plant_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error unlinking sensor {sensor_id} from plant {plant_id}: {e}", exc_info=True)
            return False
    
    def unlink_all_sensors_from_plant(self, plant_id: int) -> bool:
        """
        Unlink all sensors from a plant.
        Best-effort cleanup operation, typically called before plant deletion.
        
        Args:
            plant_id: Plant identifier
            
        Returns:
            True if successful, False otherwise
        """
        try:
            self.plant_repo.unlink_all_sensors_from_plant(plant_id)
            logger.info(f"Unlinked all sensors from plant {plant_id}")
            return True
        except Exception as e:
            logger.debug(f"Failed to unlink all sensors from plant {plant_id}: {e}", exc_info=True)
            return False
    
    def get_plant_sensor_ids(self, plant_id: int) -> List[int]:
        """
        Get sensor IDs linked to a plant.
        
        Args:
            plant_id: Plant identifier
            
        Returns:
            List of sensor IDs
        """
        try:
            return self.plant_repo.get_sensors_for_plant(plant_id)
        except Exception as e:
            logger.error(f"Error getting sensors for plant {plant_id}: {e}", exc_info=True)
            return []
    
    def get_plant_sensors(self, plant_id: int) -> List[Dict[str, Any]]:
        """
        Get full sensor details for all sensors linked to a plant.
        
        Args:
            plant_id: Plant identifier
            sensor_type: Optional sensor type filter (e.g., 'soil_moisture')
            
        Returns:
            List of sensor dictionaries with friendly names
        """
        try:
            sensor_ids = self.get_plant_sensor_ids(plant_id)
            sensors = []
            for sensor_id in sensor_ids:
                sensor = self.sensor_service.get_sensor(sensor_id)
                if sensor:
                    # Add friendly name
                    sensor['friendly_name'] = self._generate_friendly_name(sensor)
                    sensors.append(sensor)
            
            return sensors
            
        except Exception as e:
            logger.error(f"Error getting sensor details for plant {plant_id}: {e}", exc_info=True)
            return []
        
    # ==================== Plant Actuator Linking ====================

    @staticmethod
    def _normalize_actuator_type(value: Any) -> ActuatorType:
        """Normalize actuator type values to infrastructure ActuatorType."""
        actuator_type = app_to_infra_actuator_type(value)
        if actuator_type != ActuatorType.UNKNOWN:
            return actuator_type
        text = str(value or "").strip().lower().replace("-", "_")
        if text in {"water_pump", "waterpump"}:
            return ActuatorType.PUMP
        return ActuatorType.UNKNOWN

    def link_plant_actuator(self, plant_id: int, actuator_id: int) -> bool:
        """
        Link an actuator to a plant (e.g., dedicated irrigation pump).
        """
        try:
            plant = self.get_plant(plant_id)
            if not plant:
                logger.error("Plant %s not found", plant_id)
                return False

            actuator = None
            if self.devices_repo:
                actuator = self.devices_repo.get_actuator_config_by_id(actuator_id)

            if not actuator:
                logger.error("Actuator %s not found", actuator_id)
                return False

            plant_unit_id = plant.unit_id
            actuator_unit_id = actuator.get("unit_id")
            if plant_unit_id and actuator_unit_id and int(plant_unit_id) != int(actuator_unit_id):
                logger.error("Actuator %s does not belong to unit %s", actuator_id, plant_unit_id)
                return False

            actuator_type = self._normalize_actuator_type(actuator.get("actuator_type"))
            if actuator_type not in {ActuatorType.PUMP, ActuatorType.VALVE}:
                logger.error(
                    "Actuator %s is not a pump or valve (type=%s)",
                    actuator_id,
                    actuator.get("actuator_type") or "unknown",
                )
                return False

            self.plant_repo.link_actuator_to_plant(plant_id, actuator_id)
            logger.info("Linked actuator %s to plant %s", actuator_id, plant_id)
            return True
        except Exception as e:
            logger.error("Error linking actuator %s to plant %s: %s", actuator_id, plant_id, e, exc_info=True)
            return False

    def unlink_plant_actuator(self, plant_id: int, actuator_id: int) -> bool:
        """Unlink an actuator from a plant."""
        try:
            self.plant_repo.unlink_actuator_from_plant(plant_id, actuator_id)
            logger.info("Unlinked actuator %s from plant %s", actuator_id, plant_id)
            return True
        except Exception as e:
            logger.error("Error unlinking actuator %s from plant %s: %s", actuator_id, plant_id, e, exc_info=True)
            return False

    def get_plant_actuator_ids(self, plant_id: int) -> List[int]:
        """Get actuator IDs linked to a plant."""
        try:
            return self.plant_repo.get_actuators_for_plant(plant_id)
        except Exception as e:
            logger.error("Error getting actuators for plant %s: %s", plant_id, e, exc_info=True)
            return []

    def get_plant_actuators(self, plant_id: int) -> List[Dict[str, Any]]:
        """Get actuator details linked to a plant."""
        try:
            actuator_ids = self.get_plant_actuator_ids(plant_id)
            actuators: List[Dict[str, Any]] = []
            if not self.devices_repo:
                return actuators
            for actuator_id in actuator_ids:
                actuator = self.devices_repo.get_actuator_config_by_id(actuator_id)
                if actuator:
                    actuators.append(actuator)
            return actuators
        except Exception as e:
            logger.error("Error getting actuator details for plant %s: %s", plant_id, e, exc_info=True)
            return []

    def get_available_actuators_for_plant(
        self,
        unit_id: int,
        actuator_type: str = "pump",
    ) -> List[Dict[str, Any]]:
        """List available actuators for linking to plants."""
        try:
            if not self.devices_repo:
                return []
            actuators = self.devices_repo.list_actuator_configs(unit_id=unit_id)
            normalized_type = self._normalize_actuator_type(actuator_type)
            if normalized_type == ActuatorType.UNKNOWN:
                return actuators

            filtered: List[Dict[str, Any]] = []
            for actuator in actuators:
                candidate_type = self._normalize_actuator_type(actuator.get("actuator_type"))
                if candidate_type == normalized_type:
                    filtered.append(actuator)
            return filtered
        except Exception as e:
            logger.error("Error getting available actuators for unit %s: %s", unit_id, e, exc_info=True)
            return []
    
    # ==================== Available Sensors Discovery ====================
    
    def get_available_sensors_for_plant(
        self,
        unit_id: int,
        sensor_type: str = 'soil_moisture'
    ) -> List[Dict[str, Any]]:
        """
        Get all sensors available for plant linking with friendly names.
        
        This provides a unified list of sensors regardless of protocol (GPIO, MQTT, ESP32-C6)
        with user-friendly names for the UI.
        
        Args:
            unit_id: Unit identifier
            sensor_type: Type of sensor to filter (default: SOIL_MOISTURE)
            
        Returns:
            List of sensors with friendly names and availability status
        """
        try:
            # Get all sensors for the unit
            sensors = self.sensor_service.list_sensors(unit_id=unit_id)
            
            # Filter and format for plant linking
            available = []
            for sensor in sensors:
                if str(sensor.get('sensor_type') or '').strip().lower() == str(sensor_type).strip().lower():
                    # Generate friendly name
                    friendly_name = self._generate_friendly_name(sensor)
                    
                    # Check if already linked to a plant
                    is_linked = self._is_sensor_linked(sensor.get('sensor_id'))
                    
                    available.append({
                        'sensor_id': sensor['sensor_id'],
                        'name': friendly_name,
                        'sensor_type': sensor.get('sensor_type'),
                        'protocol': sensor.get('protocol', 'GPIO'),
                        'model': sensor.get('model', 'Unknown'),
                        'is_linked': is_linked,
                        'enabled': sensor.get('is_active', True)
                    })
            
            logger.debug(f"Found {len(available)} available {sensor_type} sensors for unit {unit_id}")
            return available
            
        except Exception as e:
            logger.error(f"Error getting available sensors for unit {unit_id}: {e}", exc_info=True)
            return []
    
    # ==================== Plant Status & Monitoring ====================
    
    def set_active_plant(self, unit_id: int, plant_id: int) -> bool:
        """
        Set a plant as the active plant for the unit's climate control.
        
        Owns the complete operation: DB persistence, in-memory state, runtime updates, events.
        GrowthService.set_active_plant() is now a thin wrapper that calls this method.
        
        Args:
            unit_id: Unit identifier
            plant_id: Plant identifier
            
        Returns:
            True if successful
        """
        try:
            # Verify plant exists and belongs to unit
            plant = self.get_plant(plant_id, unit_id=unit_id)
            if not plant:
                logger.error(f"Plant {plant_id} not found")
                return False
            
            # Update in-memory active plant tracking
            with self._plants_lock:
                unit_plants = self._plants.get(unit_id, {})
                if plant_id not in unit_plants:
                    logger.error(f"Plant {plant_id} does not belong to unit {unit_id}")
                    return False
                self._active_plants[unit_id] = plant_id
                logger.debug("Set active plant to %s for unit %s", plant_id, unit_id)

            # Persist active plant in DB
            try:
                if hasattr(self.plant_repo, "set_active_plant"):
                    self.plant_repo.set_active_plant(plant_id)
            except Exception as exc:
                logger.debug(f"Failed to persist active plant {plant_id}: {exc}", exc_info=True)

            # Notify GrowthService to apply plant overrides to runtime and trigger AI conditions
            # GrowthService subscribes to this event
            self.event_bus.publish(
                PlantEvent.ACTIVE_PLANT_CHANGED,
                PlantLifecyclePayload(unit_id=unit_id, plant_id=plant_id),
            )
            
            # Activity logging
            if self.activity_logger:
                from app.services.application.activity_logger import ActivityLogger
                self.activity_logger.log_activity(
                    activity_type=ActivityLogger.PLANT_UPDATED,
                    description=f"Set active plant to '{getattr(plant, 'plant_name', 'Unknown')}' in unit {unit_id}",
                    severity=ActivityLogger.INFO,
                    entity_type="plant",
                    entity_id=plant_id,
                    metadata={"plant_type": getattr(plant, 'plant_type', 'Unknown') or 'Unknown', "unit_id": unit_id},
                )
            
            logger.info(f"Set plant {plant_id} as active in unit {unit_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error setting active plant {plant_id} in unit {unit_id}: {e}", exc_info=True)
            return False
    
    def update_plant_stage(
        self,
        plant_id: int,
        new_stage: str,
        days_in_stage: int = 0,
        *,
        skip_threshold_proposal: bool = False,
    ) -> bool:
        """
        Update plant growth stage.
        
        When stage changes, proposes new thresholds based on stage-specific
        requirements and sends notification for user confirmation.
        
        Args:
            plant_id: Plant identifier
            new_stage: New growth stage
            days_in_stage: Days in new stage
            
        Returns:
            True if successful
        """
        try:
            plant = self.get_plant(plant_id)
            if not plant:
                logger.error(f"Plant {plant_id} not found")
                return False

            unit_id = plant.unit_id
            if not unit_id:
                logger.error(f"Plant {plant_id} has no unit_id")
                return False

            old_stage = plant.current_stage
            
            # Update the in-memory PlantProfile directly
            plant.set_stage(new_stage, days_in_stage)
            moisture_level = plant.moisture_level

            self.plant_repo.update_plant_progress(
                plant_id=plant_id,
                current_stage=new_stage,
                moisture_level=moisture_level,
                days_in_stage=days_in_stage,
            )

            plant_name = plant.plant_name or "Unknown"
            plant_type = plant.plant_type or "Unknown"
            # Log activity
            if self.activity_logger:
                from app.services.application.activity_logger import ActivityLogger
                self.activity_logger.log_activity(
                    activity_type=ActivityLogger.PLANT_UPDATED,
                    description=f"Updated {plant_type} plant '{plant_name}' to unit {unit_id}",
                    severity=ActivityLogger.INFO,
                    entity_type="plant",
                    entity_id=plant_id,
                    metadata={"plant_type": plant_type, "unit_id": unit_id, "stage": new_stage}
                )

            try:
                payload = PlantStageUpdatePayload(plant_id=plant_id, new_stage=new_stage, days_in_stage=days_in_stage)
                self.event_bus.publish(PlantEvent.PLANT_STAGE_UPDATE, payload)
            except Exception:
                logger.debug("Event bus publish failed for plant %s stage update", plant_id, exc_info=True)

            # Propose threshold update if stage changed
            if not skip_threshold_proposal and old_stage and old_stage.lower() != new_stage.lower():
                self._propose_stage_thresholds(plant, old_stage, new_stage)

            logger.info(f"Updated plant {plant_id} to stage '{new_stage}'")
            return True

        except Exception as e:
            logger.error(f"Error updating plant {plant_id} stage: {e}", exc_info=True)
            return False

    def _propose_stage_thresholds(
        self,
        plant: PlantProfile,
        old_stage: str,
        new_stage: str,
        *,
        seed_overrides: Optional[Dict[str, float]] = None,
        force: bool = False,
    ) -> None:
        """
        Propose new thresholds when plant enters a new growth stage.
        
        Sends notification with Apply/Keep Current/Customize options.
        
        Args:
            plant: The plant profile
            old_stage: Previous growth stage
            new_stage: New growth stage
        """
        if not self.threshold_service or not self.notifications_service:
            logger.debug(
                "Threshold proposal skipped - threshold_service or notifications_service not available"
            )
            return

        try:
            plant_type = plant.plant_type or "default"
            user_id = self._get_unit_owner(plant.unit_id)

            # Get optimal thresholds for new stage via ThresholdService
            new_thresholds = self.threshold_service.get_thresholds(
                plant_type,
                new_stage,
                user_id=user_id,
                profile_id=getattr(plant, "condition_profile_id", None),
                preferred_mode=getattr(plant, "condition_profile_mode", None),
                plant_variety=plant.plant_variety,
                strain_variety=plant.strain_variety,
                pot_size_liters=plant.pot_size_liters,
            )
            proposed_map = new_thresholds.to_settings_dict()
            if seed_overrides:
                for key, value in seed_overrides.items():
                    if key in proposed_map:
                        proposed_map[key] = value

            current_env = self.threshold_service.get_unit_thresholds_dict(plant.unit_id)
            if not current_env:
                logger.debug("No current thresholds for unit %s, using generic", plant.unit_id)
                current_env = self.threshold_service.generic_thresholds.to_settings_dict()

            threshold_comparison: Dict[str, Dict[str, float]] = {}
            for key in THRESHOLD_KEYS:
                proposed_value = proposed_map.get(key)
                if proposed_value is None:
                    continue
                current_value = current_env.get(key)
                if current_value is None:
                    current_value = proposed_value
                tolerance = THRESHOLD_UPDATE_TOLERANCE.get(key, 0.0)
                if force or abs(proposed_value - current_value) >= tolerance:
                    threshold_comparison[key] = {
                        "current": float(current_value),
                        "proposed": float(proposed_value),
                    }

            soil_proposed = proposed_map.get("soil_moisture_threshold")
            if soil_proposed is not None:
                current_soil = plant.soil_moisture_threshold_override
                if current_soil is None:
                    current_soil = soil_proposed
                tolerance = THRESHOLD_UPDATE_TOLERANCE.get("soil_moisture_threshold", 2.0)
                if force or abs(float(soil_proposed) - float(current_soil)) >= tolerance:
                    threshold_comparison["soil_moisture_threshold"] = {
                        "current": float(current_soil),
                        "proposed": float(soil_proposed),
                    }

            if not threshold_comparison:
                logger.debug(
                    "No significant threshold changes for stage %s -> %s",
                    old_stage, new_stage
                )
                return
            
            # Send notification
            self._send_threshold_proposal_notification(
                plant=plant,
                old_stage=old_stage,
                new_stage=new_stage,
                comparison=threshold_comparison,
                proposed_thresholds=new_thresholds,
            )
            
            logger.info(
                "Sent threshold proposal notification for plant %s stage %s -> %s",
                plant.plant_id, old_stage, new_stage
            )
            
        except Exception as e:
            logger.error(
                "Error proposing stage thresholds for plant %s: %s",
                plant.plant_id, e, exc_info=True
            )

    def _send_threshold_proposal_notification(
        self,
        plant: PlantProfile,
        old_stage: str,
        new_stage: str,
        comparison: Dict[str, Dict[str, float]],
        proposed_thresholds: Any,
    ) -> None:
        """
        Send notification for threshold proposal with action buttons.
        
        Args:
            plant: The plant profile
            old_stage: Previous growth stage
            new_stage: New growth stage
            comparison: Dict of parameter -> {current, proposed} values
            proposed_thresholds: EnvironmentalThresholds object for the new stage
        """
        from app.enums import NotificationType, NotificationSeverity
        
        # Get user_id from unit
        user_id = self._get_unit_owner(plant.unit_id)
        if not user_id:
            logger.warning("Cannot send threshold proposal - no owner for unit %s", plant.unit_id)
            return
        
        # Format comparison for message
        metric_meta = {
            "temperature_threshold": ("Temperature", "°C", 1),
            "humidity_threshold": ("Humidity", "%", 1),
            "soil_moisture_threshold": ("Soil Moisture", "%", 1),
            "co2_threshold": ("CO₂", "ppm", 0),
            "voc_threshold": ("VOC", "ppb", 0),
            "lux_threshold": ("Light", "lux", 0),
            "air_quality_threshold": ("Air Quality", "AQI", 0),
        }
        changes = []
        for param, values in comparison.items():
            diff = values["proposed"] - values["current"]
            if abs(diff) > 0.5:  # Only show meaningful changes
                direction = "↑" if diff > 0 else "↓"
                name, unit, precision = metric_meta.get(
                    param, (param.replace("_", " ").title(), "", 1)
                )
                fmt = f"{{:.{precision}f}}"
                current_str = fmt.format(values["current"])
                proposed_str = fmt.format(values["proposed"])
                suffix = f" {unit}" if unit else ""
                changes.append(
                    f"{name}: {current_str}{suffix} → {proposed_str}{suffix} {direction}"
                )
        
        if not changes:
            return
        
        plant_name = plant.plant_name or "Unknown"
        if old_stage and old_stage.lower() != new_stage.lower():
            header = f"Plant '{plant_name}' moved from {old_stage} to {new_stage}."
        else:
            header = f"Plant '{plant_name}' is in {new_stage} stage."
        message = header + " Recommended threshold changes:\n" + "\n".join(changes)

        actions = ["apply", "keep_current", "customize"]
        if old_stage and old_stage.lower() != new_stage.lower():
            actions.append("delay_stage")
        
        self.notifications_service.send_notification(
            user_id=user_id,
            notification_type=NotificationType.THRESHOLD_PROPOSAL,
            title=f"🌱 Threshold Update for {plant_name}",
            message=message,
            severity=NotificationSeverity.INFO,
            unit_id=plant.unit_id,
            requires_action=True,
            action_type="threshold_proposal",
            action_data={
                "plant_id": plant.plant_id,
                "unit_id": plant.unit_id,
                "old_stage": old_stage,
                "new_stage": new_stage,
                "proposed_thresholds": comparison,
                "actions": actions,
            },
        )

    def _get_unit_owner(self, unit_id: int) -> Optional[int]:
        """
        Get the owner user_id for a unit.
        
        Args:
            unit_id: Unit identifier
            
        Returns:
            User ID or None
        """
        try:
            unit = self.unit_repo.get_unit(unit_id)
            if unit:
                return unit.get("user_id")
        except Exception as e:
            logger.error("Error getting unit owner for %s: %s", unit_id, e)
        return None
    
    # ==================== Private Helper Methods ====================
    
    def _handle_soil_moisture_update(self, payload: Dict[str, Any]) -> None:
        """
        Handle soil moisture sensor data updates.
        
        Args:
            payload: Sensor event payload with unit_id, sensor_id, soil_moisture
        """
        try:
            unit_id = payload.get("unit_id")
            if unit_id is None:
                logger.warning("Soil moisture update missing unit_id")
                return
            sensor_id = payload.get("sensor_id")
            moisture_level = payload.get("soil_moisture")
            if moisture_level is None:
                moisture_level = payload.get("moisture_level")
            if sensor_id is None or moisture_level is None:
                logger.warning("Soil moisture update missing sensor_id or moisture_level")
                return
            
            # Check if unit is loaded in memory
            if not self.is_unit_loaded(unit_id):
                logger.warning(f"Unit {unit_id} not loaded in memory; cannot update soil moisture")
                return
            
            plant_ids = self.plant_repo.get_plants_for_sensor(sensor_id)
            for plant_id in plant_ids:
                self.plant_repo.update_plant_moisture_by_id(plant_id, moisture_level)

                # Update in-memory PlantProfile directly
                plant = self.get_plant(plant_id, unit_id)
                if plant:
                    plant.moisture_level = moisture_level
                    logger.debug(
                        "Updated moisture level for plant %s to %.2f%% in runtime",
                        plant_id,
                        moisture_level,
                    )
                logger.debug(
                    "Updated moisture level for plant %s to %.2f%% in database",
                    plant_id,
                    moisture_level,
                )
                
        except Exception as e:
            logger.error(f"Error handling soil moisture update: {e}", exc_info=True)

    def _generate_friendly_name(self, sensor: Dict[str, Any]) -> str:
        """
        Generate a user-friendly sensor name.
        
        Examples:
        - "Soil Moisture (GPIO Pin 17)"
        - "Soil Moisture (MQTT: growtent/sensor/soil_0)"
        - "Soil Moisture (ESP32-C6: grow-sensor-01)"
        
        Args:
            sensor: Sensor dictionary
            
        Returns:
            Friendly name string
        """
        try:
            # Base name from sensor type
            sensor_type = sensor.get('sensor_type', 'UNKNOWN')
            base_name = sensor_type.replace('_', ' ').title()
            
            # Get protocol and config
            protocol = str(sensor.get('protocol', 'GPIO') or 'GPIO')
            config_data = sensor.get('config', {}) or {}
            
            # Generate suffix based on protocol
            if protocol.upper() == 'GPIO':
                gpio = config_data.get('gpio_pin')
                if gpio is None:
                    gpio = config_data.get('gpio')
                if gpio is not None:
                    return f"{base_name} (GPIO Pin {gpio})"
                else:
                    return f"{base_name} (GPIO)"
                    
            elif protocol.lower() in ('mqtt', 'zigbee2mqtt', 'zigbee'):
                mqtt_topic = config_data.get('mqtt_topic', 'unknown')
                device_id = config_data.get('esp32_device_id') or config_data.get('device_id')
                
                if device_id:
                    # ESP32-C6 virtual sensor
                    return f"{base_name} (ESP32-C6: {device_id})"
                else:
                    # Regular MQTT sensor
                    # Shorten topic for readability
                    topic_parts = mqtt_topic.split('/')
                    short_topic = '/'.join(topic_parts[-2:]) if len(topic_parts) > 2 else mqtt_topic
                    return f"{base_name} (MQTT: {short_topic})"
                    
            elif protocol == 'WIRELESS':
                address = config_data.get('address', 'unknown')
                return f"{base_name} (Wireless: {address})"
                
            else:
                # Fallback
                sensor_id = sensor.get('sensor_id')
                return f"{base_name} (ID: {sensor_id})"
                
        except Exception as e:
            logger.warning(f"Error generating friendly name: {e}")
            return f"Sensor #{sensor.get('sensor_id', 'unknown')}"
    
    def _is_sensor_linked(self, sensor_id: int) -> bool:
        """
        Check if a sensor is already linked to any plant.
        
        Note: Currently returns False (allows sensor sharing).
        TODO: Implement actual database check if exclusive linking is needed.
        
        Args:
            sensor_id: Sensor identifier
            
        Returns:
            True if sensor is linked to a plant
        """
        try:
            # Allow sensor sharing for now
            return False
            
        except Exception as e:
            logger.warning(f"Error checking if sensor {sensor_id} is linked: {e}")
            return False
    
    # ==================== Plant Context Resolution ====================
    
    def get_plant_context_for_sensor(
        self,
        *,
        unit_id: int,
        sensor_id: int,
    ) -> Dict[str, Any]:
        """
        Resolve plant-specific context for a sensor (typically soil moisture).
        
        Returns plant metadata, target thresholds, and actuator assignments for
        the plant linked to the specified sensor.
        
        Args:
            unit_id: Unit identifier
            sensor_id: Sensor identifier
            
        Returns:
            Dictionary with plant context:
            - plant_id: Plant database ID
            - plant_name: Plant display name
            - plant_type: Plant species/type
            - growth_stage: Current growth stage
            - plant_stage: Alias for growth_stage
            - user_id: Unit owner ID
            - target_moisture: Target moisture threshold (optional)
            - actuator_id: Linked actuator ID (optional)
            - plant_pump_assigned: Whether a pump is assigned
        """
        try:
            plants = self.list_plants(unit_id=unit_id)
            for plant in plants:
                linked_sensor_id = plant.get_sensor_id()
                if sensor_id in linked_sensor_id:
                    plant_id = plant.plant_id
                    plant_name = plant.plant_name
                    plant_type = plant.plant_type
                    growth_stage = plant.current_stage
                    
                    # Resolve target moisture threshold
                    target_moisture = self._resolve_target_moisture(
                        plant_id=plant_id,
                        plant_profile=plant,
                        plant_data={}, #can be removed
                        plant_type=plant_type,
                        growth_stage=growth_stage,
                        unit_id=unit_id,
                    )
                    
                    # Resolve actuator assignment
                    actuator_id, plant_pump_assigned = self._resolve_plant_actuator(plant_id)
                    if actuator_id is None:
                        actuator_id = self._resolve_unit_pump_actuator(unit_id)
                    
                    # Get user_id from unit runtime or DB
                    user_id = None
                    runtime = self.growth_service.get_unit_runtime(unit_id)
                    if runtime:
                        user_id = runtime.user_id

                    context: Dict[str, Any] = {
                        "plant_id": plant_id,
                        "plant_name": plant_name,
                        "plant_type": plant_type,
                        "growth_stage": growth_stage,
                        "plant_stage": growth_stage,
                        "user_id": user_id,
                        "plant_pump_assigned": plant_pump_assigned,
                    }
                    
                    if target_moisture is not None:
                        context["target_moisture"] = target_moisture
                    if actuator_id is not None:
                        context["actuator_id"] = actuator_id
                    
                    return context
        except Exception as exc:
            logger.debug(f"Failed to resolve plant ids for sensor {sensor_id}: {exc}", exc_info=True)
            return {}
    
    def _resolve_target_moisture(
        self,
        *,
        plant_id: int,
        plant_profile: Optional[PlantProfile],
        plant_data: Dict[str, Any],
        plant_type: Optional[str],
        growth_stage: Optional[str],
        unit_id: int,
    ) -> Optional[float]:
        """
        Resolve target moisture threshold with fallback hierarchy.
        
        Priority:
        1. Plant-specific override (PlantProfile or DB)
        2. Plant catalog default (PlantJsonHandler)
        """
        # Check plant override (plant-owned soil moisture threshold)
        override_value = None

        if plant_profile and plant_profile.soil_moisture_threshold_override is not None:
            override_value = plant_profile.soil_moisture_threshold_override
        elif plant_data.get("soil_moisture_threshold_override") is not None:
            override_value = plant_data.get("soil_moisture_threshold_override")

        if override_value is not None:
            try:
                return float(override_value)
            except (TypeError, ValueError):
                pass

        plant_name = None
        if plant_profile and plant_profile.plant_name:
            plant_name = plant_profile.plant_name
        elif plant_data:
            plant_name = plant_data.get("plant_name") or plant_data.get("name")

        if plant_type or plant_name:
            value = self._resolve_initial_soil_moisture_threshold(
                plant_type=plant_type or plant_name or "",
                plant_name=plant_name or plant_type or "",
            )
            if value is not None:
                return value

        return None
    
    def _resolve_plant_actuator(self, plant_id: int) -> tuple[Optional[int], bool]:
        """
        Resolve actuator (pump) assignment for a plant.
        
        Returns:
            Tuple of (actuator_id, plant_pump_assigned)
        """
        try:
            actuator_ids = self.plant_repo.get_actuators_for_plant(plant_id)
        except Exception as exc:
            logger.debug(f"Failed to resolve actuators for plant {plant_id}: {exc}", exc_info=True)
            return None, False

        if not actuator_ids:
            return None, False

        # Find water pump actuator
        actuator_id = None
        if self.devices_repo:
            for candidate in actuator_ids:
                actuator = self.devices_repo.get_actuator_config_by_id(candidate)
                if not actuator:
                    continue
                actuator_type = self._normalize_actuator_type(actuator.get("actuator_type"))
                if actuator_type == ActuatorType.PUMP:
                    actuator_id = candidate
                    break
        
        if actuator_id is None:
            return None, False

        return actuator_id, True

    def _resolve_unit_pump_actuator(self, unit_id: int) -> Optional[int]:
        """Resolve a unit-level pump actuator if no plant-specific pump is set."""
        if not self.devices_repo:
            return None
        try:
            actuators = self.devices_repo.list_actuator_configs(unit_id=unit_id)
        except Exception as exc:
            logger.debug("Failed to list actuators for unit %s: %s", unit_id, exc, exc_info=True)
            return None

        for actuator in actuators or []:
            actuator_type = self._normalize_actuator_type(actuator.get("actuator_type"))
            if actuator_type == ActuatorType.PUMP:
                actuator_id = actuator.get("actuator_id")
                if actuator_id is not None:
                    return int(actuator_id)
        return None

    def get_plant_valve_actuator_id(self, plant_id: int) -> Optional[int]:
        """Resolve a valve actuator linked to a plant, if any."""
        try:
            actuator_ids = self.plant_repo.get_actuators_for_plant(plant_id)
        except Exception as exc:
            logger.debug(f"Failed to resolve actuators for plant {plant_id}: {exc}", exc_info=True)
            return None

        if not actuator_ids or not self.devices_repo:
            return None

        for candidate in actuator_ids:
            actuator = self.devices_repo.get_actuator_config_by_id(candidate)
            if not actuator:
                continue
            actuator_type = self._normalize_actuator_type(actuator.get("actuator_type"))
            if actuator_type == ActuatorType.VALVE:
                return candidate
        return None
    
    # ==================== Plant Species Metadata (delegates to PlantJsonHandler) ====================
    
    def get_plant_growth_stages(self, plant_type: str) -> List[Dict[str, Any]]:
        """
        Get growth stages for a plant type.
        
        Delegates to PlantJsonHandler (single source of truth for plant species data).
        
        Args:
            plant_type: Plant species/type name
            
        Returns:
            List of growth stage dictionaries
        """
        return self.plant_json_handler.get_growth_stages(plant_type)
    
    def get_plant_lighting_schedule(self, plant_type: str) -> Dict[str, Dict[str, Any]]:
        """
        Get lighting schedule for a plant type.
        
        Delegates to PlantJsonHandler (single source of truth for plant species data).
        
        Args:
            plant_type: Plant species/type name
            
        Returns:
            Dictionary mapping stage names to lighting settings
        """
        return self.plant_json_handler.get_lighting_schedule(plant_type)
    
    def get_plant_lighting_for_stage(
        self, plant_type: str, stage: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get lighting settings for a specific growth stage.
        
        Delegates to PlantJsonHandler (single source of truth for plant species data).
        
        Args:
            plant_type: Plant species/type name
            stage: Growth stage name
            
        Returns:
            Lighting settings dictionary or None if not found
        """
        return self.plant_json_handler.get_lighting_for_stage(plant_type, stage)
    
    def get_plant_automation_settings(self, plant_type: str) -> Dict[str, Any]:
        """
        Get automation settings for a plant type.
        
        Delegates to PlantJsonHandler (single source of truth for plant species data).
        
        Args:
            plant_type: Plant species/type name
            
        Returns:
            Automation settings dictionary
        """
        return self.plant_json_handler.get_automation_settings(plant_type)
    
    def get_plant_watering_schedule(self, plant_type: str) -> Dict[str, Any]:
        """
        Get watering schedule for a plant type.
        
        Delegates to PlantJsonHandler (single source of truth for plant species data).
        
        Args:
            plant_type: Plant species/type name
            
        Returns:
            Watering schedule dictionary
        """
        return self.plant_json_handler.get_watering_schedule(plant_type)
    
    def get_plant_gdd_base_temp(self, plant_type: str) -> Optional[float]:
        """
        Get GDD base temperature for a plant type.
        
        Delegates to PlantJsonHandler (single source of truth for plant species data).
        
        Args:
            plant_type: Plant species/type name
            
        Returns:
            Base temperature in Celsius or None if not available
        """
        return self.plant_json_handler.get_gdd_base_temp_c(plant_type)
    
    def get_plant_info(self, plant_type: str) -> Optional[Dict[str, Any]]:
        """
        Get complete plant information for a plant type.
        
        Delegates to PlantJsonHandler (single source of truth for plant species data).
        Returns all metadata: growth stages, lighting, thresholds, companion plants, etc.
        
        Args:
            plant_type: Plant species/type name
            
        Returns:
            Complete plant info dictionary or None if not found
        """
        entry = self.plant_json_handler._find_plant_entry(plant_type)
        return entry
    
    def list_available_plant_types(self) -> List[str]:
        """
        List all available plant types in the catalog.
        
        Delegates to PlantJsonHandler (single source of truth for plant species data).
        
        Returns:
            List of plant type names
        """
        return self.plant_json_handler.list_plants()

    def __repr__(self) -> str:
        """String representation for debugging."""
        return "<PlantViewService>"


class PlantService(PlantViewService):
    """Backward-compatible alias for PlantViewService."""
    pass
