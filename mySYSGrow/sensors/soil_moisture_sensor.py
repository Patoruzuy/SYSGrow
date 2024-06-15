from adafruit_ads1x15.ads1115 import ADS
from adafruit_ads1x15.analog_in import AnalogIn
import board
import busio

class SoilMoistureSensorV2:
    def __init__(self, adc_channel):
        """
        Initializes the SoilMoistureSensor.
        
        Args:
            adc_channel (int): ADC channel where the soil moisture sensor is connected.
        """
        self.adc_channel = adc_channel
        self.i2c = busio.I2C(board.SCL, board.SDA)
        self.ads = ADS.ADS1115(self.i2c)
        self.channel = AnalogIn(self.ads, self.adc_channel)

    def read(self):
        """
        Reads the soil moisture level from the sensor.
        
        Returns:
            dict: A dictionary containing 'soil_moisture'.
        """
        try:
            # Read soil moisture value from ADC
            moisture_level = self.channel.value
            return {'soil_moisture': moisture_level}
        except Exception as e:
            print(f"Error reading soil moisture level: {e}")
            return None
