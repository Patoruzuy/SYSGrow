# Actuator Database Schema Migration

## Overview

The Actuator database schema has been modernized to match the enterprise architecture of the Sensor system. This migration brings consistency, flexibility, and advanced monitoring capabilities to actuator management.

## Schema Changes

### Old Schema (Legacy)

```sql
CREATE TABLE Actuator (
    actuator_id INTEGER PRIMARY KEY,
    actuator_type TEXT NOT NULL,
    device TEXT NOT NULL,
    gpio INTEGER,
    ip_address TEXT,
    zigbee_channel TEXT,
    zigbee_topic TEXT,
    mqtt_broker TEXT,
    mqtt_port INTEGER,
    unit_id INTEGER
)

CREATE TABLE ActuatorHistory (
    event_id INTEGER PRIMARY KEY,
    actuator_id INTEGER,
    unit_id INTEGER,
    timestamp DATETIME,
    action TEXT CHECK (action IN ('ON', 'OFF')),
    duration INTEGER,
    reason TEXT
)
```

**Issues with Old Schema:**
- ❌ Mixed protocol fields (gpio, ip_address, zigbee_channel) in one table
- ❌ No name field for user-friendly identification
- ❌ No protocol field to indicate communication type
- ❌ No model field for device specifications
- ❌ No is_active flag for soft delete
- ❌ No timestamps for tracking
- ❌ No config table for flexible protocol-specific settings
- ❌ No health monitoring
- ❌ No anomaly detection
- ❌ No power monitoring integration
- ❌ No calibration support

### New Schema (Enterprise Architecture)

#### 1. Actuator Table (Main)
```sql
CREATE TABLE Actuator (
    actuator_id INTEGER PRIMARY KEY AUTOINCREMENT,
    unit_id INTEGER NOT NULL,
    name VARCHAR(100) NOT NULL,
    actuator_type VARCHAR(50) NOT NULL,
    protocol VARCHAR(20) NOT NULL,
    model VARCHAR(50) NOT NULL,
    ieee_address TEXT,
    is_active BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (unit_id) REFERENCES GrowthUnits(unit_id)
)
```

**Fields:**
- `unit_id`: Growth unit association (replaces unit_id)
- `name`: User-friendly device name (replaces device)
- `actuator_type`: Type of actuator (relay, pump, fan, light, heater, humidifier)
- `protocol`: Communication protocol (gpio, mqtt, wifi, zigbee, zigbee2mqtt, modbus)
- `model`: Device model/manufacturer
- `ieee_address`: For Zigbee2MQTT device identification
- `is_active`: Soft delete flag
- `created_at`, `updated_at`: Timestamps

#### 2. ActuatorConfig Table
```sql
CREATE TABLE ActuatorConfig (
    config_id INTEGER PRIMARY KEY AUTOINCREMENT,
    actuator_id INTEGER NOT NULL,
    config_data TEXT NOT NULL,  -- JSON
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (actuator_id) REFERENCES Actuator(actuator_id) ON DELETE CASCADE
)
```

**Purpose:** Store protocol-specific configuration as JSON

**Example JSON:**
```json
{
  "gpio": 17,
  "mqtt_broker": "localhost",
  "mqtt_port": 1883,
  "mqtt_topic": "growroom/light1/set",
  "zigbee_friendly_name": "grow_light_plug",
  "ip_address": "192.168.1.100"
}
```

#### 3. ActuatorCalibration Table
```sql
CREATE TABLE ActuatorCalibration (
    calibration_id INTEGER PRIMARY KEY AUTOINCREMENT,
    actuator_id INTEGER NOT NULL,
    calibration_type VARCHAR(20) DEFAULT 'power_profile',
    calibration_data TEXT NOT NULL,  -- JSON
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (actuator_id) REFERENCES Actuator(actuator_id) ON DELETE CASCADE
)
```

**Calibration Types:**
- `power_profile`: Power consumption profile
- `pwm_curve`: PWM duty cycle mapping
- `timing`: Response time calibration

**Example Power Profile JSON:**
```json
{
  "rated_power_watts": 150.0,
  "standby_power_watts": 2.0,
  "efficiency_factor": 0.95,
  "power_curve": {
    "0": 2.0,
    "50": 77.0,
    "100": 150.0
  }
}
```

#### 4. ActuatorHealthHistory Table
```sql
CREATE TABLE ActuatorHealthHistory (
    history_id INTEGER PRIMARY KEY AUTOINCREMENT,
    actuator_id INTEGER NOT NULL,
    health_score INTEGER NOT NULL,  -- 0-100
    status VARCHAR(20) NOT NULL,  -- healthy, degraded, critical, offline
    total_operations INTEGER DEFAULT 0,
    failed_operations INTEGER DEFAULT 0,
    average_response_time REAL DEFAULT 0.0,  -- milliseconds
    last_successful_operation TIMESTAMP,
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (actuator_id) REFERENCES Actuator(actuator_id) ON DELETE CASCADE
)
```

**Purpose:** Track actuator reliability and performance over time

#### 5. ActuatorAnomaly Table
```sql
CREATE TABLE ActuatorAnomaly (
    anomaly_id INTEGER PRIMARY KEY AUTOINCREMENT,
    actuator_id INTEGER NOT NULL,
    anomaly_type VARCHAR(50) NOT NULL,
    severity VARCHAR(20) NOT NULL,  -- low, medium, high, critical
    details TEXT,  -- JSON
    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP,
    FOREIGN KEY (actuator_id) REFERENCES Actuator(actuator_id) ON DELETE CASCADE
)
```

**Anomaly Types:**
- `stuck_on`: Relay stuck in ON state
- `stuck_off`: Relay stuck in OFF state
- `power_spike`: Unusual power consumption
- `no_response`: Device not responding
- `overheating`: Temperature exceeded threshold
- `connection_lost`: Network connection lost

#### 6. ActuatorPowerReading Table
```sql
CREATE TABLE ActuatorPowerReading (
    reading_id INTEGER PRIMARY KEY AUTOINCREMENT,
    actuator_id INTEGER NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    voltage REAL,
    current REAL,
    power_watts REAL NOT NULL,
    energy_kwh REAL,
    power_factor REAL,
    frequency REAL,
    temperature REAL,
    is_estimated BOOLEAN DEFAULT 0,
    FOREIGN KEY (actuator_id) REFERENCES Actuator(actuator_id) ON DELETE CASCADE
)
```

**Purpose:** Store power consumption data from smart switches or estimated values

**Integration:** Links with `EnergyMonitoringService` for real-time power tracking

#### 7. ActuatorHistory Table (Enhanced)
```sql
CREATE TABLE ActuatorHistory (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    actuator_id INTEGER NOT NULL,
    unit_id INTEGER NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    action TEXT NOT NULL,  -- ON, OFF, SET_LEVEL, DIM
    value INTEGER,  -- For dimmers, PWM values
    duration INTEGER,
    reason TEXT,  -- manual, schedule, ai_decision, automation
    triggered_by VARCHAR(50),  -- user, system, schedule_id, ai_agent
    power_consumed_kwh REAL,
    FOREIGN KEY (actuator_id) REFERENCES Actuator(actuator_id),
    FOREIGN KEY (unit_id) REFERENCES GrowthUnits(unit_id)
)
```

**Enhancements:**
- `value`: Support for dimming/PWM levels
- `triggered_by`: Track who/what triggered the action
- `power_consumed_kwh`: Energy used during operation

## Migration Strategy

### Backward Compatibility

The new schema maintains **full backward compatibility** with existing code:

1. **insert_actuator()** method:
   - Accepts old parameters (gpio, ip_address, zigbee_channel, etc.)
   - Automatically detects protocol
   - Builds JSON config from legacy parameters
   - Inserts into new normalized tables

2. **get_actuator_configs()** method:
   - Returns data in old format
   - Extracts legacy fields from JSON config
   - Existing code continues to work unchanged

### Migration Steps

**Option 1: Fresh Installation (Recommended)**
1. Delete existing database: `grow_tent.db`
2. Restart application
3. New schema will be created automatically

**Option 2: Data Preservation (Manual)**
```sql
-- 1. Backup existing data
CREATE TABLE Actuator_Backup AS SELECT * FROM Actuator;

-- 2. Drop old table
DROP TABLE Actuator;

-- 3. Create new tables (done automatically by application)

-- 4. Migrate data
INSERT INTO Actuator (unit_id, name, actuator_type, protocol, model)
SELECT 
    unit_id,
    device,
    actuator_type,
    CASE 
        WHEN gpio IS NOT NULL THEN 'gpio'
        WHEN mqtt_broker IS NOT NULL THEN 'mqtt'
        WHEN zigbee_channel IS NOT NULL THEN 'zigbee'
        WHEN ip_address IS NOT NULL THEN 'wifi'
        ELSE 'unknown'
    END,
    'Generic'
FROM Actuator_Backup;

-- 5. Migrate configs
INSERT INTO ActuatorConfig (actuator_id, config_data)
SELECT 
    actuator_id,
    json_object(
        'gpio', gpio,
        'ip_address', ip_address,
        'zigbee_channel', zigbee_channel,
        'zigbee_topic', zigbee_topic,
        'mqtt_broker', mqtt_broker,
        'mqtt_port', mqtt_port
    )
FROM Actuator_Backup;
```

## Indexes

Performance indexes are automatically created:

```sql
CREATE INDEX idx_actuator_unit_id ON Actuator(unit_id);
CREATE INDEX idx_actuator_type ON Actuator(actuator_type);
CREATE INDEX idx_actuator_protocol ON Actuator(protocol);
CREATE INDEX idx_actuator_ieee_address ON Actuator(ieee_address);
CREATE INDEX idx_actuator_health_actuator_id ON ActuatorHealthHistory(actuator_id);
CREATE INDEX idx_actuator_anomaly_actuator_id ON ActuatorAnomaly(actuator_id);
CREATE INDEX idx_actuator_calibration_actuator_id ON ActuatorCalibration(actuator_id);
CREATE INDEX idx_actuator_power_actuator_id ON ActuatorPowerReading(actuator_id);
CREATE INDEX idx_actuator_power_timestamp ON ActuatorPowerReading(timestamp);
CREATE INDEX idx_actuator_history_actuator_id ON ActuatorHistory(actuator_id);
CREATE INDEX idx_actuator_history_unit_id ON ActuatorHistory(unit_id);
CREATE INDEX idx_actuator_history_timestamp ON ActuatorHistory(timestamp);
```

## API Usage Examples

### Using Repository Methods

```python
from infrastructure.database.repositories.devices import DeviceRepository

# Initialize
repository = DeviceRepository(db_handler)

# Save health snapshot
repository.save_actuator_health_snapshot(
    actuator_id=1,
    health_score=95,
    status='healthy',
    total_operations=1000,
    failed_operations=2,
    average_response_time=45.3
)

# Log anomaly
repository.log_actuator_anomaly(
    actuator_id=1,
    anomaly_type='stuck_on',
    severity='high',
    details={'expected_state': 'OFF', 'actual_state': 'ON'}
)

# Save power reading
repository.save_actuator_power_reading(
    actuator_id=1,
    power_watts=150.5,
    voltage=230.2,
    current=0.654,
    energy_kwh=3.5,
    is_estimated=False
)

# Get power history
readings = repository.get_actuator_power_readings(
    actuator_id=1,
    hours=24,
    limit=1000
)

# Save calibration (power profile)
repository.save_actuator_calibration(
    actuator_id=1,
    calibration_type='power_profile',
    calibration_data={
        'rated_power_watts': 150.0,
        'standby_power_watts': 2.0,
        'efficiency_factor': 0.95
    }
)
```

## Benefits

### 1. Consistency
- Matches Sensor architecture pattern
- Unified approach across device types
- Easier maintenance and understanding

### 2. Flexibility
- JSON configs support any protocol
- No schema changes for new protocols
- Easy to extend with custom fields

### 3. Energy Monitoring
- Native support for power tracking
- Integration with EnergyMonitoringService
- Real-time and historical power data
- Estimated vs measured power tracking

### 4. Health Tracking
- Monitor device reliability
- Track operation success/failure rates
- Response time monitoring
- Proactive maintenance alerts

### 5. Anomaly Detection
- Detect stuck relays
- Identify power spikes
- Track connection issues
- Severity-based alerting

### 6. Calibration Support
- Store power profiles per device
- PWM curve calibration
- Timing adjustments
- Per-device customization

### 7. Enhanced History
- Track dimmer/PWM levels
- Record trigger sources
- Calculate energy consumed per operation
- Detailed event tracking

## Future Enhancements

### Phase 1: API Endpoints (Completed)
✅ Power monitoring endpoints
✅ Device discovery endpoints
✅ Energy statistics endpoints

### Phase 2: Database Integration (This Migration)
✅ Actuator schema modernization
✅ Power reading persistence
✅ Health monitoring storage
✅ Anomaly detection storage

### Phase 3: Advanced Features (Future)
- [ ] Automated health scoring
- [ ] Predictive maintenance alerts
- [ ] Energy optimization recommendations
- [ ] Cost analysis and reports
- [ ] Power consumption forecasting
- [ ] Device lifecycle tracking
- [ ] Warranty and maintenance schedules

### Phase 4: Frontend Integration (Future)
- [ ] Power monitoring dashboard
- [ ] Health status widgets
- [ ] Anomaly alerts UI
- [ ] Energy cost calculator
- [ ] Device management interface
- [ ] Calibration wizard

## Testing

### Verify Schema Creation
```python
import sqlite3

conn = sqlite3.connect('database/grow_tent.db')
cursor = conn.cursor()

# Check tables exist
tables = ['Actuator', 'ActuatorConfig', 'ActuatorCalibration', 
          'ActuatorHealthHistory', 'ActuatorAnomaly', 'ActuatorPowerReading']

for table in tables:
    result = cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", 
        (table,)
    ).fetchone()
    print(f"✅ {table}: {'EXISTS' if result else 'MISSING'}")

conn.close()
```

### Test Backward Compatibility
```python
from app.services.device_service import DeviceService

service = DeviceService(repository, growth_service)

# Old-style actuator creation (should still work)
actuator_id = service.create_actuator(
    actuator_type='Light',
    device='Grow Light 1',
    unit_id=1,
    gpio=17
)

# Verify data
actuators = service.repository.list_actuator_configs()
print(f"Actuators: {actuators}")
```

## Troubleshooting

### Issue: Old schema still present
**Solution:** Delete `grow_tent.db` and restart application

### Issue: Migration errors
**Solution:** Check SQLite version (requires 3.24+)

### Issue: Data loss concerns
**Solution:** Backup database before migration:
```bash
cp database/grow_tent.db database/grow_tent_backup_$(date +%Y%m%d).db
```

### Issue: Performance degradation
**Solution:** Verify indexes are created:
```sql
SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_actuator%';
```

## Summary

The actuator schema migration brings the system to enterprise-grade standards with:
- ✅ **7 new tables** for comprehensive actuator management
- ✅ **12 performance indexes** for fast queries
- ✅ **100% backward compatibility** with existing code
- ✅ **Native power monitoring** integration
- ✅ **Health tracking** and anomaly detection
- ✅ **Flexible JSON configs** for any protocol
- ✅ **Enhanced event history** with detailed tracking

This migration positions the system for advanced features like predictive maintenance, energy optimization, and comprehensive device lifecycle management.
