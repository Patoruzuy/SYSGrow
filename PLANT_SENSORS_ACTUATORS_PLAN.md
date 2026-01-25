# Plant Sensors & Actuators Management - Implementation Plan

## Overview
Enhance the plant-details-modal.js component to provide comprehensive sensor and actuator management for plants, including linking, unlinking, and viewing associated devices.

## Current State Analysis

### Existing Components
1. **plant-details-modal.js** - Modal component showing plant details
   - Has 3 action buttons (link-sensor 🔗, edit ✏️, delete 🗑️)
   - Calls `openLinkSensorModal()` from uiManager when link button clicked
   
2. **link-sensor-modal** (plants.html) - HTML modal for linking sensors
   - Simple form with sensor dropdown
   - Handled by `ui-manager.js`: `openLinkSensorModal()` + `handleLinkSensorSubmit()`

3. **API Endpoints Available**:
   ```
   Sensors:
   - GET  /api/v3/plants/units/<unit_id>/sensors/available
   - GET  /api/v3/plants/plants/<plant_id>/sensors
   - POST /api/v3/plants/plants/<plant_id>/sensors/<sensor_id>
   - DELETE /api/v3/plants/plants/<plant_id>/sensors/<sensor_id>
   
   Actuators:
   - GET  /api/v3/plants/units/<unit_id>/actuators/available
   - GET  /api/v3/plants/plants/<plant_id>/actuators
   - POST /api/v3/plants/plants/<plant_id>/actuators/<actuator_id>
   - DELETE /api/v3/plants/plants/<plant_id>/actuators/<actuator_id>
   ```

4. **API.js Methods Available**:
   ```javascript
   Plant API:
   - getAvailableSensors(unitId, sensorType)
   - linkPlantToSensor(plantId, sensorId)
   - unlinkPlantFromSensor(plantId, sensorId)
   ```

### Missing Pieces
1. No API methods for actuators in api.js
2. No modal for linking actuators
3. No UI to display currently linked sensors/actuators
4. No unlink functionality in UI
5. No prevention of duplicate linking

---

## Implementation Plan

### Phase 1: API Layer Updates ✅ PREP WORK
**File**: `static/js/api.js`

**Add Plant Actuator Methods** (after line 870, in PlantAPI object):
```javascript
/**
 * Get available actuators that can be linked to plants
 * @param {number} unitId - Unit ID
 * @param {string} [actuatorType='pump'] - Actuator type filter
 * @returns {Promise<Object>} Available actuators
 */
getAvailableActuators(unitId, actuatorType = 'pump') {
    return get(`/api/plants/units/${unitId}/actuators/available?actuator_type=${actuatorType}`);
},

/**
 * Get actuators linked to a plant
 * @param {number} plantId - Plant ID
 * @returns {Promise<Object>} Plant actuators
 */
getPlantActuators(plantId) {
    return get(`/api/plants/plants/${plantId}/actuators`);
},

/**
 * Link plant to actuator
 * @param {number} plantId - Plant ID
 * @param {number} actuatorId - Actuator ID
 * @returns {Promise<Object>} Link result
 */
linkPlantToActuator(plantId, actuatorId) {
    return post(`/api/plants/plants/${plantId}/actuators/${actuatorId}`);
},

/**
 * Unlink plant from actuator
 * @param {number} plantId - Plant ID
 * @param {number} actuatorId - Actuator ID
 * @returns {Promise<Object>} Unlink result
 */
unlinkPlantFromActuator(plantId, actuatorId) {
    return del(`/api/plants/plants/${plantId}/actuators/${actuatorId}`);
},

/**
 * Get sensors linked to a plant
 * @param {number} plantId - Plant ID
 * @returns {Promise<Object>} Plant sensors
 */
getPlantSensors(plantId) {
    return get(`/api/plants/plants/${plantId}/sensors`);
},
```

---

### Phase 2: Create Dynamic Modals in Component
**File**: `static/js/components/plant-details-modal.js`

**Make modals completely self-contained** - Create link-sensor and link-actuator modals dynamically within the component. This ensures they work on both plants.html and dashboard.html without dependency on template HTML.

**Key Changes:**
- Remove dependency on plants.html modal HTML
- Remove dependency on ui-manager.js methods
- Create all modals dynamically
- Handle all modal logic within plant-details-modal.js
- Works standalone on any page

---

### Phase 3: Update plant-details-modal.js Component (Self-Contained)
**File**: `static/js/components/plant-details-modal.js`

**Strat0 Add Constructor Initialization
Create link modals on component initialization:
```javascript
constructor(options = {}) {
  // ... existing code ...
  this._ensureModal();
  this._ensureLinkModals(); // Create sensor/actuator modals
  this._wireCloseHandlers();
  this._wireActionHandlers();
}
```

#### 3.0.1 Add _ensureLinkModals Method
```javascript
_ensureLinkModals() {
  // Create sensor link modal if not exists
  if (!document.getElementById('plant-sensor-link-modal')) {
    this._createSensorLinkModal();
  }
  
  // Create actuator link modal if not exists
  if (!document.getElementById('plant-actuator-link-modal')) {
    this._createActuatorLinkModal();
  }
}

_createSensorLinkModal() {
  const modal = document.createElement('div');
  modal.id = 'plant-sensor-link-modal';
  modal.className = 'modal';
  modal.hidden = true;
  modal.setAttribute('aria-hidden', 'true');
  modal.innerHTML = `
    <div class="modal-overlay"></div>
    <div class="modal-content">
      <div class="modal-header">
        <h2 class="modal-title">
          <i class="fas fa-link"></i> Manage Sensors
        </h2>
        <button type="button" class="modal-close" aria-label="Close">
          <i class="fas fa-times"></i>
        </button>
      </div>
      <div class="modal-body">
        <div class="device-management-section">
          <h3>Currently Linked Sensors</h3>
          <div id="current-sensors-list" class="devices-list">
            <div class="loading">Loading...</div>
          </div>
        </div>
        
        <div class="device-management-section">
          <h3>Link New Sensor</h3>
          <form id="sensor-link-form">
            <input type="hidden" name="plant_id" id="sensor-plant-id">
            <div class="form-field">
              <label for="sensor-select">Available Sensors</label>
              <select id="sensor-select" name="sensor_id" required>
                <option value="">Loading...</option>
              </select>
            </div>
            <div class="form-actions">
              <button type="button" class="btn btn-secondary modal-close">Cancel</button>
              <button type="submit" class="btn btn-primary">Link Sensor</button>
            </div>
          </form>
        </div>
      </div>
    </div>
  `;
  document.body.appendChild(modal);
  
  // Wire form handler
  const form = modal.querySelector('#sensor-link-form');
  form.addEventListener('submit', (e) => this._handleSensorLinkSubmit(e));
  
  // Wire close handlers
  modal.querySelector('.modal-overlay').addEventListener('click', () => this._closeLinkModal(modal));
  modal.querySelectorAll('.modal-close').forEach(btn => {
    btn.addEventListener('click', () => this._closeLinkModal(modal));
  });
}

_createActuatorLinkModal() {
  const modal = document.createElement('div');
  modal.id = 'plant-actuator-link-modal';
  modal.className = 'modal';
  modal.hidden = true;
  modal.setAttribute('aria-hidden', 'true');
  modal.innerHTML = `
    <div class="modal-overlay"></div>
    <div class="modal-content">
      <div class="modal-header">
        <h2 class="modal-title">
          <i class="fas fa-water"></i> Manage Actuators
        </h2>
        <button type="button" class="modal-close" aria-label="Close">
          <i class="fas fa-times"></i>
        </button>
      </div>
      <div class="modal-body">
        <div class="device-management-section">
          <h3>Currently Linked Actuators</h3>
          <div id="current-actuators-list" class="devices-list">
            <div class="loading">Loading...</div>
          </div>
        </div>
        
        <div class="device-management-section">
          <h3>Link New Actuator</h3>
          <form id="actuator-link-form">
            <input type="hidden" name="plant_id" id="actuator-plant-id">
            <div class="form-field">
              <label for="actuator-select">Available Actuators (Pumps/Valves)</label>
              <select id="actuator-select" name="actuator_id" required>
                <option value="">Loading...</option>
              </select>
            </div>
            <div class="form-actions">
              <button type="button" class="btn btn-secondary modal-close">Cancel</button>
              <button type="submit" class="btn btn-primary">Link Actuator</button>
            </div>
          </form>
        </div>
      </div>
    </div>
  `;
  document.body.appendChild(modal);
  
  // Wire form handler (Self-Contained)
Replace link-sensor handler and add new handlers:

```javascript
// Link sensor - open our self-contained modal
if (linkBtn) {
  e.preventDefault();
  const plantId = linkBtn.dataset.plantId;
  const unitId = linkBtn.dataset.unitId;
  this._openSensorLinkModal(Number(plantId), Number(unitId));
  return;
}

// Link actuator - open our self-contained modal
if (e.target.closest('.action-link-actuator')) {
  e.preventDefault();
  const btn = e.target.closest('.action-link-actuator');
  const plantId = btn.dataset.plantId;
  const unitId = btn.dataset.unitId;
  this._openActuatorLinkModal(Number(plantId), Number(unitId));odal.hidden = true;
  modal.classList.remove('is-open', 'visible');
  modal.setAttribute('aria-hidden', 'true');
}
```

#### 3.egy**: Make the component completely independent by:
1. Creating sensor/actuator link modals dynamically
2. Managing all modal state internally
3. No external dependencies on ui-manager or template HTML

#### 3.1 Update Modal Header Actions (around line 100)
Replace action buttons HTML with enhanced version:
```javascript
const actionsHtml = `
  <div class="modal-actions-group">
    <button class="modal-action action-link-sensor" data-plant-id="${escapeAttr(plant?.plant_id)}" data-unit-id="${escapeAttr(plant?.unit_id)}" title="Manage Sensors">
      <i class="fas fa-link"></i> Sensors
    </button>
    <button class="modal-action action-link-actuator" data-plant-id="${escapeAttr(plant?.plant_id)}" data-unit-id="${escapeAttr(plant?.unit_id)}" title="Manage Actuators">
      <i class="fas fa-water"></i> Actuators
    </button>
    <button class="modal-action action-delete" data-plant-id="${escapeAttr(plant?.plant_id)}" data-unit-id="${escapeAttr(plant?.unit_id)}" title="Delete Plant">
      <i class="fas fa-trash-alt"></i> Delete
    </button>
  </div>
`;
```

#### 3.2 Add Linked Devices Section to Render Method (after observations section, line ~120)
```javascript
<section class="plant-devices-section">
  <div class="devices-tabs">
    <button class="device-tab active" data-tab="sensors">
      <i class="fas fa-link"></i> Linked Sensors
    </button>
    <button class="device-tab" data-tab="actuators">
      <i class="fas fa-water"></i> Linked Actuators
    </button>
  </div>
  
  <div class="device-tab-content active" id="sensors-content">
    <div id="plant-sensors-list" class="devices-list">
      <div class="loading">Loading sensors...</div>
    </div>
  </div>
  
  <div class="device-tab-content" id="actuators-content">
    <div id="plant-actuators-list" class="devices-list">
      <div class="loading">Loading actuators...</div>
    </div>
  </div>
</section>
```

#### 3.3 Add Method to Load Linked Devices
```javascript
async _loadLinkedDevices(plantId) {
  if (!plantId) return;
  
  try {
    // Load sensors
    const sensorsResp = await window.API.Plant.getPlantSensors(plantId);
    const sensors = sensorsResp?.data?.sensors || sensorsResp?.sensors || [];
    this._renderLinkedSensors(sensors, plantId);
    
    // Load actuators
    const actuatorsResp = await window.API.Plant.getPlantActuators(plantId);
    const actuators = actuatorsResp?.data?.actuators || actuatorsResp?.actuators || [];
    this._renderLinkedActuators(actuators, plantId);
    
  } catch (error) {
    console.error('Failed to load linked devices:', error);
  }
}

_renderLiAdd Modal Open Methods
```javascript
async _openSensorLinkModal(plantId, unitId) {
  const modal = document.getElementById('plant-sensor-link-modal');
  if (!modal) return;
  
  // Set plant ID
  const hiddenInput = modal.querySelector('#sensor-plant-id');
  if (hiddenInput) hiddenInput.value = plantId;
  (OPTIONAL) Keep UI Manager Compatibility
**File**: `static/js/plants/ui-manager.js`

**Note**: Since plant-details-modal.js is now self-contained, the UI manager methods are optional. They can remain for backward compatibility with the static link-sensor-modal in plants.html, but are not required for the plant-details-modal to function.

**If keeping the old link-sensor-modal in plants.html**, the existing openLinkSensorModal and handleLinkSensorSubmit methods can remain unchanged.

**If removing the old modals**, you can remove these methods entirely:
- `openLinkSensorModal()`
- `handleLinkSensorSubmit()`
- Related event handlers in `bindEvents()
  if (!plantId || !sensorId) {
    this._showToast('Please select a sensor', 'error');
    return;
  }
  
  try {
    await window.API.Plant.linkPlantToSensor(Number(plantId), Number(sensorId));
    this._showToast('Sensor linked successfully', 'success');
    
    // Reload the modal data
    const modal = document.getElementById('plant-sensor-link-modal');
    const unitId = modal?.dataset?.unitId;
    await this._loadSensorLinkData(plantId, unitId);
    
    // Refresh main modal if still open
    if (!this.modalEl?.hidden) {
      await this._loadLinkedDevices(plantId);
    }
  } catch (error) {
    console.error('Failed to link sensor:', error);
    this._showToast('Failed to link sensor', 'error');
  }
}

async _handleActuatorLinkSubmit(e) {
  e.preventDefault();
  const form = e.target;
  const plantId = form.plant_id?.value;
  const actuatorId = form.actuator_id?.value;
  
  if (!plantId || !actuatorId) {
    this._showToast('Please select an actuator', 'error');
    return;
  }
  
  try {
    await window.API.Plant.linkPlantToActuator(Number(plantId), Number(actuatorId));
    this._showToast('Actuator linked successfully', 'success');
    
    // Reload the modal data
    const modal = document.getElementById('plant-actuator-link-modal');
    const unitId = modal?.dataset?.unitId;
    await this._loadActuatorLinkData(plantId, unitId);
    
    // Refresh main modal if still open
    if (!this.modalEl?.hidden) {
      await this._loadLinkedDevices(plantId);
    }
  } catch (error) {
    console.error('Failed to link actuator:', error);
    this._showToast('Failed to link actuator', 'error');
  }
}
```

#### 3.7 Update Unlink Handlers to Refresh Link Modals
```javascript
async _handleUnlinkSensor(plantId, sensorId) {
  if (!confirm('Unlink this sensor from the plant?')) return;
  
  try {
    await window.API.Plant.unlinkPlantFromSensor(Number(plantId), Number(sensorId));
    
    // Refresh both the main modal and link modal if open
    await this._loadLinkedDevices(plantId);
    const linkModal = document.getElementById('plant-sensor-link-modal');
    if (linkModal && !linkModal.hidden) {
      const unitId = linkModal.dataset?.unitId;
      await this._loadSensorLinkData(plantId, unitId);
    }
    
    this._showToast('Sensor unlinked successfully', 'success');
  } catch (error) {
    console.error('Failed to unlink sensor:', error);
    this._showToast('Failed to unlink sensor', 'error');
  }
}

async _handleUnlinkActuator(plantId, actuatorId) {
  if (!confirm('Unlink this actuator from the plant?')) return;
  
  try {
    await window.API.Plant.unlinkPlantFromActuator(Number(plantId), Number(actuatorId));
    
    // Refresh both the main modal and link modal if open
    await this._loadLinkedDevices(plantId);
    const linkModal = document.getElementById('plant-actuator-link-modal');
    if (linkModal && !linkModal.hidden) {
      const unitId = linkModal.dataset?.unitId;
      await this._loadActuatorLinkData(plantId, unitId);
    }
    
    this._showToast('Actuator unlinked successfully', 'success');
  } catch (error) {
    console.error('Failed to unlink actuator:', error);
    this._showToast('Failed to unlink actuator', 'error');
  }
}
```

#### 3.8 nkedSensors(sensors, plantId) {
  const container = document.getElementById('plant-sensors-list');
  if (!container) return;
  
  if (!sensors || sensors.length === 0) {
    container.innerHTML = '<div class="empty-state">No sensors linked</div>';
    return;
  }
  
  container.innerHTML = sensors.map(sensor => `
    <div class="device-item">
      <div class="device-info">
        <i class="fas fa-thermometer-half"></i>
        <div>
          <strong>${escapeHtml(sensor.name || `Sensor ${sensor.sensor_id}`)}</strong>
          <small>${escapeHtml(sensor.type || 'Unknown')}</small>
        </div>
      </div>
      <button class="btn-icon btn-unlink" 
              data-action="unlink-sensor"
              data-plant-id="${escapeAttr(plantId)}"
              data-sensor-id="${escapeAttr(sensor.sensor_id)}"
              title="Unlink sensor">
        <i class="fas fa-unlink"></i>
      </button>
    </div>
  `).join('');
}

_renderLinkedActuators(actuators, plantId) {
  const container = document.getElementById('plant-actuators-list');
  if (!container) return;
  
  if (!actuators || actuators.length === 0) {
    container.innerHTML = '<div class="empty-state">No actuators linked</div>';
    return;
  }
  
  container.innerHTML = actuators.map(actuator => `
    <div class="device-item">
      <div class="device-info">
        <i class="fas fa-tint"></i>
        <div>
          <strong>${escapeHtml(actuator.name || `Actuator ${actuator.actuator_id}`)}</strong>
          <small>${escapeHtml(actuator.type || 'Unknown')}</small>
        </div>
      </div>
      <button class="btn-icon btn-unlink"
              data-action="unlink-actuator"
              data-plant-id="${escapeAttr(plantId)}"
              data-actuator-id="${escapeAttr(actuator.actuator_id)}"
              title="Unlink actuator">
        <i class="fas fa-unlink"></i>
      </button>
    </div>
  `).join('');
}
```

#### 3.4 Update `_wireActionHandlers` to Include New Buttons
Add handlers for:
- `action-link-actuator` button
- `action-unlink-sensor` button
- `action-unlink-actuator` button
- Device tab switching

```javascript
// Add after link-sensor handler
if (e.target.closest('.action-link-actuator')) {
  e.preventDefault();
  const btn = e.target.closest('.action-link-actuator');
  const plantId = btn.dataset.plantId;
  if (window.plantsHub?.uiManager?.openLinkActuatorModal) {
    window.plantsHub.uiManager.openLinkActuatorModal(Number(plantId));
  }
  return;
}

// Unlink sensor
if (e.target.closest('[data-action="unlink-sensor"]')) {
  e.preventDefault();
  const btn = e.target.closest('[data-action="unlink-sensor"]');
  await this._handleUnlinkSensor(btn.dataset.plantId, btn.dataset.sensorId);
  return;
}

// Unlink actuator
if (e.target.closest('[data-action="unlink-actuator"]')) {
  e.preventDefault();
  const btn = e.target.closest('[data-action="unlink-actuator"]');
  await this._handleUnlinkActuator(btn.dataset.plantId, btn.dataset.actuatorId);
  return;
}

// Device tabs
if (e.target.closest('.device-tab')) {
  e.preventDefault();
  const tab = e.target.closest('.device-tab');
  this._switchDeviceTab(tab.dataset.tab);
  return;
}
```

#### 3.5 Add Unlink Handler Methods
```javascript
async _handleUnlinkSensor(plantId, sensorId) {
  if (!confirm('Unlink this sensor from the plant?')) return;
  
  try {
    await window.API.Plant.unlinkPlantFromSensor(Number(plantId), Number(sensorId));
    await this._loadLinkedDevices(plantId);
    this._showToast('Sensor unlinked successfully', 'success');
  } catch (error) {
    console.error('Failed to unlink sensor:', error);
    this._showToast('Failed to unlink sensor', 'error');
  }
}

async _handleUnlinkActuator(plantId, actuatorId) {
  if (!confirm('Unlink this actuator from the plant?')) return;
  
  try {
    await window.API.Plant.unlinkPlantFromActuator(Number(plantId), Number(actuatorId));
    await this._loadLinkedDevices(plantId);
    this._showToast('Actuator unlinked successfully', 'success');
  } catch (error) {
    console.error('Failed to unlink actuator:', error);
    this._showToast('Failed to unlink actuator', 'error');
  }
}

_switchDeviceTab(tabName) {
  const tabs = this.modalEl.querySelectorAll('.device-tab');
  const contents = this.modalEl.querySelectorAll('.device-tab-content');
  
  tabs.forEach(tab => {
    tab.classList.toggle('active', tab.dataset.tab === tabName);
  });
  
  contents.forEach(content => {
    content.classList.toggle('active', content.id === `${tabName}-content`);
  });
}

_showToast(message, type = 'info') {
  // Simple toast notification
  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.textContent = message;
  document.body.appendChild(toast);
  setTimeout(() => toast.remove(), 3000);
}
```

#### 3.6 Call `_loadLinkedDevices` in render method
After rendering main content, add:
```javascript
// Load linked devices asynchronously
this._loadLinkedDevices(plant?.plant_id);
```

---

### Phase 4: Update UI Manager for Actuators
**File**: `static/js/plants/ui-manager.js`

#### 4.1 Add Modal Event Handlers (in bindEvents method, after line 163)
```javascript
// Link actuator modal form handlers
const linkActuatorForm = document.getElementById('link-actuator-form');
if (linkActuatorForm) {
    this.addEventListener(linkActuatorForm, 'submit', (e) => this.handleLinkActuatorSubmit(e));
}

const cancelLinkActuator = document.getElementById('cancel-link-actuator');
if (cancelLinkActuator) {
    this.addEventListener(cancelLinkActuator, 'click', () => {
        const modal = document.getElementById('link-actuator-modal');
        if (modal) modal.hidden = true;
    });
}
```

#### 4.2 Add openLinkActuatorModal Method (after openLinkSensorModal, line ~896)
```javascript
async openLinkActuatorModal(plantId) {
    const modal = document.getElementById('link-actuator-modal');
    const select = document.getElementById('available-actuators');
    const hidden = document.getElementById('link-actuator-plant-id');
    if (!modal || !select || !hidden) return;
    
    hidden.value = plant (Self-Contained Modal Styles)
**File**: `static/css/components.css`

Add styles for device management UI in modalsts
    const plant = this.plants.find(p => Number(p.plant_id) === Number(plantId));
    const unitId = plant?.unit_id || document.body?.dataset?.activeUnitId || null;

    try {
        // Get currently linked actuators to filter them out
        const linkedResp = await window.API.Plant.getPlantActuators(plantId);
        const linkedActuators = linkedResp?.data?.actuators || linkedResp?.actuators || [];
        const linkedIds = new Set(linkedActuators.map(a => Number(a.actuator_id)));
        
        // Get available actuators
        const data = await window.API.Plant.getAvailableActuators(unitId, 'pump');
        const actuators = data?.data?.actuators || data?.actuators || [];
        
        // Filter out already linked actuators
        const availableActuators = actuators.filter(a => !linkedIds.has(Number(a.actuator_id)));
        
        if (!availableActuators || availableActuators.length === 0) {
            select.innerHTML = '<option value="">No actuators available</option>';
        } else {
            select.innerHTML = '<option value="">-- Select actuator --</option>' + 
                availableActuators.map(a => 
                    `<option value="${a.actuator_id}">${a.name || a.actuator_id} (${a.type || 'pump'})</option>`
                ).join('');
        }
    } catch (err) {
        console.error('Failed to load actuators', err);
        select.innerHTML = '<option value="">Failed to load actuators</option>';
    }

    modal.hidden = false;
    modal.classList.add('is-open');
    modal.setAttribute('aria-hidden', 'false');
}
```

#### 4.3 Add handleLinkActuatorSubmit Method (after handleLinkSensorSubmit, line ~920)
```javascript
async handleLinkActuatorSubmit(e) {
    e.preventDefault();
    const form = e.target;
    const plantId = form.plant_id?.value || document.getElementById('link-actuator-plant-id')?.value;
    const actuatorId = form.actuator_id?.value || document.getElementById('available-actuators')?.value;
    
    if (!plantId || !actuatorId) {
        alert('Select an actuator to link');
        return;
    }

    try {
        await window.API.Plant.linkPlantToActuator(Number(plantId), Number(actuatorId));
        alert('Actuator linked successfully');
        const modal = document.getElementById('link-actuator-modal');
        if (modal) {
            modal.hidden = true;
            modal.classList.remove('is-open');
        }
        
        // Refresh plant details modal if open
        if (this.plantDetailsModal) {
            this.plantDetailsModal.open({ plantId: Number(plantId) });
        }
        
        // Refresh plant list
        await this.loadAndRender();
    } catch (err) {
        console.error('Failed to link actuator', err);
        alert('Failed to link actuator');
    }
}
```

#### 4.4 Update openLinkSensorModal to Filter Linked Sensors (line 866)
Add filtering logic similar to actuators:
```javascript
async openLinkSensorModal(plantId) {
    const modal = document.getElementById('link-sensor-modal');
    const select = document.getElementById('available-sensors');
    const hidden = document.getElementById('link-plant-id');
    if (!modal || !select || !hidden) return;
    
    hidden.value = plantId;
    select.innerHTML = '<option value="">Loading...</option>';

    const plant = this.plants.find(p => Number(p.plant_id) === Number(plantId));
    const unitId = plant?.unit_id || document.body?.dataset?.activeUnitId || null;

    try {
        // Get currently linked sensors to filter them out
        const linkedResp = await window.API.Plant.getPlantSensors(plantId);
        const linkedSensors = linkedResp?.data?.sensors || linkedResp?.sensors || [];
        const linkedIds = new Set(linkedSensors.map(s => Number(s.sensor_id)));
        
        // Get available sensors
        const data = await window.API.Plant.getAvailableSensors(unitId);
        const sensors = data?.data?.sensors || data?.sensors || [];
        
        // Filter out already linked sensors
        const availableSensors = sensors.filter(s => !linkedIds.has(Number(s.sensor_id)));
        
        if (!availableSensors || availableSensors.length === 0) {
            select.innerHTML = '<option value="">No sensors available</option>';
        } else {
            select.innerHTML = '<option value="">-- Select sensor --</option>' + 
                availableSensors.map(s => 
                    `<option value="${s.sensor_id}">${s.name || s.sensor_id} (${s.type || ''})</option>`
                ).join('');
        }
    } catch (err) {
        console.error('Failed to load sensors', err);
        select.innerHTML = '<option value="">Failed to load sensors</option>';
    }

    modal.hidden = false;
    modal.classList.add('is-open');
    modal.setAttribute('aria-hidden', 'false');
}
```

---

### Phase 5: Add Styling
**File**: `static/css/components.css`

Add styles for device management UI:
```css
/* Plant Device Management */
.modal-actions-group {
  display: flex;
  gap: var(--space-2);
  flex-wrap: wrap;
}

.modal-action {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-2) var(--space-3);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--surface);
  color: var(--text);
  cursor: pointer;
  transition: all var(--transition-fast);
  font-size: 0.875rem;
}

.modal-action:hover {
  background: var(--surface-hover);
  border-color: var(--brand-500);
  color: var(--brand-600);
}

.plant-devices-section {
  margin-top: var(--space-4);
  border-top: 1px solid var(--border);
  padding-top: var(--space-4);
}

.devices-tabs {
  display: flex;
  gap: var(--space-2);
  border-bottom: 2px solid var(--border);
  margin-bottom: var(--space-3);
}

.device-tab {
  padding: var(--space-2) var(--space-3);
  background: transparent;
  border: none;
  border-bottom: 2px solid transparent;
  cursor: pointer;
  color: var(--text-muted);
  transition: all var(--transition-fast);
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-bottom: -2px;
}

.device-tab:hover {
  color: var(--text);
}

.device-tab.active {
  color: var(--brand-600);
  border-bottom-color: var(--brand-500);
  font-weight: 600;
}

.device-tab-content {
  display: none;
}

.device-tab-content.active {
  display: block;
}

.devices-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.device-item {
  display: flex;
  justify-content: space-between;
  align-items: center; (Self-Contained Approach)

| File | Changes | Lines Added | Complexity |
|------|---------|-------------|------------|
| `static/js/api.js` | Add 6 actuator methods + 1 sensor method | ~70 | Low |
| `static/js/components/plant-details-modal.js` | Create dynamic modals + device mgmt + handlers | ~600 | High |
| `static/css/components.css` | Add device mgmt styles | ~150 | Low |
| `static/js/plants/ui-manager.js` | (Optional) Keep for backward compatibility | ~0 | None |
| `templates/plants.html` | (Optional) Keep old modal or remove | ~0 | None |
| **TOTAL** | | **~820 lines** | **Medium-High** |

**Key Benefit**: Plant-details-modal works identically on dashboard.html and plants.html with zero dependencies on page-specific code.
  gap: var(--space-3);
} (Self-Contained Approach)
1. **Phase 1** (API Layer) - Foundation for everything
2. **Phase 3** (Modal Component - Dynamic Creation) - All UI logic and modals
3. **Phase 5** (Styling) - Polish and UX
4. **Phase 4** (Optional - UI Manager Cleanup) - Remove old code if desired

**Simplified Flow**: API → Component → Styles → Done ✅

.device-info strong {
  displa (Self-Contained Benefits)
- ✅ All API endpoints are already implemented in backend
- ✅ Modal system is centralized in components.css
- ✅ **Works on ANY page** - dashboard, plants, future pages
- ✅ **Zero external dependencies** - no ui-manager required
- ✅ **Single source of truth** - one component handles everything
- ✅ Modals created dynamically on first use
- ✅ Toast notifications built-in
- ⚠️ Slightly more complex single file (~600 lines) vs distributed
- 💡 Consider splitting into separate module later if needed
  color: var(--text-muted);
  font-size: 0.8125rem;
}

.btn-unlink {
  padding: var(--space-2);
  background: var(--danger-50);
  color: var(--danger-600);
  border: 1px solid var(--danger-200);
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.btn-unlink:hover {
  background: var(--danger-100);
  border-color: var(--danger-400);
}

.empty-state {
  padding: var(--space-4);
  text-align: center;
  color: var(--text-muted);
  font-style: italic;
}

.toast {
  position: fixed;
  bottom: var(--space-4);
  right: var(--space-4);
  padding: var(--space-3) var(--space-4);
  border-radius: var(--radius-md);
  background: var(--surface);
  box-shadow: var(--shadow-lg);
  z-index: 10000;
  animation: slideIn 0.3s ease-out;
}

.toast-success {
  background: var(--success-50);
  color: var(--success-700);
  border: 1px solid var(--success-200);
}

.toast-error {
  background: var(--danger-50);
  color: var(--danger-700);
  border: 1px solid var(--danger-200);
}

@keyframes slideIn {
  from {
    transform: translateX(100%);
    opacity: 0;
  }
  to {
    transform: translateX(0);
    opacity: 1;
  }
}
```

---

## Testing Checklist

### Unit Testing
- [ ] API methods return proper data structures
- [ ] Filtering of already-linked devices works correctly
- [ ] Unlink operations call correct API endpoints

### Integration Testing
- [ ] Open plant details modal → shows linked sensors/actuators
- [ ] Click "Sensors" button → opens link-sensor-modal with filtered list
- [ ] Click "Actuators" button → opens link-actuator-modal with filtered list
- [ ] Link sensor → appears in linked sensors list immediately
- [ ] Link actuator → appears in linked actuators list immediately
- [ ] Unlink sensor → removes from list and makes available again
- [ ] Unlink actuator → removes from list and makes available again
- [ ] Switch between tabs → displays correct device lists
- [ ] Delete plant → confirmation + removes plant + closes modal

### UI/UX Testing
- [ ] Modal displays properly on dashboard and plants page
- [ ] Action buttons are clearly labeled and responsive
- [ ] Device lists are readable and scrollable
- [ ] Toast notifications appear and disappear correctly
- [ ] Empty states display when no devices linked
- [ ] Loading states display while fetching data

### Edge Cases
- [ ] Plant with no linked devices
- [ ] All sensors/actuators already linked
- [ ] API error handling and user feedback
- [ ] Multiple rapid link/unlink operations
- [ ] Modal refresh after linking device

---

## File Changes Summary

| File | Changes | Lines Added | Complexity |
|------|---------|-------------|------------|
| `static/js/api.js` | Add 6 actuator methods + 1 sensor method | ~70 | Low |
| `templates/plants.html` | Add link-actuator-modal HTML | ~30 | Low |
| `static/js/components/plant-details-modal.js` | Add device mgmt UI + handlers | ~200 | Medium |
| `static/js/plants/ui-manager.js` | Add actuator modal handlers + filter logic | ~80 | Medium |
| `static/css/components.css` | Add device mgmt styles | ~150 | Low |
| **TOTAL** | | **~530 lines** | **Medium** |

---

## Priority Order
1. **Phase 1** (API Layer) - Foundation for everything
2. **Phase 2** (Actuator Modal HTML) - Required markup
3. **Phase 4** (UI Manager) - Business logic for modals
4. **Phase 3** (Modal Component) - Enhanced UI display
5. **Phase 5** (Styling) - Polish and UX

---

## Notes
- All API endpoints are already implemented in backend
- Modal system is centralized in components.css
- Use existing toast/alert patterns from the application
- Consider adding loading spinners for async operations
- May want to add "Refresh" button to device lists

---

## Future Enhancements (Out of Scope)
- Bulk link/unlink operations
- Drag-and-drop device assignment
- Device health status in lists
- Historical sensor/actuator data preview
- Quick device configuration from modal
