/**
 * Energy Analytics UI Manager
 * ============================================================================
 * Handles all UI rendering, event handling, charts, and real-time updates
 * for energy analytics. Extends BaseManager for automatic cleanup.
 */
(function() {
  'use strict';

  const BaseManager = window.BaseManager;

  class EnergyAnalyticsUIManager extends BaseManager {
    constructor(dataService) {
      super('EnergyAnalyticsUIManager');

      this.dataService = dataService;
      this.socketManager = null;
      this.chart = null;

      // UI elements (will be cached in init)
      this.elements = {};
    }

    // --------------------------------------------------------------------------
    // Initialization
    // --------------------------------------------------------------------------

    /**
     * Initialize the UI manager
     */
    async init() {
      console.log('[EnergyAnalyticsUIManager] Initializing...');

      try {
        // Cache DOM elements
        this._cacheElements();

        // Setup event listeners
        this._setupEventListeners();

        // Load settings and apply to form
        this._loadAndApplySettings();

        // Load initial data
        await this._loadAllData();

        // Setup chart
        this._setupChart();

        // Setup real-time updates
        await this._setupRealtimeUpdates();

        console.log('[EnergyAnalyticsUIManager] Initialized successfully');
      } catch (error) {
        console.error('[EnergyAnalyticsUIManager] Initialization failed:', error);
        this.showNotification('Failed to initialize energy analytics', 'error');
      }
    }

    /**
     * Cache DOM elements
     */
    _cacheElements() {
      this.elements = {
        // Stat elements
        currentPower: document.getElementById('current-power'),
        dailyEnergy: document.getElementById('daily-energy'),
        weeklyEnergy: document.getElementById('weekly-energy'),
        monthlyCost: document.getElementById('monthly-cost'),
        powerTrend: document.getElementById('power-trend'),

        // Tables and containers
        deviceBreakdownTbody: document.getElementById('device-breakdown-tbody'),
        predictionsContainer: document.getElementById('predictions-container'),

        // Buttons
        refreshPredBtn: document.getElementById('refresh-predictions-btn'),
        updateChartBtn: document.getElementById('update-chart-btn'),

        // Form
        energySettingsForm: document.getElementById('energy-settings-form'),
        energyRateInput: document.getElementById('energy-rate'),
        currencySelect: document.getElementById('currency'),

        // Chart controls
        chartTimerange: document.getElementById('chart-timerange'),
        chartGrouping: document.getElementById('chart-grouping'),
        energyChart: document.getElementById('energy-chart'),

        // Badge
        energyAlertsBadge: document.getElementById('energy-alerts-badge')
      };
    }

    /**
     * Setup all event listeners
     */
    _setupEventListeners() {
      // Refresh predictions
      if (this.elements.refreshPredBtn) {
        this.addEventListener(this.elements.refreshPredBtn, 'click', () => this.refreshPredictions());
      }

      // Chart controls
      if (this.elements.updateChartBtn) {
        this.addEventListener(this.elements.updateChartBtn, 'click', () => this.updateChart());
      }

      if (this.elements.chartTimerange) {
        this.addEventListener(this.elements.chartTimerange, 'change', () => this.updateChart());
      }

      if (this.elements.chartGrouping) {
        this.addEventListener(this.elements.chartGrouping, 'change', () => this.updateChart());
      }

      // Energy settings form
      if (this.elements.energySettingsForm) {
        this.addEventListener(this.elements.energySettingsForm, 'submit', (e) => this._handleSettingsSubmit(e));
      }
    }

    /**
     * Load settings and apply to form
     */
    _loadAndApplySettings() {
      const settings = this.dataService.loadSettings();

      if (this.elements.energyRateInput) {
        this.elements.energyRateInput.value = settings.energyRate;
      }

      if (this.elements.currencySelect) {
        this.elements.currencySelect.value = settings.currency;
      }
    }

    // --------------------------------------------------------------------------
    // Data Loading
    // --------------------------------------------------------------------------

    /**
     * Load all data
     */
    async _loadAllData() {
      try {
        this._showPageLoading();

        await Promise.all([
          this._loadEnergyStats(),
          this._loadDeviceBreakdown(),
          this._loadPredictions()
        ]);

        this._updateNavigationBadge();
      } catch (error) {
        console.error('[EnergyAnalyticsUIManager] _loadAllData failed:', error);
        this.showNotification('Failed to load some energy data', 'warning');
      } finally {
        this._hidePageLoading();
      }
    }

    /**
     * Load energy statistics
     */
    async _loadEnergyStats() {
      try {
        await this.dataService.loadEnergyStats();
        this._updateStatsUI();
      } catch (error) {
        console.error('[EnergyAnalyticsUIManager] _loadEnergyStats failed:', error);
        this.showNotification('Failed to load energy statistics', 'error');
      }
    }

    /**
     * Load device breakdown
     */
    async _loadDeviceBreakdown() {
      try {
        await this.dataService.loadDeviceBreakdown();
        this._updateDeviceTable();
      } catch (error) {
        console.error('[EnergyAnalyticsUIManager] _loadDeviceBreakdown failed:', error);
        this.showNotification('Failed to load device energy breakdown', 'error');
      }
    }

    /**
     * Load predictions
     */
    async _loadPredictions() {
      try {
        await this.dataService.loadPredictions();
        this._updatePredictionsUI();
      } catch (error) {
        console.error('[EnergyAnalyticsUIManager] _loadPredictions failed:', error);
        this.showNotification('Failed to load energy predictions', 'error');
      }
    }

    // --------------------------------------------------------------------------
    // Statistics UI
    // --------------------------------------------------------------------------

    /**
     * Update statistics UI
     */
    _updateStatsUI() {
      const stats = this.dataService.getEnergyStats();

      // Current power
      this._setText('current-power', stats.current_power ? `${stats.current_power} W` : '-');

      // Daily energy
      this._setText('daily-energy', stats.daily_energy ? `${stats.daily_energy} kWh` : '-');

      // Weekly energy
      this._setText('weekly-energy', stats.weekly_energy ? `${stats.weekly_energy} kWh` : '-');

      // Monthly cost
      const cost = stats.monthly_cost || (stats.daily_cost ? stats.daily_cost * 30 : 0);
      this._setText('monthly-cost', cost ? `$${cost.toFixed(2)}` : '-');

      // Power trend
      if (this.elements.powerTrend && stats.power_trend !== undefined) {
        const isIncreasing = stats.power_trend > 0;
        const changePercent = Math.abs(stats.power_trend).toFixed(1);

        this.elements.powerTrend.innerHTML = `
          <i class="fas fa-arrow-${isIncreasing ? 'up' : 'down'} trend ${isIncreasing ? 'up' : 'down'}" aria-hidden="true"></i>
          <span>${isIncreasing ? 'Increasing' : 'Decreasing'} ${changePercent}%</span>
        `;
      }
    }

    // --------------------------------------------------------------------------
    // Device Table
    // --------------------------------------------------------------------------

    /**
     * Update device breakdown table
     */
    _updateDeviceTable() {
      const tbody = this.elements.deviceBreakdownTbody;
      if (!tbody) return;

      const devices = this.dataService.getDevices();

      if (devices.length === 0) {
        tbody.innerHTML = `
          <tr>
            <td colspan="6" class="text-center">
              <div class="empty-state">
                <i class="fas fa-microchip fa-3x" aria-hidden="true"></i>
                <h3>No Devices Found</h3>
                <p>Add devices to your units to monitor energy usage.</p>
              </div>
            </td>
          </tr>
        `;
        return;
      }

      tbody.innerHTML = devices.map(device => this._createDeviceRow(device)).join('');
    }

    /**
     * Create a device row
     * @param {Object} device - Device object
     * @returns {string} HTML string
     */
    _createDeviceRow(device) {
      const status = device.status?.toLowerCase() || 'unknown';
      const isOnline = status === 'online';

      return `
        <tr role="row">
          <td data-label="Device">
            <strong>${this._escapeHtml(device.name || 'Unknown Device')}</strong>
          </td>
          <td data-label="Type">
            ${this._escapeHtml(this._formatDeviceType(device.type))}
          </td>
          <td data-label="Status">
            <span class="status-badge badge-${isOnline ? 'success' : 'danger'}" role="status">
              ${this._capitalize(status)}
            </span>
          </td>
          <td data-label="Power (W)">
            ${device.power_wattage !== undefined ? device.power_wattage + ' W' : 'N/A'}
          </td>
          <td data-label="Daily Usage (kWh)">
            ${device.daily_usage_kwh !== undefined ? device.daily_usage_kwh + ' kWh' : 'N/A'}
          </td>
          <td data-label="Monthly Est. Cost">
            ${device.monthly_cost !== undefined ? '$' + device.monthly_cost : 'N/A'}
          </td>
        </tr>
      `;
    }

    // --------------------------------------------------------------------------
    // Predictions UI
    // --------------------------------------------------------------------------

    /**
     * Update predictions UI
     */
    _updatePredictionsUI() {
      const container = this.elements.predictionsContainer;
      if (!container) return;

      const predictions = this.dataService.getPredictions();

      if (predictions.length === 0) {
        container.innerHTML = `
          <div class="empty-state">
            <i class="fas fa-chart-line fa-3x" aria-hidden="true"></i>
            <h3>No Predictions Available</h3>
            <p>AI-powered energy predictions will appear here once enough data is collected.</p>
          </div>
        `;
        return;
      }

      container.innerHTML = predictions.map((pred, index) => this._createPredictionAlert(pred, index)).join('');

      // Bind detail button clicks
      container.querySelectorAll('.prediction-detail-btn').forEach(btn => {
        this.addEventListener(btn, 'click', (e) => {
          const predIndex = parseInt(e.currentTarget.getAttribute('data-prediction-index'), 10);
          this._showPredictionDetail(predictions[predIndex]);
        });
      });
    }

    /**
     * Create prediction alert HTML
     * @param {Object} prediction - Prediction object
     * @param {number} index - Prediction index
     * @returns {string} HTML string
     */
    _createPredictionAlert(prediction, index) {
      const severity = prediction.severity?.toLowerCase() || 'low';
      const severityIcons = {
        critical: 'exclamation-triangle',
        high: 'exclamation-circle',
        medium: 'info-circle',
        low: 'check-circle'
      };

      return `
        <div class="prediction-alert ${severity}">
          <div class="prediction-alert-icon">
            <i class="fas fa-${severityIcons[severity] || 'bolt'}" aria-hidden="true"></i>
          </div>
          <div class="prediction-alert-content">
            <div class="prediction-alert-header">
              <h3 class="prediction-alert-title">${this._escapeHtml(prediction.title || 'Energy Alert')}</h3>
              <span class="risk-level ${severity}">${this._capitalize(severity)}</span>
            </div>
            <p class="prediction-alert-description">${this._escapeHtml(prediction.description || 'No description available')}</p>
            ${prediction.recommendation ? `
              <p class="prediction-alert-recommendation">
                <strong>Recommendation:</strong> ${this._escapeHtml(prediction.recommendation)}
              </p>
            ` : ''}
            <div class="prediction-alert-actions">
              <button type="button" class="prediction-alert-button primary prediction-detail-btn"
                      data-prediction-index="${index}"
                      aria-label="View details for ${this._escapeHtml(prediction.title)}">
                View Details
              </button>
              ${prediction.actionable ? `
                <button type="button" class="prediction-alert-button secondary"
                        aria-label="Take action on ${this._escapeHtml(prediction.title)}">
                  Take Action
                </button>
              ` : ''}
            </div>
          </div>
        </div>
      `;
    }

    /**
     * Show prediction detail
     * @param {Object} prediction - Prediction object
     */
    _showPredictionDetail(prediction) {
      console.log('[EnergyAnalyticsUIManager] Prediction detail:', prediction);
      this.showNotification(`Prediction: ${prediction.title} - ${prediction.description}`, 'info');
    }

    // --------------------------------------------------------------------------
    // Chart
    // --------------------------------------------------------------------------

    /**
     * Setup Chart.js chart
     */
    _setupChart() {
      const ctx = this.elements.energyChart;
      if (!ctx || typeof Chart === 'undefined') return;

      this.chart = new Chart(ctx, {
        type: 'line',
        data: {
          labels: ['Loading...'],
          datasets: [{
            label: 'Energy Consumption (kWh)',
            data: [0],
            borderColor: 'rgb(99, 102, 241)',
            backgroundColor: 'rgba(99, 102, 241, 0.1)',
            tension: 0.4,
            fill: true
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: true,
          plugins: {
            legend: {
              display: true,
              position: 'top'
            },
            title: {
              display: false
            },
            tooltip: {
              mode: 'index',
              intersect: false,
              callbacks: {
                label: function(context) {
                  return context.dataset.label + ': ' + context.parsed.y + ' kWh';
                }
              }
            }
          },
          scales: {
            y: {
              beginAtZero: true,
              title: {
                display: true,
                text: 'Energy (kWh)'
              }
            },
            x: {
              title: {
                display: true,
                text: 'Time Period'
              }
            }
          },
          interaction: {
            mode: 'nearest',
            axis: 'x',
            intersect: false
          }
        }
      });

      // Load initial chart data
      this.updateChart();
    }

    /**
     * Update chart with new data
     */
    async updateChart() {
      if (!this.chart) return;

      const timerange = this.elements.chartTimerange?.value || 'month';
      const grouping = this.elements.chartGrouping?.value || 'day';

      try {
        this._showButtonLoading(this.elements.updateChartBtn);

        const data = await this.dataService.loadEnergyTrend(timerange, grouping);

        this.chart.data.labels = data.labels || [];
        this.chart.data.datasets[0].data = data.values || [];
        this.chart.update();
      } catch (error) {
        console.error('[EnergyAnalyticsUIManager] updateChart failed:', error);
        this.showNotification('Failed to update energy chart', 'error');
      } finally {
        this._hideButtonLoading(this.elements.updateChartBtn);
      }
    }

    /**
     * Append data point to chart (for real-time updates)
     * @param {string} label - Data point label
     * @param {number} value - Data point value
     */
    _appendChartDataPoint(label, value) {
      if (!this.chart) return;

      this.chart.data.labels.push(label);
      this.chart.data.datasets[0].data.push(value);

      // Keep only last 50 data points
      if (this.chart.data.labels.length > 50) {
        this.chart.data.labels.shift();
        this.chart.data.datasets[0].data.shift();
      }

      this.chart.update();
    }

    // --------------------------------------------------------------------------
    // Settings
    // --------------------------------------------------------------------------

    /**
     * Handle energy settings form submission
     * @param {Event} e - Submit event
     */
    _handleSettingsSubmit(e) {
      e.preventDefault();

      const formData = new FormData(this.elements.energySettingsForm);
      const rate = parseFloat(formData.get('energy_rate'));
      const currency = formData.get('currency');

      if (isNaN(rate) || rate < 0) {
        this.showNotification('Please enter a valid energy rate', 'error');
        return;
      }

      this.dataService.saveSettings(rate, currency);
      this.showNotification('Energy settings saved successfully', 'success');

      // Recalculate costs
      this._updateStatsUI();
      this._updateDeviceTable();
    }

    // --------------------------------------------------------------------------
    // Refresh Actions
    // --------------------------------------------------------------------------

    /**
     * Refresh predictions
     */
    async refreshPredictions() {
      try {
        this._showButtonLoading(this.elements.refreshPredBtn);

        await this.dataService.loadPredictions({ force: true });
        this._updatePredictionsUI();
        this._updateNavigationBadge();

        this.showNotification('Predictions refreshed successfully', 'success');
      } catch (error) {
        console.error('[EnergyAnalyticsUIManager] refreshPredictions failed:', error);
        this.showNotification('Failed to refresh predictions', 'error');
      } finally {
        this._hideButtonLoading(this.elements.refreshPredBtn);
      }
    }

    // --------------------------------------------------------------------------
    // Real-time Updates
    // --------------------------------------------------------------------------

    /**
     * Setup Socket.io listeners for real-time updates
     */
    async _setupRealtimeUpdates() {
      try {
        const { default: socketManager } = await import('/static/js/socket.js');
        this.socketManager = socketManager;

        socketManager.on('energy_update', (data) => {
          console.log('[EnergyAnalyticsUIManager] Energy update received:', data);
          this._handleEnergyUpdate(data);
        });

        socketManager.on('device_energy_update', (data) => {
          console.log('[EnergyAnalyticsUIManager] Device energy update received:', data);
          this._handleDeviceEnergyUpdate(data);
        });
      } catch (error) {
        console.warn('[EnergyAnalyticsUIManager] Socket.IO not available for real-time updates', error);
      }
    }

    /**
     * Handle real-time energy update
     * @param {Object} data - Update data
     */
    _handleEnergyUpdate(data) {
      this.dataService.updateEnergyStats(data);
      this._updateStatsUI();

      if (data.chart_update && data.chart_update.label && data.chart_update.value !== undefined) {
        this._appendChartDataPoint(data.chart_update.label, data.chart_update.value);
      }
    }

    /**
     * Handle device energy update
     * @param {Object} data - Device update data
     */
    _handleDeviceEnergyUpdate(data) {
      this.dataService.updateDevice(data);
      this._updateDeviceTable();
    }

    // --------------------------------------------------------------------------
    // Navigation Badge
    // --------------------------------------------------------------------------

    /**
     * Update navigation badge count
     */
    _updateNavigationBadge() {
      const criticalCount = this.dataService.getCriticalPredictionCount();

      if (this.elements.energyAlertsBadge) {
        this.elements.energyAlertsBadge.textContent = criticalCount;
        if (criticalCount > 0) {
          this.elements.energyAlertsBadge.classList.remove('hidden');
        } else {
          this.elements.energyAlertsBadge.classList.add('hidden');
        }
      }
    }

    // --------------------------------------------------------------------------
    // Helpers
    // --------------------------------------------------------------------------

    /**
     * Set text content of element by ID
     * @param {string} id - Element ID
     * @param {string} value - Text value
     */
    _setText(id, value) {
      const el = document.getElementById(id);
      if (el) el.textContent = value !== undefined && value !== null ? value : '-';
    }

    /**
     * Format device type for display
     * @param {string} type - Device type
     * @returns {string} Formatted type
     */
    _formatDeviceType(type) {
      if (!type) return 'Unknown';
      return type.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
    }

    /**
     * Capitalize first letter
     * @param {string} str - String to capitalize
     * @returns {string} Capitalized string
     */
    _capitalize(str) {
      if (!str) return '';
      return str.charAt(0).toUpperCase() + str.slice(1);
    }

    /**
     * Escape HTML to prevent XSS
     * @param {string} text - Text to escape
     * @returns {string} Escaped text
     */
    _escapeHtml(text) {
      if (!text) return '';
      const div = document.createElement('div');
      div.textContent = text;
      return div.innerHTML;
    }

    /**
     * Show page loading indicator
     */
    _showPageLoading() {
      // Could add a page-level loading overlay
    }

    /**
     * Hide page loading indicator
     */
    _hidePageLoading() {
      // Could remove page-level loading overlay
    }

    /**
     * Show button loading state
     * @param {HTMLElement} button - Button element
     */
    _showButtonLoading(button) {
      if (button) {
        button.disabled = true;
        const icon = button.querySelector('i');
        if (icon) {
          icon.classList.add('fa-spin');
        }
      }
    }

    /**
     * Hide button loading state
     * @param {HTMLElement} button - Button element
     */
    _hideButtonLoading(button) {
      if (button) {
        button.disabled = false;
        const icon = button.querySelector('i');
        if (icon) {
          icon.classList.remove('fa-spin');
        }
      }
    }

    /**
     * Show notification message
     * @param {string} message - Message text
     * @param {string} type - Message type (success, error, info, warning)
     */
    showNotification(message, type = 'info') {
      let flashContainer = document.querySelector('.flash-messages');

      if (!flashContainer) {
        flashContainer = document.createElement('div');
        flashContainer.className = 'flash-messages';
        flashContainer.setAttribute('role', 'alert');

        const main = document.querySelector('main');
        if (main) {
          main.insertBefore(flashContainer, main.firstChild);
        }
      }

      const iconMap = {
        success: 'check-circle',
        error: 'exclamation-circle',
        warning: 'exclamation-triangle',
        info: 'info-circle'
      };

      const flash = document.createElement('div');
      flash.className = `flash-message flash-${type}`;
      flash.innerHTML = `
        <i class="fas fa-${iconMap[type] || 'info-circle'}" aria-hidden="true"></i>
        <span>${this._escapeHtml(message)}</span>
      `;

      flashContainer.appendChild(flash);

      // Auto remove after 5 seconds
      setTimeout(() => {
        flash.remove();
        if (flashContainer.children.length === 0) {
          flashContainer.remove();
        }
      }, 5000);
    }

    /**
     * Cleanup when manager is destroyed
     */
    destroy() {
      // Destroy chart
      if (this.chart) {
        this.chart.destroy();
        this.chart = null;
      }

      // Call parent destroy (cleans up event listeners)
      super.destroy();
    }
  }

  // Export to window
  window.EnergyAnalyticsUIManager = EnergyAnalyticsUIManager;
})();
