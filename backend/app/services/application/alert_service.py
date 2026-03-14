"""Alert and notification service for system monitoring."""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.utils.time import iso_now, utc_now
from infrastructure.database.repositories.alerts import AlertRepository
from app.utils.cache import TTLCache, CacheRegistry

logger = logging.getLogger(__name__)

#TODO: Consider adding alert expiration and automatic cleanup of old alerts.
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
        try:
            CacheRegistry.get_instance().register("alert_service.dedupe", self._dedupe_cache)
        except ValueError:
            # ignore already-registered
            pass

        # In-memory alert store to reduce DB reads on constrained devices (Raspberry Pi)
        # Maps alert_id -> alert row dict
        self._alerts: Dict[int, Dict[str, Any]] = {}
        # Quick index: dedup_key -> alert_id (most recent)
        self._alerts_by_dedup: Dict[str, int] = {}

    def _cache_alert_row(self, row: Dict[str, Any]) -> None:
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
                except Exception as e:
                    logger.debug("Failed to parse alert metadata for caching: %s", e)
                    meta = {}
            # Build cache entry
            cached = dict(row)
            cached["metadata"] = meta
            self._alerts[alert_id] = cached

            # Index dedup_key if present
            dk = meta.get("dedup_key")
            if dk:
                try:
                    self._alerts_by_dedup[str(dk)] = alert_id
                except Exception as e:
                    logger.debug("Failed to index alert by dedup key: %s", e)
        except Exception as e:
            # Non-fatal caching errors
            logger.debug("_cache_alert_row failed: %s", e)
            return

    def _get_cached_alert(self, alert_id: int) -> Optional[Dict[str, Any]]:
        """Return cached alert row or None. If missing, try to fetch from repo and cache it."""
        try:
            if alert_id in self._alerts:
                return self._alerts[alert_id]
            row = self.alert_repo.get_by_id(alert_id)
            if row:
                self._cache_alert_row(dict(row))
                return self._alerts.get(alert_id)
        except Exception as e:
            logger.debug("_get_cached_alert failed: %s", e)
            pass
        return None

    def create_alert(
        self,
        alert_type: str,
        severity: str,
        title: str,
        message: str,
        source_type: Optional[str] = None,
        source_id: Optional[int] = None,
        unit_id: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
        dedupe: bool = True,
        dedupe_key: Optional[str] = None,
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
            self.DEVICE_OFFLINE, self.DEVICE_MALFUNCTION, self.SENSOR_ANOMALY,
            self.ACTUATOR_FAILURE, self.THRESHOLD_EXCEEDED, self.PLANT_HEALTH_WARNING,
            self.LOW_BATTERY, self.CONNECTION_LOST, self.SYSTEM_ERROR,
            self.MAINTENANCE_REQUIRED, self.HARVEST_READY, self.WATER_LOW
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
        try:
            if dedupe:
                if dedupe_key:
                    metadata["dedup_key"] = str(dedupe_key)
                else:
                    # Compute a stable dedupe key based on alert_type/source
                    meta_key = ""
                    try:
                        if metadata and isinstance(metadata, dict):
                            meta_key = str(metadata.get("dedup_key", ""))
                    except Exception as e:
                        logger.debug("Failed reading dedup_key from metadata: %s", e)
                        meta_key = ""
                    dedup_meta = f"{alert_type}:{source_type or ''}:{source_id or ''}:{meta_key}"
                    metadata.setdefault("dedup_key", dedup_meta)
        except Exception as e:
            logger.debug("Failed computing dedupe key: %s", e)

        # For new alerts, initialize occurrence tracking
        now_iso = iso_now()
        if "occurrences" not in metadata:
            metadata.setdefault("occurrences", 1)
        metadata.setdefault("first_seen", now_iso)
        metadata["last_seen"] = now_iso

        metadata_json = json.dumps(metadata) if metadata else None

        # Build dedupe key (explicit key takes precedence)
        if dedupe:
            if dedupe_key:
                _key = f"alert:{dedupe_key}"
            else:
                meta_key = ""
                try:
                    if metadata and isinstance(metadata, dict):
                        meta_key = str(metadata.get("dedup_key", ""))
                except Exception:
                    meta_key = ""
                _key = f"alert:{alert_type}:{source_type or ''}:{source_id or ''}:{meta_key}"

            # Check cache for recent identical alert
            # Memory-first fast path: if a dedup_key is provided, check in-memory index
            try:
                if metadata and isinstance(metadata, dict) and metadata.get("dedup_key"):
                    dk = str(metadata.get("dedup_key"))
                    aid = self._alerts_by_dedup.get(dk)
                    if aid:
                        cached = self._get_cached_alert(aid)
                        if cached:
                            try:
                                ts = cached.get("timestamp")
                                existing_dt = None
                                try:
                                    existing_dt = datetime.fromisoformat(ts)
                                except Exception:
                                    from dateutil import parser as _parser
                                    existing_dt = _parser.parse(ts)

                                if (utc_now() - existing_dt).total_seconds() <= float(self._dedupe_db_seconds):
                                    existing_id = int(aid)
                                    existing_meta = cached.get("metadata") or {}
                                    existing_meta["occurrences"] = int(existing_meta.get("occurrences", 1)) + 1
                                    existing_meta["last_seen"] = now_iso
                                    # update cache and persist
                                    try:
                                        cached["metadata"] = existing_meta
                                        self._alerts[existing_id] = cached
                                    except Exception:
                                        logger.debug("Failed updating in-memory cached metadata")
                                    try:
                                        self.alert_repo.update_metadata(existing_id, json.dumps(existing_meta))
                                    except Exception:
                                        logger.debug("Failed persisting dedupe metadata update for existing alert %s", existing_id)
                                try:
                                    # refresh cache from DB to ensure complete row
                                    r = self.alert_repo.get_by_id(existing_id)
                                    if r:
                                        self._cache_alert_row(dict(r))
                                except Exception:
                                    # Non-fatal cache refresh error; continue to return existing id
                                    logger.debug("Cache refresh after dedupe hit failed")
                                # Ensure dedupe cache is set and return the existing alert id
                                try:
                                    self._dedupe_cache.set(_key, existing_id)
                                except Exception:
                                    logger.debug("Failed setting dedupe cache for key %s", _key)
                                return existing_id
                            except Exception:
                                logger.debug("Error handling in-memory dedupe hit")
            except Exception as e:
                logger.debug("In-memory dedupe fast-path failed: %s", e)

            try:
                existing = self._dedupe_cache.get(_key)
                if existing:
                    # Suppress duplicate alert within dedupe window
                    logger.debug(f"Suppressed duplicate alert (dedupe key)={_key}")
                    # If DB-backed dedupe is enabled, let the DB dedupe path handle
                    # incrementing occurrences. Invalidate the in-memory cache so the
                    # DB query runs below and updates metadata atomically.
                    try:
                        if self._dedupe_db_enabled:
                            try:
                                self._dedupe_cache.invalidate(_key)
                            except Exception as e:
                                logger.debug("Failed invalidating dedupe cache key %s: %s", _key, e)
                            # Do not return here; allow DB dedupe block to run
                        else:
                            # No DB dedupe available; try to increment occurrences locally via repository
                            try:
                                # Update cached entry if present and persist
                                cached = self._get_cached_alert(int(existing))
                                if cached:
                                    existing_meta = cached.get("metadata") or {}
                                else:
                                    existing_meta = {}
                                existing_meta["occurrences"] = int(existing_meta.get("occurrences", 1)) + 1
                                existing_meta["last_seen"] = now_iso
                                try:
                                    if cached:
                                        cached["metadata"] = existing_meta
                                        self._alerts[int(existing)] = cached
                                except Exception as e:
                                    logger.debug("Failed updating in-memory metadata for dedupe hit: %s", e)
                                try:
                                    self.alert_repo.update_metadata(int(existing), json.dumps(existing_meta))
                                except Exception as e:
                                    logger.debug("Failed persisting dedupe metadata update: %s", e)
                                try:
                                    r = self.alert_repo.get_by_id(int(existing))
                                    if r:
                                        self._cache_alert_row(dict(r))
                                except Exception as e:
                                    logger.debug("Failed refreshing cache after dedupe metadata update: %s", e)
                            except Exception:
                                logger.debug("Failed handling in-memory dedupe hit (repo path)")
                            return existing
                    except Exception:
                        logger.debug("Failed handling in-memory dedupe hit")
            except Exception as e:
                # Cache errors should not block alert creation
                logger.debug("Error checking dedupe cache for key %s: %s", _key, e)

            # DB-backed dedupe (optional) - check for recent similar alert across processes
            if self._dedupe_db_enabled:
                try:
                    cand = self.alert_repo.find_latest(alert_type, source_type, source_id, dedup_key=metadata.get("dedup_key") if metadata and isinstance(metadata, dict) else None)
                    if cand and cand.get("alert_id"):
                        try:
                            ts = cand["timestamp"]
                            existing_dt = None
                            try:
                                existing_dt = datetime.fromisoformat(ts)
                            except Exception:
                                from dateutil import parser as _parser
                                existing_dt = _parser.parse(ts)

                            age_seconds = (utc_now() - existing_dt).total_seconds()
                            if age_seconds <= float(self._dedupe_db_seconds):
                                existing_id = int(cand["alert_id"])
                                logger.debug(f"Found recent alert in DB, updating occurrences for {existing_id}")
                                existing_meta = {}
                                if cand.get("metadata"):
                                    try:
                                        existing_meta = json.loads(cand["metadata"]) or {}
                                    except Exception as e:
                                        logger.debug("Failed parsing existing alert metadata: %s", e)
                                        existing_meta = {}
                                existing_meta["occurrences"] = int(existing_meta.get("occurrences", 1)) + 1
                                existing_meta["last_seen"] = now_iso
                                try:
                                    self.alert_repo.update_metadata(existing_id, json.dumps(existing_meta))
                                except Exception as upd_err:
                                    logger.debug(f"Failed to update existing alert metadata: %s", upd_err)
                                try:
                                    self._dedupe_cache.set(_key, existing_id)
                                except Exception as e:
                                    logger.debug("Failed setting dedupe cache after DB dedupe hit: %s", e)
                                return existing_id
                        except Exception as parse_err:
                            logger.debug(f"Failed to parse alert timestamp for dedupe: %s", parse_err)
                except Exception as db_dedupe_error:
                    logger.debug(f"DB dedupe check failed: %s", db_dedupe_error)

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
            logger.info(f"Alert created: [{severity}] {title}")
            # Store in dedupe cache to prevent duplicates for TTL window
            if dedupe:
                try:
                    self._dedupe_cache.set(_key, alert_id)
                except Exception as e:
                    logger.debug("Failed setting dedupe cache after create: %s", e)
            # Cache the full row in-memory to avoid future DB reads
            try:
                r = self.alert_repo.get_by_id(alert_id)
                if r:
                    self._cache_alert_row(dict(r))
            except Exception as e:
                logger.debug("Failed caching alert row after create: %s", e)
            return alert_id
        except Exception as e:
            logger.error(f"Failed to create alert: {e}")
            raise

    def get_active_alerts(
        self,
        severity: Optional[str] = None,
        unit_id: Optional[int] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
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
            results: List[Dict[str, Any]] = []
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
                    except Exception:
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
                try:
                    self._cache_alert_row(alert)
                except Exception:
                    pass
            return alerts
        except Exception as e:
            logger.error(f"Failed to retrieve active alerts: {e}")
            return []

    def acknowledge_alert(self, alert_id: int, user_id: Optional[int] = None) -> bool:
        """Acknowledge an alert.
        
        Args:
            alert_id: ID of the alert to acknowledge
            user_id: ID of the user acknowledging the alert
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            return self.alert_repo.acknowledge(alert_id, user_id)
        except Exception as e:
            logger.error(f"Failed to acknowledge alert: {e}")
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
            if success:
                # Invalidate cache for this alert
                if alert_id in self._alerts:
                    self._alerts[alert_id]["resolved"] = True
                    self._alerts[alert_id]["resolved_at"] = iso_now()
            return success
        except Exception as e:
            logger.error(f"Failed to resolve alert: {e}")
            return False

    def get_alert_summary(self) -> Dict[str, Any]:
        """Get summary statistics of alerts.
        
        Returns:
            Dictionary containing alert counts by severity and status
        """
        try:
            return self.alert_repo.summary()
        except Exception as e:
            logger.error(f"Failed to get alert summary: {e}")
            return {
                "total_active": 0,
                "total_resolved": 0,
                "active_by_severity": {"info": 0, "warning": 0, "critical": 0},
            }

    def purge_old_alerts(self, retention_days: int = 30, resolved_only: bool = True) -> Dict[str, Any]:
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
            logger.info(f"Purged {deleted} alert(s) older than {retention_days} day(s) (resolved_only={resolved_only})")
            return {"success": True, "deleted_rows": deleted}
        except Exception as e:
            logger.error(f"Failed to purge old alerts: {e}")
            return {"success": False, "error": str(e)}