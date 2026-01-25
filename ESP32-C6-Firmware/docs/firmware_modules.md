# ESP32-C6 Firmware Modules Overview

This document describes the main firmware modules implemented for the SYSGrow ESP32-C6 family. Each module is responsible for a specific hardware or service function, providing a clear interface for integration and extension. This documentation is intended for developers working on firmware or integrating new features.

---

## General Notes
- All modules are written in C++ and follow PlatformIO project structure.
- Each module is organized by function (e.g., sensors, relays, BLE, MQTT, OTA, power management).
- Header files are in `include/`, implementation in `src/`.
- Code is structured for clarity, maintainability, and hardware abstraction.

---

## ESP32-C6-Relays

### Purpose
Controls relay outputs for actuating devices (e.g., pumps, lights, fans).

### Key Files
- `main.cpp`: Main application logic and setup.
- `include/config.h`: Pin definitions and configuration.
- `src/services/relay_service.cpp`: Relay control logic.
- `src/services/power_management.cpp`: Power-saving features.

### Main Features
- GPIO-based relay switching (active high/low configurable)
- Support for multiple relays (expandable)
- MQTT and BLE control integration
- Power management for energy efficiency
- OTA update support

### Example Usage
```cpp
#include "relay_service.h"
relay_on(1); // Turn on relay 1
relay_off(2); // Turn off relay 2
```

---

## ESP32-C6-Sensors

### Purpose
Reads environmental and air quality sensors, exposes data via MQTT, BLE, and web server.

### Key Files
- `main.cpp`: Main application logic and setup.
- `include/sensor_air.h`, `src/sensor_air.cpp`: Air quality sensor logic (e.g., CO₂, TVOC)
- `include/sensor_co.h`, `src/sensor_co.cpp`: CO sensor logic
- `src/oled_display.cpp`: OLED display output
- `src/services/mqtt_service.cpp`: MQTT publishing
- `src/services/ble_service.cpp`: BLE GATT server

### Main Features
- Reads from multiple sensors (CO₂, CO, temperature, humidity, etc.)
- Publishes sensor data to MQTT topics
- BLE GATT characteristics for sensor data
- OLED display for local feedback
- OTA update and power management

### Example Usage
```cpp
#include "sensor_air.h"
float co2 = read_co2();
float temp = read_temperature();
```

---

## ESP32-C3-Analog-Sensors

### Purpose
Reads analog sensors (e.g., soil moisture, light, gas) and exposes data via MQTT and BLE.

### Key Files
- `main.cpp`: Main application logic and setup.
- `include/analog_sensors.h`, `src/analog_sensors.cpp`: Analog sensor reading and calibration
- `src/services/mqtt_service.cpp`: MQTT publishing
- `src/services/ble_service.cpp`: BLE GATT server

### Main Features
- Reads from multiple analog channels (ADC)
- Calibration and scaling for each sensor
- MQTT and BLE integration
- OTA update and power management

### Example Usage
```cpp
#include "analog_sensors.h"
int moisture = read_soil_moisture();
int light = read_light_level();
```

---

## Common Services (All Modules)

### BLE Service
- File: `include/ble_service.h`, `src/services/ble_service.cpp`
- Provides BLE GATT server for device configuration and sensor data
- Supports notifications and custom characteristics

### MQTT Service
- File: `include/mqtt_service.h`, `src/services/mqtt_service.cpp`
- Publishes sensor data and receives control commands
- Configurable topics and QoS

### OTA Service
- File: `include/ota_service.h`, `src/services/ota_service.cpp`
- Supports over-the-air firmware updates
- Secure update process

### Power Management
- File: `include/power_management.h`, `src/services/power_management.cpp`
- Deep sleep and low-power modes
- Wakeup sources configurable

### Web Server
- File: `include/web_server.h`, `src/services/web_server.cpp`
- Simple HTTP server for configuration and status
- Serves static and dynamic content

---

## Usage Example

Typical main loop structure:
```cpp
void loop() {
    read_sensors();
    publish_mqtt();
    update_ble();
    handle_web_requests();
    manage_power();
}
```

---

## References
- [ESP32-C6 Technical Reference](https://www.espressif.com/en/products/socs/esp32-c6)
- [PlatformIO ESP32 Documentation](https://docs.platformio.org/en/latest/boards/espressif32/esp32-c6-devkitc-1.html)
- [Adafruit Sensor Guides](https://learn.adafruit.com/)

---

For more details, see the source files in each module's `include/` and `src/` directories.
