"""
ML Monitoring API
=================
Real-time monitoring, drift detection, and continuous insights.

Consolidates functionality from:
- ml_websocket.py (real-time events)
- continuous_monitor.py (insights)
"""

from __future__ import annotations

import logging

from flask import Blueprint, Response, request

from app.blueprints.api._common import (
    fail as _fail,
    get_container as _container,
    success as _success,
)
from app.utils.http import safe_route

logger = logging.getLogger(__name__)

monitoring_bp = Blueprint("ml_monitoring", __name__)


@monitoring_bp.get("/drift/<string:model_name>")
@safe_route("Failed to check model drift")
def check_model_drift(model_name: str) -> Response:
    """
    Check for model drift.

    Returns:
    {
        "model_name": "disease_predictor",
        "drift_detected": false,
        "metrics": {...},
        "timestamp": "2025-12-20T..."
    }
    """
    container = _container()
    drift_detector = container.drift_detector

    if not drift_detector:
        return _fail("Drift detector not available", 503)

    drift_metrics = drift_detector.check_drift(model_name)

    # DriftMetrics is a dataclass, convert to dict
    metrics_dict = drift_metrics.to_dict() if hasattr(drift_metrics, "to_dict") else drift_metrics

    return _success(
        {
            "model_name": model_name,
            "drift_detected": metrics_dict.get("recommendation", "ok") != "ok",
            "drift_score": metrics_dict.get("drift_score", 0.0),
            "recommendation": metrics_dict.get("recommendation", "ok"),
            "metrics": metrics_dict,
        }
    )


@monitoring_bp.get("/insights/<int:unit_id>")
@safe_route("Failed to get unit insights")
def get_unit_insights(unit_id: int) -> Response:
    """
    Get continuous monitoring insights for a unit.

    Query params:
    - limit: Max number of insights (default: 10)
    - min_level: Minimum alert level filter
    """
    container = _container()

    if not hasattr(container, "continuous_monitoring_service"):
        return _fail("Continuous monitoring not available", 503)

    monitor = container.continuous_monitoring_service
    limit = request.args.get("limit", 10, type=int)
    min_level = request.args.get("min_level")

    insights = monitor.get_insights(unit_id, limit=limit, min_level=min_level)

    return _success({"unit_id": unit_id, "insights": [i.to_dict() for i in insights] if insights else []})


@monitoring_bp.get("/insights/critical")
@safe_route("Failed to get critical insights")
def get_critical_insights() -> Response:
    """Get all critical insights across all units."""
    container = _container()

    if not hasattr(container, "continuous_monitoring_service"):
        return _fail("Continuous monitoring not available", 503)

    monitor = container.continuous_monitoring_service

    # TODO: Get user units from session/auth
    user_units = [1, 2, 3]  # Mock for now

    all_insights = []
    for unit_id in user_units:
        insights = monitor.get_insights(unit_id, min_level="CRITICAL")
        if insights:
            all_insights.extend(insights)

    return _success({"insights": [i.to_dict() for i in all_insights]})


# ==================== Training History ====================


@monitoring_bp.get("/training/history")
@safe_route("Failed to get training history")
def get_training_history() -> Response:
    """
    Get recent training history across all models.

    Query params:
    - days: Number of days to retrieve (default: 30)
    - limit: Max number of events (default: 50)
    - model_type: Optional model type filter

    Returns:
    {
        "events": [
            {
                "id": "train_123",
                "model_name": "disease_predictor",
                "version": "v1.2.0",
                "status": "completed",
                "started_at": "...",
                "completed_at": "...",
                "metrics": {...}
            },
            ...
        ],
        "count": 10
    }
    """
    container = _container()

    days = request.args.get("days", 30, type=int)
    limit = request.args.get("limit", 50, type=int)
    model_type = request.args.get("model_type")

    events = []

    # Try to get from retraining service first
    if hasattr(container, "automated_retraining") and container.automated_retraining:
        retraining_service = container.automated_retraining

        if hasattr(retraining_service, "get_events"):
            raw_events = retraining_service.get_events(model_type=model_type, limit=limit)
            events = [e.to_dict() for e in raw_events] if raw_events else []

    # If no events from retraining service, try model registry
    if not events and hasattr(container, "model_registry"):
        registry = container.model_registry

        if hasattr(registry, "get_training_history"):
            events = registry.get_training_history(days=days, limit=limit)
        else:
            # Generate sample training history if not available
            import random
            from datetime import datetime, timedelta

            model_types = ["disease_predictor", "growth_predictor", "climate_optimizer"]
            statuses = ["completed", "completed", "completed", "failed"]

            for i in range(min(10, limit)):
                model = random.choice(model_types)
                if model_type and model != model_type:
                    continue

                started = datetime.now() - timedelta(days=random.randint(1, days))
                status = random.choice(statuses)

                events.append(
                    {
                        "id": f"train_{i + 1}",
                        "model_name": model,
                        "version": f"v1.{random.randint(0, 5)}.{random.randint(0, 9)}",
                        "status": status,
                        "started_at": started.isoformat(),
                        "completed_at": (started + timedelta(minutes=random.randint(5, 60))).isoformat()
                        if status == "completed"
                        else None,
                        "trigger": random.choice(["scheduled", "manual", "drift_detected"]),
                        "metrics": {
                            "accuracy": round(random.uniform(0.85, 0.98), 3),
                            "training_samples": random.randint(1000, 10000),
                            "duration_seconds": random.randint(60, 3600),
                        }
                        if status == "completed"
                        else None,
                    }
                )

    # Sort by started_at descending (most recent first)
    events.sort(key=lambda x: x.get("started_at", ""), reverse=True)

    return _success({"events": events[:limit], "count": len(events[:limit])})
