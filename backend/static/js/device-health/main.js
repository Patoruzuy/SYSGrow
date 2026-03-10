/**
 * Device Health Module Entry Point
 * ============================================================================
 * Initializes the device health monitoring page with proper dependency
 * injection and event handling. Uses the modular pattern with data-service
 * and ui-manager.
 */
(function() {
  'use strict';

  // Module state
  let dataService = null;
  let uiManager = null;
  let isInitialized = false;

  /**
   * Initialize the device health module
   */
  async function init() {
    if (isInitialized) {
      console.warn('[DeviceHealth] Already initialized');
      return;
    }

    // Verify dependencies
    if (!window.API) {
      console.error('[DeviceHealth] API not loaded');
      return;
    }

    if (!window.DeviceHealthDataService) {
      console.error('[DeviceHealth] DeviceHealthDataService not loaded');
      return;
    }

    if (!window.DeviceHealthUIManager) {
      console.error('[DeviceHealth] DeviceHealthUIManager not loaded');
      return;
    }

    try {
      // Create services
      dataService = new window.DeviceHealthDataService();
      uiManager = new window.DeviceHealthUIManager(dataService);

      // Expose for debugging
      window.deviceHealthData = dataService;
      window.deviceHealthUI = uiManager;

      // Initialize UI (this loads data and sets up event listeners)
      await uiManager.init();

      isInitialized = true;
      console.log('[DeviceHealth] Module initialized successfully');

    } catch (error) {
      window.SYSGrow.initError('DeviceHealth', error);
    }
  }

  /**
   * Refresh all device health data
   */
  function refreshAll() {
    if (uiManager) {
      uiManager.refreshActuators();
      uiManager.refreshSensors();
      uiManager.refreshAlerts();
    }
  }

  /**
   * Get the data service instance
   */
  function getDataService() {
    return dataService;
  }

  /**
   * Get the UI manager instance
   */
  function getUIManager() {
    return uiManager;
  }

  // Wait for DOM ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  // Expose public API
  window.DeviceHealth = {
    init,
    refresh: refreshAll,
    getDataService,
    getUIManager
  };

  // Backward compatibility - expose manager on window
  Object.defineProperty(window, 'deviceHealthManager', {
    get: function() {
      return uiManager;
    }
  });
})();
