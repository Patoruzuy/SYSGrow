# app/services/hardware/sensor_polling_service.py
"""
Sensor Polling Service
======================
Periodically polls GPIO/I2C/SPI/ADC sensors with data processing pipeline.

Features:
- Periodic polling of local hardware sensors (I2C, ADC, SPI, OneWire)
- Data processor pipeline integration (Standardization -> Validation -> Calibration -> Transformation)
- EmitterService integration for WebSocket emission
- EventBus dispatch for automation and persistence
- Health tracking and exponential backoff for failed sensors

Note: MQTT-based sensors (Zigbee/ESP32) are handled by MQTTSensorService.
"""

import logging
import threading
import time
from datetime import datetime
from typing import Any

from app.domain.sensors.reading import SensorReading
from app.enums import SensorState
from app.hardware.sensors.processors.base_processor import IDataProcessor, ProcessorError
from app.utils.emitters import EmitterService
from app.utils.event_bus import EventBus
from app.utils.time import utc_now

logger = logging.getLogger(__name__)


class SensorHealth:
    """Tracks the operational state of a hardware sensor."""

    def __init__(self, sensor_id: int):
        self.sensor_id = sensor_id
        self.status = SensorState.UNKNOWN
        self.last_seen: datetime | None = None
        self.failure_count = 0
        self.last_error: str | None = None
        self.backoff_until: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "sensor_id": self.sensor_id,
            "status": self.status.value,
            "last_seen": self.last_seen.isoformat() if self.last_seen else None,
            "failure_count": self.failure_count,
            "last_error": self.last_error,
        }


class SensorPollingService:
    """
    Service for periodic sampling of locally-connected hardware sensors.

    This service manages the lifecycle of polling threads and orchestrates
    the flow from raw hardware voltage/data to processed engineering units.
    """

    def __init__(
        self,
        sensor_manager: Any,
        emitter: EmitterService,
        processor: IDataProcessor,
        poll_interval_s: int = 10,
        event_bus: EventBus | None = None,
    ):
        self.sensor_manager = sensor_manager
        self.emitter = emitter
        self.processor = processor
        self.poll_interval_s = max(1, int(poll_interval_s))
        self.event_bus = event_bus or EventBus()

        # State tracking
        self._health: dict[int, SensorHealth] = {}
        self._last_readings: dict[int, SensorReading] = {}

        # Concurrency control
        self._stop_event = threading.Event()
        self._worker_thread: threading.Thread | None = None
        self._is_running = False

        # Configuration for stability
        self.base_backoff_s = 5.0
        self.max_backoff_s = 600.0  # 10 minutes max retry interval

        logger.info(f"SensorPollingService initialized (interval={self.poll_interval_s}s)")

    # -------------------------------------------------------------------------
    # Lifecycle Management
    # -------------------------------------------------------------------------

    def start_polling(self) -> bool:
        """Starts the polling thread if suitable sensors are present."""
        if self._is_running:
            return True

        # Identify sensors that require local polling
        local_sensor_ids = self._get_local_sensors()
        if not local_sensor_ids:
            logger.info("No locally-attached sensors found (I2C/ADC/SPI/GPIO); skipping polling.")
            return False

        self._stop_event.clear()
        self._worker_thread = threading.Thread(target=self._polling_loop, name="HwSensorPoller", daemon=True)
        self._worker_thread.start()
        self._is_running = True

        logger.info(f"🚀 Started hardware polling for {len(local_sensor_ids)} sensors")
        return True

    def stop_polling(self) -> None:
        """Stops the polling thread gracefully."""
        if not self._is_running:
            return

        logger.info("🛑 Stopping hardware sensor polling...")
        self._stop_event.set()
        if self._worker_thread:
            self._worker_thread.join(timeout=5.0)

        self._is_running = False
        logger.info("Hardware sensor polling stopped")

    # -------------------------------------------------------------------------
    # Core Logic
    # -------------------------------------------------------------------------

    def _polling_loop(self) -> None:
        """Periodic loop that sweeps all registered local sensors."""
        while not self._stop_event.is_set():
            t_start = time.perf_counter()

            try:
                sensor_ids = self._get_local_sensors()
                for sid in sensor_ids:
                    if self._stop_event.is_set():
                        break

                    self._process_single_sensor(sid)
            except Exception as exc:
                logger.exception("Hardware polling loop encountered critical error: %s", exc)

            # Calculate remaining sleep to maintain consistent interval
            elapsed = time.perf_counter() - t_start
            sleep_time = max(0.1, self.poll_interval_s - elapsed)
            self._stop_event.wait(sleep_time)

    def _process_single_sensor(self, sensor_id: int) -> None:
        """Reads, processes, and dispatches data for one sensor."""
        health = self._get_health(sensor_id)

        # Check if sensor is in backoff period after failures
        if health.backoff_until and time.time() < health.backoff_until:
            return

        try:
            # 1. Hardware Read
            sensor = self.sensor_manager.get_sensor(sensor_id)
            if not sensor:
                return

            raw_reading = self.sensor_manager.read_sensor(sensor_id)
            if not raw_reading or not raw_reading.data:
                raise ValueError("No data returned from hardware layer")

            # 2. Pipeline Processing (Clean/Validate/Calibrate/Enrich)
            # We assume CompositeProcessor usage here
            reading = self.processor.process(sensor, raw_reading.data)

            # Preserve hardware-layer timestamp for accuracy
            if hasattr(raw_reading, "timestamp"):
                reading.timestamp = raw_reading.timestamp

            # 3. Payload Construction & Dispatch
            prepared = self.processor.build_payloads(sensor=sensor, reading=reading)
            if prepared:
                self._dispatch_results(prepared)

            # 4. State Update
            health.status = SensorState.HEALTHY
            health.last_seen = utc_now()
            health.failure_count = 0
            health.last_error = None
            health.backoff_until = None
            self._last_readings[sensor_id] = reading

        except ProcessorError as exc:
            logger.warning("Pipeline error for sensor %s: %s", sensor_id, exc)
            self._handle_failure(health, str(exc))
        except Exception as exc:
            logger.error("Hardware error for sensor %s: %s", sensor_id, exc)
            self._handle_failure(health, str(exc))

    def _dispatch_results(self, prepared: Any) -> None:
        """Routes processed data to WebSocket and EventBus."""
        # WebSocket broadcasting
        if prepared.device_payload:
            self.emitter.emit_device_sensor_reading(prepared.device_payload)

        if prepared.dashboard_payload:
            self.emitter.emit_dashboard_snapshot(prepared.dashboard_payload)

        # Internal event bus (for Automation / Persistence / AI)
        events = getattr(prepared, "controller_events", []) or []
        for event_name, payload in events:
            self.event_bus.publish(event_name, payload)

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    def _get_local_sensors(self) -> list[int]:
        """Returns IDs of sensors requiring local polling."""
        local_protocols = {"GPIO", "I2C", "ADC", "SPI", "ONEWIRE"}
        try:
            return [
                s.id
                for s in self.sensor_manager.get_all_sensors()
                if str(getattr(s.protocol, "value", s.protocol)).upper() in local_protocols
            ]
        except Exception:
            return []

    def _get_health(self, sensor_id: int) -> SensorHealth:
        """Get or create health tracker for a sensor."""
        if sensor_id not in self._health:
            self._health[sensor_id] = SensorHealth(sensor_id)
        return self._health[sensor_id]

    def _handle_failure(self, health: SensorHealth, error_msg: str) -> None:
        """Updates health state and calculates backoff timer."""
        health.status = SensorState.UNHEALTHY
        health.failure_count += 1
        health.last_error = error_msg

        # Exponential backoff: 5s, 10s, 20s, 40s... up to max
        backoff = min(self.max_backoff_s, self.base_backoff_s * (2 ** (health.failure_count - 1)))
        health.backoff_until = time.time() + backoff

        if health.failure_count == 1 or health.failure_count % 10 == 0:
            logger.warning(
                "Sensor %s failing consistently (%d failures). Backoff: %.0fs",
                health.sensor_id,
                health.failure_count,
                backoff,
            )

    def get_service_status(self) -> dict[str, Any]:
        """Returns comprehensive status for API/Dashboards."""
        return {
            "is_running": self._is_running,
            "poll_interval": self.poll_interval_s,
            "sensor_count": len(self._health),
            "healthy_count": sum(1 for h in self._health.values() if h.status == SensorState.HEALTHY),
            "sensors": {sid: h.to_dict() for sid, h in self._health.items()},
        }

    def get_health_status(self, sensor_id: int) -> dict[str, Any] | None:
        """Get health status for a specific sensor."""
        health = self._health.get(sensor_id)
        return health.to_dict() if health else None


__all__ = ["SensorPollingService"]
