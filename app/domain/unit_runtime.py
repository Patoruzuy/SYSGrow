"""
UnitRuntime - Domain Model for Growth Unit
===========================================

Represents a single growth unit with all its domain logic:
- Plant management (PlantProfile instances)
- Unit settings (thresholds, schedules)
- Active plant selection for climate control
- Coordinates with UnitRuntimeManager for hardware operations

This is a pure domain model - no HTTP/API concerns, no database calls.
It works with the infrastructure layer (UnitRuntimeManager) but doesn't depend on Flask.

Architecture:
    GrowthService (registry) -> UnitRuntime (domain) -> UnitRuntimeManager (hardware)

Author: Sebastian GOmez
Date: November 2025
"""
from __future__ import annotations

import logging
from typing import Dict, Optional, Any, TYPE_CHECKING
from dataclasses import dataclass
from datetime import datetime

from app.domain.plant_profile import PlantProfile
from app.utils.schedules import get_light_hours
from app.utils.event_bus import EventBus
from app.enums.events import PlantEvent, RuntimeEvent
from app.schemas.events import (
    ThresholdsUpdatePayload,
    PlantLifecyclePayload,
    ThresholdsProposedPayload,
    ActivePlantSetPayload,
)

if TYPE_CHECKING:
    from app.services.application.threshold_service import ThresholdService

logger = logging.getLogger(__name__)


@dataclass
class UnitDimensions:
    """Physical dimensions of a growth unit"""
    width: float   # cm
    height: float  # cm
    depth: float   # cm
    
    def to_dict(self) -> Dict[str, float]:
        return {
            "width": self.width,
            "height": self.height,
            "depth": self.depth,
            "volume_liters": (self.width * self.height * self.depth) / 1000
        }
    
    @staticmethod
    def from_dict(data: Dict[str, float]) -> Optional['UnitDimensions']:
        """Create UnitDimensions from dictionary"""
        if not data or 'width' not in data:
            return None
        return UnitDimensions(
            width=data['width'],
            height=data['height'],
            depth=data['depth']
        )

@dataclass
class UnitSettings:
    """Environmental settings for a growth unit (data-only)."""

    temperature_threshold: float = 24.0
    humidity_threshold: float = 50.0
    co2_threshold: float = 1000.0
    voc_threshold: float = 1000.0
    lux_threshold: float = 1000.0
    air_quality_threshold: float = 1000.0
    timezone: Optional[str] = None
    dimensions: Optional[UnitDimensions] = None
    camera_enabled: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "temperature_threshold": self.temperature_threshold,
            "humidity_threshold": self.humidity_threshold,
            "co2_threshold": self.co2_threshold,
            "voc_threshold": self.voc_threshold,
            "lux_threshold": self.lux_threshold,
            "air_quality_threshold": self.air_quality_threshold,
            "timezone": self.timezone,
            "dimensions": self.dimensions.to_dict() if hasattr(self.dimensions, "to_dict") else self.dimensions,
            "camera_enabled": self.camera_enabled,
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "UnitSettings":
        """Create UnitSettings from database row or dictionary."""
        # Import here to avoid circular dependency
        from infrastructure.utils.structured_fields import normalize_dimensions
        
        dimensions = normalize_dimensions(data.get("dimensions"))
        return UnitSettings(
            temperature_threshold=data.get("temperature_threshold", 24.0),
            humidity_threshold=data.get("humidity_threshold", 50.0),
            co2_threshold=data.get("co2_threshold", 1000.0),
            voc_threshold=data.get("voc_threshold", 1000.0),
            lux_threshold=data.get("lux_threshold", 1000.0),
            air_quality_threshold=data.get("air_quality_threshold", data.get("aqi_threshold", 1000.0)),
            timezone=data.get("timezone"),
            dimensions=UnitDimensions.from_dict(dimensions) if dimensions else None,
            camera_enabled=data.get("camera_enabled", False),
        )
    
class UnitRuntime:
    """
    Domain model for a single growth unit.

    Responsibilities:
    - Maintain unit settings (thresholds, schedules)
    - Active plant reference for climate control (set by GrowthService)
    - Apply AI-based environmental conditions
    - Coordinate with hardware layer (UnitRuntimeManager)

    This class contains pure domain logic - no HTTP/API concerns.

    Events emitted:
        - RuntimeEvent.THRESHOLDS_PROPOSED: Proposed thresholds awaiting approval
        - RuntimeEvent.ACTIVE_PLANT_SET: Request to set active plant
        - PlantEvent.ACTIVE_PLANT_CHANGED: Active plant changed notification
    """

    def __init__(
        self,
        unit_id: int,
        unit_name: str,
        location: str,
        user_id: int,
        settings: Optional[UnitSettings] = None,
        custom_image: Optional[str] = None,
        threshold_service: Optional['ThresholdService'] = None,
    ):
        """
        Initialize a growth unit runtime (pure domain model).

        Args:
            unit_id: Database ID of the unit
            unit_name: Display name
            location: Indoor/Outdoor/Greenhouse/Hydroponics
            user_id: Owner of the unit
            settings: Unit settings (thresholds, schedules, dimensions)
            custom_image: Optional custom image path
            threshold_service: Optional service for unified threshold management
            plants: IGNORED - Plants are managed by PlantService
        """
        self.unit_id = unit_id
        self.unit_name = unit_name
        self.location = location
        self.user_id = user_id
        self.custom_image = custom_image
        self.threshold_service = threshold_service

        # Hardware running state (set by GrowthService when starting/stopping)
        self._hardware_running = False
        
        # Active plant reference (set by GrowthService after PlantService lookup)
        # PlantService is the single source of truth for plant collections
        self.active_plant: Optional[PlantProfile] = None
        
        # Unit settings
        self.settings = settings or UnitSettings()
        
        # AI and events
        self.event_bus = EventBus().get_instance()
        self.ai_model = getattr(self.threshold_service, "ai_model", None)
        if self.ai_model:
            logger.info("AIClimateModel provided via ThresholdService for unit %s", unit_id)
        else:
            logger.debug("AIClimateModel not provided; using plant-specific thresholds for unit %s", unit_id)
        
        # Growth predictor has been migrated to PlantHealthMonitor service
        # Access via container.plant_health_monitor instead
        self.growth_predictor = None
        
        # Sensor data cache (updated by SensorPollingService)
        self._latest_sensor_data: Dict[str, Any] = {}

        # Metadata
        self.created_at = datetime.now()
        self.is_active = True

        # Subscribe to events
        self._subscribe_to_events()

        logger.info(f"UnitRuntime initialized: {self.unit_id} ({self.unit_name})")

    @property
    def latest_sensor_data(self) -> Dict[str, Any]:
        """Get latest sensor readings for this unit."""
        return self._latest_sensor_data

    @latest_sensor_data.setter
    def latest_sensor_data(self, data: Dict[str, Any]) -> None:
        """Update latest sensor readings."""
        self._latest_sensor_data = data or {}


    def _subscribe_to_events(self):
        """Subscribe to relevant EventBus events"""
        self.event_bus.subscribe(PlantEvent.PLANT_STAGE_UPDATE, self.apply_ai_conditions)

    # ==================== Plant Management ====================

    def get_active_plant(self) -> Optional[PlantProfile]:
        """
        Get the currently active plant for climate control.
        
        Returns the active plant reference set by GrowthService.
        PlantService is the source of truth for plant data.
        """
        return self.active_plant

    # ==================== Settings Management ====================
    
    def update_settings(self, **kwargs) -> bool:
        """
        Update unit settings (runtime + hardware only; persistence via GrowthService).
        """
        for key, value in kwargs.items():
            if hasattr(self.settings, key):
                setattr(self.settings, key, value)
        
        self.event_bus.publish(
            RuntimeEvent.THRESHOLDS_UPDATE,
            ThresholdsUpdatePayload(unit_id=self.unit_id, thresholds=self.settings.to_dict()),
        )

        return True
    
    # ==================== AI Integration ====================
    
    def apply_ai_conditions(self, data: Optional[Dict] = None) -> None:
        """
        Propose optimal environmental conditions for active plant.
        
        Uses ThresholdService to combine:
        1. Plant-specific thresholds from plants_info.json
        2. AI climate model predictions (if available)
        3. Plant growth model predictions (if available)
        4. Stage transition analysis for optimal timing
        
        This method proposes the best conditions for the current plant type and
        growth stage, and analyzes readiness for stage advancement.
        
        Args:
            data: Optional event data (from EventBus)
        """
        try:
            if not self.active_plant:
                logger.debug(f"No active plant for unit {self.unit_id}, skipping AI conditions")
                return
            
            device_schedules = getattr(self.settings, "device_schedules", None)
            lighting_hours = get_light_hours(device_schedules)
            # Get current sensor readings for analysis
            current_conditions = {}
            if self.latest_sensor_data:
                current_conditions = {
                    'temperature': self.latest_sensor_data.get('temperature', 0),
                    'humidity': self.latest_sensor_data.get('humidity', 0),
                    'soil_moisture': self.latest_sensor_data.get('soil_moisture', 0),
                    'lighting_hours': self.latest_sensor_data.get('lighting_hours', lighting_hours)
                }
            
            # Analyze stage transition readiness if growth predictor available
            if self.growth_predictor and self.growth_predictor.is_available() and current_conditions:
                try:
                    days_in_stage = self.active_plant.days_in_current_stage or 0
                    transition = self.growth_predictor.analyze_stage_transition(
                        current_stage=self.active_plant.current_stage,
                        days_in_stage=days_in_stage,
                        actual_conditions=current_conditions
                    )
                    
                    if transition.ready:
                        logger.info(
                            f"Plant ready for stage advancement: "
                            f"{transition.from_stage} -> {transition.to_stage} "
                            f"(Unit {self.unit_id})"
                        )
                        # Publish event for stage advancement recommendation
                        self.event_bus.publish(
                            PlantEvent.GROWTH_STAGE_READY,
                            {
                                'unit_id': self.unit_id,
                                'plant_id': self.active_plant.plant_id,
                                'from_stage': transition.from_stage,
                                'to_stage': transition.to_stage,
                                'recommendations': transition.recommendations
                            }
                        )
                    else:
                        logger.debug(
                            f"Plant not ready for stage transition: "
                            f"{len([v for v in transition.conditions_met.values() if not v])} conditions unmet"
                        )
                except Exception as e:
                    logger.warning(f"Stage transition analysis failed: {e}")
            
            # Use ThresholdService for unified threshold management
            if self.threshold_service:
                # Get optimal conditions (plant-specific + AI blend)
                optimal = self.threshold_service.get_optimal_conditions(
                    plant_type=self.active_plant.plant_type,
                    growth_stage=self.active_plant.current_stage,
                    use_ai=True  # Enable AI enhancement if available
                )
                
                # Get growth predictions for additional insights
                if self.growth_predictor and self.growth_predictor.is_available():
                    try:
                        days_in_stage = self.active_plant.days_in_current_stage or 0
                        growth_conditions = self.growth_predictor.predict_growth_conditions(
                            stage_name=self.active_plant.current_stage,
                            days_in_stage=days_in_stage
                        )
                        
                        if growth_conditions:
                            # Blend AI predictions (weighted average)
                            # Climate model gets 60% weight, growth model gets 40%
                            temperature = optimal.temperature * 0.6 + growth_conditions.temperature * 0.4
                            humidity = optimal.humidity * 0.6 + growth_conditions.humidity * 0.4
                            optimal = optimal.merge(
                                {
                                    "temperature": temperature,
                                    "humidity": humidity,
                                }
                            )
                            
                            logger.debug(
                                f"Blended AI predictions: temp={optimal.temperature:.1f} C, "
                                f"humidity={optimal.humidity:.1f}% "
                                f"(confidence: {growth_conditions.confidence:.2f})"
                            )
                    except Exception as e:
                        logger.warning(f"Growth prediction blending failed: {e}")

                updates = optimal.to_settings_dict()
                threshold_keys = (
                    "temperature_threshold",
                    "humidity_threshold",
                    "co2_threshold",
                    "voc_threshold",
                    "lux_threshold",
                    "air_quality_threshold",
                )
                current_thresholds = {
                    key: getattr(self.settings, key)
                    for key in threshold_keys
                    if hasattr(self.settings, key)
                }

                self.event_bus.publish(
                    RuntimeEvent.THRESHOLDS_PROPOSED,
                    ThresholdsProposedPayload(
                        unit_id=self.unit_id,
                        user_id=self.user_id,
                        plant_id=self.active_plant.plant_id if self.active_plant else None,
                        plant_type=self.active_plant.plant_type if self.active_plant else None,
                        growth_stage=self.active_plant.current_stage if self.active_plant else None,
                        current_thresholds=current_thresholds,
                        proposed_thresholds=updates,
                        source="threshold_service_ai",
                    ),
                )
                
                # Hardware services will read ranges from settings
                logger.info(
                    f"Proposed AI-enhanced conditions for unit {self.unit_id}: "
                    f"{self.active_plant.plant_type} ({self.active_plant.current_stage})"
                )
                
            else:
                # ThresholdService is the single source of truth now; if it's missing,
                # we log and skip instead of falling back to legacy AI-only behavior.
                logger.warning(
                    "ThresholdService not available for unit %s; "
                    "skipping apply_ai_conditions",
                    self.unit_id,
                )
                return

        except Exception as e:
            logger.error(f"Error applying AI conditions for unit {self.unit_id}: {e}", exc_info=True)
    
    # ==================== Hardware Coordination ====================
    # Hardware operations are now managed directly by GrowthService
    # through singleton hardware services (SensorManagementService, ActuatorManagementService)
    
    # ==================== Status & Info ====================

    def is_hardware_running(self) -> bool:
        """
        Check if hardware is running for this unit.

        Note: This is tracked externally by GrowthService. UnitRuntime doesn't
        have direct access to hardware state. This method now checks a local
        flag that can be set by GrowthService when starting/stopping hardware.

        Returns:
            True if hardware is running, False otherwise
        """
        return getattr(self, "_hardware_running", False)

    def set_hardware_running(self, running: bool) -> None:
        """Set the hardware running state (called by GrowthService)."""
        self._hardware_running = running
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get comprehensive status of this unit.
        
        NOTE: plant_count and plants are from local cache.
        For authoritative plant data, use PlantService.list_plants(unit_id).
        
        Returns:
            Dictionary with unit details, settings, hardware status.
            NOTE: For plant data, use PlantService.list_plants(unit_id).
        """
        return {
            "unit_id": self.unit_id,
            "name": self.unit_name,
            "location": self.location,
            "user_id": self.user_id,
            "is_active": self.is_active,
            "custom_image": self.custom_image,
            "settings": self.settings.to_dict(),
            "active_plant": self.active_plant.plant_name if self.active_plant else None,
            "active_plant_id": self.active_plant.id if self.active_plant else None,
            "hardware_running": self.is_hardware_running(),
            "created_at": self.created_at.isoformat()
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary (same as get_status for now)"""
        return self.get_status()
    
    # ==================== Private Methods ====================
    
    def __repr__(self) -> str:
        """String representation for debugging"""
        status = "ACTIVE" if self.is_active else "INACTIVE"
        hw_status = "HW_RUNNING" if self.is_hardware_running() else "HW_STOPPED"
        active = f"active_plant={self.active_plant.plant_id}" if self.active_plant else "no_active_plant"
        return f"<UnitRuntime unit_id={self.unit_id} name='{self.unit_name}' status={status} {hw_status} {active}>"
