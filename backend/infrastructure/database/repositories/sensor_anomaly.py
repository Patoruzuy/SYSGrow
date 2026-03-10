"""Sensor Anomaly Repository
===========================

Persistence layer for detected sensor anomalies.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class SensorAnomalyRepository:
    """Read/write access to the ``SensorAnomaly`` table."""

    def __init__(self, db_handler: Any) -> None:
        self._db = db_handler

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def insert(
        self,
        *,
        sensor_id: int,
        anomaly_type: str,
        severity: float,
        value: float | None = None,
        expected_min: float | None = None,
        expected_max: float | None = None,
        description: str | None = None,
        detected_at: str | None = None,
    ) -> int | None:
        """Persist a single anomaly.

        Returns the new ``anomaly_id`` or ``None`` on failure.
        """
        sql = (
            "INSERT INTO SensorAnomaly "
            "(sensor_id, anomaly_type, severity, value, expected_min, expected_max, "
            " description, detected_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, COALESCE(?, CURRENT_TIMESTAMP))"
        )
        try:
            with self._db.connection() as conn:
                cursor = conn.execute(
                    sql,
                    (
                        sensor_id,
                        anomaly_type,
                        severity,
                        value,
                        expected_min,
                        expected_max,
                        description,
                        detected_at,
                    ),
                )
                conn.commit()
                return cursor.lastrowid
        except Exception:
            logger.exception("Failed to insert sensor anomaly for sensor %s", sensor_id)
            return None

    def resolve(self, anomaly_id: int) -> bool:
        """Mark an anomaly as resolved."""
        sql = "UPDATE SensorAnomaly SET resolved_at = CURRENT_TIMESTAMP WHERE anomaly_id = ?"
        try:
            with self._db.connection() as conn:
                conn.execute(sql, (anomaly_id,))
                conn.commit()
            return True
        except Exception:
            logger.exception("Failed to resolve anomaly %s", anomaly_id)
            return False

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def list_recent(
        self,
        *,
        sensor_id: int | None = None,
        unit_id: int | None = None,
        since: str | None = None,
        severity_min: float | None = None,
        include_resolved: bool = False,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Return recent anomalies with optional filters.

        Parameters
        ----------
        sensor_id:
            Filter by a single sensor.
        unit_id:
            Filter by growth-unit (joins through the Sensor table).
        since:
            ISO-8601 lower-bound on ``detected_at``.
        severity_min:
            Minimum severity (0.0-1.0).
        include_resolved:
            Whether to include already-resolved anomalies.
        limit:
            Max rows to return.
        """
        clauses = []
        params: list[Any] = []
        join_sensor = ""

        if unit_id is not None:
            join_sensor = " JOIN Sensor s ON s.sensor_id = a.sensor_id"
            clauses.append("s.unit_id = ?")
            params.append(unit_id)

        if sensor_id is not None:
            clauses.append("a.sensor_id = ?")
            params.append(sensor_id)

        if since:
            clauses.append("a.detected_at >= ?")
            params.append(since)

        if severity_min is not None:
            clauses.append("a.severity >= ?")
            params.append(severity_min)

        if not include_resolved:
            clauses.append("a.resolved_at IS NULL")

        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""

        sql = f"SELECT a.* FROM SensorAnomaly a{join_sensor}{where} ORDER BY a.detected_at DESC LIMIT ?"
        params.append(limit)

        try:
            with self._db.connection() as conn:
                conn.row_factory = _dict_factory
                cursor = conn.execute(sql, params)
                return cursor.fetchall()
        except Exception:
            logger.exception("Failed to query sensor anomalies")
            return []

    def count_active(self, *, sensor_id: int | None = None) -> int:
        """Count unresolved anomalies."""
        if sensor_id is not None:
            sql = "SELECT COUNT(*) FROM SensorAnomaly WHERE resolved_at IS NULL AND sensor_id = ?"
            params: tuple = (sensor_id,)
        else:
            sql = "SELECT COUNT(*) FROM SensorAnomaly WHERE resolved_at IS NULL"
            params = ()

        try:
            with self._db.connection() as conn:
                row = conn.execute(sql, params).fetchone()
                return int(row[0]) if row else 0
        except Exception:
            logger.exception("Failed to count active anomalies")
            return 0

    def purge_old(self, days: int = 30) -> int:
        """Delete resolved anomalies older than *days*."""
        sql = "DELETE FROM SensorAnomaly WHERE resolved_at IS NOT NULL AND detected_at < datetime('now', ?)"
        try:
            with self._db.connection() as conn:
                cur = conn.execute(sql, (f"-{days} days",))
                conn.commit()
                return cur.rowcount or 0
        except Exception:
            logger.exception("Failed to purge old anomalies")
            return 0


def _dict_factory(cursor: Any, row: Any) -> dict[str, Any]:
    """sqlite3 row_factory that returns dicts."""
    return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}
