"""
Zigbee Sensor Adapter
=====================
Adapter for sensors connected to ESP32-C6 via Zigbee protocol.
"""

import json
import logging
from datetime import datetime
from typing import Any

from .base_adapter import AdapterError, ISensorAdapter

logger = logging.getLogger(__name__)


class ZigbeeAdapter(ISensorAdapter):
    """
    Adapter for ESP32-C6 Zigbee sensors.
    Communicates with ESP32-C6 devices that have Zigbee sensors connected.
    Uses MQTT as transport layer for ESP32-C6 communication.
    """

    def __init__(
        self,
        sensor_id: int,
        mqtt_client,
        esp32_device_id: int,
        zigbee_ieee: str,
        sensor_type: str,
        timeout: int = 60,
        primary_metrics: list[str] | None = None,
    ):
        """
        Initialize Zigbee adapter.

        Args:
            sensor_id: Unique sensor ID
            mqtt_client: MQTT client for ESP32-C6 communication
            esp32_device_id: ESP32-C6 device ID
            zigbee_ieee: Zigbee IEEE address of the sensor
            sensor_type: Type of sensor (temperature, humidity, etc.)
            timeout: Data timeout in seconds
            primary_metrics: Optional list of primary metrics for this sensor
        """
        self.sensor_id = sensor_id
        self.mqtt_client = mqtt_client
        self.esp32_device_id = esp32_device_id
        self.zigbee_ieee = zigbee_ieee
        self.sensor_type = sensor_type
        self.timeout = timeout

        # MQTT topics for ESP32-C6 Zigbee communication
        # Topic format: growtent/esp32c6/<device_id>/zigbee/<ieee>/<sensor_type>
        self.mqtt_topic = f"growtent/esp32c6/{esp32_device_id}/zigbee/{zigbee_ieee}/{sensor_type}"
        self.command_topic = f"growtent/esp32c6/{esp32_device_id}/zigbee/{zigbee_ieee}/cmd"

        # Cache for latest reading
        self._last_data: dict[str, Any] | None = None
        self._last_update: datetime | None = None
        self._available = False

        # Subscribe to MQTT topic
        if self.mqtt_client:
            try:
                self.mqtt_client.subscribe(self.mqtt_topic, self._on_mqtt_message)
                self._available = True
                logger.info(f"Zigbee adapter subscribed to: {self.mqtt_topic}")
            except Exception as e:
                logger.error(f"Failed to subscribe to Zigbee topic: {e}")
                self._available = False

    def _on_mqtt_message(self, client, userdata, msg):
        """
        Callback for MQTT messages from ESP32-C6 Zigbee sensor.

        Args:
            client: MQTT client
            userdata: User data
            msg: MQTT message
        """
        try:
            payload = json.loads(msg.payload.decode())

            # Validate that the message is for this sensor
            if payload.get("ieee") == self.zigbee_ieee:
                self._last_data = payload.get("data", payload)
                self._last_update = datetime.now()
                logger.debug(f"Zigbee sensor {self.zigbee_ieee} data: {self._last_data}")

        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode Zigbee MQTT message: {e}")
        except Exception as e:
            logger.error(f"Error processing Zigbee message: {e}")

    def read(self) -> dict[str, Any]:
        """
        Read cached data from Zigbee sensor.

        Returns:
            Dict with sensor readings

        Raises:
            AdapterError: If no recent data available
        """
        if self._last_data is None:
            # Try to request fresh data from ESP32-C6
            self._request_sensor_read()
            raise AdapterError(f"No Zigbee data received yet from {self.zigbee_ieee}")

        # Check if data is stale
        if self._last_update:
            age = (datetime.now() - self._last_update).total_seconds()
            if age > self.timeout:
                # Request fresh data
                self._request_sensor_read()
                raise AdapterError(f"Zigbee data is stale (age: {age:.1f}s, timeout: {self.timeout}s)")

        return self._last_data.copy()

    def _request_sensor_read(self):
        """Request ESP32-C6 to read from Zigbee sensor"""
        if self.mqtt_client:
            try:
                command = {"cmd": "read", "ieee": self.zigbee_ieee, "sensor_type": self.sensor_type}
                self.mqtt_client.publish(self.command_topic, json.dumps(command))
                logger.debug(f"Requested Zigbee sensor read from {self.zigbee_ieee}")
            except Exception as e:
                logger.error(f"Failed to request Zigbee sensor read: {e}")

    def configure(self, config: dict[str, Any]) -> None:
        """
        Reconfigure Zigbee adapter.

        Args:
            config: Configuration dictionary
        """
        if "timeout" in config:
            self.timeout = config["timeout"]

        if "zigbee_ieee" in config and config["zigbee_ieee"] != self.zigbee_ieee:
            # Unsubscribe from old topic
            if self.mqtt_client:
                try:
                    self.mqtt_client.unsubscribe(self.mqtt_topic)
                except Exception as e:
                    logger.warning(f"Failed to unsubscribe from {self.mqtt_topic}: {e}")

            # Update IEEE and topics
            self.zigbee_ieee = config["zigbee_ieee"]
            self.mqtt_topic = f"growtent/esp32c6/{self.esp32_device_id}/zigbee/{self.zigbee_ieee}/{self.sensor_type}"
            self.command_topic = f"growtent/esp32c6/{self.esp32_device_id}/zigbee/{self.zigbee_ieee}/cmd"

            # Subscribe to new topic
            if self.mqtt_client:
                try:
                    self.mqtt_client.subscribe(self.mqtt_topic, self._on_mqtt_message)
                    logger.info(f"Resubscribed to Zigbee topic: {self.mqtt_topic}")
                except Exception as e:
                    logger.error(f"Failed to subscribe to new Zigbee topic: {e}")
                    raise AdapterError(f"Failed to reconfigure Zigbee: {e}")

    def is_available(self) -> bool:
        """
        Check if Zigbee sensor is available.

        Returns:
            True if connected and data is recent
        """
        if not self._available or not self.mqtt_client:
            return False

        # Check if we have recent data
        if self._last_update:
            age = (datetime.now() - self._last_update).total_seconds()
            return age <= self.timeout

        return False

    def get_protocol_name(self) -> str:
        """Get protocol name"""
        return "Zigbee"

    def cleanup(self) -> None:
        """Cleanup Zigbee MQTT subscription"""
        if self.mqtt_client:
            try:
                self.mqtt_client.unsubscribe(self.mqtt_topic)
                logger.info(f"Unsubscribed from Zigbee topic: {self.mqtt_topic}")
            except Exception as e:
                logger.warning(f"Error during Zigbee cleanup: {e}")
