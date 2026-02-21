"""Migration 061: Add SensorAnomaly table for anomaly persistence.

Creates the SensorAnomaly table to persist detected sensor anomalies
so they survive process restarts and can be queried by the frontend.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def migrate(db) -> None:
    """Create SensorAnomaly table if it does not exist."""
    db.execute(
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
    db.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_sensor_anomaly_sensor_detected
        ON SensorAnomaly(sensor_id, detected_at DESC)
        """
    )
    db.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_sensor_anomaly_severity
        ON SensorAnomaly(severity DESC, detected_at DESC)
        """
    )
    db.commit()
    logger.info("Migration 061: SensorAnomaly table created")
