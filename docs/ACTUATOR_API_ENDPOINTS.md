# Actuator API Endpoints - Complete Reference

## Overview

Phase 2 implementation adds comprehensive health monitoring, anomaly detection, power tracking, and calibration management for actuators.

## Table of Contents

1. [Health Monitoring](#health-monitoring)
2. [Anomaly Detection](#anomaly-detection)
3. [Power Readings](#power-readings)
4. [Calibration Management](#calibration-management)

---

## Health Monitoring

### Get Actuator Health History

**Endpoint:** `GET /api/devices/actuators/{actuator_id}/health`

**Description:** Retrieve health monitoring history for an actuator.

**Query Parameters:**
- `limit` (optional, default: 100): Maximum number of records to return

**Response:**
```json
{
  "success": true,
  "data": {
    "actuator_id": 1,
    "health_history": [
      {
        "history_id": 1,
        "health_score": 95,
        "status": "healthy",
        "total_operations": 1000,
        "failed_operations": 2,
        "average_response_time": 45.3,
        "last_successful_operation": "2025-11-15T15:30:00",
        "recorded_at": "2025-11-15T16:00:00"
      }
    ],
    "count": 1
  }
}
```

**Health Status Values:**
- `healthy`: Device operating normally
- `degraded`: Performance issues detected
- `critical`: Severe problems, immediate attention required
- `offline`: Device not responding

**Example:**
```bash
curl http://localhost:5000/api/devices/actuators/1/health?limit=50
```

### Save Health Snapshot

**Endpoint:** `POST /api/devices/actuators/{actuator_id}/health`

**Description:** Save a health monitoring snapshot for an actuator.

**Request Body:**
```json
{
  "health_score": 95,
  "status": "healthy",
  "total_operations": 1000,
  "failed_operations": 2,
  "average_response_time": 45.3
}
```

**Required Fields:**
- `health_score` (int, 0-100): Overall health score
- `status` (string): Health status

**Optional Fields:**
- `total_operations` (int): Total operation count
- `failed_operations` (int): Failed operation count
- `average_response_time` (float): Average response time in milliseconds

**Response:**
```json
{
  "success": true,
  "data": {
    "history_id": 123,
    "message": "Health snapshot saved successfully"
  }
}
```

**Example:**
```bash
curl -X POST http://localhost:5000/api/devices/actuators/1/health \
  -H "Content-Type: application/json" \
  -d '{
    "health_score": 95,
    "status": "healthy",
    "total_operations": 1000,
    "failed_operations": 2
  }'
```

---

## Anomaly Detection

### Get Actuator Anomalies

**Endpoint:** `GET /api/devices/actuators/{actuator_id}/anomalies`

**Description:** Retrieve anomaly history for an actuator.

**Query Parameters:**
- `limit` (optional, default: 100): Maximum number of records to return

**Response:**
```json
{
  "success": true,
  "data": {
    "actuator_id": 1,
    "anomalies": [
      {
        "anomaly_id": 1,
        "anomaly_type": "stuck_on",
        "severity": "high",
        "details": {
          "expected_state": "OFF",
          "actual_state": "ON",
          "duration_seconds": 300
        },
        "detected_at": "2025-11-15T14:30:00",
        "resolved_at": null
      }
    ],
    "total": 1,
    "unresolved": 1,
    "resolved": 0
  }
}
```

**Anomaly Types:**
- `stuck_on`: Relay stuck in ON state
- `stuck_off`: Relay stuck in OFF state
- `power_spike`: Unusual power consumption
- `no_response`: Device not responding
- `overheating`: Temperature exceeded threshold
- `connection_lost`: Network connection lost
- `short_circuit`: Electrical short detected
- `voltage_drop`: Voltage below threshold

**Severity Levels:**
- `low`: Minor issue, no immediate action required
- `medium`: Notable issue, should be investigated
- `high`: Significant problem, requires attention soon
- `critical`: Severe issue, immediate action required

**Example:**
```bash
curl http://localhost:5000/api/devices/actuators/1/anomalies?limit=50
```

### Log Actuator Anomaly

**Endpoint:** `POST /api/devices/actuators/{actuator_id}/anomalies`

**Description:** Log a detected anomaly for an actuator.

**Request Body:**
```json
{
  "anomaly_type": "stuck_on",
  "severity": "high",
  "details": {
    "expected_state": "OFF",
    "actual_state": "ON",
    "duration_seconds": 300
  }
}
```

**Required Fields:**
- `anomaly_type` (string): Type of anomaly
- `severity` (string): Severity level

**Optional Fields:**
- `details` (object): Additional information about the anomaly

**Response:**
```json
{
  "success": true,
  "data": {
    "anomaly_id": 456,
    "message": "Anomaly logged successfully"
  }
}
```

**Example:**
```bash
curl -X POST http://localhost:5000/api/devices/actuators/1/anomalies \
  -H "Content-Type: application/json" \
  -d '{
    "anomaly_type": "power_spike",
    "severity": "high",
    "details": {
      "normal_power": 150,
      "spike_power": 500,
      "duration_ms": 2000
    }
  }'
```

### Resolve Actuator Anomaly

**Endpoint:** `PATCH /api/devices/actuators/anomalies/{anomaly_id}/resolve`

**Description:** Mark an anomaly as resolved.

**Response:**
```json
{
  "success": true,
  "data": {
    "anomaly_id": 456,
    "message": "Anomaly resolved successfully"
  }
}
```

**Example:**
```bash
curl -X PATCH http://localhost:5000/api/devices/actuators/anomalies/456/resolve
```

---

## Power Readings

### Get Power Readings

**Endpoint:** `GET /api/devices/actuators/{actuator_id}/power-readings`

**Description:** Retrieve power consumption readings for an actuator.

**Query Parameters:**
- `limit` (optional, default: 1000): Maximum number of records
- `hours` (optional): Time window in hours (e.g., 24 for last 24 hours)

**Response:**
```json
{
  "success": true,
  "data": {
    "actuator_id": 1,
    "readings": [
      {
        "reading_id": 1,
        "voltage": 230.2,
        "current": 0.654,
        "power_watts": 150.5,
        "energy_kwh": 3.5,
        "power_factor": 0.95,
        "frequency": 50.0,
        "temperature": 42.3,
        "is_estimated": false,
        "timestamp": "2025-11-15T16:00:00"
      }
    ],
    "count": 1,
    "statistics": {
      "average_power_watts": 150.5,
      "max_power_watts": 165.2,
      "min_power_watts": 145.8
    }
  }
}
```

**Example:**
```bash
# Get last 24 hours of readings
curl http://localhost:5000/api/devices/actuators/1/power-readings?hours=24

# Get last 100 readings
curl http://localhost:5000/api/devices/actuators/1/power-readings?limit=100
```

### Save Power Reading

**Endpoint:** `POST /api/devices/actuators/{actuator_id}/power-readings`

**Description:** Save a power consumption reading.

**Request Body:**
```json
{
  "power_watts": 150.5,
  "voltage": 230.2,
  "current": 0.654,
  "energy_kwh": 3.5,
  "power_factor": 0.95,
  "frequency": 50.0,
  "temperature": 42.3,
  "is_estimated": false
}
```

**Required Fields:**
- `power_watts` (float): Power consumption in watts

**Optional Fields:**
- `voltage` (float): Voltage in volts
- `current` (float): Current in amps
- `energy_kwh` (float): Cumulative energy in kWh
- `power_factor` (float): Power factor (0-1)
- `frequency` (float): Frequency in Hz
- `temperature` (float): Device temperature in Celsius
- `is_estimated` (bool): Whether reading is estimated vs measured

**Response:**
```json
{
  "success": true,
  "data": {
    "reading_id": 789,
    "message": "Power reading saved successfully"
  }
}
```

**Example:**
```bash
curl -X POST http://localhost:5000/api/devices/actuators/1/power-readings \
  -H "Content-Type: application/json" \
  -d '{
    "power_watts": 150.5,
    "voltage": 230.2,
    "current": 0.654,
    "is_estimated": false
  }'
```

---

## Calibration Management

### Get Actuator Calibrations

**Endpoint:** `GET /api/devices/actuators/{actuator_id}/calibrations`

**Description:** Retrieve all calibrations for an actuator.

**Response:**
```json
{
  "success": true,
  "data": {
    "actuator_id": 1,
    "calibrations": [
      {
        "calibration_id": 1,
        "calibration_type": "power_profile",
        "calibration_data": {
          "rated_power_watts": 150.0,
          "standby_power_watts": 2.0,
          "efficiency_factor": 0.95,
          "power_curve": {
            "0": 2.0,
            "50": 77.0,
            "100": 150.0
          }
        },
        "created_at": "2025-11-15T10:00:00"
      }
    ],
    "count": 1,
    "by_type": {
      "power_profile": [
        {...}
      ]
    }
  }
}
```

**Calibration Types:**
- `power_profile`: Power consumption profile with rated/standby power
- `pwm_curve`: PWM duty cycle mapping for dimmers
- `timing`: Response time and delay calibration

**Example:**
```bash
curl http://localhost:5000/api/devices/actuators/1/calibrations
```

### Save Calibration Profile

**Endpoint:** `POST /api/devices/actuators/{actuator_id}/calibrations`

**Description:** Save a calibration profile for an actuator.

**Request Body - Power Profile:**
```json
{
  "calibration_type": "power_profile",
  "calibration_data": {
    "rated_power_watts": 150.0,
    "standby_power_watts": 2.0,
    "efficiency_factor": 0.95,
    "power_curve": {
      "0": 2.0,
      "25": 40.0,
      "50": 77.0,
      "75": 115.0,
      "100": 150.0
    }
  }
}
```

**Request Body - PWM Curve:**
```json
{
  "calibration_type": "pwm_curve",
  "calibration_data": {
    "min_duty_cycle": 0,
    "max_duty_cycle": 100,
    "curve_points": {
      "0": 0,
      "25": 30,
      "50": 55,
      "75": 80,
      "100": 100
    }
  }
}
```

**Request Body - Timing:**
```json
{
  "calibration_type": "timing",
  "calibration_data": {
    "response_time_ms": 50,
    "settle_time_ms": 200,
    "timeout_ms": 5000
  }
}
```

**Required Fields:**
- `calibration_type` (string): Type of calibration
- `calibration_data` (object): Calibration parameters

**Response:**
```json
{
  "success": true,
  "data": {
    "calibration_id": 234,
    "message": "Calibration saved successfully"
  }
}
```

**Example:**
```bash
curl -X POST http://localhost:5000/api/devices/actuators/1/calibrations \
  -H "Content-Type: application/json" \
  -d '{
    "calibration_type": "power_profile",
    "calibration_data": {
      "rated_power_watts": 150.0,
      "standby_power_watts": 2.0,
      "efficiency_factor": 0.95
    }
  }'
```

---

## Integration Examples

### Python Client Example

```python
import requests

BASE_URL = "http://localhost:5000/api/devices"

class ActuatorClient:
    def __init__(self, base_url=BASE_URL):
        self.base_url = base_url
    
    def save_health(self, actuator_id, health_score, status):
        """Save health snapshot"""
        response = requests.post(
            f"{self.base_url}/actuators/{actuator_id}/health",
            json={
                "health_score": health_score,
                "status": status
            }
        )
        return response.json()
    
    def log_anomaly(self, actuator_id, anomaly_type, severity, details=None):
        """Log anomaly"""
        response = requests.post(
            f"{self.base_url}/actuators/{actuator_id}/anomalies",
            json={
                "anomaly_type": anomaly_type,
                "severity": severity,
                "details": details
            }
        )
        return response.json()
    
    def save_power_reading(self, actuator_id, power_watts, **kwargs):
        """Save power reading"""
        data = {"power_watts": power_watts, **kwargs}
        response = requests.post(
            f"{self.base_url}/actuators/{actuator_id}/power-readings",
            json=data
        )
        return response.json()
    
    def save_calibration(self, actuator_id, calibration_type, calibration_data):
        """Save calibration profile"""
        response = requests.post(
            f"{self.base_url}/actuators/{actuator_id}/calibrations",
            json={
                "calibration_type": calibration_type,
                "calibration_data": calibration_data
            }
        )
        return response.json()

# Usage
client = ActuatorClient()

# Save health
client.save_health(1, 95, "healthy")

# Log anomaly
client.log_anomaly(1, "power_spike", "high", {"spike_power": 500})

# Save power reading
client.save_power_reading(1, 150.5, voltage=230.2, current=0.654)

# Save calibration
client.save_calibration(1, "power_profile", {
    "rated_power_watts": 150.0,
    "standby_power_watts": 2.0
})
```

### Integration with Energy Monitoring Service

```python
# In ActuatorManager
def _on_device_state_update(self, ieee_address: str, state: dict):
    """Handle device state updates from Zigbee2MQTT"""
    # Extract power data
    if 'power' in state or 'voltage' in state:
        # Save to memory (existing)
        reading = EnergyReading(
            actuator_id=actuator_id,
            voltage=state.get('voltage'),
            current=state.get('current'),
            power=state.get('power'),
            energy=state.get('energy')
        )
        self.energy_monitoring.record_reading(reading)
        
        # NEW: Persist to database
        device_service.save_actuator_power_reading(
            actuator_id=actuator_id,
            power_watts=state.get('power'),
            voltage=state.get('voltage'),
            current=state.get('current'),
            energy_kwh=state.get('energy'),
            is_estimated=False
        )
```

---

## Error Handling

All endpoints return errors in this format:

```json
{
  "success": false,
  "error": "Error message description"
}
```

**Common HTTP Status Codes:**
- `200 OK`: Request successful
- `400 Bad Request`: Invalid input parameters
- `404 Not Found`: Resource not found
- `500 Internal Server Error`: Server error

---

## Summary of New Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/actuators/{id}/health` | Get health history |
| POST | `/actuators/{id}/health` | Save health snapshot |
| GET | `/actuators/{id}/anomalies` | Get anomaly history |
| POST | `/actuators/{id}/anomalies` | Log anomaly |
| PATCH | `/actuators/anomalies/{id}/resolve` | Resolve anomaly |
| GET | `/actuators/{id}/power-readings` | Get power readings |
| POST | `/actuators/{id}/power-readings` | Save power reading |
| GET | `/actuators/{id}/calibrations` | Get calibrations |
| POST | `/actuators/{id}/calibrations` | Save calibration |

**Total: 9 new endpoints** added in Phase 2 implementation.

Combined with Phase 1 endpoints (7 energy monitoring & discovery endpoints), the system now has **16 specialized actuator endpoints** for comprehensive device management.
