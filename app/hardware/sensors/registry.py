"""
Sensor Registry

Registry pattern for managing sensor adapters based on protocol.

Features:
- Maps protocols to adapter classes (not sensor types)
- Associates processor pipelines with sensor categories
- Provides default configurations and capabilities
"""

import logging

from app.hardware.adapters.sensors.base_adapter import ISensorAdapter
from app.hardware.sensors.processors.base_processor import IDataProcessor

logger = logging.getLogger("sensor_registry")


class SensorRegistry:
    """
    Registry for sensor configurations.

    Maps protocols to their adapter class.
    Sensor type (ENVIRONMENTAL, PLANT) determines metrics, not adapter.
    """

    def __init__(self):
        """Initialize sensor registry"""
        self._adapters_by_protocol: dict[str, type[ISensorAdapter]] = {}
        self._processors: dict[str, list[type[IDataProcessor]]] = {}
        self._default_configs: dict[str, dict] = {}
        self._capabilities: dict[str, list[str]] = {}

        logger.info("Sensor registry initialized")

    def register_protocol_adapter(
        self, protocol: str, adapter_class: type[ISensorAdapter], capabilities: list[str] | None = None
    ):
        """
        Register an adapter for a protocol.

        Args:
            protocol: Protocol identifier (e.g., 'zigbee2mqtt', 'GPIO')
            adapter_class: Adapter class for this protocol
            capabilities: List of capability names
        """
        self._adapters_by_protocol[protocol] = adapter_class

        if capabilities:
            self._capabilities[protocol] = capabilities

        logger.info(f"Registered protocol '{protocol}' with adapter {adapter_class.__name__}")

    def register_sensor_type(
        self,
        sensor_type: str,
        adapter_class: type[ISensorAdapter],
        processors: list[type[IDataProcessor]] | None = None,
        default_config: dict | None = None,
        capabilities: list[str] | None = None,
    ):
        """
        Legacy method - registers by sensor type.
        Kept for backward compatibility during migration.

        Args:
            sensor_type: Sensor type identifier
            adapter_class: Adapter class for this sensor type
            processors: List of processor classes to apply
            default_config: Default configuration dict
            capabilities: List of capability names
        """
        # Register processors by sensor type (still useful)
        if processors:
            self._processors[sensor_type] = processors

        # Register default config
        if default_config:
            self._default_configs[sensor_type] = default_config

        logger.debug(f"Legacy registration for sensor type '{sensor_type}'")

    def get_adapter_class_by_protocol(self, protocol: str) -> type[ISensorAdapter] | None:
        """
        Get adapter class for protocol.

        Args:
            protocol: Protocol string (e.g., 'zigbee2mqtt', 'GPIO')

        Returns:
            Adapter class or None
        """
        return self._adapters_by_protocol.get(protocol)

    def get_adapter_class(self, sensor_type: str) -> type[ISensorAdapter] | None:
        """
        Legacy method - get adapter by sensor type.
        Returns None - use get_adapter_class_by_protocol instead.
        """
        logger.warning(
            f"get_adapter_class(sensor_type='{sensor_type}') called - "
            f"use get_adapter_class_by_protocol(protocol) instead"
        )
        return None

    def get_processor_classes(self, sensor_type: str) -> list[type[IDataProcessor]]:
        """
        Get processor classes for sensor type.

        Args:
            sensor_type: Sensor type

        Returns:
            List of processor classes
        """
        return self._processors.get(sensor_type, [])

    def get_default_config(self, sensor_type: str) -> dict:
        """
        Get default configuration for sensor type.

        Args:
            sensor_type: Sensor type

        Returns:
            Default config dict
        """
        return self._default_configs.get(sensor_type, {}).copy()

    def get_capabilities(self, sensor_type: str) -> list[str]:
        """
        Get capabilities for sensor type.

        Args:
            sensor_type: Sensor type

        Returns:
            List of capability names
        """
        return self._capabilities.get(sensor_type, [])

    def is_registered(self, sensor_type: str) -> bool:
        """
        Check if sensor type has processors registered.

        Note: Protocol-based registration is now preferred.
        Use is_protocol_registered() for adapter checks.

        Args:
            sensor_type: Sensor type

        Returns:
            True if processors registered for this type
        """
        return sensor_type in self._processors

    def is_protocol_registered(self, protocol: str) -> bool:
        """
        Check if protocol has adapter registered.

        Args:
            protocol: Protocol string (e.g., 'zigbee2mqtt', 'GPIO')

        Returns:
            True if adapter registered for this protocol
        """
        return protocol in self._adapters_by_protocol

    def get_registered_types(self) -> list[str]:
        """
        Get all registered sensor types (with processors).

        Returns:
            List of sensor type strings
        """
        return list(self._processors.keys())

    def get_registered_protocols(self) -> list[str]:
        """
        Get all registered protocols.

        Returns:
            List of protocol strings
        """
        return list(self._adapters_by_protocol.keys())

    def unregister_sensor_type(self, sensor_type: str):
        """
        Unregister a sensor type.

        Args:
            sensor_type: Sensor type to unregister
        """
        if sensor_type in self._processors:
            del self._processors[sensor_type]
        if sensor_type in self._default_configs:
            del self._default_configs[sensor_type]
        if sensor_type in self._capabilities:
            del self._capabilities[sensor_type]

        logger.info(f"Unregistered sensor type '{sensor_type}'")

    def unregister_protocol(self, protocol: str):
        """
        Unregister a protocol adapter.

        Args:
            protocol: Protocol to unregister
        """
        if protocol in self._adapters_by_protocol:
            del self._adapters_by_protocol[protocol]
            logger.info(f"Unregistered protocol '{protocol}'")

    def auto_register_protocol_adapters(self, adapter_mapping: dict[str, type[ISensorAdapter]]):
        """
        Auto-register multiple protocol adapters.

        Args:
            adapter_mapping: Dict of protocol -> adapter_class
        """
        for protocol, adapter_class in adapter_mapping.items():
            if not self.is_protocol_registered(protocol):
                self.register_protocol_adapter(protocol, adapter_class)

        logger.info(f"Auto-registered {len(adapter_mapping)} protocol adapters")


# Global registry instance
_global_registry: SensorRegistry | None = None


def get_global_registry() -> SensorRegistry:
    """
    Get global sensor registry instance (singleton).

    Returns:
        SensorRegistry
    """
    global _global_registry
    if _global_registry is None:
        _global_registry = SensorRegistry()
        _initialize_default_registry(_global_registry)
    return _global_registry


def _initialize_default_registry(registry: SensorRegistry):
    """
    Initialize default protocol-to-adapter registrations.

    Args:
        registry: Registry to initialize
    """
    from app.domain.sensors import Protocol
    from app.hardware.adapters.sensors import (
        GPIOAdapter,
        ModbusAdapter,
        SYSGrowAdapter,
        WiFiAdapter,
        Zigbee2MQTTAdapter,
        ZigbeeAdapter,
    )
    from app.hardware.sensors.processors import (
        CalibrationProcessor,
        EnrichmentProcessor,
        TransformationProcessor,
        ValidationProcessor,
    )

    # Default processor pipeline for all sensors
    default_processors = [ValidationProcessor, TransformationProcessor, CalibrationProcessor, EnrichmentProcessor]

    # Register adapters by protocol
    registry.register_protocol_adapter(Protocol.GPIO.value, GPIOAdapter, capabilities=["wired", "direct_gpio"])

    registry.register_protocol_adapter(
        Protocol.I2C.value,
        GPIOAdapter,  # GPIO adapter handles I2C too
        capabilities=["wired", "i2c"],
    )

    registry.register_protocol_adapter(
        Protocol.ADC.value,
        GPIOAdapter,  # GPIO adapter handles ADC too
        capabilities=["wired", "analog"],
    )

    registry.register_protocol_adapter(
        Protocol.MQTT.value, SYSGrowAdapter, capabilities=["wifi", "mqtt", "bidirectional", "ota_update"]
    )

    registry.register_protocol_adapter(
        Protocol.WIRELESS.value, SYSGrowAdapter, capabilities=["wifi", "mqtt", "bidirectional", "ota_update"]
    )

    registry.register_protocol_adapter(
        Protocol.HTTP.value, WiFiAdapter, capabilities=["wifi", "http", "direct_connection"]
    )

    registry.register_protocol_adapter(
        Protocol.ZIGBEE.value, ZigbeeAdapter, capabilities=["battery_powered", "low_power", "mesh"]
    )

    registry.register_protocol_adapter(
        Protocol.ZIGBEE2MQTT.value,
        Zigbee2MQTTAdapter,
        capabilities=["plug_and_play", "battery_powered", "auto_discovery"],
    )

    registry.register_protocol_adapter(
        Protocol.MODBUS.value, ModbusAdapter, capabilities=["industrial", "wired", "high_accuracy"]
    )

    # Register processors for sensor categories using SensorType enum
    from app.domain.sensors import SensorType

    for sensor_type in SensorType:
        registry._processors[sensor_type.value] = default_processors

    logger.info("Protocol-based sensor adapters registered")
