"""
Sensor Implementation Wrappers
===============================
Specific implementations for different sensor hardware.

These adapters wrap the legacy sensor classes with a clean interface
that integrates with the new enterprise architecture.
"""

from .bme280 import BME280Adapter
from .dht11 import DHT11Adapter
from .ens160_aht21 import ENS160AHT21Adapter
from .mq2 import MQ2Adapter
from .soil_moisture import SoilMoistureAdapter
from .tsl2591 import TSL2591Adapter

__all__ = [
    "BME280Adapter",
    "DHT11Adapter",
    "ENS160AHT21Adapter",
    "MQ2Adapter",
    "SoilMoistureAdapter",
    "TSL2591Adapter",
]
