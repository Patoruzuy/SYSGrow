import adafruit_tsl2591
import board
import busio

class TSL2591Driver:
    def __init__(self):
        """
        Initializes the TSL2591 light sensor.
        """
        i2c = busio.I2C(board.SCL, board.SDA)
        self.tsl2591 = adafruit_tsl2591.TSL2591(i2c)

    def read(self):
        """
        Reads the light intensity from the TSL2591 sensor.
        
        Returns:
            dict: A dictionary containing 'lux' and 'full_spectrum', 'infrared', and 'visible' light readings.
        """
        try:
            lux = self.tsl2591.lux
            full_spectrum = self.tsl2591.full_spectrum
            infrared = self.tsl2591.infrared
            visible = full_spectrum - infrared
        except Exception as e:
            print(f"Error reading light intensity from TSL2591: {e}")
            return None

        return {
            'lux': lux,
            'full_spectrum': full_spectrum,
            'infrared': infrared,
            'visible': visible
        }
