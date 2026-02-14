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
from app.utils.event_bus import EventBus
from app.enums.events import RuntimeEvent
from app.schemas.events import (
    ThresholdsUpdatePayload,
    ActivePlantSetPayload,
)

logger = logging.getLogger(__name__)


@dataclass
class UnitDimensions:
    """Physical dimensions of a growth unit."""
    width: float   # cm
    height: float  # cm
    depth: float   # cm

    # --- computed helpers used by AI services ---

    @property
    def volume_liters(self) -> float:
        """Internal volume in litres (width × height × depth / 1000)."""
        return (self.width * self.height * self.depth) / 1000

    @property
    def area_m2(self) -> float:
        """Floor area in m² (width × depth / 10 000)."""
        return (self.width * self.depth) / 10_000

    @property
    def volume_m3(self) -> float:
        """Internal volume in m³ (width × height × depth / 1 000 000)."""
        return (self.width * self.height * self.depth) / 1_000_000

    def to_dict(self) -> Dict[str, float]:
        return {
            "width": self.width,
            "height": self.height,
            "depth": self.depth,
            "volume_liters": self.volume_liters,
            "area_m2": self.area_m2,
            "volume_m3": self.volume_m3,
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
    air_quality_threshold: float = 100.0
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
            air_quality_threshold=data.get("air_quality_threshold", data.get("aqi_threshold", 100.0)),
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
    - Coordinate with hardware layer (UnitRuntimeManager)

    This class is a pure domain model — no HTTP/API concerns, no AI orchestration.
    AI threshold proposals are handled by GrowthService at the service layer.

    Events emitted:
        - RuntimeEvent.THRESHOLDS_UPDATE: Threshold settings changed
        - RuntimeEvent.ACTIVE_PLANT_SET: Request to set active plant
    """

    def __init__(
        self,
        unit_id: int,
        unit_name: str,
        location: str,
        user_id: int,
        settings: Optional[UnitSettings] = None,
        custom_image: Optional[str] = None,
        # DEPRECATED: threshold_service is accepted for backward compat but ignored.
        threshold_service: Optional[Any] = None,
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
            threshold_service: DEPRECATED — ignored. AI orchestration moved to GrowthService.
        """
        self.unit_id = unit_id
        self.unit_name = unit_name
        self.location = location
        self.user_id = user_id
        self.custom_image = custom_image

        # Hardware running state (set by GrowthService when starting/stopping)
        self._hardware_running = False
        
        # Active plant reference (set by GrowthService after PlantService lookup)
        # PlantService is the single source of truth for plant collections
        self.active_plant: Optional[PlantProfile] = None
        
        # Unit settings
        self.settings = settings or UnitSettings()
        
        # Events
        self.event_bus = EventBus().get_instance()
        
        # Sensor data cache (updated by SensorPollingService)
        self._latest_sensor_data: Dict[str, Any] = {}

        # Metadata
        self.created_at = datetime.now()
        self.is_active = True

        logger.info(f"UnitRuntime initialized: {self.unit_id} ({self.unit_name})")

    @property
    def latest_sensor_data(self) -> Dict[str, Any]:
        """Get latest sensor readings for this unit."""
        return self._latest_sensor_data

    @latest_sensor_data.setter
    def latest_sensor_data(self, data: Dict[str, Any]) -> None:
        """Update latest sensor readings."""
        self._latest_sensor_data = data or {}


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
