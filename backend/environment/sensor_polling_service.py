import threading
import logging
import time
import json
from datetime import datetime
from typing import Dict, Any
from utils.event_bus import EventBus

logging.basicConfig(level=logging.INFO, filename='logs/sensor_polling_service.log', 
                    filemode='a', format='%(asctime)s - %(levelname)s - %(message)s')

class SensorPollingService:
    """
    SensorPollingService continuously polls GPIO and Redis-based wireless sensors,
    and also listens for MQTT-based sensor updates.

    Features:
    - Periodic polling of GPIO sensors (e.g., analog or digital sensors wired to the Pi)
    - Periodic polling of wireless sensor values stored in Redis
    - Real-time MQTT subscription to sensor update topics
    - MQTT-based reload triggering using a predefined topic ("growtent/reload")
    - Automatic publishing of all readings to the internal EventBus system
    """

    def __init__(self, sensor_manager: Any, redis_client: Any, mqtt_wrapper: Any = None,
                 gpio_poll_interval: int = 10, wireless_poll_interval: int = 30):
        """
        Initialize the polling service.

        Args:
            sensor_manager (Any): Instance of the sensor manager.
            redis_client (Any): Instance of a Redis client.
            mqtt_wrapper (Any): Instance of MQTTClientWrapper to subscribe to MQTT topics.
            gpio_poll_interval (int): Interval (seconds) between GPIO sensor polls.
            wireless_poll_interval (int): Interval (seconds) between wireless (Redis) polls.
        """
        self.sensor_manager = sensor_manager
        self.event_bus = EventBus()
        self.redis_client = redis_client
        self.gpio_poll_interval = gpio_poll_interval
        self.wireless_poll_interval = wireless_poll_interval
        self.mqtt_wrapper = mqtt_wrapper

        self._stop_event = threading.Event()
        self._started = False
        self._reload_lock = threading.Lock()
        self._reload_timer = None
        self._reload_delay = 5

        # Subscribe to MQTT sensor updates and reload trigger if MQTT is enabled
        if self.mqtt_wrapper:
            self.mqtt_wrapper.subscribe("growtent/+/sensor/+", self._on_mqtt_message)
            self.mqtt_wrapper.subscribe("growtent/reload", self._on_mqtt_message)

    def start_polling(self) -> None:
        """
        Start the polling threads for GPIO and wireless sensors.
        """
        if self._started:
            logging.warning("🔁 Sensor polling already started.")
            return

        self._stop_event.clear()
        self._started = True

        # Log registered sensors
        try:
            gpio_sensors = self.sensor_manager.get_gpio_sensor_configs()
            wireless_sensors = self.sensor_manager.get_wireless_sensor_configs()
            logging.info(f"📋 Registered GPIO Sensors: {[s.get('sensor_type') for s in gpio_sensors]}")
            logging.info(f"📡 Registered Wireless Sensors: {[s.get('sensor_type') for s in wireless_sensors]}")
        except Exception as e:
            logging.warning(f"⚠️ Failed to list sensors on startup: {e}")

        threading.Thread(target=self._poll_gpio_sensors_loop, daemon=True).start()
        threading.Thread(target=self._poll_redis_sensors_loop, daemon=True).start()
        threading.Thread(target=self._monitor_mqtt_heartbeat_loop, daemon=True).start()

        logging.info("🚀 Sensor polling service started (GPIO + Redis + MQTT + Reloads).")

    def stop_polling(self) -> None:
        """
        Stop polling, MQTT listening and clean up any timers.
        """
        self._stop_event.set()
        self._started = False
        if self._reload_timer:
            self._reload_timer.cancel()
        logging.info("Sensor polling service stopped.")

    def _poll_gpio_sensors_loop(self) -> None:
        """
        Continuously poll GPIO-based sensors and publish readings to the event bus.
        """
        while not self._stop_event.is_set():
            try:
                readings = self.sensor_manager.read_all_gpio_sensors()
                for sensor_id, reading in readings.items():
                    sensor_type = reading.get("sensor_type")
                    unit_id = reading.get("unit_id", "1")
                    self._publish_sensor_data(sensor_type, unit_id, reading)
            except Exception as e:
                logging.error(f"GPIO Polling Error: {e}")
            self._stop_event.wait(self.gpio_poll_interval)

    def _poll_redis_sensors_loop(self) -> None:
        """
        Poll Redis-based wireless sensors in a loop until stopped.

        This method retrieves sensor configurations from the sensor manager,
        checks if the data in Redis is stale, and publishes the sensor data
        to the event bus if it is valid.

        Runs in a background thread.
        """
        while not self._stop_event.is_set():
            try:
                sensor_configs = self.sensor_manager.get_wireless_sensor_configs()
                for config in sensor_configs:
                    sensor_type: str = config.get("sensor_type")
                    unit_id: str = config.get("unit_id", "1")
                    redis_key: str = f"{sensor_type}_{unit_id}"

                    if self.is_redis_data_stale(redis_key):
                        logging.warning(f"Redis data for {redis_key} is stale.")
                        continue

                    redis_value = self.redis_client.get(redis_key)
                    if redis_value:
                        try:
                            value: float = float(redis_value.decode("utf-8"))
                            self._publish_sensor_data(sensor_type, unit_id, {sensor_type: value})
                        except Exception as e:
                            logging.error(f"Failed to decode Redis value for {redis_key}: {e}")
            except Exception as e:
                logging.error(f"Wireless Polling Error: {e}")
            self._stop_event.wait(self.wireless_poll_interval)

    def _monitor_mqtt_heartbeat_loop(self) -> None:
        """
        Periodically logs the last received MQTT update times for each sensor.
        Helps monitor sensor uptime or silence.
        """
        while not self._stop_event.is_set():
            try:
                for sensor_key, last_seen in self.mqtt_last_seen.items():
                    delta = (datetime.now() - last_seen).total_seconds()
                    logging.debug(f"📶 MQTT sensor '{sensor_key}' last seen {int(delta)}s ago.")
            except Exception as e:
                logging.warning(f"Heartbeat logging error: {e}")
            self._stop_event.wait(60)  # Log every 60 seconds

    def _on_mqtt_message(self, client, userdata, msg):
        """
        Handle incoming MQTT messages either for sensor data or reload request.

        Topic format for sensor data: growtent/<unit_id>/sensor/<sensor_type>
        Topic format for reload trigger: growtent/reload
        """
        try:
            if msg.topic == "growtent/reload":
                logging.info("🔁 MQTT sensor reload requested.")
                self.debounce_reload_sensors()
                return

            payload = json.loads(msg.payload.decode())
            topic_parts = msg.topic.split("/")
            unit_id = topic_parts[1]
            sensor_type = topic_parts[-1]
            self._publish_sensor_data(sensor_type, unit_id, payload)
            self.mqtt_last_seen[f"{sensor_type}_{unit_id}"] = datetime.now()
            logging.info(f"📥 MQTT sensor update → {sensor_type} (Unit {unit_id})")
        except Exception as e:
            logging.error(f"❌ Failed to handle MQTT message: {e}")

    def _publish_sensor_data(self, sensor_type: str, unit_id: str, data: Dict[str, Any]) -> None:
        """
        Publish sensor data to the event bus.

        Args:
            sensor_type (str): Type of the sensor (e.g., temperature, humidity).
            unit_id (str): Identifier of the sensor unit.
            data (Dict[str, Any]): Sensor data to publish.
        """
        try:
            self.event_bus.publish(f"{sensor_type}_update", {"unit_id": unit_id, **data})
        except Exception as e:
            logging.error(f"Error publishing {sensor_type} data for unit {unit_id}: {e}")

    def debounce_reload_sensors(self) -> None:
        """
        Debounce sensor reloads to avoid frequent reloads within a short period.

        This method schedules a sensor reload to occur after a delay, canceling any
        previously scheduled reloads if they haven't occurred yet.
        """
        with self._reload_lock:
            if self._reload_timer:
                self._reload_timer.cancel()
            self._reload_timer = threading.Timer(self._reload_delay, self._perform_sensor_reload)
            self._reload_timer.start()
            logging.debug("Debounced sensor reload scheduled.")

    def _perform_sensor_reload(self) -> None:
        """
        Perform the actual sensor reload.

        This method is called after the debounce delay to reload all sensors.
        """
        try:
            logging.info("Performing debounced sensor reload...")
            self.sensor_manager.reload_all_sensors()
        except Exception as e:
            logging.error(f"Failed to reload sensors: {e}")

    def is_redis_data_stale(self, redis_key: str, threshold_seconds: int = 300) -> bool:
        """
        Check if the data in Redis is stale based on a timestamp.

        Args:
            redis_key (str): The Redis key for the sensor data.
            threshold_seconds (int): The threshold in seconds to consider data as stale.

        Returns:
            bool: True if the data is stale, False otherwise.
        """
        last_update_key = f"{redis_key}_timestamp"
        last_update_time = self.redis_client.get(last_update_key)
        if not last_update_time:
            return True
        try:
            last_time = datetime.fromisoformat(last_update_time.decode())
            return (datetime.now() - last_time).total_seconds() > threshold_seconds
        except Exception as e:
            logging.error(f"Failed to parse timestamp for {last_update_key}: {e}")
            return True

    # def listen_for_sensor_updates(self) -> None:
    #     """
    #     Listen for sensor updates from Redis pubsub and debounce sensor reloads.

    #     This method subscribes to the Redis pubsub channel for sensor updates and
    #     schedules a debounced sensor reload when updates are detected.
    #     """
    #     pubsub = self.redis_client.pubsub()
    #     pubsub.subscribe("sensor_updates")

    #     def _listen() -> None:
    #         for message in pubsub.listen():
    #             if message["type"] == "message":
    #                 logging.info(f"Redis sensor update detected: {message['data']}")
    #                 self.debounce_reload_sensors()

    #     threading.Thread(target=_listen, daemon=True).start()
    #     logging.info("Subscribed to Redis pubsub for dynamic sensor reloads.")