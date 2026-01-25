# Unit-Based Architecture Analysis

## Executive Summary

✅ **CONFIRMED:** The system properly implements unit-based architecture where all sensors, actuators, and plants are associated with specific growth units.

## Architecture Overview

### 1. User Login & Unit Creation ✅

**Location:** `app/blueprints/ui/helpers.py` → `determine_landing_page()`

**Flow:**
```python
def determine_landing_page(growth_service, user_id):
    units = growth_service.list_units(user_id=user_id)
    
    if len(units) == 0:
        # ✅ CREATE DEFAULT UNIT for new users
        unit_id = growth_service.create_unit(
            name="My First Growth Unit",
            location="Indoor",
            user_id=user_id
        )
        return {"route": "dashboard", "unit_id": unit_id, "is_new_user": True}
    
    elif len(units) == 1:
        # ✅ SINGLE UNIT → Go to dashboard
        return {"route": "dashboard", "unit_id": units[0]["unit_id"]}
    
    else:
        # ✅ MULTIPLE UNITS → Show selector
        return {"route": "unit_selector", "units": units}
```

**Status:** ✅ **IMPLEMENTED CORRECTLY**
- New users automatically get "My First Growth Unit"
- Users can edit/customize this default unit
- Multi-unit users see unit selector

---

### 2. Unit Selection & Session Management ✅

**Location:** `app/blueprints/ui/routes.py`

**Implementation:**
```python
# User selects unit (stored in session)
session["selected_unit"] = unit_id

# All subsequent operations use selected_unit
selected_unit_id = session.get("selected_unit")
```

**API Endpoint:**
```python
@ui_bp.post("/api/session/select-unit")
def api_select_unit():
    unit_id = data.get("unit_id")
    session["selected_unit"] = unit_id
    # User ownership validation included
```

**Status:** ✅ **IMPLEMENTED CORRECTLY**
- Unit selection stored in Flask session
- Session persists across requests
- API endpoint for programmatic selection

---

### 3. Sensor Management (Unit-Based) ✅

**API Endpoints:** `app/blueprints/api/devices.py`

#### Get Sensors by Unit
```python
@devices_api.get('/sensors/unit/<int:unit_id>')
def get_sensors_for_unit(unit_id: int):
    sensors = device_service.list_sensors(unit_id=unit_id)
    # Returns ONLY sensors for specified unit
```

#### Add Sensor to Unit
```python
@devices_api.post('/sensors')
def add_sensor():
    unit_id = int(data.get('unit_id'))  # ✅ REQUIRED
    
    # Validate unit exists
    if not _growth_service().get_unit(unit_id):
        return _fail(f'Growth unit {unit_id} not found', 404)
    
    # Create sensor linked to unit
    sensor_id = device_service.create_sensor(
        sensor_type=sensor_type,
        sensor_model=sensor_model,
        unit_id=unit_id  # ✅ UNIT ASSOCIATION
    )
```

**Status:** ✅ **IMPLEMENTED CORRECTLY**
- `unit_id` is required parameter
- Validates unit exists before creating sensor
- All sensor queries filter by unit_id

---

### 4. Actuator Management (Unit-Based) ✅

**API Endpoints:** `app/blueprints/api/devices.py`

#### Get Actuators by Unit
```python
@devices_api.get('/actuators/unit/<int:unit_id>')
def get_actuators_for_unit(unit_id: int):
    actuators = device_service.list_actuators(unit_id=unit_id)
    # Returns ONLY actuators for specified unit
```

#### Add Actuator to Unit
```python
@devices_api.post('/actuators')
def add_actuator():
    unit_id = int(data.get('unit_id'))  # ✅ REQUIRED
    
    # Validate unit exists
    if not _growth_service().get_unit(unit_id):
        return _fail(f'Growth unit {unit_id} not found', 404)
    
    # Create actuator linked to unit
    actuator_id = device_service.create_actuator(
        actuator_type=actuator_type,
        device=device,
        unit_id=unit_id  # ✅ UNIT ASSOCIATION
    )
```

**Status:** ✅ **IMPLEMENTED CORRECTLY**
- `unit_id` is required parameter
- Validates unit exists before creating actuator
- All actuator queries filter by unit_id

---

### 5. Plant Management (Unit-Based) ✅

**API Endpoints:** `app/blueprints/api/plants.py`

#### List Plants in Unit
```python
@plants_api.get("/units/<int:unit_id>/plants")
def list_plants(unit_id: int):
    if not _growth_service().get_unit(unit_id):
        return _fail(f"Growth unit {unit_id} not found", 404)
    
    plants = plant_service.list_plants(unit_id)
```

#### Add Plant to Unit
```python
@plants_api.post("/units/<int:unit_id>/plants")
def add_plant(unit_id: int):
    # unit_id is part of URL path
    if not _growth_service().get_unit(unit_id):
        return _fail(f"Growth unit {unit_id} not found", 404)
    
    plant_id = plant_service.add_plant(
        unit_id=unit_id,  # ✅ UNIT ASSOCIATION
        name=payload["name"],
        plant_type=payload["plant_type"]
    )
```

#### Remove Plant from Unit
```python
@plants_api.delete("/units/<int:unit_id>/plants/<int:plant_id>")
def remove_plant(unit_id: int, plant_id: int):
    # Both unit_id and plant_id required
    plant_service.remove_plant(unit_id, plant_id)
```

**Status:** ✅ **IMPLEMENTED CORRECTLY**
- All plant operations require `unit_id`
- Plant CRUD endpoints follow `/units/{unit_id}/plants` pattern
- Validates unit exists before operations

---

### 6. Frontend Integration Pattern

**Expected Frontend Behavior:**

```javascript
// Get selected unit from session/state
const selectedUnitId = getCurrentSelectedUnit();

// Add Sensor
fetch('/api/devices/sensors', {
    method: 'POST',
    body: JSON.stringify({
        unit_id: selectedUnitId,  // ✅ REQUIRED
        sensor_name: "Temperature Sensor",
        sensor_type: "temperature",
        sensor_model: "DHT22"
    })
});

// Add Actuator
fetch('/api/devices/actuators', {
    method: 'POST',
    body: JSON.stringify({
        unit_id: selectedUnitId,  // ✅ REQUIRED
        actuator_type: "water_pump",
        device: "Water Pump 1"
    })
});

// Add Plant
fetch('/api/plants/units/' + selectedUnitId + '/plants', {
    method: 'POST',
    body: JSON.stringify({
        name: "Tomato Plant",
        plant_type: "tomato"
    })
});
```

**Status:** ✅ **ARCHITECTURE READY**
- Backend expects `unit_id` in all requests
- Frontend should include from session/state
- All endpoints validate unit exists

---

## Device Type Differentiation (Sensor vs Actuator)

### Current Implementation

**Problem Identified:** Frontend needs way to differentiate devices

**Solution Options:**

### Option 1: Use Separate Endpoints ✅ (CURRENT)
```
GET /api/devices/sensors/unit/{unit_id}    → Returns only sensors
GET /api/devices/actuators/unit/{unit_id}  → Returns only actuators
```

**Pros:**
- Clear separation
- Type-safe at API level
- Already implemented

**Cons:**
- Two API calls if need both

### Option 2: Add Type Field to Combined Endpoint
```python
@devices_api.get('/devices/unit/<int:unit_id>')
def get_all_devices(unit_id: int):
    sensors = device_service.list_sensors(unit_id=unit_id)
    actuators = device_service.list_actuators(unit_id=unit_id)
    
    devices = []
    for sensor in sensors:
        devices.append({
            **sensor,
            "device_type": "sensor"  # ✅ TYPE INDICATOR
        })
    
    for actuator in actuators:
        devices.append({
            **actuator,
            "device_type": "actuator"  # ✅ TYPE INDICATOR
        })
    
    return _success({"devices": devices})
```

**Pros:**
- Single API call
- Frontend can filter/group by `device_type`

**Cons:**
- Mixed data structures in response

### Option 3: Grouped Response
```python
@devices_api.get('/devices/unit/<int:unit_id>')
def get_all_devices(unit_id: int):
    return _success({
        "sensors": device_service.list_sensors(unit_id=unit_id),
        "actuators": device_service.list_actuators(unit_id=unit_id),
        "unit_id": unit_id
    })
```

**Pros:**
- Single API call
- Clear grouping
- Type-safe structures

**Cons:**
- Slightly larger response

---

## Actuator Manager Enhancement Plan

### Current Sensor Manager Pattern
```python
class SensorManager:
    def __init__(self, database_handler):
        self._sensors: Dict[int, BaseSensor] = {}
        self._calibration_data: Dict[int, CalibrationData] = {}
    
    def add_sensor(self, sensor_id: int, sensor: BaseSensor):
        self._sensors[sensor_id] = sensor
    
    def read_sensor(self, sensor_id: int) -> Optional[float]:
        sensor = self._sensors.get(sensor_id)
        if sensor:
            return sensor.read()
    
    def calibrate_sensor(self, sensor_id: int, calibration: CalibrationData):
        self._calibration_data[sensor_id] = calibration
```

### Proposed Actuator Manager Pattern
```python
class ActuatorManager:
    def __init__(self, database_handler):
        self._actuators: Dict[int, BaseActuator] = {}
        self._schedules: Dict[int, Schedule] = {}
        self._state: Dict[int, ActuatorState] = {}
    
    def add_actuator(self, actuator_id: int, actuator: BaseActuator):
        """Register actuator in memory"""
        self._actuators[actuator_id] = actuator
        self._state[actuator_id] = ActuatorState.OFF
    
    def control_actuator(self, actuator_id: int, command: str, **kwargs):
        """Send control command (on/off/pwm/etc)"""
        actuator = self._actuators.get(actuator_id)
        if actuator:
            result = actuator.execute(command, **kwargs)
            self._state[actuator_id] = result.state
            return result
    
    def set_schedule(self, actuator_id: int, schedule: Schedule):
        """Set automated schedule for actuator"""
        self._schedules[actuator_id] = schedule
    
    def get_state(self, actuator_id: int) -> ActuatorState:
        """Get current state (on/off/level)"""
        return self._state.get(actuator_id, ActuatorState.UNKNOWN)
    
    def get_all_actuators(self) -> Dict[int, BaseActuator]:
        """Get all registered actuators"""
        return self._actuators.copy()
```

### Key Features to Implement

1. **State Management**
   - Track on/off/pwm states
   - Store last command/result
   - Power consumption tracking

2. **Schedule Support**
   - Time-based activation
   - Event-based triggers
   - Integration with existing device schedules

3. **Control Methods**
   - `turn_on()`, `turn_off()`, `toggle()`
   - `set_level(value)` for PWM devices
   - `pulse(duration)` for timed operations

4. **Safety Features**
   - Interlock prevention (e.g., heater + humidifier)
   - Power limit enforcement
   - Emergency stop capability

5. **Factory Pattern** (like sensors)
   ```python
   class ActuatorFactory:
       @staticmethod
       def create_actuator(config: Dict) -> BaseActuator:
           actuator_type = config['actuator_type']
           
           if actuator_type == 'water_pump':
               return WaterPumpActuator(config)
           elif actuator_type == 'fan':
               return FanActuator(config)
           elif actuator_type == 'light':
               return LightActuator(config)
           # ...
   ```

---

## Summary & Recommendations

### ✅ What's Working Correctly

1. **Unit-based architecture fully implemented**
   - All sensors require `unit_id`
   - All actuators require `unit_id`
   - All plants require `unit_id`

2. **User onboarding flow**
   - Default unit created for new users
   - Unit selector for multi-unit users
   - Session-based unit selection

3. **API consistency**
   - Endpoints follow `/api/{resource}/unit/{unit_id}` pattern
   - Unit validation before operations
   - Proper 404 responses for missing units

### 🔧 Recommendations

1. **Frontend Device Management**
   - **RECOMMENDED:** Add combined endpoint with `device_type` field (Option 3)
   - Create endpoint: `GET /api/devices/all/unit/{unit_id}`
   - Returns grouped: `{"sensors": [...], "actuators": [...]}`

2. **Actuator Manager Enhancement**
   - Mirror sensor manager architecture
   - Add state management
   - Implement control methods
   - Add schedule support
   - Safety interlocks

3. **Frontend Development Guide**
   ```javascript
   // Always include unit_id from session
   const unitId = getSelectedUnit();
   
   // For sensors
   POST /api/devices/sensors { unit_id: unitId, ... }
   
   // For actuators
   POST /api/devices/actuators { unit_id: unitId, ... }
   
   // For plants
   POST /api/plants/units/{unitId}/plants { ... }
   ```

4. **Database Schema Enhancement**
   - Ensure all tables have `unit_id` foreign key
   - Add user ownership to units table (if not present)
   - Index on `unit_id` for query performance

---

## Conclusion

✅ **The system architecture correctly implements unit-based resource management.**

All sensors, actuators, and plants are properly scoped to growth units. New users automatically get a default unit, and all API endpoints enforce unit association.

The only enhancement needed is the **Actuator Manager** to mirror the sensor manager pattern for better hardware control and state management.

Frontend can differentiate sensors from actuators by:
1. Using separate endpoints (current approach)
2. Adding a combined endpoint with device type indicators (recommended for efficiency)

**Next Steps:**
1. Create combined devices endpoint (optional, for frontend convenience)
2. Implement ActuatorManager class
3. Add actuator control methods (on/off/pwm)
4. Add schedule integration for actuators
