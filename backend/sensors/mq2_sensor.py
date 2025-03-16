import RPi.GPIO as GPIO
import time
# import board
# import busio
# import adafruit_ads1x15.ads1115 as ADS
# from adafruit_ads1x15.analog_in import AnalogIn

class MQ2Sensor:
    def __init__(self, sensor_pin, is_digital=True, channel=0):
        self.is_digital = is_digital
        self.sensor_pin = sensor_pin
        # self.channel = channel
        
        # if self.is_digital:
        #     GPIO.setmode(GPIO.BCM)
        #     GPIO.setwarnings(False)
        #     GPIO.setup(self.sensor_pin, GPIO.IN)
        # else:
        #     i2c = busio.I2C(board.SCL, board.SDA)
        #     self.adc = ADS.ADS1115(i2c)
        #     self.gain = 1
        #     self.analog_in = AnalogIn(self.adc, getattr(AnalogIn, f"P{channel}"))

    def read(self):
        """
        Reads the digital signal from the MQ-2 sensor.
        
        Returns:
            bool: True if gas is detected, False otherwise.
        """
        if self.is_digital:
            return {'Smoke': GPIO.input(self.sensor_pin)}
        else:
            raise ValueError("Sensor is set to analog mode. Use read_analog() instead.")
    
    # def read_analog(self):
    #     """
    #     Reads the analog signal from the MQ-2 sensor via the ADS1115.
        
    #     Returns:
    #         int: Analog value between 0 and 32767.
    #     """
    #     if not self.is_digital:
    #         return {'Smoke': self.analog_in.value}
    #     else:
    #         raise ValueError("Sensor is set to digital mode. Use read() instead.")

    def cleanup(self):
        """
        Cleans up the GPIO settings if in digital mode.
        """
        if self.is_digital:
            GPIO.cleanup()