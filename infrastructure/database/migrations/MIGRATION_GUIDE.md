# Database Schema Migration Guide

## Overview

This migration transforms the database schema from a denormalized sensor storage model to a normalized, enterprise-grade architecture that aligns with the Domain-Driven Design principles implemented in the application layer.

## Migration File

**File:** `migrate_to_new_sensor_schema.sql`

## What Changed

### Old Schema (Before)
```sql
CREATE TABLE Sensor (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    sensor_type TEXT,
    sensor_model TEXT,  -- Mixed hardware model with type (e.g., 'ENS160AHT21')
    gpio INTEGER,
    ip_address TEXT,
    communication TEXT,  -- 'I2C', 'MQTT', etc.
    redis_keys TEXT,
    update_interval INTEGER,
    battery_key TEXT,
    unit_id INTEGER
)
```

**Problems:**
- `sensor_model` mixed hardware model with sensor type
- `communication` duplicated protocol information
- GPIO, I2C, IP address in separate nullable columns
- No storage for calibration, health, or anomaly data
- Type mapping required in application code

### New Schema (After)

#### 1. Sensor Table (Normalized)
```sql
CREATE TABLE Sensor (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    unit_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    sensor_type TEXT NOT NULL,     -- 'temperature', 'humidity', 'environment_sensor', etc.
    protocol TEXT NOT NULL,         -- 'I2C', 'MQTT', 'ANALOG', 'HTTP'
    model TEXT,                     -- Hardware model: 'ENS160AHT21', 'DHT22', etc.
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (unit_id) REFERENCES GrowthUnit(id) ON DELETE CASCADE
)
```

**Benefits:**
- Clear separation of concerns
- Protocol stored directly (no mapping needed)
- Model separate from type
- Timestamps for auditing

#### 2. SensorConfig Table (JSON Storage)
```sql
CREATE TABLE SensorConfig (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sensor_id INTEGER NOT NULL,
    config_data TEXT NOT NULL,  -- JSON: {"gpio_pin": 4, "i2c_bus": 1, "address": "0x53"}
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (sensor_id) REFERENCES Sensor(id) ON DELETE CASCADE
)
```

**Benefits:**
- Flexible protocol-specific configuration
- Easy to add new config options
- No schema changes needed for new sensor types

**Example Config Data:**
```json
// I2C Sensor
{"i2c_bus": 1, "i2c_address": "0x53", "gpio_pin": 4}

// MQTT Sensor
{"mqtt_topic": "growtent/unit1/sensor/temp", "redis_key": "sensor:temp:1"}

// Analog Sensor
{"gpio_pin": 34, "adc_channel": 1, "voltage_divider": 3.3}

// HTTP Sensor
{"endpoint": "http://192.168.1.100/api/sensor", "auth_token": "xyz"}
```

#### 3. SensorCalibration Table (Persistent Calibration)
```sql
CREATE TABLE SensorCalibration (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sensor_id INTEGER NOT NULL,
    measured_value REAL NOT NULL,    -- Raw sensor reading
    reference_value REAL NOT NULL,   -- Known correct value
    calibration_type TEXT,           -- 'linear', 'polynomial', 'lookup'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (sensor_id) REFERENCES Sensor(id) ON DELETE CASCADE
)
```

**Use Case:** Track calibration history, allow recalculation of calibration curves

#### 4. SensorHealthHistory Table (Health Monitoring)
```sql
CREATE TABLE SensorHealthHistory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sensor_id INTEGER NOT NULL,
    health_score REAL NOT NULL,
    status TEXT NOT NULL,            -- 'healthy', 'degraded', 'critical', 'offline'
    error_rate REAL,
    consecutive_errors INTEGER,
    last_successful_read TIMESTAMP,
    read_count INTEGER,
    metrics_data TEXT,               -- JSON: additional metrics
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (sensor_id) REFERENCES Sensor(id) ON DELETE CASCADE
)
```

**Use Case:** Track sensor reliability over time, predict failures

#### 5. SensorAnomaly Table (Anomaly Detection)
```sql
CREATE TABLE SensorAnomaly (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sensor_id INTEGER NOT NULL,
    value REAL NOT NULL,             -- Anomalous reading
    mean_value REAL NOT NULL,        -- Expected mean
    std_deviation REAL NOT NULL,     -- Standard deviation
    z_score REAL NOT NULL,           -- Statistical significance
    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (sensor_id) REFERENCES Sensor(id) ON DELETE CASCADE
)
```

**Use Case:** Log unusual readings, trigger alerts, analyze patterns

#### 6. SensorReading Table (Updated)
```sql
CREATE TABLE SensorReading (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sensor_id INTEGER NOT NULL,
    reading_data TEXT NOT NULL,      -- JSON: {"temperature": 25.5, "humidity": 60.2}
    quality_score REAL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (sensor_id) REFERENCES Sensor(id) ON DELETE CASCADE
)
```

**Benefits:**
- Flexible schema (no column per sensor type)
- Supports multi-value sensors (temperature + humidity)
- Quality score for data validation

## Data Transformation Examples

### Example 1: I2C Environment Sensor
**Old:**
```sql
INSERT INTO Sensor VALUES (
    1, 'Main Env Sensor', 'environment_sensor', 'ENS160AHT21',
    4, NULL, 'I2C', 'sensor:env:1', 30, NULL, 1
);
```

**New:**
```sql
-- Sensor table
INSERT INTO Sensor (unit_id, name, sensor_type, protocol, model)
VALUES (1, 'Main Env Sensor', 'environment_sensor', 'I2C', 'ENS160AHT21');

-- SensorConfig table
INSERT INTO SensorConfig (sensor_id, config_data)
VALUES (1, '{"gpio_pin": 4, "i2c_bus": 1, "i2c_address": "0x53"}');
```

### Example 2: MQTT Temperature Sensor
**Old:**
```sql
INSERT INTO Sensor VALUES (
    2, 'MQTT Temp', 'temperature', NULL,
    NULL, '192.168.1.100', 'MQTT', 'sensor:temp:mqtt', 60, NULL, 1
);
```

**New:**
```sql
-- Sensor table
INSERT INTO Sensor (unit_id, name, sensor_type, protocol, model)
VALUES (1, 'MQTT Temp', 'temperature', 'MQTT', NULL);

-- SensorConfig table
INSERT INTO SensorConfig (sensor_id, config_data)
VALUES (2, '{"mqtt_topic": "growtent/unit1/sensor/temp", "redis_key": "sensor:temp:mqtt", "ip_address": "192.168.1.100"}');
```

## Migration Safety

### Safety Features
1. **No Data Loss:** Old tables renamed to `Sensor_OLD` and `SensorReading_OLD`
2. **Rollback Possible:** Keep old tables for manual verification
3. **Data Verification:** Compare row counts before/after
4. **Transaction Safe:** Wrapped in transaction (if supported)

### Verification Queries
```sql
-- Compare row counts
SELECT COUNT(*) FROM Sensor_OLD;
SELECT COUNT(*) FROM Sensor;

-- Check data integrity
SELECT s.id, s.name, s.sensor_type, s.protocol, sc.config_data
FROM Sensor s
LEFT JOIN SensorConfig sc ON s.id = sc.sensor_id
LIMIT 10;
```

## Application Code Changes

### Repository Layer (DeviceRepository)

**Before:**
```python
def create_sensor(self, name, sensor_type, sensor_model, gpio=None,
                 ip_address=None, communication=None, redis_keys=None,
                 update_interval=30, battery_key=None, unit_id=None):
    return self.backend.insert_sensor(...)
```

**After:**
```python
def create_sensor(self, unit_id: int, name: str, sensor_type: str,
                 protocol: str, model: Optional[str] = None,
                 config_data: Optional[Dict[str, Any]] = None) -> Optional[int]:
    return self.backend.insert_sensor(unit_id, name, sensor_type, protocol, model, config_data)
```

### New Methods Added
```python
# Calibration
save_calibration(sensor_id, measured_value, reference_value, calibration_type)
get_calibrations(sensor_id, limit=20)

# Health Monitoring
save_health_snapshot(sensor_id, health_score, status, error_rate, ...)
get_health_history(sensor_id, limit=100)

# Anomaly Detection
log_anomaly(sensor_id, value, mean_value, std_deviation, z_score)
get_anomalies(sensor_id, limit=100)

# Readings
record_sensor_reading(sensor_id, reading_data, quality_score)
```

### Runtime Manager (UnitRuntimeManager)

**Before (Type Mapping Required):**
```python
type_map = {
    'ENS160AHT21': SensorType.ENVIRONMENT,
    'DHT22': SensorType.TEMPERATURE,
    'ADS1115': SensorType.ANALOG,
    # ... 7 entries
}

sensor_type = type_map.get(config.get('sensor_model'), SensorType.UNKNOWN)

protocol_map = {
    'I2C': Protocol.I2C,
    'MQTT': Protocol.MQTT,
    # ... 7 lines
}
```

**After (Direct Enum Conversion):**
```python
sensor_type = SensorType(config['sensor_type'])
protocol = Protocol(config['protocol'])
```

**Benefit:** 60 lines → 40 lines, no mapping dictionaries needed!

### Persistence Integration

**Calibration (with persistence):**
```python
def calibrate_sensor(self, sensor_id: int, reference_value: float,
                    calibration_type: str = "linear") -> None:
    reading = self.sensor_manager.read_sensor(sensor_id)
    measured_value = reading.value

    # Add to service
    self.calibration_service.add_calibration_point(
        sensor_id, measured_value, reference_value
    )

    # Persist to database
    self.repo_devices.save_calibration(
        sensor_id, measured_value, reference_value, calibration_type
    )
```

**Health Monitoring (with persistence):**
```python
def get_sensor_health(self, sensor_id: int) -> Dict[str, Any]:
    health = self.health_service.get_sensor_health(sensor_id)

    # Persist snapshot
    self.repo_devices.save_health_snapshot(
        sensor_id=sensor_id,
        health_score=health.health_score,
        status=health.status.value,
        error_rate=health.error_rate,
        ...
    )

    return health_data
```

**Anomaly Detection (with persistence):**
```python
def check_sensor_anomalies(self, sensor_id: int) -> Dict[str, Any]:
    reading = self.sensor_manager.read_sensor(sensor_id)
    is_anomaly = self.anomaly_service.detect_anomaly(sensor_id, value)

    # If anomaly detected, log to database
    if is_anomaly:
        self.repo_devices.log_anomaly(
            sensor_id, value, mean, std_dev, z_score
        )
```

## Migration Steps

### Step 1: Backup Database
```bash
cp smart_agriculture.db smart_agriculture.db.backup
```

### Step 2: Run Migration
```bash
# Option 1: Direct SQL execution
sqlite3 smart_agriculture.db < migrate_to_new_sensor_schema.sql

# Option 2: Python script (recommended)
python -c "
from infrastructure.database.sqlite_handler import SQLiteHandler
handler = SQLiteHandler()
with open('migrate_to_new_sensor_schema.sql', 'r') as f:
    handler.execute_script(f.read())
"
```

### Step 3: Verify Migration
```python
from infrastructure.database.repositories.devices import DeviceRepository

repo = DeviceRepository()

# Test: Get sensor configs
configs = repo.list_sensor_configs()
print(f"Migrated {len(configs)} sensors")

# Test: Create new sensor
sensor_id = repo.create_sensor(
    unit_id=1,
    name="Test Sensor",
    sensor_type="temperature",
    protocol="I2C",
    model="DHT22",
    config_data={"gpio_pin": 4, "i2c_bus": 1}
)
print(f"Created sensor ID: {sensor_id}")
```

### Step 4: Test Enterprise Features
```python
from app.models.unit_runtime_manager import UnitRuntimeManager

manager = UnitRuntimeManager(unit_id=1, unit_name="Test Unit")

# Test calibration
manager.calibrate_sensor(sensor_id=1, reference_value=25.0)
history = manager.get_sensor_calibration_history(sensor_id=1)
print(f"Calibration history: {len(history)} points")

# Test health monitoring
health = manager.get_sensor_health(sensor_id=1)
print(f"Health score: {health['health_score']}")

# Test anomaly detection
anomaly = manager.check_sensor_anomalies(sensor_id=1)
print(f"Is anomaly: {anomaly['is_anomaly']}")
```

## Performance Considerations

### Indexes Created
```sql
CREATE INDEX idx_sensor_unit ON Sensor(unit_id);
CREATE INDEX idx_sensor_type ON Sensor(sensor_type);
CREATE INDEX idx_sensorconfig_sensor ON SensorConfig(sensor_id);
CREATE INDEX idx_calibration_sensor ON SensorCalibration(sensor_id);
CREATE INDEX idx_health_sensor ON SensorHealthHistory(sensor_id);
CREATE INDEX idx_health_created ON SensorHealthHistory(created_at);
CREATE INDEX idx_anomaly_sensor ON SensorAnomaly(sensor_id);
CREATE INDEX idx_anomaly_detected ON SensorAnomaly(detected_at);
CREATE INDEX idx_reading_sensor ON SensorReading(sensor_id);
CREATE INDEX idx_reading_timestamp ON SensorReading(timestamp);
```

### Query Optimization
- `unit_id` index: Fast sensor lookup by unit
- `sensor_type` index: Filter by sensor type
- Foreign key indexes: Fast joins
- Timestamp indexes: Efficient time-range queries

## Benefits Summary

### Code Quality
✅ **No Type Mapping Needed:** Database stores data in application format
✅ **Cleaner Code:** 60 lines → 40 lines in UnitRuntimeManager
✅ **Single Source of Truth:** Protocol stored directly in database
✅ **Type Safety:** Direct enum conversion, no string mapping

### Features
✅ **Calibration Persistence:** Historical calibration tracking
✅ **Health Monitoring:** Long-term reliability analysis
✅ **Anomaly Logging:** Pattern analysis and alerting
✅ **Flexible Configuration:** JSON supports any protocol

### Database Design
✅ **Normalized Schema:** Proper separation of concerns
✅ **Scalable:** Easy to add new sensor types
✅ **Performant:** Strategic indexes on common queries
✅ **Maintainable:** Clear table relationships

### Enterprise Architecture
✅ **Aligns with DDD:** Repository pattern maintained
✅ **Separation of Concerns:** Domain logic separate from persistence
✅ **Audit Trail:** Timestamps on all tables
✅ **Data Integrity:** Foreign key constraints enforced

## Rollback Plan

If issues occur, rollback to old schema:

```sql
-- Drop new tables
DROP TABLE IF EXISTS SensorAnomaly;
DROP TABLE IF EXISTS SensorHealthHistory;
DROP TABLE IF EXISTS SensorCalibration;
DROP TABLE IF EXISTS SensorConfig;
DROP TABLE IF EXISTS SensorReading;
DROP TABLE IF EXISTS Sensor;

-- Restore old tables
ALTER TABLE Sensor_OLD RENAME TO Sensor;
ALTER TABLE SensorReading_OLD RENAME TO SensorReading;
```

**Note:** Restore application code to previous version if needed.

## Support

For issues or questions:
1. Check verification queries to compare old vs new data
2. Review application logs for database errors
3. Test with small dataset first
4. Keep old tables for manual verification

## Next Steps

After successful migration:
1. Run comprehensive testing on all sensor operations
2. Monitor application logs for database errors
3. Verify all enterprise features work (calibration, health, anomalies)
4. Update any external tools/scripts that access the database directly
5. Document any custom migration steps for production deployment
