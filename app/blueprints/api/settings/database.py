"""Database Maintenance Settings API
=================================

Backend endpoints for real database maintenance actions:
- Create SQLite backup files
- Prune old SensorReading rows (optionally per unit)
- VACUUM database to reclaim disk space

These endpoints delegate all SQL work to
:class:`~app.services.utilities.database_maintenance_service.DatabaseMaintenanceService`.
"""

from __future__ import annotations

import logging
from typing import Any

from flask import Response, request

from app.blueprints.api._common import (
    get_container as _get_container,
)
from app.blueprints.api.settings import settings_api
from app.security.auth import api_login_required
from app.services.utilities.database_maintenance_service import DatabaseMaintenanceService
from app.utils.http import error_response, safe_route, success_response

logger = logging.getLogger(__name__)


def _bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, int | float):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "t", "yes", "y", "on"}
    return default


def _get_maintenance_service() -> DatabaseMaintenanceService | None:
    """Resolve the database path and return a service instance."""
    container = _get_container()
    if not container:
        return None
    config = getattr(container, "config", None)
    database_path = getattr(config, "database_path", None)
    if not database_path:
        return None
    return DatabaseMaintenanceService(database_path)


@settings_api.post("/database/backup")
@api_login_required
@safe_route("Failed to create database backup")
def create_database_backup() -> Response:
    """Create a SQLite backup file and return its filename.

    Request JSON (optional):
      {
        "label": "manual",
        "directory": "database/backups"
      }

    Notes:
    - If directory is omitted, backups are stored under ``<db_dir>/backups/``.
    - Returns only the backup filename and relative directory for safety.
    """
    svc = _get_maintenance_service()
    if not svc:
        return error_response("Service container not available", 500)

    payload = request.get_json(silent=True) or {}
    label = str(payload.get("label") or "manual").strip()[:48] or "manual"
    directory = payload.get("directory")

    try:
        result = svc.create_backup(label=label, directory=directory)
    except FileNotFoundError as exc:
        return error_response(str(exc), 404)

    return success_response({"backup": result}, message="Database backup created")


@settings_api.post("/database/prune")
@api_login_required
@safe_route("Failed to prune sensor readings")
def prune_sensor_readings() -> Response:
    """Prune old SensorReading rows.

    Request JSON:
      {
        "retention_days": 90,
        "unit_id": 1,            // optional
        "dry_run": false,        // optional
        "vacuum": false          // optional
      }

    Returns:
      {"deleted": <int>, "cutoff": <iso>, "unit_id": <int|null>}
    """
    svc = _get_maintenance_service()
    if not svc:
        return error_response("Service container not available", 500)

    payload = request.get_json(silent=True) or {}
    retention_days = payload.get("retention_days")
    if retention_days is None:
        return error_response("retention_days is required", 400)
    try:
        retention_days_int = int(retention_days)
    except Exception:
        return error_response("retention_days must be an integer", 400)
    if retention_days_int < 0:
        return error_response("retention_days must be >= 0", 400)

    unit_id = payload.get("unit_id")
    if unit_id is not None:
        try:
            unit_id = int(unit_id)
        except Exception:
            return error_response("unit_id must be an integer", 400)

    dry_run = _bool(payload.get("dry_run"), default=False)
    vacuum = _bool(payload.get("vacuum"), default=False)

    try:
        result = svc.prune_sensor_readings(
            retention_days=retention_days_int,
            unit_id=unit_id,
            dry_run=dry_run,
            vacuum=vacuum,
        )
    except FileNotFoundError as exc:
        return error_response(str(exc), 404)

    msg = "Prune preview" if dry_run else "Prune completed"
    return success_response(result, message=msg)


@settings_api.post("/database/vacuum")
@api_login_required
@safe_route("Failed to vacuum database")
def vacuum_database() -> Response:
    """Run SQLite VACUUM to reclaim disk space."""
    svc = _get_maintenance_service()
    if not svc:
        return error_response("Service container not available", 500)

    try:
        result = svc.vacuum()
    except FileNotFoundError as exc:
        return error_response(str(exc), 404)

    return success_response(result, message="VACUUM completed")
