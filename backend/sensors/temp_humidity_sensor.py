import json
from datetime import datetime

try:
    import board
    import busio
    import adafruit_bme280
    import redis
    import paho.mqtt.client as mqtt
    IS_PI = True
except (ImportError, NotImplementedError):
    print("⚠️ Raspberry Pi-specific libraries not available. Using mock BME280 sensor.")
    IS_PI = False


class BME280Sensor:
    """
    Class to interface with the BME280 sensor for temperature, humidity, pressure, and altitude,
    with optional MQTT or Redis publishing support.
    """

    def __init__(self, unit_id="1", use_mqtt=False, mqtt_config=None, redis_config=None):
        """
        Initializes the BME280 sensor with I2C and sets up Redis or MQTT backend.

        Args:
            unit_id (str): Growth unit ID.
            use_mqtt (bool): Use MQTT if True, otherwise Redis.
            mqtt_config (dict): MQTT settings with 'host' and 'port'.
            redis_config (dict): Redis settings with 'host' and 'port'.
        """
        self.unit_id = unit_id
        self.use_mqtt = use_mqtt
        self.sensor_name = "bme280"
        self.redis_key = f"unit:{unit_id}:sensor:{self.sensor_name}"
        self.mqtt_topic = f"growtent/{unit_id}/bme280"

        if use_mqtt:
            self.mqtt_client = mqtt.Client()
            self.mqtt_client.connect(
                mqtt_config.get("host", "localhost"),
                mqtt_config.get("port", 1883),
                60
            )
        else:
            self.redis_client = redis.StrictRedis(
                host=redis_config.get("host", "localhost"),
                port=redis_config.get("port", 6379),
                decode_responses=True
            )

        if IS_PI:
            try:
                self.i2c_bus = busio.I2C(board.SCL, board.SDA)
                self.bme280 = adafruit_bme280.Adafruit_BME280_I2C(self.i2c_bus)
                print("✅ BME280 initialized.")
            except Exception as e:
                print(f"❌ BME280 init failed: {e}")
                IS_PI = False
        else:
            self.mock_data = {
                'temperature': 24.7,
                'humidity': 51.2,
                'pressure': 1012.3,
                'altitude': 100.5,
                'status': 'MOCK'
            }

    def read(self, include_altitude=False, push=True):
        """
        Reads the BME280 sensor and optionally pushes the reading to MQTT or Redis.

        Args:
            include_altitude (bool): Include altitude in the output.
            push (bool): Push to backend if True.

        Returns:
            dict: Sensor data.
        """
        if IS_PI and hasattr(self, 'bme280'):
            try:
                data = {
                    'temperature': self.bme280.temperature,
                    'humidity': self.bme280.humidity,
                    'pressure': self.bme280.pressure,
                    'altitude': self.bme280.altitude if include_altitude else None,
                    'status': 'OK'
                }
            except Exception as e:
                print(f"❌ Error reading BME280: {e}")
                return {'error': str(e), 'status': 'ERROR'}
        else:
            data = self.mock_data.copy()
            if not include_altitude:
                data.pop('altitude', None)

        data['timestamp'] = datetime.utcnow().isoformat()

        if push:
            self._publish(data)

        return data

    def _publish(self, data):
        """
        Pushes the sensor data to MQTT or Redis.
        """
        try:
            if self.use_mqtt:
                self.mqtt_client.publish(self.mqtt_topic, json.dumps(data))
                print(f"📡 Sent BME280 data to MQTT → {self.mqtt_topic}")
            else:
                self.redis_client.set(self.redis_key, json.dumps(data))
                self.redis_client.set(f"{self.redis_key}_timestamp", data["timestamp"])
                print(f"📦 Pushed BME280 data to Redis → {self.redis_key}")
        except Exception as e:
            print(f"❌ Failed to publish BME280 data: {e}")

    def set_sea_level_pressure(self, pressure_hpa):
        """
        Sets the sea-level pressure for more accurate altitude calculations.

        Args:
            pressure_hpa (float): Pressure in hPa.
        """
        try:
            if IS_PI and hasattr(self, 'bme280'):
                self.bme280.sea_level_pressure = pressure_hpa
        except Exception as e:
            print(f"Error setting sea level pressure: {e}")
