/**
 * Settings Page - Main Entry Point
 *
 * Responsibilities:
 * - Validate dependencies and boot the page
 * - Wire global lifecycle (beforeunload guard + cleanup)
 * - Expose a minimal debug surface in dev
 */
(function () {
  'use strict';

  const SettingsApp = {
    cacheService: null,
    dataService: null,
    uiManager: null,

    _requireGlobals(names) {
      const missing = names.filter((n) => typeof window[n] === 'undefined');
      if (missing.length) {
        throw new Error(`Missing dependencies: ${missing.join(', ')}. Check script loading order.`);
      }
    },

    _readSelectedUnitId() {
      // First try data attribute on settings-page
      const settingsPage = document.querySelector('.settings-page');
      if (settingsPage) {
        const raw = settingsPage.dataset.selectedUnit;
        if (raw && raw !== '') {
          const parsed = Number(raw);
          if (Number.isFinite(parsed)) {
            console.log('[Settings] Got unit from data attribute:', parsed);
            return parsed;
          }
        }
      }

      // Fallback: read from unit selector dropdown (server pre-selects the correct option)
      const unitSelector = document.getElementById('schedule-unit-selector');
      if (unitSelector && unitSelector.value) {
        const parsed = Number(unitSelector.value);
        if (Number.isFinite(parsed)) {
          console.log('[Settings] Got unit from dropdown:', parsed);
          return parsed;
        }
      }

      // Second fallback: database unit selector
      const dbUnitSelector = document.getElementById('database-unit-selector');
      if (dbUnitSelector && dbUnitSelector.value) {
        const parsed = Number(dbUnitSelector.value);
        if (Number.isFinite(parsed)) {
          console.log('[Settings] Got unit from db dropdown:', parsed);
          return parsed;
        }
      }

      console.warn('[Settings] No unit ID found from any source');
      return null;
    },

    _showInitError(error) {
      console.error('[Settings] Initialization failed:', error);

      const statusElement = document.getElementById('settings-status');
      if (statusElement) {
        statusElement.textContent = `Failed to initialize settings: ${error.message || String(error)}`;
        statusElement.className = 'settings-status settings-status--error';
      }
    },

    async init() {
      try {
        this._requireGlobals([
          'API',
          'CacheService',
          'BaseManager',
          'SettingsDataService',
          'SettingsUIManager'
        ]);

        const selectedUnitId = this._readSelectedUnitId();
        console.log('[Settings] Selected unit:', selectedUnitId);

        // Cache (30s TTL)
        this.cacheService = new window.CacheService(30000);

        // Data service
        this.dataService = new window.SettingsDataService(window.API, this.cacheService, selectedUnitId);

        // UI manager
        this.uiManager = new window.SettingsUIManager(this.dataService);

        // Initialize UI (BaseManager.safe init wrapper)
        await this.uiManager._safeInit();

        // beforeunload guard (unsaved changes)
        window.addEventListener('beforeunload', this._beforeUnloadGuard);

        // cleanup
        window.addEventListener('pagehide', this.cleanup);

        // Optional debug surface
        window.SettingsDebug = {
          app: this,
          dataService: this.dataService,
          uiManager: this.uiManager,
          cache: this.cacheService,
          getSelectedUnit: () => this.dataService.selectedUnitId,
          setUnit: async (unitId) => {
            this.dataService.setSelectedUnit(unitId);
            return this.uiManager.handleUnitChange(unitId);
          },
          clearCache: () => this.cacheService.clear(),
          reload: async () => {
            this.dataService.invalidateAll?.(); // if you apply the data-service improvement below
            await this.uiManager.loadAllSettings();
          }
        };

        console.log('[Settings] Initialized successfully');
      } catch (error) {
        this._showInitError(error);
      }
    },

    _beforeUnloadGuard(event) {
      try {
        const ui = SettingsApp.uiManager;

        // Prefer an explicit API if present (recommended patch in section 4)
        const hasUnsaved =
          (typeof ui?.hasUnsavedChanges === 'function' && ui.hasUnsavedChanges()) ||
          (ui?.dirtyForms && ui.dirtyForms.size > 0);

        if (!hasUnsaved) return;

        // Browser will show a generic confirmation dialog.
        event.preventDefault();
        event.returnValue = '';
        return '';
      } catch {
        // If guard fails, do not block navigation.
        return;
      }
    },

    cleanup() {
      try {
        // Remove global guards
        window.removeEventListener('beforeunload', SettingsApp._beforeUnloadGuard);
        window.removeEventListener('pagehide', SettingsApp.cleanup);

        // Manager cleanup
        if (SettingsApp.uiManager && typeof SettingsApp.uiManager.cleanup === 'function') {
          SettingsApp.uiManager.cleanup();
        }
      } catch (e) {
        console.warn('[Settings] Cleanup failed:', e);
      }
    }
  };

  // DOM ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => SettingsApp.init());
  } else {
    SettingsApp.init();
  }
})();
