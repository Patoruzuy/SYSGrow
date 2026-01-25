import json
from datetime import datetime

try:
    import adafruit_tsl2591
    import board
    import busio
    import redis
    import paho.mqtt.client as mqtt
    IS_PI = True
except (ImportError, NotImplementedError):
    print("⚠️ Raspberry Pi-specific libraries not available. Using mock TSL2591 sensor.")
    IS_PI = False


class TSL2591Driver:
    """
    Driver for the TSL2591 light intensity sensor with optional Redis or MQTT integration.
    Compatible with Raspberry Pi I2C or mock fallback for development environments.
    """

    def __init__(self, unit_id="1", use_mqtt=False, mqtt_config=None, redis_config=None):
        """
        Initializes the TSL2591 sensor and communication backends.

        Args:
            unit_id (str): Growth unit identifier.
            use_mqtt (bool): True to use MQTT; False to use Redis.
            mqtt_config (dict): MQTT config with 'host' and 'port'.
            redis_config (dict): Redis config with 'host' and 'port'.
        """
        self.unit_id = unit_id
        self.use_mqtt = use_mqtt
        self.sensor = None

        self.redis_key = f"unit:{unit_id}:sensor:tsl2591_lux"
        self.mqtt_topic = f"growtent/{unit_id}/tsl2591_lux"

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
                i2c = busio.I2C(board.SCL, board.SDA)
                self.sensor = adafruit_tsl2591.TSL2591(i2c)
                print("✅ TSL2591 sensor initialized successfully.")
            except Exception as e:
                print(f"❌ Failed to initialize TSL2591 sensor: {e}")
                IS_PI = False
        else:
            # Mock fallback values
            self.mock_data = {
                'lux': 550.5,
                'full_spectrum': 1200,
                'infrared': 450,
                'visible': 750,
                'status': 'MOCK'
            }

    def read(self, push=True):
        """
        Reads light sensor data and optionally publishes to Redis or MQTT.

        Args:
            push (bool): Whether to publish the reading.

        Returns:
            dict: Light sensor data including lux, full_spectrum, IR, and visible light.
        """
        if IS_PI and self.sensor:
            try:
                lux = self.sensor.lux
                full = self.sensor.full_spectrum
                ir = self.sensor.infrared
                visible = full - ir
                status = 'OK'
            except Exception as e:
                print(f"❌ Error reading TSL2591: {e}")
                return {'error': str(e), 'status': 'ERROR'}
        else:
            lux = self.mock_data['lux']
            full = self.mock_data['full_spectrum']
            ir = self.mock_data['infrared']
            visible = self.mock_data['visible']
            status = self.mock_data['status']

        timestamp = datetime.utcnow().isoformat()
        reading = {
            'lux': lux,
            'full_spectrum': full,
            'infrared': ir,
            'visible': visible,
            'timestamp': timestamp,
            'status': status
        }

        if push:
            self._publish(reading)

        return reading

    def _publish(self, data):
        """
        Publishes the reading to Redis or MQTT based on configuration.
        """
        try:
            if self.use_mqtt:
                self.mqtt_client.publish(self.mqtt_topic, json.dumps(data))
                print(f"📡 Light data sent to MQTT → {self.mqtt_topic}")
            else:
                self.redis_client.set(self.redis_key, json.dumps(data))
                self.redis_client.set(f"{self.redis_key}_timestamp", data["timestamp"])
                print(f"📦 Light data pushed to Redis → {self.redis_key}")
        except Exception as e:
            print(f"❌ Failed to publish TSL2591 data: {e}")

