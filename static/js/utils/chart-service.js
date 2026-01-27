/**
 * Chart Service Utility
 * ============================================================================
 * Provides standardized Chart.js configuration, theme-aware colors,
 * and safe chart lifecycle management.
 */
(function() {
  'use strict';

  /**
   * Theme-aware color palette matching theme.css CSS variables
   */
  const CHART_COLORS = {
    // Primary brand colors
    primary: {
      solid: 'rgb(99, 102, 241)',      // --brand-primary
      fill: 'rgba(99, 102, 241, 0.1)',
      border: 'rgba(99, 102, 241, 0.8)'
    },
    secondary: {
      solid: 'rgb(100, 116, 139)',     // --brand-secondary
      fill: 'rgba(100, 116, 139, 0.1)',
      border: 'rgba(100, 116, 139, 0.8)'
    },

    // Status colors
    success: {
      solid: 'rgb(16, 185, 129)',      // --status-success
      fill: 'rgba(16, 185, 129, 0.1)',
      border: 'rgba(16, 185, 129, 0.8)'
    },
    warning: {
      solid: 'rgb(245, 158, 11)',      // --status-warning
      fill: 'rgba(245, 158, 11, 0.1)',
      border: 'rgba(245, 158, 11, 0.8)'
    },
    danger: {
      solid: 'rgb(239, 68, 68)',       // --status-danger
      fill: 'rgba(239, 68, 68, 0.1)',
      border: 'rgba(239, 68, 68, 0.8)'
    },
    info: {
      solid: 'rgb(59, 130, 246)',      // --status-info
      fill: 'rgba(59, 130, 246, 0.1)',
      border: 'rgba(59, 130, 246, 0.8)'
    },

    // Sensor-specific colors
    temperature: {
      solid: 'rgb(255, 107, 107)',     // Red-ish
      fill: 'rgba(255, 107, 107, 0.1)',
      border: 'rgba(255, 107, 107, 0.8)'
    },
    humidity: {
      solid: 'rgb(77, 171, 247)',      // Blue
      fill: 'rgba(77, 171, 247, 0.1)',
      border: 'rgba(77, 171, 247, 0.8)'
    },
    soil_moisture: {
      solid: 'rgb(139, 90, 43)',       // Brown
      fill: 'rgba(139, 90, 43, 0.1)',
      border: 'rgba(139, 90, 43, 0.8)'
    },
    lux: {
      solid: 'rgb(255, 193, 7)',       // Yellow
      fill: 'rgba(255, 193, 7, 0.1)',
      border: 'rgba(255, 193, 7, 0.8)'
    },
    co2: {
      solid: 'rgb(76, 175, 80)',       // Green
      fill: 'rgba(76, 175, 80, 0.1)',
      border: 'rgba(76, 175, 80, 0.8)'
    },
    voc: {
      solid: 'rgb(156, 39, 176)',      // Purple
      fill: 'rgba(156, 39, 176, 0.1)',
      border: 'rgba(156, 39, 176, 0.8)'
    },
    pressure: {
      solid: 'rgb(121, 85, 72)',       // Brown
      fill: 'rgba(121, 85, 72, 0.1)',
      border: 'rgba(121, 85, 72, 0.8)'
    },
    ph: {
      solid: 'rgb(0, 150, 136)',       // Teal
      fill: 'rgba(0, 150, 136, 0.1)',
      border: 'rgba(0, 150, 136, 0.8)'
    },
    ec: {
      solid: 'rgb(233, 30, 99)',       // Pink
      fill: 'rgba(233, 30, 99, 0.1)',
      border: 'rgba(233, 30, 99, 0.8)'
    },
    air_quality: {
      solid: 'rgb(103, 58, 183)',      // Deep Purple
      fill: 'rgba(103, 58, 183, 0.1)',
      border: 'rgba(103, 58, 183, 0.8)'
    },

    // Legacy Aliases
    get soilMoisture() { return this.soil_moisture; },
    get light() { return this.lux; },

    // VPD zone colors
    vpdOptimal: {
      solid: 'rgb(40, 167, 69)',
      fill: 'rgba(40, 167, 69, 0.1)',
      border: 'rgba(40, 167, 69, 0.5)'
    },
    vpdVegetative: {
      solid: 'rgb(139, 195, 74)',
      fill: 'rgba(139, 195, 74, 0.1)',
      border: 'rgba(139, 195, 74, 0.5)'
    },
    vpdWarning: {
      solid: 'rgb(255, 193, 7)',
      fill: 'rgba(255, 193, 7, 0.1)',
      border: 'rgba(255, 193, 7, 0.5)'
    },
    vpdDanger: {
      solid: 'rgb(220, 53, 69)',
      fill: 'rgba(220, 53, 69, 0.1)',
      border: 'rgba(220, 53, 69, 0.5)'
    },

    // Chart-specific palettes
    barPalette: [
      'rgba(99, 102, 241, 0.7)',   // Primary
      'rgba(16, 185, 129, 0.7)',   // Success
      'rgba(245, 158, 11, 0.7)',   // Warning
      'rgba(239, 68, 68, 0.7)',    // Danger
      'rgba(59, 130, 246, 0.7)',   // Info
      'rgba(100, 116, 139, 0.7)'   // Secondary
    ],
    linePalette: [
      'rgb(99, 102, 241)',
      'rgb(16, 185, 129)',
      'rgb(245, 158, 11)',
      'rgb(239, 68, 68)',
      'rgb(59, 130, 246)',
      'rgb(100, 116, 139)'
    ]
  };

  /**
   * Default chart options
   */
  const DEFAULT_OPTIONS = {
    responsive: true,
    maintainAspectRatio: true,
    interaction: {
      mode: 'index',
      intersect: false
    },
    plugins: {
      legend: {
        position: 'top',
        labels: {
          usePointStyle: true,
          padding: 15
        }
      },
      tooltip: {
        backgroundColor: 'rgba(0, 0, 0, 0.8)',
        titleColor: '#fff',
        bodyColor: '#fff',
        borderColor: 'rgba(255, 255, 255, 0.1)',
        borderWidth: 1,
        padding: 12,
        displayColors: true,
        callbacks: {}
      }
    }
  };

  /**
   * Common scale configurations
   */
  const SCALE_CONFIGS = {
    linear: {
      type: 'linear',
      beginAtZero: true,
      grid: {
        color: 'rgba(0, 0, 0, 0.1)'
      },
      ticks: {
        color: '#666'
      }
    },
    percentage: {
      type: 'linear',
      min: 0,
      max: 100,
      grid: {
        color: 'rgba(0, 0, 0, 0.1)'
      },
      ticks: {
        callback: (value) => value + '%',
        color: '#666'
      }
    },
    time: {
      type: 'time',
      time: {
        tooltipFormat: 'MMM d, yyyy HH:mm'
      },
      grid: {
        color: 'rgba(0, 0, 0, 0.1)'
      },
      ticks: {
        color: '#666'
      }
    },
    category: {
      type: 'category',
      grid: {
        display: false
      },
      ticks: {
        color: '#666'
      }
    }
  };

  class ChartService {
    constructor() {
      this.charts = new Map();
    }

    /**
     * Get theme-aware colors
     * @returns {Object} Color palette
     */
    getColors() {
      return CHART_COLORS;
    }

    /**
     * Get a color by name
     * @param {string} name - Color name (e.g., 'primary', 'temperature')
     * @param {string} type - Color type ('solid', 'fill', 'border')
     * @returns {string} Color value
     */
    getColor(name, type = 'solid') {
      const color = CHART_COLORS[name];
      if (!color) {
        console.warn(`[ChartService] Unknown color: ${name}`);
        return CHART_COLORS.primary[type] || CHART_COLORS.primary.solid;
      }
      return color[type] || color.solid;
    }

    /**
     * Get palette colors for multi-dataset charts
     * @param {number} count - Number of colors needed
     * @param {string} type - 'bar' or 'line'
     * @returns {Array} Array of colors
     */
    getPalette(count, type = 'bar') {
      const palette = type === 'bar' ? CHART_COLORS.barPalette : CHART_COLORS.linePalette;
      const result = [];
      for (let i = 0; i < count; i++) {
        result.push(palette[i % palette.length]);
      }
      return result;
    }

    /**
     * Get a scale configuration
     * @param {string} type - Scale type ('linear', 'percentage', 'time', 'category')
     * @param {Object} overrides - Custom options to merge
     * @returns {Object} Scale configuration
     */
    getScale(type, overrides = {}) {
      const base = SCALE_CONFIGS[type] || SCALE_CONFIGS.linear;
      return this._deepMerge(base, overrides);
    }

    /**
     * Create a new chart with standard configuration
     * @param {string|HTMLElement} canvasOrId - Canvas element or ID
     * @param {string} type - Chart type ('line', 'bar', 'pie', 'doughnut', etc.)
     * @param {Object} data - Chart data
     * @param {Object} options - Custom options
     * @param {string} chartId - Optional ID to track chart for cleanup
     * @returns {Chart} Chart instance
     */
    create(canvasOrId, type, data, options = {}, chartId = null) {
      const canvas = typeof canvasOrId === 'string'
        ? document.getElementById(canvasOrId)
        : canvasOrId;

      if (!canvas) {
        console.error(`[ChartService] Canvas not found: ${canvasOrId}`);
        return null;
      }

      // Destroy existing chart if tracked
      const trackingId = chartId || canvas.id || Date.now().toString();
      this.destroy(trackingId);

      const ctx = canvas.getContext('2d');
      const mergedOptions = this._deepMerge(DEFAULT_OPTIONS, options);

      const chart = new Chart(ctx, {
        type,
        data,
        options: mergedOptions
      });

      // Track chart for cleanup
      this.charts.set(trackingId, chart);

      return chart;
    }

    /**
     * Create a line chart with common defaults
     * @param {string|HTMLElement} canvasOrId - Canvas element or ID
     * @param {Array} labels - X-axis labels
     * @param {Array} datasets - Dataset configurations
     * @param {Object} options - Custom options
     * @param {string} chartId - Optional ID for tracking
     * @returns {Chart} Chart instance
     */
    createLineChart(canvasOrId, labels, datasets, options = {}, chartId = null) {
      const enhancedDatasets = datasets.map((ds, idx) => {
        const colorName = ds.colorName || Object.keys(CHART_COLORS)[idx % Object.keys(CHART_COLORS).length];
        const color = CHART_COLORS[colorName] || CHART_COLORS.primary;

        return {
          tension: 0.3,
          borderWidth: 2,
          pointRadius: 3,
          pointHoverRadius: 5,
          fill: ds.fill !== undefined ? ds.fill : false,
          borderColor: ds.borderColor || color.border,
          backgroundColor: ds.backgroundColor || color.fill,
          ...ds
        };
      });

      const data = { labels, datasets: enhancedDatasets };

      return this.create(canvasOrId, 'line', data, options, chartId);
    }

    /**
     * Create a bar chart with common defaults
     * @param {string|HTMLElement} canvasOrId - Canvas element or ID
     * @param {Array} labels - X-axis labels
     * @param {Array} datasets - Dataset configurations
     * @param {Object} options - Custom options
     * @param {string} chartId - Optional ID for tracking
     * @returns {Chart} Chart instance
     */
    createBarChart(canvasOrId, labels, datasets, options = {}, chartId = null) {
      const enhancedDatasets = datasets.map((ds, idx) => {
        return {
          borderWidth: 1,
          borderRadius: 4,
          backgroundColor: ds.backgroundColor || CHART_COLORS.barPalette[idx % CHART_COLORS.barPalette.length],
          ...ds
        };
      });

      const data = { labels, datasets: enhancedDatasets };

      return this.create(canvasOrId, 'bar', data, options, chartId);
    }

    /**
     * Create a doughnut chart with common defaults
     * @param {string|HTMLElement} canvasOrId - Canvas element or ID
     * @param {Array} labels - Labels
     * @param {Array} values - Data values
     * @param {Object} options - Custom options
     * @param {string} chartId - Optional ID for tracking
     * @returns {Chart} Chart instance
     */
    createDoughnutChart(canvasOrId, labels, values, options = {}, chartId = null) {
      const data = {
        labels,
        datasets: [{
          data: values,
          backgroundColor: this.getPalette(values.length, 'bar'),
          borderWidth: 0,
          hoverOffset: 10
        }]
      };

      const doughnutOptions = this._deepMerge({
        cutout: '60%',
        plugins: {
          legend: {
            position: 'right'
          }
        }
      }, options);

      return this.create(canvasOrId, 'doughnut', data, doughnutOptions, chartId);
    }

    /**
     * Safely destroy a chart
     * @param {string|Chart} chartOrId - Chart instance or tracking ID
     */
    destroy(chartOrId) {
      let chart;

      if (typeof chartOrId === 'string') {
        chart = this.charts.get(chartOrId);
        if (chart) {
          this.charts.delete(chartOrId);
        }
      } else if (chartOrId && typeof chartOrId.destroy === 'function') {
        chart = chartOrId;
        // Find and remove from map
        for (const [id, c] of this.charts.entries()) {
          if (c === chart) {
            this.charts.delete(id);
            break;
          }
        }
      }

      if (chart) {
        try {
          chart.destroy();
        } catch (e) {
          console.warn('[ChartService] Error destroying chart:', e);
        }
      }
    }

    /**
     * Destroy all tracked charts
     */
    destroyAll() {
      for (const [id, chart] of this.charts.entries()) {
        try {
          chart.destroy();
        } catch (e) {
          console.warn(`[ChartService] Error destroying chart ${id}:`, e);
        }
      }
      this.charts.clear();
    }

    /**
     * Update chart data
     * @param {string|Chart} chartOrId - Chart instance or tracking ID
     * @param {Object} data - New data
     * @param {boolean} animate - Whether to animate the update
     */
    update(chartOrId, data, animate = true) {
      const chart = typeof chartOrId === 'string'
        ? this.charts.get(chartOrId)
        : chartOrId;

      if (!chart) {
        console.warn('[ChartService] Chart not found for update');
        return;
      }

      if (data.labels) {
        chart.data.labels = data.labels;
      }

      if (data.datasets) {
        data.datasets.forEach((ds, idx) => {
          if (chart.data.datasets[idx]) {
            Object.assign(chart.data.datasets[idx], ds);
          }
        });
      }

      chart.update(animate ? 'default' : 'none');
    }

    /**
     * Get a tracked chart by ID
     * @param {string} chartId - Chart tracking ID
     * @returns {Chart|null} Chart instance or null
     */
    get(chartId) {
      return this.charts.get(chartId) || null;
    }

    /**
     * Deep merge utility
     * @private
     */
    _deepMerge(target, source) {
      const result = { ...target };

      for (const key in source) {
        if (source[key] && typeof source[key] === 'object' && !Array.isArray(source[key])) {
          result[key] = this._deepMerge(result[key] || {}, source[key]);
        } else {
          result[key] = source[key];
        }
      }

      return result;
    }
  }

  // Create singleton instance
  const chartService = new ChartService();

  // Export to window
  window.ChartService = chartService;
  window.ChartServiceClass = ChartService;

  // Also export colors for direct access
  window.CHART_COLORS = CHART_COLORS;
})();
