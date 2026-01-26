"""
ML Readiness API
================
Endpoints for checking ML model readiness and activation.

Provides:
- Check data collection progress for ML models
- Activate/deactivate ML models
- Get activation status
"""

import logging
from flask import Blueprint, jsonify, request, session

from app.blueprints.api._common import (
    get_container as _container,
    success as _success,
    fail as _fail,
)

logger = logging.getLogger(__name__)

readiness_bp = Blueprint("ml_readiness", __name__, url_prefix="/api/ml/readiness")


@readiness_bp.get("/irrigation/<int:unit_id>")
def get_irrigation_readiness(unit_id: int):
    """
    Get ML readiness status for irrigation models.
    
    Returns progress toward model activation thresholds.
    
    Response:
    {
        "ok": true,
        "data": {
            "unit_id": 1,
            "models": {
                "response_predictor": {
                    "model_name": "response_predictor",
                    "display_name": "User Response Predictor",
                    "required_samples": 20,
                    "current_samples": 15,
                    "is_ready": false,
                    "is_activated": false,
                    "progress_percent": 75.0,
                    "samples_needed": 5,
                    "description": "...",
                    "benefits": [...]
                },
                ...
            },
            "any_ready_not_activated": false,
            "all_models_activated": false,
            "last_checked": "2026-01-03T..."
        }
    }
    """
    try:
        container = _container()
        
        # Get or create ML readiness monitor
        ml_monitor = getattr(container, 'ml_readiness_monitor', None)
        if not ml_monitor:
            # Create on-the-fly if not in container
            from app.services.ai.ml_readiness_monitor import MLReadinessMonitorService
            from infrastructure.database.repositories.irrigation_ml import IrrigationMLRepository
            
            ml_repo = IrrigationMLRepository(container.database)
            ml_monitor = MLReadinessMonitorService(
                irrigation_ml_repo=ml_repo,
                notifications_service=container.notifications_service,
            )
        
        readiness = ml_monitor.check_irrigation_readiness(unit_id)
        return _success(readiness.to_dict())
        
    except Exception as e:
        logger.error(f"Error checking irrigation readiness: {e}", exc_info=True)
        return _fail(str(e), 500)


@readiness_bp.post("/irrigation/<int:unit_id>/activate/<string:model_name>")
def activate_model(unit_id: int, model_name: str):
    """
    Activate an ML model for a unit.
    
    Called when user approves model activation from notification
    or settings page.
    
    Response:
    {
        "ok": true,
        "data": {
            "activated": true,
            "model_name": "response_predictor",
            "unit_id": 1
        }
    }
    """
    try:
        container = _container()
        
        user_id = session.get("user_id")
        if not user_id:
            return _fail("User not authenticated", 401)
        
        # Get or create ML readiness monitor
        ml_monitor = getattr(container, 'ml_readiness_monitor', None)
        if not ml_monitor:
            from app.services.ai.ml_readiness_monitor import MLReadinessMonitorService
            from infrastructure.database.repositories.irrigation_ml import IrrigationMLRepository
            
            ml_repo = IrrigationMLRepository(container.database)
            ml_monitor = MLReadinessMonitorService(
                irrigation_ml_repo=ml_repo,
                notifications_service=container.notifications_service,
            )
        
        success = ml_monitor.activate_model(user_id, unit_id, model_name)
        
        if success:
            return _success({
                "activated": True,
                "model_name": model_name,
                "unit_id": unit_id,
            })
        else:
            return _fail(f"Failed to activate model: {model_name}", 400)
        
    except Exception as e:
        logger.error(f"Error activating model: {e}", exc_info=True)
        return _fail(str(e), 500)


@readiness_bp.post("/irrigation/<int:unit_id>/deactivate/<string:model_name>")
def deactivate_model(unit_id: int, model_name: str):
    """
    Deactivate an ML model for a unit.
    
    Response:
    {
        "ok": true,
        "data": {
            "deactivated": true,
            "model_name": "response_predictor",
            "unit_id": 1
        }
    }
    """
    try:
        container = _container()
        
        user_id = session.get("user_id")
        if not user_id:
            return _fail("User not authenticated", 401)
        
        ml_monitor = getattr(container, 'ml_readiness_monitor', None)
        if not ml_monitor:
            from app.services.ai.ml_readiness_monitor import MLReadinessMonitorService
            from infrastructure.database.repositories.irrigation_ml import IrrigationMLRepository
            
            ml_repo = IrrigationMLRepository(container.database)
            ml_monitor = MLReadinessMonitorService(
                irrigation_ml_repo=ml_repo,
                notifications_service=container.notifications_service,
            )
        
        success = ml_monitor.deactivate_model(user_id, unit_id, model_name)
        
        if success:
            return _success({
                "deactivated": True,
                "model_name": model_name,
                "unit_id": unit_id,
            })
        else:
            return _fail(f"Failed to deactivate model: {model_name}", 400)
        
    except Exception as e:
        logger.error(f"Error deactivating model: {e}", exc_info=True)
        return _fail(str(e), 500)


@readiness_bp.get("/irrigation/<int:unit_id>/status")
def get_activation_status(unit_id: int):
    """
    Get activation status of all ML models for a unit.
    
    Response:
    {
        "ok": true,
        "data": {
            "response_predictor": true,
            "threshold_optimizer": false,
            "duration_optimizer": false,
            "timing_predictor": false
        }
    }
    """
    try:
        container = _container()
        
        ml_monitor = getattr(container, 'ml_readiness_monitor', None)
        if not ml_monitor:
            from app.services.ai.ml_readiness_monitor import MLReadinessMonitorService
            from infrastructure.database.repositories.irrigation_ml import IrrigationMLRepository
            
            ml_repo = IrrigationMLRepository(container.database)
            ml_monitor = MLReadinessMonitorService(
                irrigation_ml_repo=ml_repo,
                notifications_service=container.notifications_service,
            )
        
        status = ml_monitor.get_activation_status(unit_id)
        return _success(status)
        
    except Exception as e:
        logger.error(f"Error getting activation status: {e}", exc_info=True)
        return _fail(str(e), 500)


@readiness_bp.post("/check-all")
def check_all_units():
    """
    Manually trigger ML readiness check for all units.
    
    This is normally run as a scheduled task, but can be
    triggered manually for testing.
    
    Response:
    {
        "ok": true,
        "data": {
            "units_checked": 5,
            "notifications_sent": {
                1: ["response_predictor"],
                3: ["threshold_optimizer", "duration_optimizer"]
            }
        }
    }
    """
    try:
        container = _container()
        
        ml_monitor = getattr(container, 'ml_readiness_monitor', None)
        if not ml_monitor:
            from app.services.ai.ml_readiness_monitor import MLReadinessMonitorService
            from infrastructure.database.repositories.irrigation_ml import IrrigationMLRepository
            
            ml_repo = IrrigationMLRepository(container.database)
            ml_monitor = MLReadinessMonitorService(
                irrigation_ml_repo=ml_repo,
                notifications_service=container.notifications_service,
            )
        
        results = ml_monitor.check_all_units()
        
        return _success({
            "units_checked": len(results),
            "notifications_sent": results,
        })
        
    except Exception as e:
        logger.error(f"Error checking all units: {e}", exc_info=True)
        return _fail(str(e), 500)
