"""
Migration 030: Add light_mode column to GrowthUnits.

Adds a column to control how day/night is determined for a growth unit:
- 'schedule': Use the configured light schedule times (default)
- 'natural': Use light sensor for day/night detection (or sun API in future)
- 'always_day': Treat as always daytime (24h lighting)
- 'always_night': Treat as always nighttime (no lighting)

Author: SYSGrow Team
Date: January 2026
"""
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from infrastructure.database.sqlite_handler import SQLiteDatabaseHandler

logger = logging.getLogger(__name__)

MIGRATION_ID = 30
MIGRATION_NAME = "add_light_mode_column"


def migrate(db_handler: "SQLiteDatabaseHandler") -> bool:
    """
    Add light_mode column to GrowthUnits table.
    
    This column determines how day/night periods are calculated:
    - 'schedule': Use device_schedules light times (default, backward compatible)
    - 'natural': Use light sensor readings or sun API for natural light detection
    - 'always_day': Always treat as daytime (24h operation)
    - 'always_night': Always treat as nighttime
    """
    try:
        db = db_handler.get_db()
        cursor = db.cursor()
        
        # Check if column already exists
        cursor.execute("PRAGMA table_info(GrowthUnits)")
        existing_columns = {row[1] for row in cursor.fetchall()}
        
        if "light_mode" not in existing_columns:
            logger.info("Adding light_mode column to GrowthUnits...")
            cursor.execute(
                "ALTER TABLE GrowthUnits ADD COLUMN light_mode TEXT DEFAULT 'schedule'"
            )
            db.commit()
            logger.info("✓ Added light_mode column to GrowthUnits")
        else:
            logger.info("light_mode column already exists in GrowthUnits")
        
        return True
        
    except Exception as e:
        logger.error("Migration %s failed: %s", MIGRATION_NAME, e)
        return False


def rollback(db_handler: "SQLiteDatabaseHandler") -> bool:
    """
    Remove light_mode column from GrowthUnits.
    
    Note: SQLite doesn't support DROP COLUMN directly in older versions.
    This is a best-effort rollback.
    """
    logger.warning("Rollback for %s not implemented (SQLite limitation)", MIGRATION_NAME)
    return True
