# Health API Consolidation

## Overview
This document describes the consolidated health API that replaces the previous scattered health endpoints across multiple blueprints.

## New Unified Health API Structure

All health endpoints are now under `/api/health/*`:

### System Health
- **GET** `/api/health/system` - Overall system health including polling, climate controllers, and event bus
  - Response: System-wide health metrics for all units
  - Replaces: `/api/dashboard/health`

### Unit Health
- **GET** `/api/health/units/<unit_id>` - Health metrics for a specific growth unit
  - Response: Unit-specific health score, metrics, alerts, and recommendations
  - Replaces: `/api/insights/unit/<unit_id>/health`

### Sensor Health
- **GET** `/api/health/sensors/<sensor_id>` - Health status for a specific sensor
  - Query params: None
  - Response: Sensor health score, status, error types
  - Replaces: `/api/devices/sensors/<sensor_id>/health`

### Actuator Health
- **GET** `/api/health/actuators/<actuator_id>` - Health history for an actuator
  - Query params: `limit` (default: 100) - number of history records to return
  - Response: Actuator health history, count
  - Replaces: `/api/devices/actuators/<actuator_id>/health` (GET)

- **POST** `/api/health/actuators/<actuator_id>` - Save actuator health snapshot
  - Request body:
    ```json
    {
      "health_score": 95,
      "status": "operational",
      "total_operations": 1000,
      "failed_operations": 5,
      "average_response_time": 0.05
    }
    ```
  - Response: `{ "history_id": 123, "message": "Health snapshot saved" }`
  - Replaces: `/api/devices/actuators/<actuator_id>/health` (POST)

### Plant Health
- **GET** `/api/health/plants/summary` - Health summary for all plants across all units
  - Response: List of all plants with health status, issues, observations
  - Replaces: `/api/plants/health/summary`

- **GET** `/api/health/plants/symptoms` - List of available plant health symptoms
  - Response: Array of symptom types (yellowing_leaves, wilting, brown_spots, etc.)

- **GET** `/api/health/plants/statuses` - List of available plant health statuses
  - Response: Array of statuses (healthy, warning, critical, recovering)

### ML Service Health
- **GET** `/api/health/ml` - Health status of ML services and models
  - Response: ML service status, features availability
  - Replaces: `/api/insights/health`

## Deprecation Strategy

### Backwards Compatibility
All old endpoints remain functional with added deprecation warnings:

1. **HTTP Headers**: Deprecated endpoints return these headers:
   - `X-Deprecated: true`
   - `X-Deprecated-Replacement: /api/health/...` (new endpoint URL)

2. **Logging**: Each call to a deprecated endpoint logs a warning:
   ```
   [DEPRECATED] /api/dashboard/health called. Use /api/health/system instead.
   ```

### Old Endpoints (Still Working)
- ❌ `/api/dashboard/health` → ✅ `/api/health/system`
- ❌ `/api/insights/unit/<unit_id>/health` → ✅ `/api/health/units/<unit_id>`
- ❌ `/api/insights/health` → ✅ `/api/health/ml`
- ❌ `/api/devices/sensors/<sensor_id>/health` → ✅ `/api/health/sensors/<sensor_id>`
- ❌ `/api/devices/actuators/<actuator_id>/health` (GET/POST) → ✅ `/api/health/actuators/<actuator_id>`
- ❌ `/api/plants/health/summary` → ✅ `/api/health/plants/summary`

### Migration Timeline
1. **Phase 1** (Current): Both old and new endpoints work
2. **Phase 2** (Next Sprint): Update frontend to use new endpoints
3. **Phase 3** (Future): Remove old endpoints after frontend migration complete

## Benefits

### 1. Clear Organization
- All health-related endpoints in one place
- Easy to find and understand health monitoring capabilities
- Consistent URL structure

### 2. Reduced Code Duplication
- Single implementation for each health check type
- Shared helper functions and error handling
- Centralized logging and metrics

### 3. Better Maintainability
- Changes to health logic only need updates in one place
- Easier to add new health check types
- Consistent response format across all health endpoints

### 4. API Discoverability
- Clear /api/health/* namespace
- Self-documenting endpoint structure
- Easier for API consumers to find health endpoints

## Implementation Files

- **New Blueprint**: `app/blueprints/api/health/__init__.py`
- **Registration**: `app/__init__.py` (line ~150)
- **Deprecated Endpoints** (with warnings):
  - `app/blueprints/api/dashboard.py`
  - `app/blueprints/api/insights.py`
  - `app/blueprints/api/devices/sensors.py`
  - `app/blueprints/api/devices/actuators.py`
  - `app/blueprints/api/plants.py`

## Testing

### Manual Testing
```bash
# Test new endpoints
curl http://localhost:5000/api/health/system
curl http://localhost:5000/api/health/units/1
curl http://localhost:5000/api/health/sensors/1
curl http://localhost:5000/api/health/actuators/1
curl http://localhost:5000/api/health/plants/summary
curl http://localhost:5000/api/health/ml

# Test deprecated endpoints (should work with deprecation headers)
curl -I http://localhost:5000/api/dashboard/health
curl -I http://localhost:5000/api/insights/unit/1/health
curl -I http://localhost:5000/api/devices/sensors/1/health
```

### Expected Behavior
- New endpoints return same data as old ones
- Old endpoints include deprecation headers
- Server logs show deprecation warnings when old endpoints called

## Next Steps

1. ✅ Create health API blueprint
2. ✅ Add deprecation warnings to old endpoints
3. ⏳ Update frontend to use new endpoints
4. ⏳ Monitor usage of deprecated endpoints
5. ⏳ Remove old endpoints after migration period
