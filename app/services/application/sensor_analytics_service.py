"""
Sensor Analytics Service
=========================

Extracted from AnalyticsService (Sprint 4 – god-service split).

Handles sensor data retrieval, caching, chart formatting,
time-series aggregation, photoperiod enrichment, and plant readings.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

from app.constants import AnalysisWindows, DataLimits
from app.domain.photoperiod import Photoperiod
from app.services.application.threshold_service import ThresholdService
from app.services.hardware.scheduling_service import SchedulingService
from app.utils.cache import CacheRegistry, TTLCache
from app.utils.time import coerce_datetime, utc_now
from infrastructure.database.repositories.analytics import AnalyticsRepository
from infrastructure.database.repositories.devices import DeviceRepository
from infrastructure.database.repositories.growth import GrowthRepository

logger = logging.getLogger(__name__)


class SensorAnalyticsService:
    """Sensor data access, caching, formatting, enrichment, and plant readings."""

    def __init__(
        self,
        repository: AnalyticsRepository,
        device_repository: DeviceRepository | None = None,
        growth_repository: GrowthRepository | None = None,
        threshold_service: "ThresholdService" | None = None,
        scheduling_service: "SchedulingService" | None = None,
        *,
        cache_name_prefix: str = "analytics_service",
    ):
        self.repository = repository
        self.device_repository = device_repository
        self.device_repo = device_repository
        self.growth_repo = growth_repository
        self.threshold_service = threshold_service
        self.scheduling_service = scheduling_service
        self.logger = logger

        # Caches
        self._latest_reading_cache = TTLCache(enabled=True, ttl_seconds=5, maxsize=32)
        self._history_cache = TTLCache(enabled=True, ttl_seconds=30, maxsize=128)

        cache_registry = CacheRegistry.get_instance()
        try:
            cache_registry.register(f"{cache_name_prefix}.latest_readings", self._latest_reading_cache)
            cache_registry.register(f"{cache_name_prefix}.history", self._history_cache)
        except ValueError:
            logger.debug("Analytics caches already registered")

    # ── Latest Readings ──────────────────────────────────────────────

    def get_latest_sensor_reading(self, unit_id: int | None = None) -> dict[str, Any] | None:
        """Get the most recent sensor reading, optionally filtered by unit. Cached 5s."""
        cache_key = f"latest_sensor_{unit_id}"

        def loader():
            try:
                logger.debug("Fetching latest sensor reading for unit_id=%s", unit_id)
                reading = self.repository.get_latest_sensor_reading(unit_id=unit_id)
                if reading:
                    logger.debug("Found latest sensor reading with timestamp: %s", reading.get("timestamp"))
                else:
                    logger.debug("No sensor readings found")
                return reading
            except Exception as e:
                logger.error("Error fetching latest sensor reading: %s", e)
                raise

        return self._latest_reading_cache.get(cache_key, loader)

    def get_latest_energy_reading(self) -> dict[str, Any] | None:
        """Get the most recent energy reading."""
        try:
            logger.debug("Fetching latest energy reading")
            reading = self.repository.get_latest_energy_reading()
            if reading:
                logger.debug("Found latest energy reading with timestamp: %s", reading.get("timestamp"))
            else:
                logger.debug("No energy readings found")
            return reading
        except Exception as e:
            logger.error("Error fetching latest energy reading: %s", e)
            raise

    # ── Sensor History ───────────────────────────────────────────────

    def fetch_sensor_history(
        self,
        start_datetime: datetime,
        end_datetime: datetime,
        *,
        unit_id: int | None = None,
        sensor_id: int | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch sensor readings within a date range. Cached 30s."""
        cache_key = f"history_{start_datetime.isoformat()}_{end_datetime.isoformat()}_{unit_id}_{sensor_id}_{limit}"

        def loader():
            try:
                if start_datetime >= end_datetime:
                    raise ValueError("Start datetime must be before end datetime")
                logger.debug("Fetching sensor history from %s to %s", start_datetime, end_datetime)
                readings = self.repository.fetch_sensor_history(
                    start_datetime,
                    end_datetime,
                    unit_id=unit_id,
                    sensor_id=sensor_id,
                    limit=limit,
                )
                logger.debug("Retrieved %s sensor readings", len(readings))
                return readings
            except ValueError as e:
                logger.warning("Invalid date range: %s", e)
                raise
            except Exception as e:
                logger.error("Error fetching sensor history: %s", e)
                raise

        return self._history_cache.get(cache_key, loader)

    # ── Enriched History (VPD + Photoperiod) ─────────────────────────

    def get_sensors_history_enriched(
        self,
        start_datetime: datetime,
        end_datetime: datetime,
        *,
        unit_id: int | None = None,
        sensor_id: int | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        """Fetch sensor history with additional analytics (VPD, photoperiod, DIF)."""
        try:
            readings = self.fetch_sensor_history(
                start_datetime, end_datetime, unit_id=unit_id, sensor_id=sensor_id, limit=limit
            )

            photoperiod = None
            if self.scheduling_service and unit_id:
                try:
                    schedules = self.scheduling_service.get_schedules_for_unit(unit_id, device_type="light")
                    if schedules:
                        sched = schedules[0]
                        photoperiod = Photoperiod(
                            day_start=sched.start_time or "06:00",
                            day_end=sched.end_time or "18:00",
                        )
                except Exception as e:
                    self.logger.debug("Failed to get photoperiod from schedule: %s", e)

            enriched = []
            temps: list[float] = []
            humids: list[float] = []
            vpds: list[float] = []

            for r in readings:
                temp = r.get("temperature")
                humid = r.get("humidity")
                r_enriched = dict(r)

                if temp is not None and humid is not None:
                    from app.utils.psychrometrics import calculate_vpd_kpa

                    vpd = calculate_vpd_kpa(temp, humid)
                    r_enriched["vpd"] = round(vpd, 2)
                    vpds.append(vpd)
                    temps.append(temp)
                    humids.append(humid)

                if photoperiod and "timestamp" in r:
                    ts = r["timestamp"]
                    if isinstance(ts, str):
                        ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    r_enriched["is_light"] = photoperiod.is_schedule_day(ts)

                enriched.append(r_enriched)

            summary = {
                "count": len(enriched),
                "avg_temp": round(sum(temps) / len(temps), 2) if temps else 0,
                "avg_humid": round(sum(humids) / len(humids), 2) if humids else 0,
                "avg_vpd": round(sum(vpds) / len(vpds), 2) if vpds else 0,
                "min_temp": min(temps) if temps else 0,
                "max_temp": max(temps) if temps else 0,
            }

            return {"readings": enriched, "summary": summary, "unit_id": unit_id, "timestamp": utc_now().isoformat()}
        except Exception as e:
            self.logger.error("Error enriching sensor history: %s", e, exc_info=True)
            return {"error": str(e)}

    # ── Statistics ───────────────────────────────────────────────────

    def get_sensor_statistics(
        self,
        start_datetime: datetime,
        end_datetime: datetime,
        *,
        unit_id: int | None = None,
        sensor_id: int | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        """Calculate statistics for sensor readings in a date range."""
        try:
            readings = self.fetch_sensor_history(
                start_datetime, end_datetime, unit_id=unit_id, sensor_id=sensor_id, limit=limit
            )
            if not readings:
                return {"count": 0, "start_date": start_datetime.isoformat(), "end_date": end_datetime.isoformat()}

            count = len(readings)
            temperatures = [r.get("temperature") for r in readings if r.get("temperature") is not None]
            humidities = [r.get("humidity") for r in readings if r.get("humidity") is not None]
            soil_moistures = [r.get("soil_moisture") for r in readings if r.get("soil_moisture") is not None]

            stats = {
                "count": count,
                "start_date": start_datetime.isoformat(),
                "end_date": end_datetime.isoformat(),
                "temperature": self._calculate_value_stats(temperatures),
                "humidity": self._calculate_value_stats(humidities),
                "soil_moisture": self._calculate_value_stats(soil_moistures),
            }

            logger.debug("Calculated statistics for %s readings", count)
            return stats

        except Exception as e:
            logger.error("Error calculating sensor statistics: %s", e)
            raise

    # ── Sensor Summaries ─────────────────────────────────────────────

    def get_sensor_summaries_for_unit(
        self,
        unit_id: int,
        start_date: str | None = None,
        end_date: str | None = None,
        sensor_type: str | None = None,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        """Get pre-aggregated sensor summaries for a growth unit."""
        if not self.device_repo:
            logger.warning("DeviceRepository not available — cannot read sensor summaries")
            return []
        try:
            return self.device_repo.get_sensor_summaries_for_unit(
                unit_id, start_date=start_date, end_date=end_date, sensor_type=sensor_type, limit=limit
            )
        except Exception as exc:
            logger.error("Error fetching sensor summaries for unit %s: %s", unit_id, exc)
            return []

    def get_sensor_summary_stats_for_harvest(
        self,
        unit_id: int,
        start_date: str,
        end_date: str,
    ) -> dict[str, Any]:
        """Get aggregated statistics grouped by sensor type for a harvest report."""
        if not self.device_repo:
            logger.warning("DeviceRepository not available — cannot read harvest stats")
            return {}
        try:
            return self.device_repo.get_sensor_summary_stats_for_harvest(unit_id, start_date, end_date)
        except Exception as exc:
            logger.error("Error fetching harvest summary stats for unit %s: %s", unit_id, exc)
            return {}

    # ── Chart Data Formatting ────────────────────────────────────────

    def format_sensor_chart_data(self, readings: list[dict], interval: str | None = None) -> dict[str, Any]:
        """Format sensor readings for chart visualization with optional aggregation."""
        if not readings:
            return {
                "timestamps": [],
                "temperature": [],
                "humidity": [],
                "soil_moisture": [],
                "lux": [],
                "co2": [],
                "voc": [],
            }

        if interval:
            readings = self._aggregate_sensor_readings(readings, interval)

        by_timestamp: dict[str, dict[str, Any]] = {}
        ordered_keys: list[str] = []

        for row in readings:
            raw_ts = row.get("timestamp")
            if raw_ts is None:
                continue
            parsed = coerce_datetime(raw_ts)
            ts_key = parsed.isoformat() if parsed else str(raw_ts)

            if ts_key not in by_timestamp:
                by_timestamp[ts_key] = {
                    "timestamp": ts_key,
                    "temperature": None,
                    "humidity": None,
                    "soil_moisture": None,
                    "lux": None,
                    "co2": None,
                    "voc": None,
                }
                ordered_keys.append(ts_key)

            entry = by_timestamp[ts_key]
            if row.get("temperature") is not None:
                entry["temperature"] = row.get("temperature")
            if row.get("humidity") is not None:
                entry["humidity"] = row.get("humidity")
            if row.get("soil_moisture") is not None:
                entry["soil_moisture"] = row.get("soil_moisture")
            if row.get("lux") is not None:
                entry["lux"] = row.get("lux")
            if row.get("co2") is not None:
                entry["co2"] = row.get("co2")
            if row.get("voc") is not None:
                entry["voc"] = row.get("voc")

        timestamps = [by_timestamp[key]["timestamp"] for key in ordered_keys]
        temperature = [by_timestamp[key]["temperature"] for key in ordered_keys]
        humidity = [by_timestamp[key]["humidity"] for key in ordered_keys]
        soil_moisture = [by_timestamp[key]["soil_moisture"] for key in ordered_keys]
        lux = [by_timestamp[key]["lux"] for key in ordered_keys]
        co2 = [by_timestamp[key]["co2"] for key in ordered_keys]
        voc = [by_timestamp[key]["voc"] for key in ordered_keys]

        return {
            "timestamps": timestamps,
            "temperature": temperature,
            "humidity": humidity,
            "soil_moisture": soil_moisture,
            "lux": lux,
            "co2": co2,
            "voc": voc,
        }

    def _aggregate_sensor_readings(self, readings: list[dict], interval: str) -> list[dict]:
        """Aggregate sensor readings by time interval."""
        if not readings:
            return []

        interval_map = {
            "1min": timedelta(minutes=1),
            "5min": timedelta(minutes=5),
            "15min": timedelta(minutes=15),
            "30min": timedelta(minutes=30),
            "1hour": timedelta(hours=1),
            "6hour": timedelta(hours=6),
            "1day": timedelta(days=1),
        }

        delta = interval_map.get(interval)
        if not delta:
            logger.warning("Unknown interval '%s', skipping aggregation", interval)
            return readings

        buckets: dict[Any, list[dict]] = defaultdict(list)
        for reading in readings:
            timestamp = coerce_datetime(reading.get("timestamp"))
            if not timestamp:
                continue
            epoch = int(timestamp.timestamp())
            bucket_epoch = (epoch // int(delta.total_seconds())) * int(delta.total_seconds())
            bucket_key = datetime.fromtimestamp(bucket_epoch, tz=timestamp.tzinfo)
            buckets[bucket_key].append(reading)

        aggregated = []
        for bucket_time in sorted(buckets.keys()):
            bucket_readings = buckets[bucket_time]

            def _safe_mean(values: list) -> float | None:
                valid = [v for v in values if v is not None]
                return sum(valid) / len(valid) if valid else None

            aggregated.append(
                {
                    "timestamp": bucket_time.isoformat(),
                    "temperature": _safe_mean([r.get("temperature") for r in bucket_readings]),
                    "humidity": _safe_mean([r.get("humidity") for r in bucket_readings]),
                    "soil_moisture": _safe_mean([r.get("soil_moisture") for r in bucket_readings]),
                    "lux": _safe_mean([r.get("lux") for r in bucket_readings]),
                    "co2": _safe_mean([r.get("co2") for r in bucket_readings]),
                    "voc": _safe_mean([r.get("voc") for r in bucket_readings]),
                    "reading_count": len(bucket_readings),
                }
            )

        return aggregated

    # ── Value Statistics Utility ──────────────────────────────────────

    def _calculate_value_stats(self, values: list[float]) -> dict[str, Any]:
        """Calculate comprehensive statistics for a list of values."""
        if not values:
            return {
                "count": 0,
                "min": None,
                "max": None,
                "avg": None,
                "median": None,
                "std_dev": None,
                "range": None,
                "trend": "stable",
            }

        count = len(values)
        min_val = min(values)
        max_val = max(values)
        avg = sum(values) / count

        sorted_values = sorted(values)
        if count % 2 == 0:
            median = (sorted_values[count // 2 - 1] + sorted_values[count // 2]) / 2
        else:
            median = sorted_values[count // 2]

        variance = sum((v - avg) ** 2 for v in values) / count
        std_dev = variance**0.5

        trend = "stable"
        if count >= 4:
            mid = count // 2
            first_half_avg = sum(values[:mid]) / mid
            second_half_avg = sum(values[mid:]) / (count - mid)
            delta = second_half_avg - first_half_avg
            threshold = std_dev * 0.5 if std_dev > 0 else abs(avg) * 0.05
            if delta > threshold:
                trend = "increasing"
            elif delta < -threshold:
                trend = "decreasing"

        return {
            "count": count,
            "min": round(min_val, 2),
            "max": round(max_val, 2),
            "avg": round(avg, 2),
            "median": round(median, 2),
            "std_dev": round(std_dev, 2),
            "range": round(max_val - min_val, 2),
            "trend": trend,
        }

    # ── Environmental Dashboard Summary ──────────────────────────────

    def get_environmental_dashboard_summary(self, unit_id: int | None = None) -> dict[str, Any]:
        """Get environmental conditions summary for dashboard."""
        try:
            end = utc_now()
            start = end - timedelta(hours=AnalysisWindows.SENSOR_HISTORY_HOURS)
            latest = self.get_latest_sensor_reading(unit_id=unit_id)
            stats = self.get_sensor_statistics(start, end, unit_id=unit_id)
            return {"unit_id": unit_id, "current": latest, "daily_stats": stats, "timestamp": end.isoformat()}
        except Exception as e:
            self.logger.error("Error generating environmental summary: %s", e, exc_info=True)
            return {"error": str(e)}

    # ── Enriched Sensor History (Photoperiod + DIF) ──────────────────

    def get_enriched_sensor_history(
        self,
        start_datetime: datetime,
        end_datetime: datetime,
        *,
        unit_id: int | None = None,
        sensor_id: int | None = None,
        limit: int | None = 500,
        interval: str | None = None,
        lux_threshold_override: float | None = None,
        prefer_lux: bool = False,
        day_start_override: str | None = None,
        day_end_override: str | None = None,
        unit_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Get sensor history enriched with photoperiod and day/night analysis."""
        readings = self.fetch_sensor_history(
            start_datetime, end_datetime, unit_id=unit_id, sensor_id=sensor_id, limit=limit
        )
        chart_data = self.format_sensor_chart_data(readings, interval)
        parsed_timestamps = self._normalize_chart_timestamps(chart_data)

        pp_cfg = self._resolve_photoperiod_config(
            unit_id=unit_id,
            unit_data=unit_data,
            lux_threshold_override=lux_threshold_override,
            prefer_lux=prefer_lux,
            day_start_override=day_start_override,
            day_end_override=day_end_override,
        )

        photoperiod_summary = self._compute_photoperiod(chart_data, parsed_timestamps, pp_cfg)

        chart_data["is_day_schedule"] = photoperiod_summary.pop("_schedule_mask")
        chart_data["is_day_sensor"] = photoperiod_summary.pop("_sensor_mask")
        chart_data["is_day"] = photoperiod_summary.pop("_day_mask")

        return {
            "start": start_datetime.isoformat(),
            "end": end_datetime.isoformat(),
            "unit_id": unit_id,
            "sensor_id": sensor_id,
            "interval": interval,
            "count": len(readings),
            "data": chart_data,
            "photoperiod": photoperiod_summary,
            "timestamp": utc_now().isoformat(),
        }

    # ── Photoperiod Helpers ──────────────────────────────────────────

    def _normalize_chart_timestamps(self, chart_data: dict[str, Any]) -> list[datetime | None]:
        """Parse and normalize chart_data timestamps in-place."""
        parsed: list[datetime | None] = []
        normalized: list[str] = []
        for ts in chart_data.get("timestamps", []):
            dt = coerce_datetime(ts)
            parsed.append(dt)
            normalized.append(dt.isoformat() if dt else str(ts))
        chart_data["timestamps"] = normalized
        return parsed

    def _resolve_photoperiod_config(
        self,
        *,
        unit_id: int | None,
        unit_data: dict[str, Any] | None,
        lux_threshold_override: float | None,
        prefer_lux: bool,
        day_start_override: str | None,
        day_end_override: str | None,
    ) -> dict[str, Any]:
        """Resolve schedule, threshold, and source-priority settings."""
        photoperiod_source = "schedule"
        schedule_present = False
        schedule_enabled = False
        schedule_day_start = day_start_override
        schedule_day_end = day_end_override
        lux_threshold = lux_threshold_override if lux_threshold_override is not None else 100.0

        unit = unit_data
        if not unit and unit_id is not None and self.growth_repo:
            try:
                row = self.growth_repo.get_unit(unit_id)
                if row:
                    unit = dict(row) if hasattr(row, "keys") else None
            except Exception as e:
                self.logger.warning("Failed to fetch unit %s for analytics: %s", unit_id, e)

        if unit_id is not None and self.scheduling_service:
            try:
                schedules = self.scheduling_service.get_schedules_for_unit(unit_id, device_type="light")
                if schedules:
                    schedule = schedules[0]
                    schedule_present = True
                    schedule_day_start = schedule_day_start or schedule.start_time
                    schedule_day_end = schedule_day_end or schedule.end_time
                    schedule_enabled = bool(schedule.enabled)
                    if schedule.photoperiod:
                        photoperiod_source = (
                            schedule.photoperiod.source.value if schedule.photoperiod.source else "schedule"
                        )
            except Exception as e:
                self.logger.warning("Failed to get light schedule from SchedulingService: %s", e)

        if unit:
            settings = unit.get("settings") or {}
            if lux_threshold_override is None:
                threshold_val = None
                if self.threshold_service and unit_id is not None:
                    thresholds = self.threshold_service.get_unit_thresholds(unit_id)
                    if thresholds:
                        threshold_val = thresholds.lux
                if threshold_val is None:
                    threshold_val = unit.get("lux_threshold")
                if threshold_val is None:
                    threshold_val = settings.get("lux_threshold")
                if threshold_val is not None:
                    lux_threshold = float(threshold_val)

        if photoperiod_source == "sensor":
            prefer_lux = True
            schedule_enabled = False
        elif photoperiod_source == "hybrid":
            prefer_lux = True

        schedule_day_start = schedule_day_start or "06:00"
        schedule_day_end = schedule_day_end or "18:00"

        return {
            "photoperiod_source": photoperiod_source,
            "schedule_present": schedule_present,
            "schedule_enabled": schedule_enabled,
            "schedule_day_start": schedule_day_start,
            "schedule_day_end": schedule_day_end,
            "lux_threshold": float(lux_threshold),
            "prefer_lux": prefer_lux,
        }

    def _compute_photoperiod(
        self,
        chart_data: dict[str, Any],
        parsed_timestamps: list[datetime | None],
        cfg: dict[str, Any],
    ) -> dict[str, Any]:
        """Build photoperiod masks + temperature DIF analysis."""
        lux_values = chart_data.get("lux", []) or []
        sensor_enabled = any(v is not None for v in lux_values)
        n = len(parsed_timestamps)

        day_mask: list[int | None] = [None] * n
        schedule_mask: list[int | None] = [None] * n
        sensor_mask: list[int | None] = [None] * n

        summary: dict[str, Any] = {
            "photoperiod_source": cfg["photoperiod_source"],
            "schedule_day_start": cfg["schedule_day_start"],
            "schedule_day_end": cfg["schedule_day_end"],
            "schedule_present": cfg["schedule_present"],
            "schedule_enabled": cfg["schedule_enabled"],
            "lux_threshold": cfg["lux_threshold"],
            "prefer_lux": cfg["prefer_lux"],
            "sensor_enabled": sensor_enabled,
            "source": None,
            "agreement_rate": None,
            "schedule_light_hours": None,
            "sensor_light_hours": None,
            "start_offset_minutes": None,
            "end_offset_minutes": None,
            "day_temperature_avg_c": None,
            "night_temperature_avg_c": None,
            "dif_c": None,
        }

        valid_indices = [i for i, ts in enumerate(parsed_timestamps) if ts is not None]
        if valid_indices:
            timestamps_valid = [parsed_timestamps[i] for i in valid_indices if parsed_timestamps[i] is not None]
            lux_valid = [lux_values[i] for i in valid_indices]

            photoperiod = Photoperiod(
                schedule_day_start=cfg["schedule_day_start"],
                schedule_day_end=cfg["schedule_day_end"],
                schedule_enabled=cfg["schedule_enabled"],
                sensor_threshold=cfg["lux_threshold"],
                greenhouse_outside=cfg["prefer_lux"],
                sensor_enabled=sensor_enabled,
            )

            resolved = photoperiod.resolve_mask(timestamps_valid, sensor_values=lux_valid)
            schedule_mask_valid = resolved.get("schedule_mask") or []
            sensor_mask_valid = resolved.get("sensor_mask") or []
            final_mask_valid = resolved.get("final_mask") or []

            for local_idx, original_idx in enumerate(valid_indices):
                if local_idx < len(schedule_mask_valid):
                    schedule_mask[original_idx] = 1 if schedule_mask_valid[local_idx] else 0
                if local_idx < len(sensor_mask_valid):
                    sensor_val = sensor_mask_valid[local_idx]
                    sensor_mask[original_idx] = None if sensor_val is None else (1 if sensor_val else 0)
                if local_idx < len(final_mask_valid):
                    day_mask[original_idx] = 1 if final_mask_valid[local_idx] else 0

            if sensor_enabled:
                alignment = photoperiod.analyze_alignment(timestamps_valid, lux_valid)
                summary.update(alignment)

            if sensor_enabled and cfg["prefer_lux"]:
                summary["source"] = "lux"
            elif cfg["schedule_enabled"]:
                summary["source"] = "schedule"
            elif sensor_enabled:
                summary["source"] = "lux"
            else:
                summary["source"] = "schedule"

            self._apply_temperature_dif(chart_data, day_mask, summary)

        summary["_schedule_mask"] = schedule_mask
        summary["_sensor_mask"] = sensor_mask
        summary["_day_mask"] = day_mask
        return summary

    def _apply_temperature_dif(
        self,
        chart_data: dict[str, Any],
        day_mask: list[int | None],
        summary: dict[str, Any],
    ) -> None:
        """Compute day/night temperature averages and DIF, updating *summary* in-place."""
        temps = chart_data.get("temperature", [])
        day_temps = [t for t, m in zip(temps, day_mask) if isinstance(t, int | float) and m == 1]
        night_temps = [t for t, m in zip(temps, day_mask) if isinstance(t, int | float) and m == 0]

        day_avg = self._safe_mean(day_temps)
        night_avg = self._safe_mean(night_temps)
        summary["day_temperature_avg_c"] = day_avg
        summary["night_temperature_avg_c"] = night_avg
        if day_avg is not None and night_avg is not None:
            summary["dif_c"] = round(day_avg - night_avg, 3)

    @staticmethod
    def _safe_mean(values: list[float]) -> float | None:
        if not values:
            return None
        valid = [v for v in values if v is not None]
        if not valid:
            return None
        return round(sum(valid) / len(valid), 3)

    # ── Cache Management ─────────────────────────────────────────────

    def get_cache_stats(self) -> dict[str, Any]:
        """Get cache statistics for monitoring and debugging."""
        return {
            "latest_readings": self._latest_reading_cache.get_stats(),
            "history": self._history_cache.get_stats(),
        }

    def clear_caches(self) -> None:
        """Clear all caches."""
        self._latest_reading_cache.clear()
        self._history_cache.clear()
        self.logger.info("Cleared all sensor analytics service caches")

    def warm_cache(self, unit_ids: list[int] | None = None) -> dict[str, Any]:
        """Pre-populate caches with frequently accessed data."""
        import time

        start_time = time.monotonic()
        units_processed = 0
        latest_readings_cached = 0
        history_windows_cached = 0

        try:
            if unit_ids is None:
                if self.device_repo:
                    try:
                        all_units = self.device_repo.list_units()
                        unit_ids = [u.get("unit_id") for u in all_units if u.get("unit_id")]
                    except Exception as e:
                        self.logger.warning("Could not list units for cache warming: %s", e)
                        unit_ids = []
                else:
                    unit_ids = []

            for uid in unit_ids:
                try:
                    self.get_latest_sensor_reading(unit_id=uid)
                    latest_readings_cached += 1
                    now = utc_now()
                    self.fetch_sensor_history(
                        now - timedelta(hours=AnalysisWindows.SENSOR_HISTORY_HOURS),
                        now,
                        unit_id=uid,
                        limit=DataLimits.LARGE_FETCH_LIMIT,
                    )
                    history_windows_cached += 1
                    self.fetch_sensor_history(
                        now - timedelta(days=7), now, unit_id=uid, limit=DataLimits.SENSOR_READINGS_MAX
                    )
                    history_windows_cached += 1
                    units_processed += 1
                except Exception as e:
                    self.logger.warning("Error warming cache for unit %s: %s", uid, e)
                    continue

            try:
                self.get_latest_sensor_reading(unit_id=None)
                latest_readings_cached += 1
            except Exception as e:
                self.logger.warning("Error warming global latest reading cache: %s", e)

            execution_time_ms = round((time.monotonic() - start_time) * 1000, 2)

            self.logger.info(
                "Cache warming complete: %s units, %s latest readings, %s history windows in %sms",
                units_processed,
                latest_readings_cached,
                history_windows_cached,
                execution_time_ms,
            )

            return {
                "units_processed": units_processed,
                "latest_readings_cached": latest_readings_cached,
                "history_windows_cached": history_windows_cached,
                "execution_time_ms": execution_time_ms,
            }

        except Exception as e:
            self.logger.error("Error during cache warming: %s", e, exc_info=True)
            return {
                "units_processed": units_processed,
                "latest_readings_cached": latest_readings_cached,
                "history_windows_cached": history_windows_cached,
                "execution_time_ms": round((time.monotonic() - start_time) * 1000, 2),
                "error": str(e),
            }

    # ── Plant Readings (Sprint 4 – Task 7) ──────────────────────────

    def get_plant_readings(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """
        Retrieve paginated plant readings for the frontend.

        Delegates to ``AnalyticsRepository.get_plant_readings`` which
        queries the plant_readings table.

        Args:
            limit:  Maximum rows to return (default 100).
            offset: Number of rows to skip (default 0).

        Returns:
            List of plant reading dictionaries.
        """
        try:
            return self.repository.get_plant_readings(limit=limit, offset=offset)
        except Exception as e:
            self.logger.error("Error fetching plant readings: %s", e, exc_info=True)
            return []

    def get_latest_plant_readings(
        self,
        plant_id: int,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Get the latest readings for a specific plant."""
        try:
            return self.repository.get_latest_plant_readings(plant_id, limit=limit)
        except Exception as e:
            self.logger.error("Error fetching latest plant readings for plant %s: %s", plant_id, e, exc_info=True)
            return []

    def get_plant_readings_in_window(
        self,
        plant_id: int,
        *,
        start: str,
        end: str,
    ) -> list[dict[str, Any]]:
        """Get plant readings within a time window."""
        try:
            return self.repository.get_plant_readings_in_window(plant_id, start=start, end=end)
        except Exception as e:
            self.logger.error("Error fetching plant readings in window for plant %s: %s", plant_id, e, exc_info=True)
            return []

    def get_plants_needing_attention(
        self,
        unit_id: int,
        *,
        moisture_threshold: float = 30.0,
        hours_since_reading: int = 24,
    ) -> list[dict[str, Any]]:
        """Get plants that need attention based on moisture threshold."""
        try:
            return self.repository.get_plants_needing_attention(
                unit_id,
                moisture_threshold=moisture_threshold,
                hours_since_reading=hours_since_reading,
            )
        except Exception as e:
            self.logger.error("Error fetching plants needing attention for unit %s: %s", unit_id, e, exc_info=True)
            return []
