"""
Zigbee2MQTT Sensor Adapter
===========================
Adapter for sensors using Zigbee2MQTT bridge.
Supports plug-and-play Zigbee sensors without ESP32-C6.
This adapter is for commercial Zigbee2MQTT-compatible sensors.
"""

import json
import logging
from datetime import datetime
from typing import Any

from .base_adapter import AdapterError, ISensorAdapter

logger = logging.getLogger(__name__)


class Zigbee2MQTTAdapter(ISensorAdapter):
    """
    Adapter for Zigbee2MQTT sensors.

    Supports various Zigbee sensors including:
    - 4-in-1 sensors (soil moisture + temperature + humidity + luminance)
    - 3-in-1 sensors (without luminance)
    - Individual sensors (temperature, humidity, soil moisture, etc.)

    Uses Zigbee2MQTT bridge as middleware.
    """

    def __init__(
        self,
        sensor_id: int,
        mqtt_client,
        friendly_name: str,
        sensor_capabilities: list[str],
        timeout: int = 600,
        ieee_address: str | None = None,
        calibration_offsets: dict[str, float] | None = None,
        **kwargs,
    ):
        """
        Initialize Zigbee2MQTT adapter.

        Args:
            sensor_id: Unique sensor ID
            mqtt_client: MQTT client instance
            friendly_name: Zigbee2MQTT friendly name (e.g., "garden_sensor_1")
            sensor_capabilities: List of sensor capabilities (e.g., ["temperature", "humidity", "soil_moisture", "illuminance"])
            timeout: Data timeout in seconds (default: 600 for battery sensors that report infrequently)
            ieee_address: IEEE address of the Zigbee device
            calibration_offsets: Initial calibration offsets
        """
        self.sensor_id = sensor_id
        self.mqtt_client = mqtt_client
        self.friendly_name = friendly_name
        self.sensor_capabilities = sensor_capabilities
        self.timeout = timeout
        self.ieee_address = ieee_address

        # Zigbee2MQTT topic structure
        # Subscribe to: zigbee2mqtt/<friendly_name>
        self.mqtt_topic = f"zigbee2mqtt/{friendly_name}"
        self.availability_topic = f"{self.mqtt_topic}/availability"

        # Bridge topic for device operations
        self._bridge_topic = "zigbee2mqtt"

        # Cache for latest reading
        self._last_data: dict[str, Any] | None = None
        self._last_update: datetime | None = None

        # Availability: Default to True (optimistic) - will be set False by
        # availability message if device is offline. This allows newly added
        # sensors to work immediately without waiting for an availability message.
        self._available = True
        self._device_available = True

        # Device calibration offsets
        self._calibration_offsets: dict[str, float] = calibration_offsets or {}

        # Device metadata cache
        self._device_info: dict[str, Any] | None = None

        # NOTE: MQTT subscriptions are now handled by MQTTSensorService (unified)
        # This adapter is passive - it only provides the read() interface
        # MQTTSensorService will call update_data() when messages arrive
        logger.info(f"Zigbee2MQTT adapter initialized for: {self.mqtt_topic} (passive mode)")

    def update_data(self, payload: dict[str, Any]) -> None:
        """
        Update adapter data from MQTTSensorService.
        Called when MQTTSensorService receives a message for this sensor.

        Args:
            payload: Zigbee2MQTT message payload (already parsed JSON)
        """
        try:
            # Zigbee2MQTT publishes all sensor values in one message
            # Extract only the capabilities we care about
            filtered_data = {}

            for capability in self.sensor_capabilities:
                # Map common Zigbee2MQTT keys to our internal keys
                key_mapping = {
                    "temperature": ["temperature", "temp"],
                    "humidity": ["humidity", "relative_humidity"],
                    "soil_moisture": ["soil_moisture", "moisture"],
                    "illuminance": ["illuminance", "illuminance_lux", "lux"],
                    "battery": ["battery", "battery_percent"],
                    "linkquality": ["linkquality", "link_quality"],
                    "pressure": ["pressure"],
                    "voltage": ["voltage"],
                }

                # Try to find the value in payload
                for key in key_mapping.get(capability, [capability]):
                    if key in payload:
                        filtered_data[capability] = payload[key]
                        break

            # Add metadata
            if "battery" in payload:
                filtered_data["battery"] = payload["battery"]
            if "linkquality" in payload:
                filtered_data["linkquality"] = payload["linkquality"]

            # Add friendly_name for Socket.IO broadcast identification
            filtered_data["friendly_name"] = self.friendly_name

            # Extract device calibration offsets (if present)
            calibration_keys = [
                "temperature_calibration",
                "humidity_calibration",
                "soil_moisture_calibration",
                "illuminance_calibration",
            ]
            for key in calibration_keys:
                if key in payload:
                    # Store calibration offset (e.g., temperature_calibration -> temperature)
                    base_key = key.replace("_calibration", "")
                    self._calibration_offsets[base_key] = payload[key]

            self._last_data = filtered_data
            self._last_update = datetime.now()
            self._device_available = True

            logger.debug(f"Zigbee2MQTT {self.friendly_name} data updated: {filtered_data}")

        except Exception as e:
            logger.error(f"Error updating Zigbee2MQTT data for {self.friendly_name}: {e}")

    def _on_mqtt_message(self, client, userdata, msg):
        """
        DEPRECATED: MQTT subscriptions now handled by MQTTSensorService.
        This method kept for backward compatibility but should not be called.
        """
        logger.warning(
            "Zigbee2MQTTAdapter._on_mqtt_message() called directly - "
            "this should not happen. MQTT subscriptions should be handled by MQTTSensorService."
        )
        try:
            payload = json.loads(msg.payload.decode())
            self.update_data(payload)
        except Exception as e:
            logger.error(f"Error in legacy _on_mqtt_message handler: {e}")

    def _on_availability_message(self, client, userdata, msg):
        """
        Callback for availability messages.

        Args:
            client: MQTT client
            userdata: User data
            msg: MQTT message
        """
        try:
            payload_str = msg.payload.decode()

            # Check if this is JSON (unexpected bridge health data on availability topic)
            if payload_str.startswith("{"):
                # This is bridge health data, not availability status
                # Log it once but don't treat as availability
                logger.debug(f"Received bridge health data on availability topic for {self.friendly_name}")
                # Don't update device_available based on health data
                return

            # Normal availability message: "online" or "offline"
            status = payload_str.lower()
            self._device_available = status == "online"
            logger.info(f"Zigbee2MQTT device {self.friendly_name} is {status}")
        except Exception as e:
            logger.error(f"Error processing availability message: {e}")

    def read(self) -> dict[str, Any]:
        """
        Read cached data from Zigbee2MQTT sensor.

        Returns:
            Dict with sensor readings. Includes '_stale' flag if data is older than timeout,
            or '_no_data' flag if no data has been received yet.

        Raises:
            AdapterError: If device is explicitly offline
        """
        if not self._device_available:
            raise AdapterError(f"Zigbee2MQTT device {self.friendly_name} is offline")

        if self._last_data is None:
            # No data received yet - return empty result with warning flag
            # This is normal on startup before sensor reports
            logger.debug(f"No Zigbee2MQTT data received yet from {self.friendly_name}")
            return {"_no_data": True, "_waiting": True}

        result = self._last_data.copy()

        # Check if data is stale - warn but don't fail
        # Battery-powered Zigbee sensors may report infrequently
        if self._last_update:
            age = (datetime.now() - self._last_update).total_seconds()
            if age > self.timeout:
                result["_stale"] = True
                result["_age_seconds"] = age
                logger.debug(
                    f"Zigbee2MQTT data from {self.friendly_name} is stale "
                    f"(age: {age:.1f}s, timeout: {self.timeout}s) - returning cached data"
                )

        return result

    def configure(self, config: dict[str, Any]) -> None:
        """
        Reconfigure Zigbee2MQTT adapter.

        Args:
            config: Configuration dictionary
        """
        if "timeout" in config:
            self.timeout = config["timeout"]

        if "sensor_capabilities" in config:
            self.sensor_capabilities = config["sensor_capabilities"]

        if "friendly_name" in config and config["friendly_name"] != self.friendly_name:
            # Unsubscribe from old topics
            if self.mqtt_client:
                try:
                    self.mqtt_client.unsubscribe(self.mqtt_topic)
                    self.mqtt_client.unsubscribe(self.availability_topic)
                except Exception as e:
                    logger.warning(f"Failed to unsubscribe from old topics: {e}")

            # Update friendly name and topics
            self.friendly_name = config["friendly_name"]
            self.mqtt_topic = f"zigbee2mqtt/{self.friendly_name}"
            self.availability_topic = f"{self.mqtt_topic}/availability"

            # Subscribe to new topics
            if self.mqtt_client:
                try:
                    self.mqtt_client.subscribe(self.mqtt_topic, self._on_mqtt_message)
                    self.mqtt_client.subscribe(self.availability_topic, self._on_availability_message)
                    logger.info(f"Resubscribed to Zigbee2MQTT: {self.mqtt_topic}")
                except Exception as e:
                    logger.error(f"Failed to subscribe to new topics: {e}")
                    raise AdapterError(f"Failed to reconfigure Zigbee2MQTT: {e}")

    def is_available(self) -> bool:
        """
        Check if Zigbee2MQTT sensor is available.

        Returns:
            True if device is online and data is recent
        """
        if not self._available or not self.mqtt_client or not self._device_available:
            return False

        # Check if we have recent data
        if self._last_update:
            age = (datetime.now() - self._last_update).total_seconds()
            return age <= self.timeout

        return False

    def get_protocol_name(self) -> str:
        """Get protocol name"""
        return "Zigbee2MQTT"

    def get_capabilities(self) -> list[str]:
        """
        Get list of sensor capabilities.

        Returns:
            List of capability names
        """
        return self.sensor_capabilities.copy()

    def has_capability(self, capability: str) -> bool:
        """
        Check if sensor has a specific capability.

        Args:
            capability: Capability name (e.g., "temperature", "soil_moisture")

        Returns:
            True if sensor has the capability
        """
        return capability in self.sensor_capabilities

    def get_calibration_offsets(self) -> dict[str, float]:
        """
        Get device-level calibration offsets.

        These are the calibration values stored on the Zigbee device itself.

        Returns:
            Dictionary mapping sensor type to calibration offset
            Example: {'temperature': -1.5, 'humidity': 2.0}
        """
        return self._calibration_offsets.copy()

    def set_calibration_offset(self, sensor_type: str, offset: float) -> None:
        """
        Set calibration offset on Zigbee2MQTT device.

        Sends a SET command to the device to update its internal calibration.

        Args:
            sensor_type: Type of sensor (e.g., 'temperature', 'humidity')
            offset: Calibration offset value

        Raises:
            AdapterError: If MQTT publish fails
        """
        if not self.mqtt_client:
            raise AdapterError("MQTT client not available")

        calibration_key = f"{sensor_type}_calibration"
        set_topic = f"{self.mqtt_topic}/set"

        try:
            payload = json.dumps({calibration_key: offset})
            self.mqtt_client.publish(set_topic, payload)

            # Update local cache
            self._calibration_offsets[sensor_type] = offset

            logger.info(f"Set {calibration_key} = {offset} for {self.friendly_name}")
        except Exception as e:
            raise AdapterError(f"Failed to set calibration: {e}")

    def send_command(self, command: dict[str, Any]) -> bool:
        """
        Send arbitrary command to Zigbee2MQTT device.

        Args:
            command: Command dictionary (e.g., {'identify': True})

        Returns:
            True if command was sent successfully

        Raises:
            AdapterError: If MQTT client not available
        """
        if not self.mqtt_client:
            raise AdapterError("MQTT client not available")

        set_topic = f"{self.mqtt_topic}/set"

        try:
            payload = json.dumps(command)
            self.mqtt_client.publish(set_topic, payload)
            logger.debug(f"Sent command to {self.friendly_name}: {command}")
            return True
        except Exception as e:
            logger.error(f"Failed to send command to {self.friendly_name}: {e}")
            return False

    # ==================== Device Operations ====================

    def identify(self, duration: int = 10) -> bool:
        """
        Trigger device identification (e.g., flash LED).

        Many Zigbee devices support an identify command that causes
        them to blink or otherwise indicate their presence.

        Args:
            duration: Identification duration in seconds

        Returns:
            True if command sent successfully
        """
        return self.send_command({"identify": duration})

    def get_state(self) -> dict[str, Any]:
        """
        Get current device state from cache.

        Returns:
            Dictionary with current sensor readings and metadata
        """
        state = {
            "friendly_name": self.friendly_name,
            "ieee_address": self.ieee_address,
            "available": self._device_available,
            "last_update": self._last_update.isoformat() if self._last_update else None,
        }

        if self._last_data:
            state["readings"] = self._last_data.copy()

        return state

    def get_device_info(self) -> dict[str, Any]:
        """
        Get device information and metadata.

        Returns:
            Dictionary with device info including capabilities,
            model, firmware version, etc.
        """
        return {
            "sensor_id": self.sensor_id,
            "friendly_name": self.friendly_name,
            "ieee_address": self.ieee_address,
            "mqtt_topic": self.mqtt_topic,
            "protocol": self.get_protocol_name(),
            "capabilities": self.sensor_capabilities.copy(),
            "timeout": self.timeout,
            "available": self._device_available,
            "calibration_offsets": self._calibration_offsets.copy(),
            "last_update": self._last_update.isoformat() if self._last_update else None,
        }

    def rename(self, new_name: str) -> bool:
        """
        Rename device in Zigbee2MQTT.

        Sends a rename request to the Zigbee2MQTT bridge.
        Note: The adapter's friendly_name will be updated on success,
        but the caller should also update the database.

        Args:
            new_name: New friendly name for the device

        Returns:
            True if rename command was sent successfully
        """
        if not self.mqtt_client:
            logger.error("MQTT client not available for rename")
            return False

        if not self.ieee_address and not self.friendly_name:
            logger.error("No device identifier available for rename")
            return False

        # Use IEEE address if available, otherwise use current friendly name
        device_id = self.ieee_address or self.friendly_name

        payload = {"from": device_id, "to": new_name, "homeassistant_rename": False}

        try:
            topic = f"{self._bridge_topic}/bridge/request/device/rename"
            self.mqtt_client.publish(topic, json.dumps(payload))
            logger.info(f"Sent rename request for {device_id} -> {new_name}")

            # Update local state (actual success depends on bridge response)
            old_name = self.friendly_name
            self.friendly_name = new_name
            self.mqtt_topic = f"zigbee2mqtt/{new_name}"
            self.availability_topic = f"{self.mqtt_topic}/availability"

            logger.info(f"Updated adapter friendly_name: {old_name} -> {new_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to rename device: {e}")
            return False

    def remove_from_network(self) -> bool:
        """
        Remove device from Zigbee network.

        Sends a remove request to the Zigbee2MQTT bridge.
        The device will need to be re-paired to rejoin the network.

        Returns:
            True if remove command was sent successfully
        """
        if not self.mqtt_client:
            logger.error("MQTT client not available for remove")
            return False

        device_id = self.ieee_address or self.friendly_name
        if not device_id:
            logger.error("No device identifier available for remove")
            return False

        payload = {"id": device_id}

        try:
            topic = f"{self._bridge_topic}/bridge/request/device/remove"
            self.mqtt_client.publish(topic, json.dumps(payload))
            logger.info(f"Sent remove request for device: {device_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to remove device: {e}")
            return False

    def update_device_info(self, info: dict[str, Any]) -> None:
        """
        Update cached device information.

        Called when device metadata is received from the bridge.

        Args:
            info: Device information dictionary
        """
        self._device_info = info

        # Update IEEE address if provided
        if "ieee_address" in info:
            self.ieee_address = info["ieee_address"]

    def cleanup(self) -> None:
        """Cleanup Zigbee2MQTT subscriptions"""
        if self.mqtt_client:
            try:
                self.mqtt_client.unsubscribe(self.mqtt_topic)
                self.mqtt_client.unsubscribe(self.availability_topic)
                logger.info(f"Unsubscribed from Zigbee2MQTT: {self.mqtt_topic}")
            except Exception as e:
                logger.warning(f"Error during Zigbee2MQTT cleanup: {e}")
