"""
Migration 033: Rename light_intensity_threshold to lux_threshold.

Renames GrowthUnits.light_intensity_threshold -> lux_threshold and
Plants.light_intensity_threshold_override -> lux_threshold_override.
Falls back to add+copy if SQLite cannot rename columns.
"""
from __future__ import annotations

import logging
import sqlite3
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from infrastructure.database.sqlite_handler import SQLiteDatabaseHandler

logger = logging.getLogger(__name__)

MIGRATION_ID = 33
MIGRATION_NAME = "rename_light_intensity_threshold_to_lux_threshold"


def _rename_or_copy(
    cursor: sqlite3.Cursor,
    table: str,
    *,
    old_name: str,
    new_name: str,
    column_type: str,
    default_clause: str,
) -> None:
    cursor.execute(f"PRAGMA table_info({table})")
    columns = {row[1] for row in cursor.fetchall()}

    if new_name in columns:
        return

    if old_name not in columns:
        cursor.execute(
            f"ALTER TABLE {table} ADD COLUMN {new_name} {column_type} {default_clause}"
        )
        return

    try:
        cursor.execute(f"ALTER TABLE {table} RENAME COLUMN {old_name} TO {new_name}")
    except sqlite3.Error:
        cursor.execute(
            f"ALTER TABLE {table} ADD COLUMN {new_name} {column_type} {default_clause}"
        )
        cursor.execute(
            f"UPDATE {table} SET {new_name} = {old_name} WHERE {new_name} IS NULL"
        )


def migrate(db_handler: "SQLiteDatabaseHandler") -> bool:
    """Rename light intensity threshold columns to lux naming."""
    try:
        db = db_handler.get_db()
        cursor = db.cursor()

        _rename_or_copy(
            cursor,
            "GrowthUnits",
            old_name="light_intensity_threshold",
            new_name="lux_threshold",
            column_type="INTEGER",
            default_clause="DEFAULT 500",
        )
        _rename_or_copy(
            cursor,
            "Plants",
            old_name="light_intensity_threshold_override",
            new_name="lux_threshold_override",
            column_type="REAL",
            default_clause="",
        )

        db.commit()
        logger.info("✓ Migration %s completed successfully", MIGRATION_NAME)
        return True
    except Exception as exc:
        logger.error("Migration %s failed: %s", MIGRATION_NAME, exc, exc_info=True)
        return False


def rollback(db_handler: "SQLiteDatabaseHandler") -> bool:
    """Rollback migration (SQLite rename rollback not implemented)."""
    logger.warning("Rollback for %s not implemented (SQLite limitation)", MIGRATION_NAME)
    return True
