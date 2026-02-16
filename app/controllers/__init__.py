"""
Controllers Package
====================

This package contains the control layer of the application:
- Event-driven controllers that subscribe to EventBus
- PID control algorithms for environmental factors
- Throttled analytics persistence
- Actuator command execution

Architecture:
    EventBus Events
         │
         ▼
    ┌─────────────────────────────────┐
    │      Controller Layer           │
    │  ┌───────────────────────────┐  │
    │  │   ClimateController       │  │  ← Environment sensors (temp, humidity, CO2, lux, pressure)
    │  │   PlantSensorController   │  │  ← Plant sensors (soil_moisture, pH, EC) + Irrigation
    │  └───────────────────────────┘  │
    │              │                  │
    │              ▼                  │
    │  ┌───────────────────────────┐  │
    │  │      ControlLogic         │  │  ← PID algorithms, actuator commands
    │  └───────────────────────────┘  │
    └─────────────────────────────────┘
         │                    │
         ▼                    ▼
    Analytics Repo      ActuatorManager

Persistence Targets:
- ClimateController → SensorReading table (environment data)
- PlantSensorController → PlantReadings table (plant-specific data)
"""

from app.controllers.climate_controller import ClimateController
from app.controllers.control_algorithms import PIDController
from app.controllers.control_logic import ControlLogic
from app.controllers.plant_sensor_controller import PlantSensorController
from app.controllers.throttle_config import DEFAULT_THROTTLE_CONFIG, ThrottleConfig
from app.controllers.throttled_analytics_writer import ThrottledAnalyticsWriter

__all__ = [
    "DEFAULT_THROTTLE_CONFIG",
    "ClimateController",
    "ControlLogic",
    "PIDController",
    "PlantSensorController",
    "ThrottleConfig",
    "ThrottledAnalyticsWriter",
]
