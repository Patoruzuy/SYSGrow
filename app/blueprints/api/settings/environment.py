"""
Environment & Light Settings Management
========================================

Endpoints for managing global/default environment thresholds.
For unit-specific thresholds, use /api/growth/v2/units/<id>/thresholds.
"""
from __future__ import annotations

from flask import request

from . import settings_api
from app.blueprints.api._common import (
    success as _success,
    fail as _fail,
    get_json as _json,
    get_threshold_service as _threshold_service,
)


# ==================== GLOBAL ENVIRONMENT THRESHOLDS ====================

@settings_api.get("/environment")
def get_environment_thresholds():
    """
    Get global/default environment monitoring thresholds.
    
    These are system-wide defaults. For unit-specific thresholds,
    use /api/growth/v2/units/<unit_id>/thresholds.
    
    Returns:
        - temperature_threshold: Target temperature in Celsius
        - humidity_threshold: Target humidity percentage
    """
    data = _threshold_service().get_environment_thresholds()
    if not data:
        return _fail("Environment thresholds not configured.", 404)
    if isinstance(data, dict):
        data.pop("soil_moisture_threshold", None)
    if isinstance(data, dict):
        data.pop("soil_moisture_threshold", None)
    return _success(data, 200)


@settings_api.put("/environment")
def update_environment_thresholds():
    """
    Update global/default environment monitoring thresholds.
    
    Request Body:
        - temperature_threshold (required): Target temperature (numeric)
        - humidity_threshold (required): Target humidity (numeric)
    
    Validation:
        - All fields are required
        - All values must be numeric
    """
    payload = _json()
    required = ["temperature_threshold", "humidity_threshold"]
    missing = [field for field in required if payload.get(field) is None]
    if missing:
        return _fail(f"Missing fields: {', '.join(missing)}", 400)
    try:
        data = _threshold_service().update_environment_thresholds(
            temperature_threshold=float(payload["temperature_threshold"]),
            humidity_threshold=float(payload["humidity_threshold"]),
        )
    except (TypeError, ValueError):
        return _fail("Threshold values must be numeric.", 400)
    return _success(data, 200)
