"""
Actuator Factory

Factory for creating actuator instances based on protocol.
"""

from __future__ import annotations

import logging
from typing import Any

from app.domain.actuators import ActuatorConfig, ActuatorEntity, Protocol
from app.hardware.actuators.relays.gpio_relay import GPIORelay
from app.hardware.actuators.relays.wifi_relay import WiFiRelay
from app.utils.event_bus import EventBus

logger = logging.getLogger(__name__)


class ActuatorFactory:
    """
    Factory for creating actuators with different protocols.

    Supported protocols:
    - GPIO: Direct GPIO control (Raspberry Pi)
    - MQTT: MQTT-based actuators
    - WiFi: HTTP-based WiFi actuators
    - Zigbee: Zigbee2MQTT actuators

    Usage:
        factory = ActuatorFactory(mqtt_client)
        actuator = factory.create_actuator(1, config)
    """

    def __init__(self, mqtt_client: Any = None, event_bus: EventBus | None = None):
        """
        Initialize factory.

        Args:
            mqtt_client: MQTT client for MQTT actuators
            event_bus: Event bus for pub/sub
        """
        self.mqtt_client = mqtt_client
        self.event_bus = event_bus or EventBus()

    def create_actuator(self, actuator_id: int, config: ActuatorConfig) -> ActuatorEntity:
        """
        Create actuator based on protocol.

        Args:
            actuator_id: Unique actuator ID
            config: Actuator configuration

        Returns:
            ActuatorEntity instance

        Raises:
            ValueError: If protocol not supported
        """
        protocol = config.protocol

        try:
            if protocol == Protocol.GPIO:
                adapter = self._create_gpio_adapter(config)
            elif protocol == Protocol.MQTT:
                adapter = self._create_mqtt_adapter(config)
            elif protocol == Protocol.WIFI or protocol == Protocol.HTTP:
                adapter = self._create_wifi_adapter(config)
            elif protocol == Protocol.ZIGBEE or protocol == Protocol.ZIGBEE2MQTT:
                adapter = self._create_zigbee_adapter(config)
            elif protocol == Protocol.MODBUS:
                adapter = self._create_modbus_adapter(config)
            else:
                raise ValueError(f"Unsupported protocol: {protocol}")

            # Create entity
            actuator = ActuatorEntity(actuator_id=actuator_id, config=config, adapter=adapter)

            logger.info("Created %s actuator: %s", protocol.value, config.name)
            return actuator

        except Exception as e:
            logger.error("Failed to create actuator %s: %s", actuator_id, e)
            raise

    def _create_gpio_adapter(self, config: ActuatorConfig) -> GPIORelay:
        """
        Create GPIO adapter.

        Args:
            config: Actuator configuration

        Returns:
            GPIORelay instance
        """
        if not config.gpio_pin:
            raise ValueError("GPIO pin required for GPIO protocol")

        # The legacy GPIORelay adapter does not support invert logic directly.
        return GPIORelay(
            device=config.name,
            pin=config.gpio_pin,
        )

    def _create_mqtt_adapter(self, config: ActuatorConfig):
        """
        Create MQTT adapter.

        Args:
            config: Actuator configuration

        Returns:
            MQTT adapter instance
        """
        if not config.mqtt_topic:
            raise ValueError("MQTT topic required for MQTT protocol")

        if not self.mqtt_client:
            raise ValueError("MQTT client not available")

        # Create MQTT adapter
        from app.hardware.adapters.actuators.mqtt_adapter import MQTTActuatorAdapter

        return MQTTActuatorAdapter(
            device_name=config.name, mqtt_client=self.mqtt_client, topic=config.mqtt_topic, event_bus=self.event_bus
        )

    def _create_wifi_adapter(self, config: ActuatorConfig) -> WiFiRelay:
        """
        Create WiFi/HTTP adapter.

        Args:
            config: Actuator configuration

        Returns:
            WiFiRelay instance
        """
        if not config.ip_address:
            raise ValueError("IP address required for WiFi protocol")

        return WiFiRelay(
            device=config.name,
            ip=config.ip_address,
        )

    def _create_zigbee_adapter(self, config: ActuatorConfig):
        """
        Create Zigbee adapter.

        Args:
            config: Actuator configuration

        Returns:
            Zigbee adapter instance
        """
        if not config.zigbee_id:
            raise ValueError("Zigbee ID required for Zigbee protocol")

        if not self.mqtt_client:
            raise ValueError("MQTT client required for Zigbee2MQTT")

        # Zigbee2MQTT uses MQTT with specific topic format
        zigbee_topic = f"zigbee2mqtt/{config.zigbee_id}/set"

        from app.hardware.adapters.actuators.zigbee_adapter import ZigbeeActuatorAdapter

        return ZigbeeActuatorAdapter(
            device_name=config.name,
            mqtt_client=self.mqtt_client,
            zigbee_id=config.zigbee_id,
            topic=zigbee_topic,
            event_bus=self.event_bus,
        )

    def _create_modbus_adapter(self, config: ActuatorConfig):
        """
        Create Modbus adapter.

        Args:
            config: Actuator configuration

        Returns:
            Modbus adapter instance
        """
        if not config.ip_address:
            raise ValueError("IP address required for Modbus protocol")

        from app.hardware.adapters.actuators.modbus_adapter import ModbusActuatorAdapter

        return ModbusActuatorAdapter(device_name=config.name, ip_address=config.ip_address, metadata=config.metadata)
