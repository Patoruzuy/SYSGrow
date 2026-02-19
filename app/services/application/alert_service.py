"""Alert and notification service for system monitoring."""

import contextlib
import json
import logging
from collections import OrderedDict
from datetime import datetime
from typing import Any

from app.utils.cache import CacheRegistry, TTLCache
from app.utils.time import iso_now, utc_now
from infrastructure.database.repositories.alerts import AlertRepository

logger = logging.getLogger(__name__)

# Maximum number of alerts kept in the in-memory cache.
_ALERTS_CACHE_MAXSIZE = 2048

# TODO: Consider adding alert expiration and automatic cleanup of old alerts.
# if the alert is the same as an existing active alert, we might want to just update a count/timestamp instead of creating a new one.
# Take all the database opertaions to repository layer.


class AlertService:
    """Service for managing system alerts and notifications."""

    # Alert type constants
    DEVICE_OFFLINE = "device_offline"
    DEVICE_MALFUNCTION = "device_malfunction"
    SENSOR_ANOMALY = "sensor_anomaly"
    ACTUATOR_FAILURE = "actuator_failure"
    THRESHOLD_EXCEEDED = "threshold_exceeded"
    PLANT_HEALTH_WARNING = "plant_health_warning"
    LOW_BATTERY = "low_battery"
    CONNECTION_LOST = "connection_lost"
    SYSTEM_ERROR = "system_error"
    MAINTENANCE_REQUIRED = "maintenance_required"
    HARVEST_READY = "harvest_ready"
    WATER_LOW = "water_low"

    # Severity levels
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"

    def __init__(self, alert_repo: AlertRepository):
        """Initialize the alert service.

        Args:
            repo: AlertRepository instance
        """
        self.alert_repo = alert_repo

        # Dedupe configuration
        # Per-process in-memory dedupe (fast) and optional DB-backed dedupe (multi-process)
        self._dedupe_ttl_seconds = 900
        self._dedupe_cache = TTLCache(enabled=True, ttl_seconds=self._dedupe_ttl_seconds, maxsize=1024)
        # Enable DB-backed dedupe to support multi-process deployments
        self._dedupe_db_enabled = True
        self._dedupe_db_seconds = self._dedupe_ttl_seconds
        with contextlib.suppress(ValueError):
            CacheRegistry.get_instance().register("alert_service.dedupe", self._dedupe_cache)

        # In-memory alert store to reduce DB reads on constrained devices (Raspberry Pi)
        # Maps alert_id -> alert row dict — bounded to _ALERTS_CACHE_MAXSIZE (LRU eviction)
        self._alerts: OrderedDict[int, dict[str, Any]] = OrderedDict()
        # Quick index: dedup_key -> alert_id (most recent)
        self._alerts_by_dedup: dict[str, int] = {}

    def _cache_alert_row(self, row: dict[str, Any]) -> None:
        """Cache a DB alert row in memory and index by dedup_key if present."""
        try:
            if not row:
                return
            alert_id = int(row.get("alert_id"))
            # Ensure metadata is JSON-decoded for quick access
            meta = {}
            if row.get("metadata"):
                try:
                    meta = json.loads(row.get("metadata") or "{}") or {}
                except (KeyError, TypeError, ValueError, AttributeError) as e:
                    logger.debug("Failed to parse alert metadata for caching: %s", e)
                    meta = {}
            # Build cache entry
            cached = dict(row)
            cached["metadata"] = meta
            self._alerts[alert_id] = cached
            # Move to end (most-recently-used) and evict oldest if over limit
            self._alerts.move_to_end(alert_id)
            while len(self._alerts) > _ALERTS_CACHE_MAXSIZE:
                evicted_id, evicted = self._alerts.popitem(last=False)
                # Remove stale dedup index entry
                evicted_meta = evicted.get("metadata") or {}
                evicted_dk = evicted_meta.get("dedup_key") if isinstance(evicted_meta, dict) else None
                if evicted_dk and self._alerts_by_dedup.get(str(evicted_dk)) == evicted_id:
                    self._alerts_by_dedup.pop(str(evicted_dk), None)

            # Index dedup_key if present
            dk = meta.get("dedup_key")
            if dk:
                try:
                    self._alerts_by_dedup[str(dk)] = alert_id
                except (KeyError, TypeError, ValueError, AttributeError) as e:
                    logger.debug("Failed to index alert by dedup key: %s", e)
        except Exception as e:  # TODO(narrow): truly defensive — wraps complex cache logic
            # Non-fatal caching errors
            logger.debug("_cache_alert_row failed: %s", e)
            return

    def _get_cached_alert(self, alert_id: int) -> dict[str, Any] | None:
        """Return cached alert row or None. If missing, try to fetch from repo and cache it."""
        try:
            if alert_id in self._alerts:
                return self._alerts[alert_id]
            row = self.alert_repo.get_by_id(alert_id)
            if row:
                self._cache_alert_row(dict(row))
                return self._alerts.get(alert_id)
        except (KeyError, TypeError, ValueError, OSError) as e:
            logger.debug("_get_cached_alert failed: %s", e)
            pass
        return None

    # ------------------------------------------------------------------
    # Deduplication helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_dedup_key(
        alert_type: str,
        source_type: str | None,
        source_id: int | None,
        explicit_key: str | None = None,
    ) -> str:
        """Return a stable cache key for deduplication."""
        if explicit_key:
            return f"alert:{explicit_key}"
        return f"alert:{alert_type}:{source_type or ''}:{source_id or ''}"

    def _parse_alert_timestamp(self, ts: str | None) -> datetime | None:
        """Parse an ISO-format timestamp, falling back to dateutil if needed."""
        if not ts:
            return None
        try:
            return datetime.fromisoformat(ts)
        except (KeyError, TypeError, ValueError, AttributeError):
            try:
                from dateutil import parser as _parser

                return _parser.parse(ts)
            except Exception:  # TODO(narrow): needs ImportError + dateutil parse errors
                return None

    def _increment_occurrences(
        self,
        existing_id: int,
        existing_meta: dict[str, Any],
        cache_key: str,
        now_iso: str,
    ) -> int:
        """Bump occurrence counter on an existing alert and return its id."""
        existing_meta["occurrences"] = int(existing_meta.get("occurrences", 1)) + 1
        existing_meta["last_seen"] = now_iso
        try:
            self.alert_repo.update_metadata(existing_id, json.dumps(existing_meta))
        except (KeyError, TypeError, ValueError, OSError):
            logger.warning("Failed persisting dedupe metadata for alert %s", existing_id)
        try:
            row = self.alert_repo.get_by_id(existing_id)
            if row:
                self._cache_alert_row(dict(row))
        except (KeyError, TypeError, ValueError, OSError):
            logger.debug("Cache refresh after dedup hit failed for alert %s", existing_id)
        with contextlib.suppress(KeyError, TypeError, ValueError, AttributeError):
            self._dedupe_cache.set(cache_key, existing_id)
        return existing_id

    def _try_deduplicate(
        self,
        cache_key: str,
        alert_type: str,
        source_type: str | None,
        source_id: int | None,
        metadata: dict[str, Any],
        now_iso: str,
    ) -> int | None:
        """Check all dedup layers and return existing alert_id, or None.

        Layer 1: In-memory ``_alerts_by_dedup`` dict (fastest).
        Layer 2: ``_dedupe_cache`` TTLCache.
        Layer 3: DB query via ``alert_repo.find_latest`` (cross-process safe).

        On a hit the existing alert's occurrence count is incremented.
        """
        dedup_key_val = metadata.get("dedup_key")
        ttl = float(self._dedupe_db_seconds)

        # --- Layer 1: in-memory dict ---
        try:
            if dedup_key_val:
                aid = self._alerts_by_dedup.get(str(dedup_key_val))
                if aid:
                    cached = self._get_cached_alert(aid)
                    if cached:
                        existing_dt = self._parse_alert_timestamp(cached.get("timestamp"))
                        if existing_dt and (utc_now() - existing_dt).total_seconds() <= ttl:
                            return self._increment_occurrences(
                                aid,
                                cached.get("metadata") or {},
                                cache_key,
                                now_iso,
                            )
        except (KeyError, TypeError, ValueError, AttributeError):
            logger.debug("In-memory dedup fast-path failed")

        # --- Layer 2: TTLCache ---
        try:
            existing = self._dedupe_cache.get(cache_key)
            if existing:
                if not self._dedupe_db_enabled:
                    # No DB layer — just increment locally
                    cached = self._get_cached_alert(int(existing))
                    return self._increment_occurrences(
                        int(existing),
                        (cached.get("metadata") or {}) if cached else {},
                        cache_key,
                        now_iso,
                    )
                # DB layer available — invalidate cache so DB check runs below
                self._dedupe_cache.invalidate(cache_key)
        except (KeyError, TypeError, ValueError, AttributeError):
            logger.debug("TTLCache dedup check failed for key %s", cache_key)

        # --- Layer 3: DB query ---
        if self._dedupe_db_enabled:
            try:
                cand = self.alert_repo.find_latest(
                    alert_type,
                    source_type,
                    source_id,
                    dedup_key=dedup_key_val if isinstance(metadata, dict) else None,
                )
                if cand and cand.get("alert_id"):
                    existing_dt = self._parse_alert_timestamp(cand.get("timestamp"))
                    if existing_dt and (utc_now() - existing_dt).total_seconds() <= ttl:
                        existing_meta = {}
                        if cand.get("metadata"):
                            try:
                                existing_meta = json.loads(cand["metadata"]) or {}
                            except (KeyError, TypeError, ValueError, AttributeError):
                                existing_meta = {}
                        return self._increment_occurrences(
                            int(cand["alert_id"]),
                            existing_meta,
                            cache_key,
                            now_iso,
                        )
            except (KeyError, TypeError, ValueError, OSError):
                logger.warning("DB dedup check failed for %s", cache_key)

        return None

    def create_alert(
        self,
        alert_type: str,
        severity: str,
        title: str,
        message: str,
        source_type: str | None = None,
        source_id: int | None = None,
        unit_id: int | None = None,
        metadata: dict[str, Any] | None = None,
        dedupe: bool = True,
        dedupe_key: str | None = None,
    ) -> int:
        """Create a new alert.

        Args:
            alert_type: Type of alert (use class constants)
            severity: Severity level (info, warning, critical)
            title: Short alert title
            message: Detailed alert message
            source_type: Type of source entity (e.g., 'sensor', 'actuator')
            source_id: ID of the source entity
            unit_id: Associated growth unit ID
            metadata: Additional metadata as dictionary (will be JSON serialized)

        Returns:
            int: The ID of the created alert

        Raises:
            ValueError: If alert_type or severity is invalid
        """
        valid_alert_types = {
            self.DEVICE_OFFLINE,
            self.DEVICE_MALFUNCTION,
            self.SENSOR_ANOMALY,
            self.ACTUATOR_FAILURE,
            self.THRESHOLD_EXCEEDED,
            self.PLANT_HEALTH_WARNING,
            self.LOW_BATTERY,
            self.CONNECTION_LOST,
            self.SYSTEM_ERROR,
            self.MAINTENANCE_REQUIRED,
            self.HARVEST_READY,
            self.WATER_LOW,
        }

        valid_severities = {self.INFO, self.WARNING, self.CRITICAL}

        if alert_type not in valid_alert_types:
            raise ValueError(f"Invalid alert_type: {alert_type}")

        if severity not in valid_severities:
            raise ValueError(f"Invalid severity: {severity}")

        # Ensure metadata is a dict we can annotate
        if metadata is None or not isinstance(metadata, dict):
            metadata = {} if metadata is None else {"value": metadata}

        # Ensure dedup_key is present for future DB-backed dedupe: prefer explicit param
        if dedupe:
            if dedupe_key:
                metadata["dedup_key"] = str(dedupe_key)
            else:
                metadata.setdefault(
                    "dedup_key",
                    f"{alert_type}:{source_type or ''}:{source_id or ''}",
                )

        # For new alerts, initialize occurrence tracking
        now_iso = iso_now()
        metadata.setdefault("occurrences", 1)
        metadata.setdefault("first_seen", now_iso)
        metadata["last_seen"] = now_iso

        metadata_json = json.dumps(metadata) if metadata else None

        # --- Deduplication (consolidated) ---
        if dedupe:
            _key = self._compute_dedup_key(alert_type, source_type, source_id, dedupe_key)
            existing_id = self._try_deduplicate(
                _key,
                alert_type,
                source_type,
                source_id,
                metadata,
                now_iso,
            )
            if existing_id is not None:
                return existing_id

        # --- Create new alert ---
        try:
            alert_id = self.alert_repo.create(
                iso_now(),
                alert_type,
                severity,
                title,
                message,
                source_type,
                source_id,
                unit_id,
                metadata_json,
            )
            if alert_id is None:
                raise RuntimeError("DB insert returned no id")
            logger.info("Alert created: [%s] %s", severity, title)
            if dedupe:
                with contextlib.suppress(KeyError, TypeError, ValueError, AttributeError):
                    self._dedupe_cache.set(_key, alert_id)
            try:
                r = self.alert_repo.get_by_id(alert_id)
                if r:
                    self._cache_alert_row(dict(r))
            except (KeyError, TypeError, ValueError, OSError):
                logger.debug("Failed caching alert row after create")
            return alert_id
        except (KeyError, TypeError, ValueError, RuntimeError, OSError) as e:
            logger.error("Failed to create alert: %s", e)
            raise

    def get_active_alerts(
        self,
        severity: str | None = None,
        unit_id: int | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Get active (unresolved) alerts.

        Args:
            severity: Filter by severity level (optional)
            unit_id: Filter by unit ID (optional)
            limit: Maximum number of alerts to return

        Returns:
            List of alert dictionaries
        """
        try:
            # Try to satisfy from in-memory cache first to reduce DB reads
            results: list[dict[str, Any]] = []
            if self._alerts:
                for a in self._alerts.values():
                    try:
                        if a.get("resolved"):
                            continue
                        if severity and a.get("severity") != severity:
                            continue
                        if unit_id is not None and a.get("unit_id") != unit_id:
                            continue
                        results.append(a)
                        if len(results) >= limit:
                            break
                    except (KeyError, TypeError, ValueError, AttributeError):
                        continue

            if results:
                return results

            # Fallback to DB
            rows = self.alert_repo.list_active(severity=severity, unit_id=unit_id, limit=limit)
            alerts = []
            for row in rows:
                alert = dict(row)
                if alert.get("metadata"):
                    try:
                        alert["metadata"] = json.loads(alert["metadata"])
                    except json.JSONDecodeError:
                        alert["metadata"] = None
                alerts.append(alert)
                # cache for later
                with contextlib.suppress(KeyError, TypeError, ValueError, AttributeError):
                    self._cache_alert_row(alert)
            return alerts
        except (KeyError, TypeError, ValueError, OSError) as e:
            logger.error("Failed to retrieve active alerts: %s", e)
            return []

    def acknowledge_alert(self, alert_id: int, user_id: int | None = None) -> bool:
        """Acknowledge an alert.

        Args:
            alert_id: ID of the alert to acknowledge
            user_id: ID of the user acknowledging the alert

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            return self.alert_repo.acknowledge(alert_id, user_id)
        except (KeyError, TypeError, ValueError, OSError) as e:
            logger.error("Failed to acknowledge alert: %s", e)
            return False

    def resolve_alert(self, alert_id: int) -> bool:
        """Mark an alert as resolved.

        Args:
            alert_id: ID of the alert to resolve

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            success = self.alert_repo.resolve(alert_id)
            if success and alert_id in self._alerts:
                # Invalidate cache for this alert
                self._alerts[alert_id]["resolved"] = True
                self._alerts[alert_id]["resolved_at"] = iso_now()
            return success
        except (KeyError, TypeError, ValueError, OSError) as e:
            logger.error("Failed to resolve alert: %s", e)
            return False

    def get_alert_summary(self) -> dict[str, Any]:
        """Get summary statistics of alerts.

        Returns:
            Dictionary containing alert counts by severity and status
        """
        try:
            return self.alert_repo.summary()
        except (KeyError, TypeError, ValueError, OSError) as e:
            logger.error("Failed to get alert summary: %s", e)
            return {
                "total_active": 0,
                "total_resolved": 0,
                "active_by_severity": {"info": 0, "warning": 0, "critical": 0},
            }

    def purge_old_alerts(self, retention_days: int = 30, resolved_only: bool = True) -> dict[str, Any]:
        """
        Purge or compact old alerts from the database.

        Args:
            retention_days: Number of days to retain alerts (older alerts will be deleted)
            resolved_only: If True, only delete alerts that are marked resolved. If False, delete all old alerts.
            Returns:
                dict: {"success": bool, "deleted_rows": int}
        """
        try:
            from datetime import timedelta

            cutoff_dt = utc_now() - timedelta(days=max(1, int(retention_days)))
            cutoff_iso = cutoff_dt.isoformat()

            deleted = self.alert_repo.purge_old(cutoff_iso, resolved_only=resolved_only)
            logger.info(
                "Purged %s alert(s) older than %s day(s) (resolved_only=%s)", deleted, retention_days, resolved_only
            )
            return {"success": True, "deleted_rows": deleted}
        except (KeyError, TypeError, ValueError, OSError) as e:
            logger.error("Failed to purge old alerts: %s", e)
            return {"success": False, "error": str(e)}
