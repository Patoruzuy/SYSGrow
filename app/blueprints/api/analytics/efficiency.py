"""
System Efficiency Score Endpoints
=================================

Endpoints for calculating and reporting system efficiency metrics.
"""

import logging

from flask import request

from app.blueprints.api._common import (
    fail as _fail,
    get_analytics_service as _analytics_service,
    success as _success,
)
from app.blueprints.api.analytics import analytics_api

logger = logging.getLogger(__name__)


# ============================================================================
# SYSTEM EFFICIENCY SCORE
# ============================================================================


@analytics_api.get("/efficiency-score")
def get_efficiency_score():
    """
    Calculate composite system efficiency score.

    Components (weighted):
    - Environmental Stability (40%): Temperature, humidity, VPD consistency
    - Energy Efficiency (30%): Power usage optimization
    - Automation Effectiveness (30%): Device response and alert handling

    Query params:
    - unit_id: Optional unit filter

    Returns:
    - overall_score: Composite score (0-100)
    - components: Breakdown by category
    - grade: Letter grade (A+, A, B+, B, C, D, F)
    - suggestions: Improvement recommendations
    - trend: Performance trend (improving/stable/declining)
    """
    try:
        unit_id = request.args.get("unit_id", type=int)
        analytics_service = _analytics_service()

        # Logic moved to service
        data = analytics_service.get_composite_efficiency_score(unit_id=unit_id, include_previous=True)

        return _success(data)

    except Exception as e:
        logger.error(f"Error calculating efficiency score: {e}", exc_info=True)
        return safe_error(e, 500)


# Standard grading and trend logic moved to service layer common helpers.
# Helper functions removed from blueprint as they are now in AnalyticsService.
