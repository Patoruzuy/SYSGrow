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

import requests
import time
import json
import paho.mqtt.client as mqtt
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)

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

        
        self.GPIO.setmode(self.GPIO.BCM)
        self.GPIO.setup(self.pin, self.GPIO.OUT)
        print(f"GPIO pin {self.pin} set as OUTPUT")

    def _setup_gpio(self):
        """Imports and sets up GPIO only if running on Raspberry Pi."""
        try:
            import RPi.GPIO as GPIO # type: ignore
        except (ImportError, RuntimeError):
            print("GPIO not available. Running in non-Raspberry Pi environment.")
            return GPIO

    def turn_on(self):
        """Turns the relay on by setting the GPIO pin HIGH."""
        self.GPIO.output(self.pin, self.GPIO.HIGH)

    def turn_off(self):
        """Turns the relay off by setting the GPIO pin LOW."""
        self.GPIO.output(self.pin, self.GPIO.LOW)

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
        self._send_request("on")

    def turn_off(self):
        """Sends an HTTP request to turn off the relay."""
        self._send_request("off")

    def _send_request(self, state: str):
        """
        Sends an HTTP request to the relay module.

        Args:
            state (str): The relay state ('on' or 'off').
        """
        url = f"http://{self.ip}/relay/{state}"
        try:
            response = requests.get(url)
            if response.status_code != 200:
                print(f"Error controlling relay: HTTP {response.status_code}")
        except requests.RequestException as e:
            print(f"Error controlling relay: {e}")


class ZigbeeRelay(RelayBase):
    """
    Controls a relay using Zigbee2MQTT via an MQTT broker.

    Attributes:
        device (str): The name of the controlled device.
        zigbee_address (str): The dynamically fetched Zigbee device address.
        zigbee_topic (str): The MQTT topic for controlling the Zigbee relay.
        mqtt_broker (str): The MQTT broker address (default: localhost).
        mqtt_port (int): The MQTT broker port (default: 1883).

    Methods:
        turn_on(): Sends an MQTT command to turn on the relay.
        turn_off(): Sends an MQTT command to turn off the relay.
        cleanup(): Disconnects the MQTT client.
    """

    def __init__(self, device: str, zigbee_channel: str, mqtt_broker: str = "localhost", mqtt_port: int = 1883):
        """
        Initializes the Zigbee relay with MQTT parameters.

        Args:
            device (str): The name of the device.
            zigbee_channel (str): The relay channel of the device.
            mqtt_broker (str, optional): The MQTT broker address (default: localhost).
            mqtt_port (int, optional): The MQTT broker port (default: 1883).
        """
        super().__init__(device)
        self.zigbee_channel = zigbee_channel
        self.mqtt_broker = mqtt_broker
        self.mqtt_port = mqtt_port

        # Setup MQTT client
        self.mqtt_client = mqtt.Client()
        self.mqtt_client.connect(self.mqtt_broker, self.mqtt_port, 60)
        self.mqtt_client.loop_start()

        print(f"Zigbee Relay initialized for {device} at channel {self.zigbee_channel}")

    def turn_on(self):
        """Sends an MQTT command to turn on the relay."""
        self._send_mqtt_command("ON")

    def turn_off(self):
        """Sends an MQTT command to turn off the relay."""
        self._send_mqtt_command("OFF")

    def _send_mqtt_command(self, state: str):
        """
        Sends an MQTT command to the Zigbee relay.

        Args:
            state (str): The relay state ('ON' or 'OFF').
        """
        topic = self.zigbee_channel
        payload = {"state": state}
        self.mqtt_client.publish(topic, json.dumps(payload))
        print(f"Sent MQTT command to {topic}: {state}")

    def cleanup(self):
        """Stops the MQTT loop and disconnects from the broker."""
        self.mqtt_client.loop_stop()
        self.mqtt_client.disconnect()

    def __del__(self):
        """Destructor to ensure cleanup is called when the object is destroyed."""
        self.cleanup()
