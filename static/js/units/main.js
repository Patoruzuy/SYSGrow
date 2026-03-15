/**
 * Units Module Entry Point
 * ============================================================================
 * Initializes the growth units page with proper dependency injection and
 * event handling. Uses the modular pattern with data-service and ui-manager.
 */
(function () {
  'use strict';

  // Module state
  let dataService = null;
  let uiManager = null;
  let isInitialized = false;

  /**
   * Initialize the units module
   */
  function init() {
    if (isInitialized) {
      console.warn('[Units] Already initialized');
      return;
    }

    // Verify dependencies
    if (!window.CacheService) {
      console.error('[Units] CacheService not loaded');
      return;
    }

    if (!window.API) {
      console.error('[Units] API not loaded');
      return;
    }

    if (!window.UnitsDataService) {
      console.error('[Units] UnitsDataService not loaded');
      return;
    }

    if (!window.UnitsUIManager) {
      console.error('[Units] UnitsUIManager not loaded');
      return;
    }

    try {
      // Create services
      dataService = new window.UnitsDataService();
      uiManager = new window.UnitsUIManager(dataService);

      // Expose for debugging and external access
      window.unitsData = dataService;
      window.unitsUI = uiManager;

      // Initialize UI
      uiManager.init();

      isInitialized = true;
      console.log('[Units] Module initialized successfully');

      // Set up periodic refresh
      setupPeriodicRefresh();

    } catch (error) {
      console.error('[Units] Initialization failed:', error);
    }
  }

  /**
   * Setup periodic environmental data refresh
   */
  function setupPeriodicRefresh() {
    // Refresh environmental data every 60 seconds
    setInterval(() => {
      if (uiManager) {
        uiManager.refreshAllEnvironmentalData();
      }
    }, 60000);
  }

  /**
   * Refresh all unit data (called externally or from other modules)
   */
  function refreshAll() {
    if (uiManager) {
      uiManager.loadUnitsOverview();
    }
  }

  /**
   * Get the current state
   */
  function getState() {
    return uiManager ? uiManager.state : null;
  }

  // Wait for DOM ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    // DOM already loaded, init immediately
    init();
  }

  // Expose public API
  window.Units = {
    init,
    refresh: refreshAll,
    getState
  };

})();
