# Device Schedules API Migration Guide

## 📋 Summary

Device schedules have been migrated from global `Settings` table to unit-specific `device_schedules` field in `GrowthUnits` table.

### ⚠️ Deprecated Endpoints (Still Working - Backward Compatible)
- `GET /api/settings/light` → Use `GET /api/growth/units/{unit_id}/schedules`
- `PUT /api/settings/light` → Use `POST /api/growth/units/{unit_id}/schedules`
- `GET /api/settings/fan` → Use `GET /api/growth/units/{unit_id}/schedules`
- `PUT /api/settings/fan` → Use `POST /api/growth/units/{unit_id}/schedules`

### ✅ New Recommended Endpoints
- `GET /api/growth/units/{unit_id}/schedules` - Get all device schedules
- `GET /api/growth/units/{unit_id}/schedules/{device_type}` - Get specific device schedule
- `POST /api/growth/units/{unit_id}/schedules` - Create/update device schedule
- `DELETE /api/growth/units/{unit_id}/schedules/{device_type}` - Delete device schedule

---

## 🔄 Migration Examples

### Before (Deprecated) ❌

#### Get Light Schedule
```http
GET /api/settings/light
```

**Response:**
```json
{
  "ok": true,
  "data": {
    "start_time": "06:00",
    "end_time": "22:00",
    "_deprecated": true,
    "_message": "This endpoint is deprecated. Use /api/growth/units/{unit_id}/schedules instead."
  }
}
```

#### Update Light Schedule
```http
PUT /api/settings/light
Content-Type: application/json

{
  "start_time": "07:00",
  "end_time": "21:00"
}
```

---

### After (Recommended) ✅

#### Get All Device Schedules
```http
GET /api/growth/units/1/schedules
```

**Response:**
```json
{
  "ok": true,
  "data": {
    "device_schedules": {
      "light": {
        "device_type": "light",
        "start_time": "06:00",
        "end_time": "22:00",
        "enabled": true,
        "created_at": "2025-11-09T10:00:00",
        "updated_at": "2025-11-09T10:00:00"
      },
      "fan": {
        "device_type": "fan",
        "start_time": "08:00",
        "end_time": "20:00",
        "enabled": true,
        "created_at": "2025-11-09T10:00:00",
        "updated_at": "2025-11-09T10:00:00"
      },
      "pump": {
        "device_type": "pump",
        "start_time": "09:00",
        "end_time": "18:00",
        "enabled": false,
        "created_at": "2025-11-09T10:00:00",
        "updated_at": "2025-11-09T10:00:00"
      }
    }
  }
}
```

#### Get Specific Device Schedule
```http
GET /api/growth/units/1/schedules/light
```

**Response:**
```json
{
  "ok": true,
  "data": {
    "device_type": "light",
    "schedule": {
      "device_type": "light",
      "start_time": "06:00",
      "end_time": "22:00",
      "enabled": true,
      "created_at": "2025-11-09T10:00:00",
      "updated_at": "2025-11-09T10:00:00"
    }
  }
}
```

#### Create/Update Device Schedule
```http
POST /api/growth/units/1/schedules
Content-Type: application/json

{
  "device_type": "light",
  "start_time": "07:00",
  "end_time": "21:00",
  "enabled": true
}
```

**Response:**
```json
{
  "ok": true,
  "data": {
    "device_type": "light",
    "start_time": "07:00",
    "end_time": "21:00",
    "enabled": true,
    "message": "Device schedule set successfully"
  }
}
```

#### Delete Device Schedule
```http
DELETE /api/growth/units/1/schedules/pump
```

**Response:**
```json
{
  "ok": true,
  "data": {
    "device_type": "pump",
    "message": "Device schedule deleted successfully"
  }
}
```

---

## 📊 Complete API Reference

### 1. Get All Device Schedules

**Endpoint:** `GET /api/growth/units/{unit_id}/schedules`

**Description:** Get all device schedules for a specific growth unit.

**Parameters:**
- `unit_id` (path, integer, required) - Growth unit ID

**Response:** Dictionary of all device schedules

**Example:**
```bash
curl http://localhost:5000/api/growth/units/1/schedules
```

---

### 2. Get Specific Device Schedule

**Endpoint:** `GET /api/growth/units/{unit_id}/schedules/{device_type}`

**Description:** Get schedule for a specific device type.

**Parameters:**
- `unit_id` (path, integer, required) - Growth unit ID
- `device_type` (path, string, required) - Device type (e.g., 'light', 'fan', 'pump')

**Response:** Specific device schedule object

**Example:**
```bash
curl http://localhost:5000/api/growth/units/1/schedules/light
```

---

### 3. Create/Update Device Schedule

**Endpoint:** `POST /api/growth/units/{unit_id}/schedules`

**Description:** Set or update a device schedule.

**Parameters:**
- `unit_id` (path, integer, required) - Growth unit ID

**Request Body:**
```json
{
  "device_type": "light",
  "start_time": "06:00",
  "end_time": "22:00",
  "enabled": true
}
```

**Required Fields:**
- `device_type` (string) - Device type
- `start_time` (string) - Start time in HH:MM format
- `end_time` (string) - End time in HH:MM format

**Optional Fields:**
- `enabled` (boolean) - Whether schedule is active (default: true)

**Example:**
```bash
curl -X POST http://localhost:5000/api/growth/units/1/schedules \
  -H "Content-Type: application/json" \
  -d '{
    "device_type": "light",
    "start_time": "06:00",
    "end_time": "22:00",
    "enabled": true
  }'
```

---

### 4. Delete Device Schedule

**Endpoint:** `DELETE /api/growth/units/{unit_id}/schedules/{device_type}`

**Description:** Remove a device schedule.

**Parameters:**
- `unit_id` (path, integer, required) - Growth unit ID
- `device_type` (path, string, required) - Device type to remove

**Example:**
```bash
curl -X DELETE http://localhost:5000/api/growth/units/1/schedules/pump
```

---

## 🔧 JavaScript/Frontend Examples

### Using Fetch API

#### Get All Schedules
```javascript
async function getAllSchedules(unitId) {
  const response = await fetch(`/api/growth/units/${unitId}/schedules`);
  const result = await response.json();
  
  if (result.ok) {
    const schedules = result.data.device_schedules;
    console.log('Schedules:', schedules);
    return schedules;
  } else {
    console.error('Error:', result.error);
    return null;
  }
}

// Usage
getAllSchedules(1);
```

#### Set Device Schedule
```javascript
async function setDeviceSchedule(unitId, deviceType, startTime, endTime, enabled = true) {
  const response = await fetch(`/api/growth/units/${unitId}/schedules`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      device_type: deviceType,
      start_time: startTime,
      end_time: endTime,
      enabled: enabled
    })
  });
  
  const result = await response.json();
  
  if (result.ok) {
    console.log('Schedule set successfully:', result.data);
    return result.data;
  } else {
    console.error('Error:', result.error);
    return null;
  }
}

// Usage
setDeviceSchedule(1, 'light', '06:00', '22:00', true);
```

#### Delete Device Schedule
```javascript
async function deleteDeviceSchedule(unitId, deviceType) {
  const response = await fetch(`/api/growth/units/${unitId}/schedules/${deviceType}`, {
    method: 'DELETE'
  });
  
  const result = await response.json();
  
  if (result.ok) {
    console.log('Schedule deleted successfully');
    return true;
  } else {
    console.error('Error:', result.error);
    return false;
  }
}

// Usage
deleteDeviceSchedule(1, 'pump');
```

---

## 🎯 Supported Device Types

You can create schedules for any device type:

- `light` - Grow lights
- `fan` - Ventilation fans
- `pump` - Water pumps
- `heater` - Heating systems
- `humidifier` - Humidity control
- `dehumidifier` - Dehumidification
- `co2` - CO2 injection
- `mist` - Misting systems
- Any custom device type

---

## ⚠️ Breaking Changes

### None - Fully Backward Compatible!

The old endpoints (`/api/settings/light` and `/api/settings/fan`) still work but:
1. Return a deprecation warning in the response
2. Only work with the legacy Settings table (global, not unit-specific)
3. Will be removed in a future version

**Recommendation:** Update your frontend to use the new growth API endpoints as soon as possible.

---

## 🔍 Error Responses

### Unit Not Found
```json
{
  "ok": false,
  "data": null,
  "error": "Growth unit 999 not found."
}
```

### Schedule Not Found
```json
{
  "ok": false,
  "data": null,
  "error": "Schedule for device 'heater' not found."
}
```

### Missing Required Fields
```json
{
  "ok": false,
  "data": null,
  "error": "Missing required fields: device_type, start_time"
}
```

### Invalid Time Format
```json
{
  "ok": false,
  "data": null,
  "error": "Invalid time format. Use HH:MM (e.g., '14:30')"
}
```

---

## 📝 Testing the API

### Using cURL

```bash
# Get all schedules
curl http://localhost:5000/api/growth/units/1/schedules

# Get light schedule
curl http://localhost:5000/api/growth/units/1/schedules/light

# Set light schedule
curl -X POST http://localhost:5000/api/growth/units/1/schedules \
  -H "Content-Type: application/json" \
  -d '{"device_type":"light","start_time":"06:00","end_time":"22:00","enabled":true}'

# Delete pump schedule
curl -X DELETE http://localhost:5000/api/growth/units/1/schedules/pump
```

### Using Python Requests

```python
import requests

BASE_URL = "http://localhost:5000/api/growth"

# Get all schedules
response = requests.get(f"{BASE_URL}/units/1/schedules")
schedules = response.json()["data"]["device_schedules"]
print(schedules)

# Set device schedule
payload = {
    "device_type": "light",
    "start_time": "06:00",
    "end_time": "22:00",
    "enabled": True
}
response = requests.post(f"{BASE_URL}/units/1/schedules", json=payload)
print(response.json())

# Delete schedule
response = requests.delete(f"{BASE_URL}/units/1/schedules/pump")
print(response.json())
```

---

## 🎨 Frontend Integration Example

### Complete Vue.js Component

```vue
<template>
  <div class="device-schedules">
    <h2>Device Schedules - Unit {{ unitId }}</h2>
    
    <!-- List schedules -->
    <div v-for="(schedule, deviceType) in schedules" :key="deviceType" class="schedule-item">
      <h3>{{ deviceType }}</h3>
      <p>
        Start: {{ schedule.start_time }} | End: {{ schedule.end_time }}
        <span :class="schedule.enabled ? 'enabled' : 'disabled'">
          {{ schedule.enabled ? 'Enabled' : 'Disabled' }}
        </span>
      </p>
      <button @click="deleteSchedule(deviceType)">Delete</button>
    </div>
    
    <!-- Add new schedule -->
    <div class="add-schedule">
      <h3>Add New Schedule</h3>
      <input v-model="newSchedule.device_type" placeholder="Device Type (e.g., light)">
      <input v-model="newSchedule.start_time" type="time">
      <input v-model="newSchedule.end_time" type="time">
      <label>
        <input v-model="newSchedule.enabled" type="checkbox">
        Enabled
      </label>
      <button @click="addSchedule">Add Schedule</button>
    </div>
  </div>
</template>

<script>
export default {
  data() {
    return {
      unitId: 1,
      schedules: {},
      newSchedule: {
        device_type: '',
        start_time: '06:00',
        end_time: '22:00',
        enabled: true
      }
    }
  },
  mounted() {
    this.loadSchedules();
  },
  methods: {
    async loadSchedules() {
      const response = await fetch(`/api/growth/units/${this.unitId}/schedules`);
      const result = await response.json();
      if (result.ok) {
        this.schedules = result.data.device_schedules;
      }
    },
    async addSchedule() {
      const response = await fetch(`/api/growth/units/${this.unitId}/schedules`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(this.newSchedule)
      });
      const result = await response.json();
      if (result.ok) {
        this.loadSchedules();
        this.newSchedule.device_type = '';
      }
    },
    async deleteSchedule(deviceType) {
      const response = await fetch(
        `/api/growth/units/${this.unitId}/schedules/${deviceType}`,
        { method: 'DELETE' }
      );
      if (response.ok) {
        this.loadSchedules();
      }
    }
  }
}
</script>
```

---

## Summary

✅ **New API endpoints** are available at `/api/growth/units/{unit_id}/schedules`  
✅ **Backward compatibility** maintained with deprecation warnings  
✅ **Unit-specific schedules** - Each growth unit has its own device schedules  
✅ **Flexible device types** - Support for any device type  
✅ **Enable/disable support** - Control schedules without deleting them  

**Action Required:** Update frontend code to use new growth API endpoints instead of deprecated settings endpoints.
