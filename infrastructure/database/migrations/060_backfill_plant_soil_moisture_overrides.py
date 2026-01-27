"""
Migration 060: Backfill soil_moisture_threshold_override for existing plants.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.utils.plant_json_handler import PlantJsonHandler

if TYPE_CHECKING:
    from infrastructure.database.sqlite_handler import SQLiteDatabaseHandler

logger = logging.getLogger(__name__)

MIGRATION_ID = 60
MIGRATION_NAME = "backfill_plant_soil_moisture_overrides"


def _resolve_trigger(handler: PlantJsonHandler, *, plant_type: str | None, plant_name: str | None) -> float | None:
    for name in (plant_type, plant_name):
        if not name:
            continue
        try:
            value = handler.get_soil_moisture_trigger(name)
        except Exception as exc:
            logger.debug("Failed to resolve soil moisture trigger for %s: %s", name, exc, exc_info=True)
            continue
        if value is None:
            continue
        try:
            value = float(value)
        except (TypeError, ValueError):
            logger.debug("Invalid soil moisture trigger for %s: %r", name, value)
            continue
        if 0 <= value <= 100:
            return value
    return None


def migrate(db_handler: "SQLiteDatabaseHandler") -> bool:
    """Backfill soil_moisture_threshold_override for existing plants if missing."""
    try:
        db = db_handler.get_db()
        cursor = db.cursor()

        handler = PlantJsonHandler()
        cursor.execute(
            """
            SELECT plant_id, plant_type, name
            FROM Plants
            WHERE soil_moisture_threshold_override IS NULL
            """
        )
        rows = cursor.fetchall()
        if not rows:
            logger.info("No plants require soil moisture override backfill.")
            return True

        updated = 0
        for row in rows:
            plant_id = row["plant_id"] if isinstance(row, dict) else row[0]
            plant_type = row["plant_type"] if isinstance(row, dict) else row[1]
            plant_name = row["name"] if isinstance(row, dict) else row[2]

            value = _resolve_trigger(handler, plant_type=plant_type, plant_name=plant_name)
            if value is None:
                continue

            cursor.execute(
                """
                UPDATE Plants
                SET soil_moisture_threshold_override = ?
                WHERE plant_id = ?
                """,
                (value, plant_id),
            )
            updated += 1

        db.commit()
        logger.info("✓ Migration %s completed successfully (%d plants updated)", MIGRATION_NAME, updated)
        return True
    except Exception as exc:
        logger.error("Migration %s failed: %s", MIGRATION_NAME, exc, exc_info=True)
        return False


def rollback(db_handler: "SQLiteDatabaseHandler") -> bool:
    """Rollback migration (no-op)."""
    logger.warning("Rollback for %s not implemented (best-effort)", MIGRATION_NAME)
    return True
