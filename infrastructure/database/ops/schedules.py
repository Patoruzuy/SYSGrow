"""
Schedule Database Operations
=============================

Database operations for the centralized DeviceSchedules table.
Implements the ScheduleRepository protocol.

Author: Sebastian Gomez
Date: January 2026
"""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime
from typing import TYPE_CHECKING, Any

from app.domain.schedules.schedule_entity import PhotoperiodConfig, Schedule
from app.enums import ScheduleState, ScheduleType

if TYPE_CHECKING:
    from sqlite3 import Connection

logger = logging.getLogger(__name__)


class ScheduleOperations:
    """Schedule-related CRUD helpers for database handlers."""

    def get_db(self) -> "Connection":
        """Get database connection. Must be implemented by mixing class."""
        raise NotImplementedError("Subclass must implement get_db()")

    # =========================================================================
    # CRUD Operations
    # =========================================================================

    def create_schedule(self, schedule: Schedule) -> Schedule | None:
        """
        Create a new schedule in the database.

        Args:
            schedule: Schedule to create (schedule_id should be None)

        Returns:
            Created schedule with assigned schedule_id, or None on error
        """
        db = self.get_db()

        try:
            cursor = db.execute(
                """
                INSERT INTO DeviceSchedules (
                    unit_id, name, device_type, actuator_id, schedule_type,
                    start_time, end_time, interval_minutes, duration_minutes,
                    days_of_week, enabled,
                    state_when_active, value, photoperiod_config, priority,
                    metadata, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    schedule.unit_id,
                    schedule.name,
                    schedule.device_type,
                    schedule.actuator_id,
                    schedule.schedule_type.value,
                    schedule.start_time,
                    schedule.end_time,
                    schedule.interval_minutes,
                    schedule.duration_minutes,
                    json.dumps(schedule.days_of_week),
                    schedule.enabled,
                    schedule.state_when_active.value,
                    schedule.value,
                    json.dumps(schedule.photoperiod.to_dict()) if schedule.photoperiod else None,
                    schedule.priority,
                    json.dumps(schedule.metadata) if schedule.metadata else None,
                    datetime.now().isoformat(),
                    datetime.now().isoformat(),
                ),
            )
            db.commit()

            schedule.schedule_id = cursor.lastrowid
            schedule.created_at = datetime.now()
            schedule.updated_at = datetime.now()

            logger.info(
                f"Created schedule {schedule.schedule_id} for {schedule.device_type} in unit {schedule.unit_id}"
            )
            return schedule

        except sqlite3.Error as e:
            logger.error(f"Error creating schedule: {e}")
            return None

    def get_schedule_by_id(self, schedule_id: int) -> Schedule | None:
        """
        Get schedule by ID.

        Args:
            schedule_id: Schedule ID

        Returns:
            Schedule if found, None otherwise
        """
        db = self.get_db()

        try:
            row = db.execute(
                "SELECT * FROM DeviceSchedules WHERE schedule_id = ?",
                (schedule_id,),
            ).fetchone()

            if row:
                return self._row_to_schedule(dict(row))
            return None

        except sqlite3.Error as e:
            logger.error(f"Error getting schedule {schedule_id}: {e}")
            return None

    def get_schedules_by_unit(self, unit_id: int) -> list[Schedule]:
        """
        Get all schedules for a growth unit.

        Args:
            unit_id: Growth unit ID

        Returns:
            List of schedules for the unit
        """
        db = self.get_db()

        try:
            rows = db.execute(
                """
                SELECT * FROM DeviceSchedules 
                WHERE unit_id = ? 
                ORDER BY device_type, priority DESC, start_time
                """,
                (unit_id,),
            ).fetchall()

            return [self._row_to_schedule(dict(row)) for row in rows]

        except sqlite3.Error as e:
            logger.error(f"Error getting schedules for unit {unit_id}: {e}")
            return []

    def get_schedules_by_device_type(self, unit_id: int, device_type: str) -> list[Schedule]:
        """
        Get all schedules for a specific device type in a unit.

        Args:
            unit_id: Growth unit ID
            device_type: Device type (e.g., 'light', 'fan')

        Returns:
            List of schedules for the device type
        """
        db = self.get_db()

        try:
            rows = db.execute(
                """
                SELECT * FROM DeviceSchedules 
                WHERE unit_id = ? AND device_type = ?
                ORDER BY priority DESC, start_time
                """,
                (unit_id, device_type),
            ).fetchall()

            return [self._row_to_schedule(dict(row)) for row in rows]

        except sqlite3.Error as e:
            logger.error(f"Error getting schedules for {device_type} in unit {unit_id}: {e}")
            return []

    def get_schedules_by_actuator(self, actuator_id: int) -> list[Schedule]:
        """
        Get all schedules for a specific actuator.

        Args:
            actuator_id: Actuator ID

        Returns:
            List of schedules for the actuator
        """
        db = self.get_db()

        try:
            rows = db.execute(
                """
                SELECT * FROM DeviceSchedules 
                WHERE actuator_id = ?
                ORDER BY priority DESC, start_time
                """,
                (actuator_id,),
            ).fetchall()

            return [self._row_to_schedule(dict(row)) for row in rows]

        except sqlite3.Error as e:
            logger.error(f"Error getting schedules for actuator {actuator_id}: {e}")
            return []

    def update_schedule(self, schedule: Schedule) -> Schedule | None:
        """
        Update an existing schedule.

        Args:
            schedule: Schedule with updated values (must have schedule_id)

        Returns:
            Updated schedule if found, None otherwise
        """
        if not schedule.schedule_id:
            logger.error("Cannot update schedule without schedule_id")
            return None

        db = self.get_db()

        try:
            schedule.updated_at = datetime.now()

            db.execute(
                """
                UPDATE DeviceSchedules SET
                    name = ?,
                    device_type = ?,
                    actuator_id = ?,
                    schedule_type = ?,
                    start_time = ?,
                    end_time = ?,
                    interval_minutes = ?,
                    duration_minutes = ?,
                    days_of_week = ?,
                    enabled = ?,
                    state_when_active = ?,
                    value = ?,
                    photoperiod_config = ?,
                    priority = ?,
                    metadata = ?,
                    updated_at = ?
                WHERE schedule_id = ?
                """,
                (
                    schedule.name,
                    schedule.device_type,
                    schedule.actuator_id,
                    schedule.schedule_type.value,
                    schedule.start_time,
                    schedule.end_time,
                    schedule.interval_minutes,
                    schedule.duration_minutes,
                    json.dumps(schedule.days_of_week),
                    schedule.enabled,
                    schedule.state_when_active.value,
                    schedule.value,
                    json.dumps(schedule.photoperiod.to_dict()) if schedule.photoperiod else None,
                    schedule.priority,
                    json.dumps(schedule.metadata) if schedule.metadata else None,
                    schedule.updated_at.isoformat(),
                    schedule.schedule_id,
                ),
            )
            db.commit()

            logger.info(f"Updated schedule {schedule.schedule_id}")
            return schedule

        except sqlite3.Error as e:
            logger.error(f"Error updating schedule {schedule.schedule_id}: {e}")
            return None

    def delete_schedule(self, schedule_id: int) -> bool:
        """
        Delete a schedule.

        Args:
            schedule_id: Schedule ID

        Returns:
            True if deleted, False if not found
        """
        db = self.get_db()

        try:
            cursor = db.execute(
                "DELETE FROM DeviceSchedules WHERE schedule_id = ?",
                (schedule_id,),
            )
            db.commit()

            if cursor.rowcount > 0:
                logger.info(f"Deleted schedule {schedule_id}")
                return True
            return False

        except sqlite3.Error as e:
            logger.error(f"Error deleting schedule {schedule_id}: {e}")
            return False

    def delete_schedules_by_unit(self, unit_id: int) -> int:
        """
        Delete all schedules for a growth unit.

        Args:
            unit_id: Growth unit ID

        Returns:
            Number of schedules deleted
        """
        db = self.get_db()

        try:
            cursor = db.execute(
                "DELETE FROM DeviceSchedules WHERE unit_id = ?",
                (unit_id,),
            )
            db.commit()

            logger.info(f"Deleted {cursor.rowcount} schedules for unit {unit_id}")
            return cursor.rowcount

        except sqlite3.Error as e:
            logger.error(f"Error deleting schedules for unit {unit_id}: {e}")
            return 0

    def set_schedule_enabled(self, schedule_id: int, enabled: bool) -> bool:
        """
        Enable or disable a schedule.

        Args:
            schedule_id: Schedule ID
            enabled: True to enable, False to disable

        Returns:
            True if updated, False if not found
        """
        db = self.get_db()

        try:
            cursor = db.execute(
                """
                UPDATE DeviceSchedules 
                SET enabled = ?, updated_at = ?
                WHERE schedule_id = ?
                """,
                (enabled, datetime.now().isoformat(), schedule_id),
            )
            db.commit()

            if cursor.rowcount > 0:
                logger.info(f"Set schedule {schedule_id} enabled={enabled}")
                return True
            return False

        except sqlite3.Error as e:
            logger.error(f"Error setting schedule {schedule_id} enabled: {e}")
            return False

    def get_enabled_schedules_by_unit(self, unit_id: int) -> list[Schedule]:
        """
        Get all enabled schedules for a unit.

        Args:
            unit_id: Growth unit ID

        Returns:
            List of enabled schedules
        """
        db = self.get_db()

        try:
            rows = db.execute(
                """
                SELECT * FROM DeviceSchedules 
                WHERE unit_id = ? AND enabled = 1
                ORDER BY device_type, priority DESC, start_time
                """,
                (unit_id,),
            ).fetchall()

            return [self._row_to_schedule(dict(row)) for row in rows]

        except sqlite3.Error as e:
            logger.error(f"Error getting enabled schedules for unit {unit_id}: {e}")
            return []

    def get_light_schedule(self, unit_id: int) -> Schedule | None:
        """
        Get the primary light schedule for a unit (highest priority enabled).

        Args:
            unit_id: Growth unit ID

        Returns:
            Primary light schedule or None
        """
        db = self.get_db()

        try:
            row = db.execute(
                """
                SELECT * FROM DeviceSchedules 
                WHERE unit_id = ? AND device_type = 'light' AND enabled = 1
                ORDER BY priority DESC
                LIMIT 1
                """,
                (unit_id,),
            ).fetchone()

            if row:
                return self._row_to_schedule(dict(row))
            return None

        except sqlite3.Error as e:
            logger.error(f"Error getting light schedule for unit {unit_id}: {e}")
            return None

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _row_to_schedule(self, row: dict[str, Any]) -> Schedule:
        """Convert database row to Schedule object."""
        # Parse JSON fields
        days_of_week = [0, 1, 2, 3, 4, 5, 6]
        if row.get("days_of_week"):
            try:
                days_of_week = json.loads(row["days_of_week"])
            except (json.JSONDecodeError, TypeError):
                pass

        photoperiod = None
        if row.get("photoperiod_config"):
            try:
                photoperiod = PhotoperiodConfig.from_dict(json.loads(row["photoperiod_config"]))
            except (json.JSONDecodeError, TypeError):
                pass

        metadata = {}
        if row.get("metadata"):
            try:
                metadata = json.loads(row["metadata"])
            except (json.JSONDecodeError, TypeError):
                pass

        # Parse timestamps
        created_at = datetime.now()
        if row.get("created_at"):
            try:
                created_at = datetime.fromisoformat(row["created_at"])
            except (ValueError, TypeError):
                pass

        updated_at = datetime.now()
        if row.get("updated_at"):
            try:
                updated_at = datetime.fromisoformat(row["updated_at"])
            except (ValueError, TypeError):
                pass

        return Schedule(
            schedule_id=row.get("schedule_id"),
            unit_id=row.get("unit_id", 0),
            name=row.get("name", ""),
            device_type=row.get("device_type", ""),
            actuator_id=row.get("actuator_id"),
            schedule_type=ScheduleType(row.get("schedule_type", "simple")),
            interval_minutes=row.get("interval_minutes"),
            duration_minutes=row.get("duration_minutes"),
            start_time=row.get("start_time", "08:00"),
            end_time=row.get("end_time", "20:00"),
            days_of_week=days_of_week,
            enabled=bool(row.get("enabled", True)),
            state_when_active=ScheduleState(row.get("state_when_active", "on")),
            value=row.get("value"),
            photoperiod=photoperiod,
            priority=row.get("priority", 0),
            metadata=metadata,
            created_at=created_at,
            updated_at=updated_at,
        )
