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
        this.plantDetailsModal = null;
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

        // Link sensor modal form handlers
        const linkSensorForm = document.getElementById('link-sensor-form');
        if (linkSensorForm) {
            this.addEventListener(linkSensorForm, 'submit', (e) => this.handleLinkSensorSubmit(e));
        }

        const cancelLink = document.getElementById('cancel-link-sensor');
        if (cancelLink) {
            this.addEventListener(cancelLink, 'click', () => {
                const modal = document.getElementById('link-sensor-modal');
                if (modal) modal.hidden = true;
            });
        }

        const addNutrientsBtn = document.getElementById('add-nutrients-btn');
        if (addNutrientsBtn) {
            this.addEventListener(addNutrientsBtn, 'click', () => this.openNutrientsModal());
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

        // Plant card action buttons (delegated)
        this.addDelegatedListener(
            document.body,
            'click',
            '[data-action="view-details"]',
            (e) => {
                const trigger = e.target.closest('[data-action="view-details"]');
                this.openPlantDetails(trigger?.dataset?.plantId, trigger?.dataset?.unitId);
            }
        );

        this.addDelegatedListener(
            document.body,
            'click',
            '[data-action="record-observation"]',
            (e) => this.openPlantDetails(e.target.closest('[data-action="record-observation"]')?.dataset?.plantId)
        );

        // Additional actions: link-sensor, edit-plant, delete-plant
        this.addDelegatedListener(
            document.body,
            'click',
            '[data-action="link-sensor"]',
            (e) => this.openLinkSensorModal(e.target.closest('[data-action="link-sensor"]')?.dataset?.plantId)
        );

        this.addDelegatedListener(
            document.body,
            'click',
            '[data-action="delete-plant"]',
            (e) => this.handleDeletePlantClick(e.target.closest('[data-action="delete-plant"]'))
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
            this.log(`Stored ${this.plants.length} plants for selects`);
            
            this.renderHealthOverview(data.plantsHealth);
            this.renderHealthCards(data.plantsHealth.plants);
            this.renderHealthScore(data.healthScore);
            this.renderDiseaseRisk(data.diseaseRisk);
            this.renderJournal(data.journal.entries);
            this.renderHarvests(data.harvests.harvests);
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
                <div class="plant-card-actions">
                    <button class="btn btn-sm" data-action="view-details" data-plant-id="${plant.plant_id}" data-unit-id="${plant.unit_id}" title="View details">
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
                                    <li>${this._formatDiseaseType(risk.disease_type)} (${risk.risk_level})</li>
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

        const plantOptions = this.plants.map(plant => 
            `<option value="${plant.plant_id}">${plant.name} (${plant.plant_type})</option>`
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
            
            // Build JSON payload matching API expectations
            const payload = {
                unit_id: plant.unit_id,
                plant_id: parseInt(plantId),
                health_status: formData.get('health_status'),
                symptoms: symptoms,
                severity_level: parseInt(formData.get('severity_level') || '1'),
                disease_type: formData.get('disease_type') || null,
                affected_parts: formData.get('affected_parts') ? [formData.get('affected_parts')] : [],
                treatment_applied: formData.get('treatment_applied') || null,
                notes: formData.get('notes') || '',
                plant_type: plant.plant_type,
                growth_stage: formData.get('growth_stage') || null
            };
            
            this.log('Observation payload:', payload);
            
            const result = await API.Plant.recordAIHealthObservation(payload);
            this.log('Observation saved successfully', result);
            
            // Close modal and refresh
            const modal = document.getElementById('add-observation-modal');
            if (modal) modal.hidden = true;
            form.reset();
            await this.refresh();
            
        } catch (error) {
            this.error('Failed to save observation:', error);
            alert(`Failed to save observation: ${error.message}`);
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
            alert('Please fill in all required fields');
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
            alert(`Error: ${error.message}`);
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

    openHarvestModal() {
        this.log('Harvest modal not yet implemented');
        alert('Harvest recording will be available soon!');
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
            alert('Select a sensor to link');
            return;
        }

        try {
            await window.API.Plant.linkPlantToSensor(Number(plantId), Number(sensorId));
            alert('Sensor linked');
            const modal = document.getElementById('link-sensor-modal');
            if (modal) modal.hidden = true;
            // Refresh data
            await this.loadAndRender();
        } catch (err) {
            console.error('Failed to link sensor', err);
            alert('Failed to link sensor');
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
            alert('Failed to delete plant');
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
            alert('Paste a share token first');
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
            alert('Failed to import profile');
        }
    }

    exportJournal() {
        this.log('Export journal functionality');
        alert('Journal export feature coming soon!\n\nThis will allow you to export your plant observations and nutrient records to CSV or PDF.');
    }

    scrollToGuide() {
        // Navigate to the dedicated plants guide page
        window.location.href = '/plants/guide';
        this.log('Navigating to plants guide page');
    }
}

// Global export
window.PlantsUIManager = PlantsUIManager;
