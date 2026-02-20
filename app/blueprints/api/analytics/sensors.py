"""
Sensor Analytics Endpoints
==========================

Endpoints for sensor data visualization, trends, and correlations.
"""

from __future__ import annotations

import logging
from contextlib import suppress
from datetime import timedelta

from flask import Response, request

from app.blueprints.api._common import (
    fail as _fail,
    get_analytics_service as _analytics_service,
    get_growth_service as _growth_service,
    get_sensor_service as _sensor_service,
    parse_datetime as _parse_datetime,
    success as _success,
)
from app.blueprints.api.analytics import analytics_api
from app.utils.http import safe_route
from app.utils.time import iso_now, utc_now

logger = logging.getLogger(__name__)


@analytics_api.get("/sensors/overview")
@safe_route("Failed to get sensors overview")
def get_sensors_overview() -> Response:
    """
    Get overview of all sensor readings across units.

    Query params:
    - unit_id: Optional unit filter

    Returns:
    - Latest readings for all sensors
    - Summary statistics (min/max/avg)
    - Health status indicators
    - Last update timestamps
    """
    unit_id = request.args.get("unit_id", type=int)
    analytics = _analytics_service()

    # Get latest reading (optionally filtered by unit)
    latest = analytics.get_latest_sensor_reading(unit_id=unit_id)

    # Get sensor list
    sensor_svc = _sensor_service()
    sensors = sensor_svc.list_sensors(unit_id=unit_id) if unit_id else sensor_svc.list_sensors()

    overview = {
        "unit_id": unit_id,
        "latest_reading": latest,
        "total_sensors": len(sensors),
        "sensors": sensors,
        "timestamp": iso_now(),
    }

    return _success(overview)


@analytics_api.get("/sensors/history")
@safe_route("Failed to get sensor history")
def get_sensors_history() -> Response:
    """
    Get historical sensor readings for time-series charts.

    Query params:
    - start: Start datetime (ISO 8601, default: 24h ago)
    - end: End datetime (ISO 8601, default: now)
    - unit_id: Optional unit filter
    - sensor_id: Optional sensor filter
    - limit: Max readings (default: 500)
    - interval: Aggregation interval (optional: '1h', '6h', '1d')

    Returns:
    - Time-series data for all sensor types
    - Formatted for chart libraries (timestamps + values)
    """
    analytics = _analytics_service()

    # Parse parameters
    end = _parse_datetime(request.args.get("end"), utc_now())
    start = _parse_datetime(request.args.get("start"), end - timedelta(hours=24))
    unit_id = request.args.get("unit_id", type=int)
    sensor_id = request.args.get("sensor_id", type=int)
    limit = request.args.get("limit", 500, type=int)
    interval = request.args.get("interval")

    if start >= end:
        return _fail("start must be before end", 400)

    # Fetch history
    readings = analytics.fetch_sensor_history(start, end, unit_id=unit_id, sensor_id=sensor_id, limit=limit)

    # Format for charts using AnalyticsService
    chart_data = analytics.format_sensor_chart_data(readings, interval)

    return _success(
        {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "unit_id": unit_id,
            "sensor_id": sensor_id,
            "interval": interval,
            "count": len(readings),
            "data": chart_data,
        }
    )


@analytics_api.get("/sensors/history/enriched")
@safe_route("Failed to get enriched sensor history")
def get_sensors_history_enriched() -> Response:
    """
    Get historical sensor readings enriched with photoperiod/day-night series.
    Delegates calculation and analysis to AnalyticsService.
    """
    analytics = _analytics_service()

    unit_id = request.args.get("unit_id", type=int)
    sensor_id = request.args.get("sensor_id", type=int)
    limit = request.args.get("limit", 500, type=int)
    interval = request.args.get("interval")

    lux_threshold_override = request.args.get("lux_threshold", type=float)
    prefer_lux = bool(request.args.get("prefer_lux", 0, type=int))
    day_start = request.args.get("day_start")
    day_end = request.args.get("day_end")

    hours = request.args.get("hours", type=int)
    end = _parse_datetime(request.args.get("end"), utc_now())

    start_param = request.args.get("start")
    if start_param:
        start = _parse_datetime(start_param, end - timedelta(hours=24))
    else:
        start = end - timedelta(hours=(hours or 24))

    if start >= end:
        return _fail("start must be before end", 400)

    # Get unit data once to pass in
    unit_data = None
    if unit_id:
        with suppress(Exception):
            unit_data = _growth_service().get_unit(unit_id)

    # Delegate to service
    result = analytics.get_enriched_sensor_history(
        start_datetime=start,
        end_datetime=end,
        unit_id=unit_id,
        sensor_id=sensor_id,
        limit=limit,
        interval=interval,
        lux_threshold_override=lux_threshold_override,
        prefer_lux=prefer_lux,
        day_start_override=day_start,
        day_end_override=day_end,
        unit_data=unit_data,
    )

    return _success(result)


@analytics_api.get("/sensors/day-night/summary")
@safe_route("Failed to get day/night summary")
def get_day_night_summary() -> Response:
    """
    Return day vs night summary metrics for a unit and time window.

    Uses the same schedule/lux logic as `/api/analytics/sensors/history/enriched`.
    """
    unit_id = request.args.get("unit_id", type=int)
    if unit_id is None:
        return _fail("unit_id is required", 400)

    response = get_sensors_history_enriched()
    payload = response.get_json(silent=True) or {}
    if not payload.get("ok") or not payload.get("data"):
        return response

    data = payload["data"]
    return _success(
        {
            "unit_id": unit_id,
            "start": data.get("start"),
            "end": data.get("end"),
            "photoperiod": data.get("photoperiod"),
            "timestamp": iso_now(),
        }
    )


@analytics_api.get("/sensors/statistics")
@safe_route("Failed to get sensor statistics")
def get_sensors_statistics() -> Response:
    """
    Get statistical analysis of sensor data.

    Query params:
    - hours: Hours to analyze (default: 24)
    - unit_id: Optional unit filter
    - sensor_id: Optional sensor filter

    Returns:
    - Min, max, average, median for each metric
    - Standard deviation
    - Trend indicators
    - Anomaly counts
    """
    analytics = _analytics_service()

    hours = request.args.get("hours", 24, type=int)
    unit_id = request.args.get("unit_id", type=int)
    sensor_id = request.args.get("sensor_id", type=int)

    end = utc_now()
    start = end - timedelta(hours=hours)

    stats = analytics.get_sensor_statistics(start, end, unit_id=unit_id, sensor_id=sensor_id)

    return _success({"period_hours": hours, "unit_id": unit_id, "sensor_id": sensor_id, "statistics": stats})


@analytics_api.get("/sensors/trends")
@safe_route("Failed to get sensor trends")
def get_sensors_trends() -> Response:
    """
    Get environmental trend analysis for identifying patterns.

    Query params:
    - days: Days to analyze (default: 7)
    - unit_id: Optional unit filter

    Returns:
    - Daily averages and trends
    - Day/night comparisons
    - Pattern detection (stable, rising, falling, volatile)
    - Correlation insights
    """
    analytics = _analytics_service()

    days = request.args.get("days", 7, type=int)
    unit_id = request.args.get("unit_id", type=int)

    end = utc_now()
    start = end - timedelta(days=days)

    # Get historical data
    readings = analytics.fetch_sensor_history(start, end, unit_id=unit_id)

    # Analyze trends using AnalyticsService
    trends = analytics.analyze_metric_trends(readings, days)

    return _success({"period_days": days, "unit_id": unit_id, "trends": trends})


@analytics_api.get("/sensors/correlations")
@safe_route("Failed to calculate sensor correlations")
def get_sensors_correlations() -> Response:
    """
    Get correlation analysis between environmental factors.

    Helps identify relationships like:
    - Temperature vs Humidity (inverse correlation)
    - Soil moisture vs watering events
    - VPD trends

    Query params:
    - days: Days to analyze (default: 7)
    - unit_id: Optional unit filter

    Returns:
    - Correlation coefficients
    - VPD analysis
    - Environmental stress indicators
    """
    analytics = _analytics_service()

    days = request.args.get("days", 7, type=int)
    unit_id = request.args.get("unit_id", type=int)

    end = utc_now()
    start = end - timedelta(days=days)

    readings = analytics.fetch_sensor_history(start, end, unit_id=unit_id)

    # Calculate environmental correlations using AnalyticsService
    correlations = analytics.calculate_environmental_correlations(readings)

    return _success({"period_days": days, "unit_id": unit_id, "correlations": correlations})
