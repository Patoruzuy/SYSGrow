"""
Throttled Analytics Writer Base Class
======================================

Provides shared throttling logic for sensor data persistence to avoid
duplication between ClimateController and PlantSensorController.

Author: Sebastian Gomez
Date: January 2026
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Any

from app.controllers.throttle_config import DEFAULT_THROTTLE_CONFIG, ThrottleConfig
from app.utils.event_bus import EventBus
from app.utils.time import utc_now

logger = logging.getLogger(__name__)


class ThrottledAnalyticsWriter(ABC):
    """
    Base class for controllers that write throttled sensor data to analytics.

    Provides common functionality:
    - Unit-based event filtering
    - Metric throttling (time-based and change-based)
    - Live reading cache management
    - Event subscription lifecycle management

    Subclasses must implement:
    - _get_managed_metrics(): Return set of metric names this controller manages
    - _subscribe_to_events(): Subscribe to relevant EventBus events
    - _unsubscribe_from_events(): Unsubscribe from EventBus events
    """

    # Metrics managed by this controller (override in subclass)
    MANAGED_METRICS: set[str] = set()

    def __init__(
        self,
        *,
        unit_id: int,
        event_bus: EventBus | None = None,
        throttle_config: ThrottleConfig | None = None,
    ) -> None:
        self.unit_id = int(unit_id)
        self.event_bus = event_bus or EventBus.get_instance()
        self.throttle_config = throttle_config or DEFAULT_THROTTLE_CONFIG

        # Dynamically create throttle state for managed metrics
        self._init_throttle_state()

        # Lifecycle state
        self._subscribed = False

    def _init_throttle_state(self) -> None:
        """Initialize throttle state attributes for managed metrics."""
        for metric in self._get_managed_metrics():
            # Last insert timestamp
            setattr(self, f"last_{metric}_insert", None)
            # Last stored baseline value
            setattr(self, f"last_stored_{metric}", None)
            # Latest reading cache (for UI)
            setattr(self, f"latest_reading_{metric}", None)

    @abstractmethod
    def _get_managed_metrics(self) -> set[str]:
        """Return set of metric names managed by this controller."""
        ...

    @abstractmethod
    def _subscribe_to_events(self) -> None:
        """Subscribe to relevant EventBus events."""
        ...

    @abstractmethod
    def _unsubscribe_from_events(self) -> None:
        """Unsubscribe from EventBus events."""
        ...

    def start(self) -> None:
        """Start the controller by subscribing to events."""
        if not self._subscribed:
            self._subscribe_to_events()
            self._subscribed = True
            logger.info("%s started for unit %s", self.__class__.__name__, self.unit_id)

    def stop(self) -> None:
        """Stop the controller by unsubscribing from events."""
        if self._subscribed:
            self._unsubscribe_from_events()
            self._subscribed = False
            logger.info("%s stopped for unit %s", self.__class__.__name__, self.unit_id)

    def _is_for_this_unit(self, data: dict[str, Any]) -> bool:
        """Return True if an incoming sensor event targets this controller's unit."""
        try:
            event_unit_id = data.get("unit_id")
            return event_unit_id is not None and int(event_unit_id) == self.unit_id
        except Exception:
            return False

    def _update_latest_reading(self, metric: str, value: Any) -> None:
        """Update the latest reading cache for a metric."""
        attr_name = f"latest_reading_{metric}"
        if hasattr(self, attr_name):
            setattr(self, attr_name, value)

    def _get_latest_reading(self, metric: str) -> float | None:
        """Get the latest reading for a metric."""
        return getattr(self, f"latest_reading_{metric}", None)

    def _should_store_metric(self, metric: str, value: float) -> bool:
        """
        Throttling logic for a single metric.
        Returns True if data SHOULD be stored, False if throttled.
        """
        now = utc_now()
        last_insert: datetime | None = getattr(self, f"last_{metric}_insert", None)

        # 1. Check time interval
        interval_mins = getattr(self.throttle_config, f"{metric}_interval_minutes", 5)
        time_elapsed = last_insert is None or (now - last_insert) >= timedelta(minutes=interval_mins)

        if not self.throttle_config.use_hybrid_strategy:
            return time_elapsed

        # 2. Check for significant change relative to last stored baseline
        baseline_val: float | None = getattr(self, f"last_stored_{metric}", None)

        # Fallback to latest_reading for first run
        if baseline_val is None:
            baseline_val = getattr(self, f"latest_reading_{metric}", None)

        if baseline_val is None:
            return True

        threshold = self._get_change_threshold(metric)
        significant_change = abs(value - baseline_val) >= threshold

        if self.throttle_config.debug_logging:
            logger.debug(
                "Throttle decision for %s: time_elapsed=%s, significant_change=%s (value=%.2f, baseline=%.2f, threshold=%.2f)",
                metric,
                time_elapsed,
                significant_change,
                value,
                baseline_val,
                threshold,
            )

        return time_elapsed or significant_change

    def _get_change_threshold(self, metric: str) -> float:
        """
        Get the change threshold for a metric from throttle config.
        Maps metric names to their threshold attribute names.
        """
        threshold_map = {
            "temperature": "temp_change_threshold_celsius",
            "humidity": "humidity_change_threshold_percent",
            "soil_moisture": "soil_moisture_change_threshold_percent",
            "co2": "co2_change_threshold_ppm",
            "voc": "voc_change_threshold_ppb",
            "air_quality": "air_quality_change_threshold",
            "lux": "light_change_threshold_lux",
            "pressure": "pressure_change_threshold_hpa",
            "ph": "ph_change_threshold",
            "ec": "ec_change_threshold_us_cm",
        }

        threshold_attr = threshold_map.get(metric, f"{metric}_change_threshold")
        return getattr(self.throttle_config, threshold_attr, 0.1)

    def _record_metric_stored(self, metric: str, value: float) -> None:
        """Record that a metric was stored (update timestamps and baselines)."""
        now = utc_now()
        setattr(self, f"last_{metric}_insert", now)
        setattr(self, f"last_stored_{metric}", value)

    def _filter_throttled_metrics(
        self,
        metrics: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Filter metrics based on throttling rules.
        Returns only metrics that should be stored.
        """
        if not self.throttle_config.throttling_enabled:
            return metrics

        result = {}
        for metric, value in metrics.items():
            if value is None:
                continue
            try:
                if self._should_store_metric(metric, float(value)):
                    result[metric] = value
            except (TypeError, ValueError):
                # Non-numeric value, include it
                result[metric] = value

        return result

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
