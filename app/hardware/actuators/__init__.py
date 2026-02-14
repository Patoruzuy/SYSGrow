"""
Actuator Management Module

Provides domain-driven actuator management with:
- Multi-protocol support (GPIO, WiFi, Zigbee, MQTT)
- State management and tracking
- Schedule integration
- Safety features and interlocks
- Event-driven architecture
- Energy monitoring for smart switches
- Zigbee2MQTT device discovery

Note: ActuatorManager has been merged into ActuatorManagementService.
Use app.services.hardware.actuator_management_service for actuator operations.
"""
from app.domain.actuators import (
    ActuatorEntity,
    ActuatorType,
    ActuatorState,
    Protocol,
    ActuatorConfig,
    ControlMode,
    ActuatorCommand,
    ActuatorReading,
)
from app.hardware.actuators.factory import ActuatorFactory
from app.domain.energy import EnergyReading, PowerProfile, ConsumptionStats
from app.services.hardware.energy_monitoring import (
    EnergyMonitoringService,
    DEFAULT_POWER_PROFILES
)
from app.services.application.zigbee_management_service import (
    ZigbeeManagementService,
    DiscoveredDevice,
    DeviceCapability
)

__all__ = [
    'ActuatorEntity',
    'ActuatorType',
    'ActuatorState',
    'Protocol',
    'ActuatorConfig',
    'ControlMode',
    'ActuatorCommand',
    'ActuatorReading',
    'ActuatorFactory',
    'EnergyMonitoringService',
    'EnergyReading',
    'PowerProfile',
    'ConsumptionStats',
    'DEFAULT_POWER_PROFILES',
    'ZigbeeManagementService',
    'DiscoveredDevice',
    'DeviceCapability',
]
