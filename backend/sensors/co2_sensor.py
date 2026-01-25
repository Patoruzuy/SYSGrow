import json
from datetime import datetime

try:
    import adafruit_ahtx0
    import adafruit_ens160
    import board
    import busio
    import redis
    import paho.mqtt.client as mqtt
    IS_PI = True
except (ImportError, NotImplementedError):
    print("⚠️ Raspberry Pi-specific libraries not available. Using mock sensors.")
    IS_PI = False


class ENS160_AHT21Sensor:
    """
    A class to interface with ENS160 and AHT21 sensors and publish data to Redis or MQTT.

    Attributes:
        unit_id (str): Unit identifier (used for Redis key or MQTT topic).
        redis_client (redis.StrictRedis): Redis client (if using Redis).
        mqtt_client (mqtt.Client): MQTT client (if using MQTT).
        ens160 (ENS160): ENS160 air quality sensor.
        aht21 (AHTx0): AHT21 temp/humidity sensor.
        mock_data (dict): Mock fallback readings.
    """

    def __init__(self, unit_id="1", use_mqtt=False, mqtt_config=None, redis_config=None):
        self.unit_id = unit_id
        self.use_mqtt = use_mqtt

        # Redis key / MQTT topic
        self.redis_key = f"unit:{unit_id}:sensor:ens160_aht21"
        self.mqtt_topic = f"growtent/{unit_id}/ens160_aht21"

        # Communication backend
        if use_mqtt:
            self.mqtt_client = mqtt.Client()
            mqtt_host = mqtt_config.get("host", "localhost")
            mqtt_port = mqtt_config.get("port", 1883)
            self.mqtt_client.connect(mqtt_host, mqtt_port, 60)
        else:
            redis_host = redis_config.get("host", "localhost")
            redis_port = redis_config.get("port", 6379)
            self.redis_client = redis.StrictRedis(
                host=redis_host, port=redis_port, decode_responses=True
            )

        # Hardware
        self.ens160 = None
        self.aht21 = None

        if IS_PI:
            try:
                self.i2c = busio.I2C(board.SCL, board.SDA)
                self.aht21 = adafruit_ahtx0.AHTx0(self.i2c)
                self.ens160 = adafruit_ens160.ENS160(self.i2c)
                self.ens160.operation_mode = adafruit_ens160.MODE_STANDARD
                print("✅ ENS160 + AHT21 initialized.")
            except Exception as e:
                print(f"❌ Sensor init failed: {e}")
                IS_PI = False
        else:
            self.mock_data = {
                'eco2': 420,
                'tvoc': 35,
                'temperature': 24.3,
                'humidity': 55.1,
                'status': 'MOCK'
            }

    def read(self, push=True):
        """
        Reads the sensor and optionally pushes data to Redis or MQTT.

        Args:
            push (bool): Whether to publish the reading to backend (Redis or MQTT)

        Returns:
            dict: Sensor reading with timestamp.
        """
        if IS_PI and self.ens160 and self.aht21:
            try:
                reading = {
                    'eco2': self.ens160.eco2,
                    'tvoc': self.ens160.tvoc,
                    'temperature': self.aht21.temperature,
                    'humidity': self.aht21.relative_humidity,
                    'status': self.ens160.operating_mode,
                    'timestamp': datetime.utcnow().isoformat()
                }
            except Exception as e:
                print(f"❌ Sensor read error: {e}")
                reading = {'error': str(e)}
        else:
            reading = self.mock_data.copy()
            reading["timestamp"] = datetime.utcnow().isoformat()

        if push:
            self._publish(reading)

        return reading

    def _publish(self, data):
        """
        Publishes data to Redis or MQTT.
        """
        try:
            if self.use_mqtt:
                self.mqtt_client.publish(self.mqtt_topic, json.dumps(data))
                print(f"📡 Sent data to MQTT → {self.mqtt_topic}")
            else:
                self.redis_client.set(self.redis_key, json.dumps(data))
                self.redis_client.set(f"{self.redis_key}_timestamp", data["timestamp"])
                print(f"📦 Pushed data to Redis → {self.redis_key}")
        except Exception as e:
            print(f"❌ Failed to publish ENS160/AHT21 data: {e}")

