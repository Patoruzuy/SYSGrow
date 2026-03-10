"""
Sensor Factory

Factory pattern for creating sensor entities with proper wiring.

Features:
- Auto-wires adapters based on protocol
- Auto-wires processor pipelines
- Applies default configurations
- Validates sensor configurations
"""

import logging
from typing import Any

from app.domain.sensors import Protocol, SensorConfig, SensorEntity, SensorType
from app.hardware.adapters.sensors.base_adapter import ISensorAdapter
from app.hardware.sensors.processors.base_processor import IDataProcessor
from app.hardware.sensors.registry import get_global_registry

logger = logging.getLogger("sensor_factory")


class SensorFactory:
    """
    Factory for creating SensorEntity instances.

    Features:
    - Auto-wires adapter based on protocol
    - Auto-wires processor pipeline
    - Applies default configurations
    - Validates sensor configurations
    """

    def __init__(self, registry=None, mqtt_client=None):
        """
        Initialize sensor factory.

        Args:
            registry: SensorRegistry to use (defaults to global)
            mqtt_client: MQTT client for wireless sensor adapters
        """
        self.registry = registry or get_global_registry()
        self.mqtt_client = mqtt_client

    def create_sensor(
        self,
        sensor_id: int,
        name: str,
        sensor_type: SensorType,
        protocol: Protocol,
        config: SensorConfig | None = None,
        unit_id: int = 0,
        model: str = "Unknown",
        adapter_params: dict[str, Any] | None = None,
        processor_params: dict[str, Any] | None = None,
    ) -> SensorEntity:
        """
        Create a new sensor entity.

        Args:
            sensor_id: Unique sensor ID
            name: Sensor name
            sensor_type: Type of sensor
            protocol: Communication protocol
            config: Sensor configuration (optional, uses defaults)
            unit_id: ID of the growth unit this sensor belongs to
            model: Hardware model identifier
            adapter_params: Parameters for adapter initialization
            processor_params: Parameters for processor initialization

        Returns:
            SensorEntity

        Raises:
            ValueError: If sensor type not registered or invalid config
        """
        sensor_type_str = sensor_type.value

        # Check if sensor type is registered
        if not self.registry.is_registered(sensor_type_str):
            raise ValueError(f"Sensor type '{sensor_type_str}' not registered")

        # Get or create config
        if config is None:
            default_config = self.registry.get_default_config(sensor_type_str)
            config = SensorConfig(
                unit=default_config.get("unit", ""),
                min_value=default_config.get("min_value"),
                max_value=default_config.get("max_value"),
                precision=default_config.get("precision", 2),
                read_interval=default_config.get("read_interval", 60),
            )

        # Prepare adapter params
        final_adapter_params = adapter_params.copy() if adapter_params else {}

        # Inject required parameters for specific protocols
        if protocol in (Protocol.ZIGBEE2MQTT, Protocol.ZIGBEE, Protocol.MQTT):
            # Add sensor_id if not present
            if "sensor_id" not in final_adapter_params:
                final_adapter_params["sensor_id"] = sensor_id

            # Add mqtt_client if available and not already present
            if "mqtt_client" not in final_adapter_params and self.mqtt_client:
                final_adapter_params["mqtt_client"] = self.mqtt_client

        logger.debug(
            f"Creating adapter for {sensor_type_str} with protocol {protocol.value}, params: {list(final_adapter_params.keys())}"
        )

        # Create adapter
        adapter = self._create_adapter(sensor_type_str, protocol, final_adapter_params)

        # Create processors
        processors = self._create_processors(sensor_type_str, processor_params or {})

        # Create sensor entity (use _adapter for dataclass)
        sensor = SensorEntity(
            id=sensor_id,
            unit_id=unit_id,
            name=name,
            sensor_type=sensor_type,
            model=model,
            protocol=protocol,
            config=config,
            _adapter=adapter,
            _processor=processors[0] if processors else None,
        )

        logger.info(
            "Created sensor: %s (ID: %s, Type: %s, Protocol: %s)", name, sensor_id, sensor_type_str, protocol.value
        )

        return sensor

    def _create_adapter(self, sensor_type: str, protocol: Protocol, params: dict[str, Any]) -> ISensorAdapter:
        """
        Create adapter for sensor based on protocol.

        Args:
            sensor_type: Sensor type string (for logging)
            protocol: Communication protocol - determines which adapter to use
            params: Adapter initialization parameters

        Returns:
            ISensorAdapter instance
        """
        # Get adapter by protocol (not sensor type)
        adapter_class = self.registry.get_adapter_class_by_protocol(protocol.value)

        if adapter_class is None:
            raise ValueError(f"No adapter registered for protocol '{protocol.value}'")

        # Create adapter with params
        try:
            adapter = adapter_class(**params)
            logger.debug("Created %s for protocol %s", adapter_class.__name__, protocol.value)
            return adapter
        except Exception as e:
            logger.error("Failed to create adapter: %s", e)
            raise ValueError(f"Failed to create adapter for protocol '{protocol.value}': {e}") from e

    def _create_processors(self, sensor_type: str, params: dict[str, Any]) -> list[IDataProcessor]:
        """
        Create processor pipeline for sensor.

        Args:
            sensor_type: Sensor type string
            params: Processor initialization parameters

        Returns:
            List of processor instances
        """
        processor_classes = self.registry.get_processor_classes(sensor_type)
        processors = []

        for processor_class in processor_classes:
            try:
                # Only ValidationProcessor requires sensor_type parameter
                if processor_class.__name__ == "ValidationProcessor":
                    processor = processor_class(sensor_type=sensor_type)
                else:
                    processor = processor_class()
                processors.append(processor)
            except Exception as e:
                logger.error("Failed to create processor %s: %s", processor_class.__name__, e)

        return processors

    def create_from_dict(self, sensor_dict: dict[str, Any]) -> SensorEntity:
        """
        Create sensor from dictionary configuration.

        Args:
            sensor_dict: Dict with sensor configuration

        Returns:
            SensorEntity
        """
        sensor_id = sensor_dict["id"]
        name = sensor_dict["name"]
        sensor_type = SensorType(sensor_dict["type"])
        protocol = Protocol(sensor_dict["protocol"])
        unit_id = int(sensor_dict.get("unit_id") or 0)
        model = sensor_dict.get("model", "Unknown")

        # Parse config if present
        config = None
        if "config" in sensor_dict:
            config_dict = sensor_dict["config"] or {}
            config_fields = {k: v for k, v in config_dict.items() if k in SensorConfig.__dataclass_fields__}
            config = SensorConfig(
                **config_fields,
                extra_config=dict(config_dict),
            )

        # Extract adapter and processor params
        adapter_params = sensor_dict.get("adapter_params", {})
        processor_params = sensor_dict.get("processor_params", {})

        return self.create_sensor(
            sensor_id=sensor_id,
            name=name,
            sensor_type=sensor_type,
            protocol=protocol,
            config=config,
            unit_id=unit_id,
            model=model,
            adapter_params=adapter_params,
            processor_params=processor_params,
        )

    def create_gpio_sensor(
        self, sensor_id: int, name: str, sensor_type: SensorType, gpio_pin: int, **kwargs
    ) -> SensorEntity:
        """
        Convenience method for creating GPIO sensor.

        Args:
            sensor_id: Sensor ID
            name: Sensor name
            sensor_type: Sensor type
            gpio_pin: GPIO pin number
            **kwargs: Additional config parameters

        Returns:
            SensorEntity
        """
        adapter_params = {"gpio_pin": gpio_pin}
        return self.create_sensor(sensor_id, name, sensor_type, Protocol.GPIO, adapter_params=adapter_params, **kwargs)

    def create_mqtt_sensor(
        self, sensor_id: int, name: str, sensor_type: SensorType, mqtt_topic: str, mqtt_client=None, **kwargs
    ) -> SensorEntity:
        """
        Convenience method for creating MQTT sensor.

        Args:
            sensor_id: Sensor ID
            name: Sensor name
            sensor_type: Sensor type
            mqtt_topic: MQTT topic to subscribe
            mqtt_client: MQTT client instance
            **kwargs: Additional config parameters

        Returns:
            SensorEntity
        """
        adapter_params = {"mqtt_topic": mqtt_topic, "mqtt_client": mqtt_client}
        return self.create_sensor(sensor_id, name, sensor_type, Protocol.MQTT, adapter_params=adapter_params, **kwargs)

    def create_zigbee2mqtt_sensor(
        self,
        sensor_id: int,
        name: str,
        sensor_type: SensorType,
        friendly_name: str,
        mqtt_client=None,
        ieee_address: str | None = None,
        **kwargs,
    ) -> SensorEntity:
        """
        Convenience method for creating Zigbee2MQTT sensor.

        Args:
            sensor_id: Sensor ID
            name: Sensor name
            sensor_type: Sensor type
            friendly_name: Zigbee2MQTT device friendly name
            mqtt_client: MQTT client instance
            ieee_address: Optional IEEE address of device
            **kwargs: Additional config parameters

        Returns:
            SensorEntity
        """
        adapter_params = {
            "sensor_id": sensor_id,
            "friendly_name": friendly_name,
            "mqtt_client": mqtt_client or self.mqtt_client,
        }
        if ieee_address:
            adapter_params["ieee_address"] = ieee_address

        return self.create_sensor(
            sensor_id, name, sensor_type, Protocol.ZIGBEE2MQTT, adapter_params=adapter_params, **kwargs
        )

    def create_sysgrow_sensor(
        self,
        sensor_id: int,
        name: str,
        sensor_type: SensorType,
        friendly_name: str,
        mqtt_client=None,
        unit_id: int = 0,
        **kwargs,
    ) -> SensorEntity:
        """
        Convenience method for creating SYSGrow ESP32-C6 sensor.

        Args:
            sensor_id: Sensor ID
            name: Sensor name
            sensor_type: Sensor type (ENVIRONMENTAL or PLANT)
            friendly_name: SYSGrow device friendly name (e.g., 'sysgrow-AABBCCDD')
            mqtt_client: MQTT client instance
            unit_id: Growth unit ID
            **kwargs: Additional config parameters

        Returns:
            SensorEntity
        """
        adapter_params = {
            "sensor_id": sensor_id,
            "friendly_name": friendly_name,
            "mqtt_client": mqtt_client or self.mqtt_client,
            "unit_id": unit_id,
        }
        return self.create_sensor(
            sensor_id,
            name,
            sensor_type,
            Protocol.MQTT,  # SYSGrow uses MQTT protocol
            adapter_params=adapter_params,
            unit_id=unit_id,
            **kwargs,
        )

    def create_wifi_sensor(
        self,
        sensor_id: int,
        name: str,
        sensor_type: SensorType,
        ip_address: str,
        unit_id: int = 0,
        http_port: int = 80,
        **kwargs,
    ) -> SensorEntity:
        """
        Convenience method for creating WiFi HTTP sensor.

        Args:
            sensor_id: Sensor ID
            name: Sensor name
            sensor_type: Sensor type (ENVIRONMENTAL or PLANT)
            ip_address: Device IP address or mDNS hostname
            unit_id: Growth unit ID
            http_port: HTTP server port (default: 80)
            **kwargs: Additional config parameters

        Returns:
            SensorEntity
        """
        adapter_params = {
            "sensor_id": sensor_id,
            "ip_address": ip_address,
            "unit_id": unit_id,
            "http_port": http_port,
        }
        return self.create_sensor(
            sensor_id, name, sensor_type, Protocol.HTTP, adapter_params=adapter_params, unit_id=unit_id, **kwargs
        )


# Global factory instance
_global_factory: SensorFactory | None = None


def get_global_factory() -> SensorFactory:
    """
    Get global sensor factory instance (singleton).

    Returns:
        SensorFactory
    """
    global _global_factory
    if _global_factory is None:
        _global_factory = SensorFactory()
    return _global_factory
