import board
import busio
import adafruit_ads1x15.ads1115 as ADC
from adafruit_ads1x15.analog_in import AnalogIn
import time
import logging

class SoilMoistureSensorV2:
    def __init__(self, adc_channel):
        """
        Initializes the SoilMoistureSensor.
        
        Args:
            adc_channel (ADS.P0, ADS.P1, etc.): ADC channel where the soil moisture sensor is connected.
        """
        self.adc_channel = adc_channel

        try:
            # Create the I2C bus
            self.i2c = busio.I2C(board.SCL, board.SDA)
            # Create the ADS object
            self.adc = ADC.ADS1115(self.i2c, address=0x48)
        except ValueError as e:
            logging.error(f"No I2C device at address: 0x48 - {e}")
            raise
        except OSError as e:
            logging.error(f"Error initializing I2C bus: {e}")
            raise

         # Calibration values (these should be determined experimentally)
        self.dry_value = 15000  # Example value, should be measured when the soil is completely dry
        self.wet_value = 8000   # Example value, should be measured when the soil is completely wet

    def read(self, retries=3, delay=1):
        """
        Reads the soil moisture level from the sensor with retry logic.

        Args:
            retries (int): The number of retries before failing.
            delay (int): The delay between retries in seconds.

        Returns:
            dict: A dictionary containing 'soil_moisture' and 'pin'.
        """
        for attempt in range(retries):   
            try:
                # Create an analog input channel on the specified ADC channel
                chan = AnalogIn(self.adc, self.adc_channel)
                moisture_level = chan.value
                print(f"Raw ADC Value: {moisture_level}")
                # Convert raw_value to voltage (for ADS1115, default range is +/- 4.096V)
                voltage = chan.voltage
                print(f"Voltage: {voltage:.2f} V")
                # Normalize and convert to percentage
                soil_moisture = self._map(moisture_level, self.dry_value, self.wet_value, 0, 100)
                soil_moisture = max(0, min(100, soil_moisture))  # Clamp to 0-100%
                return {'soil_moisture': soil_moisture}
            except OSError as e:
                print(f"Error reading soil moisture sensor on attempt {attempt + 1}: {e}")
                time.sleep(delay)
        return {'soil_moisture': {'error': '[Errno 5] Input/output error'}, 'pin': self.adc_channel}

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