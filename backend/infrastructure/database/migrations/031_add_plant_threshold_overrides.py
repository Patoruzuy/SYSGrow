"""
Migration 031: Add per-plant threshold override columns.

Adds optional override columns to the Plants table so that each plant can
store unit-specific threshold overrides that are applied when the plant
becomes active.
"""
import logging
import sqlite3
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from infrastructure.database.sqlite_handler import SQLiteDatabaseHandler

logger = logging.getLogger(__name__)

MIGRATION_ID = 31
MIGRATION_NAME = "add_plant_threshold_overrides"


def migrate(db_handler: "SQLiteDatabaseHandler") -> bool:
    """Add per-plant threshold override columns to Plants."""
    try:
        db = db_handler.get_db()
        cursor = db.cursor()

        cursor.execute("PRAGMA table_info(Plants)")
        existing_columns = {row[1] for row in cursor.fetchall()}

        new_columns = [
            ("temperature_threshold_override", "REAL"),
            ("humidity_threshold_override", "REAL"),
            ("soil_moisture_threshold_override", "REAL"),
            ("co2_threshold_override", "REAL"),
            ("voc_threshold_override", "REAL"),
            ("lux_threshold_override", "REAL"),
            ("aqi_threshold_override", "REAL"),
        ]

        for col_name, col_type in new_columns:
            if col_name in existing_columns:
                continue
            cursor.execute(f"ALTER TABLE Plants ADD COLUMN {col_name} {col_type}")
            logger.info("Added column %s to Plants", col_name)

        db.commit()
        logger.info("✓ Migration %s completed successfully", MIGRATION_NAME)
        return True

    except sqlite3.Error as exc:
        logger.error("Migration %s failed: %s", MIGRATION_NAME, exc)
        return False


def rollback(db_handler: "SQLiteDatabaseHandler") -> bool:
    """Rollback migration (SQLite does not support DROP COLUMN)."""
    logger.warning("Rollback for %s not implemented (SQLite limitation)", MIGRATION_NAME)
    return True
