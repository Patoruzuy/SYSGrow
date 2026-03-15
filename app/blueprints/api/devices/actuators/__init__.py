"""Actuators API module; imports register the actuator endpoints."""

import logging

from .. import devices_api

logger = logging.getLogger(__name__)


@devices_api.errorhandler(404)
def actuator_not_found(error):
    """Handle 404 errors in actuator routes."""
    return {"success": False, "message": "Resource not found"}, 404


@devices_api.errorhandler(500)
def actuator_internal_error(error):
    """Handle 500 errors in actuator routes."""
    logger.error("Internal error in actuator API: %s", error)
    return {"success": False, "message": "Internal server error"}, 500


# Import all route modules to register their endpoints
from . import crud  # noqa: F401
from . import control  # noqa: F401
from . import energy  # noqa: F401
from . import analytics  # noqa: F401

__all__ = ['crud', 'control', 'energy', 'analytics']
