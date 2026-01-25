# Device Schedules Update Documentation

## Overview
Updated `SettingsOperations` class to use the unified `device_schedules` JSON field in the `GrowthUnits` table instead of separate schedule columns in the `Settings` table.

## Changes Made

### ✅ New Unified Methods (Recommended)

#### `save_device_schedule(unit_id, device_type, start_time, end_time, enabled=True)`
Save or update a device schedule in the device_schedules JSON field.

**Parameters:**
- `unit_id` (int): Growth unit ID
- `device_type` (str): Device type (e.g., 'light', 'fan', 'pump', 'heater')
- `start_time` (str): Start time in HH:MM format
- `end_time` (str): End time in HH:MM format
- `enabled` (bool): Whether the schedule is enabled (default: True)

**Returns:** `bool` - True if successful, False otherwise

**Example:**
```python
db = SQLiteDatabaseHandler("sysgrow.db")

# Save light schedule
success = db.save_device_schedule(
    unit_id=1,
    device_type="light",
    start_time="06:00",
    end_time="22:00",
    enabled=True
)
```

---

#### `get_device_schedule(unit_id, device_type)`
Get a specific device schedule from the device_schedules JSON field.

**Parameters:**
- `unit_id` (int): Growth unit ID
- `device_type` (str): Device type (e.g., 'light', 'fan')

**Returns:** `Optional[Dict[str, Any]]` - Schedule dict or None if not found

**Example:**
```python
# Get light schedule
schedule = db.get_device_schedule(unit_id=1, device_type="light")
if schedule:
    print(f"Light: {schedule['start_time']} - {schedule['end_time']}")
    print(f"Enabled: {schedule['enabled']}")
```

**Response:**
```json
{
    "start_time": "06:00",
    "end_time": "22:00",
    "enabled": true
}
```

---

#### `get_all_device_schedules(unit_id)`
Get all device schedules for a growth unit.

**Parameters:**
- `unit_id` (int): Growth unit ID

**Returns:** `Dict[str, Dict[str, Any]]` - Dictionary of all device schedules

**Example:**
```python
# Get all schedules for unit 1
all_schedules = db.get_all_device_schedules(unit_id=1)

for device_type, schedule in all_schedules.items():
    print(f"{device_type}: {schedule['start_time']} - {schedule['end_time']}")
```

**Response:**
```json
{
    "light": {
        "start_time": "06:00",
        "end_time": "22:00",
        "enabled": true
    },
    "fan": {
        "start_time": "08:00",
        "end_time": "20:00",
        "enabled": true
    },
    "pump": {
        "start_time": "09:00",
        "end_time": "18:00",
        "enabled": false
    }
}
```

---

#### `update_device_schedule_status(unit_id, device_type, enabled)`
Enable or disable a device schedule without changing times.

**Parameters:**
- `unit_id` (int): Growth unit ID
- `device_type` (str): Device type
- `enabled` (bool): True to enable, False to disable

**Returns:** `bool` - True if successful, False otherwise

**Example:**
```python
# Disable light schedule temporarily
success = db.update_device_schedule_status(
    unit_id=1,
    device_type="light",
    enabled=False
)
```

---

#### `delete_device_schedule(unit_id, device_type)`
Delete a specific device schedule from the device_schedules JSON field.

**Parameters:**
- `unit_id` (int): Growth unit ID
- `device_type` (str): Device type to remove

**Returns:** `bool` - True if successful, False otherwise

**Example:**
```python
# Remove pump schedule
success = db.delete_device_schedule(unit_id=1, device_type="pump")
```

---

### ⚠️ Deprecated Methods (Backward Compatibility)

The following methods are **DEPRECATED** but still functional for backward compatibility:

#### `save_light_schedule(start_time, end_time)` ⚠️ DEPRECATED
Use `save_device_schedule(unit_id, "light", start_time, end_time)` instead.

#### `get_light_schedule()` ⚠️ DEPRECATED
Use `get_device_schedule(unit_id, "light")` instead.

#### `save_fan_schedule(start_time, end_time)` ⚠️ DEPRECATED
Use `save_device_schedule(unit_id, "fan", start_time, end_time)` instead.

#### `get_fan_schedule()` ⚠️ DEPRECATED
Use `get_device_schedule(unit_id, "fan")` instead.

**Note:** These deprecated methods work with the legacy `Settings` table which is not unit-specific. **Use the new unified methods for all new code.**

---

## Database Schema

### GrowthUnits Table
The `device_schedules` field stores all device schedules as JSON:

```sql
CREATE TABLE GrowthUnits (
    unit_id INTEGER PRIMARY KEY AUTOINCREMENT,
    ...
    device_schedules TEXT,  -- JSON field for all device schedules
    ...
)
```

### JSON Structure
```json
{
    "light": {
        "start_time": "06:00",
        "end_time": "22:00",
        "enabled": true
    },
    "fan": {
        "start_time": "08:00",
        "end_time": "20:00",
        "enabled": true
    },
    "pump": {
        "start_time": "09:00",
        "end_time": "18:00",
        "enabled": false
    },
    "heater": {
        "start_time": "00:00",
        "end_time": "06:00",
        "enabled": true
    }
}
```

---

## Migration Guide

### Old Code (Deprecated)
```python
# Old way - Settings table (global, not unit-specific)
db.save_light_schedule("06:00", "22:00")
db.save_fan_schedule("08:00", "20:00")

light_schedule = db.get_light_schedule()
fan_schedule = db.get_fan_schedule()
```

### New Code (Recommended)
```python
# New way - GrowthUnits table (unit-specific)
db.save_device_schedule(unit_id=1, device_type="light", 
                       start_time="06:00", end_time="22:00", enabled=True)
db.save_device_schedule(unit_id=1, device_type="fan",
                       start_time="08:00", end_time="20:00", enabled=True)

light_schedule = db.get_device_schedule(unit_id=1, device_type="light")
fan_schedule = db.get_device_schedule(unit_id=1, device_type="fan")

# Or get all schedules at once
all_schedules = db.get_all_device_schedules(unit_id=1)
```

---

## Benefits of New Approach

### 1. **Unit-Specific Schedules**
Each growth unit can have its own device schedules instead of global settings.

### 2. **Extensible**
Easy to add new device types (pump, heater, humidifier, etc.) without schema changes.

### 3. **Enable/Disable Support**
Can temporarily disable schedules without deleting them.

### 4. **Simplified API**
Single unified interface for all device types instead of separate methods.

### 5. **JSON Flexibility**
Can add additional properties (duration, interval, etc.) to schedules in the future.

---

## Common Use Cases

### 1. Set Up Multiple Device Schedules
```python
# Configure all devices for a grow unit
devices = [
    ("light", "06:00", "22:00", True),
    ("fan", "08:00", "20:00", True),
    ("pump", "09:00", "18:00", True),
    ("heater", "00:00", "06:00", False),  # Disabled for summer
]

for device_type, start, end, enabled in devices:
    db.save_device_schedule(
        unit_id=1,
        device_type=device_type,
        start_time=start,
        end_time=end,
        enabled=enabled
    )
```

### 2. Get All Schedules for Display
```python
# Display all schedules in UI
schedules = db.get_all_device_schedules(unit_id=1)

for device_type, schedule in schedules.items():
    status = "ON" if schedule['enabled'] else "OFF"
    print(f"{device_type.upper()}: {schedule['start_time']} - {schedule['end_time']} [{status}]")
```

### 3. Temporarily Disable Device
```python
# Disable fan during maintenance
db.update_device_schedule_status(unit_id=1, device_type="fan", enabled=False)

# ... perform maintenance ...

# Re-enable fan
db.update_device_schedule_status(unit_id=1, device_type="fan", enabled=True)
```

### 4. Update Schedule Times
```python
# Change light schedule for different season
db.save_device_schedule(
    unit_id=1,
    device_type="light",
    start_time="07:00",  # Start later in winter
    end_time="20:00",    # End earlier
    enabled=True
)
```

### 5. Check if Schedule is Active
```python
from datetime import datetime

def is_device_active(unit_id: int, device_type: str) -> bool:
    """Check if a device should be running based on schedule"""
    schedule = db.get_device_schedule(unit_id, device_type)
    
    if not schedule or not schedule['enabled']:
        return False
    
    now = datetime.now().time()
    start = datetime.strptime(schedule['start_time'], "%H:%M").time()
    end = datetime.strptime(schedule['end_time'], "%H:%M").time()
    
    if start <= end:
        return start <= now <= end
    else:  # Crosses midnight
        return now >= start or now <= end

# Usage
if is_device_active(unit_id=1, device_type="light"):
    print("Light should be ON")
else:
    print("Light should be OFF")
```

---

## Testing

All new methods have been tested and verified:

```bash
python test_device_schedule_methods.py
```

**Test Results:**
- ✅ Save device schedules
- ✅ Get specific device schedule
- ✅ Get all device schedules
- ✅ Update schedule status (enable/disable)
- ✅ Delete device schedule
- ✅ Update existing schedule times
- ✅ Backward compatibility with deprecated methods

---

## Files Modified

### Updated
- `infrastructure/database/ops/settings.py` - Added 5 new unified methods, marked 4 methods as deprecated

### Created
- `test_device_schedule_methods.py` - Comprehensive test suite
- `docs/DEVICE_SCHEDULES_UPDATE.md` - This documentation

---

## Summary

✅ **New unified device schedule methods** working perfectly  
✅ **Supports multiple device types** (light, fan, pump, heater, etc.)  
✅ **Unit-specific schedules** (each growth unit has its own)  
✅ **Enable/disable support** without losing schedule data  
✅ **Backward compatibility** maintained for existing code  
✅ **Comprehensive testing** - all tests passing  

**Recommendation:** Update all code to use the new `device_schedules` methods instead of the deprecated individual schedule methods.
