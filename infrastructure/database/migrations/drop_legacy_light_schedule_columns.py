#!/usr/bin/env python3
"""
Drop legacy light_start_time/light_end_time columns from GrowthUnits.

This migration:
- Backs up the database.
- No-ops if the legacy columns are already absent.
- Rebuilds GrowthUnits without the legacy light columns, carrying forward device_schedules
  (and seeding a light schedule from the legacy columns when needed).
"""

import argparse
import json
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional


NEW_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS GrowthUnits_new (
    unit_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL DEFAULT 1,
    name TEXT NOT NULL,
    location TEXT DEFAULT "Indoor",
    dimensions TEXT,
    custom_image TEXT,
    active_plant_id INTEGER,
    temperature_threshold REAL DEFAULT 24.0,
    humidity_threshold REAL DEFAULT 50.0,
    soil_moisture_threshold REAL DEFAULT 40.0,
    co2_threshold REAL DEFAULT 800.0,
    voc_threshold REAL DEFAULT 0.0,
    lux_threshold INTEGER DEFAULT 500,
    aqi_threshold INTEGER DEFAULT 50,
    device_schedules TEXT,
    camera_enabled BOOLEAN DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP,
    FOREIGN KEY (active_plant_id) REFERENCES Plants(plant_id),
    FOREIGN KEY (user_id) REFERENCES Users(id) ON DELETE CASCADE
);
"""


def backup_database(db_path: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = db_path.with_name(f"{db_path.name}.backup_{timestamp}")
    shutil.copy2(db_path, backup_path)
    return backup_path


def has_legacy_columns(conn: sqlite3.Connection) -> bool:
    cols = {row[1] for row in conn.execute("PRAGMA table_info(GrowthUnits)")}
    return "light_start_time" in cols or "light_end_time" in cols


def normalize_device_schedules(row: Dict[str, Any]) -> Optional[str]:
    schedules = row.get("device_schedules")
    if isinstance(schedules, (dict, list)):
        return json.dumps(schedules)
    if schedules:
        return schedules

    # Fall back to legacy columns if present
    start = row.get("light_start_time")
    end = row.get("light_end_time")
    if start and end:
        return json.dumps({"light": {"start_time": start, "end_time": end, "enabled": True}})
    return None


def migrate(db_path: Path) -> bool:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    if not has_legacy_columns(conn):
        print("No legacy light_start_time/light_end_time columns found; nothing to do.")
        return True

    backup_path = backup_database(db_path)
    print(f"Backup created at {backup_path}")

    try:
        with conn:
            conn.execute("PRAGMA foreign_keys = OFF;")
            conn.execute("DROP TABLE IF EXISTS GrowthUnits_new;")
            conn.execute(NEW_TABLE_SQL)

            rows = conn.execute("SELECT * FROM GrowthUnits").fetchall()
            insert_sql = """
                INSERT INTO GrowthUnits_new (
                    unit_id,
                    user_id,
                    name,
                    location,
                    dimensions,
                    custom_image,
                    active_plant_id,
                    temperature_threshold,
                    humidity_threshold,
                    soil_moisture_threshold,
                    co2_threshold,
                    voc_threshold,
                    lux_threshold,
                    aqi_threshold,
                    device_schedules,
                    camera_enabled,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """

            for row in rows:
                as_dict = dict(row)
                device_schedules = normalize_device_schedules(as_dict)
                camera_enabled = as_dict.get("camera_enabled")
                if camera_enabled is None:
                    camera_enabled = as_dict.get("camera_active", 0)

                conn.execute(
                    insert_sql,
                    (
                        as_dict.get("unit_id"),
                        as_dict.get("user_id", 1),
                        as_dict.get("name"),
                        as_dict.get("location"),
                        as_dict.get("dimensions"),
                        as_dict.get("custom_image"),
                        as_dict.get("active_plant_id"),
                        as_dict.get("temperature_threshold", 24.0),
                        as_dict.get("humidity_threshold", 50.0),
                        as_dict.get("soil_moisture_threshold", 40.0),
                        as_dict.get("co2_threshold", 800.0),
                        as_dict.get("voc_threshold", 0.0),
                        as_dict.get("lux_threshold", 500),
                        as_dict.get("aqi_threshold", 50),
                        device_schedules,
                        camera_enabled,
                        as_dict.get("created_at"),
                        as_dict.get("updated_at"),
                    ),
                )

            conn.execute("DROP TABLE GrowthUnits;")
            conn.execute('ALTER TABLE GrowthUnits_new RENAME TO GrowthUnits;')
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_growth_units_user_id ON GrowthUnits(user_id);"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_growth_units_created_at ON GrowthUnits(created_at DESC);"
            )
            conn.execute("PRAGMA foreign_keys = ON;")

        print("Migration complete: light_start_time/light_end_time dropped.")
        return True
    except sqlite3.Error as exc:
        print(f"Migration failed: {exc}")
        print(f"You can restore the backup at: {backup_path}")
        return False
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Drop legacy light schedule columns from GrowthUnits"
    )
    parser.add_argument(
        "database",
        nargs="?",
        default="database/sysgrow.db",
        help="Path to the SQLite database (default: database/sysgrow.db)",
    )
    args = parser.parse_args()
    db_path = Path(args.database)

    if not db_path.exists():
        raise SystemExit(f"Database not found: {db_path}")

    success = migrate(db_path)
    raise SystemExit(0 if success else 1)


if __name__ == "__main__":
    main()
