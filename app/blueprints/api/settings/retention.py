"""
Data Retention Settings Management
===================================

Endpoints for managing data retention policies, specifically for
actuator state history pruning configuration.
"""

from __future__ import annotations

from contextlib import suppress

from flask import Response, current_app

from app.blueprints.api._common import (
    fail as _fail,
    get_container,
    get_json as _json,
    success as _success,
)
from app.utils.http import safe_route

from . import settings_api

# ==================== ACTUATOR STATE RETENTION ====================


@settings_api.get("/retention/actuator-state")
@safe_route("Failed to get actuator state retention setting")
def get_retention_days() -> Response:
    """
    Get current retention setting for actuator state history.

    Returns:
        - days: Number of days to retain actuator state history

    This value controls automatic pruning of historical state data.
    Default is typically 90 days if not configured.
    """
    container = get_container()
    days = getattr(getattr(container, "config", None), "actuator_state_retention_days", None)
    if days is None:
        days = current_app.config.get("ACTUATOR_STATE_RETENTION_DAYS")
    return _success({"days": days})


@settings_api.post("/retention/actuator-state")
@safe_route("Failed to set actuator state retention setting")
def set_retention_days() -> Response:
    """
    Set retention days for actuator state history (runtime configuration).

    Request Body:
        - days (required): Number of days to retain history (1-3650)

    Validation:
        - days must be an integer between 1 and 3650 (10 years max)

    Note: This is a runtime-only setting and does not persist across restarts.
    Configure permanently through environment variables or config files.
    """
    payload = _json()
    days = int(payload.get("days", 90))
    if days < 1 or days > 3650:
        return _fail("days must be between 1 and 3650", 400)
    container = get_container()
    with suppress(Exception):
        container.config.actuator_state_retention_days = days
    # update flask config for visibility
    current_app.config["ACTUATOR_STATE_RETENTION_DAYS"] = days
    return _success({"days": days})
