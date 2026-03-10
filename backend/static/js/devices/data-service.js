/**
 * Devices Data Service
 * ============================================
 * Handles all data fetching and state management for Devices page
 */

class DevicesDataService {
    constructor() {
        this.cache = new CacheService('devices', 2 * 60 * 1000); // 2 minutes cache
        if (!window.API) {
            throw new Error('API not loaded. Ensure api.js is loaded before devices data-service.js');
        }
        this.api = window.API;
        this.dbSensors = [];
        this.selectedUnitId = 1;
    }

    /**
     * Initialize service with initial data
     */
    init(sensors, unitId) {
        this.dbSensors = sensors || [];
        this.selectedUnitId = parseInt(unitId || "1", 10);
    }

    /**
     * Get current unit ID
     */
    getSelectedUnitId() {
        return this.selectedUnitId;
    }

    /**
     * Set selected unit ID
     */
    setSelectedUnitId(unitId) {
        this.selectedUnitId = parseInt(unitId, 10);
    }

    /**
     * Get database sensors
     */
    getDBSensors() {
        return this.dbSensors;
    }

    // ============================================================================
    // SENSOR MANAGEMENT
    // ============================================================================

    /**
     * Add a new sensor
     */
    async addSensor(sensorData) {
        const response = await this.api.Device.addSensor(sensorData);
        this.cache.clearByPattern('sensors');
        return response;
    }

    /**
     * Resolve primary metrics conflicts
     */
    async resolvePrimaryMetrics(payload) {
        const response = await this.api.Device.resolvePrimaryMetrics(payload);
        this.cache.clearByPattern('sensors');
        return response;
    }

    /**
     * Update primary metrics for a sensor
     */
    async updateSensorPrimaryMetrics(sensorId, payload) {
        const response = await this.api.Device.updateSensorPrimaryMetrics(sensorId, payload);
        this.cache.clearByPattern('sensors');
        return response;
    }

    /**
     * Update sensor details (name/config)
     */
    async updateSensor(sensorId, payload) {
        const response = await this.api.Device.updateSensor(sensorId, payload);
        this.cache.clearByPattern('sensors');
        return response;
    }

    /**
     * Remove a sensor
     */
    async removeSensor(sensorId) {
        const response = await this.api.Device.deleteSensor(sensorId);
        this.cache.clearByPattern('sensors');
        return response;
    }

    // ============================================================================
    // ACTUATOR MANAGEMENT
    // ============================================================================

    /**
     * Add a new actuator
     */
    async addActuator(actuatorData) {
        const response = await this.api.Device.addActuator(actuatorData);
        this.cache.clearByPattern('actuators');
        return response;
    }

    /**
     * Remove an actuator
     */
    async removeActuator(actuatorId) {
        const response = await this.api.Device.deleteActuator(actuatorId);
        this.cache.clearByPattern('actuators');
        return response;
    }

    /**
     * Control an actuator
     */
    async controlActuator(actuatorType, action) {
        const response = await this.api.Device.controlActuator({
            actuator_type: actuatorType,
            action: action
        });
        return response;
    }

    // ============================================================================
    // DEVICE HEALTH
    // ============================================================================

    /**
     * Load device health metrics
     */
    async loadDeviceHealthMetrics() {
        const cacheKey = 'health_metrics';
        const cached = this.cache.get(cacheKey);
        if (cached) return cached;

        const data = await this.api.Health.getDevicesHealth();
        this.cache.set(cacheKey, data);
        return data;
    }

    /**
     * Load health for a specific device
     */
    async loadDeviceHealth(deviceId, deviceType) {
        const cacheKey = `health_${deviceType}_${deviceId}`;
        const cached = this.cache.get(cacheKey);
        if (cached) return cached;

        // Use appropriate API based on device type
        let data;
        if (deviceType === 'sensor') {
            data = await this.api.Device.getSensorHealth(deviceId);
        } else if (deviceType === 'actuator') {
            data = await this.api.Device.getActuatorHealth(deviceId);
        }
        this.cache.set(cacheKey, data);
        return data;
    }

    // ============================================================================
    // ZIGBEE DEVICES
    // ============================================================================

    /**
     * Load Zigbee sensors
     */
    async loadZigbeeSensors() {
        const cacheKey = 'zigbee_sensors';
        const cached = this.cache.get(cacheKey);
        if (cached) return cached;

        // Use v2 discovery (includes sensor_types/capabilities used by the Zigbee UI cards)
        const data = await this.api.Device.discoverZigbee();
        this.cache.set(cacheKey, data);
        return data;
    }

    /**
     * Discover Zigbee devices
     */
    async discoverZigbeeDevices() {
        const response = await this.api.Device.discoverZigbee();
        // Invalidate zigbee-related cached entries
        if (typeof this.cache.clearByPattern === 'function') {
            this.cache.clearByPattern('zigbee');
        } else if (typeof this.cache.clearPattern === 'function') {
            this.cache.clearPattern('zigbee*');
        } else {
            this.cache.clear();
        }
        return response;
    }

    /**
     * Load Zigbee calibration
     */
    async loadZigbeeCalibration(sensorId) {
        const cacheKey = `zigbee_calibration_${sensorId}`;
        const cached = this.cache.get(cacheKey);
        if (cached) return cached;

        const result = await this.api.Device.getZigbeeCalibration(sensorId);
        const offsets = result?.calibration_offsets || {};
        this.cache.set(cacheKey, offsets);
        return offsets;
    }

    /**
     * Set Zigbee calibration
     */
    async setZigbeeCalibration(friendlyName, sensorType, offset) {
        const sensor = this.dbSensors.find(s => (s.friendly_name || s.name) === friendlyName);
        if (!sensor) {
            throw new Error('Sensor not found');
        }

        const result = await this.api.Device.setZigbeeCalibration(sensor.sensor_id, sensorType, offset);
        if (typeof this.cache.clearByPattern === 'function') {
            this.cache.clearByPattern(`zigbee_calibration_${sensor.sensor_id}`);
        } else if (typeof this.cache.clearPattern === 'function') {
            this.cache.clearPattern(`zigbee_calibration_${sensor.sensor_id}`);
        } else {
            this.cache.invalidate(`zigbee_calibration_${sensor.sensor_id}`);
        }
        return result;
    }

    /**
     * Get Zigbee bridge status
     */
    async getBridgeStatus() {
        const cacheKey = 'zigbee_bridge_status';
        const cached = this.cache.get(cacheKey);
        if (cached) return cached;

        const response = await this.api.Device.getZigbeeBridgeStatus();
        const data = response?.data || response;
        this.cache.set(cacheKey, data, 30000); // 30 second cache
        return data;
    }

    /**
     * Enable permit join to allow new devices to join
     * @param {number} duration - Duration in seconds (0-254)
     */
    async permitJoin(duration = 254) {
        const response = await this.api.Device.permitZigbeeJoin(duration);
        return response?.data || response;
    }

    /**
     * Force rediscovery of all Zigbee devices
     */
    async forceRediscovery() {
        const response = await this.api.Device.forceZigbeeRediscovery();
        this.cache.clearByPattern('zigbee');
        return response?.data || response;
    }

    /**
     * Remove a Zigbee device from the network
     * @param {string} ieeeAddress - Device IEEE address
     */
    async removeZigbeeDevice(ieeeAddress) {
        const response = await this.api.Device.removeZigbeeDevice(ieeeAddress);
        this.cache.clearByPattern('zigbee');
        return response?.data || response;
    }

    /**
     * Rename a Zigbee device
     * @param {string} ieeeAddress - Device IEEE address
     * @param {string} newName - New friendly name
     */
    async renameZigbeeDevice(ieeeAddress, newName) {
        const response = await this.api.Device.renameZigbeeDevice(ieeeAddress, newName);
        this.cache.clearByPattern('zigbee');
        return response?.data || response;
    }

    // ============================================================================
    // ESP32 DEVICES
    // ============================================================================

    /**
     * Scan for ESP32 devices
     */
    async scanForDevices() {
        const response = await this.api.ESP32.scan();
        return response;
    }

    /**
     * Load device info
     */
    async loadDeviceInfo(deviceId) {
        const cacheKey = `esp32_info_${deviceId}`;
        const cached = this.cache.get(cacheKey);
        if (cached) return cached;

        const data = await this.api.ESP32.getDevice(deviceId);
        this.cache.set(cacheKey, data);
        return data;
    }

    /**
     * Provision ESP32 device
     */
    async provisionDevice(formData) {
        const response = await this.api.ESP32.provision(formData);
        this.cache.clearByPattern('esp32');
        return response;
    }

    unsupportedConnectivityFeature(feature) {
        throw new Error(
            `${feature} is not available from the release web UI. Use ESP32 provisioning, Zigbee2MQTT discovery, or configure Mosquitto directly on the Raspberry Pi.`
        );
    }

    /**
     * Send WiFi config
     */
    async sendWiFiConfig(configData) {
        return this.unsupportedConnectivityFeature('Direct WiFi credential push');
    }

    /**
     * Broadcast WiFi config
     */
    async broadcastWiFiConfig(configData) {
        return this.unsupportedConnectivityFeature('Broadcast WiFi provisioning');
    }

    // ============================================================================
    // MQTT DEVICES
    // ============================================================================

    /**
     * Configure MQTT broker
     */
    async configureMQTTBroker(brokerConfig) {
        return this.unsupportedConnectivityFeature('Generic MQTT broker management');
    }

    /**
     * Test MQTT connection
     */
    async testMQTTConnection() {
        return this.unsupportedConnectivityFeature('Generic MQTT connection testing');
    }

    /**
     * Discover MQTT devices
     */
    async discoverMQTTDevices() {
        return this.unsupportedConnectivityFeature('Generic MQTT device discovery');
    }

    /**
     * Add MQTT device
     */
    async addMQTTDevice(deviceData) {
        return this.unsupportedConnectivityFeature('Generic MQTT device registration');
    }

    /**
     * Add MQTT sensor
     */
    async addMQTTSensor(sensorData) {
        return this.unsupportedConnectivityFeature('Generic MQTT sensor registration');
    }

    /**
     * Add MQTT actuator
     */
    async addMQTTActuator(actuatorData) {
        return this.unsupportedConnectivityFeature('Generic MQTT actuator registration');
    }

    /**
     * Load MQTT devices
     */
    async loadMQTTDevices() {
        return this.unsupportedConnectivityFeature('Generic MQTT device inventory');
    }

    /**
     * Load growth units for MQTT
     */
    async loadGrowthUnitsForMQTT() {
        const cacheKey = 'growth_units';
        const cached = this.cache.get(cacheKey);
        if (cached) return cached;

        const response = await this.api.Growth.listUnits();
        const data = response?.data || response || [];
        this.cache.set(cacheKey, data);
        return data;
    }

    // ============================================================================
    // CAMERA DEVICES
    // ============================================================================

    /**
     * Load camera settings
     */
    async loadCameraSettings(unitId) {
        const parsedUnitId = parseInt(unitId, 10);
        if (!parsedUnitId || Number.isNaN(parsedUnitId)) return null;

        const cacheKey = `camera_settings_unit_${parsedUnitId}`;
        const cached = this.cache.get(cacheKey);
        if (cached) return cached;

        const status = await this.api.Growth.getCameraStatus(parsedUnitId);
        const settings = status?.settings || {};
        this.cache.set(cacheKey, settings);
        return settings;
    }

    /**
     * Save camera settings
     */
    async saveCameraSettings(unitId, cameraData) {
        const parsedUnitId = parseInt(unitId, 10);
        if (!parsedUnitId || Number.isNaN(parsedUnitId)) {
            throw new Error('Invalid unit ID');
        }

        const response = await this.api.Growth.updateCameraSettings(parsedUnitId, cameraData);
        this.cache.invalidate(`camera_settings_unit_${parsedUnitId}`);
        return response;
    }
}
