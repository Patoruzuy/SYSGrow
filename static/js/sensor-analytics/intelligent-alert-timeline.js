/**
 * Intelligent Alert Timeline Component
 * ============================================================================
 * Displays alerts and anomalies on an interactive timeline with:
 * - Root cause analysis
 * - Clustered related alerts
 * - Pattern detection
 * - Severity-based filtering
 * - ML-powered insights
 */

(function() {
  'use strict';

  class IntelligentAlertTimeline {
    constructor(containerId, options = {}) {
      this.containerId = containerId;
      this.container = document.getElementById(containerId);
      
      if (!this.container) {
        console.error(`Container #${containerId} not found`);
        return;
      }

      // Configuration
      this.options = {
        updateInterval: options.updateInterval || 60000, // 1 minute
        timeRange: options.timeRange || 48, // hours
        maxAlerts: options.maxAlerts || 50,
        enableClustering: options.enableClustering !== false,
        enableRootCause: options.enableRootCause !== false,
        showPatterns: options.showPatterns !== false,
        ...options
      };

      this.unitId = null;
      this.alerts = [];
      this.clusters = [];
      this.patterns = [];
      this.chart = null;
      this.filters = {
        severity: ['critical', 'warning', 'info'],
        types: []
      };
      this.updateTimer = null;

      // Check ML availability
      this.mlAvailable = false;
      this.checkMLAvailability();
    }

    async checkMLAvailability() {
      if (typeof window.MLStatus !== 'undefined') {
        const status = await window.MLStatus.isAvailable();
        this.mlAvailable = status.rootCauseAnalysis?.available || false;
      }
    }

    async init(unitId = null) {
      this.unitId = unitId;
      
      try {
        this.render();
        await this.loadData();
        this.startAutoUpdate();
        
        console.log('[IntelligentAlertTimeline] Initialized', {
          unitId: this.unitId,
          timeRange: this.options.timeRange,
          mlAvailable: this.mlAvailable
        });
      } catch (error) {
        console.error('[IntelligentAlertTimeline] Initialization failed:', error);
        this.showError('Failed to initialize alert timeline');
      }
    }

    render() {
      this.container.innerHTML = `
        <div class="alert-timeline-card">
          <div class="alert-timeline-header">
            <div class="header-top">
              <h3 class="card-title">
                <i class="fas fa-exclamation-triangle"></i>
                Intelligent Alert Timeline
              </h3>
              <span class="alert-count-badge" id="${this.containerId}-count">0 alerts</span>
              <button class="refresh-btn" id="${this.containerId}-refresh" title="Refresh Alerts">
                <i class="fas fa-sync-alt"></i>
              </button>
            </div>
            <div class="header-bottom">
              <div class="filter-group">
                <button class="filter-btn active" data-severity="all">
                  All
                </button>
                <button class="filter-btn severity-critical" data-severity="critical">
                  <i class="fas fa-circle"></i> Critical
                </button>
                <button class="filter-btn severity-warning" data-severity="warning">
                  <i class="fas fa-circle"></i> Warning
                </button>
                <button class="filter-btn severity-info" data-severity="info">
                  <i class="fas fa-circle"></i> Info
                </button>
              </div>
            </div>
          </div>

          <!-- Pattern Detection Banner -->
          <div class="patterns-banner" id="${this.containerId}-patterns" style="display: none;"></div>

          <!-- Timeline Visualization -->
          <div class="timeline-viz-container">
            <canvas id="${this.containerId}-timeline-chart"></canvas>
          </div>

          <!-- Alert Clusters -->
          <div class="alert-clusters" id="${this.containerId}-clusters">
            <div class="loading-state">
              <i class="fas fa-spinner fa-spin"></i>
              <span>Loading alerts...</span>
            </div>
          </div>
        </div>
      `;

      this.attachEventListeners();
    }

    attachEventListeners() {
      // Refresh button
      const refreshBtn = document.getElementById(`${this.containerId}-refresh`);
      if (refreshBtn) {
        refreshBtn.addEventListener('click', () => this.refresh());
      }

      // Filter buttons
      const filterBtns = this.container.querySelectorAll('.filter-btn');
      filterBtns.forEach(btn => {
        btn.addEventListener('click', (e) => {
          const severity = e.currentTarget.dataset.severity;
          this.applyFilter(severity);
        });
      });
    }

    async loadData() {
      try {
        // Load alerts
        const options = {
          hours: this.options.timeRange,
          limit: this.options.maxAlerts
        };
        
        if (this.unitId) {
          options.unit_id = this.unitId;
        }

        const result = await API.System.getAlerts(options);

        if (result) {
          this.alerts = result.alerts || [];
          
          // Process alerts
          if (this.options.enableClustering) {
            this.clusters = this.clusterAlerts(this.alerts);
          }
          
          if (this.options.showPatterns) {
            this.patterns = this.detectPatterns(this.alerts);
          }

          // Add root cause analysis if ML available
          if (this.mlAvailable && this.options.enableRootCause) {
            await this.enrichWithRootCause();
          }

          this.updateUI();
        } else {
          throw new Error(result.error?.message || 'Failed to load alerts');
        }
      } catch (error) {
        console.error('[IntelligentAlertTimeline] Error loading data:', error);
        this.showError('Failed to load alerts');
      }
    }

    clusterAlerts(alerts) {
      // Group alerts by time proximity and type
      const clusters = [];
      const timeWindow = 15 * 60 * 1000; // 15 minutes
      
      const sorted = [...alerts].sort((a, b) => 
        new Date(a.created_at) - new Date(b.created_at)
      );

      let currentCluster = null;

      sorted.forEach(alert => {
        const alertTime = new Date(alert.created_at);
        
        if (!currentCluster || 
            alertTime - new Date(currentCluster.end_time) > timeWindow ||
            currentCluster.type !== alert.alert_type) {
          // Start new cluster
          if (currentCluster) clusters.push(currentCluster);
          
          currentCluster = {
            id: `cluster-${clusters.length}`,
            type: alert.alert_type,
            severity: alert.severity,
            start_time: alert.created_at,
            end_time: alert.created_at,
            alerts: [alert],
            count: 1
          };
        } else {
          // Add to current cluster
          currentCluster.alerts.push(alert);
          currentCluster.end_time = alert.created_at;
          currentCluster.count++;
          
          // Upgrade severity if needed
          if (this.compareSeverity(alert.severity, currentCluster.severity) > 0) {
            currentCluster.severity = alert.severity;
          }
        }
      });

      if (currentCluster) clusters.push(currentCluster);

      return clusters;
    }

    detectPatterns(alerts) {
      const patterns = [];
      
      // Pattern 1: Repeated alerts of same type
      const typeGroups = {};
      alerts.forEach(alert => {
        const key = alert.alert_type;
        if (!typeGroups[key]) typeGroups[key] = [];
        typeGroups[key].push(alert);
      });

      Object.entries(typeGroups).forEach(([type, alertList]) => {
        if (alertList.length >= 3) {
          patterns.push({
            type: 'repeated',
            alertType: type,
            count: alertList.length,
            message: `${alertList.length} ${type} alerts in ${this.options.timeRange}h`,
            severity: 'warning'
          });
        }
      });

      // Pattern 2: Escalating severity
      for (let i = 0; i < alerts.length - 2; i++) {
        const window = alerts.slice(i, i + 3);
        const severities = window.map(a => this.severityToNumber(a.severity));
        
        if (severities[0] < severities[1] && severities[1] < severities[2]) {
          patterns.push({
            type: 'escalating',
            message: 'Escalating alert pattern detected',
            alerts: window,
            severity: 'critical'
          });
          break; // Only report once
        }
      }

      // Pattern 3: Simultaneous alerts (cascade failure indicator)
      const simultaneousWindow = 5 * 60 * 1000; // 5 minutes
      for (let i = 0; i < alerts.length; i++) {
        const baseTime = new Date(alerts[i].created_at);
        const simultaneous = alerts.filter(a => 
          Math.abs(new Date(a.created_at) - baseTime) < simultaneousWindow
        );
        
        if (simultaneous.length >= 3) {
          patterns.push({
            type: 'cascade',
            message: `${simultaneous.length} alerts triggered simultaneously`,
            alerts: simultaneous,
            severity: 'critical'
          });
          break; // Only report once
        }
      }

      return patterns;
    }

    async enrichWithRootCause() {
      // Call ML service for root cause analysis
      if (this.clusters.length === 0) return;

      try {
        const result = await API.ML.rootCauseAnalysis({
          clusters: this.clusters.map(c => ({
            id: c.id,
            type: c.type,
            severity: c.severity,
            alert_ids: c.alerts.map(a => a.alert_id)
          }))
        });

        if (result) {
          // Merge root cause analysis into clusters
          result.analyses?.forEach(analysis => {
            const cluster = this.clusters.find(c => c.id === analysis.cluster_id);
            if (cluster) {
              cluster.rootCause = analysis.root_cause;
              cluster.confidence = analysis.confidence;
              cluster.recommendations = analysis.recommendations;
            }
          });
        }
      } catch (error) {
        console.warn('[IntelligentAlertTimeline] Root cause analysis failed:', error);
      }
    }

    updateUI() {
      this.updateCountBadge();
      this.updatePatternsBanner();
      this.renderTimeline();
      this.renderClusters();
    }

    updateCountBadge() {
      const badge = document.getElementById(`${this.containerId}-count`);
      if (badge) {
        const count = this.getFilteredAlerts().length;
        badge.textContent = count === 1 ? '1 alert' : `${count} alerts`;
      }
    }

    updatePatternsBanner() {
      const banner = document.getElementById(`${this.containerId}-patterns`);
      if (!banner || this.patterns.length === 0) {
        if (banner) banner.style.display = 'none';
        return;
      }

      banner.style.display = 'block';
      banner.innerHTML = this.patterns.map(pattern => `
        <div class="pattern-alert pattern-${pattern.severity}">
          <i class="fas fa-lightbulb"></i>
          <span>${pattern.message}</span>
          ${pattern.type === 'cascade' ? 
            '<span class="pattern-badge">Possible cascade failure</span>' : ''}
        </div>
      `).join('');
    }

    renderTimeline() {
      const canvas = document.getElementById(`${this.containerId}-timeline-chart`);
      if (!canvas) return;

      const ctx = canvas.getContext('2d');
      
      // Destroy existing chart
      if (this.chart) {
        this.chart.destroy();
      }

      const filteredAlerts = this.getFilteredAlerts();
      
      if (filteredAlerts.length === 0) {
        canvas.style.display = 'none';
        return;
      }
      
      canvas.style.display = 'block';

      // Prepare data for scatter plot (time vs severity)
      const data = filteredAlerts.map(alert => ({
        x: new Date(alert.created_at),
        y: this.severityToNumber(alert.severity),
        alert: alert
      }));

      this.chart = new Chart(ctx, {
        type: 'scatter',
        data: {
          datasets: [{
            label: 'Alerts',
            data: data,
            backgroundColor: data.map(d => this.getSeverityColor(d.alert.severity)),
            borderColor: data.map(d => this.getSeverityColor(d.alert.severity)),
            borderWidth: 2,
            pointRadius: 6,
            pointHoverRadius: 8
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { display: false },
            tooltip: {
              callbacks: {
                title: (items) => {
                  const alert = items[0].raw.alert;
                  return this.formatDateShort(alert.created_at);
                },
                label: (item) => {
                  const alert = item.raw.alert;
                  return [
                    `Severity: ${alert.severity}`,
                    `Type: ${alert.alert_type}`,
                    alert.title || 'Alert'
                  ];
                }
              }
            }
          },
          scales: {
            x: {
              type: 'time',
              time: {
                unit: 'hour',
                displayFormats: {
                  hour: 'MMM d HH:mm',
                  day: 'MMM d'
                },
                tooltipFormat: 'MMM d, HH:mm'
              },
              title: {
                display: true,
                text: 'Time'
              }
            },
            y: {
              min: 0,
              max: 3,
              ticks: {
                callback: (value) => {
                  const labels = ['', 'Info', 'Warning', 'Critical'];
                  return labels[value] || '';
                }
              },
              title: {
                display: true,
                text: 'Severity'
              }
            }
          }
        }
      });
    }

    renderClusters() {
      const container = document.getElementById(`${this.containerId}-clusters`);
      if (!container) return;

      const filteredClusters = this.clusters.filter(cluster => 
        this.filters.severity.includes(cluster.severity)
      );

      if (filteredClusters.length === 0) {
        container.innerHTML = `
          <div class="empty-state">
            <i class="fas fa-check-circle"></i>
            <p>No alerts in the selected time range</p>
          </div>
        `;
        return;
      }

      container.innerHTML = filteredClusters.map(cluster => `
        <div class="alert-cluster severity-${cluster.severity}">
          <div class="cluster-header">
            <div class="cluster-info">
              <span class="cluster-badge badge-${cluster.severity}">
                ${cluster.severity.toUpperCase()}
              </span>
              <span class="cluster-type">${this.formatAlertType(cluster.type)}</span>
              ${cluster.count > 1 ? 
                `<span class="cluster-count">${cluster.count} occurrences</span>` : ''}
            </div>
            <div class="cluster-time">
              ${this.formatDateShort(cluster.start_time)}
              ${cluster.count > 1 ? 
                ` - ${this.formatDateShort(cluster.end_time)}` : ''}
            </div>
          </div>
          
          <div class="cluster-body">
            ${cluster.rootCause ? `
              <div class="root-cause">
                <div class="root-cause-header">
                  <i class="fas fa-search"></i>
                  <strong>Root Cause Analysis</strong>
                  <span class="confidence-badge">
                    ${Math.round(cluster.confidence * 100)}% confidence
                  </span>
                </div>
                <p>${cluster.rootCause}</p>
                ${cluster.recommendations ? `
                  <div class="recommendations">
                    <strong>Recommendations:</strong>
                    <ul>
                      ${cluster.recommendations.map(rec => `<li>${rec}</li>`).join('')}
                    </ul>
                  </div>
                ` : ''}
              </div>
            ` : ''}
            
            <div class="cluster-alerts">
              ${cluster.alerts.slice(0, 3).map(alert => `
                <div class="alert-item">
                  <div class="alert-icon">
                    <i class="fas ${this.getAlertIcon(alert.alert_type)}"></i>
                  </div>
                  <div class="alert-content">
                    <strong>${alert.title || 'Alert'}</strong>
                    <p>${alert.message || ''}</p>
                    <span class="alert-time">${this.formatTimeAgo(alert.created_at)}</span>
                  </div>
                </div>
              `).join('')}
              
              ${cluster.count > 3 ? `
                <button class="show-more-btn" onclick="this.nextElementSibling.style.display='block';this.style.display='none'">
                  Show ${cluster.count - 3} more...
                </button>
                <div class="more-alerts" style="display:none;">
                  ${cluster.alerts.slice(3).map(alert => `
                    <div class="alert-item">
                      <div class="alert-icon">
                        <i class="fas ${this.getAlertIcon(alert.alert_type)}"></i>
                      </div>
                      <div class="alert-content">
                        <strong>${alert.title || 'Alert'}</strong>
                        <p>${alert.message || ''}</p>
                        <span class="alert-time">${this.formatTimeAgo(alert.created_at)}</span>
                      </div>
                    </div>
                  `).join('')}
                </div>
              ` : ''}
            </div>
          </div>
        </div>
      `).join('');
    }

    // Utility methods
    getFilteredAlerts() {
      return this.alerts.filter(alert => 
        this.filters.severity.includes(alert.severity)
      );
    }

    applyFilter(severity) {
      // Update filter buttons
      const filterBtns = this.container.querySelectorAll('.filter-btn');
      filterBtns.forEach(btn => btn.classList.remove('active'));
      
      const clickedBtn = this.container.querySelector(`[data-severity="${severity}"]`);
      if (clickedBtn) clickedBtn.classList.add('active');

      // Update filters
      if (severity === 'all') {
        this.filters.severity = ['critical', 'warning', 'info'];
      } else {
        this.filters.severity = [severity];
      }

      this.updateUI();
    }

    formatDateShort(dateStr) {
      if (!dateStr) return '--';

      const date = new Date(dateStr);
      if (isNaN(date.getTime())) return '--';

      const options = { month: 'short', day: 'numeric' };
      return date.toLocaleDateString('en-US', options);
    }

    formatTimeAgo(dateStr) {
      if (!dateStr) return '--';

      const date = new Date(dateStr);
      if (isNaN(date.getTime())) return '--';

      const now = new Date();
      const diff = now - date;

      if (diff < 0) return 'just now';

      const minutes = Math.floor(diff / 60000);
      const hours = Math.floor(diff / 3600000);
      const days = Math.floor(diff / 86400000);

      if (minutes < 1) return 'just now';
      if (minutes < 60) return `${minutes}m ago`;
      if (hours < 24) return `${hours}h ago`;
      if (days < 30) return `${days}d ago`;
      return date.toLocaleDateString();
    }

    formatAlertType(type) {
      return type.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
    }

    getAlertIcon(type) {
      const icons = {
        sensor_anomaly: 'fa-exclamation-triangle',
        device_offline: 'fa-power-off',
        device_malfunction: 'fa-wrench',
        threshold_breach: 'fa-chart-line',
        actuator_failure: 'fa-cog',
        system_error: 'fa-bug'
      };
      return icons[type] || 'fa-bell';
    }

    getSeverityColor(severity) {
      // Use CSS variables from theme.css
      const colors = {
        critical: 'var(--danger-500, #dc3545)',
        warning: 'var(--warning-500, #f59e0b)',
        info: 'var(--info-500, #3b82f6)'
      };
      return colors[severity] || 'var(--color-text-muted, #6c757d)';
    }

    severityToNumber(severity) {
      const map = { info: 1, warning: 2, critical: 3 };
      return map[severity] || 0;
    }

    compareSeverity(s1, s2) {
      return this.severityToNumber(s1) - this.severityToNumber(s2);
    }

    showError(message) {
      if (this.container) {
        this.container.innerHTML = `
          <div class="alert-timeline-card">
            <div class="error-state">
              <i class="fas fa-exclamation-circle"></i>
              <p>${message}</p>
            </div>
          </div>
        `;
      }
    }

    async refresh() {
      const refreshBtn = document.getElementById(`${this.containerId}-refresh`);
      if (refreshBtn) {
        refreshBtn.classList.add('spinning');
      }

      await this.loadData();

      if (refreshBtn) {
        setTimeout(() => refreshBtn.classList.remove('spinning'), 500);
      }
    }

    startAutoUpdate() {
      this.stopAutoUpdate();
      
      if (this.options.updateInterval > 0) {
        this.updateTimer = setInterval(() => {
          this.refresh();
        }, this.options.updateInterval);
      }
    }

    stopAutoUpdate() {
      if (this.updateTimer) {
        clearInterval(this.updateTimer);
        this.updateTimer = null;
      }
    }

    destroy() {
      this.stopAutoUpdate();
      if (this.chart) {
        this.chart.destroy();
      }
    }
  }

  // Export to global scope
  window.IntelligentAlertTimeline = IntelligentAlertTimeline;
})();
