#!/usr/bin/env python3
"""
Migration: Add unit_id to Plants and backfill from GrowthUnitPlants.

Steps:
- Add unit_id column to Plants if missing.
- Backfill unit_id from GrowthUnitPlants mapping.
- Create an index on Plants.unit_id for faster lookups.
"""

import sqlite3
from pathlib import Path
from typing import Optional


def add_column(conn: sqlite3.Connection, table: str, column: str, col_type: str) -> None:
    cols = {row[1] for row in conn.execute(f"PRAGMA table_info('{table}')")}
    if column in cols:
        return
    conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")


def backfill_unit_ids(conn: sqlite3.Connection) -> int:
    updated = 0
    cursor = conn.execute("SELECT plant_id, unit_id FROM Plants WHERE unit_id IS NULL OR unit_id = ''")
    rows = cursor.fetchall()
    for row in rows:
        plant_id = row[0]
        mapping = conn.execute(
            "SELECT unit_id FROM GrowthUnitPlants WHERE plant_id = ? LIMIT 1", (plant_id,)
        ).fetchone()
        if mapping and mapping[0]:
            conn.execute("UPDATE Plants SET unit_id = ? WHERE plant_id = ?", (mapping[0], plant_id))
            updated += 1
    return updated


def migrate(db_path: Path) -> Optional[int]:
    if not db_path.exists():
        print(f"Database not found: {db_path}")
        return None

    conn = sqlite3.connect(db_path)
    try:
        with conn:
            add_column(conn, "Plants", "unit_id", "INTEGER")
            updated = backfill_unit_ids(conn)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_plants_unit_id ON Plants(unit_id)"
            )
        print(f"Migration complete. Backfilled unit_id for {updated} plants.")
        return updated
    finally:
        conn.close()


def main() -> None:
    db_path = Path("database/sysgrow.db")
    migrate(db_path)


if __name__ == "__main__":
    main()
