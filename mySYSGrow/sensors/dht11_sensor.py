import adafruit_dht
import board

class DHT11Sensor:
    def __init__(self, pin):
        """
        Initializes the DHT11 sensor.
        
        Args:
            pin (int): GPIO pin number where the sensor is connected.
        """
        self.sensor = adafruit_dht.DHT11(pin)

    def read(self):
        """
        Reads the temperature and humidity from the sensor.
        
        Returns:
            dict: A dictionary containing 'temperature' and 'humidity'.
        """
        try:
            temperature = self.sensor.temperature
            humidity = self.sensor.humidity
            return {'temperature': temperature, 'humidity': humidity}
        except RuntimeError as e:
            print(f'Error reading sensor: {e}')
            return {'temperature': None, 'humidity': None}
