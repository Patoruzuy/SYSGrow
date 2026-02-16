#!/usr/bin/env python3
"""Quick verification of database migration."""

import os
import sqlite3
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
db_path = Path(
    os.getenv("SYSGROW_DATABASE_PATH", str(REPO_ROOT / "database" / "sysgrow.db"))
)
conn = sqlite3.connect(str(db_path))

print("=" * 60)
print(f"Database: {db_path}")
print("=" * 60)
print("Database Tables:")
print("=" * 60)

tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
for table in tables:
    print(f"✅ {table[0]}")

print("\n" + "=" * 60)
print("Sensor Table Schema:")
print("=" * 60)

schema = conn.execute("PRAGMA table_info(Sensor)").fetchall()
for col in schema:
    print(f"  {col[1]:<20} {col[2]:<15} {'NOT NULL' if col[3] else 'NULL'}")

print("\n" + "=" * 60)
print("Indexes:")
print("=" * 60)

indexes = conn.execute("SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'").fetchall()
for idx in indexes:
    print(f"✅ {idx[0]}")

print("\n✅ Migration verification complete!")
conn.close()
