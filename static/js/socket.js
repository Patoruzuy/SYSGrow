/**
 * Centralized Socket.IO Management
 * ============================================
 * Handles all real-time communication with the server.
 *
 * Multi-Namespace Architecture:
 * -----------------------------
 * - /devices        : Device sensor readings, unregistered sensor data
 * - /dashboard      : Dashboard snapshot updates (priority metrics)
 * - /alerts         : Alert events
 * - /system         : System/health/activity events
 * - /notifications  : User notifications
 * - /session        : Session events
 *
 * New Event Types (from mqtt_sensor_service):
 * -------------------------------------------
 * - device_sensor_reading  : Full sensor reading (all metrics) -> /devices
 * - dashboard_snapshot     : Priority-selected metrics per unit -> /dashboard
 * - unregistered_sensor_data : Unregistered ESP32 sensor data  -> /devices
 *
 * Unit Room Membership:
 * ---------------------
 * Client joins a per-unit room: unit_<id>
 * Server broadcasts to room, so only relevant data reaches each client.
 *
 * IMPORTANT:
 * Unit switching on the dashboard uses a POST form and does NOT put unit_id in the URL.
 * Therefore, we must read selected unit from:
 *   1) DOM: .page-shell[data-selected-unit-id]  (most reliable for server-rendered pages)
 *   2) localStorage: selected_unit_id           (good cross-page fallback)
 *   3) URL param: ?unit_id=                    (optional)
 */

class SocketManager {
  constructor() {
    // Namespace sockets
    this.sockets = {
      devices: null,
      dashboard: null,
      alerts: null,
      system: null,
      notifications: null,
      session: null,
    };

    this.isConnected = false;

    // Local pub/sub listeners (NOT socket.io listeners)
    this.listeners = new Map();

    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 5;

    // Track room membership
    this.currentUnitId = null;

    // Constants
    this.SELECTED_UNIT_KEY = 'selected_unit_id';

    // WebSocket event names (match backend)
    this.WS_EVENTS = {
      DEVICE_SENSOR_READING: 'device_sensor_reading',
      DASHBOARD_SNAPSHOT: 'dashboard_snapshot',
      UNREGISTERED_SENSOR: 'unregistered_sensor_data',
    };

    this.init();
  }

  /**
   * Initialize Socket.IO connections to multiple namespaces
   */
  init() {
    if (typeof io === 'undefined') {
      console.warn('[Socket] Socket.IO not loaded, real-time updates disabled');
      return;
    }

    const socketOptions = {
      reconnection: true,
      reconnectionDelay: 1000,
      reconnectionDelayMax: 5000,
      reconnectionAttempts: this.maxReconnectAttempts,
      // Backend defaults to polling-only on Windows (see SYSGROW_SOCKETIO_TRANSPORTS).
      // Restricting the client to polling prevents repeated 400 "Invalid transport"
      // logs when the server does not allow websocket upgrades.
      transports: ['polling'],
      timeout: 10000,
    };

    // Connect to all namespaces
    this.sockets.devices = io('/devices', socketOptions);
    this.sockets.dashboard = io('/dashboard', socketOptions);
    this.sockets.alerts = io('/alerts', socketOptions);
    this.sockets.system = io('/system', socketOptions);
    this.sockets.notifications = io('/notifications', socketOptions);
    this.sockets.session = io('/session', socketOptions);

    // Expose socketManager globally for integration (legacy `window.socket` removed)
    if (typeof window !== 'undefined') {
      window.socketManager = this;
    }

    this.setupConnectionHandlers();
    this.setupDataHandlers();
  }

  /**
   * Setup connection event handlers for all namespaces
   */
  setupConnectionHandlers() {
    // Track connection state across namespaces
    const connectedNamespaces = new Set();

    const setupNamespace = (name, socket) => {
      if (!socket) return;

      socket.on('connect', () => {
        console.log(`[Socket] Connected to /${name} namespace`);
        connectedNamespaces.add(name);

        // Consider connected when at least one namespace is up
        if (!this.isConnected) {
          this.isConnected = true;
          this.reconnectAttempts = 0;
          this.emit('connection_status', { connected: true });

          // Join selected unit room
          this.syncUnitRoom();
        }
      });

      socket.on('disconnect', (reason) => {
        console.log(`[Socket] Disconnected from /${name} namespace:`, reason);
        connectedNamespaces.delete(name);

        if (connectedNamespaces.size === 0) {
          this.isConnected = false;
          this.emit('connection_status', { connected: false, reason });
        }
      });

      socket.on('connect_error', (error) => {
        console.error(`[Socket] Connection error on /${name}:`, error);
        this.reconnectAttempts += 1;

        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
          console.error('[Socket] Max reconnection attempts reached');
          this.emit('connection_failed', { error: 'Max reconnection attempts reached' });
        }
      });

      socket.on('error', (data) => {
        console.error(`[Socket] Error on /${name}:`, data);
        this.emit('error', data);
      });
    };

    setupNamespace('devices', this.sockets.devices);
    setupNamespace('dashboard', this.sockets.dashboard);
    setupNamespace('alerts', this.sockets.alerts);
    setupNamespace('system', this.sockets.system);
    setupNamespace('notifications', this.sockets.notifications);
    setupNamespace('session', this.sockets.session);
  }

  /**
   * Setup data event handlers for all namespaces
   *
   * NOTE:
   * Keep internal emitted event names stable.
   * Normalize backend events to consistent internal events.
   */
  setupDataHandlers() {
    // Helper to forward socket events to internal pub/sub
    const forward = (socket, socketEvent, internalEvent = socketEvent) => {
      if (!socket) return;
      socket.on(socketEvent, (data) => {
        this.emit(internalEvent, data);
      });
    };

    // ==========================================================================
    // /devices namespace - New device sensor reading events
    // ==========================================================================
    if (this.sockets.devices) {
      // New: Full device sensor readings (all metrics from a sensor)
      this.sockets.devices.on(this.WS_EVENTS.DEVICE_SENSOR_READING, (data) => {
        console.log('[Socket] Device sensor reading:', data?.sensor_id, data?.sensor_type);
        if (data && data.data && window.SensorFields) {
          data.data = window.SensorFields.standardize(data.data);
        }
        this.emit('device_sensor_reading', data);
      });

      // New: Unregistered sensor data (ESP32 sensors not yet configured)
      this.sockets.devices.on(this.WS_EVENTS.UNREGISTERED_SENSOR, (data) => {
        console.log('[Socket] Unregistered sensor detected:', data?.friendly_name);
        if (data && data.data && window.SensorFields) {
          data.data = window.SensorFields.standardize(data.data);
        }
        this.emit('unregistered_sensor_data', data);
      });

      // Forward other device events
      forward(this.sockets.devices, 'device_status_update');
      forward(this.sockets.devices, 'device_reconnected');
      forward(this.sockets.devices, 'device_disconnected');
      forward(this.sockets.devices, 'energy_update');
      forward(this.sockets.devices, 'device_energy_update');
    }

    // ==========================================================================
    // /dashboard namespace - Dashboard snapshot updates
    // ==========================================================================
    if (this.sockets.dashboard) {
      // New: Dashboard snapshot (priority-selected metrics per unit)
      this.sockets.dashboard.on(this.WS_EVENTS.DASHBOARD_SNAPSHOT, (data) => {
        console.log('[Socket] Dashboard snapshot:', data?.unit_id, Object.keys(data?.metrics || {}));
        if (data && data.metrics && window.SensorFields) {
          data.metrics = window.SensorFields.standardize(data.metrics);
        }
        this.emit('dashboard_snapshot', data);
      });
    }


    // ==========================================================================
    // /alerts namespace
    // ==========================================================================
    if (this.sockets.alerts) {
      forward(this.sockets.alerts, 'alert_created');
      forward(this.sockets.alerts, 'alert_resolved');
    }

    // ==========================================================================
    // /system namespace
    // ==========================================================================
    if (this.sockets.system) {
      // Legacy/compat events used by dashboard UI (if the backend emits them)
      forward(this.sockets.system, 'system_activity');
      forward(this.sockets.system, 'system_stats_update');
      forward(this.sockets.system, 'health_metric_update');
      forward(this.sockets.system, 'sensor_anomaly');
      forward(this.sockets.system, 'anomaly_detected');
      forward(this.sockets.system, 'plant_health_update');
      forward(this.sockets.system, 'health_observation_recorded');
    }
  }

  /**
   * Read the current unit ID from the most reliable sources (in order).
   * @returns {number|null}
   */
  getUnitId() {
    // 1) DOM source of truth for server-rendered pages
    try {
      const shell = document.querySelector('.page-shell');
      const domUnit = shell?.dataset?.selectedUnitId;
      if (domUnit !== undefined && domUnit !== null && String(domUnit).trim() !== '') {
        const parsed = Number(domUnit);
        if (Number.isFinite(parsed)) return parsed;
      }
    } catch (err) {
      console.warn('[Socket] Failed reading unit id from DOM', err);
    }

    // 2) Base layout source of truth (body dataset)
    try {
      const bodyUnit = document.body?.dataset?.activeUnitId;
      if (bodyUnit !== undefined && bodyUnit !== null && String(bodyUnit).trim() !== '') {
        const parsed = Number(bodyUnit);
        if (Number.isFinite(parsed)) return parsed;
      }
    } catch (err) {
      console.warn('[Socket] Failed reading unit id from body dataset', err);
    }

    // 3) localStorage fallback
    try {
      const storedUnit = localStorage.getItem(this.SELECTED_UNIT_KEY);
      if (storedUnit !== null && String(storedUnit).trim() !== '') {
        const parsed = Number(storedUnit);
        if (Number.isFinite(parsed)) return parsed;
      }
    } catch (err) {
      console.warn('[Socket] Failed reading unit id from localStorage', err);
    }

    // 4) URL param fallback (optional)
    try {
      const urlParams = new URLSearchParams(window.location.search);
      const urlUnit = urlParams.get('unit_id');
      if (urlUnit) {
        const parsed = Number(urlUnit);
        if (Number.isFinite(parsed)) return parsed;
      }
    } catch (err) {
      console.warn('[Socket] Failed reading unit id from URL', err);
    }

    // No unit selected
    return null;
  }

  /**
   * Persist unit selection so other pages can reuse it.
   * For "All units", pass null to remove the value.
   */
  setUnitId(unitId) {
    try {
      if (unitId === null || unitId === undefined || unitId === '') {
        localStorage.removeItem(this.SELECTED_UNIT_KEY);
      } else {
        const parsed = Number(unitId);
        if (Number.isFinite(parsed)) {
          localStorage.setItem(this.SELECTED_UNIT_KEY, String(parsed));
        }
      }
    } catch (err) {
      console.warn('[Socket] Failed persisting unit selection:', err);
    }
  }

  /**
   * Ensure we are joined to the correct unit room on ALL namespaces.
   * This should be called on connect and after unit selection changes.
   *
   * Server must support:
   * - join_unit {unit_id}
   * - leave_unit {unit_id} (optional but recommended)
   */
  syncUnitRoom() {
    const desiredUnitId = this.getUnitId();

    // Keep localStorage in sync with what the server rendered (DOM)
    this.setUnitId(desiredUnitId);

    // Handle "All units" view (desiredUnitId === null)
    if (!desiredUnitId) {
      if (this.currentUnitId) {
        console.log(`[Socket] Switching from unit_${this.currentUnitId} to "All units" view`);
        this._leaveUnitRoom(this.currentUnitId);
      }
      this.currentUnitId = null;
      console.log('[Socket] No unit selected; showing all units (not in a specific unit_* room)');
      return;
    }

    // If already in the correct unit, nothing to do
    if (this.currentUnitId === desiredUnitId) return;

    // Leave previous unit room
    if (this.currentUnitId) {
      console.log(`[Socket] Leaving unit room: unit_${this.currentUnitId}`);
      this._leaveUnitRoom(this.currentUnitId);
    }

    // Join new unit room on all namespaces
    console.log(`[Socket] Joining unit room: unit_${desiredUnitId}`);
    this._joinUnitRoom(desiredUnitId);
    this.currentUnitId = desiredUnitId;
  }

  /**
   * Join unit room on all connected namespaces
   */
  _joinUnitRoom(unitId) {
    Object.values(this.sockets).forEach((socket) => {
      if (socket?.connected) {
        try {
          socket.emit('join_unit', { unit_id: unitId });
        } catch (err) {
          console.warn('[Socket] Failed to join unit room:', err);
        }
      }
    });
  }

  /**
   * Leave unit room on all connected namespaces
   */
  _leaveUnitRoom(unitId) {
    Object.values(this.sockets).forEach((socket) => {
      if (socket?.connected) {
        try {
          socket.emit('leave_unit', { unit_id: unitId });
        } catch (err) {
          // Non-fatal: server may not support leave_unit
          console.warn('[Socket] leave_unit not supported or failed (non-fatal):', err);
        }
      }
    });
  }

  /**
   * Register local listener
   * @returns {Function} unsubscribe
   */
  on(event, callback) {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, new Set());
    }
    this.listeners.get(event).add(callback);

    return () => {
      const callbacks = this.listeners.get(event);
      if (callbacks) callbacks.delete(callback);
    };
  }

  /**
   * Emit to local listeners (not socket.io)
   */
  emit(event, data) {
    const callbacks = this.listeners.get(event);
    if (!callbacks) return;

    callbacks.forEach((callback) => {
      try {
        callback(data);
      } catch (error) {
        console.error(`[Socket] Error in ${event} listener:`, error);
      }
    });
  }

  getConnectionStatus() {
    return this.isConnected;
  }

  /**
   * Get a specific namespace socket
   */
  getSocket(namespace = 'devices') {
    return this.sockets[namespace] || this.sockets.devices;
  }

  destroy() {
    console.log('[Socket] Cleaning up SocketManager...');

    Object.entries(this.sockets).forEach(([name, socket]) => {
      try {
        if (socket) {
          socket.disconnect();
        }
      } catch (err) {
        console.warn(`[Socket] ${name} disconnect failed`, err);
      }
    });

    this.sockets = {
      devices: null,
      dashboard: null,
      alerts: null,
      system: null,
      notifications: null,
      session: null,
    };
    this.listeners.clear();
    this.isConnected = false;
    this.currentUnitId = null;
  }
}

// Create singleton instance
const socketManager = new SocketManager();

// Make available globally
if (typeof window !== 'undefined') {
  window.socketManager = socketManager;
  window.SocketManager = SocketManager;
}

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
  socketManager.destroy();
});

// CommonJS support
if (typeof module !== 'undefined' && module.exports) {
  module.exports = socketManager;
  module.exports.SocketManager = SocketManager;
}
