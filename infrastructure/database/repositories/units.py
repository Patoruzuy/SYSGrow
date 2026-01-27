"""
Unit Repository
===============

Repository for growth unit operations.
Clear ownership: UnitRepository is used exclusively by GrowthService.

Responsibilities:
- Unit CRUD operations (create, read, update, delete)
- Unit settings management
- Unit statistics and status

Author: SYSGrow Team
Date: January 2026
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from infrastructure.database.ops.growth import GrowthOperations
from infrastructure.database.decorators import (
    repository_cache,
    invalidates_caches
)


class UnitRepository:
    """Repository for growth unit operations (GrowthService exclusive)."""

    def __init__(self, backend: GrowthOperations) -> None:
        self._backend = backend

    # Unit CRUD Operations -----------------------------------------------------
    @invalidates_caches
    def create_unit(
        self,
        *,
        name: str,
        location: str = "Indoor",
        user_id: int = 1,
        timezone: Optional[str] = None,
        dimensions: Optional[str] = None,
        custom_image: Optional[str] = None,
        active_plant_id: Optional[int] = None,
        temperature_threshold: float = 24.0,
        humidity_threshold: float = 50.0,
        soil_moisture_threshold: float = 40.0,
        co2_threshold: float = 1000.0,
        voc_threshold: float = 1000.0,
        lux_threshold: float = 1000.0,
        air_quality_threshold: float = 1000.0,
        camera_enabled: bool = False,
    ) -> Optional[int]:
        """
        Create a new growth unit.
        
        Args:
            name: Unit name
            location: Location (Indoor/Outdoor/Greenhouse/Hydroponics)
            user_id: Owner ID
            dimensions: JSON string of physical dimensions
            custom_image: Optional custom image path
            active_plant_id: Optional active plant ID
            temperature_threshold: Temperature threshold in Celsius
            humidity_threshold: Humidity threshold in percentage
            soil_moisture_threshold: Soil moisture threshold in percentage
            co2_threshold: CO2 threshold in ppm
            voc_threshold: VOC threshold in ppb
            lux_threshold: Light intensity threshold in lux
            air_quality_threshold: Air quality index threshold
            camera_enabled: Enable camera for this unit
            
        Returns:
            Unit ID if successful, None otherwise
        """
        return self._backend.insert_growth_unit(
            name=name,
            location=location,
            user_id=user_id,
            timezone=timezone,
            dimensions=dimensions,
            custom_image=custom_image,
            active_plant_id=active_plant_id,
            temperature_threshold=temperature_threshold,
            humidity_threshold=humidity_threshold,
            soil_moisture_threshold=soil_moisture_threshold,
            co2_threshold=co2_threshold,
            voc_threshold=voc_threshold,
            lux_threshold=lux_threshold,
            air_quality_threshold=air_quality_threshold,
            camera_enabled=camera_enabled,
        )

    @repository_cache(maxsize=128, invalidate_on=['create_unit', 'update_unit', 'update_unit_settings', 'delete_unit'])
    def get_unit(self, unit_id: int):
        """Get unit by ID."""
        return self._backend.get_growth_unit(unit_id)

    def list_units(
        self,
        *,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> List[Any]:
        """
        List all growth units with pagination.

        Args:
            limit: Number of results per page (default: 100, max: 500)
            offset: Number of results to skip (default: 0)

        Returns:
            List of growth unit dictionaries
        """
        return self._backend.get_all_growth_units(limit=limit, offset=offset)

    def get_user_units(self, user_id: int) -> List[Dict[str, Any]]:
        """Get all units for a specific user."""
        return self._backend.get_user_growth_units(user_id)

    @invalidates_caches
    def update_unit(self, unit_id: int, **fields: Any) -> None:
        """
        Update unit fields.
        
        Args:
            unit_id: Unit ID
            **fields: Fields to update (name, location, dimensions, custom_image, camera_enabled)
        """
        self._backend.update_growth_unit(unit_id, **fields)

    @invalidates_caches
    def delete_unit(self, unit_id: int) -> None:
        """Delete a growth unit."""
        self._backend.delete_growth_unit(unit_id)

    # Unit Settings ------------------------------------------------------------
    @invalidates_caches
    def update_unit_settings(self, unit_id: int, settings: Dict[str, Any]) -> bool:
        """
        Update unit settings (thresholds, dimensions, camera).
        
        Args:
            unit_id: Unit ID
            settings: Settings dictionary
            
        Returns:
            True if successful
        """
        return self._backend.update_unit_settings(unit_id, settings)

    # Unit Statistics ----------------------------------------------------------
    def count_plants_in_unit(self, unit_id: int) -> int:
        """Count plants in a unit."""
        return self._backend.count_plants_in_unit(unit_id)

    def count_sensors_in_unit(self, unit_id: int) -> int:
        """Count sensors in a unit."""
        return self._backend.count_sensors_in_unit(unit_id)

    def count_actuators_in_unit(self, unit_id: int) -> int:
        """Count actuators in a unit."""
        return self._backend.count_actuators_in_unit(unit_id)

    def is_camera_active(self, unit_id: int) -> bool:
        """Check if camera is active for a unit."""
        return self._backend.is_camera_active(unit_id)

    def get_unit_last_activity(self, unit_id: int) -> Optional[str]:
        """Get last activity timestamp for a unit."""
        return self._backend.get_unit_last_activity(unit_id)

    def get_unit_uptime_hours(self, unit_id: int) -> int:
        """Get unit uptime in hours."""
        return self._backend.get_unit_uptime_hours(unit_id)
