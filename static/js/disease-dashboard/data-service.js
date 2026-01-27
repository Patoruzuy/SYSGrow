/**
 * Disease Dashboard Data Service
 * ============================================================================
 * Handles all API calls and data management for disease monitoring.
 * Uses CacheService for efficient data fetching.
 */
(function() {
  'use strict';

  const API = window.API;
  if (!API) {
    throw new Error('API not loaded. Ensure api.js is loaded before data-service.js');
  }

  const CACHE_TTL = 60000; // 1 minute cache for disease data

  class DiseaseDashboardDataService {
    constructor() {
      this.cache = window.CacheService ? new window.CacheService('disease_dashboard', CACHE_TTL) : null;
      this.mlApi = API.ML;

      // Local data stores
      this.riskAssessments = null;
      this.alerts = [];
      this.statistics = null;
    }

    // --------------------------------------------------------------------------
    // Risk Assessments
    // --------------------------------------------------------------------------

    /**
     * Load disease risk assessments
     * @param {Object} options - { force: boolean }
     * @returns {Promise<Object>}
     */
    async loadRiskAssessments(options = {}) {
      const cacheKey = 'risk_assessments';

      if (!options.force && this.cache) {
        const cached = this.cache.get(cacheKey);
        if (cached) {
          this.riskAssessments = cached;
          return cached;
        }
      }

      try {
        const data = await this.mlApi.getDiseaseRisks();
        this.riskAssessments = data;

        if (this.cache) {
          this.cache.set(cacheKey, data);
        }

        return data;
      } catch (error) {
        console.error('[DiseaseDashboardDataService] loadRiskAssessments failed:', error);
        throw error;
      }
    }

    /**
     * Get current risk assessments
     * @returns {Object|null}
     */
    getRiskAssessments() {
      return this.riskAssessments;
    }

    /**
     * Get risk summary stats
     * @returns {Object}
     */
    getRiskSummary() {
      if (!this.riskAssessments || !this.riskAssessments.summary) {
        return {
          total_units: 0,
          high_risk_units: 0,
          critical_risk_units: 0,
          most_common_risk: null
        };
      }
      return this.riskAssessments.summary;
    }

    /**
     * Get units with risks sorted by highest risk score
     * @returns {Array}
     */
    getUnits() {
      if (!this.riskAssessments || !this.riskAssessments.units) {
        return [];
      }
      // Sort by highest risk score descending
      return [...this.riskAssessments.units].sort(
        (a, b) => b.highest_risk_score - a.highest_risk_score
      );
    }

    // --------------------------------------------------------------------------
    // Alerts
    // --------------------------------------------------------------------------

    /**
     * Load disease alerts
     * @param {Object} options - { force: boolean }
     * @returns {Promise<Array>}
     */
    async loadAlerts(options = {}) {
      const cacheKey = 'alerts';

      if (!options.force && this.cache) {
        const cached = this.cache.get(cacheKey);
        if (cached) {
          this.alerts = cached;
          return cached;
        }
      }

      try {
        const data = await this.mlApi.getDiseaseAlerts();
        this.alerts = data.alerts || [];

        if (this.cache) {
          this.cache.set(cacheKey, this.alerts);
        }

        return this.alerts;
      } catch (error) {
        console.error('[DiseaseDashboardDataService] loadAlerts failed:', error);
        throw error;
      }
    }

    /**
     * Get current alerts
     * @returns {Array}
     */
    getAlerts() {
      return this.alerts;
    }

    /**
     * Dismiss an alert (stored locally)
     * @param {string} alertId - Alert ID to dismiss
     */
    dismissAlert(alertId) {
      // Store dismissed alerts in localStorage
      const dismissedKey = 'disease_dismissed_alerts';
      let dismissed = [];

      try {
        dismissed = JSON.parse(localStorage.getItem(dismissedKey) || '[]');
      } catch (e) {
        dismissed = [];
      }

      if (!dismissed.includes(alertId)) {
        dismissed.push(alertId);
        localStorage.setItem(dismissedKey, JSON.stringify(dismissed));
      }

      // Remove from local alerts array
      this.alerts = this.alerts.filter(a => a.alert_id !== alertId);

      // Invalidate cache
      if (this.cache) {
        this.cache.invalidate('alerts');
      }
    }

    /**
     * Check if an alert is dismissed
     * @param {string} alertId - Alert ID to check
     * @returns {boolean}
     */
    isAlertDismissed(alertId) {
      try {
        const dismissed = JSON.parse(localStorage.getItem('disease_dismissed_alerts') || '[]');
        return dismissed.includes(alertId);
      } catch (e) {
        return false;
      }
    }

    // --------------------------------------------------------------------------
    // Statistics
    // --------------------------------------------------------------------------

    /**
     * Load disease statistics
     * @param {number} days - Number of days for statistics (default 90)
     * @param {Object} options - { force: boolean }
     * @returns {Promise<Object>}
     */
    async loadStatistics(days = 90, options = {}) {
      const cacheKey = `statistics_${days}`;

      if (!options.force && this.cache) {
        const cached = this.cache.get(cacheKey);
        if (cached) {
          this.statistics = cached;
          return cached;
        }
      }

      try {
        const data = await this.mlApi.getDiseaseStatistics(days);
        this.statistics = data;

        if (this.cache) {
          this.cache.set(cacheKey, data);
        }

        return data;
      } catch (error) {
        console.error('[DiseaseDashboardDataService] loadStatistics failed:', error);
        throw error;
      }
    }

    /**
     * Get current statistics
     * @returns {Object|null}
     */
    getStatistics() {
      return this.statistics;
    }

    /**
     * Get disease distribution data
     * @returns {Array}
     */
    getDiseaseDistribution() {
      if (!this.statistics || !this.statistics.disease_distribution) {
        return [];
      }
      return this.statistics.disease_distribution;
    }

    /**
     * Get common symptoms
     * @param {number} limit - Maximum number of symptoms to return
     * @returns {Array}
     */
    getCommonSymptoms(limit = 10) {
      if (!this.statistics || !this.statistics.common_symptoms) {
        return [];
      }
      return this.statistics.common_symptoms.slice(0, limit);
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
  window.DiseaseDashboardDataService = DiseaseDashboardDataService;
})();
