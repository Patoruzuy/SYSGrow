"""
Growth API Module
=================

Modular growth units API organized by concern:
- units.py: Unit CRUD operations
- thresholds.py: Environment threshold management
- schedules.py: Device schedule management
- camera.py: Camera control operations
"""

from flask import Blueprint

from app.utils.http import error_response

# Create blueprint here to avoid circular imports
growth_api = Blueprint("growth_api", __name__)


# Error handlers
@growth_api.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    return error_response("Resource not found", 404)


@growth_api.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    return error_response("Internal server error", 500)


# Import submodules to register routes (must be after blueprint creation)
from . import camera, schedules, thresholds, units

__all__ = ["growth_api"]
