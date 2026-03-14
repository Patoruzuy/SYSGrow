"""
ML Base API
===========
Base ML endpoints that don't fit in other specific blueprints.

Provides:
- /api/ml/health - System health check
- /api/ml/training/history - Training history across all models
"""

import logging
from flask import Blueprint, jsonify, request

from app.blueprints.api._common import (
    get_container as _container,
    success as _success,
    fail as _fail,
)

logger = logging.getLogger(__name__)

base_bp = Blueprint("ml_base", __name__, url_prefix="/api/ml")


@base_bp.get("/health")
def ml_health():
    """
    ML system health check.
    
    Returns:
    {
        "healthy": true,
        "components": {
            "model_registry": true,
            "drift_detector": true,
            "retraining_service": true
        }
    }
    """
    try:
        container = _container()
        
        components = {
            "model_registry": container.model_registry is not None,
            "drift_detector": container.drift_detector is not None,
            "retraining_service": container.automated_retraining is not None,
        }
        
        healthy = all(components.values())
        
        return jsonify({
            "healthy": healthy,
            "components": components
        })
        
    except Exception as e:
        logger.error(f"Health check failed: {e}", exc_info=True)
        return jsonify({
            "healthy": False,
            "error": str(e)
        }), 500


@base_bp.get("/training/history")
def get_training_history():
    """
    Get training history across all models.
    
    Query params:
    - days: Number of days (default: 30)
    - limit: Max results (default: 50)
    
    Returns:
    {
        "history": [
            {
                "model_name": "climate_predictor",
                "version": "1.0.0",
                "accuracy": 0.87,
                "mae": 0.91,
                "data_points": 800,
                "trained_at": "2025-11-22T18:20:48",
                "status": "success"
            },
            ...
        ]
    }
    """
    try:
        container = _container()
        registry = container.model_registry
        
        # Build history from model registry
        history = []
        models = registry.list_models()
        
        for model in models:
            metrics = {}
            if model.get("accuracy"):
                metrics["accuracy"] = model["accuracy"]
            if model.get("mae"):
                metrics["mae"] = model["mae"]
            if model.get("r2"):
                metrics["r2"] = model["r2"]
                
            history.append({
                "model_name": model["name"],
                "version": model.get("latest_version", "unknown"),
                "accuracy": model.get("accuracy"),
                "mae": model.get("mae"),
                "data_points": None,  # Would need to store this in registry
                "trained_at": model.get("trained_at"),
                "status": "success" if model.get("active") else "inactive"
            })
        
        return _success({
            "history": history,
            "count": len(history)
        })
        
    except Exception as e:
        logger.error(f"Error getting training history: {e}", exc_info=True)
        return _fail(str(e), 500)


@base_bp.post("/training/cancel")
def cancel_training():
    """
    Cancel an active training/retraining job.

    Body:
    {
        "model_name": "climate"  // optional
        "event_id": "climate_..."  // optional
    }

    If both are omitted, attempts to cancel all active training jobs.
    """
    try:
        container = _container()
        retraining_service = getattr(container, "automated_retraining", None) if container else None
        if not retraining_service:
            return _fail("Retraining service not available", 503)

        payload = request.get_json(silent=True) or {}
        model_name = (payload.get("model_name") or payload.get("model_type") or "").strip() or None
        event_id = (payload.get("event_id") or "").strip() or None

        model_type = model_name
        if model_type:
            lowered = model_type.lower()
            if lowered.startswith("climate") or "irrigation" in lowered:
                model_type = "climate"
            elif "disease" in lowered:
                model_type = "disease"
            elif "growth" in lowered or "yield" in lowered:
                model_type = "growth_stage"

        cancelled = retraining_service.cancel_training(model_type=model_type, event_id=event_id)
        if not cancelled:
            return _fail("No active training job to cancel", 404)

        return _success(
            {
                "success": True,
                "message": "Cancellation requested",
                "model_name": model_name,
                "event_id": event_id,
            }
        )

    except Exception as e:
        logger.error(f"Error cancelling training: {e}", exc_info=True)
        return _fail(str(e), 500)
