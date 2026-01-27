"""
Migration 056: Set primary_metrics for specific sensors.

Configures per-sensor primary metrics used by PriorityProcessor.

Author: SYSGrow Development Team
Date: January 2026
"""
import json
import logging
import sqlite3
from pathlib import Path
from typing import Dict, List

logger = logging.getLogger(__name__)

MIGRATION_VERSION = 56
MIGRATION_NAME = "set_sensor_primary_metrics"

# Customize per-sensor primary metrics here
PRIMARY_METRICS_BY_SENSOR: Dict[int, List[str]] = {
    17: ["temperature", "humidity"],
    19: ["lux", "soil_moisture"],
}


def _load_existing_config(cursor: sqlite3.Cursor, sensor_id: int) -> Dict:
    cursor.execute(
        "SELECT config_data FROM SensorConfig WHERE sensor_id = ?",
        (sensor_id,),
    )
    row = cursor.fetchone()
    if not row:
        return {}
    try:
        return json.loads(row["config_data"]) if row["config_data"] else {}
    except json.JSONDecodeError:
        return {}


def upgrade(db_path: str) -> bool:
    """Apply primary_metrics updates for configured sensors."""
    logger.info("Running migration %s: %s", MIGRATION_VERSION, MIGRATION_NAME)

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='SensorConfig'"
        )
        if not cursor.fetchone():
            logger.error("SensorConfig table not found; aborting migration")
            conn.close()
            return False

        for sensor_id, metrics in PRIMARY_METRICS_BY_SENSOR.items():
            existing = _load_existing_config(cursor, sensor_id)
            existing["primary_metrics"] = list(metrics)
            config_json = json.dumps(existing)

            cursor.execute(
                "UPDATE SensorConfig SET config_data = ? WHERE sensor_id = ?",
                (config_json, sensor_id),
            )
            if cursor.rowcount == 0:
                cursor.execute(
                    "INSERT INTO SensorConfig (sensor_id, config_data) VALUES (?, ?)",
                    (sensor_id, config_json),
                )
            logger.info("Set primary_metrics for sensor %s -> %s", sensor_id, metrics)

        conn.commit()
        conn.close()
        logger.info("✓ Migration %s completed", MIGRATION_VERSION)
        return True

    except sqlite3.Error as e:
        logger.error("Migration %s failed: %s", MIGRATION_VERSION, e)
        return False


def downgrade(db_path: str) -> bool:
    """Remove primary_metrics for configured sensors."""
    logger.warning("Downgrade for migration %s removes primary_metrics entries", MIGRATION_VERSION)

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        for sensor_id in PRIMARY_METRICS_BY_SENSOR.keys():
            existing = _load_existing_config(cursor, sensor_id)
            if "primary_metrics" in existing:
                existing.pop("primary_metrics", None)
                config_json = json.dumps(existing)
                cursor.execute(
                    "UPDATE SensorConfig SET config_data = ? WHERE sensor_id = ?",
                    (config_json, sensor_id),
                )
                logger.info("Removed primary_metrics for sensor %s", sensor_id)

        conn.commit()
        conn.close()
        return True

    except sqlite3.Error as e:
        logger.error("Downgrade %s failed: %s", MIGRATION_VERSION, e)
        return False


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print(f"Usage: python {Path(__file__).name} <db_path>")
        sys.exit(1)

    db_path = sys.argv[1]
    success = upgrade(db_path)
    sys.exit(0 if success else 1)
