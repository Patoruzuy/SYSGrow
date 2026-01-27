"""
Hardware Service Layer
======================
Singleton services for managing sensors, actuators, and climate control.

These services replace the per-unit UnitRuntimeManager pattern with global
singleton services that manage ALL devices across ALL units.

Services:
- SensorManagementService: Global sensor operations (read, calibrate, poll)
- ActuatorManagementService: Global actuator operations (control, schedule)
- ClimateController: Per-unit climate control automation (legacy, being refactored)

Architecture:
    ServiceContainer
      ├─ SensorManagementService (singleton)
      ├─ ActuatorManagementService (singleton)
      └─ ClimateController (per-unit, legacy)

Memory-First:
    All services use TTLCache to minimize database queries, ideal for
    resource-constrained environments like Raspberry Pi.

Migration Status:
    Phase 1: SensorManagementService and ActuatorManagementService created ✓
    Phase 2: Legacy device wrappers removed ✓
    Phase 3: Refactor GrowthService (pending)
    Phase 4: Delete UnitRuntimeManager (pending)
"""

from app.services.hardware.sensor_management_service import SensorManagementService
from app.services.hardware.actuator_management_service import ActuatorManagementService

# Climate controller now in app.controllers package
from app.controllers import ClimateController

__all__ = [
    "SensorManagementService",
    "ActuatorManagementService",
    "ClimateController",
]
