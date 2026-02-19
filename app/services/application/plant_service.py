"""
Plant Service
=============
Application-level service for managing plants and their sensor relationships.

This service provides plant-specific operations including:
- Plant CRUD operations (direct access to unit runtimes)
- Plant-sensor linking with validation (via PlantDeviceLinker)
- Available sensors discovery with friendly names
- Plant status and monitoring
- Growth-stage transitions and threshold proposals (via PlantStageManager)

Responsibilities:
- Own plant/sensor linking and in-memory plant state (single source of truth)
- Delegate unit-level lifecycle persistence (add/remove) to GrowthService for consistency
- Access unit runtimes via GrowthService.get_unit_runtime() when needed
- Coordinate with SensorManagementService for sensor information
- Generate friendly sensor names for UI
- Validate plant-sensor compatibility

Architecture (audit item #8):
- PlantDeviceLinker: sensor/actuator linking operations
- PlantStageManager: stage transitions, threshold proposals, condition profiles
- PlantViewService: CRUD, cache, metadata delegation, and thin façade
"""

from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING, Any

from app.domain.plant_profile import PlantProfile
from app.enums.device import ActuatorType
from app.services.application.plant_device_linker import PlantDeviceLinker
from app.services.application.plant_stage_manager import PlantStageManager

if TYPE_CHECKING:
    from app.services.application.activity_logger import ActivityLogger
    from app.services.application.growth_service import GrowthService
    from app.services.application.notifications_service import NotificationsService
    from app.services.application.threshold_service import ThresholdService
    from app.services.hardware import SensorManagementService
    from app.utils.plant_json_handler import PlantJsonHandler

from app.enums.common import ConditionProfileMode, ConditionProfileTarget
from app.enums.events import PlantEvent, SensorEvent
from app.schemas.events import PlantLifecyclePayload
from app.utils.event_bus import EventBus

logger = logging.getLogger(__name__)


def _row_to_dict(row) -> dict[str, Any]:
    """Convert database row to dictionary."""
    if row is None:
        return {}
    if isinstance(row, dict):
        return row
    return {k: row[k] for k in row}


class PlantViewService:
    """
    Application service for plant management and viewing.

    This service owns plant read/update operations and accesses unit runtimes directly.
    It does NOT delegate plant operations to GrowthService.

    Renamed from PlantService to PlantViewService to clarify its role:
    - Views: list_plants, get_plant, get_plant_sensors
    - Updates: update_plant, update_plant_stage, link/unlink sensors
    - Lifecycle (create/remove) via GrowthService delegation

    Architecture (audit item #8 — god-class split):
    - Device linking delegated to ``PlantDeviceLinker``
    - Stage transitions / threshold proposals delegated to ``PlantStageManager``
    - CRUD, cache, metadata delegation stay here
    """

    def __init__(
        self,
        growth_service: "GrowthService",
        sensor_service: "SensorManagementService",
        plant_repo: Any | None = None,
        unit_repo: Any | None = None,
        event_bus: EventBus | None = None,
        activity_logger: "ActivityLogger" | None = None,
        plant_json_handler: "PlantJsonHandler" | None = None,
        threshold_service: "ThresholdService" | None = None,
        notifications_service: "NotificationsService" | None = None,
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

        # ==================== Extracted Helpers (audit item #8) ====================
        self._device_linker = PlantDeviceLinker(
            plant_repo=plant_repo,
            sensor_service=sensor_service,
            devices_repo=self.devices_repo,
            audit_logger=self.audit_logger,
        )
        self._stage_manager = PlantStageManager(
            plant_repo=plant_repo,
            event_bus=self.event_bus,
            threshold_service=threshold_service,
            notifications_service=notifications_service,
            activity_logger=activity_logger,
        )
        self._stage_manager.set_unit_repo(unit_repo)

        # ==================== In-Memory Plant Storage ====================
        # Primary plant storage: unit_id -> {plant_id: PlantProfile}
        # This is the single source of truth for plant state
        self._plants: dict[int, dict[int, PlantProfile]] = {}
        self._plants_lock = threading.Lock()

        # Track active plant per unit: unit_id -> plant_id
        self._active_plants: dict[int, int] = {}

        self.event_bus.subscribe(SensorEvent.SOIL_MOISTURE_UPDATE, self._handle_soil_moisture_update)

        logger.info("PlantViewService initialized with in-memory plant storage")

    # ==================== Plant JSON Handler ====================

    @property
    def plant_json_handler(self) -> "PlantJsonHandler":
        """Lazy-load PlantJsonHandler if not provided at init."""
        if self._plant_json_handler is None:
            from app.utils.plant_json_handler import PlantJsonHandler

            self._plant_json_handler = PlantJsonHandler()
        return self._plant_json_handler

    # ==================== In-Memory Plant Management ====================

    def _get_unit_plants(self, unit_id: int) -> dict[int, PlantProfile]:
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

    def get_active_plant(self, unit_id: int) -> PlantProfile | None:
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
        plant_species: str | None = None,
        plant_variety: str | None = None,
        days_in_stage: int = 0,
        moisture_level: float = 0.0,
        growth_stages: Any | None = None,
        lighting_schedule: dict[str, dict[str, Any]] | None = None,
        pot_size_liters: float = 0.0,
        pot_material: str = "plastic",
        growing_medium: str = "soil",
        medium_ph: float = 7.0,
        strain_variety: str | None = None,
        expected_yield_grams: float = 0.0,
        light_distance_cm: float = 0.0,
        gdd_base_temp_c: float | None = None,
        soil_moisture_threshold_override: float | None = None,
        condition_profile_id: str | None = None,
        condition_profile_mode: ConditionProfileMode | None = None,
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
            except (KeyError, TypeError, ValueError, OSError) as e:
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
            except (KeyError, TypeError, ValueError, OSError) as e:
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
            except (KeyError, TypeError, ValueError, OSError) as e:
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

    def load_plants_for_unit(self, unit_id: int, active_plant_id: int | None = None) -> int:
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

        except (KeyError, TypeError, ValueError, OSError) as e:
            logger.error("Error loading plants for unit %s: %s", unit_id, e, exc_info=True)
            return 0

    # ==================== Plant CRUD Operations ====================

    def list_plants(self, unit_id: int) -> list[PlantProfile]:
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

        except (KeyError, TypeError, ValueError, OSError) as e:
            logger.error("Error listing plants for unit %s: %s", unit_id, e, exc_info=True)
            return []

    def list_plants_as_dicts(self, unit_id: int) -> list[dict[str, Any]]:
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
            result: list[dict[str, Any]] = []

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

        except (KeyError, TypeError, ValueError, AttributeError) as e:
            logger.error("Error listing plants as dicts for unit %s: %s", unit_id, e, exc_info=True)
            return []

    def _resolve_initial_soil_moisture_threshold(
        self,
        *,
        plant_type: str,
        plant_name: str,
    ) -> float | None:
        """Resolve a starting soil moisture trigger for a new plant."""
        for name in (plant_type, plant_name):
            if not name:
                continue
            try:
                value = self.plant_json_handler.get_soil_moisture_trigger(name)
            except (KeyError, TypeError, ValueError, OSError) as exc:
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
        plant_variety: str | None,
        strain_variety: str | None,
        pot_size_liters: float | None,
    ) -> dict[str, float]:
        """Fetch the latest stored overrides for a matching plant context.  Delegates to PlantStageManager."""
        return self._stage_manager.resolve_historical_threshold_overrides(
            unit_id=unit_id,
            plant_type=plant_type,
            growth_stage=growth_stage,
            plant_variety=plant_variety,
            strain_variety=strain_variety,
            pot_size_liters=pot_size_liters,
        )

    def create_plant(
        self,
        unit_id: int,
        plant_name: str,
        plant_type: str,
        current_stage: str,
        plant_species: str | None = None,
        plant_variety: str | None = None,
        days_in_stage: int = 0,
        moisture_level: float = 0.0,
        sensor_ids: list[int] | None = None,
        soil_moisture_threshold_override: float | None = None,
        condition_profile_id: str | None = None,
        condition_profile_mode: ConditionProfileMode | None = None,
        condition_profile_name: str | None = None,
        # Creation-time fields
        pot_size_liters: float = 0.0,
        pot_material: str = "plastic",
        growing_medium: str = "soil",
        medium_ph: float = 7.0,
        strain_variety: str | None = None,
        expected_yield_grams: float = 0.0,
        light_distance_cm: float = 0.0,
    ) -> dict[str, Any] | None:
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
                except ValueError as e:
                    raise ValueError("Invalid condition profile mode") from e

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
                            if unit_profile and (
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
                logger.error("Failed to create plant '%s' in DB", plant_name)
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
            except (KeyError, TypeError, ValueError, OSError) as exc:
                logger.debug("Failed to assign plant %s to unit %s: %s", plant_id, unit_id, exc, exc_info=True)

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

            logger.info("Created plant %s: '%s' in unit %s", plant_id, plant_name, unit_id)

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
                    },
                )
            # Link sensors if provided
            linked_sensors = []
            if sensor_ids:
                for sensor_id in sensor_ids:
                    if self.link_plant_sensor(plant_id, sensor_id):
                        linked_sensors.append(sensor_id)
                        logger.info("Linked sensor %s to plant %s", sensor_id, plant_id)
                    else:
                        logger.warning("  x Failed to link sensor %s to plant %s", sensor_id, plant_id)

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

        except Exception as e:  # TODO(narrow): large method with DB + service + profile + event ops
            logger.error("Error creating plant '%s': %s", plant_name, e, exc_info=True)
            return None

    def update_plant(
        self,
        plant_id: int,
        plant_name: str | None = None,
        plant_type: str | None = None,
        plant_species: str | None = None,
        plant_variety: str | None = None,
        pot_size_liters: float | None = None,
        medium_ph: float | None = None,
        strain_variety: str | None = None,
        expected_yield_grams: float | None = None,
        light_distance_cm: float | None = None,
    ) -> dict[str, Any] | None:
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
                logger.error("Plant %s not found", plant_id)
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
                    except (KeyError, TypeError, ValueError, OSError) as exc:
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
                        metadata=update_fields,
                    )

                logger.info("Updated plant %s: %s", plant_id, update_fields)

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
        except Exception as e:  # TODO(narrow): DB + memory sync + activity logging
            logger.error("Error updating plant %s: %s", plant_id, e, exc_info=True)
            return None

    def update_soil_moisture_threshold(
        self,
        plant_id: int,
        threshold: float,
        unit_id: int | None = None,
    ) -> bool:
        """
        Update the per-plant soil moisture threshold override.
        Delegates to PlantStageManager.

        Args:
            plant_id: Plant identifier
            threshold: New soil moisture threshold (0-100)
            unit_id: Optional unit identifier (speeds up in-memory update)

        Returns:
            True if updated, False otherwise
        """
        plant = self.get_plant(plant_id, unit_id=unit_id)

        resolved_unit_id = unit_id
        if resolved_unit_id is None:
            with self._plants_lock:
                for uid, unit_plants in self._plants.items():
                    if plant_id in unit_plants:
                        resolved_unit_id = uid
                        break

        return self._stage_manager.update_soil_moisture_threshold(
            plant_id=plant_id,
            threshold=threshold,
            plant=plant,
            unit_id=resolved_unit_id,
        )

    def get_plant(self, plant_id: int, unit_id: int | None = None) -> PlantProfile | None:
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
                    for _uid, unit_plants in self._plants.items():
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

        except (KeyError, TypeError, ValueError, OSError) as e:
            logger.error("Error getting plant %s: %s", plant_id, e, exc_info=True)
            return None

    def apply_condition_profile_to_plant(
        self,
        *,
        plant_id: int,
        profile_id: str,
        mode: ConditionProfileMode | None = None,
        name: str | None = None,
        user_id: int | None = None,
    ) -> dict[str, Any] | None:
        """
        Apply a condition profile to an existing plant.
        Delegates to PlantStageManager.
        """
        plant = self.get_plant(plant_id)
        if not plant:
            return None

        resolved_unit_id = self._resolve_unit_id_for_plant(plant_id)

        return self._stage_manager.apply_condition_profile_to_plant(
            plant_id=plant_id,
            profile_id=profile_id,
            plant=plant,
            unit_id=resolved_unit_id,
            mode=mode,
            name=name,
            user_id=user_id,
        )

    def _resolve_unit_id_for_plant(self, plant_id: int) -> int | None:
        with self._plants_lock:
            for unit_id, unit_plants in self._plants.items():
                if plant_id in unit_plants:
                    return unit_id
        try:
            row = self.plant_repo.get_plant(plant_id)
        except (KeyError, TypeError, ValueError, OSError):
            return None
        if not row:
            return None
        if isinstance(row, dict):
            return row.get("unit_id")
        try:
            return row["unit_id"]
        except (KeyError, TypeError):
            return None

    def get_plant_as_dict(self, plant_id: int, unit_id: int | None = None) -> dict[str, Any] | None:
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

        except (KeyError, TypeError, ValueError, AttributeError) as e:
            logger.error("Error getting plant %s as dict: %s", plant_id, e, exc_info=True)
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
            plant_name: str | None = None
            plant_type: str | None = None

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
            except (KeyError, TypeError, ValueError, OSError) as exc:
                logger.debug("Failed to remove plant %s from DB: %s", plant_id, exc, exc_info=True)

            success = removed_from_memory or db_removed

            if success:
                try:
                    user_id = self._get_unit_owner(unit_id)
                    profile_service = (
                        getattr(self.threshold_service, "personalized_learning", None)
                        if self.threshold_service
                        else None
                    )
                    if user_id and profile_service:
                        profile_service.unlink_condition_profile(
                            user_id=user_id,
                            target_type=ConditionProfileTarget.PLANT,
                            target_id=int(plant_id),
                        )
                except (KeyError, TypeError, ValueError, AttributeError):
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

        except Exception as exc:  # TODO(narrow): large method with memory + DB + event + logging ops
            logger.error(
                f"Failed to remove plant {plant_id} from unit {unit_id}: {exc}",
                exc_info=True,
            )
            return False

    def link_plant_sensor(self, plant_id: int, sensor_id: int) -> bool:
        """Link a sensor to a plant with validation.  Delegates to PlantDeviceLinker."""
        plant = self.get_plant(plant_id)
        return self._device_linker.link_plant_sensor(plant_id, sensor_id, plant_profile=plant)

    def unlink_plant_sensor(self, plant_id: int, sensor_id: int) -> bool:
        """Unlink a sensor from a plant.  Delegates to PlantDeviceLinker."""
        plant = self.get_plant(plant_id)
        return self._device_linker.unlink_plant_sensor(plant_id, sensor_id, plant_profile=plant)

    def unlink_all_sensors_from_plant(self, plant_id: int) -> bool:
        """Unlink all sensors from a plant.  Delegates to PlantDeviceLinker."""
        return self._device_linker.unlink_all_sensors_from_plant(plant_id)

    def get_plant_sensor_ids(self, plant_id: int) -> list[int]:
        """Get sensor IDs linked to a plant.  Delegates to PlantDeviceLinker."""
        return self._device_linker.get_plant_sensor_ids(plant_id)

    def get_plant_sensors(self, plant_id: int) -> list[dict[str, Any]]:
        """Get full sensor details for all sensors linked to a plant.  Delegates to PlantDeviceLinker."""
        return self._device_linker.get_plant_sensors(plant_id)

    # ==================== Plant Actuator Linking (delegates to PlantDeviceLinker) ====================

    @staticmethod
    def _normalize_actuator_type(value: Any) -> "ActuatorType":
        """Normalize actuator type values to infrastructure ActuatorType.  Delegates to PlantDeviceLinker."""
        return PlantDeviceLinker._normalize_actuator_type(value)

    def link_plant_actuator(self, plant_id: int, actuator_id: int) -> bool:
        """Link an actuator to a plant.  Delegates to PlantDeviceLinker."""
        return self._device_linker.link_plant_actuator(plant_id, actuator_id, get_plant_fn=self.get_plant)

    def unlink_plant_actuator(self, plant_id: int, actuator_id: int) -> bool:
        """Unlink an actuator from a plant.  Delegates to PlantDeviceLinker."""
        return self._device_linker.unlink_plant_actuator(plant_id, actuator_id)

    def get_plant_actuator_ids(self, plant_id: int) -> list[int]:
        """Get actuator IDs linked to a plant.  Delegates to PlantDeviceLinker."""
        return self._device_linker.get_plant_actuator_ids(plant_id)

    def get_plant_actuators(self, plant_id: int) -> list[dict[str, Any]]:
        """Get actuator details linked to a plant.  Delegates to PlantDeviceLinker."""
        return self._device_linker.get_plant_actuators(plant_id)

    def get_available_actuators_for_plant(
        self,
        unit_id: int,
        actuator_type: str = "pump",
    ) -> list[dict[str, Any]]:
        """List available actuators for linking to plants.  Delegates to PlantDeviceLinker."""
        return self._device_linker.get_available_actuators_for_plant(unit_id, actuator_type)

    # ==================== Available Sensors Discovery (delegates to PlantDeviceLinker) ====================

    def get_available_sensors_for_plant(self, unit_id: int, sensor_type: str = "soil_moisture") -> list[dict[str, Any]]:
        """Get all sensors available for plant linking.  Delegates to PlantDeviceLinker."""
        return self._device_linker.get_available_sensors_for_plant(unit_id, sensor_type)

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
                logger.error("Plant %s not found", plant_id)
                return False

            # Update in-memory active plant tracking
            with self._plants_lock:
                unit_plants = self._plants.get(unit_id, {})
                if plant_id not in unit_plants:
                    logger.error("Plant %s does not belong to unit %s", plant_id, unit_id)
                    return False
                self._active_plants[unit_id] = plant_id
                logger.debug("Set active plant to %s for unit %s", plant_id, unit_id)

            # Persist active plant in DB
            try:
                if hasattr(self.plant_repo, "set_active_plant"):
                    self.plant_repo.set_active_plant(plant_id)
            except (KeyError, TypeError, ValueError, OSError) as exc:
                logger.debug("Failed to persist active plant %s: %s", plant_id, exc, exc_info=True)

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
                    metadata={"plant_type": getattr(plant, "plant_type", "Unknown") or "Unknown", "unit_id": unit_id},
                )

            logger.info("Set plant %s as active in unit %s", plant_id, unit_id)
            return True

        except Exception as e:  # TODO(narrow): memory + DB + event publish + activity logging
            logger.error("Error setting active plant %s in unit %s: %s", plant_id, unit_id, e, exc_info=True)
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
        Update plant growth stage.  Delegates to PlantStageManager.
        """
        plant = self.get_plant(plant_id)
        if not plant:
            logger.error("Plant %s not found", plant_id)
            return False

        return self._stage_manager.update_plant_stage(
            plant=plant,
            new_stage=new_stage,
            days_in_stage=days_in_stage,
            skip_threshold_proposal=skip_threshold_proposal,
        )

    def _propose_stage_thresholds(
        self,
        plant: PlantProfile,
        old_stage: str,
        new_stage: str,
        *,
        seed_overrides: dict[str, float] | None = None,
        force: bool = False,
    ) -> None:
        """Propose new thresholds when plant enters a new stage.  Delegates to PlantStageManager."""
        self._stage_manager._propose_stage_thresholds(
            plant,
            old_stage,
            new_stage,
            seed_overrides=seed_overrides,
            force=force,
        )

    def _send_threshold_proposal_notification(
        self,
        plant: PlantProfile,
        old_stage: str,
        new_stage: str,
        comparison: dict[str, dict[str, float]],
        proposed_thresholds: Any,
    ) -> None:
        """Send notification for threshold proposal.  Delegates to PlantStageManager."""
        self._stage_manager._send_threshold_proposal_notification(
            plant=plant,
            old_stage=old_stage,
            new_stage=new_stage,
            comparison=comparison,
            proposed_thresholds=proposed_thresholds,
        )

    def _get_unit_owner(self, unit_id: int) -> int | None:
        """
        Get the owner user_id for a unit.

        Args:
            unit_id: Unit identifier

        Returns:
            User ID or None
        """
        try:
            unit = self.unit_repo.get_unit(unit_id)
            if not unit:
                return None
            if isinstance(unit, dict):
                return unit.get("user_id")
            try:
                return unit["user_id"]
            except (TypeError, KeyError):
                return getattr(unit, "user_id", None)
        except (KeyError, TypeError, ValueError, OSError) as e:
            logger.error("Error getting unit owner for %s: %s", unit_id, e)
        return None

    # ==================== Private Helper Methods ====================

    def _handle_soil_moisture_update(self, payload: dict[str, Any]) -> None:
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
                logger.warning("Unit %s not loaded in memory; cannot update soil moisture", unit_id)
                return

            plant_ids = self.plant_repo.get_plants_for_sensor(sensor_id)

            # Batch DB write — single transaction instead of N individual writes
            if plant_ids:
                self.plant_repo.bulk_update_plant_moisture(plant_ids, moisture_level)

            for plant_id in plant_ids:
                # Update in-memory PlantProfile directly
                plant = self.get_plant(plant_id, unit_id)
                if plant:
                    plant.moisture_level = moisture_level
                    logger.debug(
                        "Updated moisture level for plant %s to %.2f%% in runtime",
                        plant_id,
                        moisture_level,
                    )

        except (KeyError, TypeError, ValueError, OSError) as e:
            logger.error("Error handling soil moisture update: %s", e, exc_info=True)

    def _generate_friendly_name(self, sensor: dict[str, Any]) -> str:
        """Generate a user-friendly sensor name.  Delegates to PlantDeviceLinker."""
        return PlantDeviceLinker._generate_friendly_name(sensor)

    def _is_sensor_linked(self, sensor_id: int) -> bool:
        """Check if a sensor is already linked to any plant.  Delegates to PlantDeviceLinker."""
        return PlantDeviceLinker._is_sensor_linked(sensor_id)

    # ==================== Plant Context Resolution ====================

    def get_plant_context_for_sensor(
        self,
        *,
        unit_id: int,
        sensor_id: int,
    ) -> dict[str, Any]:
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
                        plant_data={},  # can be removed
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

                    context: dict[str, Any] = {
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
        except Exception as exc:  # TODO(narrow): plant iteration + moisture/actuator resolution + runtime access
            logger.debug("Failed to resolve plant ids for sensor %s: %s", sensor_id, exc, exc_info=True)
            return {}

    def _resolve_target_moisture(
        self,
        *,
        plant_id: int,
        plant_profile: PlantProfile | None,
        plant_data: dict[str, Any],
        plant_type: str | None,
        growth_stage: str | None,
        unit_id: int,
    ) -> float | None:
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

    def _resolve_plant_actuator(self, plant_id: int) -> tuple:
        """Resolve actuator (pump) assignment for a plant.  Delegates to PlantDeviceLinker."""
        return self._device_linker.resolve_plant_actuator(plant_id)

    def _resolve_unit_pump_actuator(self, unit_id: int) -> int | None:
        """Resolve a unit-level pump actuator.  Delegates to PlantDeviceLinker."""
        return self._device_linker.resolve_unit_pump_actuator(unit_id)

    def get_plant_valve_actuator_id(self, plant_id: int) -> int | None:
        """Resolve a valve actuator linked to a plant.  Delegates to PlantDeviceLinker."""
        return self._device_linker.get_plant_valve_actuator_id(plant_id)

    # ==================== Plant Species Metadata (delegates to PlantJsonHandler) ====================
    # TODO: Consider caching results from PlantJsonHandler for performance if needed, since this may be called frequently by the UI.
    # and maybe its a good idea to let PlantJsonHandler handle all those methods directly instead of delegating from here, since
    # PlantJsonHandler is the single source of truth for plant species data. For now, we can keep this delegation layer in case we want to add additional logic later, but it does add some unnecessary indirection.
    def get_plant_growth_stages(self, plant_type: str) -> list[dict[str, Any]]:
        """
        Get growth stages for a plant type.

        Delegates to PlantJsonHandler (single source of truth for plant species data).

        Args:
            plant_type: Plant species/type name

        Returns:
            List of growth stage dictionaries
        """
        return self.plant_json_handler.get_growth_stages(plant_type)

    def get_plant_lighting_schedule(self, plant_type: str) -> dict[str, dict[str, Any]]:
        """
        Get lighting schedule for a plant type.

        Delegates to PlantJsonHandler (single source of truth for plant species data).

        Args:
            plant_type: Plant species/type name

        Returns:
            Dictionary mapping stage names to lighting settings
        """
        return self.plant_json_handler.get_lighting_schedule(plant_type)

    def get_plant_lighting_for_stage(self, plant_type: str, stage: str) -> dict[str, Any] | None:
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

    def get_plant_automation_settings(self, plant_type: str) -> dict[str, Any]:
        """
        Get automation settings for a plant type.

        Delegates to PlantJsonHandler (single source of truth for plant species data).

        Args:
            plant_type: Plant species/type name

        Returns:
            Automation settings dictionary
        """
        return self.plant_json_handler.get_automation_settings(plant_type)

    def get_plant_watering_schedule(self, plant_type: str) -> dict[str, Any]:
        """
        Get watering schedule for a plant type.

        Delegates to PlantJsonHandler (single source of truth for plant species data).

        Args:
            plant_type: Plant species/type name

        Returns:
            Watering schedule dictionary
        """
        return self.plant_json_handler.get_watering_schedule(plant_type)

    def get_plant_gdd_base_temp(self, plant_type: str) -> float | None:
        """
        Get GDD base temperature for a plant type.

        Delegates to PlantJsonHandler (single source of truth for plant species data).

        Args:
            plant_type: Plant species/type name

        Returns:
            Base temperature in Celsius or None if not available
        """
        return self.plant_json_handler.get_gdd_base_temp_c(plant_type)

    def get_plant_info(self, plant_type: str) -> dict[str, Any] | None:
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

    def list_available_plant_types(self) -> list[str]:
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
