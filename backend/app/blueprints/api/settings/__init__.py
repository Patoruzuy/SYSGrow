"""
Settings API Module
Modularized settings management endpoints split by domain.
"""

from __future__ import annotations

from flask import Blueprint, Response

from app.utils.http import error_response

# Create blueprint here to avoid circular imports
settings_api = Blueprint("settings_api", __name__)


# Error handlers
@settings_api.errorhandler(404)
def not_found(error) -> Response:
    """Handle 404 errors"""
    return error_response("Resource not found", 404)


@settings_api.errorhandler(500)
def internal_error(error) -> Response:
    """Handle 500 errors"""
    return error_response("Internal server error", 500)


# Import all route modules to register their endpoints (must be after blueprint creation)
# Note: light module removed - use /api/growth/v2/units/<id>/schedules instead
from . import camera, database, environment, hotspot, notifications, retention, security, throttle

_ = (camera, database, environment, hotspot, notifications, retention, security, throttle)

__all__ = ["settings_api"]
