"""Dashboard API  (thin routes)
================================

Route handlers for dashboard endpoints.  All business logic lives in
:class:`~app.services.application.dashboard_service.DashboardService`.
These handlers are responsible only for:

* Parsing HTTP request parameters and session state
* Calling the corresponding service method
* Wrapping results in the standard ``_success`` / ``_fail`` envelope
"""

import logging
from datetime import timedelta

from flask import Blueprint, Response, current_app, request, session

from app.blueprints.api._common import (
    fail as _fail,
    parse_datetime,
    success as _success,
)
from app.utils.http import safe_route
from app.utils.time import utc_now

dashboard_api = Blueprint("dashboard_api", __name__)
logger = logging.getLogger(__name__)


# ── helpers (HTTP-layer only) ─────────────────────────────────────────


def _resolve_unit_id() -> int | None:
    """Read unit_id from query-string or session."""
    uid = request.args.get("unit_id", type=int)
    if uid is not None:
        return uid
    raw = session.get("selected_unit")
    try:
        return int(raw) if raw is not None else None
    except (TypeError, ValueError):
        return None


def _get_service():
    """Lazy-access the DashboardService from the container."""
    container = current_app.config.get("CONTAINER")
    if not container:
        return None
    svc = getattr(container, "_dashboard_service", None)
    if svc is None:
        try:
            from app.services.application.dashboard_service import DashboardService
        except Exception as exc:
            logger.debug("DashboardService import unavailable; using legacy summary fallback: %s", exc)
            return None

        try:
            svc = DashboardService(container)
            container._dashboard_service = svc  # cache on container
        except Exception as exc:
            logger.debug("DashboardService initialization failed; using legacy summary fallback: %s", exc)
            return None
    return svc


def _is_device_active(device: dict) -> bool:
    """Best-effort active-state coercion for mixed historical payload formats."""
    raw = device.get("is_active")
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, int | float):
        return raw != 0
    if isinstance(raw, str):
        value = raw.strip().lower()
        if value in {"1", "true", "yes", "on", "active", "connected", "enabled"}:
            return True
        if value in {"0", "false", "no", "off", "inactive", "disconnected", "disabled"}:
            return False
    return str(device.get("status", "")).strip().lower() in {
        "active",
        "on",
        "connected",
        "enabled",
        "healthy",
    }


def _build_snapshot_or_analytics(container, selected_unit_id: int | None):
    """Legacy helper kept for route-level compatibility tests."""
    analytics = getattr(container, "analytics_service", None)
    if not analytics:
        return {}, {}, None
    try:
        current = analytics.get_latest_sensor_reading(unit_id=selected_unit_id) or {}
    except Exception:
        current = {}
    return current, {}, None


def _build_plants_summary(container, selected_unit_id, growth_service, plant_health_scorer):
    """Legacy helper kept for route-level compatibility tests."""
    if not growth_service or selected_unit_id is None:
        return [], None, None
    try:
        unit = growth_service.get_unit(selected_unit_id)
        plants = unit.get("plants", []) if isinstance(unit, dict) else []
        current_plant = plants[0] if plants else None
        return plants, current_plant, None
    except Exception:
        return [], None, None


def _build_alerts_summary(container, selected_unit_id):
    """Legacy helper kept for route-level compatibility tests."""
    return {"count": 0, "recent": [], "critical": 0, "warning": 0}


def _build_devices_summary(container, selected_unit_id):
    """Return sensors/actuators plus active/total device counters."""
    sensor_service = getattr(container, "sensor_management_service", None)
    actuator_service = getattr(container, "actuator_management_service", None)

    sensors = []
    actuators = []

    try:
        if sensor_service:
            sensors = sensor_service.list_sensors(unit_id=selected_unit_id) or []
    except Exception:
        sensors = []

    try:
        if actuator_service:
            actuators = actuator_service.list_actuators(unit_id=selected_unit_id) or []
    except Exception:
        actuators = []

    total_devices = len(sensors) + len(actuators)
    active_devices = sum(1 for sensor in sensors if isinstance(sensor, dict) and _is_device_active(sensor))
    active_devices += sum(1 for actuator in actuators if isinstance(actuator, dict) and _is_device_active(actuator))

    return sensors, actuators, {"active": active_devices, "total": total_devices}


def _build_system_summary(container, summary):
    """Legacy helper kept for route-level compatibility tests."""
    return summary.get("system", {}) if isinstance(summary, dict) else {}


def _build_unit_settings_summary(container, growth_service, selected_unit_id, sensors=None, actuators=None):
    """Legacy helper kept for route-level compatibility tests."""
    return {"unit_id": selected_unit_id, "sensors": sensors or [], "actuators": actuators or []}


def _build_legacy_dashboard_summary(container, selected_unit_id: int | None) -> dict:
    """Build dashboard summary using legacy helper contract."""
    growth_service = getattr(container, "growth_service", None)
    plant_health_scorer = getattr(container, "plant_health_scorer", None)

    snapshot_data, analytics_data, predictions = _build_snapshot_or_analytics(container, selected_unit_id)
    plants, current_plant, growth_stages = _build_plants_summary(
        container, selected_unit_id, growth_service, plant_health_scorer
    )
    alerts_summary = _build_alerts_summary(container, selected_unit_id)
    sensors, actuators, devices_summary = _build_devices_summary(container, selected_unit_id)

    summary = {
        "snapshot": snapshot_data,
        "analytics": analytics_data,
        "predictions": predictions,
        "plants": plants,
        "current_plant": current_plant,
        "growth_stages": growth_stages,
        "alerts": alerts_summary,
        "sensors": sensors,
        "actuators": actuators,
        "devices": devices_summary,
    }
    summary["system"] = _build_system_summary(container, summary)
    summary["unit_settings"] = _build_unit_settings_summary(
        container,
        growth_service,
        selected_unit_id,
        sensors=sensors,
        actuators=actuators,
    )
    return summary


# ── routes ────────────────────────────────────────────────────────────


@dashboard_api.get("/sensors/current")
@safe_route("Failed to get sensor data")
def get_current_sensor_data() -> Response:
    """Get current sensor readings for dashboard display."""
    try:
        svc = _get_service()
        if not svc:
            return _fail("Container unavailable", 503)
        unit_id = _resolve_unit_id()
        return _success(svc.get_current_sensor_data(unit_id))
    except RuntimeError as exc:
        return _fail(str(exc), 503)


@dashboard_api.get("/timeseries")
@safe_route("Failed to fetch timeseries")
def get_timeseries() -> Response:
    """Return decoded sensor readings for charts (optionally filtered)."""
    try:
        svc = _get_service()
        if not svc:
            return _fail("Container unavailable", 503)

        now = utc_now()
        hours = request.args.get("hours", type=int)
        end_param = request.args.get("end")
        start_param = request.args.get("start")

        end_dt = parse_datetime(end_param, now)
        start_default = end_dt - timedelta(hours=hours or 24)
        start_dt = parse_datetime(start_param, start_default)

        if start_dt >= end_dt:
            return _fail("start must be before end", 400)

        return _success(
            svc.get_timeseries(
                start_dt,
                end_dt,
                unit_id=request.args.get("unit_id", type=int),
                sensor_id=request.args.get("sensor_id", type=int),
                limit=request.args.get("limit", default=500, type=int),
                hours=hours,
            )
        )
    except ValueError as exc:
        return _fail(str(exc), 400)
    except RuntimeError as exc:
        return _fail(str(exc), 503)


@dashboard_api.get("/actuators/recent-state")
@safe_route("Failed to get recent actuator state")
def get_recent_actuator_state() -> Response:
    """Return last N actuator state transitions for dashboard tile."""
    svc = _get_service()
    if not svc:
        return _fail("Container unavailable", 503)
    return _success(
        svc.get_recent_actuator_state(
            unit_id=request.args.get("unit_id", type=int),
            limit=request.args.get("limit", default=20, type=int),
        )
    )


@dashboard_api.get("/connectivity/recent")
@safe_route("Failed to get connectivity events")
def get_recent_connectivity() -> Response:
    """Return last N connectivity events for dashboard tile."""
    svc = _get_service()
    if not svc:
        return _fail("Container unavailable", 503)
    return _success(
        svc.get_recent_connectivity(
            connection_type=request.args.get("connection_type"),
            limit=request.args.get("limit", default=20, type=int),
        )
    )


@dashboard_api.get("/status")
@safe_route("Failed to get system status")
def get_system_status() -> Response:
    """Get overall system status for dashboard header."""
    svc = _get_service()
    if not svc:
        return _fail("Container unavailable", 503)
    return _success(svc.get_system_status())


@dashboard_api.get("/summary")
@safe_route("Failed to get dashboard summary")
def get_dashboard_summary() -> Response:
    """Get comprehensive dashboard summary – aggregated data for the main dashboard."""
    unit_id = _resolve_unit_id()
    svc = _get_service()
    if svc:
        return _success(svc.get_summary(unit_id))

    container = current_app.config.get("CONTAINER")
    if not container:
        return _fail("Container unavailable", 503)
    return _success(_build_legacy_dashboard_summary(container, unit_id))


@dashboard_api.get("/growth-stage")
@safe_route("Failed to get growth stage")
def get_growth_stage() -> Response:
    """Get growth stage progress details for the selected unit."""
    try:
        svc = _get_service()
        if not svc:
            return _fail("Container unavailable", 503)
        return _success(svc.get_growth_stage_info(_resolve_unit_id()))
    except RuntimeError as exc:
        return _fail(str(exc), 503)


@dashboard_api.get("/harvest-timeline")
@safe_route("Failed to get harvest timeline")
def get_harvest_timeline() -> Response:
    """Get upcoming harvests and the most recent harvest for the selected unit."""
    try:
        svc = _get_service()
        if not svc:
            return _fail("Container unavailable", 503)
        return _success(svc.get_harvest_timeline(_resolve_unit_id()))
    except RuntimeError as exc:
        return _fail(str(exc), 503)


@dashboard_api.get("/water-schedule")
@safe_route("Failed to get water schedule")
def get_water_schedule() -> Response:
    """Get watering and feeding schedule overview for the selected unit."""
    try:
        svc = _get_service()
        if not svc:
            return _fail("Container unavailable", 503)
        return _success(svc.get_water_schedule(_resolve_unit_id()))
    except RuntimeError as exc:
        return _fail(str(exc), 503)


@dashboard_api.get("/irrigation-status")
@safe_route("Failed to get irrigation status")
def get_irrigation_status() -> Response:
    """Get recent irrigation activity and current soil moisture for the selected unit."""
    svc = _get_service()
    if not svc:
        return _fail("Container unavailable", 503)
    return _success(svc.get_irrigation_status(_resolve_unit_id()))
