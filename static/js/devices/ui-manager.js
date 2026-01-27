/**
 * Devices UI Manager
 * ============================================
 * Handles UI rendering and user interactions for Devices page
 */

class DevicesUIManager extends BaseManager {
    constructor(dataService) {
        super('DevicesUIManager');
        if (!dataService) {
            throw new Error('dataService is required for DevicesUIManager');
        }
        this.dataService = dataService;
        this.socketManager = window.socketManager;
        this.currentTab = 'gpio';
        
        // Cache DOM references by friendly_name for O(1) updates
        this.zigbeeDomIndex = new Map();

        this._zigbeeDeviceIndex = new Map();
        
        // Prevent duplicate socket subscriptions
        this.zigbeeSubscribed = false;
        
        // Sensor model options
        this.sensorModelOptions = window.SYSGROW_SENSOR_MODEL_OPTIONS || {
            'environment_sensor': [
                { value: 'MQ2', text: 'Smoke/Gas Sensor (MQ2)' },
                { value: 'MQ135', text: 'Air Quality Sensor (MQ135)' },
                { value: 'BME280', text: 'BME280 Sensor' },
                { value: 'BME680', text: 'BME680 Sensor' },
                { value: 'ENS160AHT21', text: 'Environment Sensor (ENS160+AHT21)' },
                { value: 'DHT22', text: 'DHT22 Sensor' },
                { value: 'TSL2591', text: 'Light Intensity Sensor (TSL2591)' }
            ],
            'plant_sensor': [
                { value: 'Soil-Moisture', text: 'Soil Moisture Sensor' },
                { value: 'Capacitive-Soil', text: 'Capacitive Soil Sensor' }
            ]
        };

        this.adcSensorTypes = new Set(window.SYSGROW_ADC_SENSOR_TYPES || ['plant_sensor', 'soil_moisture', 'ph', 'ec']);

        // Centralized sensor configuration (icon class instead of HTML string)
        this.SENSOR_CONFIG = {
            temperature:      { iconClass: 'fas fa-temperature-half', unit: '°C',  label: 'Temperature' },
            humidity:         { iconClass: 'fas fa-droplet text-info', unit: '%',  label: 'Humidity' },
            pressure:         { iconClass: 'fas fa-gauge', unit: 'hPa', label: 'Pressure' },
            soil_moisture:    { iconClass: 'fas fa-tint', unit: '%',   label: 'Soil Moisture' },
            illuminance:      { iconClass: 'fas fa-lightbulb', unit: 'lx', label: 'Illuminance' },
            illuminance_lux:  { iconClass: 'fas fa-lightbulb', unit: 'lx', label: 'Illuminance' },
            battery:          { iconClass: 'fas fa-battery-full', unit: '%', label: 'Battery' },
            linkquality:      { iconClass: 'fas fa-signal', unit: '', label: 'Link Quality' }
        };

        // Legacy sensorConfig for backward compatibility (remove after migration)
        this.sensorConfig = this.SENSOR_CONFIG;

        // Centralized calibration configuration
        this.CALIBRATION_CONFIG = {
            temperature:   { min: -2,  max: 2,   step: 0.1, unit: '°C' },
            humidity:      { min: -30, max: 30,  step: 1,   unit: '%'  },
            soil_moisture: { min: -10, max: 10,  step: 0.5, unit: '%'  },
            illuminance:   { min: -100,max: 100, step: 10,  unit: 'lx' }
        };
        
        // Legacy calibrationConfig for backward compatibility
        this.calibrationConfig = this.CALIBRATION_CONFIG;

        this.PRIMARY_METRICS = [
            'temperature', 'humidity', 'soil_moisture', 'co2', 'air_quality',
            'ec', 'ph', 'smoke', 'voc', 'pressure', 'lux', 'full_spectrum',
            'infrared', 'visible'
        ];

        this.PRIMARY_DEFAULTS = {
            environment_sensor: ['temperature', 'humidity', 'co2', 'lux', 'voc', 'smoke', 'pressure', 'air_quality'],
            plant_sensor: ['soil_moisture', 'ph', 'ec']
        };

        this._lastPrimaryMetricsAvailable = null;
        this._lastPrimaryMetricsSensorType = null;
    }

    async init() {
        this.setupTabs();
        this.setupForms();
        this.bindEvents();
        await this.loadInitialData();
        this.setupPolling();
    }

    // ============================================================================
    // INITIALIZATION
    // ============================================================================

    setupTabs() {
        const tabs = document.querySelectorAll('[data-tab]');
        tabs.forEach(tab => {
            this.addEventListener(tab, 'click', (e) => {
                e.preventDefault();
                const tabName = tab.dataset.tab;
                this.switchTab(tabName);
            });
        });
    }

    switchTab(tabName, isUserInitiated = true) {
        this.currentTab = tabName;

        const tabs = document.querySelectorAll('[data-tab]');
        const panels = document.querySelectorAll('.tab-panel');

        tabs.forEach(tab => {
            tab.classList.toggle('active', tab.dataset.tab === tabName);
            tab.setAttribute('aria-selected', tab.dataset.tab === tabName ? 'true' : 'false');
        });

        panels.forEach(panel => {
            const isActive = panel.id === `${tabName}-panel`;
            panel.classList.toggle('active', isActive);
            // Also set inline style to ensure visibility
            panel.style.display = isActive ? 'block' : 'none';
        });

        this.log(`Switched to ${tabName} tab`);

        // Only load bridge status when switching to Zigbee tab (don't auto-discover)
        if (tabName === 'zigbee' && isUserInitiated) {
            this.loadBridgeStatus();
        }
    }

    setupForms() {
        // Conditional field setup
        this.setupConditionalFields();
        
        // Sensor model update (only if element exists)
        const sensorTypeSelect = document.getElementById('sensor_type');
        if (sensorTypeSelect) {
            this.updateSensorModelOptions();
        }
    }

    bindEvents() {
        // Form submissions
        const addSensorForm = document.getElementById('add-sensor-form');
        if (addSensorForm) {
            this.addEventListener(addSensorForm, 'submit', (e) => this.handleAddSensor(e));
        }

        const addActuatorForm = document.getElementById('add-actuator-form');
        if (addActuatorForm) {
            this.addEventListener(addActuatorForm, 'submit', (e) => this.handleAddActuator(e));
        }

        const cameraForm = document.getElementById('camera-form');
        if (cameraForm) {
            this.addEventListener(cameraForm, 'submit', (e) => this.handleCameraSettings(e));
            
            // Camera type change handler
            const cameraTypeSelect = cameraForm.querySelector('[name="camera_type"]');
            if (cameraTypeSelect) {
                this.addEventListener(cameraTypeSelect, 'change', (e) => this.handleCameraTypeChange(e));
            }

            // Load per-unit camera settings when unit changes
            const unitSelect = cameraForm.querySelector('[name="unit_id"]');
            if (unitSelect) {
                this.addEventListener(unitSelect, 'change', () => this.loadCameraSettings());
            }
        }

        // Sensor type changes
        const sensorTypeSelect = document.getElementById('sensor_type');
        if (sensorTypeSelect) {
            this.addEventListener(sensorTypeSelect, 'change', () => this.updateSensorModelOptions());
        }

        // Event delegation for device actions
        this.addDelegatedListener(document, 'click', '[data-action]', (e) => this.handleDeviceAction(e));

        // ESP32 handlers
        this.setupESP32Handlers();
        
        // MQTT handlers
        this.setupMQTTHandlers();
        
        // Zigbee discovery
        const zigbeeDiscoverBtn = document.getElementById('zigbee-discover') || document.getElementById('discover-zigbee-btn');
        if (zigbeeDiscoverBtn) {
            this.addEventListener(zigbeeDiscoverBtn, 'click', () => this.discoverZigbeeDevices());
        }

        // Zigbee permit join
        const zigbeeJoinBtn = document.getElementById('zigbee-permit-join');
        if (zigbeeJoinBtn) {
            this.addEventListener(zigbeeJoinBtn, 'click', () => this.togglePermitJoin());
        }

        // Add Zigbee2MQTT device (sensor/actuator)
        const addDeviceForm = document.getElementById('add-device-form');
        if (addDeviceForm) {
            this.addEventListener(addDeviceForm, 'submit', (e) => this.handleAddZigbeeDevice(e));
        }

        const zigbeeUnitSelect = document.querySelector('#add-device-form [name="unit_id"]');
        const zigbeeSensorType = document.getElementById('device-type-add');
        if (zigbeeSensorType) {
            this.addEventListener(zigbeeSensorType, 'change', () => {
                const unitId = parseInt(zigbeeUnitSelect ? zigbeeUnitSelect.value : '', 10);
                this.renderPrimaryMetricsOptions({
                    sensorType: zigbeeSensorType.value,
                    availableMetrics: this._lastPrimaryMetricsAvailable || null,
                    unitId: Number.isNaN(unitId) ? null : unitId,
                });
            });
        }
        if (zigbeeUnitSelect) {
            this.addEventListener(zigbeeUnitSelect, 'change', () => {
                const unitId = parseInt(zigbeeUnitSelect.value, 10);
                this.renderPrimaryMetricsOptions({
                    sensorType: zigbeeSensorType ? zigbeeSensorType.value : null,
                    availableMetrics: this._lastPrimaryMetricsAvailable || null,
                    unitId: Number.isNaN(unitId) ? null : unitId,
                });
            });
        }

        if (addDeviceForm && zigbeeSensorType) {
            const unitId = parseInt(zigbeeUnitSelect ? zigbeeUnitSelect.value : '', 10);
            this.renderPrimaryMetricsOptions({
                sensorType: zigbeeSensorType.value,
                availableMetrics: this._lastPrimaryMetricsAvailable || null,
                unitId: Number.isNaN(unitId) ? null : unitId,
            });
        }

        const conflictApplyBtn = document.getElementById('primary-metrics-conflict-apply');
        if (conflictApplyBtn) {
            this.addEventListener(conflictApplyBtn, 'click', () => this.handlePrimaryMetricsConflictApply());
        }

        const editApplyBtn = document.getElementById('primary-metrics-edit-apply');
        if (editApplyBtn) {
            this.addEventListener(editApplyBtn, 'click', () => this.handlePrimaryMetricsEditApply());
        }

        const zigbeeEditSaveBtn = document.getElementById('zigbee-sensor-edit-save');
        if (zigbeeEditSaveBtn) {
            this.addEventListener(zigbeeEditSaveBtn, 'click', () => this.handleZigbeeSensorEditSave());
        }
    }

    async loadInitialData() {
        try {
            await this.loadDeviceHealthMetrics();
            await this.loadZigbeeSensors();
            await this.loadCameraSettings();
            await this.subscribeToZigbeeSensorUpdates();
        } catch (error) {
            this.log('Error loading initial data:', error);
            this.showNotification('Failed to load device data', 'error');
        }
    }

    setupPolling() {
        // Refresh device health every 30 seconds
        setInterval(() => this.loadDeviceHealthMetrics(), 30000);
        setInterval(() => this.loadZigbeeSensors(), 30000);
    }

    // ============================================================================
    // CONDITIONAL FIELDS
    // ============================================================================

    setupConditionalFields() {
        // Zigbee device category
        const zigbeeCategory = document.getElementById('zigbee-device-category');
        if (zigbeeCategory) {
            this.addEventListener(zigbeeCategory, 'change', (e) => {
                this.toggleZigbeeDeviceFields(e.target.value);
            });
            this.toggleZigbeeDeviceFields(zigbeeCategory.value);
        }

        // MQTT device type
        const mqttDeviceType = document.getElementById('mqtt-device-type');
        if (mqttDeviceType) {
            this.addEventListener(mqttDeviceType, 'change', (e) => {
                this.toggleMQTTDeviceFields(e.target.value);
            });
            this.toggleMQTTDeviceFields(mqttDeviceType.value);
        }

        // Camera type
        const cameraType = document.getElementById('camera-type');
        if (cameraType) {
            this.addEventListener(cameraType, 'change', (e) => {
                this.toggleCameraFields(e.target.value);
            });
            this.toggleCameraFields(cameraType.value);
        }
    }

    toggleZigbeeDeviceFields(category) {
        const sensorFields = document.getElementById('zigbee-sensor-fields');
        const actuatorFields = document.getElementById('zigbee-actuator-fields');

        if (sensorFields) sensorFields.classList.toggle('hidden', category !== 'sensor');
        if (actuatorFields) actuatorFields.classList.toggle('hidden', category !== 'actuator');
    }

    toggleMQTTDeviceFields(deviceType) {
        const sensorFields = document.getElementById('mqtt-sensor-fields');
        const actuatorFields = document.getElementById('mqtt-actuator-fields');

        if (sensorFields) sensorFields.classList.toggle('hidden', deviceType !== 'sensor');
        if (actuatorFields) actuatorFields.classList.toggle('hidden', deviceType !== 'actuator');
    }

    toggleCameraFields(cameraType) {
        const form = document.getElementById('camera-form');
        if (!form) return;

        const allConditionalFields = form.querySelectorAll('.conditional-field');
        allConditionalFields.forEach(field => { field.style.display = 'none'; });

        if (cameraType) {
            const fieldsToShow = form.querySelectorAll(`.conditional-field[data-camera*="${cameraType}"]`);
            fieldsToShow.forEach(field => { field.style.display = 'block'; });
        }
    }

    updateSensorModelOptions() {
        const sensorTypeSelect = document.getElementById('sensor_type');
        if (!sensorTypeSelect) return;

        const sensorType = sensorTypeSelect.value;
        const sensorModelSelect = document.getElementById('sensor_model');
        if (!sensorModelSelect) return;

        sensorModelSelect.innerHTML = '';

        const options = this.sensorModelOptions[sensorType] || [];
        if (options.length > 0) {
            options.forEach(option => {
                const opt = document.createElement('option');
                opt.value = option.value;
                opt.textContent = option.text;
                sensorModelSelect.appendChild(opt);
            });
        }

        this.toggleAdcChannelVisibility();
    }

    toggleAdcChannelVisibility() {
        const sensorTypeSelect = document.getElementById('sensor_type');
        if (!sensorTypeSelect) return;

        const sensorType = sensorTypeSelect.value;
        const adcChannelDiv = document.getElementById('adc_channel_div');
        const gpioPinDiv = document.getElementById('gpio_pin_div');

        if (!adcChannelDiv || !gpioPinDiv) return;

        if (this.adcSensorTypes.has(sensorType)) {
            adcChannelDiv.style.display = 'block';
            gpioPinDiv.style.display = 'none';
        } else {
            adcChannelDiv.style.display = 'none';
            gpioPinDiv.style.display = 'block';
        }
    }

    // ============================================================================
    // DEVICE ACTIONS
    // ============================================================================

    handleDeviceAction(e) {
        const target = e.target.closest('[data-action]');
        if (!target) return;

        const action = target.dataset.action;

        switch (action) {
            case 'control-actuator':
                this.controlActuator(target.dataset.actuatorType, target.dataset.command);
                break;
            case 'remove-actuator':
                this.removeActuator(target.dataset.actuatorId);
                break;
            case 'remove-sensor':
                this.removeSensor(target.dataset.sensorId);
                break;
            case 'edit-primary-metrics':
                this.openPrimaryMetricsEditor(target.dataset.sensorId);
                break;
            case 'edit-zigbee-sensor':
                this.openZigbeeSensorEditor(target.dataset.sensorId, target.dataset.friendlyName);
                break;
        }
    }

    // ============================================================================
    // SENSOR MANAGEMENT
    // ============================================================================

    async handleAddSensor(event) {
        event.preventDefault();
        const form = event.target;
        const formData = new FormData(form);

        try {
            const type = formData.get('sensor_type');
            const isAdc = this.adcSensorTypes.has(String(type || ''));
            const unitId = formData.get('sensor_unit');

            const sensorData = {
                // Matches CreateSensorRequest
                name: formData.get('sensor_name'),
                type: type,
                model: formData.get('sensor_model'),
                unit_id: unitId ? parseInt(unitId, 10) : null,
                protocol: isAdc ? 'ADC' : 'GPIO',
                gpio_pin: isAdc
                    ? (formData.get('adc_channel') ? parseInt(formData.get('adc_channel'), 10) : null)
                    : (formData.get('sensor_pin') ? parseInt(formData.get('sensor_pin'), 10) : null)
            };

            await this.dataService.addSensor(sensorData);
            this.showNotification('Sensor added successfully', 'success');
            form.reset();
            this.updateSensorModelOptions();
        } catch (error) {
            this.log('Failed to add sensor:', error);
            this.showNotification('Failed to add sensor: ' + (error.message || 'Unknown error'), 'error');
        }
    }

    async removeSensor(sensorId) {
        if (!confirm('Are you sure you want to remove this sensor?')) return;

        try {
            await this.dataService.removeSensor(sensorId);
            this.showNotification('Sensor removed successfully', 'success');
        } catch (error) {
            this.log('Failed to remove sensor:', error);
            this.showNotification('Failed to remove sensor', 'error');
        }
    }

    // ============================================================================
    // ACTUATOR MANAGEMENT
    // ============================================================================

    async handleAddActuator(event) {
        event.preventDefault();
        const form = event.target;
        const formData = new FormData(form);

        try {
            const actuatorData = {
                name: formData.get('name'),
                actuator_type: formData.get('actuator_type'),
                gpio_pin: formData.get('gpio_pin')
            };

            await this.dataService.addActuator(actuatorData);
            this.showNotification('Actuator added successfully', 'success');
            form.reset();
        } catch (error) {
            this.log('Failed to add actuator:', error);
            this.showNotification('Failed to add actuator: ' + (error.message || 'Unknown error'), 'error');
        }
    }

    async removeActuator(actuatorId) {
        if (!confirm('Are you sure you want to remove this actuator?')) return;

        try {
            await this.dataService.removeActuator(actuatorId);
            this.showNotification('Actuator removed successfully', 'success');
        } catch (error) {
            this.log('Failed to remove actuator:', error);
            this.showNotification('Failed to remove actuator', 'error');
        }
    }

    async controlActuator(actuatorType, action) {
        try {
            await this.dataService.controlActuator(actuatorType, action);
            this.showNotification(`Actuator ${action} command sent`, 'success');
        } catch (error) {
            this.log('Failed to control actuator:', error);
            this.showNotification('Failed to control actuator', 'error');
        }
    }

    // ============================================================================
    // DEVICE HEALTH
    // ============================================================================

    async loadDeviceHealthMetrics() {
        try {
            const healthData = await this.dataService.loadDeviceHealthMetrics();
            this.updateOverviewStats(healthData);
        } catch (error) {
            this.log('Failed to load device health metrics:', error);
        }
    }

    updateOverviewStats(healthData) {
        const totalEl = document.getElementById('total-devices');
        const onlineEl = document.getElementById('online-devices');
        const warningEl = document.getElementById('warning-devices');
        const offlineEl = document.getElementById('offline-devices');
        if (!totalEl || !onlineEl || !warningEl || !offlineEl) return;

        const devices = Array.isArray(healthData?.devices) ? healthData.devices : [];
        const totalDevices = devices.length;
        let online = 0;
        let warning = 0;
        let offline = 0;

        devices.forEach((d) => {
            const status = (d.status || '').toLowerCase();
            if (['healthy', 'online', 'connected'].includes(status)) online += 1;
            else if (['warning', 'degraded'].includes(status)) warning += 1;
            else if (['critical', 'offline', 'error'].includes(status)) offline += 1;
        });

        // If API omits status, keep counts coherent
        offline = Math.max(offline, totalDevices - (online + warning));

        totalEl.textContent = totalDevices;
        onlineEl.textContent = online;
        warningEl.textContent = warning;
        offlineEl.textContent = offline;
    }

    // ============================================================================
    // ZIGBEE DEVICES
    // ============================================================================

    async loadZigbeeSensors() {
        try {
            const payload = await this.dataService.loadZigbeeSensors();
            const devices = Array.isArray(payload)
                ? payload
                : payload?.devices || payload?.data?.devices || [];
            this.renderZigbeeSensors(devices);
            this.renderZigbeeDiscoverList(devices);
        } catch (error) {
            this.log('Failed to load Zigbee sensors:', error);
            const loadingDiv = document.querySelector('.zigbee-loading');
            const emptyDiv = document.querySelector('.zigbee-empty');
            if (loadingDiv) {
                loadingDiv.textContent = 'Failed to load Zigbee sensors. Ensure MQTT is enabled.';
                loadingDiv.classList.remove('hidden');
            }
            if (emptyDiv) emptyDiv.classList.add('hidden');
        }
    }

    renderZigbeeSensors(devices) {
        const container = document.getElementById('zigbee-sensors-container');
        if (!container) return;

        const loadingDiv = container.querySelector('.zigbee-loading');
        const emptyDiv = container.querySelector('.zigbee-empty');
        const listDiv = container.querySelector('.zigbee-list') || container;

        if (loadingDiv) loadingDiv.classList.add('hidden');

        // Clear DOM index for fresh render
        this.zigbeeDomIndex.clear();
        this._zigbeeDeviceIndex.clear();

        // Filter out coordinator - only show actual sensor devices
        const sensorDevices = (devices || []).filter(d => {
            if (!d || !d.friendly_name) return false;
            const deviceType = (d.type || d.device_type || '').toLowerCase();
            if (deviceType === 'coordinator') return false;
            if (d.friendly_name.toLowerCase() === 'coordinator') return false;
            return true;
        });

        if (sensorDevices.length === 0) {
            if (emptyDiv) emptyDiv.classList.remove('hidden');
            if (listDiv) listDiv.classList.add('hidden');
            return;
        }

        if (emptyDiv) emptyDiv.classList.add('hidden');
        if (listDiv) listDiv.classList.remove('hidden');

        // Use DocumentFragment for efficient DOM updates (single reflow)
        listDiv.innerHTML = '';
        const frag = document.createDocumentFragment();
        sensorDevices.forEach(device => {
            if (device?.friendly_name) {
                this._zigbeeDeviceIndex.set(device.friendly_name, device);
            }
            if (device?.ieee_address) {
                this._zigbeeDeviceIndex.set(device.ieee_address, device);
            }
            const card = this.createZigbeeSensorCard(device);
            frag.appendChild(card);
        });
        listDiv.appendChild(frag);
        
        // Subscribe once (guard prevents duplicates)
        if (!this.zigbeeSubscribed) {
            this.subscribeToZigbeeSensorUpdates();
            this.zigbeeSubscribed = true;
        }
    }

    renderZigbeeDiscoverList(devices) {
        const container = document.getElementById('zigbee-discover-list');
        if (!container) return;

        // Filter out coordinator - only show usable devices
        const usable = (devices || []).filter(d => {
            if (!d || !d.friendly_name) return false;
            // Filter out coordinator by type or device_type
            const deviceType = (d.type || d.device_type || '').toLowerCase();
            if (deviceType === 'coordinator') return false;
            // Also filter by friendly_name pattern (some coordinators are named "Coordinator")
            if (d.friendly_name.toLowerCase() === 'coordinator') return false;
            return true;
        });

        if (usable.length === 0) {
            container.innerHTML = '<div class="text-xs opacity-50">No devices discovered yet. Click "Permit Join" to allow new devices.</div>';
            return;
        }

        this._zigbeeDiscoverDevices = usable;
        container.innerHTML = '';

        const select = document.createElement('select');
        select.id = 'zigbee-discover-select';
        select.className = 'select select-bordered w-full';

        const placeholder = document.createElement('option');
        placeholder.value = '';
        placeholder.textContent = 'Select a discovered device...';
        select.appendChild(placeholder);

        usable.forEach(device => {
            const option = document.createElement('option');
            option.value = device.friendly_name;
            option.textContent = `${device.friendly_name} (${device.model_id || 'Unknown'})`;
            select.appendChild(option);
        });

        container.appendChild(select);

        this.addEventListener(select, 'change', () => {
            const friendlyName = select.value;
            const device = (this._zigbeeDiscoverDevices || []).find(d => d.friendly_name === friendlyName);
            if (device) this.prefillZigbeeAddForm(device);
        });
    }

    prefillZigbeeAddForm(device) {
        const deviceName = document.getElementById('device-name-add');
        if (deviceName) deviceName.value = device.friendly_name || deviceName.value;

        const zigbeeAddress = document.getElementById('zigbee-address-add');
        if (zigbeeAddress) zigbeeAddress.value = device.ieee_address || zigbeeAddress.value;

        const mqttTopic = document.getElementById('mqtt-topic-add');
        if (mqttTopic && device.friendly_name) mqttTopic.value = `zigbee2mqtt/${device.friendly_name}`;

        const model = document.getElementById('device-model-add');
        if (model && device.model_id) model.value = device.model_id;

        const category = document.getElementById('zigbee-device-category');
        if (category && category.value !== 'sensor') {
            category.value = 'sensor';
            this.toggleZigbeeDeviceFields('sensor');
        }

        const typeSelect = document.getElementById('device-type-add');
        if (typeSelect && Array.isArray(device.sensor_types)) {
            const types = new Set(device.sensor_types);
            const pick = () => {
                if (types.has('temperature') && types.has('humidity')) return 'environment_sensor';
                if (types.has('temperature')) return 'temperature';
                if (types.has('humidity')) return 'humidity';
                if (types.has('soil_moisture')) return 'soil_moisture';
                if (types.has('illuminance') || types.has('lux')) return 'light';
                if (types.has('pressure')) return 'pressure';
                if (types.has('co2')) return 'co2';
                return 'environment_sensor';
            };
            typeSelect.value = pick();
        }

        const available = this._deriveMetricsFromCapabilities(device.sensor_types || []);
        this._lastPrimaryMetricsAvailable = available;
        this._lastPrimaryMetricsSensorType = typeSelect ? typeSelect.value : null;
        const unitSelect = document.querySelector('#add-device-form [name="unit_id"]');
        const unitId = parseInt(unitSelect ? unitSelect.value : '', 10);
        this.renderPrimaryMetricsOptions({
            sensorType: typeSelect ? typeSelect.value : null,
            availableMetrics: available,
            unitId: Number.isNaN(unitId) ? null : unitId,
        });
    }

    async handleAddZigbeeDevice(event) {
        event.preventDefault();
        const form = event.target;
        const formData = new FormData(form);

        const category = formData.get('device_category') || 'sensor';
        if (category !== 'sensor') {
            this.showNotification('Only Zigbee2MQTT sensors are supported right now', 'warning');
            return;
        }

        const name = (formData.get('name') || '').toString().trim();
        const unitId = parseInt((formData.get('unit_id') || '').toString(), 10);
        const sensorType = (formData.get('sensor_type') || '').toString().trim();
        const protocol = (formData.get('protocol') || 'zigbee2mqtt').toString().trim();
        const zigbeeAddress = (formData.get('zigbee_address') || '').toString().trim();
        const mqttTopic = (formData.get('mqtt_topic') || '').toString().trim();
        const primaryMetrics = (formData.getAll('primary_metrics') || [])
            .map(value => value.toString().trim().toLowerCase())
            .filter(value => value);

        if (!name) {
            this.showNotification('Device name is required', 'error');
            return;
        }
        if (!unitId || Number.isNaN(unitId)) {
            this.showNotification('Select a growth unit', 'error');
            return;
        }
        if (!sensorType) {
            this.showNotification('Select a sensor type', 'error');
            return;
        }
        if (!zigbeeAddress) {
            this.showNotification('Zigbee address is required', 'error');
            return;
        }
        if (!mqttTopic || !mqttTopic.startsWith('zigbee2mqtt/') || mqttTopic.split('/').length < 2) {
            this.showNotification('MQTT topic must be like zigbee2mqtt/<friendly_name>', 'error');
            return;
        }

        try {
            await this.dataService.addSensor({
                name,
                type: sensorType,
                model: 'GENERIC_ZIGBEE',
                protocol,
                unit_id: unitId,
                mqtt_topic: mqttTopic,
                zigbee_address: zigbeeAddress,
                primary_metrics: primaryMetrics.length ? primaryMetrics : null,
            });
            this.showNotification('Zigbee2MQTT sensor added successfully', 'success');
            setTimeout(() => window.location.reload(), 500);
        } catch (error) {
            this.log('Failed to add Zigbee2MQTT sensor:', error);
            if (error?.status === 409 && error?.details?.conflicts) {
                this.showPrimaryMetricsConflictDialog(error.details.conflicts, {
                    name,
                    type: sensorType,
                    model: 'GENERIC_ZIGBEE',
                    protocol,
                    unit_id: unitId,
                    mqtt_topic: mqttTopic,
                    zigbee_address: zigbeeAddress,
                    primary_metrics: primaryMetrics,
                });
                return;
            }
            this.showNotification('Failed to add device: ' + (error.message || 'Unknown error'), 'error');
        }
    }

    _deriveMetricsFromCapabilities(capabilities) {
        const normalized = new Set();
        (capabilities || []).forEach(item => {
            const value = (item || '').toString().trim().toLowerCase();
            if (!value) return;
            if (value === 'illuminance' || value === 'illuminance_lux' || value === 'light_level' || value === 'light') {
                normalized.add('lux');
                return;
            }
            if (this.PRIMARY_METRICS.includes(value)) {
                normalized.add(value);
            }
        });
        return Array.from(normalized);
    }

    _getClaimedMetricsForUnit(unitId) {
        const claims = new Map();
        const sensors = this.dataService.getDBSensors() || [];
        sensors.forEach(sensor => {
            if (parseInt(sensor.unit_id, 10) !== unitId) return;
            const metrics = sensor.primary_metrics || sensor.config?.primary_metrics || [];
            metrics.forEach(metric => {
                const key = (metric || '').toString().trim().toLowerCase();
                if (!key || claims.has(key)) return;
                claims.set(key, {
                    sensor_id: sensor.sensor_id || sensor.id,
                    name: sensor.name,
                    type: sensor.sensor_type || sensor.type,
                });
            });
        });
        return claims;
    }

    _findDbSensorForZigbee(device) {
        const sensors = this.dataService.getDBSensors() || [];
        const friendlyName = device?.friendly_name;
        const ieee = device?.ieee_address;

        return sensors.find(sensor => {
            const config = sensor.config || {};
            const configFriendly = config.friendly_name;
            const mqttTopic = config.mqtt_topic || '';
            const mqttFriendly = mqttTopic.startsWith('zigbee2mqtt/') ? mqttTopic.split('/', 2)[1] : null;
            const configIeee = config.zigbee_address || config.zigbee_ieee;

            if (friendlyName && (configFriendly === friendlyName || sensor.name === friendlyName || mqttFriendly === friendlyName)) {
                return true;
            }
            if (ieee && configIeee && String(configIeee).toLowerCase() === String(ieee).toLowerCase()) {
                return true;
            }
            return false;
        });
    }

    _metricLabel(metric) {
        const config = this.SENSOR_CONFIG[metric];
        if (config && config.label) return config.label;
        return metric.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
    }

    renderPrimaryMetricsChips(container, metrics) {
        if (!container) return;
        container.innerHTML = '';
        const values = Array.isArray(metrics) ? metrics : [];
        if (!values.length) {
            const empty = document.createElement('span');
            empty.className = 'text-xs opacity-60';
            empty.textContent = 'None selected';
            container.appendChild(empty);
            return;
        }

        values.forEach(metric => {
            const value = (metric || '').toString().trim().toLowerCase();
            if (!value) return;
            const chip = document.createElement('span');
            chip.className = 'metric-chip';
            chip.textContent = this._metricLabel(value);
            container.appendChild(chip);
        });
    }

    renderPrimaryMetricsOptions({ sensorType, availableMetrics, unitId }) {
        const container = document.getElementById('primary-metrics-options');
        if (!container) return;

        const activeUnitId = unitId || this.dataService.getSelectedUnitId();
        const claimed = this._getClaimedMetricsForUnit(activeUnitId);

        let metrics = availableMetrics && availableMetrics.length ? availableMetrics : null;
        if (!metrics) {
            if (sensorType === 'environment_sensor') {
                metrics = this.PRIMARY_DEFAULTS.environment_sensor;
            } else if (sensorType === 'plant_sensor' || sensorType === 'soil_moisture') {
                metrics = this.PRIMARY_DEFAULTS.plant_sensor;
            } else {
                metrics = this.PRIMARY_METRICS;
            }
        }

        const defaults = new Set();
        if (sensorType === 'environment_sensor') {
            this.PRIMARY_DEFAULTS.environment_sensor.forEach(m => defaults.add(m));
        } else if (sensorType === 'plant_sensor' || sensorType === 'soil_moisture') {
            this.PRIMARY_DEFAULTS.plant_sensor.forEach(m => defaults.add(m));
        }

        container.innerHTML = '';
        metrics.forEach(metric => {
            const value = metric.toLowerCase();
            if (!this.PRIMARY_METRICS.includes(value)) return;

            const claim = claimed.get(value);
            const option = document.createElement('label');
            option.className = 'primary-metric-option';

            const input = document.createElement('input');
            input.type = 'checkbox';
            input.name = 'primary_metrics';
            input.value = value;
            input.disabled = Boolean(claim);
            input.checked = !claim && defaults.has(value);

            const text = document.createElement('span');
            text.textContent = this._metricLabel(value);

            option.appendChild(input);
            option.appendChild(text);

            if (claim) {
                const hint = document.createElement('small');
                hint.textContent = `Claimed by ${claim.name || 'sensor'} (${claim.type || 'unknown'})`;
                option.appendChild(hint);
            }

            container.appendChild(option);
        });
    }

    showPrimaryMetricsConflictDialog(conflicts, payload, mode = 'add') {
        const list = document.getElementById('primary-metrics-conflict-list');
        if (!list) return;

        this._pendingPrimaryMetricsPayload = payload;
        this._pendingPrimaryMetricsAction = mode;
        list.innerHTML = '';

        (conflicts || []).forEach(conflict => {
            const group = document.createElement('div');
            group.className = 'conflict-group';

            const title = document.createElement('h4');
            title.textContent = this._metricLabel(conflict.metric);
            group.appendChild(title);

            (conflict.sensors || []).forEach(sensor => {
                const row = document.createElement('label');
                row.className = 'conflict-sensor-row';

                const input = document.createElement('input');
                input.type = 'checkbox';
                input.dataset.sensorId = sensor.sensor_id;
                input.dataset.metric = conflict.metric;

                const text = document.createElement('span');
                text.textContent = `${sensor.name || 'Sensor'} (${sensor.type || 'unknown'})`;

                row.appendChild(input);
                row.appendChild(text);
                group.appendChild(row);
            });

            list.appendChild(group);
        });

        if (window.Modal) {
            window.Modal.open('primary-metrics-conflict-modal');
        }
    }

    async handlePrimaryMetricsConflictApply() {
        const payload = this._pendingPrimaryMetricsPayload;
        if (!payload) return;

        const list = document.getElementById('primary-metrics-conflict-list');
        const inputs = list ? Array.from(list.querySelectorAll('input[type="checkbox"]')) : [];
        const selected = {};

        inputs.forEach(input => {
            if (!input.checked) return;
            const sensorId = parseInt(input.dataset.sensorId || '0', 10);
            const metric = (input.dataset.metric || '').toString().trim().toLowerCase();
            if (!sensorId || !metric) return;
            if (!selected[sensorId]) selected[sensorId] = new Set();
            selected[sensorId].add(metric);
        });

        const unassign = Object.entries(selected).map(([sensorId, metrics]) => ({
            sensor_id: parseInt(sensorId, 10),
            metrics: Array.from(metrics),
        }));

        if (!unassign.length) {
            this.showNotification('Select at least one sensor to unassign', 'warning');
            return;
        }

        try {
            await this.dataService.resolvePrimaryMetrics({
                unit_id: payload.unit_id,
                unassign,
            });

            if (window.Modal) {
                window.Modal.close('primary-metrics-conflict-modal');
            }

            if (this._pendingPrimaryMetricsAction === 'update') {
                await this.dataService.updateSensorPrimaryMetrics(payload.sensor_id, {
                    primary_metrics: payload.primary_metrics,
                });
                this.showNotification('Primary metrics updated successfully', 'success');
                setTimeout(() => window.location.reload(), 500);
            } else {
                await this.dataService.addSensor(payload);
                this.showNotification('Zigbee2MQTT sensor added successfully', 'success');
                setTimeout(() => window.location.reload(), 500);
            }
        } catch (error) {
            this.log('Failed to resolve primary metrics conflicts:', error);
            this.showNotification('Failed to resolve conflicts: ' + (error.message || 'Unknown error'), 'error');
        }
    }

    openPrimaryMetricsEditor(sensorId) {
        const sensors = this.dataService.getDBSensors() || [];
        const sensor = sensors.find(item => String(item.sensor_id || item.id) === String(sensorId));
        if (!sensor) {
            this.showNotification('Sensor not found', 'error');
            return;
        }
        this.showPrimaryMetricsEditDialog(sensor);
    }

    showPrimaryMetricsEditDialog(sensor) {
        this._primaryMetricsEditSensor = sensor;
        this.renderPrimaryMetricsEditOptions(sensor);
        if (window.Modal) {
            window.Modal.open('primary-metrics-edit-modal');
        }
    }

    renderPrimaryMetricsEditOptions(sensor, containerId = 'primary-metrics-edit-options') {
        const container = document.getElementById(containerId);
        if (!container) return;

        const unitId = parseInt(sensor.unit_id, 10) || this.dataService.getSelectedUnitId();
        const claimed = this._getClaimedMetricsForUnit(unitId);
        const current = new Set((sensor.primary_metrics || sensor.config?.primary_metrics || [])
            .map(metric => (metric || '').toString().trim().toLowerCase())
            .filter(Boolean));

        container.innerHTML = '';

        this.PRIMARY_METRICS.forEach(metric => {
            const claim = claimed.get(metric);
            const isClaimedByOther = claim && String(claim.sensor_id) !== String(sensor.sensor_id || sensor.id);

            const option = document.createElement('label');
            option.className = 'primary-metric-option';

            const input = document.createElement('input');
            input.type = 'checkbox';
            input.value = metric;
            input.checked = current.has(metric);
            input.disabled = isClaimedByOther;

            const text = document.createElement('span');
            text.textContent = this._metricLabel(metric);

            option.appendChild(input);
            option.appendChild(text);

            if (isClaimedByOther) {
                const hint = document.createElement('small');
                hint.textContent = `Claimed by ${claim.name || 'sensor'} (${claim.type || 'unknown'})`;
                option.appendChild(hint);
            }

            container.appendChild(option);
        });
    }

    async handlePrimaryMetricsEditApply() {
        const sensor = this._primaryMetricsEditSensor;
        if (!sensor) return;

        const container = document.getElementById('primary-metrics-edit-options');
        const inputs = container ? Array.from(container.querySelectorAll('input[type="checkbox"]')) : [];
        const primaryMetrics = inputs.filter(input => input.checked).map(input => input.value);

        try {
            await this.dataService.updateSensorPrimaryMetrics(sensor.sensor_id || sensor.id, {
                primary_metrics: primaryMetrics,
            });

            if (window.Modal) {
                window.Modal.close('primary-metrics-edit-modal');
            }

            this.showNotification('Primary metrics updated successfully', 'success');
            setTimeout(() => window.location.reload(), 500);
        } catch (error) {
            if (error?.status === 409 && error?.details?.conflicts) {
                const unitId = sensor.unit_id ? parseInt(sensor.unit_id, 10) : this.dataService.getSelectedUnitId();
                this.showPrimaryMetricsConflictDialog(error.details.conflicts, {
                    sensor_id: sensor.sensor_id || sensor.id,
                    unit_id: Number.isNaN(unitId) ? this.dataService.getSelectedUnitId() : unitId,
                    primary_metrics: primaryMetrics,
                }, 'update');
                return;
            }
            this.log('Failed to update primary metrics:', error);
            this.showNotification('Failed to update primary metrics: ' + (error.message || 'Unknown error'), 'error');
        }
    }

    openZigbeeSensorEditor(sensorId, friendlyName) {
        const sensors = this.dataService.getDBSensors() || [];
        const sensor = sensors.find(item => String(item.sensor_id || item.id) === String(sensorId))
            || sensors.find(item => (item.config?.friendly_name || item.name) === friendlyName);

        if (!sensor) {
            this.showNotification('Sensor not found', 'error');
            return;
        }

        const device = this._zigbeeDeviceIndex.get(sensor.config?.friendly_name)
            || this._zigbeeDeviceIndex.get(friendlyName)
            || this._zigbeeDeviceIndex.get(sensor.config?.zigbee_address)
            || this._zigbeeDeviceIndex.get(sensor.config?.zigbee_ieee)
            || null;

        this._editingZigbeeSensor = { sensor, device };

        const nameInput = document.getElementById('zigbee-sensor-edit-name');
        if (nameInput) {
            nameInput.value = device?.friendly_name || sensor.name || '';
        }

        const modelEl = document.getElementById('zigbee-sensor-edit-model');
        if (modelEl) modelEl.textContent = device?.model_id || sensor.model || '--';

        const manufacturerEl = document.getElementById('zigbee-sensor-edit-manufacturer');
        if (manufacturerEl) manufacturerEl.textContent = device?.manufacturer || '--';

        const ieeeEl = document.getElementById('zigbee-sensor-edit-ieee');
        if (ieeeEl) ieeeEl.textContent = device?.ieee_address || sensor.config?.zigbee_address || '--';

        const topicEl = document.getElementById('zigbee-sensor-edit-topic');
        if (topicEl) topicEl.textContent = sensor.config?.mqtt_topic || '--';

        this.renderPrimaryMetricsEditOptions(sensor, 'zigbee-sensor-edit-primary-metrics');

        if (window.Modal) {
            window.Modal.open('zigbee-sensor-edit-modal');
        }
    }

    async handleZigbeeSensorEditSave() {
        const state = this._editingZigbeeSensor;
        if (!state) return;

        const sensor = state.sensor;
        const device = state.device;
        const nameInput = document.getElementById('zigbee-sensor-edit-name');
        const newName = (nameInput?.value || '').toString().trim();

        if (!newName) {
            this.showNotification('Friendly name is required', 'error');
            return;
        }

        const metricsContainer = document.getElementById('zigbee-sensor-edit-primary-metrics');
        const inputs = metricsContainer ? Array.from(metricsContainer.querySelectorAll('input[type="checkbox"]')) : [];
        const primaryMetrics = inputs.filter(input => input.checked).map(input => input.value);

        try {
            if (device?.ieee_address && newName !== device.friendly_name) {
                await this.dataService.renameZigbeeDevice(device.ieee_address, newName);
            }

            await this.dataService.updateSensor(sensor.sensor_id || sensor.id, {
                name: newName,
                friendly_name: newName,
                mqtt_topic: `zigbee2mqtt/${newName}`,
            });

            await this.dataService.updateSensorPrimaryMetrics(sensor.sensor_id || sensor.id, {
                primary_metrics: primaryMetrics,
            });

            if (window.Modal) {
                window.Modal.close('zigbee-sensor-edit-modal');
            }

            this.showNotification('Sensor updated successfully', 'success');
            setTimeout(() => window.location.reload(), 500);
        } catch (error) {
            if (error?.status === 409 && error?.details?.conflicts) {
                const unitId = sensor.unit_id ? parseInt(sensor.unit_id, 10) : this.dataService.getSelectedUnitId();
                this.showPrimaryMetricsConflictDialog(error.details.conflicts, {
                    sensor_id: sensor.sensor_id || sensor.id,
                    unit_id: Number.isNaN(unitId) ? this.dataService.getSelectedUnitId() : unitId,
                    primary_metrics: primaryMetrics,
                }, 'update');
                return;
            }
            this.log('Failed to update zigbee sensor:', error);
            this.showNotification('Failed to update sensor: ' + (error.message || 'Unknown error'), 'error');
        }
    }

    createZigbeeSensorCard(device) {
        const template = document.getElementById('zigbee-sensor-card-template');
        if (!template) return document.createElement('div');

        const fragment = template.content.cloneNode(true);
        const root = fragment.querySelector('.virtuoso-list-item');
        if (!root) return document.createElement('div');

        const dbSensor = this._findDbSensorForZigbee(device);

        // Save identifiers on root for debugging / fallback selectors
        root.dataset.ieeeAddress = device.ieee_address || '';
        root.dataset.friendlyName = device.friendly_name || '';
        if (dbSensor) {
            root.dataset.sensorId = dbSensor.sensor_id || dbSensor.id || '';
        }

        // Populate top area
        const deviceImage = root.querySelector('.device-image');
        const imageUrl = device?.definition?.image
            ? device.definition.image
            : 'https://www.zigbee2mqtt.io/logo.png';

        if (deviceImage) {
            deviceImage.src = imageUrl;
            deviceImage.alt = device.friendly_name || 'Device';
        }

        const nameEl = root.querySelector('.device-name');
        if (nameEl) nameEl.textContent = dbSensor?.name || device.friendly_name || 'Unknown device';

        const modelEl = root.querySelector('.device-model');
        if (modelEl) modelEl.textContent = device.model_id || 'Unknown Model';

        const manuEl = root.querySelector('.device-manufacturer');
        if (manuEl) manuEl.textContent = device.manufacturer || 'Unknown';

        const lastSeenEl = root.querySelector('.device-last-seen');
        if (lastSeenEl) lastSeenEl.textContent = 'N/A';

        const ieeeEl = root.querySelector('.ieee-value');
        if (ieeeEl) ieeeEl.textContent = device.ieee_address || '--';

        const editBtn = root.querySelector('[data-action="edit-zigbee-sensor"]');
        if (editBtn) {
            editBtn.dataset.sensorId = dbSensor?.sensor_id || dbSensor?.id || '';
            editBtn.dataset.friendlyName = device.friendly_name || '';
            if (!dbSensor) {
                editBtn.disabled = true;
                editBtn.title = 'Register this sensor to enable editing';
            }
        }

        // Readings + Calibration
        this.populateSensorReadings(root, device);
        this.populateCalibrationControls(root, device);

        const chipsContainer = root.querySelector('.primary-metrics-chips');
        if (chipsContainer) {
            const metrics = dbSensor?.primary_metrics || dbSensor?.config?.primary_metrics || [];
            this.renderPrimaryMetricsChips(chipsContainer, metrics);
        }

        // Build index for fast updates (O(1) lookup)
        const valueByType = new Map();
        root.querySelectorAll('[data-sensor-type] .sensor-value').forEach(span => {
            const row = span.closest('[data-sensor-type]');
            if (!row) return;
            valueByType.set(row.dataset.sensorType, span);
        });

        this.zigbeeDomIndex.set(device.friendly_name, {
            root,
            valueByType,
            lqBadge: root.querySelector('.device-linkquality'),
            lqValue: root.querySelector('.linkquality-value'),
            lqIcon: root.querySelector('.device-linkquality i'),
            batteryBadge: root.querySelector('.device-battery'),
            batteryValue: root.querySelector('.battery-value'),
        });

        return root;
    }

    populateSensorReadings(rootEl, device) {
        const readingsContainer = rootEl.querySelector('.sensor-readings');
        if (!readingsContainer) return;

        readingsContainer.innerHTML = '';

        const types = Array.isArray(device.sensor_types) ? device.sensor_types : [];
        if (types.length === 0) {
            const p = document.createElement('p');
            p.className = 'text-xs opacity-50';
            p.textContent = 'No sensor readings available';
            readingsContainer.appendChild(p);
            return;
        }

        for (const sensorType of types) {
            const cfg = this.SENSOR_CONFIG[sensorType] || {
                iconClass: 'fas fa-circle opacity-0',
                unit: '',
                label: sensorType.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())
            };

            const row = document.createElement('div');
            row.className = 'flex flex-row items-center gap-1 mb-2';
            row.dataset.sensorType = sensorType;
            row.dataset.friendlyName = device.friendly_name;

            const icon = document.createElement('i');
            icon.className = cfg.iconClass;

            const label = document.createElement('div');
            label.className = 'grow-1';
            label.textContent = cfg.label;

            const right = document.createElement('div');
            right.className = 'shrink-1';

            const inner = document.createElement('div');

            const value = document.createElement('span');
            value.className = 'font-bold sensor-value';
            value.textContent = '--';

            const unit = document.createElement('span');
            unit.className = 'text-xs ms-1 sensor-unit';
            unit.textContent = cfg.unit || '';

            inner.appendChild(value);
            inner.appendChild(unit);
            right.appendChild(inner);

            row.appendChild(icon);
            row.appendChild(label);
            row.appendChild(right);

            readingsContainer.appendChild(row);
        }
    }

    populateCalibrationControls(rootEl, device) {
        const calibrationContainer = rootEl.querySelector('.calibration-controls');
        if (!calibrationContainer) return;

        calibrationContainer.innerHTML = '';

        const types = Array.isArray(device.sensor_types) ? device.sensor_types : [];
        const supportedTypes = Object.keys(this.CALIBRATION_CONFIG).filter(t => types.includes(t));

        if (supportedTypes.length === 0) {
            const p = document.createElement('p');
            p.className = 'text-xs opacity-50';
            p.textContent = 'No calibration available for this device';
            calibrationContainer.appendChild(p);
            return;
        }

        for (const sensorType of supportedTypes) {
            const cfg = this.CALIBRATION_CONFIG[sensorType];
            const labelText = sensorType.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());

            const wrapper = document.createElement('div');
            wrapper.className = 'mb-2';
            wrapper.dataset.calibrationType = sensorType;

            const label = document.createElement('label');
            label.className = 'text-xs font-semibold';
            label.textContent = `${labelText} Calibration`;

            const row = document.createElement('div');
            row.className = 'flex items-center gap-2';

            const slider = document.createElement('input');
            slider.type = 'range';
            slider.className = 'range range-xs range-primary calibration-slider';
            slider.min = String(cfg.min);
            slider.max = String(cfg.max);
            slider.step = String(cfg.step);
            slider.value = '0';
            slider.dataset.sensorType = sensorType;
            slider.dataset.friendlyName = device.friendly_name;

            const valueSpan = document.createElement('span');
            valueSpan.className = 'text-xs calibration-value';
            valueSpan.textContent = `0${cfg.unit}`;

            // UI update while sliding
            this.addEventListener(slider, 'input', () => {
                valueSpan.textContent = `${slider.value}${cfg.unit}`;
            });

            // Persist on release
            this.addEventListener(slider, 'change', async () => {
                const offset = parseFloat(slider.value);
                await this.setZigbeeCalibration(device.friendly_name, sensorType, offset);
            });

            row.appendChild(slider);
            row.appendChild(valueSpan);

            wrapper.appendChild(label);
            wrapper.appendChild(row);

            calibrationContainer.appendChild(wrapper);
        }

        // Load saved calibration values from backend and apply
        this.loadZigbeeCalibration(device.friendly_name, calibrationContainer);
    }

    async loadZigbeeCalibration(friendlyName, container) {
        try {
            const dbSensors = this.dataService.getDBSensors();
            if (!Array.isArray(dbSensors)) return;

            const sensor = dbSensors.find(s => (s.friendly_name || s.name) === friendlyName);
            if (!sensor) return;

            const data = await this.dataService.loadZigbeeCalibration(sensor.sensor_id);

            if (data) {
                Object.keys(data).forEach(sensorType => {
                    const slider = container.querySelector(`[data-calibration-type="${sensorType}"] .calibration-slider`);
                    if (slider) {
                        slider.value = data[sensorType];
                        const config = this.calibrationConfig[sensorType];
                        const valueSpan = slider.parentElement.querySelector('.calibration-value');
                        if (valueSpan) valueSpan.textContent = data[sensorType] + config.unit;
                    }
                });
            }
        } catch (error) {
            this.log('Failed to load Zigbee calibration:', error);
        }
    }

    async setZigbeeCalibration(friendlyName, sensorType, offset) {
        try {
            await this.dataService.setZigbeeCalibration(friendlyName, sensorType, offset);
            this.showNotification('Calibration updated', 'success');
        } catch (error) {
            this.log('Failed to set calibration:', error);
            this.showNotification('Failed to update calibration', 'error');
        }
    }

    async discoverZigbeeDevices() {
        const btn = document.getElementById('zigbee-discover') || document.getElementById('discover-zigbee-btn');

        try {
            if (btn) btn.disabled = true;

            // First check bridge status
            let bridgeOnline = false;
            try {
                const status = await this.dataService.getBridgeStatus();
                bridgeOnline = status?.online || status?.coordinator_active;
                this.updateBridgeStatusUI(status);
            } catch (e) {
                this.log('Bridge status check failed:', e);
            }

            // Attempt discovery
            const result = await this.dataService.discoverZigbeeDevices();

            if (bridgeOnline) {
                this.showNotification('Zigbee discovery started. Devices will appear shortly.', 'success');
            } else {
                this.showNotification('Discovery attempted but coordinator appears offline. Connect your Zigbee coordinator.', 'warning');
            }

            // Reload sensors and update bridge status after discovery
            setTimeout(async () => {
                await this.loadZigbeeSensors();
                await this.loadBridgeStatus();
            }, 3000);

        } catch (error) {
            this.log('Failed to start Zigbee discovery:', error);
            this.showNotification('Failed to start discovery. Is MQTT enabled?', 'error');
        } finally {
            if (btn) btn.disabled = false;
        }
    }

    async loadBridgeStatus() {
        try {
            const status = await this.dataService.getBridgeStatus();
            this.updateBridgeStatusUI(status);
        } catch (error) {
            this.log('Failed to load bridge status:', error);
            this.updateBridgeStatusUI({ online: false, coordinator_active: false });
        }
    }

    updateBridgeStatusUI(status) {
        const indicator = document.getElementById('zigbee-coordinator-status');
        if (!indicator) return;

        const isOnline = status?.online || status?.coordinator_active;
        const deviceCount = status?.device_count || 0;

        indicator.classList.remove('hidden');
        const icon = indicator.querySelector('.coordinator-icon');
        const text = indicator.querySelector('.coordinator-text');

        if (icon) {
            icon.className = `coordinator-icon fas fa-broadcast-tower ${isOnline ? 'text-success' : 'text-error'}`;
        }
        if (text) {
            text.textContent = isOnline
                ? `Coordinator Online (${deviceCount} devices)`
                : 'Coordinator Offline';
        }
    }

    async togglePermitJoin() {
        const btn = document.getElementById('zigbee-permit-join');
        if (!btn) return;

        try {
            // Check if currently in permit join mode
            const isActive = btn.classList.contains('btn-warning');

            if (isActive) {
                // Disable permit join
                await this.dataService.permitJoin(0);
                btn.classList.remove('btn-warning');
                btn.classList.add('btn-secondary');
                btn.innerHTML = '<i class="fas fa-plus-circle me-2"></i>Permit Join';
                this.showNotification('Permit join disabled', 'info');
                this._permitJoinTimer && clearInterval(this._permitJoinTimer);
            } else {
                // Enable permit join for 254 seconds
                await this.dataService.permitJoin(254);
                btn.classList.remove('btn-secondary');
                btn.classList.add('btn-warning');

                // Start countdown
                let remaining = 254;
                btn.innerHTML = `<i class="fas fa-spinner fa-spin me-2"></i>Joining (${remaining}s)`;

                this._permitJoinTimer = setInterval(() => {
                    remaining--;
                    if (remaining <= 0) {
                        clearInterval(this._permitJoinTimer);
                        btn.classList.remove('btn-warning');
                        btn.classList.add('btn-secondary');
                        btn.innerHTML = '<i class="fas fa-plus-circle me-2"></i>Permit Join';
                        // Refresh device list after permit join ends
                        this.discoverZigbeeDevices();
                    } else {
                        btn.innerHTML = `<i class="fas fa-spinner fa-spin me-2"></i>Joining (${remaining}s)`;
                    }
                }, 1000);

                this.showNotification('Permit join enabled for ~4 minutes. Put your device in pairing mode.', 'success');
            }
        } catch (error) {
            this.log('Failed to toggle permit join:', error);
            this.showNotification('Failed to toggle permit join', 'error');
        }
    }

    subscribeToZigbeeSensorUpdates() {
        if (!this.socketManager) {
            this.log('SocketManager not available for Zigbee updates');
            return;
        }

        // NEW: Device sensor reading from /devices namespace (preferred)
        // Contains full payload: sensor_id, unit_id, readings, units, status, etc.
        this.socketManager.on('device_sensor_reading', (data) => {
            this.handleDeviceSensorReading(data);
        });

        // NEW: Unregistered sensor data from /devices namespace
        // For ESP32 sensors that are broadcasting but not yet configured
        this.socketManager.on('unregistered_sensor_data', (data) => {
            this.handleUnregisteredSensor(data);
        });
    }

    /**
     * Handle new device_sensor_reading events from /devices namespace
     * @param {Object} data - DeviceSensorReadingPayload
     */
    handleDeviceSensorReading(data) {
        if (!data) return;

        const sensorId = data.sensor_id;
        const unitId = data.unit_id;
        const readings = data.readings || {};
        const sensorType = data.sensor_type;
        const sensorName = data.sensor_name;
        const status = data.status || 'success';
        const isAnomaly = data.is_anomaly || false;
        const timestamp = data.timestamp;

        this.log(`Device sensor reading: sensor_id=${sensorId} type=${sensorType} readings=${Object.keys(readings).join(',')}`);

        // Update sensor card UI if it exists
        const card = document.querySelector(`[data-sensor-id="${sensorId}"]`);
        if (card) {
            // Update each reading value in the card
            Object.entries(readings).forEach(([metric, value]) => {
                const valueEl = card.querySelector(`[data-metric="${metric}"]`);
                if (valueEl) {
                    const unit = data.units?.[metric] || this.SENSOR_CONFIG[metric]?.unit || '';
                    valueEl.textContent = `${this.formatValue(value)} ${unit}`;
                }
            });

            // Update status indicator
            const statusEl = card.querySelector('.sensor-status');
            if (statusEl) {
                statusEl.className = `sensor-status status-${status}`;
                if (isAnomaly) {
                    statusEl.classList.add('anomaly');
                }
            }

            // Update timestamp
            const timeEl = card.querySelector('.sensor-timestamp');
            if (timeEl && timestamp) {
                timeEl.textContent = this.formatTimestamp(timestamp);
            }
        }

        // Also update Zigbee display if this is a Zigbee sensor
        if (sensorName) {
            this.updateZigbeeSensorDisplay({
                friendly_name: sensorName,
                ...readings,
                timestamp: timestamp,
            });
        }
    }

    /**
     * Handle unregistered sensor data from /devices namespace
     * @param {Object} data - UnregisteredSensorPayload
     */
    handleUnregisteredSensor(data) {
        if (!data) return;

        const friendlyName = data.friendly_name;
        const unitId = data.unit_id;
        const rawData = data.raw_data || {};
        const suggestedType = data.suggested_sensor_type;

        this.log(`Unregistered sensor detected: ${friendlyName} unit=${unitId}`);

        // Show notification for new unregistered sensor
        this.showNotification(
            `New sensor detected: ${friendlyName}. Configure it in the Devices tab.`,
            'info'
        );

        // Add to unregistered sensors list if it exists
        const unregisteredList = document.getElementById('unregistered-sensors-list');
        if (unregisteredList) {
            // Check if already in list
            const existing = unregisteredList.querySelector(`[data-friendly-name="${friendlyName}"]`);
            if (!existing) {
                const item = document.createElement('div');
                item.className = 'unregistered-sensor-item';
                item.dataset.friendlyName = friendlyName;
                item.innerHTML = `
                    <span class="sensor-name">${this.escapeHtml(friendlyName)}</span>
                    <span class="sensor-unit">Unit ${unitId}</span>
                    <span class="sensor-type">${suggestedType || 'Unknown'}</span>
                    <button class="btn btn-sm btn-primary" data-action="register-sensor" data-friendly-name="${friendlyName}">
                        Register
                    </button>
                `;
                unregisteredList.appendChild(item);
            }
        }
    }

    formatValue(value) {
        if (typeof value === 'number') {
            return Number.isInteger(value) ? value : value.toFixed(1);
        }
        return value;
    }

    formatTimestamp(isoString) {
        try {
            const date = new Date(isoString);
            return date.toLocaleTimeString();
        } catch (e) {
            return isoString;
        }
    }

    updateZigbeeSensorDisplay(data) {
        // Support both raw zigbee payloads and EmitterService SensorReadingPayload
        const friendlyName = data?.friendly_name || data?.device_name || data?.readings?.friendly_name;
        if (!friendlyName) {
            console.warn('⚠️ Invalid sensor data (no friendly_name):', data);
            return;
        }

        // Use cached DOM index for O(1) lookup
        const entry = this.zigbeeDomIndex.get(friendlyName);
        if (!entry) {
            console.warn(`⚠️ No DOM entry for ${friendlyName} (device might not be in current unit)`);
            return;
        }

        console.log(`📊 Updating Zigbee display for ${friendlyName}:`, data);

        // Update last seen (cached reference)
        const lastSeenEl = entry.root.querySelector('.device-last-seen');
        if (lastSeenEl) {
            const now = new Date();
            lastSeenEl.textContent = now.toLocaleTimeString();
        }

        // Update sensor readings using cached Map (O(1) lookup per key)
        const readings = data?.readings && typeof data.readings === 'object' ? data.readings : data;
        for (const [key, raw] of Object.entries(readings || {})) {
            // Skip metadata keys
            if (['friendly_name', 'device_name', 'sensor_id', 'unit_id', 'timestamp', 'units', 'linkquality', 'battery'].includes(key)) continue;
            if (raw === null || raw === undefined) continue;

            let span = entry.valueByType.get(key);

            // If row doesn't exist, create it dynamically
            if (!span) {
                span = this.createSensorReadingRow(entry, key, friendlyName);
                if (!span) continue;
            }

            const value = (typeof raw === 'number' && !Number.isInteger(raw))
                ? raw.toFixed(1)
                : raw;

            span.textContent = value;
            console.log(`   ✓ Updated ${key} = ${value}`);
        }

        // Link quality badge (cached references)
        if (readings.linkquality !== undefined && entry.lqValue && entry.lqIcon) {
            entry.lqValue.textContent = String(readings.linkquality);

            entry.lqIcon.className = 'fas fa-signal';
            if (readings.linkquality > 150) entry.lqIcon.classList.add('text-success');
            else if (readings.linkquality > 80) entry.lqIcon.classList.add('text-warning');
            else entry.lqIcon.classList.add('text-error');
        }

        // Battery badge (cached references)
        if (readings.battery !== undefined && entry.batteryBadge && entry.batteryValue) {
            entry.batteryBadge.classList.remove('hidden');
            entry.batteryValue.textContent = `${readings.battery}%`;
        }
    }

    /**
     * Dynamically creates a sensor reading row when it doesn't exist in the DOM.
     * This handles cases where sensor_types was empty during initial render.
     * @param {Object} entry - The DOM index entry for the device
     * @param {string} sensorType - The sensor type (e.g., 'temperature', 'humidity')
     * @param {string} friendlyName - The device friendly name
     * @returns {HTMLElement|null} The value span element, or null if creation failed
     */
    createSensorReadingRow(entry, sensorType, friendlyName) {
        const readingsContainer = entry.root.querySelector('.sensor-readings');
        if (!readingsContainer) {
            console.warn(`⚠️ No readings container found for ${friendlyName}`);
            return null;
        }

        // Remove "No sensor readings available" placeholder if present
        const placeholder = readingsContainer.querySelector('p.opacity-50');
        if (placeholder && placeholder.textContent.includes('No sensor readings')) {
            placeholder.remove();
        }

        // Get config for this sensor type
        const cfg = this.SENSOR_CONFIG[sensorType] || {
            iconClass: 'fas fa-circle opacity-0',
            unit: '',
            label: sensorType.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())
        };

        // Create the row structure (same as populateSensorReadings)
        const row = document.createElement('div');
        row.className = 'flex flex-row items-center gap-1 mb-2';
        row.dataset.sensorType = sensorType;
        row.dataset.friendlyName = friendlyName;

        const icon = document.createElement('i');
        icon.className = cfg.iconClass;

        const label = document.createElement('div');
        label.className = 'grow-1';
        label.textContent = cfg.label;

        const right = document.createElement('div');
        right.className = 'shrink-1';

        const inner = document.createElement('div');

        const value = document.createElement('span');
        value.className = 'font-bold sensor-value';
        value.textContent = '--';

        const unit = document.createElement('span');
        unit.className = 'text-xs ms-1 sensor-unit';
        unit.textContent = cfg.unit || '';

        inner.appendChild(value);
        inner.appendChild(unit);
        right.appendChild(inner);

        row.appendChild(icon);
        row.appendChild(label);
        row.appendChild(right);

        readingsContainer.appendChild(row);

        // Add to the valueByType cache for future O(1) lookups
        entry.valueByType.set(sensorType, value);

        console.log(`   ➕ Created row for ${sensorType} on ${friendlyName}`);
        return value;
    }

    // ============================================================================
    // ESP32 HANDLERS
    // ============================================================================

    setupESP32Handlers() {
        const scanBtn = document.getElementById('device-scan');
        if (scanBtn) {
            this.addEventListener(scanBtn, 'click', () => this.scanForDevices());
        }

        const esp32Form = document.getElementById('esp32-device-form');
        if (esp32Form) {
            this.addEventListener(esp32Form, 'submit', (e) => this.provisionDevice(e));
        }

        const provisionBtn = document.getElementById('provision-device');
        if (provisionBtn && esp32Form) {
            this.addEventListener(provisionBtn, 'click', () => {
                esp32Form.dispatchEvent(new Event('submit', { cancelable: true, bubbles: true }));
            });
        }

        const sendWiFiBtn = document.getElementById('send-wifi-config');
        if (sendWiFiBtn) {
            this.addEventListener(sendWiFiBtn, 'click', () => this.sendWiFiConfigFromUI());
        }

        const broadcastBtn = document.getElementById('broadcast-wifi');
        if (broadcastBtn) {
            this.addEventListener(broadcastBtn, 'click', () => this.broadcastWiFiConfigFromUI());
        }
    }

    async scanForDevices() {
        try {
            const deviceList = document.getElementById('device-list');
            if (deviceList) {
                deviceList.innerHTML = '<option value="">Scanning...</option>';
            }

            const devices = await this.dataService.scanForDevices();
            
            if (deviceList) {
                if (devices && devices.length > 0) {
                    deviceList.innerHTML = devices.map(device => {
                        const label = device.name || device.mac || device.ip || 'Unknown device';
                        const value = device.id || device.mac || device.ip || label;
                        return `<option value="${value}">${label}</option>`;
                    }).join('');
                } else {
                    deviceList.innerHTML = '<option value="">No devices found</option>';
                }
            }
        } catch (error) {
            this.log('Failed to scan for devices:', error);
            this.showNotification('Failed to scan for devices', 'error');
        }
    }

    async provisionDevice(event) {
        event.preventDefault();
        const form = event.target;
        const formData = new FormData(form);

        try {
            await this.dataService.provisionDevice(Object.fromEntries(formData));
            this.showNotification('Device provisioned successfully', 'success');
            form.reset();
        } catch (error) {
            this.log('Failed to provision device:', error);
            this.showNotification('Failed to provision device', 'error');
        }
    }

    getWiFiConfigFromUI() {
        const ssid = document.getElementById('setup-ssid')?.value?.trim();
        const password = document.getElementById('setup-password')?.value || '';
        const deviceId = document.getElementById('device-list')?.value || null;
        const setupMethod = document.getElementById('wifi-setup-method')?.value || null;
        return { ssid, password, device_id: deviceId || undefined, setup_method: setupMethod || undefined };
    }

    async sendWiFiConfigFromUI() {
        const config = this.getWiFiConfigFromUI();
        if (!config.ssid || !config.password) {
            this.showNotification('Please enter WiFi credentials', 'warning');
            return;
        }

        try {
            await this.dataService.sendWiFiConfig(config);
            this.showNotification('WiFi config sent successfully', 'success');
        } catch (error) {
            this.log('Failed to send WiFi config:', error);
            this.showNotification('Failed to send WiFi config', 'error');
        }
    }

    async broadcastWiFiConfigFromUI() {
        const config = this.getWiFiConfigFromUI();
        if (!config.ssid || !config.password) {
            this.showNotification('Please enter WiFi credentials', 'warning');
            return;
        }

        try {
            await this.dataService.broadcastWiFiConfig({
                ssid: config.ssid,
                password: config.password,
                setup_method: config.setup_method
            });
            this.showNotification('WiFi config broadcasted to all devices', 'success');
        } catch (error) {
            this.log('Failed to broadcast WiFi config:', error);
            this.showNotification('Failed to broadcast WiFi config', 'error');
        }
    }

    // ============================================================================
    // MQTT HANDLERS
    // ============================================================================

    setupMQTTHandlers() {
        const brokerForm = document.getElementById('mqtt-broker-form');
        if (brokerForm) {
            this.addEventListener(brokerForm, 'submit', (e) => this.handleMQTTBrokerConfig(e));
        }

        const testBtn = document.getElementById('test-mqtt-connection') || document.getElementById('test-mqtt-connection-btn');
        if (testBtn) {
            this.addEventListener(testBtn, 'click', () => this.testMQTTConnection());
        }

        const discoverBtn = document.getElementById('discover-mqtt-devices') || document.getElementById('discover-mqtt-devices-btn');
        if (discoverBtn) {
            this.addEventListener(discoverBtn, 'click', () => this.discoverMQTTDevices());
        }

        const addMQTTForm = document.getElementById('mqtt-device-form') || document.getElementById('add-mqtt-device-form');
        if (addMQTTForm) {
            this.addEventListener(addMQTTForm, 'submit', (e) => this.handleAddMQTTDevice(e));
        }
    }

    async handleMQTTBrokerConfig(event) {
        event.preventDefault();
        const form = event.target;
        const formData = new FormData(form);

        try {
            await this.dataService.configureMQTTBroker(Object.fromEntries(formData));
            this.showNotification('MQTT broker configured successfully', 'success');
        } catch (error) {
            this.log('Failed to configure MQTT broker:', error);
            this.showNotification('Failed to configure MQTT broker', 'error');
        }
    }

    async testMQTTConnection() {
        try {
            const result = await this.dataService.testMQTTConnection();
            if (result.success) {
                this.showNotification('MQTT connection successful', 'success');
            } else {
                this.showNotification('MQTT connection failed', 'error');
            }
        } catch (error) {
            this.log('Failed to test MQTT connection:', error);
            this.showNotification('MQTT connection test failed', 'error');
        }
    }

    async discoverMQTTDevices() {
        try {
            await this.dataService.discoverMQTTDevices();
            this.showNotification('MQTT discovery started', 'success');
            setTimeout(() => this.loadMQTTDevices(), 5000);
        } catch (error) {
            this.log('Failed to start MQTT discovery:', error);
            this.showNotification('Failed to start MQTT discovery', 'error');
        }
    }

    async handleAddMQTTDevice(event) {
        event.preventDefault();
        const form = event.target;
        const formData = new FormData(form);

        try {
            await this.dataService.addMQTTDevice(Object.fromEntries(formData));
            this.showNotification('MQTT device added successfully', 'success');
            form.reset();
            await this.loadMQTTDevices();
        } catch (error) {
            this.log('Failed to add MQTT device:', error);
            this.showNotification('Failed to add MQTT device', 'error');
        }
    }

    async loadMQTTDevices() {
        try {
            const devices = await this.dataService.loadMQTTDevices();
            this.renderMQTTDevices(devices);
        } catch (error) {
            this.log('Failed to load MQTT devices:', error);
        }
    }

    renderMQTTDevices(devices) {
        const container = document.getElementById('mqtt-devices-list');
        if (!container) return;

        if (!devices || devices.length === 0) {
            container.innerHTML = '<p class="text-muted">No MQTT devices found</p>';
            return;
        }

        container.innerHTML = devices.map(device => `
            <div class="device-card">
                <h4>${device.name}</h4>
                <p>Topic: ${device.topic}</p>
                <p>Type: ${device.device_type}</p>
            </div>
        `).join('');
    }

    // ============================================================================
    // CAMERA HANDLERS
    // ============================================================================

    handleCameraTypeChange(event) {
        const cameraType = event.target.value;
        const form = document.getElementById('camera-form');
        if (!form) return;

        // Hide all conditional fields
        const allConditionalFields = form.querySelectorAll('.conditional-field');
        allConditionalFields.forEach(field => {
            field.style.display = 'none';
        });

        // Show fields for selected camera type
        if (cameraType) {
            const fieldsToShow = form.querySelectorAll(`.conditional-field[data-camera*="${cameraType}"]`);
            fieldsToShow.forEach(field => {
                field.style.display = 'block';
            });
        }
    }

    async loadCameraSettings() {
        try {
            const form = document.getElementById('camera-form');
            if (!form) return;

            const unitId = form.querySelector('[name="unit_id"]')?.value;
            if (!unitId) return;

            const settings = await this.dataService.loadCameraSettings(unitId);
            if (!settings || typeof settings !== 'object') return;

            if (Object.keys(settings).length === 0) {
                const selectedUnit = unitId;
                form.reset();
                const unitSelect = form.querySelector('[name="unit_id"]');
                if (unitSelect) unitSelect.value = selectedUnit;

                const cameraTypeSelect = form.querySelector('[name="camera_type"]');
                if (cameraTypeSelect) {
                    this.handleCameraTypeChange({ target: cameraTypeSelect });
                }
                return;
            }

            // Populate form with existing settings (avoid writing "null" strings)
            Object.keys(settings).forEach(key => {
                const input = form.querySelector(`[name="${key}"]`);
                if (!input) return;
                const value = settings[key];
                input.value = value === null || value === undefined ? '' : value;
            });

            // Ensure conditional fields reflect loaded type
            const cameraTypeSelect = form.querySelector('[name="camera_type"]');
            if (cameraTypeSelect) {
                this.handleCameraTypeChange({ target: cameraTypeSelect });
            }
        } catch (error) {
            this.log('Failed to load camera settings:', error);
        }
    }

    async handleCameraSettings(event) {
        event.preventDefault();
        const form = event.target;
        const formData = new FormData(form);

        // Get unit ID
        const unitId = formData.get('unit_id');
        if (!unitId) {
            this.showNotification('Please select a growth unit', 'error');
            return;
        }

        // Get camera type
        const cameraType = formData.get('camera_type');
        if (!cameraType) {
            this.showNotification('Please select a camera type', 'error');
            return;
        }

        // Build settings object based on camera type
        const settings = {
            camera_type: cameraType
        };

        // Add type-specific fields
        if (cameraType === 'esp32') {
            settings.ip_address = formData.get('ip_address');
            settings.port = parseInt(formData.get('port')) || 81;
            
            if (!settings.ip_address) {
                this.showNotification('Please enter ESP32 IP address', 'error');
                return;
            }
        } else if (cameraType === 'usb') {
            settings.device_index = parseInt(formData.get('device_index')) || 0;
        } else if (['rtsp', 'mjpeg', 'http'].includes(cameraType)) {
            settings.stream_url = formData.get('stream_url');
            settings.username = formData.get('username') || null;
            settings.password = formData.get('password') || null;
            
            if (!settings.stream_url) {
                this.showNotification('Please enter stream URL', 'error');
                return;
            }
        }

        // Add optional settings
        const resolution = formData.get('resolution');
        if (resolution) settings.resolution = resolution;
        
        const quality = formData.get('quality');
        if (quality) settings.quality = quality;
        
        const flip = formData.get('flip');
        if (flip) settings.flip = parseInt(flip);
        
        const brightness = formData.get('brightness');
        if (brightness) settings.brightness = parseInt(brightness);
        
        const contrast = formData.get('contrast');
        if (contrast) settings.contrast = parseInt(contrast);
        
        const saturation = formData.get('saturation');
        if (saturation) settings.saturation = parseInt(saturation);

        try {
            // Call per-unit camera settings endpoint
            const result = await this.dataService.saveCameraSettings(unitId, settings);
            if (result?.restart_error) {
                this.showNotification(`Saved, but restart failed: ${result.restart_error}`, 'error');
            } else {
                this.showNotification(`Camera settings saved for Unit ${unitId}`, 'success');
            }

            // Refresh displayed settings (normalizes defaults from backend)
            await this.loadCameraSettings();
        } catch (error) {
            this.log('Failed to save camera settings:', error);
            this.showNotification('Failed to save camera settings', 'error');
        }
    }

    // ============================================================================
    // NOTIFICATION HELPER
    // ============================================================================

    showNotification(message, type = 'info') {
        const notification = document.createElement('div');
        notification.className = `alert alert-${type}`;
        notification.style.cssText = 'position: fixed; top: 20px; right: 20px; z-index: 10000; min-width: 300px; animation: slideIn 0.3s ease-out;';
        notification.innerHTML = `
            <p>${message}</p>
            <button class="flash-close" title="Close" aria-label="Close notification">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <line x1="18" y1="6" x2="6" y2="18"></line>
                    <line x1="6" y1="6" x2="18" y2="18"></line>
                </svg>
            </button>
        `;
        
        document.body.appendChild(notification);
        
        const closeBtn = notification.querySelector('.flash-close');
        if (closeBtn) {
            closeBtn.addEventListener('click', () => notification.remove());
        }
        
        // Auto-remove after 5 seconds
        setTimeout(() => {
            notification.style.animation = 'slideOut 0.3s ease-in';
            setTimeout(() => notification.remove(), 300);
        }, 5000);
    }
}
