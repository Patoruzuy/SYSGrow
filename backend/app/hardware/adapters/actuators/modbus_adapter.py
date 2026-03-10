"""
Modbus Actuator Adapter

Adapter for Modbus TCP actuators.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class ModbusActuatorAdapter:
    """
    Modbus TCP protocol adapter for actuators.

    Note: Requires pymodbus library.
    """

    def __init__(self, device_name: str, ip_address: str, metadata: dict[str, Any]):
        """
        Initialize Modbus adapter.

        Args:
            device_name: Name of actuator
            ip_address: Modbus device IP
            metadata: Modbus-specific config (unit_id, register, etc.)
        """
        self.device_name = device_name
        self.ip_address = ip_address
        self.port = metadata.get("port", 502)
        self.unit_id = metadata.get("unit_id", 1)
        self.coil_address = metadata.get("coil_address", 0)

        # Lazy import
        try:
            from pymodbus.client import ModbusTcpClient

            self.client = ModbusTcpClient(self.ip_address, port=self.port)
        except ImportError:
            logger.warning("pymodbus not installed, Modbus support disabled")
            self.client = None

    def turn_on(self):
        """Turn actuator ON via Modbus"""
        if not self.client:
            raise RuntimeError("Modbus client not available")

        self.client.connect()
        self.client.write_coil(self.coil_address, True, unit=self.unit_id)
        self.client.close()
        logger.info("Modbus: Turned ON %s at %s", self.device_name, self.ip_address)

    def turn_off(self):
        """Turn actuator OFF via Modbus"""
        if not self.client:
            raise RuntimeError("Modbus client not available")

        self.client.connect()
        self.client.write_coil(self.coil_address, False, unit=self.unit_id)
        self.client.close()
        logger.info("Modbus: Turned OFF %s at %s", self.device_name, self.ip_address)

    def get_device(self) -> str:
        """Get device identifier"""
        return f"modbus://{self.ip_address}:{self.port}/{self.unit_id}"
