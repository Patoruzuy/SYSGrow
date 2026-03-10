"""
Base class for all hardware sensor drivers.
Provides a standard interface and mock data support.
"""

import logging
from typing import Any

from app.utils.time import iso_now

logger = logging.getLogger(__name__)


class BaseSensorDriver:
    """
    Abstract base class for sensor drivers.
    All drivers should inherit from this and implement the read() method.
    """

    def __init__(self, unit_id: str = "1"):
        self.unit_id = unit_id
        self.mock_data: dict[str, Any] = {}

    def read(self) -> dict[str, Any]:
        """
        Read data from the sensor. Should be implemented by subclasses.
        Returns:
            dict: Sensor reading with timestamp.
        """
        raise NotImplementedError("read() must be implemented by subclasses.")

    def cleanup(self) -> None:
        """
        Optional cleanup for hardware resources.
        """
        pass

    def _return_mock(self) -> dict[str, Any]:
        data = self.mock_data.copy()
        data["timestamp"] = iso_now()
        data["status"] = data.get("status", "MOCK")
        return data
