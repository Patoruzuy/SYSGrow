"""
Internal hardware driver for MQ2 gas sensor (digital and analog modes).
This module should only be used by sensor adapters, not directly by application code.
"""

import logging
from typing import Any

from app.utils.time import iso_now

from .base import BaseSensorDriver

logger = logging.getLogger(__name__)

try:
    import adafruit_ads1x15.ads1115 as ADS
    import board
    import busio
    import RPi.GPIO as GPIO
    from adafruit_ads1x15.analog_in import AnalogIn

    IS_PI = True
except (ImportError, NotImplementedError):
    logger.warning("Raspberry Pi-specific libraries not available. Using mock MQ2 sensor.")
    IS_PI = False


class MQ2Sensor(BaseSensorDriver):
    """
    Hardware driver for MQ2 gas sensor supporting both digital and analog modes.
    Inherits from BaseSensorDriver for a unified interface.
    """

    def __init__(self, sensor_pin: int = 17, is_digital: bool = True, channel: int = 0, unit_id: str = "1"):
        """
        Initialize the MQ2 gas sensor hardware.

        Args:
            sensor_pin (int): GPIO pin number for digital mode.
            is_digital (bool): True for digital GPIO read, False for analog via ADC.
            channel (int): ADS1115 channel for analog mode (0-3).
            unit_id (str): Unit identifier for reference.
        """
        super().__init__(unit_id)
        self.sensor_pin = sensor_pin
        self.is_digital = is_digital
        self.channel = channel
        self.adc = None

        if IS_PI:
            if is_digital:
                GPIO.setmode(GPIO.BCM)
                GPIO.setwarnings(False)
                GPIO.setup(sensor_pin, GPIO.IN)
                logger.info("MQ2 sensor initialized in digital mode on GPIO %s", sensor_pin)
            else:
                try:
                    i2c = busio.I2C(board.SCL, board.SDA)
                    self.adc = ADS.ADS1115(i2c)
                    self.analog_in = AnalogIn(self.adc, getattr(ADS, f"P{channel}"))
                    logger.info("MQ2 sensor initialized in analog mode on ADS1115 channel %s", channel)
                except Exception as e:
                    logger.error("ADC init failed for MQ2 sensor on channel %s: %s", channel, e)
        else:
            self.mock_data = {
                "smoke": 1 if is_digital else 16384,
                "mode": "digital" if is_digital else "analog",
                "status": "MOCK",
            }

    def read(self) -> dict[str, Any]:
        """
        Read raw data from the MQ2 sensor.

        Returns:
            dict: Sensor reading with smoke value, mode, timestamp, and status.
        """
        if IS_PI:
            try:
                if self.is_digital:
                    value = GPIO.input(self.sensor_pin)
                    return {"smoke": value, "mode": "digital", "timestamp": iso_now(), "status": "OK"}
                else:
                    if self.adc and hasattr(self, "analog_in"):
                        value = self.analog_in.value
                        return {"smoke": value, "mode": "analog", "timestamp": iso_now(), "status": "OK"}
            except Exception as e:
                logger.error("MQ2 read error: %s", e)
                return {"error": str(e), "timestamp": iso_now(), "status": "ERROR"}
        return self._return_mock()

    def cleanup(self) -> None:
        """
        Clean up GPIO state if digital mode is active.
        """
        if IS_PI and self.is_digital:
            GPIO.cleanup()
            logger.info("MQ2 GPIO cleanup complete.")
