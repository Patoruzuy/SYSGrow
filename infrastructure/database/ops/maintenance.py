"""Database operations for maintenance tasks.

Provides the ``MaintenanceOperations`` mixin consumed by
``SQLiteDatabaseHandler``.  Includes:

- Backup (SQLite online backup API)
- Sensor-reading pruning
- VACUUM
- Table row-count statistics
- Database file size information
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_BACKUP_CONNECT_TIMEOUT_SECONDS = 30.0
_SQLITE_BUSY_TIMEOUT_MS = 30_000

# Tables reported by default in stats queries.
_DEFAULT_STAT_TABLES: tuple[str, ...] = (
    "SensorReading",
    "ActuatorStateHistory",
    "GrowthUnits",
    "Plants",
    "Sensor",
    "Actuator",
    "Alerts",
    "NotificationHistory",
)


class MaintenanceOperations:
    """Mixin providing maintenance SQL operations.

    Intended to be mixed into :class:`~infrastructure.database.sqlite_handler.SQLiteDatabaseHandler`.
    All methods call ``self.get_db()`` to obtain the thread-local connection and
    may read ``self._database_path`` for file-level operations.
    """

    # ------------------------------------------------------------------
    # Backup
    # ------------------------------------------------------------------

    def _database_path_obj(self) -> Path:
        """Return the configured SQLite database path."""
        return Path(self._database_path)  # type: ignore[attr-defined]

    def _require_existing_database(self) -> Path:
        """Return the database path, raising if the file is missing."""
        db_path = self._database_path_obj()
        if not db_path.exists():
            raise FileNotFoundError(f"Database not found: {db_path}")
        return db_path

    def _open_maintenance_connection(self, path: Path) -> sqlite3.Connection:
        """Open a dedicated SQLite connection with the legacy busy timeout."""
        connection = sqlite3.connect(
            str(path),
            timeout=_BACKUP_CONNECT_TIMEOUT_SECONDS,
            check_same_thread=False,
        )
        connection.execute(f"PRAGMA busy_timeout = {_SQLITE_BUSY_TIMEOUT_MS}")
        return connection

    def backup_database(
        self,
        backup_path: str | Path,
    ) -> int:
        """Copy the live database to *backup_path* using the SQLite backup API.

        Parameters
        ----------
        backup_path:
            Full filesystem path for the destination ``.db`` file.

        Returns
        -------
        int
            Size in bytes of the written backup file.

        Raises
        ------
        FileNotFoundError
            If the source database file does not exist.
        RuntimeError
            If the backup write fails.
        """
        src_path = self._require_existing_database()

        backup_path = Path(backup_path)
        backup_path.parent.mkdir(parents=True, exist_ok=True)

        # Use dedicated connections — the backup API requires a live source
        # connection and a writable destination connection.
        src: sqlite3.Connection = self._open_maintenance_connection(src_path)
        try:
            dst: sqlite3.Connection = self._open_maintenance_connection(backup_path)
            try:
                src.backup(dst)
                dst.commit()
            finally:
                dst.close()
        finally:
            src.close()

        if not backup_path.exists():
            raise RuntimeError(f"Backup file was not created at {backup_path}")

        return backup_path.stat().st_size

    # ------------------------------------------------------------------
    # Prune
    # ------------------------------------------------------------------

    def count_sensor_readings_before(
        self,
        cutoff: str,
        unit_id: int | None = None,
    ) -> int:
        """Count sensor readings older than *cutoff*.

        Parameters
        ----------
        cutoff:
            ISO-8601 datetime string used as the upper bound (exclusive).
        unit_id:
            When provided, restrict the count to sensors in that unit.
        """
        self._require_existing_database()
        try:
            db = self.get_db()  # type: ignore[attr-defined]
            if unit_id is None:
                cur = db.execute(
                    "SELECT COUNT(1) FROM SensorReading WHERE datetime(timestamp) < datetime(?)",
                    (cutoff,),
                )
            else:
                cur = db.execute(
                    "SELECT COUNT(1) "
                    "FROM SensorReading sr "
                    "JOIN Sensor s ON s.sensor_id = sr.sensor_id "
                    "WHERE s.unit_id = ? AND datetime(sr.timestamp) < datetime(?)",
                    (unit_id, cutoff),
                )
            row = cur.fetchone()
            return int(row[0]) if row else 0
        except sqlite3.Error as exc:
            logger.error("count_sensor_readings_before failed: %s", exc)
            raise

    def delete_sensor_readings_before(
        self,
        cutoff: str,
        unit_id: int | None = None,
    ) -> int:
        """Delete sensor readings older than *cutoff*.

        Parameters
        ----------
        cutoff:
            ISO-8601 datetime string used as the upper bound (exclusive).
        unit_id:
            When provided, restrict the deletion to sensors in that unit.

        Returns
        -------
        int
            Number of rows deleted.
        """
        self._require_existing_database()
        try:
            db = self.get_db()  # type: ignore[attr-defined]
            if unit_id is None:
                cur = db.execute(
                    "DELETE FROM SensorReading WHERE datetime(timestamp) < datetime(?)",
                    (cutoff,),
                )
            else:
                cur = db.execute(
                    "DELETE FROM SensorReading "
                    "WHERE reading_id IN ("
                    "  SELECT sr.reading_id "
                    "  FROM SensorReading sr "
                    "  JOIN Sensor s ON s.sensor_id = sr.sensor_id "
                    "  WHERE s.unit_id = ? AND datetime(sr.timestamp) < datetime(?)"
                    ")",
                    (unit_id, cutoff),
                )
            db.commit()
            return int(cur.rowcount or 0)
        except sqlite3.Error as exc:
            logger.error("delete_sensor_readings_before failed: %s", exc)
            raise

    # ------------------------------------------------------------------
    # Vacuum
    # ------------------------------------------------------------------

    def vacuum_database(self) -> None:
        """Run ``VACUUM`` to reclaim free pages and defragment the database."""
        self._require_existing_database()
        try:
            db = self.get_db()  # type: ignore[attr-defined]
            db.execute("VACUUM")
            db.commit()
        except sqlite3.Error as exc:
            logger.error("vacuum_database failed: %s", exc)
            raise

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    def get_table_row_counts(
        self,
        tables: tuple[str, ...] | None = None,
    ) -> dict[str, int]:
        """Return ``{table_name: row_count}`` for the given (or default) tables.

        Table names come from a trusted internal constant — the
        ``# nosec`` comment silences Bandit B608 accordingly.
        """
        tables = tables or _DEFAULT_STAT_TABLES
        counts: dict[str, int] = {}
        if not self._database_path_obj().exists():
            return counts

        db = self.get_db()  # type: ignore[attr-defined]
        for table in tables:
            try:
                cur = db.execute(f"SELECT COUNT(*) FROM {table}")  # nosec B608
                counts[table] = cur.fetchone()[0]
            except sqlite3.Error as exc:
                logger.debug("Skipping row count for table %s: %s", table, exc)
        return counts

    # ------------------------------------------------------------------
    # File-size info
    # ------------------------------------------------------------------

    def get_database_size_info(self) -> dict[str, Any]:
        """Return size (in MB) for the main ``.db``, WAL, and SHM files."""
        db_path = Path(self._database_path)  # type: ignore[attr-defined]
        info: dict[str, Any] = {
            "main_db_mb": 0.0,
            "wal_mb": 0.0,
            "shm_mb": 0.0,
            "total_mb": 0.0,
            "warning": False,
            "critical": False,
        }
        if not db_path.exists():
            return info

        info["main_db_mb"] = round(db_path.stat().st_size / (1024 * 1024), 2)

        wal = db_path.with_suffix(".db-wal")
        if wal.exists():
            info["wal_mb"] = round(wal.stat().st_size / (1024 * 1024), 2)

        shm = db_path.with_suffix(".db-shm")
        if shm.exists():
            info["shm_mb"] = round(shm.stat().st_size / (1024 * 1024), 2)

        info["total_mb"] = round(info["main_db_mb"] + info["wal_mb"] + info["shm_mb"], 2)
        info["warning"] = info["total_mb"] > 100
        info["critical"] = info["total_mb"] > 500
        return info
