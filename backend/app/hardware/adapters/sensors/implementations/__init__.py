"""
Sensor Implementation Wrappers
===============================
Specific implementations for different sensor hardware.

These adapters wrap the legacy sensor classes with a clean interface
that integrates with the new enterprise architecture.
"""

from .ens160_aht21 import ENS160AHT21Adapter
from .tsl2591 import TSL2591Adapter
from .soil_moisture import SoilMoistureAdapter
from .dht11 import DHT11Adapter
from .mq2 import MQ2Adapter
from .bme280 import BME280Adapter

__all__ = [
    'ENS160AHT21Adapter',
    'TSL2591Adapter',
    'SoilMoistureAdapter',
    'DHT11Adapter',
    'MQ2Adapter',
    'BME280Adapter',
]
