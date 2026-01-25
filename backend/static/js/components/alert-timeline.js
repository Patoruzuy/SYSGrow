/**
 * Alert Timeline Component
 * ============================================================================
 * An intelligent alert timeline with clustering, prioritization, and actions.
 *
 * Features:
 * - Groups related alerts by root cause
 * - Priority-based sorting (critical > warning > info)
 * - Time-based clustering (within 5-minute windows)
 * - Expandable alert details
 * - Quick action buttons
 *
 * Usage:
 *   const timeline = new AlertTimeline('alerts-container', {
 *     onDismiss: (alertId) => { ... },
 *     onAction: (alertId, action) => { ... },
 *     maxVisible: 10
 *   });
 *   timeline.update(alertsArray);
 */
(function() {
  'use strict';

  class AlertTimeline {
    constructor(containerId, options = {}) {
      this.containerId = containerId;
      this.container = document.getElementById(containerId);

      if (!this.container) {
        console.warn(`[AlertTimeline] Container element "${containerId}" not found`);
        return;
      }

      this.options = {
        onDismiss: options.onDismiss || null,
        onAction: options.onAction || null,
        onClick: options.onClick || null,
        maxVisible: options.maxVisible || 10,
        clusterWindowMs: options.clusterWindowMs || 5 * 60 * 1000, // 5 minutes
        showActions: options.showActions !== false,
        emptyMessage: options.emptyMessage || 'No alerts',
        ...options
      };

      this.alerts = [];
      this.clusters = [];

      // Severity configuration
      this.severityConfig = {
        critical: {
          priority: 1,
          icon: 'fas fa-exclamation-circle',
          color: 'var(--status-danger)',
          label: 'Critical'
        },
        warning: {
          priority: 2,
          icon: 'fas fa-exclamation-triangle',
          color: 'var(--status-warning)',
          label: 'Warning'
        },
        info: {
          priority: 3,
          icon: 'fas fa-info-circle',
          color: 'var(--status-info)',
          label: 'Info'
        },
        success: {
          priority: 4,
          icon: 'fas fa-check-circle',
          color: 'var(--status-success)',
          label: 'Resolved'
        }
      };

      // Alert type icons
      this.typeIcons = {
        threshold: 'fas fa-chart-line',
        sensor: 'fas fa-thermometer-half',
        device: 'fas fa-microchip',
        actuator: 'fas fa-toggle-on',
        system: 'fas fa-server',
        plant: 'fas fa-seedling',
        network: 'fas fa-wifi',
        security: 'fas fa-shield-alt'
      };

      this._bindEvents();
    }

    /**
     * Bind event listeners
     */
    _bindEvents() {
      if (!this.container) return;

      // Delegated event handling
      this.container.addEventListener('click', (e) => {
        const dismissBtn = e.target.closest('.alert-dismiss');
        if (dismissBtn) {
          e.stopPropagation();
          const alertId = dismissBtn.dataset.alertId;
          this._handleDismiss(alertId);
          return;
        }

        const actionBtn = e.target.closest('.alert-action-btn');
        if (actionBtn) {
          e.stopPropagation();
          const alertId = actionBtn.dataset.alertId;
          const action = actionBtn.dataset.action;
          this._handleAction(alertId, action);
          return;
        }

        const alertItem = e.target.closest('.alert-timeline__item');
        if (alertItem) {
          this._handleClick(alertItem.dataset.alertId);
        }

        const clusterHeader = e.target.closest('.alert-cluster__header');
        if (clusterHeader) {
          const cluster = clusterHeader.closest('.alert-cluster');
          if (cluster) {
            cluster.classList.toggle('expanded');
          }
        }
      });
    }

    /**
     * Handle dismiss click
     */
    _handleDismiss(alertId) {
      if (this.options.onDismiss) {
        this.options.onDismiss(alertId);
      }

      // Remove from local state
      this.alerts = this.alerts.filter(a => String(a.id) !== String(alertId));
      this._processAndRender();
    }

    /**
     * Handle action button click
     */
    _handleAction(alertId, action) {
      if (this.options.onAction) {
        this.options.onAction(alertId, action);
      }
    }

    /**
     * Handle alert click
     */
    _handleClick(alertId) {
      if (this.options.onClick) {
        const alert = this.alerts.find(a => String(a.id) === String(alertId));
        this.options.onClick(alertId, alert);
      }
    }

    /**
     * Update the timeline with new alerts
     * @param {Array} alerts - Array of alert objects
     */
    update(alerts) {
      if (!this.container) return;

      this.alerts = Array.isArray(alerts) ? [...alerts] : [];
      this._processAndRender();
    }

    /**
     * Add a single alert
     */
    addAlert(alert) {
      if (!alert) return;
      this.alerts.unshift(alert);
      this._processAndRender();
    }

    /**
     * Process alerts (cluster, sort) and render
     */
    _processAndRender() {
      // Sort by priority and time
      this.alerts.sort((a, b) => {
        const priorityA = this.severityConfig[a.severity]?.priority || 99;
        const priorityB = this.severityConfig[b.severity]?.priority || 99;

        if (priorityA !== priorityB) return priorityA - priorityB;

        // Same priority: sort by time (newest first)
        const timeA = new Date(a.timestamp || 0).getTime();
        const timeB = new Date(b.timestamp || 0).getTime();
        return timeB - timeA;
      });

      // Cluster related alerts
      this.clusters = this._clusterAlerts(this.alerts);

      this.render();
    }

    /**
     * Cluster related alerts by source and time proximity
     */
    _clusterAlerts(alerts) {
      if (alerts.length === 0) return [];

      const clusters = [];
      const processed = new Set();

      for (const alert of alerts) {
        if (processed.has(alert.id)) continue;

        const cluster = {
          id: `cluster-${alert.id}`,
          primary: alert,
          related: [],
          severity: alert.severity,
          source: alert.source || alert.type || 'system',
          timestamp: alert.timestamp
        };

        // Find related alerts (same source, within time window)
        for (const other of alerts) {
          if (other.id === alert.id || processed.has(other.id)) continue;

          if (this._areRelated(alert, other)) {
            cluster.related.push(other);
            processed.add(other.id);

            // Upgrade cluster severity if needed
            const otherPriority = this.severityConfig[other.severity]?.priority || 99;
            const clusterPriority = this.severityConfig[cluster.severity]?.priority || 99;
            if (otherPriority < clusterPriority) {
              cluster.severity = other.severity;
            }
          }
        }

        processed.add(alert.id);
        clusters.push(cluster);
      }

      return clusters.slice(0, this.options.maxVisible);
    }

    /**
     * Check if two alerts are related (same source, within time window)
     */
    _areRelated(a, b) {
      // Same source/type
      const sourceA = a.source || a.sensor_id || a.device_id || a.type;
      const sourceB = b.source || b.sensor_id || b.device_id || b.type;

      if (sourceA !== sourceB) return false;

      // Within time window
      const timeA = new Date(a.timestamp || 0).getTime();
      const timeB = new Date(b.timestamp || 0).getTime();

      return Math.abs(timeA - timeB) <= this.options.clusterWindowMs;
    }

    /**
     * Render the timeline
     */
    render() {
      if (!this.container) return;

      if (this.clusters.length === 0) {
        this.container.innerHTML = `<div class="empty-message">${this.options.emptyMessage}</div>`;
        return;
      }

      this.container.innerHTML = this.clusters
        .map(cluster => this._renderCluster(cluster))
        .join('');
    }

    /**
     * Render a cluster of alerts
     */
    _renderCluster(cluster) {
      const hasRelated = cluster.related.length > 0;
      const severityConfig = this.severityConfig[cluster.severity] || this.severityConfig.info;
      const typeIcon = this.typeIcons[cluster.source] || 'fas fa-bell';

      if (!hasRelated) {
        // Single alert - render directly
        return this._renderAlert(cluster.primary);
      }

      // Clustered alerts
      const totalCount = 1 + cluster.related.length;

      return `
        <div class="alert-cluster" data-cluster-id="${cluster.id}">
          <div class="alert-cluster__header">
            <div class="alert-cluster__icon" style="color: ${severityConfig.color}">
              <i class="${severityConfig.icon}"></i>
            </div>
            <div class="alert-cluster__content">
              <div class="alert-cluster__title">
                ${window.escapeHtml(cluster.primary.message || 'Alert')}
              </div>
              <div class="alert-cluster__meta">
                <span class="alert-cluster__count">${totalCount} related alerts</span>
                <span class="alert-cluster__time">${window.formatTimeAgo(cluster.timestamp)}</span>
              </div>
            </div>
            <div class="alert-cluster__expand">
              <i class="fas fa-chevron-down"></i>
            </div>
          </div>
          <div class="alert-cluster__items">
            ${this._renderAlert(cluster.primary)}
            ${cluster.related.map(a => this._renderAlert(a)).join('')}
          </div>
        </div>
      `;
    }

    /**
     * Render a single alert item
     */
    _renderAlert(alert) {
      const severity = alert.severity || 'info';
      const severityConfig = this.severityConfig[severity] || this.severityConfig.info;
      const typeIcon = this.typeIcons[alert.type] || this.typeIcons[alert.source] || 'fas fa-bell';

      const message = alert.message || alert.title || 'Alert';
      const description = alert.description || alert.details || '';
      const source = alert.source_name || alert.sensor_name || alert.device_name || '';
      const value = alert.value !== undefined ? `${alert.value}${alert.unit || ''}` : '';

      return `
        <div class="alert-timeline__item alert-timeline__item--${severity}"
             data-alert-id="${alert.id}">
          <div class="alert-timeline__dot" style="background: ${severityConfig.color}"></div>
          <div class="alert-timeline__content">
            <div class="alert-timeline__header">
              <span class="alert-timeline__icon" style="color: ${severityConfig.color}">
                <i class="${typeIcon}"></i>
              </span>
              <span class="alert-timeline__title">${window.escapeHtml(message)}</span>
              <span class="alert-timeline__severity ${severity}">${severityConfig.label}</span>
            </div>
            ${description ? `<p class="alert-timeline__description">${window.escapeHtml(description)}</p>` : ''}
            <div class="alert-timeline__meta">
              ${source ? `<span class="alert-timeline__source"><i class="${typeIcon}"></i> ${window.escapeHtml(source)}</span>` : ''}
              ${value ? `<span class="alert-timeline__value">${window.escapeHtml(value)}</span>` : ''}
              <span class="alert-timeline__time">${window.formatTimeAgo(alert.timestamp)}</span>
            </div>
            ${this.options.showActions ? this._renderActions(alert) : ''}
          </div>
          <button class="alert-dismiss" data-alert-id="${alert.id}" title="Dismiss" aria-label="Dismiss alert">
            <i class="fas fa-times"></i>
          </button>
        </div>
      `;
    }

    /**
     * Render action buttons for an alert
     */
    _renderActions(alert) {
      const actions = alert.actions || this._getDefaultActions(alert);

      if (!actions || actions.length === 0) return '';

      return `
        <div class="alert-timeline__actions">
          ${actions.map(action => `
            <button class="alert-action-btn alert-action-btn--${action.type || 'default'}"
                    data-alert-id="${alert.id}"
                    data-action="${action.action}">
              ${action.icon ? `<i class="${action.icon}"></i>` : ''}
              ${window.escapeHtml(action.label)}
            </button>
          `).join('')}
        </div>
      `;
    }

    /**
     * Get default actions based on alert type
     */
    _getDefaultActions(alert) {
      const type = alert.type || alert.source || 'system';

      switch (type) {
        case 'threshold':
          return [
            { action: 'adjust', label: 'Adjust Threshold', icon: 'fas fa-sliders-h', type: 'primary' },
            { action: 'view', label: 'View History', icon: 'fas fa-chart-line' }
          ];
        case 'sensor':
          return [
            { action: 'calibrate', label: 'Calibrate', icon: 'fas fa-wrench', type: 'primary' },
            { action: 'details', label: 'Details', icon: 'fas fa-info-circle' }
          ];
        case 'device':
        case 'actuator':
          return [
            { action: 'restart', label: 'Restart', icon: 'fas fa-redo', type: 'warning' },
            { action: 'status', label: 'Status', icon: 'fas fa-info-circle' }
          ];
        case 'plant':
          return [
            { action: 'view', label: 'View Plant', icon: 'fas fa-seedling', type: 'primary' }
          ];
        default:
          return [
            { action: 'details', label: 'Details', icon: 'fas fa-info-circle' }
          ];
      }
    }





    /**
     * Get current alert count
     */
    getCount() {
      return this.alerts.length;
    }

    /**
     * Get count by severity
     */
    getCountBySeverity(severity) {
      return this.alerts.filter(a => a.severity === severity).length;
    }

    /**
     * Get summary stats
     */
    getSummary() {
      return {
        total: this.alerts.length,
        critical: this.getCountBySeverity('critical'),
        warning: this.getCountBySeverity('warning'),
        info: this.getCountBySeverity('info'),
        clusters: this.clusters.length
      };
    }

    /**
     * Clear all alerts
     */
    clear() {
      this.alerts = [];
      this.clusters = [];
      this.render();
    }
  }

  /**
   * AlertSummary - Compact summary widget for dashboard KPI
   */
  class AlertSummary {
    constructor(options = {}) {
      this.countElementId = options.countElementId || 'critical-alerts-count';
      this.statusElementId = options.statusElementId || 'alert-status';
      this.badgeElementId = options.badgeElementId || 'alerts-badge';
    }

    /**
     * Update summary display
     */
    update(summary) {
      const countEl = document.getElementById(this.countElementId);
      const statusEl = document.getElementById(this.statusElementId);
      const badgeEl = document.getElementById(this.badgeElementId);

      const total = summary.total || 0;
      const critical = summary.critical || 0;

      if (countEl) {
        countEl.textContent = String(total);
      }

      if (statusEl) {
        if (critical > 0) {
          statusEl.textContent = `${critical} critical`;
          statusEl.className = 'alert-status critical';
        } else if (total > 0) {
          statusEl.textContent = 'Active Alerts';
          statusEl.className = 'alert-status warning';
        } else {
          statusEl.textContent = 'All Clear';
          statusEl.className = 'alert-status success';
        }
      }

      if (badgeEl) {
        if (total > 0) {
          badgeEl.textContent = total > 99 ? '99+' : String(total);
          badgeEl.classList.remove('hidden');
          badgeEl.classList.toggle('critical', critical > 0);
        } else {
          badgeEl.classList.add('hidden');
        }
      }
    }
  }

  // Export to window
  window.AlertTimeline = AlertTimeline;
  window.AlertSummary = AlertSummary;
})();
