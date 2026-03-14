/**
 * VPD Zones Distribution Chart Component
 * ============================================================================
 * A donut chart showing time spent in each VPD zone over a selected period.
 *
 * VPD Zones:
 * - Too Low (< 0.4 kPa): Risk of mold/disease
 * - Seedling (0.4-0.8 kPa): Good for seedlings/clones
 * - Vegetative (0.8-1.2 kPa): Optimal for vegetative growth
 * - Flowering (1.2-1.5 kPa): Optimal for flowering
 * - Too High (> 1.5 kPa): Stress/wilting risk
 *
 * Usage:
 *   const chart = new VPDZonesChart('vpd-zones-container', {
 *     showLegend: true,
 *     showPercentages: true
 *   });
 *   chart.update(vpdHistoryData);
 */
(function() {
  'use strict';

  class VPDZonesChart {
    constructor(containerId, options = {}) {
      this.containerId = containerId;
      this.container = document.getElementById(containerId);

      if (!this.container) {
        console.warn(`[VPDZonesChart] Container element "${containerId}" not found`);
        return;
      }

      this.options = {
        showLegend: options.showLegend !== false,
        showPercentages: options.showPercentages !== false,
        showCenter: options.showCenter !== false,
        animationDuration: options.animationDuration || 800,
        height: options.height || 250,
        ...options
      };

      this.chart = null;
      this.data = null;

      // VPD Zone definitions
      this.zones = {
        too_low: {
          min: 0,
          max: 0.4,
          color: '#3b82f6',
          label: 'Too Low',
          description: 'Risk of mold/disease',
          icon: 'fas fa-tint'
        },
        seedling: {
          min: 0.4,
          max: 0.8,
          color: '#22c55e',
          label: 'Seedling Zone',
          description: 'Good for seedlings/clones',
          icon: 'fas fa-seedling'
        },
        vegetative: {
          min: 0.8,
          max: 1.2,
          color: '#10b981',
          label: 'Vegetative',
          description: 'Optimal for veg growth',
          icon: 'fas fa-leaf'
        },
        flowering: {
          min: 1.2,
          max: 1.5,
          color: '#8b5cf6',
          label: 'Flowering',
          description: 'Optimal for flowering',
          icon: 'fas fa-spa'
        },
        too_high: {
          min: 1.5,
          max: Infinity,
          color: '#f59e0b',
          label: 'Too High',
          description: 'Stress/wilting risk',
          icon: 'fas fa-exclamation-triangle'
        }
      };

      this._initContainer();
    }

    /**
     * Initialize container with canvas
     */
    _initContainer() {
      if (!this.container) return;

      this.container.innerHTML = `
        <div class="vpd-zones-chart">
          <div class="vpd-zones-chart__chart">
            <canvas id="${this.containerId}-canvas"></canvas>
            ${this.options.showCenter ? '<div class="vpd-zones-chart__center"></div>' : ''}
          </div>
          ${this.options.showLegend ? '<div class="vpd-zones-chart__legend"></div>' : ''}
        </div>
      `;

      this.canvas = document.getElementById(`${this.containerId}-canvas`);
      this.centerEl = this.container.querySelector('.vpd-zones-chart__center');
      this.legendEl = this.container.querySelector('.vpd-zones-chart__legend');
    }

    /**
     * Update with VPD history data
     * @param {Array} data - Array of VPD readings with timestamps
     */
    update(data) {
      if (!this.container || !this.canvas) return;

      this.data = data;
      const distribution = this._calculateDistribution(data);
      this._renderChart(distribution);

      if (this.options.showLegend) {
        this._renderLegend(distribution);
      }

      if (this.options.showCenter) {
        this._renderCenter(distribution);
      }
    }

    /**
     * Calculate time distribution across VPD zones
     */
    _calculateDistribution(data) {
      const distribution = {
        too_low: 0,
        seedling: 0,
        vegetative: 0,
        flowering: 0,
        too_high: 0
      };

      if (!Array.isArray(data) || data.length === 0) {
        return distribution;
      }

      // Count readings in each zone
      for (const reading of data) {
        const vpd = reading.vpd || reading.value || reading;
        if (typeof vpd !== 'number' || isNaN(vpd)) continue;

        const zone = this._getZoneForValue(vpd);
        if (zone) {
          distribution[zone]++;
        }
      }

      // Convert to percentages
      const total = Object.values(distribution).reduce((sum, val) => sum + val, 0);

      if (total > 0) {
        for (const zone of Object.keys(distribution)) {
          distribution[zone] = (distribution[zone] / total) * 100;
        }
      }

      return distribution;
    }

    /**
     * Get zone key for a VPD value
     */
    _getZoneForValue(vpd) {
      if (vpd < 0.4) return 'too_low';
      if (vpd < 0.8) return 'seedling';
      if (vpd < 1.2) return 'vegetative';
      if (vpd < 1.5) return 'flowering';
      return 'too_high';
    }

    /**
     * Render the donut chart
     */
    _renderChart(distribution) {
      if (!this.canvas) return;

      const ctx = this.canvas.getContext('2d');

      // Destroy existing chart
      if (this.chart) {
        this.chart.destroy();
      }

      const labels = [];
      const data = [];
      const colors = [];

      // Only include zones with data
      for (const [zone, percent] of Object.entries(distribution)) {
        if (percent > 0) {
          const zoneConfig = this.zones[zone];
          labels.push(zoneConfig.label);
          data.push(percent);
          colors.push(zoneConfig.color);
        }
      }

      // If no data, show empty state
      if (data.length === 0) {
        labels.push('No Data');
        data.push(100);
        colors.push('#e2e8f0');
      }

      this.chart = new Chart(ctx, {
        type: 'doughnut',
        data: {
          labels: labels,
          datasets: [{
            data: data,
            backgroundColor: colors,
            borderWidth: 2,
            borderColor: 'var(--bg-secondary, #ffffff)'
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          cutout: '65%',
          animation: {
            duration: this.options.animationDuration,
            easing: 'easeOutQuart'
          },
          plugins: {
            legend: {
              display: false // We use custom legend
            },
            tooltip: {
              callbacks: {
                label: (context) => {
                  const value = context.raw;
                  return `${context.label}: ${value.toFixed(1)}%`;
                }
              }
            }
          }
        }
      });
    }

    /**
     * Render the custom legend
     */
    _renderLegend(distribution) {
      if (!this.legendEl) return;

      const items = Object.entries(this.zones).map(([zone, config]) => {
        const percent = distribution[zone] || 0;
        const isActive = percent > 0;

        return `
          <div class="vpd-zone-legend-item ${isActive ? 'active' : 'inactive'}">
            <span class="vpd-zone-legend-color" style="background: ${config.color}"></span>
            <span class="vpd-zone-legend-label">${config.label}</span>
            ${this.options.showPercentages ? `
              <span class="vpd-zone-legend-value">${percent.toFixed(1)}%</span>
            ` : ''}
          </div>
        `;
      }).join('');

      this.legendEl.innerHTML = items;
    }

    /**
     * Render center content (dominant zone)
     */
    _renderCenter(distribution) {
      if (!this.centerEl) return;

      // Find dominant zone
      let dominantZone = null;
      let maxPercent = 0;

      for (const [zone, percent] of Object.entries(distribution)) {
        if (percent > maxPercent) {
          maxPercent = percent;
          dominantZone = zone;
        }
      }

      if (dominantZone && maxPercent > 0) {
        const config = this.zones[dominantZone];
        this.centerEl.innerHTML = `
          <div class="vpd-center-icon" style="color: ${config.color}">
            <i class="${config.icon}"></i>
          </div>
          <div class="vpd-center-label">${config.label}</div>
          <div class="vpd-center-value">${maxPercent.toFixed(0)}%</div>
        `;
      } else {
        this.centerEl.innerHTML = `
          <div class="vpd-center-label">No Data</div>
        `;
      }
    }

    /**
     * Update chart with pre-calculated distribution
     */
    updateDistribution(distribution) {
      if (!this.container || !this.canvas) return;

      this._renderChart(distribution);

      if (this.options.showLegend) {
        this._renderLegend(distribution);
      }

      if (this.options.showCenter) {
        this._renderCenter(distribution);
      }
    }

    /**
     * Get zone statistics
     */
    getStats() {
      if (!this.data) return null;

      const distribution = this._calculateDistribution(this.data);
      const optimalPercent = (distribution.vegetative || 0) + (distribution.flowering || 0);
      const subOptimalPercent = (distribution.seedling || 0);
      const problemPercent = (distribution.too_low || 0) + (distribution.too_high || 0);

      return {
        distribution,
        optimal: optimalPercent,
        subOptimal: subOptimalPercent,
        problem: problemPercent,
        dominantZone: this._getDominantZone(distribution)
      };
    }

    /**
     * Get dominant zone
     */
    _getDominantZone(distribution) {
      let dominant = null;
      let max = 0;

      for (const [zone, percent] of Object.entries(distribution)) {
        if (percent > max) {
          max = percent;
          dominant = zone;
        }
      }

      return dominant ? { zone: dominant, percent: max, ...this.zones[dominant] } : null;
    }

    /**
     * Destroy the component
     */
    destroy() {
      if (this.chart) {
        this.chart.destroy();
        this.chart = null;
      }
    }
  }

  // Export to window
  window.VPDZonesChart = VPDZonesChart;
})();
