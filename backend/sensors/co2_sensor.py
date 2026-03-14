import smbus2
import adafruit_ahtx0
import board
import busio

class ENS160_AHT21Sensor:
    def __init__(self, ens160_address, i2c_bus=1):
        """
        Initializes the ENS160 and AHT21 sensors.
        Reads data from a sensor connected via GPIO on Raspberry Pi.
        Works only if running on Raspberry Pi.
        
        Args:
            ens160_address (int): I2C address of the ENS160 sensor.
            i2c_bus (int): I2C bus number (default is 1).
        """
        self.ens160_address = ens160_address
        self.bus = smbus2.SMBus(i2c_bus)
        
        # Initialize AHT21 sensor
        i2c = busio.I2C(board.SCL, board.SDA)
        self.aht21 = adafruit_ahtx0.AHTx0(i2c)

    def read(self):
        """
        Reads the CO2 level from the ENS160 and temperature and humidity from AHT21.
        
        Returns:
            dict: A dictionary containing 'co2', 'temperature', and 'humidity'.
        """
        try:
            # Read CO2 value from ENS160 sensor (assuming a placeholder method)
            co2_value = self.bus.read_byte_data(self.ens160_address, 0x00)
        except Exception as e:
            print(f"Error reading CO2 level from ENS160: {e}")
            co2_value = None

        try:
            # Read temperature and humidity from AHT21
            temperature = self.aht21.temperature
            humidity = self.aht21.relative_humidity
        except Exception as e:
            print(f"Error reading temperature/humidity from AHT21: {e}")
            temperature = None
            humidity = None

        return {
            'co2': co2_value,
            'temperature': temperature,
            'humidity': humidity
        }
