"""
Domain Layer for Sensor Management
===================================
Contains business entities and value objects.
"""

from app.domain.sensors.calibration import CalibrationData, CalibrationType
from app.domain.sensors.fields import FIELD_ALIASES, SensorField, get_standard_field
from app.domain.sensors.health_status import HealthLevel, HealthStatus
from app.domain.sensors.reading import ReadingStatus, SensorReading
from app.domain.sensors.sensor_config import SensorConfig
from app.domain.sensors.sensor_entity import Protocol, SensorEntity, SensorReadError, SensorType

__all__ = [
    "FIELD_ALIASES",
    "CalibrationData",
    "CalibrationType",
    "HealthLevel",
    "HealthStatus",
    "Protocol",
    "ReadingStatus",
    "SensorConfig",
    "SensorEntity",
    "SensorField",
    "SensorReadError",
    "SensorReading",
    "SensorType",
    "get_standard_field",
]
