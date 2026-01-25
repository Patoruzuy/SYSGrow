/**
 * Device Health UI Manager
 * ============================================================================
 * Handles all UI rendering, event handling, and real-time updates for
 * device health monitoring. Extends BaseManager for automatic cleanup.
 */
(function() {
  'use strict';

  const BaseManager = window.BaseManager;

  class DeviceHealthUIManager extends BaseManager {
    constructor(dataService) {
      super('DeviceHealthUIManager');

      this.dataService = dataService;
      this.alerts = [];
      this.socketManager = null;

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
      console.log('[DeviceHealthUIManager] Initializing...');

      try {
        // Cache DOM elements
        this._cacheElements();

        // Setup event listeners
        this._setupEventListeners();

        // Load initial data
        await this._loadAllData();

        // Setup real-time updates
        await this._setupRealtimeUpdates();

        console.log('[DeviceHealthUIManager] Initialized successfully');
      } catch (error) {
        console.error('[DeviceHealthUIManager] Initialization failed:', error);
        this.showNotification('Failed to initialize device health monitoring', 'error');
      }
    }

    /**
     * Cache DOM elements
     */
    _cacheElements() {
      this.elements = {
        onlineCount: document.getElementById('online-count'),
        offlineCount: document.getElementById('offline-count'),
        anomalyCount: document.getElementById('anomaly-count'),
        totalDevices: document.getElementById('total-devices'),
        alertsContainer: document.getElementById('alerts-container'),
        actuatorsTable: document.querySelector('#actuators-heading')?.closest('.card')?.querySelector('tbody'),
        sensorsTable: document.querySelector('#sensors-heading')?.closest('.card')?.querySelector('tbody'),
        deviceModal: document.getElementById('device-detail-modal'),
        deviceModalContent: document.getElementById('device-detail-content'),
        refreshAlertsBtn: document.getElementById('refresh-alerts-btn'),
        refreshActuatorsBtn: document.getElementById('refresh-actuators-btn'),
        refreshSensorsBtn: document.getElementById('refresh-sensors-btn')
      };
    }

    /**
     * Setup all event listeners
     */
    _setupEventListeners() {
      // Refresh buttons
      if (this.elements.refreshAlertsBtn) {
        this.addEventListener(this.elements.refreshAlertsBtn, 'click', () => this.refreshAlerts());
      }
      if (this.elements.refreshActuatorsBtn) {
        this.addEventListener(this.elements.refreshActuatorsBtn, 'click', () => this.refreshActuators());
      }
      if (this.elements.refreshSensorsBtn) {
        this.addEventListener(this.elements.refreshSensorsBtn, 'click', () => this.refreshSensors());
      }

      // Initial view device buttons
      document.querySelectorAll('.view-device-btn').forEach(btn => {
        this.addEventListener(btn, 'click', (e) => {
          const deviceId = e.currentTarget.dataset.deviceId;
          const deviceType = e.currentTarget.dataset.deviceType;
          this.showDeviceDetail(deviceId, deviceType);
        });
      });

      // Modal close
      const modalClose = this.elements.deviceModal?.querySelector('.modal-close');
      if (modalClose) {
        this.addEventListener(modalClose, 'click', () => this.closeModal());
      }

      // Close modal on outside click
      if (this.elements.deviceModal) {
        this.addEventListener(this.elements.deviceModal, 'click', (e) => {
          if (e.target === this.elements.deviceModal) {
            this.closeModal();
          }
        });
      }

      // ESC key to close modal
      this.addEventListener(document, 'keydown', (e) => {
        if (e.key === 'Escape' && this.elements.deviceModal && !this.elements.deviceModal.hasAttribute('hidden')) {
          this.closeModal();
        }
      });
    }

    // --------------------------------------------------------------------------
    // Data Loading
    // --------------------------------------------------------------------------

    /**
     * Load all device health data
     */
    async _loadAllData() {
      await Promise.all([
        this.dataService.loadDevices(),
        this.dataService.loadAnomalies()
      ]);

      this.alerts = this.dataService.generateAlerts();
      this._updateStatistics();
      this._updateDeviceTables();
      this._updateAlertsUI();
    }

    // --------------------------------------------------------------------------
    // Statistics Display
    // --------------------------------------------------------------------------

    /**
     * Update statistics display
     */
    _updateStatistics() {
      const stats = this.dataService.getStatistics();

      if (this.elements.onlineCount) {
        this.elements.onlineCount.textContent = stats.online;
      }
      if (this.elements.offlineCount) {
        this.elements.offlineCount.textContent = stats.offline;
      }
      if (this.elements.totalDevices) {
        this.elements.totalDevices.textContent = stats.total;
      }
      if (this.elements.anomalyCount) {
        this.elements.anomalyCount.textContent = stats.anomalies;
      }
    }

    // --------------------------------------------------------------------------
    // Alerts UI
    // --------------------------------------------------------------------------

    /**
     * Update alerts UI
     */
    _updateAlertsUI() {
      if (!this.elements.alertsContainer) return;

      if (this.alerts.length === 0) {
        this.elements.alertsContainer.innerHTML = `
          <div class="empty-state">
            <i class="fas fa-check-circle fa-3x text-success" aria-hidden="true"></i>
            <h3>No Active Alerts</h3>
            <p>All devices are functioning normally.</p>
          </div>
        `;
        return;
      }

      const alertsHTML = this.alerts.map(alert => this._createAlertHTML(alert)).join('');
      this.elements.alertsContainer.innerHTML = alertsHTML;

      // Add event listeners to alert actions
      this.elements.alertsContainer.querySelectorAll('.alert-action-btn').forEach(btn => {
        this.addEventListener(btn, 'click', (e) => this._handleAlertAction(e));
      });
    }

    /**
     * Create HTML for an alert
     */
    _createAlertHTML(alert) {
      const severityClass = alert.severity || 'medium';
      const severityIcon = {
        critical: 'fa-exclamation-circle',
        high: 'fa-exclamation-triangle',
        medium: 'fa-info-circle',
        low: 'fa-check-circle'
      }[severityClass] || 'fa-info-circle';

      const actionsHTML = alert.actions.map(action => {
        const actionLabels = {
          'view-details': 'View Details',
          'acknowledge': 'Acknowledge',
          'investigate': 'Investigate',
          'dismiss': 'Dismiss'
        };

        return `
          <button type="button"
                  class="prediction-alert-button ${action === 'view-details' ? 'primary' : 'secondary'} alert-action-btn"
                  data-alert-id="${this._escapeHtml(alert.id)}"
                  data-action="${this._escapeHtml(action)}"
                  data-device-id="${this._escapeHtml(alert.deviceId)}"
                  data-device-type="${this._escapeHtml(alert.deviceType)}"
                  aria-label="${actionLabels[action] || action}">
            <i class="fas fa-${action === 'view-details' ? 'eye' : action === 'acknowledge' ? 'check' : action === 'investigate' ? 'search' : 'times'}"
               aria-hidden="true"></i>
            ${actionLabels[action] || action}
          </button>
        `;
      }).join('');

      return `
        <div class="prediction-alert ${severityClass}" role="alert" data-alert-id="${this._escapeHtml(alert.id)}">
          <div class="prediction-alert-icon">
            <i class="fas ${severityIcon}" aria-hidden="true"></i>
          </div>
          <div class="prediction-alert-content">
            <div class="prediction-alert-header">
              <h3 class="prediction-alert-title">${this._escapeHtml(alert.title)}</h3>
              <span class="risk-level ${severityClass}">${severityClass}</span>
            </div>
            <p class="prediction-alert-description">
              ${this._escapeHtml(alert.message)}
            </p>
            <div class="prediction-alert-actions">
              ${actionsHTML}
            </div>
          </div>
        </div>
      `;
    }

    /**
     * Handle alert action button clicks
     */
    async _handleAlertAction(event) {
      const btn = event.currentTarget;
      const action = btn.dataset.action;
      const alertId = btn.dataset.alertId;
      const deviceId = btn.dataset.deviceId;
      const deviceType = btn.dataset.deviceType;

      switch (action) {
        case 'view-details':
        case 'investigate':
          await this.showDeviceDetail(deviceId, deviceType);
          break;

        case 'acknowledge':
          await this._acknowledgeAlert(alertId);
          break;

        case 'dismiss':
          await this._dismissAlert(alertId);
          break;

        default:
          console.warn('[DeviceHealthUIManager] Unknown action:', action);
      }
    }

    /**
     * Acknowledge an alert
     */
    async _acknowledgeAlert(alertId) {
      this.alerts = this.alerts.filter(a => a.id !== alertId);
      this._updateAlertsUI();
      this.showNotification('Alert acknowledged', 'success');
    }

    /**
     * Dismiss an alert
     */
    async _dismissAlert(alertId) {
      this.alerts = this.alerts.filter(a => a.id !== alertId);
      this._updateAlertsUI();
      this.showNotification('Alert dismissed', 'success');
    }

    // --------------------------------------------------------------------------
    // Device Tables
    // --------------------------------------------------------------------------

    /**
     * Update device tables
     */
    _updateDeviceTables() {
      this._updateActuatorsTable();
      this._updateSensorsTable();
    }

    /**
     * Update actuators table
     */
    _updateActuatorsTable() {
      if (!this.elements.actuatorsTable) return;

      const actuators = this.dataService.devices.actuators;

      if (actuators.length === 0) {
        const tableCard = this.elements.actuatorsTable.closest('.card');
        const cardBody = tableCard?.querySelector('.card-body');
        if (cardBody) {
          cardBody.innerHTML = `
            <div class="empty-state">
              <i class="fas fa-plug fa-3x" aria-hidden="true"></i>
              <h3>No Actuators Found</h3>
              <p>Add actuators to your units to monitor their health.</p>
            </div>
          `;
        }
        return;
      }

      const rowsHTML = actuators.map(actuator => this._createActuatorRow(actuator)).join('');
      this.elements.actuatorsTable.innerHTML = rowsHTML;

      // Re-attach event listeners
      this.elements.actuatorsTable.querySelectorAll('.view-device-btn').forEach(btn => {
        this.addEventListener(btn, 'click', (e) => {
          const deviceId = e.currentTarget.dataset.deviceId;
          const deviceType = e.currentTarget.dataset.deviceType;
          this.showDeviceDetail(deviceId, deviceType);
        });
      });
    }

    /**
     * Create actuator table row
     */
    _createActuatorRow(actuator) {
      const status = actuator.status || 'unknown';
      const statusClass = status === 'online' ? 'success' : status === 'offline' ? 'danger' : 'warning';
      const stateClass = String(actuator.state || '').toLowerCase() === 'on' ? 'success' : 'secondary';
      const lastSeen = actuator.last_state_change || actuator.updated_at;

      return `
        <tr role="row" class="device-row" data-device-id="${this._escapeHtml(actuator.id)}">
          <td data-label="Device Name">
            <strong>${this._escapeHtml(actuator.name)}</strong>
          </td>
          <td data-label="Type">
            ${this._formatDeviceType(actuator.type)}
          </td>
          <td data-label="Status">
            <span class="status-badge badge-${statusClass}" role="status" aria-label="Status: ${status}">
              ${status.charAt(0).toUpperCase() + status.slice(1)}
            </span>
          </td>
          <td data-label="Last Seen">
            ${lastSeen ?
              `<time datetime="${this._escapeHtml(lastSeen)}">${this._escapeHtml(lastSeen)}</time>` :
              '<span class="text-muted">Never</span>'
            }
          </td>
          <td data-label="State">
            <span class="badge badge-${stateClass}">
              ${actuator.state ? actuator.state.toUpperCase() : 'N/A'}
            </span>
          </td>
          <td data-label="Actions" class="actions-column">
            <button type="button" class="btn btn-sm btn-primary view-device-btn"
                    data-device-id="${this._escapeHtml(actuator.id)}"
                    data-device-type="actuator"
                    aria-label="View details for ${this._escapeHtml(actuator.name)}">
              <i class="fas fa-eye" aria-hidden="true"></i>
              Details
            </button>
          </td>
        </tr>
      `;
    }

    /**
     * Update sensors table
     */
    _updateSensorsTable() {
      if (!this.elements.sensorsTable) return;

      const sensors = this.dataService.devices.sensors;

      if (sensors.length === 0) {
        const tableCard = this.elements.sensorsTable.closest('.card');
        const cardBody = tableCard?.querySelector('.card-body');
        if (cardBody) {
          cardBody.innerHTML = `
            <div class="empty-state">
              <i class="fas fa-thermometer-half fa-3x" aria-hidden="true"></i>
              <h3>No Sensors Found</h3>
              <p>Add sensors to your units to monitor their health.</p>
            </div>
          `;
        }
        return;
      }

      const rowsHTML = sensors.map(sensor => this._createSensorRow(sensor)).join('');
      this.elements.sensorsTable.innerHTML = rowsHTML;

      // Re-attach event listeners
      this.elements.sensorsTable.querySelectorAll('.view-device-btn').forEach(btn => {
        this.addEventListener(btn, 'click', (e) => {
          const deviceId = e.currentTarget.dataset.deviceId;
          const deviceType = e.currentTarget.dataset.deviceType;
          this.showDeviceDetail(deviceId, deviceType);
        });
      });
    }

    /**
     * Create sensor table row
     */
    _createSensorRow(sensor) {
      const status = sensor.status || 'unknown';
      const statusClass = status === 'online' ? 'success' : status === 'offline' ? 'danger' : 'warning';
      const unit = this._getSensorUnit(sensor.type);

      return `
        <tr role="row" class="device-row" data-device-id="${this._escapeHtml(sensor.id)}">
          <td data-label="Sensor Name">
            <strong>${this._escapeHtml(sensor.name)}</strong>
          </td>
          <td data-label="Type">
            ${this._formatDeviceType(sensor.type)}
          </td>
          <td data-label="Status">
            <span class="status-badge badge-${statusClass}" role="status" aria-label="Status: ${status}">
              ${status.charAt(0).toUpperCase() + status.slice(1)}
            </span>
          </td>
          <td data-label="Last Reading">
            ${sensor.last_reading_time ?
              `<time datetime="${this._escapeHtml(sensor.last_reading_time)}">${this._escapeHtml(sensor.last_reading_time)}</time>` :
              '<span class="text-muted">No readings yet</span>'
            }
          </td>
          <td data-label="Current Value">
            ${sensor.last_value !== null && sensor.last_value !== undefined ?
              `<strong>${this._escapeHtml(String(sensor.last_value))}</strong> ${this._escapeHtml(unit)}` :
              '<span class="text-muted">N/A</span>'
            }
          </td>
          <td data-label="Actions" class="actions-column">
            <button type="button" class="btn btn-sm btn-primary view-device-btn"
                    data-device-id="${this._escapeHtml(sensor.id)}"
                    data-device-type="sensor"
                    aria-label="View details for ${this._escapeHtml(sensor.name)}">
              <i class="fas fa-eye" aria-hidden="true"></i>
              Details
            </button>
          </td>
        </tr>
      `;
    }

    // --------------------------------------------------------------------------
    // Device Detail Modal
    // --------------------------------------------------------------------------

    /**
     * Show device detail modal
     */
    async showDeviceDetail(deviceId, deviceType) {
      if (!this.elements.deviceModal || !this.elements.deviceModalContent) return;

      try {
        // Show loading state
        this.elements.deviceModalContent.innerHTML = `
          <div class="loading-state">
            <i class="fas fa-spinner fa-spin fa-3x" aria-hidden="true"></i>
            <p>Loading device details...</p>
          </div>
        `;

        this.elements.deviceModal.removeAttribute('hidden');

        // Get device from data service
        const deviceDetails = this.dataService.getDevice(deviceId, deviceType);
        if (!deviceDetails) {
          throw new Error(`Device not found: ${deviceType} ${deviceId}`);
        }

        // Load health history and connection metrics
        const [healthHistory, connectionMetrics] = await Promise.all([
          this.dataService.loadDeviceHealthHistory(deviceId, deviceType),
          this.dataService.loadConnectionMetrics(deviceId, deviceType)
        ]);

        // Render device details
        this._renderDeviceDetail(deviceDetails, deviceType, healthHistory, connectionMetrics);

      } catch (error) {
        console.error('[DeviceHealthUIManager] showDeviceDetail failed:', error);
        this.elements.deviceModalContent.innerHTML = `
          <div class="empty-state">
            <i class="fas fa-exclamation-circle fa-3x text-danger" aria-hidden="true"></i>
            <h3>Failed to Load Device Details</h3>
            <p>${this._escapeHtml(error.message)}</p>
          </div>
        `;
      }
    }

    /**
     * Render device detail modal content
     */
    _renderDeviceDetail(device, deviceType, healthHistory, connectionMetrics) {
      const isActuator = deviceType === 'actuator';
      const deviceId = device.id;
      const deviceName = device.name;
      const deviceTypeLabel = device.type;
      const status = device.status || 'unknown';
      const statusClass = status === 'online' ? 'success' : status === 'offline' ? 'danger' : 'warning';

      const html = `
        <div class="plant-detail-header">
          <h3>${this._escapeHtml(deviceName)}</h3>
          <p class="text-muted">${this._formatDeviceType(deviceTypeLabel)}</p>
          <span class="status-badge badge-${statusClass}">
            ${status.charAt(0).toUpperCase() + status.slice(1)}
          </span>
        </div>

        <div class="plant-detail-section">
          <h4><i class="fas fa-info-circle" aria-hidden="true"></i> Device Information</h4>
          <dl class="detail-list">
            <dt>Device ID:</dt>
            <dd>${this._escapeHtml(deviceId)}</dd>

            <dt>Status:</dt>
            <dd>
              <span class="status-badge badge-${statusClass}">
                ${status.charAt(0).toUpperCase() + status.slice(1)}
              </span>
            </dd>

            ${isActuator ? `
              <dt>Current State:</dt>
              <dd>
                <span class="badge badge-${String(device.state || '').toLowerCase() === 'on' ? 'success' : 'secondary'}">
                  ${device.state ? device.state.toUpperCase() : 'N/A'}
                </span>
              </dd>

              <dt>Last Seen:</dt>
              <dd>${device.last_state_change ? this._escapeHtml(device.last_state_change) : (device.updated_at ? this._escapeHtml(device.updated_at) : 'Never')}</dd>
            ` : `
              <dt>Current Value:</dt>
              <dd>${device.last_value !== null && device.last_value !== undefined ? `<strong>${this._escapeHtml(String(device.last_value))}</strong> ${this._escapeHtml(this._getSensorUnit(device.type))}` : 'N/A'}</dd>

              <dt>Last Reading:</dt>
              <dd>${device.last_reading_time ? this._escapeHtml(device.last_reading_time) : 'No readings yet'}</dd>
            `}

            <dt>Unit ID:</dt>
            <dd>${this._escapeHtml(device.unit_id || 'N/A')}</dd>
          </dl>
        </div>

        ${Object.keys(connectionMetrics).length > 0 ? `
          <div class="plant-detail-section">
            <h4><i class="fas fa-signal" aria-hidden="true"></i> Connection Metrics</h4>
            <dl class="detail-list">
              ${connectionMetrics.uptime_percentage !== undefined ? `
                <dt>Uptime:</dt>
                <dd>${connectionMetrics.uptime_percentage.toFixed(1)}%</dd>
              ` : ''}

              ${connectionMetrics.average_response_time !== undefined ? `
                <dt>Avg Response Time:</dt>
                <dd>${connectionMetrics.average_response_time.toFixed(0)} ms</dd>
              ` : ''}

              ${connectionMetrics.packet_loss !== undefined ? `
                <dt>Packet Loss:</dt>
                <dd>${connectionMetrics.packet_loss.toFixed(2)}%</dd>
              ` : ''}

              ${connectionMetrics.last_disconnect !== undefined ? `
                <dt>Last Disconnect:</dt>
                <dd>${this._escapeHtml(connectionMetrics.last_disconnect)}</dd>
              ` : ''}

              ${connectionMetrics.reconnect_count !== undefined ? `
                <dt>Reconnects (24h):</dt>
                <dd>${connectionMetrics.reconnect_count}</dd>
              ` : ''}
            </dl>
          </div>
        ` : ''}

        ${healthHistory.length > 0 ? `
          <div class="plant-detail-section">
            <h4><i class="fas fa-history" aria-hidden="true"></i> Health History</h4>
            <div class="health-history-timeline">
              ${healthHistory.slice(0, 10).map(entry => `
                <div class="timeline-entry">
                  <div class="timeline-marker">
                    <span class="health-badge badge-${entry.status === 'online' ? 'success' : 'danger'}">
                      <i class="fas fa-${entry.status === 'online' ? 'check' : 'times'}" aria-hidden="true"></i>
                    </span>
                  </div>
                  <div class="timeline-content">
                    <div class="timeline-header">
                      <strong>${entry.status === 'online' ? 'Online' : 'Offline'}</strong>
                      <time datetime="${this._escapeHtml(entry.timestamp)}">${this._escapeHtml(entry.timestamp)}</time>
                    </div>
                    ${entry.notes ? `
                      <p class="timeline-notes">${this._escapeHtml(entry.notes)}</p>
                    ` : ''}
                  </div>
                </div>
              `).join('')}
            </div>
          </div>
        ` : ''}
      `;

      this.elements.deviceModalContent.innerHTML = html;
    }

    /**
     * Close device detail modal
     */
    closeModal() {
      this.elements.deviceModal?.setAttribute('hidden', '');
    }

    // --------------------------------------------------------------------------
    // Refresh Actions
    // --------------------------------------------------------------------------

    /**
     * Refresh alerts
     */
    async refreshAlerts() {
      const icon = this.elements.refreshAlertsBtn?.querySelector('i');

      try {
        icon?.classList.add('fa-spin');
        await this.dataService.loadAnomalies();
        this.alerts = this.dataService.generateAlerts();
        this._updateAlertsUI();
        this.showNotification('Alerts refreshed successfully', 'success');
      } catch (error) {
        console.error('[DeviceHealthUIManager] refreshAlerts failed:', error);
        this.showNotification('Failed to refresh alerts', 'error');
      } finally {
        icon?.classList.remove('fa-spin');
      }
    }

    /**
     * Refresh actuators
     */
    async refreshActuators() {
      const icon = this.elements.refreshActuatorsBtn?.querySelector('i');

      try {
        icon?.classList.add('fa-spin');
        await this.dataService.loadActuators({ force: true });
        this._updateActuatorsTable();
        this._updateStatistics();
        this.showNotification('Actuators refreshed successfully', 'success');
      } catch (error) {
        console.error('[DeviceHealthUIManager] refreshActuators failed:', error);
        this.showNotification('Failed to refresh actuators', 'error');
      } finally {
        icon?.classList.remove('fa-spin');
      }
    }

    /**
     * Refresh sensors
     */
    async refreshSensors() {
      const icon = this.elements.refreshSensorsBtn?.querySelector('i');

      try {
        icon?.classList.add('fa-spin');
        await this.dataService.loadSensors({ force: true });
        this._updateSensorsTable();
        this._updateStatistics();
        this.showNotification('Sensors refreshed successfully', 'success');
      } catch (error) {
        console.error('[DeviceHealthUIManager] refreshSensors failed:', error);
        this.showNotification('Failed to refresh sensors', 'error');
      } finally {
        icon?.classList.remove('fa-spin');
      }
    }

    // --------------------------------------------------------------------------
    // Real-time Updates
    // --------------------------------------------------------------------------

    /**
     * Setup real-time updates via Socket.io
     */
    async _setupRealtimeUpdates() {
      try {
        const { default: socketManager } = await import('/static/js/socket.js');
        this.socketManager = socketManager;

        // Device status updates
        socketManager.on('device_status_update', (data) => {
          this._handleDeviceStatusUpdate(data);
        });

        // Anomaly detection
        socketManager.on('anomaly_detected', (data) => {
          this._handleAnomalyDetected(data);
        });

        // Device reconnected
        socketManager.on('device_reconnected', (data) => {
          this._handleDeviceReconnected(data);
        });

        // Device disconnected
        socketManager.on('device_disconnected', (data) => {
          this._handleDeviceDisconnected(data);
        });
      } catch (error) {
        console.warn('[DeviceHealthUIManager] Socket.io not available for real-time updates', error);
      }
    }

    /**
     * Handle device status update
     */
    _handleDeviceStatusUpdate(data) {
      console.log('[DeviceHealthUIManager] Device status update:', data);

      this.dataService.updateDevice(data);

      if (data.device_type === 'actuator') {
        this._updateActuatorsTable();
      } else if (data.device_type === 'sensor') {
        this._updateSensorsTable();
      }

      this._updateStatistics();
    }

    /**
     * Handle anomaly detected
     */
    _handleAnomalyDetected(data) {
      console.log('[DeviceHealthUIManager] Anomaly detected:', data);

      this.dataService.addAnomaly(data);
      this.alerts = this.dataService.generateAlerts();
      this._updateAlertsUI();
      this._updateStatistics();

      this.showNotification(`Anomaly detected: ${data.device_name}`, 'warning');
    }

    /**
     * Handle device reconnected
     */
    _handleDeviceReconnected(data) {
      console.log('[DeviceHealthUIManager] Device reconnected:', data);
      this._handleDeviceStatusUpdate({ ...data, status: 'online' });
      this.showNotification(`${data.device_name} reconnected`, 'success');
    }

    /**
     * Handle device disconnected
     */
    _handleDeviceDisconnected(data) {
      console.log('[DeviceHealthUIManager] Device disconnected:', data);
      this._handleDeviceStatusUpdate({ ...data, status: 'offline' });
      this.showNotification(`${data.device_name} disconnected`, 'error');
    }

    // --------------------------------------------------------------------------
    // Helpers
    // --------------------------------------------------------------------------

    /**
     * Format device type for display
     */
    _formatDeviceType(type) {
      if (!type) return 'Unknown';
      return type.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
    }

    /**
     * Get sensor unit
     */
    _getSensorUnit(type) {
      const normalized = String(type || '').toLowerCase();
      if (normalized === 'temperature' || normalized.includes('temp')) return '°C';
      if (normalized === 'humidity' || normalized.includes('humid')) return '%';
      if (normalized === 'soil_moisture' || normalized.includes('soil')) return '%';
      if (normalized.includes('co2')) return 'ppm';
      if (normalized.includes('voc')) return 'ppb';
      if (normalized.includes('lux') || normalized.includes('illuminance') || normalized.includes('light')) return 'lux';
      return '';
    }

    /**
     * Show notification message
     */
    showNotification(message, type = 'info') {
      const flashContainer = document.querySelector('.flash-messages');
      if (flashContainer) {
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

        // Auto-remove after 5 seconds
        setTimeout(() => {
          flash.remove();
        }, 5000);
      } else {
        console.log(`[${type.toUpperCase()}] ${message}`);
      }
    }

    /**
     * Escape HTML to prevent XSS
     */
    _escapeHtml(text) {
      if (text === null || text === undefined) return '';
      const div = document.createElement('div');
      div.textContent = String(text);
      return div.innerHTML;
    }
  }

  // Export to window
  window.DeviceHealthUIManager = DeviceHealthUIManager;
})();
