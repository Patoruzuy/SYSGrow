"""
Actuator Analytics Endpoints
============================

Endpoints for actuator energy analytics, costs, and comparative analysis.
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
# ACTUATOR ENERGY ANALYTICS ENDPOINTS
# ============================================================================


@analytics_api.get("/actuators/overview")
def get_actuators_overview():
    """
    Get overview of all actuators and their current state.

    Query params:
    - unit_id: Optional unit filter

    Returns:
    - Current state of all actuators
    - Runtime statistics
    - Energy consumption (if monitored)
    - Health status
    """
    try:
        unit_id = request.args.get("unit_id", type=int)
        analytics = _analytics_service()

        # Logic moved to service
        data = analytics.get_actuators_analytics_overview(unit_id=unit_id)

        return _success(data)

    except Exception as e:
        logger.error(f"Error getting actuators overview: {e}", exc_info=True)
        return safe_error(e, 500)


@analytics_api.get("/actuators/<int:actuator_id>/dashboard")
def get_actuator_dashboard(actuator_id: int):
    """
    Get comprehensive energy dashboard for a specific actuator.

    Returns:
    - Current status and power consumption
    - 7-day cost trends
    - Optimization recommendations
    - Recent anomalies (24h)
    - Failure risk prediction
    """
    try:
        analytics = _analytics_service()
        dashboard = analytics.get_actuator_energy_dashboard(actuator_id)

        return _success({"actuator_id": actuator_id, "dashboard": dashboard})

    except Exception as e:
        logger.error(f"Error getting actuator dashboard: {e}", exc_info=True)
        return safe_error(e, 500)


@analytics_api.get("/actuators/<int:actuator_id>/energy-costs")
def get_actuator_energy_costs(actuator_id: int):
    """
    Get detailed energy cost breakdown and trends.

    Query params:
    - days: Days to analyze (default: 7)

    Returns:
    - Daily cost breakdown
    - Total cost for period
    - Trend direction (increasing/decreasing/stable)
    - Cost projections
    """
    try:
        days = request.args.get("days", 7, type=int)

        analytics = _analytics_service()
        costs = analytics.get_actuator_energy_cost_trends(actuator_id, days)

        return _success({"actuator_id": actuator_id, "period_days": days, "costs": costs})

    except Exception as e:
        logger.error(f"Error getting energy costs: {e}", exc_info=True)
        return safe_error(e, 500)


@analytics_api.get("/actuators/<int:actuator_id>/recommendations")
def get_actuator_recommendations(actuator_id: int):
    """
    Get energy optimization recommendations for an actuator.

    Returns:
    - List of actionable recommendations
    - Potential cost savings
    - Priority levels
    - Implementation difficulty
    """
    try:
        analytics = _analytics_service()
        recommendations = analytics.get_actuator_optimization_recommendations(actuator_id)

        return _success({"actuator_id": actuator_id, "recommendations": recommendations, "count": len(recommendations)})

    except Exception as e:
        logger.error(f"Error getting recommendations: {e}", exc_info=True)
        return safe_error(e, 500)


@analytics_api.get("/actuators/<int:actuator_id>/anomalies")
def get_actuator_anomalies(actuator_id: int):
    """
    Detect power consumption anomalies (spikes, drops, unusual patterns).

    Query params:
    - hours: Hours to analyze (default: 24)

    Returns:
    - List of detected anomalies
    - Severity levels
    - Timestamps and values
    """
    try:
        hours = request.args.get("hours", 24, type=int)

        analytics = _analytics_service()
        anomalies = analytics.detect_actuator_power_anomalies(actuator_id, hours)

        return _success(
            {"actuator_id": actuator_id, "period_hours": hours, "anomalies": anomalies, "count": len(anomalies)}
        )

    except Exception as e:
        logger.error(f"Error detecting anomalies: {e}", exc_info=True)
        return safe_error(e, 500)


@analytics_api.get("/actuators/<int:actuator_id>/predict-failure")
def predict_actuator_failure(actuator_id: int):
    """
    Predict device failure risk based on historical patterns.

    Query params:
    - days_ahead: Prediction window (default: 7)

    Returns:
    - Risk score (0.0-1.0)
    - Risk level (low/medium/high/critical)
    - Contributing factors
    - Maintenance recommendation
    - Confidence level
    """
    try:
        days_ahead = request.args.get("days_ahead", 7, type=int)

        if days_ahead < 1 or days_ahead > 30:
            return _fail("days_ahead must be between 1 and 30", 400)

        analytics = _analytics_service()
        prediction = analytics.predict_device_failure(actuator_id, days_ahead)

        return _success({"actuator_id": actuator_id, "prediction": prediction})

    except Exception as e:
        logger.error(f"Error predicting failure: {e}", exc_info=True)
        return safe_error(e, 500)


# ============================================================================
# COMPARATIVE ANALYTICS ENDPOINTS
# ============================================================================


@analytics_api.get("/units/<int:unit_id>/comparison")
def get_unit_comparison(unit_id: int):
    """
    Get comparative analysis across all devices in a unit.

    Returns:
    - Energy consumption comparison
    - Efficiency rankings
    - Top consumers
    - Cost breakdown by device type
    """
    try:
        analytics = _analytics_service()
        comparison = analytics.get_comparative_energy_analysis(unit_id)

        return _success({"unit_id": unit_id, "comparison": comparison})

    except Exception as e:
        logger.error(f"Error getting unit comparison: {e}", exc_info=True)
        return safe_error(e, 500)


@analytics_api.get("/units/comparison")
def get_multi_unit_comparison():
    """
    Compare environmental conditions and energy usage across all units.

    Returns:
    - Per-unit statistics
    - Relative performance metrics
    - Best/worst performers
    - Optimization opportunities
    """
    try:
        analytics = _analytics_service()
        data = analytics.get_multi_unit_analytics_overview()
        return _success(data)

    except Exception as e:
        logger.error(f"Error getting multi-unit comparison: {e}", exc_info=True)
        return safe_error(e, 500)
