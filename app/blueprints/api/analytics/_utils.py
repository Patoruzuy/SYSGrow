"""
Analytics API Helper Functions
==============================

Shared utility functions used across analytics submodules.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.blueprints.api._common import (
    get_analytics_service as _analytics_service,
)


def format_sensor_chart_data(readings: list[dict], interval: str | None = None) -> dict[str, Any]:
    """
    Format sensor readings for chart visualization.

    DEPRECATED: This function delegates to AnalyticsService.format_sensor_chart_data()
    Use the service method directly for new code.

    Returns data structured for popular chart libraries:
    - timestamps: List of ISO datetime strings
    - temperature: List of temperature values
    - humidity: List of humidity values
    - etc.
    """
    analytics_service = _analytics_service()
    return analytics_service.format_sensor_chart_data(readings, interval)


def mean(values: list[float]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 3)


def analyze_trends(readings: list[dict], days: int) -> dict[str, Any]:
    """
    Analyze environmental trends over time.

    DEPRECATED: This function delegates to AnalyticsService.analyze_metric_trends()
    Use the service method directly for new code.

    Returns:
    - Daily averages
    - Trend directions (stable/rising/falling)
    - Volatility indicators
    """
    analytics_service = _analytics_service()
    return analytics_service.analyze_metric_trends(readings, days)


def calculate_correlations(readings: list[dict]) -> dict[str, Any]:
    """
    Calculate correlations between environmental factors.

    DEPRECATED: This function delegates to AnalyticsService.calculate_environmental_correlations()
    Use the service method directly for new code.

    Returns:
    - Temperature-Humidity correlation
    - VPD analysis
    - Soil moisture trends
    """
    analytics_service = _analytics_service()
    return analytics_service.calculate_environmental_correlations(readings)


def sqlite_timestamp(dt: datetime) -> str:
    """Format a datetime for safe use with SQLite datetime() comparisons."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    else:
        dt = dt.astimezone(UTC)
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def volatility_ratio(metric: dict[str, Any], *, default: float) -> float:
    """Calculate volatility ratio from metric dict."""
    avg = metric.get("average")
    std_dev = metric.get("std_dev")
    if not isinstance(avg, int | float) or not isinstance(std_dev, int | float):
        return default
    if avg == 0:
        return default
    return abs(std_dev / avg)
