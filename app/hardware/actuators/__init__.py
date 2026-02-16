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
    ActuatorCommand,
    ActuatorConfig,
    ActuatorEntity,
    ActuatorReading,
    ActuatorState,
    ActuatorType,
    ControlMode,
    Protocol,
)
from app.domain.energy import ConsumptionStats, EnergyReading, PowerProfile
from app.hardware.actuators.factory import ActuatorFactory
from app.services.application.zigbee_management_service import (
    DeviceCapability,
    DiscoveredDevice,
    ZigbeeManagementService,
)
from app.services.hardware.energy_monitoring import DEFAULT_POWER_PROFILES, EnergyMonitoringService

__all__ = [
    "DEFAULT_POWER_PROFILES",
    "ActuatorCommand",
    "ActuatorConfig",
    "ActuatorEntity",
    "ActuatorFactory",
    "ActuatorReading",
    "ActuatorState",
    "ActuatorType",
    "ConsumptionStats",
    "ControlMode",
    "DeviceCapability",
    "DiscoveredDevice",
    "EnergyMonitoringService",
    "EnergyReading",
    "PowerProfile",
    "Protocol",
    "ZigbeeManagementService",
]
