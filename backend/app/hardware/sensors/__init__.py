"""
Enterprise Sensor Management System
====================================

This package provides a comprehensive sensor management architecture with:
- Domain-Driven Design with rich entities
- Multi-protocol support (GPIO, MQTT, Zigbee, Zigbee2MQTT, Modbus)
- Calibration system (4 methods)
- Anomaly detection (6 types)
- Health monitoring
- Auto-discovery for Zigbee2MQTT sensors

Usage Example:
-------------

Using the SensorManagementService (recommended):
```python
from app.services.hardware import SensorManagementService
from app.domain.sensors import SensorType, Protocol

# Get service from dependency injection container
sensor_service = container.sensor_management_service

# Register GPIO sensor
sensor_service.register_sensor(
    sensor_id=1,
    name="Environment Sensor",
    sensor_type="ENVIRONMENT",
    protocol="I2C",
    unit_id=1,
    model="ENS160AHT21"
)

# Read sensor with automatic calibration and anomaly detection
reading = sensor_service.read_sensor(1)
print(reading.to_dict())
```

For migration guide, see: docs/SENSOR_MIGRATION_SUMMARY.md

Note: Legacy sensor classes have been moved to drivers/ folder and are internal only.
Use the SensorManagementService API for all sensor operations.
"""

# Factory & Registry (for internal use)
from .factory import SensorFactory, get_global_factory
from .registry import SensorRegistry, get_global_registry

# Domain Layer
from app.domain.sensors import (
    SensorEntity,
    SensorReading,
    SensorConfig,
    CalibrationData,
    HealthStatus,
    SensorType,
    Protocol,
    CalibrationType,
    HealthLevel,
    ReadingStatus
)

# Adapters
from app.hardware.adapters.sensors import (
    ISensorAdapter,
    GPIOAdapter,
    ZigbeeAdapter,
    Zigbee2MQTTAdapter,
    SYSGrowAdapter,
    ModbusAdapter
)

# Processors
from app.hardware.sensors.processors import (
    IDataProcessor,
    ValidationProcessor,
    TransformationProcessor,
    CalibrationProcessor,
    PriorityProcessor,
    EnrichmentProcessor
)

# Services
from app.services.utilities.calibration_service import CalibrationService
from app.services.utilities.anomaly_detection_service import AnomalyDetectionService
from app.services.application.zigbee_management_service import ZigbeeManagementService
from app.services.utilities.system_health_service import SystemHealthService

__all__ = [
    # Factory & Infrastructure
    'SensorFactory',
    'SensorRegistry',
    'get_global_factory',
    'get_global_registry',
    
    # Domain
    'SensorEntity',
    'SensorReading',
    'SensorConfig',
    'CalibrationData',
    'HealthStatus',
    'SensorType',
    'Protocol',
    'CalibrationType',
    'HealthLevel',
    'ReadingStatus',
    
    # Adapters
    'ISensorAdapter',
    'GPIOAdapter',
    'ZigbeeAdapter',
    'Zigbee2MQTTAdapter',
    'SYSGrowAdapter',
    'ModbusAdapter',
    
    # Processors
    'IDataProcessor',
    'ValidationProcessor',
    'TransformationProcessor',
    'CalibrationProcessor',
    'PriorityProcessor',
    'EnrichmentProcessor',
    
    # Services
    'CalibrationService',
    'AnomalyDetectionService',
    'ZigbeeManagementService',
    'SystemHealthService',
]

