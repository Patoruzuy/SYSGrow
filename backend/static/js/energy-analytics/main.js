/**
 * Energy Analytics Module Entry Point
 * ============================================================================
 * Initializes the energy analytics dashboard with proper dependency injection
 * and event handling. Uses the modular pattern with data-service and ui-manager.
 */
(function() {
  'use strict';

  // Module state
  let dataService = null;
  let uiManager = null;
  let isInitialized = false;

  /**
   * Initialize the energy analytics module
   */
  async function init() {
    if (isInitialized) {
      console.warn('[EnergyAnalytics] Already initialized');
      return;
    }

    // Verify dependencies
    if (!window.API) {
      console.error('[EnergyAnalytics] API not loaded');
      return;
    }

    if (!window.EnergyAnalyticsDataService) {
      console.error('[EnergyAnalytics] EnergyAnalyticsDataService not loaded');
      return;
    }

    if (!window.EnergyAnalyticsUIManager) {
      console.error('[EnergyAnalytics] EnergyAnalyticsUIManager not loaded');
      return;
    }

    try {
      // Create services
      dataService = new window.EnergyAnalyticsDataService();
      uiManager = new window.EnergyAnalyticsUIManager(dataService);

      // Expose for debugging
      window.energyAnalyticsData = dataService;
      window.energyAnalyticsUI = uiManager;

      // Initialize UI (this loads data, sets up chart, and event listeners)
      await uiManager.init();

      isInitialized = true;
      console.log('[EnergyAnalytics] Module initialized successfully');

    } catch (error) {
      console.error('[EnergyAnalytics] Initialization failed:', error);
    }
  }

  /**
   * Refresh all energy analytics data
   */
  async function refreshAll() {
    if (dataService && uiManager) {
      dataService.clearCache();
      await uiManager._loadAllData();
      await uiManager.updateChart();
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
  window.EnergyAnalytics = {
    init,
    refresh: refreshAll,
    getDataService,
    getUIManager,
    cleanup
  };

  // Backward compatibility - expose manager on window
  Object.defineProperty(window, 'energyAnalyticsManager', {
    get: function() {
      return uiManager;
    }
  });
})();
