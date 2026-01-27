/**
 * Disease Dashboard UI Manager
 * ============================================================================
 * Handles all UI rendering and interactions for disease monitoring.
 * Extends BaseManager for automatic event listener cleanup.
 */
(function() {
  'use strict';

  const BaseManager = window.BaseManager;
  if (!BaseManager) {
    console.warn('[DiseaseDashboardUIManager] BaseManager not loaded, using basic class');
  }

  class DiseaseDashboardUIManager extends (BaseManager || class {}) {
    constructor(dataService) {
      if (BaseManager) {
        super();
      }
      this.dataService = dataService;
      this.diseaseChart = null;
      this.refreshInterval = null;
      this.elements = {};
    }

    /**
     * Initialize the UI manager
     */
    async init() {
      this._cacheElements();
      this._bindEvents();
      await this._loadAllData();

      // Auto-refresh every 5 minutes
      this.refreshInterval = setInterval(() => this._loadAllData(), 5 * 60 * 1000);
    }

    /**
     * Cache DOM elements
     */
    _cacheElements() {
      this.elements = {
        refreshBtn: document.getElementById('refresh-btn'),
        unitsContainer: document.getElementById('units-container'),
        alertsContainer: document.getElementById('alerts-container'),
        symptomsContainer: document.getElementById('symptoms-list'),
        chartCanvas: document.getElementById('disease-distribution-chart'),
        // Summary stats
        totalUnits: document.getElementById('total-units'),
        highRiskCount: document.getElementById('high-risk-count'),
        criticalRiskCount: document.getElementById('critical-risk-count'),
        commonRisk: document.getElementById('common-risk')
      };
    }

    /**
     * Bind event listeners
     */
    _bindEvents() {
      // Refresh button
      if (this.elements.refreshBtn) {
        const handler = () => this._loadAllData();
        this.elements.refreshBtn.addEventListener('click', handler);
        if (this.registerCleanup) {
          this.registerCleanup(() => {
            this.elements.refreshBtn.removeEventListener('click', handler);
          });
        }
      }

      // Event delegation for alert dismissal
      if (this.elements.alertsContainer) {
        const handler = (e) => {
          const dismissBtn = e.target.closest('[data-action="dismiss-alert"]');
          if (dismissBtn) {
            const alertId = dismissBtn.getAttribute('data-alert-id');
            this._dismissAlert(alertId);
          }
        };
        this.elements.alertsContainer.addEventListener('click', handler);
        if (this.registerCleanup) {
          this.registerCleanup(() => {
            this.elements.alertsContainer.removeEventListener('click', handler);
          });
        }
      }
    }

    /**
     * Load all dashboard data
     */
    async _loadAllData() {
      this._showLoading();

      try {
        await Promise.all([
          this._loadRiskAssessments(),
          this._loadAlerts(),
          this._loadStatistics()
        ]);
      } catch (error) {
        console.error('[DiseaseDashboardUIManager] Error loading dashboard:', error);
        this._showNotification('Failed to load dashboard data', 'error');
      } finally {
        this._hideLoading();
      }
    }

    /**
     * Load and render risk assessments
     */
    async _loadRiskAssessments() {
      try {
        await this.dataService.loadRiskAssessments({ force: true });

        // Update summary stats
        const summary = this.dataService.getRiskSummary();
        this._updateSummaryStats(summary);

        // Render unit cards
        const units = this.dataService.getUnits();
        this._renderUnitCards(units);
      } catch (error) {
        console.error('[DiseaseDashboardUIManager] Error loading risk assessments:', error);
      }
    }

    /**
     * Load and render alerts
     */
    async _loadAlerts() {
      try {
        await this.dataService.loadAlerts({ force: true });
        const alerts = this.dataService.getAlerts();
        this._renderAlerts(alerts);
      } catch (error) {
        console.error('[DiseaseDashboardUIManager] Error loading alerts:', error);
      }
    }

    /**
     * Load and render statistics
     */
    async _loadStatistics() {
      try {
        await this.dataService.loadStatistics(90, { force: true });

        // Render disease distribution chart
        const distribution = this.dataService.getDiseaseDistribution();
        this._renderDiseaseChart(distribution);

        // Render common symptoms
        const symptoms = this.dataService.getCommonSymptoms(10);
        this._renderSymptomsList(symptoms);
      } catch (error) {
        console.error('[DiseaseDashboardUIManager] Error loading statistics:', error);
      }
    }

    /**
     * Update summary statistics display
     * @param {Object} summary - Risk summary data
     */
    _updateSummaryStats(summary) {
      if (this.elements.totalUnits) {
        this.elements.totalUnits.textContent = summary.total_units || 0;
      }
      if (this.elements.highRiskCount) {
        this.elements.highRiskCount.textContent = summary.high_risk_units || 0;
      }
      if (this.elements.criticalRiskCount) {
        this.elements.criticalRiskCount.textContent = summary.critical_risk_units || 0;
      }
      if (this.elements.commonRisk) {
        this.elements.commonRisk.textContent = summary.most_common_risk
          ? summary.most_common_risk.replace('_', ' ')
          : 'N/A';
      }
    }

    /**
     * Render unit cards with risk information
     * @param {Array} units - Units with risk data
     */
    _renderUnitCards(units) {
      const container = this.elements.unitsContainer;
      if (!container) return;

      if (!units || units.length === 0) {
        container.innerHTML = '<p class="text-muted">No units with active plants found.</p>';
        return;
      }

      let html = '';

      for (const unit of units) {
        const hasHigh = unit.risks.some(r => r.risk_level === 'high');
        const hasCritical = unit.risks.some(r => r.risk_level === 'critical');
        const cardClass = hasCritical ? 'has-critical' : (hasHigh ? 'has-high' : '');

        html += `
          <div class="unit-card ${cardClass}">
            <div class="row">
              <div class="col-md-8">
                <h5 class="mb-2">
                  ${this._escapeHtml(unit.unit_name)}
                  <span class="badge bg-secondary ms-2">${this._escapeHtml(unit.plant_type)}</span>
                </h5>
                <p class="text-muted mb-3">
                  Plant: ${this._escapeHtml(unit.plant_name)} |
                  Stage: ${this._escapeHtml(unit.growth_stage)} |
                  Age: ${unit.plant_age_days} days
                </p>
              </div>
              <div class="col-md-4 text-end">
                <h6 class="text-muted mb-2">Risk Score</h6>
                <h3 class="mb-0">${unit.highest_risk_score.toFixed(1)}/100</h3>
              </div>
            </div>

            ${unit.risks.length > 0 ? `
              <div class="risks-section">
                <h6 class="mb-2">Detected Risks:</h6>
                ${unit.risks.map(risk => this._renderRiskItem(risk)).join('')}
              </div>
            ` : `
              <div class="alert alert-success mb-0">
                No significant disease risks detected
              </div>
            `}
          </div>
        `;
      }

      container.innerHTML = html;
    }

    /**
     * Render a single risk item
     * @param {Object} risk - Risk data
     * @returns {string} HTML string
     */
    _renderRiskItem(risk) {
      const badgeClass = `risk-${risk.risk_level}`;
      const icon = this._getRiskIcon(risk.disease_type);

      return `
        <div class="risk-item">
          <div class="d-flex justify-content-between align-items-start mb-2">
            <div>
              <h6 class="mb-1">
                ${icon} ${this._formatDiseaseType(risk.disease_type)}
              </h6>
              <span class="risk-badge ${badgeClass}">${risk.risk_level}</span>
              <span class="badge bg-light text-dark ms-2">
                ${(risk.confidence * 100).toFixed(0)}% confidence
              </span>
            </div>
            <div class="text-end">
              <strong>${risk.risk_score.toFixed(1)}</strong>/100
            </div>
          </div>

          ${risk.predicted_onset_days ? `
            <div class="alert alert-warning py-2 mb-2">
              Symptoms may appear in <strong>${risk.predicted_onset_days} days</strong>
            </div>
          ` : ''}

          ${risk.contributing_factors && risk.contributing_factors.length > 0 ? `
            <div class="mb-2">
              <strong>Contributing Factors:</strong>
              <ul class="mb-0 mt-1">
                ${risk.contributing_factors.slice(0, 3).map(factor => `
                  <li>${this._formatFactor(factor)}</li>
                `).join('')}
              </ul>
            </div>
          ` : ''}

          ${risk.recommendations && risk.recommendations.length > 0 ? `
            <div>
              <strong>Recommendations:</strong>
              ${risk.recommendations.slice(0, 3).map(rec => `
                <div class="recommendation">
                  ${this._escapeHtml(rec)}
                </div>
              `).join('')}
            </div>
          ` : ''}
        </div>
      `;
    }

    /**
     * Render alerts
     * @param {Array} alerts - Alert data
     */
    _renderAlerts(alerts) {
      const container = this.elements.alertsContainer;
      if (!container) return;

      if (!alerts || alerts.length === 0) {
        container.innerHTML = '<div class="alert alert-success">No active alerts - all systems operating normally</div>';
        return;
      }

      let html = '';

      for (const alert of alerts) {
        const alertClass = alert.priority === 1 ? 'alert-danger' : 'alert-warning';
        const icon = alert.priority === 1 ? '!' : '!';

        html += `
          <div class="alert ${alertClass} mb-3">
            <div class="d-flex justify-content-between align-items-start">
              <div>
                <h6 class="alert-heading mb-2">
                  ${icon} ${this._escapeHtml(alert.message)}
                </h6>
                <p class="mb-2">
                  <strong>Unit:</strong> ${this._escapeHtml(alert.unit_name)} |
                  <strong>Risk Score:</strong> ${alert.risk_score}/100 |
                  <strong>Confidence:</strong> ${(alert.confidence * 100).toFixed(0)}%
                </p>
                ${alert.predicted_onset_days ? `
                  <p class="mb-2">
                    <strong>Estimated Onset:</strong> ${alert.predicted_onset_days} days
                  </p>
                ` : ''}
                ${alert.actions && alert.actions.length > 0 ? `
                  <div>
                    <strong>Immediate Actions:</strong>
                    <ol class="mb-0 mt-1">
                      ${alert.actions.map(action => `
                        <li>${this._escapeHtml(action)}</li>
                      `).join('')}
                    </ol>
                  </div>
                ` : ''}
              </div>
              <button class="btn btn-sm btn-outline-secondary" data-action="dismiss-alert" data-alert-id="${alert.alert_id}">
                Dismiss
              </button>
            </div>
          </div>
        `;
      }

      container.innerHTML = html;
    }

    /**
     * Render disease distribution chart
     * @param {Array} diseaseDistribution - Disease distribution data
     */
    _renderDiseaseChart(diseaseDistribution) {
      const ctx = this.elements.chartCanvas;
      if (!ctx) return;

      if (!diseaseDistribution || diseaseDistribution.length === 0) {
        ctx.parentElement.innerHTML = '<p class="text-muted">No disease data available</p>';
        return;
      }

      // Destroy existing chart
      if (this.diseaseChart) {
        this.diseaseChart.destroy();
        this.diseaseChart = null;
      }

      const labels = diseaseDistribution.map(d => this._formatDiseaseType(d.disease_type));
      const counts = diseaseDistribution.map(d => d.count);
      const severities = diseaseDistribution.map(d => d.avg_severity);

      this.diseaseChart = new Chart(ctx, {
        type: 'bar',
        data: {
          labels: labels,
          datasets: [
            {
              label: 'Occurrences',
              data: counts,
              backgroundColor: 'rgba(54, 162, 235, 0.5)',
              borderColor: 'rgba(54, 162, 235, 1)',
              borderWidth: 1,
              yAxisID: 'y'
            },
            {
              label: 'Avg Severity',
              data: severities,
              type: 'line',
              borderColor: 'rgba(255, 99, 132, 1)',
              backgroundColor: 'rgba(255, 99, 132, 0.1)',
              yAxisID: 'y1'
            }
          ]
        },
        options: {
          responsive: true,
          maintainAspectRatio: true,
          scales: {
            y: {
              type: 'linear',
              position: 'left',
              title: { display: true, text: 'Occurrences' }
            },
            y1: {
              type: 'linear',
              position: 'right',
              title: { display: true, text: 'Avg Severity' },
              min: 0,
              max: 5,
              grid: { drawOnChartArea: false }
            }
          }
        }
      });
    }

    /**
     * Render symptoms list
     * @param {Array} commonSymptoms - Common symptoms data
     */
    _renderSymptomsList(commonSymptoms) {
      const container = this.elements.symptomsContainer;
      if (!container) return;

      if (!commonSymptoms || commonSymptoms.length === 0) {
        container.innerHTML = '<p class="text-muted">No symptom data available</p>';
        return;
      }

      let html = '<ul class="list-group">';

      for (const item of commonSymptoms) {
        const symptoms = item.symptoms ? item.symptoms.split(',').map(s => s.trim()) : [];
        html += `
          <li class="list-group-item d-flex justify-content-between align-items-center">
            <span>${symptoms.slice(0, 3).join(', ')}</span>
            <span class="badge bg-primary rounded-pill">${item.count}</span>
          </li>
        `;
      }

      html += '</ul>';
      container.innerHTML = html;
    }

    /**
     * Dismiss an alert
     * @param {string} alertId - Alert ID
     */
    _dismissAlert(alertId) {
      this.dataService.dismissAlert(alertId);
      this._showNotification('Alert dismissed', 'success');

      // Re-render alerts
      const alerts = this.dataService.getAlerts();
      this._renderAlerts(alerts);
    }

    /**
     * Get risk icon for disease type
     * @param {string} diseaseType - Disease type
     * @returns {string} Icon
     */
    _getRiskIcon(diseaseType) {
      const icons = {
        'fungal': 'F',
        'bacterial': 'B',
        'viral': 'V',
        'pest': 'P',
        'nutrient_deficiency': 'N',
        'environmental_stress': 'E'
      };
      return icons[diseaseType] || '!';
    }

    /**
     * Format disease type for display
     * @param {string} diseaseType - Disease type
     * @returns {string} Formatted string
     */
    _formatDiseaseType(diseaseType) {
      if (!diseaseType) return '';
      return diseaseType.replace('_', ' ')
        .split(' ')
        .map(word => word.charAt(0).toUpperCase() + word.slice(1))
        .join(' ');
    }

    /**
     * Format contributing factor for display
     * @param {Object} factor - Factor data
     * @returns {string} Formatted string
     */
    _formatFactor(factor) {
      let text = this._formatDiseaseType(factor.factor);

      if (factor.value !== undefined) {
        text += `: ${typeof factor.value === 'number' ? factor.value.toFixed(1) : factor.value}`;
      }

      if (factor.threshold) {
        text += ` (threshold: ${factor.threshold})`;
      }

      if (factor.range) {
        text += ` (${factor.range})`;
      }

      return text;
    }

    /**
     * Show loading state
     */
    _showLoading() {
      if (this.elements.refreshBtn) {
        this.elements.refreshBtn.disabled = true;
        const icon = this.elements.refreshBtn.querySelector('i');
        if (icon) icon.classList.add('fa-spin');
      }
    }

    /**
     * Hide loading state
     */
    _hideLoading() {
      if (this.elements.refreshBtn) {
        this.elements.refreshBtn.disabled = false;
        const icon = this.elements.refreshBtn.querySelector('i');
        if (icon) icon.classList.remove('fa-spin');
      }
    }

    /**
     * Show notification
     * @param {string} message - Message to show
     * @param {string} type - Notification type
     */
    _showNotification(message, type = 'info') {
      // Use window notification system if available
      if (window.showNotification) {
        window.showNotification(message, type);
      } else {
        console.log(`[${type.toUpperCase()}] ${message}`);
      }
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
     * Cleanup resources
     */
    destroy() {
      // Clear refresh interval
      if (this.refreshInterval) {
        clearInterval(this.refreshInterval);
        this.refreshInterval = null;
      }

      // Destroy chart
      if (this.diseaseChart) {
        this.diseaseChart.destroy();
        this.diseaseChart = null;
      }

      // Call parent destroy if available
      if (super.destroy) {
        super.destroy();
      }
    }
  }

  // Export to window
  window.DiseaseDashboardUIManager = DiseaseDashboardUIManager;
})();
