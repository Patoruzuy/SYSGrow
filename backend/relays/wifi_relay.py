import requests
import logging
from .gpio_relay import RelayBase

logging.basicConfig(level=logging.INFO, filename="devices_system.log",
                    format="%(asctime)s - %(levelname)s - %(message)s")

class WiFiRelay(RelayBase):
    """
    Controls a relay via an HTTP API (e.g., ESP8266 or ESP-01).

    Attributes:
        device (str): The name of the controlled device.
        ip (str): The IP address of the relay module.
    
    Methods:
        turn_on(): Sends an HTTP request to turn on the relay.
        turn_off(): Sends an HTTP request to turn off the relay.
    """

    def __init__(self, device: str, ip: str):
        """
        Initializes the WiFi relay with an IP address.

        Args:
            device (str): The name of the device.
            ip (str): The IP address of the relay module.
        """
        super().__init__(device)
        self.ip = ip

    def turn_on(self):
        """Sends an HTTP request to turn on the relay."""
        try:
            self._send_request("on")
            self.event_bus.publish("relay_state_changed", {"device": self.device, "state": "on"}) # Publish Event
            logging.info(f"Turned on WiFi relay for {self.device} at {self.ip}")
        except Exception as e:
            logging.error(f"Error turning on WiFi relay {self.device}: {e}")

    def turn_off(self):
        """Sends an HTTP request to turn off the relay."""
        try:
            self._send_request("off")
            self.event_bus.publish("relay_state_changed", {"device": self.device, "state": "off"}) # Publish Event
            logging.info(f"Turned off WiFi relay for {self.device} at {self.ip}")
        except Exception as e:
            logging.error(f"Error turning off WiFi relay {self.device}: {e}")

    def _send_request(self, state: str):
        """
        Sends an HTTP request to the relay module.

        Args:
            state (str): The relay state ('on' or 'off').
        """
        url = f"http://{self.ip}/relay/{state}"
        try:
            response = requests.get(url, timeout=5)  # Added timeout
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise Exception(f"Error controlling relay at {url}: {e}") from e  