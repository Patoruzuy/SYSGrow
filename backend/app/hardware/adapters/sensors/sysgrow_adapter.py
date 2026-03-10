"""
SYSGrow Sensor Adapter
======================

Adapter for SYSGrow ESP32-C6 devices using Zigbee2MQTT-style MQTT protocol.
Supports bidirectional communication: receive sensor data AND send commands.

Topic Structure:
    - sysgrow/<friendly_name>              - Device state (sensor data)
    - sysgrow/<friendly_name>/set          - Send commands to device
    - sysgrow/<friendly_name>/get          - Trigger on-demand read
    - sysgrow/<friendly_name>/availability - Online/offline status (LWT)
    - sysgrow/bridge/request/*             - Bridge commands
    - sysgrow/bridge/response/*            - Command responses

Author: SYSGrow Team
Version: 1.0.0
"""

import json
import logging
import uuid
from collections import deque
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from threading import Lock
from typing import Any, Callable

from .base_adapter import AdapterError, ISensorAdapter

logger = logging.getLogger(__name__)


class DeviceAvailability(Enum):
    """Device availability states."""

    ONLINE = "online"
    OFFLINE = "offline"
    UNKNOWN = "unknown"


class CommandStatus(Enum):
    """Command execution status."""

    PENDING = "pending"
    SENT = "sent"
    ACKNOWLEDGED = "acknowledged"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"


@dataclass
class PendingCommand:
    """Represents a command waiting for response."""

    transaction_id: str
    command: str
    payload: dict[str, Any]
    sent_at: datetime
    timeout_seconds: int = 30
    callback: Callable[[str, dict], None] | None = None
    status: CommandStatus = CommandStatus.PENDING
    response: dict[str, Any] | None = None

    def is_expired(self) -> bool:
        """Check if command has timed out."""
        return (datetime.now() - self.sent_at).total_seconds() > self.timeout_seconds


@dataclass
class SYSGrowDeviceState:
    """Cached state for a SYSGrow device."""

    friendly_name: str
    availability: DeviceAvailability = DeviceAvailability.UNKNOWN
    last_seen: datetime | None = None
    last_data: dict[str, Any] | None = None
    firmware_version: str | None = None
    device_type: str | None = None
    mac_address: str | None = None
    rssi: int | None = None
    uptime: int | None = None
    sensors_status: dict[str, str] | None = None


class SYSGrowAdapter(ISensorAdapter):
    """
    Adapter for SYSGrow ESP32-C6 devices with Zigbee2MQTT-style protocol.

    Features:
        - Bidirectional MQTT communication
        - Command queue with offline support
        - Response tracking with transaction IDs
        - Availability monitoring
        - Multi-device support
    """

    # Topic prefixes
    TOPIC_PREFIX = "sysgrow"
    BRIDGE_PREFIX = "sysgrow/bridge"

    def __init__(
        self,
        sensor_id: int,
        mqtt_client,
        friendly_name: str,
        unit_id: int = 0,
        timeout: int = 120,
        command_timeout: int = 30,
        max_queue_size: int = 100,
        primary_metrics: list[str] | None = None,
    ):
        """
        Initialize SYSGrow adapter.

        Args:
            sensor_id: Unique sensor ID in database
            mqtt_client: MQTT client instance (MQTTClientWrapper)
            friendly_name: Device friendly name (e.g., sysgrow-AABBCCDD)
            unit_id: Associated growth unit ID
            timeout: Data timeout in seconds (default: 120)
            command_timeout: Command response timeout in seconds (default: 30)
            max_queue_size: Maximum commands to queue when offline (default: 100)
            primary_metrics: Optional list of primary metrics for this sensor
        """
        self.sensor_id = sensor_id
        self.mqtt_client = mqtt_client
        self.friendly_name = friendly_name
        self.unit_id = unit_id
        self.timeout = timeout
        self.command_timeout = command_timeout
        self.max_queue_size = max_queue_size

        # Device state
        self._state = SYSGrowDeviceState(friendly_name=friendly_name)
        self._state_lock = Lock()

        # Command tracking
        self._pending_commands: dict[str, PendingCommand] = {}
        self._command_queue: deque = deque(maxlen=max_queue_size)
        self._command_lock = Lock()

        # Availability callbacks
        self._availability_callbacks: list[Callable[[str, DeviceAvailability], None]] = []

        # Subscribe to device topics
        self._subscribed = False
        if self.mqtt_client:
            self._subscribe_to_topics()

    # =========================================================================
    # Topic Helpers
    # =========================================================================

    def _get_state_topic(self) -> str:
        """Get device state topic."""
        return f"{self.TOPIC_PREFIX}/{self.friendly_name}"

    def _get_set_topic(self) -> str:
        """Get device command topic."""
        return f"{self.TOPIC_PREFIX}/{self.friendly_name}/set"

    def _get_get_topic(self) -> str:
        """Get device trigger topic."""
        return f"{self.TOPIC_PREFIX}/{self.friendly_name}/get"

    def _get_availability_topic(self) -> str:
        """Get device availability topic."""
        return f"{self.TOPIC_PREFIX}/{self.friendly_name}/availability"

    # =========================================================================
    # Subscription Management
    # =========================================================================

    def _subscribe_to_topics(self) -> None:
        """Subscribe to all device-related MQTT topics."""
        if not self.mqtt_client or self._subscribed:
            return

        topics = [
            (self._get_state_topic(), self._on_state_message),
            (self._get_availability_topic(), self._on_availability_message),
            (f"{self.BRIDGE_PREFIX}/response/#", self._on_bridge_response),
        ]

        for topic, callback in topics:
            try:
                self.mqtt_client.subscribe(topic, callback)
                logger.debug("SYSGrow adapter subscribed to: %s", topic)
            except Exception as e:
                logger.error("Failed to subscribe to %s: %s", topic, e)

        self._subscribed = True
        logger.info("SYSGrow adapter initialized for device '%s' (sensor_id=%d)", self.friendly_name, self.sensor_id)

    def _unsubscribe_from_topics(self) -> None:
        """Unsubscribe from all device topics."""
        if not self.mqtt_client or not self._subscribed:
            return

        topics = [
            self._get_state_topic(),
            self._get_availability_topic(),
        ]

        for topic in topics:
            try:
                self.mqtt_client.unsubscribe(topic)
            except Exception as e:
                logger.warning("Failed to unsubscribe from %s: %s", topic, e)

        self._subscribed = False

    # =========================================================================
    # Message Handlers
    # =========================================================================

    def _on_state_message(self, client, userdata, msg) -> None:
        """Handle device state message (sensor data)."""
        try:
            payload = json.loads(msg.payload.decode())

            with self._state_lock:
                self._state.last_data = payload
                self._state.last_seen = datetime.now()
                self._state.availability = DeviceAvailability.ONLINE

                # Extract device metadata
                if "firmware_version" in payload:
                    self._state.firmware_version = payload["firmware_version"]
                if "device_type" in payload:
                    self._state.device_type = payload["device_type"]
                if "mac_address" in payload:
                    self._state.mac_address = payload["mac_address"]
                if "rssi" in payload:
                    self._state.rssi = payload["rssi"]
                if "uptime" in payload:
                    self._state.uptime = payload["uptime"]
                if "sensors_status" in payload:
                    self._state.sensors_status = payload["sensors_status"]

            logger.debug(
                "SYSGrow '%s' state update: temp=%.1f, hum=%.1f",
                self.friendly_name,
                payload.get("temperature", 0),
                payload.get("humidity", 0),
            )

        except json.JSONDecodeError as e:
            logger.error("Invalid JSON from SYSGrow '%s': %s", self.friendly_name, e)
        except Exception as e:
            logger.error("Error processing SYSGrow state: %s", e)

    def _on_availability_message(self, client, userdata, msg) -> None:
        """Handle device availability message."""
        try:
            status = msg.payload.decode().strip().lower()
            new_availability = DeviceAvailability.ONLINE if status == "online" else DeviceAvailability.OFFLINE

            with self._state_lock:
                old_availability = self._state.availability
                self._state.availability = new_availability

                if new_availability == DeviceAvailability.ONLINE:
                    self._state.last_seen = datetime.now()

            logger.info(
                "SYSGrow '%s' availability: %s -> %s",
                self.friendly_name,
                old_availability.value,
                new_availability.value,
            )

            # Notify callbacks
            for callback in self._availability_callbacks:
                try:
                    callback(self.friendly_name, new_availability)
                except Exception as e:
                    logger.error("Availability callback error: %s", e)

            # Process queued commands if device came online
            if new_availability == DeviceAvailability.ONLINE:
                self._process_command_queue()

        except Exception as e:
            logger.error("Error processing availability: %s", e)

    def _on_bridge_response(self, client, userdata, msg) -> None:
        """Handle bridge response messages."""
        try:
            topic = msg.topic
            payload = json.loads(msg.payload.decode())

            # Extract command name from topic
            # Format: sysgrow/bridge/response/<command>
            parts = topic.split("/")
            if len(parts) >= 4:
                command = "/".join(parts[3:])
            else:
                return

            transaction_id = payload.get("transaction")
            status = payload.get("status", "unknown")

            logger.debug("Bridge response for '%s': status=%s, transaction=%s", command, status, transaction_id)

            # Match to pending command
            if transaction_id:
                with self._command_lock:
                    if transaction_id in self._pending_commands:
                        cmd = self._pending_commands[transaction_id]
                        cmd.response = payload
                        cmd.status = CommandStatus.COMPLETED if status == "ok" else CommandStatus.FAILED

                        # Execute callback
                        if cmd.callback:
                            try:
                                cmd.callback(status, payload)
                            except Exception as e:
                                logger.error("Command callback error: %s", e)

                        # Remove from pending
                        del self._pending_commands[transaction_id]

        except json.JSONDecodeError:
            pass  # Some responses may be plain text
        except Exception as e:
            logger.error("Error processing bridge response: %s", e)

    # =========================================================================
    # ISensorAdapter Implementation
    # =========================================================================

    def read(self) -> dict[str, Any]:
        """
        Read cached sensor data from SYSGrow device.

        Returns:
            Dict with sensor readings

        Raises:
            AdapterError: If no recent data available
        """
        with self._state_lock:
            if self._state.last_data is None:
                raise AdapterError(f"No data received from SYSGrow device '{self.friendly_name}'")

            # Check if data is stale
            if self._state.last_seen:
                age = (datetime.now() - self._state.last_seen).total_seconds()
                if age > self.timeout:
                    raise AdapterError(f"SYSGrow data stale (age: {age:.1f}s, timeout: {self.timeout}s)")

            return self._state.last_data.copy()

    def configure(self, config: dict[str, Any]) -> None:
        """
        Reconfigure SYSGrow adapter.

        Args:
            config: Configuration dictionary
        """
        if "friendly_name" in config and config["friendly_name"] != self.friendly_name:
            old_name = self.friendly_name
            self._unsubscribe_from_topics()
            self.friendly_name = config["friendly_name"]
            self._state.friendly_name = self.friendly_name
            self._subscribe_to_topics()
            logger.info("SYSGrow adapter renamed: %s -> %s", old_name, self.friendly_name)

        if "timeout" in config:
            self.timeout = config["timeout"]

        if "command_timeout" in config:
            self.command_timeout = config["command_timeout"]

    def is_available(self) -> bool:
        """
        Check if SYSGrow device is available.

        Returns:
            True if device is online and has recent data
        """
        with self._state_lock:
            if self._state.availability != DeviceAvailability.ONLINE:
                return False

            if self._state.last_seen:
                age = (datetime.now() - self._state.last_seen).total_seconds()
                return age <= self.timeout

            return False

    def get_protocol_name(self) -> str:
        """Get protocol name."""
        return "SYSGrow"

    def cleanup(self) -> None:
        """Cleanup MQTT subscriptions."""
        self._unsubscribe_from_topics()
        logger.info("SYSGrow adapter cleaned up for '%s'", self.friendly_name)

    # =========================================================================
    # ISensorAdapter Optional Methods (Standard Interface)
    # =========================================================================

    def send_command(self, command: dict[str, Any]) -> bool:
        """
        Send command to device (ISensorAdapter interface).

        Args:
            command: Command dictionary

        Returns:
            True if command sent successfully
        """
        # Use the /set topic for direct commands
        return self._publish(self._get_set_topic(), command)

    def identify(self, duration: int = 10) -> bool:
        """
        Trigger device identification (flash LED).

        Args:
            duration: Duration in seconds

        Returns:
            True if command sent
        """
        return self._publish(self._get_set_topic(), {"identify": duration})

    def get_state(self) -> dict[str, Any] | None:
        """
        Get current device state (ISensorAdapter interface).

        Returns:
            State dictionary
        """
        with self._state_lock:
            return {
                "friendly_name": self._state.friendly_name,
                "available": self._state.availability == DeviceAvailability.ONLINE,
                "last_update": self._state.last_seen.isoformat() if self._state.last_seen else None,
                "readings": dict(self._state.last_data) if self._state.last_data else None,
                "rssi": self._state.rssi,
                "uptime": self._state.uptime,
            }

    def rename(self, new_name: str) -> bool:
        """
        Rename device on network (ISensorAdapter interface).

        Delegates to rename_via_bridge for consistency with Zigbee2MQTT.

        Args:
            new_name: New friendly name

        Returns:
            True if rename command sent
        """
        tid = self.rename_via_bridge(new_name)
        if tid:
            # Update local state optimistically
            old_name = self.friendly_name
            self.friendly_name = new_name
            logger.info("SYSGrow: Renamed %s -> %s", old_name, new_name)
            return True
        return False

    def remove_from_network(self) -> bool:
        """
        Remove device from network (ISensorAdapter interface).

        Delegates to remove_device bridge command.

        Returns:
            True if remove command sent
        """
        tid = self.remove_device(force=False)
        return tid is not None

    # =========================================================================
    # Command Sending
    # =========================================================================

    def _publish(self, topic: str, payload: Any, retain: bool = False) -> bool:
        """
        Publish message to MQTT topic.

        Args:
            topic: MQTT topic
            payload: Message payload (dict will be JSON encoded)
            retain: Whether to retain message

        Returns:
            True if published successfully
        """
        if not self.mqtt_client:
            logger.error("No MQTT client available")
            return False

        try:
            if isinstance(payload, dict):
                payload = json.dumps(payload)
            elif not isinstance(payload, str):
                payload = str(payload)

            self.mqtt_client.publish(topic, payload, retain=retain)
            return True
        except Exception as e:
            logger.error("Failed to publish to %s: %s", topic, e)
            return False

    def _send_command(
        self,
        command: str,
        payload: dict[str, Any],
        topic: str | None = None,
        callback: Callable[[str, dict], None] | None = None,
        queue_if_offline: bool = True,
    ) -> str | None:
        """
        Send command to device with tracking.

        Args:
            command: Command name (for tracking)
            payload: Command payload
            topic: Custom topic (defaults to device /set topic)
            callback: Optional callback(status, response)
            queue_if_offline: Queue command if device offline

        Returns:
            Transaction ID if sent/queued, None if failed
        """
        transaction_id = str(uuid.uuid4())[:8]

        # Add transaction ID to payload for tracking
        payload_with_id = {**payload, "_transaction": transaction_id}

        # Check device availability
        if not self.is_available():
            if queue_if_offline:
                with self._command_lock:
                    self._command_queue.append(
                        PendingCommand(
                            transaction_id=transaction_id,
                            command=command,
                            payload=payload,
                            sent_at=datetime.now(),
                            timeout_seconds=self.command_timeout,
                            callback=callback,
                            status=CommandStatus.PENDING,
                        )
                    )
                logger.info(
                    "Command '%s' queued for offline device '%s' (queue size: %d)",
                    command,
                    self.friendly_name,
                    len(self._command_queue),
                )
                return transaction_id
            else:
                logger.warning("Device '%s' offline, command '%s' not sent", self.friendly_name, command)
                return None

        # Send command
        target_topic = topic or self._get_set_topic()
        if self._publish(target_topic, payload_with_id):
            with self._command_lock:
                self._pending_commands[transaction_id] = PendingCommand(
                    transaction_id=transaction_id,
                    command=command,
                    payload=payload,
                    sent_at=datetime.now(),
                    timeout_seconds=self.command_timeout,
                    callback=callback,
                    status=CommandStatus.SENT,
                )
            logger.debug("Command '%s' sent to '%s' (transaction: %s)", command, self.friendly_name, transaction_id)
            return transaction_id

        return None

    def _process_command_queue(self) -> None:
        """Process queued commands when device comes online."""
        with self._command_lock:
            while self._command_queue:
                cmd = self._command_queue.popleft()

                # Skip expired commands
                if cmd.is_expired():
                    logger.warning("Queued command '%s' expired, discarding", cmd.command)
                    if cmd.callback:
                        with suppress(Exception):
                            cmd.callback("timeout", {})
                    continue

                # Send command
                topic = self._get_set_topic()
                payload_with_id = {**cmd.payload, "_transaction": cmd.transaction_id}

                if self._publish(topic, payload_with_id):
                    cmd.status = CommandStatus.SENT
                    cmd.sent_at = datetime.now()
                    self._pending_commands[cmd.transaction_id] = cmd
                    logger.info("Queued command '%s' sent to '%s'", cmd.command, self.friendly_name)

    def cleanup_expired_commands(self) -> None:
        """Remove expired pending commands (call periodically)."""
        with self._command_lock:
            expired = [tid for tid, cmd in self._pending_commands.items() if cmd.is_expired()]
            for tid in expired:
                cmd = self._pending_commands.pop(tid)
                cmd.status = CommandStatus.TIMEOUT
                logger.warning("Command '%s' timed out (transaction: %s)", cmd.command, tid)
                if cmd.callback:
                    with suppress(Exception):
                        cmd.callback("timeout", {})

    # =========================================================================
    # Device Commands
    # =========================================================================

    def trigger_read(self) -> bool:
        """
        Trigger immediate sensor read.

        Returns:
            True if command sent successfully
        """
        return self._publish(self._get_get_topic(), "")

    def set_polling_interval(self, interval_ms: int, callback: Callable | None = None) -> str | None:
        """
        Set sensor polling interval.

        Args:
            interval_ms: Polling interval in milliseconds (5000-3600000)
            callback: Optional callback(status, response)

        Returns:
            Transaction ID if sent
        """
        interval_ms = max(5000, min(3600000, interval_ms))
        return self._send_command(
            "set_polling_interval",
            {"polling_interval": interval_ms},
            callback=callback,
        )

    def set_friendly_name(self, new_name: str, callback: Callable | None = None) -> str | None:
        """
        Change device friendly name.

        Args:
            new_name: New friendly name
            callback: Optional callback(status, response)

        Returns:
            Transaction ID if sent
        """
        return self._send_command(
            "set_friendly_name",
            {"friendly_name": new_name},
            callback=callback,
        )

    def set_calibration(
        self,
        temperature_offset: float | None = None,
        humidity_offset: float | None = None,
        callback: Callable | None = None,
    ) -> str | None:
        """
        Set sensor calibration offsets.

        Args:
            temperature_offset: Temperature calibration offset in Celsius
            humidity_offset: Humidity calibration offset in percentage
            callback: Optional callback(status, response)

        Returns:
            Transaction ID if sent
        """
        payload = {}
        if temperature_offset is not None:
            payload["temperature_calibration"] = temperature_offset
        if humidity_offset is not None:
            payload["humidity_calibration"] = humidity_offset

        if not payload:
            return None

        return self._send_command("set_calibration", payload, callback=callback)

    def set_calibration_offset(self, sensor_type: str, offset: float) -> None:
        """
        Set calibration offset (ISensorAdapter-compatible interface).

        This provides a Zigbee2MQTT-compatible interface for calibration.

        Args:
            sensor_type: Type of sensor ('temperature', 'humidity')
            offset: Calibration offset value
        """
        if sensor_type == "temperature":
            self.set_calibration(temperature_offset=offset)
        elif sensor_type == "humidity":
            self.set_calibration(humidity_offset=offset)
        else:
            logger.warning("SYSGrow: Unknown sensor type for calibration: %s", sensor_type)

    def restart_device(self, callback: Callable | None = None) -> str | None:
        """
        Restart the device.

        Args:
            callback: Optional callback(status, response)

        Returns:
            Transaction ID if sent
        """
        return self._send_command(
            "restart",
            {"restart": True},
            callback=callback,
            queue_if_offline=False,  # No point queueing restart
        )

    def factory_reset(self, callback: Callable | None = None) -> str | None:
        """
        Factory reset the device (clears all configuration).

        Args:
            callback: Optional callback(status, response)

        Returns:
            Transaction ID if sent
        """
        return self._send_command(
            "factory_reset",
            {"factory_reset": True},
            callback=callback,
            queue_if_offline=False,
        )

    # =========================================================================
    # Bridge Commands
    # =========================================================================

    def enable_ble_pairing(self, timeout_seconds: int = 30, callback: Callable | None = None) -> str | None:
        """
        Enable BLE pairing mode on device.

        Args:
            timeout_seconds: Pairing timeout (max 300)
            callback: Optional callback(status, response)

        Returns:
            Transaction ID if sent
        """
        timeout_seconds = max(0, min(300, timeout_seconds))
        return self._send_command(
            "permit_join",
            {"value": True, "time": timeout_seconds},
            topic=f"{self.BRIDGE_PREFIX}/request/permit_join",
            callback=callback,
        )

    def disable_ble_pairing(self, callback: Callable | None = None) -> str | None:
        """
        Disable BLE pairing mode.

        Args:
            callback: Optional callback(status, response)

        Returns:
            Transaction ID if sent
        """
        return self._send_command(
            "permit_join",
            {"value": False},
            topic=f"{self.BRIDGE_PREFIX}/request/permit_join",
            callback=callback,
        )

    def rename_via_bridge(self, new_name: str, callback: Callable | None = None) -> str | None:
        """
        Rename device via bridge command.

        Args:
            new_name: New friendly name
            callback: Optional callback(status, response)

        Returns:
            Transaction ID if sent
        """
        return self._send_command(
            "device/rename",
            {"from": self.friendly_name, "to": new_name},
            topic=f"{self.BRIDGE_PREFIX}/request/device/rename",
            callback=callback,
        )

    def remove_device(self, force: bool = False, callback: Callable | None = None) -> str | None:
        """
        Remove/factory reset device via bridge.

        Args:
            force: Force removal even if offline
            callback: Optional callback(status, response)

        Returns:
            Transaction ID if sent
        """
        return self._send_command(
            "device/remove",
            {"id": self.friendly_name, "force": force},
            topic=f"{self.BRIDGE_PREFIX}/request/device/remove",
            callback=callback,
        )

    def start_ota_update(self, firmware_url: str, callback: Callable | None = None) -> str | None:
        """
        Start OTA firmware update.

        Args:
            firmware_url: URL to firmware binary
            callback: Optional callback(status, response)

        Returns:
            Transaction ID if sent
        """
        return self._send_command(
            "device/ota_update/update",
            {"id": self.friendly_name, "url": firmware_url},
            topic=f"{self.BRIDGE_PREFIX}/request/device/ota_update/update",
            callback=callback,
        )

    def request_health_check(self) -> bool:
        """
        Request bridge health check.

        Returns:
            True if request sent
        """
        return self._publish(f"{self.BRIDGE_PREFIX}/request/health_check", "{}")

    # =========================================================================
    # State Accessors
    # =========================================================================

    def get_availability(self) -> DeviceAvailability:
        """Get current device availability."""
        with self._state_lock:
            return self._state.availability

    def get_last_seen(self) -> datetime | None:
        """Get last seen timestamp."""
        with self._state_lock:
            return self._state.last_seen

    def get_firmware_version(self) -> str | None:
        """Get device firmware version."""
        with self._state_lock:
            return self._state.firmware_version

    def get_device_info(self) -> dict[str, Any]:
        """Get device information."""
        with self._state_lock:
            return {
                "friendly_name": self._state.friendly_name,
                "availability": self._state.availability.value,
                "last_seen": self._state.last_seen.isoformat() if self._state.last_seen else None,
                "firmware_version": self._state.firmware_version,
                "device_type": self._state.device_type,
                "mac_address": self._state.mac_address,
                "rssi": self._state.rssi,
                "uptime": self._state.uptime,
                "sensors_status": self._state.sensors_status,
            }

    def get_pending_commands_count(self) -> int:
        """Get number of pending commands."""
        with self._command_lock:
            return len(self._pending_commands)

    def get_queued_commands_count(self) -> int:
        """Get number of queued commands."""
        with self._command_lock:
            return len(self._command_queue)

    # =========================================================================
    # Callbacks
    # =========================================================================

    def on_availability_change(self, callback: Callable[[str, DeviceAvailability], None]) -> None:
        """
        Register availability change callback.

        Args:
            callback: Function(friendly_name, availability)
        """
        self._availability_callbacks.append(callback)

    def remove_availability_callback(self, callback: Callable[[str, DeviceAvailability], None]) -> None:
        """Remove availability callback."""
        if callback in self._availability_callbacks:
            self._availability_callbacks.remove(callback)
