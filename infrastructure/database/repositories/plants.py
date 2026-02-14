"""
Plant Repository
================

Repository for plant operations.
Clear ownership: PlantRepository is used exclusively by PlantViewService.

Responsibilities:
- Plant CRUD operations (create, read, update, delete)
- Plant-unit assignments
- Plant-sensor linkages
- Plant-actuator linkages
- Active plant management
- Plant growth tracking

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


class PlantRepository:
    """Repository for plant operations (PlantViewService exclusive)."""

    def __init__(self, backend: GrowthOperations) -> None:
        self._backend = backend

    # Plant CRUD Operations ----------------------------------------------------
    @invalidates_caches
    def create_plant(
        self,
        *,
        unit_id: Optional[int] = None,
        plant_name: str,
        plant_type: str,
        plant_species: Optional[str] = None,
        plant_variety: Optional[str] = None,
        current_stage: str,
        days_in_stage: int = 0,
        moisture_level: float = 0.0,
        planted_date: Optional[str] = None,
        created_at: Optional[str] = None,
        pot_size_liters: float = 0.0,
        pot_material: str = "plastic",
        growing_medium: str = "soil",
        medium_ph: float = 7.0,
        strain_variety: Optional[str] = None,
        expected_yield_grams: float = 0.0,
        light_distance_cm: float = 0.0,
        soil_moisture_threshold_override: Optional[float] = None,
    ) -> Optional[int]:
        """
        Create a new plant.
        
        Args:
            unit_id: Optional unit ID to assign plant to
            plant_name: Name of the plant
            plant_type: Type/species of plant
            current_stage: Current growth stage
            days_in_stage: Days in current stage
            moisture_level: Current moisture level
            planted_date: Date planted (ISO format)
            created_at: Creation timestamp (ISO format)
            pot_size_liters: Container size in liters
            pot_material: Container material
            growing_medium: Growing medium type
            medium_ph: pH level of medium
            strain_variety: Specific cultivar/strain
            expected_yield_grams: Target harvest amount
            light_distance_cm: Light distance in cm
            soil_moisture_threshold_override: Optional per-plant soil moisture trigger
            
        Returns:
            Plant ID if successful, None otherwise
        """
        return self._backend.insert_plant(
            unit_id=unit_id,
            name=plant_name,
            plant_type=plant_type,
            plant_species=plant_species,
            plant_variety=plant_variety,
            current_stage=current_stage,
            days_in_stage=days_in_stage,
            moisture_level=moisture_level,
            planted_date=planted_date,
            created_at=created_at,
            pot_size_liters=pot_size_liters,
            pot_material=pot_material,
            growing_medium=growing_medium,
            medium_ph=medium_ph,
            strain_variety=strain_variety,
            expected_yield_grams=expected_yield_grams,
            light_distance_cm=light_distance_cm,
            soil_moisture_threshold_override=soil_moisture_threshold_override,
        )

    @repository_cache(
        maxsize=256,
        invalidate_on=[
            'create_plant',
            'remove_plant',
            'update_plant',
            'assign_plant_to_unit',
            'remove_plant_from_unit',
            'update_plant_progress',
            'update_plant_days',
            'update_plant_moisture',
        ],
    )
    def get_plant(self, plant_id: int):
        """Get plant by ID."""
        return self._backend.get_plant_by_id(plant_id)

    def list_plants(
        self,
        *,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> List[Any]:
        """
        List all plants with pagination.

        Args:
            limit: Number of results per page (default: 100, max: 500)
            offset: Number of results to skip (default: 0)

        Returns:
            List of plant dictionaries
        """
        return self._backend.get_all_plants(limit=limit, offset=offset)

    def list_plants_for_unit(
        self,
        unit_id: int,
        *,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> List[Any]:
        """
        List plants for a specific unit with pagination.

        Args:
            unit_id: Growth unit ID
            limit: Number of results per page (default: 100, max: 500)
            offset: Number of results to skip (default: 0)

        Returns:
            List of plant dictionaries for the unit
        """
        return self._backend.get_plants_for_unit(unit_id, limit=limit, offset=offset)

    @repository_cache(
        maxsize=128,
        invalidate_on=[
            'create_plant',
            'remove_plant',
            'update_plant',
            'assign_plant_to_unit',
            'remove_plant_from_unit',
            'update_plant_progress',
            'update_plant_days',
            'update_plant_moisture',
        ],
    )
    def get_plants_in_unit(self, unit_id: int) -> List[Dict[str, Any]]:
        """Get all plants in a unit with full details."""
        return self._backend.get_plants_in_unit(unit_id)

    @invalidates_caches
    def update_plant(self, plant_id: int, **fields: Any) -> None:
        """
        Update plant fields.
        
        Args:
            plant_id: Plant ID
            **fields: Fields to update
        """
        self._backend.update_plant(plant_id, **fields)

    @invalidates_caches
    def remove_plant(self, plant_id: int) -> None:
        """Delete a plant."""
        self._backend.remove_plant(plant_id)

    # Plant-Unit Assignment ----------------------------------------------------
    @invalidates_caches
    def assign_plant_to_unit(self, unit_id: int, plant_id: int) -> None:
        """Assign a plant to a unit."""
        self._backend.assign_plant_to_unit(unit_id, plant_id)

    @invalidates_caches
    def remove_plant_from_unit(self, unit_id: int, plant_id: int) -> None:
        """Remove a plant from a unit."""
        self._backend.remove_plant_from_unit(unit_id, plant_id)

    # Plant-Sensor Linkage -----------------------------------------------------
    def link_sensor_to_plant(self, plant_id: int, sensor_id: int) -> None:
        """Link a sensor to a plant."""
        self._backend.link_sensor_to_plant(plant_id, sensor_id)

    def unlink_sensor_from_plant(self, plant_id: int, sensor_id: int) -> None:
        """Unlink a sensor from a plant."""
        self._backend.unlink_sensor_from_plant(plant_id, sensor_id)

    def unlink_all_sensors_from_plant(self, plant_id: int) -> None:
        """Unlink all sensors from a plant."""
        self._backend.unlink_all_sensors_from_plant(plant_id)

    def get_sensors_for_plant(self, plant_id: int) -> List[Any]:
        """Get all sensors linked to a plant."""
        return self._backend.get_sensors_for_plant(plant_id)

    def get_plants_for_sensor(self, sensor_id: int) -> List[int]:
        """Get all plant IDs linked to a sensor."""
        return self._backend.get_plants_for_sensor(sensor_id)

    # Plant-Actuator Linkage ---------------------------------------------------
    def link_actuator_to_plant(self, plant_id: int, actuator_id: int) -> None:
        """Link an actuator to a plant."""
        self._backend.link_actuator_to_plant(plant_id, actuator_id)

    def unlink_actuator_from_plant(self, plant_id: int, actuator_id: int) -> None:
        """Unlink an actuator from a plant."""
        self._backend.unlink_actuator_from_plant(plant_id, actuator_id)

    def get_actuators_for_plant(self, plant_id: int) -> List[int]:
        """Get all actuator IDs linked to a plant."""
        return self._backend.get_actuators_for_plant(plant_id)

    # Active Plant Management --------------------------------------------------
    def set_active_plant(self, plant_id: int) -> None:
        """Set a plant as active for climate control."""
        self._backend.set_active_plant(plant_id)

    def get_active_plant(self) -> Optional[int]:
        """Get the currently active plant ID."""
        return self._backend.get_active_plant()

    def get_all_active_plants(
        self,
        *,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get all active plants across growth units with pagination.

        Args:
            limit: Number of results per page (default: 100, max: 500)
            offset: Number of results to skip (default: 0)

        Returns:
            List of active plant dictionaries with unit information
        """
        return self._backend.get_all_active_plants(limit=limit, offset=offset)

    # Plant Growth Tracking ----------------------------------------------------
    @invalidates_caches
    def update_plant_days(self, plant_name: str, days: int) -> None:
        """Update days in current stage by plant name."""
        self._backend.update_plant_days(plant_name, days)

    @invalidates_caches
    def update_plant_moisture(self, plant_name: str, moisture_level: float) -> None:
        """Update moisture level by plant name."""
        self._backend.update_plant_soil_moisture(plant_name, moisture_level)

    @invalidates_caches
    def update_plant_moisture_by_id(self, plant_id: int, moisture_level: float) -> None:
        """Update moisture level by plant ID."""
        self._backend.update_plant_moisture_by_id(plant_id, moisture_level)

    @invalidates_caches
    def update_plant_progress(
        self,
        plant_id: int,
        current_stage: str,
        moisture_level: float,
        days_in_stage: int
    ) -> None:
        """Update plant growth progress."""
        self._backend.update_plant_progress(
            plant_id,
            current_stage,
            moisture_level,
            days_in_stage
        )

    # Plant History & Analytics ------------------------------------------------
    def insert_plant_history(self, *args, **kwargs) -> None:
        """Insert plant history record."""
        self._backend.insert_plant_history(*args, **kwargs)

    def get_plant_avg_temperature(self, plant_id: int) -> float:
        """Get average temperature for a plant."""
        return self._backend.get_plant_avg_temperature(plant_id)

    def get_plant_avg_humidity(self, plant_id: int) -> float:
        """Get average humidity for a plant."""
        return self._backend.get_plant_avg_humidity(plant_id)

    def get_plant_total_light_hours(self, plant_id: int) -> float:
        """Get total light hours for a plant."""
        return self._backend.get_plant_total_light_hours(plant_id)

    # Plant Cleanup (harvest) --------------------------------------------------
    def cleanup_plant_data(self, plant_id: int) -> Dict[str, int]:
        """Delete plant-specific data during harvest.

        Removes health logs, sensor associations, unit associations,
        clears ``active_plant_id`` on any growth unit, and finally
        deletes the plant record itself.

        Shared data (energy readings, sensor readings, environment data,
        device history) is intentionally preserved.

        Args:
            plant_id: Plant ID whose records should be cleaned up.

        Returns:
            Dictionary with counts of deleted records per category.
        """
        import logging

        _logger = logging.getLogger(__name__)

        deleted: Dict[str, int] = {
            "plant_health_logs": 0,
            "plant_sensors": 0,
            "plant_unit_associations": 0,
            "plant_record": 0,
        }
        with self._backend.connection() as conn:
            # 1. Health logs (plant-specific)
            for table_name in ("PlantHealthLogs", "PlantHealth"):
                try:
                    cursor = conn.execute(
                        f"DELETE FROM {table_name} WHERE plant_id = ?",  # nosec B608
                        (plant_id,),
                    )
                    deleted["plant_health_logs"] += cursor.rowcount
                except Exception as exc:
                    if "no such table" in str(exc).lower():
                        continue
                    raise

            # 2. Plant-sensor associations
            cursor = conn.execute(
                "DELETE FROM PlantSensors WHERE plant_id = ?", (plant_id,)
            )
            deleted["plant_sensors"] = cursor.rowcount

            # 3. Plant-unit associations
            cursor = conn.execute(
                "DELETE FROM GrowthUnitPlants WHERE plant_id = ?", (plant_id,)
            )
            deleted["plant_unit_associations"] = cursor.rowcount

            # 4. Clear active_plant_id on units (don't delete the unit)
            conn.execute(
                "UPDATE GrowthUnits SET active_plant_id = NULL WHERE active_plant_id = ?",
                (plant_id,),
            )

            # 5. Delete the plant record itself (last!)
            cursor = conn.execute(
                "DELETE FROM Plants WHERE plant_id = ?", (plant_id,)
            )
            deleted["plant_record"] = cursor.rowcount

        _logger.info(
            "Cleaned up plant %s: health_logs=%d, sensors=%d, unit_assoc=%d, plant=%d",
            plant_id,
            deleted["plant_health_logs"],
            deleted["plant_sensors"],
            deleted["plant_unit_associations"],
            deleted["plant_record"],
        )
        return deleted
