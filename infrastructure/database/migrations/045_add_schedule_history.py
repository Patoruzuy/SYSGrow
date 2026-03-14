"""
Migration 045: Add ScheduleHistory table for audit logging.

Tracks all schedule changes for audit purposes:
- Created, updated, deleted actions
- Before/after state snapshots
- User/system source tracking
- Execution results logging

Author: Sebastian Gomez
Date: January 2026
"""
import logging
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

MIGRATION_VERSION = 45
MIGRATION_NAME = "add_schedule_history"


def upgrade(db_path: str) -> bool:
    """
    Add ScheduleHistory table for schedule audit logging.
    
    Args:
        db_path: Path to SQLite database
        
    Returns:
        True if migration succeeded
    """
    logger.info(f"Running migration {MIGRATION_VERSION}: {MIGRATION_NAME}")
    
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Check if table already exists
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='ScheduleHistory'"
        )
        if cursor.fetchone():
            logger.info("ScheduleHistory table already exists, skipping creation")
            conn.close()
            return True
        
        # Create ScheduleHistory table
        cursor.execute("""
            CREATE TABLE ScheduleHistory (
                history_id INTEGER PRIMARY KEY AUTOINCREMENT,
                schedule_id INTEGER NOT NULL,
                unit_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                device_type TEXT,
                before_state TEXT,
                after_state TEXT,
                changed_fields TEXT,
                source TEXT DEFAULT 'user',
                user_id INTEGER,
                reason TEXT,
                created_at TEXT NOT NULL,
                
                FOREIGN KEY (unit_id) REFERENCES GrowthUnits(unit_id)
            )
        """)
        
        # Create indexes for efficient querying
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_schedule_history_schedule_id 
            ON ScheduleHistory(schedule_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_schedule_history_unit_id 
            ON ScheduleHistory(unit_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_schedule_history_created_at 
            ON ScheduleHistory(created_at DESC)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_schedule_history_action 
            ON ScheduleHistory(action)
        """)
        
        # Create ScheduleExecutionLog for tracking schedule execution results
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ScheduleExecutionLog (
                execution_id INTEGER PRIMARY KEY AUTOINCREMENT,
                schedule_id INTEGER NOT NULL,
                actuator_id INTEGER,
                execution_time TEXT NOT NULL,
                action TEXT NOT NULL,
                success INTEGER NOT NULL DEFAULT 1,
                error_message TEXT,
                retry_count INTEGER DEFAULT 0,
                response_time_ms INTEGER,
                
                FOREIGN KEY (schedule_id) REFERENCES DeviceSchedules(schedule_id)
            )
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_schedule_execution_schedule_id 
            ON ScheduleExecutionLog(schedule_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_schedule_execution_time 
            ON ScheduleExecutionLog(execution_time DESC)
        """)
        
        conn.commit()
        logger.info(f"✓ Migration {MIGRATION_VERSION} completed: Created ScheduleHistory and ScheduleExecutionLog tables")
        
        conn.close()
        return True
        
    except sqlite3.Error as e:
        logger.error(f"Migration {MIGRATION_VERSION} failed: {e}")
        return False


def downgrade(db_path: str) -> bool:
    """
    Remove ScheduleHistory and ScheduleExecutionLog tables.
    
    Args:
        db_path: Path to SQLite database
        
    Returns:
        True if downgrade succeeded
    """
    logger.info(f"Rolling back migration {MIGRATION_VERSION}: {MIGRATION_NAME}")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute("DROP TABLE IF EXISTS ScheduleExecutionLog")
        cursor.execute("DROP TABLE IF EXISTS ScheduleHistory")
        
        conn.commit()
        logger.info(f"✓ Rolled back migration {MIGRATION_VERSION}")
        
        conn.close()
        return True
        
    except sqlite3.Error as e:
        logger.error(f"Rollback of migration {MIGRATION_VERSION} failed: {e}")
        return False


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print(f"Usage: python {Path(__file__).name} <db_path> [--downgrade]")
        sys.exit(1)
    
    db_path = sys.argv[1]
    
    if "--downgrade" in sys.argv:
        success = downgrade(db_path)
    else:
        success = upgrade(db_path)
    
    sys.exit(0 if success else 1)
