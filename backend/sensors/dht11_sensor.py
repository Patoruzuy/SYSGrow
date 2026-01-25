import json
import time
from datetime import datetime
import threading

try:
    import board
    import adafruit_dht
    import redis
    import paho.mqtt.client as mqtt
    IS_PI = True
except (ImportError, NotImplementedError):
    print("Raspberry Pi-specific libraries not available. Using mock DHT11 sensor.")
    IS_PI = False


class DHT11Sensor:
    """
    Reads from a DHT11 temperature and humidity sensor and optionally pushes to Redis or MQTT.
    Supports retry logic and GPIO safety using a threading lock.
    """

    def __init__(self, pin: int, unit_id="1", use_mqtt=False, mqtt_config=None, redis_config=None):
        """
        Initializes the sensor and publishing backends.

        Args:
            pin (int): GPIO pin (e.g., 4 for D4).
            unit_id (str): Growth unit identifier.
            use_mqtt (bool): Use MQTT if True; Redis if False.
            mqtt_config (dict): MQTT settings (host, port).
            redis_config (dict): Redis settings (host, port).
        """
        self.unit_id = unit_id
        self.sensor_name = f"dht11_D{pin}"
        self.redis_key = f"unit:{unit_id}:sensor:{self.sensor_name}"
        self.mqtt_topic = f"growtent/{unit_id}/dht11/D{pin}"
        self.lock = threading.Lock()
        self.pin = pin
        self.sensor = None

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
                gpio_pin = getattr(board, f"D{pin}", None)
                if gpio_pin is None:
                    raise ValueError(f"Invalid GPIO pin: D{pin}")
                self.sensor = adafruit_dht.DHT11(gpio_pin)
                print(f"DHT11 sensor initialized on pin D{pin}")
            except Exception as e:
                print(f"Failed to initialize DHT11 on D{pin}: {e}")
                IS_PI = False
        else:
            self.mock_data = {
                'temperature': 23.4,
                'humidity': 48.6,
                'status': 'MOCK'
            }

        self.use_mqtt = use_mqtt

    def read(self, retries=3, delay=2, push=True):
        """
        Reads the sensor and optionally pushes to Redis or MQTT.

        Args:
            retries (int): Retry attempts.
            delay (int): Delay between retries (sec).
            push (bool): Publish reading if True.

        Returns:
            dict: Sensor data.
        """
        with self.lock:
            for attempt in range(retries):
                try:
                    if IS_PI and self.sensor:
                        temp = self.sensor.temperature
                        hum = self.sensor.humidity
                        if temp is not None and hum is not None:
                            break
                    else:
                        temp = self.mock_data["temperature"]
                        hum = self.mock_data["humidity"]
                        break
                except RuntimeError as e:
                    print(f"Retry {attempt + 1}: {e}")
                except Exception as e:
                    print(f"Unexpected error: {e}")
                time.sleep(delay)
            else:
                temp = None
                hum = None

        reading = {
            'temperature': temp,
            'humidity': hum,
            'timestamp': datetime.utcnow().isoformat(),
            'status': 'OK' if IS_PI else 'MOCK'
        }

        if push:
            self._publish(reading)

        return reading

    def _publish(self, data):
        """
        Pushes sensor data to Redis or MQTT.
        """
        try:
            if self.use_mqtt:
                self.mqtt_client.publish(self.mqtt_topic, json.dumps(data))
                print(f"📡 DHT11 data sent to MQTT → {self.mqtt_topic}")
            else:
                self.redis_client.set(self.redis_key, json.dumps(data))
                self.redis_client.set(f"{self.redis_key}_timestamp", data["timestamp"])
                print(f"DHT11 data stored in Redis → {self.redis_key}")
        except Exception as e:
            print(f"Failed to publish DHT11 data: {e}")

    def cleanup(self):
        """
        Cleans up GPIO state.
        """
        if IS_PI and self.sensor:
            self.sensor.exit()
            print("DHT11 sensor cleanup complete.")
