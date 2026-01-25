"""
Migration 059: Add pH and EC columns to PlantReadings.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from infrastructure.database.sqlite_handler import SQLiteDatabaseHandler

logger = logging.getLogger(__name__)

MIGRATION_ID = 59
MIGRATION_NAME = "add_ph_ec_to_plant_readings"


def migrate(db_handler: "SQLiteDatabaseHandler") -> bool:
    """Add ph/ec columns to PlantReadings table if missing."""
    try:
        db = db_handler.get_db()
        cursor = db.cursor()

        cursor.execute("PRAGMA table_info(PlantReadings)")
        columns = {row[1] for row in cursor.fetchall()}

        if "ph" not in columns:
            logger.info("Adding 'ph' column to PlantReadings table")
            cursor.execute("ALTER TABLE PlantReadings ADD COLUMN ph REAL")

        if "ec" not in columns:
            logger.info("Adding 'ec' column to PlantReadings table")
            cursor.execute("ALTER TABLE PlantReadings ADD COLUMN ec REAL")

        db.commit()
        logger.info("✓ Migration %s completed successfully", MIGRATION_NAME)
        return True
    except Exception as exc:
        logger.error("Migration %s failed: %s", MIGRATION_NAME, exc, exc_info=True)
        return False


def rollback(db_handler: "SQLiteDatabaseHandler") -> bool:
    """Rollback migration (not supported for column addition in many versions of SQLite)."""
    logger.warning("Rollback for %s not supported", MIGRATION_NAME)
    return True
