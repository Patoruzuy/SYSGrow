"""
Device-related Enumerations
============================

This module contains all enums related to devices (sensors and actuators).
Note: Protocol and SensorType enums are imported from infrastructure for standardization.
"""

from enum import Enum
# Import Protocol and SensorType from infrastructure as the source of truth
from app.domain.sensors.sensor_entity import Protocol, SensorType

class SensorModel(str, Enum):
    """Specific sensor models"""
    # Environment sensors
    DHT11 = "DHT11"
    DHT22 = "DHT22"
    BME280 = "BME280"
    BME680 = "BME680"
    ENS160AHT21 = "ENS160AHT21"
    
    # Smoke/Gas sensors
    MQ2 = "MQ2"
    MQ135 = "MQ135"
    
    # Light sensors
    TSL2591 = "TSL2591"
    BH1750 = "BH1750"
    
    # Soil sensors
    SOIL_MOISTURE = "Soil-Moisture"
    CAPACITIVE_SOIL = "Capacitive-Soil"
    
    # CO2 sensors
    MHZ19 = "MH-Z19"
    SCD30 = "SCD30"
    
    # pH/EC sensors
    PH_SENSOR = "pH-Sensor"
    EC_SENSOR = "EC-Sensor"
    
    # Zigbee2MQTT commercial sensors
    TS0201 = "TS0201"  # TuYa Temperature & Humidity Sensor
    ZG_227ZL = "ZG-227ZL"  # TuYa Temperature & Humidity Sensor
    SNZB_02 = "SNZB-02"  # Sonoff Temperature & Humidity Sensor
    WSDCGQ11LM = "WSDCGQ11LM"  # Aqara Temperature & Humidity Sensor
    RTCGQ11LM = "RTCGQ11LM"  # Aqara Motion Sensor
    MCCGQ11LM = "MCCGQ11LM"  # Aqara Door/Window Sensor
    GENERIC_ZIGBEE = "GENERIC_ZIGBEE"  # Generic Zigbee2MQTT device
    
    def __str__(self):
        return self.value


class ActuatorType(str, Enum):
    """Types of actuators"""
    LIGHT = "Light"
    HEATER = "Heater"
    COOLER = "Cooler"
    HUMIDIFIER = "Humidifier"
    DEHUMIDIFIER = "Dehumidifier"
    WATER_PUMP = "Water-Pump"
    CO2_INJECTOR = "CO2-Injector"
    FAN = "Fan"
    EXTRACTOR = "Extractor"
    RELAY = "Relay"
    VALVE = "Valve"
    MOTOR = "Motor"
    
    def __str__(self):
        return self.value
    
class StateMode(str, Enum):
    """State modes for devices"""
    AUTO = "AUTO"
    MANUAL = "MANUAL"
    
    def __str__(self):
        return self.value


class DeviceCategory(str, Enum):
    """
    Device category classification - sensor vs actuator.
    Used for: API responses to help frontend differentiate device types
    """
    SENSOR = "sensor"
    ACTUATOR = "actuator"
    
    def __str__(self) -> str:
        return self.value

    
class ActuatorState(str, Enum):
    """Possible states for actuators"""
    ON = "ON"
    OFF = "OFF"
    MODE = StateMode.AUTO

    def __str__(self):
        return self.value
    
class PowerMode(str, Enum):
    """Power modes for ESP32 devices"""
    NORMAL = "normal"
    SAVE = "save"
    SLEEP = "sleep"
    DEEP_SLEEP = "deep_sleep"
    
    def __str__(self):
        return self.value

class DeviceType(str, Enum):
    """
    Device type classification for ESP32 and Zigbee devices.
    Used by: device management, device repository
    """
    ESP32 = "esp32"
    ESP32_C3 = "esp32-c3"
    ESP32_C6 = "esp32-c6"
    ZIGBEE = "zigbee"
    MQTT = "mqtt"
    GPIO = "gpio"
    
    def __str__(self) -> str:
        return self.value


class DeviceStatus(str, Enum):
    """
    Device operational status.
    Used by: device health monitoring, device management
    """
    ACTIVE = "active"
    INACTIVE = "inactive"
    OFFLINE = "offline"
    MAINTENANCE = "maintenance"
    ERROR = "error"
    
    def __str__(self) -> str:
        return self.value