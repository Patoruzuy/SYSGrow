import redis
import threading
import json
import logging
from utils.event_bus import EventBus

logging.basicConfig(level=logging.INFO)

class ESP32SensorMonitor:
    """
    Monitors Redis Pub/Sub for new ESP32-C6 sensor modules and triggers sensor reload.
    """

    def __init__(self, sensor_manager, redis_url="redis://localhost:6379/0"):
        self.redis_client = redis.Redis.from_url(redis_url, decode_responses=True)
        self.pubsub = self.redis_client.pubsub()
        self.sensor_manager = sensor_manager
        self.event_bus = EventBus()
        self.channel = "sensor_updates"

    def _handle_new_sensor(self, message):
        try:
            if message["type"] != "message":
                return

            data = json.loads(message["data"])
            unit_id = data.get("unit_id")
            sensor_type = data.get("sensor_type")
            logging.info(f"🔔 New ESP32-C6 sensor update received: {data}")

            # Publish to your system's EventBus and reload sensors
            self.event_bus.publish("sensor_update", data)

            sensors = self.sensor_manager._load_sensors_from_db()
            self.sensor_manager.start_polling(sensors)

        except Exception as e:
            logging.error(f"Error processing sensor update message: {e}", exc_info=True)

    def start(self):
        def listener():
            self.pubsub.subscribe(self.channel)
            logging.info(f"📡 Listening for ESP32 sensor updates on Redis channel '{self.channel}'...")
            for message in self.pubsub.listen():
                self._handle_new_sensor(message)

        threading.Thread(target=listener, daemon=True).start()
