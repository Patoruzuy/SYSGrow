# Device Schedules Migration - Complete ✅

## Summary

Successfully migrated from hardcoded `light_start_time`/`light_end_time` fields to flexible JSON-based `device_schedules` system. This allows storing schedules for ANY device (lights, fans, heaters, extractors, etc.) without schema changes.

## Changes Made

### 1. **UnitSettings Dataclass** (`grow_room/unit_runtime.py`)
- ✅ **Removed** deprecated fields:
  - `light_start_time: str = "08:00"` 
  - `light_end_time: str = "20:00"`
- ✅ **Added** flexible device schedules:
  ```python
  device_schedules: Optional[Dict[str, Dict[str, str]]] = None
  # Format: {"device_type": {"start_time": "HH:MM", "end_time": "HH:MM"}}
  ```
- ✅ **Added** helper methods:
  - `get_device_schedule(device_type)` - Retrieve schedule
  - `set_device_schedule(device_type, start, end)` - Set/update schedule
  - `remove_device_schedule(device_type)` - Remove schedule

### 2. **Dimensions Storage** (`grow_room/unit_runtime.py`)
- ✅ **Fixed** serialization: `dimensions` now serializes to JSON string (not dict)
- ✅ **Fixed** deserialization: Parses JSON string back to `UnitDimensions` object
- ✅ **Migration support**: Auto-migrates legacy `light_start_time`/`light_end_time` to `device_schedules`

### 3. **Database Schema** (`infrastructure/database/sqlite_handler.py`)
```sql
CREATE TABLE IF NOT EXISTS GrowthUnits (
    -- ... other fields ...
    device_schedules TEXT,              -- NEW: JSON storage for all device schedules
    light_start_time TEXT DEFAULT "08:00",  -- Deprecated but kept for backward compatibility
    light_end_time TEXT DEFAULT "20:00",    -- Deprecated but kept for backward compatibility
    -- ... other fields ...
)
```

### 4. **Database Operations** (`infrastructure/database/ops/growth.py`)
- ✅ **Updated** `insert_growth_unit()`: Added `device_schedules` parameter
- ✅ **Updated** `update_growth_unit_settings()`: Added support for `device_schedules` and `dimensions`
- ✅ **Updated** `update_unit_settings()`: Added support for `device_schedules` and `dimensions`

### 5. **Repository Layer** (`infrastructure/database/repositories/growth.py`)
- ✅ **Updated** `create_unit()`: Added `device_schedules` parameter with documentation

### 6. **Unit Runtime** (`grow_room/unit_runtime.py`)
- ✅ **Updated** `set_device_schedule()`: Now uses helper method and works with any device type

## Usage Examples

### Setting Device Schedules
```python
# Create unit settings with multiple device schedules
settings = UnitSettings(
    temperature_threshold=25.0,
    device_schedules={
        "light": {"start_time": "08:00", "end_time": "20:00"},
        "fan": {"start_time": "09:00", "end_time": "19:00"},
        "heater": {"start_time": "06:00", "end_time": "22:00"}
    }
)

# Or use helper methods
settings.set_device_schedule("extractor", "10:00", "18:00")
fan_schedule = settings.get_device_schedule("fan")
settings.remove_device_schedule("heater")
```

### Database Storage
```python
# Serialize for database (JSON string)
settings_dict = settings.to_dict()
# device_schedules: '{"light": {"start_time": "08:00", "end_time": "20:00"}, ...}'

# Deserialize from database
restored = UnitSettings.from_dict(settings_dict)
# device_schedules: {'light': {'start_time': '08:00', 'end_time': '20:00'}, ...}
```

### Legacy Migration
```python
# Old data with separate fields automatically migrates
legacy_data = {
    'light_start_time': '07:00',
    'light_end_time': '21:00'
}

settings = UnitSettings.from_dict(legacy_data)
# Automatically creates: device_schedules = {"light": {"start_time": "07:00", "end_time": "21:00"}}
```

## Benefits

1. **Flexibility** - Add/remove device schedules without schema changes
2. **Type Safety** - JSON validated through Python dataclass
3. **Backward Compatible** - Legacy fields kept in database, auto-migration on load
4. **Clean API** - Helper methods for common operations
5. **Tested** - All scenarios validated with comprehensive test suite

## Database Columns

| Column | Type | Purpose | Status |
|--------|------|---------|--------|
| `device_schedules` | TEXT | JSON storage for all device schedules | ✅ New (recommended) |
| `dimensions` | TEXT | JSON storage for unit dimensions | ✅ Fixed serialization |
| `light_start_time` | TEXT | Legacy light schedule start | ⚠️ Deprecated |
| `light_end_time` | TEXT | Legacy light schedule end | ⚠️ Deprecated |

## Testing

✅ All tests passed:
- Device schedules serialize/deserialize correctly
- Dimensions serialize/deserialize correctly
- Helper methods work as expected
- Legacy migration works automatically
- NULL/missing values handled properly

Run tests: `python test_device_schedules.py`

## Migration Path

**For existing users:**
1. Old data with `light_start_time`/`light_end_time` continues to work
2. On first load, automatically migrates to `device_schedules["light"]`
3. New updates use `device_schedules` field
4. Can gradually phase out deprecated fields in future version

**For new users:**
- Use `device_schedules` from the start
- Set schedules for any device type
- No legacy fields needed

## Next Steps

1. Update API endpoints to accept `device_schedules` parameter ✅
2. Update frontend to support multiple device schedules
3. Add validation for time format (HH:MM)
4. Consider adding timezone support
5. Add device type enum/validation

---

**Status**: ✅ COMPLETE AND TESTED
**Backward Compatible**: ✅ YES
**Ready for Production**: ✅ YES
