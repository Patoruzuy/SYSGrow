# Zigbee2MQTT Management Service

## Overview

The Zigbee Management Service provides integration with Zigbee2MQTT bridge for discovering, pairing, and managing Zigbee devices (sensors and actuators). It communicates via MQTT and exposes REST endpoints for the frontend.

**Key Features:**
- Device discovery from Zigbee2MQTT bridge
- Permit join for pairing new devices
- Device state monitoring
- Device rename and removal
- Coordinator status tracking

---

## Backend Service

**Location:** `app/services/application/zigbee_management_service.py`

### Service Methods

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| `get_discovered_devices()` | - | `List[ZigbeeDevice]` | Returns all devices discovered from the bridge |
| `get_sensors()` | - | `List[ZigbeeDevice]` | Returns only sensor-type devices |
| `get_actuators()` | - | `List[ZigbeeDevice]` | Returns only actuator-type devices |
| `get_device_by_ieee(ieee_address)` | `str` | `ZigbeeDevice` | Find device by IEEE address |
| `get_device_by_friendly_name(name)` | `str` | `ZigbeeDevice` | Find device by friendly name |
| `get_device_state(friendly_name)` | `str` | `dict` | Get current state (readings) of a device |
| `send_command(friendly_name, command)` | `str, dict` | `bool` | Send command to device (e.g., turn on/off) |
| `request_device_list()` | - | `None` | Request fresh device list from bridge |
| `get_devices(timeout)` | `float` | `List[dict]` | Request and wait for device list |
| `permit_device_join(time, device_type)` | `int, str` | `bool` | Enable pairing mode (0-254 seconds) |
| `get_bridge_health(timeout)` | `float` | `dict` | Get bridge health status |
| `rename_device(ieee_address, new_name)` | `str, str` | `dict` | Rename device friendly name |
| `remove_device(ieee_address)` | `str` | `bool` | Remove device from network |
| `force_rediscovery()` | - | `None` | Clear cache and request fresh discovery |
| `is_online` | - | `bool` | Property: bridge online status |

---

## REST API Endpoints

**Base Path:** `/api/devices`

### Bridge Management

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/v2/zigbee2mqtt/bridge/status` | GET | Get bridge status, online state, and device count |

**Response:**
```json
{
  "ok": true,
  "data": {
    "online": true,
    "health": {...},
    "device_count": 5,
    "coordinator_active": true
  }
}
```

---

### Device Discovery

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/v2/zigbee2mqtt/discover` | GET | Discover all devices from bridge |
| `/v2/zigbee2mqtt/rediscover` | POST | Force complete rediscovery (clears cache) |
| `/v2/zigbee2mqtt/sensors` | GET | Get only sensor devices |
| `/v2/zigbee2mqtt/actuators` | GET | Get only actuator devices |

**Discover Response:**
```json
{
  "ok": true,
  "data": {
    "devices": [
      {
        "ieee_address": "0x00124b001234abcd",
        "friendly_name": "living_room_sensor",
        "device_type": "EndDevice",
        "model_id": "SNZB-02",
        "manufacturer": "SONOFF",
        "sensor_types": ["temperature", "humidity", "battery"]
      }
    ],
    "count": 5
  }
}
```

---

### Permit Join (Pairing)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/v2/zigbee2mqtt/permit-join` | POST | Enable/disable permit join for new devices |

**Request:**
```json
{
  "duration": 254
}
```
- `duration`: 0-254 seconds (0 = disable, 254 = ~4 minutes)

**Response:**
```json
{
  "ok": true,
  "data": {
    "permit_join": true,
    "duration": 254,
    "message": "Permit join enabled for 254 seconds"
  }
}
```

---

### Device Management

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/v2/zigbee2mqtt/devices/<ieee>` | GET | Get device details and current state |
| `/v2/zigbee2mqtt/devices/<ieee>/state` | GET | Get only current state |
| `/v2/zigbee2mqtt/devices/<ieee>/rename` | POST | Rename device friendly name |
| `/v2/zigbee2mqtt/devices/<ieee>` | DELETE | Remove device from network |

**Rename Request:**
```json
{
  "new_name": "kitchen_sensor"
}
```

**State Response:**
```json
{
  "ok": true,
  "data": {
    "ieee_address": "0x00124b001234abcd",
    "friendly_name": "living_room_sensor",
    "state": {
      "temperature": 23.5,
      "humidity": 65,
      "battery": 100,
      "linkquality": 156
    }
  }
}
```

---

### Device Commands

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/zigbee2mqtt/command` | POST | Send command to device |

**Request:**
```json
{
  "friendly_name": "smart_plug_1",
  "command": {
    "state": "ON"
  }
}
```

---

## Frontend Integration

### API Methods (`static/js/api.js`)

```javascript
API.Device.getZigbeeBridgeStatus()      // GET bridge status
API.Device.permitZigbeeJoin(duration)   // POST enable pairing
API.Device.forceZigbeeRediscovery()     // POST force rediscovery
API.Device.discoverZigbee()             // GET discover devices
API.Device.getZigbeeDevice(ieee)        // GET device details
API.Device.getZigbeeDeviceState(ieee)   // GET device state
API.Device.renameZigbeeDevice(ieee, name) // POST rename
API.Device.removeZigbeeDevice(ieee)     // DELETE remove
API.Device.getZigbeeSensors()           // GET sensors only
API.Device.getZigbeeActuators()         // GET actuators only
```

### Data Service (`static/js/devices/data-service.js`)

```javascript
dataService.getBridgeStatus()           // Get bridge online status
dataService.permitJoin(duration)        // Enable pairing mode
dataService.forceRediscovery()          // Force device refresh
dataService.discoverZigbeeDevices()     // Discover devices
dataService.removeZigbeeDevice(ieee)    // Remove device
dataService.renameZigbeeDevice(ieee, name) // Rename device
```

---

## User Flow

### 1. Viewing Zigbee Devices

```
User clicks "Zigbee2MQTT" tab
    │
    ├─► Auto-triggers discovery
    │       └─► Fetches devices from bridge
    │
    ├─► Loads bridge status
    │       └─► Shows coordinator indicator (online/offline)
    │
    └─► Displays device cards
            └─► Filters out coordinator (shown as status only)
```

### 2. Adding New Device

```
User clicks "Permit Join" button
    │
    ├─► Sends permit-join request (254 seconds)
    │
    ├─► Button shows countdown timer
    │       └─► "Joining (254s)... (253s)..."
    │
    ├─► User puts new Zigbee device in pairing mode
    │       └─► Device joins network
    │
    └─► Timer expires OR user clicks again to stop
            └─► Auto-refreshes device list
```

### 3. Managing Existing Device

```
Device appears in discovered list
    │
    ├─► Select from dropdown to pre-fill form
    │
    ├─► Assign to growth unit
    │
    ├─► Configure sensor type
    │
    └─► Submit to register in database
```

### 4. Removing Device

```
Call removeZigbeeDevice(ieee_address)
    │
    ├─► Device removed from Zigbee network
    │
    └─► Device list refreshes automatically
```

---

## Coordinator Handling

The Zigbee coordinator is the USB dongle that manages the Zigbee network. It:

- **Is NOT shown** in the device list (filtered out)
- **IS shown** as a status indicator at the top of the Zigbee panel
- Displays: "Coordinator Online (X devices)" or "Coordinator Offline"

**Filtering Logic:**
```javascript
// Filter out coordinator from device lists
devices.filter(d => {
    const type = (d.type || d.device_type || '').toLowerCase();
    if (type === 'coordinator') return false;
    if (d.friendly_name.toLowerCase() === 'coordinator') return false;
    return true;
});
```

---

## Error Handling

| Error | HTTP Code | Cause |
|-------|-----------|-------|
| "Zigbee2MQTT service not available" | 503 | MQTT not enabled |
| "Device not found" | 404 | Invalid IEEE address |
| "Cannot remove coordinator" | 400 | Attempted to remove coordinator |
| "Rename operation timed out" | 504 | Bridge didn't respond |

---

## Configuration

Enable MQTT in environment:
```bash
SYSGROW_ENABLE_MQTT=true
MQTT_BROKER_HOST=localhost
MQTT_BROKER_PORT=1883
```

Zigbee2MQTT must be running and connected to the same MQTT broker.
