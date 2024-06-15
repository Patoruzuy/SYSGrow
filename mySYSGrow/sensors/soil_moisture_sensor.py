import board
import busio
from adafruit_ads1x15.ads1x15 import ADS1115
from adafruit_ads1x15.analog_in import AnalogIn

class SoilMoistureSensorV2:
    def __init__(self, adc_channel):
        """
        Initializes the SoilMoistureSensor.
        
        Args:
            adc_channel (ADS.P0, ADS.P1, etc.): ADC channel where the soil moisture sensor is connected.
        """
        self.adc_channel = adc_channel

        # Create the I2C bus
        i2c = busio.I2C(board.SCL, board.SDA)

        # Create the ADS object
        self.ads = ADS1115(i2c)

    def read(self):
        """
        Reads the soil moisture level from the sensor.
        
        Returns:
            dict: A dictionary containing 'soil_moisture'.
        """
        try:
            # Create an analog input channel on the specified ADC channel
            chan = AnalogIn(self.ads, self.adc_channel)
            moisture_level = chan.value
            return {'soil_moisture': moisture_level}
        except Exception as e:
            print(f"Error reading soil moisture level: {e}")
            return None

