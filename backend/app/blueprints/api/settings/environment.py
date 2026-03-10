"""
Environment & Light Settings Management
========================================

Endpoints for managing global/default environment thresholds.
For unit-specific thresholds, use /api/growth/v2/units/<id>/thresholds.
"""

from __future__ import annotations

import logging

from flask import Response, request

from app.blueprints.api._common import (
    fail as _fail,
    get_json as _json,
    get_selected_unit_id as _selected_unit_id,
    get_threshold_service as _threshold_service,
    success as _success,
)
from app.services.application.threshold_service import THRESHOLD_KEYS
from app.utils.http import safe_route

from . import settings_api

logger = logging.getLogger("settings.environment")
LEGACY_MESSAGE = "Legacy endpoint. Use /api/growth/v2/units/<unit_id>/thresholds."

# ==================== GLOBAL ENVIRONMENT THRESHOLDS ====================


@settings_api.get("/environment")
@safe_route("Failed to get environment thresholds")
def get_environment_thresholds() -> Response:
    """
    Get environment monitoring thresholds for a unit.

    Use unit_id query param or selected unit in session.

    Returns:
        - temperature_threshold: Target temperature in Celsius
        - humidity_threshold: Target humidity percentage
    """
    unit_id = request.args.get("unit_id") or _selected_unit_id()
    if unit_id is None:
        return _fail("Missing unit_id.", 400)
    try:
        unit_id = int(unit_id)
    except (TypeError, ValueError):
        return _fail("Invalid unit_id.", 400)

    logger.warning("Legacy /api/settings/environment read for unit %s", unit_id)
    data = _threshold_service().get_environment_thresholds(unit_id=unit_id)
    if not data:
        return _fail("Environment thresholds not configured for unit.", 404)
    if isinstance(data, dict):
        data.pop("soil_moisture_threshold", None)
    return _success(data, 200, message=LEGACY_MESSAGE)


@settings_api.put("/environment")
@safe_route("Failed to update environment thresholds")
def update_environment_thresholds() -> Response:
    """
    Update environment monitoring thresholds for a unit.

    Request Body:
        - unit_id (required): Target unit ID
        - temperature_threshold (optional): Target temperature (numeric)
        - humidity_threshold (optional): Target humidity (numeric)
        - co2_threshold, voc_threshold, lux_threshold, air_quality_threshold (optional)

    Validation:
        - At least one threshold field must be provided
        - All values must be numeric
    """
    payload = _json()
    unit_id = payload.get("unit_id") or request.args.get("unit_id") or _selected_unit_id()
    if unit_id is None:
        return _fail("Missing unit_id.", 400)
    try:
        unit_id = int(unit_id)
    except (TypeError, ValueError):
        return _fail("Invalid unit_id.", 400)

    threshold_payload = {}
    for key in THRESHOLD_KEYS:
        if key not in payload:
            continue
        try:
            threshold_payload[key] = float(payload[key])
        except (TypeError, ValueError):
            return _fail("Threshold values must be numeric.", 400)

    if not threshold_payload:
        return _fail("No valid threshold fields provided.", 400)

    logger.warning("Legacy /api/settings/environment update for unit %s", unit_id)
    data = _threshold_service().update_environment_thresholds(
        unit_id=unit_id,
        thresholds=threshold_payload,
    )
    if not data:
        return _fail("Failed to update environment thresholds.", 500)
    return _success(data, 200, message=LEGACY_MESSAGE)
