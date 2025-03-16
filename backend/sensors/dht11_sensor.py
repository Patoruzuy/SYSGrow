import adafruit_dht
import time
import board
import threading

class DHT11Sensor:
    def __init__(self, pin):
        self.pin = getattr(board, f"D{pin}", None)
        if self.pin is None:
            raise ValueError(f"Invalid GPIO pin: {pin}")
        self.sensor = adafruit_dht.DHT11(self.pin)
        self.lock = threading.Lock()
        print(f"DHT11 sensor initialized on pin {self.pin}")

    def read(self, retries=3, delay=2):
        """
        Reads the temperature and humidity from the DHT sensor with retry logic.

        Args:
            retries (int): The number of retries before failing.
            delay (int): The delay between retries in seconds.

        Returns:
            dict: A dictionary containing the temperature and humidity.
        """
        with self.lock:
            for attempt in range(retries):
                try:
                    temperature = self.sensor.temperature
                    humidity = self.sensor.humidity
                    if temperature is not None and humidity is not None:
                        print(f"Read successful on attempt {attempt + 1}")
                        return {'temperature': temperature, 'humidity': humidity}
                    else:
                        print(f"Read unsuccessful on attempt {attempt + 1}: temperature or humidity is None")
                except RuntimeError as e:
                    print(f"Runtime error reading sensor on attempt {attempt + 1}: {e}")
                except Exception as e:
                    print(f"Unexpected error reading sensor on attempt {attempt + 1}: {e}")
                time.sleep(delay)
            return {'temperature': None, 'humidity': None}

    def cleanup(self):
        """
        Clean up the sensor resources.
        """
        with self.lock:
            self.sensor.exit()
