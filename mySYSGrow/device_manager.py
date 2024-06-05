"""
Description: This script defines the Device and DeviceManager.

Author: Sebastian Gomez
Date: 02/06/2024

"""
from relay.relay import Relay
import time

class Device:
    """
    Represents a controllable device with either GPIO or wireless functionality.

    Attributes:
        name (str): The name of the device.
        gpio (int, optional): The GPIO pin number used to control the device.
        ip_address (str, optional): The IP address for wireless control.
        type (str, optional): The type of control (e.g., 'temperature', 'humidity').
        functionality (str, optional): Description of the device's functionality.
        relay (Relay): The Relay object used to control the device.
    """

    def __init__(self, name, gpio=None, ip_address=None, type=None, functionality=None):
        """
        Initializes a Device object.

        Args:
            name (str): The name of the device.
            gpio (int, optional): The GPIO pin number for control.
            ip_address (str, optional): The IP address for wireless control.
            type (str, optional): The type of control (e.g., 'temperature', 'humidity').
            functionality (str, optional): Description of the device's functionality.
        """
        self.name = name
        self.gpio = gpio
        self.ip_address = ip_address
        self.type = type
        self.functionality = functionality
        self.relay = Relay(device=name, pin=gpio, ip=ip_address)

    def turn_on(self):
        """Turns on the device using the Relay object."""
        self.relay.turn_on()

    def turn_off(self):
        """Turns off the device using the Relay object."""
        self.relay.turn_off()

    def test(self):
        """
        Tests the device by turning it on, waiting for a second, and then turning it off.

        Returns:
            bool: True if the test succeeds, False if an exception occurs.
        """
        try:
            self.turn_on()
            time.sleep(1)
            self.turn_off()
            return True
        except Exception as e:
            print(f"Error testing device {self.name}: {e}")
            return False



class DeviceManager:
    """
    Manages multiple Device objects, loading their configurations from a database.

    Attributes:
        database_manager (DatabaseManager): An instance of the database manager.
        devices (dict): A dictionary of Device objects keyed by their functionalities.

    Methods:
        get_device_by_functionality(functionality): Retrieves a device by its functionality.
        add_device(name, gpio, ip_address, type, functionality): Adds a new device.
        turn_on_device(functionality): Turns on a specified device by functionality.
        turn_off_device(functionality): Turns off a specified device by functionality.
        test_device(functionality): Tests a specified device by functionality.
    """

    def __init__(self, database_manager):
        """
        Initializes a DeviceManager object.

        Args:
            database_manager (DatabaseManager): An instance of the database manager.
        """
        self.database_manager = database_manager
        self.devices = self._load_devices_from_db()

    def _load_devices_from_db(self):
        """
        Loads device configurations from the database and creates Device objects.

        Returns:
            dict: A dictionary of Device objects keyed by their functionalities.
        """
        devices = {}
        device_configs = self.database_manager.get_device_configs()
        for config in device_configs:
            device = Device(
                name=config['name'],
                gpio=config['gpio'],
                ip_address=config['ip_address'],
                type=config['type'],
                functionality=config['functionality']
            )
            devices[config['functionality']] = device
        return devices

    def get_device_by_functionality(self, functionality):
        """
        Retrieves a Device object by its functionality.

        Args:
            functionality (str): The functionality of the device to retrieve.

        Returns:
            Device: The Device object with the specified functionality, or None if not found.
        """
        return self.devices.get(functionality)

    def add_device(self, name, gpio, ip_address, type, functionality):
        """
        Adds a new device to the manager.

        Args:
            name (str): The name of the device.
            gpio (int, optional): The GPIO pin number for control.
            ip_address (str, optional): The IP address for wireless control.
            type (str): The type of control (e.g., 'temperature', 'humidity').
            functionality (str): Description of the device's functionality.
        """
        device = Device(name, gpio, ip_address, type, functionality)
        self.devices[functionality] = device
        self.database_manager.save_device_config(device)

    def turn_on_device(self, functionality):
        """
        Turns on the specified device by functionality.

        Args:
            functionality (str): The functionality of the device to turn on.
        """
        device = self.get_device_by_functionality(functionality)
        if device:
            device.turn_on()

    def turn_off_device(self, functionality):
        """
        Turns off the specified device by functionality.

        Args:
            functionality (str): The functionality of the device to turn off.
        """
        device = self.get_device_by_functionality(functionality)
        if device:
            device.turn_off()

    def test_device(self, functionality):
        """
        Tests the specified device by functionality.

        Args:
            functionality (str): The functionality of the device to test.

        Returns:
            bool: True if the test succeeds, False if the device is not found or an error occurs.
        """
        device = self.get_device_by_functionality(functionality)
        if device:
            return device.test()
        return False