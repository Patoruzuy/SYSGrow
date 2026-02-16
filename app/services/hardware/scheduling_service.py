"""
Centralized Scheduling Service
==============================

Single point of truth for all device schedules across growth units.

Features:
- CRUD operations for schedules (persisted to DeviceSchedules table)
- Multiple schedules per device type (e.g., fan every 2 hours)
- Enable/disable schedules without deletion
- Photoperiod integration for light schedules
- Schedule conflict detection and resolution
- Schedule history/audit logging
- Automatic schedule generation from plant growth stages
- Sun times API integration for outdoor units
- Startup state synchronization
- Retry logic with exponential backoff

Note: Schedule execution is handled by UnifiedScheduler via scheduled tasks.
This service manages schedule storage, retrieval, and evaluation logic.

Author: Sebastian Gomez
Date: January 2026
"""

from __future__ import annotations

import json
import logging
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import TYPE_CHECKING, Any, Callable

from app.domain.schedules import Schedule
from app.enums import PhotoperiodSource, ScheduleState, ScheduleType

if TYPE_CHECKING:
    from app.domain.schedules.repository import ScheduleRepository
    from app.services.utilities.sun_times_service import SunTimesService
    from app.workers.unified_scheduler import UnifiedScheduler

logger = logging.getLogger(__name__)


class ScheduleAction(str, Enum):
    """Actions for schedule history logging."""

    CREATED = "created"
    UPDATED = "updated"
    DELETED = "deleted"
    ENABLED = "enabled"
    DISABLED = "disabled"
    EXECUTED = "executed"
    FAILED = "failed"
    AUTO_GENERATED = "auto_generated"


@dataclass
class ScheduleConflict:
    """Represents a schedule conflict."""

    schedule_a: Schedule
    schedule_b: Schedule
    overlap_start: str
    overlap_end: str
    conflicting_days: list[int]
    resolution: str = "higher_priority_wins"


@dataclass
class SchedulePreviewEvent:
    """A preview event showing when a schedule will activate/deactivate."""

    schedule_id: int
    schedule_name: str
    device_type: str
    event_time: datetime
    event_type: str  # "activate" or "deactivate"
    state: str  # "on" or "off"
    value: float | None = None


@dataclass
class ExecutionResult:
    """Result of a schedule execution attempt."""

    schedule_id: int
    actuator_id: int | None
    success: bool
    action: str
    error_message: str | None = None
    retry_count: int = 0
    response_time_ms: int | None = None


class SchedulingService:
    """
    Centralized scheduling service for all device schedules.

    This service provides:
    - CRUD operations for schedules (persisted via repository)
    - Conflict detection between schedules
    - Schedule history/audit logging
    - Automatic schedule generation from plant stages
    - Sun times integration for outdoor units
    - Schedule preview for planning
    - Startup state synchronization
    - Retry logic with exponential backoff

    Architecture:
    - Memory-first pattern: in-memory storage is source of truth for active units
    - Repository persistence for cold-start loading and durability
    - Thread-safe access via locks
    - Sun times service for outdoor scheduling
    """

    MAX_RETRY_ATTEMPTS = 3
    RETRY_BASE_DELAY_MS = 1000

    def __init__(
        self,
        repository: "ScheduleRepository" | None = None,
        sun_times_service: "SunTimesService" | None = None,
    ):
        """
        Initialize scheduling service.

        Args:
            repository: ScheduleRepository for persistence
            sun_times_service: Service for sun times calculations
        """
        self.repository = repository
        self.sun_times_service = sun_times_service

        # ==================== In-Memory Schedule Storage ====================
        # Primary storage: unit_id -> {schedule_id: Schedule}
        # This is the single source of truth for active unit schedules
        self._schedules: dict[int, dict[int, Schedule]] = {}
        self._schedules_lock = threading.Lock()

        # Track which units have been loaded from DB
        self._loaded_units: set[int] = set()

        # Track execution state for startup sync
        self._last_execution_state: dict[int, bool] = {}  # schedule_id -> was_active

        # Track last lux-derived day/night state per unit for hysteresis
        self._last_light_sensor_state: dict[int, bool] = {}
        self._light_state_lock = threading.Lock()

        # Optional unified scheduler for interval task registration
        self._scheduler: "UnifiedScheduler" | None = None

        logger.info("SchedulingService initialized with memory-first storage")

    def set_scheduler(self, scheduler: "UnifiedScheduler") -> None:
        """Attach a UnifiedScheduler for interval task registration."""
        self._scheduler = scheduler
        logger.info("SchedulingService bound to UnifiedScheduler")

    def register_interval_task(
        self,
        *,
        task_name: str,
        func: Callable[[], Any],
        interval_seconds: int,
        job_id: str,
        namespace: str | None = None,
        start_immediately: bool = False,
    ) -> None:
        """Register an interval task with the unified scheduler."""
        if not self._scheduler:
            logger.warning("No unified scheduler available, skipping task %s", task_name)
            return

        self._scheduler.register_task(task_name, func)
        self._scheduler.schedule_interval(
            task_name=task_name,
            interval_seconds=interval_seconds,
            job_id=job_id,
            namespace=namespace,
            start_immediately=start_immediately,
        )

    # ==================== In-Memory Schedule Management ====================

    def _get_unit_schedules(self, unit_id: int) -> dict[int, Schedule]:
        """
        Get or initialize schedule collection for a unit.

        Thread-safe access to the unit's schedule dictionary.

        Args:
            unit_id: Unit identifier

        Returns:
            Dictionary of schedule_id -> Schedule for the unit
        """
        with self._schedules_lock:
            if unit_id not in self._schedules:
                self._schedules[unit_id] = {}
            return self._schedules[unit_id]

    def _add_schedule_to_memory(self, schedule: Schedule) -> None:
        """
        Add schedule to in-memory collection.

        Thread-safe insertion into the unit's schedule dictionary.

        Args:
            schedule: Schedule instance to add
        """
        if not schedule.schedule_id:
            logger.warning("Cannot add schedule without ID to memory")
            return

        with self._schedules_lock:
            unit_id = schedule.unit_id
            if unit_id not in self._schedules:
                self._schedules[unit_id] = {}
            self._schedules[unit_id][schedule.schedule_id] = schedule
            logger.debug(
                "Added schedule %s (%s) to memory for unit %s",
                schedule.schedule_id,
                schedule.name,
                unit_id,
            )

    def _remove_schedule_from_memory(self, unit_id: int, schedule_id: int) -> Schedule | None:
        """
        Remove schedule from in-memory collection.

        Thread-safe removal from the unit's schedule dictionary.

        Args:
            unit_id: Unit identifier
            schedule_id: Schedule identifier to remove

        Returns:
            Removed Schedule or None if not found
        """
        with self._schedules_lock:
            unit_schedules = self._schedules.get(unit_id, {})
            removed = unit_schedules.pop(schedule_id, None)
            if removed:
                logger.debug("Removed schedule %s from memory for unit %s", schedule_id, unit_id)
            return removed

    def _update_schedule_in_memory(self, schedule: Schedule) -> bool:
        """
        Update schedule in in-memory collection.

        Thread-safe update in the unit's schedule dictionary.

        Args:
            schedule: Schedule with updated values

        Returns:
            True if updated, False if not found
        """
        if not schedule.schedule_id:
            return False

        with self._schedules_lock:
            unit_schedules = self._schedules.get(schedule.unit_id, {})
            if schedule.schedule_id not in unit_schedules:
                return False
            unit_schedules[schedule.schedule_id] = schedule
            logger.debug("Updated schedule %s in memory for unit %s", schedule.schedule_id, schedule.unit_id)
            return True

    def get_schedule_from_memory(self, unit_id: int, schedule_id: int) -> Schedule | None:
        """
        Get schedule from in-memory collection (fast path).

        Thread-safe read from the unit's schedule dictionary.

        Args:
            unit_id: Unit identifier
            schedule_id: Schedule identifier

        Returns:
            Schedule or None if not found in memory
        """
        with self._schedules_lock:
            unit_schedules = self._schedules.get(unit_id, {})
            return unit_schedules.get(schedule_id)

    def get_schedules_for_unit_from_memory(self, unit_id: int) -> list[Schedule]:
        """
        Get all schedules for a unit from memory.

        Thread-safe read of all schedules in a unit.

        Args:
            unit_id: Unit identifier

        Returns:
            List of Schedule objects (empty if unit not loaded)
        """
        with self._schedules_lock:
            unit_schedules = self._schedules.get(unit_id, {})
            return list(unit_schedules.values())

    def clear_unit_schedules(self, unit_id: int) -> None:
        """
        Clear all schedules for a unit from memory.

        Called when a unit is stopped or deleted.

        Args:
            unit_id: Unit identifier
        """
        with self._schedules_lock:
            removed_count = len(self._schedules.pop(unit_id, {}))
            self._loaded_units.discard(unit_id)
            if removed_count > 0:
                logger.debug("Cleared %d schedules from memory for unit %s", removed_count, unit_id)

    def is_unit_loaded(self, unit_id: int) -> bool:
        """
        Check if schedules for a unit are loaded in memory.

        Args:
            unit_id: Unit identifier

        Returns:
            True if unit has been loaded (even if no schedules)
        """
        with self._schedules_lock:
            return unit_id in self._loaded_units

    def list_schedules(
        self,
        unit_id: int,
        device_type: str | None = None,
        enabled_only: bool = False,
    ) -> list[Schedule]:
        """
        List all schedules for a unit (alias for get_schedules_for_unit).

        Consistent API naming with PlantService.list_plants().
        Memory-first: returns from memory if loaded, falls back to DB.

        Args:
            unit_id: Growth unit ID
            device_type: Optional filter by device type
            enabled_only: Only return enabled schedules

        Returns:
            List of Schedule objects
        """
        return self.get_schedules_for_unit(unit_id, device_type, enabled_only)

    def load_schedules_for_unit(self, unit_id: int) -> int:
        """
        Load all schedules for a unit from database into memory.

        Called by GrowthService when starting a unit runtime.
        Uses memory-first pattern: clears existing and reloads from DB.

        Args:
            unit_id: Unit identifier

        Returns:
            Number of schedules loaded
        """
        if not self.repository:
            logger.debug("No repository, cannot load schedules for unit %s", unit_id)
            with self._schedules_lock:
                self._loaded_units.add(unit_id)
            return 0

        try:
            schedules = self.repository.get_by_unit(unit_id)
            with self._schedules_lock:
                self._schedules[unit_id] = {}
                for schedule in schedules:
                    if schedule.schedule_id:
                        self._schedules[unit_id][schedule.schedule_id] = schedule
                self._loaded_units.add(unit_id)

            logger.info("Loaded %d schedules for unit %s", len(schedules), unit_id)
            return len(schedules)

        except Exception as e:
            logger.error("Failed to load schedules for unit %s: %s", unit_id, e)
            with self._schedules_lock:
                self._loaded_units.discard(unit_id)
            return 0

    # ==================== CRUD Operations (Memory-First + Persist) ====================

    def create_schedule(
        self,
        schedule: Schedule,
        check_conflicts: bool = True,
        source: str = "user",
        user_id: int | None = None,
    ) -> Schedule | None:
        """
        Create a new schedule and persist via repository.

        Args:
            schedule: Schedule to create
            check_conflicts: Whether to check for conflicts first
            source: Source of the change (user, system, auto)
            user_id: User making the change

        Returns:
            Created schedule with ID, or None on failure
        """
        if not self.repository:
            logger.warning("No repository configured, cannot persist schedule")
            return None

        if not schedule.validate():
            logger.error(f"Invalid schedule for {schedule.device_type}")
            return None

        # Check for conflicts if requested
        if check_conflicts:
            conflicts = self.detect_conflicts(schedule)
            if conflicts:
                logger.warning(f"Schedule conflicts detected for {schedule.device_type}: {len(conflicts)} conflicts")
                # Log conflicts but don't block creation - priority resolves them
                for conflict in conflicts:
                    logger.debug(
                        f"  Conflict with schedule {conflict.schedule_b.schedule_id}: "
                        f"{conflict.overlap_start}-{conflict.overlap_end}"
                    )

        try:
            created = self.repository.create(schedule)
            if created:
                # Memory-first: add to memory immediately
                self._add_schedule_to_memory(created)
                self._log_history(
                    created,
                    ScheduleAction.CREATED,
                    after_state=created.to_dict(),
                    source=source,
                    user_id=user_id,
                )
                logger.info(
                    f"Created schedule '{created.name}' (ID={created.schedule_id}) "
                    f"for {created.device_type} on unit {created.unit_id}"
                )
            return created
        except Exception as e:
            logger.error(f"Failed to create schedule: {e}", exc_info=True)
            return None

    def get_schedule(self, schedule_id: int, unit_id: int | None = None) -> Schedule | None:
        """
        Get a schedule by ID.

        Memory-first: checks memory if unit_id provided, falls back to DB.

        Args:
            schedule_id: Schedule identifier
            unit_id: Optional unit_id for memory lookup (faster)

        Returns:
            Schedule or None if not found
        """
        # Memory-first if unit_id provided and unit is loaded
        if unit_id is not None and self.is_unit_loaded(unit_id):
            schedule = self.get_schedule_from_memory(unit_id, schedule_id)
            if schedule:
                return schedule

        # Fall back to repository
        if not self.repository:
            return None
        try:
            return self.repository.get_by_id(schedule_id)
        except Exception as e:
            logger.error(f"Failed to get schedule {schedule_id}: {e}")
            return None

    def get_schedules_for_unit(
        self,
        unit_id: int,
        device_type: str | None = None,
        enabled_only: bool = False,
    ) -> list[Schedule]:
        """
        Get all schedules for a growth unit.

        Memory-first: returns from memory if unit loaded, falls back to DB.

        Args:
            unit_id: Growth unit ID
            device_type: Optional filter by device type
            enabled_only: Only return enabled schedules

        Returns:
            List of schedules
        """
        # Memory-first: check if unit is loaded in memory
        if self.is_unit_loaded(unit_id):
            schedules = self.get_schedules_for_unit_from_memory(unit_id)
            if device_type:
                schedules = [s for s in schedules if s.device_type == device_type]
            if enabled_only:
                schedules = [s for s in schedules if s.enabled]
            return schedules

        # Fallback to repository for units not loaded in memory
        if not self.repository:
            return []

        try:
            if device_type:
                schedules = self.repository.get_by_device_type(unit_id, device_type)
            elif enabled_only:
                schedules = self.repository.get_enabled_schedules(unit_id)
            else:
                schedules = self.repository.get_by_unit(unit_id)

            return schedules
        except Exception as e:
            logger.error(f"Failed to get schedules for unit {unit_id}: {e}")
            return []

    def get_schedules_for_actuator(self, actuator_id: int) -> list[Schedule]:
        """
        Get all schedules for a specific actuator.

        Args:
            actuator_id: Actuator identifier

        Returns:
            List of schedules linked to this actuator
        """
        # Memory-first: scan in-memory schedules if available
        matches: list[Schedule] = []
        with self._schedules_lock:
            for unit_schedules in self._schedules.values():
                for schedule in unit_schedules.values():
                    if schedule.actuator_id == actuator_id:
                        matches.append(schedule)
        if matches:
            return matches

        if not self.repository:
            return []
        try:
            return self.repository.get_by_actuator(actuator_id)
        except Exception as e:
            logger.error(f"Failed to get schedules for actuator {actuator_id}: {e}")
            return []

    def update_schedule(
        self,
        schedule: Schedule,
        source: str = "user",
        user_id: int | None = None,
        reason: str | None = None,
    ) -> bool:
        """
        Update an existing schedule.

        Memory-first: updates memory immediately, then persists to DB.

        Args:
            schedule: Schedule with updated values
            source: Source of the change
            user_id: User making the change
            reason: Optional reason for the change

        Returns:
            True if updated successfully
        """
        if not schedule.schedule_id:
            logger.error("Cannot update schedule without ID")
            return False

        if not schedule.validate():
            logger.error(f"Invalid schedule data for {schedule.device_type}")
            return False

        before_schedule = None
        if self.repository:
            try:
                before_schedule = self.repository.get_by_id(schedule.schedule_id)
            except Exception as e:
                logger.warning(
                    "Failed to fetch schedule %s before update: %s",
                    schedule.schedule_id,
                    e,
                )
        if not before_schedule:
            before_schedule = self.get_schedule_from_memory(schedule.unit_id, schedule.schedule_id)
        before_snapshot = self._clone_schedule(before_schedule)
        before_state = before_snapshot.to_dict() if before_snapshot else None

        in_memory_before = self.get_schedule_from_memory(schedule.unit_id, schedule.schedule_id)
        memory_was_updated = bool(in_memory_before) and self._update_schedule_in_memory(schedule)

        # Persist to repository
        if not self.repository:
            logger.warning("No repository configured, schedule updated in memory only")
            return True

        try:
            updated = self.repository.update(schedule)
            if updated:
                self._add_schedule_to_memory(updated)
                self._log_history(
                    updated,
                    ScheduleAction.UPDATED,
                    before_state=before_state,
                    after_state=updated.to_dict(),
                    source=source,
                    user_id=user_id,
                    reason=reason,
                )
                logger.info(f"Updated schedule {schedule.schedule_id}")
                return True

            if memory_was_updated and before_snapshot:
                self._update_schedule_in_memory(before_snapshot)
            return False
        except Exception as e:
            logger.error(f"Failed to update schedule {schedule.schedule_id}: {e}")
            if memory_was_updated and before_snapshot:
                self._update_schedule_in_memory(before_snapshot)
            return False

    def delete_schedule(
        self,
        schedule_id: int,
        source: str = "user",
        user_id: int | None = None,
        reason: str | None = None,
    ) -> bool:
        """
        Delete a schedule permanently.

        Memory-first: removes from memory immediately, then deletes from DB.

        Args:
            schedule_id: Schedule to delete
            source: Source of the change
            user_id: User making the change
            reason: Optional reason for deletion

        Returns:
            True if deleted successfully
        """
        # Get schedule first for history logging and unit_id (memory first)
        schedule = None
        unit_id = None

        # Try to find schedule in memory first
        with self._schedules_lock:
            for uid, unit_schedules in self._schedules.items():
                if schedule_id in unit_schedules:
                    schedule = unit_schedules[schedule_id]
                    unit_id = uid
                    break

        # Fall back to repository if not in memory
        if not schedule and self.repository:
            try:
                schedule = self.repository.get_by_id(schedule_id)
            except Exception as e:
                logger.warning("Failed to fetch schedule %s for delete: %s", schedule_id, e)
            if schedule:
                unit_id = schedule.unit_id

        before_state = schedule.to_dict() if schedule else None

        removed_from_memory: Schedule | None = None
        # Memory-first: remove from memory immediately
        if unit_id is not None:
            removed_from_memory = self._remove_schedule_from_memory(unit_id, schedule_id)

        # Persist deletion to repository
        if not self.repository:
            logger.warning("No repository configured, schedule removed from memory only")
            return True

        try:
            success = self.repository.delete(schedule_id)
            if success and schedule:
                self._log_history(
                    schedule,
                    ScheduleAction.DELETED,
                    before_state=before_state,
                    source=source,
                    user_id=user_id,
                    reason=reason,
                )
                logger.info(f"Deleted schedule {schedule_id}")
                return True

            if removed_from_memory:
                self._add_schedule_to_memory(removed_from_memory)
            return success
        except Exception as e:
            logger.error(f"Failed to delete schedule {schedule_id}: {e}")
            if removed_from_memory:
                self._add_schedule_to_memory(removed_from_memory)
            return False

    def delete_schedules_for_unit(self, unit_id: int) -> int:
        """
        Delete all schedules for a unit.

        Memory-first: clears memory immediately, then deletes from DB.

        Args:
            unit_id: Unit to delete schedules for

        Returns:
            Number of deleted schedules
        """
        # Memory-first: clear from memory first
        self.clear_unit_schedules(unit_id)

        if not self.repository:
            logger.warning("No repository configured, schedules cleared from memory only")
            return 0
        try:
            count = self.repository.delete_by_unit(unit_id)
            logger.info(f"Deleted {count} schedules for unit {unit_id}")
            return count
        except Exception as e:
            logger.error(f"Failed to delete schedules for unit {unit_id}: {e}")
            return 0

    def set_schedule_enabled(
        self,
        schedule_id: int,
        enabled: bool,
        source: str = "user",
        user_id: int | None = None,
    ) -> bool:
        """
        Enable or disable a schedule without deleting it.

        Memory-first: updates memory immediately, then persists to DB.

        Args:
            schedule_id: Schedule to modify
            enabled: New enabled state
            source: Source of the change
            user_id: User making the change

        Returns:
            True if updated successfully
        """
        # Find schedule in memory first
        schedule = None
        unit_id = None
        with self._schedules_lock:
            for uid, unit_schedules in self._schedules.items():
                if schedule_id in unit_schedules:
                    schedule = unit_schedules[schedule_id]
                    unit_id = uid
                    break

        # Fall back to repository if not in memory
        if not schedule and self.repository:
            try:
                schedule = self.repository.get_by_id(schedule_id)
            except Exception as e:
                logger.warning("Failed to fetch schedule %s for enable toggle: %s", schedule_id, e)
            if schedule:
                unit_id = schedule.unit_id

        if not schedule:
            logger.warning(f"Schedule {schedule_id} not found")
            return False

        previous_enabled = schedule.enabled
        memory_schedule: Schedule | None = None
        # Memory-first: update in memory if loaded
        if unit_id is not None and self.is_unit_loaded(unit_id):
            with self._schedules_lock:
                if unit_id in self._schedules and schedule_id in self._schedules[unit_id]:
                    memory_schedule = self._schedules[unit_id][schedule_id]
                    previous_enabled = memory_schedule.enabled
                    memory_schedule.enabled = enabled
                    schedule.enabled = enabled

        # Persist to repository
        if not self.repository:
            logger.warning("No repository configured, schedule enabled state updated in memory only")
            return True

        try:
            success = self.repository.set_enabled(schedule_id, enabled)
            if success:
                action = ScheduleAction.ENABLED if enabled else ScheduleAction.DISABLED
                self._log_history(
                    schedule,
                    action,
                    source=source,
                    user_id=user_id,
                )
                logger.info(f"Schedule {schedule_id} {'enabled' if enabled else 'disabled'}")
                return True

            if memory_schedule is not None:
                memory_schedule.enabled = previous_enabled
            schedule.enabled = previous_enabled
            return success
        except Exception as e:
            logger.error(f"Failed to set schedule {schedule_id} enabled={enabled}: {e}")
            if memory_schedule is not None:
                memory_schedule.enabled = previous_enabled
            schedule.enabled = previous_enabled
            return False

    # ==================== Conflict Detection ====================

    def detect_conflicts(
        self,
        schedule: Schedule,
        exclude_schedule_id: int | None = None,
    ) -> list[ScheduleConflict]:
        """
        Detect time conflicts between a schedule and existing schedules.

        Args:
            schedule: Schedule to check for conflicts
            exclude_schedule_id: Schedule ID to exclude (for updates)

        Returns:
            List of detected conflicts
        """
        conflicts = []

        existing = self.get_schedules_for_unit(
            schedule.unit_id,
            device_type=schedule.device_type,
            enabled_only=True,
        )

        for other in existing:
            if exclude_schedule_id and other.schedule_id == exclude_schedule_id:
                continue
            if other.schedule_id == schedule.schedule_id:
                continue

            conflict = self._check_overlap(schedule, other)
            if conflict:
                conflicts.append(conflict)

        return conflicts

    def _check_overlap(
        self,
        schedule_a: Schedule,
        schedule_b: Schedule,
    ) -> ScheduleConflict | None:
        """Check if two schedules overlap in time."""
        segments_a = self._expand_schedule_segments(schedule_a)
        segments_b = self._expand_schedule_segments(schedule_b)

        if not segments_a or not segments_b:
            return None

        overlap_days: list[int] = []
        overlap_start = None
        overlap_end = None

        for day_a, start_a, end_a in segments_a:
            for day_b, start_b, end_b in segments_b:
                if day_a != day_b:
                    continue
                start = max(start_a, start_b)
                end = min(end_a, end_b)
                if start < end:
                    overlap_days.append(day_a)
                    if overlap_start is None:
                        overlap_start = start
                        overlap_end = end

        if not overlap_days or overlap_start is None or overlap_end is None:
            return None

        return ScheduleConflict(
            schedule_a=schedule_a,
            schedule_b=schedule_b,
            overlap_start=self._minutes_to_time(overlap_start % (24 * 60)),
            overlap_end=self._minutes_to_time(overlap_end % (24 * 60)),
            conflicting_days=sorted(set(overlap_days)),
            resolution="higher_priority_wins" if schedule_a.priority != schedule_b.priority else "first_created_wins",
        )

    def _expand_schedule_segments(self, schedule: Schedule) -> list[tuple[int, int, int]]:
        """Expand schedule into day-specific segments for overlap detection."""
        if not schedule.days_of_week:
            return []

        start = self._time_to_minutes(schedule.start_time)
        end = self._time_to_minutes(schedule.end_time)
        segments: list[tuple[int, int, int]] = []

        for day in schedule.days_of_week:
            if start == end:
                segments.append((day, 0, 24 * 60))
                continue

            if end > start:
                segments.append((day, start, end))
                continue

            segments.append((day, start, 24 * 60))
            next_day = (day + 1) % 7
            segments.append((next_day, 0, end))

        return segments

    def _time_to_minutes(self, time_str: str) -> int:
        """Convert HH:MM to minutes since midnight."""
        parts = time_str.split(":")
        return int(parts[0]) * 60 + int(parts[1])

    def _minutes_to_time(self, minutes: int) -> str:
        """Convert minutes since midnight to HH:MM."""
        h = (minutes // 60) % 24
        m = minutes % 60
        return f"{h:02d}:{m:02d}"

    @staticmethod
    def _clone_schedule(schedule: Schedule | None) -> Schedule | None:
        """Create a detached copy of a schedule object."""
        if schedule is None:
            return None
        return Schedule.from_dict(schedule.to_dict())

    @staticmethod
    def _schedule_order_key(schedule: Schedule) -> tuple[int, datetime, int]:
        """Sort key: higher priority first, then oldest creation, then smallest ID."""
        created_at = schedule.created_at if isinstance(schedule.created_at, datetime) else datetime.min
        schedule_id = schedule.schedule_id if schedule.schedule_id is not None else (2**31 - 1)
        return (-schedule.priority, created_at, schedule_id)

    def select_effective_schedule(self, schedules: list[Schedule]) -> Schedule | None:
        """Select the highest-priority schedule from an already filtered list."""
        if not schedules:
            return None
        return sorted(schedules, key=self._schedule_order_key)[0]

    # ==================== Schedule Evaluation ====================

    def is_schedule_active(
        self,
        schedule: Schedule,
        unit_id: int,
        check_time: datetime | None = None,
        lux_reading: float | None = None,
        *,
        unit_timezone: str | None = None,
    ) -> bool:
        """
        Determine if a specific schedule is active at a given time.

        For non-light schedules (or light schedules without photoperiod), this
        delegates to Schedule.is_active_at(). For photoperiod schedules, this
        applies source-aware logic (schedule/sensor/hybrid/sun_api).
        """
        if not schedule.enabled:
            return False

        schedule_active = schedule.is_active_at(check_time, timezone=unit_timezone)
        if schedule.device_type != "light" or not schedule.photoperiod:
            return schedule_active

        pp = schedule.photoperiod
        if pp.source == PhotoperiodSource.SCHEDULE:
            return schedule_active

        if pp.source == PhotoperiodSource.SENSOR and lux_reading is not None:
            is_day = self._evaluate_lux_state(
                unit_id,
                lux_reading,
                pp.sensor_threshold,
                pp.sensor_tolerance,
            )
            if is_day is None:
                return schedule_active
            if schedule_active and not is_day:
                return True
            return False

        if pp.source == PhotoperiodSource.HYBRID and lux_reading is not None:
            if not schedule_active:
                return False
            if pp.prefer_sensor:
                is_day = self._evaluate_lux_state(
                    unit_id,
                    lux_reading,
                    pp.sensor_threshold,
                    pp.sensor_tolerance,
                )
                if is_day is None:
                    return schedule_active
                return not is_day
            return True

        if pp.source == PhotoperiodSource.SUN_API:
            return self._evaluate_sun_based_schedule(
                schedule,
                check_time,
                unit_timezone=unit_timezone,
            )

        return schedule_active

    def is_device_active(
        self,
        unit_id: int,
        device_type: str,
        check_time: datetime | None = None,
        *,
        unit_timezone: str | None = None,
    ) -> bool:
        """
        Check if any schedule for device type is currently active.

        Uses priority to resolve conflicts (higher priority wins).

        Args:
            unit_id: Growth unit ID
            device_type: Device type to check
            check_time: Time to evaluate (defaults to now)

        Returns:
            True if device should be ON based on schedules
        """
        schedules = self.get_schedules_for_unit(unit_id, device_type=device_type, enabled_only=True)

        if not schedules:
            return False

        # Sort by priority (higher first)
        schedules.sort(key=lambda s: s.priority, reverse=True)

        # Check each schedule in priority order
        for schedule in schedules:
            if schedule.is_active_at(check_time, timezone=unit_timezone):
                return schedule.state_when_active == ScheduleState.ON

        return False

    def get_active_schedules(
        self,
        unit_id: int,
        check_time: datetime | None = None,
        *,
        unit_timezone: str | None = None,
    ) -> list[Schedule]:
        """
        Get all currently active schedules for a unit.

        Args:
            unit_id: Growth unit ID
            check_time: Time to evaluate (defaults to now)

        Returns:
            List of active schedules
        """
        schedules = self.get_schedules_for_unit(unit_id, enabled_only=True)
        return [s for s in schedules if s.is_active_at(check_time, timezone=unit_timezone)]

    def get_device_value(
        self,
        unit_id: int,
        device_type: str,
        check_time: datetime | None = None,
        *,
        unit_timezone: str | None = None,
    ) -> float | None:
        """
        Get the value (dimmer level) for a device based on active schedules.

        Args:
            unit_id: Growth unit ID
            device_type: Device type
            check_time: Time to evaluate

        Returns:
            Value (0-100) or None if no value specified
        """
        schedules = self.get_schedules_for_unit(unit_id, device_type=device_type, enabled_only=True)

        if not schedules:
            return None

        # Sort by priority
        schedules.sort(key=lambda s: s.priority, reverse=True)

        for schedule in schedules:
            if schedule.is_active_at(check_time, timezone=unit_timezone) and schedule.value is not None:
                return schedule.value

        return None

    # ==================== Light Schedule Helpers ====================

    def get_light_schedule(self, unit_id: int) -> Schedule | None:
        """
        Get the primary light schedule for a unit.

        Returns the highest priority enabled light schedule.

        Args:
            unit_id: Growth unit ID

        Returns:
            Primary light schedule or None
        """
        schedules = self.get_schedules_for_unit(
            unit_id,
            device_type="light",
            enabled_only=True,
        )
        return self.select_effective_schedule(schedules)

    def get_photoperiod_schedule(self, unit_id: int) -> Schedule | None:
        """
        Get the primary photoperiod light schedule for a unit.

        Returns the highest-priority light schedule whose type is photoperiod.
        """
        schedules = self.get_schedules_for_unit(unit_id, device_type="light", enabled_only=False)
        photoperiod_schedules = [s for s in schedules if s.schedule_type == ScheduleType.PHOTOPERIOD]
        return self.select_effective_schedule(photoperiod_schedules)

    def get_light_hours(self, unit_id: int) -> float:
        """
        Calculate total light hours from the light schedule.

        Args:
            unit_id: Growth unit ID

        Returns:
            Light hours per day (0 if no schedule)
        """
        schedule = self.get_light_schedule(unit_id)
        if not schedule:
            return 0.0
        return schedule.duration_hours()

    def is_light_on(
        self,
        unit_id: int,
        check_time: datetime | None = None,
        lux_reading: float | None = None,
        *,
        unit_timezone: str | None = None,
    ) -> bool:
        """
        Determine if light should be ON, considering photoperiod config.

        Args:
            unit_id: Growth unit ID
            check_time: Time to evaluate
            lux_reading: Optional current lux sensor reading

        Returns:
            True if light should be ON
        """
        schedule = self.get_light_schedule(unit_id)
        if not schedule:
            return False

        return self.is_schedule_active(
            schedule=schedule,
            unit_id=unit_id,
            check_time=check_time,
            lux_reading=lux_reading,
            unit_timezone=unit_timezone,
        )

    def _evaluate_lux_state(
        self,
        unit_id: int,
        lux_reading: float | None,
        threshold: float,
        tolerance: float,
    ) -> bool | None:
        """Evaluate day/night state with hysteresis for a unit's lux reading."""
        if lux_reading is None:
            return None

        try:
            lux_value = float(lux_reading)
        except (TypeError, ValueError):
            return None

        try:
            threshold_value = float(threshold)
        except (TypeError, ValueError):
            threshold_value = 0.0

        try:
            tolerance_value = max(0.0, float(tolerance))
        except (TypeError, ValueError):
            tolerance_value = 0.0

        upper = threshold_value + tolerance_value
        lower = threshold_value - tolerance_value

        with self._light_state_lock:
            last_state = self._last_light_sensor_state.get(unit_id)
            if last_state is None:
                is_day = lux_value >= threshold_value
            elif last_state:
                is_day = lux_value >= lower
            else:
                is_day = lux_value >= upper
            self._last_light_sensor_state[unit_id] = is_day

        return is_day

    def _evaluate_sun_based_schedule(
        self,
        schedule: Schedule,
        check_time: datetime | None = None,
        *,
        unit_timezone: str | None = None,
    ) -> bool:
        """Evaluate schedule using sun times API."""
        if not self.sun_times_service:
            logger.warning("Sun times service not configured, falling back to schedule")
            return schedule.is_active_at(check_time, timezone=unit_timezone)

        check_time = Schedule._normalize_check_time(check_time, unit_timezone)

        # Get sun times config
        sun_config = schedule.photoperiod.sun_times if schedule.photoperiod else None
        lat = sun_config.latitude if sun_config else None
        lng = sun_config.longitude if sun_config else None

        return self.sun_times_service.is_daytime(
            check_time=check_time,
            latitude=lat,
            longitude=lng,
            use_civil_twilight=sun_config.use_civil_twilight if sun_config else False,
        )

    # ==================== Schedule Preview ====================

    def preview_schedules(
        self,
        unit_id: int,
        hours_ahead: int = 24,
        device_type: str | None = None,
        *,
        unit_timezone: str | None = None,
    ) -> list[SchedulePreviewEvent]:
        """
        Preview schedule events for the next N hours.

        Args:
            unit_id: Growth unit ID
            hours_ahead: Hours to preview (default 24)
            device_type: Optional filter by device type

        Returns:
            List of upcoming schedule events
        """
        events = []
        tz = Schedule._resolve_timezone(unit_timezone)
        now = datetime.now(tz) if tz else datetime.now()
        end_time = now + timedelta(hours=hours_ahead)

        schedules = self.get_schedules_for_unit(unit_id, device_type=device_type, enabled_only=True)

        for schedule in schedules:
            # Sample at 1-minute intervals
            current = now
            was_active = schedule.is_active_at(now, timezone=unit_timezone)

            while current < end_time:
                current += timedelta(minutes=1)
                is_active = schedule.is_active_at(current, timezone=unit_timezone)

                if is_active and not was_active:
                    events.append(
                        SchedulePreviewEvent(
                            schedule_id=schedule.schedule_id,
                            schedule_name=schedule.name,
                            device_type=schedule.device_type,
                            event_time=current,
                            event_type="activate",
                            state=schedule.state_when_active.value,
                            value=schedule.value,
                        )
                    )
                elif not is_active and was_active:
                    events.append(
                        SchedulePreviewEvent(
                            schedule_id=schedule.schedule_id,
                            schedule_name=schedule.name,
                            device_type=schedule.device_type,
                            event_time=current,
                            event_type="deactivate",
                            state="off",
                            value=None,
                        )
                    )

                was_active = is_active

        # Sort by event time
        events.sort(key=lambda e: e.event_time)
        return events

    # ==================== Auto Schedule from Plant Stages ====================

    def generate_schedules_from_plant(
        self,
        unit_id: int,
        plant_info: dict[str, Any],
        current_stage: str,
        light_actuator_id: int | None = None,
        fan_actuator_id: int | None = None,
    ) -> list[Schedule]:
        """
        Generate schedules automatically from plant growth stage data.

        Reads automation and growth_stages data from plants_info.json
        and creates appropriate schedules for the current stage.

        Args:
            unit_id: Growth unit ID
            plant_info: Plant data from plants_info.json
            current_stage: Current growth stage name
            light_actuator_id: Optional actuator ID for lights
            fan_actuator_id: Optional actuator ID for fans

        Returns:
            List of generated schedules
        """
        generated = []

        # Get automation settings
        automation = plant_info.get("automation", {})
        lighting_schedule = automation.get("lighting_schedule", {})

        # Get stage-specific lighting from automation.lighting_schedule
        stage_key = current_stage.lower()
        stage_lighting = lighting_schedule.get(stage_key, {})

        if not stage_lighting:
            raise ValueError(
                f"No lighting data found for stage '{current_stage}'. Configure plant lighting before auto-generation."
            )

        hours = stage_lighting.get("hours")
        if hours is None:
            hours = stage_lighting.get("hours_per_day")
        intensity = stage_lighting.get("intensity")

        if hours is None or intensity is None:
            raise ValueError(f"Lighting data for stage '{current_stage}' is missing hours or intensity.")

        try:
            hours_value = float(hours)
            intensity_value = float(intensity)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Lighting data for stage '{current_stage}' must be numeric.") from exc

        # Calculate start/end times (centered on noon)
        half_hours = hours_value / 2
        start_minutes = int((12 - half_hours) * 60)
        end_minutes = int((12 + half_hours) * 60)

        start_time = f"{start_minutes // 60:02d}:{start_minutes % 60:02d}"
        end_time = f"{end_minutes // 60:02d}:{end_minutes % 60:02d}"

        light_schedule = Schedule(
            unit_id=unit_id,
            name=f"{current_stage} Light Schedule (Auto)",
            device_type="light",
            actuator_id=light_actuator_id,
            schedule_type=ScheduleType.PHOTOPERIOD,
            start_time=start_time,
            end_time=end_time,
            enabled=True,
            value=float(intensity_value) if intensity_value < 100 else None,
            metadata={
                "auto_generated": True,
                "plant_stage": current_stage,
                "source": "plant_info",
            },
        )
        generated.append(light_schedule)

        # Create environmental controls if defined
        env_controls = automation.get("environmental_controls", {})
        if env_controls and fan_actuator_id:
            fan_schedule = Schedule(
                unit_id=unit_id,
                name=f"{current_stage} Ventilation (Auto)",
                device_type="fan",
                actuator_id=fan_actuator_id,
                schedule_type=ScheduleType.SIMPLE,
                start_time="06:00",
                end_time="22:00",
                enabled=True,
                metadata={
                    "auto_generated": True,
                    "plant_stage": current_stage,
                },
            )
            generated.append(fan_schedule)

        return generated

    def apply_plant_stage_schedules(
        self,
        unit_id: int,
        plant_info: dict[str, Any],
        current_stage: str,
        light_actuator_id: int | None = None,
        fan_actuator_id: int | None = None,
        replace_existing: bool = True,
    ) -> int:
        """
        Apply auto-generated schedules from plant stage to a unit.

        Args:
            unit_id: Growth unit ID
            plant_info: Plant data from plants_info.json
            current_stage: Current growth stage name
            light_actuator_id: Optional actuator ID for lights
            fan_actuator_id: Optional actuator ID for fans
            replace_existing: If True, remove existing auto-generated schedules

        Returns:
            Number of schedules created
        """
        if replace_existing:
            # Remove existing auto-generated schedules
            existing = self.get_schedules_for_unit(unit_id)
            for schedule in existing:
                if schedule.metadata.get("auto_generated"):
                    self.delete_schedule(
                        schedule.schedule_id,
                        source="system",
                        reason=f"Replaced by new stage: {current_stage}",
                    )

        # Generate new schedules
        try:
            new_schedules = self.generate_schedules_from_plant(
                unit_id=unit_id,
                plant_info=plant_info,
                current_stage=current_stage,
                light_actuator_id=light_actuator_id,
                fan_actuator_id=fan_actuator_id,
            )
        except ValueError as exc:
            logger.error(
                "Failed to generate schedules for unit %s stage '%s': %s",
                unit_id,
                current_stage,
                exc,
            )
            raise

        # Create each schedule
        created_count = 0
        for schedule in new_schedules:
            created = self.create_schedule(
                schedule,
                source="system",
                check_conflicts=True,
            )
            if created:
                created_count += 1

        logger.info(f"Applied {created_count} auto-generated schedules for unit {unit_id} stage '{current_stage}'")
        return created_count

    # ==================== Startup State Sync ====================

    def sync_actuator_states_at_startup(
        self,
        unit_ids: list[int],
        actuator_manager: Any,
        *,
        unit_timezones: dict[int, str] | None = None,
    ) -> dict[str, Any]:
        """
        Synchronize actuator states with active schedules at startup.

        Ensures actuators are in the correct state when system starts,
        rather than waiting for the next schedule check.

        Args:
            unit_ids: List of unit IDs to sync
            actuator_manager: ActuatorManager instance

        Returns:
            Summary of sync results
        """
        results = {
            "units_synced": 0,
            "actuators_synced": 0,
            "errors": [],
        }

        for unit_id in unit_ids:
            try:
                unit_timezone = unit_timezones.get(unit_id) if unit_timezones else None
                tz = Schedule._resolve_timezone(unit_timezone)
                now = datetime.now(tz) if tz else datetime.now()
                schedules = self.get_schedules_for_unit(unit_id, enabled_only=True)

                active_by_schedule: dict[int, bool] = {}
                by_actuator: dict[int, list[Schedule]] = {}
                for schedule in schedules:
                    if schedule.device_type == "light" and schedule.photoperiod:
                        if schedule.photoperiod.source == PhotoperiodSource.SUN_API:
                            is_active = self._evaluate_sun_based_schedule(
                                schedule,
                                now,
                                unit_timezone=unit_timezone,
                            )
                        else:
                            is_active = schedule.is_active_at(now, timezone=unit_timezone)
                    else:
                        is_active = schedule.is_active_at(now, timezone=unit_timezone)

                    if schedule.schedule_id is not None:
                        active_by_schedule[schedule.schedule_id] = is_active
                        self._last_execution_state[schedule.schedule_id] = is_active
                    if schedule.actuator_id:
                        by_actuator.setdefault(schedule.actuator_id, []).append(schedule)

                for actuator_id, actuator_schedules in by_actuator.items():
                    active_schedules: list[Schedule] = []
                    for schedule in actuator_schedules:
                        if schedule.schedule_id is None:
                            continue
                        if active_by_schedule.get(schedule.schedule_id):
                            active_schedules.append(schedule)

                    selected = self.select_effective_schedule(active_schedules)
                    try:
                        if selected:
                            if selected.value is not None:
                                actuator_manager.set_level(actuator_id, float(selected.value))
                            elif selected.state_when_active == ScheduleState.ON:
                                actuator_manager.turn_on(actuator_id)
                            else:
                                actuator_manager.turn_off(actuator_id)
                        else:
                            actuator_manager.turn_off(actuator_id)
                        results["actuators_synced"] += 1
                    except Exception as e:
                        error_msg = f"Actuator {actuator_id}: {e}"
                        results["errors"].append(error_msg)
                        logger.error("Startup sync failed: %s", error_msg)

                results["units_synced"] += 1

            except Exception as e:
                results["errors"].append(f"Unit {unit_id}: {e}")
                logger.error(f"Startup sync failed for unit {unit_id}: {e}")

        logger.info(
            f"Startup sync: {results['units_synced']} units, "
            f"{results['actuators_synced']} actuators, "
            f"{len(results['errors'])} errors"
        )
        return results

    # ==================== Retry Logic ====================

    def execute_with_retry(
        self,
        schedule: Schedule,
        activate: bool,
        actuator_manager: Any | None = None,
    ) -> ExecutionResult:
        """
        Execute a schedule action with retry logic.

        Uses exponential backoff for retries.

        Args:
            schedule: Schedule being executed
            activate: True to activate, False to deactivate
            actuator_manager: Actuator control service (turn_on/turn_off/set_level)

        Returns:
            ExecutionResult with success/failure details
        """
        import time as time_module

        action = "activate" if activate else "deactivate"
        result = ExecutionResult(
            schedule_id=schedule.schedule_id,
            actuator_id=schedule.actuator_id,
            success=False,
            action=action,
        )

        if not schedule.actuator_id:
            result.success = True
            return result

        if actuator_manager is None:
            result.error_message = "Actuator manager is required for schedule execution"
            logger.error("Cannot execute schedule %s: %s", schedule.schedule_id, result.error_message)
            self.record_execution(
                schedule=schedule,
                action=action,
                success=False,
                error_message=result.error_message,
                retry_count=result.retry_count,
                response_time_ms=result.response_time_ms,
                source="system",
            )
            return result

        for attempt in range(self.MAX_RETRY_ATTEMPTS):
            result.retry_count = attempt
            start_time = time_module.time()

            try:
                if activate:
                    if schedule.value is not None:
                        actuator_manager.set_level(schedule.actuator_id, float(schedule.value))
                    elif schedule.state_when_active == ScheduleState.ON:
                        actuator_manager.turn_on(schedule.actuator_id)
                    else:
                        actuator_manager.turn_off(schedule.actuator_id)
                else:
                    actuator_manager.turn_off(schedule.actuator_id)

                result.success = True
                result.response_time_ms = int((time_module.time() - start_time) * 1000)

                self.record_execution(
                    schedule=schedule,
                    action=action,
                    success=True,
                    error_message=None,
                    retry_count=result.retry_count,
                    response_time_ms=result.response_time_ms,
                    source="system",
                )
                return result

            except Exception as e:
                result.error_message = str(e)
                result.response_time_ms = int((time_module.time() - start_time) * 1000)

                logger.warning(f"Schedule execution failed (attempt {attempt + 1}/{self.MAX_RETRY_ATTEMPTS}): {e}")

                if attempt < self.MAX_RETRY_ATTEMPTS - 1:
                    delay_ms = self.RETRY_BASE_DELAY_MS * (2**attempt)
                    time_module.sleep(delay_ms / 1000.0)

        # All retries failed
        logger.error(
            f"Schedule {schedule.schedule_id} execution failed after "
            f"{self.MAX_RETRY_ATTEMPTS} attempts: {result.error_message}"
        )
        self.record_execution(
            schedule=schedule,
            action=action,
            success=False,
            error_message=result.error_message,
            retry_count=result.retry_count,
            response_time_ms=result.response_time_ms,
            source="system",
        )

        return result

    # ==================== History Logging ====================

    def record_execution(
        self,
        *,
        schedule: Schedule,
        action: str,
        success: bool,
        error_message: str | None = None,
        retry_count: int = 0,
        response_time_ms: int | None = None,
        source: str = "system",
    ) -> None:
        """Record a schedule transition in execution log and history."""
        result = ExecutionResult(
            schedule_id=schedule.schedule_id or 0,
            actuator_id=schedule.actuator_id,
            success=success,
            action=action,
            error_message=error_message,
            retry_count=retry_count,
            response_time_ms=response_time_ms,
        )
        self._log_execution(result)
        if success:
            self._log_history(
                schedule,
                ScheduleAction.EXECUTED,
                source=source,
                reason=action,
            )
        else:
            self._log_history(
                schedule,
                ScheduleAction.FAILED,
                source=source,
                reason=error_message or action,
            )

    def _log_history(
        self,
        schedule: Schedule,
        action: ScheduleAction,
        before_state: dict | None = None,
        after_state: dict | None = None,
        source: str = "user",
        user_id: int | None = None,
        reason: str | None = None,
    ):
        """Log schedule change to history table."""
        if not self.repository:
            return

        try:
            # Calculate changed fields
            changed_fields = []
            if before_state and after_state:
                for key in after_state:
                    if before_state.get(key) != after_state.get(key):
                        changed_fields.append(key)

            self.repository.log_history(
                schedule_id=schedule.schedule_id or 0,
                unit_id=schedule.unit_id,
                action=action.value,
                device_type=schedule.device_type,
                before_state=json.dumps(before_state) if before_state else None,
                after_state=json.dumps(after_state) if after_state else None,
                changed_fields=json.dumps(changed_fields) if changed_fields else None,
                source=source,
                user_id=user_id,
                reason=reason,
            )
        except Exception as e:
            logger.debug(f"Failed to log schedule history: {e}")

    def _log_execution(self, result: ExecutionResult):
        """Log schedule execution to execution log table."""
        if not self.repository:
            return

        try:
            self.repository.log_execution(
                schedule_id=result.schedule_id,
                actuator_id=result.actuator_id,
                action=result.action,
                success=result.success,
                error_message=result.error_message,
                retry_count=result.retry_count,
                response_time_ms=result.response_time_ms,
            )
        except Exception as e:
            logger.debug(f"Failed to log schedule execution: {e}")

    def get_schedule_history(
        self,
        schedule_id: int | None = None,
        unit_id: int | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Get schedule history/audit log."""
        if not self.repository:
            return []
        try:
            return self.repository.get_history(
                schedule_id=schedule_id,
                unit_id=unit_id,
                limit=limit,
            )
        except Exception as e:
            logger.error(f"Failed to get schedule history: {e}")
            return []

    def get_execution_log(
        self,
        schedule_id: int | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Get schedule execution log."""
        if not self.repository:
            return []
        try:
            return self.repository.get_execution_log(
                schedule_id=schedule_id,
                limit=limit,
            )
        except Exception as e:
            logger.error(f"Failed to get execution log: {e}")
            return []

    # ==================== Utility Methods ====================

    def get_last_execution_state(self, schedule_id: int) -> bool | None:
        """Get the last known execution state for a schedule."""
        return self._last_execution_state.get(schedule_id)

    def set_last_execution_state(self, schedule_id: int, was_active: bool):
        """Set the last known execution state for a schedule."""
        self._last_execution_state[schedule_id] = was_active

    def get_schedule_summary(self, unit_id: int) -> dict[str, Any]:
        """
        Get a summary of all schedules for a unit.

        Returns:
            Summary with counts and light info
        """
        schedules = self.get_schedules_for_unit(unit_id)
        enabled = [s for s in schedules if s.enabled]

        by_device = {}
        for s in schedules:
            if s.device_type not in by_device:
                by_device[s.device_type] = {"total": 0, "enabled": 0}
            by_device[s.device_type]["total"] += 1
            if s.enabled:
                by_device[s.device_type]["enabled"] += 1

        return {
            "unit_id": unit_id,
            "total_schedules": len(schedules),
            "enabled_schedules": len(enabled),
            "by_device_type": by_device,
            "light_hours": self.get_light_hours(unit_id),
        }
