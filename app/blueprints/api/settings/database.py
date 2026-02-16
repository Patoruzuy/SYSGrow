"""Database Maintenance Settings API
=================================

Backend endpoints for real database maintenance actions:
- Create SQLite backup files
- Prune old SensorReading rows (optionally per unit)
- VACUUM database to reclaim disk space

These endpoints are intentionally lightweight and return structured results so
the Settings UI can drive them.
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from flask import request

from app.blueprints.api._common import (
    get_container as _get_container,
)
from app.blueprints.api.settings import settings_api
from app.security.auth import api_login_required
from app.utils.http import error_response, success_response
from app.utils.time import iso_now

logger = logging.getLogger(__name__)


def _bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "t", "yes", "y", "on"}
    return default


def _db_path_from_container(container: Any) -> Path:
    config = getattr(container, "config", None)
    database_path = getattr(config, "database_path", None)
    if not database_path:
        raise RuntimeError("Database path not available")
    return Path(database_path)


def _sqlite_connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path), timeout=30, check_same_thread=False)
    try:
        conn.execute("PRAGMA busy_timeout = 30000")
    except Exception:
        # Best-effort; don't fail the request if pragma isn't supported.
        pass
    return conn


@settings_api.post("/database/backup")
@api_login_required
def create_database_backup():
    """Create a SQLite backup file and return its filename.

    Request JSON (optional):
      {
        "label": "manual",
        "directory": "database/backups"
      }

    Notes:
    - If directory is omitted, backups are stored under `<db_dir>/backups/`.
    - Returns only the backup filename and relative directory for safety.
    """
    try:
        container = _get_container()
        if not container:
            return error_response("Service container not available", 500)

        payload = request.get_json(silent=True) or {}
        label = str(payload.get("label") or "manual").strip()[:48] or "manual"

        db_path = _db_path_from_container(container)
        if not db_path.exists():
            return error_response("Database file does not exist", 404)

        default_backup_dir = db_path.parent / "backups"
        backup_dir_raw = payload.get("directory")
        backup_dir = Path(str(backup_dir_raw)) if backup_dir_raw else default_backup_dir
        # Keep relative directories relative to the app working dir; create dirs.
        backup_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{db_path.stem}_{label}_{timestamp}.db"
        backup_path = backup_dir / backup_name

        # Use SQLite online backup API for consistency.
        src = _sqlite_connect(db_path)
        try:
            dst = _sqlite_connect(backup_path)
            try:
                src.backup(dst)
                dst.commit()
            finally:
                dst.close()
        finally:
            src.close()

        result = {
            "backup": {
                "directory": str(backup_dir.as_posix()),
                "filename": backup_name,
                "bytes": backup_path.stat().st_size if backup_path.exists() else None,
                "created_at": iso_now(),
            }
        }
        return success_response(result, message="Database backup created")

    except Exception as exc:
        logger.exception("Error creating database backup")
        return error_response(f"Failed to create database backup: {exc}", 500)


@settings_api.post("/database/prune")
@api_login_required
def prune_sensor_readings():
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
    try:
        container = _get_container()
        if not container:
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

        db_path = _db_path_from_container(container)
        if not db_path.exists():
            return error_response("Database file does not exist", 404)

        cutoff_dt = datetime.now() - timedelta(days=retention_days_int)
        # Format in a way SQLite datetime() parses reliably.
        cutoff = cutoff_dt.strftime("%Y-%m-%d %H:%M:%S")

        deleted = 0
        conn = _sqlite_connect(db_path)
        try:
            if unit_id is None:
                if dry_run:
                    cur = conn.execute(
                        "SELECT COUNT(1) AS cnt FROM SensorReading WHERE datetime(timestamp) < datetime(?)",
                        (cutoff,),
                    )
                    row = cur.fetchone()
                    deleted = int(row[0]) if row else 0
                else:
                    cur = conn.execute(
                        "DELETE FROM SensorReading WHERE datetime(timestamp) < datetime(?)",
                        (cutoff,),
                    )
                    deleted = int(cur.rowcount or 0)
                    conn.commit()
            else:
                if dry_run:
                    cur = conn.execute(
                        """
                        SELECT COUNT(1) AS cnt
                        FROM SensorReading sr
                        JOIN Sensor s ON s.sensor_id = sr.sensor_id
                        WHERE s.unit_id = ? AND datetime(sr.timestamp) < datetime(?)
                        """,
                        (unit_id, cutoff),
                    )
                    row = cur.fetchone()
                    deleted = int(row[0]) if row else 0
                else:
                    cur = conn.execute(
                        """
                        DELETE FROM SensorReading
                        WHERE reading_id IN (
                            SELECT sr.reading_id
                            FROM SensorReading sr
                            JOIN Sensor s ON s.sensor_id = sr.sensor_id
                            WHERE s.unit_id = ? AND datetime(sr.timestamp) < datetime(?)
                        )
                        """,
                        (unit_id, cutoff),
                    )
                    deleted = int(cur.rowcount or 0)
                    conn.commit()

            if vacuum and not dry_run:
                conn.execute("VACUUM")
                conn.commit()
        finally:
            conn.close()

        result = {
            "deleted": deleted,
            "dry_run": dry_run,
            "vacuum": vacuum and (not dry_run),
            "unit_id": unit_id,
            "retention_days": retention_days_int,
            "cutoff": cutoff_dt.isoformat(),
        }
        msg = "Prune preview" if dry_run else "Prune completed"
        return success_response(result, message=msg)

    except Exception as exc:
        logger.exception("Error pruning sensor readings")
        return error_response(f"Failed to prune sensor readings: {exc}", 500)


@settings_api.post("/database/vacuum")
@api_login_required
def vacuum_database():
    """Run SQLite VACUUM to reclaim disk space."""
    try:
        container = _get_container()
        if not container:
            return error_response("Service container not available", 500)

        db_path = _db_path_from_container(container)
        if not db_path.exists():
            return error_response("Database file does not exist", 404)

        conn = _sqlite_connect(db_path)
        try:
            conn.execute("VACUUM")
            conn.commit()
        finally:
            conn.close()

        return success_response({"vacuum": True, "timestamp": iso_now()}, message="VACUUM completed")

    except Exception as exc:
        logger.exception("Error vacuuming database")
        return error_response(f"Failed to vacuum database: {exc}", 500)
