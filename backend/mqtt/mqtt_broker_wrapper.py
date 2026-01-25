"""
    This module provides a wrapper class for handling MQTT client functionality.
    It includes methods for connecting, disconnecting, publishing, and subscribing
    to an MQTT broker, with appropriate logging for each operation.

Author: Sebastian Gomez
Date: 11/03/2025
"""

import logging
import paho.mqtt.client as mqtt

logging.basicConfig(level=logging.INFO, filename="devices_system.log",
                    format="%(asctime)s - %(levelname)s - %(message)s")

class MQTTClientWrapper:
    """
    Wrapper class for handling MQTT client functionality.
    """
    def __init__(self, broker, port, client_id=""):
        """
        Initializes the MQTT client wrapper.

        Args:
            broker (str): The MQTT broker address.
            port (int): The MQTT broker port.
            client_id (str, optional): The MQTT client ID. Defaults to "".
        """
        self.broker = broker
        self.port = port
        self.client_id = client_id
        self.client = mqtt.Client(client_id)
        self.connected = False
        self._connect()

    def _connect(self):
        """
        Connects to the MQTT broker.
        """
        try:
            self.client.connect(self.broker, self.port, 60)
            self.connected = True
            self.client.loop_start()  # Start the MQTT loop in a separate thread
            logging.info(f"Connected to MQTT broker {self.broker}:{self.port}")
        except Exception as e:
            logging.error(f"Error connecting to MQTT broker: {e}")
            self.connected = False

    def disconnect(self):
        """
        Disconnects from the MQTT broker.
        """
        if self.connected:
            try:
                self.client.disconnect()
                self.client.loop_stop()
                self.connected = False
                logging.info("Disconnected from MQTT broker.")
            except Exception as e:
                logging.error(f"Error disconnecting from MQTT broker: {e}")

    def publish(self, topic, payload):
        """
        Publishes a message to the MQTT broker.

        Args:
            topic (str): The MQTT topic to publish to.
            payload (str): The message payload.
        """
        if self.connected:
            try:
                self.client.publish(topic, payload)
                logging.debug(f"Published to {topic}: {payload}")
            except Exception as e:
                logging.error(f"Error publishing to MQTT: {e}")
        else:
            logging.warning("MQTT client not connected. Cannot publish.")

    def subscribe(self, topic, callback):
        """
        Subscribes to a topic and sets a callback function.

        Args:
            topic (str): The MQTT topic to subscribe to.
            callback (callable): The callback function to handle received messages.
        """
        if self.connected:
            try:
                self.client.subscribe(topic)
                self.client.on_message = callback
                logging.info(f"Subscribed to topic {topic}")
            except Exception as e:
                logging.error(f"Error subscribing to MQTT topic {topic}: {e}")
        else:
            logging.warning("MQTT client not connected. Cannot subscribe.")

    def __del__(self):
        """
        Destructor to ensure disconnection from the MQTT broker.
        """
        self.disconnect()
