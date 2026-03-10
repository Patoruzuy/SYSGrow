"""
Sensor Adapters
===============
Hardware abstraction layer for different communication protocols.

Adapter Types:
    - GPIOAdapter: Direct GPIO pin sensors (DHT22, soil moisture, etc.)
    - SYSGrowAdapter: SYSGrow ESP32-C6 devices via MQTT (Zigbee2MQTT-style)
    - Zigbee2MQTTAdapter: Commercial Zigbee sensors via Zigbee2MQTT
    - ZigbeeAdapter: Direct Zigbee protocol
    - ModbusAdapter: Industrial Modbus sensors
    - WiFiAdapter: Direct WiFi HTTP communication with ESP32 devices
"""

from .base_adapter import AdapterError, ISensorAdapter
from .gpio_adapter import GPIOAdapter
from .modbus_adapter import ModbusAdapter
from .sysgrow_adapter import SYSGrowAdapter
from .wifi_adapter import WiFiAdapter
from .zigbee2mqtt_adapter import Zigbee2MQTTAdapter
from .zigbee_adapter import ZigbeeAdapter

__all__ = [
    "AdapterError",
    "GPIOAdapter",
    "ISensorAdapter",
    "ModbusAdapter",
    "SYSGrowAdapter",
    "WiFiAdapter",
    "Zigbee2MQTTAdapter",
    "ZigbeeAdapter",
]
