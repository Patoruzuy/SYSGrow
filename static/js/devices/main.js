/**
 * Devices Page - Main Entry Point
 * ============================================
 * Initializes the Devices management dashboard
 */

(function() {
    'use strict';

    // Export for backward compatibility with existing code
    let dataService;
    let uiManager;

    /**
     * Initialize the devices view
     * Called from existing templates with sensors data
     */
    function initDevicesView(sensors) {
        // Wait for DOM to be ready
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => init(sensors));
        } else {
            init(sensors);
        }
    }

    /**
     * Main initialization function
     */
    async function init(sensors) {
        try {
            // Get unit ID from DOM
            const unitIdEl = document.getElementById('selected-unit-id');
            const selectedUnitId = parseInt(unitIdEl?.value || "1", 10);

            // Initialize data service
            dataService = new DevicesDataService();
            dataService.init(sensors, selectedUnitId);

            // Initialize UI manager
            uiManager = new DevicesUIManager(dataService);
            await uiManager._safeInit();

            // Make globally available for debugging
            window.devicesHub = {
                dataService,
                uiManager,
                version: '2.0.0'
            };

            console.log('[Devices] Initialization complete');
        } catch (error) {
            console.error('[Devices] Initialization failed:', error);
        }
    }

    // Export initDevicesView globally for backward compatibility
    window.initDevicesView = initDevicesView;

})();
