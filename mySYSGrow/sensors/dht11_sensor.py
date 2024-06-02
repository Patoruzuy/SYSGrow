import Adafruit_DHT

class DHT11Sensor:
    def __init__(self, pin):
        """
        Initializes the DHT11 sensor.
        
        Args:
            pin (int): GPIO pin number where the sensor is connected.
        """
        self.sensor = Adafruit_DHT.DHT11
        self.pin = pin

    def read(self):
        """
        Reads the temperature and humidity from the sensor.
        
        Returns:
            dict: A dictionary containing 'temperature' and 'humidity'.
        """
        humidity, temperature = Adafruit_DHT.read_retry(self.sensor, self.pin)
        if humidity is not None and temperature is not None:
            return {'temperature': temperature, 'humidity': humidity}
        else:
            return None
