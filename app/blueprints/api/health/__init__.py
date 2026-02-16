"""
Health API Blueprint
====================

Consolidated health monitoring endpoints for all system components.

Routes:
- GET /api/health/ping - Basic liveness check
- GET /api/health/system - Overall system health with metrics
- GET /api/health/units - Health summaries for all units
- GET /api/health/units/<unit_id> - Detailed unit health
- GET /api/health/devices - Aggregated device-level health
- GET /api/health/sensors/<sensor_id> - Sensor health
- GET /api/health/actuators/<actuator_id> - Actuator health
- GET /api/health/plants/summary - Plant health summary
- GET /api/health/ml - ML service health
- GET /api/health/detailed - Comprehensive health report
- GET /api/health/storage - Storage usage statistics
- GET /api/health/api-metrics - API performance metrics
- GET /api/health/database - Database connection health
- GET /api/health/infrastructure - Infrastructure component statuses
- GET /api/health/cache - Cache performance metrics
- GET /api/health/cache/repository - Repository cache metrics
"""

from __future__ import annotations

import logging

from flask import Blueprint

logger = logging.getLogger("health_api")

# Create the blueprint
health_api = Blueprint("health_api", __name__, url_prefix="/api/health")

# Import and register routes from submodules
from app.blueprints.api.health.cache import register_cache_routes
from app.blueprints.api.health.devices import register_device_routes
from app.blueprints.api.health.ml import register_ml_routes
from app.blueprints.api.health.plants import register_plant_routes
from app.blueprints.api.health.system import register_system_routes
from app.blueprints.api.health.units import register_unit_routes

# Register all routes on the blueprint
register_system_routes(health_api)
register_unit_routes(health_api)
register_device_routes(health_api)
register_plant_routes(health_api)
register_ml_routes(health_api)
register_cache_routes(health_api)

# Re-export for backwards compatibility
__all__ = ["health_api"]
