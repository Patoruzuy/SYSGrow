# ESP32-C6-Sensors: Data Formats and Features

This document details the data formats published by the ESP32-C6-Sensors firmware, including MQTT, BLE, and local JSON structures, as well as a summary of all key features.

---

## 1. MQTT Data Formats

### 1.1 Device Registration Payload
- **Topic:** `unit/<unit_id>/register_device`
- **Format:**
```json
{
  "device_id": "<device_id>",
  "device_type": "<DEVICE_TYPE>",
  "firmware_version": "<FW_VERSION>",
  "unit_id": "<unit_id>",
  "capabilities": [
    "temperature",
    "humidity",
    "soil_moisture",
    "co2",
    "light_level"
  ],
  "battery_voltage": <float>,
  "rssi": <int>,
  "uptime": <seconds>
}
```

### 1.2 CO Sensor Payload
- **Topic:** `homeassistant/sensor/esp32c6_co/state`
- **Format:**
```json
{
  "co_level": <float>
}
```
- **Notes:**
  - If using ZE07-CO: `co_level` is in ppm.
  - If using MQ7: `co_level` is a voltage value.

---

## 2. BLE Data Format

### 2.1 BLE Service and Characteristic
- **Service UUID:** `12345678-1234-5678-1234-56789abcdef0`
- **Characteristic UUID:** `12345678-1234-5678-1234-56789abcdef1`
- **Format:**
  - String, e.g.:
    ```
    Temp: <temperature>C, Hum: <humidity>%
    ```
  - Example: `Temp: 23.45C, Hum: 56.78%`
- **Properties:**
  - Read
  - Notify (periodic updates)

---

## 3. Local JSON Structure (getSensorData)

- **Format:**
```json
{
  "timestamp": <millis>,
  "device_id": "<device_id>",
  "unit_id": "<unit_id>",
  "sensors": {
    "temperature": <float|null>,
    "humidity": <float>,
    "soil_moisture": <float>,
    "light_level": <float>
  },
  "metadata": {
    "battery_voltage": <float>,
    "rssi": <int>,
    "error_count": <int>,
    "sensors_healthy": <bool>
  }
}
```

---

## 4. Features Overview

### 4.1 Sensor Support
- Reads and filters:
  - Temperature (analog, e.g., TMP36)
  - Humidity (analog)
  - Soil moisture (analog)
  - Light level (analog/photoresistor)
  - CO (ZE07-CO via UART or MQ7 via analog)

### 4.2 Data Publishing
- **MQTT:**
  - Device registration and sensor data
  - CO sensor data (ppm or voltage)
- **BLE:**
  - GATT service for sensor data (temperature, humidity)
  - Supports read and notify
- **Web Server:**
  - Local configuration and status (see web_server.cpp)

### 4.3 Power Management
- Deep sleep and battery conservation
- Automatic recovery if battery voltage improves

### 4.4 OTA Updates
- Firmware update support via WiFi

### 4.5 Provisioning
- BLE provisioning mode for initial setup
- EEPROM storage for WiFi and MQTT credentials

### 4.6 Error Handling & Health
- Moving average filters for sensor stability
- Error count and health status in metadata
- Logging for all major events

---

## 5. References
- [ESP32-C6 Technical Reference](https://www.espressif.com/en/products/socs/esp32-c6)
- [ArduinoJson](https://arduinojson.org/)
- [PubSubClient](https://pubsubclient.knolleary.net/)
- [ESP32 BLE Arduino](https://github.com/nkolban/ESP32_BLE_Arduino)

---

For further details, see the source files in `ESP32-C6-Sensors/src/` and the main documentation in `docs/firmware_modules.md`.
