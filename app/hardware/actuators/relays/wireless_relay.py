import json
import logging
import os
from logging.handlers import RotatingFileHandler

import requests

from app.enums.events import DeviceEvent
from app.hardware.mqtt.mqtt_broker_wrapper import MQTTClientWrapper
from app.schemas.events import RelayStatePayload

from .relay_base import RelayBase

# Module-level logger with rotation (prevents unbounded log file growth)
logger = logging.getLogger(__name__)
if not logger.handlers:
    os.makedirs("logs", exist_ok=True)
    _handler = RotatingFileHandler(
        "logs/devices.log",
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=3,
        encoding="utf-8",
    )
    _handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    logger.addHandler(_handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False  # Don't duplicate to root logger


class WirelessRelay(RelayBase):
    """
    A class to represent a wireless relay which can be controlled via Zigbee, WiFi, or BLE.

    Attributes:
        unit_id (str): The unique identifier for the relay unit.
        device (str): The device name.
        zigbee_channel (str): The Zigbee channel to use.
        connection_mode (str): The mode of connection (Zigbee, WiFi, BLE).
        mqtt_broker (str): The MQTT broker address.
        mqtt_port (int): The MQTT broker port.
        ble_client (object): The BLE client instance.
        mqtt_topic (str): The MQTT topic for communication.
        mqtt_client (MQTTClientWrapper): The MQTT client wrapper instance.
    """

    def __init__(
        self, unit_id, device: str, zigbee_channel: str, connection_mode: str, mqtt_broker: str, mqtt_port: int
    ):
        """
        Initialize the WirelessRelay with the given parameters.
        """
        super().__init__(device)
        self.unit_id = unit_id
        self.zigbee_channel = zigbee_channel
        self.connection_mode = connection_mode
        self.mqtt_broker = mqtt_broker
        self.mqtt_port = mqtt_port
        self.ble_client = None
        self.mqtt_topic = zigbee_channel
        self.mqtt_client = MQTTClientWrapper(mqtt_broker, mqtt_port)

    def turn_on(self):
        """
        Turn on the relay based on the connection mode.
        """
        try:
            if self.connection_mode == "Zigbee":
                self._send_mqtt_command("ON")
            elif self.connection_mode == "WiFi":
                self._send_http_command("ON")
            elif self.connection_mode == "BLE":
                self._send_ble_command("ON")
            self.event_bus.publish(
                DeviceEvent.RELAY_STATE_CHANGED,
                RelayStatePayload(device=self.device, state="on"),
            )
        except Exception as e:
            logger.error(f"Error turning on relay {self.device}: {e}")

    def turn_off(self):
        """
        Turn off the relay based on the connection mode.
        """
        try:
            if self.connection_mode == "Zigbee":
                self._send_mqtt_command("OFF")
            elif self.connection_mode == "WiFi":
                self._send_http_command("OFF")
            elif self.connection_mode == "BLE":
                self._send_ble_command("OFF")
            self.event_bus.publish(
                DeviceEvent.RELAY_STATE_CHANGED,
                RelayStatePayload(device=self.device, state="off"),
            )
        except Exception as e:
            logger.error(f"Error turning off relay {self.device}: {e}")

    def set_connection_mode(self, mode: str):
        """
        Set the connection mode for the relay.

        Args:
            mode (str): The connection mode to set (WiFi, BLE, Zigbee).
        """
        if mode not in ["WiFi", "BLE", "Zigbee"]:
            raise ValueError(f"Invalid connection mode: {mode}")
        self.connection_mode = mode

    def _send_mqtt_command(self, state: str):
        """
        Send an MQTT command to change the relay state.

        Args:
            state (str): The state to set (ON, OFF).
        """
        payload = {"state": state}
        self.mqtt_client.publish(self.mqtt_topic, json.dumps(payload))

    def _send_http_command(self, state: str):
        """
        Send an HTTP command to change the relay state.

        Args:
            state (str): The state to set (ON, OFF).
        """
        url = f"http://{self.mqtt_broker}/relay/{self.device}/{state.lower()}"
        try:
            response = requests.get(url, timeout=5)
            response.raise_for_status()
        except requests.RequestException as e:
            raise Exception(f"Error sending HTTP command to {url}: {e}")

    def _send_ble_command(self, state: str):
        """
        Send a BLE command to change the relay state.

        Args:
            state (str): The state to set (ON, OFF).
        """
        if self.ble_client:
            try:
                self.ble_client.write(f"{self.device},{state}")
            except Exception as e:
                raise Exception(f"BLE command error: {e}")

    def update_wifi_credentials(self, topic, encrypted_payload):
        """
        Update the WiFi credentials via MQTT.

        Args:
            topic (str): The MQTT topic to publish to.
            encrypted_payload (dict): The encrypted WiFi credentials.
        """
        self.mqtt_client.publish(topic, json.dumps(encrypted_payload))

    def update_esp32_mqtt_topic(self, new_topic):
        """
        Update the MQTT topic for the ESP32.

        Args:
            new_topic (str): The new MQTT topic.
        """
        payload = json.dumps({"new_topic": new_topic})
        self.mqtt_client.publish(self.mqtt_topic, payload)
        self.mqtt_topic = new_topic

    def cleanup(self):
        """
        Clean up resources by disconnecting MQTT and BLE clients.
        """
        self.mqtt_client.disconnect()
        if self.ble_client:
            self.ble_client.disconnect()

    def __del__(self):
        """
        Destructor to ensure cleanup is called.
        """
        self.cleanup()
