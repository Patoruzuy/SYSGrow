import adafruit_dht
import board

class DHT11Sensor:
    def __init__(self, pin):
        """
        Initializes the DHT11 sensor.
        
        Args:
            pin (int): GPIO pin number where the sensor is connected.
        """
        pin_mapping = {
            4: board.D4,
            17: board.D17,
            27: board.D27,
            22: board.D22,
        }
        self.sensor = adafruit_dht.DHT11(pin_mapping[pin])

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
