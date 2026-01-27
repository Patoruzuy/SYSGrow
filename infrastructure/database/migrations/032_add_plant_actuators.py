"""
Migration 032: Add plant-actuator mapping table.

Creates PlantActuators table for per-plant actuator assignments
(e.g., dedicated irrigation pumps).
"""
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from infrastructure.database.sqlite_handler import SQLiteDatabaseHandler

logger = logging.getLogger(__name__)

MIGRATION_ID = 32
MIGRATION_NAME = "add_plant_actuators"


def migrate(db_handler: "SQLiteDatabaseHandler") -> bool:
    """Create PlantActuators table if missing."""
    try:
        db = db_handler.get_db()
        cursor = db.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS PlantActuators (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                plant_id INTEGER NOT NULL,
                actuator_id INTEGER NOT NULL,
                UNIQUE(actuator_id),
                UNIQUE(plant_id, actuator_id),
                FOREIGN KEY (plant_id) REFERENCES Plants(plant_id),
                FOREIGN KEY (actuator_id) REFERENCES Actuator(actuator_id)
            )
            """
        )
        db.commit()
        logger.info("✓ Migration %s completed successfully", MIGRATION_NAME)
        return True
    except Exception as exc:
        logger.error("Migration %s failed: %s", MIGRATION_NAME, exc)
        return False


def rollback(db_handler: "SQLiteDatabaseHandler") -> bool:
    """Rollback migration (SQLite does not support DROP TABLE easily in place)."""
    logger.warning("Rollback for %s not implemented (SQLite limitation)", MIGRATION_NAME)
    return True
