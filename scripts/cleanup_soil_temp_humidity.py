"""Cleanup temperature/humidity readings from a soil moisture sensor.

By default this script runs in dry-run mode and reports rows that would be deleted.
Use --execute to apply changes.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Iterable, List

DEFAULT_DB_PATH = Path("database/sysgrow.db")


def _load_row_ids(
    conn: sqlite3.Connection,
    *,
    sensor_id: int,
    metrics: Iterable[str],
) -> List[int]:
    conn.row_factory = sqlite3.Row
    cursor = conn.execute(
        "SELECT reading_id, reading_data FROM SensorReading WHERE sensor_id = ?",
        (sensor_id,),
    )

    metric_set = {m.strip().lower() for m in metrics if str(m).strip()}
    reading_ids: List[int] = []

    for row in cursor.fetchall():
        try:
            payload = json.loads(row["reading_data"]) if row["reading_data"] else {}
        except json.JSONDecodeError:
            payload = {}

        keys = {str(k).strip().lower() for k in payload.keys()}
        if keys & metric_set:
            reading_ids.append(int(row["reading_id"]))

    return reading_ids


def _delete_rows(conn: sqlite3.Connection, ids: List[int]) -> int:
    if not ids:
        return 0
    placeholders = ",".join("?" for _ in ids)
    conn.execute(
        f"DELETE FROM SensorReading WHERE reading_id IN ({placeholders})",
        ids,
    )
    conn.commit()
    return len(ids)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Delete temperature/humidity readings logged under a soil moisture sensor.",
    )
    parser.add_argument(
        "--db",
        default=str(DEFAULT_DB_PATH),
        help="Path to SQLite database (default: database/sysgrow.db)",
    )
    parser.add_argument(
        "--sensor-id",
        type=int,
        default=19,
        help="Sensor ID to clean (default: 19)",
    )
    parser.add_argument(
        "--metrics",
        nargs="+",
        default=["temperature", "humidity"],
        help="Metrics to remove (default: temperature humidity)",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Apply deletions (default is dry-run)",
    )

    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"Database not found: {db_path}")
        return 1

    conn = sqlite3.connect(str(db_path))
    try:
        ids = _load_row_ids(conn, sensor_id=args.sensor_id, metrics=args.metrics)
        print(
            f"Found {len(ids)} rows for sensor {args.sensor_id} "
            f"matching metrics {', '.join(args.metrics)}"
        )
        if not args.execute:
            print("Dry-run only. Re-run with --execute to delete.")
            return 0

        deleted = _delete_rows(conn, ids)
        print(f"Deleted {deleted} rows.")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
