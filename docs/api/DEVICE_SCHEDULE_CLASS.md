# DeviceSchedule Dataclass Documentation

## Overview

The `DeviceSchedule` dataclass provides a type-safe, validated way to manage device schedules in growth units. It supports any device type (lights, fans, heaters, extractors, pumps, etc.) with start/end times and enable/disable functionality.

## Features

✅ **Type-safe** - Dataclass with proper typing
✅ **Validation** - Built-in time format validation
✅ **Time checking** - Check if device should be active at any given time
✅ **Midnight crossing** - Handles schedules that span midnight (e.g., 22:00 - 06:00)
✅ **Enable/disable** - Toggle schedules without deleting them
✅ **JSON compatible** - Serializes to/from JSON for database storage

## Class Definition

```python
@dataclass
class DeviceSchedule:
    device_type: str      # e.g., 'light', 'fan', 'heater', 'extractor', 'pump'
    start_time: str       # HH:MM format (24-hour)
    end_time: str         # HH:MM format (24-hour)
    enabled: bool = True  # Whether this schedule is active
```

## Methods

### `to_dict() -> Dict[str, Any]`
Serialize to dictionary for JSON storage.

```python
schedule = DeviceSchedule("fan", "09:00", "19:00", enabled=True)
schedule_dict = schedule.to_dict()
# {'device_type': 'fan', 'start_time': '09:00', 'end_time': '19:00', 'enabled': True}
```

### `from_dict(data: Dict[str, Any]) -> Optional[DeviceSchedule]`
Deserialize from dictionary. Returns `None` if data is invalid.

```python
data = {'device_type': 'fan', 'start_time': '09:00', 'end_time': '19:00', 'enabled': True}
schedule = DeviceSchedule.from_dict(data)
```

### `is_active_at(current_time: str) -> bool`
Check if device should be active at given time.

```python
schedule = DeviceSchedule("fan", "09:00", "19:00")

schedule.is_active_at("08:00")  # False - before start
schedule.is_active_at("12:00")  # True - during schedule
schedule.is_active_at("20:00")  # False - after end
```

**Handles midnight crossing:**
```python
night_schedule = DeviceSchedule("heater", "22:00", "06:00")

night_schedule.is_active_at("23:00")  # True
night_schedule.is_active_at("02:00")  # True
night_schedule.is_active_at("10:00")  # False
```

**Respects enabled flag:**
```python
disabled = DeviceSchedule("pump", "10:00", "16:00", enabled=False)
disabled.is_active_at("12:00")  # False - schedule is disabled
```

### `validate() -> bool`
Validate the schedule configuration.

```python
valid = DeviceSchedule("fan", "09:00", "17:00")
valid.validate()  # True

invalid = DeviceSchedule("fan", "25:00", "17:00")
invalid.validate()  # False - invalid time

empty = DeviceSchedule("", "09:00", "17:00")
empty.validate()  # False - no device type
```

## Usage Examples

### Basic Creation

```python
# Create a fan schedule (9am - 5pm)
fan_schedule = DeviceSchedule(
    device_type="fan",
    start_time="09:00",
    end_time="17:00",
    enabled=True
)

# Create a light schedule with default enabled=True
light_schedule = DeviceSchedule(
    device_type="light",
    start_time="08:00",
    end_time="20:00"
)
```

### Integration with UnitSettings

```python
from grow_room.unit_runtime import UnitSettings, DeviceSchedule

settings = UnitSettings()

# Set schedule using helper method
settings.set_device_schedule("fan", "09:00", "19:00", enabled=True)

# Or set from DeviceSchedule object
schedule = DeviceSchedule("heater", "06:00", "22:00")
settings.set_device_schedule_from_object(schedule)

# Get schedule as DeviceSchedule object
fan_schedule = settings.get_device_schedule_object("fan")
if fan_schedule and fan_schedule.is_active_at("12:00"):
    print("Fan should be running!")

# Get all schedules
all_schedules = settings.get_all_schedules()
for schedule in all_schedules:
    print(f"{schedule.device_type}: {schedule.start_time} - {schedule.end_time}")

# Get active devices at specific time
active_devices = settings.get_active_devices_at("12:00")
print(f"Active at noon: {active_devices}")
```

### Database Storage

```python
# Store in database (as part of UnitSettings)
settings_dict = settings.to_dict()
# settings_dict['device_schedules'] is a JSON string

# Load from database
settings = UnitSettings.from_dict(db_row)
# Automatically deserializes device_schedules from JSON
```

### Time-based Control

```python
from datetime import datetime

# Get current time
current_time = datetime.now().strftime("%H:%M")

# Check which devices should be active
for schedule in settings.get_all_schedules():
    if schedule.is_active_at(current_time):
        print(f"✅ {schedule.device_type} should be ON")
    else:
        print(f"⏸️  {schedule.device_type} should be OFF")
```

### Validation Before Saving

```python
schedule = DeviceSchedule("fan", start_time, end_time)

if schedule.validate():
    settings.set_device_schedule_from_object(schedule)
    print("✅ Schedule saved")
else:
    print("❌ Invalid schedule")
```

## Time Format

**Required format:** `HH:MM` (24-hour format)

**Valid examples:**
- `00:00` - Midnight
- `09:00` - 9 AM
- `12:00` - Noon
- `17:30` - 5:30 PM
- `23:59` - 11:59 PM

**Invalid examples:**
- `9:00` - ❌ Missing leading zero (actually valid in Python, but inconsistent)
- `25:00` - ❌ Invalid hour
- `12:60` - ❌ Invalid minute
- `9am` - ❌ Wrong format
- `5pm` - ❌ Wrong format

## Storage Format

Device schedules are stored as JSON in the database:

```json
{
  "light": {
    "start_time": "08:00",
    "end_time": "20:00",
    "enabled": true
  },
  "fan": {
    "start_time": "09:00",
    "end_time": "19:00",
    "enabled": true
  },
  "heater": {
    "start_time": "22:00",
    "end_time": "06:00",
    "enabled": false
  }
}
```

## API Integration

### Creating/Updating Schedules via API

```python
# In your API route
from grow_room.unit_runtime import DeviceSchedule

@app.route('/units/<unit_id>/schedules', methods=['POST'])
def set_schedule(unit_id):
    data = request.json
    
    # Create DeviceSchedule from API data
    schedule = DeviceSchedule(
        device_type=data['device_type'],
        start_time=data['start_time'],
        end_time=data['end_time'],
        enabled=data.get('enabled', True)
    )
    
    # Validate before saving
    if not schedule.validate():
        return {"error": "Invalid schedule"}, 400
    
    # Get unit and update schedule
    unit = growth_service.get_unit(unit_id)
    unit.settings.set_device_schedule_from_object(schedule)
    
    return {"message": "Schedule updated"}, 200
```

### Getting Schedules via API

```python
@app.route('/units/<unit_id>/schedules', methods=['GET'])
def get_schedules(unit_id):
    unit = growth_service.get_unit(unit_id)
    
    # Get all schedules as objects
    schedules = unit.settings.get_all_schedules()
    
    # Serialize for API response
    return {
        "schedules": [s.to_dict() for s in schedules]
    }, 200

@app.route('/units/<unit_id>/schedules/active', methods=['GET'])
def get_active_devices(unit_id):
    current_time = request.args.get('time', datetime.now().strftime("%H:%M"))
    unit = growth_service.get_unit(unit_id)
    
    active_devices = unit.settings.get_active_devices_at(current_time)
    
    return {
        "time": current_time,
        "active_devices": active_devices
    }, 200
```

## Testing

Run comprehensive tests:
```bash
python test_device_schedule_class.py
```

Tests cover:
- ✅ Basic creation
- ✅ Serialization/deserialization
- ✅ Validation
- ✅ Time checking (including midnight crossing)
- ✅ Edge cases
- ✅ JSON storage compatibility

## Migration from Legacy System

Old code with separate `light_start_time`/`light_end_time` automatically migrates to `device_schedules["light"]`:

```python
# Legacy data
legacy_data = {
    'light_start_time': '08:00',
    'light_end_time': '20:00'
}

# Automatically converts to:
settings = UnitSettings.from_dict(legacy_data)
light_schedule = settings.get_device_schedule_object("light")
# DeviceSchedule(device_type='light', start_time='08:00', end_time='20:00', enabled=True)
```

## Best Practices

1. **Always validate** before saving schedules
2. **Use DeviceSchedule objects** for type safety in your code
3. **Store as JSON** in the database for flexibility
4. **Check enabled flag** before using `is_active_at()`
5. **Handle None returns** from `get_device_schedule_object()`
6. **Use consistent device_type names** across your application

## Common Patterns

### Temporary Disable

```python
# Disable schedule without deleting it
schedule = settings.get_device_schedule_object("fan")
if schedule:
    schedule.enabled = False
    settings.set_device_schedule_from_object(schedule)
```

### Bulk Schedule Management

```python
# Set schedules for multiple devices
devices = [
    ("light", "08:00", "20:00"),
    ("fan", "09:00", "19:00"),
    ("heater", "06:00", "22:00"),
]

for device_type, start, end in devices:
    settings.set_device_schedule(device_type, start, end)
```

### Daily Schedule Report

```python
from datetime import datetime, timedelta

# Generate 24-hour schedule report
current = datetime.strptime("00:00", "%H:%M")
for hour in range(24):
    time_str = current.strftime("%H:%M")
    active = settings.get_active_devices_at(time_str)
    print(f"{time_str}: {', '.join(active) if active else 'No devices'}")
    current += timedelta(hours=1)
```

---

**Status**: ✅ PRODUCTION READY
**Version**: 1.0
**Last Updated**: November 2025
