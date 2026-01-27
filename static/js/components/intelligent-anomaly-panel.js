/**
 * Intelligent Anomaly Panel Component
 * ============================================================================
 * Enhanced anomaly detection display with:
 * - Clustered anomalies by root cause
 * - Priority scoring and severity levels
 * - Action items and recommendations
 * - Trend analysis for recurring issues
 *
 * Usage:
 *   const panel = new IntelligentAnomalyPanel('anomaly-container', {
 *     showActions: true,
 *     onAction: (anomaly, action) => handleAction(anomaly, action)
 *   });
 *   panel.update(anomaliesData);
 */
(function() {
  'use strict';

  class IntelligentAnomalyPanel {
    constructor(containerId, options = {}) {
      this.containerId = containerId;
      this.container = document.getElementById(containerId);

      if (!this.container) {
        console.warn(`[IntelligentAnomalyPanel] Container "${containerId}" not found`);
        return;
      }

      this.options = {
        showActions: options.showActions !== false,
        showTrends: options.showTrends !== false,
        maxVisible: options.maxVisible || 10,
        clusterWindowMs: options.clusterWindowMs || 15 * 60 * 1000, // 15 minutes
        onAction: options.onAction || null,
        onDismiss: options.onDismiss || null,
        ...options
      };

      this.data = [];
      this.clusters = [];

      // Anomaly type configurations
      this.anomalyTypes = {
        spike: {
          icon: 'fas fa-arrow-up',
          label: 'Spike Detected',
          color: 'warning',
          description: 'Sudden increase above normal range'
        },
        drop: {
          icon: 'fas fa-arrow-down',
          label: 'Drop Detected',
          color: 'warning',
          description: 'Sudden decrease below normal range'
        },
        threshold_breach: {
          icon: 'fas fa-exclamation-triangle',
          label: 'Threshold Breach',
          color: 'danger',
          description: 'Value exceeded configured threshold'
        },
        sensor_drift: {
          icon: 'fas fa-chart-line',
          label: 'Sensor Drift',
          color: 'warning',
          description: 'Gradual deviation from expected values'
        },
        correlation_break: {
          icon: 'fas fa-unlink',
          label: 'Correlation Break',
          color: 'info',
          description: 'Expected sensor relationship disrupted'
        },
        pattern_anomaly: {
          icon: 'fas fa-wave-square',
          label: 'Pattern Anomaly',
          color: 'info',
          description: 'Unusual pattern detected in readings'
        },
        offline: {
          icon: 'fas fa-plug',
          label: 'Sensor Offline',
          color: 'danger',
          description: 'Sensor stopped reporting data'
        },
        unknown: {
          icon: 'fas fa-question-circle',
          label: 'Unknown Anomaly',
          color: 'secondary',
          description: 'Anomaly type not classified'
        }
      };

      // Sensor labels
      this.sensorLabels = {
        temperature: 'Temperature',
        humidity: 'Humidity',
        soil_moisture: 'Soil Moisture',
        co2_level: 'CO2 Level',
        light_level: 'Light Level',
        vpd: 'VPD'
      };

      // Root cause templates
      this.rootCauses = {
        'temperature_spike': [
          'Grow lights generating excess heat',
          'HVAC system failure',
          'External heat source (weather, equipment)'
        ],
        'humidity_drop': [
          'Ventilation running too aggressively',
          'Temperature increase causing humidity reduction',
          'Dehumidifier malfunction'
        ],
        'co2_spike': [
          'CO2 enrichment system activated',
          'Poor ventilation during high plant respiration',
          'External CO2 source'
        ],
        'soil_moisture_drop': [
          'Irrigation schedule missed',
          'Pump or valve malfunction',
          'Increased plant uptake during growth phase'
        ],
        'light_level_drop': [
          'Light fixture failure',
          'Timer or schedule issue',
          'Power supply problem'
        ]
      };

      this._initContainer();
    }

    /**
     * Initialize container structure
     */
    _initContainer() {
      if (!this.container) return;

      this.container.innerHTML = `
        <div class="anomaly-panel">
          <div class="anomaly-panel__header">
            <div class="anomaly-panel__summary">
              <span class="anomaly-count">0 anomalies</span>
              <span class="anomaly-timeframe">Last 24h</span>
            </div>
            <div class="anomaly-panel__filters">
              <select class="anomaly-filter" id="${this.containerId}-severity">
                <option value="all">All Severities</option>
                <option value="high">High Priority</option>
                <option value="medium">Medium Priority</option>
                <option value="low">Low Priority</option>
              </select>
            </div>
          </div>
          <div class="anomaly-panel__list"></div>
          ${this.options.showTrends ? '<div class="anomaly-panel__trends"></div>' : ''}
        </div>
      `;

      this.summaryEl = this.container.querySelector('.anomaly-panel__summary');
      this.listEl = this.container.querySelector('.anomaly-panel__list');
      this.trendsEl = this.container.querySelector('.anomaly-panel__trends');
      this.filterEl = this.container.querySelector('.anomaly-filter');

      if (this.filterEl) {
        this.filterEl.addEventListener('change', () => this._applyFilter());
      }
    }

    /**
     * Update with anomaly data
     * @param {Array} anomalies - Array of anomaly objects
     */
    update(anomalies) {
      if (!this.container) return;

      this.data = Array.isArray(anomalies) ? anomalies : [];

      // Score and cluster anomalies
      const scored = this._scoreAnomalies(this.data);
      this.clusters = this._clusterAnomalies(scored);

      this._renderSummary();
      this._renderList();

      if (this.options.showTrends) {
        this._renderTrends();
      }
    }

    /**
     * Score anomalies by priority
     */
    _scoreAnomalies(anomalies) {
      return anomalies.map(anomaly => {
        let score = 0;

        // Severity multiplier
        const severity = anomaly.severity || 'medium';
        const severityScores = { critical: 100, high: 75, medium: 50, low: 25 };
        score += severityScores[severity] || 50;

        // Recency bonus
        const age = Date.now() - new Date(anomaly.timestamp).getTime();
        const hoursOld = age / (1000 * 60 * 60);
        if (hoursOld < 1) score += 30;
        else if (hoursOld < 6) score += 15;

        // Sensor importance
        const criticalSensors = ['temperature', 'humidity', 'soil_moisture'];
        if (criticalSensors.includes(anomaly.sensor_type)) {
          score += 20;
        }

        // Deviation magnitude
        if (anomaly.deviation) {
          score += Math.min(Math.abs(anomaly.deviation) * 2, 30);
        }

        return {
          ...anomaly,
          priority_score: score,
          priority: score >= 80 ? 'high' : score >= 50 ? 'medium' : 'low'
        };
      }).sort((a, b) => b.priority_score - a.priority_score);
    }

    /**
     * Cluster related anomalies
     */
    _clusterAnomalies(anomalies) {
      const clusters = [];
      const used = new Set();

      for (let i = 0; i < anomalies.length; i++) {
        if (used.has(i)) continue;

        const cluster = {
          primary: anomalies[i],
          related: [],
          root_cause: null,
          recommendations: []
        };

        // Find related anomalies
        for (let j = i + 1; j < anomalies.length; j++) {
          if (used.has(j)) continue;

          if (this._areRelated(anomalies[i], anomalies[j])) {
            cluster.related.push(anomalies[j]);
            used.add(j);
          }
        }

        // Analyze root cause
        cluster.root_cause = this._identifyRootCause(cluster);
        cluster.recommendations = this._generateRecommendations(cluster);

        clusters.push(cluster);
        used.add(i);
      }

      return clusters;
    }

    /**
     * Check if two anomalies are related
     */
    _areRelated(a, b) {
      // Same sensor
      if (a.sensor_type === b.sensor_type && a.sensor_id === b.sensor_id) {
        return true;
      }

      // Time proximity
      const timeDiff = Math.abs(
        new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
      );
      if (timeDiff > this.options.clusterWindowMs) return false;

      // Known correlated sensors
      const correlatedPairs = [
        ['temperature', 'humidity'],
        ['temperature', 'vpd'],
        ['humidity', 'vpd'],
        ['light_level', 'temperature']
      ];

      for (const [s1, s2] of correlatedPairs) {
        if ((a.sensor_type === s1 && b.sensor_type === s2) ||
            (a.sensor_type === s2 && b.sensor_type === s1)) {
          return true;
        }
      }

      return false;
    }

    /**
     * Identify root cause for a cluster
     */
    _identifyRootCause(cluster) {
      const primary = cluster.primary;
      const type = primary.type || 'unknown';
      const sensor = primary.sensor_type;

      const key = `${sensor}_${type}`;
      const causes = this.rootCauses[key];

      if (causes && causes.length > 0) {
        return causes[0]; // Return most likely cause
      }

      // Default based on type
      if (type === 'threshold_breach') {
        return `${this.sensorLabels[sensor] || sensor} exceeded configured limits`;
      }
      if (type === 'offline') {
        return `${this.sensorLabels[sensor] || sensor} sensor connection lost`;
      }

      return 'Unusual sensor behavior detected';
    }

    /**
     * Generate recommendations for a cluster
     */
    _generateRecommendations(cluster) {
      const recommendations = [];
      const primary = cluster.primary;
      const sensor = primary.sensor_type;
      const type = primary.type;

      // Type-specific recommendations
      if (type === 'threshold_breach') {
        recommendations.push({
          action: 'adjust_threshold',
          label: 'Review threshold settings',
          icon: 'fas fa-sliders-h'
        });
        recommendations.push({
          action: 'view_history',
          label: 'View sensor history',
          icon: 'fas fa-chart-line'
        });
      }

      if (type === 'offline') {
        recommendations.push({
          action: 'check_connection',
          label: 'Check sensor connection',
          icon: 'fas fa-plug'
        });
        recommendations.push({
          action: 'restart_sensor',
          label: 'Restart sensor',
          icon: 'fas fa-redo'
        });
      }

      if (type === 'spike' || type === 'drop') {
        recommendations.push({
          action: 'investigate',
          label: 'Investigate root cause',
          icon: 'fas fa-search'
        });
      }

      // Sensor-specific recommendations
      if (sensor === 'temperature') {
        recommendations.push({
          action: 'check_hvac',
          label: 'Check HVAC system',
          icon: 'fas fa-fan'
        });
      }

      if (sensor === 'soil_moisture') {
        recommendations.push({
          action: 'check_irrigation',
          label: 'Check irrigation system',
          icon: 'fas fa-faucet'
        });
      }

      return recommendations.slice(0, 3); // Max 3 recommendations
    }

    /**
     * Render summary section
     */
    _renderSummary() {
      if (!this.summaryEl) return;

      const total = this.data.length;
      const highPriority = this.clusters.filter(c => c.primary.priority === 'high').length;

      this.summaryEl.innerHTML = `
        <span class="anomaly-count ${highPriority > 0 ? 'has-high' : ''}">
          ${total} ${total === 1 ? 'anomaly' : 'anomalies'}
          ${highPriority > 0 ? `<span class="high-priority-badge">${highPriority} high priority</span>` : ''}
        </span>
        <span class="anomaly-timeframe">
          ${this.clusters.length} ${this.clusters.length === 1 ? 'issue' : 'issues'} identified
        </span>
      `;
    }

    /**
     * Render anomaly list
     */
    _renderList() {
      if (!this.listEl) return;

      if (this.clusters.length === 0) {
        this.listEl.innerHTML = `
          <div class="anomaly-empty">
            <i class="fas fa-check-circle"></i>
            <span>No anomalies detected</span>
            <small>Your system is operating normally</small>
          </div>
        `;
        return;
      }

      const visibleClusters = this.clusters.slice(0, this.options.maxVisible);

      const html = visibleClusters.map((cluster, index) => {
        const primary = cluster.primary;
        const typeConfig = this.anomalyTypes[primary.type] || this.anomalyTypes.unknown;
        const sensorLabel = this.sensorLabels[primary.sensor_type] || primary.sensor_type;
        const relatedCount = cluster.related.length;

        return `
          <div class="anomaly-item priority-${primary.priority}" data-index="${index}">
            <div class="anomaly-item__icon ${typeConfig.color}">
              <i class="${typeConfig.icon}"></i>
            </div>
            <div class="anomaly-item__content">
              <div class="anomaly-item__header">
                <span class="anomaly-type">${typeConfig.label}</span>
                <span class="anomaly-sensor">${sensorLabel}</span>
                ${relatedCount > 0 ? `<span class="anomaly-cluster-badge">+${relatedCount} related</span>` : ''}
              </div>
              <div class="anomaly-item__details">
                ${primary.value !== undefined ? `
                  <span class="anomaly-value">${this._formatValue(primary.value, primary.sensor_type)}</span>
                ` : ''}
                ${primary.deviation !== undefined ? `
                  <span class="anomaly-deviation ${primary.deviation > 0 ? 'up' : 'down'}">
                    ${primary.deviation > 0 ? '+' : ''}${primary.deviation.toFixed(1)}%
                  </span>
                ` : ''}
                <span class="anomaly-time">${this._formatTime(primary.timestamp)}</span>
              </div>
              ${cluster.root_cause ? `
                <div class="anomaly-item__cause">
                  <i class="fas fa-lightbulb"></i>
                  <span>${cluster.root_cause}</span>
                </div>
              ` : ''}
            </div>
            <div class="anomaly-item__actions">
              ${this.options.showActions ? this._renderActions(cluster) : ''}
              ${this.options.onDismiss ? `
                <button class="anomaly-dismiss" data-index="${index}" title="Dismiss">
                  <i class="fas fa-times"></i>
                </button>
              ` : ''}
            </div>
          </div>
        `;
      }).join('');

      this.listEl.innerHTML = html;

      // Show more indicator
      if (this.clusters.length > this.options.maxVisible) {
        this.listEl.innerHTML += `
          <div class="anomaly-show-more">
            <button class="btn btn-sm btn-outline">
              Show ${this.clusters.length - this.options.maxVisible} more
            </button>
          </div>
        `;
      }

      this._attachListeners();
    }

    /**
     * Render action buttons for a cluster
     */
    _renderActions(cluster) {
      if (!cluster.recommendations || cluster.recommendations.length === 0) {
        return '';
      }

      const primary = cluster.recommendations[0];

      return `
        <button class="anomaly-action" data-action="${primary.action}" title="${primary.label}">
          <i class="${primary.icon}"></i>
        </button>
      `;
    }

    /**
     * Render trends section
     */
    _renderTrends() {
      if (!this.trendsEl || this.data.length === 0) {
        if (this.trendsEl) {
          this.trendsEl.style.display = 'none';
        }
        return;
      }

      // Calculate trends
      const bySensor = {};
      const byType = {};

      for (const anomaly of this.data) {
        const sensor = anomaly.sensor_type;
        const type = anomaly.type;

        bySensor[sensor] = (bySensor[sensor] || 0) + 1;
        byType[type] = (byType[type] || 0) + 1;
      }

      // Find most affected sensor
      const topSensor = Object.entries(bySensor)
        .sort((a, b) => b[1] - a[1])[0];

      // Find most common type
      const topType = Object.entries(byType)
        .sort((a, b) => b[1] - a[1])[0];

      this.trendsEl.style.display = 'block';
      this.trendsEl.innerHTML = `
        <div class="anomaly-trends">
          <div class="trend-title">Trends</div>
          <div class="trend-items">
            ${topSensor ? `
              <div class="trend-item">
                <span class="trend-label">Most affected:</span>
                <span class="trend-value">${this.sensorLabels[topSensor[0]] || topSensor[0]}</span>
                <span class="trend-count">(${topSensor[1]} issues)</span>
              </div>
            ` : ''}
            ${topType ? `
              <div class="trend-item">
                <span class="trend-label">Common issue:</span>
                <span class="trend-value">${(this.anomalyTypes[topType[0]] || this.anomalyTypes.unknown).label}</span>
                <span class="trend-count">(${topType[1]} occurrences)</span>
              </div>
            ` : ''}
          </div>
        </div>
      `;
    }

    /**
     * Attach event listeners
     */
    _attachListeners() {
      // Action buttons
      const actionBtns = this.listEl.querySelectorAll('.anomaly-action');
      actionBtns.forEach(btn => {
        btn.addEventListener('click', (e) => {
          e.stopPropagation();
          const index = parseInt(btn.closest('.anomaly-item').dataset.index);
          const action = btn.dataset.action;
          const cluster = this.clusters[index];

          if (this.options.onAction && cluster) {
            this.options.onAction(cluster.primary, action, cluster);
          }
        });
      });

      // Dismiss buttons
      const dismissBtns = this.listEl.querySelectorAll('.anomaly-dismiss');
      dismissBtns.forEach(btn => {
        btn.addEventListener('click', (e) => {
          e.stopPropagation();
          const index = parseInt(btn.dataset.index);
          const cluster = this.clusters[index];

          if (this.options.onDismiss && cluster) {
            this.options.onDismiss(cluster.primary, cluster);
          }
        });
      });

      // Show more button
      const showMoreBtn = this.listEl.querySelector('.anomaly-show-more button');
      if (showMoreBtn) {
        showMoreBtn.addEventListener('click', () => {
          this.options.maxVisible = this.clusters.length;
          this._renderList();
        });
      }

      // Item expansion (show related)
      const items = this.listEl.querySelectorAll('.anomaly-item');
      items.forEach(item => {
        const badge = item.querySelector('.anomaly-cluster-badge');
        if (badge) {
          badge.addEventListener('click', (e) => {
            e.stopPropagation();
            item.classList.toggle('expanded');
          });
        }
      });
    }

    /**
     * Apply severity filter
     */
    _applyFilter() {
      const filter = this.filterEl?.value || 'all';

      const items = this.listEl.querySelectorAll('.anomaly-item');
      items.forEach(item => {
        if (filter === 'all') {
          item.style.display = '';
        } else {
          const isMatch = item.classList.contains(`priority-${filter}`);
          item.style.display = isMatch ? '' : 'none';
        }
      });
    }

    /**
     * Format value with sensor unit
     */
    _formatValue(value, sensorType) {
      if (value === null || value === undefined) return '--';

      const units = {
        temperature: '°C',
        humidity: '%',
        soil_moisture: '%',
        co2_level: ' ppm',
        light_level: ' lux',
        vpd: ' kPa'
      };

      const unit = units[sensorType] || '';
      return `${typeof value === 'number' ? value.toFixed(1) : value}${unit}`;
    }

    /**
     * Format timestamp
     */
    _formatTime(timestamp) {
      if (!timestamp) return '';

      const date = new Date(timestamp);
      const now = new Date();
      const diffMs = now - date;
      const diffMins = Math.floor(diffMs / 60000);
      const diffHours = Math.floor(diffMs / 3600000);
      const diffDays = Math.floor(diffMs / 86400000);

      if (diffMins < 1) return 'Just now';
      if (diffMins < 60) return `${diffMins}m ago`;
      if (diffHours < 24) return `${diffHours}h ago`;
      if (diffDays < 7) return `${diffDays}d ago`;

      return date.toLocaleDateString();
    }

    /**
     * Get statistics
     */
    getStats() {
      return {
        total: this.data.length,
        clusters: this.clusters.length,
        byPriority: {
          high: this.clusters.filter(c => c.primary.priority === 'high').length,
          medium: this.clusters.filter(c => c.primary.priority === 'medium').length,
          low: this.clusters.filter(c => c.primary.priority === 'low').length
        },
        bySensor: Object.fromEntries(
          Object.keys(this.sensorLabels).map(sensor => [
            sensor,
            this.data.filter(a => a.sensor_type === sensor).length
          ])
        )
      };
    }

    /**
     * Destroy the component
     */
    destroy() {
      if (this.filterEl) {
        this.filterEl.removeEventListener('change', this._applyFilter);
      }
    }
  }

  // Export to window
  window.IntelligentAnomalyPanel = IntelligentAnomalyPanel;
})();
