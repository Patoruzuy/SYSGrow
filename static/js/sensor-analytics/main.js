/**
 * Sensor Analytics - Main entry point
 * ============================================================================
 * - DOMContentLoaded safe init
 * - Initializes DataService and UIManager
 * - Optional debugging via localStorage "sensor-analytics:debug"
 */
(function () {
  'use strict';

  let dataService;
  let uiManager;

  const DEBUG = localStorage.getItem('sensor-analytics:debug') === '1';

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init, { once: true });
  } else {
    init();
  }

  async function init() {
    try {
      // Check for required dependencies
      if (!window.CacheService) {
        throw new Error('CacheService not loaded. Ensure cache-service.js is loaded first.');
      }

      if (!window.BaseManager) {
        throw new Error('BaseManager not loaded. Ensure base-manager.js is loaded first.');
      }

      if (!window.API) {
        throw new Error('API not loaded. Ensure api.js is loaded first.');
      }

      // Read selected unit from DOM (server-rendered)
      const pageShell = document.querySelector('.page-shell');
      const raw = pageShell?.dataset?.selectedUnitId ?? null;

      const parsed = raw !== null && raw !== '' ? parseInt(raw, 10) : null;
      const selectedUnitId = Number.isFinite(parsed) ? parsed : null;

      // Initialize data service
      dataService = new window.SensorAnalyticsDataService();
      dataService.init(selectedUnitId);

      // Initialize UI manager
      uiManager = new window.SensorAnalyticsUIManager(dataService);
      await uiManager._safeInit();

      // Expose only in debug mode
      if (DEBUG) {
        window.SensorAnalytics = { dataService, uiManager, version: '1.0.0' };
        console.log('[SensorAnalytics] Debug mode enabled. Access via window.SensorAnalytics');
      }

      console.log('[SensorAnalytics] Initialized successfully');
    } catch (error) {
      window.SYSGrow.initError('SensorAnalytics', error);
    }
  }

  // Cleanup on page unload
  window.addEventListener('beforeunload', () => {
    try {
      uiManager?.destroy?.();
    } catch (error) {
      console.warn('[SensorAnalytics] Cleanup error:', error);
    }
  });

  // Expose initialization status (useful for tests/debugging)
  window.SensorAnalyticsStatus = {
    get isInitialized() {
      return Boolean(dataService && uiManager);
    },
    get dataService() {
      return dataService;
    },
    get uiManager() {
      return uiManager;
    },
  };
})();
