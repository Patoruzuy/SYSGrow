# mqtt_notifier.py
import paho.mqtt.client as mqtt
import json

class MQTTNotifier:
    """Publishes sensor updates and alerts to an MQTT broker."""

    def __init__(self, broker="mqtt-broker.local", port=1883):
        self.client = mqtt.Client()
        self.client.connect(broker, port, 60)

    def publish_sensor_update(self, sensor_type, value):
        """Publishes real-time sensor data."""
        payload = json.dumps({sensor_type: value})
        self.client.publish(f"growtent/sensors/{sensor_type}", payload)

    def publish_event(self, event_type, data):
        """Publishes system events."""
        payload = json.dumps(data)
        self.client.publish(f"growtent/events/{event_type}", payload)
