# ESP32-C3 API Documentation

## Overview

This document describes the REST API endpoints for controlling ESP32-C3 analog sensor devices in the SysGrow system. The ESP32-C3 modules are specialized for analog sensor applications, featuring 4 soil moisture sensors and 1 lux sensor with advanced calibration and power management capabilities.

## Base URL

All ESP32-C3 endpoints are prefixed with `/api/esp32-c3`

## Authentication

All endpoints require authentication. Include appropriate authentication headers with your requests.

## Device Management

### Get All Devices

```http
GET /api/esp32-c3/devices
```

**Response:**
```json
{
  "devices": [
    {
      "device_id": "esp32c3-001",
      "unit_id": "grow-unit-1",
      "device_name": "Soil Sensors North",
      "device_type": "ESP32-C3-AnalogSensors",
      "location": "North Corner",
      "soil_sensor_count": 4,
      "lux_sensor_type": "digital",
      "status": "online",
      "last_seen": "2025-11-03T10:30:00",
      "battery_voltage": 3.8,
      "wifi_rssi": -65,
      "sensors_active": true
    }
  ],
  "count": 1
}
```

### Get Specific Device

```http
GET /api/esp32-c3/devices/{device_id}
```

**Response:**
```json
{
  "device_id": "esp32c3-001",
  "unit_id": "grow-unit-1",
  "device_name": "Soil Sensors North",
  "device_type": "ESP32-C3-AnalogSensors",
  "location": "North Corner",
  "soil_sensor_count": 4,
  "lux_sensor_type": "digital",
  "calibration_data": {
    "soil_sensors": [
      {"sensor_index": 0, "dry_value": 4095, "wet_value": 1500},
      {"sensor_index": 1, "dry_value": 4090, "wet_value": 1480}
    ],
    "lux_sensor": {"calibration_factor": 1.0}
  },
  "status": "online",
  "firmware_version": "1.0.0",
  "created_at": "2025-11-01T09:00:00",
  "updated_at": "2025-11-03T10:30:00"
}
```

### Register New Device

```http
POST /api/esp32-c3/devices
```

**Request Body:**
```json
{
  "device_id": "esp32c3-002",
  "unit_id": "grow-unit-1",
  "device_name": "Soil Sensors South",
  "location": "South Corner",
  "soil_sensor_count": 4,
  "lux_sensor_type": "digital"
}
```

**Response:** 201 Created with device data

### Update Device

```http
PUT /api/esp32-c3/devices/{device_id}
```

**Request Body:**
```json
{
  "device_name": "Updated Sensor Name",
  "location": "New Location",
  "lux_sensor_type": "analog"
}
```

### Delete Device

```http
DELETE /api/esp32-c3/devices/{device_id}
```

**Response:**
```json
{
  "message": "Device 'esp32c3-001' deleted successfully."
}
```

## Device Control

### Send Generic Command

```http
POST /api/esp32-c3/devices/{device_id}/command
```

**Request Body:**
```json
{
  "command": "read_sensors",
  "parameters": {
    "force_read": true
  }
}
```

**Response:**
```json
{
  "success": true,
  "message": "Command 'read_sensors' sent to device esp32c3-001",
  "command_data": {
    "command": "read_sensors",
    "device_id": "esp32c3-001",
    "timestamp": "2025-11-03T10:35:00",
    "parameters": {"force_read": true}
  }
}
```

### Restart Device

```http
POST /api/esp32-c3/devices/{device_id}/restart
```

**Response:**
```json
{
  "success": true,
  "message": "Command 'restart' sent to device esp32c3-001"
}
```

## Sensor Control

### Read All Sensors

```http
POST /api/esp32-c3/devices/{device_id}/sensors/read
```

Triggers an immediate reading of all sensors on the device.

### Enable Sensors

```http
POST /api/esp32-c3/devices/{device_id}/sensors/enable
```

Enables all sensors on the device.

### Disable Sensors

```http
POST /api/esp32-c3/devices/{device_id}/sensors/disable
```

Disables all sensors to save power.

## Calibration

### Generic Calibration

```http
POST /api/esp32-c3/devices/{device_id}/calibration
```

**Request Body:**
```json
{
  "sensor_type": "soil_moisture",
  "action": "start_dry",
  "sensor_index": 0
}
```

**Valid sensor_type values:**
- `soil_moisture`
- `lux`

**Valid action values:**
- `start_dry` (soil moisture only)
- `start_wet` (soil moisture only)
- `start` (lux sensor)
- `complete`
- `reset`

### Soil Moisture Calibration

#### Start Dry Calibration

```http
POST /api/esp32-c3/devices/{device_id}/calibration/soil/{sensor_index}/dry
```

Start dry calibration for soil sensor at the specified index (0-3).

#### Start Wet Calibration

```http
POST /api/esp32-c3/devices/{device_id}/calibration/soil/{sensor_index}/wet
```

Start wet calibration for soil sensor at the specified index (0-3).

### Lux Sensor Calibration

```http
POST /api/esp32-c3/devices/{device_id}/calibration/lux
```

Start lux sensor calibration.

## Power Management

### Generic Power Control

```http
POST /api/esp32-c3/devices/{device_id}/power
```

**Request Body:**
```json
{
  "command": "power_save",
  "duration_minutes": 60
}
```

**Valid command values:**
- `normal` - Normal power mode
- `power_save` - Power saving mode
- `sleep` - Deep sleep mode (requires duration_minutes)
- `wake` - Wake from sleep

### Set Normal Power Mode

```http
POST /api/esp32-c3/devices/{device_id}/power/normal
```

### Set Power Save Mode

```http
POST /api/esp32-c3/devices/{device_id}/power/save
```

### Set Sleep Mode

```http
POST /api/esp32-c3/devices/{device_id}/power/sleep
```

**Request Body:**
```json
{
  "duration_minutes": 120
}
```

Default sleep duration is 60 minutes if not specified.

## Configuration

### Update Device Configuration

```http
POST /api/esp32-c3/devices/{device_id}/config
```

**Request Body:**
```json
{
  "sensor_interval": 30000,
  "power_save": {
    "enabled": true,
    "battery_threshold": 3.2
  },
  "sensors": {
    "soil_moisture": {
      "filter_window": 10,
      "calibration_timeout": 300
    },
    "lux": {
      "integration_time": "medium",
      "gain": "auto"
    }
  }
}
```

### Get Device Configuration

```http
GET /api/esp32-c3/devices/{device_id}/config
```

**Response:**
```json
{
  "device_id": "esp32c3-001",
  "device_name": "Soil Sensors North",
  "location": "North Corner",
  "soil_sensor_count": 4,
  "lux_sensor_type": "digital",
  "calibration_data": {},
  "status": "online",
  "sensors_active": true
}
```

## Monitoring and Statistics

### Get Device Statistics

```http
GET /api/esp32-c3/devices/{device_id}/stats
```

**Response:**
```json
{
  "device_id": "esp32c3-001",
  "status": "online",
  "last_seen": "2025-11-03T10:30:00",
  "uptime": 86400,
  "firmware_version": "1.0.0",
  "battery_voltage": 3.8,
  "wifi_rssi": -65,
  "free_heap": 200000,
  "power_mode": "normal",
  "sensors_active": true,
  "created_at": "2025-11-01T09:00:00",
  "updated_at": "2025-11-03T10:30:00"
}
```

### Get All Devices Statistics

```http
GET /api/esp32-c3/devices/stats
```

**Response:**
```json
{
  "total_devices": 3,
  "online_devices": 2,
  "offline_devices": 1,
  "devices": [
    {
      "device_id": "esp32c3-001",
      "device_name": "Soil Sensors North",
      "status": "online",
      "last_seen": "2025-11-03T10:30:00",
      "battery_voltage": 3.8,
      "power_mode": "normal",
      "location": "North Corner"
    }
  ]
}
```

### Update Device Status (Heartbeat)

```http
POST /api/esp32-c3/devices/{device_id}/status
```

This endpoint is typically called by the device itself to report status.

**Request Body:**
```json
{
  "firmware_version": "1.0.0",
  "battery_voltage": 3.8,
  "wifi_rssi": -65,
  "free_heap": 200000,
  "uptime": 86400,
  "power_mode": "normal",
  "sensors_active": true
}
```

## Error Responses

All endpoints return standard HTTP status codes:

- `200` - Success
- `201` - Created (for device registration)
- `400` - Bad Request (invalid parameters)
- `404` - Not Found (device not found)
- `500` - Internal Server Error

**Error Response Format:**
```json
{
  "error": "ESP32-C3 device 'esp32c3-999' not found."
}
```

## MQTT Integration

When commands are sent via the API, they are also published to MQTT topics for real-time device communication:

- **Command Topic:** `sysgrow/device/{device_id}/command`
- **Status Topic:** `sysgrow/device/{device_id}/status`
- **Sensor Topic:** `sysgrow/unit/{unit_id}/sensors/{device_id}`
- **Alert Topic:** `sysgrow/unit/{unit_id}/alerts`

## Usage Examples

### Complete Device Setup Workflow

1. **Register Device:**
```bash
curl -X POST http://localhost:5000/api/esp32-c3/devices \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": "esp32c3-001",
    "unit_id": "grow-unit-1", 
    "device_name": "Main Soil Sensors",
    "location": "Grow Tent 1"
  }'
```

2. **Calibrate Soil Sensors:**
```bash
# Dry calibration for sensor 0
curl -X POST http://localhost:5000/api/esp32-c3/devices/esp32c3-001/calibration/soil/0/dry

# Wet calibration for sensor 0
curl -X POST http://localhost:5000/api/esp32-c3/devices/esp32c3-001/calibration/soil/0/wet
```

3. **Enable Sensors:**
```bash
curl -X POST http://localhost:5000/api/esp32-c3/devices/esp32c3-001/sensors/enable
```

4. **Read Sensor Data:**
```bash
curl -X POST http://localhost:5000/api/esp32-c3/devices/esp32c3-001/sensors/read
```

### Power Management Example

```bash
# Set power save mode
curl -X POST http://localhost:5000/api/esp32-c3/devices/esp32c3-001/power/save

# Put device to sleep for 2 hours
curl -X POST http://localhost:5000/api/esp32-c3/devices/esp32c3-001/power/sleep \
  -H "Content-Type: application/json" \
  -d '{"duration_minutes": 120}'
```

### Configuration Update Example

```bash
curl -X POST http://localhost:5000/api/esp32-c3/devices/esp32c3-001/config \
  -H "Content-Type: application/json" \
  -d '{
    "sensor_interval": 30000,
    "power_save": {"enabled": true},
    "sensors": {
      "soil_moisture": {"filter_window": 15}
    }
  }'
```

This API provides comprehensive control over ESP32-C3 analog sensor devices, enabling device management, sensor calibration, power control, and real-time monitoring through a RESTful interface.