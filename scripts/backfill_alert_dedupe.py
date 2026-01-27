#!/usr/bin/env python3
"""
scripts/backfill_alert_dedupe.py

Idempotent backfill script:
- Scans `Alert` rows for `metadata` containing `dedup_key`.
- Upserts entries into `AlertDedupe` with `alert_id`, `occurrences`, `last_seen`.

Usage:
    python scripts/backfill_alert_dedupe.py
    python scripts/backfill_alert_dedupe.py --db path/to/sysgrow.db

"""
import os
import sys
import json
import argparse
from typing import Any

# Ensure repository root is on sys.path when executed as a script
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from infrastructure.database.sqlite_handler import SQLiteDatabaseHandler
from app.utils.time import iso_now


def backfill(db_path: str) -> int:
    dbh = SQLiteDatabaseHandler(db_path)
    # Ensure schema exists
    dbh.create_tables()

    backfilled = 0
    with dbh.connection() as conn:
        cur = conn.execute("SELECT alert_id, timestamp, metadata FROM Alert WHERE metadata IS NOT NULL")
        rows = cur.fetchall()
        for row in rows:
            try:
                alert_id = int(row["alert_id"])
                ts = row["timestamp"]
                meta_raw = row["metadata"]
                if not meta_raw:
                    continue
                try:
                    md = json.loads(meta_raw)
                except Exception:
                    continue
                dk = md.get("dedup_key")
                if not dk:
                    continue
                occurrences = int(md.get("occurrences", 1))
                last_seen = md.get("last_seen") or ts or iso_now()

                # Upsert AlertDedupe
                cur2 = conn.execute("SELECT dedupe_id, occurrences FROM AlertDedupe WHERE dedup_key = ?", (dk,))
                existing = cur2.fetchone()
                if existing:
                    try:
                        existing_occ = int(existing.get("occurrences", 0))
                    except Exception:
                        existing_occ = 0
                    new_occ = max(existing_occ, occurrences)
                    conn.execute(
                        "UPDATE AlertDedupe SET alert_id = ?, occurrences = ?, last_seen = ? WHERE dedup_key = ?",
                        (alert_id, new_occ, last_seen, dk),
                    )
                else:
                    conn.execute(
                        "INSERT INTO AlertDedupe (dedup_key, alert_id, occurrences, last_seen) VALUES (?, ?, ?, ?)",
                        (dk, alert_id, occurrences, last_seen),
                    )
                backfilled += 1
            except Exception as e:
                # skip problematic rows but surface minimal info
                print(f"Skipping alert row due to error: {e}")
        conn.commit()

    return backfilled


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backfill AlertDedupe table from existing Alert rows.")
    parser.add_argument("--db", dest="db", default="sysgrow.db", help="Path to SQLite DB file (default: sysgrow.db)")
    args = parser.parse_args()
    n = backfill(args.db)
    print(f"Backfilled {n} dedupe entries into AlertDedupe from Alert metadata.")
