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
        self.state = 'off'
    
    def activate(self):
        """
        Activates the actuator.
        """
        self.relay.turn_on()
        self.state = 'on'
    
    def deactivate(self):
        """
        Deactivates the actuator.
        """
        self.relay.turn_off()
        self.state = 'off'
    
    def get_state(self):
        """
        Returns the current state of the actuator.

        Returns:
            str: The current state ('on' or 'off').
        """
        return self.state

class ActuatorManager:
    """
    Manages multiple actuator objects.

    Attributes:
        database_manager (DatabaseManager): An instance of the database manager.
        actuators (dict): Dictionary to store actuators with their names as keys.
    
    Methods:
        add_actuator(name, actuator): Adds an actuator to the manager.
        remove_actuator(name): Removes an actuator from the manager by name.
        activate_actuator(name): Activates a specified actuator by name.
        deactivate_actuator(name): Deactivates a specified actuator by name.
        get_actuators(): Returns the names of all managed actuators.
        get_actuator_by_name(name): Retrieves an actuator by its name.
    """
    def __init__(self, database_manager):
        """
        Initializes the ActuatorManager with an empty dictionary of actuators.
        """
        self.database_manager = database_manager
        self.actuators = {}

    def _load_actuators_from_db(self):
        """
        Loads actuator configurations from the database and creates Actuator objects.

        Returns:
            dict: A dictionary of Actuator objects keyed by their names.
        """
        actuators = {}
        actuator_configs = self.database_manager.get_actuator_configs()
        for config in actuator_configs:
            actuator = RelayActuator(device=config['name'], pin=config['gpio'], ip=config['ip_address'])
            actuators[config['name']] = actuator
        return actuators
    
    def add_actuator(self, name, actuator):
        """
        Adds an actuator to the manager.

        Args:
            name (str): The name of the actuator.
            actuator (Actuator): The actuator object to be added.
        """
        self.actuators[name] = actuator
        self.database_manager.insert_actuator(name, actuator.relay.pin, actuator.relay.ip)
    
    def remove_actuator(self, name):
        """
        Removes an actuator from the manager by name.

        Args:
            name (str): The name of the actuator to be removed.
        """
        if name in self.actuators:
            del self.actuators[name]
            self.database_manager.remove_actuator(name)
    
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

    def get_actuator(self, name):
        """
        Retrieves an actuator by its name.

        Args:
            name (str): The name of the actuator to retrieve.

        Returns:
            Actuator: The actuator object with the specified name, or None if not found.
        """
        return self.actuators.get(name)
    
    def get_actuators(self):
        """
        Returns the names of all managed actuators.

        Returns:
            list: A list of actuator names.
        """
        print("ActuatorManager value: ",self.actuators.values())
        return self.actuators.keys()
    
    def get_actuator_states(self):
        """
        Returns the states of all managed actuators.

        Returns:
            dict: A dictionary with actuator names as keys and their states as values.
        """
        return {name: actuator.get_state() for name, actuator in self.actuators.items()}

    def cleanup(self):
        """
        Cleans up all actuator managed by the ActuatorManager.
        """
        for actuator in self.actuators.values():
            actuator.relay.cleanup()

    def __del__(self):
        """
        Destructor to ensure cleanup is called when the ActuatorManager object is destroyed.
        """
        self.cleanup()