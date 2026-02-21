"""Migration 061: Add SensorAnomaly table for anomaly persistence.

Creates the SensorAnomaly table to persist detected sensor anomalies
so they survive process restarts and can be queried by the frontend.
"""

from __future__ import annotations

import logging
import sqlite3
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from infrastructure.database.sqlite_handler import SQLiteDatabaseHandler

logger = logging.getLogger(__name__)


def migrate(db_handler: "SQLiteDatabaseHandler") -> bool:
    """Create SensorAnomaly table if it does not exist."""
    try:
        db = db_handler.get_db()
        cursor = db.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS SensorAnomaly (
                anomaly_id   INTEGER PRIMARY KEY AUTOINCREMENT,
                sensor_id    INTEGER NOT NULL,
                anomaly_type VARCHAR(50) NOT NULL,
                severity     REAL    NOT NULL DEFAULT 0.0,
                value        REAL,
                expected_min REAL,
                expected_max REAL,
                description  TEXT,
                detected_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                resolved_at  TIMESTAMP,
                FOREIGN KEY (sensor_id) REFERENCES Sensor(sensor_id) ON DELETE CASCADE
            )
            """
        )
        # Index for common query patterns
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_sensor_anomaly_sensor_detected
            ON SensorAnomaly(sensor_id, detected_at DESC)
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_sensor_anomaly_severity
            ON SensorAnomaly(severity DESC, detected_at DESC)
            """
        )
        db.commit()
        logger.info("Migration 061: SensorAnomaly table created")
        return True
    except sqlite3.Error as exc:
        logger.error("Migration 061 failed: %s", exc)
        return False
