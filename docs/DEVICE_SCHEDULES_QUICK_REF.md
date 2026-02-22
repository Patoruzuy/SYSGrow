# Device Schedules Quick Reference

## Import
```python
from infrastructure.database.sqlite_handler import SQLiteDatabaseHandler
db = SQLiteDatabaseHandler("sysgrow.db")
```

## Save Schedule
```python
db.save_device_schedule(
    unit_id=1,
    device_type="light",
    start_time="06:00",
    end_time="22:00",
    enabled=True
)
```

## Get Single Schedule
```python
schedule = db.get_device_schedule(unit_id=1, device_type="light")
# Returns: {"start_time": "06:00", "end_time": "22:00", "enabled": True}
```

## Get All Schedules
```python
all_schedules = db.get_all_device_schedules(unit_id=1)
# Returns: {
#     "light": {"start_time": "06:00", "end_time": "22:00", "enabled": True},
#     "fan": {"start_time": "08:00", "end_time": "20:00", "enabled": True}
# }
```

## Enable/Disable Schedule
```python
db.update_device_schedule_status(unit_id=1, device_type="fan", enabled=False)
```

## Delete Schedule
```python
db.delete_device_schedule(unit_id=1, device_type="pump")
```

## Supported Device Types
- `light` - Grow lights
- `fan` - Ventilation fans
- `pump` - Water pumps
- `heater` - Heating systems
- `humidifier` - Humidity control
- `dehumidifier` - Dehumidification
- `co2` - CO2 injection
- Any custom device type

## Complete Example
```python
# Set up multiple devices
devices = [
    ("light", "06:00", "22:00", True),
    ("fan", "08:00", "20:00", True),
    ("pump", "09:00", "18:00", False),
]

for device_type, start, end, enabled in devices:
    db.save_device_schedule(1, device_type, start, end, enabled)

# Get all schedules
schedules = db.get_all_device_schedules(unit_id=1)

# Display schedules
for device, schedule in schedules.items():
    status = "ON" if schedule['enabled'] else "OFF"
    print(f"{device}: {schedule['start_time']}-{schedule['end_time']} [{status}]")
```

## ⚠️ Deprecated Methods (Don't Use)
- `save_light_schedule()` → Use `save_device_schedule(unit_id, "light", ...)`
- `get_light_schedule()` → Use `get_device_schedule(unit_id, "light")`
- `save_fan_schedule()` → Use `save_device_schedule(unit_id, "fan", ...)`
- `get_fan_schedule()` → Use `get_device_schedule(unit_id, "fan")`
