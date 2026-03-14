# app/hardware/sensors/processors/utils.py
"""
Shared Utilities for Sensor Processors
=======================================

Common helper functions and constants used across processor modules.
Centralizes duplicate code from pipeline.py and priority_processor.py.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Set, Tuple

from app.utils.time import utc_now

# ============================================================================
# Constants
# ============================================================================

# Metrics that appear on the dashboard
DASHBOARD_METRICS: Set[str] = {
    "temperature", "humidity", "soil_moisture", "co2", "air_quality",
    "ec", "ph", "smoke", "voc", "pressure", "lux", "full_spectrum",
    "infrared", "visible", "dew_point", "vpd", "heat_index",
}

# Keys that are metadata, not sensor readings
META_KEYS: Set[str] = {"battery", "linkquality", "report_interval", "temperature_unit"}

# Suffixes that indicate metadata keys
META_SUFFIXES: Tuple[str, ...] = ("_calibration", "_unit")

# Unit mapping for sensor readings
UNIT_MAP: Dict[str, str] = {
    "temperature": "°c",
    "humidity": "%",
    "soil_moisture": "%",
    "lux": "lux",
    "illuminance": "lux",
    "light": "lux",
    "co2": "ppm",
    "co2_ppm": "ppm",
    "voc": "ppb",
    "voc_ppb": "ppb",
    "pressure": "hpa",
    "dew_point": "°c",
    "vpd": "kpa",
    "heat_index": "°c",
}

# Valid wire status values
VALID_STATUSES: Set[str] = {"success", "warning", "error", "mock"}

# Keyword sets for sensor type classification (DRY constants)
SOIL_PLANT_TYPE_KEYWORDS = frozenset({
    "soil", "moisture", "soil_moisture", "plant_sensor", "plant", "ph", "ec"
})
SOIL_PLANT_MODEL_KEYWORDS = frozenset({
    "soil", "moisture", "capacitive", "ph", "ec"
})
ENVIRONMENT_KEYWORDS = frozenset({
    "environment", "env", "temp_humidity", "temp-humidity", "temperature", "humidity"
})
LIGHT_TYPE_KEYWORDS = frozenset({"light", "lux", "illuminance"})
LIGHT_MODEL_KEYWORDS = frozenset({"bh1750", "tsl2591"})
AIR_QUALITY_MODEL_KEYWORDS = frozenset({"ens160", "bme680", "mq135", "mq2"})
DERIVED_METRICS = frozenset({"dew_point", "vpd", "heat_index"})


# ============================================================================
# Helper Functions
# ============================================================================

def matches_any(text: str, keywords: frozenset) -> bool:
    """Check if any keyword is a substring of text."""
    return any(kw in text for kw in keywords)


def is_soil_sensor(sensor: Any) -> bool:
    """Determine if a sensor is a soil/plant sensor."""
    st, model = extract_sensor_strings(sensor)
    return matches_any(st, SOIL_PLANT_TYPE_KEYWORDS) or matches_any(model, SOIL_PLANT_MODEL_KEYWORDS)


def is_environment_sensor(sensor: Any) -> bool:
    """Determine if a sensor is an environment-monitoring sensor."""
    st, _ = extract_sensor_strings(sensor)
    return matches_any(st, ENVIRONMENT_KEYWORDS)


def extract_sensor_strings(sensor: Any) -> Tuple[str, str]:
    """Extract normalized sensor_type and model strings from a sensor entity.
    
    Returns:
        Tuple of (sensor_type, model) as lowercase strings
    """
    st_raw = getattr(sensor, "sensor_type", None)
    st = str(getattr(st_raw, "value", None) or st_raw or "").lower()
    model_raw = getattr(sensor, "model", None)
    model = str(getattr(model_raw, "value", None) or model_raw or "").lower()
    return st, model


def is_meta_key(key: str) -> bool:
    """Check if a key is a metadata key (not a sensor reading)."""
    return key in META_KEYS or key.endswith(META_SUFFIXES)


def coerce_float(value: Any) -> Optional[float]:
    """
    Safely coerce a value to float.

    Returns None for:
    - None values
    - Boolean values (to avoid True->1.0)
    - Unparseable strings
    """
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except (ValueError, TypeError):
            return None
    return None


def coerce_int(value: Any) -> Optional[int]:
    """
    Safely coerce a value to int.

    Returns None for:
    - None values
    - Boolean values
    - Unparseable strings
    """
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        try:
            return int(float(value))
        except (ValueError, TypeError):
            return None
    return None


def to_wire_status(status_obj: Any) -> str:
    """
    Convert a status object to a wire-safe string.

    Handles:
    - Enum values (extracts .value)
    - Strings (normalizes case)
    - Other types (returns "success" default)
    """
    raw = getattr(status_obj, "value", status_obj)
    if not isinstance(raw, str):
        return "success"
    v = raw.strip().lower()
    return v if v in VALID_STATUSES else "success"


def get_meta_val(obj: Any, attr: str, default: Any = "unknown") -> Any:
    """Safely extract value from an object attribute, handling Enums."""
    raw = getattr(obj, attr, None)
    if raw is None:
        return default
    if hasattr(raw, "value"):
        return raw.value
    return str(raw) if raw else default


def coerce_numeric_readings(readings: Dict[str, Any], exclude_meta: bool = True) -> Dict[str, float]:
    """
    Filter and coerce raw values to floats for payload.readings.

    Args:
        readings: Raw readings dict
        exclude_meta: If True, skip metadata keys

    Returns:
        Dict of key -> float for numeric values only
    """
    out: Dict[str, float] = {}
    for k, v in (readings or {}).items():
        if exclude_meta and is_meta_key(k):
            continue
        fv = coerce_float(v)
        if fv is not None:
            out[k] = fv
    return out


def get_unit_for_metric(metric: str) -> str:
    """Get the unit string for a metric name."""
    return UNIT_MAP.get(metric, "")


def infer_power_source(data: Dict[str, Any]) -> str:
    """
    Infer power source from sensor data.

    Returns:
        "battery", "mains", or "unknown"
    """
    # Check explicit power_source field first
    power_source = data.get("power_source")
    if isinstance(power_source, str) and power_source.strip():
        ps = power_source.strip().lower()
        if ps in {"battery", "mains"}:
            return ps
        return "unknown"

    # Infer from battery presence
    battery = coerce_float(data.get("battery"))
    return "battery" if battery is not None else "mains"
