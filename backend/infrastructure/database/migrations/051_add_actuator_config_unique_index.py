#!/usr/bin/env python3
"""
Migration 051: Add unique index on ActuatorConfig.actuator_id

This ensures the ON CONFLICT clause works correctly for pump calibration data upserts.

Usage:
    python infrastructure/database/migrations/051_add_actuator_config_unique_index.py database/sysgrow.db
"""

import sqlite3
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from infrastructure.database.sqlite_handler import SQLiteDatabaseHandler


def migrate(db_handler: "SQLiteDatabaseHandler") -> bool:
    """
    Add unique index on ActuatorConfig.actuator_id for upsert support.

    Args:
        db_handler: SQLiteDatabaseHandler instance

    Returns:
        True if successful
    """
    print("Running migration 051")

    conn = db_handler.get_db()
    cursor = conn.cursor()

    try:
        # Check if index already exists
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='index' AND name='idx_actuator_config_actuator_id_unique'
        """)
        if cursor.fetchone():
            print("Index idx_actuator_config_actuator_id_unique already exists, skipping")
            return True

        # Check if the table exists
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='ActuatorConfig'
        """)
        if not cursor.fetchone():
            print("ActuatorConfig table does not exist, creating it")
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ActuatorConfig (
                    config_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    actuator_id INTEGER NOT NULL UNIQUE,
                    config_data TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (actuator_id) REFERENCES Actuator(actuator_id) ON DELETE CASCADE
                )
            """)
            conn.commit()
            print("Created ActuatorConfig table with UNIQUE constraint")
            return True

        # Create unique index on existing table
        cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_actuator_config_actuator_id_unique
            ON ActuatorConfig(actuator_id)
        """)

        conn.commit()
        print("✓ Created unique index idx_actuator_config_actuator_id_unique")
        return True

    except sqlite3.Error as e:
        print(f"Error during migration: {e}")
        conn.rollback()
        return False


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python 051_add_actuator_config_unique_index.py <database_path>")
        sys.exit(1)

    db_path = sys.argv[1]
    if not Path(db_path).exists():
        print(f"Database not found: {db_path}")
        sys.exit(1)

    success = migrate(db_path)
    sys.exit(0 if success else 1)
