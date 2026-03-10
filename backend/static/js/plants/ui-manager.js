/**
 * Plants UI Manager
 * ============================================
 * Handles UI rendering and state management for Plants Hub
 */

class PlantsUIManager extends BaseManager {
    constructor(dataService) {
        super('PlantsUIManager');
        if (!dataService) {
            throw new Error('dataService is required for PlantsUIManager');
        }
        this.dataService = dataService;
        this.currentTab = 'health';
        this.currentFilter = 'all';
        this.plants = []; // Store plants for use in selects
        this.units = [];
        this.plantDetailsModal = null;
        this.latestHealthData = null;
        this.latestDiseaseRisk = null;
        this.latestDiseaseHistory = [];
        this.latestHarvestInsights = null;
        this.selectedUnitId = this._readSelectedUnitId();
    }

    async init() {
        await this.loadAndRender();
        this.bindEvents();
    }

    bindEvents() {
        // Tab switching
        this.addDelegatedListener(
            document.body,
            'click',
            '[data-tab]',
            (e) => this.switchTab(e.target.dataset.tab)
        );

        // Filter buttons
        this.addDelegatedListener(
            document.body,
            'click',
            '.filter-btn',
            (e) => this.filterPlants(e.target.dataset.filter)
        );

        // Refresh button
        const refreshBtn = document.getElementById('refresh-btn');
        if (refreshBtn) {
            this.addEventListener(refreshBtn, 'click', () => this.refresh());
        }

        // Search
        const searchInput = document.getElementById('plants-search');
        if (searchInput) {
            this.addEventListener(searchInput, 'input', (e) => this.searchPlants(e.target.value));
        }

        // Guide search
        const guideSearchInput = document.getElementById('guide-search-input');
        if (guideSearchInput) {
            this.addEventListener(guideSearchInput, 'input', (e) => this.searchGuide(e.target.value));
        }

        // Import shared profile tokens
        this.addDelegatedListener(
            document.body,
            'click',
            '[data-action="import-plant-profile"]',
            () => this.handleImportPlantProfile()
        );

        this.addDelegatedListener(
            document.body,
            'click',
            '[data-action="clear-plant-profile"]',
            () => this._resetPlantProfileSelection()
        );

        // Modal trigger buttons
        const addPlantBtn = document.getElementById('add-plant-btn');
        if (addPlantBtn) {
            this.addEventListener(addPlantBtn, 'click', () => this.openAddPlantModal());
        }

        const addObservationBtn = document.getElementById('add-observation-btn');
        if (addObservationBtn) {
            this.addEventListener(addObservationBtn, 'click', () => this.openObservationModal());
        }

        const healthDetailsBtn = document.getElementById('health-details-btn');
        if (healthDetailsBtn) {
            this.addEventListener(healthDetailsBtn, 'click', () => this.openHealthDetailsModal());
        }

        // Link sensor modal form handlers
        const linkSensorForm = document.getElementById('link-sensor-form');
        if (linkSensorForm) {
            this.addEventListener(linkSensorForm, 'submit', (e) => this.handleLinkSensorSubmit(e));
        }

        const cancelLink = document.getElementById('cancel-link-sensor');
        if (cancelLink) {
            this.addEventListener(cancelLink, 'click', () => this.closeAllModals());
        }

        const addNutrientsBtn = document.getElementById('add-nutrients-btn');
        if (addNutrientsBtn) {
            this.addEventListener(addNutrientsBtn, 'click', () => this.openNutrientsModal());
        }

        const cancelObservationBtn = document.getElementById('cancel-observation');
        if (cancelObservationBtn) {
            this.addEventListener(cancelObservationBtn, 'click', () => this.closeAllModals());
        }

        const cancelNutrientsBtn = document.getElementById('cancel-nutrients');
        if (cancelNutrientsBtn) {
            this.addEventListener(cancelNutrientsBtn, 'click', () => this.closeAllModals());
        }

        const recordHarvestBtn = document.getElementById('record-harvest-btn');
        if (recordHarvestBtn) {
            this.addEventListener(recordHarvestBtn, 'click', () => this.openHarvestModal());
        }

        // Quick action buttons
        const bulkNutrientBtn = document.getElementById('bulk-nutrient-btn');
        if (bulkNutrientBtn) {
            this.addEventListener(bulkNutrientBtn, 'click', () => this.openBulkNutrientModal());
        }

        const exportJournalBtn = document.getElementById('export-journal-btn');
        if (exportJournalBtn) {
            this.addEventListener(exportJournalBtn, 'click', () => this.exportJournal());
        }

        const viewGuideBtn = document.getElementById('view-guide-btn');
        if (viewGuideBtn) {
            this.addEventListener(viewGuideBtn, 'click', () => this.scrollToGuide());
        }

        // Form submissions
        const observationForm = document.getElementById('add-observation-form');
        if (observationForm) {
            this.addEventListener(observationForm, 'submit', (e) => this.handleObservationSubmit(e));
        }

        const harvestForm = document.getElementById('harvest-form');
        if (harvestForm) {
            this.addEventListener(harvestForm, 'submit', (e) => this.handleHarvestSubmit(e));
        }

        const resolveDiseaseForm = document.getElementById('resolve-disease-form');
        if (resolveDiseaseForm) {
            this.addEventListener(resolveDiseaseForm, 'submit', (e) => this.handleResolveDiseaseSubmit(e));
        }

        const predictionFeedbackForm = document.getElementById('prediction-feedback-form');
        if (predictionFeedbackForm) {
            this.addEventListener(predictionFeedbackForm, 'submit', (e) => this.handlePredictionFeedbackSubmit(e));
        }

        const predictionActualOccurred = document.getElementById('prediction-actual-occurred');
        if (predictionActualOccurred) {
            this.addEventListener(predictionActualOccurred, 'change', (e) => {
                this.togglePredictionOutcomeFields(String(e.target.value).toLowerCase() === 'true');
            });
        }

        const predictionFeedbackBtn = document.getElementById('prediction-feedback-btn');
        if (predictionFeedbackBtn) {
            this.addEventListener(predictionFeedbackBtn, 'click', () => this.openPredictionFeedbackModal());
        }

        this.addDelegatedListener(
            document.body,
            'click',
            '[data-action="resolve-disease"]',
            (e) => {
                e.preventDefault();
                const trigger = e.target.closest('[data-action="resolve-disease"]');
                if (!trigger) return;
                this.openResolveDiseaseModal(trigger.dataset.occurrenceId);
            }
        );

        this.addDelegatedListener(
            document.body,
            'click',
            '[data-action="feedback-risk"]',
            (e) => {
                e.preventDefault();
                const trigger = e.target.closest('[data-action="feedback-risk"]');
                if (!trigger) return;
                this.openPredictionFeedbackModal({
                    unitId: trigger.dataset.unitId,
                    diseaseType: trigger.dataset.diseaseType,
                    riskLevel: trigger.dataset.riskLevel,
                    riskScore: trigger.dataset.riskScore,
                });
            }
        );

        // Plant card actions are nested in clickable cards, so route all actions
        // through one delegated handler and suppress parent navigation.
        this.addEventListener(
            document.body,
            'click',
            (e) => {
                const trigger = e.target.closest('[data-action]');
                if (!trigger) return;

                const action = trigger.dataset?.action;
                const plantId = trigger.dataset?.plantId;
                const unitId = trigger.dataset?.unitId;

                if (!action || !['view-details', 'record-observation', 'link-sensor', 'delete-plant'].includes(action)) {
                    return;
                }

                e.preventDefault();
                e.stopPropagation();

                if (action === 'view-details') {
                    this.openPlantDetails(plantId, unitId);
                    return;
                }

                if (action === 'record-observation') {
                    this.openPlantDetails(plantId);
                    return;
                }

                if (action === 'link-sensor') {
                    this.openLinkSensorModal(plantId);
                    return;
                }

                if (action === 'delete-plant') {
                    this.handleDeletePlantClick(trigger);
                }
            },
            { capture: true }
        );

        // Modal close buttons (delegated)
        this.addDelegatedListener(
            document.body,
            'click',
            '.modal-close',
            () => this.closeAllModals()
        );

        // Backdrop click: close when clicking the modal container itself
        this.addEventListener(
            document.body,
            'click',
            (e) => {
                const modal = e.target;
                if (modal && modal.classList && modal.classList.contains('modal')) {
                    this.closeAllModals();
                }
            }
        );
    }

    async loadAndRender() {
        try {
            const data = await this.dataService.loadAll();
            
            // Store plants for use in selects - MUST happen before rendering guide
            this.plants = data.plantsHealth?.plants || [];
            this.units = this._collectUnits(this.plants);
            this.selectedUnitId = this._resolveActiveUnitId();
            this.log(`Stored ${this.plants.length} plants for selects`);

            const diseaseHistoryParams = {
                unit_id: this.selectedUnitId || undefined,
                limit: 8,
            };
            const diseaseStatsParams = {
                unit_id: this.selectedUnitId || undefined,
                days: 90,
            };
            const diseaseAccuracyParams = { days: 90 };

            const [diseaseHistoryResult, diseaseStatsResult, diseaseAccuracyResult] = await Promise.allSettled([
                this.dataService.loadDiseaseHistory(diseaseHistoryParams),
                this.dataService.loadDiseaseStatistics(diseaseStatsParams),
                this.dataService.loadDiseasePredictionAccuracy(diseaseAccuracyParams),
            ]);

            const diseaseHistory = this._settledValue(diseaseHistoryResult, { occurrences: [] });
            const diseaseStats = this._settledValue(diseaseStatsResult, {});
            const diseaseAccuracy = this._settledValue(diseaseAccuracyResult, {});

            let harvestInsights = {
                unitStats: null,
                growthCycles: null,
                comparison: null,
                environment: null,
            };

            if (this.selectedUnitId) {
                const [unitStatsResult, growthCyclesResult] = await Promise.allSettled([
                    this.dataService.loadUnitHarvestStats(this.selectedUnitId, 10),
                    this.dataService.loadGrowthCycleComparison(this.selectedUnitId, 10),
                ]);

                harvestInsights.unitStats = this._settledValue(unitStatsResult, null);
                harvestInsights.growthCycles = this._settledValue(growthCyclesResult, null);

                const compareIds = (harvestInsights.growthCycles?.harvests || [])
                    .slice(0, 3)
                    .map((harvest) => harvest.harvest_id)
                    .filter((value) => Number.isFinite(Number(value)) && Number(value) > 0);
                const latestWindow = this._latestHarvestWindow(harvestInsights.growthCycles);

                const [comparisonResult, environmentResult] = await Promise.allSettled([
                    compareIds.length >= 2
                        ? this.dataService.loadHarvestComparison(compareIds)
                        : Promise.resolve({ harvest_count: 0, comparisons: [] }),
                    latestWindow
                        ? this.dataService.loadHarvestEnvironment(this.selectedUnitId, latestWindow)
                        : Promise.resolve(null),
                ]);

                harvestInsights.comparison = this._settledValue(comparisonResult, { harvest_count: 0, comparisons: [] });
                harvestInsights.environment = this._settledValue(environmentResult, null);
            }
            
            this.renderHealthOverview(data.plantsHealth);
            this.renderHealthCards(data.plantsHealth.plants);
            this.renderHealthScore(data.healthScore);
            this.renderDiseaseRisk(data.diseaseRisk);
            this.renderDiseaseTracking({
                history: diseaseHistory,
                statistics: diseaseStats,
                accuracy: diseaseAccuracy,
            });
            this.renderJournal(data.journal.entries);
            this.renderHarvests(data.harvests.harvests);
            this.renderHarvestInsights(harvestInsights);
            this.renderGuide(data.plantsGuide.plants);
            this.renderAIStatus();
            this.populatePlantSelects();

            this.log('Data loaded and rendered successfully');
        } catch (error) {
            this.error('Failed to load plants data:', error);
            this.showError(
                document.querySelector('.plants-content'),
                'Failed to load plants data. Please try again.'
            );
        }
    }

    renderHealthOverview(healthData) {
        if (!healthData) return;
        this.latestHealthData = healthData;

        // Use backend-provided summary if available, otherwise calculate from plants
        const summary = healthData.summary;
        if (summary) {
            // Use pre-computed summary from backend
            this._updateStat('total-plants', summary.total || 0);
            this._updateStat('healthy-count', summary.healthy || 0);
            this._updateStat('stressed-count', summary.stressed || 0);
            this._updateStat('diseased-count', summary.diseased || 0);
        } else if (healthData.plants) {
            // Fallback: calculate from plants array (legacy support)
            const plants = healthData.plants;
            const healthyCount = plants.filter(p => !p.current_health_status || p.current_health_status === 'healthy').length;
            const stressedCount = plants.filter(p => p.current_health_status === 'stressed').length;
            const diseasedCount = plants.filter(p => p.current_health_status === 'diseased').length;

            this._updateStat('total-plants', plants.length);
            this._updateStat('healthy-count', healthyCount);
            this._updateStat('stressed-count', stressedCount);
            this._updateStat('diseased-count', diseasedCount);
        }
    }

    renderHealthCards(plants) {
        const container = document.getElementById('plants-list');
        if (!container) return;

        if (!plants || plants.length === 0) {
            this.showEmpty(container, 'No plants found');
            return;
        }

        container.innerHTML = plants.map(plant => this._plantCardHTML(plant)).join('');
    }

    renderHealthScore(score) {
        const scoreEl = document.getElementById('health-score');
        if (scoreEl) {
            scoreEl.textContent = score || 0;
            // Animate SVG gauge
            const circle = document.getElementById('health-circle');
            if (circle) {
                const max = 339.292;
                const offset = max * (1 - (score || 0) / 100);
                circle.style.transition = 'stroke-dashoffset 0.6s ease, stroke 0.4s ease';
                circle.style.strokeDashoffset = offset;
                // Color thresholds
                if (score >= 80) {
                    circle.style.stroke = 'var(--success-500)';
                } else if (score >= 50) {
                    circle.style.stroke = 'var(--warning-500)';
                } else {
                    circle.style.stroke = 'var(--danger-500)';
                }
            }
            // Update status title and message
            const statusTitle = document.getElementById('status-title');
            const statusMessage = document.getElementById('status-message');
            if (statusTitle) {
                statusTitle.textContent = score >= 80 ? 'Excellent Health' : score >= 50 ? 'Fair Health' : 'Needs Attention';
            }
            if (statusMessage) {
                statusMessage.textContent = score >= 80 ? 'Your plants are thriving!' : score >= 50 ? 'Some plants need attention' : 'Multiple issues detected';
            }
        }
    }

    renderDiseaseRisk(riskData) {
        const container = document.getElementById('disease-units');
        const summaryContainer = document.getElementById('disease-risk-summary');
        if (!container) return;
        this.latestDiseaseRisk = riskData;

        // Check if disease risk data is available
        if (!riskData || riskData.length === 0 || (Array.isArray(riskData) && riskData.length === 0)) {
            if (summaryContainer) {
                summaryContainer.innerHTML = `
                    <div class="info-state">
                        <i class="fas fa-info-circle"></i>
                        <p>Disease risk prediction is not available</p>
                        <small>Ensure the ML service is running to enable disease risk assessment</small>
                    </div>
                `;
            }
            container.innerHTML = `
                <div class="info-state">
                    <i class="fas fa-info-circle"></i>
                    <p>Disease risk prediction service is not available</p>
                    <small>Ensure the ML service is running to enable disease risk assessment</small>
                </div>
            `;
            return;
        }

        // If riskData has units property
        const units = riskData.units || riskData;
        if (!units || units.length === 0) {
            if (summaryContainer) {
                summaryContainer.innerHTML = `
                    <div class="info-state">
                        <i class="fas fa-info-circle"></i>
                        <p>No disease risk data available</p>
                    </div>
                `;
            }
            this.showEmpty(container, 'No disease risk data available');
            return;
        }

        if (summaryContainer) {
            const summary = riskData.summary || this._computeRiskSummary(units);
            const mostCommon = summary?.most_common_risk
                ? this._formatDiseaseType(summary.most_common_risk)
                : 'None';
            summaryContainer.innerHTML = `
                <div class="risk-card">
                    <div class="risk-value">${summary?.total_units ?? units.length}</div>
                    <div class="risk-label">Units</div>
                </div>
                <div class="risk-card">
                    <div class="risk-value">${summary?.high_risk_units ?? 0}</div>
                    <div class="risk-label">High Risk</div>
                </div>
                <div class="risk-card">
                    <div class="risk-value">${summary?.critical_risk_units ?? 0}</div>
                    <div class="risk-label">Critical</div>
                </div>
                <div class="risk-card">
                    <div class="risk-value">${mostCommon}</div>
                    <div class="risk-label">Top Risk</div>
                </div>
            `;
        }

        container.innerHTML = units.map(unit => this._riskCardHTML(unit)).join('');
    }

    renderDiseaseTracking({ history, statistics, accuracy }) {
        const summaryContainer = document.getElementById('disease-ops-summary');
        const historyContainer = document.getElementById('disease-history-list');
        this.latestDiseaseHistory = history?.occurrences || [];

        if (summaryContainer) {
            const totalOccurrences = Number(statistics?.total_occurrences || 0);
            const activeCount = Number(statistics?.active_count || 0);
            const resolvedCount = Number(statistics?.resolved_count || 0);
            const hasAccuracyMetrics = !accuracy?.error && accuracy?.accuracy !== undefined && accuracy?.accuracy !== null;
            const accuracyValue = hasAccuracyMetrics ? Number(accuracy?.accuracy) : null;
            const precisionValue = !accuracy?.error && accuracy?.precision !== undefined && accuracy?.precision !== null
                ? Number(accuracy?.precision)
                : null;
            const avgResolution = statistics?.avg_resolution_days;

            summaryContainer.innerHTML = `
                <div class="risk-card">
                    <div class="risk-value">${activeCount}</div>
                    <div class="risk-label">Active Cases</div>
                </div>
                <div class="risk-card">
                    <div class="risk-value">${resolvedCount}</div>
                    <div class="risk-label">Resolved</div>
                </div>
                <div class="risk-card">
                    <div class="risk-value">${totalOccurrences}</div>
                    <div class="risk-label">Cases (90d)</div>
                </div>
                <div class="risk-card">
                    <div class="risk-value">${accuracyValue === null ? '--' : this._formatPercentage(accuracyValue, 0)}</div>
                    <div class="risk-label">Prediction Accuracy</div>
                </div>
                <div class="risk-card">
                    <div class="risk-value">${avgResolution ?? '--'}</div>
                    <div class="risk-label">Avg Resolve Days</div>
                </div>
                <div class="risk-card">
                    <div class="risk-value">${precisionValue === null ? '--' : precisionValue.toFixed(2)}</div>
                    <div class="risk-label">Precision</div>
                </div>
            `;
        }

        if (!historyContainer) return;

        if (!this.latestDiseaseHistory.length) {
            this.showEmpty(historyContainer, 'No confirmed disease cases recorded yet');
            return;
        }

        historyContainer.innerHTML = this.latestDiseaseHistory
            .map((occurrence) => this._diseaseHistoryItemHTML(occurrence))
            .join('');
    }

    renderJournal(entries) {
        const container = document.getElementById('journal-entries');
        if (!container) return;

        if (!entries || entries.length === 0) {
            this.showEmpty(container, 'No journal entries yet');
            return;
        }

        container.innerHTML = entries.map(entry => this._journalEntryHTML(entry)).join('');
    }

    renderHarvests(harvests) {
        const container = document.getElementById('recent-harvests');
        if (!container) return;

        if (!harvests || harvests.length === 0) {
            this.showEmpty(container, 'No harvests recorded');
            return;
        }

        container.innerHTML = harvests.map(h => this._harvestItemHTML(h)).join('');
    }

    renderHarvestInsights(insights) {
        const summaryContainer = document.getElementById('harvest-insights-summary');
        const cyclesContainer = document.getElementById('harvest-cycle-comparison');
        const environmentContainer = document.getElementById('harvest-environment-summary');
        this.latestHarvestInsights = insights;

        if (summaryContainer) {
            const statistics = insights?.growthCycles?.statistics || {};
            const bestPerformers = insights?.growthCycles?.best_performers || {};
            const totalCycles = Number(insights?.growthCycles?.harvest_count || 0);
            const yieldAverage = statistics?.yield_grams?.avg;
            const efficiencyAverage = statistics?.efficiency_grams_per_kwh?.avg;
            const bestYield = bestPerformers?.highest_yield?.value;
            const bestQuality = bestPerformers?.highest_quality?.value;

            summaryContainer.innerHTML = `
                <div class="risk-card">
                    <div class="risk-value">${totalCycles}</div>
                    <div class="risk-label">Cycles Compared</div>
                </div>
                <div class="risk-card">
                    <div class="risk-value">${this._formatWeight(yieldAverage)}</div>
                    <div class="risk-label">Avg Yield</div>
                </div>
                <div class="risk-card">
                    <div class="risk-value">${this._formatNumber(efficiencyAverage, 1, '--')}</div>
                    <div class="risk-label">g / kWh</div>
                </div>
                <div class="risk-card">
                    <div class="risk-value">${this._formatWeight(bestYield)}</div>
                    <div class="risk-label">Best Yield</div>
                </div>
                <div class="risk-card">
                    <div class="risk-value">${this._formatNumber(bestQuality, 1, '--')}</div>
                    <div class="risk-label">Best Quality</div>
                </div>
            `;
        }

        if (cyclesContainer) {
            const cycles = insights?.growthCycles?.harvests || [];
            const trendRows = this._normalizeHarvestTrendRows(insights?.unitStats);

            if (!cycles.length && !trendRows.length) {
                this.showEmpty(cyclesContainer, 'Harvest analytics will appear after you record completed cycles');
            } else {
                cyclesContainer.innerHTML = `
                    ${cycles.length ? `
                        <div class="analytics-section-block">
                            <h4>Recent Growth Cycles</h4>
                            <div class="analytics-list">
                                ${cycles.slice(0, 5).map((cycle) => this._growthCycleCardHTML(cycle)).join('')}
                            </div>
                        </div>
                    ` : ''}
                    ${trendRows.length ? `
                        <div class="analytics-section-block">
                            <h4>Efficiency Trend</h4>
                            <div class="analytics-list">
                                ${trendRows.slice(0, 5).map((row) => this._harvestTrendCardHTML(row)).join('')}
                            </div>
                        </div>
                    ` : ''}
                `;
            }
        }

        if (!environmentContainer) return;

        const comparisons = insights?.comparison?.comparisons || [];
        const environmentStats = insights?.environment?.environment_stats || {};

        if (!comparisons.length && !Object.keys(environmentStats).length) {
            this.showEmpty(environmentContainer, 'Environment summaries appear after completed harvest cycles');
            return;
        }

        environmentContainer.innerHTML = `
            ${comparisons.length ? `
                <div class="analytics-section-block">
                    <h4>Cycle Comparison</h4>
                    <div class="analytics-list">
                        ${comparisons.slice(0, 3).map((entry) => this._harvestEnvironmentComparisonHTML(entry)).join('')}
                    </div>
                </div>
            ` : ''}
            ${Object.keys(environmentStats).length ? `
                <div class="analytics-section-block">
                    <h4>Latest Cycle Environment</h4>
                    <div class="analytics-grid">
                        ${Object.entries(environmentStats).map(([sensorType, stats]) => this._environmentStatCardHTML(sensorType, stats)).join('')}
                    </div>
                </div>
            ` : ''}
        `;
    }

    renderGuide(guidePlants) {
        const container = document.getElementById('guide-list');
        if (!container) return;

        if (!guidePlants || guidePlants.length === 0) {
            this.showEmpty(container, 'No plant guide data available');
            return;
        }

        container.innerHTML = guidePlants.map(plant => this._guideItemHTML(plant)).join('');
    }

    renderAIStatus() {
        const container = document.getElementById('ai-status');
        if (!container) return;

        container.innerHTML = `
            <div class="ai-service-item">
                <div class="service-icon">
                    <i class="fas fa-brain"></i>
                </div>
                <div class="service-info">
                    <h4>Disease Prediction</h4>
                    <span class="service-status status-active">
                        <i class="fas fa-circle"></i> Active
                    </span>
                </div>
            </div>
            <div class="ai-service-item">
                <div class="service-icon">
                    <i class="fas fa-chart-line"></i>
                </div>
                <div class="service-info">
                    <h4>Growth Prediction</h4>
                    <span class="service-status status-active">
                        <i class="fas fa-circle"></i> Active
                    </span>
                </div>
            </div>
        `;
    }

    switchTab(tabName) {
        this.currentTab = tabName;

        // Update tab buttons
        document.querySelectorAll('[data-tab]').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.tab === tabName);
        });

        // Update tab content
        document.querySelectorAll('.tab-content').forEach(content => {
            content.classList.toggle('active', content.id === `${tabName}-tab`);
        });

        this.log(`Switched to tab: ${tabName}`);
    }

    filterPlants(filter) {
        this.currentFilter = filter;
        this.log(`Filtering plants by: ${filter}`);

        // Update filter buttons - use .filter-btn class to target the correct buttons
        const buttons = document.querySelectorAll('.filter-btn');
        this.log(`Found ${buttons.length} filter buttons`);
        buttons.forEach(btn => {
            btn.classList.toggle('active', btn.dataset.filter === filter);
        });

        // Filter plant cards
        const cards = document.querySelectorAll('.plant-card');
        this.log(`Found ${cards.length} plant cards to filter`);
        
        // Debug: show first few card statuses
        const statusSamples = Array.from(cards).slice(0, 3).map(c => 
            `${c.dataset.name}: "${c.dataset.status}"`
        );
        this.log(`Sample card statuses: ${statusSamples.join(', ')}`);
        
        let visibleCount = 0;
        cards.forEach(card => {
            const status = card.dataset.status;
            const visible = filter === 'all' || status === filter;
            card.style.display = visible ? 'block' : 'none';
            if (visible) visibleCount++;
        });

        this.log(`Filtered plants: ${filter} - showing ${visibleCount}/${cards.length} cards`);
    }

    searchPlants(query) {
        const lowerQuery = query.toLowerCase().trim();

        document.querySelectorAll('.plant-card').forEach(card => {
            const name = card.dataset.name?.toLowerCase() || '';
            const type = card.dataset.type?.toLowerCase() || '';
            const visible = !lowerQuery || name.includes(lowerQuery) || type.includes(lowerQuery);
            card.style.display = visible ? 'block' : 'none';
        });
    }

    searchGuide(query) {
        const lowerQuery = query.toLowerCase().trim();

        document.querySelectorAll('.guide-item').forEach(item => {
            const name = item.dataset.plantName || '';
            const species = item.dataset.species || '';
            const visible = !lowerQuery || name.includes(lowerQuery) || species.includes(lowerQuery);
            item.style.display = visible ? 'block' : 'none';
        });
    }

    async refresh() {
        this.dataService.clearCache();
        await this.loadAndRender();
    }

    // HTML template helpers

    _plantCardHTML(plant) {
        // Default to 'healthy' if status is null/empty, since unknown status plants are likely healthy
        const statusClass = plant.current_health_status || 'healthy';
        const statusIcon = {
            'healthy': 'fa-check-circle',
            'stressed': 'fa-exclamation-triangle',
            'diseased': 'fa-times-circle'
        }[statusClass] || 'fa-question-circle';

        return `
            <a href="/plants/${plant.plant_id}/my-detail" class="plant-card-link" title="View plant details">
            <div class="plant-card" data-status="${statusClass}" data-name="${plant.name}" data-type="${plant.plant_type}">
                <div class="plant-card-header">
                    <h4>${plant.name}</h4>
                    <span class="status-badge status-${statusClass}">
                        <i class="fas ${statusIcon}"></i>
                        ${statusClass}
                    </span>
                </div>
                <div class="plant-card-body">
                    <p><strong>Type:</strong> ${plant.plant_type}</p>
                    <p><strong>Stage:</strong> ${plant.current_stage}</p>
                    <p><strong>Days in stage:</strong> ${plant.days_in_stage}</p>
                    <p><strong>Unit:</strong> ${plant.unit_name || `Unit ${plant.unit_id}`}</p>
                </div>
                <div class="plant-card-actions" onclick="event.preventDefault(); event.stopPropagation();">
                    <button class="btn btn-sm" data-action="view-details" data-plant-id="${plant.plant_id}" data-unit-id="${plant.unit_id}" title="Quick view">
                        <i class="fas fa-eye"></i>
                    </button>
                    <button class="btn btn-sm" data-action="link-sensor" data-plant-id="${plant.plant_id}" data-unit-id="${plant.unit_id}" title="Link sensor">
                        <i class="fas fa-link"></i>
                    </button>
                    <button class="btn btn-sm" data-action="delete-plant" data-plant-id="${plant.plant_id}" data-unit-id="${plant.unit_id}" title="Delete plant">
                        <i class="fas fa-trash-alt"></i>
                    </button>
                </div>
            </div>
            </a>
        `;
    }

    _riskCardHTML(unit) {
        const risks = unit.risks || [];
        const riskClass = this._getUnitRiskLevel(risks);
        const badgeLevel = riskClass === 'critical' ? 'high' : riskClass;
        const cardClass = riskClass === 'critical' ? 'critical-risk'
            : riskClass === 'high' ? 'high-risk'
                : '';
        const riskIcon = {
            'low': 'fa-check-circle',
            'medium': 'fa-exclamation-triangle',
            'high': 'fa-exclamation-circle',
            'critical': 'fa-skull-crossbones'
        }[riskClass] || 'fa-question';

        return `
            <div class="disease-unit-card ${cardClass}">
                <div class="disease-unit-header">
                    <h4>${unit.unit_name || `Unit ${unit.unit_id}`}</h4>
                    <span class="risk-badge ${badgeLevel}">
                        <i class="fas ${riskIcon}"></i>
                        ${riskClass} risk
                    </span>
                </div>
                <div class="unit-details">
                    <p><strong>Plant Type:</strong> ${unit.plant_type || 'Unknown'}</p>
                    <p><strong>Growth Stage:</strong> ${unit.growth_stage || 'Unknown'}</p>
                    <p><strong>Risks Detected:</strong> ${unit.risk_count ?? risks.length}</p>
                    <p><strong>Highest Risk:</strong> ${Number(unit.highest_risk_score || 0).toFixed(1)}/100</p>
                    ${risks.length > 0 ? `
                        <div class="risk-factors">
                            <strong>Top Risks:</strong>
                            <ul>
                                ${risks.slice(0, 3).map(risk => `
                                    <li>
                                        ${this._formatDiseaseType(risk.disease_type)} (${risk.risk_level})
                                        <button
                                            type="button"
                                            class="btn btn-link btn-sm analytics-inline-action"
                                            data-action="feedback-risk"
                                            data-unit-id="${unit.unit_id || ''}"
                                            data-disease-type="${risk.disease_type || ''}"
                                            data-risk-level="${risk.risk_level || ''}"
                                            data-risk-score="${risk.risk_score || risk.score || ''}"
                                        >
                                            Send feedback
                                        </button>
                                    </li>
                                `).join('')}
                            </ul>
                        </div>
                    ` : ''}
                </div>
            </div>
        `;
    }

    _getUnitRiskLevel(risks) {
        if (!Array.isArray(risks) || risks.length === 0) return 'low';
        if (risks.some(risk => risk.risk_level === 'critical')) return 'critical';
        if (risks.some(risk => risk.risk_level === 'high')) return 'high';
        if (risks.some(risk => risk.risk_level === 'medium')) return 'medium';
        return 'low';
    }

    _computeRiskSummary(units) {
        const summary = {
            total_units: units.length,
            high_risk_units: 0,
            critical_risk_units: 0,
            most_common_risk: null,
            total_risks_detected: 0
        };
        const typeCounts = {};
        units.forEach(unit => {
            const risks = unit.risks || [];
            summary.total_risks_detected += risks.length;
            if (risks.some(risk => risk.risk_level === 'critical')) {
                summary.critical_risk_units += 1;
            } else if (risks.some(risk => risk.risk_level === 'high')) {
                summary.high_risk_units += 1;
            }
            risks.forEach(risk => {
                const key = risk.disease_type || 'unknown';
                typeCounts[key] = (typeCounts[key] || 0) + 1;
            });
        });
        const sorted = Object.entries(typeCounts).sort((a, b) => b[1] - a[1]);
        summary.most_common_risk = sorted.length ? sorted[0][0] : null;
        return summary;
    }

    _formatDiseaseType(type) {
        if (!type) return 'Unknown';
        return String(type)
            .replace(/_/g, ' ')
            .replace(/\b\w/g, c => c.toUpperCase());
    }

    _escapeHTML(value) {
        const div = document.createElement('div');
        div.textContent = String(value ?? '');
        return div.innerHTML;
    }

    _formatDate(value, includeTime = false) {
        if (!value) return '--';
        const date = new Date(value);
        if (Number.isNaN(date.getTime())) return '--';
        return includeTime
            ? date.toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' })
            : date.toLocaleDateString();
    }

    _formatNumber(value, decimals = 1, fallback = '0') {
        const numeric = Number(value);
        return Number.isFinite(numeric) ? numeric.toFixed(decimals) : fallback;
    }

    _formatWeight(value) {
        const numeric = Number(value);
        if (!Number.isFinite(numeric)) return '--';
        return `${numeric.toFixed(numeric >= 100 ? 0 : 1)} g`;
    }

    _formatPercentage(value, decimals = 1) {
        const numeric = Number(value);
        if (!Number.isFinite(numeric)) return '--';
        const normalized = numeric <= 1 ? numeric * 100 : numeric;
        return `${normalized.toFixed(decimals)}%`;
    }

    _settledValue(result, fallback) {
        return result?.status === 'fulfilled' ? result.value : fallback;
    }

    _readSelectedUnitId() {
        const raw = document.querySelector('.health-dashboard')?.dataset?.selectedUnitId
            || document.body?.dataset?.activeUnitId
            || '';
        const parsed = parseInt(raw, 10);
        return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
    }

    _collectUnits(plants = []) {
        const byId = new Map();
        plants.forEach((plant) => {
            const unitId = Number(plant.unit_id);
            if (!Number.isFinite(unitId) || unitId <= 0 || byId.has(unitId)) {
                return;
            }
            byId.set(unitId, {
                unit_id: unitId,
                unit_name: plant.unit_name || `Unit ${unitId}`,
            });
        });
        return Array.from(byId.values());
    }

    _resolveActiveUnitId() {
        if (Number.isFinite(this.selectedUnitId) && this.selectedUnitId > 0) {
            return this.selectedUnitId;
        }
        if (this.units.length > 0) {
            return this.units[0].unit_id;
        }
        const firstPlantUnit = Number(this.plants[0]?.unit_id);
        return Number.isFinite(firstPlantUnit) && firstPlantUnit > 0 ? firstPlantUnit : null;
    }

    _latestHarvestWindow(growthCycles) {
        const latest = growthCycles?.harvests?.[0];
        if (!latest?.planted_date || !latest?.harvested_date) {
            return null;
        }
        return {
            start_date: latest.planted_date,
            end_date: latest.harvested_date,
        };
    }

    _mapSeverityLevelToLabel(level) {
        const numeric = Number(level);
        if (!Number.isFinite(numeric)) return 'mild';
        if (numeric >= 4) return 'severe';
        if (numeric >= 2) return 'moderate';
        return 'mild';
    }

    _normalizeDiseaseType(diseaseType, healthStatus) {
        if (diseaseType) {
            return String(diseaseType).toLowerCase();
        }

        const status = String(healthStatus || '').toLowerCase();
        if (status === 'pest_infestation') return 'pest';
        if (status === 'nutrient_deficiency') return 'nutrient_deficiency';
        if (status === 'stressed') return 'environmental_stress';
        return 'fungal';
    }

    _shouldCreateDiseaseOccurrence(payload) {
        const status = String(payload?.health_status || '').toLowerCase();
        return ['diseased', 'pest_infestation', 'nutrient_deficiency', 'stressed'].includes(status);
    }

    _normalizeHarvestTrendRows(unitStats) {
        const raw = unitStats?.statistics || unitStats?.harvests || unitStats || [];
        return Array.isArray(raw) ? raw : [];
    }

    _diseaseHistoryItemHTML(occurrence) {
        const resolved = Boolean(occurrence.resolved_at);
        return `
            <div class="analytics-history-item ${resolved ? 'is-resolved' : 'is-active'}">
                <div class="analytics-history-header">
                    <div>
                        <strong>${this._formatDiseaseType(occurrence.disease_type)}</strong>
                        <span class="status-badge ${resolved ? 'success' : 'inactive'}">
                            ${resolved ? 'Resolved' : 'Open'}
                        </span>
                    </div>
                    <span class="text-muted">${this._formatDate(occurrence.detected_at, true)}</span>
                </div>
                <p class="analytics-history-meta">
                    Unit ${occurrence.unit_id || '--'}
                    ${occurrence.plant_id ? ` • Plant ${occurrence.plant_id}` : ''}
                    ${occurrence.severity ? ` • ${this._formatDiseaseType(occurrence.severity)}` : ''}
                </p>
                ${occurrence.symptoms ? `<p>${this._escapeHTML(occurrence.symptoms)}</p>` : ''}
                ${occurrence.treatment_applied ? `<p><strong>Treatment:</strong> ${this._escapeHTML(occurrence.treatment_applied)}</p>` : ''}
                <div class="analytics-history-actions">
                    ${!resolved ? `
                        <button type="button" class="btn btn-outline btn-sm" data-action="resolve-disease" data-occurrence-id="${occurrence.occurrence_id}">
                            Resolve case
                        </button>
                    ` : ''}
                </div>
            </div>
        `;
    }

    _growthCycleCardHTML(cycle) {
        return `
            <div class="analytics-history-item">
                <div class="analytics-history-header">
                    <strong>${this._escapeHTML(cycle.plant_name || `Harvest ${cycle.harvest_id}`)}</strong>
                    <span class="text-muted">${this._formatDate(cycle.harvested_date)}</span>
                </div>
                <p class="analytics-history-meta">
                    ${this._formatWeight(cycle.yield_weight_grams)}
                    • ${this._formatNumber(cycle.quality_rating, 1, '--')}/5 quality
                    • ${this._formatNumber(cycle.total_days, 0, '--')} days
                </p>
                <p class="analytics-history-meta">
                    ${this._formatNumber(cycle.avg_temperature, 1, '--')}°C
                    • ${this._formatNumber(cycle.avg_humidity, 1, '--')}% humidity
                    • ${this._formatNumber(cycle.grams_per_kwh, 1, '--')} g/kWh
                </p>
            </div>
        `;
    }

    _harvestTrendCardHTML(row) {
        return `
            <div class="analytics-history-item">
                <div class="analytics-history-header">
                    <strong>${this._escapeHTML(row.plant_name || row.plant_type || `Harvest ${row.harvest_id || ''}`)}</strong>
                    <span class="text-muted">${this._formatDate(row.harvested_date || row.harvest_date)}</span>
                </div>
                <p class="analytics-history-meta">
                    ${this._formatWeight(row.yield_weight_grams || row.yield_amount)}
                    • ${this._formatNumber(row.grams_per_kwh, 1, '--')} g/kWh
                    • ${this._formatNumber(row.cost_per_gram, 2, '--')} cost/g
                </p>
            </div>
        `;
    }

    _harvestEnvironmentComparisonHTML(entry) {
        return `
            <div class="analytics-history-item">
                <div class="analytics-history-header">
                    <strong>${this._escapeHTML(entry.plant_name || `Harvest ${entry.harvest_id}`)}</strong>
                    <span class="text-muted">${this._formatDate(entry.harvested_date)}</span>
                </div>
                <p class="analytics-history-meta">
                    ${this._formatNumber(entry.avg_temperature, 1, '--')}°C
                    • ${this._formatNumber(entry.avg_humidity, 1, '--')}% humidity
                    • ${this._formatNumber(entry.avg_co2, 0, '--')} ppm CO2
                </p>
                <p class="analytics-history-meta">
                    ${this._formatWeight(entry.yield_weight_grams)}
                    • ${this._formatNumber(entry.quality_rating, 1, '--')}/5 quality
                    • ${this._formatNumber(entry.total_energy_kwh, 1, '--')} kWh
                </p>
            </div>
        `;
    }

    _environmentStatCardHTML(sensorType, stats) {
        return `
            <div class="analytics-stat-card">
                <strong>${this._formatDiseaseType(sensorType)}</strong>
                <span>Avg ${this._formatNumber(stats?.avg, 1, '--')}</span>
                <span>Min ${this._formatNumber(stats?.min, 1, '--')}</span>
                <span>Max ${this._formatNumber(stats?.max, 1, '--')}</span>
            </div>
        `;
    }

    _journalEntryHTML(entry) {
        const typeIcon = {
            'observation': 'fa-eye',
            'nutrient': 'fa-flask',
            'treatment': 'fa-medkit',
            'note': 'fa-sticky-note'
        }[entry.entry_type] || 'fa-file';

        return `
            <div class="journal-entry">
                <div class="entry-icon">
                    <i class="fas ${typeIcon}"></i>
                </div>
                <div class="entry-content">
                    <div class="entry-header">
                        <span class="entry-type">${entry.entry_type}</span>
                        <span class="entry-date">${new Date(entry.created_at).toLocaleDateString()}</span>
                    </div>
                    <p class="entry-notes">${entry.notes || 'No notes'}</p>
                    ${entry.nutrient_type ? `<p><strong>Nutrient:</strong> ${entry.nutrient_type} (${entry.amount}${entry.unit})</p>` : ''}
                </div>
            </div>
        `;
    }

    _harvestItemHTML(harvest) {
        return `
            <div class="harvest-item">
                <div class="harvest-info">
                    <h5>${harvest.plant_name || `Plant ${harvest.plant_id}`}</h5>
                    <p class="harvest-date">${new Date(harvest.harvest_date).toLocaleDateString()}</p>
                </div>
                <div class="harvest-yield">
                    <strong>${harvest.yield_amount || 0} ${harvest.yield_unit || 'g'}</strong>
                    <span class="harvest-quality">Quality: ${harvest.quality || 'N/A'}</span>
                </div>
            </div>
        `;
    }

    _guideItemHTML(plant) {
        // API returns: common_name, species, pH_range, water_requirements, growth_stages (may be string or other), tips
        const name = plant.common_name || plant.name || 'Unknown Plant';
        const species = plant.species || 'Species not specified';
        const phRange = plant.pH_range || plant.ph_range || 'N/A';
        const waterReq = plant.water_requirements || 'Standard watering';
        const tips = plant.tips || '';
        
        // growth_stages handling - may not be a string, so check type first
        const stageCount = (plant.growth_stages && typeof plant.growth_stages === 'string') 
            ? (plant.growth_stages.trim().length || plant.growth_stages.length) 
            : 0;
        
        return `
            <div class="guide-item" data-plant-name="${name.toLowerCase()}" data-species="${species.toLowerCase()}">
                <div class="guide-header">
                    <h4>${name}</h4>
                    <span class="guide-badge">
                        <i class="fas fa-leaf"></i>
                    </span>
                </div>
                <div class="guide-info">
                    <p><strong>Species:</strong> <em>${species}</em></p>
                    <p><strong>pH Range:</strong> ${phRange}</p>
                    <p><strong>Water:</strong> ${waterReq}</p>
                    ${tips ? `<p class="guide-tips"><i class="fas fa-lightbulb"></i> ${tips}</p>` : ''}
                </div>
            </div>
        `;
    }

    _updateStat(id, value) {
        const el = document.getElementById(id);
        if (el) el.textContent = value;
    }

    // Populate plant select dropdowns
    populatePlantSelects() {
        const observationPlantSelect = document.getElementById('observation-plant');
        const nutrientPlantSelect = document.getElementById('nutrient-plant');
        const journalFilterSelect = document.getElementById('journal-plant-filter');
        const harvestPlantSelect = document.getElementById('harvest-plant');
        const feedbackUnitSelect = document.getElementById('prediction-feedback-unit');

        const plantOptions = this.plants.map(plant => 
            `<option value="${plant.plant_id}">${plant.name} (${plant.plant_type})</option>`
        ).join('');
        const unitOptions = this.units.map((unit) =>
            `<option value="${unit.unit_id}">${this._escapeHTML(unit.unit_name)}</option>`
        ).join('');

        if (observationPlantSelect) {
            observationPlantSelect.innerHTML = '<option value="">-- Select a plant --</option>' + plantOptions;
        }

        if (nutrientPlantSelect) {
            nutrientPlantSelect.innerHTML = '<option value="">Select plant...</option>' + plantOptions;
        }

        if (journalFilterSelect) {
            journalFilterSelect.innerHTML = '<option value="all">All Plants</option>' + plantOptions;
        }

        if (harvestPlantSelect) {
            harvestPlantSelect.innerHTML = '<option value="">Select plant...</option>' + plantOptions;
        }

        if (feedbackUnitSelect && this.units.length > 0) {
            feedbackUnitSelect.innerHTML = '<option value="">Select unit...</option>' + unitOptions;
            if (this.selectedUnitId) {
                feedbackUnitSelect.value = String(this.selectedUnitId);
            }
        }

        this.log(`Populated plant selects with ${this.plants.length} plants`);
    }

    // Form handlers
    async handleObservationSubmit(e) {
        e.preventDefault();
        const form = e.target;
        const formData = new FormData(form);
        
        try {
            this.log('Submitting observation...');
            
            // Get unit_id from selected plant
            const plantId = formData.get('plant_id');
            const plant = this.plants.find(p => p.plant_id == plantId);
            if (!plant) {
                throw new Error('Selected plant not found');
            }
            
            // Collect checked symptoms
            const symptoms = Array.from(form.querySelectorAll('input[name="symptoms"]:checked'))
                .map(cb => cb.value);
            const affectedParts = Array.from(form.querySelectorAll('input[name="affected_parts"]:checked'))
                .map(cb => cb.value);
            
            // Build JSON payload matching API expectations
            const payload = {
                unit_id: plant.unit_id,
                plant_id: parseInt(plantId),
                health_status: formData.get('health_status'),
                symptoms: symptoms,
                severity_level: parseInt(formData.get('severity_level') || '1'),
                disease_type: formData.get('disease_type') || null,
                affected_parts: affectedParts,
                treatment_applied: formData.get('treatment_applied') || null,
                notes: formData.get('notes') || '',
                plant_type: plant.plant_type,
                growth_stage: plant.current_stage || formData.get('growth_stage') || null
            };
            
            this.log('Observation payload:', payload);
            
            const result = await API.Plant.recordAIHealthObservation(payload);
            this.log('Observation saved successfully', result);

            if (this._shouldCreateDiseaseOccurrence(payload)) {
                try {
                    await this.dataService.recordDiseaseOccurrence({
                        unit_id: plant.unit_id,
                        plant_id: parseInt(plantId, 10),
                        disease_type: this._normalizeDiseaseType(payload.disease_type, payload.health_status),
                        severity: this._mapSeverityLevelToLabel(payload.severity_level),
                        symptoms: symptoms.join(', '),
                        affected_parts: affectedParts.join(', '),
                        notes: payload.notes || '',
                        plant_type: plant.plant_type || null,
                        growth_stage: plant.current_stage || null,
                        days_in_stage: plant.days_in_stage ?? null,
                    });
                } catch (trackingError) {
                    this.warn('Disease occurrence tracking failed after observation save:', trackingError);
                }
            }
            
            // Close modal and refresh
            this.closeAllModals();
            form.reset();
            await this.refresh();
            
        } catch (error) {
            this.error('Failed to save observation:', error);
            if (window.showNotification) {
                window.showNotification(`Failed to save observation: ${error.message}`, 'error');
            }
        }
    }

    // Modal helpers
    async openAddPlantModal() {
        const modal = document.getElementById('add-plant-modal');
        if (!modal) {
            this.error('Add plant modal not found');
            return;
        }
        
        // Initialize mode toggle (default to catalog mode)
        this.togglePlantMode('catalog');
        
        // Load catalog and populate dropdown FIRST (before any cloning)
        await this.populatePlantCatalog();
        
        // Pre-select the current unit if available (check multiple sources like base.html does)
        const selectedUnitId = document.body.dataset.activeUnitId 
            || document.querySelector('.health-dashboard')?.dataset.selectedUnitId
            || window.selectedUnitId;
            
        const unitSelect = document.getElementById('unit-select');
        if (unitSelect && selectedUnitId) {
            unitSelect.value = selectedUnitId;
            this.log(`Pre-selected unit: ${selectedUnitId}`);
        }
        
        // Bind mode toggle buttons (use simple removeEventListener approach)
        const modeCatalogBtn = document.getElementById('mode-catalog');
        const modeCustomBtn = document.getElementById('mode-custom');
        
        if (modeCatalogBtn && modeCustomBtn) {
            // Use a property to track handlers for proper removal
            if (this._catalogModeHandler) {
                modeCatalogBtn.removeEventListener('click', this._catalogModeHandler);
            }
            if (this._customModeHandler) {
                modeCustomBtn.removeEventListener('click', this._customModeHandler);
            }
            
            // Store handlers for future removal
            this._catalogModeHandler = () => this.togglePlantMode('catalog');
            this._customModeHandler = () => this.togglePlantMode('custom');
            
            // Add new listeners
            modeCatalogBtn.addEventListener('click', this._catalogModeHandler);
            modeCustomBtn.addEventListener('click', this._customModeHandler);
        }
        
        // Bind catalog selection
        const plantSelect = document.getElementById('plant-select');
        if (plantSelect) {
            if (this._plantSelectHandler) {
                plantSelect.removeEventListener('change', this._plantSelectHandler);
            }
            this._plantSelectHandler = (e) => this.handleCatalogSelection(e.target.value);
            plantSelect.addEventListener('change', this._plantSelectHandler);
        }

        const customPlantType = document.getElementById('custom-plant-type');
        if (customPlantType) {
            customPlantType.addEventListener('input', () => this._loadPlantProfileSelector());
        }
        
        // Bind form submission
        const form = document.getElementById('add-plant-form');
        if (form) {
            if (this._formSubmitHandler) {
                form.removeEventListener('submit', this._formSubmitHandler);
            }
            this._formSubmitHandler = (e) => this.handleAddPlant(e);
            form.addEventListener('submit', this._formSubmitHandler);
        }

        // Bind stage change for profile filtering
        const stageSelect = document.getElementById('plant-stage');
        if (stageSelect) {
            stageSelect.addEventListener('change', () => this._loadPlantProfileSelector());
        }
        
        // Bind cancel button
        const cancelBtn = document.getElementById('cancel-add-plant');
        if (cancelBtn) {
            cancelBtn.addEventListener('click', () => this.closeAllModals());
        }
        
        modal.hidden = false;
        modal.classList.add('is-open');
        modal.setAttribute('aria-hidden', 'false');
        this._initPlantProfileSelector();
        this._resetPlantProfileSelection();
        this._loadPlantProfileSelector();
        this.log('Opened add plant modal');
    }

    /**
     * Toggle between catalog and custom mode
     */
    togglePlantMode(mode) {
        const catalogSection = document.getElementById('catalog-mode-section');
        const customSection = document.getElementById('custom-mode-section');
        const catalogBtn = document.getElementById('mode-catalog');
        const customBtn = document.getElementById('mode-custom');
        
        if (mode === 'catalog') {
            if (catalogSection) catalogSection.style.display = 'block';
            if (customSection) customSection.style.display = 'none';
            if (catalogBtn) catalogBtn.classList.add('active');
            if (customBtn) customBtn.classList.remove('active');
            this.currentPlantMode = 'catalog';
        } else {
            if (catalogSection) catalogSection.style.display = 'none';
            if (customSection) customSection.style.display = 'block';
            if (catalogBtn) catalogBtn.classList.remove('active');
            if (customBtn) customBtn.classList.add('active');
            this.currentPlantMode = 'custom';
            this.clearPlantRequirements();
        }
        
        this.log(`Switched to ${mode} mode`);
        this._loadPlantProfileSelector();
    }

    /**
     * Handle add plant form submission
     */
    async handleAddPlant(e) {
        e.preventDefault();
        
        const formData = new FormData(e.target);
        const data = {
            name: formData.get('name'),
            unit_id: formData.get('unit_id'),
            stage: formData.get('stage'),
            days_in_stage: parseInt(formData.get('days_in_stage')) || 0,
            pot_size_liters: parseFloat(formData.get('pot_size_liters')) || null,
            pot_material: formData.get('pot_material') || null,
            growing_medium: formData.get('growing_medium') || null,
            medium_ph: parseFloat(formData.get('medium_ph')) || null,
            strain_variety: formData.get('strain_variety') || null,
            expected_yield_grams: parseFloat(formData.get('expected_yield_grams')) || null,
            light_distance_cm: parseFloat(formData.get('light_distance_cm')) || null,
            condition_profile_id: formData.get('condition_profile_id') || null,
            condition_profile_mode: formData.get('condition_profile_mode') || null,
            condition_profile_name: formData.get('condition_profile_name') || null,
            csrf_token: formData.get('csrf_token')
        };
        
        // Get plant type based on mode
        if (this.currentPlantMode === 'catalog') {
            data.plant_type = document.getElementById('plant-type').value;
            data.variety = document.getElementById('plant-variety').value;
        } else {
            data.plant_type = document.getElementById('custom-plant-type').value;
            data.variety = document.getElementById('custom-variety').value;
        }
        
        // Validate required fields
        if (!data.name || !data.unit_id || !data.plant_type) {
            if (window.showNotification) {
                window.showNotification('Please fill in all required fields', 'warning');
            }
            return;
        }
        
        this.log('Submitting new plant:', data);
        
        try {
            // Extract unit_id for API call, remove from body
            const unitId = data.unit_id;
            delete data.unit_id;
            delete data.csrf_token;
            
            const result = await API.Plant.addPlant(unitId, data);
            this.log('Plant added successfully', result);
            this.closeAllModals();
            await this.refresh();
        } catch (error) {
            this.error('Error adding plant:', error);
            if (window.showNotification) {
                window.showNotification(`Error: ${error.message}`, 'error');
            }
        }
    }

    openObservationModal(plantId = null) {
        const modal = document.getElementById('add-observation-modal');
        if (modal) {
            modal.hidden = false;
            modal.classList.add('is-open');
            modal.setAttribute('aria-hidden', 'false');
            if (plantId) {
                const selectEl = document.getElementById('observation-plant');
                if (selectEl) selectEl.value = plantId;
            }
            this.log('Opened observation modal', plantId ? `for plant ${plantId}` : '');
        }
    }

    openNutrientsModal() {
        const modal = document.getElementById('add-nutrients-modal');
        if (modal) {
            modal.hidden = false;
            modal.classList.add('is-open');
            modal.setAttribute('aria-hidden', 'false');
            this.log('Opened nutrients modal');
        }
    }

    openHealthDetailsModal() {
        const modal = document.getElementById('health-details-modal');
        const content = document.getElementById('health-details-content');
        if (!modal || !content) return;

        const scoreValue = parseInt(document.getElementById('health-score')?.textContent || '0', 10) || 0;
        const summary = this.latestHealthData?.summary || {};
        const healthy = Number(summary.healthy ?? document.getElementById('healthy-count')?.textContent ?? 0) || 0;
        const stressed = Number(summary.stressed ?? document.getElementById('stressed-count')?.textContent ?? 0) || 0;
        const diseased = Number(summary.diseased ?? document.getElementById('diseased-count')?.textContent ?? 0) || 0;
        const total = Number(summary.total ?? document.getElementById('total-plants')?.textContent ?? (healthy + stressed + diseased)) || 0;
        const status = scoreValue >= 80 ? 'Excellent' : scoreValue >= 50 ? 'Fair' : 'Needs Attention';

        content.innerHTML = `
            <div class="health-stats-grid">
                <div class="health-stat">
                    <span class="health-stat-value">${scoreValue}%</span>
                    <span class="health-stat-label">Health Score</span>
                </div>
                <div class="health-stat">
                    <span class="health-stat-value">${total}</span>
                    <span class="health-stat-label">Total Plants</span>
                </div>
                <div class="health-stat">
                    <span class="health-stat-value success">${healthy}</span>
                    <span class="health-stat-label">Healthy</span>
                </div>
                <div class="health-stat">
                    <span class="health-stat-value warning">${stressed}</span>
                    <span class="health-stat-label">Stressed</span>
                </div>
                <div class="health-stat">
                    <span class="health-stat-value danger">${diseased}</span>
                    <span class="health-stat-label">Diseased</span>
                </div>
            </div>
            <div class="empty-state mt-3">
                <strong>Overall Status: ${status}</strong>
            </div>
        `;

        modal.hidden = false;
        modal.classList.add('is-open');
        modal.setAttribute('aria-hidden', 'false');
    }

    openHarvestModal(plantId = null) {
        const modal = document.getElementById('harvest-modal');
        if (!modal) {
            return;
        }

        modal.hidden = false;
        modal.classList.add('is-open');
        modal.setAttribute('aria-hidden', 'false');

        const plantSelect = document.getElementById('harvest-plant');
        if (plantSelect && plantId) {
            plantSelect.value = String(plantId);
        }
    }

    async openResolveDiseaseModal(occurrenceId) {
        const modal = document.getElementById('resolve-disease-modal');
        const occurrenceInput = document.getElementById('resolve-disease-occurrence-id');
        const summary = document.getElementById('resolve-disease-summary');
        if (!modal || !occurrenceInput) {
            return;
        }

        occurrenceInput.value = occurrenceId || '';
        if (summary) {
            summary.textContent = 'Loading case details...';
        }

        try {
            const occurrence = await this.dataService.getDiseaseOccurrence(occurrenceId);
            if (summary && occurrence) {
                summary.textContent = `${this._formatDiseaseType(occurrence.disease_type)} detected ${this._formatDate(occurrence.detected_at, true)}${occurrence.plant_id ? ` for plant ${occurrence.plant_id}` : ''}.`;
            }
        } catch (error) {
            if (summary) {
                summary.textContent = 'Unable to load case details.';
            }
            this.warn('Failed to load disease occurrence details:', error);
        }

        modal.hidden = false;
        modal.classList.add('is-open');
        modal.setAttribute('aria-hidden', 'false');
    }

    openPredictionFeedbackModal(prefill = {}) {
        const modal = document.getElementById('prediction-feedback-modal');
        if (!modal) {
            return;
        }

        const unitSelect = document.getElementById('prediction-feedback-unit');
        const diseaseTypeSelect = document.getElementById('prediction-disease-type');
        const riskLevelSelect = document.getElementById('prediction-risk-level');
        const riskScoreInput = document.getElementById('prediction-risk-score');

        if (unitSelect) {
            unitSelect.value = String(prefill.unitId || this.selectedUnitId || unitSelect.value || '');
        }
        if (diseaseTypeSelect && prefill.diseaseType) {
            diseaseTypeSelect.value = String(prefill.diseaseType);
        }
        if (riskLevelSelect && prefill.riskLevel) {
            riskLevelSelect.value = String(prefill.riskLevel);
        }
        if (riskScoreInput && prefill.riskScore) {
            riskScoreInput.value = String(prefill.riskScore);
        }

        this.togglePredictionOutcomeFields(
            String(document.getElementById('prediction-actual-occurred')?.value || '').toLowerCase() === 'true'
        );

        modal.hidden = false;
        modal.classList.add('is-open');
        modal.setAttribute('aria-hidden', 'false');
    }

    togglePredictionOutcomeFields(showActualFields) {
        const actualTypeGroup = document.getElementById('prediction-actual-type-group');
        const actualSeverityGroup = document.getElementById('prediction-actual-severity-group');
        const daysToOccurrenceGroup = document.getElementById('prediction-days-group');

        [actualTypeGroup, actualSeverityGroup, daysToOccurrenceGroup].forEach((element) => {
            if (element) {
                element.hidden = !showActualFields;
            }
        });
    }

    async handleHarvestSubmit(e) {
        e.preventDefault();
        const form = e.target;
        const plantId = Number(form.plant_id?.value);
        if (!Number.isFinite(plantId) || plantId <= 0) {
            if (window.showNotification) {
                window.showNotification('Select a plant to record the harvest', 'warning');
            }
            return;
        }

        try {
            await this.dataService.recordHarvest(plantId, {
                harvest_weight_grams: Number(form.harvest_weight_grams?.value || 0),
                quality_rating: Number(form.quality_rating?.value || 0),
                notes: form.notes?.value?.trim() || '',
                delete_plant_data: Boolean(form.delete_plant_data?.checked),
            });

            this.closeAllModals();
            form.reset();
            await this.refresh();

            if (window.showNotification) {
                window.showNotification('Harvest recorded successfully', 'success');
            }
        } catch (error) {
            this.error('Failed to record harvest:', error);
            if (window.showNotification) {
                window.showNotification(`Failed to record harvest: ${error.message}`, 'error');
            }
        }
    }

    async handleResolveDiseaseSubmit(e) {
        e.preventDefault();
        const form = e.target;
        const occurrenceId = Number(form.occurrence_id?.value);

        if (!Number.isFinite(occurrenceId) || occurrenceId <= 0) {
            return;
        }

        try {
            await this.dataService.resolveDiseaseOccurrence(occurrenceId, {
                treatment_applied: form.treatment_applied?.value?.trim() || '',
                notes: form.notes?.value?.trim() || '',
            });

            this.closeAllModals();
            form.reset();
            await this.refresh();

            if (window.showNotification) {
                window.showNotification('Disease case resolved', 'success');
            }
        } catch (error) {
            this.error('Failed to resolve disease occurrence:', error);
            if (window.showNotification) {
                window.showNotification(`Failed to resolve disease case: ${error.message}`, 'error');
            }
        }
    }

    async handlePredictionFeedbackSubmit(e) {
        e.preventDefault();
        const form = e.target;
        const actualDiseaseOccurred = String(form.actual_disease_occurred?.value || '').toLowerCase() === 'true';
        const rawRiskScore = form.predicted_risk_score?.value ? Number(form.predicted_risk_score.value) : null;
        const normalizedRiskScore = Number.isFinite(rawRiskScore)
            ? (rawRiskScore > 1 ? rawRiskScore / 100 : rawRiskScore)
            : null;

        try {
            await this.dataService.recordDiseasePredictionFeedback({
                unit_id: Number(form.unit_id?.value),
                predicted_disease_type: form.predicted_disease_type?.value,
                predicted_risk_level: form.predicted_risk_level?.value,
                predicted_risk_score: normalizedRiskScore,
                actual_disease_occurred: actualDiseaseOccurred,
                actual_disease_type: actualDiseaseOccurred ? (form.actual_disease_type?.value || null) : null,
                actual_severity: actualDiseaseOccurred ? (form.actual_severity?.value || null) : null,
                days_to_occurrence: actualDiseaseOccurred && form.days_to_occurrence?.value
                    ? Number(form.days_to_occurrence.value)
                    : null,
                feedback_source: 'user',
            });

            this.closeAllModals();
            form.reset();
            this.togglePredictionOutcomeFields(false);
            await this.refresh();

            if (window.showNotification) {
                window.showNotification('Prediction feedback saved', 'success');
            }
        } catch (error) {
            this.error('Failed to save prediction feedback:', error);
            if (window.showNotification) {
                window.showNotification(`Failed to save feedback: ${error.message}`, 'error');
            }
        }
    }

    async openPlantDetails(plantId, unitId) {
        const numericPlantId = Number(plantId);
        if (!Number.isFinite(numericPlantId) || numericPlantId <= 0) {
            this.warn('Invalid plant ID for details modal:', plantId);
            return;
        }
        const numericUnitId = Number(unitId);
        const resolvedUnitId = Number.isFinite(numericUnitId) && numericUnitId > 0 ? numericUnitId : null;

        if (!this.plantDetailsModal) {
            if (!window.PlantDetailsModal) {
                this.error('PlantDetailsModal component not loaded');
                return;
            }
            try {
                this.plantDetailsModal = new window.PlantDetailsModal({
                    fetchPlant: ({ plantId: fetchPlantId, unitId: fetchUnitId }) =>
                        this.dataService.getPlantDetails(fetchPlantId, fetchUnitId),
                });
            } catch (error) {
                this.error('Failed to initialize PlantDetailsModal:', error);
                return;
            }
        }

        const plantSummary = this.plants.find(p => Number(p.plant_id) === numericPlantId) || null;

        this.log('Opening plant details modal', { plantId: numericPlantId, unitId: resolvedUnitId });
        try {
            this.plantDetailsModal.open({ plantId: numericPlantId, unitId: resolvedUnitId, plantSummary });
        } catch (error) {
            this.error('Failed to open plant details modal:', error);
        }
    }

    async openLinkSensorModal(plantId) {
        const modal = document.getElementById('link-sensor-modal');
        const select = document.getElementById('available-sensors');
        const hidden = document.getElementById('link-plant-id');
        if (!modal || !select || !hidden) return;
        hidden.value = plantId;
        select.innerHTML = '<option value="">Loading...</option>';

        // Attempt to infer unit id from stored plants
        const plant = this.plants.find(p => Number(p.plant_id) === Number(plantId));
        const unitId = plant?.unit_id || document.body?.dataset?.activeUnitId || null;

        console.log('[PlantsUIManager] Opening link sensor modal for plant:', plantId, 'unit:', unitId, 'plant:', plant);

        try {
            // Get already linked sensors for this plant
            let linkedSensorIds = new Set();
            try {
                const linkedResp = await window.API.Plant.getPlantSensors(plantId);
                console.log('[PlantsUIManager] Linked sensors response:', linkedResp);
                const linkedSensors = linkedResp?.data?.sensors || linkedResp?.sensors || [];
                linkedSensorIds = new Set(linkedSensors.map(s => Number(s.sensor_id)));
            } catch (err) {
                console.warn('[PlantsUIManager] Could not fetch linked sensors:', err);
            }

            // Get available sensors
            const response = await window.API.Plant.getAvailableSensors(unitId);
            console.log('[PlantsUIManager] Available sensors response:', response);
            // Handle nested data structure: response.data.sensors
            const allSensors = response?.data?.sensors || response?.sensors || [];
            console.log('[PlantsUIManager] All sensors:', allSensors, 'Linked IDs:', Array.from(linkedSensorIds));
            // Filter out already linked sensors
            const availableSensors = allSensors.filter(s => !linkedSensorIds.has(Number(s.sensor_id)));
            console.log('[PlantsUIManager] Available sensors after filtering:', availableSensors);

            if (!availableSensors || availableSensors.length === 0) {
                select.innerHTML = '<option value="">No sensors available</option>';
            } else {
                select.innerHTML = '<option value="">-- Select sensor --</option>' +
                    availableSensors.map(s =>
                        `<option value="${s.sensor_id}">${window.escapeHtml(s.name || s.sensor_id)} (${window.escapeHtml(s.type || '')})</option>`
                    ).join('');
            }
        } catch (err) {
            console.error('[PlantsUIManager] Failed to load sensors', err);
            select.innerHTML = '<option value="">Failed to load sensors</option>';
        }

        modal.hidden = false;
        modal.classList.add('is-open');
        modal.setAttribute('aria-hidden', 'false');
    }

    async handleLinkSensorSubmit(e) {
        e.preventDefault();
        const form = e.target;
        const plantId = form.plant_id?.value || document.getElementById('link-plant-id')?.value;
        const sensorId = form.sensor_id?.value || document.getElementById('available-sensors')?.value;
        if (!plantId || !sensorId) {
            if (window.showNotification) {
                window.showNotification('Select a sensor to link', 'warning');
            }
            return;
        }

        try {
            await window.API.Plant.linkPlantToSensor(Number(plantId), Number(sensorId));
            if (window.showNotification) {
                window.showNotification('Sensor linked successfully', 'success');
            }
            this.closeAllModals();
            // Refresh data
            await this.loadAndRender();
        } catch (err) {
            console.error('Failed to link sensor', err);
            if (window.showNotification) {
                window.showNotification('Failed to link sensor', 'error');
            }
        }
    }

    async handleDeletePlantClick(el) {
        if (!el) return;
        const plantId = el.dataset?.plantId;
        const unitId = el.dataset?.unitId;
        if (!plantId) return;
        if (!confirm('Delete this plant? This action cannot be undone.')) return;

        try {
            await window.API.Plant.removePlant(Number(unitId), Number(plantId));
            this.log('Plant deleted', plantId);
            await this.loadAndRender();
        } catch (err) {
            console.error('Failed to delete plant', err);
            if (window.showNotification) {
                window.showNotification('Failed to delete plant', 'error');
            }
        }
    }

    closeAllModals() {
        // Blur active element to avoid aria-hidden focus warning
        if (document.activeElement && document.activeElement !== document.body) {
            document.activeElement.blur();
        }
        
        document.querySelectorAll('.modal').forEach(modal => {
            modal.hidden = true;
            modal.classList.remove('visible');
            modal.classList.remove('is-open');
            modal.classList.remove('active');
            modal.setAttribute('aria-hidden', 'true');
        });
        this._resetPlantProfileSelection?.();
        this.log('Closed all modals');
    }

    openBulkNutrientModal() {
        const modal = document.getElementById('add-nutrients-modal');
        if (modal) {
            // Switch to bulk mode
            const bulkRadio = document.querySelector('input[name="application_type"][value="bulk"]');
            if (bulkRadio) bulkRadio.checked = true;
            
            // Trigger the radio change to show/hide correct fields
            const singleGroup = document.getElementById('single-plant-group');
            const bulkGroup = document.getElementById('bulk-unit-group');
            if (singleGroup) singleGroup.hidden = true;
            if (bulkGroup) bulkGroup.hidden = false;
            
            modal.hidden = false;
            modal.classList.add('is-open');
            modal.setAttribute('aria-hidden', 'false');
            this.log('Opened bulk nutrient modal');
        }
    }

    /**
     * Populate plant catalog dropdown
     */
    async populatePlantCatalog() {
        const select = document.getElementById('plant-select');
        console.log('[populatePlantCatalog] Select element:', select);
        
        if (!select) {
            this.error('Plant select element not found');
            return;
        }
        
        try {
            const catalog = await this.dataService.loadPlantCatalog();
            console.log('[populatePlantCatalog] Loaded catalog:', catalog);
            console.log('[populatePlantCatalog] Catalog length:', catalog?.length);
            
            if (!catalog || catalog.length === 0) {
                this.error('No plants in catalog');
                select.innerHTML = '<option value="">No plants available</option>';
                return;
            }
            
            // Clear existing options except first
            select.innerHTML = '<option value="">Search plants...</option>';
            
            // Add catalog plants
            catalog.forEach(plant => {
                console.log('[populatePlantCatalog] Adding plant:', plant.common_name, plant.id);
                const option = document.createElement('option');
                option.value = plant.id;
                option.textContent = `${plant.common_name} (${plant.species || plant.variety || ''})`;
                select.appendChild(option);
            });
            
            console.log('[populatePlantCatalog] Final select HTML:', select.innerHTML);
            console.log('[populatePlantCatalog] Final option count:', select.options.length);
            
            this.log(`Populated catalog with ${catalog.length} plants`);
        } catch (error) {
            this.error('Failed to load plant catalog:', error);
            select.innerHTML = '<option value="">Error loading catalog</option>';
        }
    }

    /**
     * Handle catalog plant selection
     */
    async handleCatalogSelection(plantId) {
        if (!plantId) {
            this.clearPlantRequirements();
            return;
        }
        
        try {
            const plant = await this.dataService.getCatalogPlant(plantId);
            if (!plant) {
                this.error('Plant not found in catalog');
                return;
            }
            
            this.log('Selected plant:', plant);
            this.fillPlantFromCatalog(plant);
            this.displayPlantRequirements(plant);
            this._loadPlantProfileSelector();
        } catch (error) {
            this.error('Failed to load plant details:', error);
        }
    }

    /**
     * Fill form fields from catalog plant data
     */
    fillPlantFromCatalog(plant) {
        // Set hidden fields
        document.getElementById('plant-type').value = plant.species || '';
        document.getElementById('plant-variety').value = plant.variety || '';
        document.getElementById('strain-variety').value = plant.variety || '';
        
        // Set suggested values with help text
        if (plant.ph_range) {
            const [minPh, maxPh] = plant.ph_range;
            const avgPh = ((minPh + maxPh) / 2).toFixed(1);
            document.getElementById('medium-ph').value = avgPh;
            const phHelp = document.getElementById('suggested-ph');
            if (phHelp) {
                phHelp.textContent = `(Optimal: ${minPh} - ${maxPh})`;
                phHelp.style.color = 'var(--text-muted)';
            }
        }
        
        // Set expected yield if available
        if (plant.average_yield) {
            document.getElementById('expected-yield').value = plant.average_yield;
        }
        
        // Suggest pot size based on plant difficulty
        const suggestedPotSizes = {
            'easy': 11.4,      // 3 gallon
            'medium': 18.9,    // 5 gallon
            'hard': 26.5       // 7 gallon
        };
        
        if (plant.difficulty_level) {
            const potSize = suggestedPotSizes[plant.difficulty_level] || 11.4;
            document.getElementById('pot-size').value = potSize;
            const potHelp = document.getElementById('suggested-pot-size');
            if (potHelp) {
                potHelp.textContent = `(Recommended for ${plant.difficulty_level} plants)`;
                potHelp.style.color = 'var(--text-muted)';
            }
        }
        
        this.log('Filled form from catalog plant');
    }

    /**
     * Display plant requirements card
     */
    displayPlantRequirements(plant) {
        const card = document.getElementById('plant-requirements-card');
        if (!card) return;
        
        // pH Range
        const phDisplay = document.getElementById('display-ph');
        if (phDisplay && plant.ph_range) {
            phDisplay.textContent = `${plant.ph_range[0]} - ${plant.ph_range[1]}`;
        }
        
        // Soil Moisture
        const moistureDisplay = document.getElementById('display-soil-moisture');
        if (moistureDisplay && plant.sensor_requirements) {
            const { soil_moisture_min, soil_moisture_max } = plant.sensor_requirements;
            moistureDisplay.textContent = `${soil_moisture_min || 0} - ${soil_moisture_max || 100}`;
        }
        
        // Temperature
        const tempDisplay = document.getElementById('display-temperature');
        if (tempDisplay && plant.sensor_requirements) {
            const { temperature_min, temperature_max } = plant.sensor_requirements;
            tempDisplay.textContent = `${temperature_min || 0} - ${temperature_max || 0}`;
        }
        
        // Difficulty Badge
        const difficultyDisplay = document.getElementById('display-difficulty');
        if (difficultyDisplay && plant.difficulty_level) {
            difficultyDisplay.textContent = plant.difficulty_level;
            difficultyDisplay.className = `badge badge-${plant.difficulty_level}`;
        }
        
        // Companion Plants
        const companionDiv = document.getElementById('companion-suggestions');
        if (companionDiv && plant.companion_plants && plant.companion_plants.length > 0) {
            companionDiv.innerHTML = `
                <strong><i class="fas fa-heart"></i> Companion Plants:</strong>
                <div style="margin-top: 0.5rem; display: flex; flex-wrap: wrap; gap: 0.5rem;">
                    ${plant.companion_plants.map(c => 
                        `<span class="badge badge-success" style="font-size: 0.8rem;">${c}</span>`
                    ).join('')}
                </div>
            `;
            companionDiv.style.display = 'block';
        } else {
            companionDiv.style.display = 'none';
        }
        
        // Show card
        card.style.display = 'block';
        this.log('Displayed plant requirements');
    }

    /**
     * Clear plant requirements display
     */
    clearPlantRequirements() {
        const card = document.getElementById('plant-requirements-card');
        if (card) {
            card.style.display = 'none';
        }
        
        // Clear help text
        const phHelp = document.getElementById('suggested-ph');
        const potHelp = document.getElementById('suggested-pot-size');
        if (phHelp) phHelp.textContent = '';
        if (potHelp) potHelp.textContent = '';
        
        this.log('Cleared plant requirements');
    }

    _getUserId() {
        const raw = document.body?.dataset?.userId;
        const parsed = raw ? parseInt(raw, 10) : NaN;
        return Number.isFinite(parsed) ? parsed : 1;
    }

    _initPlantProfileSelector() {
        const container = document.getElementById('plantProfileSelector');
        if (!container || !window.ProfileSelector) {
            return;
        }
        if (this.plantProfileSelector) {
            return;
        }
        this.plantProfileSelector = new window.ProfileSelector(container, {
            onSelect: async (profile, sectionType) => {
                let selectedProfile = profile;
                if (sectionType === 'public' && profile.shared_token) {
                    const imported = await API.PersonalizedLearning.importSharedConditionProfile({
                        user_id: this._getUserId(),
                        token: profile.shared_token,
                        name: profile.name || undefined,
                        mode: 'active',
                    });
                    const payload = imported?.data || imported || {};
                    if (payload.already_imported && window.showToast) {
                        window.showToast('Profile already in your library. Selected existing profile.', 'info');
                    }
                    selectedProfile = payload.profile || imported?.profile || profile;
                }
                const mode = sectionType === 'template' ? 'active' : (profile.mode || 'active');
                this._setPlantProfileSelection(selectedProfile, mode);
                return selectedProfile;
            },
            onLoad: (payload) => this._handlePlantProfileLoad(payload),
        });
    }

    _toggleProfileSelectable(container, hasProfiles) {
        if (!container) return;
        container.hidden = !hasProfiles;
    }

    _handlePlantProfileLoad(payload) {
        const hasProfiles = Boolean(payload?.hasProfiles);
        if (!hasProfiles) {
            const hasFilters = Boolean(
                this._getPlantTypeForProfile() ||
                document.getElementById('plant-stage')?.value?.trim()
            );
            if (hasFilters) {
                this._toggleProfileSelectable(document.getElementById('plantProfileSelectable'), true);
                return;
            }
        }
        this._toggleProfileSelectable(document.getElementById('plantProfileSelectable'), hasProfiles);
    }

    _getPlantTypeForProfile() {
        if (this.currentPlantMode === 'custom') {
            return document.getElementById('custom-plant-type')?.value?.trim();
        }
        return document.getElementById('plant-type')?.value?.trim();
    }

    _loadPlantProfileSelector() {
        if (!this.plantProfileSelector) return;
        const plantType = this._getPlantTypeForProfile();
        const growthStage = document.getElementById('plant-stage')?.value?.trim();
        this.plantProfileSelector.load({
            user_id: this._getUserId(),
            plant_type: plantType || undefined,
            growth_stage: growthStage || undefined,
            target_type: 'plant',
        });
    }

    _setPlantProfileSelection(profile, mode) {
        const idInput = document.getElementById('plantConditionProfileId');
        const modeInput = document.getElementById('plantConditionProfileMode');
        const summary = document.getElementById('plantProfileSelectionSummary');
        const chip = document.getElementById('plantProfileChip');
        if (idInput) idInput.value = profile?.profile_id || '';
        if (modeInput) modeInput.value = mode || 'active';
        if (summary) {
            summary.textContent = profile ? `Selected: ${profile.name || profile.profile_id}` : 'No profile selected';
        }
        if (chip) {
            chip.textContent = profile ? (profile.name || 'Profile selected') : 'No profile';
            chip.classList.toggle('active', Boolean(profile));
        }
    }

    _resetPlantProfileSelection() {
        this._setPlantProfileSelection(null, 'active');
        if (this.plantProfileSelector) {
            this.plantProfileSelector.setSelected('');
        }
    }

    async handleImportPlantProfile() {
        const tokenInput = document.getElementById('plantProfileImportToken');
        if (!tokenInput) return;
        const token = tokenInput.value.trim();
        if (!token) {
            if (window.showNotification) {
                window.showNotification('Paste a share token first', 'warning');
            }
            return;
        }
        try {
            const imported = await API.PersonalizedLearning.importSharedConditionProfile({
                user_id: this._getUserId(),
                token,
                mode: 'active',
            });
            const payload = imported?.data || imported || {};
            if (payload.already_imported && window.showToast) {
                window.showToast('Profile already in your library. Selected existing profile.', 'info');
            }
            const profile = payload.profile || imported?.profile;
            if (profile) {
                this._setPlantProfileSelection(profile, 'active');
                this.plantProfileSelector?.setSelected(profile.profile_id);
                await this._loadPlantProfileSelector();
            }
        } catch (error) {
            this.error('Failed to import profile:', error);
            if (window.showNotification) {
                window.showNotification('Failed to import profile', 'error');
            }
        }
    }

    exportJournal() {
        this.log('Export journal functionality');
        if (window.showNotification) {
            window.showNotification('Journal export feature coming soon! This will allow you to export your plant observations and nutrient records to CSV or PDF.', 'info');
        }
    }

    scrollToGuide() {
        // Navigate to the dedicated plants guide page
        window.location.href = '/plants/guide';
        this.log('Navigating to plants guide page');
    }
}

// Global export
window.PlantsUIManager = PlantsUIManager;
