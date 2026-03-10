from __future__ import annotations

import logging
import sqlite3
from typing import Any

from infrastructure.utils.structured_fields import (
    dump_json_field,
    normalize_device_schedules,
    parse_json_object,
)

logger = logging.getLogger(__name__)


class SettingsOperations:
    """Settings-related CRUD helpers shared across database handlers."""

    def _ensure_settings_seeded(self) -> None:
        db = self.get_db()
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS Settings (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                temperature_threshold REAL,
                humidity_threshold REAL,
                soil_moisture_threshold REAL
            )
            """
        )
        db.execute("INSERT OR IGNORE INTO Settings (id) VALUES (1)")

        # Create ESP32-C3 devices table
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS ESP32C3Devices (
                device_id TEXT PRIMARY KEY,
                device_data TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        db.commit()

    # --- Hotspot ---------------------------------------------------------------
    def save_hotspot_settings(self, ssid: str, encrypted_password: str) -> None:
        db = self.get_db()
        db.execute(
            """
            INSERT OR REPLACE INTO HotspotSettings (id, ssid, encrypted_password)
            VALUES (1, ?, ?)
            """,
            (ssid, encrypted_password),
        )
        db.commit()

    def load_hotspot_settings(self) -> dict[str, Any] | None:
        db = self.get_db()
        settings = db.execute("SELECT ssid, encrypted_password FROM HotspotSettings WHERE id = 1").fetchone()
        if settings:
            return {"ssid": settings["ssid"], "encrypted_password": settings["encrypted_password"]}
        return None

    # --- Camera -----------------------------------------------------------------
    def save_camera_settings(
        self,
        camera_type: str,
        ip_address: str | None,
        usb_cam_index: int | None,
        last_used: str | None,
        resolution: int | None,
        quality: int | None,
        brightness: int | None,
        contrast: int | None,
        saturation: int | None,
        flip: int | None,
    ) -> None:
        db = self.get_db()
        db.execute(
            """
            INSERT OR REPLACE INTO CameraSettings (
                id,
                camera_type,
                ip_address,
                usb_cam_index,
                last_used,
                resolution,
                quality,
                brightness,
                contrast,
                saturation,
                flip
            ) VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                camera_type,
                ip_address,
                usb_cam_index,
                last_used,
                resolution,
                quality,
                brightness,
                contrast,
                saturation,
                flip,
            ),
        )
        db.commit()

    def load_camera_settings(self) -> dict[str, Any] | None:
        db = self.get_db()
        result = db.execute(
            """
            SELECT camera_type,
                   ip_address,
                   usb_cam_index,
                   last_used,
                   resolution,
                   quality,
                   brightness,
                   contrast,
                   saturation,
                   flip
            FROM CameraSettings
            WHERE id = 1
            """
        ).fetchone()

        if not result:
            return None

        return {
            "camera_type": result["camera_type"],
            "ip_address": result["ip_address"],
            "usb_cam_index": result["usb_cam_index"],
            "last_used": result["last_used"],
            "resolution": result["resolution"],
            "quality": result["quality"],
            "brightness": result["brightness"],
            "contrast": result["contrast"],
            "saturation": result["saturation"],
            "flip": result["flip"],
        }

    # --- Environment Info ------------------------------------------------------
    def save_environment_info(self, unit_id: int, info_data: dict[str, Any]) -> int | None:
        """
        Save or update environment information for a unit.

        Calculates room_volume if dimensions (m) are provided.
        """
        try:
            db = self.get_db()

            # Calculate volume if needed
            width = info_data.get("room_width", 0)
            length = info_data.get("room_length", 0)
            height = info_data.get("room_height", 0)
            volume = info_data.get("room_volume")
            if not volume and width and length and height:
                volume = width * length * height

            # Check if exists
            existing = db.execute("SELECT env_id FROM EnvironmentInfo WHERE unit_id = ?", (unit_id,)).fetchone()

            if existing:
                query = """
                    UPDATE EnvironmentInfo SET
                        room_width=?, room_length=?, room_height=?, room_volume=?,
                        insulation_type=?, ventilation_type=?, window_area=?,
                        light_source_type=?, ambient_light_hours=?, location_climate=?,
                        outdoor_temperature_avg=?, outdoor_humidity_avg=?,
                        electricity_cost_per_kwh=?, updated_at=CURRENT_TIMESTAMP
                    WHERE unit_id = ?
                """
                db.execute(
                    query,
                    (
                        width,
                        length,
                        height,
                        volume,
                        info_data.get("insulation_type"),
                        info_data.get("ventilation_type"),
                        info_data.get("window_area"),
                        info_data.get("light_source_type"),
                        info_data.get("ambient_light_hours"),
                        info_data.get("location_climate"),
                        info_data.get("outdoor_temperature_avg"),
                        info_data.get("outdoor_humidity_avg"),
                        info_data.get("electricity_cost_per_kwh"),
                        unit_id,
                    ),
                )
                db.commit()
                return existing["env_id"]
            else:
                query = """
                    INSERT INTO EnvironmentInfo (
                        unit_id, room_width, room_length, room_height, room_volume,
                        insulation_type, ventilation_type, window_area,
                        light_source_type, ambient_light_hours, location_climate,
                        outdoor_temperature_avg, outdoor_humidity_avg,
                        electricity_cost_per_kwh
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """
                cursor = db.execute(
                    query,
                    (
                        unit_id,
                        width,
                        length,
                        height,
                        volume,
                        info_data.get("insulation_type"),
                        info_data.get("ventilation_type"),
                        info_data.get("window_area"),
                        info_data.get("light_source_type"),
                        info_data.get("ambient_light_hours"),
                        info_data.get("location_climate"),
                        info_data.get("outdoor_temperature_avg"),
                        info_data.get("outdoor_humidity_avg"),
                        info_data.get("electricity_cost_per_kwh"),
                    ),
                )
                db.commit()
                return cursor.lastrowid
        except sqlite3.Error as exc:
            logging.error("Error saving environment info: %s", exc)
            return None

    def get_environment_info(self, unit_id: int) -> dict[str, Any] | None:
        """Get environment information for a unit."""
        try:
            db = self.get_db()
            row = db.execute("SELECT * FROM EnvironmentInfo WHERE unit_id = ?", (unit_id,)).fetchone()
            return dict(row) if row else None
        except sqlite3.Error as exc:
            logging.error("Error getting environment info: %s", exc)
            return None

    # --- Environment thresholds -------------------------------------------------

    def save_device_schedule(
        self, unit_id: int, device_type: str, start_time: str, end_time: str, enabled: bool = True
    ) -> bool:
        """
        Save or update a device schedule in the device_schedules JSON field.

        Args:
            unit_id: Growth unit ID
            device_type: Device type (e.g., 'light', 'fan', 'pump', 'heater')
            start_time: Start time in HH:MM format
            end_time: End time in HH:MM format
            enabled: Whether the schedule is enabled

        Returns:
            True if successful, False otherwise
        """
        db = self.get_db()

        # Get current device_schedules
        row = db.execute("SELECT device_schedules FROM GrowthUnits WHERE unit_id = ?", (unit_id,)).fetchone()

        if not row:
            logging.warning(f"Unit {unit_id} not found")
            return False

        # Parse existing schedules or create new dict
        schedules = normalize_device_schedules(row["device_schedules"]) or {}

        # Update the specific device schedule
        schedules[device_type] = {"start_time": start_time, "end_time": end_time, "enabled": enabled}

        # Save back to database
        db.execute(
            """
            UPDATE GrowthUnits
            SET device_schedules = ?, updated_at = CURRENT_TIMESTAMP
            WHERE unit_id = ?
            """,
            (dump_json_field(schedules), unit_id),
        )
        db.commit()
        return True

    def get_device_schedule(self, unit_id: int, device_type: str) -> dict[str, Any] | None:
        """
        Get a specific device schedule from the device_schedules JSON field.

        Args:
            unit_id: Growth unit ID
            device_type: Device type (e.g., 'light', 'fan', 'pump', 'heater')

        Returns:
            Schedule dict with start_time, end_time, enabled or None if not found
        """
        db = self.get_db()

        row = db.execute("SELECT device_schedules FROM GrowthUnits WHERE unit_id = ?", (unit_id,)).fetchone()

        if not row or not row["device_schedules"]:
            return None

        schedules = normalize_device_schedules(row["device_schedules"])
        if schedules is None:
            logging.error(f"Invalid JSON in device_schedules for unit {unit_id}")
            return None
        return schedules.get(device_type)

    def get_all_device_schedules(self, unit_id: int) -> dict[str, dict[str, Any]]:
        """
        Get all device schedules for a growth unit.

        Args:
            unit_id: Growth unit ID

        Returns:
            Dictionary of all device schedules, e.g.:
            {
                "light": {"start_time": "06:00", "end_time": "22:00", "enabled": True},
                "fan": {"start_time": "08:00", "end_time": "20:00", "enabled": True}
            }
        """
        db = self.get_db()

        row = db.execute("SELECT device_schedules FROM GrowthUnits WHERE unit_id = ?", (unit_id,)).fetchone()

        if not row or not row["device_schedules"]:
            return {}

        schedules = normalize_device_schedules(row["device_schedules"])
        if schedules is None:
            logging.error(f"Invalid JSON in device_schedules for unit {unit_id}")
            return {}
        return schedules

    def delete_device_schedule(self, unit_id: int, device_type: str) -> bool:
        """
        Delete a specific device schedule from the device_schedules JSON field.

        Args:
            unit_id: Growth unit ID
            device_type: Device type to remove

        Returns:
            True if successful, False otherwise
        """
        db = self.get_db()

        row = db.execute("SELECT device_schedules FROM GrowthUnits WHERE unit_id = ?", (unit_id,)).fetchone()

        if not row:
            return False

        schedules = normalize_device_schedules(row["device_schedules"]) or {}

        if device_type in schedules:
            del schedules[device_type]

            db.execute(
                """
                UPDATE GrowthUnits
                SET device_schedules = ?, updated_at = CURRENT_TIMESTAMP
                WHERE unit_id = ?
                """,
                (dump_json_field(schedules), unit_id),
            )
            db.commit()
            return True

        return False

    def update_device_schedule_status(self, unit_id: int, device_type: str, enabled: bool) -> bool:
        """
        Enable or disable a device schedule without changing times.

        Args:
            unit_id: Growth unit ID
            device_type: Device type
            enabled: True to enable, False to disable

        Returns:
            True if successful, False otherwise
        """
        db = self.get_db()

        row = db.execute("SELECT device_schedules FROM GrowthUnits WHERE unit_id = ?", (unit_id,)).fetchone()

        if not row:
            return False

        schedules = normalize_device_schedules(row["device_schedules"]) or {}

        if device_type in schedules:
            schedules[device_type]["enabled"] = enabled

            db.execute(
                """
                UPDATE GrowthUnits
                SET device_schedules = ?, updated_at = CURRENT_TIMESTAMP
                WHERE unit_id = ?
                """,
                (dump_json_field(schedules), unit_id),
            )
            db.commit()
            return True

        return False

    def save_environment_thresholds(
        self,
        temperature_threshold: float,
        humidity_threshold: float,
        soil_moisture_threshold: float,
    ) -> None:
        try:
            db = self.get_db()
            db.execute(
                """
                UPDATE Settings
                SET temperature_threshold = ?,
                    humidity_threshold = ?,
                    soil_moisture_threshold = ?
                WHERE id = 1
                """,
                (temperature_threshold, humidity_threshold, soil_moisture_threshold),
            )
            db.commit()
        except sqlite3.Error as exc:
            logger.error("Failed to save environment thresholds: %s", exc)

    def get_environment_thresholds(self) -> dict[str, Any] | None:
        try:
            db = self.get_db()
            row = db.execute(
                """
                SELECT temperature_threshold,
                       humidity_threshold,
                       soil_moisture_threshold
                FROM Settings
                WHERE id = 1
                """
            ).fetchone()
            if row:
                return {
                    "temperature_threshold": row["temperature_threshold"],
                    "humidity_threshold": row["humidity_threshold"],
                    "soil_moisture_threshold": row["soil_moisture_threshold"],
                }
            return None
        except sqlite3.Error as exc:
            logger.error("Failed to fetch environment thresholds: %s", exc)
            return None

    # --- ESP32-C3 Device Management ------------------------------------------
    def get_esp32_c6_devices(self) -> list[dict[str, Any]]:
        """Get all ESP32-C3 devices."""
        db = self.get_db()
        rows = db.execute("SELECT device_id, device_data FROM ESP32C3Devices ORDER BY created_at").fetchall()

        devices = []
        for row in rows:
            device_data = parse_json_object(row["device_data"])
            if isinstance(device_data, dict):
                devices.append(device_data)

        return devices

    def get_esp32_c6_device(self, device_id: str) -> dict[str, Any] | None:
        """Get a specific ESP32-C3 device by ID."""
        db = self.get_db()
        row = db.execute("SELECT device_data FROM ESP32C3Devices WHERE device_id = ?", (device_id,)).fetchone()

        if row:
            data = parse_json_object(row["device_data"])
            return data if isinstance(data, dict) else None
        return None

    def save_esp32_c6_device(self, device_id: str, device_data: dict[str, Any]) -> None:
        """Save or update ESP32-C3 device data."""
        db = self.get_db()
        device_json = dump_json_field(device_data)

        db.execute(
            """
            INSERT OR REPLACE INTO ESP32C3Devices (device_id, device_data, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            """,
            (device_id, device_json),
        )
        db.commit()

    def delete_esp32_c6_device(self, device_id: str) -> bool:
        """Delete an ESP32-C3 device."""
        db = self.get_db()
        cursor = db.execute("DELETE FROM ESP32C3Devices WHERE device_id = ?", (device_id,))
        db.commit()
        return cursor.rowcount > 0

    # Placeholder methods to satisfy type checkers; real implementations must exist.
    def get_db(self) -> sqlite3.Connection:  # pragma: no cover - implemented by subclasses
        raise NotImplementedError
