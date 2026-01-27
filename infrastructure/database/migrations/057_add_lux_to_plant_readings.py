"""
Migration 057: Add lux column to PlantReadings.
Ensures light intensity is captured in aggregated plant environmental snapshots.
"""
from __future__ import annotations

import logging
import sqlite3
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from infrastructure.database.sqlite_handler import SQLiteDatabaseHandler

logger = logging.getLogger(__name__)

MIGRATION_ID = 57
MIGRATION_NAME = "add_lux_to_plant_readings"


def migrate(db_handler: "SQLiteDatabaseHandler") -> bool:
    """Add lux column to PlantReadings table if missing."""
    try:
        db = db_handler.get_db()
        cursor = db.cursor()

        # Check existing columns
        cursor.execute("PRAGMA table_info(PlantReadings)")
        columns = {row[1] for row in cursor.fetchall()}

        if "lux" not in columns:
            logger.info("Adding 'lux' column to PlantReadings table")
            cursor.execute("ALTER TABLE PlantReadings ADD COLUMN lux REAL")
        
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
