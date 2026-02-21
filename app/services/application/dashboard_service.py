"""Dashboard Aggregation Service
================================

Orchestrates multiple domain services to produce dashboard payloads.
Extracted from ``app.blueprints.api.dashboard`` (Sprint 4 / Ref #10)
so that route handlers contain only HTTP concerns while all business
logic lives in the service layer.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from app.domain.agronomics import infer_gdd_base_temp_c
from app.utils.psychrometrics import calculate_vpd_kpa
from app.utils.time import coerce_datetime, iso_now

logger = logging.getLogger(__name__)

# Fallback thresholds when DeviceHealthService is unavailable
_SENSOR_THRESHOLDS: dict[str, dict[str, int]] = {
    "temperature": {"min": 18, "max": 28},
    "humidity": {"min": 40, "max": 80},
    "soil_moisture": {"min": 30, "max": 70},
    "lux": {"min": 200, "max": 1500},
    "co2": {"min": 300, "max": 800},
    "energy_usage": {"min": 0, "max": 5},
}

_CACHE_TTL = 30

from app.utils.cache import TTLCache

# ── standalone utilities ─────────────────────────────────────────────


def _ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _normalize_stage(name: str | None) -> str:
    return str(name or "").strip().lower()


# =====================================================================
# DashboardService
# =====================================================================


class DashboardService:
    """Aggregate dashboard data from sensor, plant, device and alert services.

    Accepts the application *ServiceContainer* so that the ~20 private
    builder methods can reach whichever sub-service they need without
    having to thread 12+ constructor parameters.
    """

    def __init__(self, container: Any) -> None:
        self._c = container
        self._ts_cache = TTLCache(enabled=True, ttl_seconds=_CACHE_TTL, maxsize=64)

    # ------------------------------------------------------------------
    # Public API – one method per dashboard endpoint
    # ------------------------------------------------------------------

    def get_current_sensor_data(self, unit_id: int | None) -> dict[str, Any]:
        """Return current sensor readings for the given unit."""
        snapshot = None
        try:
            mqtt = getattr(self._c, "mqtt_sensor_service", None)
            processor = getattr(mqtt, "processor", None) if mqtt else None
            if processor and unit_id is not None:
                snapshot = processor.get_dashboard_snapshot(unit_id=unit_id)
        except (RuntimeError, OSError, KeyError, TypeError, ValueError) as exc:
            logger.debug("Failed to build live dashboard snapshot: %s", exc)

        analytics = getattr(self._c, "analytics_service", None)
        latest = None
        energy_row = None
        if analytics:
            try:
                if snapshot is None:
                    latest = analytics.get_latest_sensor_reading(unit_id=unit_id)
                energy_row = analytics.get_latest_energy_reading()
            except (OSError, KeyError, TypeError, ValueError) as db_err:
                logger.error("Service error: %s", db_err, exc_info=True)
                if snapshot is None:
                    raise RuntimeError("Analytics service unavailable") from db_err

        if snapshot is not None:
            metrics = getattr(snapshot, "metrics", None) or {}
            timestamp = getattr(snapshot, "timestamp", None) or iso_now()
            sensor_data = {
                "temperature": self._snap_metric(metrics, "temperature", "°C", "temperature", timestamp),
                "humidity": self._snap_metric(metrics, "humidity", "%", "humidity", timestamp),
                "soil_moisture": self._snap_metric(
                    metrics, "soil_moisture", "%", "soil_moisture", timestamp, trend="up"
                ),
                "co2": self._snap_metric(metrics, "co2", "ppm", "co2", timestamp),
                "lux": self._snap_metric(metrics, "lux", "lux", "lux", timestamp),
                "energy_usage": self._energy_metric(energy_row),
            }
        else:
            sensor_data = {
                "temperature": self._build_metric(latest, "temperature", "°C", "temperature"),
                "humidity": self._build_metric(latest, "humidity", "%", "humidity"),
                "soil_moisture": self._build_metric(latest, "soil_moisture", "%", "soil_moisture", trend="up"),
                "co2": self._build_metric(latest, "co2", "ppm", "co2"),
                "lux": self._build_metric(latest, "lux", "lux", "lux"),
                "energy_usage": self._energy_metric(energy_row),
            }

        return {
            "sensor_data": sensor_data,
            "timestamp": (
                (getattr(snapshot, "timestamp", None) if snapshot else None)
                or (latest["timestamp"] if latest else iso_now())
            ),
        }

    # ---- timeseries --------------------------------------------------

    def get_timeseries(
        self,
        start: datetime,
        end: datetime,
        *,
        unit_id: int | None = None,
        sensor_id: int | None = None,
        limit: int = 500,
        hours: int | None = None,
    ) -> dict[str, Any]:
        """Return sensor readings for charts, with caching and downsampling."""
        analytics = getattr(self._c, "analytics_service", None)
        if not analytics:
            raise RuntimeError("Analytics service unavailable")

        target_limit = limit or 500
        if hours and hours > 168:
            target_limit = min(target_limit, 800)
        elif hours and hours > 72:
            target_limit = min(target_limit, 1200)
        target_limit = max(50, target_limit)

        key = self._ts_key(start, end, unit_id, sensor_id, target_limit, hours)
        cached = self._ts_get(key)
        if cached is not None:
            return cached

        db_limit = max(target_limit * 4, 0) if target_limit else None
        readings = analytics.fetch_sensor_history(start, end, unit_id=unit_id, sensor_id=sensor_id, limit=db_limit)
        series = self._downsample(readings, target=target_limit)

        for row in series:
            parsed = coerce_datetime(row.get("timestamp"))
            if parsed:
                row["timestamp"] = parsed.isoformat()

        payload = {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "unit_id": unit_id,
            "sensor_id": sensor_id,
            "count": len(readings),
            "returned": len(series),
            "series": series,
        }
        self._ts_set(key, payload)
        return payload

    # ---- simple device queries ---------------------------------------

    def get_recent_actuator_state(self, *, unit_id: int | None = None, limit: int = 20) -> dict[str, Any]:
        """Last *limit* actuator state transitions."""
        rows = self._c.device_repo.get_recent_actuator_state(limit=limit, unit_id=unit_id)
        return {"states": rows, "count": len(rows)}

    def get_recent_connectivity(self, *, connection_type: str | None = None, limit: int = 20) -> dict[str, Any]:
        """Last *limit* connectivity events."""
        rows = self._c.device_repo.get_connectivity_history(connection_type=connection_type, limit=limit)
        return {"events": rows, "count": len(rows)}

    # ---- system status -----------------------------------------------

    def get_system_status(self) -> dict[str, Any]:
        """System status for dashboard header."""
        growth = getattr(self._c, "growth_service", None)
        zigbee = getattr(self._c, "zigbee_service", None)
        try:
            connected = bool(zigbee.is_connected()) if zigbee and hasattr(zigbee, "is_connected") else False
        except (AttributeError, TypeError, OSError):
            connected = False
        database_online = bool(self._c.database)
        units_online = len(growth.get_unit_runtimes()) if growth else 0

        try:
            devices_count = len(self._c.sensor_management_service.list_sensors()) + len(
                self._c.actuator_management_service.list_actuators()
            )
        except (RuntimeError, OSError, KeyError, TypeError, ValueError):
            devices_count = 0

        alerts_count = 0
        alert_svc = getattr(self._c, "alert_service", None)
        if alert_svc:
            try:
                alerts_count = len(alert_svc.get_active_alerts(limit=1000))
            except (OSError, KeyError, TypeError, ValueError) as exc:
                logger.debug("Could not fetch alert count: %s", exc)

        return {
            "connected": bool(connected),
            "sensors_online": units_online > 0,
            "database_online": database_online,
            "last_update": iso_now(),
            "devices_count": devices_count,
            "alerts_count": alerts_count,
        }

    # ---- comprehensive summary ---------------------------------------

    def get_summary(self, unit_id: int | None) -> dict[str, Any]:
        """Full dashboard summary – sensors, plants, alerts, energy, devices, system."""
        growth = getattr(self._c, "growth_service", None)
        scorer = getattr(self._c, "plant_health_scorer", None)

        summary: dict[str, Any] = {
            "unit_id": unit_id,
            "timestamp": iso_now(),
            "sensors": {},
            "vpd": {},
            "plants": [],
            "active_plant": None,
            "alerts": {"count": 0, "recent": []},
            "energy": {},
            "devices": {"active": 0, "total": 0},
            "actuators": [],
            "system": {"health_score": 0, "status": "unknown"},
            "unit_settings": None,
        }
        sensors_raw: list = []
        actuators_raw: list = []

        # 1. Sensor data (snapshot or analytics fallback)
        try:
            s_dict, vpd_dict, energy_row = self._build_snapshot_or_analytics(unit_id)
            summary["sensors"] = s_dict or {}
            summary["vpd"] = vpd_dict or {}
            if energy_row:
                try:
                    summary["energy"] = self._build_energy_summary(energy_row, unit_id)
                except (KeyError, TypeError, ValueError, AttributeError) as exc:
                    logger.debug("Failed to build energy summary: %s", exc)
        except (KeyError, TypeError, ValueError, RuntimeError, OSError) as exc:
            logger.warning("Error fetching sensor/energy data: %s", exc)

        # 2. Plants
        try:
            plant_summaries, focus_plant, health_avg = self._build_plants_summary(unit_id, growth, scorer)
            summary["plants"] = plant_summaries
            if focus_plant:
                summary["active_plant"] = self._build_active_plant_details(focus_plant)
            if health_avg is not None:
                summary["system"]["plant_health_avg"] = health_avg
        except (KeyError, TypeError, ValueError, AttributeError, OSError) as exc:
            logger.warning("Error fetching plant data: %s", exc)

        # 3. Alerts
        try:
            summary["alerts"] = self._build_alerts_summary(unit_id)
        except (KeyError, TypeError, ValueError, OSError) as exc:
            logger.warning("Error fetching alerts: %s", exc)

        # 4. Devices
        try:
            sensors_raw, actuators_raw, dev_summary = self._build_devices_summary(unit_id)
            summary["devices"] = dev_summary
            summary["actuators"] = actuators_raw if isinstance(actuators_raw, list) else []
        except (KeyError, TypeError, ValueError, RuntimeError, OSError) as exc:
            logger.warning("Error fetching devices: %s", exc)

        # 5. System health
        try:
            summary["system"] = self._build_system_summary(summary)
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            logger.debug("Failed to build system summary: %s", exc)

        # 6. Unit settings (thresholds, schedules, configured devices)
        if unit_id and growth:
            try:
                summary["unit_settings"] = self._build_unit_settings(
                    growth, unit_id, sensors=sensors_raw, actuators=actuators_raw
                )
            except (KeyError, TypeError, ValueError, AttributeError, OSError) as exc:
                logger.warning("Error building unit settings for unit %s: %s", unit_id, exc)

        return summary

    # ---- growth stage ------------------------------------------------

    def get_growth_stage_info(self, unit_id: int | None) -> dict[str, Any]:
        """Growth-stage progress details for a unit."""
        empty: dict[str, Any] = {
            "unit_id": unit_id,
            "plant_id": None,
            "plant_name": None,
            "current_stage": "unknown",
            "stage_index": -1,
            "stages": [],
            "days_in_stage": 0,
            "days_left": None,
            "days_total": 0,
            "progress": 0,
            "tip": None,
        }

        growth = getattr(self._c, "growth_service", None)
        plant_svc = getattr(self._c, "plant_service", None)
        if not growth or not plant_svc:
            raise RuntimeError("Services unavailable")

        if unit_id is None:
            return empty

        active_plant = plant_svc.get_active_plant(unit_id)
        if not active_plant:
            return empty

        plant = active_plant.to_dict()
        current_stage = plant.get("current_stage") or plant.get("growth_stage") or plant.get("stage") or "unknown"
        stage_names = self._extract_stage_names(plant.get("growth_stages"))
        if not stage_names:
            stage_names = ["seedling", "vegetative", "flowering", "fruiting", "harvest"]

        stage_index = -1
        norm = _normalize_stage(current_stage)
        for idx, name in enumerate(stage_names):
            if _normalize_stage(name) == norm:
                stage_index = idx
                break

        days_in_stage = plant.get("days_in_stage") or plant.get("days_in_current_stage")
        try:
            days_in_stage = int(days_in_stage) if days_in_stage is not None else 0
        except (TypeError, ValueError):
            days_in_stage = 0

        days_left = plant.get("days_left")
        try:
            days_left = int(days_left) if days_left is not None else None
        except (TypeError, ValueError):
            days_left = None

        stage_det = self._find_stage_details(plant.get("growth_stages"), current_stage) or {}
        duration = stage_det.get("duration", {}) if isinstance(stage_det, dict) else {}
        stage_total = duration.get("max_days") or duration.get("min_days")
        if stage_total in (None, 0) and days_left is not None:
            stage_total = days_in_stage + days_left
        try:
            stage_total = int(stage_total) if stage_total is not None else 0
        except (TypeError, ValueError):
            stage_total = 0

        stage_progress = (days_in_stage / stage_total) if stage_total > 0 else 0
        if stage_index >= 0 and stage_names:
            progress = ((stage_index + stage_progress) / len(stage_names)) * 100
        else:
            progress = stage_progress * 100
        progress = max(0, min(100, round(progress, 1)))

        return {
            "unit_id": unit_id,
            "plant_id": plant.get("plant_id") or plant.get("id"),
            "plant_name": plant.get("plant_name") or plant.get("name"),
            "current_stage": current_stage,
            "stage_index": stage_index,
            "stages": stage_names,
            "days_in_stage": days_in_stage,
            "days_left": days_left,
            "days_total": stage_total,
            "progress": progress,
            "tip": None,
        }

    # ---- harvest timeline --------------------------------------------

    def get_harvest_timeline(self, unit_id: int | None) -> dict[str, Any]:
        """Upcoming harvests and most recent harvest for a unit."""
        plant_svc = getattr(self._c, "plant_service", None)
        harvest_svc = getattr(self._c, "harvest_service", None)

        if not plant_svc:
            raise RuntimeError("Services unavailable")

        upcoming: list[dict] = []
        if unit_id is not None:
            plants = plant_svc.list_plants(unit_id)
            now = datetime.now(UTC)
            for p in plants:
                p = p.to_dict() if hasattr(p, "to_dict") else dict(p)
                expected = p.get("expected_harvest_date") or p.get("expected_harvest") or p.get("harvest_date")
                target = self._parse_date_value(expected)
                if not target:
                    continue
                days_until = max(0, (target.date() - now.date()).days)
                upcoming.append(
                    {
                        "plant_id": p.get("plant_id") or p.get("id"),
                        "name": p.get("plant_name") or p.get("name") or "Plant",
                        "expected_harvest_date": target.date().isoformat(),
                        "days_until_harvest": days_until,
                    }
                )
            upcoming.sort(key=lambda item: item.get("days_until_harvest", 0))

        recent = None
        if harvest_svc and unit_id is not None:
            reports = harvest_svc.get_harvest_reports(unit_id)
            if reports:
                r = reports[0]
                recent = {
                    "harvest_id": r.get("harvest_id"),
                    "plant_id": r.get("plant_id"),
                    "date": r.get("harvested_date"),
                    "amount": r.get("harvest_weight_grams"),
                }

        return {"unit_id": unit_id, "upcoming": upcoming, "recent_harvest": recent}

    # ---- water schedule ----------------------------------------------

    def get_water_schedule(self, unit_id: int | None) -> dict[str, Any]:
        """Watering and feeding schedule overview for a unit."""
        sched_svc = self._scheduling_service
        if not sched_svc:
            raise RuntimeError("Scheduling service unavailable")

        if unit_id is None:
            return {
                "unit_id": None,
                "next_water_hours": None,
                "next_feed_hours": None,
                "water_days": [],
                "feed_days": [],
            }

        schedules = sched_svc.get_schedules_for_unit(unit_id)

        water_sched = next(
            (
                s
                for s in schedules
                if s.device_type and s.device_type.lower() in ("watering", "water", "irrigation", "pump")
            ),
            None,
        )
        feed_sched = next(
            (
                s
                for s in schedules
                if s.device_type and s.device_type.lower() in ("feeding", "feed", "nutrient", "fertigation")
            ),
            None,
        )

        water_p = {"start_time": water_sched.start_time, "end_time": water_sched.end_time} if water_sched else None
        feed_p = {"start_time": feed_sched.start_time, "end_time": feed_sched.end_time} if feed_sched else None

        return {
            "unit_id": unit_id,
            "next_water_hours": self._hours_until_time(water_p.get("start_time") if water_p else None),
            "next_feed_hours": self._hours_until_time(feed_p.get("start_time") if feed_p else None),
            "water_days": self._schedule_days(water_p),
            "feed_days": self._schedule_days(feed_p),
        }

    # ---- irrigation status -------------------------------------------

    def get_irrigation_status(self, unit_id: int | None) -> dict[str, Any]:
        """Recent irrigation activity and current soil moisture for a unit."""
        irrig_svc = getattr(self._c, "irrigation_workflow_service", None)
        analytics = getattr(self._c, "analytics_service", None)

        last_run = None
        duration = None
        amount = None

        if irrig_svc and unit_id is not None:
            last = irrig_svc.get_last_completed_irrigation(unit_id)
            if last:
                last_run = last.get("executed_at") or last.get("scheduled_time")
                duration = last.get("execution_duration_seconds") or last.get("duration_seconds")

        soil_moisture = None
        if analytics and unit_id is not None:
            try:
                latest = analytics.get_latest_sensor_reading(unit_id=unit_id)
                soil_moisture = latest.get("soil_moisture") if latest else None
            except (OSError, KeyError, TypeError, ValueError) as exc:
                logger.debug("Failed to load soil moisture for unit %s: %s", unit_id, exc)

        return {
            "unit_id": unit_id,
            "last_run": last_run,
            "duration_seconds": duration,
            "amount_ml": amount,
            "soil_moisture": soil_moisture,
        }

    # ------------------------------------------------------------------
    # Service accessors (private)
    # ------------------------------------------------------------------

    @property
    def _scheduling_service(self):
        act = getattr(self._c, "actuator_management_service", None)
        return getattr(act, "scheduling_service", None) if act else None

    # ------------------------------------------------------------------
    # Private builders
    # ------------------------------------------------------------------

    def _build_snapshot_or_analytics(self, unit_id):
        """Return ``(sensors_dict, vpd_dict, energy_row)``."""
        try:
            snapshot = None
            try:
                mqtt = getattr(self._c, "mqtt_sensor_service", None)
                processor = getattr(mqtt, "processor", None) if mqtt else None
                if processor and unit_id is not None:
                    snapshot = processor.get_dashboard_snapshot(unit_id=unit_id)
            except (RuntimeError, OSError, KeyError, TypeError, ValueError) as exc:
                logger.debug("Live snapshot failed: %s", exc)

            analytics = getattr(self._c, "analytics_service", None)
            latest = None
            energy_row = None
            if analytics:
                try:
                    if snapshot is None:
                        latest = analytics.get_latest_sensor_reading(unit_id=unit_id)
                except (OSError, KeyError, TypeError, ValueError) as err:
                    logger.debug("get_latest_sensor_reading failed: %s", err)
                try:
                    energy_row = analytics.get_latest_energy_reading()
                except (OSError, KeyError, TypeError, ValueError) as err:
                    logger.debug("get_latest_energy_reading failed: %s", err)

            if snapshot is not None:
                metrics = getattr(snapshot, "metrics", None) or {}
                ts = getattr(snapshot, "timestamp", None) or iso_now()
                sensors = {
                    "temperature": self._snap_metric(metrics, "temperature", "°C", "temperature", ts),
                    "humidity": self._snap_metric(metrics, "humidity", "%", "humidity", ts),
                    "soil_moisture": self._snap_metric(metrics, "soil_moisture", "%", "soil_moisture", ts, trend="up"),
                    "co2": self._snap_metric(metrics, "co2", "ppm", "co2", ts),
                    "lux": self._snap_metric(metrics, "lux", "lux", "lux", ts),
                    "energy_usage": self._energy_metric(energy_row),
                }
                temp_m = metrics.get("temperature")
                hum_m = metrics.get("humidity")
                vpd = self._compute_vpd(
                    getattr(temp_m, "value", None) if temp_m else None,
                    getattr(hum_m, "value", None) if hum_m else None,
                )
                return sensors, vpd, energy_row

            if latest is not None:
                sensors = {
                    "temperature": self._build_metric(latest, "temperature", "°C", "temperature"),
                    "humidity": self._build_metric(latest, "humidity", "%", "humidity"),
                    "soil_moisture": self._build_metric(latest, "soil_moisture", "%", "soil_moisture", trend="up"),
                    "co2": self._build_metric(latest, "co2", "ppm", "co2"),
                    "lux": self._build_metric(latest, "lux", "lux", "lux"),
                    "energy_usage": self._energy_metric(energy_row),
                }
                vpd = self._compute_vpd(latest.get("temperature"), latest.get("humidity"))
                return sensors, vpd, energy_row

        except Exception as exc:  # TODO(narrow): wide catch for snapshot/analytics fallback path
            logger.debug("_build_snapshot_or_analytics error: %s", exc)
            return {}, {}, None

        return {}, {}, energy_row

    def _build_unit_settings(self, growth_service, unit_id, *, sensors=None, actuators=None):
        """Thresholds, schedules and configured devices for a unit."""
        try:
            thresholds_raw = growth_service.get_thresholds(unit_id) or {}
            thresholds = {
                "temperature_threshold": thresholds_raw.get("temperature_threshold"),
                "humidity_threshold": thresholds_raw.get("humidity_threshold"),
                "co2_threshold": thresholds_raw.get("co2_threshold"),
                "voc_threshold": thresholds_raw.get("voc_threshold"),
                "lux_threshold": thresholds_raw.get("lux_threshold"),
                "air_quality_threshold": thresholds_raw.get(
                    "air_quality_threshold", thresholds_raw.get("aqi_threshold")
                ),
            }

            sched_svc = self._scheduling_service
            schedules_summary: dict[str, list] = {}
            if sched_svc:
                try:
                    scheds = sched_svc.get_schedules_for_unit(unit_id)
                except (OSError, KeyError, TypeError, ValueError) as exc:
                    logger.warning("Error fetching schedules for unit %s: %s", unit_id, exc)
                    scheds = []

                if scheds:
                    by_device: dict[str, list] = {}
                    for s in scheds:
                        dt = s.device_type or "device"
                        by_device.setdefault(dt, []).append(s)

                    for dt, items in by_device.items():
                        items.sort(
                            key=lambda x: (
                                0 if x.enabled else 1,
                                -(getattr(x, "priority", 0) or 0),
                                getattr(x, "schedule_id", 0) or 0,
                            )
                        )
                        schedules_summary[dt] = [
                            {
                                "schedule_id": (p := s.to_dict() if hasattr(s, "to_dict") else dict(s)).get(
                                    "schedule_id"
                                ),
                                "name": p.get("name"),
                                "schedule_type": p.get("schedule_type"),
                                "start_time": p.get("start_time"),
                                "end_time": p.get("end_time"),
                                "enabled": p.get("enabled"),
                                "priority": p.get("priority"),
                            }
                            for s in items
                        ]

            sensors = sensors or []
            actuators = actuators or []

            sensors_list = [
                {
                    "sensor_id": s.get("sensor_id") or s.get("id"),
                    "name": s.get("name") or s.get("sensor_name") or "Sensor",
                    "sensor_type": s.get("sensor_type") or s.get("type") or "unknown",
                    "protocol": s.get("protocol"),
                    "model": s.get("model"),
                    "is_active": s.get("is_active", True),
                }
                for s in sensors
            ]
            actuators_list = [
                {
                    "actuator_id": a.get("actuator_id") or a.get("id"),
                    "name": a.get("name") or "Actuator",
                    "actuator_type": a.get("actuator_type") or a.get("type") or "unknown",
                    "protocol": a.get("protocol"),
                    "model": a.get("model"),
                    "is_active": a.get("is_active", True),
                }
                for a in actuators
            ]
            return {
                "thresholds": thresholds,
                "schedules": schedules_summary,
                "sensors": sensors_list,
                "actuators": actuators_list,
            }
        except Exception as exc:  # TODO(narrow): wide catch for unit settings builder
            logger.debug("Error building unit settings: %s", exc)
            return {}

    def _build_active_plant_details(self, focus_plant):
        """Active-plant dashboard payload from a focus plant dict."""
        try:
            pid = focus_plant.get("plant_id")
            stage = focus_plant.get("current_stage")
            gs = focus_plant.get("growth_stages") or []
            conds = self._find_stage_conditions(gs, stage)

            temp_cfg = conds.get("temperature_C", {}) or {}
            hum_cfg = conds.get("humidity_percent", {}) or {}
            hours = conds.get("hours_per_day")

            explicit = focus_plant.get("gdd_base_temp_c")
            src = "explicit" if explicit is not None else "inferred"
            base: float | None = None
            try:
                if explicit is not None:
                    base = float(explicit)
                else:
                    base = float(infer_gdd_base_temp_c(gs, stage_name=stage, default=10.0))
            except (ValueError, TypeError):
                base = None
                src = "unknown"

            return {
                "plant_id": pid,
                "active_plant_id": pid,
                "name": focus_plant.get("plant_name") or focus_plant.get("name", "Unknown"),
                "plant_type": focus_plant.get("plant_type") or focus_plant.get("species") or "",
                "status": focus_plant.get("status") or "active",
                "current_stage": stage,
                "days_in_stage": focus_plant.get("days_in_stage", 0),
                "days_left": focus_plant.get("days_left", 0),
                "gdd_base_temp_c": base,
                "gdd_base_temp_source": src,
                "targets": {
                    "temperature_c": {"min": temp_cfg.get("min"), "max": temp_cfg.get("max")},
                    "humidity_percent": {"min": hum_cfg.get("min"), "max": hum_cfg.get("max")},
                    "photoperiod_hours": hours,
                },
            }
        except Exception as exc:  # TODO(narrow): wide catch for active plant details builder
            logger.debug("Failed to build active plant details: %s", exc)
            return None

    def _build_alerts_summary(self, unit_id):
        alert_svc = getattr(self._c, "alert_service", None)
        if not alert_svc:
            return {"count": 0, "recent": [], "critical": 0, "warning": 0}
        try:
            recent = alert_svc.get_active_alerts(unit_id=unit_id, limit=20)
            return {
                "count": len(recent),
                "critical": len([a for a in recent if a.get("severity") == "critical"]),
                "warning": len([a for a in recent if a.get("severity") == "warning"]),
                "recent": recent[:5],
            }
        except (OSError, KeyError, TypeError, ValueError) as exc:
            logger.debug("Failed to fetch alerts for unit %s: %s", unit_id, exc)
            return {"count": 0, "recent": [], "critical": 0, "warning": 0}

    def _build_devices_summary(self, unit_id):
        """Return ``(sensors_list, actuators_list, devices_summary)``."""
        sensor_svc = getattr(self._c, "sensor_management_service", None)
        actuator_svc = getattr(self._c, "actuator_management_service", None)

        try:
            sensors = sensor_svc.list_sensors(unit_id=unit_id) if sensor_svc else []
        except (RuntimeError, OSError, KeyError, TypeError, ValueError):
            sensors = []
        try:
            actuators = actuator_svc.list_actuators(unit_id=unit_id) if actuator_svc else []
        except (RuntimeError, OSError, KeyError, TypeError, ValueError):
            actuators = []

        def _active(d):
            if not isinstance(d, dict):
                return False
            if "is_active" in d:
                v = d["is_active"]
                if isinstance(v, str):
                    return v.strip().lower() in {"1", "true", "active", "enabled", "on", "yes"}
                return bool(v)
            return str(d.get("status") or "").strip().lower() in {"active", "enabled", "on", "running", "online"}

        active_s = len([s for s in sensors if _active(s)]) if isinstance(sensors, list) else 0
        active_a = len([a for a in actuators if _active(a)]) if isinstance(actuators, list) else 0
        total = (len(sensors) if isinstance(sensors, list) else 0) + (
            len(actuators) if isinstance(actuators, list) else 0
        )
        return sensors, actuators, {"active": active_s + active_a, "total": total}

    def _build_energy_summary(self, energy_row, unit_id):
        if not energy_row:
            return {}
        act_svc = getattr(self._c, "actuator_management_service", None)
        try:
            if act_svc:
                em = getattr(act_svc.actuator_manager, "energy_monitoring", None)
                if em:
                    return em.get_energy_summary(energy_row)
        except (KeyError, TypeError, ValueError, RuntimeError, OSError) as exc:
            logger.debug("Energy monitoring call failed: %s", exc)
        return {
            "current_power_watts": energy_row.get("power_watts", 0),
            "daily_cost": 0.0,
            "trend": "stable",
            "timestamp": energy_row.get("timestamp"),
        }

    def _build_system_summary(self, current_summary):
        system = dict(current_summary.get("system", {"health_score": 0, "status": "unknown"}))
        try:
            dhs = getattr(self._c, "device_health_service", None)
            if dhs:
                try:
                    sh = dhs.calculate_system_health(
                        vpd_status=current_summary.get("vpd", {}).get("status"),
                        plant_health_avg=system.get("plant_health_avg"),
                        critical_alerts=current_summary.get("alerts", {}).get("critical", 0),
                        warning_alerts=current_summary.get("alerts", {}).get("warning", 0),
                        devices_active=current_summary.get("devices", {}).get("active", 0),
                        devices_total=current_summary.get("devices", {}).get("total", 0),
                    )
                    system["health_score"] = sh["health_score"]
                    system["status"] = sh["status"]
                    system["health_factors"] = sh.get("factors", {})
                    return system
                except (KeyError, TypeError, ValueError, RuntimeError, OSError) as exc:
                    logger.debug("calculate_system_health failed: %s", exc)

            avg = system.get("plant_health_avg")
            if avg is not None:
                system["health_score"] = max(system.get("health_score", 0), float(avg))

            score = system.get("health_score", 0)
            if score >= 80:
                system["status"] = "healthy"
            elif score >= 50:
                system["status"] = "degraded"
            elif score > 0:
                system["status"] = "unhealthy"
            else:
                system.setdefault("health_score", 75.0)
                system.setdefault("status", "good")
        except Exception:  # TODO(narrow): wide catch for system summary builder
            system.setdefault("health_score", 75.0)
            system.setdefault("status", "good")
        return system

    def _build_plants_summary(self, unit_id, growth_service, scorer):
        """Return ``(plant_summaries, focus_plant, health_avg)``."""
        try:
            plant_svc = getattr(self._c, "plant_service", None)
            if not plant_svc:
                return [], None, None
            plants = plant_svc.list_plants(unit_id) if unit_id else []
            summaries: list[dict] = []
            scores: list[float] = []

            active_plant_id = None
            active_plant = None
            try:
                active = plant_svc.get_active_plant(unit_id) if growth_service and unit_id else None
                active_plant = active.to_dict() if active else None
                active_plant_id = active_plant.get("plant_id") if active_plant else None
            except (KeyError, TypeError, ValueError, AttributeError, OSError):
                pass

            focus = active_plant
            if focus is None and plants:
                focus = plants[0].to_dict() if hasattr(plants[0], "to_dict") else dict(plants[0])

            dhs = getattr(self._c, "device_health_service", None)
            for p in plants:
                p = p.to_dict() if hasattr(p, "to_dict") else dict(p)
                pid = p.get("plant_id") or p.get("id")
                health = scorer.score_plant_health(pid) if scorer and pid else None
                hs = getattr(health, "overall_score", 75) if health else 75
                scores.append(hs)
                status_str = dhs.interpret_health_score(hs) if dhs else "good"
                summaries.append(
                    {
                        "plant_id": pid,
                        "name": p.get("plant_name") or p.get("name", "Unknown"),
                        "plant_name": p.get("plant_name") or p.get("name", "Unknown"),
                        "species": p.get("species") or p.get("plant_type") or "",
                        "plant_type": p.get("plant_type") or p.get("species") or "",
                        "current_stage": p.get("current_stage") or p.get("growth_stage", "vegetative"),
                        "growth_stage": p.get("current_stage") or p.get("growth_stage", "vegetative"),
                        "days_in_stage": p.get("days_in_stage", 0),
                        "status": p.get("status") or ("active" if pid == active_plant_id else "inactive"),
                        "health_score": hs,
                        "health_status": status_str,
                        "moisture_level": p.get("moisture_level"),
                        "moisture_percent": (
                            p.get("moisture_percent") if p.get("moisture_percent") is not None else p.get("moisture")
                        ),
                        "last_watered": p.get("last_watered") or p.get("last_watered_at"),
                        "custom_image": p.get("custom_image") or p.get("image"),
                        "image": p.get("image") or p.get("image_url") or p.get("custom_image"),
                        "image_url": p.get("image_url") or p.get("image"),
                    }
                )

            avg = sum(scores) / len(scores) if scores else None
            return summaries, focus, avg
        except Exception as exc:  # TODO(narrow): wide catch for plants summary builder
            logger.warning("Error building plants summary: %s", exc)
            return [], None, None

    # ------------------------------------------------------------------
    # Private metric / VPD helpers
    # ------------------------------------------------------------------

    def _build_metric(self, row, key, unit, threshold_key, trend="stable"):
        value = row.get(key) if row else None
        ts = row.get("timestamp") if row else iso_now()
        status = "Unknown"
        if value is not None:
            dhs = getattr(self._c, "device_health_service", None)
            status = (
                dhs.evaluate_sensor_status(value, threshold_key) if dhs else self._fallback_status(value, threshold_key)
            )
        return {"value": value, "unit": unit, "status": status, "trend": trend, "timestamp": ts}

    def _energy_metric(self, row):
        value = row["power_watts"] if row else None
        ts = row["timestamp"] if row else iso_now()
        return {
            "value": value,
            "unit": "W",
            "status": self._fallback_status(value, "energy_usage") if value is not None else "Unknown",
            "trend": "stable",
            "timestamp": ts,
        }

    def _snap_metric(self, metrics, metric_key, default_unit, threshold_key, timestamp, trend="stable"):
        m = metrics.get(metric_key)
        if not m:
            return {"value": None, "unit": default_unit, "status": "Unknown", "trend": trend, "timestamp": timestamp}
        value = getattr(m, "value", None)
        unit = getattr(m, "unit", None) or default_unit
        source = getattr(m, "source", None)
        status = getattr(source, "status", None) if source else None
        if not status and value is not None:
            dhs = getattr(self._c, "device_health_service", None)
            if dhs:
                try:
                    status = dhs.evaluate_sensor_status(value, threshold_key)
                except (KeyError, TypeError, ValueError, RuntimeError, OSError):
                    status = self._fallback_status(value, threshold_key)
            else:
                status = self._fallback_status(value, threshold_key)
        elif status is None:
            status = "Unknown"
        return {"value": value, "unit": unit, "status": status, "trend": trend, "timestamp": timestamp}

    def _compute_vpd(self, temperature, humidity):
        """VPD calculation with zone classification."""
        analytics = getattr(self._c, "analytics_service", None)
        if analytics:
            try:
                return analytics.calculate_vpd_with_zones(temperature, humidity)
            except (KeyError, TypeError, ValueError, RuntimeError, OSError):
                pass
        return self._calculate_vpd_fallback(temperature, humidity)

    # ------------------------------------------------------------------
    # Timeseries cache (delegates to TTLCache utility)
    # ------------------------------------------------------------------

    @staticmethod
    def _ts_key(start, end, uid, sid, limit, hours):
        return (start.isoformat(), end.isoformat(), uid, sid, limit, hours)

    def _ts_get(self, key):
        return self._ts_cache.get(key)

    def _ts_set(self, key, value):
        self._ts_cache.set(key, value)

    # ------------------------------------------------------------------
    # Static / pure helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _downsample(rows: list[dict], target: int) -> list[dict]:
        if not target or len(rows) <= target:
            return rows
        stride = max(1, len(rows) // target)
        return rows[::stride][:target]

    @staticmethod
    def _fallback_status(value, sensor_type: str) -> str:
        """Fallback sensor status when DeviceHealthService is unavailable."""
        try:
            thr = _SENSOR_THRESHOLDS.get(sensor_type, {"min": 0, "max": 100})
            if value < thr["min"]:
                return "Low"
            elif value > thr["max"]:
                return "High"
            return "Normal"
        except (KeyError, TypeError):
            return "Unknown"

    @staticmethod
    def _calculate_vpd_fallback(temperature, humidity):
        """Pure VPD calculation with zone classification."""
        if temperature is None or humidity is None:
            return {"value": None, "unit": "kPa", "status": "unknown", "zone": "unknown", "optimal_for": []}
        try:
            vpd_value = calculate_vpd_kpa(temperature, humidity)
            if vpd_value is None:
                raise ValueError("VPD inputs missing")
            vpd = round(float(vpd_value), 2)
            if vpd < 0.4:
                zone, status, optimal = "too_low", "low", []
            elif vpd < 0.8:
                zone, status, optimal = "seedling", "optimal", ["seedling", "clone", "early_veg"]
            elif vpd < 1.2:
                zone, status, optimal = "vegetative", "optimal", ["vegetative", "late_veg"]
            elif vpd < 1.5:
                zone, status, optimal = "flowering", "optimal", ["flowering", "bloom"]
            else:
                zone, status, optimal = "too_high", "high", []
            return {
                "value": vpd,
                "unit": "kPa",
                "status": status,
                "zone": zone,
                "optimal_for": optimal,
                "temperature": temperature,
                "humidity": humidity,
            }
        except (ValueError, TypeError, ZeroDivisionError, ArithmeticError) as exc:
            logger.warning("Error calculating VPD: %s", exc)
            return {"value": None, "unit": "kPa", "status": "error", "zone": "unknown", "optimal_for": []}

    @staticmethod
    def _extract_stage_names(growth_stages) -> list[str]:
        stages: list[str] = []
        if isinstance(growth_stages, dict):
            growth_stages = growth_stages.get("growth_stage") or growth_stages.get("stages") or []
        if isinstance(growth_stages, list):
            for s in growth_stages:
                name = s.get("stage") if isinstance(s, dict) else None
                if name:
                    stages.append(str(name))
        return stages

    @staticmethod
    def _find_stage_details(growth_stages, stage_name):
        if not growth_stages or not stage_name:
            return None
        target = _normalize_stage(stage_name)
        stages = growth_stages
        if isinstance(growth_stages, dict):
            stages = growth_stages.get("growth_stage") or growth_stages.get("stages") or []
        if not isinstance(stages, list):
            return None
        for s in stages:
            if isinstance(s, dict) and _normalize_stage(s.get("stage")) == target:
                return s
        return None

    @staticmethod
    def _find_stage_conditions(growth_stages, stage_name):
        if not growth_stages or not stage_name:
            return {}
        target = _normalize_stage(stage_name)
        try:
            for s in growth_stages:
                if _normalize_stage(s.get("stage", "")) == target:
                    return s.get("conditions", {}) or {}
        except (KeyError, TypeError, AttributeError):
            return {}
        return {}

    @staticmethod
    def _hours_until_time(start_time: str | None) -> int | None:
        if not start_time:
            return None
        try:
            target = datetime.strptime(start_time, "%H:%M")
        except ValueError:
            return None
        now = datetime.now()
        scheduled = now.replace(hour=target.hour, minute=target.minute, second=0, microsecond=0)
        if scheduled <= now:
            scheduled += timedelta(days=1)
        return max(0, int((scheduled - now).total_seconds() // 3600))

    @staticmethod
    def _schedule_days(payload: dict | None) -> list[int]:
        if not payload or payload.get("enabled") is False:
            return []
        days = payload.get("days_of_week") or payload.get("days")
        if isinstance(days, list):
            result: list[int] = []
            for entry in days:
                try:
                    result.append(int(entry))
                except (TypeError, ValueError):
                    continue
            return result
        return list(range(7))

    @staticmethod
    def _parse_date_value(value) -> datetime | None:
        if value is None:
            return None
        if isinstance(value, datetime):
            return _ensure_utc(value)
        try:
            from datetime import date as date_type

            if isinstance(value, date_type):
                return datetime(value.year, value.month, value.day, tzinfo=UTC)
        except (TypeError, ValueError, AttributeError):
            pass
        if isinstance(value, str):
            return coerce_datetime(value)
        return None
