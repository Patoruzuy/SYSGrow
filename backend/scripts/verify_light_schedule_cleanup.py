"""
Verify legacy light schedule columns are removed and device_schedules is populated.

Usage:
    python scripts/verify_light_schedule_cleanup.py --db database/sysgrow.db
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any, Dict


def has_column(conn: sqlite3.Connection, table: str, column: str) -> bool:
    cols = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
    return column in cols


def safe_load_device_schedules(raw: Any) -> Any:
    if raw is None:
        return None
    if isinstance(raw, (dict, list)):
        return raw
    try:
        return json.loads(raw)
    except Exception:
        return raw


def summarize(db_path: Path) -> int:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    has_start = has_column(conn, "GrowthUnits", "light_start_time")
    has_end = has_column(conn, "GrowthUnits", "light_end_time")

    print(f"Database: {db_path}")
    print(f"Columns present: light_start_time={has_start}, light_end_time={has_end}")

    select_cols = ["unit_id", "device_schedules"]
    if has_start:
        select_cols.append("light_start_time")
    if has_end:
        select_cols.append("light_end_time")
    select_sql = f"SELECT {', '.join(select_cols)} FROM GrowthUnits LIMIT 50"

    rows = conn.execute(select_sql).fetchall()
    missing_schedules = 0
    legacy_populated = 0

    for row in rows:
        row_dict = dict(row)
        if has_start and row_dict.get("light_start_time"):
            legacy_populated += 1
        if has_end and row_dict.get("light_end_time"):
            legacy_populated += 1
        schedules = safe_load_device_schedules(row_dict.get("device_schedules"))
        if schedules in (None, "", {}):
            missing_schedules += 1

    print(f"Sample size: {len(rows)} rows")
    if has_start or has_end:
        print(f"Rows with legacy light_start/end populated: {legacy_populated}")
    print(f"Rows missing device_schedules (None/empty): {missing_schedules}")

    # Show first few device_schedules for inspection
    print("Sample device_schedules (first 3):")
    for row in rows[:3]:
        row_dict = dict(row)
        schedules = safe_load_device_schedules(row_dict.get("device_schedules"))
        print(f"  unit_id={row_dict['unit_id']}: {schedules}")

    conn.close()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify legacy light schedule cleanup")
    parser.add_argument("--db", default="database/sysgrow.db", help="Path to SQLite DB")
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"Database not found: {db_path}")
        return 1

    return summarize(db_path)


if __name__ == "__main__":
    raise SystemExit(main())
