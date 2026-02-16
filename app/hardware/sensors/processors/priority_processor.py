# app/hardware/sensors/processors/priority_processor.py
"""
Priority Processor
==================

Owns dashboard sensor selection logic and state.

Responsible for:
- Tracking which sensor is "primary" for each metric per unit
- Handling stale sensor detection
- Supporting manual priority overrides
- Building DashboardSnapshotPayload with best available readings

Design:
- Does NOT own SensorManager; uses injected resolver
- Thread-safe via explicit resolver parameter (no method assignment)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Callable

from app.hardware.sensors.processors.utils import (
    DASHBOARD_METRICS,
    UNIT_MAP,
    coerce_float,
    get_meta_val,
    is_environment_sensor,
    is_meta_key,
    is_soil_sensor,
    to_wire_status,
)
from app.schemas.events import DashboardSnapshotPayload

# Psychrometric helpers:
# - calculate_vpd_kpa / calculate_dew_point_c use a Magnus–Tetens-style saturation
#   vapor pressure approximation, typically accurate for roughly -45°C to 60°C.
# - calculate_heat_index_c implements the NOAA/NWS Rothfusz regression, which is
#   intended primarily for "hot and humid" conditions (≈ ≥26–27°C and RH ≥40–50%).
# For full derivations, coefficients, and caveats, see app.utils.psychrometrics.
from app.utils.psychrometrics import (
    compute_derived_metrics,
)
from app.utils.time import utc_now

logger = logging.getLogger(__name__)

# Protocol values accepted by DashboardSnapshotPayload schemas (lowercase).
ALLOWED_PROTOCOLS = {
    "zigbee2mqtt",
    "zigbee",
    "mqtt",
    "esp32",
    "gpio",
    "i2c",
    "adc",
    "spi",
    "onewire",
    "http",
    "modbus",
    "wireless",
}


def _normalize_protocol(value: Any) -> str | None:
    """Normalize protocol values to lowercase schema-compatible strings."""
    if value is None:
        return None
    text = str(value).strip().lower()
    if not text:
        return None
    if text in ALLOWED_PROTOCOLS:
        return text
    return "other"


# Type alias for sensor resolver function
SensorResolver = Callable[[int], Any | None]


@dataclass
class ManualPriority:
    """Manual priority override configuration for a sensor."""

    sensor_id: int
    priority: int  # lower = better
    reading_types: set[str]  # empty means "all metrics"


class PriorityProcessor:
    """
    Owns dashboard selection logic and state.

    Input: SensorEntity + SensorReading
    Output: DashboardSnapshotPayload for the unit (or None if nothing to emit)

    Thread Safety:
    - The resolver is passed as a parameter to avoid method assignment.
    - State (last_seen, last_readings, etc.) should only be modified
      from a single thread (the MQTT handler thread).
    """

    # Maximum number of sensors tracked per unit before cleanup is triggered
    MAX_SENSORS_PER_UNIT = 50

    # Configuration bounds
    MIN_STALE_SECONDS = 10
    MAX_STALE_SECONDS = 3600
    MIN_TRACKED_SENSORS = 10
    MAX_TRACKED_SENSORS = 10000

    def __init__(self, *, stale_seconds: int = 180, max_tracked_sensors: int = 500):
        """
        Initialize the priority processor.

        Args:
            stale_seconds: Seconds after which a sensor is considered stale (10-3600)
            max_tracked_sensors: Maximum total sensors to track before evicting stale entries (10-10000)

        Raises:
            ValueError: If configuration values are out of valid range
        """
        # Validate configuration
        stale_s = int(stale_seconds)
        max_tracked = int(max_tracked_sensors)

        if not (self.MIN_STALE_SECONDS <= stale_s <= self.MAX_STALE_SECONDS):
            raise ValueError(
                f"stale_seconds must be between {self.MIN_STALE_SECONDS} and {self.MAX_STALE_SECONDS}, got {stale_s}"
            )
        if not (self.MIN_TRACKED_SENSORS <= max_tracked <= self.MAX_TRACKED_SENSORS):
            raise ValueError(
                f"max_tracked_sensors must be between {self.MIN_TRACKED_SENSORS} and {self.MAX_TRACKED_SENSORS}, got {max_tracked}"
            )

        self.stale_seconds = stale_s
        self._max_tracked = max_tracked

        # Per-sensor tracking
        self.last_seen: dict[int, datetime] = {}
        self.last_readings: dict[int, Any] = {}  # sensor_id -> SensorReading

        # Per-unit index: unit_id -> set of sensor_ids
        # Improves lookup performance for soil_moisture averaging and candidate selection
        self._unit_sensors: dict[int, set[int]] = {}

        # Per-unit per-metric primary sensor selection
        # Key: (unit_id, metric) -> sensor_id
        self.primary_sensors: dict[tuple[int, str], int] = {}

        # Per-unit per-metric previous values for trend computation
        # Key: (unit_id, metric) -> previous_value
        self._previous_values: dict[tuple[int, str], float] = {}

        # Manual priority overrides
        self.manual: dict[int, ManualPriority] = {}

        # Snapshot cache for REST endpoints (avoids recomputation)
        # Key: unit_id -> (snapshot, timestamp)
        self._snapshot_cache: dict[int, tuple[DashboardSnapshotPayload, datetime]] = {}
        self._snapshot_cache_ttl_seconds: float = self.MIN_STALE_SECONDS  # Cache TTL for REST endpoints

        # Observability counters
        self._stats = {
            "ingest_count": 0,
            "primary_changes": 0,
            "evictions": 0,
            "cache_hits": 0,
            "cache_misses": 0,
        }

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    def set_manual_priority(self, sensor_id: int, priority: int, reading_types: set[str] | None = None) -> None:
        """
        Set manual priority override for a sensor.

        Args:
            sensor_id: The sensor ID
            priority: Priority value (lower = higher priority)
            reading_types: Set of metrics this priority applies to (empty = all)
        """
        # Normalize reading_types: empty set means "all metrics"
        reading_types_set = set(reading_types or set())
        self.manual[int(sensor_id)] = ManualPriority(
            sensor_id=int(sensor_id),
            priority=int(priority),
            reading_types=reading_types_set,
        )
        logger.debug(
            "Manual priority set: sensor_id=%s priority=%s reading_types=%s", sensor_id, priority, reading_types_set
        )

        # Clear affected primaries so they recompute. An empty `reading_types_set`
        # is documented to mean "all metrics", so clear primaries for all
        # dashboard metrics in that case.
        if reading_types_set:
            metrics_to_clear = reading_types_set
        else:
            metrics_to_clear = set(DASHBOARD_METRICS)

        for metric in metrics_to_clear:
            keys_to_remove = [k for k in list(self.primary_sensors.keys()) if k[1] == metric]
            for key in keys_to_remove:
                self.primary_sensors.pop(key, None)

    def clear_manual_priority(self, sensor_id: int) -> None:
        """Remove manual priority override for a sensor."""
        self.manual.pop(int(sensor_id), None)
        logger.debug("Manual priority cleared: sensor_id=%s", sensor_id)

    def ingest(
        self, *, sensor: Any, reading: Any, resolve_sensor: SensorResolver | None = None
    ) -> DashboardSnapshotPayload | None:
        """
        Update selection state and return a fresh dashboard snapshot.

        Args:
            sensor: The SensorEntity
            reading: The SensorReading
            resolve_sensor: Optional function to resolve sensor_id -> SensorEntity

        Returns:
            DashboardSnapshotPayload for the unit, or None if no metrics available
        """
        unit_id = int(getattr(reading, "unit_id", 0) or 0)
        sensor_id = int(getattr(sensor, "id", 0) or 0)

        if unit_id <= 0 or sensor_id <= 0:
            return None

        now = utc_now()
        self.last_seen[sensor_id] = now
        self.last_readings[sensor_id] = reading

        # Maintain per-unit sensor index for efficient lookups
        if unit_id not in self._unit_sensors:
            self._unit_sensors[unit_id] = set()
        self._unit_sensors[unit_id].add(sensor_id)

        # Periodic cleanup to prevent memory growth
        if len(self.last_readings) > self._max_tracked:
            self._evict_stale_entries()

        logger.debug(
            "PriorityProcessor.ingest: unit_id=%s sensor_id=%s metrics=%s",
            unit_id,
            sensor_id,
            list((getattr(reading, "data", {}) or {}).keys()),
        )
        self._consider_primary(sensor=sensor, reading=reading, resolve_sensor=resolve_sensor)
        snapshot = self._build_snapshot(unit_id=unit_id, resolve_sensor=resolve_sensor)

        # Update cache and stats
        self._stats["ingest_count"] += 1
        if snapshot:
            self._snapshot_cache[unit_id] = (snapshot, now)

        logger.debug(
            "PriorityProcessor.ingest -> snapshot metrics=%s", list(snapshot.metrics.keys()) if snapshot else None
        )
        return snapshot

    def build_dashboard_snapshot(
        self, sensor: Any, reading: Any, resolve_sensor: SensorResolver | None = None
    ) -> DashboardSnapshotPayload | None:
        """
        Alternative API matching IPriorityProcessor protocol.

        Calls ingest() internally.
        """
        return self.ingest(sensor=sensor, reading=reading, resolve_sensor=resolve_sensor)

    def build_snapshot_for_unit(
        self,
        unit_id: int,
        resolve_sensor: SensorResolver | None = None,
        use_cache: bool = True,
    ) -> DashboardSnapshotPayload | None:
        """Build a dashboard snapshot for a unit from current internal state.

        Intended for REST endpoints that need the current primary metrics without
        waiting for a new ingest() call.

        Args:
            unit_id: The unit ID to build snapshot for
            resolve_sensor: Optional function to resolve sensor_id -> SensorEntity
            use_cache: If True, return cached snapshot if fresh (within TTL)
        """
        try:
            uid = int(unit_id)
        except Exception:
            return None
        if uid <= 0:
            return None

        # Check cache first (if enabled)
        if use_cache:
            cached = self._snapshot_cache.get(uid)
            if cached:
                snapshot, cached_at = cached
                age = (utc_now() - cached_at).total_seconds()
                if age < self._snapshot_cache_ttl_seconds:
                    self._stats["cache_hits"] += 1
                    return snapshot

        self._stats["cache_misses"] += 1
        snapshot = self._build_snapshot(unit_id=uid, resolve_sensor=resolve_sensor)

        # Update cache
        if snapshot:
            self._snapshot_cache[uid] = (snapshot, utc_now())

        return snapshot

    def get_primary_sensor(self, unit_id: int, metric: str) -> int | None:
        """Get the current primary sensor ID for a unit/metric pair."""
        return self.primary_sensors.get((unit_id, metric))

    def is_primary_metric(self, sensor: Any, metric: str) -> bool:
        """Return True if the sensor declares the metric as primary."""
        try:
            return self._is_primary_metric(sensor, metric)
        except Exception:
            return False

    def get_sensor_last_seen(self, sensor_id: int) -> datetime | None:
        """Get when a sensor was last seen."""
        return self.last_seen.get(sensor_id)

    def get_stats(self) -> dict[str, Any]:
        """Get observability statistics for monitoring.

        Returns:
            Dict with counters for ingest_count, primary_changes, evictions,
            cache_hits, cache_misses, and current tracking sizes.
        """
        return {
            **self._stats,
            "tracked_sensors": len(self.last_readings),
            "tracked_units": len(self._unit_sensors),
            "primary_selections": len(self.primary_sensors),
            "manual_overrides": len(self.manual),
            "cached_snapshots": len(self._snapshot_cache),
        }

    def clear_cache(self) -> None:
        """Clear the snapshot cache. Useful after manual priority changes."""
        self._snapshot_cache.clear()

    # -------------------------------------------------------------------------
    # Trend Computation
    # -------------------------------------------------------------------------

    # Threshold for considering a value "stable" (no meaningful change)
    TREND_STABLE_THRESHOLD = 0.1  # 0.1 units (e.g., 0.1°C, 0.1%, 0.1 kPa)

    def _compute_trend(
        self,
        unit_id: int,
        metric: str,
        current_value: float,
    ) -> tuple[str, float | None]:
        """
        Compute the trend direction and delta for a metric.

        Compares current value with the previous value stored for this unit/metric.
        Updates the stored previous value after computation.

        Args:
            unit_id: Growth unit ID
            metric: Metric name (e.g., "temperature")
            current_value: Current metric value

        Returns:
            Tuple of (trend_direction, trend_delta) where:
            - trend_direction: "rising", "falling", "stable", or "unknown"
            - trend_delta: absolute change from previous, or None if unknown
        """
        key = (unit_id, metric)
        previous = self._previous_values.get(key)

        # Store current as next "previous"
        self._previous_values[key] = current_value

        if previous is None:
            return ("unknown", None)

        delta = current_value - previous
        abs_delta = abs(delta)

        if abs_delta <= self.TREND_STABLE_THRESHOLD:
            return ("stable", round(delta, 3))
        elif delta > 0:
            return ("rising", round(delta, 3))
        else:
            return ("falling", round(delta, 3))

    # -------------------------------------------------------------------------
    # Internal Methods
    # -------------------------------------------------------------------------

    def _is_stale(self, sensor_id: int) -> bool:
        """Check if a sensor is stale (no recent readings)."""
        last = self.last_seen.get(sensor_id)
        if not last:
            return True
        return (utc_now() - last).total_seconds() > self.stale_seconds

    def _get_metric_value(self, data: dict[str, Any], metric: str) -> float | None:
        """Extract a metric value from already-standardized data."""
        val = data.get(metric)
        if val is None:
            return None
        return coerce_float(val)

    def _evict_stale_entries(self) -> None:
        """Remove stale sensors from tracking to prevent memory growth.

        Called periodically when tracking exceeds max_tracked_sensors threshold.
        Uses a generous grace period (2x stale_seconds) to avoid thrashing.
        """
        eviction_threshold = self.stale_seconds * 2
        now = utc_now()
        stale_ids: list[int] = []

        for sensor_id, last in self.last_seen.items():
            age = (now - last).total_seconds()
            if age <= eviction_threshold:
                continue

            # Keep low-frequency sensors longer (soil moisture, light).
            # These may report every 5-10 minutes, so extend their lifetime.
            reading = self.last_readings.get(sensor_id)
            data = getattr(reading, "data", None) or {}
            if age <= self.MAX_STALE_SECONDS:
                if "soil_moisture" in data or "lux" in data:
                    continue

            stale_ids.append(sensor_id)

        for sensor_id in stale_ids:
            self.last_seen.pop(sensor_id, None)
            self.last_readings.pop(sensor_id, None)
            self.manual.pop(sensor_id, None)

            # Remove from per-unit index
            for unit_set in self._unit_sensors.values():
                unit_set.discard(sensor_id)

        # Remove empty unit sets
        empty_units = [uid for uid, sids in self._unit_sensors.items() if not sids]
        for uid in empty_units:
            self._unit_sensors.pop(uid, None)

        # Clear primary sensor entries pointing to evicted sensors
        keys_to_remove = [k for k, sid in self.primary_sensors.items() if sid in stale_ids]
        for key in keys_to_remove:
            self.primary_sensors.pop(key, None)

        # Invalidate cached snapshots for affected units
        affected_units = {uid for uid, _ in keys_to_remove}
        for uid in affected_units:
            self._snapshot_cache.pop(uid, None)

        if stale_ids:
            self._stats["evictions"] += len(stale_ids)
            logger.debug(
                "Evicted %d stale sensors from tracking (threshold=%ds)",
                len(stale_ids),
                eviction_threshold,
            )

    def _manual_priority_for(self, sensor_id: int, metric: str) -> int | None:
        """Get manual priority for a sensor/metric if configured."""
        cfg = self.manual.get(sensor_id)
        if not cfg:
            return None
        if not cfg.reading_types or metric in cfg.reading_types:
            return cfg.priority
        return None

    def _auto_priority(self, sensor: Any, metric: str) -> int:
        """Compute automatic priority based on explicit config with safe fallback.

        Rules:
        - If metric is in sensor's primary_metrics: priority 10 (highest)
        - If sensor has any primary_metrics but not this metric: priority 50
        - If sensor has no primary_metrics configured, apply compatibility fallback:
          - Environment sensors preferred for air metrics (temperature/humidity/pressure/co2/voc/air_quality)
          - Soil/plant sensors preferred for soil_moisture
        """
        primary_metrics = self._primary_metrics_for_sensor(sensor)

        if metric in primary_metrics:
            return 10  # High priority - explicitly configured as primary

        if primary_metrics:
            return 50  # Explicit config exists; this metric is secondary

        # Backward-compatible fallback when no explicit primary_metrics were configured.
        # This preserves expected dashboard behavior for legacy sensor setups.
        air_metrics = {"temperature", "humidity", "pressure", "co2", "voc", "air_quality"}
        if metric in air_metrics:
            return 20 if is_environment_sensor(sensor) else 40
        if metric == "soil_moisture":
            return 20 if is_soil_sensor(sensor) else 40

        return 50

    def _primary_metrics_for_sensor(self, sensor: Any) -> set[str]:
        """Return the set of primary metrics for a sensor.

        The user explicitly configures which metrics each sensor provides as primary.
        No guessing or heuristics - the user's choice is respected.

        Lookup order:
        1) sensor.config.primary_metrics (explicit user configuration)
        2) sensor.config.extra_config["primary_metrics"] (alternative storage)
        3) Empty set (sensor provides secondary metrics only)
        """
        cfg = getattr(sensor, "config", None)
        if cfg is None:
            return set()

        # 1) Check sensor.config.primary_metrics (preferred location)
        pm = getattr(cfg, "primary_metrics", None)
        if isinstance(pm, list) and pm:
            return {str(x).strip().lower() for x in pm if str(x).strip()}

        # 2) Check extra_config["primary_metrics"] (fallback storage)
        extra = getattr(cfg, "extra_config", None)
        if isinstance(extra, dict):
            pm2 = extra.get("primary_metrics")
            if isinstance(pm2, list) and pm2:
                return {str(x).strip().lower() for x in pm2 if str(x).strip()}

        # No primary_metrics configured - sensor provides secondary metrics only
        return set()

    def _is_primary_metric(self, sensor: Any, metric: str) -> bool:
        m = str(metric or "").strip().lower()
        if not m:
            return False
        return m in self._primary_metrics_for_sensor(sensor)

    def _priority_for(self, sensor: Any, metric: str) -> int:
        """Get priority for a sensor/metric (manual override or auto)."""
        sid = int(getattr(sensor, "id", 0) or 0)
        mp = self._manual_priority_for(sid, metric)
        if mp is not None:
            return mp
        return self._auto_priority(sensor, metric)

    def _consider_primary(self, *, sensor: Any, reading: Any, resolve_sensor: SensorResolver | None = None) -> None:
        """Update primary sensor selection based on new reading."""
        unit_id = int(getattr(reading, "unit_id", 0) or 0)
        if unit_id <= 0:
            return

        sensor_id = int(getattr(sensor, "id", 0) or 0)
        data = getattr(reading, "data", None) or {}

        for raw_metric in list(data.keys()):
            metric = str(raw_metric).strip()
            if metric not in DASHBOARD_METRICS:
                continue
            if is_meta_key(metric):
                continue
            if data.get(raw_metric) is None:
                continue

            key = (unit_id, metric)
            current_id = self.primary_sensors.get(key)

            # First sensor for this metric (change from None -> sensor_id)
            if current_id is None:
                if self._is_primary_metric(sensor, metric):
                    self.primary_sensors[key] = sensor_id
                    self._stats["primary_changes"] += 1
                    logger.debug("Primary chosen (first): unit=%s metric=%s sensor=%s", unit_id, metric, sensor_id)
                continue

            # Same sensor, no change needed
            if current_id == sensor_id:
                continue

            # Stale replacement: prefer fresh sensor
            if self._is_stale(current_id) and not self._is_stale(sensor_id):
                self.primary_sensors[key] = sensor_id
                self._stats["primary_changes"] += 1
                logger.debug(
                    "Primary replaced (stale): unit=%s metric=%s old=%s new=%s", unit_id, metric, current_id, sensor_id
                )
                continue

            # Priority replacement
            current_sensor = resolve_sensor(current_id) if resolve_sensor else None
            if not current_sensor:
                self.primary_sensors[key] = sensor_id
                self._stats["primary_changes"] += 1
                logger.debug(
                    "Primary replaced (no current sensor resolved): unit=%s metric=%s old=%s new=%s",
                    unit_id,
                    metric,
                    current_id,
                    sensor_id,
                )
                continue

            # Primary-vs-secondary replacement: a sensor for which this metric is *primary*
            # should win over a sensor that only provides the metric as a secondary reading.
            try:
                new_is_primary = self._is_primary_metric(sensor, metric)
                cur_is_primary = self._is_primary_metric(current_sensor, metric)
            except Exception:
                new_is_primary = False
                cur_is_primary = False

            if new_is_primary and not cur_is_primary:
                self.primary_sensors[key] = sensor_id
                self._stats["primary_changes"] += 1
                logger.debug(
                    "Primary replaced (primary-metric preference): unit=%s metric=%s old=%s new=%s",
                    unit_id,
                    metric,
                    current_id,
                    sensor_id,
                )
                continue

            new_pr = self._priority_for(sensor, metric)
            cur_pr = self._priority_for(current_sensor, metric)
            if new_pr < cur_pr:
                self.primary_sensors[key] = sensor_id
                self._stats["primary_changes"] += 1
                logger.debug(
                    "Primary replaced (priority): unit=%s metric=%s old=%s(old_pr=%s) new=%s(new_pr=%s)",
                    unit_id,
                    metric,
                    current_id,
                    cur_pr,
                    sensor_id,
                    new_pr,
                )

    def _build_snapshot(
        self, *, unit_id: int, resolve_sensor: SensorResolver | None = None
    ) -> DashboardSnapshotPayload | None:
        """Build dashboard snapshot with best available readings for each metric."""
        metrics: dict[str, Any] = {}

        for metric in sorted(DASHBOARD_METRICS):
            if metric == "soil_moisture":
                self._add_soil_moisture_aggregate(unit_id, metrics)
            elif metric == "lux":
                self._add_lux_metric(unit_id, metrics, resolve_sensor)
            else:
                self._add_standard_metric(unit_id, metric, metrics, resolve_sensor)

        # Compute derived metrics (VPD, etc.) from best T/H
        self._fill_derived_metrics(unit_id, metrics)

        if not metrics:
            return None

        return DashboardSnapshotPayload(
            schema_version=1,
            unit_id=int(unit_id),
            timestamp=utc_now().isoformat(),
            metrics=metrics,
        )

    def _add_soil_moisture_aggregate(self, unit_id: int, metrics: dict[str, Any]) -> None:
        """Add aggregated soil moisture metric to metrics dict.

        Handles both simple values and nested lists from multi-channel sensors.
        """
        values: list[float] = []
        unit_sensor_ids = self._unit_sensors.get(unit_id, set())

        for sid in unit_sensor_ids:
            last = self.last_seen.get(sid)
            if not last or (utc_now() - last).total_seconds() > self.MAX_STALE_SECONDS:
                continue

            reading = self.last_readings.get(sid)
            data = getattr(reading, "data", None) or {}

            # 1. Check for flat value
            val = coerce_float(data.get("soil_moisture"))
            if val is not None:
                values.append(float(val))
                continue

            # 2. Check for nested list (e.g. ESP32-GrowTent v3.0+)
            raw_moisture = data.get("soil_moisture")
            if isinstance(raw_moisture, list):
                for item in raw_moisture:
                    if isinstance(item, dict):
                        # Extract percentage from dict
                        pv = item.get("moisture_percentage") or item.get("value")
                        f_pv = coerce_float(pv)
                        if f_pv is not None:
                            values.append(f_pv)
                    else:
                        f_v = coerce_float(item)
                        if f_v is not None:
                            values.append(f_v)

        if not values:
            return

        avg = sum(values) / len(values)
        trend_dir, trend_delta = self._compute_trend(unit_id, "soil_moisture", avg)

        metrics["soil_moisture"] = {
            "value": round(avg, 1),
            "unit": UNIT_MAP.get("soil_moisture", "%"),
            "trend": trend_dir,
            "trend_delta": trend_delta,
            "source": {
                "sensor_id": 0,
                "sensor_name": "Soil Moisture (avg)",
                "sensor_type": "aggregate",
                "protocol": None,
                "battery": None,
                "power_source": "unknown",
                "linkquality": None,
                "quality_score": None,
                "status": "success",
                "is_anomaly": False,
            },
        }

    def _add_lux_metric(self, unit_id: int, metrics: dict[str, Any], resolve_sensor: SensorResolver | None) -> None:
        """Add lux metric with extended freshness window."""
        sid = self.primary_sensors.get((unit_id, "lux"))

        # Fallback to finding any lux sensor if primary not set
        if not sid:
            unit_sensor_ids = self._unit_sensors.get(unit_id, set())
            for candidate_sid in unit_sensor_ids:
                data = getattr(self.last_readings.get(candidate_sid), "data", None) or {}
                if "lux" in data:
                    sid = candidate_sid
                    self.primary_sensors[(unit_id, "lux")] = sid
                    break

        if not sid:
            return

        last = self.last_seen.get(sid)
        reading = self.last_readings.get(sid)
        age = (utc_now() - last).total_seconds() if last else float("inf")

        # Use generous MAX_STALE_SECONDS for light sensors (infrequent reporting)
        if not reading or age > self.MAX_STALE_SECONDS:
            return

        data = getattr(reading, "data", None) or {}
        val = self._get_metric_value(data, "lux")
        if val is None:
            return

        sensor = resolve_sensor(sid) if resolve_sensor else None
        if not sensor:
            return

        battery = coerce_float(data.get("battery"))
        linkquality = coerce_float(data.get("linkquality"))
        protocol = _normalize_protocol(get_meta_val(sensor, "protocol", None))
        trend_dir, trend_delta = self._compute_trend(unit_id, "lux", float(val))

        metrics["lux"] = {
            "value": float(val),
            "unit": UNIT_MAP.get("lux", "lux"),
            "trend": trend_dir,
            "trend_delta": trend_delta,
            "source": {
                "sensor_id": sid,
                "sensor_name": getattr(sensor, "name", None),
                "sensor_type": get_meta_val(sensor, "sensor_type"),
                "protocol": protocol,
                "battery": int(battery) if battery is not None else None,
                "power_source": get_meta_val(sensor, "power_source"),
                "linkquality": int(linkquality) if linkquality is not None else None,
                "quality_score": None,
                "status": to_wire_status(getattr(reading, "status", None)),
                "is_anomaly": False,
            },
        }

    def _add_standard_metric(
        self, unit_id: int, metric: str, metrics: dict[str, Any], resolve_sensor: SensorResolver | None
    ) -> None:
        """Add a standard metric using best available sensor."""
        sid = self._select_best_sensor(unit_id=unit_id, metric=metric, resolve_sensor=resolve_sensor)
        if not sid or self._is_stale(sid):
            return

        reading = self.last_readings.get(sid)
        if not reading:
            return

        data = getattr(reading, "data", None) or {}
        val = self._get_metric_value(data, metric)
        if val is None:
            return

        sensor = resolve_sensor(sid) if resolve_sensor else None
        if not sensor:
            return

        battery = coerce_float(data.get("battery"))
        linkquality = coerce_float(data.get("linkquality"))
        protocol = _normalize_protocol(get_meta_val(sensor, "protocol", None))
        trend_dir, trend_delta = self._compute_trend(unit_id, metric, float(val))

        metrics[metric] = {
            "value": float(val),
            "unit": UNIT_MAP.get(metric, ""),
            "trend": trend_dir,
            "trend_delta": trend_delta,
            "source": {
                "sensor_id": sid,
                "sensor_name": getattr(sensor, "name", None),
                "sensor_type": get_meta_val(sensor, "sensor_type"),
                "protocol": protocol,
                "battery": int(battery) if battery is not None else None,
                "power_source": get_meta_val(sensor, "power_source"),
                "linkquality": int(linkquality) if linkquality is not None else None,
                "quality_score": getattr(reading, "quality_score", None),
                "status": to_wire_status(getattr(reading, "status", None)),
                "is_anomaly": bool(getattr(reading, "is_anomaly", False)),
            },
        }

    def _select_best_sensor(
        self, *, unit_id: int, metric: str, resolve_sensor: SensorResolver | None = None
    ) -> int | None:
        """Select the best sensor for a unit/metric pair."""
        # Check current primary first
        primary = self.primary_sensors.get((unit_id, metric))
        if primary and not self._is_stale(primary):
            reading = self.last_readings.get(primary)
            if reading and self._get_metric_value(getattr(reading, "data", None) or {}, metric) is not None:
                return primary

        # Find all valid candidates using per-unit index for efficiency
        candidates: list[int] = []
        unit_sensor_ids = self._unit_sensors.get(unit_id, set())
        for sid in unit_sensor_ids:
            if self._is_stale(sid):
                continue
            reading = self.last_readings.get(sid)
            if not reading:
                continue
            if self._get_metric_value(getattr(reading, "data", None) or {}, metric) is None:
                continue
            candidates.append(sid)

        if not candidates:
            return None

        # Prefer sensors for which the metric is primary, then fallback to secondary.
        # Resolve sensors once and reuse — avoids repeated (potentially expensive)
        # resolver calls during sorting and primary checks.
        resolved_cache: dict[int, Any | None] = {}
        primary_candidates: list[int] = []
        secondary_candidates: list[int] = []
        for sid in candidates:
            sensor = resolved_cache.get(sid)
            if sensor is None and resolve_sensor:
                sensor = resolve_sensor(sid)
                resolved_cache[sid] = sensor

            if sensor is not None and self._is_primary_metric(sensor, metric):
                primary_candidates.append(sid)
            else:
                secondary_candidates.append(sid)

        preferred = primary_candidates or secondary_candidates

        # Sort by priority, then age, then quality
        ref_now = utc_now()

        def sort_key(sid: int) -> tuple[int, float, float]:
            sensor = resolved_cache.get(sid)
            pr = self._priority_for(sensor, metric) if sensor else 30
            last = self.last_seen.get(sid) or datetime.fromtimestamp(0, tz=UTC)
            # Use one consistent reference time for all candidates to keep ordering stable.
            age = (ref_now - last).total_seconds()
            reading = self.last_readings.get(sid)
            qv = float(getattr(reading, "quality_score", 0.0) or 0.0)
            return (pr, age, -qv)

        best = sorted(preferred, key=sort_key)[0]
        self.primary_sensors[(unit_id, metric)] = best
        return best

    def _fill_derived_metrics(self, unit_id: int, metrics: dict[str, Any]) -> None:
        """Compute derived metrics (VPD, dew_point, heat_index) if missing.

        Requires temperature and humidity to be present in metrics.
        Derived values are computed and added in-place with trend information.

        Args:
            unit_id: Growth unit ID for trend tracking
            metrics: Metrics dict to update in-place
        """
        temp_data = metrics.get("temperature")
        humidity_data = metrics.get("humidity")

        if not temp_data or not humidity_data:
            return

        temp = temp_data.get("value") if isinstance(temp_data, dict) else None
        humidity = humidity_data.get("value") if isinstance(humidity_data, dict) else None

        if temp is None or humidity is None:
            return

        # Compute all derived metrics at once
        derived = compute_derived_metrics(float(temp), float(humidity))

        # Build base source info for derived metrics
        derived_source = {
            "sensor_id": 0,
            "sensor_name": "Computed",
            "sensor_type": "derived",
            "protocol": None,
            "battery": None,
            "power_source": "unknown",
            "linkquality": None,
            "quality_score": None,
            "status": "success",
            "is_anomaly": False,
        }

        # Map internal keys to dashboard keys
        mapping = {
            "vpd_kpa": ("vpd", "kPa"),
            "dew_point_c": ("dew_point", "°C"),
            "heat_index_c": ("heat_index", "°C"),
        }

        for internal_key, (dash_key, unit) in mapping.items():
            if dash_key not in metrics:
                val = derived.get(internal_key)
                if val is not None:
                    trend_dir, trend_delta = self._compute_trend(unit_id, dash_key, val)
                    metrics[dash_key] = {
                        "value": val,
                        "unit": UNIT_MAP.get(dash_key, unit),
                        "trend": trend_dir,
                        "trend_delta": trend_delta,
                        "source": derived_source.copy(),
                    }
