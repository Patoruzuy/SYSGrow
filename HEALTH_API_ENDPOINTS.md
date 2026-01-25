# Health API Endpoints

## Overview
The Health API provides comprehensive system monitoring with real-time metrics from various services across the backend.

## Endpoints

### 1. **GET /api/health/ping**
Basic liveness check for monitoring tools.

**Response:**
```json
{
  "data": {
    "status": "ok",
    "timestamp": "2025-12-08T17:00:00Z"
  }
}
```

**Use Case:** Load balancer health checks, uptime monitoring

---

### 2. **GET /api/health/system**
System-wide health with all units and event bus metrics.

**Response:**
```json
{
  "data": {
    "status": "healthy|degraded|critical",
    "units": {
      "1": {
        "unit_id": 1,
        "name": "Grow Tent 1",
        "hardware_running": true,
        "status": "healthy",
        "polling": {
          "mqtt_last_seen": {},
          "sensor_health": {},
          "event_bus": {
            "queue_depth": 0,
            "dropped_events": 0,
            "subscribers": 12
          }
        },
        "controller": {
          "started": true,
          "sensor_updates": {},
          "control_actions": {},
          "stale_sensors": [],
          "control_logic_enabled": true
        }
      }
    },
    "event_bus": {
      "queue_depth": 0,
      "dropped_events": 0,
      "subscribers": 15
    },
    "summary": {
      "total_units": 2,
      "healthy_units": 2,
      "degraded_units": 0,
      "offline_units": 0
    },
    "timestamp": "2025-12-08T17:00:00Z"
  }
}
```

**Data Sources:**
- `SensorPollingService.get_health_snapshot()` - Sensor polling metrics
- `ClimateController.get_health_status()` - Climate control status
- `EventBus.get_metrics()` - Event system metrics
- `UnitRuntime.is_hardware_running()` - Hardware operational status

**Status Logic:**
- `healthy`: All units running, no stale sensors
- `degraded`: Some units have issues or stale sensors
- `critical`: All units offline

---

### 3. **GET /api/health/units**
Summary health for all units.

**Response:**
```json
{
  "data": {
    "units": [
      {
        "unit_id": 1,
        "name": "Grow Tent 1",
        "status": "healthy",
        "hardware_running": true,
        "sensor_count": 5,
        "actuator_count": 3,
        "plant_count": 2,
        "active_plant": "Tomato Plant 1",
        "stale_sensors": 0
      }
    ],
    "summary": {
      "total": 2,
      "healthy": 2,
      "degraded": 0,
      "offline": 0
    }
  }
}
```

**Data Sources:**
- `GrowthService.get_unit_runtimes()` - All unit runtimes
- `DeviceService.list_sensors()` - Sensor count per unit
- `DeviceService.list_actuators()` - Actuator count per unit
- `UnitRuntime.plants` - Plant count
- `ClimateController.get_health_status()` - Stale sensor detection

---

### 4. **GET /api/health/units/{unit_id}**
Detailed health for a specific unit (drill-down view).

**Response:**
```json
{
  "data": {
    "unit_id": 1,
    "name": "Grow Tent 1",
    "status": "healthy",
    "hardware_running": true,
    "polling": {
      "mqtt_last_seen": {},
      "sensor_health": {},
      "last_known_readings": ["sensor_1", "sensor_2"],
      "event_bus": {}
    },
    "controller": {
      "started": true,
      "sensor_updates": {},
      "control_actions": {},
      "stale_sensors": []
    },
    "sensors": [
      {
        "id": 1,
        "name": "Temperature Sensor",
        "sensor_type": "temperature",
        "protocol": "mqtt"
      }
    ],
    "actuators": [
      {
        "id": 1,
        "name": "Exhaust Fan",
        "actuator_type": "fan",
        "status": "off"
      }
    ],
    "plants": [
      {
        "id": 1,
        "name": "Tomato Plant 1",
        "plant_type": "Tomato",
        "current_stage": "vegetative"
      }
    ],
    "active_plant": {...},
    "timestamp": "2025-12-08T17:00:00Z"
  }
}
```

**Use Case:** Detailed troubleshooting, unit dashboard

---

### 5. **GET /api/health/devices**
Aggregated device-level health across all units.

**Response:**
```json
{
  "data": {
    "sensors": {
      "total": 10,
      "healthy": 8,
      "degraded": 1,
      "offline": 1
    },
    "actuators": {
      "total": 6,
      "operational": 5,
      "failed": 1
    },
    "by_unit": {
      "1": {
        "sensors": {
          "total": 5,
          "healthy": 4,
          "degraded": 0,
          "offline": 1
        },
        "actuators": {
          "total": 3,
          "operational": 3,
          "failed": 0
        }
      }
    },
    "timestamp": "2025-12-08T17:00:00Z"
  }
}
```

**Data Sources:**
- `DeviceService.list_sensors()` - All sensors
- `DeviceService.list_actuators()` - All actuators
- `DeviceHealthService.get_sensor_health()` - Sensor health scores

**Health Score Ranges:**
- **Healthy**: 80-100
- **Degraded**: 50-79
- **Offline**: 0-49

---

### 6. **GET /api/health/sensors/{sensor_id}**
Health status for a specific sensor (unchanged).

**Response:**
```json
{
  "data": {
    "success": true,
    "sensor_id": 1,
    "health_score": 95,
    "status": "operational",
    "last_reading": "2025-12-08T16:59:00Z",
    "total_reads": 1000,
    "failed_reads": 5,
    "success_rate": 99.5
  }
}
```

**Data Source:** `DeviceHealthService.get_sensor_health()`

---

### 7. **GET /api/health/actuators/{actuator_id}**
Health history for an actuator (unchanged).

---

### 8. **GET /api/health/plants/summary**
Plant health summary across all units (unchanged).

---

### 9. **GET /api/health/ml**
ML service health status (unchanged).

---

## Architecture

### Services Used

1. **GrowthService** (`app/services/growth_service.py`)
   - `get_unit_runtimes()` - Get all unit runtime instances
   - `get_unit_runtime(unit_id)` - Get specific unit runtime

2. **UnitRuntime** (`app/domain/unit_runtime.py`)
   - `is_hardware_running()` - Check if hardware operational
   - `hardware_manager` - Access to hardware services
   - `plants` - Plant data
   - `active_plant` - Currently active plant

3. **UnitRuntimeManager** (`infrastructure/hardware/unit_runtime_manager.py`)
   - `polling_service` - Sensor polling service
   - `climate_controller` - Climate control service

4. **SensorPollingService** (`app/services/hardware/sensor_polling_service.py`)
   - `get_health_snapshot()` - Returns:
     * mqtt_last_seen
     * sensor_health
     * backoff_seconds_remaining
     * last_known_readings
     * event_bus metrics

5. **ClimateController** (`app/services/hardware/climate_control_service.py`)
   - `get_health_status()` - Returns:
     * started
     * sensor_updates
     * control_actions
     * stale_sensors (sensors not updated in 5 minutes)
     * control_logic_enabled
     * control_metrics

6. **DeviceService** (`app/services/application/device_service.py`)
   - `list_sensors(unit_id)` - Get all sensors
   - `list_actuators(unit_id)` - Get all actuators

7. **DeviceHealthService** (`app/services/application/device_health_service.py`)
   - `get_sensor_health(sensor_id)` - Sensor health with score

8. **EventBus** (`app/utils/event_bus.py`)
   - `get_metrics()` - Returns:
     * queue_depth
     * dropped_events
     * subscribers

---

## Frontend Integration

### Dashboard Components

1. **System Status Card**
   ```javascript
   GET /api/health/system
   // Show: Overall status badge, unit count, event bus metrics
   ```

2. **Units List**
   ```javascript
   GET /api/health/units
   // Show: Grid of unit cards with status badges
   ```

3. **Unit Detail Modal**
   ```javascript
   GET /api/health/units/{unit_id}
   // Show: Detailed metrics, sensor list, actuator list, plants
   ```

4. **Devices Overview**
   ```javascript
   GET /api/health/devices
   // Show: Device counts, health distribution, per-unit breakdown
   ```

### Status Badges

- **healthy**: Green badge (✓)
- **degraded**: Yellow badge (⚠)
- **offline**: Red badge (✗)
- **critical**: Red badge (!)

### Refresh Strategy

- **Ping**: Every 10 seconds
- **System/Units**: Every 30 seconds
- **Devices**: Every 60 seconds
- **Detailed views**: On demand + every 30 seconds when open

---

## Error Responses

All endpoints return consistent error format:

```json
{
  "error": "Error message",
  "status": 500
}
```

**Status Codes:**
- `200` - Success
- `404` - Resource not found
- `500` - Internal server error
- `503` - Service unavailable

---

## Testing

```bash
# Basic liveness
curl http://localhost:5000/api/health/ping

# System health
curl http://localhost:5000/api/health/system

# All units
curl http://localhost:5000/api/health/units

# Specific unit
curl http://localhost:5000/api/health/units/1

# All devices
curl http://localhost:5000/api/health/devices

# Specific sensor
curl http://localhost:5000/api/health/sensors/1
```

---

## Implementation Complete

All endpoints are now implemented with real data from the following services:
- ✅ SensorPollingService metrics
- ✅ ClimateController health
- ✅ EventBus metrics
- ✅ UnitRuntime status
- ✅ DeviceService counts
- ✅ DeviceHealthService scores

Ready for frontend integration!
