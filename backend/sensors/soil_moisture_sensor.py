import json
import logging
import time
from datetime import datetime

try:
    import board
    import busio
    import adafruit_ads1x15.ads1115 as ADC
    from adafruit_ads1x15.analog_in import AnalogIn
    import redis
    IS_PI = True
except (ImportError, NotImplementedError):
    print("⚠️ Raspberry Pi-specific libraries not available. Using mock soil sensor.")
    IS_PI = False


class SoilMoistureSensorV2:
    """
    Reads soil moisture from an analog sensor via ADS1115 ADC, and optionally pushes readings to Redis.
    """

    def __init__(self, adc_channel, unit_id="1", redis_host="localhost", redis_port=6379):
        """
        Initializes the soil moisture sensor.

        Args:
            adc_channel: ADC.P0, ADC.P1, etc. (channel on the ADS1115 board).
            unit_id (str): Identifier of the unit, used in Redis key.
            redis_host (str): Redis server address.
            redis_port (int): Redis server port.
        """
        self.adc_channel = adc_channel
        self.unit_id = unit_id
        self.redis_key = f"unit:{unit_id}:sensor:soil_moisture_{adc_channel}"

        # Redis client
        self.redis_client = redis.StrictRedis(host=redis_host, port=redis_port, decode_responses=True)

        if IS_PI:
            try:
                self.i2c = busio.I2C(board.SCL, board.SDA)
                self.adc = ADC.ADS1115(self.i2c, address=0x48)
            except Exception as e:
                logging.error(f"❌ Failed to initialize ADS1115: {e}")
                IS_PI = False
        else:
            # Mock fallback
            self.mock_data = {
                'soil_moisture': 52.4,
                'adc_channel': str(adc_channel),
                'status': 'MOCK'
            }

        # Calibration values (customize as needed)
        self.dry_value = 15000  # ADC value when dry
        self.wet_value = 8000   # ADC value when fully wet

    def read(self, retries=3, delay=1, push_to_redis=True):
        """
        Reads moisture level from sensor and optionally pushes it to Redis.

        Args:
            retries (int): Retry attempts if I/O fails.
            delay (int): Delay between retries in seconds.
            push_to_redis (bool): Whether to save to Redis.

        Returns:
            dict: {
                'soil_moisture': float,
                'adc_raw': int,
                'voltage': float,
                'timestamp': str,
                'status': 'OK' | 'MOCK' | 'ERROR'
            }
        """
        if IS_PI:
            for attempt in range(retries):
                try:
                    chan = AnalogIn(self.adc, self.adc_channel)
                    raw = chan.value
                    voltage = chan.voltage
                    moisture = self._map(raw, self.dry_value, self.wet_value, 0, 100)
                    moisture = max(0, min(100, moisture))  # Clamp 0–100%
                    status = "OK"
                    break
                except OSError as e:
                    print(f"⚠️ Read failed (attempt {attempt+1}): {e}")
                    time.sleep(delay)
            else:
                return {'soil_moisture': None, 'status': 'ERROR'}
        else:
            # Use mock values
            moisture = self.mock_data['soil_moisture']
            raw = 12000
            voltage = 2.3
            status = "MOCK"

        timestamp = datetime.utcnow().isoformat()
        reading = {
            'soil_moisture': round(moisture, 2),
            'adc_raw': raw,
            'voltage': round(voltage, 3),
            'timestamp': timestamp,
            'status': status
        }

        if push_to_redis:
            try:
                self.redis_client.set(self.redis_key, json.dumps(reading))
                self.redis_client.set(f"{self.redis_key}_timestamp", timestamp)
                print(f"📦 Pushed soil data to Redis → {self.redis_key}")
            except Exception as e:
                print(f"❌ Redis push failed: {e}")

        return reading

    def _map(self, x, in_min, in_max, out_min, out_max):
        """
        Maps an input value from one range to another.

        Args:
            x (float): Input value.
            in_min (float): Input range min.
            in_max (float): Input range max.
            out_min (float): Output range min.
            out_max (float): Output range max.

        Returns:
            float: Mapped output value.
        """
        return (x - in_min) * (out_max - out_min) / (in_max - in_min) + out_min
