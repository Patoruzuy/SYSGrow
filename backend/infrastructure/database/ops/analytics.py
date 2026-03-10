from __future__ import annotations

import json
import logging
import math
import sqlite3
from datetime import UTC, datetime
from typing import Any

from infrastructure.database.pagination import validate_pagination
from infrastructure.utils.time import iso_now

logger = logging.getLogger(__name__)


class AnalyticsOperations:
    """Aggregate and history helpers for sensors and plants."""

    @staticmethod
    def _timestamp_query_param(dt: datetime) -> str:
        """Return ISO8601 timestamp suitable for lexical range filtering.

        We strip timezone offsets to keep comparisons compatible with older rows
        stored as naive ISO strings.
        """
        if dt.tzinfo is not None:
            dt = dt.astimezone(UTC).replace(tzinfo=None)
        return dt.isoformat()

    def _decode_reading_payload(self, row: dict[str, Any]) -> dict[str, Any]:
        """
        Decode a SensorReading row into a flat dict of metric keys.

        The reading_data JSON column already contains standardized field names
        (lux, co2, voc, etc.) because the processor pipeline normalizes them
        before storage. No additional translation is needed here.
        """
        raw = row.get("reading_data")
        if not raw:
            return {}
        try:
            decoded = json.loads(raw)
        except (TypeError, ValueError):
            logging.warning("Failed to decode reading_data JSON payload")
            return {}

        if not isinstance(decoded, dict):
            return {}

        return decoded

    def insert_sensor_reading(
        self,
        *,
        sensor_id: int,
        reading_data: dict[str, Any],
        quality_score: float = 1.0,
        timestamp: str | None = None,
    ) -> int | None:
        """
        Insert a sensor reading into the database.

        Args:
            sensor_id: ID of the sensor
            reading_data: JSON payload of readings (e.g. {"temperature": 24.0, "humidity": 50.0})
            quality_score: Optional quality score for the reading (default 1.0)
            timestamp: Optional ISO-8601 timestamp override (defaults to now)
        """
        stamp = timestamp or iso_now()
        try:
            with self.connection() as db:
                cursor = db.execute(
                    """
                    INSERT INTO SensorReading (sensor_id, timestamp, reading_data, quality_score)
                    VALUES (?, ?, ?, ?)
                    """,
                    (sensor_id, stamp, json.dumps(reading_data), quality_score),
                )
                return cursor.lastrowid
        except sqlite3.Error as exc:
            logging.error("Error inserting sensor reading (sensor_id=%s): %s", sensor_id, exc)
            return None

    # --- Sensor history -------------------------------------------------------
    def get_sensor_data(self, limit: int = 20, offset: int = 0) -> list[dict[str, Any]]:
        """
        Retrieve sensor readings ordered by newest first.

        Args:
            limit: Maximum number of rows to return.
            offset: Number of rows to skip (for pagination).
        """
        try:
            db = self.get_db()
            cursor = db.execute(
                """
                SELECT reading_id, sensor_id, timestamp, reading_data, quality_score
                FROM SensorReading
                ORDER BY timestamp DESC
                LIMIT ? OFFSET ?
                """,
                (limit, offset),
            )
            rows = []
            for row in cursor.fetchall():
                as_dict = dict(row)
                payload = self._decode_reading_payload(as_dict)
                rows.append(
                    {
                        "reading_id": as_dict.get("reading_id"),
                        "sensor_id": as_dict.get("sensor_id"),
                        "timestamp": as_dict.get("timestamp"),
                        "quality_score": as_dict.get("quality_score"),
                        **payload,
                    }
                )
            return rows
        except sqlite3.Error as exc:
            logging.error("Error getting sensor data: %s", exc)
            return []

    def get_latest_sensor_readings(self, unit_id: int) -> dict[str, float | None]:
        """
        Retrieve the latest reading snapshot for a growth unit.

        Scans recent SensorReading rows to populate the most recent value for
        each metric. Returns None for any metric with no observed data.
        """
        from app.domain.sensors.fields import SensorField

        db = self.get_db()
        keys = [f.value for f in SensorField]
        query = """
            SELECT timestamp, reading_data
            FROM SensorReading
            WHERE sensor_id IN (
                SELECT sensor_id
                FROM Sensor
                WHERE unit_id = ?
            )
            ORDER BY timestamp DESC
            LIMIT ?
        """
        rows = db.execute(query, (unit_id, 50)).fetchall()
        if not rows:
            return {k: None for k in keys}

        latest_values = {k: None for k in keys}
        remaining = set(keys)

        for row in rows:
            payload = self._decode_reading_payload(dict(row))
            if not payload:
                continue
            for key in list(remaining):
                if key in payload and payload[key] is not None:
                    latest_values[key] = payload[key]
                    remaining.remove(key)
            if not remaining:
                break

        return latest_values

    def save_plant_reading(
        self,
        plant_id: int | None = None,
        unit_id: int | None = None,
        soil_moisture: float | None = None,
        ph: float | None = None,
        ec: float | None = None,
        timestamp: str | None = None,
    ) -> int | None:
        """
        Save plant sensor readings to PlantReadings table.

        PlantReadings is now reserved for plant sensor metrics (e.g. soil moisture, pH, EC).
        Environmental metrics are stored in SensorReading instead.
        Records snapshots for ALL plants in the unit if plant_id is not specified.
        """
        db = self.get_db()
        ts = timestamp or iso_now()

        # Only plant sensor metrics are persisted in PlantReadings.

        try:
            target_plant_ids = []
            if plant_id is not None:
                target_plant_ids.append(plant_id)
                # Resolve unit_id if missing but plant_id is present
                if unit_id is None:
                    plant_info = db.execute("SELECT unit_id FROM Plants WHERE plant_id = ?", (plant_id,)).fetchone()
                    if plant_info:
                        unit_id = plant_info["unit_id"]
            elif unit_id is not None:
                # Find all plants in this unit to store readings for each
                plants = db.execute("SELECT plant_id FROM Plants WHERE unit_id = ?", (unit_id,)).fetchall()
                target_plant_ids = [p["plant_id"] for p in plants]

            if not target_plant_ids:
                logger.info(f"No plants found to record snapshot for unit {unit_id}")
                return None

            last_id = None
            for p_id in target_plant_ids:
                cursor = db.execute(
                    """
                    INSERT INTO PlantReadings (
                        plant_id, unit_id, soil_moisture,
                        ph, ec, timestamp
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        p_id,
                        unit_id,
                        soil_moisture,
                        ph,
                        ec,
                        ts,
                    ),
                )
                last_id = cursor.lastrowid

            db.commit()
            return last_id
        except sqlite3.Error as e:
            logger.error(f"Failed to insert plant reading: {e}")
            return None

    def get_plant_id_for_sensor(self, sensor_id: int) -> int | None:
        """
        Look up the plant_id associated with a sensor via PlantSensors table.

        Args:
            sensor_id: The sensor ID

        Returns:
            plant_id if a mapping exists, None otherwise
        """
        db = self.get_db()
        row = db.execute(
            """
            SELECT plant_id FROM PlantSensors WHERE sensor_id = ? LIMIT 1
            """,
            (sensor_id,),
        ).fetchone()
        return row["plant_id"] if row else None

    def get_all_plant_readings(self, limit: int | None = None, offset: int | None = None) -> list[dict[str, Any]]:
        """Return plant readings ordered by newest first."""
        db = self.get_db()
        query = "SELECT * FROM PlantReadings ORDER BY timestamp DESC"
        params: list[Any] = []

        if limit is not None:
            query += " LIMIT ?"
            params.append(limit)
        if offset is not None:
            query += " OFFSET ?"
            params.append(offset)

        return [dict(row) for row in db.execute(query, params).fetchall()]

    def get_latest_plant_readings(self, plant_id: int, limit: int = 1) -> list[dict[str, Any]]:
        """
        Get most recent PlantReadings for a specific plant.

        Args:
            plant_id: The plant ID
            limit: Maximum number of readings to return

        Returns:
            List of plant reading dictionaries ordered by newest first
        """
        try:
            db = self.get_db()
            query = """
                SELECT *
                FROM PlantReadings
                WHERE plant_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
            """
            rows = db.execute(query, (plant_id, limit)).fetchall()
            return [dict(row) for row in rows]
        except sqlite3.Error as exc:
            logging.error(f"Error getting latest plant readings for {plant_id}: {exc}")
            return []

    def get_plant_readings_in_window(
        self,
        plant_id: int,
        start: str,
        end: str,
    ) -> list[dict[str, Any]]:
        """
        Get PlantReadings in time window for a plant.

        Args:
            plant_id: The plant ID
            start: Start timestamp (ISO 8601)
            end: End timestamp (ISO 8601)

        Returns:
            List of plant reading dictionaries ordered by timestamp
        """
        try:
            db = self.get_db()
            query = """
                SELECT *
                FROM PlantReadings
                WHERE plant_id = ?
                  AND timestamp >= ?
                  AND timestamp <= ?
                ORDER BY timestamp ASC
            """
            rows = db.execute(query, (plant_id, start, end)).fetchall()
            return [dict(row) for row in rows]
        except sqlite3.Error as exc:
            logging.error(f"Error getting plant readings in window for {plant_id}: {exc}")
            return []

    def get_plants_needing_attention(
        self,
        unit_id: int | None = None,
        moisture_threshold: float = 30.0,
        hours_since_reading: int = 24,
    ) -> list[dict[str, Any]]:
        """
        Find plants with concerning readings (dry, overwatered, no recent data).

        Args:
            unit_id: Optional filter by growth unit
            moisture_threshold: Soil moisture below which plant needs attention
            hours_since_reading: Hours without data to flag as stale

        Returns:
            List of plants needing attention with reason
        """
        try:
            db = self.get_db()
            results = []
            now_ts = iso_now()

            # Build base query for active plants
            if unit_id is not None:
                plant_query = """
                    SELECT p.plant_id, p.name, p.plant_type, p.unit_id, p.moisture_level
                    FROM Plants p
                    WHERE p.unit_id = ? AND p.is_active = 1
                """
                plants = db.execute(plant_query, (unit_id,)).fetchall()
            else:
                plant_query = """
                    SELECT p.plant_id, p.name, p.plant_type, p.unit_id, p.moisture_level
                    FROM Plants p
                    WHERE p.is_active = 1
                """
                plants = db.execute(plant_query).fetchall()

            for plant in plants:
                plant_dict = dict(plant)
                plant_id = plant_dict["plant_id"]
                reasons = []

                # Check in-memory moisture level
                moisture = plant_dict.get("moisture_level")
                if moisture is not None and moisture < moisture_threshold:
                    reasons.append(f"Low soil moisture: {moisture:.0f}%")

                # Check latest PlantReading
                latest = db.execute(
                    """
                    SELECT soil_moisture, ph, ec, timestamp
                    FROM PlantReadings
                    WHERE plant_id = ?
                    ORDER BY timestamp DESC
                    LIMIT 1
                    """,
                    (plant_id,),
                ).fetchone()

                if latest:
                    latest_dict = dict(latest)
                    soil = latest_dict.get("soil_moisture")
                    if soil is not None and soil < moisture_threshold:
                        reasons.append(f"Recent reading shows low moisture: {soil:.0f}%")
                    elif soil is not None and soil > 85:
                        reasons.append(f"Recent reading shows overwatering: {soil:.0f}%")

                    # Check for stale data
                    ts = latest_dict.get("timestamp")
                    if ts:
                        try:
                            from datetime import datetime

                            reading_dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                            now_dt = datetime.fromisoformat(now_ts.replace("Z", "+00:00"))
                            hours_diff = (now_dt - reading_dt).total_seconds() / 3600
                            if hours_diff > hours_since_reading:
                                reasons.append(f"No data for {int(hours_diff)} hours")
                        except (ValueError, TypeError):
                            pass
                else:
                    reasons.append("No sensor data available")

                if reasons:
                    results.append(
                        {
                            "plant_id": plant_id,
                            "plant_name": plant_dict.get("name"),
                            "plant_type": plant_dict.get("plant_type"),
                            "unit_id": plant_dict.get("unit_id"),
                            "reasons": reasons,
                        }
                    )

            return results

        except sqlite3.Error as exc:
            logging.error(f"Error finding plants needing attention: {exc}")
            return []

    def get_latest_plant_moisture_in_window(
        self,
        plant_id: int,
        *,
        start_ts: str,
        end_ts: str,
    ) -> dict[str, Any] | None:
        """Fetch the latest plant moisture reading within a time window."""
        db = self.get_db()
        row = db.execute(
            """
            SELECT soil_moisture, timestamp
            FROM PlantReadings
            WHERE plant_id = ?
              AND soil_moisture IS NOT NULL
              AND timestamp >= ?
              AND timestamp <= ?
            ORDER BY timestamp DESC
            LIMIT 1
            """,
            (plant_id, start_ts, end_ts),
        ).fetchone()
        return dict(row) if row else None

    def get_plant_moisture_readings_in_window(
        self,
        plant_id: int,
        *,
        start_ts: str,
        end_ts: str,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch plant moisture readings within a time window."""
        db = self.get_db()
        query = """
            SELECT soil_moisture, timestamp
            FROM PlantReadings
            WHERE plant_id = ?
              AND soil_moisture IS NOT NULL
              AND timestamp >= ?
              AND timestamp <= ?
            ORDER BY timestamp ASC
        """
        params: list[Any] = [plant_id, start_ts, end_ts]
        if limit is not None:
            query += " LIMIT ?"
            params.append(limit)

        rows = db.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    # --- Plant analytics ------------------------------------------------------
    def insert_plant_history(
        self,
        plant_name: str,
        days_germination: int,
        days_seed: int,
        days_veg: int,
        days_flower: int,
        days_fruit_dev: int,
        avg_temp: float,
        avg_humidity: float,
        light_hours: float,
        harvest_weight: float,
        photo_path: str,
        date_harvested: str,
    ) -> None:
        db = self.get_db()
        db.execute(
            """
            INSERT INTO plant_history (
                plant_name,
                days_germination,
                days_seed,
                days_veg,
                days_flower,
                days_fruit_dev,
                avg_temp,
                avg_humidity,
                light_hours,
                harvest_weight,
                photo_path,
                date_harvested
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                plant_name,
                days_germination,
                days_seed,
                days_veg,
                days_flower,
                days_fruit_dev,
                avg_temp,
                avg_humidity,
                light_hours,
                harvest_weight,
                photo_path,
                date_harvested,
            ),
        )
        db.commit()

    def get_average_temperature(self, plant_id: int) -> float:
        try:
            return self._get_average_environment_metric(plant_id, "temperature")
        except sqlite3.Error as exc:
            logging.error("Error calculating average temperature for plant %s: %s", plant_id, exc)
            return 0.0

    def get_average_humidity(self, plant_id: int) -> float:
        try:
            return self._get_average_environment_metric(plant_id, "humidity")
        except sqlite3.Error as exc:
            logging.error("Error calculating average humidity for plant %s: %s", plant_id, exc)
            return 0.0

    def _get_average_environment_metric(self, plant_id: int, metric_key: str) -> float:
        """Compute an environmental average from SensorReading payloads.

        PlantReadings no longer stores environmental values such as temperature
        and humidity, so harvest analytics now derive those values from
        SensorReading JSON payloads.
        """
        db = self.get_db()

        plant = db.execute(
            """
            SELECT
                COALESCE(gup.unit_id, p.unit_id) AS unit_id,
                COALESCE(p.planted_date, p.created_at) AS started_at
            FROM Plants p
            LEFT JOIN GrowthUnitPlants gup ON gup.plant_id = p.plant_id
            WHERE p.plant_id = ?
            LIMIT 1
            """,
            (plant_id,),
        ).fetchone()
        if not plant:
            return 0.0

        unit_id = plant["unit_id"]
        started_at = plant["started_at"]

        sensor_rows = db.execute(
            """
            SELECT sensor_id
            FROM PlantSensors
            WHERE plant_id = ?
            """,
            (plant_id,),
        ).fetchall()
        sensor_ids = [row["sensor_id"] for row in sensor_rows if row["sensor_id"] is not None]

        params: list[Any] = []
        if sensor_ids:
            placeholders = ", ".join("?" for _ in sensor_ids)
            query = f"""
                SELECT sr.reading_data
                FROM SensorReading sr
                WHERE sr.sensor_id IN ({placeholders})
            """
            params.extend(sensor_ids)
        elif unit_id is not None:
            query = """
                SELECT sr.reading_data
                FROM SensorReading sr
                JOIN Sensor s ON s.sensor_id = sr.sensor_id
                WHERE s.unit_id = ?
            """
            params.append(unit_id)
        else:
            return 0.0

        if started_at:
            query += " AND sr.timestamp >= ?"
            params.append(started_at)

        total = 0.0
        count = 0
        for row in db.execute(query, params):
            payload = self._decode_reading_payload(dict(row))
            raw_value = payload.get(metric_key)
            if raw_value is None or isinstance(raw_value, bool):
                continue
            try:
                value = float(raw_value)
            except (TypeError, ValueError):
                continue
            if not math.isfinite(value):
                continue
            total += value
            count += 1

        if count == 0:
            return 0.0
        return total / count

    def get_total_light_hours(self, plant_id: int) -> float:
        try:
            db = self.get_db()
            query = """
                SELECT ds.start_time, ds.end_time
                FROM DeviceSchedules ds
                JOIN GrowthUnits gu ON gu.unit_id = ds.unit_id
                WHERE gu.active_plant_id = ?
                  AND ds.device_type = 'light'
                  AND ds.enabled = 1
                ORDER BY ds.priority DESC, ds.schedule_id DESC
                LIMIT 1
                """
            schedule = db.execute(query, (plant_id,)).fetchone()
            if not schedule:
                return 0.0

            start_time = schedule["start_time"]
            end_time = schedule["end_time"]
            if not start_time or not end_time:
                return 0.0

            def _parse_time(value: str) -> datetime | None:
                for fmt in ("%H:%M", "%H:%M:%S", "%H:%M:%S.%f"):
                    try:
                        return datetime.strptime(value, fmt)
                    except ValueError:
                        continue
                return None

            start_dt = _parse_time(start_time)
            end_dt = _parse_time(end_time)
            if not start_dt or not end_dt:
                raise ValueError("Invalid light schedule time format")

            diff_seconds = (end_dt - start_dt).total_seconds()
            if diff_seconds <= 0:
                diff_seconds += 24 * 3600
            return diff_seconds / 3600
        except sqlite3.Error as exc:
            logging.error("Error calculating total light hours for plant %s: %s", plant_id, exc)
            return 0.0
        except (TypeError, ValueError):
            logging.warning("Invalid light schedule for active plant %s", plant_id)
            return 0.0

    def get_latest_ai_log(self, unit_id: int) -> dict[str, Any] | None:
        """Retrieve the latest AI log entry for a specific growth unit."""
        try:
            db = self.get_db()
            query = """
                SELECT *
                FROM AI_DecisionLogs
                WHERE unit_id = ?
                ORDER BY timestamp DESC
                LIMIT 1
                """
            result = db.execute(query, (unit_id,)).fetchone()
            return dict(result) if result else None
        except sqlite3.Error as exc:
            logging.error("Error retrieving latest AI log for unit %s: %s", unit_id, exc)
            return None

    def get_latest_sensor_reading(self, unit_id: int | None = None) -> dict[str, Any] | None:
        """
        Get the most recent sensor reading across all sensors, optionally filtered by unit.

        Args:
            unit_id: Optional unit ID to filter by.

        Returns:
            Dictionary with sensor reading data or None if no readings exist.
        """
        try:
            db = self.get_db()
            if unit_id is not None:
                query = """
                    SELECT sr.timestamp, sr.reading_data, sr.quality_score
                    FROM SensorReading sr
                    JOIN Sensor s ON sr.sensor_id = s.sensor_id
                    WHERE s.unit_id = ?
                    ORDER BY sr.timestamp DESC
                    LIMIT 1
                """
                params = (unit_id,)
            else:
                query = """
                    SELECT timestamp, reading_data, quality_score
                    FROM SensorReading
                    ORDER BY timestamp DESC
                    LIMIT 1
                """
                params = ()

            result = db.execute(query, params).fetchone()
            if not result:
                return None
            as_dict = dict(result)
            payload = self._decode_reading_payload(as_dict)
            return {
                "timestamp": as_dict.get("timestamp"),
                "quality_score": as_dict.get("quality_score"),
                **payload,
            }
        except sqlite3.Error as exc:
            logging.error("Error getting latest sensor reading: %s", exc)
            return None

    def get_latest_energy_reading(self) -> dict[str, Any] | None:
        """
        Get the most recent energy reading.
        Note: Redirected to unified EnergyReadings table (zigbee source).
        """
        try:
            db = self.get_db()
            query = """
                SELECT timestamp, power_watts
                FROM EnergyReadings
                WHERE source_type = 'zigbee'
                ORDER BY timestamp DESC
                LIMIT 1
            """
            result = db.execute(query).fetchone()
            return dict(result) if result else None
        except sqlite3.Error as exc:
            logging.error("Error getting latest energy reading: %s", exc)
            return None

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
        """
        Insert an energy consumption reading from a Zigbee monitor.
        Note: Redirected to unified EnergyReadings table.
        """
        stamp = timestamp or iso_now()
        try:
            db = self.get_db()

            # Lookup context: unit, plant and current growth stage
            monitor = db.execute(
                """
                SELECT zm.unit_id, p.plant_id, p.current_stage
                FROM ZigBeeEnergyMonitors zm
                LEFT JOIN Plants p ON p.unit_id = zm.unit_id AND p.is_active = 1
                WHERE zm.monitor_id = ?
                """,
                (monitor_id,),
            ).fetchone()

            unit_id = monitor["unit_id"] if monitor else None
            plant_id = monitor["plant_id"] if monitor else None
            growth_stage = monitor["current_stage"] if monitor else None

            cursor = db.execute(
                """
                INSERT INTO EnergyReadings (
                    device_id, unit_id, plant_id, growth_stage, timestamp,
                    voltage, current, power_watts, energy_kwh, frequency,
                    power_factor, temperature, source_type
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    monitor_id,
                    unit_id,
                    plant_id,
                    growth_stage,
                    stamp,
                    voltage,
                    current,
                    power_watts,
                    energy_kwh,
                    frequency,
                    power_factor,
                    temperature,
                    "zigbee",
                ),
            )
            db.commit()
            return cursor.lastrowid
        except sqlite3.Error as exc:
            logging.error(
                "Error inserting energy consumption (monitor_id=%s): %s",
                monitor_id,
                exc,
            )
            return None

    def save_energy_reading(
        self,
        *,
        device_id: int,
        unit_id: int,
        power_watts: float,
        timestamp: str | None = None,
        plant_id: int | None = None,
        growth_stage: str | None = None,
        voltage: float | None = None,
        current: float | None = None,
        energy_kwh: float | None = None,
        power_factor: float | None = None,
        frequency: float | None = None,
        temperature: float | None = None,
        source_type: str = "unknown",
        is_estimated: bool = False,
    ) -> int | None:
        """
        Insert an energy reading into EnergyReadings.

        Args:
            device_id: Device/actuator ID
            unit_id: Growth unit ID
            power_watts: Current power draw (required)
            timestamp: Optional ISO-8601 timestamp (defaults to now)
            plant_id/growth_stage: Optional lifecycle context
            voltage/current/energy_kwh/power_factor/frequency/temperature: Optional metrics
            source_type: Data source (zigbee/gpio/mqtt/wifi/estimated)
            is_estimated: Flag for estimated readings
        """
        stamp = timestamp or iso_now()
        try:
            with self.connection() as db:
                cursor = db.execute(
                    """
                    INSERT INTO EnergyReadings (
                        device_id,
                        plant_id,
                        unit_id,
                        growth_stage,
                        timestamp,
                        voltage,
                        current,
                        power_watts,
                        energy_kwh,
                        power_factor,
                        frequency,
                        temperature,
                        source_type,
                        is_estimated
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        device_id,
                        plant_id,
                        unit_id,
                        growth_stage,
                        stamp,
                        voltage,
                        current,
                        power_watts,
                        energy_kwh,
                        power_factor,
                        frequency,
                        temperature,
                        source_type,
                        1 if is_estimated else 0,
                    ),
                )
                return cursor.lastrowid
        except sqlite3.Error as exc:
            logging.error(
                "Error inserting energy reading (device_id=%s): %s",
                device_id,
                exc,
            )
            return None

    def get_all_harvest_reports(
        self,
        unit_id: int | None = None,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch all harvest summaries with pagination, optionally filtered by unit."""
        try:
            validated_limit, validated_offset = validate_pagination(limit, offset)
            db = self.get_db()
            params: list[Any] = []
            where = ""
            if unit_id is not None:
                where = "WHERE unit_id = ?"
                params.append(unit_id)

            # Add pagination parameters
            params.extend([validated_limit, validated_offset])

            cursor = db.execute(
                f"""
                SELECT *
                FROM PlantHarvestSummary
                {where}
                ORDER BY harvested_date DESC
                LIMIT ? OFFSET ?
                """,
                params,
            )
            reports: list[dict[str, Any]] = []
            json_fields = {
                "energy_by_stage",
                "cost_by_stage",
                "device_usage",
                "health_incidents",
                "light_hours_by_stage",
            }
            for row in cursor.fetchall():
                as_dict = dict(row)
                for field in json_fields:
                    raw_val = as_dict.get(field)
                    if raw_val:
                        try:
                            as_dict[field] = json.loads(raw_val)
                        except (TypeError, ValueError):
                            as_dict[field] = None
                reports.append(as_dict)
            return reports
        except sqlite3.Error as exc:
            logging.error("Error fetching harvest reports: %s", exc)
            return []

    def fetch_sensor_history(
        self,
        start_dt: datetime,
        end_dt: datetime,
        unit_id: int | None = None,
        sensor_id: int | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        Fetch sensor readings between start and end datetime, optionally filtered.

        Args:
            start_dt: Start datetime for the range
            end_dt: End datetime for the range
            unit_id: Optional unit filter (via Sensor table)
            sensor_id: Optional sensor filter
            limit: Optional row cap
        Returns:
            List of sensor readings ordered by timestamp
        """
        try:
            db = self.get_db()
            params: list[Any] = [
                self._timestamp_query_param(start_dt),
                self._timestamp_query_param(end_dt),
            ]
            filters: list[str] = ["sr.timestamp BETWEEN ? AND ?"]

            if sensor_id is not None:
                filters.append("sr.sensor_id = ?")
                params.append(sensor_id)
            if unit_id is not None:
                filters.append("sr.sensor_id IN (SELECT sensor_id FROM Sensor WHERE unit_id = ?)")
                params.append(unit_id)

            limit_clause = ""
            if limit is not None:
                limit_clause = " LIMIT ?"
                params.append(limit)

            where_clause = " AND ".join(filters)
            query = f"""
                SELECT sr.sensor_id,
                       sr.timestamp,
                       sr.reading_data,
                       sr.quality_score,
                       s.unit_id AS sensor_unit_id,
                       s.name AS sensor_name
                FROM SensorReading sr
                LEFT JOIN Sensor s ON sr.sensor_id = s.sensor_id
                WHERE {where_clause}
                ORDER BY sr.timestamp ASC{limit_clause}
            """
            cursor = db.execute(query, params)
            rows: list[dict[str, Any]] = []
            for row in cursor.fetchall():
                as_dict = dict(row)
                payload = self._decode_reading_payload(as_dict)
                rows.append(
                    {
                        "timestamp": as_dict.get("timestamp"),
                        "sensor_id": as_dict.get("sensor_id"),
                        "unit_id": as_dict.get("sensor_unit_id"),
                        "sensor_name": as_dict.get("sensor_name"),
                        "quality_score": as_dict.get("quality_score"),
                        **payload,
                    }
                )
            return rows
        except sqlite3.Error as exc:
            logging.error("Error fetching sensor history: %s", exc)
            return []

    def get_plant_info(self, plant_id: int) -> dict[str, object] | None:
        """Get plant information by plant ID."""
        try:
            db = self.get_db()
            query = """
                SELECT
                    p.plant_id,
                    p.name,
                    p.plant_type,
                    p.current_stage,
                    p.days_in_stage,
                    p.moisture_level,
                    p.planted_date,
                    p.created_at,
                    p.last_updated,
                    gup.unit_id
                FROM Plants p
                LEFT JOIN GrowthUnitPlants gup ON p.plant_id = gup.plant_id
                WHERE p.plant_id = ?
            """
            result = db.execute(query, (plant_id,)).fetchone()
            return dict(result) if result else None
        except sqlite3.Error as exc:
            logging.error("Error retrieving plant info for plant %s: %s", plant_id, exc)
            return None

    def save_harvest_summary(self, plant_id: int, summary: dict[str, object]) -> int:
        """
        Save a comprehensive harvest summary report to the database.

        Args:
            plant_id: ID of the harvested plant
            summary: Complete harvest report dictionary with all metrics

        Returns:
            harvest_id: ID of the newly created harvest record
        """
        import json

        try:
            lifecycle = summary.get("lifecycle", {})
            stages = lifecycle.get("stages", {})
            energy = summary.get("energy_consumption", {})
            efficiency = summary.get("efficiency_metrics", {})
            env_conditions = summary.get("environmental_conditions", {})

            # Ensure we have required dates
            planted_date = lifecycle.get("planted_date") or iso_now()
            harvested_date = lifecycle.get("harvested_date") or iso_now()
            total_days = lifecycle.get("total_days", 0)

            with self.connection() as db:
                cursor = db.execute(
                    """
                    INSERT INTO PlantHarvestSummary (
                        plant_id,
                        unit_id,
                        planted_date,
                        harvested_date,
                        total_days,
                        seedling_days,
                        vegetative_days,
                        flowering_days,
                        total_energy_kwh,
                        energy_by_stage,
                        total_cost,
                        cost_by_stage,
                        device_usage,
                        health_incidents,
                        avg_temperature,
                        avg_humidity,
                        avg_co2,
                        harvest_weight_grams,
                        quality_rating,
                        notes,
                        grams_per_kwh,
                        cost_per_gram
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        plant_id,
                        summary.get("unit_id"),
                        planted_date,
                        harvested_date,
                        total_days,
                        stages.get("seedling", {}).get("days", 0),
                        stages.get("vegetative", {}).get("days", 0),
                        stages.get("flowering", {}).get("days", 0),
                        energy.get("total_kwh", 0.0),
                        json.dumps(energy.get("by_stage", {})),
                        energy.get("total_cost", 0.0),
                        json.dumps(energy.get("cost_by_stage", {})),
                        json.dumps(summary.get("device_usage", {})),
                        json.dumps(summary.get("health_incidents", {})),
                        env_conditions.get("temperature", {}).get("avg"),
                        env_conditions.get("humidity", {}).get("avg"),
                        env_conditions.get("co2", {}).get("avg"),
                        summary.get("yield", {}).get("weight_grams"),
                        summary.get("yield", {}).get("quality_rating"),
                        summary.get("yield", {}).get("notes", ""),
                        efficiency.get("grams_per_kwh", 0.0),
                        efficiency.get("cost_per_gram", 0.0),
                    ),
                )
                harvest_id = cursor.lastrowid
                logging.info(f"Saved harvest summary for plant {plant_id}, harvest_id={harvest_id}")
                return harvest_id

        except sqlite3.Error as exc:
            logging.error(f"Error saving harvest summary for plant {plant_id}: {exc}")
            raise

    # --- Growth Cycle Comparison Methods --------------------------------------
    def compare_growth_cycles(
        self,
        unit_id: int,
        limit: int = 10,
    ) -> dict[str, Any]:
        """
        Compare multiple growth cycles (harvests) for a unit.

        Provides side-by-side comparison of:
        - Yield (weight, quality)
        - Duration
        - Energy consumption
        - Environmental conditions
        - Efficiency metrics

        Args:
            unit_id: Growth unit ID
            limit: Number of harvests to compare

        Returns:
            Comparison data with statistics
        """
        try:
            db = self.get_db()

            # Get harvests for this unit
            cursor = db.execute(
                """
                SELECT
                    harvest_id, plant_id, plant_name, plant_type,
                    planted_date, harvested_date, total_days,
                    total_energy_kwh, energy_cost,
                    avg_temperature, avg_humidity,
                    yield_weight_grams, quality_rating,
                    grams_per_kwh, cost_per_gram
                FROM HarvestReport
                WHERE unit_id = ?
                ORDER BY harvested_date DESC
                LIMIT ?
                """,
                (unit_id, limit),
            )
            rows = cursor.fetchall()

            if not rows:
                return {
                    "unit_id": unit_id,
                    "harvest_count": 0,
                    "harvests": [],
                    "statistics": {},
                    "best_performers": {},
                }

            harvests = [dict(row) for row in rows]

            # Calculate statistics
            yields = [h["yield_weight_grams"] or 0 for h in harvests if h.get("yield_weight_grams")]
            durations = [h["total_days"] or 0 for h in harvests if h.get("total_days")]
            energies = [h["total_energy_kwh"] or 0 for h in harvests if h.get("total_energy_kwh")]
            efficiencies = [h["grams_per_kwh"] or 0 for h in harvests if h.get("grams_per_kwh")]
            qualities = [h["quality_rating"] or 0 for h in harvests if h.get("quality_rating")]

            def calc_stats(values: list) -> dict:
                if not values:
                    return {"min": None, "max": None, "avg": None, "count": 0}
                return {
                    "min": min(values),
                    "max": max(values),
                    "avg": round(sum(values) / len(values), 2),
                    "count": len(values),
                }

            statistics = {
                "yield_grams": calc_stats(yields),
                "duration_days": calc_stats(durations),
                "energy_kwh": calc_stats(energies),
                "efficiency_grams_per_kwh": calc_stats(efficiencies),
                "quality_rating": calc_stats(qualities),
            }

            # Find best performers
            best_performers = {}
            if yields:
                best_yield_idx = yields.index(max(yields))
                best_performers["highest_yield"] = {
                    "harvest_id": harvests[best_yield_idx]["harvest_id"],
                    "plant_name": harvests[best_yield_idx]["plant_name"],
                    "value": max(yields),
                }
            if efficiencies:
                best_eff_idx = efficiencies.index(max(efficiencies))
                best_performers["most_efficient"] = {
                    "harvest_id": harvests[best_eff_idx]["harvest_id"],
                    "plant_name": harvests[best_eff_idx]["plant_name"],
                    "value": max(efficiencies),
                }
            if qualities:
                best_qual_idx = qualities.index(max(qualities))
                best_performers["highest_quality"] = {
                    "harvest_id": harvests[best_qual_idx]["harvest_id"],
                    "plant_name": harvests[best_qual_idx]["plant_name"],
                    "value": max(qualities),
                }

            return {
                "unit_id": unit_id,
                "harvest_count": len(harvests),
                "harvests": harvests,
                "statistics": statistics,
                "best_performers": best_performers,
            }

        except sqlite3.Error as exc:
            logging.error(f"Error comparing growth cycles for unit {unit_id}: {exc}")
            return {"error": str(exc)}

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
        try:
            db = self.get_db()

            if not harvest_ids:
                return {"error": "No harvest IDs provided"}

            placeholders = ",".join(["?"] * len(harvest_ids))
            cursor = db.execute(
                f"""
                SELECT
                    harvest_id, plant_name, plant_type,
                    planted_date, harvested_date, total_days,
                    avg_temperature, avg_humidity, avg_co2,
                    total_energy_kwh, yield_weight_grams, quality_rating
                FROM HarvestReport
                WHERE harvest_id IN ({placeholders})
                ORDER BY harvested_date DESC
                """,
                tuple(harvest_ids),
            )
            rows = cursor.fetchall()

            comparisons = []
            for row in rows:
                comparisons.append(dict(row))

            return {
                "harvest_count": len(comparisons),
                "comparisons": comparisons,
            }

        except sqlite3.Error as exc:
            logging.error(f"Error getting environmental comparison: {exc}")
            return {"error": str(exc)}

    def get_plant_type_performance(
        self,
        plant_type: str,
        limit: int = 20,
    ) -> dict[str, Any]:
        """
        Get performance statistics for a specific plant type across all units.

        Useful for understanding how a plant type performs in your environment.

        Args:
            plant_type: Plant type/species to analyze
            limit: Max records to analyze

        Returns:
            Performance statistics for the plant type
        """
        try:
            db = self.get_db()

            cursor = db.execute(
                """
                SELECT
                    harvest_id, unit_id, plant_name,
                    planted_date, harvested_date, total_days,
                    avg_temperature, avg_humidity,
                    total_energy_kwh, yield_weight_grams, quality_rating,
                    grams_per_kwh, cost_per_gram
                FROM HarvestReport
                WHERE plant_type = ?
                ORDER BY harvested_date DESC
                LIMIT ?
                """,
                (plant_type, limit),
            )
            rows = cursor.fetchall()

            if not rows:
                return {
                    "plant_type": plant_type,
                    "harvest_count": 0,
                    "statistics": {},
                }

            harvests = [dict(row) for row in rows]

            # Calculate comprehensive statistics
            yields = [h["yield_weight_grams"] for h in harvests if h.get("yield_weight_grams")]
            durations = [h["total_days"] for h in harvests if h.get("total_days")]
            temps = [h["avg_temperature"] for h in harvests if h.get("avg_temperature")]
            humidities = [h["avg_humidity"] for h in harvests if h.get("avg_humidity")]
            efficiencies = [h["grams_per_kwh"] for h in harvests if h.get("grams_per_kwh")]

            def calc_stats(values):
                if not values:
                    return None
                return {
                    "min": round(min(values), 2),
                    "max": round(max(values), 2),
                    "avg": round(sum(values) / len(values), 2),
                }

            # Find optimal conditions from best harvests
            best_harvests = sorted(harvests, key=lambda x: x.get("yield_weight_grams") or 0, reverse=True)[:3]
            optimal_conditions = None
            if best_harvests:
                best_temps = [h["avg_temperature"] for h in best_harvests if h.get("avg_temperature")]
                best_hums = [h["avg_humidity"] for h in best_harvests if h.get("avg_humidity")]
                optimal_conditions = {
                    "avg_temperature": round(sum(best_temps) / len(best_temps), 1) if best_temps else None,
                    "avg_humidity": round(sum(best_hums) / len(best_hums), 1) if best_hums else None,
                    "based_on": len(best_harvests),
                }

            return {
                "plant_type": plant_type,
                "harvest_count": len(harvests),
                "units_used": len(set(h["unit_id"] for h in harvests)),
                "statistics": {
                    "yield_grams": calc_stats(yields),
                    "duration_days": calc_stats(durations),
                    "temperature": calc_stats(temps),
                    "humidity": calc_stats(humidities),
                    "efficiency_grams_per_kwh": calc_stats(efficiencies),
                },
                "optimal_conditions": optimal_conditions,
                "harvests": harvests,
            }

        except sqlite3.Error as exc:
            logging.error(f"Error getting plant type performance for {plant_type}: {exc}")
            return {"error": str(exc)}

    def get_plant_energy_summary(self, plant_id: int) -> dict[str, Any]:
        """Get comprehensive energy summary for a plant.

        Returns dict with total_kwh, total_cost, avg_daily_power_watts,
        by_stage, cost_by_stage, and by_device.
        """
        empty = {
            "total_kwh": 0.0,
            "total_cost": 0.0,
            "avg_daily_power_watts": 0.0,
            "by_stage": {},
            "cost_by_stage": {},
            "by_device": {},
        }
        try:
            db = self.get_db()

            # Total energy for this plant
            result = db.execute(
                """
                SELECT
                    SUM(er.energy_kwh)  AS total_kwh,
                    AVG(er.power_watts) AS avg_power
                FROM EnergyReadings er
                JOIN Plants p ON p.unit_id = er.unit_id
                WHERE p.plant_id = ?
                """,
                (plant_id,),
            ).fetchone()

            total_kwh = (result["total_kwh"] or 0.0) if result else 0.0
            avg_power = (result["avg_power"] or 0.0) if result else 0.0

            # Energy breakdown by growth stage
            by_stage_rows = db.execute(
                """
                SELECT
                    er.growth_stage  AS growth_stage,
                    SUM(er.energy_kwh) AS stage_kwh,
                    AVG(er.power_watts) AS stage_power
                FROM EnergyReadings er
                JOIN Plants p ON p.unit_id = er.unit_id
                WHERE p.plant_id = ?
                GROUP BY er.growth_stage
                """,
                (plant_id,),
            ).fetchall()

            by_stage = {row["growth_stage"]: row["stage_kwh"] for row in by_stage_rows if row["growth_stage"]}

            cost_per_kwh = 0.20
            total_cost = total_kwh * cost_per_kwh
            cost_by_stage = {stage: kwh * cost_per_kwh for stage, kwh in by_stage.items()}

            return {
                "total_kwh": round(total_kwh, 2),
                "total_cost": round(total_cost, 2),
                "avg_daily_power_watts": round(avg_power, 2),
                "by_stage": by_stage,
                "cost_by_stage": cost_by_stage,
                "by_device": {},
            }
        except sqlite3.Error as exc:
            logging.error("Error getting plant energy summary for %s: %s", plant_id, exc)
            return empty

    # Placeholder for static analysers
    def get_db(self):  # pragma: no cover
        raise NotImplementedError
