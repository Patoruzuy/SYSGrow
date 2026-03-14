"""
Migration 048: Add optimized indexes for sensor reading queries

This migration adds composite indexes to improve query performance for:
- Sensor readings filtered by sensor_id and timestamp
- Recent readings queries (most common pattern)
- Time-range queries for analytics

These indexes are critical for Raspberry Pi performance with large datasets.

Author: SYSGrow Team
Date: January 2026
"""
import logging
import sqlite3

logger = logging.getLogger(__name__)

MIGRATION_ID = 48
MIGRATION_NAME = "optimize_sensor_indexes"


def upgrade(conn: sqlite3.Connection) -> bool:
    """
    Add composite indexes for better sensor reading query performance.

    Indexes created:
    1. idx_sensor_reading_sensor_time - For queries by sensor_id + timestamp DESC
    2. idx_sensor_reading_time_desc - For recent readings across all sensors

    Returns:
        True if successful, False otherwise
    """
    try:
        cursor = conn.cursor()

        # Index for queries like: SELECT * FROM SensorReading
        # WHERE sensor_id = X ORDER BY timestamp DESC LIMIT Y
        logger.info("Creating index idx_sensor_reading_sensor_time...")
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_sensor_reading_sensor_time
            ON SensorReading(sensor_id, timestamp DESC)
        """)

        # Index for queries like: SELECT * FROM SensorReading
        # ORDER BY timestamp DESC LIMIT Y
        logger.info("Creating index idx_sensor_reading_time_desc...")
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_sensor_reading_time_desc
            ON SensorReading(timestamp DESC)
        """)

        # Index for ActuatorStateHistory queries
        logger.info("Creating index idx_actuator_state_time...")
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_actuator_state_time
            ON ActuatorStateHistory(actuator_id, timestamp DESC)
        """)

        # Index for Alert by unit and timestamp
        logger.info("Creating index idx_alert_unit_time...")
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_alert_unit_time
            ON Alert(unit_id, timestamp DESC)
        """)

        conn.commit()
        logger.info("Migration 048 completed successfully - sensor indexes optimized")
        return True

    except sqlite3.Error as e:
        logger.error(f"Migration 048 failed: {e}")
        conn.rollback()
        return False


def downgrade(conn: sqlite3.Connection) -> bool:
    """
    Remove the composite indexes.

    Returns:
        True if successful, False otherwise
    """
    try:
        cursor = conn.cursor()

        cursor.execute("DROP INDEX IF EXISTS idx_sensor_reading_sensor_time")
        cursor.execute("DROP INDEX IF EXISTS idx_sensor_reading_time_desc")
        cursor.execute("DROP INDEX IF EXISTS idx_actuator_state_time")
        cursor.execute("DROP INDEX IF EXISTS idx_alert_unit_time")

        conn.commit()
        logger.info("Migration 048 downgrade completed - indexes removed")
        return True

    except sqlite3.Error as e:
        logger.error(f"Migration 048 downgrade failed: {e}")
        conn.rollback()
        return False


def check_applied(conn: sqlite3.Connection) -> bool:
    """
    Check if this migration has already been applied.

    Returns:
        True if the indexes exist, False otherwise
    """
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='index' AND name='idx_sensor_reading_sensor_time'
        """)
        return cursor.fetchone() is not None
    except sqlite3.Error:
        return False


# For direct execution
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python 048_optimize_sensor_indexes.py <database_path>")
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
