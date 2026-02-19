"""
ClimateController: Manages all environmental factors in the grow tent.

Enhanced with:
- Dependency injection for better testability
- Configurable control parameters
- Health monitoring and metrics tracking
- Decoupled from ControlLogic creation

Author: Sebastian Gomez
Date: 2024
Updated: November 2024 - Enhanced architecture
Updated: January 2026 - Moved to app.control_loops package
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from functools import wraps
from time import perf_counter
from typing import TYPE_CHECKING, Any

from app.control_loops.throttle_config import DEFAULT_THROTTLE_CONFIG, ThrottleConfig
from app.enums.events import RuntimeEvent, SensorEvent
from app.utils.event_bus import EventBus
from app.utils.time import iso_now, utc_now

if TYPE_CHECKING:
    from app.control_loops.control_logic import ControlLogic
    from infrastructure.database.repositories.analytics import AnalyticsRepository

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetric:
    count: int = 0
    total_ms: float = 0.0
    min_ms: float | None = None
    max_ms: float | None = None

    def record(self, elapsed_ms: float) -> None:
        self.count += 1
        self.total_ms += elapsed_ms
        self.min_ms = elapsed_ms if self.min_ms is None else min(self.min_ms, elapsed_ms)
        self.max_ms = elapsed_ms if self.max_ms is None else max(self.max_ms, elapsed_ms)

    @property
    def avg_ms(self) -> float:
        return self.total_ms / self.count if self.count else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "count": self.count,
            "total_ms": self.total_ms,
            "min_ms": self.min_ms,
            "max_ms": self.max_ms,
            "avg_ms": self.avg_ms,
        }


@dataclass
class PerformanceMetrics:
    metrics: dict[str, PerformanceMetric] = field(default_factory=dict)

    def record(self, name: str, elapsed_ms: float) -> None:
        metric = self.metrics.get(name)
        if metric is None:
            metric = PerformanceMetric()
            self.metrics[name] = metric
        metric.record(elapsed_ms)

    def to_dict(self) -> dict[str, Any]:
        return {name: metric.to_dict() for name, metric in self.metrics.items()}


def track_performance(name: str):
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            start = perf_counter()
            try:
                return func(self, *args, **kwargs)
            finally:
                elapsed_ms = (perf_counter() - start) * 1000.0
                if hasattr(self, "performance_metrics"):
                    self.performance_metrics.record(name, elapsed_ms)

        return wrapper

    return decorator


class ClimateController:
    """
    ClimateController manages environmental factors in the grow tent.

    Responsibilities:
    - Routing: Subscribers to EventBus and routes to ControlLogic.
    - Analytics: Filters and throttles sensor data for DB storage.
    - Health: Monitors loop frequency and sensor staleness.

    Note:
        Plant sensors (soil_moisture, ph, ec) are handled by PlantSensorController.
        Irrigation is user-controlled via IrrigationWorkflowService, not PID-controlled.
    """

    def __init__(
        self,
        unit_id: int,
        control_logic: "ControlLogic",
        polling_service: Any,
        analytics_repo: "AnalyticsRepository",
        event_bus: EventBus | None = None,
        throttle_config: ThrottleConfig | None = None,
    ):
        """
        Initialize the ClimateController with dependency injection.

        Args:
            unit_id: Growth unit identifier that this controller manages
            control_logic: ControlLogic instance for actuator control
            polling_service: Service for polling sensors
            analytics_repo: Analytics repository for storing sensor history
            event_bus: Optional EventBus instance (creates new if not provided)
            throttle_config: Optional throttle configuration (uses defaults if not provided)

        Note:
            Primary sensor filtering is done by CompositeProcessor before events reach this service.
            Plant sensors (soil_moisture, ph, ec) are handled by PlantSensorController.
        """
        self.unit_id = unit_id
        self.event_bus = event_bus or EventBus().get_instance()
        self.control_logic = control_logic
        self.polling_service = polling_service
        self.analytics_repo = analytics_repo
        self.throttle_config = throttle_config or DEFAULT_THROTTLE_CONFIG

        self.performance_metrics = PerformanceMetrics()
        self._primary_log_last: dict[str, datetime] = {}

        # Throttling state tracking (per-metric intervals)
        # Note: soil_moisture, ph, ec are handled by PlantSensorController
        self.last_temperature_insert: datetime | None = None
        self.last_humidity_insert: datetime | None = None
        self.last_co2_insert: datetime | None = None
        self.last_voc_insert: datetime | None = None
        self.last_air_quality_insert: datetime | None = None
        self.last_lux_insert: datetime | None = None
        self.last_pressure_insert: datetime | None = None

        # Persistence Baselines: The actual values last stored in the Database.
        # Note: soil_moisture, ph, ec are handled by PlantSensorController
        self.last_stored_temperature: float | None = None
        self.last_stored_humidity: float | None = None
        self.last_stored_co2: float | None = None
        self.last_stored_voc: float | None = None
        self.last_stored_air_quality: float | None = None
        self.last_stored_lux: float | None = None
        self.last_stored_pressure: float | None = None

        # Real-time Cache: The most recent received values (regardless of throttling).
        # Note: soil_moisture, ph, ec are handled by PlantSensorController
        self.latest_reading_temperature: float | None = None
        self.latest_reading_humidity: float | None = None
        self.latest_reading_co2: float | None = None
        self.latest_reading_voc: float | None = None
        self.latest_reading_air_quality: float | None = None
        self.latest_reading_lux: float | None = None
        self.latest_reading_pressure: float | None = None

        # Health monitoring
        self.sensor_update_counts: dict[str, int] = {}
        self.last_sensor_update: dict[str, datetime] = {}
        self.control_action_counts: dict[str, int] = {}
        self.started = False

        # Subscribe to relevant sensor update events
        self._subscribe_to_events()
        self.last_thresholds_update: dict[str, Any] | None = None

        logger.info("ClimateController initialized with dependency injection")

    def _log_primary_metric(self, metric: str, sensor_id: Any) -> None:
        if not self.throttle_config.debug_logging:
            return
        now = utc_now()
        last = self._primary_log_last.get(metric)
        if last and (now - last).total_seconds() < 60:
            return
        self._primary_log_last[metric] = now
        logger.debug(
            "Primary metric update (unit=%s metric=%s sensor=%s)",
            self.unit_id,
            metric,
            sensor_id,
        )

    def _is_for_this_unit(self, data: dict[str, Any]) -> bool:
        """Return True if an incoming sensor event targets this controller's unit."""
        try:
            event_unit_id = data.get("unit_id")
            return event_unit_id is not None and int(event_unit_id) == int(self.unit_id)
        except Exception:
            return False

    def _subscribe_to_events(self):
        """Subscribe to sensor update events."""
        self.event_bus.subscribe(SensorEvent.TEMPERATURE_UPDATE, self.on_temperature_update)
        self.event_bus.subscribe(SensorEvent.HUMIDITY_UPDATE, self.on_humidity_update)
        self.event_bus.subscribe(SensorEvent.CO2_UPDATE, self.on_co2_update)
        self.event_bus.subscribe(SensorEvent.VOC_UPDATE, self.on_voc_update)
        self.event_bus.subscribe(SensorEvent.LIGHT_UPDATE, self.on_light_update)
        self.event_bus.subscribe(SensorEvent.PRESSURE_UPDATE, self.on_pressure_update)
        self.event_bus.subscribe(SensorEvent.AIR_QUALITY_UPDATE, self.on_air_quality_update)
        self.event_bus.subscribe(RuntimeEvent.THRESHOLDS_UPDATE, self.on_thresholds_update)
        logger.info("Subscribed to sensor update events")

    @track_performance("on_thresholds_update")
    def on_thresholds_update(self, data: dict[str, Any]) -> None:
        """Handle threshold updates (store/acknowledge)."""
        try:
            if not isinstance(data, dict) or not self._is_for_this_unit(data):
                return

            thresholds = data.get("thresholds", data)
            if not isinstance(thresholds, dict):
                return

            updates: dict[str, Any] = {}
            threshold_mapping = {
                "temperature_threshold": "temperature",
                "humidity_threshold": "humidity",
                "co2_threshold": "co2",
                "voc_threshold": "voc",
                "lux_threshold": "lux",
                "air_quality_threshold": "air_quality",
            }

            for key, metric in threshold_mapping.items():
                if key in thresholds:
                    updates[metric] = thresholds[key]

            if updates:
                self.control_logic.update_thresholds(updates)

            self.last_thresholds_update = thresholds
            logger.info("Thresholds update received: %s", thresholds)
        except Exception as exc:
            logger.warning("Failed to process thresholds_update: %s", exc)

    @track_performance("on_temperature_update")
    def on_temperature_update(self, data: dict[str, Any]) -> None:
        """Handle temperature/humidity sensor updates."""
        if not self._is_for_this_unit(data):
            return

        temp = data.get("temperature")
        sensor_id = data.get("sensor_id")

        if temp is not None:
            self._log_primary_metric("temperature", sensor_id)
            self._track_sensor_update("temperature", sensor_id)
            if self.control_logic.control_temperature(
                {"unit_id": self.unit_id, "temperature": temp, "sensor_id": sensor_id}
            ):
                self._track_control_action("temperature")

        self._log_analytics_data(data, {"temperature", "humidity"})

    @track_performance("on_humidity_update")
    def on_humidity_update(self, data: dict[str, Any]) -> None:
        """Handle humidity updates (often grouped with temp)."""
        if not self._is_for_this_unit(data):
            return

        hum = data.get("humidity")
        sensor_id = data.get("sensor_id")

        if hum is not None:
            self._log_primary_metric("humidity", sensor_id)
            self._track_sensor_update("humidity", sensor_id)
            if self.control_logic.control_humidity({"unit_id": self.unit_id, "humidity": hum, "sensor_id": sensor_id}):
                self._track_control_action("humidity")

        self._log_analytics_data(data, {"humidity"})

    @track_performance("on_co2_update")
    def on_co2_update(self, data: dict[str, Any]) -> None:
        """Handle CO2/VOC updates."""
        if not self._is_for_this_unit(data):
            return

        co2 = data.get("co2")
        sensor_id = data.get("sensor_id")

        if co2 is not None:
            self._log_primary_metric("co2", sensor_id)
            self._track_sensor_update("co2", sensor_id)
            if self.control_logic.control_co2({"unit_id": self.unit_id, "co2": co2, "sensor_id": sensor_id}):
                self._track_control_action("co2")

        if data.get("voc") is not None:
            self._log_primary_metric("voc", sensor_id)
            self._track_sensor_update("voc", sensor_id)

        self._log_analytics_data(data, {"co2", "voc"})

    @track_performance("on_voc_update")
    def on_voc_update(self, data: dict[str, Any]) -> None:
        """Handle VOC updates."""
        self.on_co2_update(data)

    @track_performance("on_light_update")
    def on_light_update(self, data: dict[str, Any]) -> None:
        """Handle light updates - writes directly to ledger."""
        if not self._is_for_this_unit(data):
            return

        lux = data.get("lux")
        sensor_id = data.get("sensor_id")

        if lux is not None:
            self._log_primary_metric("lux", sensor_id)
            self._track_sensor_update("lux", sensor_id)
            if self.control_logic.control_lux({"unit_id": self.unit_id, "lux": lux, "sensor_id": sensor_id}):
                self._track_control_action("lux")

            self._log_analytics_data(data, {"lux"})

    @track_performance("on_pressure_update")
    def on_pressure_update(self, data: dict[str, Any]) -> None:
        """Handle pressure updates - writes directly to ledger."""
        if not self._is_for_this_unit(data):
            return

        pressure = data.get("pressure")
        sensor_id = data.get("sensor_id")

        if pressure is not None:
            self._log_primary_metric("pressure", sensor_id)
            self._track_sensor_update("pressure", sensor_id)
            # TODO: Implement notification/alert/widget update for pressure thresholds
            self._log_analytics_data(data, {"pressure"})

    @track_performance("on_air_quality_update")
    def on_air_quality_update(self, data: dict[str, Any]) -> None:
        """Handle air quality index updates."""
        if self._is_for_this_unit(data) and data.get("air_quality") is not None:
            self._log_primary_metric("air_quality", data.get("sensor_id"))
            self._track_sensor_update("air_quality", data.get("sensor_id"))
            # TODO: Implement notification/alert/widget update for Air Quality thresholds
            self._log_analytics_data(data, {"air_quality"})

    def _track_sensor_update(self, sensor_type: str, sensor_id: Any):
        """Track sensor update for health monitoring."""
        key = f"{sensor_type}_{sensor_id}"
        self.sensor_update_counts[key] = self.sensor_update_counts.get(key, 0) + 1
        self.last_sensor_update[key] = utc_now()

    def _track_control_action(self, control_type: str):
        """Track control action for health monitoring."""
        self.control_action_counts[control_type] = self.control_action_counts.get(control_type, 0) + 1

    @track_performance("_log_analytics_data")
    def _log_analytics_data(self, data: dict[str, Any], metrics: set[str]) -> None:
        """
        Unified method to log sensor data to analytics repository with throttling.

        Note: Primary sensor filtering is already done by CompositeProcessor._build_controller_events()
        before events reach this service. All metrics in the event payload are pre-filtered.
        """
        sensor_id = data.get("sensor_id")
        if sensor_id is None:
            return

        # 1. Extract savable metrics (already filtered by CompositeProcessor)
        savable_metrics = {}
        for k, v in data.items():
            if v is None or k in ["unit_id", "sensor_id", "timestamp"]:
                continue
            if k not in metrics:
                continue
            savable_metrics[k] = v

        if not savable_metrics:
            return

        # 2. Update Live Cache (Always - for UI and Snapshot enrichment)
        for metric, value in savable_metrics.items():
            if self.throttle_config.debug_logging:
                logger.debug("Updating latest reading cache: %s = %s", metric, value)
            attr_name = f"latest_reading_{metric}"
            if hasattr(self, attr_name):
                setattr(self, attr_name, value)

        # 3. Check Throttling (User Preference: Time vs Percentage)
        if self.throttle_config.throttling_enabled:
            per_metric_store: dict[str, bool] = {}
            for metric, value in savable_metrics.items():
                per_metric_store[metric] = self._should_store_metric(metric, value)

            savable_metrics = {
                metric: value for metric, value in savable_metrics.items() if per_metric_store.get(metric)
            }

            if not savable_metrics:
                if self.throttle_config.debug_logging:
                    logger.debug("Throttled ledger record for sensor %s", sensor_id)
                return

        # 4. Persistence
        try:
            now = utc_now()
            logger.info("Storing analytics data (metrics=%s): %s", list(savable_metrics.keys()), savable_metrics)
            # THE LEDGER: Write raw sensor reading (Throttled Hardware Audit)
            self.analytics_repo.insert_sensor_reading(
                sensor_id=sensor_id, reading_data=savable_metrics, timestamp=iso_now()
            )
            for metric in savable_metrics:
                setattr(self, f"last_{metric}_insert", now)

            # Update baseline values (Only when stored) to prevent baseline drift
            for metric, value in savable_metrics.items():
                attr_name = f"last_stored_{metric}"
                if hasattr(self, attr_name):
                    setattr(self, attr_name, value)

        except Exception as exc:
            logger.error("Failed to log analytics data: %s", exc)

    def _should_store_metric(self, metric: str, value: float) -> bool:
        """
        Throttling logic for a single metric.
        Returns True if data SHOULD be stored, False if throttled.
        """
        now = utc_now()
        last_insert = getattr(self, f"last_{metric}_insert", None)

        # 1. Check time interval
        interval_mins = getattr(self.throttle_config, f"{metric}_interval_minutes", 5)
        time_elapsed = last_insert is None or (now - last_insert) >= timedelta(minutes=interval_mins)

        if not self.throttle_config.use_hybrid_strategy:
            return time_elapsed

        # 2. Check for significant change relative to last stored baseline
        baseline_val = getattr(self, f"last_stored_{metric}", None)

        # Fallback to latest_reading for first run
        if baseline_val is None:
            baseline_val = getattr(self, f"latest_reading_{metric}", None)

        if baseline_val is None:
            return True

        threshold = self._get_change_threshold(metric)
        significant_change = abs(value - baseline_val) >= threshold

        if self.throttle_config.debug_logging:
            logger.debug(
                "Throttle decision for %s: time_elapsed=%s, significant_change=%s",
                metric,
                time_elapsed,
                significant_change,
            )

        return time_elapsed or significant_change

    def _get_change_threshold(self, metric: str) -> float:
        """
        Correctly map metric names to their threshold attributes.
        Note: Plant sensors (soil_moisture, ph, ec) are handled by PlantSensorController.
        """
        threshold_map = {
            "temperature": "temp_change_threshold_celsius",
            "humidity": "humidity_change_threshold_percent",
            "co2": "co2_change_threshold_ppm",
            "voc": "voc_change_threshold_ppb",
            "air_quality": "air_quality_change_threshold",
            "lux": "light_change_threshold_lux",
            "pressure": "pressure_change_threshold_hpa",
        }

        threshold_attr = threshold_map.get(metric, f"{metric}_change_threshold")
        return getattr(self.throttle_config, threshold_attr, 0.1)

    def start(self):
        """
        Start the polling service for all sensors.
        MQTT automatically handles incoming updates and reload triggers.
        """
        if not self.started:
            polling_started = self.polling_service.start_polling()
            self.started = True
            if polling_started:
                logger.info("ClimateController started - sensor polling active")
            else:
                logger.info("ClimateController started - sensor polling skipped (no pollable sensors)")
        else:
            logger.warning("ClimateController already started")

    def stop(self):
        """Stop the climate controller."""
        if self.started:
            self.polling_service.stop_polling()
            self.started = False
            logger.info("ClimateController stopped")
        else:
            logger.warning("ClimateController already stopped")

    def get_throttle_config(self) -> dict[str, Any]:
        """Get current throttle configuration."""
        return self.throttle_config.to_dict()

    def update_throttle_config(self, config_dict: dict[str, Any]) -> None:
        """Update throttle configuration at runtime."""
        current = self.throttle_config.to_dict()

        # Deep merge simplistic implementation
        for key, value in config_dict.items():
            if isinstance(value, dict) and key in current:
                current[key].update(value)
            else:
                current[key] = value

        self.throttle_config = ThrottleConfig.from_dict(current)
        logger.info("Throttle configuration updated for unit %s", self.unit_id)

    def get_health_status(self) -> dict[str, Any]:
        """Get comprehensive health status of climate control system."""
        now = utc_now()
        stale_sensors = [
            {"sensor": k, "age": (now - v).total_seconds()}
            for k, v in self.last_sensor_update.items()
            if (now - v).total_seconds() > 300
        ]

        return {
            "unit_id": self.unit_id,
            "started": self.started,
            "stale_sensors": stale_sensors,
            "control_metrics": self.control_logic.get_metrics(),
            "performance_metrics": self.performance_metrics.to_dict(),
            "last_stored": {
                "temp": self.latest_reading_temperature,
                "hum": self.latest_reading_humidity,
                "co2": self.latest_reading_co2,
                "lux": self.latest_reading_lux,
            },
        }

    def get_status(self) -> dict[str, Any]:
        """Get full system status including sub-services."""
        return {
            "controller": self.get_health_status(),
            "logic": self.control_logic.get_status(),
            "timestamp": iso_now(),
        }
