"""
Scheduled Tasks: All background task definitions for the UnifiedScheduler.

This module contains task functions organized by namespace:
- plant.*: Plant growth and health tasks
- actuator.*: Actuator scheduling tasks
- ml.*: ML model retraining tasks
- maintenance.*: Database and system maintenance tasks

Usage:
    from app.workers.scheduled_tasks import register_all_tasks
    from app.workers.unified_scheduler import get_scheduler

    scheduler = get_scheduler()
    register_all_tasks(scheduler, container)
    scheduler.start()

Celery Migration:
    When migrating to Celery, move each task to a celery_tasks.py module
    and replace @scheduler.task with @celery.task

Author: SYSGrow Team
Date: December 2024
"""

from __future__ import annotations

import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime
from functools import wraps
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.enums import ScheduleState

if TYPE_CHECKING:
    from app.services.container import ServiceContainer
    from app.workers.unified_scheduler import UnifiedScheduler

logger = logging.getLogger(__name__)

TASK_SOFT_ERRORS = (
    RuntimeError,
    ValueError,
    TypeError,
    AttributeError,
    OSError,
    ImportError,
)

from app.utils.persistent_store import load_growth_last_runs, save_growth_last_runs

# Per-unit locks to prevent concurrent growth runs for the same unit (in-process)
_unit_locks: dict[int, threading.Lock] = {}


# ==================== Plant Namespace Tasks ====================


def plant_grow_task(container: "ServiceContainer") -> dict[str, Any]:
    """
    Notify plant growth observers to advance plant growth.

    This task runs daily at midnight (configurable) to:
    - Increment days_in_stage for all plants
    - Check for stage transitions
    - Publish growth events

    Celery name: plant.grow
    """
    growth_service = container.growth_service
    plant_service = container.plant_service

    results = {
        "plants_processed": 0,
        "errors": [],
    }
    # Note: load_growth_last_runs() tracks the last processed date per unit, so missed days
    # are caught automatically. Batching can be considered if unit count grows significantly.
    try:
        # Get all unit runtimes (snapshot for safe iteration)
        last_runs = load_growth_last_runs()

        for unit_id, _runtime in growth_service.get_unit_runtimes().items():
            unit_lock = _unit_locks.setdefault(unit_id, threading.Lock())
            try:
                # Serialize processing per-unit in-process to avoid races
                with unit_lock:
                    # Get plants from PlantService (single source of truth)
                    plants = plant_service.list_plants(unit_id)

                    # Determine how many days we need to advance (handles missed days)
                    today = date.today()
                    last_str = last_runs.get(str(unit_id))
                    last_date = None
                    if last_str:
                        try:
                            last_date = date.fromisoformat(last_str)
                        except (TypeError, ValueError):
                            last_date = None

                    # If never run before, treat as single run today
                    days_to_advance = 1
                    if last_date is not None:
                        delta = (today - last_date).days
                        if delta <= 0:
                            # Already processed today
                            logger.debug("Skipping unit %s growth check; already processed today", unit_id)
                            continue
                        days_to_advance = max(1, delta)

                    # Advance each plant by the number of missed days
                    # Optional parallelization per-unit (bounded workers) via container.config
                    try:
                        config = getattr(container, "config", None)
                        workers = 1
                        if config:
                            try:
                                workers = int(getattr(config, "growth_parallel_workers_per_unit", 1) or 1)
                            except (TypeError, ValueError):
                                workers = 1

                        def _process_plant(p, days_to_advance=days_to_advance):
                            # Advance plant locally
                            for _ in range(days_to_advance):
                                p.grow()
                            # Persist once
                            plant_service.update_plant_stage(p.plant_id, p.current_stage, p.days_in_stage)
                            return p

                        if workers and workers > 1:
                            futures = []
                            with ThreadPoolExecutor(
                                max_workers=workers, thread_name_prefix=f"grow_unit_{unit_id}"
                            ) as ex:
                                for plant in plants:
                                    futures.append(ex.submit(_process_plant, plant))

                                for fut in as_completed(futures):
                                    try:
                                        p = fut.result()
                                        results["plants_processed"] += 1
                                        logger.debug(
                                            "Plant %s (ID: %s) advanced: Stage '%s' - Day %s (advanced %s day(s))",
                                            p.plant_name,
                                            p.id,
                                            p.current_stage,
                                            p.days_in_stage,
                                            days_to_advance,
                                        )
                                    except TASK_SOFT_ERRORS as e:
                                        results["errors"].append(str(e))
                                        logger.error("Error growing plant in parallel for unit %s: %s", unit_id, e)
                        else:
                            for plant in plants:
                                try:
                                    _process_plant(plant)
                                    results["plants_processed"] += 1
                                    logger.debug(
                                        "Plant %s (ID: %s) advanced: Stage '%s' - Day %s (advanced %s day(s))",
                                        plant.plant_name,
                                        plant.id,
                                        plant.current_stage,
                                        plant.days_in_stage,
                                        days_to_advance,
                                    )
                                except TASK_SOFT_ERRORS as e:
                                    results["errors"].append(f"Plant {plant.id}: {e!s}")
                                    logger.error("Error growing plant %s: %s", plant.id, e)
                    except TASK_SOFT_ERRORS as e:
                        results["errors"].append(f"Unit {unit_id} plant processing error: {e!s}")
                        logger.error("Error processing plants for unit %s: %s", unit_id, e)

                    # Persist last run date for this unit so restarts can detect missed days
                    last_runs[str(unit_id)] = today.isoformat()
                    save_growth_last_runs(last_runs)

            except TASK_SOFT_ERRORS as e:
                results["errors"].append(f"Unit {unit_id}: {e!s}")
                logger.error("Error processing unit %s: %s", unit_id, e)

        logger.info("Plant growth task complete: %s plants processed", results["plants_processed"])

    except TASK_SOFT_ERRORS as e:
        logger.error("Plant growth task failed: %s", e, exc_info=True)
        results["errors"].append(str(e))

    return results


def plant_health_check_task(container: "ServiceContainer") -> dict[str, Any]:
    """
    Run ML-based health analysis on all plants.

    This task runs daily to:
    - Analyze plant health using ML models
    - Publish health update events
    - Log health issues

    Celery name: plant.health_check
    """
    growth_service = container.growth_service
    plant_service = container.plant_service

    # Get plant health monitor from container if available
    plant_health_monitor = getattr(container, "plant_health_monitor", None)

    results = {
        "plants_checked": 0,
        "issues_found": 0,
        "errors": [],
    }

    if not plant_health_monitor:
        logger.debug("Plant health monitor not available - skipping health check")
        return results

    try:
        from app.enums.events import PlantEvent
        from app.utils.time import iso_now

        event_bus = getattr(growth_service, "event_bus", None)

        for unit_id, _runtime in growth_service.get_unit_runtimes().items():
            try:
                # Get plants from PlantService (single source of truth)
                plants = plant_service.list_plants(unit_id)

                for plant in plants:
                    try:
                        health_status = plant_health_monitor.analyze_plant_health(
                            unit_id=unit_id,
                            plant_id=plant.id,
                        )

                        if health_status:
                            results["plants_checked"] += 1

                            # Check for issues
                            status = health_status.get("status", "unknown")
                            if status not in ("healthy", "good", "unknown"):
                                results["issues_found"] += 1

                            # Publish health update event
                            if event_bus:
                                event_bus.publish(
                                    PlantEvent.PLANT_HEALTH_UPDATE,
                                    {
                                        "unit_id": unit_id,
                                        "plant_id": plant.id,
                                        "health_status": health_status,
                                        "timestamp": iso_now(),
                                    },
                                )

                            logger.debug("Health check for plant %s: %s", plant.plant_name, status)

                    except TASK_SOFT_ERRORS as e:
                        results["errors"].append(f"Plant {plant.id}: {e!s}")
                        logger.error("Failed to check health for plant %s: %s", plant.id, e)

            except TASK_SOFT_ERRORS as e:
                results["errors"].append(f"Unit {unit_id}: {e!s}")
                logger.error("Failed to check plants in unit %s: %s", unit_id, e)

        logger.info(
            "Plant health check complete: %s plants, %s issues found",
            results["plants_checked"],
            results["issues_found"],
        )

    except TASK_SOFT_ERRORS as e:
        logger.error("Plant health check failed: %s", e, exc_info=True)
        results["errors"].append(str(e))

    return results


# ==================== Actuator Namespace Tasks ====================

# State tracking for schedule transitions (keyed by schedule_id)
_schedule_last_state: dict[int, bool] = {}
# Effective actuator command state (keyed by actuator_id)
_actuator_last_command: dict[int, tuple[str, float | None]] = {}
# Last schedule that drove each actuator command
_actuator_last_schedule: dict[int, int | None] = {}


def actuator_startup_sync_task(container: "ServiceContainer") -> dict[str, Any]:
    """
    Synchronize actuator states with active schedules at system startup.

    This task runs once at startup to ensure actuators are in the correct
    state based on currently active schedules, rather than waiting for the
    next scheduled check.

    Celery name: actuator.startup_sync
    """
    actuator_service = getattr(container, "actuator_management_service", None)
    growth_service = getattr(container, "growth_service", None)

    global _actuator_last_command
    global _actuator_last_schedule

    results = {
        "units_synced": 0,
        "actuators_synced": 0,
        "errors": [],
    }

    if not actuator_service:
        return results

    try:
        # ActuatorManagementService now contains scheduling_service directly
        scheduling_service = getattr(actuator_service, "scheduling_service", None)
        if not scheduling_service:
            return results

        # Get all unit IDs
        unit_ids = _get_active_unit_ids(growth_service)
        if not unit_ids:
            return results

        # Resolve per-unit timezones (if available)
        unit_timezones = {unit_id: _get_unit_timezone(growth_service, unit_id) for unit_id in unit_ids}

        # Perform startup sync - actuator_service now has all manager methods
        sync_results = scheduling_service.sync_actuator_states_at_startup(
            unit_ids=unit_ids,
            actuator_manager=actuator_service,
            unit_timezones=unit_timezones,
        )

        # Initialize _schedule_last_state from service's execution state
        for schedule_id, was_active in scheduling_service._last_execution_state.items():
            _schedule_last_state[schedule_id] = was_active
        _actuator_last_command = {}
        _actuator_last_schedule = {}

        results.update(sync_results)
        logger.info(
            "Startup sync completed: %s units, %s actuators synchronized",
            results["units_synced"],
            results["actuators_synced"],
        )

    except TASK_SOFT_ERRORS as e:
        logger.error("Startup sync failed: %s", e, exc_info=True)
        results["errors"].append(str(e))

    return results


def actuator_schedule_check_task(container: "ServiceContainer") -> dict[str, Any]:
    """
    Check and execute actuator schedules from the centralized DeviceSchedules table.

    This task runs every 30 seconds to:
    - Fetch enabled schedules for all units (memory-first)
    - Evaluate each schedule (with photoperiod support for lights)
    - Turn actuators on/off based on schedule transitions

    Celery name: actuator.schedule_check
    """
    global _schedule_last_state
    global _actuator_last_command
    global _actuator_last_schedule

    actuator_service = getattr(container, "actuator_management_service", None)
    analytics_service = getattr(container, "analytics_service", None)
    growth_service = getattr(container, "growth_service", None)

    results = {
        "units_checked": 0,
        "schedules_checked": 0,
        "transitions": 0,
        "errors": [],
    }

    if not actuator_service:
        return results

    try:
        # ActuatorManagementService now contains scheduling_service directly
        scheduling_service = getattr(actuator_service, "scheduling_service", None)
        if not scheduling_service:
            return results

        # Get all unit IDs to iterate
        unit_ids = _get_active_unit_ids(growth_service)
        if not unit_ids:
            return results

        for unit_id in unit_ids:
            results["units_checked"] += 1

            try:
                unit_timezone = _get_unit_timezone(growth_service, unit_id)
                tz = None
                if unit_timezone:
                    try:
                        tz = ZoneInfo(unit_timezone)
                    except (TypeError, ValueError, ZoneInfoNotFoundError):
                        logger.warning(
                            "Invalid timezone '%s' for unit %s; using system time",
                            unit_timezone,
                            unit_id,
                        )
                now = datetime.now(tz) if tz else datetime.now()

                # Get enabled schedules for this unit
                schedules = scheduling_service.get_schedules_for_unit(unit_id, enabled_only=True)

                if not schedules:
                    continue

                lux_reading = None
                if any(s.device_type == "light" and s.photoperiod for s in schedules):
                    lux_reading = _get_lux_reading(analytics_service, unit_id)

                schedule_by_id: dict[int, Any] = {}
                actuator_schedules: dict[int, list] = {}
                active_schedules_by_actuator: dict[int, list] = {}

                for schedule in schedules:
                    results["schedules_checked"] += 1
                    schedule_key = schedule.schedule_id
                    if schedule_key is None:
                        continue
                    schedule_by_id[schedule_key] = schedule

                    try:
                        is_active = scheduling_service.is_schedule_active(
                            schedule=schedule,
                            unit_id=unit_id,
                            check_time=now,
                            lux_reading=lux_reading,
                            unit_timezone=unit_timezone,
                        )
                        was_active = scheduling_service.get_last_execution_state(schedule_key)
                        if was_active is None:
                            was_active = _schedule_last_state.get(schedule_key)

                        # Execution log for schedules without linked actuators
                        if not schedule.actuator_id:
                            if is_active and was_active is False:
                                scheduling_service.record_execution(
                                    schedule=schedule,
                                    action="activate",
                                    success=True,
                                    source="system",
                                )
                            elif not is_active and was_active is True:
                                scheduling_service.record_execution(
                                    schedule=schedule,
                                    action="deactivate",
                                    success=True,
                                    source="system",
                                )
                            _schedule_last_state[schedule_key] = is_active
                            scheduling_service.set_last_execution_state(schedule_key, is_active)
                            continue

                        actuator_id = schedule.actuator_id
                        actuator_schedules.setdefault(actuator_id, []).append(schedule)
                        if is_active:
                            active_schedules_by_actuator.setdefault(actuator_id, []).append(schedule)

                        _schedule_last_state[schedule_key] = is_active
                        scheduling_service.set_last_execution_state(schedule_key, is_active)
                    except TASK_SOFT_ERRORS as e:
                        error_msg = f"Schedule {schedule_key} ({schedule.device_type}): {e}"
                        results["errors"].append(error_msg)
                        logger.error("Error checking schedule: %s", error_msg)

                for actuator_id, _all_for_actuator in actuator_schedules.items():
                    active_for_actuator = active_schedules_by_actuator.get(actuator_id, [])
                    selected = scheduling_service.select_effective_schedule(active_for_actuator)

                    if selected is None:
                        desired_command: tuple[str, float | None] = ("off", None)
                    elif selected.value is not None:
                        desired_command = ("level", float(selected.value))
                    elif selected.state_when_active == ScheduleState.ON:
                        desired_command = ("on", None)
                    else:
                        desired_command = ("off", None)

                    previous_command = _actuator_last_command.get(actuator_id)
                    if previous_command is None:
                        current_state = actuator_service.get_actuator_state(actuator_id)
                        if current_state is True:
                            previous_command = ("on", None)
                        elif current_state is False:
                            previous_command = ("off", None)
                        else:
                            previous_command = desired_command

                    if desired_command == previous_command:
                        _actuator_last_schedule[actuator_id] = selected.schedule_id if selected else None
                        continue

                    transition_ok = False
                    if selected is not None:
                        transition_ok = _handle_schedule_activation(
                            scheduling_service,
                            actuator_service,
                            selected,
                            actuator_id,
                            results,
                        )
                    else:
                        previous_schedule_id = _actuator_last_schedule.get(actuator_id)
                        previous_schedule = schedule_by_id.get(previous_schedule_id) if previous_schedule_id else None
                        if previous_schedule is not None:
                            transition_ok = _handle_schedule_deactivation(
                                scheduling_service,
                                actuator_service,
                                previous_schedule,
                                actuator_id,
                                results,
                            )
                        else:
                            try:
                                actuator_service.turn_off(actuator_id)
                                results["transitions"] += 1
                                transition_ok = True
                            except TASK_SOFT_ERRORS as e:
                                results["errors"].append(f"Actuator {actuator_id} off: {e!s}")
                                logger.error(
                                    "Failed to deactivate actuator %s without schedule context: %s",
                                    actuator_id,
                                    e,
                                )

                    if transition_ok:
                        _actuator_last_command[actuator_id] = desired_command
                        _actuator_last_schedule[actuator_id] = selected.schedule_id if selected else None

            except TASK_SOFT_ERRORS as e:
                error_msg = f"Unit {unit_id}: {e}"
                results["errors"].append(error_msg)
                logger.error("Error processing unit schedules: %s", error_msg)

        if results["transitions"] > 0:
            logger.debug(
                "Schedule check: %s units, %s schedules, %s transitions",
                results["units_checked"],
                results["schedules_checked"],
                results["transitions"],
            )

    except TASK_SOFT_ERRORS as e:
        logger.error("Actuator schedule check failed: %s", e, exc_info=True)
        results["errors"].append(str(e))

    return results


def _get_active_unit_ids(growth_service) -> list:
    """Get list of active unit IDs from growth service."""
    if not growth_service:
        return []

    try:
        # Try to get unit runtimes (preferred - only active units)
        runtimes = getattr(growth_service, "get_unit_runtimes", None)
        if runtimes:
            return list(runtimes().keys())

        # Fall back to listing all units
        units = growth_service.list_units()
        return [u.get("unit_id") or u.get("id") for u in units if u]

    except TASK_SOFT_ERRORS as e:
        logger.warning("Failed to get unit IDs: %s", e)
        return []


def _get_unit_timezone(growth_service, unit_id: int) -> str | None:
    """Resolve the timezone string for a unit (if configured)."""
    if not growth_service:
        return None
    try:
        runtime = growth_service.get_unit_runtime(unit_id)
        settings = getattr(runtime, "settings", None) if runtime else None
        return getattr(settings, "timezone", None) if settings else None
    except TASK_SOFT_ERRORS as exc:
        logger.debug("Could not resolve timezone for unit %s: %s", unit_id, exc)
        return None


def _get_lux_reading(analytics_service, unit_id: int) -> float | None:
    """Get current lux reading for a unit from analytics service."""
    if not analytics_service:
        return None

    try:
        reading = analytics_service.get_latest_sensor_reading(unit_id=unit_id)
        if not reading:
            return None
        val = reading.get("lux")
        if val is not None:
            return float(val)

        return None

    except TASK_SOFT_ERRORS as e:
        logger.debug("Could not get lux reading for unit %s: %s", unit_id, e)
        return None


def _handle_schedule_activation(
    scheduling_service,
    actuator_service,
    schedule,
    actuator_id: int,
    results: dict,
) -> bool:
    """Handle transition from inactive to active state."""
    try:
        if scheduling_service:
            result = scheduling_service.execute_with_retry(
                schedule,
                activate=True,
                actuator_manager=actuator_service,
            )
            if result.success:
                results["transitions"] += 1
                logger.info(
                    "Schedule %s (%s) activated -> actuator %s",
                    schedule.schedule_id,
                    schedule.device_type,
                    actuator_id,
                )
                return True
            else:
                results["errors"].append(f"Actuator {actuator_id} on: {result.error_message}")
            return False

        if schedule.value is not None:
            actuator_service.set_level(actuator_id, float(schedule.value))
        elif schedule.state_when_active.value == "on":
            actuator_service.turn_on(actuator_id)
        else:
            actuator_service.turn_off(actuator_id)

        results["transitions"] += 1
        logger.info(
            "Schedule %s (%s) activated -> actuator %s", schedule.schedule_id, schedule.device_type, actuator_id
        )
        return True
    except TASK_SOFT_ERRORS as e:
        results["errors"].append(f"Actuator {actuator_id} on: {e!s}")
        logger.error("Failed to activate schedule for actuator %s: %s", actuator_id, e)
        return False


def _handle_schedule_deactivation(
    scheduling_service,
    actuator_service,
    schedule,
    actuator_id: int,
    results: dict,
) -> bool:
    """Handle transition from active to inactive state."""
    try:
        if scheduling_service:
            result = scheduling_service.execute_with_retry(
                schedule,
                activate=False,
                actuator_manager=actuator_service,
            )
            if result.success:
                results["transitions"] += 1
                logger.info(
                    "Schedule %s (%s) deactivated -> actuator %s OFF",
                    schedule.schedule_id,
                    schedule.device_type,
                    actuator_id,
                )
                return True
            else:
                results["errors"].append(f"Actuator {actuator_id} off: {result.error_message}")
            return False

        actuator_service.turn_off(actuator_id)
        results["transitions"] += 1
        logger.info(
            "Schedule %s (%s) deactivated -> actuator %s OFF",
            schedule.schedule_id,
            schedule.device_type,
            actuator_id,
        )
        return True
    except TASK_SOFT_ERRORS as e:
        results["errors"].append(f"Actuator {actuator_id} off: {e!s}")
        logger.error("Failed to deactivate schedule for actuator %s: %s", actuator_id, e)
        return False


# ==================== ML Namespace Tasks ====================


def ml_drift_check_task(container: "ServiceContainer") -> dict[str, Any]:
    """
    Check for model drift and trigger retraining if needed.

    This task runs hourly to:
    - Check drift metrics for all ML models
    - Trigger retraining if drift exceeds threshold
    - Check scheduled retraining jobs

    Celery name: ml.drift_check
    """
    retraining_service = getattr(container, "automated_retraining", None)
    if not retraining_service:
        return {"status": "retraining_service_not_available"}

    results = {
        "drift_checks": 0,
        "retraining_triggered": 0,
        "scheduled_runs": 0,
        "errors": [],
    }

    try:
        now = datetime.now()

        # Check drift triggers
        try:
            drift_events = retraining_service.check_drift_triggers()
            results["drift_checks"] = len(retraining_service.jobs)
            results["retraining_triggered"] = len(drift_events)
        except TASK_SOFT_ERRORS as e:
            results["errors"].append(f"Drift check: {e!s}")
            logger.error("Error checking drift triggers: %s", e)

        # Check scheduled jobs
        for job in list(retraining_service.jobs.values()):
            if not job.enabled:
                continue

            try:
                if job.next_run and now >= job.next_run:
                    from app.services.ai.automated_retraining import RetrainingTrigger

                    logger.info("Triggering scheduled retraining job: %s", job.job_id)
                    retraining_service.trigger_retraining(
                        model_type=job.model_type,
                        trigger=RetrainingTrigger.SCHEDULED,
                        job_id=job.job_id,
                    )
                    results["scheduled_runs"] += 1
            except TASK_SOFT_ERRORS as e:
                results["errors"].append(f"Job {job.job_id}: {e!s}")
                logger.error("Error triggering job %s: %s", job.job_id, e)

        if results["retraining_triggered"] > 0 or results["scheduled_runs"] > 0:
            logger.info(
                "ML drift check: %s drift-triggered, %s scheduled",
                results["retraining_triggered"],
                results["scheduled_runs"],
            )

    except TASK_SOFT_ERRORS as e:
        logger.error("ML drift check failed: %s", e, exc_info=True)
        results["errors"].append(str(e))

    return results


def ml_readiness_check_task(container: "ServiceContainer") -> dict[str, Any]:
    """
    Check ML model readiness and notify users when models are ready.

    This task runs daily to:
    - Check training data collection progress for each unit
    - Detect when models have enough data for activation
    - Send notifications to users about ready models

    Celery name: ml.readiness_check
    """
    results = {
        "units_checked": 0,
        "notifications_sent": 0,
        "models_notified": {},
        "errors": [],
    }

    try:
        # Get or create ML readiness monitor
        ml_monitor = getattr(container, "ml_readiness_monitor", None)

        if not ml_monitor:
            # Create on-the-fly if not in container
            from app.services.ai.ml_readiness_monitor import MLReadinessMonitorService
            from infrastructure.database.repositories.irrigation_ml import IrrigationMLRepository

            database = getattr(container, "database", None)
            if not database:
                return {"status": "database_not_available"}

            notifications_service = getattr(container, "notifications_service", None)
            ml_repo = IrrigationMLRepository(database)
            ml_monitor = MLReadinessMonitorService(
                irrigation_ml_repo=ml_repo,
                notifications_service=notifications_service,
            )

        # Check all units for ML readiness
        check_results = ml_monitor.check_all_units()

        results["units_checked"] = len(check_results)
        for unit_id, models in check_results.items():
            results["notifications_sent"] += len(models)
            results["models_notified"][unit_id] = models

        if results["notifications_sent"] > 0:
            logger.info(
                "ML readiness check: Sent %s notifications for %s units",
                results["notifications_sent"],
                results["units_checked"],
            )
        else:
            logger.debug("ML readiness check: No new models ready for activation")

    except TASK_SOFT_ERRORS as e:
        logger.error("ML readiness check failed: %s", e, exc_info=True)
        results["errors"].append(str(e))

    return results


# ==================== Plant Namespace Tasks (continued) ====================


def plant_harvest_readiness_task(container: "ServiceContainer") -> dict[str, Any]:
    """
    Check all plants for harvest readiness and send notifications.

    This task runs daily at 08:00 to:
    - Check if plants are nearing or past optimal harvest time
    - Send notifications to users about ready plants
    - Help prevent over-maturing and optimize harvest timing

    Notifications are sent:
    - 7 days before expected harvest
    - 3 days before expected harvest
    - On the expected harvest day
    - 3 days after expected harvest (overdue warning)

    Celery name: plant.harvest_readiness
    """
    results = {
        "plants_checked": 0,
        "notifications_sent": 0,
        "overdue_plants": 0,
        "errors": [],
    }

    try:
        plant_service = getattr(container, "plant_service", None)
        growth_service = getattr(container, "growth_service", None)
        notifications_service = getattr(container, "notifications_service", None)
        plant_catalog = getattr(container, "plant_catalog", None)

        if not all([plant_service, growth_service]):
            logger.debug("Plant or growth service not available - skipping harvest readiness check")
            return results

        # Get all unit runtimes
        runtimes = growth_service.get_unit_runtimes()

        for unit_id, runtime in runtimes.items():
            try:
                plants = plant_service.list_plants(unit_id)

                for plant in plants:
                    results["plants_checked"] += 1

                    try:
                        plant_dict = plant.to_dict() if hasattr(plant, "to_dict") else plant
                        plant_id = plant_dict.get("plant_id") or plant_dict.get("id")
                        plant_name = plant_dict.get("plant_name", f"Plant {plant_id}")
                        plant_type = plant_dict.get("plant_type")
                        current_stage = plant_dict.get("current_stage", "").lower()

                        # Get expected harvest period from catalog
                        harvest_weeks = None
                        if plant_catalog and plant_type:
                            try:
                                catalog_data = plant_catalog.get_plant_by_type(plant_type)
                                if catalog_data:
                                    yield_data = catalog_data.get("yield_data", {})
                                    harvest_weeks = yield_data.get("harvest_period_weeks")
                            except TASK_SOFT_ERRORS as exc:
                                logger.debug("Plant catalog lookup failed for '%s': %s", plant_type, exc)

                        # Default harvest periods by stage if not in catalog
                        if not harvest_weeks:
                            default_periods = {
                                "flowering": 8,
                                "fruiting": 10,
                                "ripening": 6,
                            }
                            harvest_weeks = default_periods.get(current_stage, 8)

                        # Calculate total days since planting
                        total_days = sum(
                            [
                                plant_dict.get("days_in_seedling") or 0,
                                plant_dict.get("days_in_vegetative") or 0,
                                plant_dict.get("days_in_flowering") or 0,
                                plant_dict.get("days_in_fruiting") or 0,
                            ]
                        )

                        expected_harvest_days = harvest_weeks * 7
                        days_until_harvest = expected_harvest_days - total_days

                        # Check if we should send a notification
                        notification_days = [7, 3, 0, -3]  # Days before/after harvest

                        if days_until_harvest in notification_days and notifications_service:
                            if days_until_harvest > 0:
                                title = "Harvest Reminder"
                                message = f"{plant_name} will be ready for harvest in {days_until_harvest} days"
                                severity = "info"
                            elif days_until_harvest == 0:
                                title = "Harvest Ready!"
                                message = f"{plant_name} is ready for harvest today!"
                                severity = "success"
                            else:
                                title = "Harvest Overdue"
                                message = f"{plant_name} is {abs(days_until_harvest)} days past optimal harvest time"
                                severity = "warning"
                                results["overdue_plants"] += 1

                            try:
                                notifications_service.create_notification(
                                    user_id=runtime.user_id if hasattr(runtime, "user_id") else 1,
                                    notification_type="harvest_ready",
                                    title=title,
                                    message=message,
                                    severity=severity,
                                    unit_id=unit_id,
                                    source_type="plant",
                                    source_id=plant_id,
                                )
                                results["notifications_sent"] += 1
                                logger.info("Harvest notification sent: %s", message)
                            except TASK_SOFT_ERRORS as e:
                                logger.warning("Failed to send harvest notification: %s", e)

                    except TASK_SOFT_ERRORS as e:
                        results["errors"].append(f"Plant {plant_id}: {e!s}")
                        logger.warning("Error checking harvest readiness for plant: %s", e)

            except TASK_SOFT_ERRORS as e:
                results["errors"].append(f"Unit {unit_id}: {e!s}")
                logger.warning("Error processing unit %s: %s", unit_id, e)

        if results["notifications_sent"] > 0:
            logger.info(
                "Harvest readiness check complete: %s notifications sent, %s overdue plants",
                results["notifications_sent"],
                results["overdue_plants"],
            )

    except TASK_SOFT_ERRORS as e:
        logger.error("Harvest readiness check failed: %s", e, exc_info=True)
        results["errors"].append(str(e))

    return results


# ==================== Maintenance Namespace Tasks ====================


def maintenance_aggregate_sensor_data_task(container: "ServiceContainer") -> dict[str, Any]:
    """
    Aggregate old sensor readings before they are pruned.

    This task runs daily at 02:30 (BEFORE the 03:00 prune task) to:
    - Create daily summaries (min, max, avg, count, stddev) for sensor readings
    - Target readings older than 25 days (will be pruned at 30 days)
    - Store summaries in SensorReadingSummary table
    - These summaries are preserved for harvest reports

    This is critical to preserve historical data for harvest reports after
    raw sensor readings are pruned for disk space savings.

    Celery name: maintenance.aggregate_sensor_data
    """
    results = {
        "summaries_created": 0,
        "days_aggregated": 0,
        "errors": [],
    }

    try:
        device_repo = getattr(container, "device_repo", None)
        config = getattr(container, "config", None)

        if not device_repo:
            logger.debug("Device repository not available - skipping sensor data aggregation")
            results["errors"].append("device_repo_unavailable")
            return results

        # Aggregate data older than (retention_days - 5) to ensure we catch it before pruning
        # Default: if retention is 30 days, aggregate anything older than 25 days
        sensor_retention_days = int(getattr(config, "sensor_retention_days", 30)) if config else 30
        aggregation_threshold = max(1, sensor_retention_days - 5)

        if hasattr(device_repo, "aggregate_readings_by_days_old"):
            summaries = device_repo.aggregate_readings_by_days_old(aggregation_threshold)
            results["summaries_created"] = summaries or 0

            if summaries > 0:
                logger.info(
                    "Aggregated %s sensor reading summaries (data older than %s days)",
                    summaries,
                    aggregation_threshold,
                )
            else:
                logger.debug("No sensor readings needed aggregation")
        else:
            logger.warning("Device repo does not support aggregate_readings_by_days_old")
            results["errors"].append("method_not_available")

    except TASK_SOFT_ERRORS as e:
        logger.error("Sensor data aggregation task failed: %s", e, exc_info=True)
        results["errors"].append(str(e))

    return results


def maintenance_prune_state_history_task(container: "ServiceContainer") -> dict[str, Any]:
    """
    Prune old actuator state history entries.

    This task runs daily at 02:15 to:
    - Delete old state history records
    - Keep database size manageable

    Celery name: maintenance.prune_state_history
    """
    prune_days = int(getattr(getattr(container, "config", None), "actuator_state_retention_days", 90))
    results = {
        "deleted_rows": 0,
        "prune_days": max(1, prune_days),
        "errors": [],
    }

    try:
        device_repo = getattr(container, "device_repo", None)
        if not device_repo:
            logger.debug("Device repository not available - skipping state history prune")
            return results

        # Prune old state history
        if hasattr(device_repo, "prune_actuator_state_history"):
            deleted = device_repo.prune_actuator_state_history(results["prune_days"])
            results["deleted_rows"] = deleted or 0
            logger.info(
                "Pruned %s actuator state rows older than %s days", results["deleted_rows"], results["prune_days"]
            )

    except TASK_SOFT_ERRORS as e:
        logger.error("State history prune failed: %s", e, exc_info=True)
        results["errors"].append(str(e))

    return results


def maintenance_prune_old_data_task(container: "ServiceContainer") -> dict[str, Any]:
    """
    Prune old sensor readings and actuator state history to prevent database bloat.

    This task runs daily at 03:00 to:
    - Delete sensor readings older than sensor_retention_days (default 30 days)
    - Delete actuator state history older than actuator_state_retention_days (default 90 days)
    - Run VACUUM weekly (on Sundays) to reclaim disk space

    This is critical for Raspberry Pi deployments to prevent disk space exhaustion.

    Celery name: maintenance.prune_old_data
    """
    results = {
        "sensor_readings_deleted": 0,
        "actuator_states_deleted": 0,
        "errors": [],
    }

    try:
        config = getattr(container, "config", None)
        device_repo = getattr(container, "device_repo", None)
        getattr(container, "database", None)

        if not device_repo:
            logger.debug("Device repository not available - skipping data prune")
            results["errors"].append("device_repo_unavailable")
            return results

        # Get retention settings from config
        sensor_retention_days = int(getattr(config, "sensor_retention_days", 30)) if config else 30
        actuator_retention_days = int(getattr(config, "actuator_state_retention_days", 90)) if config else 90

        # Prune sensor readings
        if hasattr(device_repo, "prune_sensor_readings"):
            deleted = device_repo.prune_sensor_readings(sensor_retention_days)
            results["sensor_readings_deleted"] = deleted or 0
            if deleted:
                logger.info("Pruned %s sensor readings older than %s days", deleted, sensor_retention_days)

        # Prune actuator state history
        if hasattr(device_repo, "prune_actuator_state_history"):
            deleted = device_repo.prune_actuator_state_history(actuator_retention_days)
            results["actuator_states_deleted"] = deleted or 0
            if deleted:
                logger.info("Pruned %s actuator state records older than %s days", deleted, actuator_retention_days)

        # Note: VACUUM now runs as a separate scheduled task (maintenance.vacuum_database)
        # at 04:00 on Sundays to reclaim disk space after pruning

        total_deleted = results["sensor_readings_deleted"] + results["actuator_states_deleted"]
        if total_deleted > 0:
            logger.info(
                "Data pruning complete: %s sensor readings, %s actuator states deleted",
                results["sensor_readings_deleted"],
                results["actuator_states_deleted"],
            )

    except TASK_SOFT_ERRORS as e:
        logger.error("Data pruning task failed: %s", e, exc_info=True)
        results["errors"].append(str(e))

    return results


def maintenance_purge_old_alerts_task(container: "ServiceContainer") -> dict[str, Any]:
    """
    Purge old alerts from the database.

    Uses container.alert_service if available. Configurable retention via
    container.config.alert_retention_days (default 30).
    """
    alert_service = getattr(container, "alert_service", None)

    results = {"deleted_rows": 0, "success": False, "errors": []}

    if not alert_service:
        logger.debug("AlertService not available - skipping purge_old_alerts task")
        results["success"] = False
        results["errors"].append("alert_service_unavailable")
        return results

    try:
        retention_days = int(getattr(getattr(container, "config", None), "alert_retention_days", 30))
        resolved_only = bool(getattr(getattr(container, "config", None), "purge_resolved_only", True))

        resp = alert_service.purge_old_alerts(retention_days=retention_days, resolved_only=resolved_only)
        if resp.get("success"):
            results["deleted_rows"] = int(resp.get("deleted_rows", 0))
            results["success"] = True
        else:
            results["success"] = False
            results["errors"].append(resp.get("error", "unknown"))

    except TASK_SOFT_ERRORS as e:
        logger.error("Failed to run purge_old_alerts task: %s", e)
        results["success"] = False
        results["errors"].append(str(e))

    return results


def maintenance_vacuum_database_task(container: "ServiceContainer") -> dict[str, Any]:
    """
    Run SQLite VACUUM to reclaim disk space after data pruning.

    This task runs weekly (typically Sundays at 04:00) to:
    - Reclaim disk space after sensor/actuator data pruning
    - Optimize database performance
    - Rebuild internal indexes

    IMPORTANT: VACUUM requires exclusive database access and can take time
    on large databases. Schedule during low-activity periods.

    Celery name: maintenance.vacuum_database
    """
    results = {
        "vacuum_run": False,
        "db_size_before_mb": None,
        "db_size_after_mb": None,
        "space_reclaimed_mb": None,
        "errors": [],
    }

    try:
        import os

        database = getattr(container, "database", None)
        config = getattr(container, "config", None)

        if not database:
            logger.debug("Database not available - skipping VACUUM")
            results["errors"].append("database_unavailable")
            return results

        # Get database path for size measurement
        db_path = getattr(config, "database_path", "database/sysgrow.db") if config else "database/sysgrow.db"

        # Measure size before VACUUM
        try:
            if os.path.exists(db_path):
                results["db_size_before_mb"] = round(os.path.getsize(db_path) / (1024 * 1024), 2)
        except (OSError, TypeError, ValueError) as e:
            logger.warning("Could not measure database size: %s", e)

        # Run VACUUM
        try:
            db = database.get_db()
            logger.info("Starting database VACUUM (this may take a moment)...")
            db.execute("VACUUM")
            results["vacuum_run"] = True
            logger.info("Database VACUUM completed successfully")
        except TASK_SOFT_ERRORS as e:
            results["errors"].append(f"vacuum_failed: {e!s}")
            logger.error("VACUUM failed: %s", e)
            return results

        # Measure size after VACUUM
        try:
            if os.path.exists(db_path):
                results["db_size_after_mb"] = round(os.path.getsize(db_path) / (1024 * 1024), 2)
                if results["db_size_before_mb"] is not None:
                    results["space_reclaimed_mb"] = round(results["db_size_before_mb"] - results["db_size_after_mb"], 2)
                    if results["space_reclaimed_mb"] > 0:
                        logger.info(
                            "VACUUM reclaimed %s MB (before: %s MB, after: %s MB)",
                            results["space_reclaimed_mb"],
                            results["db_size_before_mb"],
                            results["db_size_after_mb"],
                        )
        except (OSError, TypeError, ValueError) as e:
            logger.warning("Could not measure database size after VACUUM: %s", e)

    except TASK_SOFT_ERRORS as e:
        logger.error("VACUUM task failed: %s", e, exc_info=True)
        results["errors"].append(str(e))

    return results


def maintenance_system_health_check_task(container: "ServiceContainer") -> dict[str, Any]:
    """
    Perform system health checks and create alerts.

    This task runs every 5 minutes to:
    - Check storage usage
    - Check database health
    - Create alerts for critical issues

    Celery name: maintenance.system_health_check
    """
    results = {
        "storage_checked": False,
        "database_checked": False,
        "alerts_created": 0,
        "errors": [],
    }

    try:
        system_health_service = getattr(container, "system_health_service", None)
        database = getattr(container, "database", None)

        if not system_health_service:
            return results

        # Refresh storage usage
        try:
            system_health_service.refresh_storage_usage()
            results["storage_checked"] = True
        except TASK_SOFT_ERRORS as e:
            results["errors"].append(f"Storage check: {e!s}")
            logger.warning("Storage check failed: %s", e)

        # Check database health
        if database:
            try:
                system_health_service.check_database_health(database)
                results["database_checked"] = True
            except TASK_SOFT_ERRORS as e:
                results["errors"].append(f"Database check: {e!s}")
                logger.warning("Database check failed: %s", e)

        # Check and create alerts
        try:
            alert_ids = system_health_service.check_and_alert_on_health_issues()
            results["alerts_created"] = len(alert_ids) if alert_ids else 0

            if results["alerts_created"] > 0:
                logger.warning("Health check created %s alerts", results["alerts_created"])
            else:
                logger.debug("Health check complete - no issues detected")

        except TASK_SOFT_ERRORS as e:
            results["errors"].append(f"Alert check: {e!s}")
            logger.warning("Alert check failed: %s", e)

    except TASK_SOFT_ERRORS as e:
        logger.error("System health check failed: %s", e, exc_info=True)
        results["errors"].append(str(e))

    return results


# ==================== Task Registration ====================


def register_all_tasks(
    scheduler: "UnifiedScheduler",
    container: "ServiceContainer",
) -> None:
    """
    Register all tasks with the unified scheduler.

    This should be called once during application startup.

    Args:
        scheduler: UnifiedScheduler instance
        container: ServiceContainer with all services
    """
    logger.info("Registering scheduled tasks...")

    def bind_noargs(task_fn):
        @wraps(task_fn)
        def bound_task():
            try:
                return task_fn(container)
            # Intentional broad catch: this wrapper executes arbitrary scheduled task callables.
            except Exception as e:
                logger.exception("Scheduled task %s raised: %s", task_fn.__name__, e)
                # Surface an alert if AlertService available
                try:
                    alert_svc = getattr(container, "alert_service", None)
                    if alert_svc:
                        alert_svc.create_alert(
                            alert_type=alert_svc.SYSTEM_ERROR,
                            severity=alert_svc.CRITICAL,
                            title=f"Scheduled task failure: {task_fn.__name__}",
                            message=str(e),
                            dedupe=True,
                            dedupe_key=f"scheduled_task:{task_fn.__name__}",
                        )
                except TASK_SOFT_ERRORS as alert_exc:
                    logger.debug("Failed to create alert for scheduled task failure: %s", alert_exc)
                # Re-raise to let scheduler record failure in history as well
                raise

        return bound_task

    # Register task functions
    try:
        scheduler.register_task("plant.grow", bind_noargs(plant_grow_task))
        scheduler.register_task("plant.health_check", bind_noargs(plant_health_check_task))
        scheduler.register_task("plant.harvest_readiness", bind_noargs(plant_harvest_readiness_task))
        scheduler.register_task("actuator.startup_sync", bind_noargs(actuator_startup_sync_task))
        scheduler.register_task("actuator.schedule_check", bind_noargs(actuator_schedule_check_task))
        # Device health check (delegates to DeviceHealthService.check_all_devices_health_and_alert)
        scheduler.register_task(
            "device.health_check",
            bind_noargs(
                lambda c: (
                    getattr(c, "device_health_service", None)
                    and c.device_health_service.check_all_devices_health_and_alert()
                )
            ),
        )
        scheduler.register_task("ml.drift_check", bind_noargs(ml_drift_check_task))
        scheduler.register_task("ml.readiness_check", bind_noargs(ml_readiness_check_task))
        scheduler.register_task(
            "maintenance.aggregate_sensor_data", bind_noargs(maintenance_aggregate_sensor_data_task)
        )
        scheduler.register_task("maintenance.prune_state_history", bind_noargs(maintenance_prune_state_history_task))
        scheduler.register_task("maintenance.prune_old_data", bind_noargs(maintenance_prune_old_data_task))
        scheduler.register_task("maintenance.system_health_check", bind_noargs(maintenance_system_health_check_task))
        scheduler.register_task("maintenance.vacuum_database", bind_noargs(maintenance_vacuum_database_task))
        # Purge old alerts task
        scheduler.register_task(
            "maintenance.purge_old_alerts", bind_noargs(lambda c: maintenance_purge_old_alerts_task(c))
        )
    except TASK_SOFT_ERRORS:
        # If AlertService not available at registration time, skip registration (will log at runtime)
        logger.debug("AlertService not available for task registration: maintenance.purge_old_alerts")

    logger.info("Registered %s tasks", len(scheduler._tasks))


def schedule_default_jobs(scheduler: "UnifiedScheduler") -> None:
    """
    Schedule default jobs with standard timing.

    Call this after register_all_tasks() to set up default schedules.

    Args:
        scheduler: UnifiedScheduler instance
    """
    logger.info("Scheduling default jobs...")

    # Plant namespace
    scheduler.schedule_daily(
        "plant.grow",
        time_of_day="00:00",
        job_id="plant_grow_daily",
    )

    scheduler.schedule_daily(
        "plant.health_check",
        time_of_day="09:00",
        job_id="plant_health_check_daily",
    )

    # Harvest readiness check - daily at 08:00 to notify users about harvest timing
    scheduler.schedule_daily(
        "plant.harvest_readiness",
        time_of_day="08:00",
        job_id="plant_harvest_readiness_daily",
    )

    # Actuator namespace - startup sync runs once at startup
    scheduler.run_now("actuator.startup_sync")

    # Actuator namespace - schedule check every 30 seconds
    scheduler.schedule_interval(
        "actuator.schedule_check",
        interval_seconds=30,
        job_id="actuator_schedule_check",
        start_immediately=False,  # Startup sync handles initial state
    )

    # ML namespace - hourly
    scheduler.schedule_interval(
        "ml.drift_check",
        interval_seconds=3600,
        job_id="ml_drift_check_hourly",
    )

    # ML readiness check - daily at 10:00 to notify users when models are ready
    scheduler.schedule_daily(
        "ml.readiness_check",
        time_of_day="10:00",
        job_id="ml_readiness_check_daily",
    )

    # Device health checks - every 10 minutes by default
    scheduler.schedule_interval(
        "device.health_check",
        interval_seconds=600,
        job_id="device_health_check_10min",
        start_immediately=True,
    )

    # Maintenance namespace
    scheduler.schedule_daily(
        "maintenance.prune_state_history",
        time_of_day="02:15",
        job_id="maintenance_prune_daily",
    )

    # Aggregate sensor data daily at 02:30 BEFORE pruning
    # Creates daily summaries (min, max, avg) for harvest reports
    # Critical: must run BEFORE prune_old_data to preserve historical data
    scheduler.schedule_daily(
        "maintenance.aggregate_sensor_data",
        time_of_day="02:30",
        job_id="maintenance_aggregate_sensor_data_daily",
    )

    # Prune old sensor readings and actuator states daily at 03:00
    # Critical for Raspberry Pi to prevent database bloat
    # Note: runs AFTER aggregate_sensor_data to preserve summaries
    scheduler.schedule_daily(
        "maintenance.prune_old_data",
        time_of_day="03:00",
        job_id="maintenance_prune_old_data_daily",
    )

    # Purge old alerts daily at 03:30 by default
    scheduler.schedule_daily(
        "maintenance.purge_old_alerts",
        time_of_day="03:30",
        job_id="maintenance_purge_old_alerts_daily",
    )

    # VACUUM database weekly on Sundays at 04:00
    # Reclaims disk space after pruning tasks complete
    # Critical for Raspberry Pi to prevent database file growth
    scheduler.schedule_weekly(
        "maintenance.vacuum_database",
        day_of_week=6,  # Sunday
        time_of_day="04:00",
        job_id="maintenance_vacuum_weekly",
    )

    scheduler.schedule_interval(
        "maintenance.system_health_check",
        interval_seconds=300,  # 5 minutes
        job_id="maintenance_health_check",
        start_immediately=True,
    )

    jobs = scheduler.get_jobs()
    logger.info("Scheduled %s default jobs", len(jobs))

    for job in jobs:
        logger.debug("  - %s: %s (%s)", job.job_id, job.schedule_type.value, job.namespace)


def configure_scheduler(
    scheduler: "UnifiedScheduler",
    container: "ServiceContainer",
    *,
    reset_jobs: bool = True,
    start: bool = True,
) -> None:
    """Register tasks, apply default schedules, and optionally start the scheduler."""
    if reset_jobs:
        scheduler.clear_jobs()

    register_all_tasks(scheduler, container)
    schedule_default_jobs(scheduler)

    if start:
        scheduler.start()
