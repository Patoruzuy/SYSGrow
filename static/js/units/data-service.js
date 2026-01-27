/**
 * UnitsDataService
 * ============================================================================
 * Centralized data fetching for growth units with:
 *  - TTL caching (CacheService)
 *  - In-flight de-duplication
 *  - Consistent error handling
 */
(function () {
  'use strict';

  class UnitsDataService {
    constructor() {
      this.cache = new CacheService('units', 30 * 1000);

      if (!window.API) {
        throw new Error('API not loaded. Ensure api.js is loaded before units/data-service.js');
      }

      this.api = window.API;
      this.inFlight = new Map();
    }

    /**
     * Cache key builder
     */
    _key(base, id = null) {
      return id ? `${base}_${id}` : base;
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
        } finally {
          this.inFlight.delete(key);
        }
      })();

      this.inFlight.set(key, p);
      return p;
    }

    // --------------------------------------------------------------------------
    // Unit Operations
    // --------------------------------------------------------------------------

    /**
     * Load all units
     */
    async loadUnits({ force = false } = {}) {
      const cacheKey = 'units_list';

      try {
        return await this._cached(
          cacheKey,
          async () => {
            const response = await this.api.Growth.listUnits();
            return Array.isArray(response) ? response : (response?.units || response?.data || []);
          },
          { force }
        );
      } catch (error) {
        console.error('[UnitsDataService] loadUnits failed:', error);
        return [];
      }
    }

    /**
     * Load single unit details
     */
    async loadUnit(unitId, { force = false } = {}) {
      if (!unitId) return null;

      const cacheKey = this._key('unit', unitId);

      try {
        return await this._cached(
          cacheKey,
          async () => {
            const response = await this.api.Growth.getUnit(unitId);
            return response?.unit || response?.data || response || null;
          },
          { force }
        );
      } catch (error) {
        console.error(`[UnitsDataService] loadUnit(${unitId}) failed:`, error);
        return null;
      }
    }

    /**
     * Create a new unit
     */
    async createUnit(formData) {
      try {
        const response = await this.api.Growth.createUnit(formData);
        this.invalidateUnitsCache();
        return { ok: true, data: response?.unit || response?.data || response };
      } catch (error) {
        console.error('[UnitsDataService] createUnit failed:', error);
        return { ok: false, error: error.message || 'Failed to create unit' };
      }
    }

    /**
     * Update an existing unit
     */
    async updateUnit(unitId, data) {
      try {
        const response = await this.api.Growth.updateUnit(unitId, data);
        this.invalidateUnitsCache();
        this.cache.invalidate(this._key('unit', unitId));
        return { ok: true, data: response?.unit || response?.data || response };
      } catch (error) {
        console.error(`[UnitsDataService] updateUnit(${unitId}) failed:`, error);
        return { ok: false, error: error.message || 'Failed to update unit' };
      }
    }

    /**
     * Delete a unit
     */
    async deleteUnit(unitId) {
      try {
        await this.api.Growth.deleteUnit(unitId);
        this.invalidateUnitsCache();
        this.cache.invalidate(this._key('unit', unitId));
        return { ok: true };
      } catch (error) {
        console.error(`[UnitsDataService] deleteUnit(${unitId}) failed:`, error);
        return { ok: false, error: error.message || 'Failed to delete unit' };
      }
    }

    // --------------------------------------------------------------------------
    // Schedule Operations
    // --------------------------------------------------------------------------

    /**
     * Load schedules for a unit
     */
    async loadSchedules(unitId, { force = false } = {}) {
      if (!unitId) return [];

      const cacheKey = this._key('schedules', unitId);

      try {
        return await this._cached(
          cacheKey,
          async () => {
            const response = await this.api.Device.getSchedulesForUnit(unitId);
            return response?.schedules || response?.data || response || [];
          },
          { force }
        );
      } catch (error) {
        console.error(`[UnitsDataService] loadSchedules(${unitId}) failed:`, error);
        return [];
      }
    }

    /**
     * Create a schedule
     */
    async createSchedule(payload) {
      try {
        const response = await this.api.Device.createSchedule(payload);
        if (payload.unit_id) {
          this.cache.invalidate(this._key('schedules', payload.unit_id));
        }
        return { ok: true, data: response?.schedule || response?.data || response };
      } catch (error) {
        console.error('[UnitsDataService] createSchedule failed:', error);
        return { ok: false, error: error.message || 'Failed to create schedule' };
      }
    }

    /**
     * Update a schedule
     */
    async updateSchedule(scheduleId, payload) {
      try {
        const response = await this.api.Device.updateSchedule(scheduleId, payload);
        if (payload.unit_id) {
          this.cache.invalidate(this._key('schedules', payload.unit_id));
        }
        return { ok: true, data: response?.schedule || response?.data || response };
      } catch (error) {
        console.error(`[UnitsDataService] updateSchedule(${scheduleId}) failed:`, error);
        return { ok: false, error: error.message || 'Failed to update schedule' };
      }
    }

    /**
     * Delete a schedule
     */
    async deleteSchedule(scheduleId, unitId = null) {
      try {
        await this.api.Device.deleteSchedule(scheduleId);
        if (unitId) {
          this.cache.invalidate(this._key('schedules', unitId));
        }
        return { ok: true };
      } catch (error) {
        console.error(`[UnitsDataService] deleteSchedule(${scheduleId}) failed:`, error);
        return { ok: false, error: error.message || 'Failed to delete schedule' };
      }
    }

    // --------------------------------------------------------------------------
    // V3 Schedule Operations (Enhanced API)
    // --------------------------------------------------------------------------

    /**
     * Load schedules for a unit using v3 API
     */
    async loadSchedulesV3(unitId, { force = false } = {}) {
      if (!unitId) return [];

      const cacheKey = this._key('schedules_v3', unitId);

      try {
        return await this._cached(
          cacheKey,
          async () => {
            const response = await this.api.Growth.getSchedulesV3(unitId);
            return response?.schedules || response?.data || response || [];
          },
          { force }
        );
      } catch (error) {
        console.error(`[UnitsDataService] loadSchedulesV3(${unitId}) failed:`, error);
        return [];
      }
    }

    /**
     * Get schedule summary for a unit
     */
    async getScheduleSummary(unitId, { force = false } = {}) {
      if (!unitId) return null;

      const cacheKey = this._key('schedule_summary', unitId);

      try {
        return await this._cached(
          cacheKey,
          async () => {
            const response = await this.api.Growth.getScheduleSummaryV3(unitId);
            return response?.summary || response?.data || response || null;
          },
          { force }
        );
      } catch (error) {
        console.error(`[UnitsDataService] getScheduleSummary(${unitId}) failed:`, error);
        return null;
      }
    }

    /**
     * Create a schedule using v3 API
     */
    async createScheduleV3(unitId, payload) {
      try {
        const response = await this.api.Growth.createScheduleV3(unitId, payload);
        this.cache.invalidate(this._key('schedules_v3', unitId));
        this.cache.invalidate(this._key('schedule_summary', unitId));
        return { ok: true, data: response?.schedule || response?.data || response };
      } catch (error) {
        console.error('[UnitsDataService] createScheduleV3 failed:', error);
        return { ok: false, error: error.message || 'Failed to create schedule' };
      }
    }

    /**
     * Update a schedule using v3 API
     */
    async updateScheduleV3(unitId, scheduleId, payload) {
      try {
        const response = await this.api.Growth.updateScheduleV3(unitId, scheduleId, payload);
        this.cache.invalidate(this._key('schedules_v3', unitId));
        this.cache.invalidate(this._key('schedule_summary', unitId));
        return { ok: true, data: response?.schedule || response?.data || response };
      } catch (error) {
        console.error(`[UnitsDataService] updateScheduleV3(${scheduleId}) failed:`, error);
        return { ok: false, error: error.message || 'Failed to update schedule' };
      }
    }

    /**
     * Toggle schedule enabled state
     */
    async toggleScheduleV3(unitId, scheduleId, enabled) {
      try {
        const response = await this.api.Growth.toggleScheduleV3(unitId, scheduleId, enabled);
        this.cache.invalidate(this._key('schedules_v3', unitId));
        this.cache.invalidate(this._key('schedule_summary', unitId));
        return { ok: true, data: response };
      } catch (error) {
        console.error(`[UnitsDataService] toggleScheduleV3(${scheduleId}) failed:`, error);
        return { ok: false, error: error.message || 'Failed to toggle schedule' };
      }
    }

    /**
     * Delete a schedule using v3 API
     */
    async deleteScheduleV3(unitId, scheduleId) {
      try {
        await this.api.Growth.deleteScheduleV3(unitId, scheduleId);
        this.cache.invalidate(this._key('schedules_v3', unitId));
        this.cache.invalidate(this._key('schedule_summary', unitId));
        return { ok: true };
      } catch (error) {
        console.error(`[UnitsDataService] deleteScheduleV3(${scheduleId}) failed:`, error);
        return { ok: false, error: error.message || 'Failed to delete schedule' };
      }
    }

    /**
     * Preview schedules for a unit
     */
    async previewSchedules(unitId, { hours = 24, force = false } = {}) {
      if (!unitId) return { events: [] };

      const cacheKey = this._key('schedule_preview', unitId);

      try {
        return await this._cached(
          cacheKey,
          async () => {
            const response = await this.api.Growth.previewSchedulesV3(unitId, hours);
            return response || { events: [] };
          },
          { force }
        );
      } catch (error) {
        console.error(`[UnitsDataService] previewSchedules(${unitId}) failed:`, error);
        return { events: [] };
      }
    }

    /**
     * Detect schedule conflicts for a unit
     */
    async detectConflicts(unitId, { force = false } = {}) {
      if (!unitId) return { has_conflicts: false, conflicts: [] };

      const cacheKey = this._key('schedule_conflicts', unitId);

      try {
        return await this._cached(
          cacheKey,
          async () => {
            const response = await this.api.Growth.detectScheduleConflictsV3(unitId);
            return response || { has_conflicts: false, conflicts: [] };
          },
          { force }
        );
      } catch (error) {
        console.error(`[UnitsDataService] detectConflicts(${unitId}) failed:`, error);
        return { has_conflicts: false, conflicts: [] };
      }
    }

    /**
     * Get schedule history for a unit
     */
    async getScheduleHistory(unitId, { limit = 50, force = false } = {}) {
      if (!unitId) return { history: [] };

      const cacheKey = this._key('schedule_history', unitId);

      try {
        return await this._cached(
          cacheKey,
          async () => {
            const response = await this.api.Growth.getScheduleHistoryV3(unitId, limit);
            return response || { history: [] };
          },
          { force }
        );
      } catch (error) {
        console.error(`[UnitsDataService] getScheduleHistory(${unitId}) failed:`, error);
        return { history: [] };
      }
    }

    /**
     * Get execution log for a schedule
     */
    async getExecutionLog(unitId, scheduleId, { limit = 50, force = false } = {}) {
      if (!unitId || !scheduleId) return { execution_log: [] };

      const cacheKey = this._key('execution_log', `${unitId}_${scheduleId}`);

      try {
        return await this._cached(
          cacheKey,
          async () => {
            const response = await this.api.Growth.getScheduleExecutionLogV3(scheduleId, { limit });
            return response || { execution_log: [] };
          },
          { force }
        );
      } catch (error) {
        console.error(`[UnitsDataService] getExecutionLog(${scheduleId}) failed:`, error);
        return { execution_log: [] };
      }
    }

    /**
     * Auto-generate schedules from plant stage
     */
    async autoGenerateSchedules(unitId, options = {}) {
      try {
        const response = await this.api.Growth.autoGenerateSchedulesV3(unitId, options);
        // Invalidate schedule caches
        this.cache.invalidate(this._key('schedules_v3', unitId));
        this.cache.invalidate(this._key('schedule_summary', unitId));
        this.cache.invalidate(this._key('schedule_preview', unitId));
        return { ok: true, data: response };
      } catch (error) {
        console.error(`[UnitsDataService] autoGenerateSchedules(${unitId}) failed:`, error);
        return { ok: false, error: error.message || 'Failed to auto-generate schedules' };
      }
    }

    /**
     * Get schedule templates based on plant stage
     */
    async getScheduleTemplates(unitId, { force = false } = {}) {
      if (!unitId) return { templates: [] };

      const cacheKey = this._key('schedule_templates', unitId);

      try {
        return await this._cached(
          cacheKey,
          async () => {
            const response = await this.api.Growth.getScheduleTemplatesV3(unitId);
            return response || { templates: [] };
          },
          { force }
        );
      } catch (error) {
        console.error(`[UnitsDataService] getScheduleTemplates(${unitId}) failed:`, error);
        return { templates: [] };
      }
    }

    /**
     * Bulk update schedules (enable/disable/delete multiple)
     */
    async bulkUpdateSchedules(unitId, scheduleIds, action) {
      try {
        const response = await this.api.Growth.bulkUpdateSchedulesV3(unitId, {
          schedule_ids: scheduleIds,
          action: action
        });
        // Invalidate schedule caches
        this.cache.invalidate(this._key('schedules_v3', unitId));
        this.cache.invalidate(this._key('schedule_summary', unitId));
        this.cache.invalidate(this._key('schedule_preview', unitId));
        return { ok: true, data: response };
      } catch (error) {
        console.error(`[UnitsDataService] bulkUpdateSchedules(${unitId}) failed:`, error);
        return { ok: false, error: error.message || 'Failed to bulk update schedules' };
      }
    }

    // --------------------------------------------------------------------------
    // Device Operations
    // --------------------------------------------------------------------------

    /**
     * Load sensors for a unit
     */
    async loadSensors(unitId, { force = false } = {}) {
      if (!unitId) return [];

      const cacheKey = this._key('sensors', unitId);

      try {
        return await this._cached(
          cacheKey,
          async () => {
            const response = await this.api.Device.getSensorsByUnit(unitId);
            return Array.isArray(response) ? response : (response?.sensors || response?.data || []);
          },
          { force }
        );
      } catch (error) {
        console.error(`[UnitsDataService] loadSensors(${unitId}) failed:`, error);
        return [];
      }
    }

    /**
     * Load actuators for a unit
     */
    async loadActuators(unitId, { force = false } = {}) {
      if (!unitId) return [];

      const cacheKey = this._key('actuators', unitId);

      try {
        return await this._cached(
          cacheKey,
          async () => {
            const response = await this.api.Device.getActuatorsByUnit(unitId);
            return Array.isArray(response) ? response : (response?.actuators || response?.data || []);
          },
          { force }
        );
      } catch (error) {
        console.error(`[UnitsDataService] loadActuators(${unitId}) failed:`, error);
        return [];
      }
    }

    /**
     * Load all sensors (unlinked)
     */
    async loadAllSensors({ force = false } = {}) {
      const cacheKey = 'all_sensors';

      try {
        return await this._cached(
          cacheKey,
          async () => {
            const response = await this.api.Device.getAllSensors();
            return Array.isArray(response) ? response : (response?.sensors || response?.data || []);
          },
          { force }
        );
      } catch (error) {
        console.error('[UnitsDataService] loadAllSensors failed:', error);
        return [];
      }
    }

    /**
     * Load all actuators (unlinked)
     */
    async loadAllActuators({ force = false } = {}) {
      const cacheKey = 'all_actuators';

      try {
        return await this._cached(
          cacheKey,
          async () => {
            const response = await this.api.Device.getAllActuators();
            return Array.isArray(response) ? response : (response?.actuators || response?.data || []);
          },
          { force }
        );
      } catch (error) {
        console.error('[UnitsDataService] loadAllActuators failed:', error);
        return [];
      }
    }

    /**
     * Link sensor to unit
     */
    async linkSensor(sensorId, unitId) {
      try {
        await this.api.Device.linkSensorToUnit(sensorId, unitId);
        this.invalidateDevicesCache(unitId);
        return { ok: true };
      } catch (error) {
        console.error(`[UnitsDataService] linkSensor(${sensorId}, ${unitId}) failed:`, error);
        return { ok: false, error: error.message || 'Failed to link sensor' };
      }
    }

    /**
     * Unlink sensor from unit
     */
    async unlinkSensor(sensorId, unitId = null) {
      try {
        await this.api.Device.unlinkSensorFromUnit(sensorId);
        if (unitId) this.invalidateDevicesCache(unitId);
        return { ok: true };
      } catch (error) {
        console.error(`[UnitsDataService] unlinkSensor(${sensorId}) failed:`, error);
        return { ok: false, error: error.message || 'Failed to unlink sensor' };
      }
    }

    /**
     * Link actuator to unit
     */
    async linkActuator(actuatorId, unitId) {
      try {
        await this.api.Device.linkActuatorToUnit(actuatorId, unitId);
        this.invalidateDevicesCache(unitId);
        return { ok: true };
      } catch (error) {
        console.error(`[UnitsDataService] linkActuator(${actuatorId}, ${unitId}) failed:`, error);
        return { ok: false, error: error.message || 'Failed to link actuator' };
      }
    }

    /**
     * Unlink actuator from unit
     */
    async unlinkActuator(actuatorId, unitId = null) {
      try {
        await this.api.Device.unlinkActuatorFromUnit(actuatorId);
        if (unitId) this.invalidateDevicesCache(unitId);
        return { ok: true };
      } catch (error) {
        console.error(`[UnitsDataService] unlinkActuator(${actuatorId}) failed:`, error);
        return { ok: false, error: error.message || 'Failed to unlink actuator' };
      }
    }

    // --------------------------------------------------------------------------
    // Plant Operations
    // --------------------------------------------------------------------------

    /**
     * Load plants for a unit
     */
    async loadPlants(unitId, { force = false } = {}) {
      if (!unitId) return [];

      const cacheKey = this._key('plants', unitId);

      try {
        return await this._cached(
          cacheKey,
          async () => {
            const response = await this.api.Plant.listPlantsInUnit(unitId);
            return Array.isArray(response) ? response : (response?.plants || response?.data || []);
          },
          { force }
        );
      } catch (error) {
        console.error(`[UnitsDataService] loadPlants(${unitId}) failed:`, error);
        return [];
      }
    }

    /**
     * Load plant info
     */
    async loadPlantInfo(plantId, { force = false } = {}) {
      if (!plantId) return null;

      const cacheKey = this._key('plant_info', plantId);

      try {
        return await this._cached(
          cacheKey,
          async () => {
            const response = await this.api.Plant.getPlantInfo(plantId);
            return response?.plant || response?.data || response || null;
          },
          { force }
        );
      } catch (error) {
        console.error(`[UnitsDataService] loadPlantInfo(${plantId}) failed:`, error);
        return null;
      }
    }

    /**
     * Add plant to unit
     */
    async addPlant(payload) {
      try {
        const response = await this.api.Plant.addPlant(payload);
        if (payload.unit_id) {
          this.cache.invalidate(this._key('plants', payload.unit_id));
        }
        return { ok: true, data: response?.plant || response?.data || response };
      } catch (error) {
        console.error('[UnitsDataService] addPlant failed:', error);
        return { ok: false, error: error.message || 'Failed to add plant' };
      }
    }

    /**
     * Remove plant
     */
    async removePlant(plantId, unitId = null) {
      try {
        await this.api.Plant.removePlant(plantId);
        if (unitId) {
          this.cache.invalidate(this._key('plants', unitId));
        }
        return { ok: true };
      } catch (error) {
        console.error(`[UnitsDataService] removePlant(${plantId}) failed:`, error);
        return { ok: false, error: error.message || 'Failed to remove plant' };
      }
    }

    /**
     * Update plant stage
     */
    async updatePlantStage(plantId, stage, unitId = null) {
      try {
        const response = await this.api.Plant.updatePlantStage(plantId, stage);
        if (unitId) {
          this.cache.invalidate(this._key('plants', unitId));
        }
        this.cache.invalidate(this._key('plant_info', plantId));
        return { ok: true, data: response?.plant || response?.data || response };
      } catch (error) {
        console.error(`[UnitsDataService] updatePlantStage(${plantId}, ${stage}) failed:`, error);
        return { ok: false, error: error.message || 'Failed to update plant stage' };
      }
    }

    /**
     * Set active plant for unit
     */
    async setActivePlant(unitId, plantId) {
      try {
        const response = await this.api.Plant.setActivePlant(unitId, plantId);
        this.cache.invalidate(this._key('unit', unitId));
        this.cache.invalidate(this._key('plants', unitId));
        return { ok: true, data: response };
      } catch (error) {
        console.error(`[UnitsDataService] setActivePlant(${unitId}, ${plantId}) failed:`, error);
        return { ok: false, error: error.message || 'Failed to set active plant' };
      }
    }

    // --------------------------------------------------------------------------
    // Thresholds Operations
    // --------------------------------------------------------------------------

    /**
     * Update thresholds for unit
     */
    async updateThresholds(unitId, thresholds) {
      try {
        const response = await this.api.Settings.updateThresholds(unitId, thresholds);
        this.cache.invalidate(this._key('unit', unitId));
        return { ok: true, data: response };
      } catch (error) {
        console.error(`[UnitsDataService] updateThresholds(${unitId}) failed:`, error);
        return { ok: false, error: error.message || 'Failed to update thresholds' };
      }
    }

    // --------------------------------------------------------------------------
    // Analytics & Health Operations
    // --------------------------------------------------------------------------

    /**
     * Load environmental metrics for unit
     */
    async loadEnvironmentalMetrics(unitId, { force = false } = {}) {
      if (!unitId) return null;

      const cacheKey = this._key('env_metrics', unitId);

      try {
        return await this._cached(
          cacheKey,
          async () => {
            const response = await this.api.Analytics.getEnvironmentalMetrics(unitId);
            return response?.metrics || response?.data || response || null;
          },
          { force }
        );
      } catch (error) {
        console.error(`[UnitsDataService] loadEnvironmentalMetrics(${unitId}) failed:`, error);
        return null;
      }
    }

    /**
     * Load health metrics for unit
     */
    async loadHealthMetrics(unitId, { force = false } = {}) {
      if (!unitId) return null;

      const cacheKey = this._key('health_metrics', unitId);

      try {
        return await this._cached(
          cacheKey,
          async () => {
            const response = await this.api.Insights.getUnitHealthMetrics(unitId);
            return response?.metrics || response?.data || response || null;
          },
          { force }
        );
      } catch (error) {
        console.error(`[UnitsDataService] loadHealthMetrics(${unitId}) failed:`, error);
        return null;
      }
    }

    // --------------------------------------------------------------------------
    // Camera Operations
    // --------------------------------------------------------------------------

    /**
     * Start camera for unit
     */
    async startCamera(unitId) {
      try {
        const response = await fetch(`/api/growth/units/${unitId}/camera/start`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' }
        });
        if (!response.ok) {
          return { ok: false, error: `HTTP ${response.status}: ${response.statusText}` };
        }
        const data = await response.json();
        return data.ok !== false ? { ok: true, data } : { ok: false, error: data.error || 'Failed to start camera' };
      } catch (error) {
        console.error(`[UnitsDataService] startCamera(${unitId}) failed:`, error);
        return { ok: false, error: error.message || 'Failed to start camera' };
      }
    }

    /**
     * Stop camera for unit
     */
    async stopCamera(unitId) {
      try {
        const response = await fetch(`/api/growth/units/${unitId}/camera/stop`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' }
        });
        if (!response.ok) {
          return { ok: false, error: `HTTP ${response.status}: ${response.statusText}` };
        }
        const data = await response.json();
        return data.ok !== false ? { ok: true, data } : { ok: false, error: data.error || 'Failed to stop camera' };
      } catch (error) {
        console.error(`[UnitsDataService] stopCamera(${unitId}) failed:`, error);
        return { ok: false, error: error.message || 'Failed to stop camera' };
      }
    }

    /**
     * Get camera status for unit
     */
    async getCameraStatus(unitId) {
      try {
        const response = await fetch(`/api/growth/units/${unitId}/camera/status`);
        if (!response.ok) {
          return { ok: false, error: `HTTP ${response.status}: ${response.statusText}` };
        }
        const data = await response.json();
        return data.ok !== false ? { ok: true, data } : { ok: false, error: data.error || 'Failed to get camera status' };
      } catch (error) {
        console.error(`[UnitsDataService] getCameraStatus(${unitId}) failed:`, error);
        return { ok: false, error: error.message || 'Failed to get camera status' };
      }
    }

    // --------------------------------------------------------------------------
    // Cache Management
    // --------------------------------------------------------------------------

    invalidateUnitsCache() {
      this.cache.invalidate('units_list');
    }

    invalidateDevicesCache(unitId = null) {
      this.cache.invalidate('all_sensors');
      this.cache.invalidate('all_actuators');
      if (unitId) {
        this.cache.invalidate(this._key('sensors', unitId));
        this.cache.invalidate(this._key('actuators', unitId));
      }
    }

    invalidateUnitCache(unitId) {
      this.cache.invalidate(this._key('unit', unitId));
      this.cache.invalidate(this._key('schedules', unitId));
      this.cache.invalidate(this._key('sensors', unitId));
      this.cache.invalidate(this._key('actuators', unitId));
      this.cache.invalidate(this._key('plants', unitId));
      this.cache.invalidate(this._key('env_metrics', unitId));
      this.cache.invalidate(this._key('health_metrics', unitId));
    }

    invalidateAll() {
      this.cache.clear();
    }
  }

  window.UnitsDataService = UnitsDataService;
})();
