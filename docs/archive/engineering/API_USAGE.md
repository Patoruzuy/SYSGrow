# SYSGrow API Module Usage Guide

## Overview

The API module (`/static/js/api.js`) provides a centralized, type-safe interface for all backend API endpoints.

## Including the Module

Add this script tag to your HTML templates:

```html
<script src="{{ url_for('static', filename='js/api.js') }}"></script>
```

## Usage Examples

### Growth Units

```javascript
// List all units
const units = await API.Growth.listUnits();
console.log(units); // { units: [...], count: 5 }

// Create a new unit
const newUnit = await API.Growth.createUnit({
    name: "My Greenhouse",
    location: "Outdoor",
    camera_enabled: true
});

// Update unit
const updated = await API.Growth.updateUnit(unitId, {
    name: "Updated Name"
});

// Delete unit
await API.Growth.deleteUnit(unitId);

// Get/Set thresholds
const thresholds = await API.Growth.getThresholds(unitId);
await API.Growth.setThresholds(unitId, {
    temperature_threshold: 25.0,
    humidity_threshold: 60.0,
    soil_moisture_threshold: 45.0
});
```

### Plants

```javascript
// List plants in a unit
const plants = await API.Plant.listPlants(unitId);

// Add a plant
const plant = await API.Plant.addPlant(unitId, {
    name: "Tomato Plant #1",
    plant_type: "Tomato",
    current_stage: "Seedling",
    days_in_stage: 3
});

// Remove plant
await API.Plant.removePlant(unitId, plantId);

// Set active plant for climate control
await API.Plant.setActivePlant(unitId, plantId);

// Update plant stage
await API.Plant.updatePlantStage(unitId, plantId, {
    stage: "Vegetative",
    days_in_stage: 0
});

// Link/unlink sensors
await API.Plant.linkPlantToSensor(unitId, plantId, sensorId);
await API.Plant.unlinkPlantFromSensor(unitId, plantId, sensorId);
const sensors = await API.Plant.getPlantSensors(unitId, plantId);
```

### Camera

```javascript
// Start/stop camera
await API.Camera.start(unitId);
await API.Camera.stop(unitId);

// Capture photo
const photo = await API.Camera.capture(unitId);

// Get camera status
const status = await API.Camera.getStatus(unitId);
```

### Device Schedules

```javascript
// Get all schedules
const schedules = await API.Growth.getSchedules(unitId);

// Get specific device schedule
const lightSchedule = await API.Growth.getDeviceSchedule(unitId, 'light');

// Set schedule
await API.Growth.setDeviceSchedule(unitId, {
    device_type: 'light',
    start_time: '08:00',
    end_time: '20:00',
    enabled: true
});

// Delete schedule
await API.Growth.deleteDeviceSchedule(unitId, 'light');

// Get active devices
const active = await API.Growth.getActiveDevices(unitId);
```

### Devices (Sensors & Actuators)

```javascript
// Get all sensors
const sensors = await API.Device.getSensors();

// Get sensors for specific unit
const unitSensors = await API.Device.getSensorsByUnit(unitId);

// Add sensor
const sensor = await API.Device.addSensor({
    sensor_type: 'DHT22',
    gpio: 4,
    growth_unit_id: unitId
});

// Remove sensor
await API.Device.removeSensor({ sensor_id: sensorId });

// Get all actuators
const actuators = await API.Device.getActuators();

// Add actuator
const actuator = await API.Device.addActuator({
    actuator_type: 'Relay',
    device: 'Light',
    gpio: 17,
    growth_unit_id: unitId
});

// Control actuator
await API.Device.controlActuator({
    actuator_id: actuatorId,
    state: 'ON',
    duration: 3600  // Optional: auto-off after 1 hour
});
```

### Sensor History

```javascript
// Get sensor history (last 24 hours by default)
const history = await API.Sensor.getHistory();

// Get history for specific date range
const customHistory = await API.Sensor.getHistory({
    start_date: '2025-01-01T00:00:00',
    end_date: '2025-01-31T23:59:59'
});

console.log(customHistory);
// {
//     timestamps: ['2025-01-01T00:00:00', ...],
//     readings: {
//         temperature: [22.5, 23.1, ...],
//         humidity: [55.2, 56.0, ...],
//         co2: [800, 820, ...],
//         voc: [120, 115, ...],
//         soil_moisture: [45.3, 44.8, ...]
//     }
// }
```

### Dashboard

```javascript
// Get current sensor readings
const current = await API.Dashboard.getCurrentSensors();

// Toggle device
await API.Dashboard.toggleDevice('light', { enabled: true });

// Get system status
const status = await API.Dashboard.getStatus();
```

### Settings

```javascript
// Hotspot settings
const hotspot = await API.Settings.getHotspot();
await API.Settings.updateHotspot({
    ssid: "SYSGrow-WiFi",
    password: "mysecurepass"
});

// Camera settings
const camera = await API.Settings.getCamera();
await API.Settings.updateCamera({
    camera_type: 'esp32',
    ip_address: '192.168.1.100'
});

// Environment settings
const env = await API.Settings.getEnvironment();
await API.Settings.updateEnvironment({
    timezone: 'UTC',
    units: 'metric'
});
```

### ESP32 Devices

```javascript
// Get all ESP32 devices
const devices = await API.ESP32.getDevices();

// Get specific device
const device = await API.ESP32.getDevice('ESP32_SENSOR_01');

// Register device
const registered = await API.ESP32.registerDevice({
    device_id: 'ESP32_SENSOR_02',
    unit_id: 1,
    device_name: 'Soil Sensor Module',
    location: 'Greenhouse A'
});

// Read sensors
const readings = await API.ESP32.readSensors('ESP32_SENSOR_01');

// Set power mode
await API.ESP32.setPowerMode('ESP32_SENSOR_01', { mode: 'save' });

// Get device stats
const stats = await API.ESP32.getStats('ESP32_SENSOR_01');
```

### Climate Control

```javascript
// Get climate status
const status = await API.Climate.getStatus();

// Get unit climate status
const unitStatus = await API.Climate.getUnitStatus(unitId);

// Start/stop climate control
await API.Climate.start(unitId);
await API.Climate.stop(unitId);

// Reload sensors/actuators
await API.Climate.reloadSensors(unitId);
await API.Climate.reloadActuators(unitId);

// Set schedules
await API.Climate.setLightSchedule(unitId, {
    start_time: '06:00',
    end_time: '22:00'
});

await API.Climate.setFanSchedule(unitId, {
    start_time: '09:00',
    end_time: '21:00'
});
```

### Agriculture Insights

```javascript
// Get watering decision
const watering = await API.Agriculture.getWateringDecision({
    unit_id: unitId
});

// Get environmental alerts
const alerts = await API.Agriculture.getEnvironmentalAlerts({
    unit_id: unitId
});

// Diagnose problems
const diagnosis = await API.Agriculture.getProblemDiagnosis({
    plant_type: 'Tomato',
    symptoms: ['yellowing_leaves', 'stunted_growth']
});

// Get yield projection
const yield = await API.Agriculture.getYieldProjection({
    plant_id: plantId
});

// Get available plants
const plants = await API.Agriculture.getAvailablePlants();
```

### Session Management

```javascript
// Select unit in session
await API.Session.selectUnit({ unit_id: unitId });
```

## Migration Examples

### Before (Direct fetch)

```javascript
// Old way
fetch('/api/devices/add_sensor', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(sensorData)
})
.then(response => response.json())
.then(data => {
    if (data.ok) {
        console.log('Success:', data.data);
    } else {
        console.error('Error:', data.error);
    }
})
.catch(error => console.error('Error:', error));
```

### After (Using API module)

```javascript
// New way
try {
    const result = await API.Device.addSensor(sensorData);
    console.log('Success:', result);
} catch (error) {
    console.error('Error:', error.message);
}
```

## Error Handling

All API functions throw errors on failure, so always use try-catch:

```javascript
try {
    const units = await API.Growth.listUnits();
    // Success
} catch (error) {
    console.error('Failed to fetch units:', error.message);
    // Show user-friendly error message
    alert('Failed to load units. Please try again.');
}
```

## Benefits

1. **Type Safety**: JSDoc comments provide IDE autocomplete and type hints
2. **Consistency**: Single source of truth for all API calls
3. **Maintainability**: Changes to endpoints only need to be updated in one place
4. **Error Handling**: Centralized error handling and response parsing
5. **Readability**: Clean, semantic function names
6. **Documentation**: Self-documenting code with clear parameter names

## Templates to Update

The following templates currently use direct `fetch()` calls and should be updated:

1. `devices.html` - Device management (5 fetch calls)
2. `units.html` - Unit management (1 fetch call)
3. `unit_selector.html` - Unit selection (3 fetch calls)
4. `settings.html` - Settings management (2 fetch calls)
5. `status.html` - Status page (2 fetch calls)
6. `index.html` - Dashboard camera (1 fetch call)
7. `dashboard.html` - Dashboard data (2 fetch calls)
8. `mqtt_sensor_uptime.html` - Status check (1 fetch call)
9. `fullscreen.html` - Device control (1 fetch call)
