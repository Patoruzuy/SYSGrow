from __future__ import annotations

from typing import Any

from infrastructure.database.decorators import invalidates_caches, repository_cache
from infrastructure.database.ops.growth import GrowthOperations
from infrastructure.database.repositories.plants import PlantRepository
from infrastructure.database.repositories.units import UnitRepository


class GrowthRepository:
    """
    DEPRECATED: Compatibility facade for growth unit and plant operations.

    This class is maintained for backward compatibility during migration.
    New code should use:
    - UnitRepository for unit operations (GrowthService)
    - PlantRepository for plant operations (PlantViewService)

    Will be removed in a future release.
    """

    def __init__(self, backend: GrowthOperations) -> None:
        self._backend = backend
        # Delegate to specialized repositories
        self._unit_repo = UnitRepository(backend)
        self._plant_repo = PlantRepository(backend)

    # Growth units -------------------------------------------------------------
    @invalidates_caches
    def create_unit(
        self,
        *,
        name: str,
        location: str = "Indoor",
        user_id: int = 1,
        timezone: str | None = None,
        dimensions: str | None = None,
        custom_image: str | None = None,
        active_plant_id: int | None = None,
        temperature_threshold: float = 24.0,
        humidity_threshold: float = 50.0,
        soil_moisture_threshold: float = 40.0,
        co2_threshold: float = 1000.0,
        voc_threshold: float = 1000.0,
        lux_threshold: float = 1000.0,
        aqi_threshold: float = 100.0,
        device_schedules: str | None = None,
        camera_enabled: bool = False,
    ) -> int | None:
        """
        Create a new growth unit.

        Args:
            dimensions: JSON string of dimensions
            device_schedules: JSON string of device schedules
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
            air_quality_threshold=aqi_threshold,
            device_schedules=device_schedules,
            camera_enabled=camera_enabled,
        )

    @repository_cache(maxsize=128, invalidate_on=["create_unit", "update_unit", "update_unit_settings", "delete_unit"])
    def get_unit(self, unit_id: int):
        return self._backend.get_growth_unit(unit_id)

    def list_units(
        self,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[Any]:
        """
        List all growth units with pagination.

        Args:
            limit: Number of results per page (default: 100, max: 500)
            offset: Number of results to skip (default: 0)

        Returns:
            List of growth unit dictionaries
        """
        return self._backend.get_all_growth_units(limit=limit, offset=offset)

    @invalidates_caches
    def update_unit(self, unit_id: int, **fields: Any) -> None:
        self._backend.update_growth_unit(unit_id, **fields)

    @invalidates_caches
    def delete_unit(self, unit_id: int) -> None:
        self._backend.delete_growth_unit(unit_id)

    # Plants -------------------------------------------------------------------
    @invalidates_caches
    def create_plant(
        self,
        *,
        unit_id: int | None = None,
        plant_name: str,
        plant_type: str,
        current_stage: str,
        days_in_stage: int = 0,
        moisture_level: float = 0.0,
        planted_date: str | None = None,
        created_at: str | None = None,
        pot_size_liters: float = 0.0,
        pot_material: str = "plastic",
        growing_medium: str = "soil",
        medium_ph: float = 7.0,
        strain_variety: str | None = None,
        expected_yield_grams: float = 0.0,
        light_distance_cm: float = 0.0,
        soil_moisture_threshold_override: float | None = None,
    ) -> int | None:
        return self._backend.insert_plant(
            unit_id=unit_id,
            name=plant_name,
            plant_type=plant_type,
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

    @invalidates_caches
    def update_plant(self, plant_id: int, **fields: Any) -> None:
        self._backend.update_plant(plant_id, **fields)

    @invalidates_caches
    def remove_plant(self, plant_id: int) -> None:
        self._backend.remove_plant(plant_id)

    @repository_cache(
        maxsize=256,
        invalidate_on=[
            "create_plant",
            "remove_plant",
            "update_plant",
            "assign_plant_to_unit",
            "remove_plant_from_unit",
            "update_plant_progress",
            "update_plant_days",
            "update_plant_moisture",
        ],
    )
    def get_plant(self, plant_id: int):
        return self._backend.get_plant_by_id(plant_id)

    def list_plants(
        self,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[Any]:
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
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[Any]:
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

    @invalidates_caches
    def assign_plant_to_unit(self, unit_id: int, plant_id: int) -> None:
        self._backend.assign_plant_to_unit(unit_id, plant_id)

    @invalidates_caches
    def remove_plant_from_unit(self, unit_id: int, plant_id: int) -> None:
        self._backend.remove_plant_from_unit(unit_id, plant_id)

    def link_sensor_to_plant(self, plant_id: int, sensor_id: int) -> None:
        self._backend.link_sensor_to_plant(plant_id, sensor_id)

    def unlink_sensor_from_plant(self, plant_id: int, sensor_id: int) -> None:
        self._backend.unlink_sensor_from_plant(plant_id, sensor_id)

    def link_actuator_to_plant(self, plant_id: int, actuator_id: int) -> None:
        self._backend.link_actuator_to_plant(plant_id, actuator_id)

    def unlink_actuator_from_plant(self, plant_id: int, actuator_id: int) -> None:
        self._backend.unlink_actuator_from_plant(plant_id, actuator_id)

    def get_actuators_for_plant(self, plant_id: int) -> list[int]:
        return self._backend.get_actuators_for_plant(plant_id)

    def unlink_all_sensors_from_plant(self, plant_id: int) -> None:
        self._backend.unlink_all_sensors_from_plant(plant_id)

    def get_sensors_for_plant(self, plant_id: int) -> list[Any]:
        return self._backend.get_sensors_for_plant(plant_id)

    def set_active_plant(self, plant_id: int) -> None:
        self._backend.set_active_plant(plant_id)

    def get_active_plant(self) -> int | None:
        return self._backend.get_active_plant()

    def get_all_active_plants(
        self,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        Get all active plants across growth units with pagination.

        Args:
            limit: Number of results per page (default: 100, max: 500)
            offset: Number of results to skip (default: 0)

        Returns:
            List of active plant dictionaries with unit information
        """
        return self._backend.get_all_active_plants(limit=limit, offset=offset)

    @invalidates_caches
    def update_plant_days(self, plant_name: str, days: int) -> None:
        self._backend.update_plant_days(plant_name, days)

    @invalidates_caches
    def update_plant_moisture(self, plant_name: str, moisture_level: float) -> None:
        self._backend.update_plant_soil_moisture(plant_name, moisture_level)

    @invalidates_caches
    def update_plant_moisture_by_id(self, plant_id: int, moisture_level: float) -> None:
        self._backend.update_plant_moisture_by_id(plant_id, moisture_level)

    # User-scoped units
    def get_user_growth_units(self, user_id: int) -> list[dict[str, Any]]:
        return self._backend.get_user_growth_units(user_id)

    def insert_growth_unit_with_user(self, user_id: int, name: str, location: str, data: dict[str, Any]) -> int | None:
        return self._backend.insert_growth_unit_with_user(user_id, name, location, data)

    # Settings
    @invalidates_caches
    def update_unit_settings(self, unit_id: int, settings: dict[str, Any]) -> bool:
        return self._backend.update_unit_settings(unit_id, settings)

    # Plants (richer)
    @repository_cache(
        maxsize=128,
        invalidate_on=[
            "create_plant",
            "remove_plant",
            "update_plant",
            "assign_plant_to_unit",
            "remove_plant_from_unit",
            "update_plant_progress",
            "update_plant_days",
            "update_plant_moisture",
        ],
    )
    def get_plants_in_unit(self, unit_id: int) -> list[dict[str, Any]]:
        return self._backend.get_plants_in_unit(unit_id)

    def get_plants_for_sensor(self, sensor_id: int) -> list[int]:
        return self._backend.get_plants_for_sensor(sensor_id)

    # Stats / status
    def count_plants_in_unit(self, unit_id: int) -> int:
        return self._backend.count_plants_in_unit(unit_id)

    def count_sensors_in_unit(self, unit_id: int) -> int:
        return self._backend.count_sensors_in_unit(unit_id)

    def count_actuators_in_unit(self, unit_id: int) -> int:
        return self._backend.count_actuators_in_unit(unit_id)

    def is_camera_active(self, unit_id: int) -> bool:
        return self._backend.is_camera_active(unit_id)

    def get_unit_last_activity(self, unit_id: int) -> str | None:
        return self._backend.get_unit_last_activity(unit_id)

    def get_unit_uptime_hours(self, unit_id: int) -> int:
        return self._backend.get_unit_uptime_hours(unit_id)

    # PlantProfile needs these:
    @invalidates_caches
    def update_plant_progress(
        self, plant_id: int, current_stage: str, moisture_level: float, days_in_stage: int
    ) -> None:
        self._backend.update_plant_progress(plant_id, current_stage, moisture_level, days_in_stage)

    def insert_plant_history(self, *args, **kwargs) -> None:
        self._backend.insert_plant_history(*args, **kwargs)

    def get_plant_avg_temperature(self, plant_id: int) -> float:
        return self._backend.get_plant_avg_temperature(plant_id)

    def get_plant_avg_humidity(self, plant_id: int) -> float:
        return self._backend.get_plant_avg_humidity(plant_id)

    def get_plant_total_light_hours(self, plant_id: int) -> float:
        return self._backend.get_plant_total_light_hours(plant_id)
