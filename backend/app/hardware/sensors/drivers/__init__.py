"""
Internal hardware drivers for sensors.

This package contains low-level hardware drivers that communicate directly with sensors
via I2C, GPIO, and ADC interfaces. These drivers should NOT be used directly by application
code. Instead, use the sensor adapters in the parent package.

You should add third-party or custom drivers here as needed.

Available drivers:
- ENS160_AHT21Sensor: Air quality and environmental sensor
- TSL2591Driver: Light intensity sensor
- SoilMoistureSensorV2: Analog soil moisture sensor
- DHT11Sensor: Temperature and humidity sensor
- MQ2Sensor: Gas sensor (digital and analog)
- BME280Sensor: Temperature, humidity, and pressure sensor
"""

from .co2_sensor import ENS160_AHT21Sensor
from .dht11_sensor import DHT11Sensor
from .light_sensor import TSL2591Driver
from .mq2_sensor import MQ2Sensor
from .soil_moisture_sensor import SoilMoistureSensorV2
from .temp_humidity_sensor import BME280Sensor

__all__ = [
    "BME280Sensor",
    "DHT11Sensor",
    "ENS160_AHT21Sensor",
    "MQ2Sensor",
    "SoilMoistureSensorV2",
    "TSL2591Driver",
]
