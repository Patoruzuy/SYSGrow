"""
ML Health Endpoints
===================

Health monitoring endpoints for ML services.
"""

from __future__ import annotations

import logging

from flask import Blueprint, Response

from app.blueprints.api._common import (
    success as _success,
)
from app.enums.common import HealthLevel
from app.utils.http import safe_route
from app.utils.time import iso_now

logger = logging.getLogger("health_api")


def register_ml_routes(health_api: Blueprint):
    """Register ML health routes on the blueprint."""

    @health_api.get("/ml")
    @safe_route("Failed to get ML health status")
    def get_ml_health() -> Response:
        """
        Get health status of ML services and models.

        Returns:
            {
                "status": "healthy",
                "service": "ml-api",
                "timestamp": "2025-12-07T...",
                "models": {...},
                "features": {...}
            }
        """
        return _success(
            {
                "status": HealthLevel.HEALTHY.value,
                "service": "ml-api",
                "timestamp": iso_now(),
                "features": {
                    "model_training": True,
                    "drift_detection": True,
                    "predictions": True,
                    "feature_importance": True,
                },
            }
        )
