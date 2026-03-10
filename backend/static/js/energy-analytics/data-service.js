/**
 * Energy Analytics Data Service
 * ============================================================================
 * Handles all API calls and data management for energy analytics.
 * Uses CacheService for efficient data fetching.
 */
(function() {
  'use strict';

  const API = window.API;
  if (!API) {
    throw new Error('API not loaded. Ensure api.js is loaded before data-service.js');
  }

  const CACHE_TTL = 60000; // 1 minute cache for energy data

  class EnergyAnalyticsDataService {
    constructor() {
      this.cache = window.CacheService ? new window.CacheService('energy_analytics', CACHE_TTL) : null;
      this.insightsApi = API.Insights;
      this.deviceApi = API.Device;

      // Local data stores
      this.energyStats = {};
      this.devices = [];
      this.predictions = [];

      // Settings (loaded from localStorage via CacheService)
      this.energyRate = 0.12; // Default rate per kWh
      this.currency = 'USD';
    }

    // --------------------------------------------------------------------------
    // Energy Statistics
    // --------------------------------------------------------------------------

    /**
     * Load energy statistics
     * @param {Object} options - { force: boolean }
     * @returns {Promise<Object>}
     */
    async loadEnergyStats(options = {}) {
      const cacheKey = 'energy_stats';

      if (!options.force && this.cache) {
        const cached = this.cache.get(cacheKey);
        if (cached) {
          this.energyStats = cached;
          return cached;
        }
      }

      try {
        const data = await this.insightsApi.getEnergyStats();
        this.energyStats = data || {};

        if (this.cache) {
          this.cache.set(cacheKey, this.energyStats);
        }

        return this.energyStats;
      } catch (error) {
        console.error('[EnergyAnalyticsDataService] loadEnergyStats failed:', error);
        throw error;
      }
    }

    /**
     * Get current energy stats
     * @returns {Object}
     */
    getEnergyStats() {
      return this.energyStats;
    }

    // --------------------------------------------------------------------------
    // Device Energy Breakdown
    // --------------------------------------------------------------------------

    /**
     * Load device energy breakdown
     * @param {Object} options - { force: boolean }
     * @returns {Promise<Array>}
     */
    async loadDeviceBreakdown(options = {}) {
      const cacheKey = 'device_breakdown';

      if (!options.force && this.cache) {
        const cached = this.cache.get(cacheKey);
        if (cached) {
          this.devices = cached;
          return cached;
        }
      }

      try {
        const data = await this.deviceApi.getDeviceEnergyBreakdown();
        this.devices = data?.devices || [];

        if (this.cache) {
          this.cache.set(cacheKey, this.devices);
        }

        return this.devices;
      } catch (error) {
        console.error('[EnergyAnalyticsDataService] loadDeviceBreakdown failed:', error);
        throw error;
      }
    }

    /**
     * Get devices list
     * @returns {Array}
     */
    getDevices() {
      return this.devices;
    }

    /**
     * Update device in local store (for real-time updates)
     * @param {Object} data - Device update data
     */
    updateDevice(data) {
      const deviceIndex = this.devices.findIndex(d => d.device_id === data.device_id);

      if (deviceIndex !== -1) {
        this.devices[deviceIndex] = { ...this.devices[deviceIndex], ...data };

        // Invalidate cache
        if (this.cache) {
          this.cache.invalidate('device_breakdown');
        }
      }
    }

    // --------------------------------------------------------------------------
    // Predictions
    // --------------------------------------------------------------------------

    /**
     * Load energy predictions
     * @param {Object} options - { force: boolean }
     * @returns {Promise<Array>}
     */
    async loadPredictions(options = {}) {
      const cacheKey = 'predictions';

      if (!options.force && this.cache) {
        const cached = this.cache.get(cacheKey);
        if (cached) {
          this.predictions = cached;
          return cached;
        }
      }

      try {
        const data = await this.insightsApi.getEnergyPredictions();
        this.predictions = data?.predictions || [];

        if (this.cache) {
          this.cache.set(cacheKey, this.predictions);
        }

        return this.predictions;
      } catch (error) {
        console.error('[EnergyAnalyticsDataService] loadPredictions failed:', error);
        throw error;
      }
    }

    /**
     * Get predictions list
     * @returns {Array}
     */
    getPredictions() {
      return this.predictions;
    }

    /**
     * Get critical prediction count
     * @returns {number}
     */
    getCriticalPredictionCount() {
      return this.predictions.filter(p =>
        p.severity?.toLowerCase() === 'critical' || p.severity?.toLowerCase() === 'high'
      ).length;
    }

    // --------------------------------------------------------------------------
    // Chart Data
    // --------------------------------------------------------------------------

    /**
     * Load energy trend data for chart
     * @param {string} timerange - 'day', 'week', 'month', 'year'
     * @param {string} grouping - 'hour', 'day', 'week', 'month'
     * @returns {Promise<Object>}
     */
    async loadEnergyTrend(timerange = 'month', grouping = 'day') {
      const cacheKey = `trend_${timerange}_${grouping}`;

      if (this.cache) {
        const cached = this.cache.get(cacheKey);
        if (cached) {
          return cached;
        }
      }

      try {
        const data = await this.insightsApi.getEnergyTrend(timerange, grouping);

        if (this.cache) {
          this.cache.set(cacheKey, data);
        }

        return data;
      } catch (error) {
        console.error('[EnergyAnalyticsDataService] loadEnergyTrend failed:', error);
        throw error;
      }
    }

    // --------------------------------------------------------------------------
    // Settings Management
    // --------------------------------------------------------------------------

    /**
     * Load energy settings from cache/localStorage
     */
    loadSettings() {
      if (this.cache) {
        const savedRate = this.cache.get('energy_rate');
        const savedCurrency = this.cache.get('energy_currency');

        if (savedRate !== null) {
          this.energyRate = parseFloat(savedRate);
        }
        if (savedCurrency !== null) {
          this.currency = savedCurrency;
        }
      } else {
        // Fallback to localStorage
        const savedRate = localStorage.getItem('energy_rate');
        const savedCurrency = localStorage.getItem('energy_currency');

        if (savedRate) {
          this.energyRate = parseFloat(savedRate);
        }
        if (savedCurrency) {
          this.currency = savedCurrency;
        }
      }

      return {
        energyRate: this.energyRate,
        currency: this.currency
      };
    }

    /**
     * Save energy settings
     * @param {number} rate - Energy rate per kWh
     * @param {string} currency - Currency code
     */
    saveSettings(rate, currency) {
      this.energyRate = rate;
      this.currency = currency;

      if (this.cache) {
        // Use longer TTL for settings (1 year)
        this.cache.set('energy_rate', rate.toString(), 365 * 24 * 60 * 60 * 1000);
        this.cache.set('energy_currency', currency, 365 * 24 * 60 * 60 * 1000);
      } else {
        localStorage.setItem('energy_rate', rate.toString());
        localStorage.setItem('energy_currency', currency);
      }
    }

    /**
     * Get current settings
     * @returns {Object}
     */
    getSettings() {
      return {
        energyRate: this.energyRate,
        currency: this.currency
      };
    }

    // --------------------------------------------------------------------------
    // Real-time Updates
    // --------------------------------------------------------------------------

    /**
     * Update energy stats from real-time data
     * @param {Object} data - Update data
     */
    updateEnergyStats(data) {
      if (data.stats) {
        this.energyStats = { ...this.energyStats, ...data.stats };

        // Invalidate cache
        if (this.cache) {
          this.cache.invalidate('energy_stats');
        }
      }
    }

    // --------------------------------------------------------------------------
    // Cache Management
    // --------------------------------------------------------------------------

    /**
     * Clear all caches
     */
    clearCache() {
      if (this.cache) {
        this.cache.clear();
      }
    }

    /**
     * Invalidate specific cache key
     * @param {string} key - Cache key to invalidate
     */
    invalidateCache(key) {
      if (this.cache) {
        this.cache.invalidate(key);
      }
    }
  }

  // Export to window
  window.EnergyAnalyticsDataService = EnergyAnalyticsDataService;
})();
