from enum import Enum


class SensorField(str, Enum):
    """Standardized sensor reading field names."""

    TEMPERATURE = "temperature"
    HUMIDITY = "humidity"
    SOIL_MOISTURE = "soil_moisture"
    CO2 = "co2"
    AIR_QUALITY = "air_quality"
    EC = "ec"
    PH = "ph"
    SMOKE = "smoke"
    VOC = "voc"
    PRESSURE = "pressure"
    LUX = "lux"
    FULL_SPECTRUM = "full_spectrum"
    INFRARED = "infrared"
    VISIBLE = "visible"
    BATTERY = "battery"
    LINK_QUALITY = "linkquality"


# Aliases mapping: alias -> standard_field
# This maps various incoming field names to our standardized SensorField values.
FIELD_ALIASES: dict[str, str] = {
    # Temperature
    "temp": SensorField.TEMPERATURE,
    "temp_c": SensorField.TEMPERATURE,
    "Temperature": SensorField.TEMPERATURE,
    # Humidity
    "humidity_percent": SensorField.HUMIDITY,
    "relative_humidity": SensorField.HUMIDITY,
    "Humidity": SensorField.HUMIDITY,
    "rh": SensorField.HUMIDITY,
    # Soil Moisture
    "moisture": SensorField.SOIL_MOISTURE,
    "moisture_level": SensorField.SOIL_MOISTURE,
    "Soil Moisture": SensorField.SOIL_MOISTURE,
    # CO2
    "co2_ppm": SensorField.CO2,
    "CO2": SensorField.CO2,
    "eco2": SensorField.CO2,
    "co2": SensorField.CO2,
    # VOC
    "tvoc": SensorField.VOC,
    "VOC": SensorField.VOC,
    "voc_ppb": SensorField.VOC,
    "Formaldehyde": SensorField.VOC,
    # Light / LUX
    "light": SensorField.LUX,
    "light_lux": SensorField.LUX,
    "light_level": SensorField.LUX,
    "light_intensity": SensorField.LUX,
    "illuminance": SensorField.LUX,
    "illuminance_lux": SensorField.LUX,
    "Lux": SensorField.LUX,
    # Smoke
    "smoke_ppm": SensorField.SMOKE,
    "smoke_level": SensorField.SMOKE,
    # Pressure
    "pressure_hpa": SensorField.PRESSURE,
    # EC
    "ec_us_cm": SensorField.EC,
    # Air Quality
    "aqi": SensorField.AIR_QUALITY,
    # Battery
    "battery_percent": SensorField.BATTERY,
    "Battery": SensorField.BATTERY,
    # Link Quality
    "link_quality": SensorField.LINK_QUALITY,
    "rssi": SensorField.LINK_QUALITY,
}


def get_standard_field(field_name: str) -> str:
    """
    Returns the standardized field name for a given alias.
    If no alias is found, returns the original field_name.
    """
    res = FIELD_ALIASES.get(field_name, field_name)
    # Ensure we return the primitive string value, not the Enum object
    return str(getattr(res, "value", res))
