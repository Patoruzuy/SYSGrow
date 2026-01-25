# API Updates Summary - Device Schedules & Complete Fields Support

## Overview
Updated Growth API endpoints and services to support all new fields including `dimensions`, `device_schedules`, `camera_enabled`, and `custom_image`. Replaced deprecated `light_start_time`/`light_end_time` with flexible device schedules.

---

## Changes Made

### 1. **GrowthService Updates** (`app/services/growth.py`)

#### ✅ Updated `create_unit()` method
- **Added parameters**: `device_schedules`, `camera_enabled`
- **Enhanced parameters**: `dimensions` now properly serialized to JSON
- **What changed**:
  ```python
  # BEFORE
  def create_unit(self, *, name: str, location: str = "Indoor", 
                  user_id: Optional[int] = None,
                  dimensions: Optional[Dict[str, float]] = None,
                  custom_image: Optional[str] = None) -> Optional[int]:
      unit_id = self.repo_growth.create_unit(name=name, location=location)  # Only 2 params
  
  # AFTER
  def create_unit(self, *, name: str, location: str = "Indoor",
                  user_id: Optional[int] = None,
                  dimensions: Optional[Dict[str, float]] = None,
                  device_schedules: Optional[Dict[str, Dict[str, Any]]] = None,
                  custom_image: Optional[str] = None,
                  camera_enabled: bool = False) -> Optional[int]:
      # Serialize to JSON strings
      dimensions_json = json.dumps(dimensions) if dimensions else None
      device_schedules_json = json.dumps(device_schedules) if device_schedules else None
      
      unit_id = self.repo_growth.create_unit(
          name=name, location=location,
          dimensions=dimensions_json,
          device_schedules=device_schedules_json,
          custom_image=custom_image,
          camera_enabled=camera_enabled
      )
  ```

#### ✅ Updated `get_thresholds()` method
- **Removed**: Deprecated `light_start_time` and `light_end_time`
- **Added**: `device_schedules`, `dimensions`, `camera_enabled`
- **What changed**:
  ```python
  # BEFORE
  return {
      "temperature_threshold": settings.temperature_threshold,
      # ... other thresholds
      "light_start_time": settings.light_start_time,  # ❌ Deprecated
      "light_end_time": settings.light_end_time,      # ❌ Deprecated
  }
  
  # AFTER
  return {
      "temperature_threshold": settings.temperature_threshold,
      # ... other thresholds
      "device_schedules": settings.device_schedules,  # ✅ New
      "dimensions": settings.dimensions,               # ✅ New
      "camera_enabled": settings.camera_enabled,       # ✅ New
  }
  ```

---

### 2. **Growth API Endpoints Updates** (`app/blueprints/api/growth.py`)

#### ✅ Updated `POST /units` - Create Unit
- **Added field extraction**: dimensions, device_schedules, custom_image, camera_enabled
- **What changed**:
  ```python
  # BEFORE
  @growth_api.post("/units")
  def create_unit():
      payload = request.get_json() or {}
      name = payload.get("name")
      location = payload.get("location", "Indoor")
      unit = _service().create_unit(name=name, location=location)  # Only 2 params
  
  # AFTER
  @growth_api.post("/units")
  def create_unit():
      payload = request.get_json() or {}
      name = payload.get("name")
      if not name:
          return _fail("name is required", 400)
      
      # Extract all supported fields
      location = payload.get("location", "Indoor")
      dimensions = payload.get("dimensions")
      device_schedules = payload.get("device_schedules")
      custom_image = payload.get("custom_image")
      camera_enabled = payload.get("camera_enabled", False)
      
      # Create unit with all fields
      unit = _service().create_unit(
          name=name,
          location=location,
          dimensions=dimensions,
          device_schedules=device_schedules,
          custom_image=custom_image,
          camera_enabled=camera_enabled
      )
  ```

#### ✅ New Device Schedule Management Endpoints

**1. GET `/units/<unit_id>/schedules` - Get All Schedules**
- Returns all device schedules for a unit
- Example response:
  ```json
  {
    "ok": true,
    "data": {
      "device_schedules": {
        "light": {
          "device_type": "light",
          "start_time": "08:00",
          "end_time": "20:00",
          "enabled": true
        },
        "fan": {
          "device_type": "fan",
          "start_time": "09:00",
          "end_time": "21:00",
          "enabled": true
        }
      }
    }
  }
  ```

**2. GET `/units/<unit_id>/schedules/<device_type>` - Get Single Schedule**
- Returns schedule for a specific device type (e.g., "light", "fan", "pump")
- Example response:
  ```json
  {
    "ok": true,
    "data": {
      "device_type": "light",
      "schedule": {
        "device_type": "light",
        "start_time": "08:00",
        "end_time": "20:00",
        "enabled": true
      }
    }
  }
  ```

**3. POST `/units/<unit_id>/schedules` - Set/Update Schedule**
- Create or update a device schedule
- Request body:
  ```json
  {
    "device_type": "fan",
    "start_time": "09:00",
    "end_time": "21:00",
    "enabled": true
  }
  ```
- Validates time format (HH:MM in 24-hour format)
- Persists to database automatically

**4. DELETE `/units/<unit_id>/schedules/<device_type>` - Remove Schedule**
- Removes a device schedule
- Returns success message

**5. GET `/units/<unit_id>/schedules/active` - Get Active Devices**
- Returns list of devices that should be active based on current time
- Handles midnight crossing (e.g., 22:00-06:00)
- Example response:
  ```json
  {
    "ok": true,
    "data": {
      "current_time": "14:30",
      "active_devices": ["light", "fan"],
      "count": 2
    }
  }
  ```

---

## API Usage Examples

### Creating a Unit with Full Configuration

```bash
# Create unit with dimensions, device schedules, and camera enabled
curl -X POST http://localhost:5000/api/v1/growth/units \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Greenhouse A",
    "location": "Greenhouse",
    "dimensions": {
      "width": 300,
      "height": 250,
      "depth": 200
    },
    "device_schedules": {
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
        "start_time": "07:00",
        "end_time": "19:00",
        "enabled": false
      }
    },
    "camera_enabled": true,
    "custom_image": "/path/to/image.jpg"
  }'
```

### Managing Device Schedules

```bash
# Get all schedules
curl http://localhost:5000/api/v1/growth/units/1/schedules

# Get specific device schedule
curl http://localhost:5000/api/v1/growth/units/1/schedules/light

# Set device schedule
curl -X POST http://localhost:5000/api/v1/growth/units/1/schedules \
  -H "Content-Type: application/json" \
  -d '{
    "device_type": "heater",
    "start_time": "22:00",
    "end_time": "06:00",
    "enabled": true
  }'

# Delete device schedule
curl -X DELETE http://localhost:5000/api/v1/growth/units/1/schedules/heater

# Get currently active devices
curl http://localhost:5000/api/v1/growth/units/1/schedules/active
```

### Getting Thresholds (Now includes device_schedules)

```bash
curl http://localhost:5000/api/v1/growth/units/1/thresholds

# Response includes:
# {
#   "temperature_threshold": 24.0,
#   "humidity_threshold": 50.0,
#   ...
#   "device_schedules": {...},
#   "dimensions": {...},
#   "camera_enabled": true
# }
```

---

## Data Models

### Unit Creation Request Body
```typescript
{
  name: string;                    // Required
  location?: string;               // Default: "Indoor"
  dimensions?: {                   // Optional
    width: number;
    height: number;
    depth: number;
  };
  device_schedules?: {             // Optional
    [device_type: string]: {
      start_time: string;          // HH:MM format
      end_time: string;            // HH:MM format
      enabled: boolean;
    }
  };
  custom_image?: string;           // Optional
  camera_enabled?: boolean;        // Default: false
}
```

### Device Schedule Object
```typescript
{
  device_type: string;             // "light", "fan", "pump", etc.
  start_time: string;              // HH:MM format (24-hour)
  end_time: string;                // HH:MM format (24-hour)
  enabled: boolean;                // Whether schedule is active
}
```

---

## Migration Notes

### Deprecated Fields
- `light_start_time` - Replaced by `device_schedules["light"]["start_time"]`
- `light_end_time` - Replaced by `device_schedules["light"]["end_time"]`

These fields are still present in the database for backward compatibility but are no longer returned by `get_thresholds()`.

### Automatic Migration
When loading a unit with legacy `light_start_time`/`light_end_time` fields:
- UnitSettings automatically creates a `device_schedules["light"]` entry
- Legacy fields are used as defaults if `device_schedules` is empty
- No manual migration required

---

## Testing

All changes have been tested:
- ✅ DeviceSchedule dataclass with validation
- ✅ UnitSettings schedule management methods
- ✅ Time checking with midnight crossing
- ✅ JSON serialization/deserialization
- ✅ Database operations (create, update, retrieve)

---

## Related Documentation
- `DEVICE_SCHEDULE_CLASS.md` - DeviceSchedule dataclass documentation
- `DEVICE_SCHEDULES_MIGRATION.md` - Migration guide from legacy fields
- `ENHANCED_FEATURES_SETUP.md` - General setup guide

---

## Next Steps

### Frontend Updates Required
1. **Unit Creation Form**
   - Add dimensions input fields (width, height, depth)
   - Add device schedule management UI
   - Add camera enabled checkbox

2. **Unit Details View**
   - Display dimensions
   - Show device schedules table
   - Add schedule management controls

3. **Schedule Management UI**
   - Create/edit schedule form
   - List all device schedules
   - Toggle enable/disable
   - Show currently active devices

### Example Frontend Form Structure
```html
<form id="create-unit">
  <input name="name" placeholder="Unit Name" required>
  <select name="location">
    <option>Indoor</option>
    <option>Outdoor</option>
    <option>Greenhouse</option>
  </select>
  
  <!-- Dimensions -->
  <fieldset>
    <legend>Dimensions (cm)</legend>
    <input name="dimensions.width" type="number" placeholder="Width">
    <input name="dimensions.height" type="number" placeholder="Height">
    <input name="dimensions.depth" type="number" placeholder="Depth">
  </fieldset>
  
  <!-- Device Schedules -->
  <fieldset id="schedules">
    <legend>Device Schedules</legend>
    <div class="schedule-row">
      <select name="device_type">
        <option>light</option>
        <option>fan</option>
        <option>pump</option>
        <option>heater</option>
      </select>
      <input name="start_time" type="time" placeholder="Start Time">
      <input name="end_time" type="time" placeholder="End Time">
      <input name="enabled" type="checkbox" checked>
      <button type="button" onclick="addScheduleRow()">+</button>
    </div>
  </fieldset>
  
  <!-- Camera -->
  <label>
    <input name="camera_enabled" type="checkbox">
    Enable Camera
  </label>
  
  <button type="submit">Create Unit</button>
</form>
```

---

## Summary

**What was updated:**
1. ✅ GrowthService.create_unit() - Now passes all fields (dimensions, device_schedules, camera_enabled)
2. ✅ GrowthService.get_thresholds() - Returns device_schedules instead of deprecated light fields
3. ✅ API POST /units - Accepts all new fields
4. ✅ Added 5 new device schedule management endpoints
5. ✅ Database already returns all fields (no changes needed)

**What's working:**
- Full CRUD operations for device schedules
- Time validation and midnight crossing support
- Automatic JSON serialization/deserialization
- Backward compatibility with legacy fields

**What's next:**
- Update frontend templates to use new API fields
- Add device schedule management UI
- Test end-to-end unit creation with all fields
