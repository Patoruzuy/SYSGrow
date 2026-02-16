from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.utils.time import iso_now
from infrastructure.database.ops.alerts import AlertOperations


@dataclass(frozen=True)
class AlertRepository:
    """Repository facade for alert operations."""

    _backend: AlertOperations

    def find_latest(
        self,
        alert_type: str,
        source_type: str | None = None,
        source_id: int | None = None,
        dedup_key: str | None = None,
    ):
        return self._backend.find_latest_matching_alert(alert_type, source_type, source_id, dedup_key)

    def upsert_dedupe(self, dedup_key: str, alert_id: int, occurrences: int = 1, last_seen: str | None = None):
        # convenience pass-through if needed by higher-level code
        try:
            db = self._backend.get_db()
            if last_seen is None:
                last_seen = iso_now()
            cur = db.execute("SELECT dedupe_id FROM AlertDedupe WHERE dedup_key = ?", (dedup_key,))
            if cur.fetchone():
                db.execute(
                    "UPDATE AlertDedupe SET alert_id = ?, occurrences = occurrences + ?, last_seen = ? WHERE dedup_key = ?",
                    (alert_id, occurrences, last_seen, dedup_key),
                )
            else:
                db.execute(
                    "INSERT INTO AlertDedupe (dedup_key, alert_id, occurrences, last_seen) VALUES (?, ?, ?, ?)",
                    (dedup_key, alert_id, occurrences, last_seen),
                )
            db.commit()
            return True
        except Exception:
            return False

    def get_by_id(self, alert_id: int):
        return self._backend.get_alert_by_id(alert_id)

    def create(
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
        return self._backend.insert_alert(
            timestamp, alert_type, severity, title, message, source_type, source_id, unit_id, metadata_json
        )

    def update_metadata(self, alert_id: int, metadata_json: str) -> bool:
        return self._backend.update_alert_metadata(alert_id, metadata_json)

    def list_active(
        self, severity: str | None = None, unit_id: int | None = None, limit: int = 100
    ) -> list[dict[str, Any]]:
        return self._backend.get_active_alerts(severity=severity, unit_id=unit_id, limit=limit)

    def acknowledge(self, alert_id: int, user_id: int | None = None) -> bool:
        return self._backend.acknowledge_alert(alert_id, user_id)

    def resolve(self, alert_id: int) -> bool:
        return self._backend.resolve_alert(alert_id)

    def summary(self) -> dict[str, Any]:
        return self._backend.get_alert_summary()

    def purge_old(self, cutoff_iso: str, resolved_only: bool = True) -> int:
        return self._backend.purge_old_alerts(cutoff_iso, resolved_only)
