import RPi.GPIO as GPIO
import requests

class Relay:
    def __init__(self, device=None, pin=None, ip=None):
        """
        Initialize the Relay instance.

        Args:
            pin (int): The GPIO pin number to which the relay is connected (for wired relay).
            ip (str): The IP address of the ESP8266 ESP-01 module (for wireless relay).
        """
        self.device = device
        self.pin = pin
        self.ip = ip
        self.is_gpio_relay = pin is not None
        self.is_wireless_relay = ip is not None

        if self.is_gpio_relay:
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(self.pin, GPIO.OUT)

    def get_device(self) -> str:
        """
        Returns the name of the device.

        Returns:
            str: The name of the device.
        """
        return self.device

    def turn_on(self):
        """Turn on the relay."""
        if self.is_gpio_relay:
            GPIO.output(self.pin, GPIO.HIGH)
        elif self.is_wireless_relay:
            url = f"http://{self.ip}/relay/on"
            self._send_request(url)

    def turn_off(self):
        """Turn off the relay."""
        if self.is_gpio_relay:
            GPIO.output(self.pin, GPIO.LOW)
        elif self.is_wireless_relay:
            url = f"http://{self.ip}/relay/off"
            self._send_request(url)

    def _send_request(self, url):
        """Send HTTP request to ESP8266 ESP-01."""
        try:
            response = requests.get(url)
            if response.status_code != 200:
                print(f"Error controlling relay: HTTP {response.status_code}")
        except requests.RequestException as e:
            print(f"Error controlling relay: {e}")

    def cleanup(self):
        """Cleanup GPIO resources."""
        if self.is_gpio_relay:
            GPIO.cleanup(self.pin)

