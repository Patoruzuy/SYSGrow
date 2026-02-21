"""
Device-related Enumerations
============================

This module contains all enums related to devices (sensors and actuators).
"""

from enum import Enum


class SensorType(str, Enum):
    """
    Sensor categories.

    Two categories that group all sensors:
    - ENVIRONMENTAL: temperature, humidity, co2, lux, voc, smoke, pressure, air_quality
    - PLANT: soil_moisture, ph, ec

    The specific metrics each sensor provides are defined in ``primary_metrics`` field,
    allowing maximum flexibility (e.g., a plant sensor can provide lux readings).
    """

    ENVIRONMENTAL = "environmental"
    PLANT = "plant"

    @classmethod
    def _missing_(cls, value: object) -> "SensorType | None":
        """Map legacy sensor type values to new categories."""
        if not isinstance(value, str):
            return None
        environmental_types = {
            "environment_sensor",
            "temperature",
            "temperature_sensor",
            "humidity",
            "humidity_sensor",
            "co2",
            "lux_sensor",
            "light",
            "light_sensor",
            "voc",
            "smoke_sensor",
            "pressure",
            "pressure_sensor",
            "air_quality",
            "air_quality_sensor",
        }
        plant_types = {
            "plant_sensor",
            "soil_moisture",
            "soil_moisture_sensor",
            "ph",
            "ec",
        }
        if value in environmental_types:
            return cls.ENVIRONMENTAL
        if value in plant_types:
            return cls.PLANT
        return None


class Protocol(str, Enum):
    """Communication protocols"""

    GPIO = "GPIO"
    I2C = "I2C"
    ADC = "ADC"
    MQTT = "mqtt"
    ZIGBEE = "zigbee"
    ZIGBEE2MQTT = "zigbee2mqtt"
    HTTP = "http"
    MODBUS = "Modbus"
    WIRELESS = "wireless"

    @classmethod
    def _missing_(cls, value: object) -> "Protocol | None":
        """Backwards-compatible mapping for legacy protocol values."""
        if not isinstance(value, str):
            return None
        legacy_map = {
            "MQTT": cls.MQTT.value,
            "ZIGBEE": cls.ZIGBEE.value,
            "ZIGBEE2MQTT": cls.ZIGBEE2MQTT.value,
            "HTTP": cls.HTTP.value,
            "MODBUS": cls.MODBUS.value,
            "WIRELESS": cls.WIRELESS.value,
        }
        mapped = legacy_map.get(value)
        if mapped is None:
            return None
        return cls(mapped)


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
    """Types of actuators.

    This is the single canonical enum for actuator types across the
    entire codebase.  Formerly a second ``ActuatorType`` lived in
    ``app.domain.actuators.actuator_entity`` with lowercase values;
    that definition now re-exports this one.

    The ``_missing_`` hook ensures backward-compatibility with legacy
    lowercase values (e.g. ``"pump"``, ``"light"``) stored in older
    records or passed through domain-layer code.
    """

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
    # Members added from domain enum (previously app.domain.actuators only)
    DIMMER = "Dimmer"
    SWITCH = "Switch"
    SENSOR = "Sensor"  # For devices with actuator capabilities
    UNKNOWN = "Unknown"

    # Backward-compatible alias: domain code used ActuatorType.PUMP
    PUMP = "Water-Pump"

    @classmethod
    def _missing_(cls, value: object) -> "ActuatorType | None":
        """Map legacy lowercase values to canonical members.

        The former domain enum used lowercase strings (``"light"``,
        ``"pump"``, etc.).  This hook lets ``ActuatorType("pump")``
        work transparently.
        """
        if not isinstance(value, str):
            return None
        _legacy_map: dict[str, ActuatorType] = {
            "light": cls.LIGHT,
            "heater": cls.HEATER,
            "cooler": cls.COOLER,
            "humidifier": cls.HUMIDIFIER,
            "dehumidifier": cls.DEHUMIDIFIER,
            "pump": cls.WATER_PUMP,
            "water-pump": cls.WATER_PUMP,
            "water_pump": cls.WATER_PUMP,
            "waterpump": cls.WATER_PUMP,
            "co2-injector": cls.CO2_INJECTOR,
            "co2_injector": cls.CO2_INJECTOR,
            "fan": cls.FAN,
            "extractor": cls.EXTRACTOR,
            "relay": cls.RELAY,
            "valve": cls.VALVE,
            "motor": cls.MOTOR,
            "dimmer": cls.DIMMER,
            "switch": cls.SWITCH,
            "sensor": cls.SENSOR,
            "unknown": cls.UNKNOWN,
        }
        return _legacy_map.get(value.lower())

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
