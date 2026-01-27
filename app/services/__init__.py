"""
Service Organization
====================
Services are organized by their lifecycle and instantiation pattern:

**application/**
  Singleton services managed by ServiceContainer. One instance per application.
  Examples: GrowthService, DeviceCoordinator, AuthService, PlantService
  
**hardware/**
  Per-unit runtime worker services instantiated by UnitRuntimeManager.
  One instance per growth unit for hardware control.
  Examples: SensorPollingService, ClimateControlService, SafetyService
  
**utilities/**
  Stateless utility services that can be instantiated multiple times.
  Pure functions and helper services without shared state.
  Examples: CalibrationService, AnomalyDetectionService

For detailed architecture, see: SERVICE_REORGANIZATION.md
"""

# Import commonly-used services for convenience
from .hardware.safety_service import SafetyService
from .hardware.state_tracking_service import StateTrackingService
from .hardware.scheduling_service import SchedulingService
from .hardware.energy_monitoring import (
    EnergyMonitoringService,
    EnergyReading,
    DEFAULT_POWER_PROFILES
)
from .application.zigbee_management_service import (
    ZigbeeManagementService,
    DiscoveredDevice,
    DeviceCapability
)

__all__ = [
    'SafetyService',
    'StateTrackingService',
    'SchedulingService',
    'EnergyMonitoringService',
    'EnergyReading',
    'DEFAULT_POWER_PROFILES',
    'ZigbeeManagementService',
    'DiscoveredDevice',
    'DeviceCapability',
]