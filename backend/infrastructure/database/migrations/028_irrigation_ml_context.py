"""
Migration 028: Add ML context columns to irrigation workflow tables.

Adds environmental context and ML activation status columns to support
the irrigation ML learning system.

Author: SYSGrow Team
Date: January 2026
"""
import logging
import sqlite3
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from infrastructure.database.sqlite_handler import SQLiteDatabaseHandler

logger = logging.getLogger(__name__)

MIGRATION_ID = 28
MIGRATION_NAME = "irrigation_ml_context"


def migrate(db_handler: "SQLiteDatabaseHandler") -> bool:
    """
    Add ML context columns to PendingIrrigationRequest and IrrigationWorkflowConfig.
    
    New columns for PendingIrrigationRequest:
    - temperature_at_detection: Temperature when irrigation need detected
    - humidity_at_detection: Humidity when detected
    - vpd_at_detection: VPD when detected
    - lux_at_detection: Light level when detected
    - hours_since_last_irrigation: Hours since last completed irrigation
    - plant_type: Plant type for context
    - growth_stage: Growth stage for context
    
    New columns for IrrigationWorkflowConfig:
    - ml_response_predictor_enabled: Whether user response predictor is active
    - ml_threshold_optimizer_enabled: Whether threshold optimizer is active
    - ml_duration_optimizer_enabled: Whether duration optimizer is active
    - ml_timing_predictor_enabled: Whether timing predictor is active
    - ml_response_predictor_notified_at: When user was notified about this model
    - ml_threshold_optimizer_notified_at: When user was notified
    - ml_duration_optimizer_notified_at: When user was notified
    - ml_timing_predictor_notified_at: When user was notified
    """
    try:
        db = db_handler.get_db()
        cursor = db.cursor()
        
        # ========== PendingIrrigationRequest columns ==========
        
        # Check existing columns
        cursor.execute("PRAGMA table_info(PendingIrrigationRequest)")
        existing_columns = {row[1] for row in cursor.fetchall()}
        
        new_request_columns = [
            ("temperature_at_detection", "REAL"),
            ("humidity_at_detection", "REAL"),
            ("vpd_at_detection", "REAL"),
            ("lux_at_detection", "REAL"),
            ("hours_since_last_irrigation", "REAL"),
            ("plant_type", "TEXT"),
            ("growth_stage", "TEXT"),
        ]
        
        for col_name, col_type in new_request_columns:
            if col_name not in existing_columns:
                cursor.execute(
                    f"ALTER TABLE PendingIrrigationRequest ADD COLUMN {col_name} {col_type}"
                )
                logger.info(f"Added column {col_name} to PendingIrrigationRequest")
        
        # ========== IrrigationWorkflowConfig columns ==========
        
        cursor.execute("PRAGMA table_info(IrrigationWorkflowConfig)")
        existing_config_columns = {row[1] for row in cursor.fetchall()}
        
        new_config_columns = [
            ("ml_response_predictor_enabled", "INTEGER DEFAULT 0"),
            ("ml_threshold_optimizer_enabled", "INTEGER DEFAULT 0"),
            ("ml_duration_optimizer_enabled", "INTEGER DEFAULT 0"),
            ("ml_timing_predictor_enabled", "INTEGER DEFAULT 0"),
            ("ml_response_predictor_notified_at", "TEXT"),
            ("ml_threshold_optimizer_notified_at", "TEXT"),
            ("ml_duration_optimizer_notified_at", "TEXT"),
            ("ml_timing_predictor_notified_at", "TEXT"),
        ]
        
        for col_name, col_type in new_config_columns:
            if col_name not in existing_config_columns:
                cursor.execute(
                    f"ALTER TABLE IrrigationWorkflowConfig ADD COLUMN {col_name} {col_type}"
                )
                logger.info(f"Added column {col_name} to IrrigationWorkflowConfig")
        
        db.commit()
        logger.info(f"Migration {MIGRATION_ID} ({MIGRATION_NAME}) completed successfully")
        return True
        
    except sqlite3.Error as e:
        logger.error(f"Migration {MIGRATION_ID} failed: {e}")
        return False


def rollback(db_handler: "SQLiteDatabaseHandler") -> bool:
    """
    Rollback is not supported for column additions in SQLite.
    
    SQLite doesn't support DROP COLUMN directly (before version 3.35).
    To truly rollback, you'd need to recreate the table without the columns.
    For safety, we just log a warning.
    """
    logger.warning(
        f"Rollback for migration {MIGRATION_ID} not implemented. "
        "Column additions cannot be easily reversed in SQLite."
    )
    return False
