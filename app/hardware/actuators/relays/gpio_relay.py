# Description: GPIO relay implementation for Raspberry Pi.
#
import logging

from app.enums.events import DeviceEvent
from app.schemas.events import RelayStatePayload

from .relay_base import RelayBase

logger = logging.getLogger(__name__)


class GPIORelay(RelayBase):
    """
    Controls a relay using Raspberry Pi GPIO.

    Attributes:
        device (str): The name of the controlled device.
        pin (int): The GPIO pin used to control the relay.

    Methods:
        turn_on(): Turns the relay on by setting the GPIO pin HIGH.
        turn_off(): Turns the relay off by setting the GPIO pin LOW.
        cleanup(): Releases the GPIO pin resources.
    """

    def __init__(self, device: str, pin: int):
        """
        Initializes the GPIO relay with the specified GPIO pin.

        Args:
            device (str): The name of the device.
            pin (int): The GPIO pin number to control the relay.
        """
        super().__init__(device)
        self.pin = pin
        self.GPIO = self._setup_gpio()
        if self.GPIO:
            self.GPIO.setmode(self.GPIO.BCM)
            self.GPIO.setup(self.pin, self.GPIO.OUT)
            logger.info(f"GPIO pin {self.pin} set as OUTPUT")
        else:
            logger.warning(f"GPIO is not available.  GPIO Relay {self.device} will not function.")

    def _setup_gpio(self):
        """Imports and sets up GPIO only if running on Raspberry Pi."""
        try:
            import RPi.GPIO as GPIO  # type: ignore

            return GPIO
        except (ImportError, RuntimeError):
            logger.error("GPIO not available. Running in non-Raspberry Pi environment.")
            return None

    def turn_on(self):
        """Turns the relay on by setting the GPIO pin HIGH."""
        if self.GPIO:
            try:
                self.GPIO.output(self.pin, self.GPIO.HIGH)
                self.event_bus.publish(
                    DeviceEvent.RELAY_STATE_CHANGED,
                    RelayStatePayload(device=self.device, state="on"),
                )  # Publish Event
                logger.info(f"Turned on GPIO relay for {self.device} on pin {self.pin}")
            except Exception as e:
                logger.error(f"Error turning on GPIO relay {self.device}: {e}")
        else:
            logger.warning(f"GPIO not initialized. Cannot turn on relay {self.device}")

    def turn_off(self):
        """Turns the relay off by setting the GPIO pin LOW."""
        if self.GPIO:
            try:
                self.GPIO.output(self.pin, self.GPIO.LOW)
                self.event_bus.publish(
                    DeviceEvent.RELAY_STATE_CHANGED,
                    RelayStatePayload(device=self.device, state="off"),
                )  # Publish Event
                logger.info(f"Turned off GPIO relay for {self.device} on pin {self.pin}")
            except Exception as e:
                logger.error(f"Error turning off GPIO relay {self.device}: {e}")
        else:
            logger.warning(f"GPIO not initialized. Cannot turn off relay {self.device}")

    def cleanup(self):
        """Releases the GPIO pin resources."""
        if self.GPIO:
            try:
                self.GPIO.cleanup(self.pin)
                logger.info(f"Cleaned up GPIO pin {self.pin} for {self.device}")
            except Exception as e:
                logger.error(f"Error cleaning up GPIO pin {self.pin}: {e}")

    def __enter__(self):
        """Enter the runtime context related to this object."""
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """Exit the runtime context related to this object."""
        self.cleanup()

    def __del__(self):
        """Destructor to ensure cleanup is called when the object is destroyed."""
        self.cleanup()
