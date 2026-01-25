# ActuatorManager Integration - Phase 3 Documentation

## Overview

Phase 3 completes the actuator modernization by integrating database persistence into the ActuatorManager. This enables automatic tracking of device health, real-time anomaly detection, power consumption logging, and calibration profile management.

## Features Implemented

### 1. **Automatic Power Reading Persistence**
- Real-time power data from Zigbee2MQTT devices automatically saved to database
- Captured metrics: voltage, current, power (watts), energy (kWh), power factor, frequency
- Enables long-term energy analysis and cost tracking

### 2. **Automated Health Monitoring**
- Health snapshots taken periodically (every 100 operations or hourly)
- Health score calculation (0-100) based on error rate
- Status levels: excellent (90+), good (75+), fair (50+), poor (<50)
- Tracks: total operations, failed operations, uptime hours, response times

### 3. **Real-time Anomaly Detection**
- Automatic logging of operation errors to database
- Anomaly types: operation_error, stuck_relay, power_spike, connection_loss, etc.
- Severity levels: critical, major, minor, info
- Event bus integration for real-time alerts

### 4. **Calibration Profile Loading**
- Saved calibration profiles loaded when actuator registered
- Applies custom power profiles to EnergyMonitoringService
- Supports: power_profile, pwm_curve, timing calibrations
- Enables device-specific accuracy improvements

## Architecture Changes

### Before Phase 3
```
ActuatorManager
    ↓
EnergyMonitoringService (memory only)
    ↓
No persistence
```

### After Phase 3
```
ActuatorManager
    ↓
├── EnergyMonitoringService (memory cache)
└── DeviceService (database persistence)
    ↓
Database Tables:
- ActuatorHealthHistory
- ActuatorAnomaly
- ActuatorPowerReading
- ActuatorCalibration
```

## Key Components

### ActuatorManager Updates

#### New Constructor Parameter
```python
actuator_manager = ActuatorManager(
    mqtt_client=mqtt_client,
    event_bus=event_bus,
    enable_energy_monitoring=True,
    enable_zigbee2mqtt_discovery=True,
    electricity_rate_kwh=0.12,
    device_service=device_service  # NEW: Enable database persistence
)
```

#### Health Tracking State
```python
self._operation_counts: Dict[int, int] = {}      # Operations per actuator
self._error_counts: Dict[int, int] = {}          # Errors per actuator
self._last_health_check: Dict[int, datetime] = {}  # Last health snapshot time
```

### New Private Methods

#### `_track_operation(actuator_id, result)`
Called after every actuator operation (on, off, toggle, set_level):
- Increments operation counter
- Tracks errors and logs anomalies
- Triggers periodic health snapshots

**Health Check Triggers:**
- Every 100 operations
- Every 1 hour (whichever comes first)

#### `_save_health_snapshot(actuator_id)`
Saves health metrics to database:
```python
{
    "health_score": 95.5,           # 0-100 based on error rate
    "status": "excellent",          # excellent/good/fair/poor
    "uptime_hours": 72.5,
    "total_operations": 1250,
    "failed_operations": 3,
    "last_operation": "2024-01-15T10:30:00",
    "average_response_time_ms": 45.2,
    "notes": "Automatic health check after 100 operations"
}
```

#### `_log_anomaly(actuator_id, type, severity, details)`
Logs anomaly to database:
```python
{
    "anomaly_type": "operation_error",
    "severity": "major",
    "details": {
        "error_message": "GPIO pin not responding",
        "timestamp": "2024-01-15T10:30:00"
    }
}
```

#### `_persist_power_reading(actuator_id, reading)`
Saves power readings from Zigbee2MQTT devices:
```python
{
    "power_watts": 145.3,
    "voltage": 230.2,
    "current": 0.65,
    "energy_kwh": 0.145,
    "power_factor": 0.95,
    "frequency": 50.0,
    "temperature": 42.5,
    "is_estimated": False
}
```

#### `_load_calibration_profiles(actuator_id, actuator_type)`
Loads saved calibrations when actuator registered:
- Queries database for calibration data
- Applies power profiles to EnergyMonitoringService
- Improves power estimation accuracy

## Integration Points

### Power Reading Flow
```
Zigbee2MQTT Device State Update
    ↓
_on_device_state_update()
    ↓
├── energy_monitoring.record_reading()  (memory)
└── _persist_power_reading()            (database)
```

### Health Tracking Flow
```
turn_on() / turn_off() / toggle() / set_level()
    ↓
_track_operation()
    ↓
├── Increment operation counter
├── Track errors → _log_anomaly()
└── Periodic check → _save_health_snapshot()
```

### Actuator Registration Flow
```
register_actuator()
    ↓
├── Create actuator entity
├── _load_calibration_profiles()  (NEW)
└── Initialize health tracking     (NEW)
```

## Database Schema Integration

### ActuatorHealthHistory
```sql
CREATE TABLE ActuatorHealthHistory (
    id INTEGER PRIMARY KEY,
    actuator_id INTEGER NOT NULL,
    health_score REAL NOT NULL,
    status TEXT NOT NULL,
    uptime_hours REAL,
    total_operations INTEGER,
    failed_operations INTEGER,
    last_operation TIMESTAMP,
    average_response_time_ms REAL,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### ActuatorAnomaly
```sql
CREATE TABLE ActuatorAnomaly (
    id INTEGER PRIMARY KEY,
    actuator_id INTEGER NOT NULL,
    anomaly_type TEXT NOT NULL,
    severity TEXT NOT NULL,
    details TEXT,
    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP,
    resolution_notes TEXT
);
```

### ActuatorPowerReading
```sql
CREATE TABLE ActuatorPowerReading (
    id INTEGER PRIMARY KEY,
    actuator_id INTEGER NOT NULL,
    power_watts REAL,
    voltage REAL,
    current REAL,
    energy_kwh REAL,
    power_factor REAL,
    frequency REAL,
    temperature REAL,
    is_estimated BOOLEAN DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### ActuatorCalibration
```sql
CREATE TABLE ActuatorCalibration (
    id INTEGER PRIMARY KEY,
    actuator_id INTEGER NOT NULL,
    calibration_type TEXT NOT NULL,
    calibration_data TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## Usage Examples

### Example 1: Creating ActuatorManager with Persistence
```python
from app.services.device_service import DeviceService
from infrastructure.hardware.actuators import ActuatorManager

# Initialize DeviceService
device_service = DeviceService(device_repository)

# Create ActuatorManager with database persistence
actuator_manager = ActuatorManager(
    mqtt_client=mqtt_client,
    event_bus=event_bus,
    enable_energy_monitoring=True,
    enable_zigbee2mqtt_discovery=True,
    electricity_rate_kwh=0.12,
    device_service=device_service  # Enable Phase 3 features
)

# Register actuator - calibrations automatically loaded
actuator_manager.register_actuator(
    actuator_id=1,
    name="Grow Light",
    actuator_type=ActuatorType.GROW_LIGHT,
    protocol=Protocol.ZIGBEE,
    config={'zigbee_id': 'light_001'}
)

# Control actuator - health automatically tracked
result = actuator_manager.turn_on(1)
# → Operation counted, health checked periodically

# Power readings automatically persisted
# When Zigbee2MQTT reports power data:
# → Stored in memory (EnergyMonitoringService)
# → Persisted to database (ActuatorPowerReading)
```

### Example 2: Automatic Health Monitoring
```python
# Operations are automatically tracked
for i in range(150):
    actuator_manager.toggle(1)
    # Every 100 operations → health snapshot saved
    # At operation 100: health_score calculated and saved
    # Any errors → anomaly logged immediately

# View health history via API
# GET /api/devices/actuators/1/health
# Returns all health snapshots with scores and trends
```

### Example 3: Real-time Anomaly Detection
```python
# If operation fails
result = actuator_manager.turn_on(1)
if result.state == ActuatorState.ERROR:
    # Anomaly automatically logged:
    # - Type: operation_error
    # - Severity: major
    # - Details: error_message, timestamp
    # - Event published: actuator_anomaly_detected
    pass

# View anomalies via API
# GET /api/devices/actuators/1/anomalies
# Returns all detected anomalies with resolution status
```

### Example 4: Power Consumption Tracking
```python
# Zigbee2MQTT device reports state change:
# {
#     "state": "ON",
#     "power": 145.3,
#     "voltage": 230.2,
#     "current": 0.65,
#     "energy": 0.145
# }

# ActuatorManager automatically:
# 1. Records in EnergyMonitoringService (memory)
# 2. Persists to ActuatorPowerReading (database)

# Query power history via API
# GET /api/devices/actuators/1/power-readings?hours=24
# Returns 24-hour power consumption with statistics
```

### Example 5: Calibration Profile Management
```python
# Save calibration via API
# POST /api/devices/actuators/1/calibrations
{
    "calibration_type": "power_profile",
    "calibration_data": {
        "rated_power_watts": 150.0,
        "standby_power_watts": 2.5,
        "efficiency_factor": 0.95,
        "power_curve": {
            "0": 0.0,
            "25": 30.0,
            "50": 75.0,
            "75": 115.0,
            "100": 150.0
        }
    }
}

# Next time actuator registered:
# → Calibration automatically loaded
# → Applied to EnergyMonitoringService
# → Power estimates use custom profile
```

## Health Score Calculation

### Algorithm
```python
error_rate = failed_operations / total_operations
health_score = max(0, 100 - (error_rate * 100))
```

### Status Mapping
| Health Score | Status    | Meaning                          |
|--------------|-----------|----------------------------------|
| 90-100       | excellent | Near-perfect reliability         |
| 75-89        | good      | Reliable with minor issues       |
| 50-74        | fair      | Functional with noticeable errors|
| 0-49         | poor      | Unreliable, needs attention      |

### Example Calculations
```python
# Scenario 1: Reliable device
operations = 1000
errors = 5
error_rate = 5 / 1000 = 0.005
health_score = 100 - (0.005 * 100) = 99.5  → "excellent"

# Scenario 2: Degrading device
operations = 500
errors = 75
error_rate = 75 / 500 = 0.15
health_score = 100 - (0.15 * 100) = 85.0  → "good"

# Scenario 3: Failing device
operations = 200
errors = 120
error_rate = 120 / 200 = 0.6
health_score = 100 - (0.6 * 100) = 40.0  → "poor"
```

## Performance Considerations

### Memory Efficiency
- Only tracks operation counts and error counts in memory
- Health snapshots saved periodically (not every operation)
- Power readings persisted asynchronously

### Database Load
- Health snapshot: ~1 write per 100 operations (or hourly)
- Anomaly log: Only on errors (typically rare)
- Power reading: ~1 write per Zigbee2MQTT state update (~1-60s depending on device)

### Query Optimization
All queries use indexes:
```sql
CREATE INDEX idx_health_actuator_id ON ActuatorHealthHistory(actuator_id);
CREATE INDEX idx_health_created_at ON ActuatorHealthHistory(created_at);
CREATE INDEX idx_anomaly_actuator_id ON ActuatorAnomaly(actuator_id);
CREATE INDEX idx_anomaly_severity ON ActuatorAnomaly(severity);
CREATE INDEX idx_power_actuator_id ON ActuatorPowerReading(actuator_id);
CREATE INDEX idx_power_created_at ON ActuatorPowerReading(created_at);
CREATE INDEX idx_calibration_actuator_id ON ActuatorCalibration(actuator_id);
```

## Monitoring & Alerting

### Event Bus Events

#### actuator_anomaly_detected
```python
{
    "actuator_id": 1,
    "anomaly_type": "operation_error",
    "severity": "major",
    "details": {...},
    "timestamp": "2024-01-15T10:30:00"
}
```

#### actuator_health_warning
(Future enhancement - not yet implemented)
```python
{
    "actuator_id": 1,
    "health_score": 55.0,
    "status": "fair",
    "trend": "declining",
    "timestamp": "2024-01-15T10:30:00"
}
```

### Recommended Alerts

1. **Critical Health**: health_score < 50
2. **Anomaly Spike**: >5 anomalies in 1 hour
3. **Power Anomaly**: power reading >20% deviation from profile
4. **No Data**: No power readings in 5 minutes (for powered devices)

## Testing Phase 3

### Test 1: Health Tracking
```python
# Start server
python run_server.py

# Register actuator
POST /api/devices/actuators
{
    "unit_id": 1,
    "name": "Test Light",
    "actuator_type": "grow_light",
    "protocol": "gpio",
    "gpio_pin": 17
}

# Perform 150 operations to trigger health snapshot
for i in range(150):
    POST /api/devices/actuators/1/toggle

# Check health history
GET /api/devices/actuators/1/health
# Should show at least 1 health snapshot (at 100 ops)
```

### Test 2: Anomaly Detection
```python
# Create scenario that causes error
# (e.g., invalid GPIO pin, disconnected device)

# Attempt operation
POST /api/devices/actuators/1/toggle
# If fails → anomaly logged

# Check anomalies
GET /api/devices/actuators/1/anomalies
# Should show operation_error anomaly
```

### Test 3: Power Reading Persistence
```python
# Register Zigbee2MQTT device with power monitoring
POST /api/devices/actuators
{
    "unit_id": 1,
    "name": "Smart Plug",
    "actuator_type": "outlet",
    "protocol": "zigbee",
    "zigbee_id": "plug_001",
    "metadata": {
        "ieee_address": "0x00158d00045d3b21"
    }
}

# Zigbee2MQTT will report power data automatically
# Wait for state updates from Zigbee2MQTT

# Check power readings
GET /api/devices/actuators/1/power-readings?hours=1
# Should show persisted power readings
```

### Test 4: Calibration Loading
```python
# Save calibration
POST /api/devices/actuators/1/calibrations
{
    "calibration_type": "power_profile",
    "calibration_data": {
        "rated_power_watts": 200.0,
        "standby_power_watts": 3.0,
        "efficiency_factor": 0.92
    }
}

# Restart server to re-register actuator
# Calibration should be loaded automatically

# Check power estimation uses custom profile
GET /api/devices/actuators/1/energy-stats
# Should reflect calibrated values
```

## Troubleshooting

### Issue: Health snapshots not being saved
**Symptoms**: GET /api/devices/actuators/{id}/health returns empty

**Causes**:
1. DeviceService not passed to ActuatorManager
2. Less than 100 operations performed
3. Database permission error

**Solution**:
```python
# Check ActuatorManager initialization
if actuator_manager.device_service is None:
    logger.error("DeviceService not initialized")
    
# Manually trigger health snapshot
actuator_manager._save_health_snapshot(actuator_id)
```

### Issue: Power readings not being persisted
**Symptoms**: GET /api/devices/actuators/{id}/power-readings returns empty

**Causes**:
1. Zigbee2MQTT not sending power data
2. IEEE address not in actuator metadata
3. DeviceService not available

**Solution**:
```python
# Check Zigbee2MQTT device state
mosquitto_sub -t "zigbee2mqtt/device_name" -v

# Verify IEEE address in actuator metadata
GET /api/devices/actuators/{id}
# Should have metadata.ieee_address

# Check logs for persistence errors
grep "Failed to persist power reading" logs/app.log
```

### Issue: Anomalies not being logged
**Symptoms**: No anomalies despite operation errors

**Causes**:
1. Operations not returning ERROR state
2. DeviceService not available
3. Database write error

**Solution**:
```python
# Check operation result state
result = actuator_manager.turn_on(actuator_id)
logger.debug(f"Operation result: {result.state}")

# Manually log anomaly
actuator_manager._log_anomaly(
    actuator_id=1,
    anomaly_type='test',
    severity='minor',
    details={'test': 'manual'}
)
```

### Issue: Calibrations not being loaded
**Symptoms**: Power estimates don't reflect saved calibration

**Causes**:
1. Calibration saved after actuator registered
2. Calibration type not 'power_profile'
3. Database query error

**Solution**:
```python
# Check saved calibrations
GET /api/devices/actuators/{id}/calibrations

# Manually reload calibrations
actuator_manager._load_calibration_profiles(
    actuator_id=1,
    actuator_type=ActuatorType.GROW_LIGHT
)

# Verify EnergyMonitoringService profile
power = actuator_manager.energy_monitoring.estimate_power(
    actuator_id=1,
    actuator_type='grow_light',
    level=100,
    state='on'
)
```

## Migration Guide

### Updating Existing Code

#### Before (Phase 2)
```python
# Old initialization without database persistence
actuator_manager = ActuatorManager(
    mqtt_client=mqtt_client,
    event_bus=event_bus,
    enable_energy_monitoring=True
)

# Power readings only in memory
# No health tracking
# No anomaly logging
```

#### After (Phase 3)
```python
from app.services.device_service import DeviceService

# Initialize DeviceService
device_service = DeviceService(device_repository)

# New initialization with database persistence
actuator_manager = ActuatorManager(
    mqtt_client=mqtt_client,
    event_bus=event_bus,
    enable_energy_monitoring=True,
    enable_zigbee2mqtt_discovery=True,
    electricity_rate_kwh=0.12,
    device_service=device_service  # ADD THIS
)

# Now features:
# ✓ Automatic power reading persistence
# ✓ Health tracking every 100 operations
# ✓ Real-time anomaly detection
# ✓ Calibration profile loading
```

## Future Enhancements

### Phase 4: Predictive Maintenance
- Machine learning model for failure prediction
- Health trend analysis
- Proactive replacement recommendations
- Cost-benefit analysis of maintenance actions

### Phase 5: Energy Optimization
- AI-driven scheduling for minimum cost
- Load balancing across actuators
- Peak demand avoidance
- Renewable energy integration

### Phase 6: Advanced Analytics
- Comparative analysis across devices
- Performance benchmarking
- Efficiency optimization recommendations
- Custom dashboards and reports

## Related Documentation

- [Actuator Schema Migration](./ACTUATOR_SCHEMA_MIGRATION.md) - Phase 1 database schema
- [Actuator API Endpoints](./ACTUATOR_API_ENDPOINTS.md) - Phase 2 REST API
- [Energy Monitoring Integration](./ENERGY_MONITORING_INTEGRATION.md) - Power tracking details
- [Zigbee2MQTT Discovery](./ZIGBEE2MQTT_DISCOVERY.md) - Device discovery features

## Conclusion

Phase 3 completes the actuator modernization by seamlessly integrating database persistence into the ActuatorManager. All operations now automatically track health metrics, detect anomalies, persist power readings, and load calibration profiles - with zero impact on existing code patterns.

The system now provides:
- **Observability**: Complete history of device operations and health
- **Reliability**: Early warning of device degradation
- **Efficiency**: Long-term power consumption analysis
- **Accuracy**: Device-specific calibration for better estimates

All features work automatically once DeviceService is passed to ActuatorManager constructor.
