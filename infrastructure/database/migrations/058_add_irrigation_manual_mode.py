"""
Migration 058: Add manual_mode_enabled to IrrigationWorkflowConfig.

This migration exists to cover databases that already recorded migration 054
before manual_mode_enabled was introduced. Safe to run multiple times.
"""
import logging
import sqlite3
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from infrastructure.database.sqlite_handler import SQLiteDatabaseHandler

logger = logging.getLogger(__name__)

MIGRATION_ID = 58
MIGRATION_NAME = "irrigation_manual_mode_flag_backfill"


def _existing_columns(cursor: sqlite3.Cursor, table_name: str) -> set[str]:
    cursor.execute(f"PRAGMA table_info({table_name})")
    return {row[1] for row in cursor.fetchall()}


def migrate(db_handler: "SQLiteDatabaseHandler") -> bool:
    """Add manual_mode_enabled column to IrrigationWorkflowConfig if missing."""
    try:
        db = db_handler.get_db()
        cursor = db.cursor()
        existing = _existing_columns(cursor, "IrrigationWorkflowConfig")
        if "manual_mode_enabled" not in existing:
            cursor.execute(
                """
                ALTER TABLE IrrigationWorkflowConfig
                ADD COLUMN manual_mode_enabled INTEGER NOT NULL DEFAULT 0
                """
            )
            logger.info("Added manual_mode_enabled to IrrigationWorkflowConfig")
        db.commit()
        return True
    except sqlite3.Error as exc:
        logger.error("Failed migration 058 (manual_mode_enabled): %s", exc)
        return False
