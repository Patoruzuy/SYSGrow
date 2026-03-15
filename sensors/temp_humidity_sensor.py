import adafruit_bme280
import board
import busio

class BME280Sensor:
    """
    Class to interface with the BME280 sensor for reading temperature, humidity, and pressure.

    Attributes:
        i2c_bus (busio.I2C): The I2C bus interface.
        bme280 (adafruit_bme280.Adafruit_BME280_I2C): The BME280 sensor object.
    """

    def __init__(self):
        """
        Initializes the BME280 sensor with the I2C interface.
        """
        try:
            self.i2c_bus = busio.I2C(board.SCL, board.SDA)
            self.bme280 = adafruit_bme280.Adafruit_BME280_I2C(self.i2c_bus)
        except Exception as e:
            raise RuntimeError(f"Failed to initialize BME280 sensor: {e}")

    def read(self):
        """
        Reads temperature, humidity, and pressure from the BME280 sensor.

        Returns:
            dict: A dictionary containing the sensor readings:
                - 'temperature' (float): Temperature in Celsius.
                - 'humidity' (float): Relative humidity in percentage.
                - 'pressure' (float): Atmospheric pressure in hPa.
        """
        try:
            temperature = self.bme280.temperature
            humidity = self.bme280.humidity
            pressure = self.bme280.pressure
            return {
                'temperature': temperature,
                'humidity': humidity,
                'pressure': pressure
            }
        except Exception as e:
            print(f"Error reading BME280 sensor: {e}")
            return {
                'temperature': None,
                'humidity': None,
                'pressure': None
            }

    def set_sea_level_pressure(self, pressure_hpa):
        """
        Sets the sea level pressure for accurate altitude readings.

        Args:
            pressure_hpa (float): The sea level pressure in hPa.
        """
        try:
            self.bme280.sea_level_pressure = pressure_hpa
        except Exception as e:
            print(f"Error setting sea level pressure: {e}")

    def get_altitude(self):
        """
        Calculates the altitude based on the current pressure and sea level pressure.

        Returns:
            float: The altitude in meters.
        """
        try:
            return self.bme280.altitude
        except Exception as e:
            print(f"Error calculating altitude: {e}")
            return None
