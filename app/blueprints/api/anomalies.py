"""Anomaly Detection API
========================

Endpoints for querying persisted sensor anomalies.

Routes:
    GET  /api/anomalies          — List recent anomalies (filterable)
    GET  /api/anomalies/summary  — Quick counts / severity breakdown
"""

from __future__ import annotations

import logging

from flask import Blueprint, Response, request

from app.security.auth import api_login_required
from app.utils.http import error_response, safe_route, success_response

logger = logging.getLogger(__name__)

anomalies_api = Blueprint("anomalies_api", __name__)


def _get_anomaly_repo():
    """Resolve the SensorAnomalyRepository from the app container."""
    from flask import current_app

    container = current_app.config.get("CONTAINER")
    if not container:
        return None
    # Try direct attribute first, fall back to building one on the fly
    repo = getattr(container, "sensor_anomaly_repo", None)
    if repo:
        return repo
    # Fallback: construct from the database handler
    from infrastructure.database.repositories.sensor_anomaly import SensorAnomalyRepository

    return SensorAnomalyRepository(container.database)


@anomalies_api.get("/")
@api_login_required
@safe_route("Failed to list anomalies")
def list_anomalies() -> Response:
    """List recent sensor anomalies with optional filters.

    Query parameters:
        sensor_id    (int, optional)  — filter by sensor
        unit_id      (int, optional)  — filter by growth unit
        since        (str, optional)  — ISO-8601 lower-bound on detected_at
        severity_min (float, optional) — minimum severity (0.0-1.0)
        resolved     (bool, optional) — include resolved anomalies (default false)
        limit        (int, optional)  — max rows (default 100)

    Returns:
        ``{"anomalies": [...], "total": <int>}``
    """
    repo = _get_anomaly_repo()
    if not repo:
        return error_response("Anomaly service not available", 500)

    sensor_id = request.args.get("sensor_id", type=int)
    unit_id = request.args.get("unit_id", type=int)
    since = request.args.get("since")
    severity_min = request.args.get("severity_min", type=float)
    include_resolved = request.args.get("resolved", "false").lower() in {"1", "true", "yes"}
    limit = min(request.args.get("limit", 100, type=int), 500)

    anomalies = repo.list_recent(
        sensor_id=sensor_id,
        unit_id=unit_id,
        since=since,
        severity_min=severity_min,
        include_resolved=include_resolved,
        limit=limit,
    )
    return success_response({"anomalies": anomalies, "total": len(anomalies)})


@anomalies_api.get("/summary")
@api_login_required
@safe_route("Failed to get anomaly summary")
def anomaly_summary() -> Response:
    """Quick anomaly count and severity breakdown.

    Query parameters:
        unit_id   (int, optional) — scope to a growth unit
        sensor_id (int, optional) — scope to a single sensor

    Returns:
        ``{"active_count": <int>}``
    """
    repo = _get_anomaly_repo()
    if not repo:
        return error_response("Anomaly service not available", 500)

    sensor_id = request.args.get("sensor_id", type=int)
    active = repo.count_active(sensor_id=sensor_id)
    return success_response({"active_count": active})
