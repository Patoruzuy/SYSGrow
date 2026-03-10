from __future__ import annotations

import json
import logging
import sqlite3
from typing import Any

from app.utils.time import iso_now

logger = logging.getLogger(__name__)


class AlertOperations:
    """Database operations for Alert entity."""

    def find_latest_matching_alert(
        self,
        alert_type: str,
        source_type: str | None = None,
        source_id: int | None = None,
        dedup_key: str | None = None,
    ):
        try:
            db = self.get_db()
            # If dedup_key is provided, prefer the AlertDedupe table for a fast indexed lookup
            if dedup_key:
                try:
                    cur = db.execute(
                        "SELECT alert_id, dedup_key, occurrences, last_seen FROM AlertDedupe WHERE dedup_key = ?",
                        (dedup_key,),
                    )
                    ded = cur.fetchone()
                    if ded and ded.get("alert_id"):
                        # Return the linked alert row
                        cur2 = db.execute("SELECT * FROM Alert WHERE alert_id = ? AND resolved = 0", (ded["alert_id"],))
                        arow = cur2.fetchone()
                        if arow:
                            return arow
                except sqlite3.Error:
                    # fallback to scanning Alert table
                    pass

            conditions = ["alert_type = ?", "resolved = 0"]
            params: list[Any] = [alert_type]

            if source_type is None:
                conditions.append("source_type IS NULL")
            else:
                conditions.append("source_type = ?")
                params.append(source_type)

            if source_id is None:
                conditions.append("source_id IS NULL")
            else:
                conditions.append("source_id = ?")
                params.append(source_id)

            if dedup_key:
                conditions.append("metadata LIKE ?")
                params.append(f'%"dedup_key": "{dedup_key}"%')

            query = "SELECT * FROM Alert WHERE " + " AND ".join(conditions) + " ORDER BY timestamp DESC LIMIT 1"
            cur = db.execute(query, params)
            return cur.fetchone()
        except sqlite3.Error as exc:
            logger.debug("AlertOperations.find_latest_matching_alert failed: %s", exc)
            return None

    def get_alert_by_id(self, alert_id: int):
        try:
            db = self.get_db()
            cur = db.execute("SELECT * FROM Alert WHERE alert_id = ?", (alert_id,))
            return cur.fetchone()
        except sqlite3.Error:
            return None

    def insert_alert(
        self,
        timestamp: str,
        alert_type: str,
        severity: str,
        title: str,
        message: str,
        source_type: str | None,
        source_id: int | None,
        unit_id: int | None,
        metadata_json: str | None,
    ) -> int | None:
        try:
            db = self.get_db()
            cur = db.cursor()
            cur.execute(
                """
                INSERT INTO Alert (
                    timestamp, alert_type, severity, title, message,
                    source_type, source_id, unit_id, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    timestamp,
                    alert_type,
                    severity,
                    title,
                    message,
                    source_type,
                    source_id,
                    unit_id,
                    metadata_json,
                ),
            )
            alert_id = cur.lastrowid
            # If metadata includes a dedup_key, upsert the AlertDedupe table
            try:
                if metadata_json:
                    md = json.loads(metadata_json)
                    dk = md.get("dedup_key")
                    if dk:
                        # Upsert dedupe mapping
                        cur2 = db.execute("SELECT dedupe_id FROM AlertDedupe WHERE dedup_key = ?", (dk,))
                        existing = cur2.fetchone()
                        if existing and existing.get("dedupe_id"):
                            db.execute(
                                "UPDATE AlertDedupe SET alert_id = ?, last_seen = ?, occurrences = occurrences + 1 WHERE dedup_key = ?",
                                (alert_id, timestamp, dk),
                            )
                        else:
                            db.execute(
                                "INSERT INTO AlertDedupe (dedup_key, alert_id, occurrences, last_seen) VALUES (?, ?, ?, ?)",
                                (dk, alert_id, int(md.get("occurrences", 1)), timestamp),
                            )
            except Exception:
                # non-fatal
                pass

            db.commit()
            return alert_id
        except sqlite3.Error as exc:
            logger.error("Failed to insert alert: %s", exc)
            return None

    def update_alert_metadata(self, alert_id: int, metadata_json: str) -> bool:
        try:
            db = self.get_db()
            db.execute("UPDATE Alert SET metadata = ? WHERE alert_id = ?", (metadata_json, alert_id))
            # If metadata contains dedup_key, ensure AlertDedupe points to this alert_id
            try:
                md = json.loads(metadata_json) if metadata_json else {}
                dk = md.get("dedup_key")
                if dk:
                    cur = db.execute("SELECT dedupe_id FROM AlertDedupe WHERE dedup_key = ?", (dk,))
                    if cur.fetchone():
                        db.execute(
                            "UPDATE AlertDedupe SET alert_id = ?, last_seen = ?, occurrences = occurrences + 1 WHERE dedup_key = ?",
                            (alert_id, iso_now(), dk),
                        )
                    else:
                        db.execute(
                            "INSERT INTO AlertDedupe (dedup_key, alert_id, occurrences, last_seen) VALUES (?, ?, ?, ?)",
                            (dk, alert_id, int(md.get("occurrences", 1)), iso_now()),
                        )
            except Exception:
                pass
            db.commit()
            return True
        except sqlite3.Error as exc:
            logger.debug("Failed to update alert metadata: %s", exc)
            return False

    def get_active_alerts(self, severity: str | None = None, unit_id: int | None = None, limit: int = 100):
        try:
            db = self.get_db()
            query = "SELECT * FROM Alert WHERE resolved = 0"
            params: list[Any] = []
            if severity:
                query += " AND severity = ?"
                params.append(severity)
            if unit_id is not None:
                query += " AND unit_id = ?"
                params.append(unit_id)
            query += " ORDER BY severity DESC, timestamp DESC LIMIT ?"
            params.append(limit)
            cur = db.execute(query, params)
            return cur.fetchall()
        except sqlite3.Error as exc:
            logger.debug("get_active_alerts failed: %s", exc)
            return []

    def list_active(self, severity: str | None = None, unit_id: int | None = None, limit: int = 100):
        """Alias for get_active_alerts for consistency."""
        return self.get_active_alerts(severity=severity, unit_id=unit_id, limit=limit)

    def acknowledge_alert(self, alert_id: int, user_id: int | None = None) -> bool:
        try:
            db = self.get_db()
            db.execute(
                "UPDATE Alert SET acknowledged = 1, acknowledged_at = ?, acknowledged_by = ? WHERE alert_id = ?",
                (iso_now(), user_id, alert_id),
            )
            db.commit()
            return True
        except Exception as exc:
            logger.debug("acknowledge_alert failed: %s", exc)
            return False

    def resolve_alert(self, alert_id: int) -> bool:
        try:
            from app.utils.time import iso_now

            db = self.get_db()
            db.execute("UPDATE Alert SET resolved = 1, resolved_at = ? WHERE alert_id = ?", (iso_now(), alert_id))
            db.commit()
            return True
        except Exception as exc:
            logger.debug("resolve_alert failed: %s", exc)
            return False

    def get_alert_summary(self) -> dict[str, Any]:
        try:
            db = self.get_db()
            cursor = db.execute("SELECT severity, COUNT(*) as count FROM Alert WHERE resolved = 0 GROUP BY severity")
            active_by_severity = {row[0]: row[1] for row in cursor.fetchall()}
            cursor = db.execute("SELECT COUNT(*) as total FROM Alert WHERE resolved = 0")
            total_active = cursor.fetchone()[0]
            cursor = db.execute("SELECT COUNT(*) as total FROM Alert WHERE resolved = 1")
            total_resolved = cursor.fetchone()[0]
            return {
                "total_active": total_active,
                "total_resolved": total_resolved,
                "active_by_severity": {
                    "info": active_by_severity.get("info", 0),
                    "warning": active_by_severity.get("warning", 0),
                    "critical": active_by_severity.get("critical", 0),
                },
            }
        except Exception as exc:
            logger.debug("get_alert_summary failed: %s", exc)
            return {
                "total_active": 0,
                "total_resolved": 0,
                "active_by_severity": {"info": 0, "warning": 0, "critical": 0},
            }

    def purge_old_alerts(self, cutoff_iso: str, resolved_only: bool = True) -> int:
        try:
            db = self.get_db()
            if resolved_only:
                cur = db.execute(
                    "SELECT COUNT(*) as cnt FROM Alert WHERE resolved = 1 AND timestamp < ?", (cutoff_iso,)
                )
                to_delete = cur.fetchone()[0]
                if to_delete > 0:
                    db.execute("DELETE FROM Alert WHERE resolved = 1 AND timestamp < ?", (cutoff_iso,))
                    db.commit()
                return to_delete
            else:
                cur = db.execute("SELECT COUNT(*) as cnt FROM Alert WHERE timestamp < ?", (cutoff_iso,))
                to_delete = cur.fetchone()[0]
                if to_delete > 0:
                    db.execute("DELETE FROM Alert WHERE timestamp < ?", (cutoff_iso,))
                    db.commit()
                return to_delete
        except Exception as exc:
            logger.debug("purge_old_alerts failed: %s", exc)
            return 0
