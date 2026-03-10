"""
MQTT Sensor Service
===================

Router and dispatcher for sensor data coming from MQTT.

This service acts as the 'Hardware Integration Layer' interface. It is strictly
responsible for:
1. MQTT transport management (subscribe/receive).
2. Identity resolution (Mapping unique MQTT topics/friendly names to SensorEntity).
3. Pipeline Delegation (Forwarding raw data to the processing pipeline).
4. Real-time Emission (Broadcasting processed payloads via WebSockets).

Processing Contract:
-------------------
This service does NOT validate, calibrate, or transform data. It delegates all
business logic to an injected IDataProcessor implementation (usually CompositeProcessor).

Architecture:
------------
- Inbound: MQTT Messages (Zigbee2MQTT or ESP32-GrowTent).
- Logic: Resolve Sensor -> Pipeline.process() -> Pipeline.build_payloads().
- Outbound:
    - Device readings (/devices)
    - Primary metrics snapshots (/dashboard)
    - Internal events (EventBus) for automation and persistence.

Author: Sebastian Gomez
Updated: January 2026
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime
from typing import TYPE_CHECKING, Any

from app.hardware.mqtt.mqtt_broker_wrapper import MQTTClientWrapper
from app.hardware.sensors.processors.base_processor import IDataProcessor, ProcessorError

if TYPE_CHECKING:
    from app.services.hardware.sensor_management_service import SensorManagementService
import contextlib

from app.domain.sensors.sensor_entity import SensorEntity
from app.enums.events import DeviceEvent
from app.schemas.events import (
    UnregisteredSensorPayload,
)
from app.utils.cache import TTLCache
from app.utils.emitters import EmitterService
from app.utils.event_bus import EventBus
from app.utils.time import iso_now, utc_now

logger = logging.getLogger(__name__)


def _safe_int(value: Any, default: int = 0) -> int:
    """Safely convert any value to int, returning default on failure."""
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


class NoOpMetrics:
    """Default no-op implementation for the metrics interface."""

    def inc(self, name: str, value: int = 1, **labels: Any) -> None:
        """No-op increment."""
        return

    def observe(self, name: str, value: float, **labels: Any) -> None:
        """No-op observation."""
        return


class MQTTSensorService:
    """
    High-performance MQTT router and websocket emitter.

    This service connects the asynchronous world of MQTT devices to the synchronous
    business logic of the sensor processing pipeline.
    """

    def __init__(
        self,
        mqtt_client: MQTTClientWrapper,
        emitter: EmitterService,
        sensor_manager: "SensorManagementService",
        processor: IDataProcessor,
        metrics: Any | None = None,
    ):
        """
        Initializes the service and binds events.

        Args:
            mqtt_client: Wrapper for MQTT subscriptions and message handling.
            emitter: WebSocket service for broadcasting payloads.
            sensor_manager: Primary source of truth for Sensor entities.
            processor: The processing pipeline (must implement process and build_payloads).
            metrics: Optional Prometheus/OpenTelemetry metrics collector.
        """
        self.mqtt_client = mqtt_client
        self.emitter = emitter
        self.sensor_manager = sensor_manager
        self.processor = processor
        self.metrics = metrics or NoOpMetrics()
        self.event_bus = EventBus()

        # Trace logging (payload preview) is intentionally noisy for debugging.
        trace_env = os.getenv("SYSGROW_MQTT_TRACE", "false").strip().lower()
        self._trace_messages = trace_env in {"1", "true", "yes", "on"}

        # Local state and caches
        self._friendly_name_cache: TTLCache = TTLCache(enabled=True, ttl_seconds=300, maxsize=256)
        self._unmapped_last_logged_at: dict[str, float] = {}

        # Basic health tracking (routing state; not “processing” logic)
        self.last_seen: dict[int, datetime] = {}
        self.sensor_health: dict[int, dict[str, Any]] = {}

        # Cooldown for 'unmapped device' logs to avoid log flooding
        self._unmapped_log_cooldown_s = int(os.getenv("SYSGROW_UNMAPPED_LOG_COOLDOWN", "600"))

        # Keep caches coherent when sensors are modified.
        try:
            self.event_bus.subscribe(DeviceEvent.SENSOR_CREATED, lambda _p: self._clear_mapping_caches())
            self.event_bus.subscribe(DeviceEvent.SENSOR_DELETED, lambda _p: self._clear_mapping_caches())
        except Exception as exc:
            logger.warning("Failed to subscribe cache-invalidation listeners: %s", exc)

        self._subscribe_to_topics()
        logger.info("MQTTSensorService initialized and listening")

    # ---------------------------------------------------------------------
    # Topic Management
    # ---------------------------------------------------------------------

    def _subscribe_to_topics(self) -> None:
        """Configures MQTT subscriptions for all supported protocols."""
        topics = [
            ("zigbee2mqtt/+", self._on_message),
            ("zigbee2mqtt/+/availability", self._on_message),  # Device availability
            ("zigbee2mqtt/bridge/#", self._on_message),
            # SYSGrow Zigbee2MQTT-style topics (ESP32-C6 devices)
            ("sysgrow/+", self._on_message),
            ("sysgrow/+/availability", self._on_message),
            ("sysgrow/bridge/#", self._on_message),
        ]

        for topic, callback in topics:
            try:
                self.mqtt_client.subscribe(topic, callback)
                logger.debug("✅ Subscribed to MQTT topic: %s", topic)
            except Exception as exc:
                logger.error("Failed to subscribe to %s: %s", topic, exc)
                self.metrics.inc("mqtt_subscribe_errors_total", topic=topic)

        self.metrics.inc("mqtt_subscriptions_total", value=len(topics))

    # ---------------------------------------------------------------------
    # Unified Message Handling
    # ---------------------------------------------------------------------

    def _on_message(self, client: Any, userdata: Any, msg: Any) -> None:
        """
        Central message router for ALL incoming MQTT traffic.

        Guaranteed not to raise exceptions to prevent killing the MQTT loop.
        """
        t0 = time.perf_counter()
        topic = str(getattr(msg, "topic", ""))
        payload_bytes = getattr(msg, "payload", b"")
        source = self._source_from_topic(topic)

        self.metrics.inc("mqtt_messages_total", source=source)

        if self._trace_messages:
            with contextlib.suppress(Exception):
                logger.info("MQTT [%s] -> %s", topic, payload_bytes.decode(errors="ignore")[:250])

        try:
            if topic.startswith("zigbee2mqtt/"):
                self._handle_mqtt_message(topic, payload_bytes)
            elif topic.startswith("sysgrow/"):
                self._handle_sysgrow_message(topic, payload_bytes)
            else:
                logger.warning("Unroutable MQTT topic: %s", topic)
                self.metrics.inc("mqtt_messages_unknown_topic_total")

        except Exception as exc:
            logger.exception("Hardware routing error topic=%s: %s", topic, exc)
            self.metrics.inc("mqtt_message_handler_errors_total", source=source)

        finally:
            self.metrics.observe("mqtt_message_handle_latency_seconds", time.perf_counter() - t0, source=source)

    def _source_from_topic(self, topic: str) -> str:
        """Categorizes the MQTT message source based on its topic prefix."""
        if topic.startswith("zigbee2mqtt/"):
            return "zigbee2mqtt"
        if topic.startswith("sysgrow/"):
            return "sysgrow"
        return "unknown"

    # ---------------------------------------------------------------------
    # Zigbee2MQTT handling
    # ---------------------------------------------------------------------

    def _handle_mqtt_message(self, topic: str, payload: bytes) -> None:
        """
        Handles Zigbee2MQTT messages (Format: zigbee2mqtt/<friendly_name>).

        Zigbee devices must be registered in the gateway to resolve their unit_id.
        Unregistered Zigbee messages are dropped as their context is unknown.
        """
        parts = topic.split("/")

        # Handle availability messages: zigbee2mqtt/<friendly_name>/availability
        if len(parts) == 3 and parts[2] == "availability":
            friendly_name = parts[1]
            self._handle_zigbee_availability(friendly_name, payload)
            return

        friendly_name = parts[-1].strip()

        if friendly_name == "bridge":
            self.metrics.inc("mqtt_zigbee_bridge_messages_total")
            return

        data = self._parse_json(payload, source="zigbee2mqtt", identity=friendly_name)
        if data is None:
            return

        sensor_id, sensor = self._resolve_registered_sensor(friendly_name)
        if sensor_id is None or sensor is None:
            self._log_unregistered_zigbee(friendly_name)
            self.metrics.inc("mqtt_unregistered_total", source="zigbee2mqtt")
            return

        unit_id = _safe_int(getattr(sensor, "unit_id", 0))
        if unit_id <= 0:
            logger.warning("Dropped Zigbee reading: No valid unit_id for %s", friendly_name)
            self.metrics.inc("mqtt_dropped_invalid_unit_total", source="zigbee2mqtt")
            return

        self._ingest_registered(sensor=sensor, raw_data=data, source="zigbee2mqtt")

    def _handle_zigbee_availability(self, friendly_name: str, payload: bytes) -> None:
        """
        Handle Zigbee2MQTT device availability messages.

        Args:
            friendly_name: Device friendly name
            payload: Raw payload (b"online" or b"offline" or JSON)
        """
        try:
            payload_str = payload.decode().strip().lower()

            # Skip JSON payloads (bridge health data)
            if payload_str.startswith("{"):
                return

            is_online = payload_str == "online"
            self.metrics.inc("mqtt_zigbee_availability_total", status=payload_str)

            # Update adapter availability if sensor is registered
            _sensor_id, sensor = self._resolve_registered_sensor(friendly_name)
            if sensor is not None and hasattr(sensor, "_adapter"):
                adapter = sensor._adapter
                if hasattr(adapter, "_device_available"):
                    adapter._device_available = is_online
                    logger.info("Zigbee2MQTT device '%s' is %s", friendly_name, payload_str)

            # Emit availability event for UI updates
            if self.event_bus:
                try:
                    from app.enums.events import DeviceEvent

                    self.event_bus.publish(
                        DeviceEvent.DEVICE_AVAILABILITY_CHANGED,
                        {
                            "friendly_name": friendly_name,
                            "available": is_online,
                            "source": "zigbee2mqtt",
                        },
                    )
                except Exception as exc:
                    logger.debug("Failed to publish availability event: %s", exc)

        except Exception as e:
            logger.error("Error handling Zigbee availability for %s: %s", friendly_name, e)

    def _log_unregistered_zigbee(self, friendly_name: str) -> None:
        """Throttled logging for unregistered Zigbee devices to prevent log spam."""
        now = time.time()
        last = self._unmapped_last_logged_at.get(friendly_name, 0.0)
        if (now - last) < self._unmapped_log_cooldown_s:
            return
        self._unmapped_last_logged_at[friendly_name] = now

        logger.warning("Unregistered Zigbee device '%s' detected. Mapping missing in dashboard.", friendly_name)

    # ---------------------------------------------------------------------
    # SYSGrow Zigbee2MQTT-style handling
    # ---------------------------------------------------------------------

    def _handle_sysgrow_message(self, topic: str, payload: bytes) -> None:
        """
        Handles SYSGrow Zigbee2MQTT-style messages.

        Topics:
            sysgrow/<friendly_name>             - Device state (sensor data)
            sysgrow/<friendly_name>/availability - Online/offline status
            sysgrow/bridge/info                 - Bridge status
            sysgrow/bridge/health               - Health check
            sysgrow/bridge/response/*           - Command responses
        """
        parts = topic.split("/")

        # Handle bridge topics
        if len(parts) >= 2 and parts[1] == "bridge":
            self._handle_sysgrow_bridge(topic, payload)
            return

        # Handle availability messages (plain text: "online" or "offline")
        if len(parts) == 3 and parts[2] == "availability":
            friendly_name = parts[1]
            status_text = payload.decode(errors="ignore").strip().lower()
            is_online = status_text == "online"
            logger.info("SYSGrow device '%s' is now %s", friendly_name, status_text)
            self.metrics.inc("mqtt_sysgrow_availability_total", status=status_text)

            # Emit availability event for UI updates
            try:
                self.event_bus.publish(
                    DeviceEvent.DEVICE_AVAILABILITY_CHANGED,
                    {
                        "friendly_name": friendly_name,
                        "protocol": "sysgrow",
                        "online": is_online,
                        "timestamp": iso_now(),
                    },
                )
            except Exception as exc:
                logger.debug("Failed to publish availability event: %s", exc)
            return

        # Handle device state messages (JSON payload)
        if len(parts) == 2:
            friendly_name = parts[1]
            data = self._parse_json(payload, source="sysgrow", identity=friendly_name)
            if data is None:
                return

            # Try to resolve registered sensor by friendly name
            sensor_id, sensor = self._resolve_registered_sensor(friendly_name)

            if sensor_id is None or sensor is None:
                # Try by MAC address (sysgrow devices include mac_address in payload)
                mac_address = data.get("mac_address")
                if mac_address:
                    sensor_id, sensor = self._resolve_sensor_by_mac(mac_address)

            if sensor is None:
                # Device discovery: emit as unregistered
                self._emit_unregistered_sysgrow(friendly_name=friendly_name, raw_data=data)
                self.metrics.inc("mqtt_unregistered_total", source="sysgrow")
                return

            unit_id = _safe_int(getattr(sensor, "unit_id", 0))
            if unit_id <= 0:
                logger.warning("Dropped SYSGrow reading: No valid unit_id for %s", friendly_name)
                self.metrics.inc("mqtt_dropped_invalid_unit_total", source="sysgrow")
                return

            # Pass raw data directly - normalization is handled by the processor pipeline
            # (TransformationProcessor.standardize_fields() handles field mapping)
            self._ingest_registered(sensor=sensor, raw_data=data, source="sysgrow")

    def _handle_sysgrow_bridge(self, topic: str, payload: bytes) -> None:
        """
        Handles SYSGrow bridge messages (info, health, responses).

        Topics:
            sysgrow/bridge/info          - Bridge status and device list
            sysgrow/bridge/health        - Health check response
            sysgrow/bridge/response/*    - Command responses
        """
        from app.enums.common import SYSGrowEvent
        from app.utils.time import iso_now

        parts = topic.split("/")
        if len(parts) < 3:
            return

        bridge_subtopic = "/".join(parts[2:])
        self.metrics.inc("mqtt_sysgrow_bridge_total", subtopic=bridge_subtopic.split("/")[0])

        data = self._parse_json(payload, source="sysgrow_bridge", identity=bridge_subtopic)
        if data is None:
            # Some bridge messages may be plain text
            return

        if bridge_subtopic == "info":
            # Process bridge info (contains device list)
            devices = data.get("devices", [])
            for device in devices:
                friendly_name = device.get("friendly_name")
                if friendly_name:
                    logger.debug("SYSGrow bridge reports device: %s", friendly_name)

            # Publish bridge info event
            try:
                self.event_bus.publish(
                    SYSGrowEvent.BRIDGE_INFO,
                    {
                        "devices": devices,
                        "device_count": len(devices),
                        "timestamp": iso_now(),
                    },
                )
            except Exception as exc:
                logger.debug("Failed to publish bridge info event: %s", exc)

        elif bridge_subtopic == "health":
            # Log bridge health status
            status = data.get("status", "unknown")
            uptime = data.get("uptime")
            free_heap = data.get("free_heap")
            logger.info("SYSGrow bridge health: %s (uptime=%ss, heap=%s)", status, uptime, free_heap)

            # Publish bridge health event
            try:
                self.event_bus.publish(
                    SYSGrowEvent.BRIDGE_HEALTH,
                    {
                        "status": status,
                        "uptime": uptime,
                        "free_heap": free_heap,
                        "timestamp": iso_now(),
                        **data,  # Include all health fields
                    },
                )
            except Exception as exc:
                logger.debug("Failed to publish bridge health event: %s", exc)

        elif bridge_subtopic.startswith("response/"):
            # Command response
            command = bridge_subtopic.replace("response/", "")
            status = data.get("status", "unknown")
            logger.info("SYSGrow bridge response for '%s': %s", command, status)

            # Publish command response event
            try:
                self.event_bus.publish(
                    SYSGrowEvent.COMMAND_RESPONSE,
                    {
                        "command": command,
                        "status": status,
                        "response": data,
                        "timestamp": iso_now(),
                    },
                )
            except Exception as exc:
                logger.debug("Failed to publish command response event: %s", exc)

    def _emit_unregistered_sysgrow(
        self,
        *,
        friendly_name: str,
        raw_data: dict[str, Any],
    ) -> None:
        """Emits discovery payload for unregistered SYSGrow devices."""
        # Throttle logging for repeated unregistered devices
        now = time.time()
        last = self._unmapped_last_logged_at.get(friendly_name, 0.0)
        if (now - last) >= self._unmapped_log_cooldown_s:
            self._unmapped_last_logged_at[friendly_name] = now
            logger.info(
                "Discovered unregistered SYSGrow device: %s (type=%s)",
                friendly_name,
                raw_data.get("device_type", "unknown"),
            )

        publisher_id = f"sysgrow:{friendly_name}"
        topic = f"sysgrow/{friendly_name}"

        # Detect device capabilities from payload
        capabilities = []
        if raw_data.get("temperature") is not None:
            capabilities.append("temperature")
        if raw_data.get("humidity") is not None:
            capabilities.append("humidity")
        if raw_data.get("co2") is not None:
            capabilities.append("co2")
        if raw_data.get("air_quality") is not None:
            capabilities.append("air_quality")
        if raw_data.get("voc") is not None:
            capabilities.append("voc")
        if raw_data.get("lux") is not None:
            capabilities.append("light")
        if raw_data.get("smoke") is not None:
            capabilities.append("smoke")

        payload = UnregisteredSensorPayload(
            schema_version=1,
            unit_id=0,  # Unknown until registered
            publisher_id=publisher_id,
            topic=topic,
            friendly_name=friendly_name,
            registered=False,
            timestamp=iso_now(),
            raw_data=raw_data,
            suggested_sensor_type=raw_data.get("device_type"),
            detected_capabilities=capabilities if capabilities else None,
        )

        try:
            self.emitter.emit_unregistered_sensor_data(payload)
            self.metrics.inc("mqtt_emits_total", target="unregistered", source="sysgrow")
        except Exception as exc:
            logger.error("Failed to emit SYSGrow discovery payload for %s: %s", friendly_name, exc)
            self.metrics.inc("mqtt_emit_errors_total", source="sysgrow")

    def _resolve_sensor_by_mac(self, mac_address: str) -> tuple[int | None, SensorEntity | None]:
        """
        Resolves a sensor by MAC address.

        This is useful for SYSGrow devices which may use MAC-based friendly names.
        """
        if not mac_address:
            return None, None

        # Try common MAC-based friendly name formats
        mac_clean = mac_address.replace(":", "").upper()
        mac_suffix = mac_clean[-8:]  # Last 4 bytes

        possible_names = [
            f"sysgrow-{mac_suffix}",
            f"sysgrow-{mac_suffix.lower()}",
            mac_address.replace(":", "-"),
            mac_address,
        ]

        for name in possible_names:
            sensor_id, sensor = self._resolve_registered_sensor(name)
            if sensor is not None:
                return sensor_id, sensor

        return None, None

    # ---------------------------------------------------------------------
    # Processing & Emission Flow
    # ---------------------------------------------------------------------

    def _ingest_registered(self, *, sensor: SensorEntity, raw_data: dict[str, Any], source: str) -> None:
        """
        Orchestrates the transition from raw hardware data to enriched system domain models.

        Flow:
        1. Pipeline Processing (Clean/Validate/Transform/Enrich).
        2. Snapshot Building (Priority selection for dashboards).
        3. Internal Dispatch (Automations/Persistence).
        4. External Broadcast (WebSockets).
        """
        t0 = time.perf_counter()
        sensor_id = _safe_int(getattr(sensor, "id", 0))
        unit_id = _safe_int(getattr(sensor, "unit_id", 0))

        if unit_id <= 0:
            return

        try:
            # 1) Execute Pipeline: Raw Data -> Domain Reading
            # This triggers: Standardization -> Validation -> Calibration -> Transformation -> Enrichment
            reading = self.processor.process(sensor, raw_data)

            # Sync with hardware-level adapter (if registered) to support on-demand /read API
            try:
                active_sensor = self._get_sensor_entity(sensor_id)
                if (
                    active_sensor
                    and hasattr(active_sensor, "_adapter")
                    and active_sensor._adapter
                    and hasattr(active_sensor._adapter, "update_data")
                ):
                    active_sensor._adapter.update_data(raw_data)
            except Exception as e:
                logger.debug("Failed to sync adapter for sensor %s: %s", sensor_id, e)

            # verify reading contains a valid unit (pipeline should ensure this)
            reading_unit = _safe_int(getattr(reading, "unit_id", 0))
            if reading_unit <= 0:
                logger.error("Pipeline failure: Reading for sensor %s missing unit context", sensor_id)
                return

            # 2) Build Multi-Target Payloads (WebSocket/Events bundle)
            prepared = self.processor.build_payloads(sensor=sensor, reading=reading)
            if prepared is None:
                return

            # Track health status (last seen and processing result)
            now = utc_now()
            self.last_seen[sensor_id] = now
            self.sensor_health[sensor_id] = {
                "last_seen": now.isoformat(),
                "status": getattr(getattr(reading, "status", None), "value", "unknown"),
                "is_anomaly": bool(getattr(reading, "is_anomaly", False)),
                "source": source,
            }

            # 3) Dispatch internal events (Automation layers, MQTT-back-persistence, etc)
            controller_events = getattr(prepared, "controller_events", []) or []
            for event_name, payload in controller_events:
                self.event_bus.publish(event_name, payload)

            # 4) Broadcast to external clients
            self._emit_prepared(prepared, source=source)

            self.metrics.inc("mqtt_processed_total", source=source)

        except ProcessorError as exc:
            logger.error("Data processing failed for sensor %s: %s", sensor_id, exc)
            self.metrics.inc("mqtt_processing_errors_total", source=source, kind="processor_error")
        except Exception as exc:
            logger.exception("Unexpected processing error (source=%s): %s", source, exc)
            self.metrics.inc("mqtt_processing_errors_total", source=source, kind="exception")
        finally:
            self.metrics.observe("mqtt_processing_latency_seconds", time.perf_counter() - t0, source=source)

    def _emit_prepared(self, prepared: Any, *, source: str) -> None:
        """Broadcasts processed results to WebSocket namespaces."""
        t0 = time.perf_counter()
        unit_id = _safe_int(getattr(prepared, "unit_id", 0))
        if unit_id <= 0:
            return

        try:
            # Raw device reading for real-time graphs/logs
            device_payload = getattr(prepared, "device_payload", None)
            if device_payload:
                self.emitter.emit_device_sensor_reading(device_payload)
                self.metrics.inc("mqtt_emits_total", target="devices", source=source)

            # Top-level metric for dashboard snapshots
            dashboard_payload = getattr(prepared, "dashboard_payload", None)
            if dashboard_payload:
                self.emitter.emit_dashboard_snapshot(dashboard_payload)
                self.metrics.inc("mqtt_emits_total", target="dashboard", source=source)

        except Exception as exc:
            logger.error("WebSocket emission failed for unit %s: %s", unit_id, exc)
            self.metrics.inc("mqtt_emit_errors_total", source=source)
        finally:
            self.metrics.observe("mqtt_emit_latency_seconds", time.perf_counter() - t0, source=source)

    def _parse_json(self, payload: bytes, *, source: str, identity: str) -> dict[str, Any] | None:
        """Safely decodes MQTT byte payload into a JSON dictionary."""
        try:
            decoded = payload.decode(errors="strict")
            data = json.loads(decoded)

            if not isinstance(data, dict):
                logger.warning("Dropped non-dict payload from %s (%s)", source, identity)
                self.metrics.inc("mqtt_messages_invalid_payload_total", source=source)
                return None

            return data

        except json.JSONDecodeError as exc:
            logger.error("Invalid JSON from %s (%s): %s", source, identity, exc)
            self.metrics.inc("mqtt_messages_invalid_json_total", source=source)
        except Exception as exc:
            logger.error("Payload decode error from %s (%s): %s", source, identity, exc)
            self.metrics.inc("mqtt_messages_decode_errors_total", source=source)

        return None

    # ---------------------------------------------------------------------
    # Identity Resolution (Registry & Cache)
    # ---------------------------------------------------------------------

    def _clear_mapping_caches(self) -> None:
        """Invalidates all resolution caches (triggers on sensor config changes)."""
        self._friendly_name_cache.clear()
        self._unmapped_last_logged_at.clear()

        # Clear priority processor state to force re-election of primary sensors
        try:
            if hasattr(self.processor, "_priority") and self.processor._priority:
                # Clear snapshots and primary mappings
                self.processor._priority.primary_sensors.clear()
                self.processor._priority._snapshot_cache.clear()
                logger.info("MQTTSensorService: PriorityProcessor state cleared")
        except Exception as e:
            logger.warning("Failed to clear PriorityProcessor state: %s", e)

        logger.info("MQTTSensorService: Resolution caches cleared")

    def _get_sensor_entity(self, sensor_id: int) -> SensorEntity | None:
        """
        Retrieves a SensorEntity by ID.

        Delegates to SensorManagementService which owns the sensor registry.
        """
        if sensor_id <= 0:
            return None

        try:
            return self.sensor_manager.get_sensor_entity(sensor_id)
        except Exception:
            return None

    def _resolve_registered_sensor(self, friendly_name: str) -> tuple[int | None, SensorEntity | None]:
        """
        Resolves a friendly name to a concrete SensorID and Entity.

        Delegates to SensorManagementService which owns the sensor registry.
        """
        if not friendly_name:
            return None, None

        # Check local cache first for performance
        cached_id = self._friendly_name_cache.get(friendly_name)
        if cached_id:
            sensor = self._get_sensor_entity(cached_id)
            if sensor:
                return cached_id, sensor
            # Cache is stale, clear it
            self._friendly_name_cache.invalidate(friendly_name)

        # Delegate to sensor_manager
        try:
            sensor = self.sensor_manager.get_sensor_by_friendly_name(friendly_name)
            if sensor:
                sensor_id = _safe_int(getattr(sensor, "id", 0))
                if sensor_id > 0:
                    self._friendly_name_cache.set(friendly_name, sensor_id)
                    return sensor_id, sensor
        except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
            logger.debug("Friendly-name lookup failed for '%s': %s", friendly_name, exc)

        return None, None

    # ---------------------------------------------------------------------
    # Public API
    # ---------------------------------------------------------------------

    def ingest_zigbee_payload(
        self,
        *,
        friendly_name: str,
        payload: dict[str, Any],
        sensor_id: int | None = None,
    ) -> bool:
        """
        Manually injects a Zigbee payload into the pipeline.

        Used for hydrating state on startup or reconnect.
        """
        try:
            if not friendly_name or not isinstance(payload, dict):
                return False

            resolved_sensor = None
            if sensor_id:
                resolved_sensor = self._get_sensor_entity(_safe_int(sensor_id))

            if resolved_sensor is None:
                _, resolved_sensor = self._resolve_registered_sensor(friendly_name)

            if resolved_sensor is None:
                return False

            self._ingest_registered(sensor=resolved_sensor, raw_data=payload, source="zigbee2mqtt")
            return True

        except Exception:
            logger.exception("Manual Zigbee ingestion failed for %s", friendly_name)
            return False

    def get_sensor_health(self, sensor_id: int | None = None) -> dict[str, Any]:
        """Returns the routing health status for one or all sensors."""
        if sensor_id is not None:
            return self.sensor_health.get(sensor_id, {"status": "unknown"})

        return {
            "total_tracked": len(self.sensor_health),
            "sensors": self.sensor_health,
        }

    def shutdown(self) -> None:
        """Gracefully releases MQTT subscriptions."""
        logger.info("MQTTSensorService shutting down")
        # MQTT client cleanup handled by container/framework
