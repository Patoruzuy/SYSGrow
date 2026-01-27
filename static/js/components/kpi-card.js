/**
 * KPI Card Component
 * ============================================================================
 * A reusable KPI (Key Performance Indicator) card for displaying sensor values,
 * status indicators, and trends.
 *
 * Usage:
 *   const card = new KPICard('temperature-card', {
 *     type: 'temperature',
 *     icon: 'fas fa-thermometer-half',
 *     label: 'Temperature',
 *     unit: '°C',
 *     thresholds: { low: 18, high: 28, criticalLow: 10, criticalHigh: 35 }
 *   });
 *   card.update({ value: 24.5, trend: 'up', status: 'optimal' });
 */
(function() {
  'use strict';

  class KPICard {
    constructor(containerId, options = {}) {
      this.containerId = containerId;
      this.container = document.getElementById(containerId);

      if (!this.container) {
        console.warn(`[KPICard] Container element "${containerId}" not found`);
        return;
      }

      this.options = {
        type: options.type || 'generic',
        icon: options.icon || 'fas fa-chart-bar',
        label: options.label || 'Value',
        unit: options.unit || '',
        decimals: options.decimals !== undefined ? options.decimals : 1,
        thresholds: options.thresholds || null,
        showTrend: options.showTrend !== false,
        animateValue: options.animateValue !== false,
        ...options
      };

      this.currentValue = null;
      this.previousValue = null;
      this.currentStatus = 'unknown';

      // Status colors
      this.statusColors = {
        optimal: 'var(--status-success)',
        warning: 'var(--status-warning)',
        critical: 'var(--status-danger)',
        low: 'var(--status-info)',
        high: 'var(--status-warning)',
        unknown: 'var(--text-tertiary)'
      };

      // Trend icons
      this.trendIcons = {
        up: '↑',
        down: '↓',
        stable: '→',
        rising: '↗',
        falling: '↘'
      };
    }

    /**
     * Initialize the card with default state
     */
    init() {
      if (!this.container) return;
      this.render();
    }

    /**
     * Update the card with new data
     * @param {Object} data - Card data
     * @param {number} data.value - The value to display
     * @param {string} data.status - Status: optimal, warning, critical, low, high, unknown
     * @param {string} data.trend - Trend from backend: rising, falling, stable, unknown
     * @param {number} data.trend_delta - Trend delta from backend
     * @param {string} data.statusText - Optional status text override
     */
    update(data) {
      if (!this.container || !data) return;

      this.previousValue = this.currentValue;
      this.currentValue = data.value;

      const status = data.status || this.calculateStatus(data.value);
      // Use backend-provided trend, fallback to 'stable' if not provided
      const trend = this.normalizeBackendTrend(data.trend);
      const statusText = data.statusText || this.getStatusText(status);

      this.currentStatus = status;
      this.render(data.value, status, trend, statusText, data.trend_delta);
    }

    /**
     * Normalize backend trend string to internal format
     * Backend sends: "rising", "falling", "stable", "unknown"
     * Internal uses: "up", "down", "stable", "rising", "falling"
     */
    normalizeBackendTrend(backendTrend) {
      if (!backendTrend || typeof backendTrend !== 'string') return 'stable';
      
      const t = backendTrend.toLowerCase();
      if (t === 'rising') return 'rising';
      if (t === 'falling') return 'falling';
      if (t === 'stable') return 'stable';
      // "unknown" treated as stable (no arrow change)
      return 'stable';
    }

    /**
     * Render the card
     * @param {number|null} value - The value to display
     * @param {string} status - Status class
     * @param {string} trend - Trend direction
     * @param {string} statusText - Status label text
     * @param {number|null} trendDelta - Optional trend delta from backend
     */
    render(value = null, status = 'unknown', trend = 'stable', statusText = '--', trendDelta = null) {
      if (!this.container) return;

      const formattedValue = this.formatValue(value);
      const trendIcon = this.trendIcons[trend] || this.trendIcons.stable;
      const trendClass = this.getTrendClass(trend);
      
      // Build trend label: icon + optional delta
      let trendLabel = trendIcon;
      if (trendDelta !== null && Number.isFinite(trendDelta) && trend !== 'stable') {
        const sign = trendDelta > 0 ? '+' : '';
        const decimals = Math.abs(trendDelta) < 1 ? 2 : 1;
        trendLabel = `${trendIcon} ${sign}${trendDelta.toFixed(decimals)}`;
      }

      this.container.innerHTML = `
        <div class="sensor-card__icon">
          <i class="${this.options.icon}"></i>
        </div>
        <div class="sensor-card__content">
          <div class="sensor-value">${formattedValue}</div>
          <div class="sensor-label">${this.options.label}</div>
          <div class="sensor-status ${status}">${statusText}</div>
        </div>
        ${this.options.showTrend ? `
        <div class="sensor-card__trend">
          <span class="trend-pill ${trendClass}">
            <span class="sensor-trend">${trendLabel}</span>
          </span>
        </div>
        ` : ''}
      `;

      // Update card status class
      this.container.classList.remove('optimal', 'warning', 'critical', 'low', 'high', 'unknown');
      this.container.classList.add(status);
    }

    /**
     * Format the value for display
     */
    formatValue(value) {
      if (value === null || value === undefined) {
        return `--${this.options.unit}`;
      }

      const formatted = typeof value === 'number'
        ? value.toFixed(this.options.decimals)
        : value;

      return `${formatted}${this.options.unit}`;
    }

    /**
     * Calculate status based on thresholds
     */
    calculateStatus(value) {
      if (value === null || value === undefined) return 'unknown';
      if (!this.options.thresholds) return 'optimal';

      const { low, high, criticalLow, criticalHigh } = this.options.thresholds;

      if (criticalLow !== undefined && value < criticalLow) return 'critical';
      if (criticalHigh !== undefined && value > criticalHigh) return 'critical';
      if (low !== undefined && value < low) return 'low';
      if (high !== undefined && value > high) return 'high';

      return 'optimal';
    }

    /**
     * Get status text based on status
     */
    getStatusText(status) {
      const statusTexts = {
        optimal: 'Optimal',
        warning: 'Warning',
        critical: 'Critical',
        low: 'Low',
        high: 'High',
        unknown: '--'
      };
      return statusTexts[status] || '--';
    }

    /**
     * Get trend CSS classes (returns both direction and semantic class)
     * e.g., "rising positive" or "falling negative"
     */
    getTrendClass(trend) {
      const semanticMap = {
        up: 'positive',
        rising: 'positive',
        down: 'negative',
        falling: 'negative',
        stable: 'neutral'
      };
      const semantic = semanticMap[trend] || 'neutral';
      // Return both classes for CSS compatibility
      return `${trend} ${semantic}`;
    }

    /**
     * Set thresholds dynamically
     */
    setThresholds(thresholds) {
      this.options.thresholds = thresholds;
    }

    /**
     * Get current value
     */
    getValue() {
      return this.currentValue;
    }

    /**
     * Get current status
     */
    getStatus() {
      return this.currentStatus;
    }
  }

  /**
   * KPICardGroup - Manages a group of KPI cards
   */
  class KPICardGroup {
    constructor(containerSelector, cardConfigs = []) {
      this.container = document.querySelector(containerSelector);
      this.cards = new Map();
      this.cardConfigs = cardConfigs;
    }

    /**
     * Initialize all cards in the group
     */
    init() {
      if (!this.container) return;

      this.cardConfigs.forEach(config => {
        const cardElement = this.container.querySelector(`[data-sensor="${config.type}"]`);
        if (cardElement) {
          const card = new KPICard(cardElement.id || config.type, config);
          card.container = cardElement; // Use existing element
          card.init();
          this.cards.set(config.type, card);
        }
      });
    }

    /**
     * Update a specific card
     */
    updateCard(type, data) {
      const card = this.cards.get(type);
      if (card) {
        card.update(data);
      }
    }

    /**
     * Update all cards from sensor data
     * @param {Object} sensorData - Object with sensor type keys
     */
    updateAll(sensorData) {
      Object.entries(sensorData).forEach(([type, data]) => {
        this.updateCard(type, data);
      });
    }

    /**
     * Get a specific card instance
     */
    getCard(type) {
      return this.cards.get(type);
    }
  }

  // Default sensor configurations
  KPICard.SENSOR_CONFIGS = {
    temperature: {
      type: 'temperature',
      icon: 'fas fa-thermometer-half',
      label: 'Temperature',
      unit: '°C',
      decimals: 1,
      thresholds: { low: 18, high: 28, criticalLow: 10, criticalHigh: 35 }
    },
    humidity: {
      type: 'humidity',
      icon: 'fas fa-tint',
      label: 'Humidity',
      unit: '%',
      decimals: 0,
      thresholds: { low: 40, high: 70, criticalLow: 20, criticalHigh: 90 }
    },
    soil_moisture: {
      type: 'soil_moisture',
      icon: 'fas fa-water',
      label: 'Soil Moisture',
      unit: '%',
      decimals: 0,
      thresholds: { low: 30, high: 80, criticalLow: 15, criticalHigh: 95 }
    },
    co2_level: {
      type: 'co2_level',
      icon: 'fas fa-cloud',
      label: 'CO2',
      unit: ' ppm',
      decimals: 0,
      thresholds: { low: 400, high: 1200, criticalLow: 300, criticalHigh: 2000 }
    },
    light_level: {
      type: 'light_level',
      icon: 'fas fa-sun',
      label: 'Light',
      unit: ' lux',
      decimals: 0,
      thresholds: { low: 5000, high: 50000, criticalLow: 1000, criticalHigh: 100000 }
    },
    energy_usage: {
      type: 'energy_usage',
      icon: 'fas fa-bolt',
      label: 'Power',
      unit: ' W',
      decimals: 0,
      thresholds: null // No thresholds for power
    }
  };

  // Export to window
  window.KPICard = KPICard;
  window.KPICardGroup = KPICardGroup;
})();
