"""
Migration 055: Expand irrigation feedback responses.

Adds timing feedback options to IrrigationFeedback by rebuilding the table
with an updated CHECK constraint. Safe to run multiple times.
"""
from __future__ import annotations

import logging
import sqlite3
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from infrastructure.database.sqlite_handler import SQLiteDatabaseHandler

logger = logging.getLogger(__name__)

MIGRATION_ID = 55
MIGRATION_NAME = "update_irrigation_feedback_responses"


def _table_exists(cursor: sqlite3.Cursor, table_name: str) -> bool:
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    )
    return cursor.fetchone() is not None


def _table_sql(cursor: sqlite3.Cursor, table_name: str) -> str:
    cursor.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    )
    row = cursor.fetchone()
    return row[0] if row and row[0] else ""


def _existing_columns(cursor: sqlite3.Cursor, table_name: str) -> set[str]:
    cursor.execute(f"PRAGMA table_info({table_name})")
    return {row[1] for row in cursor.fetchall()}


def migrate(db_handler: "SQLiteDatabaseHandler") -> bool:
    """Expand irrigation feedback responses with timing options."""
    try:
        db = db_handler.get_db()
        cursor = db.cursor()

        if not _table_exists(cursor, "IrrigationFeedback"):
            return True

        existing_sql = _table_sql(cursor, "IrrigationFeedback")
        if "triggered_too_early" in existing_sql and "triggered_too_late" in existing_sql:
            if _table_exists(cursor, "IrrigationFeedback_old"):
                cursor.execute("DROP TABLE IF EXISTS IrrigationFeedback_old")
                db.commit()
            return True

        # Prepare source table with existing data
        if _table_exists(cursor, "IrrigationFeedback_old"):
            source_table = "IrrigationFeedback_old"
            cursor.execute("DROP TABLE IF EXISTS IrrigationFeedback")
        else:
            cursor.execute("ALTER TABLE IrrigationFeedback RENAME TO IrrigationFeedback_old")
            source_table = "IrrigationFeedback_old"

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS IrrigationFeedback (
                feedback_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                unit_id INTEGER NOT NULL,
                plant_id INTEGER,
                soil_moisture_before REAL,
                soil_moisture_after REAL,
                irrigation_duration_seconds INTEGER,
                actuator_id INTEGER,
                feedback_response TEXT CHECK(feedback_response IN (
                    'too_little', 'just_right', 'too_much',
                    'triggered_too_early', 'triggered_too_late',
                    'skipped'
                )),
                feedback_notes TEXT,
                suggested_threshold_adjustment REAL,
                threshold_adjustment_applied BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES Users(id) ON DELETE CASCADE,
                FOREIGN KEY (unit_id) REFERENCES GrowthUnits(unit_id) ON DELETE CASCADE,
                FOREIGN KEY (plant_id) REFERENCES Plants(plant_id) ON DELETE SET NULL,
                FOREIGN KEY (actuator_id) REFERENCES Actuator(actuator_id) ON DELETE SET NULL
            )
            """
        )

        existing_columns = _existing_columns(cursor, source_table)
        target_columns = [
            "feedback_id",
            "user_id",
            "unit_id",
            "plant_id",
            "soil_moisture_before",
            "soil_moisture_after",
            "irrigation_duration_seconds",
            "actuator_id",
            "feedback_response",
            "feedback_notes",
            "suggested_threshold_adjustment",
            "threshold_adjustment_applied",
            "created_at",
        ]
        copy_columns = [col for col in target_columns if col in existing_columns]
        if copy_columns:
            columns_csv = ", ".join(copy_columns)
            cursor.execute(
                f"""
                INSERT INTO IrrigationFeedback ({columns_csv})
                SELECT {columns_csv} FROM {source_table}
                """
            )

        cursor.execute("DROP TABLE IF EXISTS IrrigationFeedback_old")
        db.commit()
        logger.info("Migration %s (%s) completed successfully", MIGRATION_ID, MIGRATION_NAME)
        return True
    except sqlite3.Error as exc:
        logger.error("Migration %s failed: %s", MIGRATION_ID, exc)
        return False


def rollback(db_handler: "SQLiteDatabaseHandler") -> bool:
    """Rollback not supported for this migration."""
    logger.warning(
        "Rollback for migration %s not supported; manual intervention required.",
        MIGRATION_ID,
    )
    return False
