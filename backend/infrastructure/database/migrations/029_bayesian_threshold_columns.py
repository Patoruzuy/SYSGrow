"""
Migration 029: Add Bayesian threshold belief columns to IrrigationUserPreference.

Adds columns to store Bayesian learning state for soil moisture threshold
optimization.

Author: SYSGrow Team
Date: January 2026
"""
import logging
import sqlite3
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from infrastructure.database.sqlite_handler import SQLiteDatabaseHandler

logger = logging.getLogger(__name__)

MIGRATION_ID = 29
MIGRATION_NAME = "bayesian_threshold_columns"


def migrate(db_handler: "SQLiteDatabaseHandler") -> bool:
    """
    Add Bayesian threshold belief columns to IrrigationUserPreference.
    
    New columns:
    - threshold_belief_json: Full JSON representation of ThresholdBelief
    - threshold_variance: Posterior variance (uncertainty)
    - threshold_sample_count: Number of feedback samples processed
    
    These columns support the Bayesian threshold optimization system that
    learns optimal soil moisture thresholds from user feedback.
    """
    try:
        db = db_handler.get_db()
        cursor = db.cursor()
        
        # Check existing columns
        cursor.execute("PRAGMA table_info(IrrigationUserPreference)")
        existing_columns = {row[1] for row in cursor.fetchall()}
        
        new_columns = [
            ("threshold_belief_json", "TEXT"),
            ("threshold_variance", "REAL"),
            ("threshold_sample_count", "INTEGER DEFAULT 0"),
        ]
        
        for col_name, col_type in new_columns:
            if col_name not in existing_columns:
                cursor.execute(
                    f"ALTER TABLE IrrigationUserPreference ADD COLUMN {col_name} {col_type}"
                )
                logger.info(f"Added column {col_name} to IrrigationUserPreference")
        
        db.commit()
        logger.info("✅ Migration 029 (bayesian_threshold_columns) completed successfully")
        return True
        
    except sqlite3.Error as e:
        logger.error(f"Migration 029 failed: {e}")
        return False


def rollback(db_handler: "SQLiteDatabaseHandler") -> bool:
    """
    Rollback migration (SQLite doesn't support DROP COLUMN easily).
    
    Note: SQLite doesn't support DROP COLUMN in older versions.
    For a true rollback, you would need to recreate the table.
    """
    logger.warning("Rollback not fully supported for SQLite column additions")
    return True
