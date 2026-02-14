"""Dashboard API 
===================
"""
from flask import Blueprint, request, current_app, session
from datetime import datetime, timedelta, timezone
from app.domain.agronomics import infer_gdd_base_temp_c
from app.utils.psychrometrics import calculate_vpd_kpa
from app.utils.time import iso_now
import logging
from typing import List, Dict, Any, Optional, Tuple

from app.blueprints.api._common import (
    get_scheduling_service,
    success as _success,
    fail as _fail,
    ensure_utc as _ensure_utc,
    parse_datetime,
    coerce_datetime as _coerce_datetime,
    get_plant_service,
    get_growth_service,
)

logger = logging.getLogger(__name__)

# Create blueprint for dashboard API
dashboard_api = Blueprint('dashboard_api', __name__, url_prefix='/api/dashboard')

CACHE_TTL_SECONDS = 30
_timeseries_cache: Dict[Tuple[str, str, Optional[int], Optional[int], Optional[int], Optional[int]], Dict[str, Any]] = {}


def _parse_iso8601(value: Optional[str], fallback: datetime) -> datetime:
    """Parse ISO 8601 datetime - wraps common parse_datetime."""
    return parse_datetime(value, fallback)


def _downsample(rows: List[Dict[str, Any]], target: int) -> List[Dict[str, Any]]:
    if not target or len(rows) <= target:
        return rows
    stride = max(1, len(rows) // target)
    return rows[::stride][:target]


def _cache_key(start: datetime, end: datetime, unit_id: Optional[int], sensor_id: Optional[int], limit: Optional[int], hours: Optional[int]):
    return (
        start.isoformat(),
        end.isoformat(),
        unit_id,
        sensor_id,
        limit,
        hours,
    )


def _build_snapshot_or_analytics(container, selected_unit_id):
    """Return a tuple (sensors_dict, vpd_dict, energy_row) by preferring
    live MQTT snapshot and falling back to analytics service. Logs debug on
    exceptions and returns sensible defaults.
    """
    try:
        snapshot = None
        try:
            mqtt_service = getattr(container, "mqtt_sensor_service", None)
            processor = getattr(mqtt_service, "processor", None) if mqtt_service else None
            if processor and selected_unit_id is not None:
                snapshot = processor.get_dashboard_snapshot(unit_id=selected_unit_id)
        except Exception as exc:
            logger.debug("Failed to build live dashboard snapshot: %s", exc)
            snapshot = None

        analytics_service = getattr(container, "analytics_service", None)
        latest = None
        energy_row = None
        if analytics_service:
            try:
                if snapshot is None:
                    latest = analytics_service.get_latest_sensor_reading(unit_id=selected_unit_id)
                    logger.debug(f"Latest sensor data for unit {selected_unit_id}: {latest}")
            except Exception as db_error:
                logger.debug("Analytics service get_latest_sensor_reading failed: %s", db_error)
                latest = None
            try:
                energy_row = analytics_service.get_latest_energy_reading()
            except Exception as db_error:
                logger.debug("Analytics service get_latest_energy_reading failed: %s", db_error)
                energy_row = None

        # Build sensor payloads depending on source
        try:
            if snapshot is not None:
                metrics = getattr(snapshot, 'metrics', None) or {}
                timestamp = getattr(snapshot, 'timestamp', None) or iso_now()
                sensors = {
                    'temperature': _snap_metric_from_metrics(metrics, 'temperature', '°C', 'temperature', timestamp, container),
                    'humidity': _snap_metric_from_metrics(metrics, 'humidity', '%', 'humidity', timestamp, container),
                    'soil_moisture': _snap_metric_from_metrics(metrics, 'soil_moisture', '%', 'soil_moisture', timestamp, container, trend='up'),
                    'co2': _snap_metric_from_metrics(metrics, 'co2', 'ppm', 'co2', timestamp, container),
                    'lux': _snap_metric_from_metrics(metrics, 'lux', 'lux', 'lux', timestamp, container),
                    'energy_usage': _build_energy_metric(energy_row),
                }

                temp_m = metrics.get('temperature')
                hum_m = metrics.get('humidity')
                if temp_m and hum_m:
                    analytics_service = getattr(container, "analytics_service", None)
                    if analytics_service:
                        try:
                            vpd = analytics_service.calculate_vpd_with_zones(
                                getattr(temp_m, 'value', None),
                                getattr(hum_m, 'value', None)
                            )
                        except Exception as exc:
                            logger.debug("Analytics vpd calculation failed: %s", exc)
                            vpd = _calculate_vpd(getattr(temp_m, 'value', None), getattr(hum_m, 'value', None))
                    else:
                        vpd = _calculate_vpd(getattr(temp_m, 'value', None), getattr(hum_m, 'value', None))
                else:
                    vpd = {}

                return sensors, vpd, energy_row

            if latest is not None:
                sensors = {
                    'temperature': _build_metric(latest, 'temperature', '°C', 'temperature'),
                    'humidity': _build_metric(latest, 'humidity', '%', 'humidity'),
                    'soil_moisture': _build_metric(latest, 'soil_moisture', '%', 'soil_moisture', trend='up'),
                    'co2': _build_metric(latest, 'co2', 'ppm', 'co2'),
                    'lux': _build_metric(latest, 'lux', 'lux', 'lux'),
                    'energy_usage': _build_energy_metric(energy_row),
                }
                analytics_service = getattr(container, "analytics_service", None)
                if analytics_service:
                    try:
                        vpd = analytics_service.calculate_vpd_with_zones(
                            latest.get('temperature'),
                            latest.get('humidity')
                        )
                    except Exception as exc:
                        logger.debug("Analytics vpd calculation failed: %s", exc)
                        vpd = _calculate_vpd(latest.get('temperature'), latest.get('humidity'))
                else:
                    vpd = _calculate_vpd(latest.get('temperature'), latest.get('humidity'))
                return sensors, vpd, energy_row

        except Exception as exc:
            logger.debug("Failed building snapshot or analytics sensors/vpd: %s", exc)
            return {}, {}, energy_row

        # No data available
        return {}, {}, energy_row
    except Exception as exc:
        logger.debug("Unhandled error in _build_snapshot_or_analytics: %s", exc)
        return {}, {}, None


def _build_unit_settings_summary(container, growth_service, selected_unit_id, sensors=None, actuators=None):
    """Build thresholds, schedules and configured device summaries for a unit.

    Accepts optional raw `sensors` and `actuators` lists (may be empty).
    """
    try:
        thresholds_payload = growth_service.get_thresholds(selected_unit_id) or {}
        thresholds = {
            "temperature_threshold": thresholds_payload.get("temperature_threshold"),
            "humidity_threshold": thresholds_payload.get("humidity_threshold"),
            "co2_threshold": thresholds_payload.get("co2_threshold"),
            "voc_threshold": thresholds_payload.get("voc_threshold"),
            "lux_threshold": thresholds_payload.get("lux_threshold"),
            "air_quality_threshold": thresholds_payload.get(
                "air_quality_threshold", thresholds_payload.get("aqi_threshold")
            ),
        }

        schedules_summary = {}
        try:
            scheduling_service = get_scheduling_service()
        except Exception as exc:
            scheduling_service = None
            logger.debug("Scheduling service unavailable for dashboard summary: %s", exc)

        if scheduling_service:
            try:
                schedules = scheduling_service.get_schedules_for_unit(selected_unit_id)
            except Exception as exc:
                logger.warning(
                    "Error fetching schedules for unit %s: %s",
                    selected_unit_id,
                    exc,
                )
                schedules = []

            if schedules:
                by_device = {}
                for schedule in schedules:
                    device_type = schedule.device_type or "device"
                    by_device.setdefault(device_type, []).append(schedule)

                for device_type, device_schedules in by_device.items():
                    device_schedules.sort(
                        key=lambda s: (
                            0 if s.enabled else 1,
                            -(getattr(s, "priority", 0) or 0),
                            getattr(s, "schedule_id", 0) or 0,
                        )
                    )
                    schedules_summary[device_type] = []
                    for schedule in device_schedules:
                        payload = schedule.to_dict() if hasattr(schedule, "to_dict") else dict(schedule)
                        schedules_summary[device_type].append({
                            "schedule_id": payload.get("schedule_id"),
                            "name": payload.get("name"),
                            "schedule_type": payload.get("schedule_type"),
                            "start_time": payload.get("start_time"),
                            "end_time": payload.get("end_time"),
                            "enabled": payload.get("enabled"),
                            "priority": payload.get("priority"),
                        })

        sensors = sensors or []
        actuators = actuators or []

        sensors_list = [
            {
                "sensor_id": s.get("sensor_id") or s.get("id"),
                "name": s.get("name") or s.get("sensor_name") or "Sensor",
                "sensor_type": s.get("sensor_type") or s.get("type") or "unknown",
                "protocol": s.get("protocol"),
                "model": s.get("model"),
                "is_active": s.get("is_active", True),
            }
            for s in sensors
        ]

        actuators_list = [
            {
                "actuator_id": a.get("actuator_id") or a.get("id"),
                "name": a.get("name") or "Actuator",
                "actuator_type": a.get("actuator_type") or a.get("type") or "unknown",
                "protocol": a.get("protocol"),
                "model": a.get("model"),
                "is_active": a.get("is_active", True),
            }
            for a in actuators
        ]

        return {
            "thresholds": thresholds,
            "schedules": schedules_summary,
            "sensors": sensors_list,
            "actuators": actuators_list,
        }
    except Exception as exc:
        logger.debug("Error building unit settings summary: %s", exc)
        return {}


def _build_active_plant_details(focus_plant):
    """Build active_plant dashboard payload from a focus plant dict."""
    try:
        focus_plant_id = focus_plant.get('plant_id')
        focus_stage = focus_plant.get('current_stage')
        growth_stages = focus_plant.get('growth_stages') or []
        conditions = _find_stage_conditions(growth_stages, focus_stage)

        temp_cfg = conditions.get('temperature_C', {}) or {}
        humidity_cfg = conditions.get('humidity_percent', {}) or {}
        hours_per_day = conditions.get('hours_per_day')

        explicit_base = focus_plant.get('gdd_base_temp_c')
        base_source = 'explicit' if explicit_base is not None else 'inferred'
        base_temp_c = None
        try:
            if explicit_base is not None:
                base_temp_c = float(explicit_base)
            else:
                base_temp_c = float(
                    infer_gdd_base_temp_c(growth_stages, stage_name=focus_stage, default=10.0)
                )
        except Exception:
            base_temp_c = None
            base_source = 'unknown'

        return {
            'plant_id': focus_plant_id,
            'active_plant_id': focus_plant_id,
            'name': focus_plant.get('plant_name') or focus_plant.get('name', 'Unknown'),
            'plant_type': focus_plant.get('plant_type') or focus_plant.get('species') or '',
            'status': focus_plant.get('status') or 'active',
            'current_stage': focus_stage,
            'days_in_stage': focus_plant.get('days_in_stage', 0),
            'days_left': focus_plant.get('days_left', 0),
            'gdd_base_temp_c': base_temp_c,
            'gdd_base_temp_source': base_source,
            'targets': {
                'temperature_c': {'min': temp_cfg.get('min'), 'max': temp_cfg.get('max')},
                'humidity_percent': {'min': humidity_cfg.get('min'), 'max': humidity_cfg.get('max')},
                'photoperiod_hours': hours_per_day,
            },
        }
    except Exception as exc:
        logger.debug('Failed to build active plant details: %s', exc)
        return None


def _build_alerts_summary(container, selected_unit_id):
    """Return a concise alerts summary for dashboard."""
    alert_service = getattr(container, "alert_service", None)
    if not alert_service:
        return {'count': 0, 'recent': [], 'critical': 0, 'warning': 0}

    try:
        recent_alerts = alert_service.get_active_alerts(unit_id=selected_unit_id, limit=20)
        return {
            'count': len(recent_alerts),
            'critical': len([a for a in recent_alerts if a.get('severity') == 'critical']),
            'warning': len([a for a in recent_alerts if a.get('severity') == 'warning']),
            'recent': recent_alerts[:5]
        }
    except Exception as exc:
        logger.debug("Failed to fetch alerts for unit %s: %s", selected_unit_id, exc)
        return {'count': 0, 'recent': [], 'critical': 0, 'warning': 0}


def _build_devices_summary(container, selected_unit_id):
    """Return sensors list, actuators list, and devices summary dict."""
    sensors = []
    actuators = []
    sensor_service = getattr(container, "sensor_management_service", None)
    actuator_service = getattr(container, "actuator_management_service", None)

    try:
        sensors = sensor_service.list_sensors(unit_id=selected_unit_id) if sensor_service else []
    except Exception as exc:
        logger.debug("Failed to list sensors for unit %s: %s", selected_unit_id, exc)
        sensors = []

    try:
        actuators = actuator_service.list_actuators(unit_id=selected_unit_id) if actuator_service else []
    except Exception as exc:
        logger.debug("Failed to list actuators for unit %s: %s", selected_unit_id, exc)
        actuators = []

    def _is_active(device):
        if not isinstance(device, dict):
            return False

        if "is_active" in device:
            value = device.get("is_active")
            if isinstance(value, str):
                normalized = value.strip().lower()
                if normalized in {"1", "true", "active", "enabled", "on", "yes"}:
                    return True
                if normalized in {"0", "false", "inactive", "disabled", "off", "no"}:
                    return False
            return bool(value)

        status = str(device.get("status") or "").strip().lower()
        return status in {"active", "enabled", "on", "running", "online"}

    active_sensors = len([s for s in sensors if _is_active(s)]) if isinstance(sensors, list) else 0
    active_actuators = len([a for a in actuators if _is_active(a)]) if isinstance(actuators, list) else 0

    devices_summary = {
        'active': active_sensors + active_actuators,
        'total': (len(sensors) if isinstance(sensors, list) else 0) + (len(actuators) if isinstance(actuators, list) else 0)
    }
    return sensors, actuators, devices_summary


def _build_energy_summary(container, energy_row, selected_unit_id):
    """Build a standard energy summary dictionary from energy_row and available services."""
    if not energy_row:
        return {}

    actuator_service = getattr(container, "actuator_management_service", None)
    try:
        if actuator_service:
            energy_monitoring = getattr(actuator_service.actuator_manager, "energy_monitoring", None)
            if energy_monitoring:
                return energy_monitoring.get_energy_summary(energy_row)
    except Exception as exc:
        logger.debug("Energy monitoring call failed: %s", exc)

    # Fallback summary
    return {
        'current_power_watts': energy_row.get('power_watts', 0),
        'daily_cost': 0.0,
        'trend': 'stable',
        'timestamp': energy_row.get('timestamp')
    }


def _build_system_summary(container, current_summary):
    """Compose system health summary using DeviceHealthService when available,
    falling back to a simple heuristic."""
    system = dict(current_summary.get('system', {'health_score': 0, 'status': 'unknown'}))
    try:
        device_health_service = getattr(container, "device_health_service", None)
        if device_health_service:
            try:
                system_health = device_health_service.calculate_system_health(
                    vpd_status=current_summary.get('vpd', {}).get('status'),
                    plant_health_avg=system.get('plant_health_avg'),
                    critical_alerts=current_summary.get('alerts', {}).get('critical', 0),
                    warning_alerts=current_summary.get('alerts', {}).get('warning', 0),
                    devices_active=current_summary.get('devices', {}).get('active', 0),
                    devices_total=current_summary.get('devices', {}).get('total', 0),
                )
                system['health_score'] = system_health['health_score']
                system['status'] = system_health['status']
                system['health_factors'] = system_health.get('factors', {})
                return system
            except Exception as exc:
                logger.debug("DeviceHealthService.calculate_system_health failed: %s", exc)

        # Fallback: derive from plant_health_avg
        plant_health_avg = system.get('plant_health_avg')
        if plant_health_avg is not None:
            system['health_score'] = max(system.get('health_score', 0), float(plant_health_avg))

        score = system.get('health_score', 0)
        if score >= 80:
            system['status'] = 'healthy'
        elif score >= 50:
            system['status'] = 'degraded'
        elif score > 0:
            system['status'] = 'unhealthy'
        else:
            system.setdefault('health_score', 75.0)
            system.setdefault('status', 'good')
    except Exception as exc:
        logger.debug("Failed to compute system summary: %s", exc)
        system.setdefault('health_score', 75.0)
        system.setdefault('status', 'good')
    return system


def _cache_get(key):
    entry = _timeseries_cache.get(key)
    if not entry:
        return None
    expires = entry.get("expires")
    if expires:
        now = datetime.now(timezone.utc)
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if expires < now:
            _timeseries_cache.pop(key, None)
            return None

        return entry.get("value")
    return entry.get("value")


def _cache_set(key, value):
    _timeseries_cache[key] = {
        "value": value,
        "expires": datetime.now(timezone.utc) + timedelta(seconds=CACHE_TTL_SECONDS),
    }
    if len(_timeseries_cache) > 64:
        # Drop oldest-ish entry to avoid unbounded growth
        oldest_key = next(iter(_timeseries_cache))
        _timeseries_cache.pop(oldest_key, None)


def _resolve_unit_id() -> Optional[int]:
    unit_id = request.args.get("unit_id", type=int)
    if unit_id is not None:
        return unit_id
    raw_unit_id = session.get("selected_unit")
    try:
        return int(raw_unit_id) if raw_unit_id is not None else None
    except (TypeError, ValueError):
        return None


def _normalize_stage_name(stage_name: Optional[str]) -> str:
    return str(stage_name or "").strip().lower()


def _parse_date_value(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return _ensure_utc(value)
    try:
        from datetime import date as date_type
        if isinstance(value, date_type):
            return datetime(value.year, value.month, value.day, tzinfo=timezone.utc)
    except Exception:
        pass
    if isinstance(value, str):
        return _coerce_datetime(value)
    return None


def _extract_stage_names(growth_stages: Any) -> List[str]:
    stages: List[str] = []
    if isinstance(growth_stages, dict):
        growth_stages = growth_stages.get("growth_stage") or growth_stages.get("stages") or []
    if isinstance(growth_stages, list):
        for stage in growth_stages:
            name = stage.get("stage") if isinstance(stage, dict) else None
            if name:
                stages.append(str(name))
    return stages


def _find_stage_details(growth_stages: Any, stage_name: Optional[str]) -> Optional[Dict[str, Any]]:
    if not growth_stages or not stage_name:
        return None
    target = _normalize_stage_name(stage_name)
    stages = growth_stages
    if isinstance(growth_stages, dict):
        stages = growth_stages.get("growth_stage") or growth_stages.get("stages") or []
    if not isinstance(stages, list):
        return None
    for stage in stages:
        if not isinstance(stage, dict):
            continue
        if _normalize_stage_name(stage.get("stage")) == target:
            return stage
    return None


def _hours_until_time(start_time: Optional[str]) -> Optional[int]:
    if not start_time:
        return None
    try:
        target = datetime.strptime(start_time, "%H:%M")
    except ValueError:
        return None
    now = datetime.now()
    scheduled = now.replace(hour=target.hour, minute=target.minute, second=0, microsecond=0)
    if scheduled <= now:
        scheduled += timedelta(days=1)
    delta = scheduled - now
    return max(0, int(delta.total_seconds() // 3600))


def _schedule_days(payload: Optional[Dict[str, Any]]) -> List[int]:
    if not payload:
        return []
    if payload.get("enabled") is False:
        return []
    days = payload.get("days_of_week") or payload.get("days")
    if isinstance(days, list):
        result: List[int] = []
        for entry in days:
            try:
                result.append(int(entry))
            except (TypeError, ValueError):
                continue
        return result
    return list(range(7))


@dashboard_api.get('/sensors/current')
def get_current_sensor_data():
    """Get current sensor readings for dashboard display"""
    try:
        # Get selected unit from session
        raw_unit_id = session.get('selected_unit')
        try:
            selected_unit_id = int(raw_unit_id) if raw_unit_id is not None else None
        except (TypeError, ValueError):
            selected_unit_id = None
        
        # Get services from app container
        container = current_app.config.get("CONTAINER")
        if not container:
            return _fail('Container unavailable', 503)

        # Prefer live, priority-selected snapshot from MQTT pipeline.
        snapshot = None
        try:
            mqtt_service = getattr(container, "mqtt_sensor_service", None)
            processor = getattr(mqtt_service, "processor", None) if mqtt_service else None
            if processor and selected_unit_id is not None:
                snapshot = processor.get_dashboard_snapshot(unit_id=selected_unit_id)
        except Exception as exc:
            logger.debug("Failed to build live dashboard snapshot: %s", exc)

        # Fallback: analytics latest (may not respect primaries)
        latest = None
        energy_row = None
        analytics_service = getattr(container, "analytics_service", None)
        if analytics_service:
            try:
                if snapshot is None:
                    latest = analytics_service.get_latest_sensor_reading(unit_id=selected_unit_id)
                    logger.debug(f"Latest sensor data for unit {selected_unit_id}: {latest}")
                energy_row = analytics_service.get_latest_energy_reading()
            except Exception as db_error:
                logger.error(f"Service error: {db_error}", exc_info=True)
                if snapshot is None:
                    return _fail('Analytics service unavailable', 503)

        if snapshot is not None:
            metrics = getattr(snapshot, 'metrics', None) or {}
            timestamp = getattr(snapshot, 'timestamp', None) or iso_now()
            sensor_data = {
                'temperature': _snap_metric_from_metrics(metrics, 'temperature', '°C', 'temperature', timestamp, container),
                'humidity': _snap_metric_from_metrics(metrics, 'humidity', '%', 'humidity', timestamp, container),
                'soil_moisture': _snap_metric_from_metrics(metrics, 'soil_moisture', '%', 'soil_moisture', timestamp, container, trend='up'),
                'co2': _snap_metric_from_metrics(metrics, 'co2', 'ppm', 'co2', timestamp, container),
                'lux': _snap_metric_from_metrics(metrics, 'lux', 'lux', 'lux', timestamp, container),
                'energy_usage': _build_energy_metric(energy_row),
            }
        else:
            # Build sensor data - will show N/A for units with no sensors
            sensor_data = {
                'temperature': _build_metric(latest, 'temperature', '°C', 'temperature'),
                'humidity': _build_metric(latest, 'humidity', '%', 'humidity'),
                'soil_moisture': _build_metric(latest, 'soil_moisture', '%', 'soil_moisture', trend='up'),
                'co2': _build_metric(latest, 'co2', 'ppm', 'co2'),
                'lux': _build_metric(latest, 'lux', 'lux', 'lux'),
                'energy_usage': _build_energy_metric(energy_row)
            }
        
        logger.debug(f"Sensor data response: {sensor_data}")

        return _success(
            {
                'sensor_data': sensor_data,
                'timestamp': ((getattr(snapshot, 'timestamp', None) if snapshot else None) or (latest['timestamp'] if latest else iso_now()))
            }
        )
        
    except Exception as e:
        logger.error(f"Error getting current sensor data: {e}", exc_info=True)
        return _fail('Failed to get sensor data', 500)


@dashboard_api.get("/timeseries")
def get_timeseries():
    """Return decoded sensor readings for charts (optionally filtered)."""
    try:
        container = current_app.config.get("CONTAINER")
        analytics_service = getattr(container, "analytics_service", None) if container else None
        if not analytics_service:
            return _fail("Analytics service unavailable", 503)

        end_param = request.args.get("end")
        start_param = request.args.get("start")
        unit_id = request.args.get("unit_id", type=int)
        sensor_id = request.args.get("sensor_id", type=int)
        limit = request.args.get("limit", default=500, type=int)
        horizon_hours = request.args.get("hours", type=int)

        now = datetime.now(timezone.utc)
        end_dt = _parse_iso8601(end_param, fallback=now)
        start_default = end_dt - timedelta(hours=horizon_hours or 24)
        start_dt = _parse_iso8601(start_param, fallback=start_default)

        if start_dt >= end_dt:
            return _fail("start must be before end", 400)

        target_limit = limit or 500
        if horizon_hours and horizon_hours > 168:
            target_limit = min(target_limit, 800)
        elif horizon_hours and horizon_hours > 72:
            target_limit = min(target_limit, 1200)
        target_limit = max(50, target_limit)

        cache_key = _cache_key(start_dt, end_dt, unit_id, sensor_id, target_limit, horizon_hours)
        cached = _cache_get(cache_key)
        if cached:
            return _success(cached)

        # Fetch a larger sample than the desired limit so downsampling preserves shape.
        db_limit = max(target_limit * 4, 0) if target_limit else None
        readings = analytics_service.fetch_sensor_history(
            start_dt,
            end_dt,
            unit_id=unit_id,
            sensor_id=sensor_id,
            limit=db_limit,
        )
        series = _downsample(readings, target=target_limit)

        for row in series:
            parsed = _coerce_datetime(row.get("timestamp"))
            if parsed:
                row["timestamp"] = parsed.isoformat()

        payload = {
            "start": start_dt.isoformat(),
            "end": end_dt.isoformat(),
            "unit_id": unit_id,
            "sensor_id": sensor_id,
            "count": len(readings),
            "returned": len(series),
            "series": series,
        }
        _cache_set(cache_key, payload)
        return _success(payload)
    except ValueError as exc:
        logger.warning("Validation error in get_timeseries: %s", exc)
        return _fail(str(exc), 400)
    except Exception as exc:
        logger.exception("Error fetching dashboard timeseries: %s", exc)
        return _fail("Failed to fetch timeseries", 500)


@dashboard_api.get('/actuators/recent-state')
def get_recent_actuator_state():
    """Return last N actuator state transitions for dashboard tile."""
    try:
        limit = request.args.get('limit', default=20, type=int)
        unit_id = request.args.get('unit_id', default=None, type=int)
        container = current_app.config.get("CONTAINER")
        if not container:
            return _fail("Container unavailable", 503)
        rows = container.device_repo.get_recent_actuator_state(limit=limit, unit_id=unit_id)
        return _success({"states": rows, "count": len(rows)})
    except Exception as e:
        logger.error(f"Error getting recent actuator state: {e}")
        return _fail("Failed to get recent actuator state", 500)


@dashboard_api.get('/connectivity/recent')
def get_recent_connectivity():
    """Return last N connectivity events for dashboard tile (optional type filter)."""
    try:
        limit = request.args.get('limit', default=20, type=int)
        connection_type = request.args.get('connection_type')
        container = current_app.config.get("CONTAINER")
        if not container:
            return _fail("Container unavailable", 503)
        rows = container.device_repo.get_connectivity_history(connection_type=connection_type, limit=limit)
        return _success({"events": rows, "count": len(rows)})
    except Exception as e:
        logger.error(f"Error getting recent connectivity events: {e}")
        return _fail("Failed to get connectivity events", 500)

def _build_metric(row, value_key, unit, threshold_key, trend='stable'):
    value = row.get(value_key) if row else None
    timestamp = row.get('timestamp') if row else iso_now()
    
    # Use DeviceHealthService for status evaluation
    status = 'Unknown'
    if value is not None:
        container = current_app.config.get("CONTAINER")
        device_health_service = getattr(container, "device_health_service", None) if container else None
        if device_health_service:
            status = device_health_service.evaluate_sensor_status(value, threshold_key)
        else:
            # Fallback to simple evaluation
            status = get_status(value, threshold_key)
    
    return {
        'value': value,
        'unit': unit,
        'status': status,
        'trend': trend,
        'timestamp': timestamp
    }


def _build_energy_metric(row):
    value = row['power_watts'] if row else None
    timestamp = row['timestamp'] if row else iso_now()
    return {
        'value': value,
        'unit': 'W',
        'status': get_status(value, 'energy_usage') if value is not None else 'Unknown',
        'trend': 'stable',
        'timestamp': timestamp
    }


def _snap_metric_from_metrics(metrics: Dict[str, Any], metric_key: str, default_unit: str, threshold_key: str, timestamp: Any, container, trend: str = 'stable') -> Dict[str, Any]:
    """Construct a metric response from a snapshot metrics mapping.

    This pulls a metric object from `metrics` and returns a normalized dict.
    Extracted to reduce duplication inside route handlers and lower cyclomatic
    complexity in large functions.
    """
    m = metrics.get(metric_key)
    if not m:
        return {
            'value': None,
            'unit': default_unit,
            'status': 'Unknown',
            'trend': trend,
            'timestamp': timestamp,
        }
    value = getattr(m, 'value', None)
    unit = getattr(m, 'unit', None) or default_unit
    source = getattr(m, 'source', None)
    source_status = getattr(source, 'status', None) if source else None

    # Use DeviceHealthService for status evaluation when available
    status = source_status
    if not status and value is not None:
        device_health_service = getattr(container, "device_health_service", None) if container else None
        if device_health_service:
            try:
                status = device_health_service.evaluate_sensor_status(value, threshold_key)
            except Exception:
                status = get_status(value, threshold_key)
        else:
            status = get_status(value, threshold_key)
    elif status is None:
        status = 'Unknown'

    return {
        'value': value,
        'unit': unit,
        'status': status,
        'trend': trend,
        'timestamp': timestamp,
    }


@dashboard_api.get('/status')
def get_system_status():
    """Get overall system status for dashboard header"""
    try:
        container = current_app.config["CONTAINER"]
        growth_service = getattr(container, "growth_service", None)
        connected = getattr(container, "zigbee_service", None).is_connected() if getattr(container, "zigbee_service", None) else False
        database_online = bool(container.database)
        units_online = len(growth_service.get_unit_runtimes()) if growth_service else 0
        try:
            devices_count = (
                len(container.sensor_management_service.list_sensors())
                + len(container.actuator_management_service.list_actuators())
            )
        except Exception:
            devices_count = 0
        
        # Count active alerts (critical + warning)
        alerts_count = 0
        try:
            alert_service = getattr(container, "alert_service", None)
            if alert_service:
                active_alerts = alert_service.get_active_alerts(limit=1000)
                alerts_count = len(active_alerts)
        except Exception as e:
            logger.debug(f"Could not fetch alert count: {e}")
            alerts_count = 0
        
        system_status = {
            'connected': bool(connected),
            'sensors_online': units_online > 0,
            'database_online': database_online,
            'last_update': iso_now(),
            'devices_count': devices_count,
            'alerts_count': alerts_count
        }
        return _success(system_status)
        
    except Exception as e:
        logger.exception(f"Error getting system status: {e}")
        return _fail('Failed to get system status', 500)


def _find_stage_conditions(
    growth_stages: Any,
    stage_name: str,
) -> Dict[str, Any]:
    if not growth_stages or not stage_name:
        return {}

    target = str(stage_name).strip().lower()
    try:
        for stage in growth_stages:
            name = str(stage.get("stage", "")).strip().lower()
            if name != target:
                continue
            return stage.get("conditions", {}) or {}
    except Exception:
        return {}

    return {}


def _build_plants_summary(container, selected_unit_id, growth_service, plant_health_scorer):
    """Build plant summaries and compute average health for the dashboard.

    Returns (plant_summaries:list, active_plant:dict|None, plant_health_avg:float|None)
    """
    try:
        plant_service = getattr(container, "plant_service", None)
        if not plant_service:
            return [], None, None

        plants = plant_service.list_plants(selected_unit_id) if selected_unit_id else []
        plant_summaries = []
        health_scores = []

        active_plant_id = None
        active_plant = None
        try:
            active = plant_service.get_active_plant(selected_unit_id) if growth_service and selected_unit_id else None
            active_plant = active.to_dict() if active else None
            active_plant_id = active_plant.get('plant_id') if active_plant else None
        except Exception:
            active_plant_id = None

        focus_plant = active_plant
        if focus_plant is None and plants:
            focus_plant = plants[0].to_dict() if hasattr(plants[0], 'to_dict') else dict(plants[0])

        for plant in plants:
            plant = plant.to_dict() if hasattr(plant, 'to_dict') else dict(plant)
            plant_id = plant.get('plant_id') or plant.get('id')
            health = plant_health_scorer.score_plant_health(plant_id) if plant_id else None
            health_score = health.get('overall_score', 75) if health else 75
            health_scores.append(health_score)

            device_health_service = getattr(container, "device_health_service", None)
            health_status = device_health_service.interpret_health_score(health_score) if device_health_service else 'good'

            plant_summaries.append({
                'plant_id': plant_id,
                'name': plant.get('plant_name') or plant.get('name', 'Unknown'),
                'plant_name': plant.get('plant_name') or plant.get('name', 'Unknown'),
                'species': plant.get('species') or plant.get('plant_type') or '',
                'plant_type': plant.get('plant_type') or plant.get('species') or '',
                'current_stage': plant.get('current_stage') or plant.get('growth_stage', 'vegetative'),
                'growth_stage': plant.get('current_stage') or plant.get('growth_stage', 'vegetative'),
                'days_in_stage': plant.get('days_in_stage', 0),
                'status': plant.get('status') or ('active' if plant_id == active_plant_id else 'inactive'),
                'health_score': health_score,
                'health_status': health_status,
                'moisture_level': plant.get('moisture_level'),
                'moisture_percent': plant.get('moisture_percent') if plant.get('moisture_percent') is not None else plant.get('moisture'),
                'last_watered': plant.get('last_watered') or plant.get('last_watered_at'),
                'custom_image': plant.get('custom_image') or plant.get('image'),
                'image': plant.get('image') or plant.get('image_url') or plant.get('custom_image'),
                'image_url': plant.get('image_url') or plant.get('image'),
            })

        plant_health_avg = sum(health_scores) / len(health_scores) if health_scores else None
        return plant_summaries, focus_plant, plant_health_avg
    except Exception as e:
        logger.warning(f"Error building plants summary: {e}")
        return [], None, None


@dashboard_api.get('/summary')
def get_dashboard_summary():
    """
    Get comprehensive dashboard summary - aggregated data for the main dashboard.

    Returns:
        - sensors: Current sensor values with status
        - vpd: VPD calculation with status (optimal for veg/flower)
        - plants: Plants in unit with health summary
        - alerts: Recent alerts count and list
        - energy: Current power consumption and daily cost
        - devices: Active devices count
        - system: Overall system health score
    """
    try:
        raw_unit_id = session.get("selected_unit")
        try:
            selected_unit_id = int(raw_unit_id) if raw_unit_id is not None else None
        except (TypeError, ValueError):
            selected_unit_id = None
        container = current_app.config.get("CONTAINER")
        growth_service = getattr(container, "growth_service", None) if container else None
        plant_health_scorer = getattr(container, "plant_health_scorer")

        if not container:
            return _fail('Container unavailable', 503)

        # Collect all dashboard data in parallel-ish fashion
        summary = {
            'unit_id': selected_unit_id,
            'timestamp': iso_now(),
            'sensors': {},
            'vpd': {},
            'plants': [],
            'active_plant': None,
            'alerts': {'count': 0, 'recent': []},
            'energy': {},
            'devices': {'active': 0, 'total': 0},
            'actuators': [],
            'system': {'health_score': 0, 'status': 'unknown'},
            'unit_settings': None,
        }
        sensors = []
        actuators = []

        # 1. Get current sensor data (snapshot preferred, analytics fallback)
        try:
            sensors_dict, vpd_dict, energy_row = _build_snapshot_or_analytics(container, selected_unit_id)
            summary['sensors'] = sensors_dict or {}
            summary['vpd'] = vpd_dict or {}
            if energy_row:
                try:
                    summary['energy'] = _build_energy_summary(container, energy_row, selected_unit_id)
                except Exception as exc:
                    logger.debug("Failed to build energy summary: %s", exc)
        except Exception as e:
            logger.warning(f"Error fetching sensor/energy data: {e}")

        # 3. Get plants in unit with health summary
        try:
            plant_summaries, focus_plant, plant_health_avg = _build_plants_summary(
                container, selected_unit_id, growth_service, plant_health_scorer
            )
            summary['plants'] = plant_summaries
            if focus_plant:
                summary['active_plant'] = _build_active_plant_details(focus_plant)
            if plant_health_avg is not None:
                summary['system']['plant_health_avg'] = plant_health_avg
        except Exception as e:
            logger.warning(f"Error fetching plant data: {e}")

        # 4. Get alerts count
        try:
            summary['alerts'] = _build_alerts_summary(container, selected_unit_id)
        except Exception as e:
            logger.warning(f"Error fetching alerts: {e}")

        # 5. Get active devices count
        try:
            sensors_summary, actuators_summary, devices_summary = _build_devices_summary(container, selected_unit_id)
            # merge into summary
            summary['devices'] = devices_summary
            summary['actuators'] = actuators_summary if isinstance(actuators_summary, list) else []
            # keep raw device lists for downstream use
            sensors = sensors_summary if isinstance(sensors_summary, list) else []
            actuators = actuators_summary if isinstance(actuators_summary, list) else []
        except Exception as e:
            logger.warning(f"Error fetching devices: {e}")

        # 6. System health summary
        try:
            summary['system'] = _build_system_summary(container, summary)
        except Exception as exc:
            logger.debug("Failed to build system summary: %s", exc)

        # 7. Unit settings snapshot (thresholds, schedules, configured devices)
        if selected_unit_id and growth_service:
            try:
                summary["unit_settings"] = _build_unit_settings_summary(
                    container,
                    growth_service,
                    selected_unit_id,
                    sensors=sensors,
                    actuators=actuators,
                )
            except Exception as e:
                logger.warning("Error building unit settings snapshot for unit %s: %s", selected_unit_id, e)

        return _success(summary)

    except Exception as e:
        logger.exception(f"Error getting dashboard summary: {e}")
        return _fail('Failed to get dashboard summary', 500)


@dashboard_api.get("/growth-stage")
def get_growth_stage():
    """Get growth stage progress details for the selected unit.
    """
    try:
        unit_id = _resolve_unit_id()

        growth_service = get_growth_service()
        plant_service = get_plant_service()

        if not growth_service or not plant_service:
            return _fail("Services unavailable", 503)

        if unit_id is None:
            return _success({
                "unit_id": None,
                "plant_id": None,
                "plant_name": None,
                "current_stage": "unknown",
                "stage_index": -1,
                "stages": [],
                "days_in_stage": 0,
                "days_left": None,
                "days_total": 0,
                "progress": 0,
                "tip": None,
            })

        active_plant = plant_service.get_active_plant(unit_id)

        if not active_plant:
            return _success({
                "unit_id": unit_id,
                "plant_id": None,
                "plant_name": None,
                "current_stage": "unknown",
                "stage_index": -1,
                "stages": [],
                "days_in_stage": 0,
                "days_left": None,
                "days_total": 0,
                "progress": 0,
                "tip": None,
            })
        plant = active_plant.to_dict()
        current_stage = plant.get("current_stage") or plant.get("growth_stage") or plant.get("stage") or "unknown"
        stage_names = _extract_stage_names(plant.get("growth_stages"))
        if not stage_names:
            stage_names = ["seedling", "vegetative", "flowering", "fruiting", "harvest"]

        stage_index = -1
        norm_stage = _normalize_stage_name(current_stage)
        for idx, name in enumerate(stage_names):
            if _normalize_stage_name(name) == norm_stage:
                stage_index = idx
                break

        days_in_stage = plant.get("days_in_stage")
        if days_in_stage is None:
            days_in_stage = plant.get("days_in_current_stage")
        try:
            days_in_stage = int(days_in_stage) if days_in_stage is not None else 0
        except (TypeError, ValueError):
            days_in_stage = 0

        days_left = plant.get("days_left")
        try:
            days_left = int(days_left) if days_left is not None else None
        except (TypeError, ValueError):
            days_left = None

        stage_details = _find_stage_details(plant.get("growth_stages"), current_stage) or {}
        duration = stage_details.get("duration", {}) if isinstance(stage_details, dict) else {}
        stage_total = duration.get("max_days") or duration.get("min_days")
        if stage_total in (None, 0) and days_left is not None:
            stage_total = days_in_stage + days_left

        try:
            stage_total = int(stage_total) if stage_total is not None else 0
        except (TypeError, ValueError):
            stage_total = 0

        stage_progress = (days_in_stage / stage_total) if stage_total > 0 else 0
        if stage_index >= 0 and stage_names:
            progress = ((stage_index + stage_progress) / len(stage_names)) * 100
        else:
            progress = stage_progress * 100
        progress = max(0, min(100, round(progress, 1)))

        payload = {
            "unit_id": unit_id,
            "plant_id": plant.get("plant_id") or plant.get("id"),
            "plant_name": plant.get("plant_name") or plant.get("name"),
            "current_stage": current_stage,
            "stage_index": stage_index,
            "stages": stage_names,
            "days_in_stage": days_in_stage,
            "days_left": days_left,
            "days_total": stage_total,
            "progress": progress,
            "tip": None,
        }

        return _success(payload)
    except Exception as exc:
        logger.exception("Error getting growth stage: %s", exc)
        return _fail("Failed to get growth stage", 500)


@dashboard_api.get("/harvest-timeline")
def get_harvest_timeline():
    """Get upcoming harvests and the most recent harvest for the selected unit."""
    try:
        unit_id = _resolve_unit_id()
        container = current_app.config.get("CONTAINER")
        plant_service = getattr(container, "plant_service", None) if container else None
        harvest_service = getattr(container, "harvest_service", None) if container else None

        if not container or not plant_service:
            return _fail("Services unavailable", 503)

        upcoming = []
        if unit_id is not None:
            plants = plant_service.list_plants(unit_id)
            now = datetime.now(timezone.utc)
            for plant in plants:
                plant = plant.to_dict()
                expected = (
                    plant.get("expected_harvest_date")
                    or plant.get("expected_harvest")
                    or plant.get("harvest_date")
                )
                target = _parse_date_value(expected)
                if not target:
                    continue
                days_until = max(0, (target.date() - now.date()).days)
                upcoming.append({
                    "plant_id": plant.get("plant_id") or plant.get("id"),
                    "name": plant.get("plant_name") or plant.get("name") or "Plant",
                    "expected_harvest_date": target.date().isoformat(),
                    "days_until_harvest": days_until,
                })
            upcoming.sort(key=lambda item: item.get("days_until_harvest", 0))

        recent = None
        if harvest_service and unit_id is not None:
            reports = harvest_service.get_harvest_reports(unit_id)
            if reports:
                report = reports[0]
                recent = {
                    "harvest_id": report.get("harvest_id"),
                    "plant_id": report.get("plant_id"),
                    "date": report.get("harvested_date"),
                    "amount": report.get("harvest_weight_grams"),
                }

        return _success({
            "unit_id": unit_id,
            "upcoming": upcoming,
            "recent_harvest": recent,
        })
    except Exception as exc:
        logger.exception("Error getting harvest timeline: %s", exc)
        return _fail("Failed to get harvest timeline", 500)

#TODO: This belong to api/growth/schedule.py?
@dashboard_api.get("/water-schedule")
def get_water_schedule():
    """Get watering and feeding schedule overview for the selected unit."""
    try:
        unit_id = _resolve_unit_id()
        scheduling_service = get_scheduling_service()
        
        if not scheduling_service:
            return _fail("Scheduling service unavailable", 503)

        if unit_id is None:
            return _success({
                "unit_id": None,
                "next_water_hours": None,
                "next_feed_hours": None,
                "water_days": [],
                "feed_days": [],
            })

        # Get schedules from SchedulingService
        schedules = scheduling_service.get_schedules_for_unit(unit_id)
        
        # Find water/irrigation schedule
        water_schedule = None
        for sched in schedules:
            if sched.device_type and sched.device_type.lower() in ("watering", "water", "irrigation", "pump"):
                water_schedule = sched
                break
        
        # Find feed/nutrient schedule
        feed_schedule = None
        for sched in schedules:
            if sched.device_type and sched.device_type.lower() in ("feeding", "feed", "nutrient", "fertigation"):
                feed_schedule = sched
                break

        water_payload = {"start_time": water_schedule.start_time, "end_time": water_schedule.end_time} if water_schedule else None
        feed_payload = {"start_time": feed_schedule.start_time, "end_time": feed_schedule.end_time} if feed_schedule else None

        next_water = _hours_until_time(water_payload.get("start_time") if water_payload else None)
        next_feed = _hours_until_time(feed_payload.get("start_time") if feed_payload else None)

        return _success({
            "unit_id": unit_id,
            "next_water_hours": next_water,
            "next_feed_hours": next_feed,
            "water_days": _schedule_days(water_payload),
            "feed_days": _schedule_days(feed_payload),
        })
    except Exception as exc:
        logger.exception("Error getting water schedule: %s", exc)
        return _fail("Failed to get water schedule", 500)


@dashboard_api.get("/irrigation-status")
def get_irrigation_status():
    """Get recent irrigation activity and current soil moisture for the selected unit."""
    try:
        unit_id = _resolve_unit_id()
        container = current_app.config.get("CONTAINER")
        irrigation_service = getattr(container, "irrigation_workflow_service", None) if container else None
        analytics_service = getattr(container, "analytics_service", None) if container else None

        if not container:
            return _fail("Container unavailable", 503)

        last_run = None
        duration = None
        amount = None

        if irrigation_service and unit_id is not None:
            last = irrigation_service.get_last_completed_irrigation(unit_id)
            if last:
                last_run = last.get("executed_at") or last.get("scheduled_time")
                duration = last.get("execution_duration_seconds") or last.get("duration_seconds")

        soil_moisture = None
        if analytics_service and unit_id is not None:
            try:
                latest = analytics_service.get_latest_sensor_reading(unit_id=unit_id)
                soil_moisture = latest.get("soil_moisture") if latest else None
            except Exception as exc:
                logger.debug("Failed to load latest soil moisture for unit %s: %s", unit_id, exc)

        return _success({
            "unit_id": unit_id,
            "last_run": last_run,
            "duration_seconds": duration,
            "amount_ml": amount,
            "soil_moisture": soil_moisture,
        })
    except Exception as exc:
        logger.exception("Error getting irrigation status: %s", exc)
        return _fail("Failed to get irrigation status", 500)


def _calculate_vpd(temperature: float, humidity: float) -> Dict[str, Any]:
    """
    Calculate Vapor Pressure Deficit (VPD) from temperature and humidity.

    VPD = SVP × (1 - RH/100)
    where SVP (Saturation Vapor Pressure) = 0.6108 × exp(17.27 × T / (T + 237.3))

    Optimal VPD zones:
    - Seedling/Clone: 0.4-0.8 kPa
    - Vegetative: 0.8-1.2 kPa
    - Flowering: 1.0-1.5 kPa
    """
    if temperature is None or humidity is None:
        return {
            'value': None,
            'unit': 'kPa',
            'status': 'unknown',
            'zone': 'unknown',
            'optimal_for': []
        }

    try:
        vpd_value = calculate_vpd_kpa(temperature, humidity)
        if vpd_value is None:
            raise ValueError("VPD inputs missing")

        vpd = round(float(vpd_value), 2)

        # Determine zone and optimal stage
        zone = 'unknown'
        optimal_for = []
        status = 'normal'

        if vpd < 0.4:
            zone = 'too_low'
            status = 'low'
            optimal_for = []
        elif vpd < 0.8:
            zone = 'seedling'
            status = 'optimal'
            optimal_for = ['seedling', 'clone', 'early_veg']
        elif vpd < 1.2:
            zone = 'vegetative'
            status = 'optimal'
            optimal_for = ['vegetative', 'late_veg']
        elif vpd < 1.5:
            zone = 'flowering'
            status = 'optimal'
            optimal_for = ['flowering', 'bloom']
        else:
            zone = 'too_high'
            status = 'high'
            optimal_for = []

        return {
            'value': vpd,
            'unit': 'kPa',
            'status': status,
            'zone': zone,
            'optimal_for': optimal_for,
            'temperature': temperature,
            'humidity': humidity
        }
    except Exception as e:
        logger.warning(f"Error calculating VPD: {e}")
        return {
            'value': None,
            'unit': 'kPa',
            'status': 'error',
            'zone': 'unknown',
            'optimal_for': []
        }


def get_status(value, sensor_type):
    """Determine sensor status based on value and thresholds (fallback when service unavailable)"""
    try:
        # Simple threshold logic as fallback
        # Production code should use DeviceHealthService.evaluate_sensor_status()
        thresholds = {
            'temperature': {'min': 18, 'max': 28},
            'humidity': {'min': 40, 'max': 80},
            'soil_moisture': {'min': 30, 'max': 70},
            'lux': {'min': 200, 'max': 1500},
            'co2': {'min': 300, 'max': 800},
            'energy_usage': {'min': 0, 'max': 5}
        }
        
        threshold = thresholds.get(sensor_type, {'min': 0, 'max': 100})
        
        if value < threshold['min']:
            return 'Low'
        elif value > threshold['max']:
            return 'High'
        else:
            return 'Normal'
            
    except Exception:
        return 'Unknown'
