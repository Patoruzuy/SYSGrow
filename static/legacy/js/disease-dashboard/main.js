/**
 * Disease Dashboard Module Entry Point
 * ============================================================================
 * Initializes the disease monitoring dashboard with proper dependency injection
 * and event handling. Uses the modular pattern with data-service and ui-manager.
 */
(function() {
  'use strict';

  // Module state
  let dataService = null;
  let uiManager = null;
  let isInitialized = false;

  /**
   * Initialize the disease dashboard module
   */
  async function init() {
    if (isInitialized) {
      console.warn('[DiseaseDashboard] Already initialized');
      return;
    }

    // Verify dependencies
    if (!window.API) {
      console.error('[DiseaseDashboard] API not loaded');
      return;
    }

    if (!window.DiseaseDashboardDataService) {
      console.error('[DiseaseDashboard] DiseaseDashboardDataService not loaded');
      return;
    }

    if (!window.DiseaseDashboardUIManager) {
      console.error('[DiseaseDashboard] DiseaseDashboardUIManager not loaded');
      return;
    }

    try {
      // Create services
      dataService = new window.DiseaseDashboardDataService();
      uiManager = new window.DiseaseDashboardUIManager(dataService);

      // Expose for debugging
      window.diseaseDashboardData = dataService;
      window.diseaseDashboardUI = uiManager;

      // Initialize UI (this loads data, sets up chart, and event listeners)
      await uiManager.init();

      isInitialized = true;
      console.log('[DiseaseDashboard] Module initialized successfully');

    } catch (error) {
      console.error('[DiseaseDashboard] Initialization failed:', error);
    }
  }

  /**
   * Refresh all disease dashboard data
   */
  async function refreshAll() {
    if (dataService && uiManager) {
      dataService.clearCache();
      await uiManager._loadAllData();
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

  /**
   * Cleanup when leaving page
   */
  function cleanup() {
    if (uiManager) {
      uiManager.destroy();
    }
  }

  // Wait for DOM ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  // Cleanup on page unload
  window.addEventListener('beforeunload', cleanup);

  // Expose public API
  window.DiseaseDashboard = {
    init,
    refresh: refreshAll,
    getDataService,
    getUIManager,
    cleanup
  };

  // Backward compatibility - expose dashboard instance on window
  Object.defineProperty(window, 'dashboard', {
    get: function() {
      return uiManager;
    }
  });
})();
