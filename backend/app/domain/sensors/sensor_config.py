"""
Sensor Configuration Value Object
==================================
Immutable configuration for sensors.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class SensorConfig:
    """
    Immutable sensor configuration.
    Protocol-specific settings are stored in extra_config.
    """

    # Reading semantics
    unit: str = ""
    min_value: float | None = None
    max_value: float | None = None
    precision: int = 2
    read_interval: int = 60  # seconds

    # Dashboard selection
    # If set, these metrics are treated as the sensor's *primary* readings.
    # Other readings (still emitted in DeviceSensorReadingPayload) are considered secondary.
    primary_metrics: list[str] | None = None

    # GPIO/I2C specific
    gpio_pin: int | None = None
    i2c_bus: int | None = None
    i2c_address: str | None = None
    adc_channel: int | None = None

    # Wireless specific
    ip_address: str | None = None
    mqtt_topic: str | None = None
    zigbee_ieee: str | None = None  # Zigbee IEEE address
    zigbee_friendly_name: str | None = None  # Zigbee2MQTT friendly name
    modbus_address: int | None = None
    modbus_slave_id: int | None = None

    # ESP32-C6 specific
    esp32_device_id: int | None = None

    # Polling/update settings (legacy name; prefer read_interval)
    poll_interval: int = 60  # seconds
    timeout: int = 5  # seconds

    # Thresholds
    min_threshold: float | None = None
    max_threshold: float | None = None

    # Extra protocol-specific config
    extra_config: dict[str, Any] = field(default_factory=dict)

    def get_mqtt_topic(self) -> str | None:
        """Get MQTT topic for the sensor"""
        return self.mqtt_topic

    def get_zigbee_identifier(self) -> str | None:
        """Get Zigbee identifier (IEEE or friendly name)"""
        return self.zigbee_ieee or self.zigbee_friendly_name

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary"""
        return {
            "unit": self.unit,
            "min_value": self.min_value,
            "max_value": self.max_value,
            "precision": self.precision,
            "read_interval": self.read_interval,
            "primary_metrics": self.primary_metrics,
            "gpio_pin": self.gpio_pin,
            "i2c_bus": self.i2c_bus,
            "i2c_address": self.i2c_address,
            "adc_channel": self.adc_channel,
            "ip_address": self.ip_address,
            "mqtt_topic": self.mqtt_topic,
            "zigbee_ieee": self.zigbee_ieee,
            "zigbee_friendly_name": self.zigbee_friendly_name,
            "modbus_address": self.modbus_address,
            "modbus_slave_id": self.modbus_slave_id,
            "esp32_device_id": self.esp32_device_id,
            "poll_interval": self.poll_interval,
            "timeout": self.timeout,
            "min_threshold": self.min_threshold,
            "max_threshold": self.max_threshold,
            "extra_config": self.extra_config,
        }
