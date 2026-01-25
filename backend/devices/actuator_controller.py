from abc import ABC, abstractmethod
from relays.relay import GPIORelay, WiFiRelay, ZigbeeRelay
import time
import logging

logging.basicConfig(level=logging.INFO, filename="devices_system.log",
                    format="%(asctime)s - %(levelname)s - %(message)s")

class Actuator(ABC):
    """
    Abstract base class representing a generic actuator.

    This class should be inherited by any specific actuator implementation.
    It defines the interface that all actuators must implement, ensuring
    consistency and interoperability within the system.

    Methods:
        activate(): Activates the actuator.
        deactivate(): Deactivates the actuator.
    
    Usage:
        To create a new actuator type, inherit from this class and implement
        the activate and deactivate methods. For example:

        class MyCustomActuator(Actuator):
            def activate(self):
                # Custom activation logic
                pass

            def deactivate(self):
                # Custom deactivation logic
                pass
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

    @abstractmethod
    def get_state(self):
        """
        Returns the current state

        Returns:
            str: on or off
        """
        pass

class GIORelayActuator(Actuator):
    """A relay actuator that controls a GPIO relay."""

    def __init__(self, actuator_id, device, pin=None, init_delay=1):
        """
        Initializes the actuator with the correct relay type.

        Args:
            actuator_id (int): Unique ID for the actuator.
            device (str): Device name.
            pin (int, optional): GPIO pin (for wired relay).
            init_delay (int, optional): Delay before initializing to prevent power surges (default: 1).
        """
        self.id = actuator_id
        self.device = device
        self.pin = pin
        self.state = 'off'

        try:
            self.relay = GPIORelay(self.device, self.pin)
        except ValueError:
            raise ValueError("No valid relay configuration provided.")

        # Add delay during initialization, ensures that each relay is initialized one after another,
        # reducing the risk of all relays turning on simultaneously during startup
        # preventing sudden power surges that could cause the relay board or power supply to shut down.
        if init_delay > 0:
            time.sleep(init_delay)
    
    def activate(self):
        """
        Activates the actuator.
        """
        self.relay.turn_on()
        self.state = 'on'
        logging.info(f"Actuator {self.id} ({self.device}): Activated (GPIO)")
    
    def deactivate(self):
        """
        Deactivates the actuator.
        """
        self.relay.turn_off()
        self.state = 'off'
        logging.info(f"Actuator {self.id} ({self.device}): Deactivated (GPIO)")
    
    def get_state(self):
        """
        Returns the current state of the actuator.

        Returns:
            str: The current state ('on' or 'off').
        """
        return self.state
    
class WiFiRelayActuator(Actuator):
    """Handles wireless relay actuators connected via WiFi."""
    
    def __init__(self, actuator_id, device, ip_address=None):
        """
        Initializes the WiFiRelayActuator with the given IP address.

        Args:
            ip (str): IP address for ESP8266 WiFi relay.
        """
        self.id = actuator_id
        self.device = device
        self.ip_address = ip_address
        self.state = 'off'
        try:
            self.relay = WiFiRelay(self.device, self.ip_address)
        except ValueError:
            raise ValueError("No valid relay configuration provided.")

    def activate(self):
        """
        Sends an HTTP request to turn on the relay.
        """
        self.relay.turn_on()
        self.state = 'on'
        logging.info(f"Actuator {self.id} ({self.device}): Activated (Wifi-Reley)")
    
    def deactivate(self):
        """
        Sends an HTTP request to turn off the relay.
        """
        self.relay.turn_off()
        self.state = 'off'
        logging.info(f"Actuator {self.id} ({self.device}): Deactivated (Wifi-Reley)")

    def get_state(self):
        """
        Returns the current state of the actuator.

        Returns:
            str: The current state ('on' or 'off').
        """
        return self.state
    
class WirelessRelayActuator(Actuator):
    """Handles wireless relay actuators connected via Zigbee."""

    def __init__(self, actuator_id, device: str, zigbee_channel: str, connection_mode: str = "Zigbee", mqtt_broker: str = "localhost", mqtt_port: int = 1883):
        """
        Initializes the relay with the chosen communication method.

        Args:
            device (str): The name of the device.
            zigbee_channel (str): The relay channel of the device.
            connection_mode (str, optional): Communication mode ('WiFi', 'BLE', 'Zigbee').
            mqtt_broker (str, optional): The MQTT broker address (default: localhost).
            mqtt_port (int, optional): The MQTT broker port (default: 1883).
       """
        self.id = actuator_id
        self.device = device
        self.zigbee_channel = zigbee_channel
        self.connection_mode = connection_mode
        self.ble_client = None
        self.mqtt_broker = mqtt_broker
        self.mqtt_port = mqtt_port
        self.state = 'off'
        try:
            self.relay = ZigbeeRelay(device, zigbee_channel, connection_mode, mqtt_broker, mqtt_port)
        except ValueError:
            raise ValueError("No valid relay configuration provided.")

    def activate(self):
        """
        Sends a command to activate the relay.
        """
        self.relay.turn_on()
        self.state = 'on'
        logging.info(f"Actuator {self.id} ({self.device}): Activated {self.connection_mode}")

    def deactivate(self):
        """
        Sends a command to deactivate the relay.
        """
        self.relay.turn_off()
        self.state = 'off'
        logging.info(f"Actuator {self.id} ({self.device}): Deactivated ({self.connection_mode})")

    def get_state(self):
            """
            Returns the current state of the actuator.

            Returns:
                str: The current state ('on' or 'off').
            """
            return self.state
    
class ActuatorFactory:
    """Factory for dynamically creating actuators."""

    @staticmethod
    def create_actuator(actuator_type, **kwargs):
        """
        Creates an actuator instance dynamically based on the communication type.

        Args:
            actuator_type (str): Type of actuator (GPIO, WiFi, Zigbee).
            kwargs: Additional parameters (pin, ip, zigbee_topic, etc.).

        Returns:
            Actuator instance or raises an error if the type is unknown.
        """
        if actuator_type == "GPIO":
            return GIORelayActuator(
                actuator_id=kwargs.get("actuator_id"),
                device=kwargs.get("device"),
                pin=kwargs.get("pin"),
            )
        elif actuator_type == "WiFi":
            return WiFiRelayActuator(
                actuator_id=kwargs.get("actuator_id"),
                device=kwargs.get("device"),
                ip_address=kwargs.get("ip_address"),
            )
        elif actuator_type == "Zigbee":
            return WirelessRelayActuator(
                actuator_id=kwargs.get("actuator_id"),
                device=kwargs.get("device"),
                zigbee_channel=kwargs.get("zigbee_channel"),
                mqtt_broker=kwargs.get("mqtt_broker", "localhost"),
                mqtt_port=kwargs.get("mqtt_port", 1883),
            )
        else:
            raise ValueError(f"Unknown actuator type: {actuator_type}")

class ActuatorController:
    """
    Manages multiple actuators dynamically.

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
    def __init__(self, unit_name, database_manager):
        """
        Initializes the ActuatorManager with an empty dictionary of actuators.

        Args:
            unit_name (str): The name of the unit.
            database_handler (DatabaseHandler): An instance of the database handler.
        """
        self.unit_name = unit_name
        self.database_manager = database_manager
        self.actuators = self._load_actuators_from_db()

    def _load_actuators_from_db(self):
        """
        Loads actuator configurations from the database and creates Actuator objects.

        Returns:
            dict: A dictionary of Actuator objects keyed by their names.
        """
        actuators = {}
        actuator_configs = self.database_manager.get_actuator_configs()
        
        for config in actuator_configs:
            actuator = self._create_actuator_from_config(config)
            if actuator:
                actuators[config['device']] = actuator

        return actuators

    def _create_actuator_from_config(self, config):
        """
        Creates an actuator instance from a configuration dictionary.

        Args:
            config (dict): Configuration dictionary for the actuator.

        Returns:
                logging.warning(f"Skipping unknown actuator config: {config}")
        """
        actuator_id = config['id']
        actuator_type = config['actuator_type']
        device = config['device']
        pin = config.get('gpio')
        ip = config.get('ip_address')
        zigbee_topic = config.get('zigbee_topic')
        zigbee_channel = config.get('zigbee_channel')
        mqtt_broker = config.get('mqtt_broker', 'localhost')
        mqtt_port = config.get('mqtt_port', 1883)

        return ActuatorFactory.create_actuator(
            actuator_type,
            actuator_id=actuator_id,
            device=device,
            pin=pin,
            ip=ip,
            zigbee_topic=zigbee_topic,
            zigbee_channel = zigbee_channel,
            mqtt_broker=mqtt_broker,
            mqtt_port=mqtt_port
        )
    
    def add_actuator(self, device, actuator_type, **kwargs):
        """
        Adds an actuator dynamically.
        """
        actuator_id = self.database_manager.insert_actuator(device, actuator_type, kwargs.get("pin"), kwargs.get("ip"), kwargs.get("zigbee_topic"), kwargs.get("zigbee_channel"), kwargs.get("mqtt_broker"), kwargs.get("mqtt_port"))
        actuator = ActuatorFactory.create_actuator(
            actuator_type,
            actuator_id=actuator_id,
            device=device,
            **kwargs
        )
        self.actuators[device] = actuator
    
    def remove_actuator(self, device):
        """
        Removes an actuator from the manager by device.

        Args:
            device (str): The device type to be removed.
        """
        if device in self.actuators:
            del self.actuators[device]
            self.database_manager.remove_actuator(device)
    
    def activate_actuator(self, device):
        """
        Activates a specified actuator by device.

        Args:
            device (str): The actuator type to be activated.
        """
        if device in self.actuators:
            self.actuators[device].activate()
        else:
            logging.error(f"Actuator {device} not found.")
    
    def deactivate_actuator(self, device):
        """
        Deactivates a specified actuator by device.

        Args:
            device (str): The name of the actuator to be deactivated.
        """
        if device in self.actuators:
            self.actuators[device].deactivate()
            logging.info(f"Deactivate device: {device}")
        else:
            print(f"Actuator {device} not found.")
    
    def get_actuators(self):
        """
        Returns all the actuators.

        Returns:
            dict: A dict of actuator.
        """
        return self.actuators

def cleanup(self):
    """
    Cleans up all actuator managed by the ActuatorManager.
    """
    for actuator in self.actuators.values():
        if hasattr(actuator, 'relay'):  # Check if the actuator has a relay attribute
            actuator.relay.cleanup()
            
def __del__(self):
    """
    Destructor to ensure cleanup is called when the ActuatorManager object is destroyed.
    """
    self.cleanup()
    try:
        super().__del__()
    except AttributeError:
        pass