"""Database Maintenance Service
==============================

Encapsulates all database maintenance operations: backup, prune, vacuum,
and table statistics.  Blueprint routes should call this service instead of
performing raw SQL against the SQLite database directly.
"""

from __future__ import annotations

import logging
import sqlite3
from contextlib import suppress
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from app.utils.time import iso_now

logger = logging.getLogger(__name__)


class DatabaseMaintenanceService:
    """Service for database maintenance operations.

    Parameters
    ----------
    db_path:
        Path to the main SQLite database file.
    """

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = Path(db_path)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        """Open a dedicated connection with a generous timeout."""
        conn = sqlite3.connect(str(self._db_path), timeout=30, check_same_thread=False)
        with suppress(Exception):
            conn.execute("PRAGMA busy_timeout = 30000")
        return conn

    # ------------------------------------------------------------------
    # Backup
    # ------------------------------------------------------------------

    def create_backup(
        self,
        *,
        label: str = "manual",
        directory: str | Path | None = None,
    ) -> dict[str, Any]:
        """Create an online SQLite backup using the backup API.

        Parameters
        ----------
        label:
            Short tag embedded in the backup filename.
        directory:
            Destination directory.  Defaults to ``<db_dir>/backups/``.

        Returns
        -------
        dict with ``directory``, ``filename``, ``bytes``, ``created_at``.

        Raises
        ------
        FileNotFoundError
            If the main database file does not exist.
        """
        if not self._db_path.exists():
            raise FileNotFoundError("Database file does not exist")

        safe_label = label.strip()[:48] or "manual"
        backup_dir = Path(directory) if directory else self._db_path.parent / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{self._db_path.stem}_{safe_label}_{timestamp}.db"
        backup_path = backup_dir / backup_name

        src = self._connect()
        try:
            dst = self._connect()
            try:
                src.backup(dst)
                dst.commit()
            finally:
                dst.close()
        finally:
            src.close()

        return {
            "directory": str(backup_dir.as_posix()),
            "filename": backup_name,
            "bytes": backup_path.stat().st_size if backup_path.exists() else None,
            "created_at": iso_now(),
        }

    # ------------------------------------------------------------------
    # Prune
    # ------------------------------------------------------------------

    def prune_sensor_readings(
        self,
        *,
        retention_days: int,
        unit_id: int | None = None,
        dry_run: bool = False,
        vacuum: bool = False,
    ) -> dict[str, Any]:
        """Delete sensor readings older than *retention_days*.

        Parameters
        ----------
        retention_days:
            How many days of data to keep.
        unit_id:
            Optional — restrict deletion to readings belonging to sensors
            in this growth unit.
        dry_run:
            If ``True``, report the count without actually deleting.
        vacuum:
            If ``True`` *and* not a dry run, run ``VACUUM`` after the delete.

        Returns
        -------
        dict with ``deleted``, ``dry_run``, ``vacuum``, ``unit_id``,
        ``retention_days``, ``cutoff``.
        """
        if not self._db_path.exists():
            raise FileNotFoundError("Database file does not exist")

        cutoff_dt = datetime.now() - timedelta(days=retention_days)
        cutoff = cutoff_dt.strftime("%Y-%m-%d %H:%M:%S")

        deleted = 0
        conn = self._connect()
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
                        "SELECT COUNT(1) AS cnt "
                        "FROM SensorReading sr "
                        "JOIN Sensor s ON s.sensor_id = sr.sensor_id "
                        "WHERE s.unit_id = ? AND datetime(sr.timestamp) < datetime(?)",
                        (unit_id, cutoff),
                    )
                    row = cur.fetchone()
                    deleted = int(row[0]) if row else 0
                else:
                    cur = conn.execute(
                        "DELETE FROM SensorReading "
                        "WHERE reading_id IN ("
                        "  SELECT sr.reading_id "
                        "  FROM SensorReading sr "
                        "  JOIN Sensor s ON s.sensor_id = sr.sensor_id "
                        "  WHERE s.unit_id = ? AND datetime(sr.timestamp) < datetime(?)"
                        ")",
                        (unit_id, cutoff),
                    )
                    deleted = int(cur.rowcount or 0)
                    conn.commit()

            if vacuum and not dry_run:
                conn.execute("VACUUM")
                conn.commit()
        finally:
            conn.close()

        return {
            "deleted": deleted,
            "dry_run": dry_run,
            "vacuum": vacuum and (not dry_run),
            "unit_id": unit_id,
            "retention_days": retention_days,
            "cutoff": cutoff_dt.isoformat(),
        }

    # ------------------------------------------------------------------
    # Vacuum
    # ------------------------------------------------------------------

    def vacuum(self) -> dict[str, Any]:
        """Run ``VACUUM`` to reclaim disk space.

        Raises
        ------
        FileNotFoundError
            If the database file does not exist.
        """
        if not self._db_path.exists():
            raise FileNotFoundError("Database file does not exist")

        conn = self._connect()
        try:
            conn.execute("VACUUM")
            conn.commit()
        finally:
            conn.close()

        return {"vacuum": True, "timestamp": iso_now()}

    # ------------------------------------------------------------------
    # Table statistics
    # ------------------------------------------------------------------

    _KEY_TABLES = (
        "SensorReading",
        "ActuatorStateHistory",
        "GrowthUnits",
        "Plants",
        "Sensor",
        "Actuator",
        "Alerts",
        "NotificationHistory",
    )

    def get_table_row_counts(self, tables: tuple[str, ...] | None = None) -> dict[str, int]:
        """Return ``{table_name: row_count}`` for a fixed set of key tables.

        Parameters
        ----------
        tables:
            Explicit list of table names.  Defaults to :pyattr:`_KEY_TABLES`.
        """
        tables = tables or self._KEY_TABLES
        counts: dict[str, int] = {}
        conn = self._connect()
        try:
            for table in tables:
                try:
                    # table names come from an internal constant, not user input
                    cursor = conn.execute(
                        f"SELECT COUNT(*) FROM {table}"  # nosec B608
                    )
                    counts[table] = cursor.fetchone()[0]
                except Exception as exc:
                    logger.debug("Skipping row count for table %s: %s", table, exc)
        finally:
            conn.close()
        return counts

    # ------------------------------------------------------------------
    # DB size info
    # ------------------------------------------------------------------

    def get_database_size_info(self) -> dict[str, Any]:
        """Return size information about the SQLite database files."""
        info: dict[str, Any] = {
            "main_db_mb": 0,
            "wal_mb": 0,
            "shm_mb": 0,
            "total_mb": 0,
            "warning": False,
            "critical": False,
        }
        if not self._db_path.exists():
            return info

        info["main_db_mb"] = round(self._db_path.stat().st_size / (1024 * 1024), 2)

        wal = self._db_path.with_suffix(".db-wal")
        if wal.exists():
            info["wal_mb"] = round(wal.stat().st_size / (1024 * 1024), 2)

        shm = self._db_path.with_suffix(".db-shm")
        if shm.exists():
            info["shm_mb"] = round(shm.stat().st_size / (1024 * 1024), 2)

        info["total_mb"] = round(info["main_db_mb"] + info["wal_mb"] + info["shm_mb"], 2)
        info["warning"] = info["total_mb"] > 100
        info["critical"] = info["total_mb"] > 500
        return info
