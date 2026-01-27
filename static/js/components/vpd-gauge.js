/**
 * VPD Gauge Component
 * ============================================================================
 * A reusable VPD (Vapor Pressure Deficit) gauge using Chart.js doughnut chart.
 *
 * VPD Zones:
 * - < 0.4 kPa: Too Low (risk of mold/disease)
 * - 0.4-0.8 kPa: Seedling/Clone zone
 * - 0.8-1.2 kPa: Vegetative zone (optimal)
 * - 1.2-1.5 kPa: Flowering zone (optimal)
 * - > 1.5 kPa: Too High (stress/wilting)
 *
 * Usage:
 *   const gauge = new VPDGauge('vpd-gauge-canvas', {
 *     showLabels: true,
 *     animationDuration: 800
 *   });
 *   gauge.update({ value: 1.1, status: 'optimal', zone: 'vegetative' });
 */
(function() {
  'use strict';

  class VPDGauge {
    constructor(canvasId, options = {}) {
      this.canvasId = canvasId;
      this.canvas = document.getElementById(canvasId);

      if (!this.canvas) {
        console.warn(`[VPDGauge] Canvas element "${canvasId}" not found`);
        return;
      }

      this.options = {
        showLabels: options.showLabels !== false,
        animationDuration: options.animationDuration || 800,
        maxVPD: options.maxVPD || 2.0,
        valueElementId: options.valueElementId || 'vpd-value',
        zoneElementId: options.zoneElementId || 'vpd-zone',
        ...options
      };

      this.chart = null;
      this.currentValue = null;

      // Zone definitions
      this.zones = {
        too_low: { min: 0, max: 0.4, color: '#3b82f6', label: 'Too Low' },
        seedling: { min: 0.4, max: 0.8, color: '#22c55e', label: 'Seedling Zone' },
        vegetative: { min: 0.8, max: 1.2, color: '#10b981', label: 'Vegetative Zone' },
        flowering: { min: 1.2, max: 1.5, color: '#8b5cf6', label: 'Flowering Zone' },
        too_high: { min: 1.5, max: 2.0, color: '#f59e0b', label: 'Too High' }
      };

      // Status colors
      this.statusColors = {
        optimal: '#22c55e',
        low: '#3b82f6',
        high: '#f59e0b',
        unknown: '#94a3b8',
        error: '#ef4444'
      };
    }

    /**
     * Initialize the gauge chart
     */
    init() {
      if (!this.canvas) return;
      this.render(0, 'unknown');
    }

    /**
     * Update the gauge with new VPD data
     * @param {Object} vpdData - VPD data object
     * @param {number} vpdData.value - VPD value in kPa
     * @param {string} vpdData.status - Status: optimal, low, high, unknown
     * @param {string} vpdData.zone - Zone: seedling, vegetative, flowering, too_low, too_high
     */
    update(vpdData) {
      if (!vpdData) return;

      const value = vpdData.value;
      const status = vpdData.status || this.getStatusFromValue(value);
      const zone = vpdData.zone || this.getZoneFromValue(value);

      // Update value display
      const valueEl = document.getElementById(this.options.valueElementId);
      if (valueEl) {
        valueEl.textContent = value !== null && value !== undefined
          ? `${value.toFixed(2)} kPa`
          : '-- kPa';
      }

      // Update zone display
      const zoneEl = document.getElementById(this.options.zoneElementId);
      if (zoneEl) {
        const zoneInfo = this.zones[zone] || { label: 'Unknown' };
        zoneEl.textContent = zoneInfo.label;
        zoneEl.className = `vpd-zone ${status}`;
      }

      // Update gauge chart
      if (value !== null && value !== undefined) {
        this.render(value, status);
      }

      this.currentValue = value;
    }

    /**
     * Render or update the gauge chart
     */
    render(value, status) {
      if (!this.canvas) return;

      const ctx = this.canvas.getContext('2d');
      const normalizedValue = Math.min(value / this.options.maxVPD, 1);
      const remaining = 1 - normalizedValue;
      const color = this.statusColors[status] || this.statusColors.unknown;

      // Destroy existing chart
      if (this.chart) {
        this.chart.destroy();
      }

      this.chart = new Chart(ctx, {
        type: 'doughnut',
        data: {
          datasets: [{
            data: [normalizedValue, remaining],
            backgroundColor: [color, 'rgba(226, 232, 240, 0.5)'],
            borderWidth: 0,
            circumference: 180,
            rotation: 270
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          cutout: '70%',
          animation: {
            duration: this.options.animationDuration,
            easing: 'easeOutQuart'
          },
          plugins: {
            legend: { display: false },
            tooltip: { enabled: false }
          }
        }
      });
    }

    /**
     * Get status from VPD value
     */
    getStatusFromValue(value) {
      if (value === null || value === undefined) return 'unknown';
      if (value < 0.4) return 'low';
      if (value > 1.5) return 'high';
      return 'optimal';
    }

    /**
     * Get zone from VPD value
     */
    getZoneFromValue(value) {
      if (value === null || value === undefined) return 'unknown';
      if (value < 0.4) return 'too_low';
      if (value < 0.8) return 'seedling';
      if (value < 1.2) return 'vegetative';
      if (value < 1.5) return 'flowering';
      return 'too_high';
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
  window.VPDGauge = VPDGauge;
})();
