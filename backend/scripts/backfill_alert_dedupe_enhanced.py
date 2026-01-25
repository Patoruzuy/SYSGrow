#!/usr/bin/env python3
"""
Enhanced backfill: compute dedupe keys for existing alerts and populate AlertDedupe.

Strategies (in order):
- If `metadata.dedup_key` exists, skip (already handled).
- If `source_type` and `source_id` present -> dedup_key = f"{alert_type}:{source_type}:{source_id}"
- Else if metadata contains a sensor or device name field -> use that.
- Else fallback to SHA1(title + message) to group identical messages.

This script updates Alert.metadata (adds dedup_key) and upserts AlertDedupe entries.

Usage:
    python scripts/backfill_alert_dedupe_enhanced.py --db database/sysgrow.db
"""
import os
import sys
import json
import argparse
import hashlib
from typing import Optional

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from infrastructure.database.sqlite_handler import SQLiteDatabaseHandler
from app.utils.time import iso_now


def compute_key(row: dict) -> Optional[str]:
    # Prefer explicit metadata dedup_key
    meta_raw = row.get('metadata')
    try:
        md = json.loads(meta_raw) if meta_raw else {}
    except Exception:
        md = {}

    if md.get('dedup_key'):
        return str(md.get('dedup_key'))

    alert_type = row.get('alert_type')
    source_type = row.get('source_type')
    source_id = row.get('source_id')
    title = row.get('title') or ''
    message = row.get('message') or ''

    if source_type and source_id:
        return f"{alert_type}:{source_type}:{source_id}"

    # Try name fields in metadata
    for k in ('sensor_name', 'name', 'device_name', 'sensor', 'device'):
        if k in md and md.get(k):
            return f"{alert_type}:{md.get(k)}"

    # Fallback: hash title+message
    h = hashlib.sha1()
    h.update((title + '\n' + message).encode('utf-8'))
    return f"{alert_type}:msghash:{h.hexdigest()[:12]}"


def backfill(db_path: str) -> int:
    dbh = SQLiteDatabaseHandler(db_path)
    dbh.create_tables()

    updated = 0
    with dbh.connection() as conn:
        cur = conn.execute("SELECT alert_id, timestamp, alert_type, title, message, source_type, source_id, metadata FROM Alert ORDER BY timestamp DESC")
        rows = cur.fetchall()
        for r in rows:
            try:
                alert = dict(r)
                aid = int(alert.get('alert_id'))
                meta_raw = alert.get('metadata')
                try:
                    md = json.loads(meta_raw) if meta_raw else {}
                except Exception:
                    md = {}

                if md.get('dedup_key'):
                    # Ensure AlertDedupe exists for this key
                    dk = str(md.get('dedup_key'))
                else:
                    dk = compute_key(alert)
                    if not dk:
                        continue
                    md['dedup_key'] = dk

                occurrences = int(md.get('occurrences', 1))
                last_seen = md.get('last_seen') or alert.get('timestamp') or iso_now()

                # Update Alert.metadata if we added dedup_key
                if meta_raw is None or 'dedup_key' not in (json.loads(meta_raw) if meta_raw else {}):
                    try:
                        conn.execute("UPDATE Alert SET metadata = ? WHERE alert_id = ?", (json.dumps(md), aid))
                    except Exception:
                        pass

                # Upsert AlertDedupe
                cur2 = conn.execute("SELECT dedupe_id, occurrences FROM AlertDedupe WHERE dedup_key = ?", (dk,))
                ex = cur2.fetchone()
                if ex:
                    try:
                        existing_occ = int(ex.get('occurrences', 0))
                    except Exception:
                        existing_occ = 0
                    new_occ = max(existing_occ, occurrences)
                    conn.execute("UPDATE AlertDedupe SET alert_id = ?, occurrences = ?, last_seen = ? WHERE dedup_key = ?", (aid, new_occ, last_seen, dk))
                else:
                    conn.execute("INSERT INTO AlertDedupe (dedup_key, alert_id, occurrences, last_seen) VALUES (?, ?, ?, ?)", (dk, aid, occurrences, last_seen))

                updated += 1
            except Exception as e:
                print(f"Skipping row due to error: {e}")
        conn.commit()
    return updated


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--db', default='var/data.db')
    args = p.parse_args()
    n = backfill(args.db)
    print(f"Enhanced backfilled {n} alerts (added dedup_key and/or AlertDedupe rows).")
