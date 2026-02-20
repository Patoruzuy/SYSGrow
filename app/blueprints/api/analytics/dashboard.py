"""
Dashboard Summary Endpoints
===========================

Endpoints for dashboard cards and summary views.
"""

from __future__ import annotations

import logging

from flask import Response, request

from app.blueprints.api._common import (
    get_analytics_service as _analytics_service,
    success as _success,
)
from app.blueprints.api.analytics import analytics_api
from app.utils.http import safe_route

logger = logging.getLogger(__name__)


# ============================================================================
# DASHBOARD SUMMARY ENDPOINTS
# ============================================================================


@analytics_api.get("/dashboard/environmental-summary")
@safe_route("Failed to get environmental summary")
def get_environmental_summary() -> Response:
    """
    Get environmental conditions summary for dashboard cards.

    Query params:
    - unit_id: Optional unit filter

    Returns:
    - Current conditions (latest readings)
    - 24h averages and trends
    - Alert conditions
    - Health indicators
    """
    unit_id = request.args.get("unit_id", type=int)
    analytics = _analytics_service()

    # Logic moved to service
    data = analytics.get_environmental_dashboard_summary(unit_id=unit_id)

    return _success(data)


@analytics_api.get("/dashboard/energy-summary")
@safe_route("Failed to get energy summary")
def get_energy_summary() -> Response:
    """
    Get energy consumption summary for dashboard cards.

    Query params:
    - unit_id: Optional unit filter
    - days: Days to analyze (default: 7)

    Returns:
    - Total cost for period
    - Top consumers
    - Cost trends
    - Optimization opportunities
    """
    unit_id = request.args.get("unit_id", type=int)
    days = request.args.get("days", 7, type=int)

    analytics = _analytics_service()

    # Logic moved to service
    data = analytics.get_energy_dashboard_summary(unit_id=unit_id, days=days)

    return _success(data)
