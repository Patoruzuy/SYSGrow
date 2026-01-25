"""
Domain Layer for Sensor Management
===================================
Contains business entities and value objects.
"""
from app.domain.sensors.sensor_entity import SensorEntity, SensorType, Protocol, SensorReadError
from app.domain.sensors.reading import SensorReading, ReadingStatus
from app.domain.sensors.sensor_config import SensorConfig
from app.domain.sensors.calibration import CalibrationData, CalibrationType
from app.domain.sensors.health_status import HealthStatus, HealthLevel
from app.domain.sensors.fields import SensorField, FIELD_ALIASES, get_standard_field



__all__ = [
    'SensorEntity',
    'SensorType',
    'Protocol',
    'SensorReadError',
    'SensorReading',
    'ReadingStatus',
    'SensorConfig',
    'CalibrationData',
    'CalibrationType',
    'HealthStatus',
    'HealthLevel',
    'SensorField',
    'FIELD_ALIASES',
    'get_standard_field',
]
