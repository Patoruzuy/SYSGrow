"""
Schedule Repository
====================

Concrete implementation of ScheduleRepository protocol using SQLite.
Wraps ScheduleOperations mixin from infrastructure layer.

Features:
- Full CRUD with caching
- Schedule history/audit logging
- Execution logging for tracking

Author: Sebastian Gomez
Date: January 2026
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, TYPE_CHECKING
import json

from app.domain.schedules import Schedule
from app.domain.schedules.repository import ScheduleRepository as ScheduleRepositoryProtocol
from app.utils.time import iso_now
from infrastructure.database.decorators import repository_cache, invalidates_caches

if TYPE_CHECKING:
    from infrastructure.database.ops.schedules import ScheduleOperations


class ScheduleRepository:
    """
    Concrete implementation of ScheduleRepository protocol.
    
    Wraps the ScheduleOperations mixin to provide repository pattern access.
    """

    def __init__(self, backend: "ScheduleOperations") -> None:
        """
        Initialize with database backend.
        
        Args:
            backend: Database handler that implements ScheduleOperations
        """
        self._backend = backend

    # ==================== CRUD Operations ====================

    @invalidates_caches
    def create(self, schedule: Schedule) -> Optional[Schedule]:
        """Create a new schedule."""
        return self._backend.create_schedule(schedule)

    @repository_cache(maxsize=256, invalidate_on=['create', 'update', 'delete', 'delete_by_unit', 'set_enabled'])
    def get_by_id(self, schedule_id: int) -> Optional[Schedule]:
        """Get schedule by ID."""
        return self._backend.get_schedule_by_id(schedule_id)

    @repository_cache(maxsize=64, invalidate_on=['create', 'update', 'delete', 'delete_by_unit', 'set_enabled'])
    def get_by_unit(self, unit_id: int) -> List[Schedule]:
        """Get all schedules for a growth unit."""
        return self._backend.get_schedules_by_unit(unit_id)

    @repository_cache(maxsize=128, invalidate_on=['create', 'update', 'delete', 'delete_by_unit', 'set_enabled'])
    def get_by_device_type(self, unit_id: int, device_type: str) -> List[Schedule]:
        """Get all schedules for a specific device type in a unit."""
        return self._backend.get_schedules_by_device_type(unit_id, device_type)

    @repository_cache(maxsize=128, invalidate_on=['create', 'update', 'delete', 'set_enabled'])
    def get_by_actuator(self, actuator_id: int) -> List[Schedule]:
        """Get all schedules for a specific actuator."""
        return self._backend.get_schedules_by_actuator(actuator_id)

    @invalidates_caches
    def update(self, schedule: Schedule) -> Optional[Schedule]:
        """Update an existing schedule."""
        result = self._backend.update_schedule(schedule)
        # Return the updated schedule on success
        if result:
            return self._backend.get_schedule_by_id(schedule.schedule_id)
        return None

    @invalidates_caches
    def delete(self, schedule_id: int) -> bool:
        """Delete a schedule."""
        return self._backend.delete_schedule(schedule_id)

    @invalidates_caches
    def delete_by_unit(self, unit_id: int) -> int:
        """Delete all schedules for a growth unit."""
        return self._backend.delete_schedules_by_unit(unit_id)

    @invalidates_caches
    def set_enabled(self, schedule_id: int, enabled: bool) -> bool:
        """Enable or disable a schedule."""
        return self._backend.set_schedule_enabled(schedule_id, enabled)

    # ==================== Query Operations ====================

    @repository_cache(maxsize=64, invalidate_on=['create', 'update', 'delete', 'delete_by_unit', 'set_enabled'])
    def get_enabled_schedules(self, unit_id: int) -> List[Schedule]:
        """Get all enabled schedules for a unit."""
        return self._backend.get_enabled_schedules_by_unit(unit_id)

    @repository_cache(maxsize=64, invalidate_on=['create', 'update', 'delete', 'delete_by_unit', 'set_enabled'])
    def get_active_schedules(self, unit_id: int) -> List[Schedule]:
        """
        Get schedules that are currently active (enabled and within time window).
        
        Note: This is an alias for get_enabled_schedules. 
        Actual time-based evaluation is done by the SchedulingService.
        """
        return self._backend.get_enabled_schedules_by_unit(unit_id)

    @repository_cache(maxsize=64, invalidate_on=['create', 'update', 'delete', 'delete_by_unit', 'set_enabled'])
    def get_light_schedule(self, unit_id: int) -> Optional[Schedule]:
        """Get the primary light schedule for a unit."""
        return self._backend.get_light_schedule(unit_id)

    # ==================== History/Audit Logging ====================

    def log_history(
        self,
        schedule_id: int,
        unit_id: int,
        action: str,
        device_type: Optional[str] = None,
        before_state: Optional[str] = None,
        after_state: Optional[str] = None,
        changed_fields: Optional[str] = None,
        source: str = "user",
        user_id: Optional[int] = None,
        reason: Optional[str] = None,
    ) -> bool:
        """Log a schedule change to history table."""
        try:
            db = self._backend.get_db()
            db.execute(
                """
                INSERT INTO ScheduleHistory (
                    schedule_id, unit_id, action, device_type,
                    before_state, after_state, changed_fields,
                    source, user_id, reason, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    schedule_id, unit_id, action, device_type,
                    before_state, after_state, changed_fields,
                    source, user_id, reason, iso_now()
                ),
            )
            db.commit()
            return True
        except Exception:
            return False

    def get_history(
        self,
        schedule_id: Optional[int] = None,
        unit_id: Optional[int] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Get schedule history records."""
        try:
            db = self._backend.get_db()
            query = "SELECT * FROM ScheduleHistory WHERE 1=1"
            params = []
            
            if schedule_id:
                query += " AND schedule_id = ?"
                params.append(schedule_id)
            if unit_id:
                query += " AND unit_id = ?"
                params.append(unit_id)
            
            query += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)
            
            rows = db.execute(query, params).fetchall()
            return [dict(row) for row in rows]
        except Exception:
            return []

    # ==================== Execution Logging ====================

    def log_execution(
        self,
        schedule_id: int,
        actuator_id: Optional[int],
        action: str,
        success: bool,
        error_message: Optional[str] = None,
        retry_count: int = 0,
        response_time_ms: Optional[int] = None,
    ) -> bool:
        """Log a schedule execution to the execution log table."""
        try:
            db = self._backend.get_db()
            db.execute(
                """
                INSERT INTO ScheduleExecutionLog (
                    schedule_id, actuator_id, execution_time, action,
                    success, error_message, retry_count, response_time_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    schedule_id, actuator_id, iso_now(),
                    action, 1 if success else 0, error_message,
                    retry_count, response_time_ms
                ),
            )
            db.commit()
            return True
        except Exception:
            return False

    def get_execution_log(
        self,
        schedule_id: Optional[int] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Get schedule execution log records."""
        try:
            db = self._backend.get_db()
            if schedule_id:
                query = """
                    SELECT * FROM ScheduleExecutionLog 
                    WHERE schedule_id = ? 
                    ORDER BY execution_time DESC LIMIT ?
                """
                rows = db.execute(query, (schedule_id, limit)).fetchall()
            else:
                query = """
                    SELECT * FROM ScheduleExecutionLog 
                    ORDER BY execution_time DESC LIMIT ?
                """
                rows = db.execute(query, (limit,)).fetchall()
            return [dict(row) for row in rows]
        except Exception:
            return []


# Type assertion to ensure we implement the protocol
def _check_protocol() -> None:
    """Static check that ScheduleRepository implements the protocol."""
    repo: ScheduleRepositoryProtocol = ScheduleRepository(None)  # type: ignore
    _ = repo
