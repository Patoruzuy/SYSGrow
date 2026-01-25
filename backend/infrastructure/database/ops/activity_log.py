from __future__ import annotations

import logging
import sqlite3
import json
from typing import Any, Dict, List, Optional


logger = logging.getLogger(__name__)


class ActivityOperations:
    """Database operations for ActivityLog table."""

    def insert_activity(self, activity: Dict[str, Any]) -> Optional[int]:
        try:
            db = self.get_db()
            cur = db.cursor()
            metadata_json = json.dumps(activity.get("metadata", {})) if activity.get("metadata") else None
            cur.execute(
                """
                INSERT INTO ActivityLog (
                    timestamp, user_id, activity_type, severity,
                    entity_type, entity_id, description, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    activity.get("timestamp"),
                    activity.get("user_id"),
                    activity.get("activity_type"),
                    activity.get("severity"),
                    activity.get("entity_type"),
                    activity.get("entity_id"),
                    activity.get("description"),
                    metadata_json,
                ),
            )
            db.commit()
            return cur.lastrowid
        except sqlite3.Error as exc:
            logger.debug("insert_activity failed: %s", exc)
            return None

    def get_recent_activities(self, limit: int = 50, activity_type: Optional[str] = None, severity: Optional[str] = None, user_id: Optional[int] = None) -> List[Dict[str, Any]]:
        try:
            db = self.get_db()
            query = "SELECT * FROM ActivityLog WHERE 1=1"
            params: List[Any] = []
            if activity_type:
                query += " AND activity_type = ?"
                params.append(activity_type)
            if severity:
                query += " AND severity = ?"
                params.append(severity)
            if user_id is not None:
                query += " AND user_id = ?"
                params.append(user_id)
            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)
            cur = db.execute(query, params)
            rows = cur.fetchall()
            results = []
            for r in rows:
                row = dict(r)
                if row.get("metadata"):
                    try:
                        row["metadata"] = json.loads(row["metadata"])
                    except Exception:
                        row["metadata"] = None
                results.append(row)
            return results
        except sqlite3.Error as exc:
            logger.debug("get_recent_activities failed: %s", exc)
            return []

    def get_activities_for_entity(self, entity_type: str, entity_id: int, limit: int = 20) -> List[Dict[str, Any]]:
        try:
            db = self.get_db()
            cur = db.execute(
                "SELECT * FROM ActivityLog WHERE entity_type = ? AND entity_id = ? ORDER BY timestamp DESC LIMIT ?",
                (entity_type, entity_id, limit),
            )
            rows = cur.fetchall()
            results = []
            for r in rows:
                row = dict(r)
                if row.get("metadata"):
                    try:
                        row["metadata"] = json.loads(row["metadata"])
                    except Exception:
                        row["metadata"] = None
                results.append(row)
            return results
        except sqlite3.Error as exc:
            logger.debug("get_activities_for_entity failed: %s", exc)
            return []

    def get_activity_statistics(self) -> Dict[str, Any]:
        try:
            db = self.get_db()
            cursor = db.execute("SELECT activity_type, COUNT(*) as count FROM ActivityLog GROUP BY activity_type")
            by_type = {row[0]: row[1] for row in cursor.fetchall()}
            cursor = db.execute("SELECT severity, COUNT(*) as count FROM ActivityLog GROUP BY severity")
            by_severity = {row[0]: row[1] for row in cursor.fetchall()}
            cursor = db.execute("SELECT COUNT(*) as total FROM ActivityLog")
            total = cursor.fetchone()[0]
            return {"total": total, "by_type": by_type, "by_severity": by_severity}
        except sqlite3.Error as exc:
            logger.debug("get_activity_statistics failed: %s", exc)
            return {"total": 0, "by_type": {}, "by_severity": {}}
