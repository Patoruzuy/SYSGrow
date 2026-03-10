"""Typed repository for database maintenance operations."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from app.utils.time import iso_now
from infrastructure.database.ops.maintenance import MaintenanceOperations


class MaintenanceRepository:
    """Repository providing typed access to database maintenance operations.

    Parameters
    ----------
    backend:
        The database handler (``SQLiteDatabaseHandler``) which implements
        :class:`~infrastructure.database.ops.maintenance.MaintenanceOperations`.
    """

    def __init__(self, backend: MaintenanceOperations) -> None:
        self._backend = backend

    # ------------------------------------------------------------------
    # Backup
    # ------------------------------------------------------------------

    def create_backup(
        self,
        *,
        label: str = "manual",
        directory: str | Path | None = None,
    ) -> dict[str, Any]:
        """Create an online SQLite backup and return metadata.

        Parameters
        ----------
        label:
            Short tag embedded in the backup filename (max 48 chars).
        directory:
            Destination directory.  Defaults to ``<db_dir>/backups/``.

        Returns
        -------
        dict with keys: ``directory``, ``filename``, ``bytes``, ``created_at``.

        Raises
        ------
        FileNotFoundError
            When the source database file does not exist.
        """
        from pathlib import Path as _Path

        db_path = _Path(self._backend._database_path)  # type: ignore[attr-defined]
        safe_label = label.strip()[:48] or "manual"
        backup_dir = _Path(directory) if directory else db_path.parent / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{db_path.stem}_{safe_label}_{timestamp}.db"
        backup_path = backup_dir / backup_name

        size = self._backend.backup_database(backup_path)

        return {
            "directory": str(backup_dir.as_posix()),
            "filename": backup_name,
            "bytes": size,
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
        """Delete (or count) sensor readings older than *retention_days*.

        Parameters
        ----------
        retention_days:
            How many days of data to keep.
        unit_id:
            Restrict to sensors in this growth unit (optional).
        dry_run:
            Report the count without deleting when ``True``.
        vacuum:
            Run ``VACUUM`` after deletion (ignored when ``dry_run=True``).

        Returns
        -------
        dict with keys: ``deleted``, ``dry_run``, ``vacuum``, ``unit_id``,
        ``retention_days``, ``cutoff``.
        """
        cutoff_dt = datetime.now() - timedelta(days=retention_days)
        cutoff = cutoff_dt.strftime("%Y-%m-%d %H:%M:%S")

        if dry_run:
            deleted = self._backend.count_sensor_readings_before(cutoff, unit_id)
        else:
            deleted = self._backend.delete_sensor_readings_before(cutoff, unit_id)
            if vacuum:
                self._backend.vacuum_database()

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

        Returns
        -------
        dict with keys: ``vacuum``, ``timestamp``.
        """
        self._backend.vacuum_database()
        return {"vacuum": True, "timestamp": iso_now()}

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    def get_table_row_counts(
        self,
        tables: tuple[str, ...] | None = None,
    ) -> dict[str, int]:
        """Return ``{table_name: row_count}`` for the given (or default) tables."""
        return self._backend.get_table_row_counts(tables)

    def get_database_size_info(self) -> dict[str, Any]:
        """Return size information (MB) about the main DB, WAL, and SHM files."""
        return self._backend.get_database_size_info()
