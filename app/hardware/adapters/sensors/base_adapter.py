"""
Base Sensor Adapter Interface
==============================
Abstract interface that all sensor adapters must implement.
"""

from abc import ABC, abstractmethod
from typing import Any


class ISensorAdapter(ABC):
    """
    Abstract interface for sensor hardware adapters.
    Each communication protocol (GPIO, MQTT, Zigbee, etc.) implements this interface.

    Required Methods (must override):
        - read(): Read raw data from sensor
        - configure(): Apply configuration
        - is_available(): Check sensor availability
        - get_protocol_name(): Get protocol identifier

    Optional Methods (override for specific protocols):
        - cleanup(): Resource cleanup
        - send_command(): Send commands to device (Zigbee, MQTT, etc.)
        - identify(): Trigger device identification
        - get_state(): Get current device state
        - get_device_info(): Get device metadata
        - rename(): Rename device on network
        - remove_from_network(): Remove from network
    """

    @abstractmethod
    def read(self) -> dict[str, Any]:
        """
        Read raw data from the sensor.

        Returns:
            Dict containing raw sensor data

        Raises:
            AdapterError: If read fails
        """
        pass

    @abstractmethod
    def configure(self, config: dict[str, Any]) -> None:
        """
        Apply configuration to the sensor.

        Args:
            config: Configuration dictionary

        Raises:
            AdapterError: If configuration fails
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """
        Check if the sensor is available/reachable.

        Returns:
            True if sensor is available
        """
        pass

    @abstractmethod
    def get_protocol_name(self) -> str:
        """
        Get the name of the communication protocol.

        Returns:
            Protocol name (e.g., 'GPIO', 'MQTT', 'Zigbee')
        """
        pass

    # ==================== Optional Methods ====================
    # Override these for protocols that support device operations

    def cleanup(self) -> None:
        """
        Cleanup resources (optional, override if needed).
        Called when sensor is removed or system shuts down.
        """
        return None

    def send_command(self, command: dict[str, Any]) -> bool:
        """
        Send command to device (optional, for addressable devices).

        Args:
            command: Command dictionary

        Returns:
            True if command sent successfully

        Note:
            Override for protocols that support commands (Zigbee, MQTT, HTTP).
            Default implementation returns False (not supported).
        """
        return False

    def identify(self, duration: int = 10) -> bool:
        """
        Trigger device identification (optional).

        Many networked devices support identification commands
        that cause LEDs to blink or other visual/audio signals.

        Args:
            duration: Identification duration in seconds

        Returns:
            True if identify command sent successfully
        """
        return False

    def get_state(self) -> dict[str, Any] | None:
        """
        Get current device state (optional).

        Returns:
            State dictionary or None if not supported
        """
        return None

    def get_device_info(self) -> dict[str, Any] | None:
        """
        Get device information and metadata (optional).

        Returns:
            Device info dictionary or None if not supported
        """
        return None

    def rename(self, new_name: str) -> bool:
        """
        Rename device on network (optional).

        Args:
            new_name: New device name

        Returns:
            True if rename command sent successfully
        """
        return False

    def remove_from_network(self) -> bool:
        """
        Remove device from network (optional).

        For network-attached devices (Zigbee, WiFi), this removes
        the device from the network. The device will need to be
        re-paired/re-provisioned to rejoin.

        Returns:
            True if remove command sent successfully
        """
        return False


class AdapterError(Exception):
    """Exception raised by sensor adapters"""

    pass
