"""
MQTT Actuator Adapter

Adapter for MQTT-based actuators.
"""

import json
import logging
from typing import Any

from app.utils.event_bus import EventBus

logger = logging.getLogger(__name__)


class MQTTActuatorAdapter:
    """
    MQTT protocol adapter for actuators.

    Publishes commands to MQTT topics.
    """

    def __init__(self, device_name: str, mqtt_client: Any, topic: str, event_bus: EventBus | None = None):
        """
        Initialize MQTT adapter.

        Args:
            device_name: Name of actuator
            mqtt_client: MQTT client instance
            topic: MQTT topic for commands
            event_bus: Event bus for events
        """
        self.device_name = device_name
        self.mqtt_client = mqtt_client
        self.topic = topic
        self.event_bus = event_bus or EventBus()

    def turn_on(self):
        """Turn actuator ON via MQTT"""
        payload = json.dumps({"state": "ON"})
        self.mqtt_client.publish(self.topic, payload)
        logger.info(f"MQTT: Turned ON {self.device_name} on {self.topic}")

    def turn_off(self):
        """Turn actuator OFF via MQTT"""
        payload = json.dumps({"state": "OFF"})
        self.mqtt_client.publish(self.topic, payload)
        logger.info(f"MQTT: Turned OFF {self.device_name} on {self.topic}")

    def set_level(self, value: float):
        """
        Set actuator level via MQTT.

        Args:
            value: Level from 0-100
        """
        payload = json.dumps(
            {
                "state": "ON" if value > 0 else "OFF",
                "brightness": int(value * 2.55),  # Convert 0-100 to 0-255
            }
        )
        self.mqtt_client.publish(self.topic, payload)
        logger.info(f"MQTT: Set {self.device_name} to {value}% on {self.topic}")

    def get_device(self) -> str:
        """Get device identifier"""
        return f"mqtt://{self.topic}"

    def cleanup(self) -> None:
        """
        Cleanup resources.

        Unsubscribes from MQTT topics if subscribed.
        Called when actuator is unregistered or deleted.
        """
        try:
            # Unsubscribe from state topic if we were subscribed
            state_topic = self.topic.replace("/set", "")
            if hasattr(self.mqtt_client, "unsubscribe"):
                self.mqtt_client.unsubscribe(state_topic)
            logger.debug(f"MQTT actuator {self.device_name} cleaned up")
        except Exception as e:
            logger.warning(f"Cleanup failed for MQTT actuator {self.device_name}: {e}")
