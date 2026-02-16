from __future__ import annotations

import datetime
from typing import Any

from infrastructure.database.ops.analytics import AnalyticsOperations


class AnalyticsRepository:
    """Expose sensor and plant analytics operations."""

    def __init__(self, backend: AnalyticsOperations, analytics: AnalyticsOperations | None = None) -> None:
        self._backend = backend
        self._analytics = analytics or backend

    def insert_sensor_reading(
        self,
        *,
        sensor_id: int,
        reading_data: dict[str, Any],
        quality_score: float = 1.0,
        timestamp: str | None = None,
    ) -> int | None:
        return self._backend.insert_sensor_reading(
            sensor_id=sensor_id,
            reading_data=reading_data,
            quality_score=quality_score,
            timestamp=timestamp,
        )

    def list_sensor_readings(self, *, limit: int = 20, offset: int = 0) -> list[dict[str, object]]:
        return self._backend.get_sensor_data(limit=limit, offset=offset)

    def latest_readings_for_unit(self, unit_id: int) -> dict[str, float | None]:
        return self._backend.get_latest_sensor_readings(unit_id)

    def list_plant_readings(self, *, limit: int | None = None, offset: int | None = None) -> list[dict[str, object]]:
        return self._backend.get_all_plant_readings(limit=limit, offset=offset)

    def get_latest_plant_readings(self, plant_id: int, limit: int = 1) -> list[dict[str, object]]:
        """Get most recent PlantReadings for a specific plant."""
        return self._backend.get_latest_plant_readings(plant_id, limit=limit)

    def get_plant_readings_in_window(
        self,
        plant_id: int,
        *,
        start: str,
        end: str,
    ) -> list[dict[str, object]]:
        """Get PlantReadings in time window for a plant."""
        return self._backend.get_plant_readings_in_window(plant_id, start, end)

    def get_plants_needing_attention(
        self,
        unit_id: int | None = None,
        moisture_threshold: float = 30.0,
        hours_since_reading: int = 24,
    ) -> list[dict[str, object]]:
        """Find plants with concerning readings (dry, overwatered, no recent data)."""
        return self._backend.get_plants_needing_attention(
            unit_id=unit_id,
            moisture_threshold=moisture_threshold,
            hours_since_reading=hours_since_reading,
        )

    def get_latest_plant_moisture_in_window(
        self,
        plant_id: int,
        *,
        start_ts: str,
        end_ts: str,
    ) -> dict[str, object] | None:
        """Fetch latest plant moisture reading within a time window."""
        return self._backend.get_latest_plant_moisture_in_window(
            plant_id,
            start_ts=start_ts,
            end_ts=end_ts,
        )

    def get_plant_moisture_readings_in_window(
        self,
        plant_id: int,
        *,
        start_ts: str,
        end_ts: str,
        limit: int | None = None,
    ) -> list[dict[str, object]]:
        """Fetch plant moisture readings within a time window."""
        return self._backend.get_plant_moisture_readings_in_window(
            plant_id,
            start_ts=start_ts,
            end_ts=end_ts,
            limit=limit,
        )

    def save_plant_reading(self, **kwargs) -> int | None:
        """Expose unified plant reading save."""
        return self._backend.save_plant_reading(**kwargs)

    # ---------- Analytics-facing delegates ----------
    def get_average_temperature(self, plant_id: int) -> float:
        return self._analytics.get_average_temperature(plant_id)

    def get_average_humidity(self, plant_id: int) -> float:
        return self._analytics.get_average_humidity(plant_id)

    def get_total_light_hours(self, plant_id: int) -> float:
        return self._analytics.get_total_light_hours(plant_id)

    # ---------- AI analytics ----------
    def get_latest_ai_log(self, unit_id: int) -> dict[str, float] | None:
        return self._analytics.get_latest_ai_log(unit_id)

    def get_latest_sensor_reading(self, unit_id: int | None = None) -> dict[str, object] | None:
        """Get the most recent sensor reading across all sensors, optionally filtered by unit."""
        return self._backend.get_latest_sensor_reading(unit_id=unit_id)

    def get_latest_energy_reading(self) -> dict[str, object] | None:
        """Get the most recent energy consumption reading."""
        return self._backend.get_latest_energy_reading()

    def fetch_sensor_history(
        self,
        start_dt: "datetime",
        end_dt: "datetime",
        *,
        unit_id: int | None = None,
        sensor_id: int | None = None,
        limit: int | None = None,
    ) -> list[dict[str, object]]:
        """
        Fetch sensor readings between start and end datetime.

        Args:
            start_dt: Start datetime for the range
            end_dt: End datetime for the range
            unit_id: Optional unit filter
            sensor_id: Optional sensor filter
            limit: Optional row cap

        Returns:
            List of sensor readings ordered by timestamp
        """
        return self._backend.fetch_sensor_history(
            start_dt,
            end_dt,
            unit_id=unit_id,
            sensor_id=sensor_id,
            limit=limit,
        )

    def get_plant_info(self, plant_id: int) -> dict[str, object] | None:
        """Get plant information by plant ID."""
        return self._backend.get_plant_info(plant_id)

    def get_plant_id_for_sensor(self, sensor_id: int) -> int | None:
        """Get plant ID associated with a sensor ID."""
        return self._backend.get_plant_id_for_sensor(sensor_id)

    def insert_plant_history_analytics(
        self,
        *,
        plant_name: str,
        current_stage: str,
        days_in_stage: int,
        avg_temp: float,
        avg_humidity: float,
        light_hours: float,
        harvest_weight: float = 0.0,
        photo_path: str = "",
        date_harvested: str,
    ) -> None:
        """
        Map PlantProfile's compact history call to AnalyticsOperations.insert_plant_history
        which stores days per stage.
        """
        stage_key = (current_stage or "").lower()
        days = dict(days_germination=0, days_seed=0, days_veg=0, days_flower=0, days_fruit_dev=0)
        # simple mapping — tweak to your stage names
        if "germ" in stage_key:
            days["days_germination"] = days_in_stage
        elif "seed" in stage_key:
            days["days_seed"] = days_in_stage
        elif "veg" in stage_key:
            days["days_veg"] = days_in_stage
        elif "flow" in stage_key:
            days["days_flower"] = days_in_stage
        else:
            days["days_fruit_dev"] = days_in_stage

        self._analytics.insert_plant_history(
            plant_name=plant_name,
            days_germination=days["days_germination"],
            days_seed=days["days_seed"],
            days_veg=days["days_veg"],
            days_flower=days["days_flower"],
            days_fruit_dev=days["days_fruit_dev"],
            avg_temp=avg_temp,
            avg_humidity=avg_humidity,
            light_hours=light_hours,
            harvest_weight=harvest_weight,
            photo_path=photo_path,
            date_harvested=date_harvested,
        )

    # ---------- Unified Energy Monitoring (New) ----------

    def save_energy_reading(self, **reading_data) -> int | None:
        """Save energy reading to unified EnergyReadings table."""
        return self._backend.save_energy_reading(**reading_data)

    def save_energy_consumption(
        self,
        *,
        monitor_id: int,
        power_watts: float,
        timestamp: str | None = None,
        voltage: float | None = None,
        current: float | None = None,
        energy_kwh: float | None = None,
        frequency: float | None = None,
        power_factor: float | None = None,
        temperature: float | None = None,
    ) -> int | None:
        """Save energy consumption reading to unified EnergyReadings table."""
        return self._backend.save_energy_consumption(
            monitor_id=monitor_id,
            power_watts=power_watts,
            timestamp=timestamp,
            voltage=voltage,
            current=current,
            energy_kwh=energy_kwh,
            frequency=frequency,
            power_factor=power_factor,
            temperature=temperature,
        )

    def get_power_reading_near_timestamp(
        self, device_id: int, timestamp: "datetime.datetime", tolerance_seconds: int = 30
    ) -> float | None:
        """Get power reading closest to timestamp within tolerance window."""
        return self._backend.get_power_reading_near_timestamp(device_id, timestamp, tolerance_seconds)

    def get_plant_energy_summary(self, plant_id: int) -> dict[str, object]:
        """Get comprehensive energy summary for a plant."""
        return self._backend.get_plant_energy_summary(plant_id)

    def save_harvest_summary(self, plant_id: int, summary: dict[str, object]) -> int:
        """Save comprehensive harvest summary when plant is harvested."""
        return self._backend.save_harvest_summary(plant_id, summary)

    def get_harvest_report(self, harvest_id: int) -> dict[str, object] | None:
        """Get complete harvest report by ID."""
        return self._backend.get_harvest_report(harvest_id)

    def get_all_harvest_reports(
        self,
        unit_id: int | None = None,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[dict[str, object]]:
        """
        Get all harvest reports with pagination, optionally filtered by unit.

        Args:
            unit_id: Optional unit filter
            limit: Number of results per page (default: 100, max: 500)
            offset: Number of results to skip (default: 0)

        Returns:
            List of harvest report dictionaries
        """
        return self._backend.get_all_harvest_reports(unit_id, limit=limit, offset=offset)

    def get_active_units(self) -> list[int]:
        """Get list of active growth unit IDs.

        Returns:
            List of unit IDs that are currently active (have an active plant)
        """
        try:
            db = self._backend.get_db()
            cursor = db.cursor()
            cursor.execute(
                """
                SELECT unit_id 
                FROM GrowthUnits 
                WHERE active_plant_id IS NOT NULL
                ORDER BY unit_id
                """
            )
            return [row[0] for row in cursor.fetchall()]
        except Exception as e:
            import logging

            logging.error(f"Error getting active units: {e}", exc_info=True)
            return []

    # Growth Cycle Comparison Methods ------------------------------------------
    def compare_growth_cycles(
        self,
        unit_id: int,
        limit: int = 10,
    ) -> dict[str, Any]:
        """
        Compare multiple growth cycles (harvests) for a unit.

        Provides side-by-side comparison with statistics and best performers.

        Args:
            unit_id: Growth unit ID
            limit: Number of harvests to compare

        Returns:
            Comparison data with statistics
        """
        return self._backend.compare_growth_cycles(unit_id, limit)

    def get_cycle_environmental_comparison(
        self,
        harvest_ids: list[int],
    ) -> dict[str, Any]:
        """
        Compare environmental conditions between specific cycles.

        Args:
            harvest_ids: List of harvest IDs to compare

        Returns:
            Environmental comparison data
        """
        return self._backend.get_cycle_environmental_comparison(harvest_ids)

    def get_plant_type_performance(
        self,
        plant_type: str,
        limit: int = 20,
    ) -> dict[str, Any]:
        """
        Get performance statistics for a specific plant type across all units.

        Args:
            plant_type: Plant type/species to analyze
            limit: Max records to analyze

        Returns:
            Performance statistics for the plant type
        """
        return self._backend.get_plant_type_performance(plant_type, limit)
