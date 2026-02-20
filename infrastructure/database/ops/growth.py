from __future__ import annotations

import logging
import sqlite3
from typing import Any

from infrastructure.database.pagination import validate_pagination
from infrastructure.utils.structured_fields import (
    dump_json_field,
    normalize_device_schedules,
    normalize_dimensions,
)


class GrowthOperations:
    """Growth unit and plant related helpers shared across database handlers."""

    # --- Growth units ---------------------------------------------------------
    def insert_growth_unit(
        self,
        name: str,
        location: str = "Indoor",
        user_id: int = None,
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
        air_quality_threshold: float = 100.0,
        camera_enabled: bool = False,
        aqi_threshold: float | None = None,
    ) -> int | None:
        """
        Insert a new growth unit.
        """
        try:
            db = self.get_db()
            cursor = db.cursor()
            if aqi_threshold is not None:
                air_quality_threshold = aqi_threshold

            cursor.execute(
                """
                INSERT INTO GrowthUnits (
                    name,
                    location,
                    user_id,
                    timezone,
                    dimensions,
                    custom_image,
                    active_plant_id,
                    temperature_threshold,
                    humidity_threshold,
                    soil_moisture_threshold,
                    co2_threshold,
                    voc_threshold,
                    lux_threshold,
                    air_quality_threshold,
                    camera_enabled

                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    name,
                    location,
                    user_id,
                    timezone,
                    dimensions,
                    custom_image,
                    active_plant_id,
                    temperature_threshold,
                    humidity_threshold,
                    soil_moisture_threshold,
                    co2_threshold,
                    voc_threshold,
                    lux_threshold,
                    air_quality_threshold,
                    camera_enabled,
                ),
            )
            db.commit()
            return cursor.lastrowid
        except sqlite3.Error as exc:
            logging.error("Error inserting growth unit: %s", exc)
            return None

    def get_growth_unit(self, unit_id: int):
        try:
            db = self.get_db()
            cursor = db.execute("SELECT * FROM GrowthUnits WHERE unit_id = ?", (unit_id,))
            return cursor.fetchone()
        except sqlite3.Error as exc:
            logging.error("Error fetching growth unit: %s", exc)
            return None

    def get_all_growth_units(
        self,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[Any]:
        """Get all growth units with pagination."""
        try:
            validated_limit, validated_offset = validate_pagination(limit, offset)
            db = self.get_db()
            cursor = db.execute(
                "SELECT * FROM GrowthUnits ORDER BY unit_id ASC LIMIT ? OFFSET ?",
                (validated_limit, validated_offset),
            )
            return cursor.fetchall()
        except sqlite3.Error as exc:
            logging.error("Error fetching all growth units: %s", exc)
            return []

    def update_growth_unit(self, unit_id: int, **fields: Any) -> None:
        """Update a growth unit row with the provided fields."""
        try:
            allowed_fields = {
                "name",
                "location",
                "user_id",
                "timezone",
                "dimensions",
                "custom_image",
                "active_plant_id",
                "temperature_threshold",
                "humidity_threshold",
                "soil_moisture_threshold",
                "co2_threshold",
                "voc_threshold",
                "lux_threshold",
                "air_quality_threshold",
                "camera_enabled",
            }

            updates: list[str] = []
            values: list[Any] = []

            for key, value in fields.items():
                if key not in allowed_fields or value is None:
                    continue
                updates.append(f"{key} = ?")
                values.append(value)

            if not updates:
                return

            values.append(unit_id)
            query = f"UPDATE GrowthUnits SET {', '.join(updates)} WHERE unit_id = ?"  # nosec B608 — allowed_fields allowlist above

            db = self.get_db()
            db.execute(query, values)
            db.commit()
        except sqlite3.Error as exc:
            logging.error("Error updating growth unit %s: %s", unit_id, exc)

    def update_growth_unit_settings(self, unit_id, settings):
        """Update threshold settings for a growth unit"""
        try:
            db = self.get_db()

            fields = []
            values = []

            # Threshold updates
            if "temperature_threshold" in settings:
                fields.append("temperature_threshold = ?")
                values.append(settings["temperature_threshold"])
            if "humidity_threshold" in settings:
                fields.append("humidity_threshold = ?")
                values.append(settings["humidity_threshold"])
            if "soil_moisture_threshold" in settings:
                fields.append("soil_moisture_threshold = ?")
                values.append(settings["soil_moisture_threshold"])
            if "co2_threshold" in settings:
                fields.append("co2_threshold = ?")
                values.append(settings["co2_threshold"])
            if "voc_threshold" in settings:
                fields.append("voc_threshold = ?")
                values.append(settings["voc_threshold"])
            if "lux_threshold" in settings:
                fields.append("lux_threshold = ?")
                values.append(settings["lux_threshold"])
            if "air_quality_threshold" in settings:
                fields.append("air_quality_threshold = ?")
                values.append(settings["air_quality_threshold"])
            elif "aqi_threshold" in settings:
                fields.append("air_quality_threshold = ?")
                values.append(settings["aqi_threshold"])

            # Dimensions (JSON string)
            if "dimensions" in settings:
                fields.append("dimensions = ?")
                values.append(settings["dimensions"])

            # Timezone
            if "timezone" in settings:
                fields.append("timezone = ?")
                values.append(settings["timezone"])

            # Camera enabled
            if "camera_enabled" in settings:
                fields.append("camera_enabled = ?")
                values.append(settings["camera_enabled"])

            if not fields:
                return True

            values.append(unit_id)
            query = f"UPDATE GrowthUnits SET {', '.join(fields)} WHERE unit_id = ?"  # nosec B608 — hardcoded field names above
            db.execute(query, values)
            db.commit()
            return True
        except sqlite3.Error as exc:
            logging.error("Error updating growth unit settings for unit %s: %s", unit_id, exc)
            return False

    def delete_growth_unit(self, unit_id: int) -> None:
        try:
            db = self.get_db()
            db.execute("DELETE FROM GrowthUnits WHERE unit_id = ?", (unit_id,))
            db.commit()
        except sqlite3.Error as exc:
            logging.error("Error deleting growth unit: %s", exc)

    # --- Plants ----------------------------------------------------------------
    def insert_plant(
        self,
        name: str,
        plant_type: str,
        current_stage: str,
        plant_species: str | None = None,
        plant_variety: str | None = None,
        days_in_stage: int = 0,
        moisture_level: float = 0.0,
        planted_date: str | None = None,
        created_at: str | None = None,
        unit_id: int | None = None,
        pot_size_liters: float = 0.0,
        pot_material: str = "plastic",
        growing_medium: str = "soil",
        medium_ph: float = 7.0,
        strain_variety: str | None = None,
        expected_yield_grams: float = 0.0,
        light_distance_cm: float = 0.0,
        soil_moisture_threshold_override: float | None = None,
    ) -> int | None:
        try:
            db = self.get_db()
            cursor = db.cursor()
            cursor.execute(
                """
                INSERT INTO Plants (
                    unit_id, name, plant_type, current_stage, plant_species, plant_variety,
                    days_in_stage, moisture_level, planted_date, created_at,
                    pot_size_liters, pot_material, growing_medium, medium_ph,
                    strain_variety, expected_yield_grams, light_distance_cm,
                    soil_moisture_threshold_override
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    unit_id,
                    name,
                    plant_type,
                    current_stage,
                    plant_species,
                    plant_variety,
                    days_in_stage,
                    moisture_level,
                    planted_date,
                    created_at,
                    pot_size_liters,
                    pot_material,
                    growing_medium,
                    medium_ph,
                    strain_variety,
                    expected_yield_grams,
                    light_distance_cm,
                    soil_moisture_threshold_override,
                ),
            )
            db.commit()
            return cursor.lastrowid
        except sqlite3.Error as exc:
            logging.error("Error inserting plant: %s", exc)
            return None

    def update_plant(self, plant_id: int, **fields: Any) -> None:
        """Update a plant row with the provided fields."""
        try:
            allowed_fields = {
                "name",
                "plant_type",
                "pot_size_liters",
                "pot_material",
                "growing_medium",
                "medium_ph",
                "strain_variety",
                "expected_yield_grams",
                "light_distance_cm",
                "temperature_threshold_override",
                "humidity_threshold_override",
                "soil_moisture_threshold_override",
                "co2_threshold_override",
                "voc_threshold_override",
                "lux_threshold_override",
                "air_quality_threshold_override",
            }

            updates: list[str] = []
            values: list[Any] = []

            for key, value in fields.items():
                if key not in allowed_fields or value is None:
                    continue
                updates.append(f"{key} = ?")
                values.append(value)

            if not updates:
                return

            values.append(plant_id)
            query = f"UPDATE Plants SET {', '.join(updates)} WHERE plant_id = ?"  # nosec B608 — allowed_fields allowlist above

            db = self.get_db()
            db.execute(query, values)
            db.commit()
        except sqlite3.Error as exc:
            logging.error("Error updating plant %s: %s", plant_id, exc)

    def remove_plant(self, plant_id: int) -> None:
        try:
            db = self.get_db()
            db.execute("DELETE FROM Plants WHERE plant_id = ?", (plant_id,))
            db.commit()
        except sqlite3.Error as exc:
            logging.error("Error removing plant: %s", exc)

    def get_plant_by_id(self, plant_id: int):
        try:
            db = self.get_db()
            cursor = db.execute(
                """
                SELECT
                    p.*,
                    COALESCE(gup.unit_id, p.unit_id) AS unit_id,
                    gu.name AS unit_name
                FROM Plants AS p
                LEFT JOIN GrowthUnitPlants AS gup ON p.plant_id = gup.plant_id
                LEFT JOIN GrowthUnits AS gu ON gu.unit_id = COALESCE(gup.unit_id, p.unit_id)
                WHERE p.plant_id = ?
                LIMIT 1
                """,
                (plant_id,),
            )
            return cursor.fetchone()
        except sqlite3.Error as exc:
            logging.error("Error getting plant by ID: %s", exc)
            return None

    def get_all_plants(
        self,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[Any]:
        """Get all plants with pagination."""
        try:
            validated_limit, validated_offset = validate_pagination(limit, offset)
            db = self.get_db()
            return db.execute(
                """
                SELECT
                    p.*,
                    COALESCE(gup.unit_id, p.unit_id) AS unit_id,
                    gu.name AS unit_name
                FROM Plants AS p
                LEFT JOIN GrowthUnitPlants AS gup ON p.plant_id = gup.plant_id
                LEFT JOIN GrowthUnits AS gu ON gu.unit_id = COALESCE(gup.unit_id, p.unit_id)
                ORDER BY p.plant_id ASC
                LIMIT ? OFFSET ?
                """,
                (validated_limit, validated_offset),
            ).fetchall()
        except sqlite3.Error as exc:
            logging.error("Error getting plants: %s", exc)
            return []

    def get_plants_for_unit(
        self,
        unit_id: int,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[Any]:
        """Get plants for a specific unit with pagination."""
        try:
            validated_limit, validated_offset = validate_pagination(limit, offset)
            db = self.get_db()
            cursor = db.execute(
                """
                SELECT
                    p.*,
                    COALESCE(gup.unit_id, p.unit_id) AS unit_id,
                    gu.name AS unit_name
                FROM Plants AS p
                LEFT JOIN GrowthUnitPlants AS gup ON p.plant_id = gup.plant_id
                LEFT JOIN GrowthUnits AS gu ON gu.unit_id = COALESCE(gup.unit_id, p.unit_id)
                WHERE COALESCE(gup.unit_id, p.unit_id) = ?
                ORDER BY p.plant_id ASC
                LIMIT ? OFFSET ?
                """,
                (unit_id, validated_limit, validated_offset),
            )
            return cursor.fetchall()
        except sqlite3.Error as exc:
            logging.error("Error retrieving plants for unit %s: %s", unit_id, exc)
            return []

    def assign_plant_to_unit(self, unit_id: int, plant_id: int) -> None:
        db = self.get_db()
        db.execute(
            """
            INSERT OR IGNORE INTO GrowthUnitPlants (unit_id, plant_id)
            VALUES (?, ?)
            """,
            (unit_id, plant_id),
        )
        # Keep Plants table in sync for deployments that still rely on unit_id column
        db.execute(
            "UPDATE Plants SET unit_id = ? WHERE plant_id = ?",
            (unit_id, plant_id),
        )
        db.commit()

    def remove_plant_from_unit(self, unit_id: int, plant_id: int) -> None:
        db = self.get_db()
        db.execute(
            "DELETE FROM GrowthUnitPlants WHERE unit_id = ? AND plant_id = ?",
            (unit_id, plant_id),
        )
        db.execute(
            "UPDATE Plants SET unit_id = NULL WHERE plant_id = ?",
            (plant_id,),
        )
        db.commit()

    # --- Plant sensors ---------------------------------------------------------
    def get_plant_sensors(self) -> list[dict[str, Any]]:
        db = self.get_db()
        cursor = db.execute("SELECT * FROM PlantSensors")
        return [dict(row) for row in cursor.fetchall()]

    def link_sensor_to_plant(self, plant_id: int, sensor_id: int) -> None:
        try:
            db = self.get_db()
            db.execute(
                "INSERT INTO PlantSensors (plant_id, sensor_id) VALUES (?, ?)",
                (plant_id, sensor_id),
            )
            db.commit()
        except sqlite3.Error as exc:
            logging.error("Error linking sensor %s to plant %s: %s", sensor_id, plant_id, exc)

    def get_sensors_for_plant(self, plant_id: int) -> list[Any]:
        try:
            db = self.get_db()
            query = "SELECT sensor_id FROM PlantSensors WHERE plant_id = ?"
            return [row["sensor_id"] for row in db.execute(query, (plant_id,)).fetchall()]
        except sqlite3.Error as exc:
            logging.error("Error retrieving sensors for plant %s: %s", plant_id, exc)
            return []

    def get_plants_for_sensor(self, sensor_id: int) -> list[int]:
        """Get plant IDs linked to a sensor."""
        try:
            db = self.get_db()
            query = "SELECT plant_id FROM PlantSensors WHERE sensor_id = ?"
            return [row["plant_id"] for row in db.execute(query, (sensor_id,)).fetchall()]
        except sqlite3.Error as exc:
            logging.error("Error retrieving plants for sensor %s: %s", sensor_id, exc)
            return []

    def unlink_sensor_from_plant(self, plant_id: int, sensor_id: int) -> None:
        """Remove sensor link from a specific plant"""
        try:
            db = self.get_db()
            db.execute(
                "DELETE FROM PlantSensors WHERE plant_id = ? AND sensor_id = ?",
                (plant_id, sensor_id),
            )
            db.commit()
        except sqlite3.Error as exc:
            logging.error("Error unlinking sensor %s from plant %s: %s", sensor_id, plant_id, exc)

    def unlink_all_sensors_from_plant(self, plant_id: int) -> None:
        """Remove all sensor links from a plant"""
        try:
            db = self.get_db()
            db.execute("DELETE FROM PlantSensors WHERE plant_id = ?", (plant_id,))
            db.commit()
        except sqlite3.Error as exc:
            logging.error("Error unlinking all sensors from plant %s: %s", plant_id, exc)

    # --- Plant actuators -------------------------------------------------------
    def link_actuator_to_plant(self, plant_id: int, actuator_id: int) -> None:
        try:
            db = self.get_db()
            db.execute(
                "INSERT INTO PlantActuators (plant_id, actuator_id) VALUES (?, ?)",
                (plant_id, actuator_id),
            )
            db.commit()
        except sqlite3.Error as exc:
            logging.error("Error linking actuator %s to plant %s: %s", actuator_id, plant_id, exc)

    def get_actuators_for_plant(self, plant_id: int) -> list[int]:
        try:
            db = self.get_db()
            query = "SELECT actuator_id FROM PlantActuators WHERE plant_id = ?"
            return [row["actuator_id"] for row in db.execute(query, (plant_id,)).fetchall()]
        except sqlite3.Error as exc:
            logging.error("Error retrieving actuators for plant %s: %s", plant_id, exc)
            return []

    def unlink_actuator_from_plant(self, plant_id: int, actuator_id: int) -> None:
        try:
            db = self.get_db()
            db.execute(
                "DELETE FROM PlantActuators WHERE plant_id = ? AND actuator_id = ?",
                (plant_id, actuator_id),
            )
            db.commit()
        except sqlite3.Error as exc:
            logging.error("Error unlinking actuator %s from plant %s: %s", actuator_id, plant_id, exc)

    def unlink_all_actuators_from_plant(self, plant_id: int) -> None:
        try:
            db = self.get_db()
            db.execute("DELETE FROM PlantActuators WHERE plant_id = ?", (plant_id,))
            db.commit()
        except sqlite3.Error as exc:
            logging.error("Error unlinking all actuators from plant %s: %s", plant_id, exc)

    # --- Active plant helpers --------------------------------------------------
    def set_active_plant(self, plant_id: int) -> None:
        db = self.get_db()
        db.execute("UPDATE Settings SET active_plant_id = ?", (plant_id,))
        db.commit()

    def get_active_plant(self) -> int | None:
        db = self.get_db()
        active_plant = db.execute("SELECT active_plant_id FROM Settings LIMIT 1").fetchone()
        return active_plant["active_plant_id"] if active_plant else None

    def get_all_active_plants(
        self,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[dict[str, Any]]:
        """Get all active plants across growth units with pagination."""
        try:
            validated_limit, validated_offset = validate_pagination(limit, offset)
            db = self.get_db()
            cursor = db.execute(
                """
                SELECT
                    gu.unit_id,
                    gu.name AS unit_name,
                    p.plant_id,
                    p.name AS plant_name,
                    p.plant_type,
                    p.current_stage as current_stage,
                    p.current_stage as growth_stage,
                    p.days_in_stage,
                    p.moisture_level,
                    p.planted_date,
                    p.created_at
                FROM GrowthUnits AS gu
                JOIN Plants AS p ON gu.active_plant_id = p.plant_id
                WHERE gu.active_plant_id IS NOT NULL
                ORDER BY gu.unit_id ASC
                LIMIT ? OFFSET ?
                """,
                (validated_limit, validated_offset),
            )
            return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error as exc:
            logging.error("Error fetching all active plants: %s", exc)
            return []

    # --- Plant analytics -------------------------------------------------------
    def update_plant_days(self, plant_name: str, days_in_current_stage: int) -> None:
        try:
            db = self.get_db()
            db.execute(
                "UPDATE Plants SET days_in_current_stage = ? WHERE name = ?",
                (days_in_current_stage, plant_name),
            )
            db.commit()
        except sqlite3.Error as exc:
            logging.error("Error updating plant days: %s", exc)

    def update_plant_soil_moisture(self, plant_name: str, moisture_level: float) -> None:
        try:
            db = self.get_db()
            db.execute(
                "UPDATE Plants SET moisture_level = ? WHERE name = ?",
                (moisture_level, plant_name),
            )
            db.commit()
        except sqlite3.Error as exc:
            logging.error("Error updating plant moisture: %s", exc)

    def update_plant_moisture_by_id(self, plant_id: int, moisture_level: float) -> None:
        try:
            db = self.get_db()
            db.execute(
                "UPDATE Plants SET moisture_level = ? WHERE plant_id = ?",
                (moisture_level, plant_id),
            )
            db.commit()
        except sqlite3.Error as exc:
            logging.error("Error updating plant moisture for %s: %s", plant_id, exc)

    def bulk_update_plant_moisture(self, plant_ids: list[int], moisture_level: float) -> None:
        """Batch-update moisture_level for multiple plants in a single transaction."""
        if not plant_ids:
            return
        try:
            db = self.get_db()
            db.executemany(
                "UPDATE Plants SET moisture_level = ? WHERE plant_id = ?",
                [(moisture_level, pid) for pid in plant_ids],
            )
            db.commit()
        except sqlite3.Error as exc:
            logging.error("Error bulk-updating moisture for %s plants: %s", len(plant_ids), exc)

    def update_plant_progress(
        self,
        plant_id: int,
        current_stage: str,
        moisture_level: float,
        days_in_stage: int,
    ) -> None:
        try:
            db = self.get_db()
            db.execute(
                """
                UPDATE Plants
                SET current_stage = ?, days_in_stage = ?, moisture_level = ?
                WHERE plant_id = ?
                """,
                (current_stage, days_in_stage, moisture_level, plant_id),
            )
            db.commit()
        except sqlite3.Error as exc:
            logging.error("Error updating plant progress: %s", exc)

    def insert_plant_history(
        self,
        plant_name: str,
        current_stage: str,
        days_in_stage: int,
        avg_temp: float,
        avg_humidity: float,
        light_hours: float,
        harvest_weight: float | None,
        photo_path: str | None,
        date_harvested: str,
    ) -> None:
        try:
            db = self.get_db()
            db.execute(
                """
                INSERT INTO PlantHistory(
                    plant_name, current_stage, days_in_stage,
                    average_temp, average_humidity, light_hours,
                    harvest_weight, photo_path, date_harvested
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    plant_name,
                    current_stage,
                    days_in_stage,
                    avg_temp,
                    avg_humidity,
                    light_hours,
                    harvest_weight,
                    photo_path,
                    date_harvested,
                ),
            )
            db.commit()
        except sqlite3.Error as exc:
            logging.error("Error inserting plant history: %s", exc)

    def get_plant_avg_temperature(self, plant_id: int) -> float:
        try:
            db = self.get_db()
            row = db.execute(
                """
                SELECT AVG(sr.value) AS avg_val
                FROM SensorReading sr
                JOIN PlantSensors ps ON ps.sensor_id = sr.sensor_id
                WHERE ps.plant_id = ? AND sr.metric = 'temperature'
                """,
                (plant_id,),
            ).fetchone()
            return float(row["avg_val"] or 0.0) if row else 0.0
        except sqlite3.Error as exc:
            logging.error("Error computing temp avg for plant %s: %s", plant_id, exc)
            return 0.0

    def get_plant_avg_humidity(self, plant_id: int) -> float:
        try:
            db = self.get_db()
            row = db.execute(
                """
                SELECT AVG(sr.value) AS avg_val
                FROM SensorReading sr
                JOIN PlantSensors ps ON ps.sensor_id = sr.sensor_id
                WHERE ps.plant_id = ? AND sr.metric = 'humidity'
                """,
                (plant_id,),
            ).fetchone()
            return float(row["avg_val"] or 0.0) if row else 0.0
        except sqlite3.Error as exc:
            logging.error("Error computing humidity avg for plant %s: %s", plant_id, exc)
            return 0.0

    def get_plant_total_light_hours(self, plant_id: int) -> float:
        try:
            db = self.get_db()
            row = db.execute(
                """
                SELECT COALESCE(SUM(sr.value), 0) AS total_hours
                FROM SensorReading sr
                JOIN PlantSensors ps ON ps.sensor_id = sr.sensor_id
                WHERE ps.plant_id = ? AND sr.metric = 'light_hours'
                """,
                (plant_id,),
            ).fetchone()
            return float(row["total_hours"] or 0.0) if row else 0.0
        except sqlite3.Error as exc:
            logging.error("Error computing light hours for plant %s: %s", plant_id, exc)
            return 0.0

    def get_latest_threshold_overrides(
        self,
        *,
        user_id: int,
        plant_type: str,
        growth_stage: str,
        plant_variety: str | None = None,
        strain_variety: str | None = None,
        pot_size_liters: float | None = None,
    ) -> dict[str, Any] | None:
        """Fetch the latest plant threshold overrides for a matching plant context."""
        try:
            db = self.get_db()
            query = """
                SELECT
                    p.temperature_threshold_override,
                    p.humidity_threshold_override,
                    p.co2_threshold_override,
                    p.voc_threshold_override,
                    p.lux_threshold_override,
                    p.air_quality_threshold_override,
                    p.soil_moisture_threshold_override,
                    p.current_stage,
                    p.plant_type,
                    p.plant_variety,
                    p.strain_variety,
                    p.pot_size_liters,
                    p.last_updated,
                    p.created_at
                FROM Plants p
                JOIN GrowthUnits u ON u.unit_id = p.unit_id
                WHERE u.user_id = ?
                  AND p.plant_type = ?
                  AND LOWER(COALESCE(p.current_stage, '')) = LOWER(?)
            """
            params: list[Any] = [user_id, plant_type, growth_stage]
            if plant_variety:
                query += " AND LOWER(COALESCE(p.plant_variety, '')) = LOWER(?)"
                params.append(plant_variety)
            if strain_variety:
                query += " AND LOWER(COALESCE(p.strain_variety, '')) = LOWER(?)"
                params.append(strain_variety)
            if pot_size_liters is not None:
                query += " AND ABS(COALESCE(p.pot_size_liters, 0) - ?) < 0.01"
                params.append(float(pot_size_liters))

            query += """
                  AND (
                    p.temperature_threshold_override IS NOT NULL
                    OR p.humidity_threshold_override IS NOT NULL
                    OR p.co2_threshold_override IS NOT NULL
                    OR p.voc_threshold_override IS NOT NULL
                    OR p.lux_threshold_override IS NOT NULL
                    OR p.air_quality_threshold_override IS NOT NULL
                    OR p.soil_moisture_threshold_override IS NOT NULL
                  )
                ORDER BY COALESCE(p.last_updated, p.created_at) DESC
                LIMIT 1
            """
            row = db.execute(query, params).fetchone()
            return dict(row) if row else None
        except sqlite3.Error as exc:
            logging.error("Error fetching threshold overrides: %s", exc)
            return None

    # --- Multi-user support ---------------------------------------------------
    def get_user_growth_units(self, user_id: int) -> list[dict[str, Any]]:
        """Get all growth units for a specific user."""
        try:
            db = self.get_db()
            cursor = db.execute(
                """
                SELECT *
                FROM GrowthUnits
                WHERE user_id = ?
                ORDER BY created_at DESC
                """,
                (user_id,),
            )
            rows = cursor.fetchall()

            units = []
            for row in rows:
                unit = dict(row)
                unit["dimensions"] = normalize_dimensions(unit.get("dimensions"))
                unit["device_schedules"] = normalize_device_schedules(unit.get("device_schedules"))
                units.append(unit)

            return units
        except sqlite3.Error as exc:
            logging.error("Error fetching units for user %s: %s", user_id, exc)
            return []

    def insert_growth_unit_with_user(self, user_id: int, name: str, location: str, data: dict[str, Any]) -> int | None:
        """Create a new growth unit with user association."""
        try:
            db = self.get_db()
            cursor = db.cursor()

            normalized_dimensions = normalize_dimensions(data.get("dimensions"))
            dimensions_json = dump_json_field(normalized_dimensions)
            device_schedules = normalize_device_schedules(data.get("device_schedules"))
            device_schedules_json = dump_json_field(device_schedules)

            cursor.execute(
                """
                INSERT INTO GrowthUnits (
                    user_id,
                    name,
                    location,
                    timezone,
                    dimensions,
                    custom_image,
                    active_plant_id,
                    created_at,
                    temperature_threshold,
                    humidity_threshold,
                    soil_moisture_threshold,
                    co2_threshold,
                    voc_threshold,
                    lux_threshold,
                    air_quality_threshold,
                    device_schedules,
                    camera_enabled
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'), ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    name,
                    location,
                    data.get("timezone"),
                    dimensions_json,
                    data.get("custom_image"),
                    data.get("active_plant_id"),
                    data.get("temperature_threshold", 24.0),
                    data.get("humidity_threshold", 50.0),
                    data.get("soil_moisture_threshold", 40.0),
                    data.get("co2_threshold", 1000.0),
                    data.get("voc_threshold", 1000.0),
                    data.get("lux_threshold", data.get("lux_threshold", 1000.0)),
                    data.get("air_quality_threshold", data.get("aqi_threshold", 100.0)),
                    device_schedules_json,
                    data.get("camera_enabled", False),
                ),
            )
            db.commit()
            return cursor.lastrowid
        except sqlite3.Error as exc:
            logging.error("Error inserting unit for user %s: %s", user_id, exc)
            return None

    def update_unit_settings(self, unit_id: int, settings: dict[str, Any]) -> bool:
        """Update unit settings."""
        try:
            db = self.get_db()
            fields = []
            values = []

            # Threshold updates
            if "temperature_threshold" in settings:
                fields.append("temperature_threshold = ?")
                values.append(settings["temperature_threshold"])
            if "humidity_threshold" in settings:
                fields.append("humidity_threshold = ?")
                values.append(settings["humidity_threshold"])
            if "soil_moisture_threshold" in settings:
                fields.append("soil_moisture_threshold = ?")
                values.append(settings["soil_moisture_threshold"])
            if "co2_threshold" in settings:
                fields.append("co2_threshold = ?")
                values.append(settings["co2_threshold"])

            # Device schedules (NEW)
            if "device_schedules" in settings:
                fields.append("device_schedules = ?")
                values.append(settings["device_schedules"])

            # Dimensions (JSON string)
            if "dimensions" in settings:
                fields.append("dimensions = ?")
                values.append(settings["dimensions"])

            # Timezone
            if "timezone" in settings:
                fields.append("timezone = ?")
                values.append(settings["timezone"])

            if fields:
                fields.append("updated_at = CURRENT_TIMESTAMP")

            if not fields:
                return True

            values.append(unit_id)
            query = f"UPDATE GrowthUnits SET {', '.join(fields)} WHERE unit_id = ?"  # nosec B608 — hardcoded field names above
            db.execute(query, values)
            db.commit()
            return True
        except sqlite3.Error as exc:
            logging.error("Error updating unit settings for unit %s: %s", unit_id, exc)
            return False

    # --- Statistics helpers ---------------------------------------------------
    def count_plants_in_unit(self, unit_id: int) -> int:
        """Count active plants in a unit."""
        try:
            db = self.get_db()
            # Prefer direct Plants.unit_id if present
            try:
                cursor = db.execute(
                    "SELECT COUNT(*) as count FROM Plants WHERE unit_id = ?",
                    (unit_id,),
                )
                result = cursor.fetchone()
                if result and result["count"] is not None:
                    return int(result["count"])
            except sqlite3.Error:
                pass

            # Fallback: mapping table
            try:
                cursor = db.execute(
                    """
                    SELECT COUNT(*) as count
                    FROM GrowthUnitPlants
                    WHERE unit_id = ?
                    """,
                    (unit_id,),
                )
                result = cursor.fetchone()
                if result and result["count"] is not None:
                    return int(result["count"])
            except sqlite3.Error:
                pass

            return 0
        except sqlite3.Error as exc:
            logging.error("Error counting plants for unit %s: %s", unit_id, exc)
            return 0

    def count_sensors_in_unit(self, unit_id: int) -> int:
        """Count sensors linked to a unit."""
        try:
            db = self.get_db()
            cursor = db.execute(
                """
                SELECT COUNT(*) as count
                FROM Sensor
                WHERE unit_id = ?
                """,
                (unit_id,),
            )
            result = cursor.fetchone()
            return result["count"] if result else 0
        except sqlite3.Error as exc:
            logging.error("Error counting sensors for unit %s: %s", unit_id, exc)
            return 0

    def count_actuators_in_unit(self, unit_id: int) -> int:
        """Count actuators linked to a unit."""
        try:
            db = self.get_db()
            cursor = db.execute(
                """
                SELECT COUNT(*) as count
                FROM Actuator
                WHERE unit_id = ?
                """,
                (unit_id,),
            )
            result = cursor.fetchone()
            return result["count"] if result else 0
        except sqlite3.Error as exc:
            logging.error("Error counting actuators for unit %s: %s", unit_id, exc)
            return 0

    def is_camera_active(self, unit_id: int) -> bool:
        """Check if camera is active for a unit."""
        try:
            db = self.get_db()
            cursor = db.execute(
                """
                SELECT camera_enabled
                FROM GrowthUnits
                WHERE unit_id = ?
                """,
                (unit_id,),
            )
            result = cursor.fetchone()
            return bool(result["camera_enabled"]) if result and "camera_enabled" in result else False
        except sqlite3.Error as exc:
            logging.error("Error checking camera status for unit %s: %s", unit_id, exc)
            return False

    def get_unit_last_activity(self, unit_id: int) -> str | None:
        """Get last activity timestamp for a unit."""
        try:
            db = self.get_db()
            cursor = db.execute(
                """
                SELECT MAX(timestamp) as last_activity
                FROM SensorReading
                WHERE sensor_id IN (
                    SELECT sensor_id FROM Sensor WHERE unit_id = ?
                )
                """,
                (unit_id,),
            )
            result = cursor.fetchone()
            return result["last_activity"] if result else None
        except sqlite3.Error as exc:
            logging.error("Error getting last activity for unit %s: %s", unit_id, exc)
            return None

    def get_unit_uptime_hours(self, unit_id: int) -> int:
        """Get uptime in hours since unit was created."""
        try:
            db = self.get_db()
            cursor = db.execute(
                """
                SELECT
                    CAST((julianday('now') - julianday(created_at)) * 24 AS INTEGER) as uptime_hours
                FROM GrowthUnits
                WHERE unit_id = ?
                """,
                (unit_id,),
            )
            result = cursor.fetchone()
            return result["uptime_hours"] if result else 0
        except sqlite3.Error as exc:
            logging.error("Error getting uptime for unit %s: %s", unit_id, exc)
            return 0

    def get_plants_in_unit(self, unit_id: int) -> list[dict[str, Any]]:
        """Get detailed plant information for a unit."""
        try:
            plants = self.get_plants_for_unit(unit_id)
            result = []
            for plant in plants:
                plant_dict = dict(plant)
                # Ensure we have the required fields
                plant_dict["plant_name"] = plant_dict.get("name", "Unknown Plant")
                plant_dict["plant_type"] = plant_dict.get("plant_type", "unknown")
                plant_dict["moisture_level"] = plant_dict.get("moisture_level", 0.0)
                plant_dict["current_stage"] = plant_dict.get("current_stage", "Unknown")
                result.append(plant_dict)
            return result
        except Exception as exc:
            logging.error("Error getting plants for unit %s: %s", unit_id, exc)
            return []

    # Placeholder to satisfy static analysers; implemented by concrete handler.
    def get_db(self):  # pragma: no cover
        raise NotImplementedError
