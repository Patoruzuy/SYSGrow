# Frontend Integration Guide

## Device Management with Unit Association

### Overview
All devices (sensors & actuators) MUST be associated with a growth unit. The selected unit is stored in the session and should be used for all device operations.

---

## API Endpoints Summary

### Combined Devices Endpoint (NEW - RECOMMENDED)
```
GET /api/devices/all/unit/{unit_id}
```

**Response:**
```json
{
  "ok": true,
  "data": {
    "unit_id": 1,
    "unit_name": "My First Growth Unit",
    "sensors": [
      {
        "sensor_id": 1,
        "name": "Temperature Sensor",
        "sensor_type": "temperature",
        "sensor_model": "DHT22",
        "gpio": 4,
        "device_type": "sensor"  // ← Type indicator
      }
    ],
    "actuators": [
      {
        "actuator_id": 1,
        "device": "Water Pump",
        "actuator_type": "water_pump",
        "gpio": 18,
        "device_type": "actuator"  // ← Type indicator
      }
    ],
    "total_devices": 2,
    "sensor_count": 1,
    "actuator_count": 1
  }
}
```

**Usage:**
```javascript
// Fetch all devices for current unit
const response = await fetch(`/api/devices/all/unit/${unitId}`);
const data = await response.json();

// Separate by type
const sensors = data.data.sensors;
const actuators = data.data.actuators;

// Or iterate all with type check
const allDevices = [...data.data.sensors, ...data.data.actuators];
allDevices.forEach(device => {
  if (device.device_type === 'sensor') {
    // Handle sensor
  } else if (device.device_type === 'actuator') {
    // Handle actuator
  }
});
```

---

### Separate Endpoints (ALTERNATIVE)

#### Sensors
```
GET  /api/devices/sensors/unit/{unit_id}     // List sensors
POST /api/devices/sensors                     // Add sensor (requires unit_id in body)
DELETE /api/devices/sensors/{sensor_id}       // Remove sensor
```

#### Actuators
```
GET  /api/devices/actuators/unit/{unit_id}   // List actuators
POST /api/devices/actuators                   // Add actuator (requires unit_id in body)
DELETE /api/devices/actuators/{actuator_id}  // Remove actuator
```

---

## Adding Devices

### Add Sensor Example

```javascript
async function addSensor(unitId, sensorData) {
  const response = await fetch('/api/devices/sensors', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      unit_id: unitId,  // ← REQUIRED: Associate with unit
      sensor_name: sensorData.name,
      sensor_type: sensorData.type,  // 'temperature', 'humidity', 'soil_moisture'
      sensor_model: sensorData.model, // 'DHT22', 'BME280', etc.
      gpio_pin: sensorData.gpio,      // GPIO pin number (optional)
      ip_address: sensorData.ip,      // For wireless sensors (optional)
      communication: 'GPIO'            // 'GPIO', 'ADC', or 'wireless'
    })
  });
  
  const result = await response.json();
  if (result.ok) {
    console.log('Sensor added:', result.data.sensor_id);
  } else {
    console.error('Error:', result.error.message);
  }
}

// Usage
addSensor(currentUnitId, {
  name: 'Living Room Temperature',
  type: 'temperature',
  model: 'DHT22',
  gpio: 4
});
```

### Add Actuator Example

```javascript
async function addActuator(unitId, actuatorData) {
  const response = await fetch('/api/devices/actuators', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      unit_id: unitId,  // ← REQUIRED: Associate with unit
      actuator_type: actuatorData.type,  // 'water_pump', 'fan', 'light'
      device: actuatorData.name,
      gpio_pin: actuatorData.gpio,       // GPIO pin number (optional)
      ip_address: actuatorData.ip,       // For wireless actuators (optional)
      zigbee_channel: actuatorData.zigbee_channel,  // For ZigBee devices
      zigbee_topic: actuatorData.zigbee_topic
    })
  });
  
  const result = await response.json();
  if (result.ok) {
    console.log('Actuator added:', result.data.actuator_id);
  } else {
    console.error('Error:', result.error.message);
  }
}

// Usage
addActuator(currentUnitId, {
  type: 'water_pump',
  name: 'Main Water Pump',
  gpio: 18
});
```

---

## Complete Device Management Component Example

```javascript
class DeviceManager {
  constructor(unitId) {
    this.unitId = unitId;
  }
  
  // Get all devices (recommended)
  async getAllDevices() {
    const response = await fetch(`/api/devices/all/unit/${this.unitId}`);
    const data = await response.json();
    
    if (!data.ok) {
      throw new Error(data.error.message);
    }
    
    return {
      sensors: data.data.sensors,
      actuators: data.data.actuators,
      totalCount: data.data.total_devices
    };
  }
  
  // Add sensor
  async addSensor(sensorConfig) {
    const response = await fetch('/api/devices/sensors', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        unit_id: this.unitId,
        ...sensorConfig
      })
    });
    
    return await response.json();
  }
  
  // Add actuator
  async addActuator(actuatorConfig) {
    const response = await fetch('/api/devices/actuators', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        unit_id: this.unitId,
        ...actuatorConfig
      })
    });
    
    return await response.json();
  }
  
  // Remove device (type-aware)
  async removeDevice(deviceId, deviceType) {
    const endpoint = deviceType === 'sensor' 
      ? `/api/devices/sensors/${deviceId}`
      : `/api/devices/actuators/${deviceId}`;
    
    const response = await fetch(endpoint, { method: 'DELETE' });
    return await response.json();
  }
  
  // Render devices in UI
  renderDevices(devices) {
    const { sensors, actuators } = devices;
    
    // Render sensors
    const sensorHTML = sensors.map(sensor => `
      <div class="device-card sensor" data-id="${sensor.sensor_id}">
        <span class="device-type-badge">Sensor</span>
        <h3>${sensor.name}</h3>
        <p>Type: ${sensor.sensor_type}</p>
        <p>Model: ${sensor.sensor_model}</p>
        <button onclick="removeDevice(${sensor.sensor_id}, 'sensor')">
          Remove
        </button>
      </div>
    `).join('');
    
    // Render actuators
    const actuatorHTML = actuators.map(actuator => `
      <div class="device-card actuator" data-id="${actuator.actuator_id}">
        <span class="device-type-badge">Actuator</span>
        <h3>${actuator.device}</h3>
        <p>Type: ${actuator.actuator_type}</p>
        <button onclick="removeDevice(${actuator.actuator_id}, 'actuator')">
          Remove
        </button>
      </div>
    `).join('');
    
    document.getElementById('devices-container').innerHTML = 
      sensorHTML + actuatorHTML;
  }
}

// Usage
const deviceManager = new DeviceManager(currentUnitId);

// Load and display devices
async function loadDevices() {
  try {
    const devices = await deviceManager.getAllDevices();
    deviceManager.renderDevices(devices);
  } catch (error) {
    console.error('Failed to load devices:', error);
  }
}

// Add sensor form handler
document.getElementById('add-sensor-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  
  const formData = new FormData(e.target);
  const result = await deviceManager.addSensor({
    sensor_name: formData.get('name'),
    sensor_type: formData.get('type'),
    sensor_model: formData.get('model'),
    gpio_pin: formData.get('gpio')
  });
  
  if (result.ok) {
    alert('Sensor added successfully!');
    loadDevices(); // Refresh list
  } else {
    alert('Error: ' + result.error.message);
  }
});

// Add actuator form handler
document.getElementById('add-actuator-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  
  const formData = new FormData(e.target);
  const result = await deviceManager.addActuator({
    actuator_type: formData.get('type'),
    device: formData.get('name'),
    gpio_pin: formData.get('gpio')
  });
  
  if (result.ok) {
    alert('Actuator added successfully!');
    loadDevices(); // Refresh list
  } else {
    alert('Error: ' + result.error.message);
  }
});
```

---

## UI Form Examples

### Add Sensor Form

```html
<form id="add-sensor-form">
  <h2>Add Sensor</h2>
  
  <label>Sensor Name</label>
  <input type="text" name="name" required>
  
  <label>Sensor Type</label>
  <select name="type" required>
    <option value="temperature">Temperature</option>
    <option value="humidity">Humidity</option>
    <option value="soil_moisture">Soil Moisture</option>
    <option value="co2">CO2</option>
    <option value="light">Light</option>
  </select>
  
  <label>Sensor Model</label>
  <select name="model" required>
    <option value="DHT22">DHT22 (Temperature/Humidity)</option>
    <option value="BME280">BME280 (Temperature/Humidity/Pressure)</option>
    <option value="capacitive">Capacitive (Soil Moisture)</option>
    <option value="SCD30">SCD30 (CO2)</option>
  </select>
  
  <label>GPIO Pin</label>
  <input type="number" name="gpio" min="2" max="27">
  
  <button type="submit">Add Sensor</button>
</form>
```

### Add Actuator Form

```html
<form id="add-actuator-form">
  <h2>Add Actuator</h2>
  
  <label>Actuator Name</label>
  <input type="text" name="name" required>
  
  <label>Actuator Type</label>
  <select name="type" required>
    <option value="water_pump">Water Pump</option>
    <option value="fan">Fan</option>
    <option value="light">Grow Light</option>
    <option value="heater">Heater</option>
    <option value="humidifier">Humidifier</option>
  </select>
  
  <label>GPIO Pin</label>
  <input type="number" name="gpio" min="2" max="27">
  
  <button type="submit">Add Actuator</button>
</form>
```

---

## Device Type Differentiation

### Visual Indicators

```css
/* Device cards with type indicators */
.device-card {
  border: 2px solid #ccc;
  padding: 1rem;
  margin: 0.5rem;
  border-radius: 8px;
}

.device-card.sensor {
  border-color: #007bff;  /* Blue for sensors */
  background: #e7f3ff;
}

.device-card.actuator {
  border-color: #28a745;  /* Green for actuators */
  background: #e7f9ec;
}

.device-type-badge {
  display: inline-block;
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  font-size: 0.8rem;
  font-weight: bold;
  text-transform: uppercase;
}

.device-card.sensor .device-type-badge {
  background: #007bff;
  color: white;
}

.device-card.actuator .device-type-badge {
  background: #28a745;
  color: white;
}
```

### Icons

```javascript
const DEVICE_ICONS = {
  // Sensors
  'temperature': '🌡️',
  'humidity': '💧',
  'soil_moisture': '🌱',
  'co2': '🌫️',
  'light': '☀️',
  
  // Actuators
  'water_pump': '💦',
  'fan': '💨',
  'light': '💡',
  'heater': '🔥',
  'humidifier': '💧'
};

function getDeviceIcon(device) {
  if (device.device_type === 'sensor') {
    return DEVICE_ICONS[device.sensor_type] || '📡';
  } else {
    return DEVICE_ICONS[device.actuator_type] || '⚙️';
  }
}
```

---

## Error Handling

```javascript
async function safeDeviceOperation(operation) {
  try {
    const result = await operation();
    
    if (!result.ok) {
      // Handle API error response
      const errorMessage = result.error?.message || 'Unknown error';
      console.error('Device operation failed:', errorMessage);
      
      // Show user-friendly error
      if (errorMessage.includes('unit_id')) {
        alert('Please select a growth unit first');
      } else if (errorMessage.includes('not found')) {
        alert('Unit or device not found');
      } else {
        alert(`Error: ${errorMessage}`);
      }
      
      return null;
    }
    
    return result.data;
    
  } catch (error) {
    console.error('Network or parsing error:', error);
    alert('Failed to connect to server');
    return null;
  }
}

// Usage
const devices = await safeDeviceOperation(() => 
  deviceManager.getAllDevices()
);

if (devices) {
  deviceManager.renderDevices(devices);
}
```

---

## Summary

### Key Points

1. **Always include `unit_id`** when adding sensors or actuators
2. **Use the combined endpoint** (`/api/devices/all/unit/{id}`) for efficiency
3. **Check `device_type`** field to differentiate sensors from actuators
4. **Validate unit selection** before showing device management UI
5. **Handle errors gracefully** with user-friendly messages

### Recommended Flow

```
1. User logs in
   ↓
2. System checks units
   ↓
3a. No units → Create default unit
3b. One unit → Auto-select
3c. Multiple units → Show selector
   ↓
4. Store selected unit in session/state
   ↓
5. Load devices for selected unit
   ↓
6. Display sensors and actuators separately
   ↓
7. All add/remove operations use selected unit
```

