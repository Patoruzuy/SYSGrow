import json
import time
from datetime import datetime

try:
    import board
    import busio
    import adafruit_ads1x15.ads1115 as ADS
    from adafruit_ads1x15.analog_in import AnalogIn
    import RPi.GPIO as GPIO
    import redis
    import paho.mqtt.client as mqtt
    IS_PI = True
except (ImportError, NotImplementedError):
    print("⚠️ Raspberry Pi-specific libraries not available. Using mock MQ2 sensor.")
    IS_PI = False


class MQ2Sensor:
    """
    Handles both digital and analog modes of the MQ2 gas sensor, 
    and can optionally publish data to Redis or MQTT.
    """

    def __init__(self, sensor_pin=17, is_digital=True, channel=0, unit_id="1",
                 use_mqtt=False, mqtt_config=None, redis_config=None):
        """
        Initializes the MQ2 gas sensor.

        Args:
            sensor_pin (int): GPIO pin number for digital mode.
            is_digital (bool): True for GPIO read, False for analog via ADC.
            channel (int): ADS1115 channel for analog mode (0–3).
            unit_id (str): Growth unit ID.
            use_mqtt (bool): Push readings to MQTT if True, else Redis.
            mqtt_config (dict): MQTT config with host and port.
            redis_config (dict): Redis config with host and port.
        """
        self.sensor_pin = sensor_pin
        self.is_digital = is_digital
        self.channel = channel
        self.unit_id = unit_id
        self.use_mqtt = use_mqtt
        self.adc = None

        self.sensor_name = f"mq2_{'digital' if is_digital else 'analog'}"
        self.redis_key = f"unit:{unit_id}:sensor:{self.sensor_name}"
        self.mqtt_topic = f"growtent/{unit_id}/mq2/{'digital' if is_digital else f'P{channel}'}"

        if IS_PI:
            if is_digital:
                GPIO.setmode(GPIO.BCM)
                GPIO.setwarnings(False)
                GPIO.setup(sensor_pin, GPIO.IN)
            else:
                try:
                    i2c = busio.I2C(board.SCL, board.SDA)
                    self.adc = ADS.ADS1115(i2c)
                    self.analog_in = AnalogIn(self.adc, getattr(ADS, f"P{channel}"))
                except Exception as e:
                    print(f"❌ ADC init failed: {e}")
                    IS_PI = False

        # Setup Redis or MQTT
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

    def read(self, push_to_output=True):
        """
        Reads from the MQ2 sensor and optionally pushes data to Redis/MQTT.

        Returns:
            dict: {
                'smoke': int or bool,
                'mode': 'digital' | 'analog',
                'timestamp': ISO UTC string,
                'status': 'OK' | 'MOCK'
            }
        """
        timestamp = datetime.utcnow().isoformat()

        if IS_PI:
            if self.is_digital:
                value = GPIO.input(self.sensor_pin)
                status = "OK"
            else:
                value = self.analog_in.value
                status = "OK"
        else:
            value = 1 if self.is_digital else 16384
            status = "MOCK"

        data = {
            "smoke": value,
            "mode": "digital" if self.is_digital else "analog",
            "timestamp": timestamp,
            "status": status
        }

        if push_to_output:
            self._publish(data)

        return data

    def _publish(self, data):
        """
        Pushes sensor data to MQTT or Redis.
        """
        try:
            if self.use_mqtt:
                self.mqtt_client.publish(self.mqtt_topic, json.dumps(data))
                print(f"📡 Sent MQ2 data to MQTT → {self.mqtt_topic}")
            else:
                self.redis_client.set(self.redis_key, json.dumps(data))
                self.redis_client.set(f"{self.redis_key}_timestamp", data["timestamp"])
                print(f"📦 Stored MQ2 data in Redis → {self.redis_key}")
        except Exception as e:
            print(f"❌ Failed to publish MQ2 data: {e}")

    def cleanup(self):
        """
        Clean up GPIO state if digital mode is active.
        """
        if IS_PI and self.is_digital:
            GPIO.cleanup()
