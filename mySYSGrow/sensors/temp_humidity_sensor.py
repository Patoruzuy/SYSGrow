import adafruit_bme280
import board
import busio

class BME280Sensor:
    def __init__(self, i2c_bus):
        self.i2c_bus = busio.I2C(board.SCL, board.SDA)
        self.bme280 = adafruit_bme280.Adafruit_BME280_I2C(self.i2c_bus)

    def read(self):
        try:
            temperature = self.bme280.temperature
            humidity = self.bme280.humidity
            return {'temperature': temperature, 'humidity': humidity}
        except Exception as e:
            print(f"Error reading BME280 sensor: {e}")
            return {'temperature': None, 'humidity': None}
