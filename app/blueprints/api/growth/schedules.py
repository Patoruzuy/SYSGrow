"""
Device Schedule Management
===========================

Endpoints for managing device schedules (on/off times) for growth units.

API Versions:
- v2: Legacy endpoints using device_schedules JSON column (deprecated)
- v3: New endpoints using DeviceSchedules table with full CRUD support

Includes getting active devices based on current time.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from flask import request
from pydantic import ValidationError

from app.blueprints.api._common import (
    fail as _fail,
    get_device_repo as _device_repo,
    get_growth_service as _service,
    get_plant_service as _plant_service,
    get_scheduling_service as _scheduling_service,
    success as _success,
)
from app.domain.schedules import PhotoperiodConfig, Schedule
from app.enums import PhotoperiodSource, ScheduleType
from app.schemas.growth import (
    ScheduleCreateSchema,
    ScheduleUpdateSchema,
)

from . import growth_api

logger = logging.getLogger("growth_api.schedules")


# ============================================================================
# V3 API - UNIFIED SCHEDULE MANAGEMENT (DeviceSchedules table)
# ============================================================================


@growth_api.get("/v3/units/<int:unit_id>/schedules")
def get_schedules(unit_id: int):
    """
    Get all schedules for a growth unit.

    Query params:
        device_type: Filter by device type (optional)
        enabled_only: Only return enabled schedules (optional, default false)
    """
    logger.info(f"[v3] Getting schedules for unit {unit_id}")
    try:
        sched_service = _scheduling_service()
        growth_service = _service()

        # Check unit exists
        unit = growth_service.get_unit_runtime(unit_id)
        if not unit:
            return _fail(f"Growth unit {unit_id} not found", 404)

        # Get query params
        device_type = request.args.get("device_type")
        enabled_only = request.args.get("enabled_only", "false").lower() == "true"

        # Fetch schedules
        if device_type:
            schedules = sched_service.get_schedules_for_unit(unit_id, device_type)
            if enabled_only:
                schedules = [s for s in schedules if s.enabled]
        elif enabled_only:
            schedules = sched_service.get_schedules_for_unit(unit_id, enabled_only=True)
        else:
            schedules = sched_service.get_schedules_for_unit(unit_id)

        return _success(
            {
                "schedules": [s.to_dict() for s in schedules],
                "count": len(schedules),
                "unit_id": unit_id,
            }
        )

    except Exception as e:
        logger.exception(f"Error getting schedules for unit {unit_id}: {e}")
        return _fail("Failed to get schedules", 500)


@growth_api.get("/v3/units/<int:unit_id>/schedules/<int:schedule_id>")
def get_schedule(unit_id: int, schedule_id: int):
    """Get a specific schedule by ID."""
    logger.info(f"[v3] Getting schedule {schedule_id} for unit {unit_id}")
    try:
        sched_service = _scheduling_service()

        schedule = sched_service.get_schedule(schedule_id)
        if not schedule:
            return _fail(f"Schedule {schedule_id} not found", 404)

        # Verify it belongs to the unit
        if schedule.unit_id != unit_id:
            return _fail(f"Schedule {schedule_id} does not belong to unit {unit_id}", 404)

        return _success({"schedule": schedule.to_dict()})

    except Exception as e:
        logger.exception(f"Error getting schedule {schedule_id}: {e}")
        return _fail("Failed to get schedule", 500)


@growth_api.post("/v3/units/<int:unit_id>/schedules")
def create_schedule(unit_id: int):
    """
    Create a new schedule for a growth unit.

    Supports multiple schedules per device type.
    """
    logger.info(f"Creating schedule for unit {unit_id}")
    try:
        sched_service = _scheduling_service()
        growth_service = _service()

        # Check unit exists
        unit = growth_service.get_unit_runtime(unit_id)
        if not unit:
            return _fail(f"Growth unit {unit_id} not found", 404)

        # Validate input
        raw = request.get_json() or {}
        device_type = raw.get("device_type")
        schedule_type = raw.get("schedule_type")
        end_time = raw.get("end_time")
        raw = _normalize_photoperiod_times(raw)
        if (
            str(device_type or "").lower() == "light"
            and str(schedule_type or "").lower() == "automatic"
            and not end_time
        ):
            start_time = raw.get("start_time")
            if not start_time:
                return _fail("'start_time' is required for automatic light schedules", 400)
            hours = _resolve_automatic_light_hours(unit_id, unit, raw.get("plant_id"))
            if hours is None:
                return _fail(
                    "Automatic light schedules require an active plant to determine light hours. "
                    "Activate a plant or provide an end time.",
                    400,
                )
            computed_end = _calculate_end_time_from_start(start_time, hours)
            if not computed_end:
                return _fail("Invalid start_time format; expected HH:MM", 400)
            raw["end_time"] = computed_end
        try:
            payload = ScheduleCreateSchema(**raw)
        except ValidationError as ve:
            return _fail("Invalid schedule data", 400, details={"errors": ve.errors()})

        # Build photoperiod config if provided
        photoperiod = None
        if payload.photoperiod:
            photoperiod = PhotoperiodConfig(
                source=payload.photoperiod.source,
                sensor_threshold=payload.photoperiod.sensor_threshold,
                sensor_tolerance=payload.photoperiod.sensor_tolerance,
                prefer_sensor=payload.photoperiod.prefer_sensor,
                min_light_hours=payload.photoperiod.min_light_hours,
                max_light_hours=payload.photoperiod.max_light_hours,
            )

        # Create schedule entity
        schedule = Schedule(
            unit_id=unit_id,
            name=payload.name,
            device_type=payload.device_type,
            actuator_id=payload.actuator_id,
            schedule_type=payload.schedule_type,
            start_time=payload.start_time,
            end_time=payload.end_time,
            interval_minutes=payload.interval_minutes,
            duration_minutes=payload.duration_minutes,
            days_of_week=payload.days_of_week,
            enabled=payload.enabled,
            state_when_active=payload.state_when_active,
            value=payload.value,
            photoperiod=photoperiod,
            priority=payload.priority,
        )

        if not schedule.validate():
            return _fail("Invalid schedule configuration", 400)

        check_conflicts = True
        if schedule.device_type == "light" and schedule.schedule_type == ScheduleType.PHOTOPERIOD:
            # Ensure only one photoperiod schedule per unit
            existing_photoperiod = sched_service.get_photoperiod_schedule(unit_id)
            if existing_photoperiod:
                return _fail(
                    "A photoperiod schedule already exists for this unit. "
                    "Please update the existing schedule or delete it before creating a new one.",
                    400,
                )
        # Persist
        created = sched_service.create_schedule(schedule, check_conflicts)
        if not created:
            return _fail("Failed to create schedule", 500)

        logger.info(f"Created schedule {created.schedule_id} for unit {unit_id}")
        return _success({"schedule": created.to_dict()}, status=201)

    except Exception as e:
        logger.exception(f"Error creating schedule for unit {unit_id}: {e}")
        return _fail("Failed to create schedule", 500)


@growth_api.put("/v3/units/<int:unit_id>/schedules/<int:schedule_id>")
def update_schedule(unit_id: int, schedule_id: int):
    """Update an existing schedule."""
    logger.info(f"Updating schedule {schedule_id} for unit {unit_id}")
    try:
        sched_service = _scheduling_service()

        # Get existing schedule
        existing = sched_service.get_schedule(schedule_id)
        if not existing:
            return _fail(f"Schedule {schedule_id} not found", 404)

        if existing.unit_id != unit_id:
            return _fail(f"Schedule {schedule_id} does not belong to unit {unit_id}", 404)
        # TODO: can be added reason to update, the service can log it but i need to implent frontend part
        # Validate input
        raw = request.get_json() or {}
        device_type = raw.get("device_type") or existing.device_type
        schedule_type = raw.get("schedule_type") or existing.schedule_type
        end_time = raw.get("end_time")
        raw = _normalize_photoperiod_times(raw, existing)
        if (
            str(device_type or "").lower() == "light"
            and str(schedule_type or "").lower() == "automatic"
            and not end_time
        ):
            start_time = raw.get("start_time") or existing.start_time
            if not start_time:
                return _fail("'start_time' is required for automatic light schedules", 400)
            growth_service = _service()
            unit = growth_service.get_unit_runtime(unit_id) if growth_service else None
            hours = _resolve_automatic_light_hours(unit_id, unit, raw.get("plant_id"))
            if hours is None:
                return _fail(
                    "Automatic light schedules require an active plant to determine light hours. "
                    "Activate a plant or provide an end time.",
                    400,
                )
            computed_end = _calculate_end_time_from_start(start_time, hours)
            if not computed_end:
                return _fail("Invalid start_time format; expected HH:MM", 400)
            raw["end_time"] = computed_end
        try:
            payload = ScheduleUpdateSchema(**raw)
        except ValidationError as ve:
            return _fail("Invalid schedule data", 400, details={"errors": ve.errors()})

        # Apply updates (only non-None fields)
        if payload.name is not None:
            existing.name = payload.name
        if payload.device_type is not None:
            existing.device_type = payload.device_type
        if payload.actuator_id is not None:
            existing.actuator_id = payload.actuator_id
        if payload.schedule_type is not None:
            existing.schedule_type = payload.schedule_type
        if payload.start_time is not None:
            existing.start_time = payload.start_time
        if payload.end_time is not None:
            existing.end_time = payload.end_time
        if payload.interval_minutes is not None:
            existing.interval_minutes = payload.interval_minutes
        if payload.duration_minutes is not None:
            existing.duration_minutes = payload.duration_minutes
        if payload.days_of_week is not None:
            existing.days_of_week = payload.days_of_week
        if payload.enabled is not None:
            existing.enabled = payload.enabled
        if payload.state_when_active is not None:
            existing.state_when_active = payload.state_when_active
        if payload.value is not None:
            existing.value = payload.value
        if payload.priority is not None:
            existing.priority = payload.priority
        if payload.photoperiod is not None:
            existing.photoperiod = PhotoperiodConfig(
                source=payload.photoperiod.source,
                sensor_threshold=payload.photoperiod.sensor_threshold,
                sensor_tolerance=payload.photoperiod.sensor_tolerance,
                prefer_sensor=payload.photoperiod.prefer_sensor,
                min_light_hours=payload.photoperiod.min_light_hours,
                max_light_hours=payload.photoperiod.max_light_hours,
            )

        existing.updated_at = datetime.now()

        if not existing.validate():
            return _fail("Invalid schedule configuration", 400)

        # Persist
        success = sched_service.update_schedule(schedule=existing)
        if not success:
            return _fail("Failed to update schedule", 500)

        # Refetch to get updated data
        updated = sched_service.get_schedule(schedule_id)
        logger.info(f"Updated schedule {schedule_id}")
        return _success({"schedule": updated.to_dict()})

    except Exception as e:
        logger.exception(f"Error updating schedule {schedule_id}: {e}")
        return _fail("Failed to update schedule", 500)


@growth_api.patch("/v3/units/<int:unit_id>/schedules/<int:schedule_id>/enabled")
def toggle_schedule(unit_id: int, schedule_id: int):
    """Enable or disable a schedule without deleting it."""
    logger.info(f"Toggling schedule {schedule_id} for unit {unit_id}")
    try:
        sched_service = _scheduling_service()

        # Get existing schedule
        existing = sched_service.get_schedule(schedule_id)
        if not existing:
            return _fail(f"Schedule {schedule_id} not found", 404)

        if existing.unit_id != unit_id:
            return _fail(f"Schedule {schedule_id} does not belong to unit {unit_id}", 404)

        # Get new enabled state
        raw = request.get_json() or {}
        enabled_raw = raw.get("enabled")
        if enabled_raw is None:
            return _fail("'enabled' field is required", 400)

        if isinstance(enabled_raw, bool):
            enabled = enabled_raw
        elif isinstance(enabled_raw, (int, float)) and enabled_raw in (0, 1):
            enabled = bool(enabled_raw)
        elif isinstance(enabled_raw, str):
            normalized = enabled_raw.strip().lower()
            if normalized in {"true", "1", "yes", "on"}:
                enabled = True
            elif normalized in {"false", "0", "no", "off"}:
                enabled = False
            else:
                return _fail("'enabled' must be a boolean", 400)
        else:
            return _fail("'enabled' must be a boolean", 400)

        # Update
        success = sched_service.set_schedule_enabled(schedule_id, enabled)
        if not success:
            return _fail("Failed to update schedule", 500)

        logger.info(f"Schedule {schedule_id} {'enabled' if enabled else 'disabled'}")
        return _success(
            {
                "schedule_id": schedule_id,
                "enabled": enabled,
                "message": f"Schedule {'enabled' if enabled else 'disabled'}",
            }
        )

    except Exception as e:
        logger.exception(f"Error toggling schedule {schedule_id}: {e}")
        return _fail("Failed to toggle schedule", 500)


@growth_api.post("/v3/units/<int:unit_id>/schedules/bulk-update")
def bulk_update_schedules(unit_id: int):
    """Bulk enable, disable, or delete multiple schedules at once.

    Request body:
    {
        "schedule_ids": [1, 2, 3],
        "action": "enable" | "disable" | "delete"
    }
    """
    logger.info(f"[v3] Bulk updating schedules for unit {unit_id}")
    try:
        sched_service = _scheduling_service()
        growth_service = _service()

        # Check unit exists
        unit = growth_service.get_unit_runtime(unit_id)
        if not unit:
            return _fail(f"Growth unit {unit_id} not found", 404)

        raw = request.get_json() or {}
        schedule_ids = raw.get("schedule_ids", [])
        action = raw.get("action", "").lower()

        if not schedule_ids:
            return _fail("'schedule_ids' is required and must be a non-empty list", 400)

        if action not in ("enable", "disable", "delete"):
            return _fail("'action' must be one of: enable, disable, delete", 400)

        # Validate all schedules belong to this unit
        results = {"success": [], "failed": [], "not_found": []}

        for schedule_id in schedule_ids:
            existing = sched_service.get_schedule(schedule_id)
            if not existing:
                results["not_found"].append(schedule_id)
                continue

            if existing.unit_id != unit_id:
                results["failed"].append({"id": schedule_id, "error": "Schedule does not belong to this unit"})
                continue
            # TODO: can be added reason to update, the service can log it but i need to implent frontend part
            try:
                if action == "enable":
                    success = sched_service.set_schedule_enabled(schedule_id, True)
                elif action == "disable":
                    success = sched_service.set_schedule_enabled(schedule_id, False)
                else:  # delete
                    success = sched_service.delete_schedule(schedule_id)

                if success:
                    results["success"].append(schedule_id)
                else:
                    results["failed"].append({"id": schedule_id, "error": f"Failed to {action} schedule"})
            except Exception as e:
                results["failed"].append({"id": schedule_id, "error": str(e)})

        logger.info(
            f"Bulk {action}: {len(results['success'])} success, "
            f"{len(results['failed'])} failed, {len(results['not_found'])} not found"
        )

        return _success(
            {
                "action": action,
                "results": results,
                "message": f"Bulk {action}: {len(results['success'])} schedules updated",
            }
        )

    except Exception as e:
        logger.exception(f"Error in bulk update for unit {unit_id}: {e}")
        return _fail("Failed to bulk update schedules", 500)


@growth_api.delete("/v3/units/<int:unit_id>/schedules/<int:schedule_id>")
def delete_schedule(unit_id: int, schedule_id: int):
    """Delete a schedule permanently."""
    logger.info(f"[v3] Deleting schedule {schedule_id} for unit {unit_id}")
    try:
        sched_service = _scheduling_service()

        # Get existing schedule
        existing = sched_service.get_schedule(schedule_id)
        if not existing:
            return _fail(f"Schedule {schedule_id} not found", 404)

        if existing.unit_id != unit_id:
            return _fail(f"Schedule {schedule_id} does not belong to unit {unit_id}", 404)

        # Delete
        success = sched_service.delete_schedule(schedule_id)
        if not success:
            return _fail("Failed to delete schedule", 500)

        logger.info(f"Deleted schedule {schedule_id}")
        return _success(
            {
                "schedule_id": schedule_id,
                "message": "Schedule deleted",
            }
        )

    except Exception as e:
        logger.exception(f"Error deleting schedule {schedule_id}: {e}")
        return _fail("Failed to delete schedule", 500)


@growth_api.get("/v3/units/<int:unit_id>/schedules/active")
def get_active_schedules(unit_id: int):
    """Get list of currently active schedules based on time and day."""
    logger.info(f"[v3] Getting active schedules for unit {unit_id}")
    try:
        sched_service = _scheduling_service()
        growth_service = _service()

        # Check unit exists
        unit = growth_service.get_unit_runtime(unit_id)
        if not unit:
            return _fail(f"Growth unit {unit_id} not found", 404)

        # Get enabled schedules
        schedules = sched_service.get_schedules_for_unit(unit_id, enabled_only=True)
        unit_timezone = getattr(getattr(unit, "settings", None), "timezone", None)
        tz = None
        if unit_timezone:
            try:
                tz = ZoneInfo(unit_timezone)
            except Exception:
                logger.warning(
                    "Invalid timezone '%s' for unit %s; using system time",
                    unit_timezone,
                    unit_id,
                )
        now = datetime.now(tz) if tz else datetime.now()

        # Filter to currently active
        active = [s for s in schedules if s.is_active_at(now, timezone=unit_timezone)]

        # Group by device type
        by_device = {}
        for s in active:
            if s.device_type not in by_device:
                by_device[s.device_type] = []
            by_device[s.device_type].append(s.to_dict())

        return _success(
            {
                "current_time": now.strftime("%H:%M"),
                "current_day": now.strftime("%A"),
                "weekday": now.weekday(),
                "active_schedules": [s.to_dict() for s in active],
                "active_devices": list(by_device.keys()),
                "by_device_type": by_device,
                "count": len(active),
            }
        )

    except Exception as e:
        logger.exception(f"Error getting active schedules for unit {unit_id}: {e}")
        return _fail("Failed to get active schedules", 500)


@growth_api.get("/v3/units/<int:unit_id>/schedules/summary")
def get_schedule_summary(unit_id: int):
    """Get summary of all schedules for a unit."""
    logger.info(f"[v3] Getting schedule summary for unit {unit_id}")
    try:
        sched_service = _scheduling_service()
        growth_service = _service()

        # Check unit exists
        unit = growth_service.get_unit_runtime(unit_id)
        if not unit:
            return _fail(f"Growth unit {unit_id} not found", 404)

        schedules = sched_service.get_schedules_for_unit(unit_id)
        enabled = [s for s in schedules if s.enabled]

        # Group by device type
        by_device = {}
        for s in schedules:
            if s.device_type not in by_device:
                by_device[s.device_type] = {"total": 0, "enabled": 0}
            by_device[s.device_type]["total"] += 1
            if s.enabled:
                by_device[s.device_type]["enabled"] += 1

        # Calculate light hours from primary light schedule
        light_hours = 0.0
        light_schedule = sched_service.get_light_schedule(unit_id)
        if light_schedule:
            light_hours = light_schedule.duration_hours()

        return _success(
            {
                "unit_id": unit_id,
                "total_schedules": len(schedules),
                "enabled_schedules": len(enabled),
                "by_device_type": by_device,
                "light_hours": light_hours,
            }
        )

    except Exception as e:
        logger.exception(f"Error getting schedule summary for unit {unit_id}: {e}")
        return _fail("Failed to get schedule summary", 500)


@growth_api.get("/v3/units/<int:unit_id>/schedules/preview")
def preview_schedules(unit_id: int):
    """
    Preview upcoming schedule events for the next N hours.

    Query params:
        hours: Number of hours to preview (default 24, max 168)
        device_type: Filter by device type (optional)
    """
    logger.info(f"[v3] Getting schedule preview for unit {unit_id}")
    try:
        sched_service = _scheduling_service()
        growth_service = _service()

        # Check unit exists
        unit = growth_service.get_unit_runtime(unit_id)
        if not unit:
            return _fail(f"Growth unit {unit_id} not found", 404)

        # Get query params
        hours = min(int(request.args.get("hours", 24)), 168)
        device_type = request.args.get("device_type")

        # Get preview events
        unit_timezone = getattr(getattr(unit, "settings", None), "timezone", None)
        events = sched_service.preview_schedules(
            unit_id=unit_id,
            hours_ahead=hours,
            device_type=device_type,
            unit_timezone=unit_timezone,
        )

        return _success(
            {
                "unit_id": unit_id,
                "hours_ahead": hours,
                "events": [
                    {
                        "schedule_id": e.schedule_id,
                        "schedule_name": e.schedule_name,
                        "device_type": e.device_type,
                        "event_time": e.event_time.isoformat(),
                        "event_type": e.event_type,
                        "state": e.state,
                        "value": e.value,
                    }
                    for e in events
                ],
                "count": len(events),
            }
        )

    except Exception as e:
        logger.exception(f"Error getting schedule preview for unit {unit_id}: {e}")
        return _fail("Failed to get schedule preview", 500)


@growth_api.get("/v3/units/<int:unit_id>/schedules/history")
def get_schedule_history(unit_id: int):
    """
    Get schedule change history/audit log for a unit.

    Query params:
        schedule_id: Filter by specific schedule (optional)
        limit: Maximum records to return (default 100, max 1000)
    """
    logger.info(f"[v3] Getting schedule history for unit {unit_id}")
    try:
        sched_service = _scheduling_service()
        growth_service = _service()

        # Check unit exists
        unit = growth_service.get_unit_runtime(unit_id)
        if not unit:
            return _fail(f"Growth unit {unit_id} not found", 404)

        # Get query params
        schedule_id = request.args.get("schedule_id", type=int)
        limit = min(int(request.args.get("limit", 100)), 1000)

        # Get history from schedule_history table
        # For now, return empty list as history tracking may not be implemented
        # This can be extended when schedule_history table is available
        history = []

        history = sched_service.get_schedule_history(
            unit_id=unit_id,
            schedule_id=schedule_id,
            limit=limit,
        )

        return _success(
            {
                "unit_id": unit_id,
                "history": history,
                "count": len(history),
            }
        )

    except Exception as e:
        logger.exception(f"Error getting schedule history for unit {unit_id}: {e}")
        return _fail("Failed to get schedule history", 500)


@growth_api.get("/v3/schedules/<int:schedule_id>/execution-log")
def get_schedule_execution_log(schedule_id: int):
    """
    Get execution log for a specific schedule.

    Query params:
        limit: Maximum records to return (default 100, max 1000)
    """
    logger.info(f"[v3] Getting execution log for schedule {schedule_id}")
    try:
        sched_service = _scheduling_service()

        # Check schedule exists
        schedule = sched_service.get_schedule(schedule_id)
        if not schedule:
            return _fail(f"Schedule {schedule_id} not found", 404)

        # Get query params
        limit = min(int(request.args.get("limit", 100)), 1000)

        # Get execution log
        log = sched_service.get_execution_log(
            schedule_id=schedule_id,
            limit=limit,
        )

        return _success(
            {
                "schedule_id": schedule_id,
                "execution_log": log,
                "count": len(log),
            }
        )

    except Exception as e:
        logger.exception(f"Error getting execution log for schedule {schedule_id}: {e}")
        return _fail("Failed to get execution log", 500)


@growth_api.get("/v3/units/<int:unit_id>/schedules/conflicts")
def detect_schedule_conflicts(unit_id: int):
    """
    Detect conflicts between schedules for a unit.

    Query params:
        device_type: Filter by device type (optional)
    """
    logger.info(f"[v3] Detecting schedule conflicts for unit {unit_id}")
    try:
        sched_service = _scheduling_service()
        growth_service = _service()

        # Check unit exists
        unit = growth_service.get_unit_runtime(unit_id)
        if not unit:
            return _fail(f"Growth unit {unit_id} not found", 404)

        # Get query params
        device_type = request.args.get("device_type")

        # Get schedules
        schedules = sched_service.get_schedules_for_unit(
            unit_id=unit_id,
            device_type=device_type,
        )

        all_conflicts = []
        for schedule in schedules:
            conflicts = sched_service.detect_conflicts(schedule)
            for conflict in conflicts:
                all_conflicts.append(
                    {
                        "schedule_a_id": conflict.schedule_a.schedule_id,
                        "schedule_a_name": conflict.schedule_a.name,
                        "schedule_b_id": conflict.schedule_b.schedule_id,
                        "schedule_b_name": conflict.schedule_b.name,
                        "overlap_start": conflict.overlap_start,
                        "overlap_end": conflict.overlap_end,
                        "conflicting_days": conflict.conflicting_days,
                        "resolution": conflict.resolution,
                    }
                )

        # Remove duplicate pairs
        seen = set()
        unique_conflicts = []
        for c in all_conflicts:
            key = tuple(sorted([c["schedule_a_id"], c["schedule_b_id"]]))
            if key not in seen:
                seen.add(key)
                unique_conflicts.append(c)

        return _success(
            {
                "unit_id": unit_id,
                "conflicts": unique_conflicts,
                "count": len(unique_conflicts),
                "has_conflicts": len(unique_conflicts) > 0,
            }
        )

    except Exception as e:
        logger.exception(f"Error detecting conflicts for unit {unit_id}: {e}")
        return _fail("Failed to detect schedule conflicts", 500)


@growth_api.post("/v3/units/<int:unit_id>/schedules/auto-generate")
def auto_generate_schedules(unit_id: int):
    """
    Auto-generate schedules based on the active plant's growth stage.

    This creates AUTOMATIC type schedules derived from plant metadata via
    PlantService. These schedules replace any existing auto-generated schedules
    for the unit.

    Request body (optional):
        replace_existing: Whether to replace existing auto schedules (default true)
        plant_id: Specific plant ID (default: use active plant)
    """
    logger.info(f"Auto-generating schedules for unit {unit_id}")
    try:
        sched_service = _scheduling_service()
        growth_service = _service()

        # Check unit exists
        unit = growth_service.get_unit_runtime(unit_id)
        if not unit:
            return _fail(f"Growth unit {unit_id} not found", 404)

        # Parse request body
        data = request.get_json(silent=True) or {}
        replace_existing = data.get("replace_existing", True)
        plant_id = data.get("plant_id")

        # Get plant from PlantService (memory-first)
        plant_service = _plant_service()
        plant = None

        if plant_id:
            plant = plant_service.get_plant(plant_id, unit_id=unit_id)
        else:
            # Get active plant for unit
            active_plant_id = getattr(unit, "active_plant_id", None) or getattr(unit, "_active_plant_id", None)
            if active_plant_id:
                plant = plant_service.get_plant(active_plant_id, unit_id=unit_id)
            else:
                # Fallback to first plant in unit
                plants = plant_service.list_plants(unit_id)
                plant = plants[0] if plants else None

        if not plant:
            return _fail("No plant found for this unit. Add a plant first.", 400)

        # Extract plant info - PlantProfile is a dataclass
        plant_type = plant.plant_type or plant.plant_name or "default"
        current_stage = plant.current_stage or "Vegetative"

        # Build automation settings using PlantService (single source of truth)
        stage_key = (current_stage or "").strip().lower() or "default"
        stage_lighting = plant_service.get_plant_lighting_for_stage(plant_type, current_stage) or {}
        if not stage_lighting:
            return _fail(
                f"No lighting data found for plant '{plant_type}' at stage '{current_stage}'. "
                "Please configure plant lighting before generating schedules.",
                400,
            )

        hours = stage_lighting.get("hours")
        if hours is None:
            hours = stage_lighting.get("hours_per_day")
        intensity = stage_lighting.get("intensity")

        if hours is None or intensity is None:
            return _fail(
                f"Lighting data for plant '{plant_type}' at stage '{current_stage}' is missing hours or intensity.",
                400,
            )
        default_requirements = _get_default_plant_requirements(current_stage)

        plant_info = {
            "automation": {
                "lighting_schedule": {stage_key: {"hours": hours, "intensity": intensity}},
                "environmental_controls": default_requirements.get("automation", {}).get(
                    "environmental_controls",
                    {},
                ),
            }
        }

        # Get actuators for the unit
        device_repo = _device_repo()
        actuators = device_repo.list_actuator_configs(unit_id=unit_id)
        light_actuator = next(
            (a for a in actuators if str(a.get("actuator_type", "")).lower() == "light"),
            None,
        )
        fan_actuator = next(
            (a for a in actuators if str(a.get("actuator_type", "")).lower() == "fan"),
            None,
        )
        light_actuator_id = light_actuator.get("actuator_id") if light_actuator else None
        fan_actuator_id = fan_actuator.get("actuator_id") if fan_actuator else None

        # Apply plant stage schedules
        created_count = sched_service.apply_plant_stage_schedules(
            unit_id=unit_id,
            plant_info=plant_info,
            current_stage=current_stage,
            light_actuator_id=light_actuator_id,
            fan_actuator_id=fan_actuator_id,
            replace_existing=replace_existing,
        )

        # Get the newly created schedules
        new_schedules = sched_service.get_schedules_for_unit(unit_id)
        auto_schedules = [s for s in new_schedules if s.metadata.get("auto_generated")]

        return _success(
            {
                "unit_id": unit_id,
                "plant_type": plant_type,
                "current_stage": current_stage,
                "schedules_created": created_count,
                "schedules": [s.to_dict() for s in auto_schedules],
                "message": f"Created {created_count} automatic schedules for {current_stage} stage",
            }
        )

    except Exception as e:
        logger.exception(f"Error auto-generating schedules for unit {unit_id}: {e}")
        return _fail("Failed to auto-generate schedules", 500)


def _get_default_plant_requirements(stage: str) -> dict:
    """Get default plant requirements for a growth stage."""
    defaults = {
        "Seed": {
            "automation": {
                "light": {"hours": 0, "intensity": 0},
            }
        },
        "Germination": {
            "automation": {
                "light": {"hours": 12, "intensity": 30},
            }
        },
        "Seedling": {
            "automation": {
                "light": {"hours": 16, "intensity": 50},
                "environmental_controls": {"fan": True},
            }
        },
        "Vegetative": {
            "automation": {
                "light": {"hours": 18, "intensity": 80},
                "environmental_controls": {"fan": True},
            }
        },
        "Flowering": {
            "automation": {
                "light": {"hours": 12, "intensity": 100},
                "environmental_controls": {"fan": True},
            }
        },
        "Fruiting": {
            "automation": {
                "light": {"hours": 12, "intensity": 100},
                "environmental_controls": {"fan": True},
            }
        },
        "Harvest": {
            "automation": {
                "light": {"hours": 8, "intensity": 50},
            }
        },
    }
    return defaults.get(stage, defaults["Vegetative"])


def _calculate_end_time_from_start(start_time, hours):
    try:
        start_dt = datetime.strptime(start_time, "%H:%M")
    except ValueError:
        return None
    try:
        hours_value = float(hours)
    except (TypeError, ValueError):
        return None
    minutes = int(round(hours_value * 60))
    end_dt = start_dt + timedelta(minutes=minutes)
    return end_dt.strftime("%H:%M")


def _normalize_photoperiod_times(raw, existing=None):
    schedule_type = raw.get("schedule_type")
    if schedule_type is None and existing is not None:
        schedule_type = getattr(existing.schedule_type, "value", existing.schedule_type)
    if isinstance(schedule_type, ScheduleType):
        schedule_type = schedule_type.value
    schedule_type = str(schedule_type or "").lower()
    if schedule_type != "photoperiod":
        return raw

    source = None
    photoperiod = raw.get("photoperiod")
    if isinstance(photoperiod, dict):
        source = photoperiod.get("source")
    elif existing is not None and getattr(existing, "photoperiod", None):
        source = existing.photoperiod.source
    if isinstance(source, PhotoperiodSource):
        source = source.value
    source = str(source or "").lower()

    if source in {"sensor", "sun_api"}:
        raw["start_time"] = "00:00"
        raw["end_time"] = "00:00"

    return raw


def _resolve_automatic_light_hours(unit_id, unit, plant_id):
    plant_service = _plant_service()
    plant = None

    if plant_id:
        plant = plant_service.get_plant(plant_id, unit_id=unit_id)

    if not plant:
        active_plant_id = getattr(unit, "active_plant_id", None) or getattr(unit, "_active_plant_id", None)
        if active_plant_id:
            plant = plant_service.get_plant(active_plant_id, unit_id=unit_id)

    if not plant:
        plants = plant_service.list_plants(unit_id)
        plant = plants[0] if plants else None

    if not plant:
        return None

    plant_type = getattr(plant, "plant_type", None) or getattr(plant, "plant_name", None) or "default"
    current_stage = getattr(plant, "current_stage", None) or "Vegetative"

    stage_lighting = plant_service.get_plant_lighting_for_stage(plant_type, current_stage) or {}
    hours = stage_lighting.get("hours")
    if hours is None:
        hours = stage_lighting.get("hours_per_day")
    return hours


@growth_api.get("/v3/units/<int:unit_id>/schedules/templates")
def get_schedule_templates(unit_id: int):
    """
    Get schedule templates based on unit's active plant type and stage.

    Returns recommended schedule configurations that can be applied.
    """
    logger.info(f"[v3] Getting schedule templates for unit {unit_id}")
    try:
        sched_service = _scheduling_service()
        growth_service = _service()

        # Check unit exists
        unit = growth_service.get_unit_runtime(unit_id)
        if not unit:
            return _fail(f"Growth unit {unit_id} not found", 404)

        # Get active plant from PlantService
        plant_service = _plant_service()
        plants = plant_service.list_plants(unit_id)
        active_plant = next((p for p in plants if getattr(p, "is_active", False)), None)
        if not active_plant and plants:
            active_plant = plants[0]

        plant_type = getattr(active_plant, "plant_type", "default") if active_plant else "default"
        current_stage = getattr(active_plant, "current_stage", "Vegetative") if active_plant else "Vegetative"

        # Get templates for each stage
        templates = {}
        for stage in ["Seedling", "Vegetative", "Flowering", "Fruiting", "Harvest"]:
            req = _get_default_plant_requirements(stage)
            automation = req.get("automation", {})
            light = automation.get("light", {})

            templates[stage] = {
                "stage": stage,
                "light": {
                    "hours": light.get("hours", 12),
                    "intensity": light.get("intensity", 80),
                    "start_time": _calculate_light_start(light.get("hours", 12)),
                    "end_time": _calculate_light_end(light.get("hours", 12)),
                },
                "fan": {
                    "enabled": automation.get("environmental_controls", {}).get("fan", False),
                    "start_time": "06:00",
                    "end_time": "22:00",
                },
                "is_current": stage == current_stage,
            }

        return _success(
            {
                "unit_id": unit_id,
                "plant_type": plant_type,
                "current_stage": current_stage,
                "templates": templates,
            }
        )

    except Exception as e:
        logger.exception(f"Error getting schedule templates for unit {unit_id}: {e}")
        return _fail("Failed to get schedule templates", 500)


def _calculate_light_start(hours: int) -> str:
    """Calculate light start time centered around noon."""
    half = hours / 2
    start_minutes = int((12 - half) * 60)
    return f"{start_minutes // 60:02d}:{start_minutes % 60:02d}"


def _calculate_light_end(hours: int) -> str:
    """Calculate light end time centered around noon."""
    half = hours / 2
    end_minutes = int((12 + half) * 60)
    return f"{end_minutes // 60:02d}:{end_minutes % 60:02d}"
