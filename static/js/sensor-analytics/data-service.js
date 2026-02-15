/**
 * SensorAnalyticsDataService
 * ============================================================================
 * Centralized data fetching for sensor analytics with:
 *  - TTL caching (CacheService)
 *  - in-flight de-duplication
 *  - unit-aware cache keys
 *  - consistent error handling
 */
(function () {
  'use strict';

  class SensorAnalyticsDataService {
    constructor() {
      this.cache = new CacheService('sensor-analytics', 30 * 1000);

      if (!window.API) {
        throw new Error('API not loaded. Ensure api.js is loaded before sensor-analytics data-service.js');
      }

      this.api = window.API;
      this.selectedUnitId = null;

      // In-flight request registry
      this.inFlight = new Map();
    }

    /**
     * Unit-aware cache key builder
     */
    _key(base) {
      const unitPart = this.selectedUnitId ? `unit_${this.selectedUnitId}` : 'all';
      return `${base}__${unitPart}`;
    }

    /**
     * Initialize with selected unit
     */
    init(unitId) {
      const next = unitId && unitId !== '' ? Number(unitId) : null;
      this.selectedUnitId = Number.isFinite(next) ? next : null;

      // Clear legacy non-scoped cache keys
      this.cache.invalidate('units');
      this.cache.invalidate('sensors');
      this.cache.invalidate('plants');
      this.cache.invalidate('timeseries');
      this.cache.invalidate('sensor_history');
      this.cache.invalidate('statistics');
      this.cache.invalidate('anomalies');
    }

    getSelectedUnitId() {
      return this.selectedUnitId;
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

    // --------------------------------------------------------------------------
    // Data Methods
    // --------------------------------------------------------------------------

    /**
     * Load available units
     */
    async loadUnits({ force = false } = {}) {
      const cacheKey = 'units';

      try {
        return await this._cached(
          cacheKey,
          async () => {
            const response = await this.api.Growth.listUnits();
            // API already unwraps data.data, so response is the actual data
            const units = Array.isArray(response) ? response : (response?.units || response?.data || []);
            return units;
          },
          { force }
        );
      } catch (error) {
        console.error('[SensorAnalyticsDataService] loadUnits failed:', error);
        return [];
      }
    }

    /**
     * Load sensors (optionally filtered by unit)
     */
    async loadSensors({ force = false } = {}) {
      const cacheKey = this._key('sensors');

      try {
        return await this._cached(
          cacheKey,
          async () => {
            const response = this.selectedUnitId
              ? await this.api.Device.getSensorsByUnit(this.selectedUnitId)
              : await this.api.Device.getAllSensors();
            // API already unwraps data.data, so response is the actual data
            const sensors = Array.isArray(response) ? response : (response?.sensors || response?.data || []);
            return sensors;
          },
          { force }
        );
      } catch (error) {
        console.error('[SensorAnalyticsDataService] loadSensors failed:', error);
        return [];
      }
    }

    /**
     * Load plants for selected unit
     */
    async loadPlants({ force = false } = {}) {
      if (!this.selectedUnitId) return [];

      const cacheKey = this._key('plants');

      try {
        return await this._cached(
          cacheKey,
          async () => {
            const response = await this.api.Plant.listPlantsInUnit(this.selectedUnitId);
            // API already unwraps data.data, so response is the actual data
            return Array.isArray(response) ? response : (response?.plants || response?.data || []);
          },
          { force }
        );
      } catch (error) {
        console.error('[SensorAnalyticsDataService] loadPlants failed:', error);
        return [];
      }
    }

    /**
     * Load timeseries data
     */
    async loadTimeseries(params = {}, { force = false } = {}) {
      const cacheKey = this._key(`timeseries_${JSON.stringify(params)}`);

      try {
        return await this._cached(
          cacheKey,
          async () => {
            const response = await this.api.Dashboard.getTimeseries(params);
            return response || { series: [], start: null, end: null };
          },
          { force }
        );
      } catch (error) {
        console.error('[SensorAnalyticsDataService] loadTimeseries failed:', error);
        return { series: [], start: null, end: null };
      }
    }

    /**
     * Load sensor history (legacy endpoint)
     */
    async loadSensorHistory({ force = false } = {}) {
      const cacheKey = this._key('sensor_history');

      try {
        return await this._cached(
          cacheKey,
          async () => {
            return await this.api.Analytics.getSensorsHistory(
              this.selectedUnitId ? { unit_id: this.selectedUnitId } : {}
            );
          },
          { force }
        );
      } catch (error) {
        console.error('[SensorAnalyticsDataService] loadSensorHistory failed:', error);
        return null;
      }
    }

    /**
     * Load plant health observations
     */
    async loadPlantHealth(plantId, { force = false } = {}) {
      if (!plantId) return null;

      const cacheKey = this._key(`plant_health_${plantId}`);

      try {
        return await this._cached(
          cacheKey,
          async () => {
            const response = await this.api.Plant.getPlantHealth(plantId);
            return response?.observations || response?.data || [];
          },
          { force }
        );
      } catch (error) {
        console.error('[SensorAnalyticsDataService] loadPlantHealth failed:', error);
        return [];
      }
    }

    /**
     * Load sensor status
     */
    async loadSensorStatus({ force = false } = {}) {
      const cacheKey = this._key('sensor_status');

      try {
        return await this._cached(
          cacheKey,
          async () => {
            const response = await this.api.Status.getStatus();
            // API already unwraps data.data, so response is the actual data
            return response?.sensors || response?.data?.sensors || response || {};
          },
          { force }
        );
      } catch (error) {
        console.error('[SensorAnalyticsDataService] loadSensorStatus failed:', error);
        return {};
      }
    }

    /**
     * Load statistics for sensor data from backend
     * Uses /api/analytics/sensors/statistics endpoint
     */
    async loadStatistics(params = {}, { force = false } = {}) {
      const hours = params.hours || 24;
      const cacheKey = this._key(`statistics_${hours}`);

      try {
        return await this._cached(
          cacheKey,
          async () => {
            const options = { hours };
            if (this.selectedUnitId) options.unit_id = this.selectedUnitId;
            if (params.sensor_id) options.sensor_id = params.sensor_id;

            const response = await this.api.Analytics.getSensorsStatistics(options);

            if (response.ok && response.data) {
              return response.data;
            }
            return response || null;
          },
          { force }
        );
      } catch (error) {
        console.error('[SensorAnalyticsDataService] loadStatistics failed:', error);
        return null;
      }
    }

    /**
     * Load anomalies from backend
     * Fetches anomalies for sensors in the selected unit
     */
    async loadAnomalies({ force = false } = {}) {
      const cacheKey = this._key('anomalies');

      try {
        return await this._cached(
          cacheKey,
          async () => {
            // Get sensors for the unit
            const sensors = await this.loadSensors();
            if (!sensors || sensors.length === 0) {
              return [];
            }

            // Fetch anomalies for each sensor (limit to first 5 for performance)
            const anomalyPromises = sensors.slice(0, 5).map(async sensor => {
              try {
                const sensorId = sensor.sensor_id || sensor.id;
                const response = await this.api.Device.getSensorAnomalies(sensorId);
                const anomalies = response?.anomalies || response?.data?.anomalies || [];
                return anomalies.map(a => ({ ...a, sensor_id: sensorId }));
              } catch (err) {
                console.warn(`[SensorAnalyticsDataService] Could not load anomalies for sensor ${sensor.sensor_id || sensor.id}:`, err);
                return [];
              }
            });

            const results = await Promise.all(anomalyPromises);
            return results.flat().filter(Boolean);
          },
          { force }
        );
      } catch (error) {
        console.error('[SensorAnalyticsDataService] loadAnomalies failed:', error);
        return [];
      }
    }

    // --------------------------------------------------------------------------
    // Cache Management
    // --------------------------------------------------------------------------

    invalidateTimeseriesCache() {
      // Clear all timeseries-related cache entries
      const keys = Array.from(this.cache.cache.keys());
      keys.forEach(key => {
        if (key.includes('timeseries') || key.includes('sensor_history')) {
          this.cache.invalidate(key);
        }
      });
    }

    invalidatePlantsCache() {
      const keys = Array.from(this.cache.cache.keys());
      keys.forEach(key => {
        if (key.includes('plants') || key.includes('plant_health')) {
          this.cache.invalidate(key);
        }
      });
    }

    invalidateAll() {
      this.cache.clear();
    }
  }

  window.SensorAnalyticsDataService = SensorAnalyticsDataService;
})();
