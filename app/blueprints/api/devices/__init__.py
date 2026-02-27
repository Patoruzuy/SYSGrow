"""
Device Management API Blueprint
================================

Modular device management API organized into logical sub-modules:
- sensors.py: Sensor CRUD, health, calibration, discovery
- actuators.py: Actuator CRUD, control, energy monitoring
- zigbee.py: Zigbee2MQTT integration and device management
- esp32.py: ESP32-C3 analog sensor device management
- shared.py: Common endpoints (config, connectivity, etc.)

All routes are registered under /api/devices prefix.
"""

from __future__ import annotations

import logging

from flask import Blueprint

# Create main blueprint
devices_api = Blueprint("devices_api", __name__)
logger = logging.getLogger("devices_api")

# Import all sub-modules to register their routes
# These will add routes to the devices_api blueprint
from . import (
    actuators,  # Registers actuator routes and error handlers
    esp32,  # ESP32-C3 analog sensor device management
    sensors,
    shared,
    zigbee,
)

_ = (actuators, esp32, sensors, shared, zigbee)

__all__ = ["devices_api"]
