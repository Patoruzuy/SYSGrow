#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import sqlite3
from pathlib import Path


def _apply_updates(conn: sqlite3.Connection, updates: list[tuple[int, float]]) -> int:
    cursor = conn.cursor()
    applied = 0
    for plant_id, threshold in updates:
        cursor.execute(
            """
            UPDATE Plants
            SET soil_moisture_threshold_override = ?
            WHERE plant_id = ?
            """,
            (threshold, plant_id),
        )
        if cursor.rowcount:
            applied += 1
    conn.commit()
    return applied


def _parse_updates_from_csv(csv_path: Path) -> list[tuple[int, float]]:
    updates: list[tuple[int, float]] = []
    with csv_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            plant_id_raw = row.get("plant_id") or row.get("id")
            threshold_raw = row.get("soil_moisture_threshold_override") or row.get("threshold")
            if plant_id_raw is None or threshold_raw is None:
                continue
            try:
                plant_id = int(plant_id_raw)
                threshold = float(threshold_raw)
            except (TypeError, ValueError):
                continue
            if not (0 <= threshold <= 100):
                continue
            updates.append((plant_id, threshold))
    return updates


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply per-plant soil moisture thresholds.")
    parser.add_argument(
        "--db",
        dest="db_path",
        default=str(Path(__file__).resolve().parents[1] / "sysgrow.db"),
        help="Path to SQLite database (default: ./sysgrow.db)",
    )
    parser.add_argument("--csv", dest="csv_path", help="CSV file with plant_id,threshold columns")
    parser.add_argument("--plant-id", dest="plant_id", type=int, help="Plant ID to update")
    parser.add_argument("--threshold", dest="threshold", type=float, help="Soil moisture threshold (0-100)")
    args = parser.parse_args()

    db_path = Path(args.db_path)
    if not db_path.exists():
        print(f"Database not found: {db_path}")
        return 1

    updates: list[tuple[int, float]] = []
    if args.csv_path:
        updates.extend(_parse_updates_from_csv(Path(args.csv_path)))
    if args.plant_id is not None and args.threshold is not None:
        if 0 <= args.threshold <= 100:
            updates.append((args.plant_id, args.threshold))

    if not updates:
        print("No valid updates provided. Use --csv or --plant-id/--threshold.")
        return 1

    conn = sqlite3.connect(str(db_path))
    applied = _apply_updates(conn, updates)
    conn.close()
    print(f"Applied overrides for {applied} plant(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
