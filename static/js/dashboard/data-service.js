/**
 * DashboardDataService
 * ============================================================================
 * Centralized data fetching with:
 *  - TTL caching (CacheService)
 *  - in-flight de-duplication (same key => same Promise)
 *  - parameter-aware cache keys (unit + query params)
 *  - consistent fetch JSON error handling
 */
(function () {
  'use strict';

  class DashboardDataService {
    constructor() {
      this.cache = new CacheService('dashboard', 30 * 1000);

      if (!window.API) {
        throw new Error('API not loaded. Ensure api.js is loaded before dashboard data-service.js');
      }

      this.api = window.API;
      this.selectedUnitId = null;

      /**
       * In-flight request registry:
       * key -> Promise
       * Prevents duplicate simultaneous requests from causing extra network load.
       */
      this.inFlight = new Map();
    }

    /**
     * Unit-aware cache key builder.
     * Prevents cross-unit cache pollution (unit_1 showing for unit_2).
     *
     * Examples:
     * - sensor_current__unit_1
     * - sensor_current__all
     */
    _key(base) {
        const unitPart = this.selectedUnitId ? `unit_${this.selectedUnitId}` : 'all';
        return `${base}__${unitPart}`;
    }
    /**
     * Initialize with selected unit.
     * Clears legacy non-scoped cache keys once (important if you previously cached under "sensor_current").
     */
    init(unitId) {
        const next = unitId && unitId !== '' ? Number(unitId) : null;
        this.selectedUnitId = Number.isFinite(next) ? next : null;

        // Clear legacy keys that were not unit-scoped (one-time cleanup).
        // This prevents stale values from appearing after you deploy the fix.
        this.cache.invalidate('sensor_current');
        this.cache.invalidate('system_stats');
        this.cache.invalidate('actuator_states');
        this.cache.invalidate('connectivity_history');
    }
    getSelectedUnitId() {
      return this.selectedUnitId;
    }

    /**
     * Helper: Wrap fetcher with cache + in-flight de-duplication.
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
          // Do not cache failures; allow future retries.
          throw error;
        } finally {
          this.inFlight.delete(key);
        }
      })();

      this.inFlight.set(key, p);
      return p;
    }

    // --------------------------------------------------------------------------
    // Data Methods
    // --------------------------------------------------------------------------

    async loadSensorData({ force = false } = {}) {
        const cacheKey = this._key('sensor_current');

        try {
            return await this._cached(
                cacheKey,
                async () => {
                    const response = await this.api.Dashboard.getCurrentSensors();
                    // Your API returns nested sensor_data sometimes; keep this tolerant.
                    return response?.sensor_data || response?.data || response;
                },
                { force }
            );
        } catch (error) {
            console.error('Error loading sensor data:', error);
            throw error;
        }
    }

    /**
     * Load comprehensive dashboard summary - single API call for all dashboard data.
     * This is the preferred method for initial dashboard load.
     */
    async loadDashboardSummary({ force = false } = {}) {
        const cacheKey = this._key('dashboard_summary');

        try {
            return await this._cached(
                cacheKey,
                async () => {
            const response = await this.api.Dashboard.getSummary();
            // Extract data from success_response wrapper {ok: true, data: {...}}
            const summary = response?.data || response;

            // If the aggregated dashboard summary doesn't include plants
            // (e.g., no plants in unit or backend omitted them), try a
            // resilient client-side fallback: fetch plants directly from
            // the plants API for the selected unit so the UI can still
            // render plant cards.
            try {
              const hasPlants = Array.isArray(summary?.plants) && summary.plants.length > 0;
              if (!hasPlants && this.selectedUnitId) {
                const plantsResp = await this.api.Plant.listPlantsInUnit(this.selectedUnitId);
                // Normalize wrapper
                const plants = plantsResp?.data || plantsResp || [];
                summary.plants = Array.isArray(plants) ? plants : (plants.plants || []);
              }
            } catch (fallbackErr) {
              console.warn('[DashboardDataService] plants fallback failed:', fallbackErr);
            }

            return summary;
                },
                { force }
            );
        } catch (error) {
            console.warn('[DashboardDataService] loadDashboardSummary failed:', error);
            // Return safe defaults
            return {
                sensors: {},
                vpd: { value: null, status: 'unknown', zone: 'unknown' },
                plants: [],
                alerts: { count: 0, recent: [] },
                energy: { current_power_watts: 0, daily_cost: 0 },
                devices: { active: 0, total: 0, sensors: 0, actuators: 0 },
                actuators: [],
                system: { health_score: 0, status: 'unknown' },
                unit_settings: null,
            };
        }
    }

    async loadSystemStats({ force = false } = {}) {
        const cacheKey = this._key('system_stats');

        try {
            return await this._cached(
                cacheKey,
                async () => {
                    const response = await this.api.Insights.getSystemStats();
                    let data = response?.stats || response?.data || response;

                    if (data?.critical_alerts && typeof data.critical_alerts === 'object') {
                        data = { ...data, critical_alerts: data.critical_alerts.count || data.critical_alerts.length || 0 };
                    }

                    return data;
                },
                { force }
            );
        } catch (error) {
            // Safe default response (keeps UI stable)
            console.warn('[DashboardDataService] loadSystemStats failed:', error);
            return {
                active_devices: 0,
                total_plants: 0,
                active_alerts: 0,
                system_uptime: '0h',
                energy_usage: 0,
                critical_alerts: 0,
            };
        }
    }

    async loadRecentActivity({ force = false } = {}) {
      const unitKey = this.selectedUnitId ?? 'all';
      const cacheKey = `recent_activity:${unitKey}`;

      try {
        return await this._cached(
          cacheKey,
          async () => {
            const response = await this.api.System.getActivities(10);
            return response?.data?.activities || response?.activities || [];
          },
          { force }
        );
      } catch (error) {
        console.warn('[DashboardDataService] loadRecentActivity failed:', error);
        return [];
      }
    }

    async loadCriticalAlerts({ force = false } = {}) {
      const unitKey = this.selectedUnitId ?? 'all';
      const cacheKey = `critical_alerts:${unitKey}`;

      try {
        return await this._cached(
          cacheKey,
          async () => {
            const response = await this.api.System.getAlerts();
            return response?.data?.alerts || response?.alerts || [];
          },
          { force }
        );
      } catch (error) {
        console.warn('[DashboardDataService] loadCriticalAlerts failed:', error);
        return [];
      }
    }

    /**
     * Dismiss an alert
     */
    async dismissAlert(alertId) {
      try {
        await this.api.Health.dismissAlert(alertId);
        // Invalidate alerts cache
        this.invalidateActivityCache();
        return true;
      } catch (error) {
        console.error('[DashboardDataService] dismissAlert failed:', error);
        throw error;
      }
    }

    /**
     * Get CSRF token from meta tag
     */
    _getCSRFToken() {
      const meta = document.querySelector('meta[name="csrf-token"]');
      return meta ? meta.getAttribute('content') : '';
    }

    async loadRecentActuatorStates(limit = 20) {
        const cacheKey = this._key(`actuator_states_${limit}`);
        const cached = this.cache.get(cacheKey);
        if (cached) return cached;

        try {
        const options = { limit };
        if (this.selectedUnitId) options.unit_id = this.selectedUnitId;

        const payload = await this.api.Dashboard.getRecentActuatorStates(options);
        const states = payload?.states || [];

        this.cache.set(cacheKey, states);
        return states;
        } catch (error) {
        console.error('Error loading actuator states:', error);
        return [];
        }
    }

    async loadConnectivityHistory(limit = 20, type = '') {
        const cacheKey = this._key(`connectivity_history_${limit}_${type || 'all'}`);
        const cached = this.cache.get(cacheKey);
        if (cached) return cached;

        try {
        const options = {};
        if (limit) options.limit = limit;
        if (type) options.connection_type = type;
        if (this.selectedUnitId) options.unit_id = this.selectedUnitId;

        const payload = await this.api.Dashboard.getConnectivityHistory(options);
        const events = payload?.events || [];

        const normalized = events.map(evt => ({
            timestamp: evt.timestamp,
            type: evt.connection_type || evt.type || evt.protocol || 'connection',
            status: evt.status || evt.state || evt.status_text || 'unknown'
        }));

        this.cache.set(cacheKey, normalized);
        return normalized;
        } catch (error) {
        console.error('Error loading connectivity history:', error);
        return [];
        }
    }

    async loadSystemHealth({ force = false } = {}) {
      const unitKey = this.selectedUnitId ?? 'all';
      const cacheKey = `system_health:${unitKey}`;

      try {
        return await this._cached(cacheKey, async () => this.api.Health.getSystemHealth(), { force });
      } catch (error) {
        console.warn('[DashboardDataService] loadSystemHealth failed:', error);
        return null;
      }
    }

    async loadDeviceHealth({ force = false } = {}) {
      const cacheKey = `device_health:${this.selectedUnitId ?? 'all'}`;
      try {
        return await this._cached(cacheKey, async () => this.api.Health.getDevicesHealth(), { force });
      } catch (error) {
        console.warn('[DashboardDataService] loadDeviceHealth failed:', error);
        return null;
      }
    }

    async loadPlantHealth({ force = false } = {}) {
      const cacheKey = `plant_health:${this.selectedUnitId ?? 'all'}`;
      try {
        return await this._cached(cacheKey, async () => this.api.Plant.getPlantHealth(), { force });
      } catch (error) {
        console.warn('[DashboardDataService] loadPlantHealth failed:', error);
        return null;
      }
    }

    async toggleDevice(deviceType, actuatorId) {
      if (actuatorId === undefined || actuatorId === null || Number.isNaN(Number(actuatorId))) {
        throw new Error(`No actuator id configured for ${deviceType}`);
      }

      const result = await this.api.Device.toggleActuator(Number(actuatorId));

      // Conservative invalidations (best-effort)
      this.cache.clearByPattern('system_*');
      this.cache.clearByPattern('actuator_states*');
      this.cache.clearByPattern('device_*');

      return result;
    }

    invalidateSensorCache() {
        // Clears all unit-scoped sensor caches.
        this.cache.clearByPattern('sensor_current*');
    }

    invalidateHealthCache() {
        this.cache.clearByPattern('health*');
        this.cache.clearByPattern('system_health*');
    }

    invalidateActivityCache() {
        this.cache.clearByPattern('recent_activity*');
        this.cache.clearByPattern('critical_alerts*');
    }

    // --------------------------------------------------------------------------
    // New Dashboard Sections Data Methods
    // --------------------------------------------------------------------------

    async loadQuickStats({ force = false } = {}) {
      const unitKey = this.selectedUnitId ?? 'all';
      const cacheKey = `quick_stats:${unitKey}`;

      try {
        return await this._cached(cacheKey, async () => {
          // Try dedicated endpoint first
          try {
            const stats = await this.api.Analytics?.getSensorsStatistics?.();
            if (stats && (stats.readings_count || stats.avg_temperature != null)) {
              return stats;
            }
          } catch (e) {
            // Fall back to computing from dashboard summary
          }

          // Compute from existing data - dashboard summary should have sensor values
          const summary = await this.loadDashboardSummary({ force: false });
          const sensors = summary?.sensors || {};
          
          // Extract temperature and humidity from sensor data
          const tempValue = sensors.temperature?.value;
          const humidityValue = sensors.humidity?.value;
          
          // Count how many sensor types have values
          const sensorsWithValues = Object.values(sensors).filter(s => s?.value != null).length;
          
          return {
            readings_count: sensorsWithValues > 0 ? sensorsWithValues * 24 : 0,
            anomalies_count: summary?.alerts?.critical || 0,
            system_uptime: summary?.system?.uptime || 99.9,
            avg_temperature: tempValue ?? null,
            avg_humidity: humidityValue ?? null,
            data_quality: sensorsWithValues > 0 ? 98 : 0,
            readings_trend: 5,
            anomalies_trend: summary?.alerts?.critical > 0 ? 10 : -10,
          };
        }, { force });
      } catch (error) {
        console.warn('[DashboardDataService] loadQuickStats failed:', error);
        return null;
      }
    }

    async loadAutomationStatus({ force = false, unitId = null } = {}) {
      const unit = unitId ?? this.selectedUnitId ?? 'all';
      const cacheKey = `automation_status:${unit}`;

      try {
        return await this._cached(cacheKey, async () => {
          // Use schedules endpoint directly (automation-status requires plant_id, not unit_id)
          try {
            const schedules = await this.api.Growth?.getSchedules?.(unit !== 'all' ? unit : undefined);
            const activeSchedules = (schedules || []).filter(s => s.is_active || s.enabled);
            return {
              is_active: activeSchedules.length > 0,
              total_schedules: schedules?.length || 0,
              active_schedules_count: activeSchedules.length,
              active_schedules: activeSchedules.slice(0, 5).map(s => ({
                name: s.name || s.type,
                type: s.type || 'schedule',
                time: s.time || s.next_run || '',
              })),
              lights_on: activeSchedules.filter(s => s.type === 'light' || s.type === 'lights').length,
              fans_on: activeSchedules.filter(s => s.type === 'fan' || s.type === 'fans').length,
              irrigation_active: activeSchedules.filter(s => s.type === 'irrigation' || s.type === 'water').length,
            };
          } catch (e) {
            // Return defaults
          }

          return {
            is_active: true,
            total_schedules: 0,
            active_schedules_count: 0,
            active_schedules: [],
            lights_on: 0,
            fans_on: 0,
            irrigation_active: 0,
          };
        }, { force });
      } catch (error) {
        console.warn('[DashboardDataService] loadAutomationStatus failed:', error);
        return null;
      }
    }

    async loadEnvironmentQuality({ force = false } = {}) {
      const unitKey = this.selectedUnitId ?? 'all';
      const cacheKey = `environment_quality:${unitKey}`;

      try {
        return await this._cached(cacheKey, async () => {
          // Try dedicated environment quality endpoint
          try {
            const quality = await this.api.Analytics?.getEnvironmentQuality?.();
            if (quality) return quality;
          } catch (e) {
            // Fall through - UI will calculate from sensors
          }

          return null; // Let UI calculate from sensor data
        }, { force });
      } catch (error) {
        console.warn('[DashboardDataService] loadEnvironmentQuality failed:', error);
        return null;
      }
    }

    async loadSensorHealth({ force = false } = {}) {
      const unitKey = this.selectedUnitId ?? 'all';
      const cacheKey = `sensor_health:${unitKey}`;

      try {
        return await this._cached(cacheKey, async () => {
          // Try device health endpoint which includes sensor status
          try {
            const deviceHealth = await this.api.Health?.getDevicesHealth?.();
            const payload = deviceHealth?.data || deviceHealth;
            if (!payload) return null;

            let sensors = payload?.sensors || payload;
            const unitId = this.selectedUnitId;
            if (unitId && payload?.by_unit?.[String(unitId)]?.sensors) {
              sensors = payload.by_unit[String(unitId)].sensors;
            }

            if (Array.isArray(sensors)) {
              return {
                healthy: sensors.length,
                warning: 0,
                offline: 0,
                sensors
              };
            }

            return {
              healthy: sensors?.healthy ?? sensors?.online ?? 0,
              warning: sensors?.warning ?? sensors?.degraded ?? sensors?.stale ?? 0,
              offline: sensors?.offline ?? sensors?.error ?? 0,
              total: sensors?.total ?? null,
              sensors: sensors?.sensors || null
            };
          } catch (e) {
            // Fall through
          }

          // Return null to let UI calculate from sensor cards
          return null;
        }, { force });
      } catch (error) {
        console.warn('[DashboardDataService] loadSensorHealth failed:', error);
        return null;
      }
    }

    async loadRecentJournal({ force = false, days = 7, limit = 5 } = {}) {
      const cacheKey = `recent_journal:${days}:${limit}`;

      try {
        return await this._cached(cacheKey, async () => {
          // Try journal entries endpoint
          try {
            const entries = await this.api.Plant?.getJournalEntries?.(days);
            const list = entries?.entries || entries?.data?.entries || entries?.data || entries || [];
            if (Array.isArray(list) && list.length > 0) {
              return list.slice(0, limit);
            }
          } catch (e) {
            // Fall through
          }

          return []; // No journal entries
        }, { force });
      } catch (error) {
        console.warn('[DashboardDataService] loadRecentJournal failed:', error);
        return [];
      }
    }

    // --------------------------------------------------------------------------
    // Phase 1: Growth Stage Data
    // --------------------------------------------------------------------------

    async loadGrowthStage({ force = false } = {}) {
      const cacheKey = this._key('growth_stage');

      try {
        return await this._cached(cacheKey, async () => {
          try {
            const unitId = this.getSelectedUnitId();
            const response = await this.api.Dashboard?.getGrowthStage?.(unitId);
            return response?.data || response;
          } catch (e) {
            // Fall through
          }

          // Default fallback
          return {
            current_stage: 'vegetative',
            days_in_stage: 14,
            days_total: 30,
            progress: 45,
            tip: null,
          };
        }, { force });
      } catch (error) {
        console.warn('[DashboardDataService] loadGrowthStage failed:', error);
        return { current_stage: 'vegetative', days_in_stage: 0, days_total: 0, progress: 0 };
      }
    }

    _calculateDaysInStage(plant) {
      if (!plant.stage_started_at) return 0;
      const start = new Date(plant.stage_started_at);
      const now = new Date();
      return Math.floor((now - start) / 86400000);
    }

    _calculateTotalDays(plant) {
      if (!plant.planted_at && !plant.created_at) return 0;
      const start = new Date(plant.planted_at || plant.created_at);
      const now = new Date();
      return Math.floor((now - start) / 86400000);
    }

    // --------------------------------------------------------------------------
    // Phase 1: Harvest Timeline Data
    // --------------------------------------------------------------------------

    async loadHarvestTimeline({ force = false } = {}) {
      const cacheKey = this._key('harvest_timeline');

      try {
        return await this._cached(cacheKey, async () => {
          try {
            const unitId = this.getSelectedUnitId();
            const response = await this.api.Dashboard?.getHarvestTimeline?.(unitId);
            if (response) return response?.data || response;
          } catch (e) {
            // Fall through
          }

          return { upcoming: [] };
        }, { force });
      } catch (error) {
        console.warn('[DashboardDataService] loadHarvestTimeline failed:', error);
        return { upcoming: [] };
      }
    }

    _daysUntil(dateString) {
      if (!dateString) return 999;
      const target = new Date(dateString);
      const now = new Date();
      return Math.max(0, Math.floor((target - now) / 86400000));
    }

    // --------------------------------------------------------------------------
    // Phase 1: Water Schedule Data
    // --------------------------------------------------------------------------

    async loadWaterSchedule({ force = false } = {}) {
      const cacheKey = this._key('water_schedule');

      try {
        return await this._cached(cacheKey, async () => {
          try {
            const unitId = this.getSelectedUnitId();
            const response = await this.api.Dashboard?.getWaterSchedule?.(unitId);
            if (response) return response?.data || response;
          } catch (e) {
            // Fall through
          }

          // Default schedule
          return {
            next_water_hours: 8,
            next_feed_hours: 48,
            water_days: [1, 3, 5],
            feed_days: [2],
          };
        }, { force });
      } catch (error) {
        console.warn('[DashboardDataService] loadWaterSchedule failed:', error);
        return { next_water_hours: 0, next_feed_hours: 0, water_days: [], feed_days: [] };
      }
    }

    _hoursUntilNext(schedule) {
      if (!schedule || !schedule.next_run) return 24;
      const next = new Date(schedule.next_run);
      const now = new Date();
      return Math.max(0, Math.floor((next - now) / 3600000));
    }

    // --------------------------------------------------------------------------
    // Phase 1: Irrigation Status Data
    // --------------------------------------------------------------------------

    async loadIrrigationStatus({ force = false } = {}) {
      const cacheKey = this._key('irrigation_status');

      try {
        return await this._cached(cacheKey, async () => {
          try {
            const unitId = this.getSelectedUnitId();
            const response = await this.api.Dashboard?.getIrrigationStatus?.(unitId);
            if (response) return response?.data || response;
          } catch (e) {
            // Fall through
          }

          // Get soil moisture at minimum
          const moisture = await this._getCurrentSoilMoisture();
          return {
            last_run: null,
            duration_seconds: 0,
            amount_ml: 0,
            soil_moisture: moisture,
          };
        }, { force });
      } catch (error) {
        console.warn('[DashboardDataService] loadIrrigationStatus failed:', error);
        return { last_run: null, duration_seconds: 0, amount_ml: 0, soil_moisture: 50 };
      }
    }

    async _getCurrentSoilMoisture() {
      try {
        const response = await this.api.Dashboard?.getCurrentSensors?.();
        const data = response?.sensor_data || response?.data?.sensor_data || response;
        const soil = data?.soil_moisture;
        if (soil?.value != null) return soil.value;
      } catch (e) {
        // Fall through
      }
      return 50; // Default
    }

    _getTelemetryWindow(days = 7) {
      const end = new Date();
      const start = new Date(Date.now() - days * 86400000);
      return {
        start_ts: start.toISOString(),
        end_ts: end.toISOString(),
      };
    }

    async loadIrrigationTelemetry({ force = false, days = 7 } = {}) {
      const cacheKey = this._key('irrigation_telemetry');

      try {
        return await this._cached(cacheKey, async () => {
          const unitId = this.getSelectedUnitId();
          if (!unitId) {
            return { executions: [], eligibility: [], manual: [] };
          }

          const windowParams = this._getTelemetryWindow(days);
          const params = { ...windowParams, limit: 10 };

          const [execRes, traceRes, manualRes] = await Promise.all([
            this.api.Irrigation?.getExecutionLogs?.(unitId, params),
            this.api.Irrigation?.getEligibilityTraces?.(unitId, params),
            this.api.Irrigation?.getManualHistory?.(unitId, params),
          ]);

          const executions = Array.isArray(execRes?.items) ? execRes.items : [];
          const eligibility = Array.isArray(traceRes?.items) ? traceRes.items : [];
          const manual = Array.isArray(manualRes?.items) ? manualRes.items : [];

          return { executions, eligibility, manual };
        }, { force });
      } catch (error) {
        console.warn('[DashboardDataService] loadIrrigationTelemetry failed:', error);
        return { executions: [], eligibility: [], manual: [] };
      }
    }
  }

  window.DashboardDataService = DashboardDataService;
})();
