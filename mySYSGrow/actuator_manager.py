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
        actuators (dict): Dictionary to store actuators with their IDs as keys.
    
    Methods:
        add_actuator(name, gpio, ip_address): Adds an actuator to the manager.
        remove_actuator(actuator_id): Removes an actuator from the manager by its ID.
        activate_actuator(actuator_id): Activates a specified actuator by its ID.
        deactivate_actuator(actuator_id): Deactivates a specified actuator by its ID.
        get_actuator(actuator_id): Retrieves an actuator by its ID.
        get_actuators(): Returns the IDs of all managed actuators.
        get_actuator_states(): Returns the states of all managed actuators.
    """
    count = 0  # Class variable to keep track of the number of actuators created

    def __init__(self, database_manager):
        """
        Initializes the ActuatorManager with an empty dictionary of actuators.
        """
        self.database_manager = database_manager
        self.actuators = self._load_actuators_from_db()

    def _load_actuators_from_db(self):
        """
        Loads actuator configurations from the database and creates Actuator objects.

        Returns:
            dict: A dictionary of Actuator objects keyed by their unique IDs.
        """
        actuators = {}
        actuator_configs = self.database_manager.get_actuator_configs()
        for config in actuator_configs:
            actuator = RelayActuator(device=config['name'], pin=config['gpio'], ip=config['ip_address'])
            actuators[config['id']] = actuator  # Use the actuator ID from the database as the key

            # Ensure the count reflects the highest ID loaded from the database
            if config['id'] > ActuatorManager.count:
                ActuatorManager.count = config['id']

        return actuators
    
    def add_actuator(self, name, gpio, ip_address=None):
        """
        Adds a new actuator to the manager.

        Args:
            name (str): The name of the actuator.
            gpio (int): The GPIO pin number to which the actuator is connected.
            ip_address (str, optional): The IP address for wireless control.

        Returns:
            int: The unique ID of the newly added actuator.
        """
        ActuatorManager.count += 1  # Increment the count for the next actuator ID
        actuator_id = ActuatorManager.count  # Use the updated count as the actuator ID

        actuator = RelayActuator(device=name, pin=gpio, ip=ip_address)
        self.actuators[actuator_id] = actuator

        # Store the actuator in the database
        self.database_manager.insert_actuator(actuator_id, name, gpio, ip_address)
        print(f"Added actuator '{name}' with ID {actuator_id}.")
        return actuator_id
    
    def remove_actuator(self, actuator_id):
        """
        Removes an actuator from the manager by its ID.

        Args:
            actuator_id (int): The ID of the actuator to be removed.
        """
        if actuator_id in self.actuators:
            del self.actuators[actuator_id]
            self.database_manager.remove_actuator(actuator_id)
            print(f"Removed actuator with ID {actuator_id}.")
        else:
            print(f"Actuator with ID '{actuator_id}' not found.")
    
    def activate_actuator(self, actuator_id):
        """
        Activates a specified actuator by its ID.

        Args:
            actuator_id (int): The ID of the actuator to be activated.
        """
        if actuator_id in self.actuators:
            self.actuators[actuator_id].activate()
            print(f"Activated actuator with ID {actuator_id}.")
        else:
            print(f"Actuator with ID '{actuator_id}' not found.")
    
    def deactivate_actuator(self, actuator_id):
        """
        Deactivates a specified actuator by its ID.

        Args:
            actuator_id (int): The ID of the actuator to be deactivated.
        """
        if actuator_id in self.actuators:
            self.actuators[actuator_id].deactivate()
            print(f"Deactivated actuator with ID {actuator_id}.")
        else:
            print(f"Actuator with ID '{actuator_id}' not found.")

    def get_actuator(self, actuator_id):
        """
        Retrieves an actuator by its ID.

        Args:
            actuator_id (int): The ID of the actuator to retrieve.

        Returns:
            Actuator: The actuator object with the specified ID, or None if not found.
        """
        return self.actuators.get(actuator_id)
    
    def get_actuators(self):
        """
        Returns the IDs of all managed actuators.

        Returns:
            list: A list of actuator IDs.
        """
        return list(self.actuators.keys())
    
    def get_actuator_states(self):
        """
        Returns the states of all managed actuators.

        Returns:
            dict: A dictionary with actuator IDs as keys and their states as values.
        """
        return {actuator_id: actuator.get_state() for actuator_id, actuator in self.actuators.items()}

    def cleanup(self):
        """
        Cleans up all actuators managed by the ActuatorManager.
        """
        for actuator in self.actuators.values():
            actuator.relay.cleanup()

    def __del__(self):
        """
        Destructor to ensure cleanup is called when the ActuatorManager object is destroyed.
        """
        self.cleanup()