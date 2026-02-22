/**
 * Plants Hub - Main Entry Point
 * ============================================
 * Initializes the Plants Hub dashboard
 */

(function() {
    'use strict';

    // Wait for DOM to be ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    async function init() {
        try {
            // Initialize data service
            const dataService = new PlantsDataService();

            // Initialize UI manager
            const uiManager = new PlantsUIManager(dataService);
            await uiManager._safeInit();

            // Make globally available for debugging
            window.plantsHub = {
                dataService,
                uiManager,
                version: '2.0.0'
            };

            // Global delegated handlers only when the UI manager failed to init.
            if (!uiManager.initialized) {
                document.body.addEventListener('click', (evt) => {
                    const btn = evt.target.closest && evt.target.closest('[data-action]');
                    if (!btn) return;
                    const action = btn.dataset.action;
                    const plantId = btn.dataset.plantId;
                    const unitId = btn.dataset.unitId;

                    if (!action) return;

                    if (action === 'view-details') {
                        evt.preventDefault();
                        if (window.PlantDetailsModal) {
                            const modal = new window.PlantDetailsModal();
                            modal.open({ plantId: Number(plantId), unitId: Number(unitId) });
                            return;
                        }
                    }

                    if (action === 'link-sensor') {
                        evt.preventDefault();
                        const modal = document.getElementById('link-sensor-modal');
                        const hidden = document.getElementById('link-plant-id');
                        if (hidden) hidden.value = plantId;
                        if (modal) {
                            modal.hidden = false;
                            modal.classList.add('is-open');
                            modal.setAttribute('aria-hidden', 'false');
                        }
                    }

                    if (action === 'delete-plant') {
                        evt.preventDefault();
                        (async () => {
                            if (!confirm('Delete this plant?')) return;
                            try {
                                await window.API.Plant.removePlant(Number(unitId), Number(plantId));
                                window.location.reload();
                            } catch (err) {
                                console.error('Failed to delete plant', err);
                                if (window.showNotification) {
                                    window.showNotification('Failed to delete plant', 'error');
                                }
                            }
                        })();
                    }
                });
            }

            console.log('[Plants Hub] Initialized successfully');
        } catch (error) {
            window.SYSGrow.initError('PlantsHub', error);
        }
    }
})();
