from __future__ import annotations

import json
import logging
import sqlite3
from typing import Any, Dict, List, Optional

from infrastructure.database.pagination import validate_pagination


class DeviceOperations:
    """Sensor and actuator related helpers shared across database handlers."""

    # --- Actuators (New Schema) -----------------------------------------------
    def insert_actuator(
        self,
        *,
        unit_id: int,
        name: str,
        actuator_type: str,
        protocol: str,
        model: str = "Generic",
        config_data: Optional[Dict[str, Any]] = None,
    ) -> Optional[int]:
        """Insert actuator with new schema."""
        try:
            db = self.get_db()
            
            # Insert into Actuator table
            cursor = db.execute(
                """
                INSERT INTO Actuator (
                    unit_id,
                    name,
                    actuator_type,
                    protocol,
                    model
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    unit_id,
                    name,
                    actuator_type,
                    protocol,
                    model,
                ),
            )
            actuator_id = cursor.lastrowid
            
            # Insert config if present
            if config_data:
                db.execute(
                    """
                    INSERT INTO ActuatorConfig (actuator_id, config_data)
                    VALUES (?, ?)
                    """,
                    (actuator_id, json.dumps(config_data)),
                )
            
            db.commit()
            logging.info("✅ Actuator '%s' inserted successfully.", name)
            return actuator_id
        except sqlite3.Error as exc:
            logging.error("Error inserting actuator: %s", exc)
            return None

    def remove_actuator(self, actuator_id: int) -> None:
        try:
            db = self.get_db()
            db.execute("DELETE FROM Actuator WHERE actuator_id = ?", (actuator_id,))
            db.commit()
        except sqlite3.Error as exc:
            logging.error("Error removing actuator: %s", exc)

    def get_actuator_configs(
        self,
        unit_id: Optional[int] = None,
        *,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Get actuator configs with new schema and pagination."""
        try:
            # Validate pagination parameters
            validated_limit, validated_offset = validate_pagination(limit, offset)

            db = self.get_db()
            query = """
                SELECT
                    a.actuator_id,
                    a.unit_id,
                    a.name,
                    a.actuator_type,
                    a.protocol,
                    a.model,
                    a.ieee_address,
                    a.is_active,
                    a.created_at,
                    a.updated_at,
                    ac.config_data
                FROM Actuator a
                LEFT JOIN ActuatorConfig ac ON a.actuator_id = ac.actuator_id
            """
            if unit_id is not None:
                query += " WHERE a.unit_id = ?"
                query += f" ORDER BY a.actuator_id ASC LIMIT ? OFFSET ?"
                cursor = db.execute(query, (unit_id, validated_limit, validated_offset))
            else:
                query += " ORDER BY a.actuator_id ASC LIMIT ? OFFSET ?"
                cursor = db.execute(query, (validated_limit, validated_offset))
            rows = cursor.fetchall()
            
            results = []
            for row in rows:
                config_data = json.loads(row["config_data"]) if row["config_data"] else {}

                actuator = {
                    "actuator_id": row["actuator_id"],
                    "unit_id": row["unit_id"],
                    "name": row["name"],
                    "actuator_type": row["actuator_type"],
                    "protocol": row["protocol"],
                    "model": row["model"],
                    "ieee_address": row["ieee_address"],
                    "is_active": row["is_active"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                    "config": config_data,
                }
                results.append(actuator)
            
            return results
        except sqlite3.Error as exc:
            logging.error("Error getting actuator configs: %s", exc)
            return []

    def get_actuator_config_by_id(self, actuator_id: int) -> Optional[Dict[str, Any]]:
        """Get actuator config by actuator_id with new schema."""
        try:
            db = self.get_db()
            cursor = db.execute(
                """
                SELECT 
                    a.actuator_id,
                    a.unit_id,
                    a.name,
                    a.actuator_type,
                    a.protocol,
                    a.model,
                    a.ieee_address,
                    a.is_active,
                    a.created_at,
                    a.updated_at,
                    ac.config_data
                FROM Actuator a
                LEFT JOIN ActuatorConfig ac ON a.actuator_id = ac.actuator_id
                WHERE a.actuator_id = ?
                """,
                (actuator_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None

            config_data = json.loads(row["config_data"]) if row["config_data"] else {}
            return {
                "actuator_id": row["actuator_id"],
                "unit_id": row["unit_id"],
                "name": row["name"],
                "actuator_type": row["actuator_type"],
                "protocol": row["protocol"],
                "model": row["model"],
                "ieee_address": row["ieee_address"],
                "is_active": row["is_active"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "config": config_data,
            }
        except sqlite3.Error as exc:
            logging.error("Error getting actuator config by ID: %s", exc)
            return None

    def get_all_actuators(
        self,
        *,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Get all actuators with pagination."""
        # Validate pagination parameters
        validated_limit, validated_offset = validate_pagination(limit, offset)

        db = self.get_db()
        cursor = db.execute(
            "SELECT * FROM Actuator ORDER BY actuator_id ASC LIMIT ? OFFSET ?",
            (validated_limit, validated_offset)
        )
        return [dict(row) for row in cursor.fetchall()]

    def update_actuator_config(
        self,
        actuator_id: int,
        config_data: Dict[str, Any],
    ) -> bool:
        """
        Update actuator config_data (upsert pattern).

        Args:
            actuator_id: The actuator ID
            config_data: New config data to store

        Returns:
            True if successful
        """
        try:
            db = self.get_db()
            config_json = json.dumps(config_data)

            # Use INSERT OR REPLACE for upsert behavior
            db.execute(
                """
                INSERT INTO ActuatorConfig (actuator_id, config_data)
                VALUES (?, ?)
                ON CONFLICT(actuator_id) DO UPDATE SET
                    config_data = excluded.config_data
                """,
                (actuator_id, config_json),
            )
            db.commit()
            logging.info("Updated config for actuator %s", actuator_id)
            return True
        except sqlite3.Error as exc:
            logging.error("Error updating actuator config: %s", exc)
            return False

    def check_actuator_triggered(self, unit_id: int, actuator_name: str) -> bool:
        db = self.get_db()
        query = """
            SELECT timestamp
            FROM ActuatorHistory
            WHERE unit_id = ?
              AND actuator_id = (
                  SELECT actuator_id FROM Actuator WHERE actuator_type = ?
              )
              AND action = 'ON'
            ORDER BY timestamp DESC
            LIMIT 1
        """
        last_activation = db.execute(query, (unit_id, actuator_name)).fetchone()

        if last_activation:
            from datetime import datetime, timedelta

            last_time = datetime.strptime(last_activation["timestamp"], "%Y-%m-%d %H:%M:%S")
            return (datetime.now() - last_time) < timedelta(hours=1)
        return False

    # --- Sensors (New Schema) -------------------------------------------------
    def insert_sensor(
        self,
        unit_id: int,
        name: str,
        sensor_type: str,
        protocol: str,
        model: str,
        config_data: Optional[Dict[str, Any]] = None,
    ) -> Optional[int]:
        """Insert sensor with new schema."""
        try:
            db = self.get_db()
            cursor = db.execute(
                """
                INSERT INTO Sensor (unit_id, name, sensor_type, protocol, model)
                VALUES (?, ?, ?, ?, ?)
                """,
                (unit_id, name, sensor_type, protocol, model),
            )
            sensor_id = cursor.lastrowid
            
            # Insert config
            if config_data:
                db.execute(
                    """
                    INSERT INTO SensorConfig (sensor_id, config_data)
                    VALUES (?, ?)
                    """,
                    (sensor_id, json.dumps(config_data)),
                )
            
            db.commit()
            logging.info("✅ Sensor '%s' inserted successfully.", name)
            return sensor_id
        except sqlite3.Error as exc:
            logging.error("Error inserting sensor '%s': %s", name, exc)
            return None

    def update_sensor_config(
        self,
        sensor_id: int,
        config_data: Dict[str, Any],
    ) -> bool:
        """
        Update sensor config_data (upsert pattern).

        Args:
            sensor_id: The sensor ID
            config_data: New config data to store

        Returns:
            True if successful
        """
        try:
            db = self.get_db()
            config_json = json.dumps(config_data)

            cursor = db.execute(
                """
                UPDATE SensorConfig
                SET config_data = ?
                WHERE sensor_id = ?
                """,
                (config_json, sensor_id),
            )

            if cursor.rowcount == 0:
                db.execute(
                    """
                    INSERT INTO SensorConfig (sensor_id, config_data)
                    VALUES (?, ?)
                    """,
                    (sensor_id, config_json),
                )

            db.commit()
            logging.info("Updated config for sensor %s", sensor_id)
            return True
        except sqlite3.Error as exc:
            logging.error("Error updating sensor config: %s", exc)
            return False

    def update_sensor_fields(
        self,
        sensor_id: int,
        *,
        name: Optional[str] = None,
        sensor_type: Optional[str] = None,
        protocol: Optional[str] = None,
        model: Optional[str] = None,
    ) -> bool:
        """Update base sensor fields (name/type/protocol/model)."""
        try:
            updates: Dict[str, Any] = {}
            if name is not None:
                updates["name"] = name
            if sensor_type is not None:
                updates["sensor_type"] = sensor_type
            if protocol is not None:
                updates["protocol"] = protocol
            if model is not None:
                updates["model"] = model

            if not updates:
                return True

            fields = ", ".join([f"{key} = ?" for key in updates.keys()])
            values = list(updates.values()) + [sensor_id]

            db = self.get_db()
            db.execute(
                f"UPDATE Sensor SET {fields} WHERE sensor_id = ?",
                values,
            )
            db.commit()
            logging.info("Updated sensor %s fields: %s", sensor_id, list(updates.keys()))
            return True
        except sqlite3.Error as exc:
            logging.error("Error updating sensor fields: %s", exc)
            return False

    def remove_sensor(self, sensor_id: int) -> None:
        try:
            db = self.get_db()
            db.execute("DELETE FROM Sensor WHERE sensor_id = ?", (sensor_id,))
            db.commit()
        except sqlite3.Error as exc:
            logging.error("Error removing sensor: %s", exc)

    def get_sensor_configs(
        self,
        unit_id: Optional[int] = None,
        *,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Get sensor configs with new schema and pagination."""
        try:
            # Validate pagination parameters
            validated_limit, validated_offset = validate_pagination(limit, offset)

            db = self.get_db()
            query = """
                SELECT
                    s.sensor_id,
                    s.unit_id,
                    s.name,
                    s.sensor_type,
                    s.protocol,
                    s.model,
                    s.is_active,
                    s.created_at,
                    s.updated_at,
                    sc.config_data
                FROM Sensor s
                LEFT JOIN SensorConfig sc ON s.sensor_id = sc.sensor_id
            """

            if unit_id is not None:
                query += " WHERE s.unit_id = ?"
                query += " ORDER BY s.sensor_id ASC LIMIT ? OFFSET ?"
                cursor = db.execute(query, (unit_id, validated_limit, validated_offset))
            else:
                query += " ORDER BY s.sensor_id ASC LIMIT ? OFFSET ?"
                cursor = db.execute(query, (validated_limit, validated_offset))

            rows = cursor.fetchall()
            configs: List[Dict[str, Any]] = []
            for row in rows:
                config = {
                    "sensor_id": row["sensor_id"],
                    "unit_id": row["unit_id"],
                    "name": row["name"],
                    "sensor_type": row["sensor_type"],
                    "protocol": row["protocol"],
                    "model": row["model"],
                    "is_active": row["is_active"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                }
                # Parse JSON config
                if row["config_data"]:
                    try:
                        config["config"] = json.loads(row["config_data"])
                    except json.JSONDecodeError:
                        config["config"] = {}
                else:
                    config["config"] = {}
                configs.append(config)
            return configs
        except sqlite3.Error as exc:
            logging.error("Error getting sensor configs: %s", exc)
            return []

    def get_all_sensors(
        self,
        *,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Get all sensors with pagination."""
        # Validate pagination parameters
        validated_limit, validated_offset = validate_pagination(limit, offset)

        db = self.get_db()
        cursor = db.execute(
            "SELECT * FROM Sensor ORDER BY sensor_id ASC LIMIT ? OFFSET ?",
            (validated_limit, validated_offset)
        )
        return [dict(row) for row in cursor.fetchall()]

    def get_sensors_by_model(self, sensor_model: str) -> List[Any]:
        try:
            db = self.get_db()
            return db.execute("SELECT * FROM Sensor WHERE model = ?", (sensor_model,)).fetchall()
        except sqlite3.Error as exc:
            logging.error("Error retrieving sensors by model: %s", exc)
            return []

    def get_sensor_by_id(self, sensor_id: int):
        try:
            db = self.get_db()
            cursor = db.execute("SELECT * FROM Sensor WHERE sensor_id = ?", (sensor_id,))
            return cursor.fetchone()
        except sqlite3.Error as exc:
            logging.error("Error getting sensor by ID: %s", exc)
            return None

    def get_sensor_config_by_id(self, sensor_id: int) -> Optional[Dict[str, Any]]:
        """Get sensor config by sensor_id with new schema."""
        try:
            db = self.get_db()
            cursor = db.execute(
                """
                SELECT 
                    s.sensor_id,
                    s.unit_id,
                    s.name,
                    s.sensor_type,
                    s.protocol,
                    s.model,
                    s.is_active,
                    s.created_at,
                    s.updated_at,
                    sc.config_data
                FROM Sensor s
                LEFT JOIN SensorConfig sc ON s.sensor_id = sc.sensor_id
                WHERE s.sensor_id = ?
                """,
                (sensor_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None

            config_data = json.loads(row["config_data"]) if row["config_data"] else {}
            return {
                "sensor_id": row["sensor_id"],
                "unit_id": row["unit_id"],
                "name": row["name"],
                "sensor_type": row["sensor_type"],
                "protocol": row["protocol"],
                "model": row["model"],
                "is_active": row["is_active"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "config": config_data,
            }
        except sqlite3.Error as exc:
            logging.error("Error getting sensor config by ID: %s", exc)
            return None

    # --- Actuator State History ----------------------------------------------
    def save_actuator_state(
        self,
        actuator_id: int,
        state: str,
        value: Optional[float] = None,
        timestamp: Optional[str] = None,
    ) -> Optional[int]:
        """Persist actuator state change (on/off/partial) to ActuatorStateHistory."""
        try:
            db = self.get_db()
            if timestamp:
                cursor = db.execute(
                    """
                    INSERT INTO ActuatorStateHistory (actuator_id, state, value, timestamp)
                    VALUES (?, ?, ?, ?)
                    """,
                    (actuator_id, state, value, timestamp),
                )
            else:
                cursor = db.execute(
                    """
                    INSERT INTO ActuatorStateHistory (actuator_id, state, value)
                    VALUES (?, ?, ?)
                    """,
                    (actuator_id, state, value),
                )
            db.commit()
            return cursor.lastrowid
        except sqlite3.Error as exc:
            logging.error("Error saving actuator state: %s", exc)
            return None

    def get_actuator_state_history(
        self,
        actuator_id: int,
        limit: int = 100,
        since: Optional[str] = None,
        until: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch recent state history for an actuator."""
        try:
            db = self.get_db()
            query = (
                "SELECT state_id, actuator_id, state, value, timestamp "
                "FROM ActuatorStateHistory WHERE actuator_id = ?"
            )
            params: List[Any] = [actuator_id]
            if since:
                query += " AND timestamp >= ?"
                params.append(since)
            if until:
                query += " AND timestamp <= ?"
                params.append(until)
            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)
            cur = db.execute(query, tuple(params))
            rows = [dict(row) for row in cur.fetchall()]
            return rows
        except sqlite3.Error as exc:
            logging.error("Error fetching actuator state history: %s", exc)
            return []

    def get_unit_actuator_state_history(
        self,
        unit_id: int,
        limit: int = 100,
        since: Optional[str] = None,
        until: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch recent state history for all actuators in a unit (joins Actuator)."""
        try:
            db = self.get_db()
            query = (
                "SELECT h.state_id, h.actuator_id, a.name, a.unit_id, h.state, h.value, h.timestamp "
                "FROM ActuatorStateHistory h JOIN Actuator a ON a.actuator_id = h.actuator_id "
                "WHERE a.unit_id = ?"
            )
            params: List[Any] = [unit_id]
            if since:
                query += " AND h.timestamp >= ?"
                params.append(since)
            if until:
                query += " AND h.timestamp <= ?"
                params.append(until)
            query += " ORDER BY h.timestamp DESC LIMIT ?"
            params.append(limit)
            cur = db.execute(query, tuple(params))
            return [dict(row) for row in cur.fetchall()]
        except sqlite3.Error as exc:
            logging.error("Error fetching unit actuator state history: %s", exc)
            return []

    def get_recent_actuator_state(
        self,
        limit: int = 100,
        unit_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch last N actuator state changes across system (optional unit filter)."""
        try:
            db = self.get_db()
            base = (
                "SELECT h.state_id, h.actuator_id, a.name, a.unit_id, h.state, h.value, h.timestamp "
                "FROM ActuatorStateHistory h JOIN Actuator a ON a.actuator_id = h.actuator_id"
            )
            params: List[Any] = []
            if unit_id is not None:
                base += " WHERE a.unit_id = ?"
                params.append(unit_id)
            base += " ORDER BY h.timestamp DESC LIMIT ?"
            params.append(limit)
            cur = db.execute(base, tuple(params))
            return [dict(row) for row in cur.fetchall()]
        except sqlite3.Error as exc:
            logging.error("Error fetching recent actuator states: %s", exc)
            return []

    # --- Prune Actuator State History ----------------------------------------
    def prune_actuator_state_history(self, days: int) -> int:
        """Delete state history rows older than N days. Returns rows deleted."""
        try:
            db = self.get_db()
            cur = db.execute(
                "DELETE FROM ActuatorStateHistory WHERE timestamp < datetime('now', ?)",
                (f'-{int(days)} days',),
            )
            db.commit()
            return cur.rowcount or 0
        except sqlite3.Error as exc:
            logging.error("Error pruning actuator state history: %s", exc)
            return 0

    # --- Prune Sensor Readings ------------------------------------------------
    def prune_sensor_readings(self, days: int) -> int:
        """Delete sensor reading rows older than N days. Returns rows deleted."""
        try:
            db = self.get_db()
            cur = db.execute(
                "DELETE FROM SensorReading WHERE timestamp < datetime('now', ?)",
                (f'-{int(days)} days',),
            )
            db.commit()
            return cur.rowcount or 0
        except sqlite3.Error as exc:
            logging.error("Error pruning sensor readings: %s", exc)
            return 0

    # --- Connectivity History -------------------------------------------------
    def save_connectivity_event(
        self,
        connection_type: str,
        status: str,
        *,
        endpoint: Optional[str] = None,
        port: Optional[int] = None,
        unit_id: Optional[int] = None,
        device_id: Optional[str] = None,
        details: Optional[str] = None,
        timestamp: Optional[str] = None,
    ) -> Optional[int]:
        """Persist connectivity event in history table."""
        try:
            db = self.get_db()
            if timestamp:
                cur = db.execute(
                    """
                    INSERT INTO DeviceConnectivityHistory
                    (connection_type, status, endpoint, port, unit_id, device_id, details, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        connection_type,
                        status,
                        endpoint,
                        port,
                        unit_id,
                        device_id,
                        details,
                        timestamp,
                    ),
                )
            else:
                cur = db.execute(
                    """
                    INSERT INTO DeviceConnectivityHistory
                    (connection_type, status, endpoint, port, unit_id, device_id, details)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        connection_type,
                        status,
                        endpoint,
                        port,
                        unit_id,
                        device_id,
                        details,
                    ),
                )
            db.commit()
            return cur.lastrowid
        except sqlite3.Error as exc:
            logging.error("Error saving connectivity event: %s", exc)
            return None

    def get_connectivity_history(
        self,
        *,
        connection_type: Optional[str] = None,
        limit: int = 100,
        since: Optional[str] = None,
        until: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch connectivity history across types (optionally filtered)."""
        try:
            db = self.get_db()
            query = (
                "SELECT event_id, connection_type, status, endpoint, port, unit_id, device_id, details, timestamp "
                "FROM DeviceConnectivityHistory"
            )
            params: List[Any] = []
            first_clause = True
            if connection_type:
                query += " WHERE connection_type = ?"
                params.append(connection_type)
                first_clause = False
            if since:
                query += " AND timestamp >= ?" if not first_clause else " WHERE timestamp >= ?"
                params.append(since)
                first_clause = False
            if until:
                query += " AND timestamp <= ?" if not first_clause else " WHERE timestamp <= ?"
                params.append(until)
            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)
            cur = db.execute(query, tuple(params))
            return [dict(row) for row in cur.fetchall()]
        except sqlite3.Error as exc:
            logging.error("Error fetching connectivity history: %s", exc)
            return []

    # --- Sensor Calibration ---------------------------------------------------
    def save_calibration(
        self,
        sensor_id: int,
        measured_value: float,
        reference_value: float,
        calibration_type: str = "linear",
    ) -> Optional[int]:
        """Save calibration point."""
        try:
            db = self.get_db()
            cursor = db.execute(
                """
                INSERT INTO SensorCalibration 
                (sensor_id, calibration_type, measured_value, reference_value)
                VALUES (?, ?, ?, ?)
                """,
                (sensor_id, calibration_type, measured_value, reference_value),
            )
            db.commit()
            logging.info("✅ Calibration point saved for sensor %d", sensor_id)
            return cursor.lastrowid
        except sqlite3.Error as exc:
            logging.error("Error saving calibration: %s", exc)
            return None

    def get_calibrations(self, sensor_id: int) -> List[Dict[str, Any]]:
        """Get all calibration points for a sensor."""
        try:
            db = self.get_db()
            cursor = db.execute(
                """
                SELECT calibration_id, calibration_type, measured_value, 
                       reference_value, created_at
                FROM SensorCalibration
                WHERE sensor_id = ?
                ORDER BY created_at
                """,
                (sensor_id,),
            )
            return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error as exc:
            logging.error("Error getting calibrations: %s", exc)
            return []

    # --- Sensor Health ---------------------------------------------------------
    def save_health_snapshot(
        self,
        sensor_id: int,
        health_score: int,
        status: str,
        error_rate: float,
        total_readings: int = 0,
        failed_readings: int = 0,
    ) -> Optional[int]:
        """Save health monitoring snapshot."""
        try:
            db = self.get_db()
            cursor = db.execute(
                """
                INSERT INTO SensorHealthHistory
                (sensor_id, health_score, status, error_rate, total_readings, failed_readings)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (sensor_id, health_score, status, error_rate, total_readings, failed_readings),
            )
            db.commit()
            return cursor.lastrowid
        except sqlite3.Error as exc:
            logging.error("Error saving health snapshot: %s", exc)
            return None

    def get_health_history(self, sensor_id: int, limit: int = 100) -> List[Dict[str, Any]]:
        """Get health history for a sensor."""
        try:
            db = self.get_db()
            cursor = db.execute(
                """
                SELECT history_id, health_score, status, error_rate, 
                       total_readings, failed_readings, recorded_at
                FROM SensorHealthHistory
                WHERE sensor_id = ?
                ORDER BY recorded_at DESC
                LIMIT ?
                """,
                (sensor_id, limit),
            )
            return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error as exc:
            logging.error("Error getting health history: %s", exc)
            return []

    # --- Anomaly Detection -----------------------------------------------------
    def log_anomaly(
        self,
        sensor_id: int,
        value: float,
        mean_value: float,
        std_deviation: float,
        z_score: float,
    ) -> Optional[int]:
        """Log detected anomaly."""
        try:
            db = self.get_db()
            cursor = db.execute(
                """
                INSERT INTO SensorAnomaly
                (sensor_id, value, mean_value, std_deviation, z_score)
                VALUES (?, ?, ?, ?, ?)
                """,
                (sensor_id, value, mean_value, std_deviation, z_score),
            )
            db.commit()
            logging.info("⚠️ Anomaly logged for sensor %d", sensor_id)
            return cursor.lastrowid
        except sqlite3.Error as exc:
            logging.error("Error logging anomaly: %s", exc)
            return None

    def get_anomalies(self, sensor_id: int, limit: int = 100) -> List[Dict[str, Any]]:
        """Get anomalies for a sensor."""
        try:
            db = self.get_db()
            cursor = db.execute(
                """
                SELECT anomaly_id, value, mean_value, std_deviation, z_score, detected_at
                FROM SensorAnomaly
                WHERE sensor_id = ?
                ORDER BY detected_at DESC
                LIMIT ?
                """,
                (sensor_id, limit),
            )
            return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error as exc:
            logging.error("Error getting anomalies: %s", exc)
            return []

    def count_anomalies_for_sensors(
        self,
        sensor_ids: List[int],
        *,
        start: Optional[str] = None,
        end: Optional[str] = None,
    ) -> int:
        """Count anomalies for a set of sensors, optionally within a datetime range."""
        if not sensor_ids:
            return 0

        try:
            db = self.get_db()
            placeholders = ",".join(["?"] * len(sensor_ids))
            sql = f"""
                SELECT COUNT(*)
                FROM SensorAnomaly
                WHERE sensor_id IN ({placeholders})
            """
            params: List[Any] = list(sensor_ids)

            if start:
                sql += " AND datetime(detected_at) >= datetime(?)"
                params.append(start)
            if end:
                sql += " AND datetime(detected_at) <= datetime(?)"
                params.append(end)

            row = db.execute(sql, tuple(params)).fetchone()
            if not row:
                return 0
            return int(row[0])
        except sqlite3.Error as exc:
            logging.error("Error counting anomalies: %s", exc)
            return 0

    # --- Actuator Health -------------------------------------------------------
    def save_actuator_health_snapshot(
        self,
        actuator_id: int,
        health_score: int,
        status: str,
        total_operations: int = 0,
        failed_operations: int = 0,
        average_response_time: float = 0.0,
    ) -> Optional[int]:
        """Save actuator health monitoring snapshot."""
        try:
            db = self.get_db()
            cursor = db.execute(
                """
                INSERT INTO ActuatorHealthHistory
                (actuator_id, health_score, status, total_operations, 
                 failed_operations, average_response_time)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (actuator_id, health_score, status, total_operations, 
                 failed_operations, average_response_time),
            )
            db.commit()
            return cursor.lastrowid
        except sqlite3.Error as exc:
            logging.error("Error saving actuator health snapshot: %s", exc)
            return None

    def get_actuator_health_history(self, actuator_id: int, limit: int = 100) -> List[Dict[str, Any]]:
        """Get health history for an actuator."""
        try:
            db = self.get_db()
            cursor = db.execute(
                """
                SELECT history_id, health_score, status, total_operations,
                       failed_operations, average_response_time, 
                       last_successful_operation, recorded_at
                FROM ActuatorHealthHistory
                WHERE actuator_id = ?
                ORDER BY recorded_at DESC
                LIMIT ?
                """,
                (actuator_id, limit),
            )
            return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error as exc:
            logging.error("Error getting actuator health history: %s", exc)
            return []

    # --- Actuator Anomaly Detection --------------------------------------------
    def log_actuator_anomaly(
        self,
        actuator_id: int,
        anomaly_type: str,
        severity: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> Optional[int]:
        """Log detected actuator anomaly."""
        try:
            db = self.get_db()
            cursor = db.execute(
                """
                INSERT INTO ActuatorAnomaly
                (actuator_id, anomaly_type, severity, details)
                VALUES (?, ?, ?, ?)
                """,
                (actuator_id, anomaly_type, severity, json.dumps(details) if details else None),
            )
            db.commit()
            logging.warning("⚠️ Actuator anomaly logged: %s (severity: %s)", anomaly_type, severity)
            return cursor.lastrowid
        except sqlite3.Error as exc:
            logging.error("Error logging actuator anomaly: %s", exc)
            return None

    def get_actuator_anomalies(self, actuator_id: int, limit: int = 100) -> List[Dict[str, Any]]:
        """Get anomalies for an actuator."""
        try:
            db = self.get_db()
            cursor = db.execute(
                """
                SELECT anomaly_id, anomaly_type, severity, details, 
                       detected_at, resolved_at
                FROM ActuatorAnomaly
                WHERE actuator_id = ?
                ORDER BY detected_at DESC
                LIMIT ?
                """,
                (actuator_id, limit),
            )
            results = []
            for row in cursor.fetchall():
                anomaly = dict(row)
                if anomaly["details"]:
                    anomaly["details"] = json.loads(anomaly["details"])
                results.append(anomaly)
            return results
        except sqlite3.Error as exc:
            logging.error("Error getting actuator anomalies: %s", exc)
            return []

    def resolve_actuator_anomaly(self, anomaly_id: int) -> bool:
        """Mark an actuator anomaly as resolved."""
        try:
            db = self.get_db()
            db.execute(
                """
                UPDATE ActuatorAnomaly
                SET resolved_at = CURRENT_TIMESTAMP
                WHERE anomaly_id = ?
                """,
                (anomaly_id,),
            )
            db.commit()
            return True
        except sqlite3.Error as exc:
            logging.error("Error resolving actuator anomaly: %s", exc)
            return False

    # --- Actuator Power Readings -----------------------------------------------
    def save_actuator_power_reading(
        self,
        actuator_id: int,
        power_watts: float,
        voltage: Optional[float] = None,
        current: Optional[float] = None,
        energy_kwh: Optional[float] = None,
        power_factor: Optional[float] = None,
        frequency: Optional[float] = None,
        temperature: Optional[float] = None,
        is_estimated: bool = False,
    ) -> Optional[int]:
        """
        Save actuator power reading.
        
        Note: Redirected to unified EnergyReadings table.
        """
        try:
            db = self.get_db()
            
            # Lookup context: unit, plant and current growth stage
            actuator = db.execute(
                """
                SELECT a.unit_id, p.plant_id, p.current_stage
                FROM Actuator a
                LEFT JOIN Plants p ON p.unit_id = a.unit_id AND p.is_active = 1
                WHERE a.actuator_id = ?
                """, 
                (actuator_id,)
            ).fetchone()
            
            if not actuator:
                logging.warning("Actuator %d not found, cannot save power reading", actuator_id)
                return None
                
            unit_id = actuator["unit_id"]
            plant_id = actuator["plant_id"]
            growth_stage = actuator["current_stage"]

            cursor = db.execute(
                """
                INSERT INTO EnergyReadings (
                    device_id, unit_id, plant_id, growth_stage, 
                    voltage, current, power_watts, energy_kwh,
                    power_factor, frequency, temperature, is_estimated, source_type
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    actuator_id, unit_id, plant_id, growth_stage,
                    voltage, current, power_watts, energy_kwh,
                    power_factor, frequency, temperature, is_estimated, 'actuator'
                ),
            )
            db.commit()
            return cursor.lastrowid
        except sqlite3.Error as exc:
            logging.error("Error saving actuator power reading: %s", exc)
            return None

    def get_actuator_power_readings(
        self, 
        actuator_id: int, 
        limit: int = 1000,
        hours: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get power readings for an actuator.
        
        Note: Redirected to unified EnergyReadings table.
        """
        try:
            db = self.get_db()
            
            if hours:
                query = """
                    SELECT reading_id, voltage, current, power_watts, energy_kwh,
                           power_factor, frequency, temperature, is_estimated, timestamp
                    FROM EnergyReadings
                    WHERE device_id = ? AND source_type = 'actuator'
                      AND timestamp >= datetime('now', '-' || ? || ' hours')
                    ORDER BY timestamp DESC
                    LIMIT ?
                """
                cursor = db.execute(query, (actuator_id, hours, limit))
            else:
                query = """
                    SELECT reading_id, voltage, current, power_watts, energy_kwh,
                           power_factor, frequency, temperature, is_estimated, timestamp
                    FROM EnergyReadings
                    WHERE device_id = ? AND source_type = 'actuator'
                    ORDER BY timestamp DESC
                    LIMIT ?
                """
                cursor = db.execute(query, (actuator_id, limit))
            
            return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error as exc:
            logging.error("Error getting actuator power readings: %s", exc)
            return []

    # --- Actuator Calibration --------------------------------------------------
    def save_actuator_calibration(
        self,
        actuator_id: int,
        calibration_type: str,
        calibration_data: Dict[str, Any],
    ) -> Optional[int]:
        """Save actuator calibration (power profile, PWM curve, etc.)."""
        try:
            db = self.get_db()
            cursor = db.execute(
                """
                INSERT INTO ActuatorCalibration
                (actuator_id, calibration_type, calibration_data)
                VALUES (?, ?, ?)
                """,
                (actuator_id, calibration_type, json.dumps(calibration_data)),
            )
            db.commit()
            logging.info("✅ Calibration saved for actuator %d", actuator_id)
            return cursor.lastrowid
        except sqlite3.Error as exc:
            logging.error("Error saving actuator calibration: %s", exc)
            return None

    def get_actuator_calibrations(self, actuator_id: int) -> List[Dict[str, Any]]:
        """Get all calibrations for an actuator."""
        try:
            db = self.get_db()
            cursor = db.execute(
                """
                SELECT calibration_id, calibration_type, calibration_data, created_at
                FROM ActuatorCalibration
                WHERE actuator_id = ?
                ORDER BY created_at DESC
                """,
                (actuator_id,),
            )
            results = []
            for row in cursor.fetchall():
                calibration = dict(row)
                calibration["calibration_data"] = json.loads(calibration["calibration_data"])
                results.append(calibration)
            return results
        except sqlite3.Error as exc:
            logging.error("Error getting actuator calibrations: %s", exc)
            return []

    # --- Sensor Readings (Updated) ---------------------------------------------
    def insert_sensor_reading(
        self,
        sensor_id: int,
        reading_data: Dict[str, Any],
        quality_score: float = 1.0,
    ) -> Optional[int]:
        """Insert sensor reading with JSON data."""
        try:
            db = self.get_db()
            cursor = db.execute(
                """
                INSERT INTO SensorReading (sensor_id, reading_data, quality_score)
                VALUES (?, ?, ?)
                """,
                (sensor_id, json.dumps(reading_data), quality_score),
            )
            db.commit()
            return cursor.lastrowid
        except sqlite3.Error as exc:
            logging.error("Error inserting sensor reading: %s", exc)
            return None

    # --- Sensor Reading Aggregation (for Harvest Reports) -----------------------
    def aggregate_sensor_readings_for_period(
        self,
        period_start: str,
        period_end: str,
        granularity: str = "daily",
    ) -> int:
        """
        Aggregate sensor readings for a time period and save to SensorReadingSummary.

        This should be run BEFORE pruning to preserve summarized data for harvest reports.

        Args:
            period_start: ISO timestamp for start of period (e.g., '2026-01-11 00:00:00')
            period_end: ISO timestamp for end of period (e.g., '2026-01-12 00:00:00')
            granularity: 'daily', 'hourly', or 'weekly'

        Returns:
            Number of summary records created
        """
        try:
            db = self.get_db()

            # Get all sensors with readings in this period
            sensors_query = """
                SELECT DISTINCT
                    sr.sensor_id,
                    s.unit_id,
                    s.sensor_type
                FROM SensorReading sr
                JOIN Sensor s ON sr.sensor_id = s.sensor_id
                WHERE sr.timestamp >= ? AND sr.timestamp < ?
            """
            sensors = db.execute(sensors_query, (period_start, period_end)).fetchall()

            records_created = 0

            for sensor_row in sensors:
                sensor_id = sensor_row["sensor_id"]
                unit_id = sensor_row["unit_id"]
                sensor_type = sensor_row["sensor_type"]

                # Calculate aggregates for this sensor using per-sensor JSON paths.
                value_expr = self._sensor_value_expression(sensor_type)
                agg_query = f"""
                    SELECT
                        COUNT(*) as count_readings,
                        MIN(CAST({value_expr} AS REAL)) as min_value,
                        MAX(CAST({value_expr} AS REAL)) as max_value,
                        AVG(CAST({value_expr} AS REAL)) as avg_value,
                        SUM(CAST({value_expr} AS REAL)) as sum_value
                    FROM SensorReading
                    WHERE sensor_id = ?
                      AND timestamp >= ? AND timestamp < ?
                      AND {value_expr} IS NOT NULL
                """
                agg_row = db.execute(agg_query, (sensor_id, period_start, period_end)).fetchone()

                if not agg_row or agg_row["count_readings"] == 0:
                    continue

                # Calculate standard deviation manually (SQLite doesn't have STDDEV)
                stddev = self._calculate_stddev(
                    db, sensor_id, period_start, period_end, agg_row["avg_value"], value_expr
                )

                # Insert or update summary (REPLACE handles duplicates via UNIQUE constraint)
                insert_query = """
                    INSERT OR REPLACE INTO SensorReadingSummary (
                        sensor_id, unit_id, sensor_type, period_start, period_end,
                        granularity, min_value, max_value, avg_value, sum_value,
                        count_readings, stddev_value
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """
                db.execute(insert_query, (
                    sensor_id,
                    unit_id,
                    sensor_type,
                    period_start,
                    period_end,
                    granularity,
                    agg_row["min_value"],
                    agg_row["max_value"],
                    agg_row["avg_value"],
                    agg_row["sum_value"],
                    agg_row["count_readings"],
                    stddev,
                ))
                records_created += 1

            db.commit()
            logging.info(
                "Aggregated %d sensor summaries for period %s to %s",
                records_created, period_start, period_end
            )
            return records_created

        except sqlite3.Error as exc:
            logging.error("Error aggregating sensor readings: %s", exc)
            return 0

    def _calculate_stddev(
        self,
        db,
        sensor_id: int,
        period_start: str,
        period_end: str,
        mean: float,
        value_expr: str,
    ) -> Optional[float]:
        """Calculate standard deviation manually (SQLite lacks STDDEV)."""
        if mean is None:
            return None
        try:
            query = f"""
                SELECT AVG(
                    (CAST({value_expr} AS REAL) - ?) *
                    (CAST({value_expr} AS REAL) - ?)
                ) as variance
                FROM SensorReading
                WHERE sensor_id = ?
                  AND timestamp >= ? AND timestamp < ?
                  AND {value_expr} IS NOT NULL
            """
            row = db.execute(query, (mean, mean, sensor_id, period_start, period_end)).fetchone()
            if row and row["variance"] is not None:
                import math
                return math.sqrt(row["variance"])
            return None
        except Exception:
            return None

    def _sensor_value_expression(self, sensor_type: Optional[str]) -> str:
        """Build a safe SQL expression to extract the primary sensor value."""
        normalized = str(sensor_type or "").strip().lower()
        if normalized.endswith("_sensor"):
            normalized = normalized[: -len("_sensor")]

        def coalesce(keys: List[str]) -> str:
            # Move internal import here to avoid circular dependencies if any
            parts = [f"json_extract(reading_data, '$.{key}')" for key in keys]
            if len(parts) == 1:
                return parts[0]
            return f"COALESCE({', '.join(parts)})"

        from app.domain.sensors.fields import FIELD_ALIASES, SensorField
        
        # Build mapping based on standard fields
        value_keys: Dict[str, List[str]] = {}
        
        # Initialize with standard field names
        for field in SensorField:
            value_keys[field.value] = [field.value]
            
        # Add aliases
        for alias, standard_field in FIELD_ALIASES.items():
            field_name = standard_field.value if isinstance(standard_field, SensorField) else standard_field
            if field_name in value_keys:
                if alias not in value_keys[field_name]:
                    value_keys[field_name].append(alias)
            else:
                value_keys[field_name] = [field_name, alias]

        # Multi-type custom mappings
        value_keys.update({
            "temp_humidity": ["temperature", "humidity"],
            "environment": ["temperature", "humidity", "lux", "co2", "voc", "pressure", "soil_moisture", "ph", "ec", "air_quality"],
            "combo": ["temperature", "humidity", "lux", "co2", "voc", "pressure", "soil_moisture", "ph", "ec", "air_quality"],
            "plant": ["soil_moisture", "temperature", "humidity"],
            "light": value_keys.get("lux", ["lux"]), # legacy 'light' type uses 'lux' keys
        })

        for key, keys in value_keys.items():
            if normalized == key or normalized.startswith(key):
                return coalesce(keys)

        return "json_extract(reading_data, '$.value')"

    def aggregate_readings_by_days_old(self, days_threshold: int) -> int:
        """
        Aggregate all readings older than N days that haven't been summarized yet.

        This creates daily summaries for data that will soon be pruned.

        Args:
            days_threshold: Days threshold (e.g., 25 to aggregate before 30-day prune)

        Returns:
            Total summary records created
        """
        from datetime import datetime, timedelta

        try:
            db = self.get_db()

            # Find the date range for readings older than threshold
            cutoff_date = datetime.now() - timedelta(days=days_threshold)

            # Find the oldest reading date
            oldest_query = """
                SELECT MIN(DATE(timestamp)) as oldest_date
                FROM SensorReading
                WHERE timestamp < ?
            """
            oldest_row = db.execute(oldest_query, (cutoff_date.strftime("%Y-%m-%d %H:%M:%S"),)).fetchone()

            if not oldest_row or not oldest_row["oldest_date"]:
                logging.info("No old readings to aggregate")
                return 0

            oldest_date = datetime.strptime(oldest_row["oldest_date"], "%Y-%m-%d")
            total_created = 0

            # Process each day from oldest to cutoff
            current_date = oldest_date
            while current_date < cutoff_date:
                period_start = current_date.strftime("%Y-%m-%d 00:00:00")
                next_date = current_date + timedelta(days=1)
                period_end = next_date.strftime("%Y-%m-%d 00:00:00")

                # Check if already aggregated
                check_query = """
                    SELECT COUNT(*) as cnt FROM SensorReadingSummary
                    WHERE period_start = ? AND granularity = 'daily'
                """
                check_row = db.execute(check_query, (period_start,)).fetchone()

                if check_row and check_row["cnt"] > 0:
                    # Already aggregated, skip
                    current_date = next_date
                    continue

                # Aggregate this day
                created = self.aggregate_sensor_readings_for_period(
                    period_start, period_end, "daily"
                )
                total_created += created
                current_date = next_date

            logging.info("Total sensor summaries created: %d", total_created)
            return total_created

        except Exception as exc:
            logging.error("Error in aggregate_readings_by_days_old: %s", exc)
            return 0

    def get_sensor_summaries_for_unit(
        self,
        unit_id: int,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        sensor_type: Optional[str] = None,
        limit: int = 1000,
    ) -> List[Dict[str, Any]]:
        """
        Get aggregated sensor summaries for a unit (used in harvest reports).

        Args:
            unit_id: Growth unit ID
            start_date: Optional start date filter
            end_date: Optional end date filter
            sensor_type: Optional filter by sensor type
            limit: Max records to return

        Returns:
            List of summary records
        """
        try:
            db = self.get_db()

            query = """
                SELECT
                    id, sensor_id, unit_id, sensor_type, period_start, period_end,
                    granularity, min_value, max_value, avg_value, sum_value,
                    count_readings, stddev_value, created_at
                FROM SensorReadingSummary
                WHERE unit_id = ?
            """
            params: List[Any] = [unit_id]

            if start_date:
                query += " AND period_start >= ?"
                params.append(start_date)
            if end_date:
                query += " AND period_end <= ?"
                params.append(end_date)
            if sensor_type:
                query += " AND sensor_type = ?"
                params.append(sensor_type)

            query += " ORDER BY period_start DESC LIMIT ?"
            params.append(limit)

            cursor = db.execute(query, tuple(params))
            return [dict(row) for row in cursor.fetchall()]

        except sqlite3.Error as exc:
            logging.error("Error getting sensor summaries for unit: %s", exc)
            return []

    def get_sensor_summary_stats_for_harvest(
        self,
        unit_id: int,
        start_date: str,
        end_date: str,
    ) -> Dict[str, Any]:
        """
        Get aggregated statistics for a harvest report.

        Combines all summaries in the period to provide overall stats by sensor type.

        Args:
            unit_id: Growth unit ID
            start_date: Cycle start date
            end_date: Cycle end date

        Returns:
            Dict with stats grouped by sensor_type
        """
        try:
            db = self.get_db()

            query = """
                SELECT
                    sensor_type,
                    MIN(min_value) as overall_min,
                    MAX(max_value) as overall_max,
                    AVG(avg_value) as overall_avg,
                    SUM(count_readings) as total_readings,
                    COUNT(*) as summary_count
                FROM SensorReadingSummary
                WHERE unit_id = ?
                  AND period_start >= ?
                  AND period_end <= ?
                GROUP BY sensor_type
            """
            cursor = db.execute(query, (unit_id, start_date, end_date))

            stats: Dict[str, Any] = {}
            for row in cursor.fetchall():
                stats[row["sensor_type"]] = {
                    "min": row["overall_min"],
                    "max": row["overall_max"],
                    "avg": row["overall_avg"],
                    "total_readings": row["total_readings"],
                    "summary_periods": row["summary_count"],
                }

            return stats

        except sqlite3.Error as exc:
            logging.error("Error getting harvest summary stats: %s", exc)
            return {}

    # Placeholder for static type checkers.
    def get_db(self):  # pragma: no cover
        raise NotImplementedError
