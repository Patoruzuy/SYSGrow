/**
 * Settings Data Service
 * 
 * Handles all API interactions for settings with caching support.
 * Provides methods for loading and saving configuration data.
 */

class SettingsDataService {
  constructor(api, cacheService, selectedUnitId = null) {
    if (!api) throw new Error('API instance is required');
    if (!cacheService) throw new Error('CacheService is required');

    this.api = api;
    this.cache = cacheService;
    this.selectedUnitId = selectedUnitId;
    this.inFlight = new Map();
  }

  /**
   * Generate cache key with unit scope
   */
  _key(base) {
    return this.selectedUnitId ? `${base}__unit_${this.selectedUnitId}` : `${base}__all`;
  }

  /**
   * Update selected unit and clear unit-scoped cache
   */
  setSelectedUnit(unitId) {
    const prev = this.selectedUnitId;
    this.selectedUnitId = Number.isFinite(unitId) ? unitId : null;

    if (prev !== this.selectedUnitId) {
      // Invalidate unit-scoped caches
      this.cache.invalidate(this._key('environment'));
      this.cache.invalidate(this._key('schedules'));
      this.cache.invalidate(this._key('throttle'));

      // Drop in-flight unit-scoped promises (prevents old unit responses "winning")
      for (const key of Array.from(this.inFlight.keys())) {
        if (key.includes('__unit_')) {
          this.inFlight.delete(key);
        }
      }
    }
  }

  /**
   * Helper: Wrap fetcher with cache + in-flight de-duplication
   */
  async _cached(key, fetcher, { force = false } = {}) {
    if (!force) {
      const cached = this.cache.get(key);
      if (cached !== null) return cached;
    }

    if (this.inFlight.has(key)) return this.inFlight.get(key);

    const p = (async () => {
      try {
        const data = await fetcher();
        this.cache.set(key, data);
        return data;
      } catch (error) {
        throw error;
      } finally {
        this.inFlight.delete(key);
      }
    })();

    this.inFlight.set(key, p);
    return p;
  }

  // ============================================================================
  // ENVIRONMENT SETTINGS
  // ============================================================================

  async loadEnvironment({ force = false } = {}) {
    if (!this.selectedUnitId) return null;

    const cacheKey = this._key('environment');

    try {
      return await this._cached(
        cacheKey,
        async () => {
          const response = await this.api.Growth.getThresholds(this.selectedUnitId);
          return response || {};
        },
        { force }
      );
    } catch (error) {
      console.error('[SettingsDataService] loadEnvironment failed:', error);
      return null;
    }
  }

  async saveEnvironment(data) {
    if (!this.selectedUnitId) throw new Error('No unit selected');

    try {
      const response = await this.api.Growth.setThresholds(this.selectedUnitId, data);
      
      // Invalidate cache
      this.cache.invalidate(this._key('environment'));
      
      return response;
    } catch (error) {
      console.error('[SettingsDataService] saveEnvironment failed:', error);
      throw error;
    }
  }

  async suggestThresholds() {
    if (!this.selectedUnitId) throw new Error('No unit selected');

    try {
      return await this.api.Growth.suggestThresholds(this.selectedUnitId);
    } catch (error) {
      console.error('[SettingsDataService] suggestThresholds failed:', error);
      throw error;
    }
  }

  // ============================================================================
  // DEVICE SCHEDULES (V3 API)
  // ============================================================================

  /**
   * Load all schedules for the selected unit using v3 API
   */
  async loadSchedulesV3({ force = false, device_type = null, enabled_only = false } = {}) {
    if (!this.selectedUnitId) return [];

    const cacheKey = this._key('schedules_v3');

    try {
      return await this._cached(
        cacheKey,
        async () => {
          const response = await this.api.Growth.getSchedulesV3(this.selectedUnitId, {
            device_type,
            enabled_only
          });
          return response?.schedules || [];
        },
        { force }
      );
    } catch (error) {
      console.error('[SettingsDataService] loadSchedulesV3 failed:', error);
      return [];
    }
  }

  /**
   * Get schedule summary for the selected unit
   */
  async getScheduleSummary({ force = false } = {}) {
    if (!this.selectedUnitId) return null;

    const cacheKey = this._key('schedule_summary');

    try {
      return await this._cached(
        cacheKey,
        async () => {
          return await this.api.Growth.getScheduleSummaryV3(this.selectedUnitId);
        },
        { force }
      );
    } catch (error) {
      console.error('[SettingsDataService] getScheduleSummary failed:', error);
      return null;
    }
  }

  /**
   * Create a new schedule using v3 API
   */
  async createScheduleV3(scheduleData) {
    if (!this.selectedUnitId) throw new Error('No unit selected');

    try {
      const response = await this.api.Growth.createScheduleV3(this.selectedUnitId, scheduleData);
      
      // Invalidate caches
      this.cache.invalidate(this._key('schedules_v3'));
      this.cache.invalidate(this._key('schedule_summary'));
      
      return response;
    } catch (error) {
      console.error('[SettingsDataService] createScheduleV3 failed:', error);
      throw error;
    }
  }

  /**
   * Update an existing schedule using v3 API
   */
  async updateScheduleV3(scheduleId, scheduleData) {
    if (!this.selectedUnitId) throw new Error('No unit selected');

    try {
      const response = await this.api.Growth.updateScheduleV3(this.selectedUnitId, scheduleId, scheduleData);
      
      // Invalidate caches
      this.cache.invalidate(this._key('schedules_v3'));
      this.cache.invalidate(this._key('schedule_summary'));
      
      return response;
    } catch (error) {
      console.error('[SettingsDataService] updateScheduleV3 failed:', error);
      throw error;
    }
  }

  /**
   * Toggle schedule enabled state
   */
  async toggleScheduleV3(scheduleId, enabled) {
    if (!this.selectedUnitId) throw new Error('No unit selected');

    try {
      const response = await this.api.Growth.toggleScheduleV3(this.selectedUnitId, scheduleId, enabled);
      
      // Invalidate caches
      this.cache.invalidate(this._key('schedules_v3'));
      this.cache.invalidate(this._key('schedule_summary'));
      
      return response;
    } catch (error) {
      console.error('[SettingsDataService] toggleScheduleV3 failed:', error);
      throw error;
    }
  }

  /**
   * Delete a schedule using v3 API
   */
  async deleteScheduleV3(scheduleId) {
    if (!this.selectedUnitId) throw new Error('No unit selected');

    try {
      const response = await this.api.Growth.deleteScheduleV3(this.selectedUnitId, scheduleId);
      
      // Invalidate caches
      this.cache.invalidate(this._key('schedules_v3'));
      this.cache.invalidate(this._key('schedule_summary'));
      
      return response;
    } catch (error) {
      console.error('[SettingsDataService] deleteScheduleV3 failed:', error);
      throw error;
    }
  }

  /**
   * Preview upcoming schedule events
   */
  async previewSchedules({ hours = 24, device_type = null } = {}) {
    if (!this.selectedUnitId) return { events: [] };

    try {
      return await this.api.Growth.previewSchedulesV3(this.selectedUnitId, { hours, device_type });
    } catch (error) {
      console.error('[SettingsDataService] previewSchedules failed:', error);
      return { events: [] };
    }
  }

  /**
   * Detect schedule conflicts
   */
  async detectConflicts({ device_type = null } = {}) {
    if (!this.selectedUnitId) return { conflicts: [], has_conflicts: false };

    try {
      return await this.api.Growth.detectScheduleConflictsV3(this.selectedUnitId, { device_type });
    } catch (error) {
      console.error('[SettingsDataService] detectConflicts failed:', error);
      return { conflicts: [], has_conflicts: false };
    }
  }

  /**
   * Get schedule history/audit log
   */
  async getScheduleHistory({ schedule_id = null, limit = 50 } = {}) {
    if (!this.selectedUnitId) return { history: [] };

    try {
      return await this.api.Growth.getScheduleHistoryV3(this.selectedUnitId, { schedule_id, limit });
    } catch (error) {
      console.error('[SettingsDataService] getScheduleHistory failed:', error);
      return { history: [] };
    }
  }

  /**
   * Get schedule execution log
   */
  async getExecutionLog(scheduleId, { limit = 50 } = {}) {
    try {
      return await this.api.Growth.getScheduleExecutionLogV3(scheduleId, { limit });
    } catch (error) {
      console.error('[SettingsDataService] getExecutionLog failed:', error);
      return { execution_log: [] };
    }
  }

  /**
   * Auto-generate schedules from plant stage
   */
  async autoGenerateSchedules(options = {}) {
    if (!this.selectedUnitId) return { ok: false, error: 'No unit selected' };

    try {
      const response = await this.api.Growth.autoGenerateSchedulesV3(this.selectedUnitId, options);
      // Invalidate caches
      this.cache.invalidate(this._key('schedules_v3'));
      this.cache.invalidate(this._key('schedule_summary'));
      return { ok: true, data: response };
    } catch (error) {
      console.error('[SettingsDataService] autoGenerateSchedules failed:', error);
      return { ok: false, error: error.message || 'Failed to auto-generate schedules' };
    }
  }

  /**
   * Get schedule templates based on plant stage
   */
  async getScheduleTemplates() {
    if (!this.selectedUnitId) return { templates: [] };

    try {
      return await this.api.Growth.getScheduleTemplatesV3(this.selectedUnitId);
    } catch (error) {
      console.error('[SettingsDataService] getScheduleTemplates failed:', error);
      return { templates: [] };
    }
  }

  /**
   * Bulk update schedules (enable/disable/delete multiple)
   */
  async bulkUpdateSchedules(scheduleIds, action) {
    if (!this.selectedUnitId) return { ok: false, error: 'No unit selected' };

    try {
      const response = await this.api.Growth.bulkUpdateSchedulesV3(this.selectedUnitId, {
        schedule_ids: scheduleIds,
        action: action
      });
      // Invalidate caches
      this.cache.invalidate(this._key('schedules_v3'));
      this.cache.invalidate(this._key('schedule_summary'));
      return { ok: true, data: response };
    } catch (error) {
      console.error('[SettingsDataService] bulkUpdateSchedules failed:', error);
      return { ok: false, error: error.message || 'Failed to bulk update schedules' };
    }
  }

  // Legacy v2 methods (kept for backward compatibility)
  async loadDeviceSchedules({ force = false } = {}) {
    if (!this.selectedUnitId) return [];

    const cacheKey = this._key('schedules');

    try {
      return await this._cached(
        cacheKey,
        async () => {
          const response = await this.api.Growth.getSchedules(this.selectedUnitId);
          const schedules = response?.device_schedules;

          if (schedules && typeof schedules === 'object' && !Array.isArray(schedules)) {
            return Object.entries(schedules).map(([device_type, schedule]) => ({
              device_type,
              ...(schedule || {})
            }));
          }

          if (Array.isArray(response)) return response;
          if (Array.isArray(response?.schedules)) return response.schedules;
          return [];
        },
        { force }
      );
    } catch (error) {
      console.error('[SettingsDataService] loadDeviceSchedules failed:', error);
      return [];
    }
  }

  async saveDeviceSchedule(deviceType, scheduleData) {
    if (!this.selectedUnitId) throw new Error('No unit selected');

    try {
      const response = await this.api.Growth.setDeviceSchedule(this.selectedUnitId, {
        device_type: deviceType,
        ...scheduleData
      });
      
      // Invalidate cache
      this.cache.invalidate(this._key('schedules'));
      
      return response;
    } catch (error) {
      console.error('[SettingsDataService] saveDeviceSchedule failed:', error);
      throw error;
    }
  }

  // ============================================================================
  // WIFI & CONNECTIVITY
  // ============================================================================

  async scanWiFiNetworks({ force = false } = {}) {
    const cacheKey = 'wifi_networks';

    try {
      return await this._cached(
        cacheKey,
        async () => {
          const response = await this.api.Settings.scanWiFi();
          return response?.networks || [];
        },
        { force }
      );
    } catch (error) {
      console.error('[SettingsDataService] scanWiFiNetworks failed:', error);
      throw error;
    }
  }

  async sendWiFiConfig(payload) {
    try {
      return await this.api.Settings.configureWiFi(payload);
    } catch (error) {
      console.error('[SettingsDataService] sendWiFiConfig failed:', error);
      throw error;
    }
  }

  async broadcastWiFiConfig(payload) {
    try {
      return await this.api.Settings.broadcastWiFi(payload);
    } catch (error) {
      console.error('[SettingsDataService] broadcastWiFiConfig failed:', error);
      throw error;
    }
  }

  // ============================================================================
  // HOTSPOT SETTINGS
  // ============================================================================

  async loadHotspotSettings({ force = false } = {}) {
    const cacheKey = 'hotspot_settings';

    try {
      return await this._cached(
        cacheKey,
        async () => {
          const response = await this.api.Settings.getHotspot();
          return response || {};
        },
        { force }
      );
    } catch (error) {
      console.error('[SettingsDataService] loadHotspotSettings failed:', error);
      return {};
    }
  }

  async saveHotspotSettings(data) {
    try {
      const response = await this.api.Settings.updateHotspot(data);
      
      // Invalidate cache
      this.cache.invalidate('hotspot_settings');
      
      return response;
    } catch (error) {
      console.error('[SettingsDataService] saveHotspotSettings failed:', error);
      throw error;
    }
  }

  // ============================================================================
  // ESP32 DEVICE MANAGEMENT
  // ============================================================================

  async scanESP32Devices({ force = false } = {}) {
    const cacheKey = 'esp32_devices';

    try {
      return await this._cached(
        cacheKey,
        async () => {
          const response = await this.api.ESP32.scan();
          return response?.devices || [];
        },
        { force }
      );
    } catch (error) {
      console.error('[SettingsDataService] scanESP32Devices failed:', error);
      throw error;
    }
  }

  async loadESP32Device(deviceId) {
    try {
      return await this.api.ESP32.getDevice(deviceId);
    } catch (error) {
      console.error('[SettingsDataService] loadESP32Device failed:', error);
      throw error;
    }
  }

  async saveESP32Device(deviceId, data) {
    try {
      const response = await this.api.ESP32.updateDevice(deviceId, data);
      
      // Invalidate devices cache
      this.cache.invalidate('esp32_devices');
      
      return response;
    } catch (error) {
      console.error('[SettingsDataService] saveESP32Device failed:', error);
      throw error;
    }
  }

  async checkFirmwareUpdate(deviceId) {
    try {
      return await this.api.ESP32.checkFirmware(deviceId);
    } catch (error) {
      console.error('[SettingsDataService] checkFirmwareUpdate failed:', error);
      throw error;
    }
  }

  async provisionDevice(deviceId) {
    try {
      return await this.api.ESP32.provision(deviceId);
    } catch (error) {
      console.error('[SettingsDataService] provisionDevice failed:', error);
      throw error;
    }
  }

  // ============================================================================
  // CAMERA SETTINGS
  // ============================================================================

  async loadCameraSettings({ force = false } = {}) {
    const cacheKey = 'camera_settings';

    try {
      return await this._cached(
        cacheKey,
        async () => {
          const response = await this.api.Settings.getCamera();
          return response || {};
        },
        { force }
      );
    } catch (error) {
      console.error('[SettingsDataService] loadCameraSettings failed:', error);
      return {};
    }
  }

  async saveCameraSettings(data) {
    try {
      const response = await this.api.Settings.updateCamera(data);
      
      // Invalidate cache
      this.cache.invalidate('camera_settings');
      
      return response;
    } catch (error) {
      console.error('[SettingsDataService] saveCameraSettings failed:', error);
      throw error;
    }
  }

  // ============================================================================
  // ANALYTICS SETTINGS
  // ============================================================================

  async loadAnalyticsSettings() {
    try {
      // Load from localStorage (client-side only settings)
      const energySettings = JSON.parse(localStorage.getItem('analytics_energy') || '{}');
      const alertSettings = JSON.parse(localStorage.getItem('analytics_alerts') || '{}');
      const dataSettings = JSON.parse(localStorage.getItem('analytics_data') || '{}');

      return {
        energy: {
          rate: energySettings.rate || 0.12,
          currency: energySettings.currency || 'USD',
          showEstimates: energySettings.showEstimates !== false
        },
        alerts: {
          criticalTemp: alertSettings.criticalTemp || 35,
          criticalHumidity: alertSettings.criticalHumidity || 85,
          methods: alertSettings.methods || ['browser', 'dashboard'],
          frequency: alertSettings.frequency || 'immediate'
        },
        data: {
          exportFormat: dataSettings.exportFormat || 'csv',
          retention: dataSettings.retention || 90,
          autoBackup: dataSettings.autoBackup || false
        }
      };
    } catch (error) {
      console.error('[SettingsDataService] loadAnalyticsSettings failed:', error);
      return null;
    }
  }

  saveAnalyticsSettings(settings) {
    try {
      if (settings.energy) {
        localStorage.setItem('analytics_energy', JSON.stringify(settings.energy));
      }
      if (settings.alerts) {
        localStorage.setItem('analytics_alerts', JSON.stringify(settings.alerts));
      }
      if (settings.data) {
        localStorage.setItem('analytics_data', JSON.stringify(settings.data));
      }
      return true;
    } catch (error) {
      console.error('[SettingsDataService] saveAnalyticsSettings failed:', error);
      throw error;
    }
  }

  // ============================================================================
  // ZIGBEE DISCOVERY
  // ============================================================================

  async discoverZigbeeDevices({ force = false } = {}) {
    const cacheKey = 'zigbee_devices';

    try {
      return await this._cached(
        cacheKey,
        async () => {
          const response = await this.api.Device.discoverZigbee();
          return response?.devices || [];
        },
        { force }
      );
    } catch (error) {
      console.error('[SettingsDataService] discoverZigbeeDevices failed:', error);
      throw error;
    }
  }

  async addDevice(deviceData) {
    try {
      const response = await this.api.Device.addSensor(deviceData);
      
      // Invalidate relevant caches
      this.cache.invalidate('zigbee_devices');
      
      return response;
    } catch (error) {
      console.error('[SettingsDataService] addDevice failed:', error);
      throw error;
    }
  }

  // ============================================================================
  // DATA EXPORT
  // ============================================================================

  async exportAnalyticsData(format = 'csv') {
    try {
      // This would call a backend endpoint to generate and download the export
      const response = await this.api.System.exportData({ format });
      return response;
    } catch (error) {
      console.error('[SettingsDataService] exportAnalyticsData failed:', error);
      throw error;
    }
  }

  // ============================================================================
  // DATABASE THROTTLING (unit-scoped)
  // ============================================================================

  async loadThrottleConfig({ force = false } = {}) {
    if (!this.selectedUnitId) return null;

    const cacheKey = this._key('throttle');

    try {
      return await this._cached(
        cacheKey,
        async () => {
          const response = await this.api.Settings.getThrottleConfig(this.selectedUnitId);
          return response || {};
        },
        { force }
      );
    } catch (error) {
      console.error('[SettingsDataService] loadThrottleConfig failed:', error);
      return null;
    }
  }

  async saveThrottleConfig(payload) {
    if (!this.selectedUnitId) throw new Error('No unit selected');

    try {
      const response = await this.api.Settings.updateThrottleConfig(this.selectedUnitId, payload);
      this.cache.invalidate(this._key('throttle'));
      return response;
    } catch (error) {
      console.error('[SettingsDataService] saveThrottleConfig failed:', error);
      throw error;
    }
  }

  async resetThrottleConfig() {
    if (!this.selectedUnitId) throw new Error('No unit selected');

    try {
      const response = await this.api.Settings.resetThrottleConfig(this.selectedUnitId);
      this.cache.invalidate(this._key('throttle'));
      return response;
    } catch (error) {
      console.error('[SettingsDataService] resetThrottleConfig failed:', error);
      throw error;
    }
  }

  // ============================================================================
  // IRRIGATION WORKFLOW
  // ============================================================================

  async loadIrrigationConfig({ force = false } = {}) {
    if (!this.selectedUnitId) return null;

    const cacheKey = this._key('irrigation_config');

    try {
      return await this._cached(
        cacheKey,
        async () => {
          const response = await this.api.Irrigation.getConfig(this.selectedUnitId);
          return response || {};
        },
        { force }
      );
    } catch (error) {
      console.error('[SettingsDataService] loadIrrigationConfig failed:', error);
      return null;
    }
  }

  async saveIrrigationConfig(config) {
    if (!this.selectedUnitId) throw new Error('No unit selected');

    try {
      const response = await this.api.Irrigation.updateConfig(this.selectedUnitId, config);
      this.cache.invalidate(this._key('irrigation_config'));
      return response;
    } catch (error) {
      console.error('[SettingsDataService] saveIrrigationConfig failed:', error);
      throw error;
    }
  }

  // ============================================================================
  // PUMP CALIBRATION
  // ============================================================================

  async loadPumpCalibration(actuatorId) {
    if (!actuatorId) throw new Error('Actuator ID required');

    try {
      return await this.api.Irrigation.getCalibration(actuatorId);
    } catch (error) {
      console.error('[SettingsDataService] loadPumpCalibration failed:', error);
      return null;
    }
  }

  async startPumpCalibration(actuatorId, durationSeconds = null) {
    if (!actuatorId) throw new Error('Actuator ID required');

    try {
      return await this.api.Irrigation.startCalibration(actuatorId, durationSeconds);
    } catch (error) {
      console.error('[SettingsDataService] startPumpCalibration failed:', error);
      throw error;
    }
  }

  async completePumpCalibration(actuatorId, measuredMl) {
    if (!actuatorId) throw new Error('Actuator ID required');

    try {
      return await this.api.Irrigation.completeCalibration(actuatorId, measuredMl);
    } catch (error) {
      console.error('[SettingsDataService] completePumpCalibration failed:', error);
      throw error;
    }
  }

  async loadUnitPumps() {
    if (!this.selectedUnitId) return [];

    try {
      // Get actuators for the unit and filter to pumps
      const response = await this.api.Device.getActuators(this.selectedUnitId);
      const actuators = response?.actuators || response || [];
      return actuators.filter(a =>
        a.actuator_type === 'pump' ||
        a.actuator_type === 'water_pump' ||
        a.device_type === 'pump'
      );
    } catch (error) {
      console.error('[SettingsDataService] loadUnitPumps failed:', error);
      return [];
    }
  }

  // ============================================================================
  // SECURITY SETTINGS
  // ============================================================================

  /**
   * Get the count of remaining (unused) recovery codes
   */
  async getRecoveryCodeCount() {
    try {
      const response = await this.api.fetch('/api/settings/security/recovery-codes/count');
      return response?.data?.count ?? 0;
    } catch (error) {
      console.error('[SettingsDataService] getRecoveryCodeCount failed:', error);
      return 0;
    }
  }

  /**
   * Generate new recovery codes (requires password confirmation)
   * @param {string} currentPassword - User's current password for verification
   * @returns {Promise<{ok: boolean, codes?: string[], error?: string}>}
   */
  async generateRecoveryCodes(currentPassword) {
    try {
      const response = await this.api.fetch('/api/settings/security/recovery-codes/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ current_password: currentPassword })
      });

      if (response?.ok) {
        return { ok: true, codes: response.data?.codes || [] };
      } else {
        return { ok: false, error: response?.error?.message || 'Failed to generate codes' };
      }
    } catch (error) {
      console.error('[SettingsDataService] generateRecoveryCodes failed:', error);
      return { ok: false, error: error.message || 'Failed to generate recovery codes' };
    }
  }

  // ============================================================================
  // CACHE MANAGEMENT
  // ============================================================================

  invalidateAll() {
    this.cache.clear();
    this.inFlight.clear();
  }

  invalidateEnvironment() {
    this.cache.invalidate(this._key('environment'));
  }

  invalidateSchedules() {
    this.cache.invalidate(this._key('schedules'));
  }

  invalidateIrrigationConfig() {
    this.cache.invalidate(this._key('irrigation_config'));
  }
}

// Export for module usage
if (typeof window !== 'undefined') {
  window.SettingsDataService = SettingsDataService;
}
