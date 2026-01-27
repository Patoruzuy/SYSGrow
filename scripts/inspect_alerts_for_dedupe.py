#!/usr/bin/env python3
"""
Inspect Alert rows and report how many have `metadata` and `dedup_key`.

Usage:
    python scripts/inspect_alerts_for_dedupe.py --db var/data.db --limit 50
"""
import os
import sys
import json
import argparse

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from infrastructure.database.sqlite_handler import SQLiteDatabaseHandler


def inspect(db_path: str, limit: int = 50):
    dbh = SQLiteDatabaseHandler(db_path)
    dbh.create_tables()
    with dbh.connection() as conn:
        cur = conn.execute("SELECT COUNT(*) as cnt FROM Alert")
        total = cur.fetchone()[0]
        cur = conn.execute("SELECT COUNT(*) as cnt FROM Alert WHERE metadata IS NOT NULL")
        with_meta = cur.fetchone()[0]
        cur = conn.execute("SELECT COUNT(*) as cnt FROM Alert WHERE metadata LIKE '%dedup_key%'")
        meta_contains_dedup = cur.fetchone()[0]

        print(f"Total alerts: {total}")
        print(f"Alerts with metadata: {with_meta}")
        print(f"Alerts with metadata containing 'dedup_key' substring: {meta_contains_dedup}")
        print("--- Sample rows ---")

        cur = conn.execute("SELECT alert_id, timestamp, alert_type, source_type, source_id, metadata FROM Alert ORDER BY timestamp DESC LIMIT ?", (limit,))
        rows = cur.fetchall()
        for r in rows:
            aid = r["alert_id"]
            t = r["timestamp"]
            atype = r["alert_type"]
            stype = r["source_type"]
            sid = r["source_id"]
            meta_raw = r["metadata"]
            has_dk = False
            parsed = None
            if meta_raw:
                try:
                    parsed = json.loads(meta_raw)
                    has_dk = 'dedup_key' in parsed
                except Exception:
                    parsed = meta_raw
                    has_dk = ('dedup_key' in str(meta_raw))
            print(f"[{aid}] {t} | type={atype} | src={stype}/{sid} | dedup_key_in_meta={has_dk}")
            print(f"  metadata: {parsed}")


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--db', default='var/data.db')
    p.add_argument('--limit', type=int, default=50)
    args = p.parse_args()
    inspect(args.db, args.limit)
