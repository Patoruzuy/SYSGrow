"""Database migration utilities for startup tasks."""
from __future__ import annotations

import json
import hashlib
from typing import Optional

from app.utils.time import iso_now


def compute_dedup_key_for_row(row: dict) -> str:
    """Compute a stable dedupe key for an Alert row."""
    md = {}
    try:
        md = json.loads(row.get("metadata") or "{}")
    except Exception:
        md = {}

    if md.get("dedup_key"):
        return str(md.get("dedup_key"))

    alert_type = row.get("alert_type") or ""
    source_type = row.get("source_type") or ""
    source_id = row.get("source_id") or ""
    title = row.get("title") or ""
    message = row.get("message") or ""

    if source_type and source_id:
        return f"{alert_type}:{source_type}:{source_id}"

    for k in ("sensor_name", "name", "device_name", "sensor", "device"):
        if md.get(k):
            return f"{alert_type}:{md.get(k)}"

    h = hashlib.sha1()
    h.update((title + "\n" + message).encode("utf-8"))
    return f"{alert_type}:msghash:{h.hexdigest()[:12]}"


def run_startup_migrations(db_handler) -> int:
    """Run idempotent startup migrations against provided DB handler.

    Returns the number of dedupe rows created/updated.
    """
    updated = 0
    try:
        with db_handler.connection() as conn:
            # Quick check: if AlertDedupe exists and has rows, skip heavy backfill
            cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='AlertDedupe'")
            if cur.fetchone():
                cur = conn.execute("SELECT COUNT(*) as cnt FROM AlertDedupe")
                cnt = cur.fetchone()[0]
                if cnt and int(cnt) > 0:
                    return 0

            cur = conn.execute("SELECT alert_id, timestamp, alert_type, title, message, source_type, source_id, metadata FROM Alert ORDER BY timestamp DESC")
            rows = cur.fetchall()
            for r in rows:
                try:
                    row = dict(r)
                    aid = int(row.get("alert_id"))
                    md_raw = row.get("metadata")
                    try:
                        md = json.loads(md_raw) if md_raw else {}
                    except Exception:
                        md = {}

                    dk = md.get("dedup_key") if md.get("dedup_key") else compute_dedup_key_for_row(row)
                    md["dedup_key"] = dk
                    occurrences = int(md.get("occurrences", 1))
                    last_seen = md.get("last_seen") or row.get("timestamp") or iso_now()

                    # Update Alert metadata if needed
                    try:
                        conn.execute("UPDATE Alert SET metadata = ? WHERE alert_id = ?", (json.dumps(md), aid))
                    except Exception:
                        pass

                    # Upsert AlertDedupe
                    cur2 = conn.execute("SELECT dedupe_id, occurrences FROM AlertDedupe WHERE dedup_key = ?", (dk,))
                    ex = cur2.fetchone()
                    if ex:
                        try:
                            existing_occ = int(ex.get("occurrences", 0))
                        except Exception:
                            existing_occ = 0
                        new_occ = max(existing_occ, occurrences)
                        conn.execute(
                            "UPDATE AlertDedupe SET alert_id = ?, occurrences = ?, last_seen = ? WHERE dedup_key = ?",
                            (aid, new_occ, last_seen, dk),
                        )
                    else:
                        conn.execute(
                            "INSERT INTO AlertDedupe (dedup_key, alert_id, occurrences, last_seen) VALUES (?, ?, ?, ?)",
                            (dk, aid, occurrences, last_seen),
                        )
                    updated += 1
                except Exception:
                    continue
            conn.commit()
    except Exception:
        return updated
    return updated
