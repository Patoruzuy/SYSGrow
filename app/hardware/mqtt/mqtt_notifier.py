# mqtt_notifier.py
import json
import logging

from app.hardware.mqtt.client_factory import create_mqtt_client

logger = logging.getLogger(__name__)


class MQTTNotifier:
    """Publishes sensor updates and alerts to an MQTT broker."""

    def __init__(self, broker: str = "mqtt-broker.local", port: int = 1883):
        self.client = None
        try:
            client = create_mqtt_client()
            client.connect(broker, port, 60)
            self.client = client
            logger.info("Connected to MQTT broker at %s:%s", broker, port)
        except Exception as exc:
            # In test or offline environments we continue without MQTT.
            logger.warning("MQTT notifier disabled (connection failed): %s", exc)

    def publish_sensor_update(self, sensor_type, value):
        """Publishes real-time sensor data."""
        if not self.client:
            return False
        try:
            payload = json.dumps({sensor_type: value})
            self.client.publish(f"growtent/sensors/{sensor_type}", payload)
            return True
        except Exception as exc:
            logger.warning("MQTT publish failed for sensor update: %s", exc)
            return False

    def publish_event(self, event_type, data):
        """Publishes system events."""
        if not self.client:
            return False
        try:
            payload = json.dumps(data)
            self.client.publish(f"growtent/events/{event_type}", payload)
            return True
        except Exception as exc:
            logger.warning("MQTT publish failed for event %s: %s", event_type, exc)
            return False
