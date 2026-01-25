# Sensor Management Quick Reference

## Memory-First Architecture Pattern

### Core Concept
**Objects live in memory (single source of truth)**  
**Database is only for persistence (load once, explicit saves)**

---

## Common Operations

### 1. Creating a New Sensor

#### ❌ WRONG - Old Way
```python
# Creates in DB but NOT in memory
sensor_id = repo_devices.create_sensor(
    unit_id=1,
    sensor_type='TEMPERATURE',
    config={'pin_number': 4}
)
# ❌ Sensor NOT available until manager restarts!
```

#### ✅ CORRECT - New Way
```python
# Step 1: Create in database
sensor_id = repo_devices.create_sensor(
    unit_id=1,
    sensor_type='TEMPERATURE',
    config={'pin_number': 4}
)

# Step 2: Register in memory (REQUIRED!)
manager.register_new_sensor(
    sensor_id=sensor_id,
    sensor_type='TEMPERATURE',
    config={'pin_number': 4}
)

# ✅ Sensor immediately available!
reading = manager.sensor_manager.read_sensor(sensor_id)
```

---

### 2. Deleting a Sensor

#### ❌ WRONG - Old Way
```python
# Deletes from DB but leaves in memory
repo_devices.delete_sensor(sensor_id)
# ❌ Sensor still accessible in memory! (stale data)
```

#### ✅ CORRECT - New Way
```python
# Step 1: Delete from database
repo_devices.delete_sensor(sensor_id)

# Step 2: Unregister from memory (REQUIRED!)
manager.unregister_sensor(sensor_id)

# ✅ Sensor immediately removed from memory!
sensor = manager.get_sensor(sensor_id)  # Returns None
```

---

### 3. Reading Sensor Data

#### ✅ No Changes Required
```python
# Get sensor (lazy loads if needed)
sensor = manager.get_sensor(sensor_id)

# Read current value
reading = manager.sensor_manager.read_sensor(sensor_id)

# Get health
health = manager.get_sensor_health(sensor_id)

# Check anomalies
anomalies = manager.check_sensor_anomalies(sensor_id)
```

---

### 4. Calibrating a Sensor

```python
result = manager.calibrate_sensor(
    sensor_id=1,
    reference_value=25.0,  # Known correct value
    calibration_type='linear'  # or 'polynomial', 'lookup'
)

if result['success']:
    print(f"Calibrated! ID: {result['calibration_id']}")
else:
    print(f"Failed: {result['error']} ({result['error_type']})")
```

**Returns:**
```python
{
    "success": True,
    "sensor_id": 1,
    "measured_value": 24.8,
    "reference_value": 25.0,
    "calibration_type": "linear",
    "calibration_id": 42
}
```

---

### 5. Checking Sensor Health

```python
health = manager.get_sensor_health(sensor_id=1)

if health['success']:
    print(f"Health Score: {health['health_score']:.2f}")
    print(f"Status: {health['status']}")
    print(f"Error Rate: {health['error_rate']:.2%}")
else:
    print(f"Failed: {health['error']}")
```

**Returns:**
```python
{
    "success": True,
    "sensor_id": 1,
    "health_score": 0.95,  # 0-1 scale
    "status": "healthy",
    "last_reading": "2024-01-15T10:30:00",
    "error_rate": 0.02,
    "is_available": True
}
```

---

### 6. Detecting Anomalies

```python
result = manager.check_sensor_anomalies(sensor_id=1)

if result['success'] and result['is_anomaly']:
    print(f"⚠️ Anomaly detected!")
    print(f"Current: {result['current_value']}")
    print(f"Mean: {result['mean']}")
    print(f"Std Dev: {result['std_dev']}")
```

**Returns:**
```python
{
    "success": True,
    "sensor_id": 1,
    "is_anomaly": True,
    "current_value": 35.5,
    "mean": 24.2,
    "std_dev": 1.5,
    "min": 22.0,
    "max": 26.5,
    "count": 1000,
    "threshold": 3.0
}
```

---

### 7. Getting Statistics

```python
stats = manager.get_sensor_statistics(sensor_id=1)

if stats['success']:
    print(f"Mean: {stats['mean']:.2f}")
    print(f"Min: {stats['min']:.2f}")
    print(f"Max: {stats['max']:.2f}")
    print(f"Readings: {stats['count']}")
```

**Returns:**
```python
{
    "success": True,
    "sensor_id": 1,
    "mean": 24.5,
    "std_dev": 1.2,
    "min": 22.0,
    "max": 27.5,
    "count": 1500
}
```

---

### 8. Force Reload from Database

```python
# Clear cache and reload all sensors
manager.reload_sensors()

# All sensors reloaded from database
# Use when database was modified externally
```

---

### 9. Discovering MQTT Sensors

```python
discovered = manager.discover_mqtt_sensors(
    mqtt_topic_prefix="growtent"
)

print(f"Found {len(discovered)} sensors:")
for sensor in discovered:
    print(f"  - {sensor['model']} ({sensor['sensor_type']})")
    print(f"    Interface: {sensor['interface']}")
    print(f"    Address: {sensor['address']}")
```

---

### 10. Getting History

#### Calibration History
```python
history = manager.get_sensor_calibration_history(
    sensor_id=1,
    limit=20  # Last 20 calibrations
)

for cal in history:
    print(f"{cal['timestamp']}: {cal['reference_value']}°C")
```

#### Health History
```python
history = manager.get_sensor_health_history(
    sensor_id=1,
    limit=100  # Last 100 snapshots
)

for snapshot in history:
    print(f"{snapshot['timestamp']}: {snapshot['health_score']}")
```

#### Anomaly History
```python
history = manager.get_sensor_anomaly_history(
    sensor_id=1,
    limit=50  # Last 50 anomalies
)

for anomaly in history:
    print(f"{anomaly['timestamp']}: {anomaly['value']} (z={anomaly['z_score']})")
```

---

## Error Handling

### All Methods Return Structured Errors

```python
result = manager.some_sensor_operation(sensor_id=999)

if not result.get('success', True):
    error_type = result.get('error_type')
    
    if error_type == 'validation':
        print(f"Invalid input: {result['error']}")
    elif error_type == 'not_found':
        print(f"Sensor not found: {result['error']}")
    elif error_type == 'read_error':
        print(f"Failed to read sensor: {result['error']}")
    elif error_type == 'runtime':
        print(f"Runtime error: {result['error']}")
```

### Error Types
- **`validation`**: Invalid input parameters
- **`not_found`**: Sensor doesn't exist
- **`read_error`**: Failed to read sensor value
- **`no_data`**: No data available (statistics, health)
- **`runtime`**: Unexpected runtime error

---

## API Endpoint Patterns

### POST /sensors (Create)
```python
@app.post("/sensors")
def create_sensor(sensor_data: SensorCreate):
    try:
        # 1. Validate input
        if not sensor_data.sensor_type:
            raise ValueError("sensor_type required")
        
        # 2. Create in database
        sensor_id = repo_devices.create_sensor(
            unit_id=sensor_data.unit_id,
            sensor_type=sensor_data.sensor_type,
            config=sensor_data.config
        )
        
        # 3. Register in memory (REQUIRED!)
        manager.register_new_sensor(
            sensor_id=sensor_id,
            sensor_type=sensor_data.sensor_type,
            config=sensor_data.config
        )
        
        # 4. Return response
        return {
            "success": True,
            "sensor_id": sensor_id
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
```

### DELETE /sensors/{sensor_id}
```python
@app.delete("/sensors/{sensor_id}")
def delete_sensor(sensor_id: int):
    try:
        # 1. Validate sensor exists
        sensor = manager.get_sensor(sensor_id)
        if not sensor:
            raise ValueError(f"Sensor {sensor_id} not found")
        
        # 2. Delete from database
        repo_devices.delete_sensor(sensor_id)
        
        # 3. Unregister from memory (REQUIRED!)
        manager.unregister_sensor(sensor_id)
        
        # 4. Return response
        return {
            "success": True,
            "message": f"Sensor {sensor_id} deleted"
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
```

### PUT /sensors/{sensor_id} (Update)
```python
@app.put("/sensors/{sensor_id}")
def update_sensor(sensor_id: int, updates: SensorUpdate):
    try:
        # 1. Update in database
        repo_devices.update_sensor(sensor_id, updates)
        
        # 2. Reload from database to sync memory
        manager.reload_sensors()
        
        # 3. Return response
        return {
            "success": True,
            "sensor_id": sensor_id
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
```

---

## Service Layer Patterns

### GrowthService Example
```python
class GrowthService:
    def add_sensor_to_unit(self, unit_id: int, sensor_data: dict):
        # 1. Create in database
        sensor_id = self.repo.create_sensor(
            unit_id=unit_id,
            sensor_type=sensor_data['sensor_type'],
            config=sensor_data['config']
        )
        
        # 2. Get unit manager
        manager = self.get_unit_manager(unit_id)
        
        # 3. Register in memory (REQUIRED!)
        manager.register_new_sensor(
            sensor_id=sensor_id,
            sensor_type=sensor_data['sensor_type'],
            config=sensor_data['config']
        )
        
        return sensor_id
    
    def remove_sensor_from_unit(self, unit_id: int, sensor_id: int):
        # 1. Delete from database
        self.repo.delete_sensor(sensor_id)
        
        # 2. Get unit manager
        manager = self.get_unit_manager(unit_id)
        
        # 3. Unregister from memory (REQUIRED!)
        manager.unregister_sensor(sensor_id)
```

---

## Testing Patterns

### Unit Test Example
```python
def test_register_new_sensor():
    """Test explicit sensor registration."""
    # Arrange
    manager = UnitRuntimeManager(...)
    sensor_id = 1
    sensor_type = 'TEMPERATURE'
    config = {'pin_number': 4}
    
    # Act
    manager.register_new_sensor(sensor_id, sensor_type, config)
    
    # Assert
    sensor = manager.get_sensor(sensor_id)
    assert sensor is not None
    assert sensor.sensor_type == 'TEMPERATURE'
```

### Integration Test Example
```python
def test_create_and_read_sensor():
    """Test full create workflow."""
    # 1. Create in database
    sensor_id = repo.create_sensor(
        unit_id=1,
        sensor_type='TEMPERATURE',
        config={'pin_number': 4}
    )
    
    # 2. Register in memory
    manager.register_new_sensor(sensor_id, 'TEMPERATURE', {'pin_number': 4})
    
    # 3. Verify accessible
    sensor = manager.get_sensor(sensor_id)
    assert sensor is not None
    
    # 4. Read value
    reading = manager.sensor_manager.read_sensor(sensor_id)
    assert reading is not None
```

---

## Common Pitfalls

### ❌ WRONG: Forgetting to Register
```python
sensor_id = repo.create_sensor(...)
# ❌ Forgot to call register_new_sensor!
reading = manager.sensor_manager.read_sensor(sensor_id)
# ERROR: Sensor not found!
```

### ❌ WRONG: Forgetting to Unregister
```python
repo.delete_sensor(sensor_id)
# ❌ Forgot to call unregister_sensor!
sensor = manager.get_sensor(sensor_id)
# Returns stale sensor from memory!
```

### ❌ WRONG: Not Checking Error Responses
```python
result = manager.calibrate_sensor(...)
# ❌ Assumes success without checking
print(result['calibration_id'])
# ERROR: KeyError if calibration failed!
```

### ✅ CORRECT: Always Check Success
```python
result = manager.calibrate_sensor(...)
if result['success']:
    print(result['calibration_id'])
else:
    print(f"Error: {result['error']}")
```

---

## Performance Tips

1. **Lazy Loading**: Sensors load on first access, not in constructor
2. **Cache**: Once loaded, sensors stay in memory (fast access)
3. **Reload**: Use `reload_sensors()` only when needed (clears cache)
4. **History Limits**: Use reasonable limits (default: 20-100) to avoid large queries

---

## Checklist for New Features

When adding a new sensor-related feature:

- [ ] Validate all inputs (sensor_id, values, types)
- [ ] Check sensor existence with `get_sensor()`
- [ ] Return structured error response `{"success": False, "error": ..., "error_type": ...}`
- [ ] Add try/except with `exc_info=True` for debugging
- [ ] Convert enums gracefully with fallbacks
- [ ] Log operations (INFO for success, ERROR for failures)
- [ ] Handle partial failures gracefully (don't fail entire operation)
- [ ] Persist important data to database (calibrations, health, anomalies)
- [ ] Document the method with clear Args and Returns

---

## Need Help?

See full documentation: `SENSOR_ARCHITECTURE_IMPROVEMENTS.md`
