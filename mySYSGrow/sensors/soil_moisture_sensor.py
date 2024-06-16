import board
import busio
import adafruit_ads1x15.ads1115 as ADS
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
        self.ads = ADS.ADS1115(i2c)

         # Calibration values (these should be determined experimentally)
        self.dry_value = 20000  # Example value, should be measured when the soil is completely dry
        self.wet_value = 8000   # Example value, should be measured when the soil is completely wet

    def read(self):
        """
        Reads the soil moisture level from the sensor and converts it to a percentage.
        
        Returns:
            dict: A dictionary containing 'soil_moisture' percentage.
        """
        try:
            # Read raw soil moisture value from ADC
            raw_value = self.adc.read_adc(self.adc_channel, gain=1)
            print(f"Raw ADC Value: {raw_value}")

            # Convert raw_value to voltage (for ADS1115, default range is +/- 4.096V)
            voltage = (raw_value / 32767.0) * 4.096
            print(f"Voltage: {voltage:.2f} V")

            # Normalize and convert to percentage
            soil_moisture = self._map(raw_value, self.dry_value, self.wet_value, 0, 100)
            soil_moisture = max(0, min(100, soil_moisture))  # Clamp to 0-100%
            return {'soil_moisture': soil_moisture}
        except Exception as e:
            print(f"Error reading soil moisture level: {e}")
            return {'error': str(e)}

    def _map(self, x, in_min, in_max, out_min, out_max):
        """
        Maps an input value from one range to another.

        Args:
            x (float): Input value to map.
            in_min (float): Minimum value of the input range.
            in_max (float): Maximum value of the input range.
            out_min (float): Minimum value of the output range.
            out_max (float): Maximum value of the output range.

        Returns:
            float: Mapped value.
        """
        return (x - in_min) * (out_max - out_min) / (in_max - in_min) + out_min

