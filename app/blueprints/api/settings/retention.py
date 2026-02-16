"""
Data Retention Settings Management
===================================

Endpoints for managing data retention policies, specifically for
actuator state history pruning configuration.
"""

from __future__ import annotations

from flask import current_app

from app.blueprints.api._common import (
    fail as _fail,
    get_container,
    get_json as _json,
    success as _success,
)

from . import settings_api

# ==================== ACTUATOR STATE RETENTION ====================


@settings_api.get("/retention/actuator-state")
def get_retention_days():
    """
    Get current retention setting for actuator state history.

    Returns:
        - days: Number of days to retain actuator state history

    This value controls automatic pruning of historical state data.
    Default is typically 90 days if not configured.
    """
    try:
        container = get_container()
        days = getattr(getattr(container, "config", None), "actuator_state_retention_days", None)
        if days is None:
            days = current_app.config.get("ACTUATOR_STATE_RETENTION_DAYS")
        return _success({"days": days})
    except Exception as e:
        return safe_error(e, 500)


@settings_api.post("/retention/actuator-state")
def set_retention_days():
    """
    Set retention days for actuator state history (runtime configuration).

    Request Body:
        - days (required): Number of days to retain history (1-3650)

    Validation:
        - days must be an integer between 1 and 3650 (10 years max)

    Note: This is a runtime-only setting and does not persist across restarts.
    Configure permanently through environment variables or config files.
    """
    try:
        payload = _json()
        days = int(payload.get("days", 90))
        if days < 1 or days > 3650:
            return _fail("days must be between 1 and 3650", 400)
        container = get_container()
        try:
            container.config.actuator_state_retention_days = days
        except Exception:
            pass
        # update flask config for visibility
        current_app.config["ACTUATOR_STATE_RETENTION_DAYS"] = days
        # Reflect in container config too (non-persistent)
        try:
            container.config.actuator_state_retention_days = days
        except Exception:
            pass
        return _success({"days": days})
    except Exception as e:
        return safe_error(e, 500)
