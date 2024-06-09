from abc import ABC, abstractmethod
from relay.relay import Relay

class Actuator(ABC):
    """
    Abstract base class representing a generic actuator.

    Methods:
        activate(): Activates the actuator.
        deactivate(): Deactivates the actuator.
    """
    @abstractmethod
    def activate(self):
        """
        Activates the actuator.
        """
        pass
    
    @abstractmethod
    def deactivate(self):
        """
        Deactivates the actuator.
        """
        pass

class RelayActuator(Actuator):
    """
    A generic actuator controlled by a relay.

    Attributes:
        relay (Relay): The relay controlling the actuator.
    
    Methods:
        activate(): Activates the actuator.
        deactivate(): Deactivates the actuator.
    """
    def __init__(self, device, pin=None, ip=None):
        """
        Initializes the RelayActuator with a relay.

        Args:
            device (str): The name of the device.
            pin (int, optional): The GPIO pin used to control the relay.
            ip (str, optional): The IP address for wireless control of the relay.
        """
        self.relay = Relay(device=device, pin=pin, ip=ip)
    
    def activate(self):
        """
        Activates the actuator.
        """
        self.relay.turn_on()
    
    def deactivate(self):
        """
        Deactivates the actuator.
        """
        self.relay.turn_off()

class ActuatorManager:
    """
    Manages multiple actuator objects.

    Attributes:
        actuators (dict): Dictionary to store actuators with their names as keys.
    
    Methods:
        add_actuator(name, actuator): Adds an actuator to the manager.
        remove_actuator(name): Removes an actuator from the manager by name.
        activate_actuator(name): Activates a specified actuator by name.
        deactivate_actuator(name): Deactivates a specified actuator by name.
        get_actuators(): Returns the names of all managed actuators.
    """
    def __init__(self):
        """
        Initializes the ActuatorManager with an empty dictionary of actuators.
        """
        self.actuators = {}
    
    def add_actuator(self, name, actuator):
        """
        Adds an actuator to the manager.

        Args:
            name (str): The name of the actuator.
            actuator (Actuator): The actuator object to be added.
        """
        self.actuators[name] = actuator
    
    def remove_actuator(self, name):
        """
        Removes an actuator from the manager by name.

        Args:
            name (str): The name of the actuator to be removed.
        """
        if name in self.actuators:
            del self.actuators[name]
    
    def activate_actuator(self, name):
        """
        Activates a specified actuator by name.

        Args:
            name (str): The name of the actuator to be activated.
        """
        if name in self.actuators:
            self.actuators[name].activate()
            print("Activate name: ", + name)
    
    def deactivate_actuator(self, name):
        """
        Deactivates a specified actuator by name.

        Args:
            name (str): The name of the actuator to be deactivated.
        """
        if name in self.actuators:
            self.actuators[name].deactivate()
            print("Deactivate name: ", + name)
    
    def get_actuators(self):
        """
        Returns the names of all managed actuators.

        Returns:
            list: A list of actuator names.
        """
        print("ActuatorManager value: ",self.actuators.values())
        return self.actuators.keys()