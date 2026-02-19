"""
Plant Sensor Controller
=======================

Handles plant sensor events (soil moisture, pH, EC) and delegates irrigation
decisions to IrrigationWorkflowService. Keeps ClimateController focused on
environment sensors only.

Architecture:
- Inherits throttling logic from ThrottledAnalyticsWriter
- Manages plant-specific sensors: soil_moisture, ph, ec
- Persists to PlantReadings table (not SensorReading)
- Delegates irrigation detection to IrrigationWorkflowService

Note:
    Irrigation is user-controlled via IrrigationWorkflowService.
    The soil moisture PID controller has been removed - users decide when to water.

Author: Sebastian Gomez
Date: 2024
Updated: January 2026 - Moved to app.control_loops package
"""

from __future__ import annotations

import contextlib
import logging
from typing import Any, Callable

from app.control_loops.throttle_config import ThrottleConfig
from app.control_loops.throttled_analytics_writer import ThrottledAnalyticsWriter
from app.enums import IrrigationEligibilityDecision, IrrigationSkipReason, NotificationSeverity
from app.enums.events import NotificationEvent, SensorEvent
from app.utils.event_bus import EventBus
from app.utils.psychrometrics import calculate_vpd_kpa
from app.utils.time import iso_now

logger = logging.getLogger(__name__)


class PlantSensorController(ThrottledAnalyticsWriter):
    """
    Per-unit controller for plant sensor events and irrigation detection.

    Persists plant sensor data to PlantReadings table.
    Environment sensors are handled by ClimateController -> SensorReading table.

    Note:
        Irrigation is user-controlled. This controller detects when irrigation
        might be needed and notifies the user, but does not control it via PID.
    """

    # Metrics managed by this controller
    MANAGED_METRICS: set[str] = {"soil_moisture", "ph", "ec"}

    def __init__(
        self,
        *,
        unit_id: int,
        analytics_repo: Any,
        irrigation_workflow_service: Any,
        plant_context_resolver: Callable[..., dict[str, Any]] | None = None,
        threshold_service: Any | None = None,
        event_bus: EventBus | None = None,
        throttle_config: ThrottleConfig | None = None,
    ) -> None:
        # Initialize base class
        super().__init__(
            unit_id=unit_id,
            event_bus=event_bus,
            throttle_config=throttle_config,
        )

        self._unsubscribe_callbacks: list[Callable[[], None]] = []

        self.analytics_repo = analytics_repo
        self.irrigation_workflow_service = irrigation_workflow_service
        self.plant_context_resolver = plant_context_resolver
        self.threshold_service = threshold_service

        # Subscribe to events immediately (maintains existing behavior)
        self._subscribe_to_events()
        self._subscribed = True
        logger.info("PlantSensorController initialized for unit %s", self.unit_id)

    def _get_managed_metrics(self) -> set[str]:
        """Return set of metric names managed by this controller."""
        return self.MANAGED_METRICS

    def _subscribe_to_events(self) -> None:
        """Subscribe to plant sensor events."""
        self._unsubscribe_from_events()
        self._unsubscribe_callbacks = [
            self.event_bus.subscribe(SensorEvent.SOIL_MOISTURE_UPDATE, self.on_soil_moisture_update),
            self.event_bus.subscribe(SensorEvent.PH_UPDATE, self.on_ph_update),
            self.event_bus.subscribe(SensorEvent.EC_UPDATE, self.on_ec_update),
        ]
        logger.debug("PlantSensorController subscribed to events for unit %s", self.unit_id)

    def _unsubscribe_from_events(self) -> None:
        """Unsubscribe from plant sensor events."""
        for unsubscribe in self._unsubscribe_callbacks:
            try:
                unsubscribe()
            except Exception:
                continue
        self._unsubscribe_callbacks = []
        logger.debug("PlantSensorController unsubscribed from events for unit %s", self.unit_id)

    # ==================== Context Resolution ====================

    def _resolve_context(self, sensor_id: int | None) -> dict[str, Any]:
        """Resolve plant context for a sensor."""
        if not self.plant_context_resolver or sensor_id is None:
            return {}
        try:
            return self.plant_context_resolver(unit_id=self.unit_id, sensor_id=int(sensor_id)) or {}
        except Exception as exc:
            logger.debug("Plant context resolution failed for sensor %s: %s", sensor_id, exc, exc_info=True)
            return {}

    def _resolve_threshold(self, context: dict[str, Any]) -> float | None:
        """Extract target moisture threshold from context."""
        value = context.get("target_moisture")
        if value is not None:
            try:
                return float(value)
            except (TypeError, ValueError):
                return None
        return None

    # ==================== Irrigation Workflow ====================

    def _record_skip(
        self,
        *,
        sensor_id: int | None,
        plant_id: int | None,
        moisture: float | None,
        threshold: float | None,
        reason: IrrigationSkipReason,
    ) -> None:
        """Record an irrigation eligibility skip in the trace log."""
        if not self.irrigation_workflow_service:
            return
        self.irrigation_workflow_service.record_eligibility_trace(
            unit_id=self.unit_id,
            plant_id=plant_id,
            sensor_id=sensor_id,
            moisture=moisture,
            threshold=threshold,
            decision=IrrigationEligibilityDecision.SKIP,
            skip_reason=reason,
        )

    def _get_latest_environment_snapshot(self) -> dict[str, float | None]:
        """Fetch latest environment readings for irrigation context enrichment."""
        if not self.analytics_repo:
            return {}
        try:
            return self.analytics_repo.get_latest_sensor_readings(self.unit_id) or {}
        except Exception as exc:
            logger.debug("Failed to fetch latest environment snapshot: %s", exc, exc_info=True)
            return {}

    def _evaluate_irrigation(
        self,
        *,
        moisture: float,
        sensor_id: int | None,
        reading_timestamp: str | None,
        context: dict[str, Any],
    ) -> None:
        """Evaluate if irrigation should be triggered and delegate to workflow service."""
        if not self.irrigation_workflow_service:
            return

        threshold = self._resolve_threshold(context)
        plant_id = context.get("plant_id")

        if threshold is None:
            self._record_skip(
                sensor_id=sensor_id,
                plant_id=plant_id,
                moisture=moisture,
                threshold=None,
                reason=IrrigationSkipReason.NO_SENSOR,
            )
            return

        if moisture >= float(threshold):
            self._record_skip(
                sensor_id=sensor_id,
                plant_id=plant_id,
                moisture=moisture,
                threshold=threshold,
                reason=IrrigationSkipReason.HYSTERESIS_NOT_MET,
            )
            return

        actuator_id = context.get("actuator_id")
        if actuator_id is None:
            self._record_skip(
                sensor_id=sensor_id,
                plant_id=plant_id,
                moisture=moisture,
                threshold=threshold,
                reason=IrrigationSkipReason.NO_ACTUATOR,
            )
            return

        env_snapshot = self._get_latest_environment_snapshot()
        temperature = env_snapshot.get("temperature")
        humidity = env_snapshot.get("humidity")
        vpd = None
        if temperature is not None and humidity is not None:
            try:
                vpd = calculate_vpd_kpa(float(temperature), float(humidity))
            except Exception:
                vpd = None

        user_id = context.get("user_id")
        if user_id is None:
            self._record_skip(
                sensor_id=sensor_id,
                plant_id=plant_id,
                moisture=moisture,
                threshold=threshold,
                reason=IrrigationSkipReason.REQUEST_CREATE_FAILED,
            )
            return

        self.irrigation_workflow_service.detect_irrigation_need(
            unit_id=self.unit_id,
            soil_moisture=float(moisture),
            threshold=float(threshold),
            user_id=int(user_id),
            plant_id=plant_id,
            actuator_id=actuator_id,
            sensor_id=sensor_id,
            reading_timestamp=reading_timestamp,
            plant_name=context.get("plant_name"),
            plant_pump_assigned=bool(context.get("plant_pump_assigned")),
            temperature=temperature,
            humidity=humidity,
            vpd=vpd,
            lux=env_snapshot.get("lux"),
            plant_type=context.get("plant_type"),
            growth_stage=context.get("growth_stage"),
        )

    # ==================== Event Handlers ====================

    def on_soil_moisture_update(self, data: dict[str, Any]) -> None:
        """Handle soil moisture updates and trigger irrigation workflow."""
        if not self._is_for_this_unit(data):
            return

        moisture = data.get("soil_moisture")
        sensor_id = data.get("sensor_id")
        if moisture is None or sensor_id is None:
            return

        context = self._resolve_context(sensor_id)
        self._evaluate_irrigation(
            moisture=float(moisture),
            sensor_id=int(sensor_id) if sensor_id is not None else None,
            reading_timestamp=data.get("timestamp"),
            context=context,
        )

        payload = dict(data)
        if context.get("plant_id") is not None:
            payload["plant_id"] = context.get("plant_id")
        self._log_analytics_data(payload, {"soil_moisture"})

    def on_ph_update(self, data: dict[str, Any]) -> None:
        """Handle pH updates and alert on out-of-range values."""
        if not self._is_for_this_unit(data):
            return

        ph = data.get("ph")
        sensor_id = data.get("sensor_id")
        if ph is None or sensor_id is None:
            return

        ph_val = float(ph)
        self._check_ph_thresholds(ph_val, sensor_id)

        context = self._resolve_context(sensor_id)
        payload = dict(data)
        if context.get("plant_id") is not None:
            payload["plant_id"] = context.get("plant_id")
        self._log_analytics_data(payload, {"ph"})

    def on_ec_update(self, data: dict[str, Any]) -> None:
        """Handle EC updates and alert on out-of-range values."""
        if not self._is_for_this_unit(data):
            return

        ec = data.get("ec")
        sensor_id = data.get("sensor_id")
        if ec is None or sensor_id is None:
            return

        ec_val = float(ec)
        self._check_ec_thresholds(ec_val, sensor_id)

        context = self._resolve_context(sensor_id)
        payload = dict(data)
        if context.get("plant_id") is not None:
            payload["plant_id"] = context.get("plant_id")
        self._log_analytics_data(payload, {"ec"})

    # ==================== Alert Threshold Checking ====================

    def _check_ph_thresholds(self, ph_val: float, sensor_id: Any) -> None:
        """Check pH value against configurable thresholds and publish alerts."""
        cfg = self.throttle_config

        # Check if outside warning range
        if ph_val < cfg.ph_warning_min or ph_val > cfg.ph_warning_max:
            # Determine severity based on critical thresholds
            is_critical = ph_val < cfg.ph_critical_min or ph_val > cfg.ph_critical_max

            self.event_bus.publish(
                NotificationEvent.PLANT_HEALTH_WARNING,
                {
                    "unit_id": self.unit_id,
                    "sensor_id": sensor_id,
                    "metric": "ph",
                    "value": ph_val,
                    "message": f"pH Level out of safe range: {ph_val:.2f}",
                    "severity": NotificationSeverity.CRITICAL if is_critical else NotificationSeverity.WARNING,
                },
            )

    def _check_ec_thresholds(self, ec_val: float, sensor_id: Any) -> None:
        """Check EC value against configurable thresholds and publish alerts."""
        cfg = self.throttle_config

        # Check if above warning threshold
        if ec_val > cfg.ec_warning_max:
            is_critical = ec_val > cfg.ec_critical_max

            self.event_bus.publish(
                NotificationEvent.PLANT_HEALTH_WARNING,
                {
                    "unit_id": self.unit_id,
                    "sensor_id": sensor_id,
                    "metric": "ec",
                    "value": ec_val,
                    "message": f"EC (Nutrient) Concentration too high: {ec_val:.2f} mS/cm",
                    "severity": NotificationSeverity.CRITICAL if is_critical else NotificationSeverity.WARNING,
                },
            )

    # ==================== Analytics Persistence ====================

    def _log_analytics_data(self, data: dict[str, Any], metrics: set[str]) -> None:
        """
        Log plant sensor data to PlantReadings table with throttling.

        Note: This persists to PlantReadings (plant-specific), not SensorReading
        (environment sensors handled by ClimateController).
        """
        sensor_id = data.get("sensor_id")
        if sensor_id is None or not self.analytics_repo:
            return

        # Extract metrics to save
        savable_metrics: dict[str, Any] = {}
        for metric in metrics:
            value = data.get(metric)
            if value is not None:
                savable_metrics[metric] = value

        if not savable_metrics:
            return

        # Update latest reading cache (always, for UI)
        for metric, value in savable_metrics.items():
            self._update_latest_reading(metric, value)

        # Apply throttling
        if self.throttle_config.throttling_enabled:
            savable_metrics = self._filter_throttled_metrics(savable_metrics)
            if not savable_metrics:
                return

        # Require plant_id for PlantReadings
        plant_id = data.get("plant_id")
        if plant_id is None:
            logger.debug("Skipping plant sensor persistence: no plant_id for unit %s", self.unit_id)
            return

        try:
            # Record storage timestamps and baselines
            for metric, value in savable_metrics.items():
                with contextlib.suppress(TypeError, ValueError):
                    self._record_metric_stored(metric, float(value))

            # Persist to PlantReadings table
            if self.MANAGED_METRICS & savable_metrics.keys():
                self.analytics_repo.save_plant_reading(
                    unit_id=self.unit_id,
                    plant_id=plant_id,
                    soil_moisture=self._get_latest_reading("soil_moisture"),
                    ph=self._get_latest_reading("ph"),
                    ec=self._get_latest_reading("ec"),
                    timestamp=iso_now(),
                )
        except Exception as exc:
            logger.error("Failed to log plant sensor analytics: %s", exc)
