"""
Plants API Module
=================

Modular plants API organized by concern:
- crud.py: Plant CRUD operations
- lifecycle.py: Growth stages and active plant management
- sensors.py: Plant-sensor linking
- actuators.py: Plant-actuator linking
- health.py: Health monitoring and recommendations
- journal.py: Plant journal, growing guide, harvests, disease risk
"""

from flask import Blueprint
from app.utils.http import error_response

# Create blueprint here to avoid circular imports
plants_api = Blueprint("plants_api", __name__)

# Error handlers
@plants_api.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    return error_response("Resource not found", 404)

@plants_api.errorhandler(405)
def method_not_allowed(error):
    """Handle 405 errors"""
    return error_response("Method not allowed", 405)

@plants_api.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    return error_response("Internal server error", 500)

# Import submodules to register routes (must be after blueprint creation)
from . import actuators, crud, health, intelligence, journal, journal_extended, lifecycle, sensors

__all__ = ['plants_api']
