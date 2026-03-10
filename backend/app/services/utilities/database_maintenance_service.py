"""Database Maintenance Service
==============================

Encapsulates all database maintenance operations: backup, prune, vacuum,
and table statistics.  Blueprint routes should call this service instead of
performing raw SQL against the SQLite database directly.

All SQL is delegated to
:class:`~infrastructure.database.repositories.maintenance.MaintenanceRepository`;
this service contains only orchestration/validation logic.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from infrastructure.database.repositories.maintenance import MaintenanceRepository

logger = logging.getLogger(__name__)


class DatabaseMaintenanceService:
    """Service for database maintenance operations.

    Parameters
    ----------
    repo:
        :class:`~infrastructure.database.repositories.maintenance.MaintenanceRepository`
        that handles all SQL and file-system work.
    """

    def __init__(self, repo: "MaintenanceRepository") -> None:
        self._repo = repo

    # ------------------------------------------------------------------
    # Backup
    # ------------------------------------------------------------------

    def create_backup(
        self,
        *,
        label: str = "manual",
        directory: str | Path | None = None,
    ) -> dict[str, Any]:
        """Create an online SQLite backup and return its metadata.

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
            If the source database file does not exist.
        """
        return self._repo.create_backup(label=label, directory=directory)

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
            Optional — restrict deletion to sensors in this growth unit.
        dry_run:
            If ``True``, report the count without actually deleting.
        vacuum:
            If ``True`` *and* not a dry run, run ``VACUUM`` after the delete.

        Returns
        -------
        dict with ``deleted``, ``dry_run``, ``vacuum``, ``unit_id``,
        ``retention_days``, ``cutoff``.
        """
        return self._repo.prune_sensor_readings(
            retention_days=retention_days,
            unit_id=unit_id,
            dry_run=dry_run,
            vacuum=vacuum,
        )

    # ------------------------------------------------------------------
    # Vacuum
    # ------------------------------------------------------------------

    def vacuum(self) -> dict[str, Any]:
        """Run ``VACUUM`` to reclaim disk space."""
        return self._repo.vacuum()

    # ------------------------------------------------------------------
    # Table statistics
    # ------------------------------------------------------------------

    def get_table_row_counts(self, tables: tuple[str, ...] | None = None) -> dict[str, int]:
        """Return ``{table_name: row_count}`` for a fixed set of key tables.

        Parameters
        ----------
        tables:
            Explicit list of table names.  Defaults to the built-in set in
            :class:`~infrastructure.database.ops.maintenance.MaintenanceOperations`.
        """
        return self._repo.get_table_row_counts(tables)

    # ------------------------------------------------------------------
    # DB size info
    # ------------------------------------------------------------------

    def get_database_size_info(self) -> dict[str, Any]:
        """Return size information about the SQLite database files."""
        return self._repo.get_database_size_info()
