/**
 * Device Health Data Service
 * ============================================================================
 * Handles all API calls and data management for device health monitoring.
 * Uses CacheService for efficient data fetching.
 */
(function() {
  'use strict';

  const API = window.API;
  if (!API) {
    throw new Error('API not loaded. Ensure api.js is loaded before data-service.js');
  }

  const CACHE_TTL = 60000; // 1 minute cache for device health data

  class DeviceHealthDataService {
    constructor() {
      this.cache = window.CacheService ? new window.CacheService('device_health', CACHE_TTL) : null;
      this.deviceAPI = API.Device;
      this.insightsAPI = API.Insights;

      // Local data stores
      this.devices = {
        actuators: [],
        sensors: []
      };
      this.anomalies = [];
      this.healthHistory = new Map();
      this.connectionMetrics = new Map();
    }

    // --------------------------------------------------------------------------
    // Device Loading
    // --------------------------------------------------------------------------

    /**
     * Load all devices (actuators and sensors)
     * @param {Object} options - { force: boolean }
     * @returns {Promise<{actuators: Array, sensors: Array}>}
     */
    async loadDevices(options = {}) {
      const cacheKey = 'all_devices';

      if (!options.force && this.cache) {
        const cached = this.cache.get(cacheKey);
        if (cached) {
          this.devices = cached;
          return cached;
        }
      }

      try {
        // Load actuators
        const actuatorsResponse = await this.deviceAPI.getAllActuators();
        const actuators = actuatorsResponse?.data ?? actuatorsResponse;
        this.devices.actuators = Array.isArray(actuators) ? actuators : [];
        this.devices.actuators = this.devices.actuators.map(actuator => ({
          ...actuator,
          status: actuator.enabled === false ? 'offline' : 'online',
        }));

        // Load sensors
        const sensorsResponse = await this.deviceAPI.getAllSensors();
        const sensors = sensorsResponse?.data ?? sensorsResponse;
        this.devices.sensors = Array.isArray(sensors) ? sensors : [];
        this.devices.sensors = this.devices.sensors.map(sensor => ({
          ...sensor,
          status: sensor.enabled === false ? 'offline' : (sensor.last_reading_time ? 'online' : 'unknown'),
        }));

        // Cache the result
        if (this.cache) {
          this.cache.set(cacheKey, this.devices);
        }

        return this.devices;
      } catch (error) {
        console.error('[DeviceHealthDataService] loadDevices failed:', error);
        throw error;
      }
    }

    /**
     * Load actuators only
     * @param {Object} options - { force: boolean }
     * @returns {Promise<Array>}
     */
    async loadActuators(options = {}) {
      const cacheKey = 'actuators';

      if (!options.force && this.cache) {
        const cached = this.cache.get(cacheKey);
        if (cached) {
          this.devices.actuators = cached;
          return cached;
        }
      }

      try {
        const response = await this.deviceAPI.getAllActuators();
        const actuators = response?.data ?? response;
        this.devices.actuators = Array.isArray(actuators) ? actuators : [];
        this.devices.actuators = this.devices.actuators.map(actuator => ({
          ...actuator,
          status: actuator.enabled === false ? 'offline' : 'online',
        }));

        if (this.cache) {
          this.cache.set(cacheKey, this.devices.actuators);
        }

        return this.devices.actuators;
      } catch (error) {
        console.error('[DeviceHealthDataService] loadActuators failed:', error);
        throw error;
      }
    }

    /**
     * Load sensors only
     * @param {Object} options - { force: boolean }
     * @returns {Promise<Array>}
     */
    async loadSensors(options = {}) {
      const cacheKey = 'sensors';

      if (!options.force && this.cache) {
        const cached = this.cache.get(cacheKey);
        if (cached) {
          this.devices.sensors = cached;
          return cached;
        }
      }

      try {
        const response = await this.deviceAPI.getAllSensors();
        const sensors = response?.data ?? response;
        this.devices.sensors = Array.isArray(sensors) ? sensors : [];
        this.devices.sensors = this.devices.sensors.map(sensor => ({
          ...sensor,
          status: sensor.enabled === false ? 'offline' : (sensor.last_reading_time ? 'online' : 'unknown'),
        }));

        if (this.cache) {
          this.cache.set(cacheKey, this.devices.sensors);
        }

        return this.devices.sensors;
      } catch (error) {
        console.error('[DeviceHealthDataService] loadSensors failed:', error);
        throw error;
      }
    }

    // --------------------------------------------------------------------------
    // Anomalies & Alerts
    // --------------------------------------------------------------------------

    /**
     * Load device anomalies
     * @returns {Promise<Array>}
     */
    async loadAnomalies() {
      try {
        // No unified "all-device anomalies" endpoint is currently exposed.
        // Anomalies are loaded per-device on demand.
        this.anomalies = [];
        return this.anomalies;
      } catch (error) {
        console.error('[DeviceHealthDataService] loadAnomalies failed:', error);
        return [];
      }
    }

    /**
     * Generate alerts from device data and anomalies
     * @returns {Array}
     */
    generateAlerts() {
      const alerts = [];

      // Check offline devices
      const offlineActuators = this.devices.actuators.filter(d => d.status === 'offline');
      const offlineSensors = this.devices.sensors.filter(d => d.status === 'offline');

      offlineActuators.forEach(device => {
        alerts.push({
          id: `offline-actuator-${device.id}`,
          type: 'offline',
          severity: 'high',
          deviceId: device.id,
          deviceType: 'actuator',
          deviceName: device.name,
          title: `Actuator Offline: ${device.name}`,
          message: `${device.type} has been offline since ${device.last_state_change || 'unknown'}.`,
          timestamp: new Date(device.last_state_change || Date.now()),
          actions: ['view-details', 'acknowledge']
        });
      });

      offlineSensors.forEach(device => {
        alerts.push({
          id: `offline-sensor-${device.id}`,
          type: 'offline',
          severity: 'high',
          deviceId: device.id,
          deviceType: 'sensor',
          deviceName: device.name,
          title: `Sensor Offline: ${device.name}`,
          message: `${this._formatDeviceType(device.type)} has been offline since ${device.last_reading_time || 'unknown'}.`,
          timestamp: new Date(device.last_reading_time || Date.now()),
          actions: ['view-details', 'acknowledge']
        });
      });

      // Add anomaly alerts
      this.anomalies.forEach(anomaly => {
        alerts.push({
          id: `anomaly-${anomaly.id || Date.now()}`,
          type: 'anomaly',
          severity: anomaly.severity || 'medium',
          deviceId: anomaly.device_id,
          deviceType: anomaly.device_type,
          deviceName: anomaly.device_name,
          title: `Anomaly Detected: ${anomaly.device_name}`,
          message: anomaly.description || 'Unusual behavior detected',
          timestamp: new Date(anomaly.detected_at || Date.now()),
          actions: ['view-details', 'investigate']
        });
      });

      // Sort by severity and timestamp
      const severityOrder = { critical: 0, high: 1, medium: 2, low: 3 };
      return alerts.sort((a, b) => {
        const severityDiff = severityOrder[a.severity] - severityOrder[b.severity];
        if (severityDiff !== 0) return severityDiff;
        return b.timestamp - a.timestamp;
      });
    }

    // --------------------------------------------------------------------------
    // Device Health History
    // --------------------------------------------------------------------------

    /**
     * Load device health history
     * @param {string|number} deviceId
     * @param {string} deviceType - 'actuator' or 'sensor'
     * @returns {Promise<Array>}
     */
    async loadDeviceHealthHistory(deviceId, deviceType) {
      try {
        const cacheKey = `${deviceType}-${deviceId}`;
        if (this.healthHistory.has(cacheKey)) {
          return this.healthHistory.get(cacheKey);
        }

        let historyData = [];
        if (deviceType === 'sensor') {
          const response = await this.deviceAPI.getSensorHealthHistory(deviceId);
          historyData = response?.data?.history || [];
        } else if (deviceType === 'actuator') {
          const response = await this.deviceAPI.getActuatorHealth(deviceId);
          historyData = response?.data?.health_history || [];
        }

        // Cache it
        this.healthHistory.set(cacheKey, historyData);
        return historyData;
      } catch (error) {
        console.error(`[DeviceHealthDataService] loadDeviceHealthHistory(${deviceId}, ${deviceType}) failed:`, error);
        return [];
      }
    }

    /**
     * Load connection metrics for a device
     * @param {string|number} deviceId
     * @param {string} deviceType
     * @returns {Promise<Object>}
     */
    async loadConnectionMetrics(deviceId, deviceType) {
      try {
        const cacheKey = `metrics-${deviceType}-${deviceId}`;
        if (this.connectionMetrics.has(cacheKey)) {
          return this.connectionMetrics.get(cacheKey);
        }

        // Connection metrics endpoint not currently implemented
        const metrics = {};
        this.connectionMetrics.set(cacheKey, metrics);
        return metrics;
      } catch (error) {
        console.error(`[DeviceHealthDataService] loadConnectionMetrics(${deviceId}, ${deviceType}) failed:`, error);
        return {};
      }
    }

    // --------------------------------------------------------------------------
    // Statistics
    // --------------------------------------------------------------------------

    /**
     * Get device statistics
     * @returns {Object}
     */
    getStatistics() {
      const onlineActuators = this.devices.actuators.filter(d => d.status === 'online').length;
      const onlineSensors = this.devices.sensors.filter(d => d.status === 'online').length;
      const offlineActuators = this.devices.actuators.filter(d => d.status === 'offline').length;
      const offlineSensors = this.devices.sensors.filter(d => d.status === 'offline').length;

      return {
        online: onlineActuators + onlineSensors,
        offline: offlineActuators + offlineSensors,
        total: this.devices.actuators.length + this.devices.sensors.length,
        anomalies: this.anomalies.length,
        actuators: {
          total: this.devices.actuators.length,
          online: onlineActuators,
          offline: offlineActuators
        },
        sensors: {
          total: this.devices.sensors.length,
          online: onlineSensors,
          offline: offlineSensors
        }
      };
    }

    /**
     * Get device by ID
     * @param {string|number} deviceId
     * @param {string} deviceType
     * @returns {Object|null}
     */
    getDevice(deviceId, deviceType) {
      const numericId = Number(deviceId);
      const deviceList = deviceType === 'actuator' ? this.devices.actuators : this.devices.sensors;
      return deviceList.find(d => Number(d.id) === numericId) || null;
    }

    /**
     * Update device in local store (for real-time updates)
     * @param {Object} data - Device update data
     */
    updateDevice(data) {
      const deviceType = data.device_type;
      const deviceId = Number(data.device_id);

      if (deviceType === 'actuator') {
        const index = this.devices.actuators.findIndex(a => Number(a.id) === deviceId);
        if (index !== -1) {
          this.devices.actuators[index] = { ...this.devices.actuators[index], ...data };
        }
      } else if (deviceType === 'sensor') {
        const index = this.devices.sensors.findIndex(s => Number(s.id) === deviceId);
        if (index !== -1) {
          this.devices.sensors[index] = { ...this.devices.sensors[index], ...data };
        }
      }

      // Invalidate cache
      if (this.cache) {
        this.cache.invalidate('all_devices');
        this.cache.invalidate(deviceType === 'actuator' ? 'actuators' : 'sensors');
      }
    }

    /**
     * Add anomaly to local store
     * @param {Object} anomaly
     */
    addAnomaly(anomaly) {
      this.anomalies.push(anomaly);
    }

    // --------------------------------------------------------------------------
    // Helpers
    // --------------------------------------------------------------------------

    _formatDeviceType(type) {
      if (!type) return 'Unknown';
      return type.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
    }

    /**
     * Clear all caches
     */
    clearCache() {
      if (this.cache) {
        this.cache.clear();
      }
      this.healthHistory.clear();
      this.connectionMetrics.clear();
    }
  }

  // Export to window
  window.DeviceHealthDataService = DeviceHealthDataService;
})();
