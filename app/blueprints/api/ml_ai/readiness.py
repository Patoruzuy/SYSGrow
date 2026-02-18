"""
ML Readiness API
================
Endpoints for checking ML model readiness and activation.

Provides:
- Check data collection progress for ML models
- Activate/deactivate ML models
- Get activation status
"""

import logging

from flask import Blueprint, Response, session

from app.blueprints.api._common import (
    fail as _fail,
    get_container as _container,
    success as _success,
)
from app.utils.http import safe_route

logger = logging.getLogger(__name__)

readiness_bp = Blueprint("ml_readiness", __name__)


def _get_ml_monitor():
    """Return the MLReadinessMonitorService from the container.

    Raises ``RuntimeError`` if the service is not available.
    """
    container = _container()
    monitor = getattr(container, "ml_readiness_monitor", None)
    if monitor is None:
        raise RuntimeError("ML readiness monitor not available - irrigation ML features may be disabled")
    return monitor


@readiness_bp.get("/irrigation/<int:unit_id>")
@safe_route("Failed to check irrigation readiness")
def get_irrigation_readiness(unit_id: int) -> Response:
    """
    Get ML readiness status for irrigation models.

    Returns progress toward model activation thresholds.
    """
    ml_monitor = _get_ml_monitor()
    readiness = ml_monitor.check_irrigation_readiness(unit_id)
    return _success(readiness.to_dict())


@readiness_bp.post("/irrigation/<int:unit_id>/activate/<string:model_name>")
@safe_route("Failed to activate ML model")
def activate_model(unit_id: int, model_name: str) -> Response:
    """
    Activate an ML model for a unit.

    Called when user approves model activation from notification
    or settings page.
    """
    user_id = session.get("user_id")
    if not user_id:
        return _fail("User not authenticated", 401)

    ml_monitor = _get_ml_monitor()
    success = ml_monitor.activate_model(user_id, unit_id, model_name)

    if success:
        return _success(
            {
                "activated": True,
                "model_name": model_name,
                "unit_id": unit_id,
            }
        )
    else:
        return _fail(f"Failed to activate model: {model_name}", 400)


@readiness_bp.post("/irrigation/<int:unit_id>/deactivate/<string:model_name>")
@safe_route("Failed to deactivate ML model")
def deactivate_model(unit_id: int, model_name: str) -> Response:
    """
    Deactivate an ML model for a unit.
    """
    user_id = session.get("user_id")
    if not user_id:
        return _fail("User not authenticated", 401)

    ml_monitor = _get_ml_monitor()
    success = ml_monitor.deactivate_model(user_id, unit_id, model_name)

    if success:
        return _success(
            {
                "deactivated": True,
                "model_name": model_name,
                "unit_id": unit_id,
            }
        )
    else:
        return _fail(f"Failed to deactivate model: {model_name}", 400)


@readiness_bp.get("/irrigation/<int:unit_id>/status")
@safe_route("Failed to get ML activation status")
def get_activation_status(unit_id: int) -> Response:
    """
    Get activation status of all ML models for a unit.
    """
    ml_monitor = _get_ml_monitor()
    status = ml_monitor.get_activation_status(unit_id)
    return _success(status)


@readiness_bp.post("/check-all")
@safe_route("Failed to check ML readiness for all units")
def check_all_units() -> Response:
    """
    Manually trigger ML readiness check for all units.

    This is normally run as a scheduled task, but can be
    triggered manually for testing.
    """
    ml_monitor = _get_ml_monitor()
    results = ml_monitor.check_all_units()

    return _success(
        {
            "units_checked": len(results),
            "notifications_sent": results,
        }
    )
