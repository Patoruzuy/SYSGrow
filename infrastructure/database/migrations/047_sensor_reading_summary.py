"""
Migration 047: Create SensorReadingSummary table for aggregated data

This migration creates a table to store daily/hourly aggregated sensor readings.
This data is preserved even after raw readings are pruned, enabling:
- Harvest reports with historical data
- Long-term trend analysis
- Resource-efficient historical queries

The aggregation task runs BEFORE the pruning task to ensure data is summarized
before raw readings are deleted.

Author: SYSGrow Team
Date: January 2026
"""
import logging
import sqlite3

logger = logging.getLogger(__name__)

MIGRATION_ID = 47
MIGRATION_NAME = "sensor_reading_summary"


def upgrade(conn: sqlite3.Connection) -> bool:
    """
    Create SensorReadingSummary table for aggregated sensor data.

    Table stores:
    - Daily summaries (min, max, avg, count, stddev)
    - Linked to sensor_id and unit_id
    - Granularity field for future hourly/weekly options

    Returns:
        True if successful, False otherwise
    """
    try:
        cursor = conn.cursor()

        logger.info("Creating SensorReadingSummary table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS SensorReadingSummary (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sensor_id INTEGER NOT NULL,
                unit_id INTEGER,
                sensor_type TEXT NOT NULL,
                period_start DATETIME NOT NULL,
                period_end DATETIME NOT NULL,
                granularity TEXT NOT NULL DEFAULT 'daily',

                -- Aggregated values
                min_value REAL,
                max_value REAL,
                avg_value REAL,
                sum_value REAL,
                count_readings INTEGER NOT NULL DEFAULT 0,
                stddev_value REAL,

                -- Metadata
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,

                -- Prevent duplicate summaries
                UNIQUE(sensor_id, period_start, granularity)
            )
        """)

        # Indexes for efficient queries
        logger.info("Creating indexes for SensorReadingSummary...")
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_summary_sensor_period
            ON SensorReadingSummary(sensor_id, period_start DESC)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_summary_unit_period
            ON SensorReadingSummary(unit_id, period_start DESC)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_summary_type_period
            ON SensorReadingSummary(sensor_type, period_start DESC)
        """)

        conn.commit()
        logger.info("Migration 047 completed successfully - SensorReadingSummary table created")
        return True

    except sqlite3.Error as e:
        logger.error(f"Migration 047 failed: {e}")
        conn.rollback()
        return False


def downgrade(conn: sqlite3.Connection) -> bool:
    """
    Remove the SensorReadingSummary table.

    Returns:
        True if successful, False otherwise
    """
    try:
        cursor = conn.cursor()

        cursor.execute("DROP INDEX IF EXISTS idx_summary_sensor_period")
        cursor.execute("DROP INDEX IF EXISTS idx_summary_unit_period")
        cursor.execute("DROP INDEX IF EXISTS idx_summary_type_period")
        cursor.execute("DROP TABLE IF EXISTS SensorReadingSummary")

        conn.commit()
        logger.info("Migration 047 downgrade completed - SensorReadingSummary table removed")
        return True

    except sqlite3.Error as e:
        logger.error(f"Migration 047 downgrade failed: {e}")
        conn.rollback()
        return False


def check_applied(conn: sqlite3.Connection) -> bool:
    """
    Check if this migration has already been applied.

    Returns:
        True if the table exists, False otherwise
    """
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='SensorReadingSummary'
        """)
        return cursor.fetchone() is not None
    except sqlite3.Error:
        return False


# For direct execution
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python 047_sensor_reading_summary.py <database_path>")
        sys.exit(1)

    db_path = sys.argv[1]
    conn = sqlite3.connect(db_path)

    if check_applied(conn):
        print("Migration already applied")
    else:
        if upgrade(conn):
            print("Migration successful")
        else:
            print("Migration failed")
            sys.exit(1)

    conn.close()
