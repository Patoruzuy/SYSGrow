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
from .base_adapter import ISensorAdapter, AdapterError
from .gpio_adapter import GPIOAdapter
from .zigbee_adapter import ZigbeeAdapter
from .zigbee2mqtt_adapter import Zigbee2MQTTAdapter
from .modbus_adapter import ModbusAdapter
from .sysgrow_adapter import SYSGrowAdapter
from .wifi_adapter import WiFiAdapter

__all__ = [
    'ISensorAdapter',
    'AdapterError',
    'GPIOAdapter',
    'ZigbeeAdapter',
    'Zigbee2MQTTAdapter',
    'ModbusAdapter',
    'SYSGrowAdapter',
    'WiFiAdapter',
]
