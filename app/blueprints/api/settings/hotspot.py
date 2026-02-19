"""
Hotspot Settings Management
============================

Endpoints for managing WiFi hotspot configuration including SSID and password.
Includes security features for password masking and validation.
"""

from __future__ import annotations

from flask import Response

from app.blueprints.api._common import (
    fail as _fail,
    get_json as _json,
    get_settings_service as _service,
    success as _success,
)
from app.utils.http import safe_error, safe_route

from . import settings_api


@settings_api.get("/hotspot")
@safe_route("Failed to get hotspot settings")
def get_hotspot_settings() -> Response:
    """
    Get hotspot settings with masked password for security.

    Returns:
        - ssid: Hotspot network name
        - password_present: Boolean indicating if password is configured

    Note: Actual password is never returned for security reasons.
    """
    data = _service().get_hotspot_settings()
    if not data:
        return _fail("Hotspot settings not configured.", 404)

    # Mask sensitive password data in the response
    response_data = {
        "ssid": data.get("ssid", ""),
        "password_present": bool(data.get("password_present")),
    }
    # Never return the actual password in GET requests for security
    return _success(response_data, 200)


@settings_api.put("/hotspot")
@safe_route("Failed to update hotspot settings")
def update_hotspot_settings() -> Response:
    """
    Update hotspot settings (SSID and/or password).

    Request Body:
        - ssid (required): Hotspot network name
        - password (optional): Password (min 8 characters, only required for initial setup)

    Security:
        - Passwords are encrypted before storage
        - Password validation enforces minimum length
        - SSID-only updates are allowed after initial setup
    """
    payload = _json()
    ssid = payload.get("ssid")
    password = payload.get("password")

    if not ssid:
        return _fail("ssid is required.", 400)

    # Only update password if provided (allow SSID-only updates)
    if password:
        if len(password) < 8:
            return _fail("Password must be at least 8 characters long.", 400)
        try:
            data = _service().update_hotspot_settings(ssid=ssid, encrypted_password=password)
        except ValueError as exc:
            return safe_error(exc, 400)
    else:
        # Update only SSID, keep existing password
        current_settings = _service().get_hotspot_settings()
        if not current_settings or not current_settings.get("encrypted_password"):
            return _fail("Password is required for initial hotspot setup.", 400)
        try:
            data = _service().update_hotspot_settings(
                ssid=ssid, encrypted_password=current_settings["encrypted_password"]
            )
        except ValueError as exc:
            return safe_error(exc, 400)

    # Return masked response
    response_data = {
        "ssid": data.get("ssid", ssid),
        "password_present": bool(data.get("password_present", True)),
    }
    return _success(response_data, 200, message="Hotspot settings updated successfully")
