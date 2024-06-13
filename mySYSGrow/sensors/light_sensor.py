import time
import board
import busio
import adafruit_tsl2591


class LightSensor:
    def __init__(self):
        
        self.i2c = busio.I2C(board.SCL, board.SDA) # Create I2C bus
        self.sensor = adafruit_tsl2591.TSL2591(self.i2c) # Create TSL2591 instance

    def read(self):
        lux = self.sensor.lux
        visible = self.sensor.visible
        infrared = self.sensor.infrared
        full_spectrum = self.sensor.full_spectrum
        print(f"Lux: {lux}, Visible: {visible}, Infrared: {infrared}, Full Spectrum: {full_spectrum}")
        return {'lux': lux, 'visible': visible, 'infrared': infrared, 'full_spectrum': full_spectrum}