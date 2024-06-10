import adafruit_dht
import time
import board

class DHTSensor:
    def __init__(self, pin):
        self.pin = getattr(board, f"D{pin}")
        self.sensor = adafruit_dht.DHT11(self.pin)

    def read(self, retries=3, delay=2):
        """
        Reads the temperature and humidity from the DHT sensor with retry logic.

        Args:
            retries (int): The number of retries before failing.
            delay (int): The delay between retries in seconds.

        Returns:
            dict: A dictionary containing the temperature and humidity.
        """
        for _ in range(retries):
            try:
                temperature = self.sensor.temperature
                humidity = self.sensor.humidity
                if temperature is not None and humidity is not None:
                    return {'temperature': temperature, 'humidity': humidity}
            except RuntimeError as e:
                print(f"Error reading sensor: {e}")
                time.sleep(delay)
        return {'temperature': None, 'humidity': None}
