"""
Internal hardware driver for DHT11 temperature and humidity sensor.
This module should only be used by sensor adapters, not directly by application code.
"""

import logging
import threading
import time
from typing import Any

from app.utils.time import iso_now

from .base import BaseSensorDriver

logger = logging.getLogger(__name__)

try:
    import adafruit_dht
    import board

    IS_PI = True
except (ImportError, NotImplementedError):
    logger.warning("Raspberry Pi-specific libraries not available. Using mock DHT11 sensor.")
    IS_PI = False


class DHT11Sensor(BaseSensorDriver):
    """
    Hardware driver for DHT11 temperature and humidity sensor via GPIO.
    Inherits from BaseSensorDriver for a unified interface.
    Provides raw sensor readings with retry logic and thread-safe GPIO access.
    """

    def __init__(self, pin: int, unit_id: str = "1"):
        """
        Initialize the DHT11 sensor hardware.

        Args:
            pin (int): GPIO pin number (e.g., 4 for D4).
            unit_id (str): Unit identifier for reference.
        """
        super().__init__(unit_id)
        self.pin = pin
        self.sensor = None
        self.lock = threading.Lock()

        if IS_PI:
            try:
                gpio_pin = getattr(board, f"D{pin}", None)
                if gpio_pin is None:
                    raise ValueError(f"Invalid GPIO pin: D{pin}")
                self.sensor = adafruit_dht.DHT11(gpio_pin)
                logger.info("DHT11 sensor initialized on pin D%s", pin)
            except Exception as e:
                logger.error("Failed to initialize DHT11 on D%s: %s", pin, e)
        else:
            self.mock_data = {"temperature": 23.4, "humidity": 48.6, "status": "MOCK"}

    def read(self, retries: int = 3, delay: int = 2) -> dict[str, Any]:
        """
        Read raw data from the sensor with retry logic.

        Args:
            retries (int): Number of retry attempts.
            delay (int): Delay between retries in seconds.

        Returns:
            dict: Sensor reading with timestamp and status.
        """
        with self.lock:
            temp = None
            hum = None
            for attempt in range(retries):
                try:
                    if IS_PI and self.sensor:
                        temp = self.sensor.temperature
                        hum = self.sensor.humidity
                        if temp is not None and hum is not None:
                            return {"temperature": temp, "humidity": hum, "timestamp": iso_now(), "status": "OK"}
                    else:
                        break
                except RuntimeError as e:
                    logger.warning("DHT11 read retry %s failed: %s", attempt + 1, e)
                except Exception as e:
                    logger.error("Unexpected DHT11 read error: %s", e)
                time.sleep(delay)
        return self._return_mock()

    def cleanup(self) -> None:
        """
        Clean up GPIO state.
        """
        if IS_PI and self.sensor:
            self.sensor.exit()
            logger.info("DHT11 sensor cleanup complete.")
