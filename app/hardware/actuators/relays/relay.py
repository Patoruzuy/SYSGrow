"""
Relay Control System

This module defines a base class and three subclasses to control relays via different
communication methods: GPIO (wired), WiFi (HTTP API), and Zigbee (MQTT).

Classes:
    - RelayBase: Abstract base class for all relay types.
    - GPIORelay: Controls a relay via Raspberry Pi GPIO.
    - WiFiRelay: Controls a relay via an HTTP API (e.g., ESP8266).
    - ZigbeeRelay: Controls a relay via Zigbee2MQTT.

Author: Sebastian Gomez
Date: 01/03/2025
"""

import json
import logging
import os
from logging.handlers import RotatingFileHandler

import requests

from app.enums.events import DeviceEvent
from app.hardware.mqtt.mqtt_broker_wrapper import MQTTClientWrapper
from app.schemas.events import RelayStatePayload
from app.utils.event_bus import EventBus

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


class RelayBase:
    """
    Abstract base class for all relay types.

    Attributes:
        device (str): The name of the device controlled by the relay.

    Methods:
        turn_on(): Turns the relay on. (Implemented in subclasses)
        turn_off(): Turns the relay off. (Implemented in subclasses)
        get_device(): Returns the device name.
    """

    def __init__(self, device: str):
        """
        Initializes the relay with a device name.

        Args:
            device (str): The name of the device controlled by the relay.
        """
        self.device = device
        self.event_bus = EventBus()  # Get the global EventBus instance

    def turn_on(self):
        """Turns the relay on. It is implemented in subclasses."""
        pass

    def turn_off(self):
        """Turns the relay off. It is implemented in subclasses."""
        pass

    def get_device(self) -> str:
        """
        Returns the name of the device.

        Returns:
            str: The device name.
        """
        return self.device


class GPIORelay(RelayBase):
    """
    Controls a relay using Raspberry Pi GPIO.

    Attributes:
        device (str): The name of the controlled device.
        pin (int): The GPIO pin used to control the relay.

    Methods:
        turn_on(): Turns the relay on by setting the GPIO pin HIGH.
        turn_off(): Turns the relay off by setting the GPIO pin LOW.
        cleanup(): Releases the GPIO pin resources.
    """

    def __init__(self, device: str, pin: int):
        """
        Initializes the GPIO relay with the specified GPIO pin.

        Args:
            device (str): The name of the device.
            pin (int): The GPIO pin number to control the relay.
        """
        super().__init__(device)
        self.pin = pin
        self.GPIO = self._setup_gpio()
        if self.GPIO:
            self.GPIO.setmode(self.GPIO.BCM)
            self.GPIO.setup(self.pin, self.GPIO.OUT)
            logger.info(f"GPIO pin {self.pin} set as OUTPUT")
        else:
            logger.warning(f"GPIO is not available.  GPIO Relay {self.device} will not function.")

    def _setup_gpio(self):
        """Imports and sets up GPIO only if running on Raspberry Pi."""
        try:
            import RPi.GPIO as GPIO  # type: ignore

            return GPIO
        except (ImportError, RuntimeError):
            logger.error("GPIO not available. Running in non-Raspberry Pi environment.")
            return None

    def turn_on(self):
        """Turns the relay on by setting the GPIO pin HIGH."""
        if self.GPIO:
            try:
                self.GPIO.output(self.pin, self.GPIO.HIGH)
                self.event_bus.publish(
                    DeviceEvent.RELAY_STATE_CHANGED,
                    RelayStatePayload(device=self.device, state="on"),
                )  # Publish Event
                logger.info(f"Turned on GPIO relay for {self.device} on pin {self.pin}")
            except Exception as e:
                logger.error(f"Error turning on GPIO relay {self.device}: {e}")
        else:
            logger.warning(f"GPIO not initialized. Cannot turn on relay {self.device}")

    def turn_off(self):
        """Turns the relay off by setting the GPIO pin LOW."""
        if self.GPIO:
            try:
                self.GPIO.output(self.pin, self.GPIO.LOW)
                self.event_bus.publish(
                    DeviceEvent.RELAY_STATE_CHANGED,
                    RelayStatePayload(device=self.device, state="off"),
                )  # Publish Event
                logger.info(f"Turned off GPIO relay for {self.device} on pin {self.pin}")
            except Exception as e:
                logger.error(f"Error turning off GPIO relay {self.device}: {e}")
        else:
            logger.warning(f"GPIO not initialized. Cannot turn off relay {self.device}")

    def cleanup(self):
        """Releases the GPIO pin resources."""
        if self.GPIO:
            try:
                self.GPIO.cleanup(self.pin)
                logger.info(f"Cleaned up GPIO pin {self.pin} for {self.device}")
            except Exception as e:
                logger.error(f"Error cleaning up GPIO pin {self.pin}: {e}")

    def __enter__(self):
        """Enter the runtime context related to this object."""
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """Exit the runtime context related to this object."""
        self.cleanup()

    def __del__(self):
        """Destructor to ensure cleanup is called when the object is destroyed."""
        self.cleanup()


class WiFiRelay(RelayBase):
    """
    Controls a relay via an HTTP API (e.g., ESP8266 or ESP-01).

    Attributes:
        device (str): The name of the controlled device.
        ip (str): The IP address of the relay module.

    Methods:
        turn_on(): Sends an HTTP request to turn on the relay.
        turn_off(): Sends an HTTP request to turn off the relay.
    """

    def __init__(self, device: str, ip: str):
        """
        Initializes the WiFi relay with an IP address.

        Args:
            device (str): The name of the device.
            ip (str): The IP address of the relay module.
        """
        super().__init__(device)
        self.ip = ip

    def turn_on(self):
        """Sends an HTTP request to turn on the relay."""
        try:
            self._send_request("on")
            self.event_bus.publish(
                DeviceEvent.RELAY_STATE_CHANGED,
                RelayStatePayload(device=self.device, state="on"),
            )  # Publish Event
            logger.info(f"Turned on WiFi relay for {self.device} at {self.ip}")
        except Exception as e:
            logger.error(f"Error turning on WiFi relay {self.device}: {e}")

    def turn_off(self):
        """Sends an HTTP request to turn off the relay."""
        try:
            self._send_request("off")
            self.event_bus.publish(
                DeviceEvent.RELAY_STATE_CHANGED,
                RelayStatePayload(device=self.device, state="off"),
            )  # Publish Event
            logger.info(f"Turned off WiFi relay for {self.device} at {self.ip}")
        except Exception as e:
            logger.error(f"Error turning off WiFi relay {self.device}: {e}")

    def _send_request(self, state: str):
        """
        Sends an HTTP request to the relay module.

        Args:
            state (str): The relay state ('on' or 'off').
        """
        url = f"http://{self.ip}/relay/{state}"
        try:
            response = requests.get(url, timeout=5)  # Added timeout
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise Exception(f"Error controlling relay at {url}: {e}") from e


class WirelessRelay(RelayBase):
    """
    Controls a relay using Wi-Fi, Bluetooth, and Zigbee2MQTT via an MQTT broker.

    Attributes:
        device (str): The name of the controlled device.
        zigbee_channel (str): The relay channel of the device.
        mqtt_broker (str): The MQTT broker address (default: localhost).
        mqtt_port (int): The MQTT broker port (default: 1883).
        connection_mode (str): The communication mode ('WiFi', 'BLE', 'Zigbee').
        wifi_config_topic (str): The MQTT topic for Wi-Fi configuration.
    Methods:
        turn_on(): Activates the relay based on the selected communication mode.
        turn_off(): Deactivates the relay based on the selected communication mode.
        update_wifi_credentials(): Sends new Wi-Fi credentials over MQTT.
        cleanup(): Cleans up MQTT and Bluetooth resources.
        update_mqtt_topic(): Updates the MQTT topic for the relay.
    """

    def __init__(
        self, unit_id, device: str, zigbee_channel: str, connection_mode: str, mqtt_broker: str, mqtt_port: int
    ):
        """
        Initializes the relay with the chosen communication method.

        Args:
            device (str): The name of the device.
            zigbee_channel (str): The relay channel of the device.
            connection_mode (str, optional): Communication mode ('WiFi', 'BLE', 'Zigbee').
            mqtt_broker (str, optional): The MQTT broker address (default: localhost).
            mqtt_port (int, optional): The MQTT broker port (default: 1883).
        """
        super().__init__(device)
        self.unit_id = unit_id
        self.device = device
        self.zigbee_channel = zigbee_channel
        self.connection_mode = connection_mode
        self.mqtt_broker = mqtt_broker
        self.mqtt_port = mqtt_port
        self.ble_client = None
        self.mqtt_topic = zigbee_channel  # Default MQTT topic
        self.mqtt_client = MQTTClientWrapper(mqtt_broker, mqtt_port)

        print(f"Relay initialized for {device} using {connection_mode} at channel {self.zigbee_channel}")

    def turn_on(self):
        """Activates the relay based on the selected communication mode."""
        try:
            if self.connection_mode == "Zigbee":
                self._send_mqtt_command("ON")
            elif self.connection_mode == "WiFi":
                self._send_http_command("ON")
            elif self.connection_mode == "BLE":
                self._send_ble_command("ON")
            else:
                raise ValueError(f"Invalid communication mode selected: {self.connection_mode}")
            self.event_bus.publish(
                DeviceEvent.RELAY_STATE_CHANGED,
                RelayStatePayload(device=self.device, state="on"),
            )  # Publish Event
            logger.info(f"Turned on {self.connection_mode} relay for {self.device}")
        except Exception as e:
            logger.error(f"Error turning on relay {self.device}: {e}")

    def turn_off(self):
        """Deactivates the relay based on the selected communication mode."""
        try:
            if self.connection_mode == "Zigbee":
                self._send_mqtt_command("OFF")
            elif self.connection_mode == "WiFi":
                self._send_http_command("OFF")
            elif self.connection_mode == "BLE":
                self._send_ble_command("OFF")
            else:
                raise ValueError(f"Invalid communication mode selected: {self.connection_mode}")
            self.event_bus.publish(
                DeviceEvent.RELAY_STATE_CHANGED,
                RelayStatePayload(device=self.device, state="off"),
            )  # Publish Event
            logger.info(f"Turned off {self.connection_mode} relay for {self.device}")
        except Exception as e:
            logger.error(f"Error turning off relay {self.device}: {e}")

    def set_connection_mode(self, mode: str):
        """
        Changes the connection mode dynamically at runtime.
        Args:
            mode (str): 'WiFi', 'BLE', or 'Zigbee'
        """
        if mode not in ["WiFi", "BLE", "Zigbee"]:
            raise ValueError(f"Invalid mode: {mode}")
        logger.info(f"Switching connection mode to: {mode}")
        self.connection_mode = mode

    def _send_mqtt_command(self, state: str):
        """
        Sends an MQTT command to the Zigbee relay.

        Args:
            state (str): The relay state ('ON' or 'OFF').
        """
        topic = self.mqtt_topic  # Use the instance variable
        payload = {"state": state}
        self.mqtt_client.publish(topic, json.dumps(payload))

    def _send_http_command(self, state: str):
        """
        Sends an HTTP request to control the Wi-Fi relay.

        Args:
            state (str): The relay state ('ON' or 'OFF').
        """
        url = f"http://{self.mqtt_broker}/relay/{self.device}/{state.lower()}"
        try:
            response = requests.get(url, timeout=5)  # Added timeout
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise Exception(f"Error sending HTTP command to {url}: {e}") from e

    def _send_ble_command(self, state: str):
        """
        Sends a BLE command to control the Bluetooth relay.

        Args:
            state (str): The relay state ('ON' or 'OFF').
        """
        if self.ble_client:
            try:
                self.ble_client.write(f"{self.device},{state}")
                logger.debug(f"BLE Command Sent: {state}")
            except Exception as e:
                raise Exception(f"Error sending BLE command: {e}") from e
        else:
            logger.warning("BLE client not initialized.")

    def update_wifi_credentials(self, mqtt_topic, encrypted_payload):
        """
        Updates Wi-Fi credentials on the ESP32-C6 via MQTT.

        Args:
            mqtt_topic (str): mqtt topic for the module to be updated
            encrypted_payload (dict): The encrypted ssid and password
        """
        # topic = self.wifi_config_topic
        topic = mqtt_topic  # Use the parameter
        payload = json.dumps(encrypted_payload)  # Use the encrypted payload
        self.mqtt_client.publish(topic, payload)
        logger.info(f"Sent new Wi-Fi credentials to topic {topic}")

    def update_esp32_mqtt_topic(self, new_topic):
        """
        Updates the module ESP32-C6 MQTT topic for the relay.

        Args:
            new_topic (str): The new MQTT topic.
        """
        topic = self.mqtt_topic
        payload = json.dumps({"new_topic": new_topic})
        self.mqtt_client.publish(topic, payload)
        self.mqtt_topic = new_topic
        logger.info(f"Sent MQTT topic update command to ESP32-C6: {new_topic}")

    def cleanup(self):
        """Stops the MQTT loop, disconnects BLE, and cleans up resources."""
        self.mqtt_client.disconnect()
        if self.ble_client:
            try:
                self.ble_client.disconnect()
                logger.info("Disconnected BLE client.")
            except Exception as e:
                logger.error(f"Error disconnecting BLE client: {e}")
        logger.info("Cleanup completed.")

    def __del__(self):
        """Destructor to ensure cleanup is called when the object is destroyed."""
        self.cleanup()
