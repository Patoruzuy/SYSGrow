"""
Migration 034: Standardize sensor column names.

Renames:
- GrowthUnits: aqi_threshold -> air_quality_threshold
- Plants: aqi_threshold_override -> air_quality_threshold_override
- PlantReadings: co2_ppm -> co2, voc_ppb -> voc, aqi -> air_quality
- MLTrainingData: co2_ppm -> co2, voc_ppb -> voc, aqi -> air_quality
- PlantHarvestSummary: avg_co2_ppm -> avg_co2

Falls back to add+copy if SQLite cannot rename columns.
"""
from __future__ import annotations

import logging
import sqlite3
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from infrastructure.database.sqlite_handler import SQLiteDatabaseHandler

logger = logging.getLogger(__name__)

MIGRATION_ID = 34
MIGRATION_NAME = "standardize_sensor_columns"


def _rename_or_copy(
    cursor: sqlite3.Cursor,
    table: str,
    *,
    old_name: str,
    new_name: str,
    column_type: str,
    default_clause: str = "",
) -> None:
    # Skip entirely if the table doesn't exist yet (created by a later migration)
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
    if cursor.fetchone() is None:
        logger.info("Table %s does not exist yet, skipping column migration", table)
        return

    cursor.execute(f"PRAGMA table_info({table})")
    columns = {row[1] for row in cursor.fetchall()}

    if new_name in columns:
        logger.info("Column %s already exists in %s", new_name, table)
        return

    if old_name not in columns:
        logger.info("Old column %s not found in %s, adding %s", old_name, table, new_name)
        cursor.execute(
            f"ALTER TABLE {table} ADD COLUMN {new_name} {column_type} {default_clause}"
        )
        return

    try:
        logger.info("Renaming %s.%s to %s", table, old_name, new_name)
        cursor.execute(f"ALTER TABLE {table} RENAME COLUMN {old_name} TO {new_name}")
    except sqlite3.Error as e:
        logger.warning("Rename failed for %s.%s: %s. Using copy fallback.", table, old_name, e)
        cursor.execute(
            f"ALTER TABLE {table} ADD COLUMN {new_name} {column_type} {default_clause}"
        )
        cursor.execute(
            f"UPDATE {table} SET {new_name} = {old_name} WHERE {new_name} IS NULL"
        )


def migrate(db_handler: "SQLiteDatabaseHandler") -> bool:
    """Standardize sensor column names across all tables."""
    try:
        db = db_handler.get_db()
        cursor = db.cursor()

        # GrowthUnits
        _rename_or_copy(cursor, "GrowthUnits", old_name="aqi_threshold", new_name="air_quality_threshold", column_type="INTEGER", default_clause="DEFAULT 50")

        # Plants
        _rename_or_copy(cursor, "Plants", old_name="aqi_threshold_override", new_name="air_quality_threshold_override", column_type="REAL")

        # PlantReadings
        _rename_or_copy(cursor, "PlantReadings", old_name="co2_ppm", new_name="co2", column_type="REAL")
        _rename_or_copy(cursor, "PlantReadings", old_name="voc_ppb", new_name="voc", column_type="REAL")
        _rename_or_copy(cursor, "PlantReadings", old_name="aqi", new_name="air_quality", column_type="INTEGER")

        # MLTrainingData
        _rename_or_copy(cursor, "MLTrainingData", old_name="co2_ppm", new_name="co2", column_type="REAL")
        _rename_or_copy(cursor, "MLTrainingData", old_name="voc_ppb", new_name="voc", column_type="REAL")
        _rename_or_copy(cursor, "MLTrainingData", old_name="aqi", new_name="air_quality", column_type="INTEGER")

        # PlantHarvestSummary
        _rename_or_copy(cursor, "PlantHarvestSummary", old_name="avg_co2_ppm", new_name="avg_co2", column_type="REAL")

        db.commit()
        logger.info("✓ Migration %s completed successfully", MIGRATION_NAME)
        return True
    except Exception as exc:
        logger.error("Migration %s failed: %s", MIGRATION_NAME, exc, exc_info=True)
        return False


def rollback(db_handler: "SQLiteDatabaseHandler") -> bool:
    """Rollback migration."""
    # SQLite rename rollback is tricky, we'll just log
    logger.warning("Rollback for %s not implemented (best-effort)", MIGRATION_NAME)
    return True
