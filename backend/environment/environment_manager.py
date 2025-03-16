# environment/environment_manager.py
from utils.event_bus import EventBus
from environment.control_logic import ControlLogic

class EnvironmentManager:
    """Manages climate control."""
    def __init__(self, actuator_manager):
        self.event_bus = EventBus()
        self.control_logic = ControlLogic(actuator_manager)

        self.event_bus.subscribe("temperature_update", self.control_logic.control_temperature)
        self.event_bus.subscribe("humidity_update", self.control_logic.control_humidity)
