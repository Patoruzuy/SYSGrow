# Frontend Template Updates Guide

## Overview
This document provides guidance for updating frontend templates to support the new API fields: `dimensions`, `device_schedules`, `camera_enabled`, and `custom_image`.

---

## 1. Unit Creation Form

### Location
Look for templates in:
- `templates/growth/` or `templates/units/`
- Files like `create_unit.html`, `new_unit.html`, or similar

### Updates Needed

#### A. Add Dimensions Input Fields

```html
<!-- Add this section to the create unit form -->
<div class="form-group">
  <label>Dimensions (cm)</label>
  <div class="dimensions-inputs">
    <div class="dimension-field">
      <label for="dimension-width">Width</label>
      <input type="number" 
             id="dimension-width" 
             name="dimensions[width]" 
             min="0" 
             step="0.1"
             placeholder="e.g., 300">
    </div>
    
    <div class="dimension-field">
      <label for="dimension-height">Height</label>
      <input type="number" 
             id="dimension-height" 
             name="dimensions[height]" 
             min="0" 
             step="0.1"
             placeholder="e.g., 250">
    </div>
    
    <div class="dimension-field">
      <label for="dimension-depth">Depth</label>
      <input type="number" 
             id="dimension-depth" 
             name="dimensions[depth]" 
             min="0" 
             step="0.1"
             placeholder="e.g., 200">
    </div>
  </div>
</div>
```

#### B. Add Camera Enable Checkbox

```html
<div class="form-group">
  <label>
    <input type="checkbox" 
           name="camera_enabled" 
           id="camera-enabled"
           value="true">
    Enable Camera for this unit
  </label>
  <small class="form-text text-muted">
    Enable camera to capture time-lapse images and monitor growth
  </small>
</div>
```

#### C. Add Device Schedules Section

```html
<div class="form-group">
  <label>Device Schedules</label>
  <small class="form-text text-muted">
    Configure when devices should be active
  </small>
  
  <div id="device-schedules-container">
    <!-- Initial schedule row -->
    <div class="schedule-row" data-schedule-id="0">
      <div class="row">
        <div class="col-md-3">
          <label>Device Type</label>
          <select name="device_schedules[0][device_type]" class="form-control" required>
            <option value="">Select device...</option>
            <option value="light">Light</option>
            <option value="fan">Fan</option>
            <option value="pump">Water Pump</option>
            <option value="heater">Heater</option>
            <option value="cooler">Cooler</option>
            <option value="humidifier">Humidifier</option>
            <option value="dehumidifier">Dehumidifier</option>
          </select>
        </div>
        
        <div class="col-md-3">
          <label>Start Time</label>
          <input type="time" 
                 name="device_schedules[0][start_time]" 
                 class="form-control" 
                 required>
        </div>
        
        <div class="col-md-3">
          <label>End Time</label>
          <input type="time" 
                 name="device_schedules[0][end_time]" 
                 class="form-control" 
                 required>
        </div>
        
        <div class="col-md-2">
          <label>Enabled</label>
          <div class="form-check">
            <input type="checkbox" 
                   name="device_schedules[0][enabled]" 
                   class="form-check-input" 
                   checked>
          </div>
        </div>
        
        <div class="col-md-1">
          <label>&nbsp;</label>
          <button type="button" 
                  class="btn btn-sm btn-danger remove-schedule" 
                  onclick="removeScheduleRow(0)">
            <i class="fas fa-trash"></i>
          </button>
        </div>
      </div>
    </div>
  </div>
  
  <button type="button" 
          class="btn btn-sm btn-secondary mt-2" 
          onclick="addScheduleRow()">
    <i class="fas fa-plus"></i> Add Device Schedule
  </button>
</div>
```

#### D. JavaScript for Dynamic Schedules

```javascript
<script>
let scheduleCounter = 1;

function addScheduleRow() {
  const container = document.getElementById('device-schedules-container');
  const newRow = document.createElement('div');
  newRow.className = 'schedule-row mt-2';
  newRow.setAttribute('data-schedule-id', scheduleCounter);
  
  newRow.innerHTML = `
    <div class="row">
      <div class="col-md-3">
        <select name="device_schedules[${scheduleCounter}][device_type]" class="form-control" required>
          <option value="">Select device...</option>
          <option value="light">Light</option>
          <option value="fan">Fan</option>
          <option value="pump">Water Pump</option>
          <option value="heater">Heater</option>
          <option value="cooler">Cooler</option>
          <option value="humidifier">Humidifier</option>
          <option value="dehumidifier">Dehumidifier</option>
        </select>
      </div>
      <div class="col-md-3">
        <input type="time" name="device_schedules[${scheduleCounter}][start_time]" class="form-control" required>
      </div>
      <div class="col-md-3">
        <input type="time" name="device_schedules[${scheduleCounter}][end_time]" class="form-control" required>
      </div>
      <div class="col-md-2">
        <div class="form-check">
          <input type="checkbox" name="device_schedules[${scheduleCounter}][enabled]" class="form-check-input" checked>
        </div>
      </div>
      <div class="col-md-1">
        <button type="button" class="btn btn-sm btn-danger" onclick="removeScheduleRow(${scheduleCounter})">
          <i class="fas fa-trash"></i>
        </button>
      </div>
    </div>
  `;
  
  container.appendChild(newRow);
  scheduleCounter++;
}

function removeScheduleRow(id) {
  const row = document.querySelector(`[data-schedule-id="${id}"]`);
  if (row) {
    row.remove();
  }
}

// Form submission handler
document.getElementById('create-unit-form').addEventListener('submit', async function(e) {
  e.preventDefault();
  
  const formData = new FormData(this);
  
  // Build dimensions object
  const dimensions = {
    width: parseFloat(formData.get('dimensions[width]')) || null,
    height: parseFloat(formData.get('dimensions[height]')) || null,
    depth: parseFloat(formData.get('dimensions[depth]')) || null
  };
  
  // Build device_schedules object
  const device_schedules = {};
  let scheduleIndex = 0;
  while (formData.has(`device_schedules[${scheduleIndex}][device_type]`)) {
    const deviceType = formData.get(`device_schedules[${scheduleIndex}][device_type]`);
    if (deviceType) {
      device_schedules[deviceType] = {
        start_time: formData.get(`device_schedules[${scheduleIndex}][start_time]`),
        end_time: formData.get(`device_schedules[${scheduleIndex}][end_time]`),
        enabled: formData.has(`device_schedules[${scheduleIndex}][enabled]`)
      };
    }
    scheduleIndex++;
  }
  
  // Build request payload
  const payload = {
    name: formData.get('name'),
    location: formData.get('location') || 'Indoor',
    dimensions: (dimensions.width || dimensions.height || dimensions.depth) ? dimensions : null,
    device_schedules: Object.keys(device_schedules).length > 0 ? device_schedules : null,
    camera_enabled: formData.has('camera_enabled'),
    custom_image: formData.get('custom_image') || null
  };
  
  try {
    const response = await fetch('/api/v1/growth/units', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(payload)
    });
    
    const result = await response.json();
    
    if (result.ok) {
      // Success - redirect or show success message
      window.location.href = '/units';
    } else {
      // Show error
      alert('Error: ' + (result.error?.message || 'Unknown error'));
    }
  } catch (error) {
    alert('Network error: ' + error.message);
  }
});
</script>
```

---

## 2. Unit Details/View Page

### Updates Needed

#### A. Display Dimensions

```html
<div class="card mb-3">
  <div class="card-header">
    <h5>Physical Dimensions</h5>
  </div>
  <div class="card-body">
    {% if unit.dimensions %}
      <div class="row">
        <div class="col-md-4">
          <strong>Width:</strong> {{ unit.dimensions.width }} cm
        </div>
        <div class="col-md-4">
          <strong>Height:</strong> {{ unit.dimensions.height }} cm
        </div>
        <div class="col-md-4">
          <strong>Depth:</strong> {{ unit.dimensions.depth }} cm
        </div>
      </div>
      <div class="mt-2">
        <strong>Total Volume:</strong> 
        {{ (unit.dimensions.width * unit.dimensions.height * unit.dimensions.depth / 1000000)|round(2) }} m³
      </div>
    {% else %}
      <p class="text-muted">No dimensions specified</p>
    {% endif %}
  </div>
</div>
```

#### B. Display Device Schedules

```html
<div class="card mb-3">
  <div class="card-header d-flex justify-content-between align-items-center">
    <h5>Device Schedules</h5>
    <button class="btn btn-sm btn-primary" onclick="showAddScheduleModal()">
      <i class="fas fa-plus"></i> Add Schedule
    </button>
  </div>
  <div class="card-body">
    {% if unit.device_schedules %}
      <table class="table table-striped">
        <thead>
          <tr>
            <th>Device</th>
            <th>Start Time</th>
            <th>End Time</th>
            <th>Status</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {% for device_type, schedule in unit.device_schedules.items() %}
          <tr>
            <td>
              <i class="fas fa-{{ device_icon(device_type) }}"></i>
              {{ device_type|title }}
            </td>
            <td>{{ schedule.start_time }}</td>
            <td>{{ schedule.end_time }}</td>
            <td>
              {% if schedule.enabled %}
                <span class="badge badge-success">Enabled</span>
              {% else %}
                <span class="badge badge-secondary">Disabled</span>
              {% endif %}
            </td>
            <td>
              <button class="btn btn-sm btn-primary" 
                      onclick="editSchedule('{{ device_type }}', {{ schedule|tojson }})">
                <i class="fas fa-edit"></i>
              </button>
              <button class="btn btn-sm btn-danger" 
                      onclick="deleteSchedule('{{ device_type }}')">
                <i class="fas fa-trash"></i>
              </button>
            </td>
          </tr>
          {% endfor %}
        </tbody>
      </table>
    {% else %}
      <p class="text-muted">No device schedules configured</p>
      <button class="btn btn-sm btn-primary" onclick="showAddScheduleModal()">
        <i class="fas fa-plus"></i> Add First Schedule
      </button>
    {% endif %}
  </div>
</div>
```

#### C. Show Camera Status

```html
<div class="card mb-3">
  <div class="card-header">
    <h5>Camera</h5>
  </div>
  <div class="card-body">
    {% if unit.camera_enabled %}
      <p>
        <span class="badge badge-success">
          <i class="fas fa-camera"></i> Camera Enabled
        </span>
      </p>
      <button class="btn btn-sm btn-primary" onclick="viewCameraFeed()">
        <i class="fas fa-video"></i> View Live Feed
      </button>
    {% else %}
      <p class="text-muted">
        <i class="fas fa-camera-slash"></i> Camera not enabled for this unit
      </p>
    {% endif %}
  </div>
</div>
```

#### D. JavaScript for Schedule Management

```javascript
<script>
const unitId = {{ unit.unit_id }};

async function editSchedule(deviceType, currentSchedule) {
  // Show modal or inline form with current values
  const startTime = prompt('Start Time (HH:MM):', currentSchedule.start_time);
  const endTime = prompt('End Time (HH:MM):', currentSchedule.end_time);
  const enabled = confirm('Enable this schedule?');
  
  if (startTime && endTime) {
    try {
      const response = await fetch(`/api/v1/growth/units/${unitId}/schedules`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          device_type: deviceType,
          start_time: startTime,
          end_time: endTime,
          enabled: enabled
        })
      });
      
      const result = await response.json();
      if (result.ok) {
        location.reload();
      } else {
        alert('Error: ' + (result.error?.message || 'Unknown error'));
      }
    } catch (error) {
      alert('Network error: ' + error.message);
    }
  }
}

async function deleteSchedule(deviceType) {
  if (confirm(`Delete schedule for ${deviceType}?`)) {
    try {
      const response = await fetch(`/api/v1/growth/units/${unitId}/schedules/${deviceType}`, {
        method: 'DELETE'
      });
      
      const result = await response.json();
      if (result.ok) {
        location.reload();
      } else {
        alert('Error: ' + (result.error?.message || 'Unknown error'));
      }
    } catch (error) {
      alert('Network error: ' + error.message);
    }
  }
}

async function showAddScheduleModal() {
  const deviceType = prompt('Device Type (light, fan, pump, etc.):');
  const startTime = prompt('Start Time (HH:MM):');
  const endTime = prompt('End Time (HH:MM):');
  const enabled = confirm('Enable this schedule?');
  
  if (deviceType && startTime && endTime) {
    try {
      const response = await fetch(`/api/v1/growth/units/${unitId}/schedules`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          device_type: deviceType,
          start_time: startTime,
          end_time: endTime,
          enabled: enabled
        })
      });
      
      const result = await response.json();
      if (result.ok) {
        location.reload();
      } else {
        alert('Error: ' + (result.error?.message || 'Unknown error'));
      }
    } catch (error) {
      alert('Network error: ' + error.message);
    }
  }
}

// Show active devices indicator
async function updateActiveDevices() {
  try {
    const response = await fetch(`/api/v1/growth/units/${unitId}/schedules/active`);
    const result = await response.json();
    
    if (result.ok) {
      const container = document.getElementById('active-devices');
      if (container) {
        container.innerHTML = result.data.active_devices.map(device => 
          `<span class="badge badge-success mr-1">
            <i class="fas fa-circle"></i> ${device}
          </span>`
        ).join('');
      }
    }
  } catch (error) {
    console.error('Error fetching active devices:', error);
  }
}

// Update active devices every minute
updateActiveDevices();
setInterval(updateActiveDevices, 60000);
</script>
```

---

## 3. Unit List/Dashboard

### Updates Needed

#### A. Show Dimensions in Card/List View

```html
<div class="unit-card">
  <div class="unit-header">
    <h4>{{ unit.name }}</h4>
    <span class="badge badge-info">{{ unit.location }}</span>
  </div>
  
  <div class="unit-details">
    {% if unit.dimensions %}
      <div class="unit-dimensions">
        <small class="text-muted">
          <i class="fas fa-ruler-combined"></i>
          {{ unit.dimensions.width }} × {{ unit.dimensions.height }} × {{ unit.dimensions.depth }} cm
        </small>
      </div>
    {% endif %}
    
    {% if unit.device_schedules %}
      <div class="unit-schedules">
        <small class="text-muted">
          <i class="fas fa-clock"></i>
          {{ unit.device_schedules|length }} device schedule(s)
        </small>
      </div>
    {% endif %}
    
    {% if unit.camera_enabled %}
      <div class="unit-camera">
        <small class="badge badge-success">
          <i class="fas fa-camera"></i> Camera
        </small>
      </div>
    {% endif %}
  </div>
</div>
```

---

## 4. CSS Styling (Optional)

```css
/* Dimensions inputs */
.dimensions-inputs {
  display: flex;
  gap: 1rem;
}

.dimension-field {
  flex: 1;
}

.dimension-field label {
  display: block;
  font-size: 0.875rem;
  margin-bottom: 0.25rem;
}

/* Schedule rows */
.schedule-row {
  padding: 1rem;
  border: 1px solid #dee2e6;
  border-radius: 0.25rem;
  margin-bottom: 0.5rem;
}

.schedule-row:hover {
  background-color: #f8f9fa;
}

/* Active device badges */
#active-devices .badge {
  animation: pulse 2s infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.7; }
}
```

---

## 5. Backend Route Updates (if using Flask templates)

If you're using server-side rendering with Flask/Jinja2, you may need to update your route handlers:

```python
@app.route('/units/<int:unit_id>')
def view_unit(unit_id):
    unit = growth_service.get_unit(unit_id)
    
    # Parse JSON fields if stored as strings
    if unit.get('dimensions') and isinstance(unit['dimensions'], str):
        unit['dimensions'] = json.loads(unit['dimensions'])
    
    if unit.get('device_schedules') and isinstance(unit['device_schedules'], str):
        unit['device_schedules'] = json.loads(unit['device_schedules'])
    
    return render_template('units/view.html', unit=unit)
```

---

## 6. Testing Checklist

- [ ] Create unit with dimensions
- [ ] Create unit with device schedules
- [ ] Create unit with camera enabled
- [ ] View unit with all new fields
- [ ] Edit device schedule
- [ ] Delete device schedule
- [ ] Add new device schedule to existing unit
- [ ] View active devices indicator
- [ ] Test time inputs (24-hour format)
- [ ] Test midnight-crossing schedules (e.g., 22:00-06:00)
- [ ] Verify dimensions display correctly
- [ ] Verify camera status display

---

## Summary

**Files to Update:**
1. `templates/units/create.html` or similar - Add dimensions, camera, schedules
2. `templates/units/view.html` or similar - Display all new fields
3. `templates/units/list.html` or similar - Show dimensions/schedules summary
4. `static/js/units.js` - Add JavaScript handlers
5. Route handlers (if server-side rendering) - Parse JSON fields

**New API Endpoints to Use:**
- `POST /api/v1/growth/units` - Create with all fields
- `GET /api/v1/growth/units/<id>/schedules` - Get all schedules
- `POST /api/v1/growth/units/<id>/schedules` - Set schedule
- `DELETE /api/v1/growth/units/<id>/schedules/<device>` - Delete schedule
- `GET /api/v1/growth/units/<id>/schedules/active` - Get active devices

**Next Steps:**
1. Locate existing unit templates
2. Add HTML sections from this guide
3. Add JavaScript handlers
4. Test unit creation with new fields
5. Test schedule management
6. Update styling as needed
