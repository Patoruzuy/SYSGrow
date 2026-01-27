"""
Migration 046: Add interval fields to DeviceSchedules.

Adds:
- interval_minutes
- duration_minutes

Author: SYSGrow Development Team
Date: January 2026
"""
import logging
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)

MIGRATION_VERSION = 46
MIGRATION_NAME = "add_schedule_interval_fields"


def _column_exists(cursor: sqlite3.Cursor, column_name: str) -> bool:
    cursor.execute("PRAGMA table_info(DeviceSchedules)")
    return any(row[1] == column_name for row in cursor.fetchall())


def upgrade(db_path: str) -> bool:
    """Add interval columns to DeviceSchedules table."""
    logger.info("Running migration %s: %s", MIGRATION_VERSION, MIGRATION_NAME)

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='DeviceSchedules'"
        )
        if not cursor.fetchone():
            logger.error("DeviceSchedules table not found; aborting migration")
            conn.close()
            return False

        columns = [
            ("interval_minutes", "INTEGER"),
            ("duration_minutes", "INTEGER"),
        ]

        for column_name, column_type in columns:
            if _column_exists(cursor, column_name):
                continue
            cursor.execute(
                f"ALTER TABLE DeviceSchedules ADD COLUMN {column_name} {column_type}"
            )
            logger.info("Added column %s to DeviceSchedules", column_name)

        conn.commit()
        conn.close()
        logger.info("✓ Migration %s completed", MIGRATION_VERSION)
        return True

    except sqlite3.Error as e:
        logger.error("Migration %s failed: %s", MIGRATION_VERSION, e)
        return False


def downgrade(db_path: str) -> bool:
    """SQLite does not support dropping columns; downgrade not supported."""
    logger.warning("Downgrade not supported for migration %s", MIGRATION_VERSION)
    return False


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print(f"Usage: python {Path(__file__).name} <db_path>")
        sys.exit(1)

    db_path = sys.argv[1]
    success = upgrade(db_path)
    sys.exit(0 if success else 1)
