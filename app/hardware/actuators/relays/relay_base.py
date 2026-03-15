"""
This file contains the abstract base class for all relay types.
The RelayBase class defines the common interface for all relay classes. It provides methods to turn the relay on and off, and to get the device name.

    
"""

from app.utils.event_bus import EventBus

class RelayBase:
    """
    Abstract base class for all relay types.

    Attributes:
        device (str): The name of the device controlled by the relay.
    
    Methods:
        turn_on(): Turns the relay on. (Implemented in subclasses)
        turn_off(): Turns the relay off. (Implemented in subclasses)
        get_device(): Returns the device name.
    """

    def __init__(self, device: str):
        """
        Initializes the relay with a device name.

        Args:
            device (str): The name of the device controlled by the relay.
        """
        self.device = device
        self.event_bus = EventBus()

    def turn_on(self):
        """Turns the relay on. It is implemented in subclasses."""
        raise NotImplementedError("Subclasses must implement turn_on method")

    def turn_off(self):
        """Turns the relay off. It is implemented in subclasses."""
        raise NotImplementedError("Subclasses must implement turn_off method")

    def get_device(self) -> str:
        """
        Returns the name of the device.

        Returns:
            str: The device name.
        """
        return self.device