#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path
from typing import Optional

from app.utils.plant_json_handler import PlantJsonHandler


def _resolve_trigger(handler: PlantJsonHandler, plant_type: Optional[str], plant_name: Optional[str]) -> Optional[float]:
    for name in (plant_type, plant_name):
        if not name:
            continue
        try:
            value = handler.get_soil_moisture_trigger(name)
        except Exception:
            continue
        if value is None:
            continue
        try:
            value = float(value)
        except (TypeError, ValueError):
            continue
        if 0 <= value <= 100:
            return value
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Report plants missing soil_moisture_threshold_override.")
    parser.add_argument(
        "--db",
        dest="db_path",
        default=str(Path(__file__).resolve().parents[1] / "sysgrow.db"),
        help="Path to SQLite database (default: ./sysgrow.db)",
    )
    args = parser.parse_args()

    db_path = Path(args.db_path)
    if not db_path.exists():
        print(f"Database not found: {db_path}")
        return 1

    handler = PlantJsonHandler()
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT plant_id, unit_id, name, plant_type, soil_moisture_threshold_override
        FROM Plants
        ORDER BY plant_id ASC
        """
    )
    rows = cursor.fetchall()
    conn.close()

    missing = []
    suggested = 0
    unresolved = 0

    for row in rows:
        if row["soil_moisture_threshold_override"] is not None:
            continue
        plant_id = row["plant_id"]
        unit_id = row["unit_id"]
        name = row["name"]
        plant_type = row["plant_type"]
        suggestion = _resolve_trigger(handler, plant_type, name)
        missing.append((plant_id, unit_id, name, plant_type, suggestion))
        if suggestion is None:
            unresolved += 1
        else:
            suggested += 1

    total = len(rows)
    print(f"Total plants: {total}")
    print(f"Missing soil_moisture_threshold_override: {len(missing)}")
    print(f"With suggested default: {suggested}")
    print(f"Unresolved (no catalog match): {unresolved}")

    if not missing:
        return 0

    print("\nMissing overrides:")
    for plant_id, unit_id, name, plant_type, suggestion in missing:
        label = f"{suggestion:.1f}%" if suggestion is not None else "none"
        print(f"- plant_id={plant_id} unit_id={unit_id} name={name} type={plant_type} suggested={label}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
