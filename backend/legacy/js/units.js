const API = window.API;
if (!API) {
    throw new Error('API not loaded. Ensure api.js is loaded before units.js');
}

// Global variables
let currentUnitId = null;
let scheduleCounter = 1; // Start at 1 since we have row 0 already
let currentUnitPlantsById = new Map();

// Initialize page
export function initUnitsPage() {
    if (window.__sysgrowUnitsPageInitialized) {
        return;
    }
    window.__sysgrowUnitsPageInitialized = true;

    const init = function() {
        loadUnitsOverview();
        refreshEnvironmentalData();
        setInterval(refreshEnvironmentalData, 30000); // Refresh every 30 seconds
        
        // Initialize event listeners
        setupEventListeners();
        
        // Update camera indicators
        setTimeout(updateCameraIndicators, 1000);
    };

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
}

// =====================================
// UTILITY FUNCTIONS
// =====================================

function showLoading() {
    const overlay = document.getElementById('loadingOverlay');
    if (overlay) overlay.classList.remove('hidden');
}

function hideLoading() {
    const overlay = document.getElementById('loadingOverlay');
    if (overlay) overlay.classList.add('hidden');
}



// =====================================
// MODAL FUNCTIONS (focus management + trap)
// =====================================

let lastFocusedElement = null;
function getFocusable(modal) {
    return modal.querySelectorAll('a[href], button:not([disabled]), textarea, input, select, [tabindex]:not([tabindex="-1"])');
}

function trapFocus(modal, enable = true) {
    const handler = (e) => {
        if (e.key !== 'Tab') return;
        const focusable = getFocusable(modal);
        if (!focusable.length) return;
        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        if (e.shiftKey && document.activeElement === first) {
            e.preventDefault();
            last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
            e.preventDefault();
            first.focus();
        }
    };
    if (enable) {
        modal.__trapHandler = handler;
        modal.addEventListener('keydown', handler);
    } else if (modal.__trapHandler) {
        modal.removeEventListener('keydown', modal.__trapHandler);
        delete modal.__trapHandler;
    }
}

function openModal(modalId) {
    lastFocusedElement = document.activeElement;
    const modal = document.getElementById(modalId);
    if (!modal) return;
    
    modal.classList.add('visible');
    modal.classList.remove('active');
    trapFocus(modal, true);
    const first = modal.querySelector('input, select, textarea, button');
    if (first) first.focus();
}

function closeModal(modalId) {
    const modal = document.getElementById(modalId);
    if (!modal) return;
    
    trapFocus(modal, false);
    modal.classList.remove('visible');
    modal.classList.remove('active');
    if (lastFocusedElement && typeof lastFocusedElement.focus === 'function') {
        lastFocusedElement.focus();
        lastFocusedElement = null;
    }
}

// =====================================
// UNIT MANAGEMENT
// =====================================

// Add/Remove Device Schedule Rows
function addScheduleRow() {
    const container = document.getElementById('deviceSchedulesContainer');
    if (!container) return;
    
    const newRow = document.createElement('div');
    newRow.className = 'schedule-row';
    newRow.setAttribute('data-schedule-index', scheduleCounter);
    
    newRow.innerHTML = `
        <div class="form-row">
            <div class="form-group">
                <label>Device Type</label>
                <select name="device_schedules[${scheduleCounter}][device_type]" class="schedule-device-type">
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
            <div class="form-group">
                <label>Start Time</label>
                <input type="time" name="device_schedules[${scheduleCounter}][start_time]" class="schedule-start-time">
            </div>
            <div class="form-group">
                <label>End Time</label>
                <input type="time" name="device_schedules[${scheduleCounter}][end_time]" class="schedule-end-time">
            </div>
            <div class="form-group-checkbox">
                <label>
                    <input type="checkbox" name="device_schedules[${scheduleCounter}][enabled]" checked>
                    Enabled
                </label>
            </div>
            <div class="form-group-action">
                <button type="button" class="btn-icon btn-danger" 
                        data-action="remove-schedule-row" data-row-index="${scheduleCounter}" title="Remove schedule">
                    <i class="fas fa-trash"></i>
                </button>
            </div>
        </div>
    `;
    
    container.appendChild(newRow);
    scheduleCounter++;
}

function removeScheduleRow(index) {
    const row = document.querySelector(`[data-schedule-index="${index}"]`);
    if (row) {
        row.remove();
    }
}

async function createUnit(event) {
    event.preventDefault();
    const form = event.target;
    const formData = new FormData(form);
    
    // Build dimensions object
    const width = parseFloat(formData.get('dimensions[width]'));
    const height = parseFloat(formData.get('dimensions[height]'));
    const depth = parseFloat(formData.get('dimensions[depth]'));
    const dimensions = (width || height || depth) ? {
        width: width || null,
        height: height || null,
        depth: depth || null
    } : null;
    
    // Build device_schedules object
    const device_schedules = {};
    let scheduleIndex = 0;
    while (formData.has(`device_schedules[${scheduleIndex}][device_type]`)) {
        const deviceType = formData.get(`device_schedules[${scheduleIndex}][device_type]`);
        if (deviceType) {
            const startTime = formData.get(`device_schedules[${scheduleIndex}][start_time]`);
            const endTime = formData.get(`device_schedules[${scheduleIndex}][end_time]`);
            
            // Only add if both times are provided
            if (startTime && endTime) {
                device_schedules[deviceType] = {
                    start_time: startTime,
                    end_time: endTime,
                    enabled: formData.has(`device_schedules[${scheduleIndex}][enabled]`)
                };
            }
        }
        scheduleIndex++;
    }
    
    // Build request payload
    const unitData = {
        name: formData.get('name'),
        location: formData.get('location') || 'Indoor',
        dimensions: dimensions,
        device_schedules: Object.keys(device_schedules).length > 0 ? device_schedules : null,
        camera_enabled: formData.has('camera_enabled'),
        custom_image: null
    };
    
    console.log('Creating unit with data:', unitData);
    
    showLoading();
    try {
        await API.Growth.createUnit(unitData);
        
        window.showToast('Growth unit created successfully!', 'success');
        closeModal('createUnitModal');
        form.reset();
        scheduleCounter = 1; // Reset counter
        location.reload(); // Refresh page to show new unit
        
    } catch (error) {
        window.showToast(`Failed to create growth unit: ${error.message}`, 'error');
    } finally {
        hideLoading();
    }
}

async function deleteUnit(unitId) {
    if (!confirm('Are you sure you want to delete this growth unit? This action cannot be undone.')) {
        return;
    }
    
    showLoading();
    try {
        await API.Growth.deleteUnit(unitId);
        
        window.showToast('Growth unit deleted successfully!', 'success');
        location.reload(); // Refresh page
        
    } catch (error) {
        window.showToast(`Failed to delete growth unit: ${error.message}`, 'error');
    } finally {
        hideLoading();
    }
}

function toggleUnitDetails(unitId) {
    const details = document.getElementById(`details-${unitId}`);
    const button = details.parentNode.querySelector('.unit-toggle');
    const isVisible = !details.classList.contains('hidden');
    
    if (isVisible) {
        details.classList.add('hidden');
        button.querySelector('.toggle-text').textContent = 'Show Details';
        button.querySelector('i').className = 'fas fa-chevron-down';
    } else {
        details.classList.remove('hidden');
        button.querySelector('.toggle-text').textContent = 'Hide Details';
        button.querySelector('i').className = 'fas fa-chevron-up';
        
        // Load detailed data
        loadUnitDetails(unitId);
    }
}

async function loadUnitDetails(unitId) {
    try {
        // Load plants (via plants_api)
        const plantsResp = await API.Plant.listPlants(unitId);
        const plants = (plantsResp.data && plantsResp.data.plants) || plantsResp.plants || [];
        updatePlantsDisplay(unitId, plants);
        
        // Load devices (grouped sensors + actuators)
        const devicesResp = await API.Device.getDevicesByUnit(unitId);
        updateDevicesDisplay(unitId, devicesResp);
        
        // Load thresholds
        const thresholdsResp = await API.Growth.getThresholds(unitId);
        updateThresholdsDisplay(unitId, thresholdsResp.data || thresholdsResp || {});
        
    } catch (error) {
        console.error('Failed to load unit details:', error);
    }
}

function updatePlantsDisplay(unitId, plants) {
    const container = document.getElementById(`plants-list-${unitId}`);
    if (!container) return;

    if (!plants.length) {
        container.innerHTML = '<div class="empty-message">No plants in this unit</div>';
        const countEl = document.getElementById(`plants-count-${unitId}`);
        if (countEl) countEl.textContent = 0;
        return;
    }
    
    const countEl = document.getElementById(`plants-count-${unitId}`);
    if (countEl) countEl.textContent = plants.length;
    
    container.innerHTML = plants.map((plant) => {
        const plantId = plant.plant_id ?? plant.id;
        const plantName = plant.name ?? plant.plant_name ?? (plantId ? `Plant ${plantId}` : 'Plant');
        const plantType = plant.plant_type ?? plant.type ?? 'Unknown';
        const plantStage = plant.current_stage ?? plant.growth_stage ?? '--';

        return `
            <div class="plant-item">
                <div class="plant-info">
                    <strong>${plantName}</strong>
                    <span class="plant-type">${plantType}</span>
                    <span class="plant-stage">${plantStage}</span>
                </div>
                <div class="plant-actions">
                    <button class="btn-icon" data-action="set-active-plant" data-unit-id="${unitId}" data-plant-id="${plantId}"
                            title="Set as active plant">
                        <i class="fas fa-star"></i>
                    </button>
                </div>
            </div>
        `;
    }).join('');
}

function updateDevicesDisplay(unitId, devicesData) {
    const container = document.getElementById(`devices-list-${unitId}`);
    if (!container) return;

    const sensors = devicesData.sensors || [];
    const actuators = devicesData.actuators || [];
    
    if (!sensors.length && !actuators.length) {
        container.innerHTML = '<div class="empty-message">No devices connected</div>';
        return;
    }
    
    let html = '';
    if (sensors.length) {
        html += `<div class="device-group">
            <h5>Sensors (${sensors.length})</h5>
            ${sensors.map(s => `<span class="device-tag sensor">${s.name || `Sensor ${s.id}`}</span>`).join('')}
        </div>`;
    }
    
    if (actuators.length) {
        html += `<div class="device-group">
            <h5>Actuators (${actuators.length})</h5>
            ${actuators.map(a => `<span class="device-tag actuator">${a.name || `Actuator ${a.id}`}</span>`).join('')}
        </div>`;
    }
    
    container.innerHTML = html;
    
    // Update counts in unit card
    const sensorsCount = document.getElementById(`sensors-count-${unitId}`);
    if (sensorsCount) sensorsCount.textContent = sensors.length;
    
    const actuatorsCount = document.getElementById(`actuators-count-${unitId}`);
    if (actuatorsCount) actuatorsCount.textContent = actuators.length;
}

function updateThresholdsDisplay(unitId, thresholds) {
    const container = document.getElementById(`thresholds-list-${unitId}`);
    if (!container) return;

    container.innerHTML = `
        <div class="threshold-grid">
            <div class="threshold-item">
                <span class="threshold-label">Temperature:</span>
                <span class="threshold-value">${thresholds.temperature_threshold || 'Not set'}°C</span>
            </div>
            <div class="threshold-item">
                <span class="threshold-label">Humidity:</span>
                <span class="threshold-value">${thresholds.humidity_threshold || 'Not set'}%</span>
            </div>
            <div class="threshold-item">
                <span class="threshold-label">Soil Moisture:</span>
                <span class="threshold-value">${thresholds.soil_moisture_threshold || 'Not set'}%</span>
            </div>
        </div>
    `;
}

// =====================================
// UNIT MANAGEMENT MODAL
// =====================================

function manageUnit(unitId) {
    currentUnitId = unitId;
    openModal('unitManagementModal');
    switchTab('plants');
}

function switchTab(tabName) {
    // Hide all tabs
    document.querySelectorAll('.tab-content').forEach(tab => {
        tab.classList.remove('active');
    });
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    
    // Show selected tab
    const tabContent = document.getElementById(`${tabName}Tab`);
    if (tabContent) tabContent.classList.add('active');
    
    const tabBtn = document.querySelector(`[data-action="switch-tab"][data-tab="${tabName}"]`);
    if (tabBtn) tabBtn.classList.add('active');
    
    // Load tab-specific data
    loadManagementData(tabName);
}

async function loadManagementData(activeTab = 'plants') {
    if (!currentUnitId) return;
    
    try {
        if (activeTab === 'plants') {
            const response = await API.Plant.listPlants(currentUnitId);
            const payload = response?.data ?? response ?? {};
            const plants = Array.isArray(payload)
                ? payload
                : payload?.plants || response?.plants || [];
            loadPlantsManagement(plants);
        } else if (activeTab === 'devices') {
            const devices = await API.Device.getDevicesByUnit(currentUnitId);
            loadDevicesManagement(devices || {});
        } else if (activeTab === 'schedule') {
            await loadScheduleManagement();
        } else if (activeTab === 'thresholds') {
            const thresholds = await API.Growth.getThresholds(currentUnitId);
            loadThresholdsManagement(thresholds.data || thresholds || {});
        }
    } catch (error) {
        console.error('Failed to load management data:', error);
    }
}

function loadPlantsManagement(plants) {
    const container = document.getElementById('plantsManagementContent');
    if (!container) return;

    currentUnitPlantsById = new Map();
    plants.forEach((plant) => {
        const plantId = plant.plant_id ?? plant.id;
        if (plantId !== null && plantId !== undefined) {
            currentUnitPlantsById.set(String(plantId), plant);
        }
    });

    if (!plants.length) {
        container.innerHTML = '<div class="empty-state-small">No plants in this unit</div>';
        return;
    }
    
    container.innerHTML = `
        <div class="plants-grid">
            ${plants.map((plant) => {
                const plantId = plant.plant_id ?? plant.id;
                const plantName = plant.name ?? plant.plant_name ?? (plantId ? `Plant ${plantId}` : 'Plant');
                const plantType = plant.plant_type ?? plant.type ?? 'Unknown';
                const plantStage = plant.current_stage ?? plant.growth_stage ?? '--';
                const daysInStage = plant.days_in_stage ?? plant.daysInStage ?? 0;

                return `
                    <div class="plant-card">
                        <div class="plant-header">
                            <h4>${plantName}</h4>
                            <div class="plant-actions">
                                <button class="btn-icon" data-action="update-plant-stage" data-plant-id="${plantId}" title="Update stage">
                                    <i class="fas fa-edit"></i>
                                </button>
                                <button class="btn-icon danger" data-action="remove-plant" data-plant-id="${plantId}" title="Remove plant">
                                    <i class="fas fa-trash"></i>
                                </button>
                            </div>
                        </div>
                        <div class="plant-details">
                            <span class="detail-item">Type: ${plantType}</span>
                            <span class="detail-item">Stage: ${plantStage}</span>
                            <span class="detail-item">Days: ${daysInStage}</span>
                        </div>
                        <button class="btn btn-sm btn-outline" data-action="set-active-plant" data-unit-id="${currentUnitId}" data-plant-id="${plantId}">
                            Set Active
                        </button>
                    </div>
                `;
            }).join('')}
        </div>
    `;
}

function loadDevicesManagement(devicesData) {
    const container = document.getElementById('devicesManagementContent');
    if (!container) return;

    const sensors = devicesData.sensors || [];
    const actuators = devicesData.actuators || [];
    
    container.innerHTML = `
        <div class="device-group">
            <h5>Sensors (${sensors.length})</h5>
            ${sensors.length
                ? sensors.map(s => `
                    <span class="device-tag sensor">
                        ${s.name || `Sensor ${s.id}`}
                        <button type="button" class="device-tag-action" data-action="unlink-device" data-device-type="sensor" data-device-id="${s.id}" title="Remove sensor" aria-label="Remove sensor">
                            <i class="fas fa-times" aria-hidden="true"></i>
                        </button>
                    </span>
                `).join('')
                : '<div class="empty-message">No sensors connected</div>'}
        </div>
        <div class="device-group">
            <h5>Actuators (${actuators.length})</h5>
            ${actuators.length
                ? actuators.map(a => `
                    <span class="device-tag actuator">
                        ${a.name || `Actuator ${a.id}`}
                        <button type="button" class="device-tag-action" data-action="unlink-device" data-device-type="actuator" data-device-id="${a.id}" title="Remove actuator" aria-label="Remove actuator">
                            <i class="fas fa-times" aria-hidden="true"></i>
                        </button>
                    </span>
                `).join('')
                : '<div class="empty-message">No actuators connected</div>'}
        </div>
    `;
}

function loadThresholdsManagement(thresholds) {
    const temp = document.getElementById('tempThreshold');
    if (temp) temp.value = thresholds.temperature_threshold || '';
    
    const hum = document.getElementById('humidityThreshold');
    if (hum) hum.value = thresholds.humidity_threshold || '';
    
    const soil = document.getElementById('soilThreshold');
    if (soil) soil.value = thresholds.soil_moisture_threshold || '';
}

// =====================================
// SCHEDULE MANAGEMENT
// =====================================

async function loadScheduleManagement() {
    if (!currentUnitId) return;
    
    const container = document.getElementById('scheduleManagementContent');
    if (!container) return;
    
    try {
        const result = await API.Growth.getSchedules(currentUnitId);
        const schedules = result?.device_schedules || {};
        
        if (Object.keys(schedules).length === 0) {
            container.innerHTML = `
                <div class="empty-state-small">
                    <i class="fas fa-clock"></i>
                    <p>No device schedules configured</p>
                    <small>Click "Add Schedule" to create your first device schedule</small>
                </div>
            `;
            return;
        }
        
        container.innerHTML = `
            <div class="schedules-table">
                <table class="data-table">
                    <thead>
                        <tr>
                            <th scope="col"><i class="fas fa-microchip"></i> Device</th>
                            <th scope="col"><i class="fas fa-clock"></i> Start Time</th>
                            <th scope="col"><i class="fas fa-clock"></i> End Time</th>
                            <th scope="col"><i class="fas fa-toggle-on"></i> Status</th>
                            <th scope="col"><i class="fas fa-cog"></i> Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${Object.entries(schedules).map(([deviceType, schedule]) => `
                            <tr>
                                <td>
                                    <span class="device-badge">${deviceType}</span>
                                </td>
                                <td>${schedule.start_time}</td>
                                <td>${schedule.end_time}</td>
                                <td>
                                    ${schedule.enabled ? 
                                        '<span class="badge badge-success"><i class="fas fa-check"></i> Enabled</span>' :
                                        '<span class="badge badge-secondary"><i class="fas fa-times"></i> Disabled</span>'
                                    }
                                </td>
                                <td class="actions">
                                    <button class="btn-icon" data-action="edit-schedule" data-device-type="${deviceType}" data-schedule='${JSON.stringify(schedule).replace(/'/g, "&apos;")}' 
                                            title="Edit schedule">
                                        <i class="fas fa-edit"></i>
                                    </button>
                                    <button class="btn-icon btn-danger" data-action="delete-schedule" data-device-type="${deviceType}" 
                                            title="Delete schedule">
                                        <i class="fas fa-trash"></i>
                                    </button>
                                </td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>
            
            <!-- Active Devices Indicator -->
            <div class="active-devices-section">
                <h4><i class="fas fa-bolt"></i> Currently Active Devices</h4>
                <div id="activeDevicesIndicator" class="active-devices-list">
                    <div class="loading-small">Checking...</div>
                </div>
            </div>
        `;
        
        // Load active devices
        loadActiveDevices();
        
    } catch (error) {
        console.error('Failed to load schedules:', error);
        container.innerHTML = '<div class="error-message">Failed to load schedules</div>';
    }
}

async function loadActiveDevices() {
    if (!currentUnitId) return;
    
    try {
        const result = await API.Growth.getActiveDevices(currentUnitId);
        const container = document.getElementById('activeDevicesIndicator');
        if (!container) return;

        const activeDevices = result?.active_devices || [];
        
        if (activeDevices.length === 0) {
            container.innerHTML = '<span class="text-muted">No devices currently active</span>';
        } else {
            container.innerHTML = activeDevices.map(device => 
                `<span class="badge badge-success pulse">
                    <i class="fas fa-circle"></i> ${device}
                </span>`
            ).join('');
        }
    } catch (error) {
        console.error('Failed to load active devices:', error);
    }
}

function openScheduleForm() {
    const container = document.getElementById('scheduleFormContainer');
    if (container) container.classList.remove('hidden');
    
    const form = document.getElementById('deviceScheduleForm');
    if (form) form.reset();
}

function closeScheduleForm() {
    const container = document.getElementById('scheduleFormContainer');
    if (container) container.classList.add('hidden');
}

async function saveDeviceSchedule(event) {
    event.preventDefault();
    
    if (!currentUnitId) {
        window.showToast('No unit selected', 'error');
        return;
    }
    
    const form = event.target;
    const formData = new FormData(form);
    
    const scheduleData = {
        device_type: formData.get('device_type'),
        start_time: formData.get('start_time'),
        end_time: formData.get('end_time'),
        enabled: formData.has('enabled')
    };
    
    try {
        showLoading();
        await API.Growth.setDeviceSchedule(currentUnitId, scheduleData);
        
        window.showToast(`Schedule for ${scheduleData.device_type} saved successfully`, 'success');
        closeScheduleForm();
        loadScheduleManagement();
        
    } catch (error) {
        window.showToast(`Failed to save schedule: ${error.message}`, 'error');
    } finally {
        hideLoading();
    }
}

async function editSchedule(deviceType, currentSchedule) {
    // Open form with current values
    openScheduleForm();
    
    // Parse schedule if it's a string
    const schedule = typeof currentSchedule === 'string' ? 
        JSON.parse(currentSchedule.replace(/&quot;/g, '"')) : currentSchedule;
    
    const typeEl = document.getElementById('scheduleDeviceType');
    if (typeEl) typeEl.value = deviceType;
    
    const startEl = document.getElementById('scheduleStartTime');
    if (startEl) startEl.value = schedule.start_time;
    
    const endEl = document.getElementById('scheduleEndTime');
    if (endEl) endEl.value = schedule.end_time;
    
    const enabledEl = document.getElementById('scheduleEnabled');
    if (enabledEl) enabledEl.checked = schedule.enabled;
}

async function deleteSchedule(deviceType) {
    if (!confirm(`Delete schedule for ${deviceType}?`)) {
        return;
    }
    
    try {
        showLoading();
        await API.Growth.deleteDeviceSchedule(currentUnitId, deviceType);
        
        window.showToast(`Schedule for ${deviceType} deleted successfully`, 'success');
        loadScheduleManagement();
        
    } catch (error) {
        window.showToast(`Failed to delete schedule: ${error.message}`, 'error');
    } finally {
        hideLoading();
    }
}

function showSchedule(unitId) {
    currentUnitId = unitId;
    openModal('unitManagementModal');
    switchTab('schedule');
}

// =====================================
// CAMERA FUNCTIONS
// =====================================

let currentCameraUnitId = null;

function _normalizeCameraStatus(status) {
    const payload = status?.data ?? status ?? {};
    return {
        camera_enabled: payload.camera_enabled ?? false,
        camera_active: payload.camera_active ?? payload.camera_running ?? false,
        camera_running: payload.camera_running ?? payload.camera_active ?? false,
        settings: payload.settings ?? {},
    };
}

async function toggleCamera(unitId) {
    try {
        // Get current camera status
        const status = _normalizeCameraStatus(await API.Growth.getCameraStatus(unitId));

        if (status.camera_active) {
            // Open camera modal showing live feed
            openCameraModal(unitId);
        } else {
            // Start camera and open modal
            await startCameraForUnit(unitId);
            openCameraModal(unitId);
        }
    } catch (error) {
        console.error('Failed to toggle camera:', error);
        window.showToast('Failed to toggle camera', 'error');
    }
}

function openCameraModal(unitId) {
    currentCameraUnitId = unitId;
    
    // Update modal title
    const modalTitle = document.getElementById('cameraModalTitle');
    if (modalTitle) {
        modalTitle.textContent = `Camera Control - Unit ${unitId}`;
    }
    
    // Set fullscreen link
    const fullscreenBtn = document.getElementById('fullscreenBtn');
    if (fullscreenBtn) {
        fullscreenBtn.href = `/fullscreen?unit_id=${unitId}`;
    }
    
    // Show modal
    openModal('cameraModal');
    
    // Load camera status and update UI
    updateCameraModalUI(unitId);
}

async function updateCameraModalUI(unitId) {
    try {
        const status = _normalizeCameraStatus(await API.Growth.getCameraStatus(unitId));
        const isRunning = status.camera_active;
        
        const startBtn = document.getElementById('startCameraBtn');
        const stopBtn = document.getElementById('stopCameraBtn');
        const feedImg = document.getElementById('cameraFeedImg');
        const placeholder = document.getElementById('cameraPlaceholder');
        
        if (isRunning) {
            // Camera is running - show feed
            startBtn.classList.add('hidden');
            stopBtn.classList.remove('hidden');
            
            if (feedImg && placeholder) {
                feedImg.src = API.Growth.getCameraFeedUrl(unitId);
                feedImg.classList.remove('hidden');
                placeholder.classList.add('hidden');
                
                // Handle feed error
                feedImg.onerror = function() {
                    placeholder.innerHTML = '<i class="fas fa-exclamation-triangle"></i><p>Camera feed not available</p>';
                    placeholder.classList.remove('hidden');
                    feedImg.classList.add('hidden');
                };
            }
        } else {
            // Camera is stopped
            startBtn.classList.remove('hidden');
            stopBtn.classList.add('hidden');
            
            if (feedImg && placeholder) {
                feedImg.classList.add('hidden');
                placeholder.innerHTML = '<i class="fas fa-camera"></i><p>Start the camera to see live feed</p>';
                placeholder.classList.remove('hidden');
            }
        }
    } catch (error) {
        console.error('Failed to get camera status:', error);
    }
}

async function startCameraForUnit(unitId) {
    try {
        await API.Growth.startCamera(unitId);
        
        const icon = document.getElementById(`camera-icon-${unitId}`);
        if (icon) icon.className = 'fas fa-video';
        
        window.showToast('Camera started', 'success');
        
        // Update modal UI if it's open
        if (currentCameraUnitId === unitId) {
            setTimeout(() => updateCameraModalUI(unitId), 1000);
        }
    } catch (error) {
        console.error('Failed to start camera:', error);
        window.showToast('Failed to start camera', 'error');
    }
}

async function stopCameraForUnit(unitId) {
    try {
        await API.Growth.stopCamera(unitId);
        
        const icon = document.getElementById(`camera-icon-${unitId}`);
        if (icon) icon.className = 'fas fa-camera';
        
        window.showToast('Camera stopped', 'success');
        
        // Update modal UI if it's open
        if (currentCameraUnitId === unitId) {
            updateCameraModalUI(unitId);
        }
    } catch (error) {
        console.error('Failed to stop camera:', error);
        window.showToast('Failed to stop camera', 'error');
    }
}

async function capturePhoto() {
    if (!currentCameraUnitId) return;
    
    try {
        await API.Growth.capturePhoto(currentCameraUnitId);
        window.showToast('Photo captured successfully!', 'success');
    } catch (error) {
        console.error('Failed to capture photo:', error);
        window.showToast('Failed to capture photo', 'error');
    }
}

// Check camera availability for each unit
let _cameraIndicatorsInFlight = false;
let _cameraIndicatorsLastRun = 0;
async function updateCameraIndicators() {
    const now = Date.now();
    if (_cameraIndicatorsInFlight) return;
    // Prevent noisy repeated calls if init runs more than once
    if (_cameraIndicatorsLastRun && (now - _cameraIndicatorsLastRun) < 10000) return;
    _cameraIndicatorsLastRun = now;
    _cameraIndicatorsInFlight = true;

    const units = document.querySelectorAll('.unit-card[data-unit-id]');
    
    for (const unitCard of units) {
        const unitId = parseInt(unitCard.dataset.unitId);
        if (!unitId) continue;

        const indicator = document.getElementById(`camera-indicator-${unitId}`);
        if (!indicator) continue;
        
        try {
            const status = _normalizeCameraStatus(await API.Growth.getCameraStatus(unitId));

            if (status.camera_enabled) {
                indicator.classList.remove('hidden');
                indicator.title = status.camera_active ? 'Camera active' : 'Camera configured';
            } else {
                indicator.classList.add('hidden');
                indicator.title = 'Camera not configured';
            }

            indicator.classList.toggle('camera-active', Boolean(status.camera_active));
        } catch (error) {
            // Camera not configured or error - keep hidden
            console.debug(`Camera not available for unit ${unitId}`);
            indicator.classList.add('hidden');
            indicator.classList.remove('camera-active');
            indicator.title = 'Camera not available';
        }
    }

    _cameraIndicatorsInFlight = false;
}

// =====================================
// PLANT MANAGEMENT
// =====================================

function openAddPlantModal() {
    if (!currentUnitId) {
        window.showToast('No unit selected', 'error');
        return;
    }

    const form = document.getElementById('addPlantForm');
    if (form) {
        form.reset();
        const days = form.querySelector('[name="days_in_stage"]');
        if (days) days.value = 0;
    }

    openModal('addPlantModal');
}

async function addPlant(event) {
    event.preventDefault();
    if (!currentUnitId) {
        window.showToast('No unit selected', 'error');
        return;
    }

    const form = event.target;
    const formData = new FormData(form);
    const payload = {
        name: (formData.get('name') || '').trim(),
        plant_type: (formData.get('plant_type') || '').trim(),
        current_stage: (formData.get('current_stage') || '').trim(),
        days_in_stage: parseInt(formData.get('days_in_stage') || '0', 10) || 0,
    };

    if (!payload.name || !payload.plant_type || !payload.current_stage) {
        window.showToast('Please fill in all required fields', 'warning');
        return;
    }

    showLoading();
    try {
        await API.Plant.addPlant(currentUnitId, payload);
        window.showToast('Plant added successfully', 'success');
        closeModal('addPlantModal');
        await loadManagementData('plants');
        await loadUnitDetails(currentUnitId);
        await loadUnitsOverview();
    } catch (error) {
        window.showToast(error.message || 'Failed to add plant', 'error');
    } finally {
        hideLoading();
    }
}

function openUpdatePlantStageModal(plantId) {
    if (!plantId) {
        window.showToast('Plant not found', 'error');
        return;
    }

    const form = document.getElementById('updatePlantStageForm');
    if (form) {
        form.reset();
        const plantIdEl = document.getElementById('updatePlantStagePlantId');
        if (plantIdEl) plantIdEl.value = plantId;

        const plant = currentUnitPlantsById.get(String(plantId));
        const stage = plant?.current_stage ?? plant?.growth_stage ?? '';
        const days = plant?.days_in_stage ?? plant?.daysInStage ?? 0;

        const stageSelect = form.querySelector('[name="stage"]');
        if (stageSelect && stage) stageSelect.value = stage;

        const daysInput = form.querySelector('[name="days_in_stage"]');
        if (daysInput) daysInput.value = days;
    }

    openModal('updatePlantStageModal');
}

async function updatePlantStageFromModal(event) {
    event.preventDefault();

    const form = event.target;
    const formData = new FormData(form);
    const plantId = formData.get('plant_id');
    const stage = (formData.get('stage') || '').trim();
    const daysInStage = parseInt(formData.get('days_in_stage') || '0', 10) || 0;

    if (!plantId || !stage) {
        window.showToast('Stage is required', 'warning');
        return;
    }

    showLoading();
    try {
        await API.Plant.updatePlantStage(plantId, { stage, days_in_stage: daysInStage });
        window.showToast('Plant stage updated', 'success');
        closeModal('updatePlantStageModal');
        await loadManagementData('plants');
        await loadUnitDetails(currentUnitId);
    } catch (error) {
        window.showToast(error.message || 'Failed to update plant stage', 'error');
    } finally {
        hideLoading();
    }
}

async function setActivePlant(unitId, plantId) {
    try {
        await API.Plant.setActivePlant(unitId, plantId);

        window.showToast('Active plant updated', 'success');
        await loadManagementData('plants');
        await loadUnitsOverview();
    } catch (error) {
        window.showToast(error.message || 'Failed to set active plant', 'error');
    }
}

async function removePlant(plantId) {
    if (!confirm('Are you sure you want to remove this plant?')) return;
    
    try {
        await API.Plant.removePlant(currentUnitId, plantId);
        
        window.showToast('Plant removed successfully', 'success');
        await loadManagementData('plants');
        await loadUnitDetails(currentUnitId);
        await loadUnitsOverview();
    } catch (error) {
        window.showToast(error.message || 'Failed to remove plant', 'error');
    }
}

// =====================================
// DEVICE MANAGEMENT
// =====================================

function _setSectionEnabled(section, enabled) {
    if (!section) return;
    section.querySelectorAll('input, select, textarea, button').forEach((el) => {
        // Keep buttons clickable for UX even when disabled, but disable form controls.
        if (el.tagName === 'BUTTON') return;
        el.disabled = !enabled;
    });
}

function setLinkDeviceKind(kind) {
    const sensorFields = document.getElementById('linkDeviceSensorFields');
    const actuatorFields = document.getElementById('linkDeviceActuatorFields');
    if (!sensorFields || !actuatorFields) return;

    const isSensor = kind === 'sensor';
    sensorFields.classList.toggle('hidden', !isSensor);
    actuatorFields.classList.toggle('hidden', isSensor);

    _setSectionEnabled(sensorFields, isSensor);
    _setSectionEnabled(actuatorFields, !isSensor);
}

function openLinkDeviceModal() {
    if (!currentUnitId) {
        window.showToast('No unit selected', 'error');
        return;
    }

    const form = document.getElementById('linkDeviceForm');
    if (form) {
        form.reset();
        const kindEl = form.querySelector('[name="device_kind"]');
        if (kindEl) kindEl.value = 'sensor';
        setLinkDeviceKind('sensor');
    }

    openModal('linkDeviceModal');
}

function _optionalInt(value) {
    if (value === null || value === undefined) return undefined;
    const trimmed = String(value).trim();
    if (!trimmed) return undefined;
    const parsed = parseInt(trimmed, 10);
    return Number.isFinite(parsed) ? parsed : undefined;
}

async function linkDevice(event) {
    event.preventDefault();
    if (!currentUnitId) {
        window.showToast('No unit selected', 'error');
        return;
    }

    const form = event.target;
    const formData = new FormData(form);
    const kind = (formData.get('device_kind') || 'sensor').toString();
    const name = (formData.get('name') || '').toString().trim();

    if (!name) {
        window.showToast('Device name is required', 'warning');
        return;
    }

    const unitId = parseInt(currentUnitId, 10);
    if (!Number.isFinite(unitId)) {
        window.showToast('Invalid unit', 'error');
        return;
    }

    showLoading();
    try {
        if (kind === 'sensor') {
            const type = (formData.get('sensor_type') || '').toString();
            const model = (formData.get('sensor_model') || '').toString();
            const protocol = (formData.get('sensor_protocol') || 'GPIO').toString();
            const gpioPin = _optionalInt(formData.get('sensor_gpio_pin'));
            const esp32Id = _optionalInt(formData.get('sensor_esp32_id'));
            const i2cAddress = (formData.get('i2c_address') || '').toString().trim();
            const mqttTopic = (formData.get('mqtt_topic') || '').toString().trim();
            const zigbeeAddress = (formData.get('zigbee_address') || '').toString().trim();

            if (!type || !model) {
                window.showToast('Sensor type and model are required', 'warning');
                return;
            }

            const protocolLower = protocol.toLowerCase();
            if (protocolLower === 'mqtt' && !mqttTopic) {
                window.showToast('MQTT topic is required for MQTT sensors', 'warning');
                return;
            }
            if (protocolLower === 'i2c' && i2cAddress && !i2cAddress.startsWith('0x')) {
                window.showToast('I2C address must start with 0x', 'warning');
                return;
            }

            const payload = {
                unit_id: unitId,
                name,
                type,
                model,
                protocol,
                gpio_pin: gpioPin,
                i2c_address: i2cAddress || undefined,
                mqtt_topic: mqttTopic || undefined,
                zigbee_address: zigbeeAddress || undefined,
                esp32_id: esp32Id,
            };

            const result = await API.Device.addSensor(payload);
            window.showToast(result?.message || 'Sensor linked successfully', 'success');
        } else if (kind === 'actuator') {
            const type = (formData.get('actuator_type') || '').toString();
            const communicationType = (formData.get('actuator_protocol') || 'GPIO').toString();
            const gpioPin = _optionalInt(formData.get('actuator_gpio_pin'));
            const esp32Id = _optionalInt(formData.get('actuator_esp32_id'));

            if (!type) {
                window.showToast('Actuator type is required', 'warning');
                return;
            }

            const payload = {
                unit_id: unitId,
                name,
                type,
                communication_type: communicationType,
                gpio_pin: gpioPin,
                esp32_id: esp32Id,
            };

            const result = await API.Device.addActuator(payload);
            window.showToast(result?.message || 'Actuator linked successfully', 'success');
        } else {
            window.showToast('Invalid device kind', 'error');
            return;
        }

        closeModal('linkDeviceModal');
        await loadManagementData('devices');
        await loadUnitDetails(currentUnitId);
        await loadUnitsOverview();
    } catch (error) {
        window.showToast(error.message || 'Failed to link device', 'error');
    } finally {
        hideLoading();
    }
}

async function unlinkDevice(deviceType, deviceId) {
    const type = (deviceType || '').toString();
    if (!deviceId || !type) {
        window.showToast('Device not found', 'error');
        return;
    }

    const label = type === 'actuator' ? 'actuator' : 'sensor';
    if (!confirm(`Remove this ${label} from the unit?`)) return;

    showLoading();
    try {
        if (type === 'actuator') {
            await API.Device.deleteActuator(deviceId);
        } else {
            await API.Device.deleteSensor(deviceId);
        }

        window.showToast(`${label} removed`, 'success');
        await loadManagementData('devices');
        await loadUnitDetails(currentUnitId);
        await loadUnitsOverview();
    } catch (error) {
        window.showToast(error.message || `Failed to remove ${label}`, 'error');
    } finally {
        hideLoading();
    }
}

// =====================================
// THRESHOLDS MANAGEMENT
// =====================================

async function updateThresholds(event) {
    event.preventDefault();
    const form = event.target;
    const formData = new FormData(form);
    
    const thresholds = {
        temperature_threshold: parseFloat(formData.get('temperature_threshold')),
        humidity_threshold: parseFloat(formData.get('humidity_threshold')),
        soil_moisture_threshold: parseFloat(formData.get('soil_moisture_threshold'))
    };
    
    try {
        await API.Growth.setThresholds(currentUnitId, thresholds);
        
        window.showToast('Thresholds updated successfully', 'success');
    } catch (error) {
        window.showToast('Failed to update thresholds', 'error');
    }
}

// =====================================
// OVERVIEW AND REFRESH
// =====================================

async function loadUnitsOverview() {
    try {
        const units = await API.Growth.listUnits();
        updateOverviewStats(units.data || units || []);
    } catch (error) {
        console.error('Failed to load units overview:', error);
    }
}

function updateOverviewStats(units) {
    const totalUnitsEl = document.getElementById('totalUnits');
    if (totalUnitsEl) totalUnitsEl.textContent = units.length;
    
    let totalPlants = 0;
    let totalDevices = 0;
    let activeCameras = 0;

    units.forEach(unit => {
        totalPlants += unit.plant_count || 0;
        totalDevices += unit.device_count || 0;
        if (unit.camera_enabled) {
            activeCameras += 1;
        }

        // Update per-unit cards if present
        const unitId = unit.id || unit.unit_id;
        if (unitId) {
            const plantEl = document.getElementById(`plants-count-${unitId}`);
            if (plantEl) {
                plantEl.textContent = unit.plant_count ?? 0;
            }
        }
    });

    const activePlantsEl = document.getElementById('activePlants');
    if (activePlantsEl) activePlantsEl.textContent = totalPlants;
    
    const connectedDevicesEl = document.getElementById('connectedDevices');
    if (connectedDevicesEl) connectedDevicesEl.textContent = totalDevices;
    
    const activeCamerasEl = document.getElementById('activeCameras');
    if (activeCamerasEl) activeCamerasEl.textContent = activeCameras;
}

async function refreshAllUnits() {
    showLoading();
    try {
        await loadUnitsOverview();
        await refreshEnvironmentalData();
        window.showToast('Data refreshed successfully', 'success');
    } catch (error) {
        showToast('Failed to refresh data', 'error');
    } finally {
        hideLoading();
    }
}

const ENV_METRICS = [
    { key: 'temperature', label: 'Temperature', icon: 'thermometer-half', unit: '°C', decimals: 1, aliases: ['temp', 'temp_c'] },
    { key: 'humidity', label: 'Humidity', icon: 'tint', unit: '%', decimals: 0 },
    { key: 'soil_moisture', label: 'Soil Moisture', icon: 'seedling', unit: '%', decimals: 0, aliases: ['moisture'] },
    { key: 'co2_ppm', label: 'CO₂', icon: 'cloud', unit: 'ppm', decimals: 0, aliases: ['co2'] },
    { key: 'voc_ppb', label: 'VOC', icon: 'smog', unit: 'ppb', decimals: 0, aliases: ['voc'] },
    { key: 'aqi', label: 'Air Quality', icon: 'wind', unit: '', decimals: 0 },
    { key: 'pressure', label: 'Pressure', icon: 'compress-arrows-alt', unit: 'hPa', decimals: 0 },
    { key: 'illuminance', label: 'Light', icon: 'sun', unit: 'lx', decimals: 0, aliases: ['lux', 'light_intensity'] },
    { key: 'ph', label: 'pH', icon: 'flask', unit: '', decimals: 1 },
    { key: 'ec', label: 'EC', icon: 'bolt', unit: '', decimals: 1 },
];

function _formatMetricValue(value, decimals) {
    if (value === null || value === undefined || value === '') return null;
    if (typeof value === 'number' && Number.isFinite(value)) {
        return value.toFixed(decimals);
    }
    const asNum = Number(value);
    if (Number.isFinite(asNum)) {
        return asNum.toFixed(decimals);
    }
    return String(value);
}

function _pickMetricValue(reading, metric) {
    if (!reading || typeof reading !== 'object') return undefined;
    if (Object.prototype.hasOwnProperty.call(reading, metric.key)) {
        return reading[metric.key];
    }
    const aliases = metric.aliases || [];
    for (const alias of aliases) {
        if (Object.prototype.hasOwnProperty.call(reading, alias)) {
            return reading[alias];
        }
    }
    return undefined;
}

function renderEnvironmentalChips(unitId, latestReading) {
    const container = document.getElementById(`env-chips-${unitId}`);
    if (!container) return;

    const reading = latestReading && typeof latestReading === 'object' ? latestReading : {};
    const ignoredKeys = new Set(['timestamp', 'quality_score', 'reading_id', 'sensor_id', 'unit_id']);

    container.textContent = '';

    const renderedKeys = new Set();
    for (const metric of ENV_METRICS) {
        const rawValue = _pickMetricValue(reading, metric);
        if (rawValue === undefined || rawValue === null || rawValue === '') continue;

        const formatted = _formatMetricValue(rawValue, metric.decimals);
        if (formatted === null) continue;

        const chip = document.createElement('span');
        chip.className = 'env-chip';
        chip.title = metric.label;
        chip.setAttribute('aria-label', metric.label);

        const icon = document.createElement('i');
        icon.className = `fas fa-${metric.icon}`;
        icon.setAttribute('aria-hidden', 'true');

        const valueEl = document.createElement('span');
        valueEl.className = 'env-chip-value';
        valueEl.textContent = `${formatted}${metric.unit}`;

        chip.append(icon, valueEl);
        container.appendChild(chip);

        renderedKeys.add(metric.key);
        (metric.aliases || []).forEach(a => renderedKeys.add(a));
    }

    // Render any extra numeric readings we don't recognize, so nothing is hidden.
    const extra = Object.keys(reading)
        .filter(key => !ignoredKeys.has(key) && !renderedKeys.has(key))
        .sort();

    for (const key of extra) {
        const rawValue = reading[key];
        if (rawValue === null || rawValue === undefined || rawValue === '') continue;
        if (typeof rawValue === 'object') continue;

        const chip = document.createElement('span');
        chip.className = 'env-chip';
        chip.title = key;
        chip.setAttribute('aria-label', key);

        const icon = document.createElement('i');
        icon.className = 'fas fa-chart-line';
        icon.setAttribute('aria-hidden', 'true');

        const valueEl = document.createElement('span');
        valueEl.className = 'env-chip-value';
        valueEl.textContent = String(rawValue);

        chip.append(icon, valueEl);
        container.appendChild(chip);
    }

    if (!container.children.length) {
        const chip = document.createElement('span');
        chip.className = 'env-chip is-muted';
        chip.title = 'No sensor data';
        chip.setAttribute('aria-label', 'No sensor data');

        const icon = document.createElement('i');
        icon.className = 'fas fa-chart-line';
        icon.setAttribute('aria-hidden', 'true');

        const valueEl = document.createElement('span');
        valueEl.className = 'env-chip-value';
        valueEl.textContent = '--';

        chip.append(icon, valueEl);
        container.appendChild(chip);
    }
}

async function refreshEnvironmentalData() {
    const unitCards = document.querySelectorAll('.unit-card[data-unit-id]');
    const unitIds = Array.from(unitCards)
        .map(card => parseInt(card.dataset.unitId, 10))
        .filter(Number.isFinite);

    await Promise.all(unitIds.map(async (unitId) => {
        try {
            const overview = await API.Analytics.getSensorsOverview(unitId);
            renderEnvironmentalChips(unitId, overview?.latest_reading);
        } catch (error) {
            console.error(`Failed to load sensor overview for unit ${unitId}:`, error);
            renderEnvironmentalChips(unitId, null);
        }

        await loadUnitHealthMetrics(unitId);
    }));
}

// =====================================
// HEALTH METRICS
// =====================================

async function loadUnitHealthMetrics(unitId) {
    try {
        // Fetch health metrics from API
        const response = await API.Insights.getUnitHealth(unitId);
        
        if (response) {
            updateHealthDisplay(unitId, response);
        }
    } catch (error) {
        console.error(`Failed to load health metrics for unit ${unitId}:`, error);
        // Set default values on error
        updateHealthDisplay(unitId, {
            overall_score: 0,
            plant_health: 0,
            device_health: 0,
            environmental_health: 0
        });
    }
}

function updateHealthDisplay(unitId, healthData) {
    const overallScore = Math.round(healthData.overall_score || 0);
    const plantHealth = Math.round(healthData.plant_health || 0);
    const deviceHealth = Math.round(healthData.device_health || 0);
    const envHealth = Math.round(healthData.environmental_health || 0);
    
    // Update overall health score
    const healthScoreElement = document.getElementById(`health-score-${unitId}`);
    if (healthScoreElement) {
        healthScoreElement.textContent = overallScore;
        
        // Update health score color class
        healthScoreElement.className = 'health-score';
        if (overallScore >= 80) {
            healthScoreElement.classList.add('excellent');
        } else if (overallScore >= 60) {
            healthScoreElement.classList.add('good');
        } else if (overallScore >= 40) {
            healthScoreElement.classList.add('warning');
        } else {
            healthScoreElement.classList.add('critical');
        }
    }
    
    // Update plant health indicator
    updateHealthIndicator(`plant-health-${unitId}`, plantHealth);
    
    // Update device health indicator
    updateHealthIndicator(`device-health-${unitId}`, deviceHealth);
    
    // Update environmental health indicator
    updateHealthIndicator(`env-health-${unitId}`, envHealth);
}

function updateHealthIndicator(elementId, value) {
    const indicator = document.getElementById(elementId);
    if (!indicator) return;
    
    const valueElement = indicator.querySelector('.indicator-value');
    if (valueElement) {
        valueElement.textContent = value;
    }
    
    // Update indicator color class
    indicator.className = 'health-indicator';
    if (value >= 80) {
        indicator.classList.add('healthy');
    } else if (value >= 60) {
        // Good - no additional class (default gray)
    } else if (value >= 40) {
        indicator.classList.add('warning');
    } else {
        indicator.classList.add('critical');
    }
}

// =====================================
// EVENT LISTENERS SETUP
// =====================================

function setupEventListeners() {
    // Form submissions
    document.addEventListener('submit', function(e) {
        if (e.target.id === 'createUnitForm') {
            createUnit(e);
        } else if (e.target.id === 'thresholdsForm') {
            updateThresholds(e);
        } else if (e.target.id === 'addPlantForm') {
            addPlant(e);
        } else if (e.target.id === 'updatePlantStageForm') {
            updatePlantStageFromModal(e);
        } else if (e.target.id === 'linkDeviceForm') {
            linkDevice(e);
        } else if (e.target.id === 'deviceScheduleForm') {
            saveDeviceSchedule(e);
        }
    });

    // Form field changes
    document.addEventListener('change', function(e) {
        if (e.target && e.target.id === 'linkDeviceKind') {
            setLinkDeviceKind(e.target.value);
        }
    });

    // Click delegation
    document.body.addEventListener('click', function(e) {
        const target = e.target.closest('[data-action]');
        if (!target) return;

        const action = target.dataset.action;
        const unitId = target.dataset.unitId;
        const plantId = target.dataset.plantId;
        const modalId = target.dataset.modalId;
        const rowIndex = target.dataset.rowIndex;
        const tab = target.dataset.tab;
        const deviceType = target.dataset.deviceType;
        const deviceId = target.dataset.deviceId;

        switch (action) {
            case 'open-create-unit-modal':
                openModal('createUnitModal');
                break;
            case 'refresh-all-units':
                refreshAllUnits();
                break;
            case 'open-unit-settings':
                manageUnit(unitId);
                break;
            case 'delete-unit':
                deleteUnit(unitId);
                break;
            case 'manage-unit':
                manageUnit(unitId);
                break;
            case 'toggle-camera':
                toggleCamera(unitId);
                break;
            case 'show-schedule':
                showSchedule(unitId);
                break;
            case 'toggle-unit-details':
                toggleUnitDetails(unitId);
                break;
            case 'close-modal':
                closeModal(modalId);
                break;
            case 'remove-schedule-row':
                removeScheduleRow(rowIndex);
                break;
            case 'add-schedule-row':
                addScheduleRow();
                break;
            case 'switch-tab':
                switchTab(tab);
                break;
            case 'open-add-plant-form':
                openAddPlantModal();
                break;
            case 'open-link-device-form':
                openLinkDeviceModal();
                break;
            case 'open-schedule-form':
                openScheduleForm();
                break;
            case 'close-schedule-form':
                closeScheduleForm();
                break;
            case 'start-camera':
                if (currentCameraUnitId) startCameraForUnit(currentCameraUnitId);
                break;
            case 'stop-camera':
                if (currentCameraUnitId) stopCameraForUnit(currentCameraUnitId);
                break;
            case 'capture-photo':
                capturePhoto();
                break;
            case 'set-active-plant':
                setActivePlant(unitId, plantId);
                break;
            case 'update-plant-stage':
                openUpdatePlantStageModal(plantId);
                break;
            case 'remove-plant':
                removePlant(plantId);
                break;
            case 'unlink-device':
                unlinkDevice(deviceType, deviceId);
                break;
            case 'edit-schedule':
                try {
                    const schedule = JSON.parse(target.dataset.schedule);
                    editSchedule(deviceType, schedule);
                } catch (err) {
                    console.error('Failed to parse schedule data', err);
                }
                break;
            case 'delete-schedule':
                deleteSchedule(deviceType);
                break;
        }
    });

    // Modal close on outside click
    window.addEventListener('click', function(e) {
        if (e.target.classList.contains('modal')) {
            closeModal(e.target.id);
        }
    });

    // Keyboard shortcuts
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            const openModal = document.querySelector('.modal.visible');
            if (openModal) {
                closeModal(openModal.id);
            }
        }
    });
}
