"""
ML Health Endpoints
===================

Health monitoring endpoints for ML services.
"""
import logging
from flask import Blueprint

from app.utils.time import iso_now
from app.enums.common import HealthLevel

from app.blueprints.api._common import (
    success as _success,
)

logger = logging.getLogger('health_api')


def register_ml_routes(health_api: Blueprint):
    """Register ML health routes on the blueprint."""

    @health_api.get('/ml')
    def get_ml_health():
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
        return _success({
            'status': HealthLevel.HEALTHY.value,
            'service': 'ml-api',
            'timestamp': iso_now(),
            'features': {
                'model_training': True,
                'drift_detection': True,
                'predictions': True,
                'feature_importance': True
            }
        })
