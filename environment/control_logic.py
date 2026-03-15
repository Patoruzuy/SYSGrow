# environment/control_logic.py
from control_algorithms import PIDController
from utils.event_bus import EventBus

class ControlLogic:
    """Uses PID & ML to adjust environment."""
    def __init__(self, actuator_manager):
        self.actuator_manager = actuator_manager
        self.event_bus = EventBus()
        
        self.temp_pid = PIDController(kp=1.0, ki=0.1, kd=0.05, setpoint=24.0)
        self.humidity_pid = PIDController(kp=1.0, ki=0.1, kd=0.05, setpoint=50.0)

        self.event_bus.subscribe("temperature_update", self.control_temperature)
        self.event_bus.subscribe("humidity_update", self.control_humidity)

    def control_temperature(self, data):
        control_signal = self.temp_pid.compute(float(data["temperature"]))
        if control_signal > 0:
            self.event_bus.publish("activate_actuator", {"actuator": "Heater"})
        else:
            self.event_bus.publish("deactivate_actuator", {"actuator": "Heater"})

    def control_humidity(self, data):
        control_signal = self.humidity_pid.compute(float(data["humidity"]))
        if control_signal > 0:
            self.event_bus.publish("activate_actuator", {"actuator": "Humidifier"})
        else:
            self.event_bus.publish("deactivate_actuator", {"actuator": "Humidifier"})
