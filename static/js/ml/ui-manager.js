/**
 * ML Dashboard UI Manager
 * Handles DOM rendering, events, and modals for ML dashboard
 * 
 * @module ml/ui-manager
 */

class MLUIManager {
    constructor(dataService) {
        this.dataService = dataService || window.MLDataService;
        this.driftChart = null;
        this.comparisonChart = null;
        this.featureChart = null;
        this.diseaseTrendsChart = null;
        this.inlineComparisonChart = null;
        this.currentDriftModel = null;
        
        // Lazy-section load tracking
        this.loadedSections = new Set();
        
        // DOM element cache
        this.elements = {};
    }

    /** Escape HTML to prevent XSS */
    _esc(text) {
        if (window.escapeHtml) return window.escapeHtml(text);
        if (!text) return '';
        const d = document.createElement('div');
        d.textContent = text;
        return d.innerHTML;
    }

    // =========================================================================
    // Initialization
    // =========================================================================

    /**
     * Initialize UI components
     */
    init() {
        this.cacheElements();
        this.attachEventListeners();
    }

    /**
     * Cache frequently accessed DOM elements
     */
    cacheElements() {
        this.elements = {
            // Health
            healthIndicator: document.getElementById('health-indicator'),
            healthStatus: document.getElementById('health-status'),
            websocketStatus: document.getElementById('websocket-status'),
            
            // Alerts
            alertContainer: document.getElementById('alert-container'),
            
            // Training Progress
            trainingProgressCard: document.getElementById('training-progress-card'),
            trainingProgressBar: document.getElementById('training-progress-bar'),
            trainingModelName: document.getElementById('training-model-name'),
            trainingStatus: document.getElementById('training-status'),
            trainingStage: document.getElementById('training-stage'),
            trainingElapsed: document.getElementById('training-elapsed'),
            trainingEta: document.getElementById('training-eta'),
            
            // Models
            modelsListContainer: document.getElementById('models-list-container'),
            modelsCount: document.getElementById('models-count'),
            driftModelSelect: document.getElementById('drift-model-select'),
            
            // Drift
            driftStatus: document.getElementById('drift-status'),
            driftAccuracy: document.getElementById('drift-accuracy'),
            driftConfidence: document.getElementById('drift-confidence'),
            driftErrorRate: document.getElementById('drift-error-rate'),
            driftRecommendation: document.getElementById('drift-recommendation'),
            dataQuality: document.getElementById('data-quality'),
            trainingSamples: document.getElementById('training-samples'),
            driftAlert: document.getElementById('drift-alert'),
            driftAlertMessage: document.getElementById('drift-alert-message'),
            driftChartCanvas: document.getElementById('drift-chart'),
            
            // Jobs
            jobsListContainer: document.getElementById('jobs-list-container'),
            jobsCount: document.getElementById('jobs-count'),
            
            // Training History
            trainingHistoryContainer: document.getElementById('training-history-container'),
            
            // Modals
            modelDetailsModal: document.getElementById('model-details-modal'),
            modelDetailsContent: document.getElementById('model-details-content'),
            featuresModal: document.getElementById('features-modal'),
            featureImportanceChart: document.getElementById('feature-importance-chart'),

            // KPI values
            kpiModelsValue: document.getElementById('kpi-models-value'),
            kpiAccuracyValue: document.getElementById('kpi-accuracy-value'),
            kpiJobsValue: document.getElementById('kpi-jobs-value'),
            kpiHealthValue: document.getElementById('kpi-health-value'),

            // Scheduler
            schedulerStatus: document.getElementById('scheduler-status'),

            // Lazy sections
            continuousBody: document.getElementById('continuous-body'),
            continuousInsightsContainer: document.getElementById('continuous-insights-container'),
            continuousStatusBadge: document.getElementById('continuous-status-badge'),
            trainingDataBody: document.getElementById('training-data-body'),
            trainingDataContainer: document.getElementById('training-data-container'),
            diseaseTrendsBody: document.getElementById('disease-trends-body'),
            diseaseTrendsChart: document.getElementById('disease-trends-chart'),
            modelComparisonBody: document.getElementById('model-comparison-body'),
            comparisonChartCanvas: document.getElementById('comparison-chart-canvas'),

            // ML Readiness (Phase C)
            readinessBody: document.getElementById('ml-readiness-body'),
            readinessModelsContainer: document.getElementById('readiness-models-container'),
            readinessStatusBadge: document.getElementById('readiness-status-badge'),

            // Irrigation ML (Phase C)
            irrigationBody: document.getElementById('irrigation-ml-body'),
            irrigationRequestsContainer: document.getElementById('irrigation-requests-container'),
            irrigationConfigContainer: document.getElementById('irrigation-config-container'),
            irrigationPendingBadge: document.getElementById('irrigation-pending-badge'),

            // A/B Testing (Phase C)
            abTestingBody: document.getElementById('ab-testing-body'),
            abTestsContainer: document.getElementById('ab-tests-container'),
            abTestsCountBadge: document.getElementById('ab-tests-count-badge')
        };
    }

    /**
     * Attach event listeners
     */
    attachEventListeners() {
        // Static buttons
        this.addClickListener('btn-train-new-model', () => this.onTrainNewModel());
        this.addClickListener('btn-compare-models', () => this.scrollToComparisonSection());
        this.addClickListener('btn-refresh-models', () => this.refreshModels());
        this.addClickListener('btn-view-drift-history', () => this.onViewDriftHistory());
        this.addClickListener('btn-refresh-training-history', () => this.refreshTrainingHistory());
        this.addClickListener('btn-cancel-training', () => this.onCancelTraining());
        this.addClickListener('btn-trigger-retraining', () => this.onTriggerRetraining());

        // Scheduler controls
        this.addClickListener('btn-start-scheduler', () => this.onStartScheduler());
        this.addClickListener('btn-stop-scheduler', () => this.onStopScheduler());

        // Continuous monitoring controls
        this.addClickListener('btn-start-monitoring', () => this.onStartMonitoring());
        this.addClickListener('btn-stop-monitoring', () => this.onStopMonitoring());
        this.addClickListener('btn-refresh-insights', () => this.onRefreshInsights());

        // Training data controls
        this.addClickListener('btn-validate-data', () => this.onValidateData());
        this.addClickListener('btn-refresh-training-data', () => this.onRefreshTrainingData());

        // ML Readiness controls
        this.addClickListener('btn-check-all-readiness', () => this.onCheckAllReadiness());

        // Lazy-load section collapse buttons
        document.querySelectorAll('.section-collapse-btn').forEach(btn => {
            btn.addEventListener('click', () => this.toggleSection(btn));
        });

        // Drift model select
        const driftSelect = this.elements.driftModelSelect;
        if (driftSelect) {
            driftSelect.addEventListener('change', (e) => {
                this.currentDriftModel = e.target.value;
                this.loadDriftMetrics();
                this.updateDriftChart();
            });
        }

        // Filter buttons
        document.querySelectorAll('[data-filter]').forEach(btn => {
            btn.addEventListener('click', (e) => {
                document.querySelectorAll('[data-filter]').forEach(b => b.classList.remove('active'));
                e.target.classList.add('active');
                this.filterModels(e.target.dataset.filter);
            });
        });

        // Modal close buttons
        document.querySelectorAll('.btn-close-modal').forEach(btn => {
            btn.addEventListener('click', () => this.closeModal());
        });
        document.querySelectorAll('.btn-close-features-modal').forEach(btn => {
            btn.addEventListener('click', () => this.closeFeaturesModal());
        });

        // Event delegation for models list
        if (this.elements.modelsListContainer) {
            this.elements.modelsListContainer.addEventListener('click', (e) => {
                this.handleModelsListClick(e);
            });
        }

        // Event delegation for jobs list
        if (this.elements.jobsListContainer) {
            this.elements.jobsListContainer.addEventListener('click', (e) => {
                this.handleJobsListClick(e);
            });
        }
    }

    /**
     * Helper to add click listener
     */
    addClickListener(elementId, handler) {
        const el = document.getElementById(elementId);
        if (el) el.addEventListener('click', handler);
    }

    // =========================================================================
    // Models List Rendering
    // =========================================================================

    /**
     * Render models list
     * @param {Array} models - List of models
     */
    renderModels(models) {
        const container = this.elements.modelsListContainer;
        const countBadge = this.elements.modelsCount;
        const modelSelect = this.elements.driftModelSelect;

        if (!container) return;

        if (models.length > 0) {
            if (countBadge) countBadge.textContent = `${models.length} Models`;

            let html = '<ul class="models-list">';
            models.forEach(model => {
                html += this.renderModelItem(model);
            });
            html += '</ul>';
            container.innerHTML = html;

            // Update model selector
            if (modelSelect) {
                modelSelect.innerHTML = '<option value="">Select Model</option>';
                models.forEach(model => {
                    const option = document.createElement('option');
                    option.value = model.name;
                    option.textContent = `${model.name} (v${model.latest_version})`;
                    modelSelect.appendChild(option);
                });

                // Select first model if none selected
                if (!this.currentDriftModel && models.length > 0) {
                    this.currentDriftModel = models[0].name;
                    modelSelect.value = this.currentDriftModel;
                }
            }
        } else {
            if (countBadge) countBadge.textContent = '0 Models';
            container.innerHTML = `
                <div class="empty-state">
                    <div class="empty-state-icon">📦</div>
                    <p>No models registered yet</p>
                </div>
            `;
        }
    }

    /**
     * Render a single model item
     */
    renderModelItem(model) {
        const statusClass = model.active ? 'badge-success' : 'badge-warning';
        const statusText = model.active ? 'Active' : 'Inactive';
        const esc = (t) => this._esc(t);

        return `
            <li class="model-item" data-model-name="${esc(model.name)}">
                <div class="model-header">
                    <span class="model-name">${esc(model.name)}</span>
                    <span class="card-badge ${statusClass}">${statusText}</span>
                </div>
                <div class="model-version">Version: ${esc(String(model.latest_version))}</div>
                <div class="model-metrics">
                    <div class="model-metric">
                        <span class="model-metric-label">Accuracy</span>
                        <span class="model-metric-value">${model.accuracy ? (model.accuracy * 100).toFixed(1) + '%' : '--'}</span>
                    </div>
                    <div class="model-metric">
                        <span class="model-metric-label">MAE</span>
                        <span class="model-metric-value">${model.mae ? model.mae.toFixed(3) : '--'}</span>
                    </div>
                    <div class="model-metric">
                        <span class="model-metric-label">Trained</span>
                        <span class="model-metric-value">${this.formatDate(model.trained_at)}</span>
                    </div>
                </div>
                <div class="btn-group">
                    <button class="btn btn-sm btn-primary btn-view-details">
                        📊 Details
                    </button>
                    <button class="btn btn-sm btn-info btn-view-features">
                        🔍 Features
                    </button>
                    <button class="btn btn-sm btn-success btn-retrain" ${model.active ? '' : 'disabled'}>
                        🔄 Retrain
                    </button>
                    ${!model.active ? `
                        <button class="btn btn-sm btn-success btn-activate" data-version="${model.latest_version}">
                            ✅ Activate
                        </button>
                    ` : ''}
                </div>
            </li>
        `;
    }

    /**
     * Filter models by type
     */
    filterModels(filter) {
        const modelItems = document.querySelectorAll('.model-item');

        modelItems.forEach(item => {
            const modelName = item.dataset.modelName.toLowerCase();
            if (filter === 'all' || modelName.includes(filter.toLowerCase())) {
                item.style.display = '';
            } else {
                item.style.display = 'none';
            }
        });

        // Update count
        const visibleCount = document.querySelectorAll('.model-item:not([style*="display: none"])').length;
        if (this.elements.modelsCount) {
            this.elements.modelsCount.textContent = `${visibleCount} Model${visibleCount !== 1 ? 's' : ''}`;
        }
    }

    /**
     * Handle clicks on models list
     */
    handleModelsListClick(e) {
        const target = e.target.closest('button');
        if (!target) return;

        const modelItem = target.closest('.model-item');
        if (!modelItem) return;

        const modelName = modelItem.dataset.modelName;

        if (target.classList.contains('btn-view-details')) {
            this.showModelDetails(modelName);
        } else if (target.classList.contains('btn-view-features')) {
            this.showFeaturesModal(modelName);
        } else if (target.classList.contains('btn-retrain')) {
            this.onRetrainModel(modelName);
        } else if (target.classList.contains('btn-activate')) {
            this.onActivateModel(modelName, target.dataset.version);
        }
    }

    // =========================================================================
    // Drift Monitoring UI
    // =========================================================================

    /**
     * Render drift metrics
     * @param {Object} data - Drift data
     */
    renderDriftMetrics(data) {
        if (!data || data.drift_detected === undefined) return;

        // Status badge
        if (this.elements.driftStatus) {
            if (data.drift_detected) {
                this.elements.driftStatus.className = 'card-badge badge-warning';
                this.elements.driftStatus.textContent = 'Drift Detected';
            } else {
                this.elements.driftStatus.className = 'card-badge badge-success';
                this.elements.driftStatus.textContent = 'Healthy';
            }
        }

        // Accuracy
        if (this.elements.driftAccuracy) {
            this.elements.driftAccuracy.textContent = data.current_accuracy 
                ? (data.current_accuracy * 100).toFixed(1) + '%' : '--';
        }

        // Confidence with color-coded badge
        if (this.elements.driftConfidence) {
            const confValue = data.mean_confidence || 0;
            this.elements.driftConfidence.textContent = (confValue * 100).toFixed(1) + '%';
            
            if (confValue >= 0.9) {
                this.elements.driftConfidence.className = 'confidence-badge badge badge-success';
            } else if (confValue >= 0.7) {
                this.elements.driftConfidence.className = 'confidence-badge badge badge-warning';
            } else {
                this.elements.driftConfidence.className = 'confidence-badge badge badge-danger';
            }
        }

        // Error rate
        if (this.elements.driftErrorRate) {
            this.elements.driftErrorRate.textContent = data.error_rate 
                ? (data.error_rate * 100).toFixed(1) + '%' : '--';
        }

        // Data quality
        if (this.elements.dataQuality) {
            const quality = data.data_quality || 0;
            this.elements.dataQuality.textContent = (quality * 100).toFixed(0) + '%';
            
            if (quality >= 0.8) {
                this.elements.dataQuality.className = 'badge badge-success';
            } else if (quality >= 0.6) {
                this.elements.dataQuality.className = 'badge badge-warning';
            } else {
                this.elements.dataQuality.className = 'badge badge-danger';
            }
        }

        // Training samples
        if (this.elements.trainingSamples) {
            this.elements.trainingSamples.textContent = `(${data.training_samples || 0} samples)`;
        }

        // Recommendation
        if (this.elements.driftRecommendation) {
            this.elements.driftRecommendation.textContent = data.recommendation || 'Continue monitoring';
        }

        // Drift alert
        if (data.drift_detected) {
            if (this.elements.driftAlert && this.elements.driftAlertMessage) {
                this.elements.driftAlert.style.display = 'block';
                this.elements.driftAlertMessage.textContent = data.recommendation || 'Model performance degraded';
            }
        } else if (this.elements.driftAlert) {
            this.elements.driftAlert.style.display = 'none';
        }
    }

    /**
     * Render drift chart
     * @param {Array} history - Drift history data
     */
    renderDriftChart(history) {
        if (!history || history.length === 0) {
            console.warn('No drift history data available');
            return;
        }

        const ctx = this.elements.driftChartCanvas?.getContext('2d');
        if (!ctx) return;

        // Destroy existing chart
        if (this.driftChart) {
            this.driftChart.destroy();
        }

        // Parse history data
        const timestamps = history.map(h => 
            new Date(h.timestamp).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
        );
        const accuracies = history.map(h => h.accuracy * 100);
        const errorRates = history.map(h => h.error_rate * 100);

        // Create new chart
        this.driftChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: timestamps,
                datasets: [
                    {
                        label: 'Accuracy (%)',
                        data: accuracies,
                        borderColor: '#10b981',
                        backgroundColor: 'rgba(16, 185, 129, 0.1)',
                        tension: 0.4
                    },
                    {
                        label: 'Error Rate (%)',
                        data: errorRates,
                        borderColor: '#ef4444',
                        backgroundColor: 'rgba(239, 68, 68, 0.1)',
                        tension: 0.4
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: 'top' },
                    title: { display: false }
                },
                scales: {
                    y: { beginAtZero: true, max: 100 }
                }
            }
        });
    }

    // =========================================================================
    // Jobs List Rendering
    // =========================================================================

    /**
     * Render retraining jobs
     * @param {Object} data - Jobs data
     */
    renderJobs(data) {
        const container = this.elements.jobsListContainer;
        const countBadge = this.elements.jobsCount;

        if (!container) return;

        if (data.jobs && data.jobs.length > 0) {
            if (countBadge) countBadge.textContent = `${data.jobs.length} Jobs`;

            let html = '<ul class="job-list">';
            data.jobs.forEach(job => {
                const statusClass = job.enabled ? 'badge-success' : 'badge-warning';
                const statusText = job.enabled ? 'Enabled' : 'Disabled';

                html += `
                    <li class="job-item">
                        <div class="job-info">
                            <div class="job-name">
                                ${this._esc(job.model_name)}
                                <span class="card-badge ${statusClass}">${statusText}</span>
                            </div>
                            <div class="job-schedule">${this._esc(job.schedule_description || 'Custom schedule')}</div>
                        </div>
                        <div class="job-actions">
                            <button class="btn btn-sm btn-success btn-run-job" data-job-id="${job.job_id}">
                                ▶️ Run Now
                            </button>
                            <button class="btn btn-sm btn-secondary btn-toggle-job" 
                                    data-job-id="${job.job_id}" 
                                    data-enabled="${job.enabled}">
                                ${job.enabled ? '⏸️ Pause' : '▶️ Enable'}
                            </button>
                        </div>
                    </li>
                `;
            });
            html += '</ul>';
            container.innerHTML = html;
        } else {
            if (countBadge) countBadge.textContent = '0 Jobs';
            container.innerHTML = `
                <div class="empty-state">
                    <div class="empty-state-icon">📅</div>
                    <p>No retraining jobs configured</p>
                </div>
            `;
        }
    }

    /**
     * Handle clicks on jobs list
     */
    handleJobsListClick(e) {
        const target = e.target.closest('button');
        if (!target) return;

        if (target.classList.contains('btn-run-job')) {
            this.onRunJob(target.dataset.jobId);
        } else if (target.classList.contains('btn-toggle-job')) {
            const enabled = target.dataset.enabled === 'true';
            this.onToggleJob(target.dataset.jobId, !enabled);
        }
    }

    // =========================================================================
    // Training History Rendering
    // =========================================================================

    /**
     * Render training history
     * @param {Object} data - Training history data
     */
    renderTrainingHistory(data) {
        const container = this.elements.trainingHistoryContainer;
        if (!container) return;

        if (data.history && data.history.length > 0) {
            let html = '<div class="table-responsive"><table class="table table-hover">';
            html += `
                <thead>
                    <tr>
                        <th>Model</th>
                        <th>Version</th>
                        <th>Accuracy</th>
                        <th>MAE</th>
                        <th>Data Points</th>
                        <th>Trained At</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody>
            `;

            data.history.forEach(event => {
                const statusClass = event.status === 'success' ? 'badge-success' : 'badge-error';
                html += `
                    <tr>
                        <td><strong>${this._esc(event.model_name)}</strong></td>
                        <td>v${this._esc(String(event.version))}</td>
                        <td>${event.accuracy ? (event.accuracy * 100).toFixed(1) + '%' : '--'}</td>
                        <td>${event.mae ? event.mae.toFixed(3) : '--'}</td>
                        <td>${event.data_points || '--'}</td>
                        <td><span class="timestamp">${this.formatDateTime(event.trained_at)}</span></td>
                        <td><span class="card-badge ${statusClass}">${this._esc(event.status)}</span></td>
                    </tr>
                `;
            });

            html += '</tbody></table></div>';
            container.innerHTML = html;
        } else {
            container.innerHTML = `
                <div class="empty-state">
                    <div class="empty-state-icon">🎓</div>
                    <p>No training events recorded</p>
                </div>
            `;
        }
    }

    // =========================================================================
    // Training Progress UI
    // =========================================================================

    /**
     * Update training progress display
     * @param {Object} data - Progress data
     */
    updateTrainingProgress(data) {
        const card = this.elements.trainingProgressCard;
        const bar = this.elements.trainingProgressBar;

        if (!card || !bar) return;

        // Show progress card
        card.style.display = 'block';

        // Update model name
        if (this.elements.trainingModelName) {
            this.elements.trainingModelName.textContent = data.model_name || 'Training Model';
        }

        // Update progress bar
        const progress = Math.min(100, Math.max(0, data.progress || 0));
        bar.style.width = progress + '%';
        bar.textContent = progress.toFixed(0) + '%';
        bar.setAttribute('aria-valuenow', progress);

        // Update stage badge
        if (this.elements.trainingStage && data.stage) {
            this.elements.trainingStage.textContent = data.stage;
            
            if (data.stage.toLowerCase().includes('complete')) {
                this.elements.trainingStage.className = 'badge badge-success';
            } else if (data.stage.toLowerCase().includes('training')) {
                this.elements.trainingStage.className = 'badge badge-primary';
            } else {
                this.elements.trainingStage.className = 'badge badge-info';
            }
        }

        // Update status message
        if (this.elements.trainingStatus) {
            let message = data.message || 'Training in progress...';
            if (data.metrics) {
                if (data.metrics.loss !== undefined) {
                    message += ` | Loss: ${data.metrics.loss.toFixed(4)}`;
                }
                if (data.metrics.accuracy !== undefined) {
                    message += ` | Accuracy: ${(data.metrics.accuracy * 100).toFixed(1)}%`;
                }
            }
            this.elements.trainingStatus.textContent = message;
        }

        // Update elapsed time
        if (this.elements.trainingElapsed && data.elapsed_seconds) {
            const minutes = Math.floor(data.elapsed_seconds / 60);
            const seconds = Math.floor(data.elapsed_seconds % 60);
            this.elements.trainingElapsed.textContent = `Elapsed: ${minutes}m ${seconds}s`;
        }

        // Update ETA
        if (this.elements.trainingEta && data.eta_seconds) {
            const minutes = Math.floor(data.eta_seconds / 60);
            const seconds = Math.floor(data.eta_seconds % 60);
            this.elements.trainingEta.textContent = `ETA: ${minutes}m ${seconds}s`;
        }

        // Hide progress card when complete
        if (progress >= 100) {
            setTimeout(() => {
                card.style.display = 'none';
            }, 3000);
        }
    }

    /**
     * Hide training progress
     */
    hideTrainingProgress() {
        if (this.elements.trainingProgressCard) {
            this.elements.trainingProgressCard.style.display = 'none';
        }
    }

    // =========================================================================
    // Health & Status UI
    // =========================================================================

    /**
     * Update health indicator
     * @param {boolean} healthy - Health status
     * @param {string} [message] - Status message
     */
    updateHealthIndicator(healthy, message) {
        if (this.elements.healthIndicator) {
            this.elements.healthIndicator.className = healthy ? 'health-dot healthy' : 'health-dot error';
        }
        if (this.elements.healthStatus) {
            this.elements.healthStatus.textContent = message || 
                (healthy ? 'All Systems Operational' : 'System Issues Detected');
        }
    }

    /**
     * Update WebSocket connection status
     * @param {boolean} connected - Connection status
     */
    updateConnectionStatus(connected) {
        if (this.elements.websocketStatus) {
            this.elements.websocketStatus.className = connected 
                ? 'ws-status-dot connected' 
                : 'ws-status-dot disconnected';
            this.elements.websocketStatus.title = connected 
                ? 'Real-time updates active' 
                : 'Polling mode';
        }
    }

    // =========================================================================
    // Alerts
    // =========================================================================

    /**
     * Show an alert message
     * @param {string} type - Alert type (success, info, warning, danger, error)
     * @param {string} message - Alert message
     */
    showAlert(type, message) {
        const container = this.elements.alertContainer;
        if (!container) return;

        const normalizedType = type === 'danger' ? 'error' : type;
        const alertId = 'alert-' + Date.now();

        const alertHtml = `
            <div id="${alertId}" class="alert alert-${normalizedType}">
                <span>${this._esc(message)}</span>
            </div>
        `;

        container.insertAdjacentHTML('beforeend', alertHtml);

        // Auto-dismiss after 5 seconds
        setTimeout(() => {
            const alert = document.getElementById(alertId);
            if (alert) {
                alert.style.opacity = '0';
                setTimeout(() => alert.remove(), 300);
            }
        }, 5000);
    }

    // =========================================================================
    // Modals
    // =========================================================================

    /**
     * Show model details modal
     * @param {string} modelName - Model name
     */
    async showModelDetails(modelName) {
        try {
            const data = await this.dataService.getModel(modelName);
            
            let html = `
                <h4>${this._esc(modelName)}</h4>
                <p><strong>Status:</strong> ${data.active ? 'Active' : 'Inactive'}</p>
                <p><strong>Latest Version:</strong> ${this._esc(String(data.latest_version))}</p>
                <p><strong>Trained:</strong> ${this.formatDateTime(data.trained_at)}</p>
                
                <h5 class="mt-3">Performance Metrics</h5>
                <table class="table">
                    <tr><td>Accuracy</td><td>${data.accuracy ? (data.accuracy * 100).toFixed(1) + '%' : '--'}</td></tr>
                    <tr><td>MAE</td><td>${data.mae ? data.mae.toFixed(3) : '--'}</td></tr>
                    <tr><td>R² Score</td><td>${data.r2 ? data.r2.toFixed(3) : '--'}</td></tr>
                </table>
            `;

            if (data.versions && data.versions.length > 0) {
                html += '<h5 class="mt-3">Version History</h5><ul class="list-group">';
                data.versions.forEach(v => {
                    html += `
                        <li class="list-group-item">
                            <strong>Version ${this._esc(String(v.version))}</strong> - ${this.formatDateTime(v.trained_at)}
                            ${v.active ? '<span class="badge bg-success">Active</span>' : ''}
                        </li>
                    `;
                });
                html += '</ul>';
            }

            if (this.elements.modelDetailsContent) {
                this.elements.modelDetailsContent.innerHTML = html;
            }

            const modal = new bootstrap.Modal(this.elements.modelDetailsModal);
            modal.show();
        } catch (error) {
            console.error('Failed to load model details:', error);
            this.showAlert('danger', 'Failed to load model details.');
        }
    }

    /**
     * Scroll to and expand the inline model comparison section
     */
    scrollToComparisonSection() {
        const section = document.getElementById('section-model-comparison');
        const btn = section?.querySelector('.section-collapse-btn');
        if (!section || !btn) return;

        // Expand if collapsed
        if (btn.getAttribute('aria-expanded') !== 'true') {
            this.toggleSection(btn);
        }

        // Scroll into view
        section.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    /**
     * Render model comparison chart (modal version — kept for backward compat)
     */
    renderModelComparison(models) {
        const container = this.elements.modelComparisonChart;
        if (!container) return;

        const canvas = document.createElement('canvas');
        canvas.id = 'comparison-chart';
        container.innerHTML = '';
        container.appendChild(canvas);

        const modelNames = models.map(m => m.name);
        const accuracyData = models.map(m => (m.accuracy * 100) || 0);
        const r2Data = models.map(m => (m.r2_score * 100) || 0);

        if (this.comparisonChart) {
            this.comparisonChart.destroy();
        }
        this.comparisonChart = new Chart(canvas.getContext('2d'), {
            type: 'bar',
            data: {
                labels: modelNames,
                datasets: [
                    {
                        label: 'Accuracy (%)',
                        data: accuracyData,
                        backgroundColor: 'rgba(102, 126, 234, 0.7)',
                        borderColor: 'rgb(102, 126, 234)',
                        borderWidth: 1
                    },
                    {
                        label: 'R² Score (%)',
                        data: r2Data,
                        backgroundColor: 'rgba(118, 75, 162, 0.7)',
                        borderColor: 'rgb(118, 75, 162)',
                        borderWidth: 1
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: { beginAtZero: true, max: 100, title: { display: true, text: 'Score (%)' } }
                },
                plugins: {
                    title: { display: true, text: 'Model Performance Comparison' },
                    legend: { display: true, position: 'top' }
                }
            }
        });
    }

    /**
     * Show feature importance modal
     * @param {string} modelName - Model name
     */
    async showFeaturesModal(modelName) {
        const modal = this.elements.featuresModal;
        if (!modal) return;

        modal.style.display = 'block';
        modal.classList.add('show');
        document.body.classList.add('modal-open');

        await this.loadFeatureImportance(modelName);
    }

    /**
     * Load and render feature importance
     */
    async loadFeatureImportance(modelName) {
        try {
            const data = await this.dataService.getModelFeatures(modelName);
            const container = this.elements.featureImportanceChart;

            if (data.features && data.features.length > 0) {
                this.renderFeatureImportance(data.features, modelName);
            } else if (container) {
                container.innerHTML = '<div class="alert alert-info">No feature importance data available for this model.</div>';
            }
        } catch (error) {
            console.error('Error loading feature importance:', error);
            if (this.elements.featureImportanceChart) {
                this.elements.featureImportanceChart.innerHTML = '<div class="alert alert-danger">Failed to load feature importance data.</div>';
            }
        }
    }

    /**
     * Render feature importance chart
     */
    renderFeatureImportance(features, modelName) {
        const container = this.elements.featureImportanceChart;
        if (!container) return;

        const canvas = document.createElement('canvas');
        canvas.id = 'features-chart';
        container.innerHTML = '';
        container.appendChild(canvas);

        const featureNames = features.map(f => f.name);
        const importanceValues = features.map(f => f.importance * 100);

        if (this.featureChart) {
            this.featureChart.destroy();
        }
        this.featureChart = new Chart(canvas.getContext('2d'), {
            type: 'bar',
            data: {
                labels: featureNames,
                datasets: [{
                    label: 'Importance (%)',
                    data: importanceValues,
                    backgroundColor: 'rgba(16, 185, 129, 0.7)',
                    borderColor: 'rgb(16, 185, 129)',
                    borderWidth: 1
                }]
            },
            options: {
                indexAxis: 'y',
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: { beginAtZero: true, max: 100, title: { display: true, text: 'Importance (%)' } }
                },
                plugins: {
                    title: { display: true, text: `Feature Importance: ${modelName}` },
                    legend: { display: false }
                }
            }
        });
    }

    /**
     * Close model details modal
     */
    closeModal() {
        const modal = this.elements.modelDetailsModal;
        if (modal) {
            modal.style.display = 'none';
            modal.classList.remove('show');
            document.querySelector('.modal-backdrop')?.remove();
            document.body.classList.remove('modal-open');
            document.body.style.removeProperty('overflow');
            document.body.style.removeProperty('padding-right');
        }
    }

    /**
     * Close comparison section (no-op, kept for backward compat)
     */
    closeComparisonModal() {
        // Comparison is now inline, no modal to close
    }

    /**
     * Close features modal
     */
    closeFeaturesModal() {
        const modal = this.elements.featuresModal;
        if (modal) {
            modal.style.display = 'none';
            modal.classList.remove('show');
            document.body.classList.remove('modal-open');
        }
    }

    // =========================================================================
    // KPI Rendering
    // =========================================================================

    /**
     * Update KPI card values
     * @param {Object} kpis - { activeModels, bestAccuracy, jobCount, healthStatus }
     */
    renderKPIs(kpis) {
        if (this.elements.kpiModelsValue && kpis.activeModels !== undefined) {
            this.elements.kpiModelsValue.textContent = kpis.activeModels;
        }
        if (this.elements.kpiAccuracyValue && kpis.bestAccuracy !== undefined) {
            this.elements.kpiAccuracyValue.textContent = kpis.bestAccuracy !== null
                ? (kpis.bestAccuracy * 100).toFixed(1) + '%' : '--';
        }
        if (this.elements.kpiJobsValue && kpis.jobCount !== undefined) {
            this.elements.kpiJobsValue.textContent = kpis.jobCount;
        }
        if (this.elements.kpiHealthValue && kpis.healthStatus !== undefined) {
            this.elements.kpiHealthValue.textContent = kpis.healthStatus ? '✓ OK' : '⚠ Issue';
        }
    }

    // =========================================================================
    // Scheduler Status
    // =========================================================================

    /**
     * Render scheduler status badge
     * @param {Object} data - Retraining status data
     */
    renderSchedulerStatus(data) {
        const badge = this.elements.schedulerStatus;
        if (!badge) return;

        const running = data.scheduler_running || data.running || false;
        badge.className = `scheduler-badge ${running ? 'running' : 'stopped'}`;
        badge.innerHTML = `<i class="fas fa-circle" style="font-size:0.5rem"></i> ${running ? 'Running' : 'Stopped'}`;
    }

    // =========================================================================
    // Lazy Section Toggle
    // =========================================================================

    /**
     * Toggle a collapsible section and trigger first-load
     * @param {HTMLElement} btn - Collapse button element
     */
    toggleSection(btn) {
        const sectionKey = btn.dataset.section;
        const targetId = btn.getAttribute('aria-controls');
        const body = document.getElementById(targetId);
        if (!body) return;

        const isExpanded = btn.getAttribute('aria-expanded') === 'true';
        btn.setAttribute('aria-expanded', !isExpanded);
        body.classList.toggle('collapsed');

        // Trigger first-load for this section
        if (!isExpanded && !this.loadedSections.has(sectionKey)) {
            this.loadedSections.add(sectionKey);
            window.dispatchEvent(new CustomEvent('ml:section-expand', {
                detail: { section: sectionKey }
            }));
        }
    }

    // =========================================================================
    // Continuous Monitoring Insights
    // =========================================================================

    /**
     * Render continuous monitoring status and insights
     * @param {Object} statusData - Monitoring status
     * @param {Object} insightsData - Critical insights
     */
    renderContinuousInsights(statusData, insightsData) {
        // Status badge
        const badge = this.elements.continuousStatusBadge;
        if (badge && statusData) {
            const running = statusData.is_running || statusData.running || false;
            badge.textContent = running ? 'Active' : 'Inactive';
            badge.className = `badge rounded-pill ${running
                ? 'bg-success-subtle text-success'
                : 'bg-secondary-subtle text-secondary'}`;
        }

        // Insights feed
        const container = this.elements.continuousInsightsContainer;
        if (!container) return;

        const insights = insightsData?.insights || insightsData || [];
        if (!Array.isArray(insights) || insights.length === 0) {
            container.innerHTML = `
                <div class="text-center py-4 text-muted">
                    <i class="fas fa-check-circle fa-2x mb-2 opacity-50"></i>
                    <p class="mb-0 small">No critical insights at this time</p>
                </div>`;
            return;
        }

        let html = '';
        insights.forEach(insight => {
            const severityClass = insight.severity === 'critical' ? 'danger'
                : insight.severity === 'warning' ? 'warning' : 'info';
            html += `
                <div class="insight-item insight-${severityClass}">
                    <div class="d-flex justify-content-between align-items-start">
                        <div>
                            <strong>${this._esc(insight.title || insight.type || 'Insight')}</strong>
                            <p class="mb-0 small text-muted">${this._esc(insight.message || insight.description || '')}</p>
                        </div>
                        <span class="badge bg-${severityClass}-subtle text-${severityClass} small">${this._esc(insight.severity || 'info')}</span>
                    </div>
                    ${insight.timestamp ? `<div class="text-muted smallest mt-1">${this.formatDateTime(insight.timestamp)}</div>` : ''}
                </div>`;
        });
        container.innerHTML = html;
    }

    // =========================================================================
    // Training Data Quality
    // =========================================================================

    /**
     * Render training data summary and quality metrics
     * @param {Object} summary - Training data summary
     * @param {Object} quality - Quality metrics per dataset type
     */
    renderTrainingDataQuality(summary, quality) {
        const container = this.elements.trainingDataContainer;
        if (!container) return;

        let html = '';

        // Summary card if available
        if (summary) {
            const datasets = summary.datasets || summary.data_types || {};
            const totalSamples = summary.total_samples || Object.values(datasets).reduce((s, d) => s + (d.count || 0), 0);
            html += `
                <div class="data-quality-card">
                    <div class="data-quality-card-header">
                        <i class="fas fa-layer-group"></i> Total Samples
                    </div>
                    <div class="data-quality-card-value">${totalSamples.toLocaleString()}</div>
                </div>`;
        }

        // Quality cards per dataset type
        if (quality) {
            const types = ['disease', 'climate', 'growth'];
            types.forEach(type => {
                const q = quality[type];
                if (!q) return;
                const score = q.average_quality_score || q.quality_score || 0;
                const scorePct = (score * 100).toFixed(0);
                const samples = q.total_samples || q.sample_count || 0;
                const variant = score >= 0.8 ? 'success' : score >= 0.5 ? 'warning' : 'danger';

                html += `
                    <div class="data-quality-card">
                        <div class="data-quality-card-header">
                            <i class="fas fa-${type === 'disease' ? 'virus' : type === 'climate' ? 'cloud-sun' : 'seedling'}"></i>
                            ${this._esc(type.charAt(0).toUpperCase() + type.slice(1))}
                        </div>
                        <div class="data-quality-card-value">
                            <span class="badge bg-${variant}-subtle text-${variant} border border-${variant} fs-6">${scorePct}%</span>
                        </div>
                        <div class="text-muted smallest">${samples.toLocaleString()} samples</div>
                    </div>`;
            });
        }

        if (!html) {
            html = `
                <div class="text-center py-4 text-muted" style="grid-column:1/-1">
                    <i class="fas fa-database fa-2x mb-2 opacity-25"></i>
                    <p class="mb-0 small">No training data available</p>
                </div>`;
        }

        container.innerHTML = html;
    }

    // =========================================================================
    // Disease Trends Chart
    // =========================================================================

    /**
     * Render disease trends time-series chart
     * @param {Object} data - Disease trends data from backend
     */
    renderDiseaseTrends(data) {
        const canvas = this.elements.diseaseTrendsChart;
        if (!canvas) return;
        const ctx = canvas.getContext('2d');

        if (this.diseaseTrendsChart) {
            this.diseaseTrendsChart.destroy();
        }

        const dailyCounts = data.daily_counts || [];
        if (dailyCounts.length === 0) {
            canvas.parentElement.innerHTML = `
                <div class="text-center py-4 text-muted">
                    <i class="fas fa-chart-line fa-2x mb-2 opacity-25"></i>
                    <p class="mb-0 small">No disease trend data available</p>
                </div>`;
            return;
        }

        const labels = dailyCounts.map(d => d.date || d.day);
        const counts = dailyCounts.map(d => d.count || d.total || 0);

        this.diseaseTrendsChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels,
                datasets: [{
                    label: 'Disease Detections',
                    data: counts,
                    borderColor: 'var(--danger-500, #ef4444)',
                    backgroundColor: 'rgba(239, 68, 68, 0.08)',
                    fill: true,
                    tension: 0.4,
                    pointRadius: 2,
                    pointHoverRadius: 5
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    title: { display: false }
                },
                scales: {
                    y: { beginAtZero: true, ticks: { precision: 0 } }
                }
            }
        });
    }

    // =========================================================================
    // Model Comparison (Inline Lazy Panel)
    // =========================================================================

    /**
     * Render inline model comparison chart using backend comparison endpoint
     * @param {Object} data - Comparison data { comparison: [{ name, accuracy, ... }] }
     */
    renderModelComparisonInline(data) {
        const canvas = this.elements.comparisonChartCanvas;
        if (!canvas) return;
        const ctx = canvas.getContext('2d');

        if (this.inlineComparisonChart) {
            this.inlineComparisonChart.destroy();
        }

        const items = data.comparison || [];
        if (items.length === 0) {
            canvas.parentElement.innerHTML = `
                <div class="text-center py-4 text-muted">
                    <i class="fas fa-chart-column fa-2x mb-2 opacity-25"></i>
                    <p class="mb-0 small">Not enough models for comparison (need at least 2)</p>
                </div>`;
            return;
        }

        const names = items.map(m => m.name);
        const accuracy = items.map(m => (m.accuracy || 0) * 100);
        const f1 = items.map(m => (m.f1_score || 0) * 100);

        this.inlineComparisonChart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: names,
                datasets: [
                    {
                        label: 'Accuracy (%)',
                        data: accuracy,
                        backgroundColor: 'rgba(59, 130, 246, 0.7)',
                        borderColor: 'rgb(59, 130, 246)',
                        borderWidth: 1
                    },
                    {
                        label: 'F1 Score (%)',
                        data: f1,
                        backgroundColor: 'rgba(139, 92, 246, 0.7)',
                        borderColor: 'rgb(139, 92, 246)',
                        borderWidth: 1
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: { beginAtZero: true, max: 100, title: { display: true, text: 'Score (%)' } }
                },
                plugins: {
                    legend: { position: 'top' }
                }
            }
        });
    }

    // =========================================================================
    // ML Readiness (Phase C)
    // =========================================================================

    /**
     * Render ML readiness model cards for a unit
     * @param {Object} data - Readiness data from backend
     */
    renderMLReadiness(data) {
        const container = this.elements.readinessModelsContainer;
        if (!container) return;

        const models = data?.models || {};
        const entries = Object.values(models);

        // Update badge
        const badge = this.elements.readinessStatusBadge;
        if (badge) {
            const ready = entries.filter(m => m.is_ready).length;
            const activated = entries.filter(m => m.is_activated).length;
            if (entries.length === 0) {
                badge.textContent = 'No models';
                badge.className = 'badge bg-secondary-subtle text-secondary rounded-pill';
            } else if (activated === entries.length) {
                badge.textContent = 'All Active';
                badge.className = 'badge bg-success-subtle text-success rounded-pill';
            } else if (ready > 0) {
                badge.textContent = `${ready} Ready`;
                badge.className = 'badge bg-warning-subtle text-warning rounded-pill';
            } else {
                badge.textContent = 'Collecting Data';
                badge.className = 'badge bg-info-subtle text-info rounded-pill';
            }
        }

        if (entries.length === 0) {
            container.innerHTML = `
                <div class="text-center py-4 text-muted" style="grid-column:1/-1">
                    <i class="fas fa-robot fa-2x mb-2 opacity-25"></i>
                    <p class="mb-0 small">No irrigation ML models configured for this unit</p>
                </div>`;
            return;
        }

        container.innerHTML = entries.map(model => {
            const pct = Math.min(100, model.progress_percent || 0);
            const variant = model.is_activated ? 'success' : model.is_ready ? 'warning' : 'info';
            const statusLabel = model.is_activated ? 'Active'
                : model.is_ready ? 'Ready to Activate' : `${model.samples_needed || '?'} samples needed`;
            const barColor = model.is_activated ? 'var(--success-500)' : model.is_ready ? 'var(--warning-500)' : 'var(--ml-blue)';

            return `
                <div class="readiness-card">
                    <div class="readiness-card-header">
                        <strong>${this._esc(model.display_name || model.model_name)}</strong>
                        <span class="badge bg-${variant}-subtle text-${variant} rounded-pill small">${statusLabel}</span>
                    </div>
                    <p class="text-muted smallest mb-2">${this._esc(model.description || '')}</p>
                    <div class="progress mb-2" style="height: 0.5rem;">
                        <div class="progress-bar" style="width:${pct}%; background:${barColor}" role="progressbar"
                             aria-valuenow="${pct}" aria-valuemin="0" aria-valuemax="100"></div>
                    </div>
                    <div class="d-flex justify-content-between align-items-center">
                        <span class="smallest text-muted">${model.current_samples || 0} / ${model.required_samples || '?'} samples (${pct.toFixed(0)}%)</span>
                        ${model.is_ready && !model.is_activated
                            ? `<button class="btn btn-sm btn-outline-success btn-activate-model" data-model="${this._esc(model.model_name)}">
                                <i class="fas fa-power-off"></i> Activate
                               </button>`
                            : model.is_activated
                            ? `<button class="btn btn-sm btn-outline-secondary btn-deactivate-model" data-model="${this._esc(model.model_name)}">
                                <i class="fas fa-pause"></i> Deactivate
                               </button>`
                            : ''}
                    </div>
                </div>`;
        }).join('');

        // Attach activate/deactivate handlers
        container.querySelectorAll('.btn-activate-model').forEach(btn => {
            btn.addEventListener('click', () => {
                window.dispatchEvent(new CustomEvent('ml:activate-readiness-model', {
                    detail: { modelName: btn.dataset.model }
                }));
            });
        });
        container.querySelectorAll('.btn-deactivate-model').forEach(btn => {
            btn.addEventListener('click', () => {
                window.dispatchEvent(new CustomEvent('ml:deactivate-readiness-model', {
                    detail: { modelName: btn.dataset.model }
                }));
            });
        });
    }

    // =========================================================================
    // Irrigation ML Overview (Phase C)
    // =========================================================================

    /**
     * Render irrigation pending requests and config summary
     * @param {Object} requestsData - Pending requests
     * @param {Object} configData - Workflow config (optional)
     */
    renderIrrigationOverview(requestsData, configData) {
        // Requests container
        const reqContainer = this.elements.irrigationRequestsContainer;
        if (reqContainer) {
            const requests = requestsData?.requests || [];
            const badge = this.elements.irrigationPendingBadge;

            if (badge) {
                badge.textContent = requests.length > 0 ? `${requests.length} Pending` : 'No Pending';
                badge.className = `badge rounded-pill ${
                    requests.length > 0 ? 'bg-warning-subtle text-warning' : 'bg-success-subtle text-success'}`;
            }

            if (requests.length === 0) {
                reqContainer.innerHTML = `
                    <div class="text-center py-3 text-muted">
                        <i class="fas fa-check-circle fa-2x mb-2 opacity-50"></i>
                        <p class="mb-0 small">No pending irrigation requests</p>
                    </div>`;
            } else {
                reqContainer.innerHTML = `
                    <div class="table-responsive">
                        <table class="table table-sm">
                            <thead><tr>
                                <th>Plant</th><th>Unit</th><th>Status</th><th>Scheduled</th>
                            </tr></thead>
                            <tbody>
                                ${requests.slice(0, 10).map(r => `
                                    <tr>
                                        <td>${this._esc(r.plant_name || `Plant ${r.plant_id}`)}</td>
                                        <td>${this._esc(String(r.unit_id || ''))}</td>
                                        <td><span class="badge bg-${r.status === 'pending' ? 'warning' : 'info'}-subtle text-${r.status === 'pending' ? 'warning' : 'info'}">${this._esc(r.status || 'pending')}</span></td>
                                        <td class="smallest">${r.scheduled_time ? this.formatDateTime(r.scheduled_time) : '--'}</td>
                                    </tr>`).join('')}
                            </tbody>
                        </table>
                    </div>
                    ${requests.length > 10 ? `<p class="text-muted smallest">Showing 10 of ${requests.length} requests</p>` : ''}`;
            }
        }

        // Config summary
        const cfgContainer = this.elements.irrigationConfigContainer;
        if (cfgContainer && configData) {
            const cfg = configData.config || configData;
            cfgContainer.innerHTML = `
                <div class="d-flex flex-wrap gap-3 pt-3 border-top smallest">
                    <span><i class="fas fa-toggle-${cfg.workflow_enabled ? 'on text-success' : 'off text-muted'}"></i> Workflow ${cfg.workflow_enabled ? 'On' : 'Off'}</span>
                    <span><i class="fas fa-toggle-${cfg.auto_irrigation_enabled ? 'on text-success' : 'off text-muted'}"></i> Auto ${cfg.auto_irrigation_enabled ? 'On' : 'Off'}</span>
                    <span><i class="fas fa-toggle-${cfg.ml_learning_enabled ? 'on text-success' : 'off text-muted'}"></i> ML Learning ${cfg.ml_learning_enabled ? 'On' : 'Off'}</span>
                    <span><i class="fas fa-shield-alt ${cfg.require_approval ? 'text-warning' : 'text-muted'}"></i> Approval ${cfg.require_approval ? 'Required' : 'Off'}</span>
                </div>`;
        }
    }

    // =========================================================================
    // A/B Testing (Phase C)
    // =========================================================================

    /**
     * Render A/B tests list with analysis summaries
     * @param {Object} testsData - { tests: [...], count: int }
     */
    renderABTests(testsData) {
        const container = this.elements.abTestsContainer;
        if (!container) return;

        const tests = testsData?.tests || [];
        const badge = this.elements.abTestsCountBadge;

        if (badge) {
            const running = tests.filter(t => t.status === 'running').length;
            badge.textContent = running > 0 ? `${running} Running` : `${tests.length} Total`;
            badge.className = `badge rounded-pill ${
                running > 0 ? 'bg-primary-subtle text-primary' : 'bg-secondary-subtle text-secondary'}`;
        }

        if (tests.length === 0) {
            container.innerHTML = `
                <div class="text-center py-4 text-muted">
                    <i class="fas fa-flask fa-2x mb-2 opacity-25"></i>
                    <p class="mb-0 small">No A/B tests configured</p>
                    <p class="smallest text-muted">A/B tests compare two model versions to find the best performer</p>
                </div>`;
            return;
        }

        container.innerHTML = tests.map(test => {
            const statusVariant = test.status === 'running' ? 'primary'
                : test.status === 'completed' ? 'success' : 'secondary';
            const splitPct = ((test.split_ratio || 0.5) * 100).toFixed(0);

            return `
                <div class="ab-test-card">
                    <div class="d-flex justify-content-between align-items-start mb-2">
                        <div>
                            <strong>${this._esc(test.model_name || 'Unknown Model')}</strong>
                            <div class="smallest text-muted">
                                v${this._esc(String(test.version_a || '?'))} vs v${this._esc(String(test.version_b || '?'))}
                                &nbsp;·&nbsp; Split: ${splitPct}/${100 - parseInt(splitPct)}
                            </div>
                        </div>
                        <span class="badge bg-${statusVariant}-subtle text-${statusVariant} rounded-pill">${this._esc(test.status || 'unknown')}</span>
                    </div>
                    <div class="d-flex gap-3 smallest text-muted mb-2">
                        <span><i class="fas fa-chart-bar"></i> ${test.total_predictions || test.sample_count || 0} predictions</span>
                        <span><i class="fas fa-bullseye"></i> min ${test.min_samples || 100} samples</span>
                        ${test.winner ? `<span class="text-success"><i class="fas fa-trophy"></i> Winner: v${this._esc(String(test.winner))}</span>` : ''}
                    </div>
                    ${test.status === 'running' ? `
                        <div class="d-flex gap-2">
                            <button class="btn btn-sm btn-outline-primary btn-analyze-test" data-test-id="${this._esc(test.test_id || test.id)}">
                                <i class="fas fa-chart-pie"></i> Analyze
                            </button>
                            <button class="btn btn-sm btn-outline-success btn-complete-test" data-test-id="${this._esc(test.test_id || test.id)}">
                                <i class="fas fa-check"></i> Complete
                            </button>
                            <button class="btn btn-sm btn-outline-danger btn-cancel-test" data-test-id="${this._esc(test.test_id || test.id)}">
                                <i class="fas fa-times"></i> Cancel
                            </button>
                        </div>` : ''}
                </div>`;
        }).join('');

        // Attach handlers
        container.querySelectorAll('.btn-analyze-test').forEach(btn => {
            btn.addEventListener('click', () => {
                window.dispatchEvent(new CustomEvent('ml:analyze-ab-test', {
                    detail: { testId: btn.dataset.testId }
                }));
            });
        });
        container.querySelectorAll('.btn-complete-test').forEach(btn => {
            btn.addEventListener('click', () => {
                window.dispatchEvent(new CustomEvent('ml:complete-ab-test', {
                    detail: { testId: btn.dataset.testId }
                }));
            });
        });
        container.querySelectorAll('.btn-cancel-test').forEach(btn => {
            btn.addEventListener('click', () => {
                window.dispatchEvent(new CustomEvent('ml:cancel-ab-test', {
                    detail: { testId: btn.dataset.testId }
                }));
            });
        });
    }

    /**
     * Render A/B test analysis results
     * @param {Object} analysis - Statistical analysis data
     */
    renderABTestAnalysis(analysis) {
        if (!analysis) return;

        const container = this.elements.abTestsContainer;
        if (!container) return;

        // Append analysis result below the test list
        const existing = document.getElementById('ab-analysis-result');
        if (existing) existing.remove();

        const sig = analysis.statistical_significance;
        const sigVariant = sig ? 'success' : 'warning';

        const resultHtml = `
            <div id="ab-analysis-result" class="ab-analysis-card mt-3">
                <div class="d-flex justify-content-between align-items-center mb-2">
                    <strong><i class="fas fa-chart-pie"></i> Statistical Analysis</strong>
                    <span class="badge bg-${sigVariant}-subtle text-${sigVariant} rounded-pill">
                        ${sig ? 'Statistically Significant' : 'Not Significant'}
                    </span>
                </div>
                <div class="d-flex flex-wrap gap-4 smallest">
                    <div>
                        <span class="text-muted">p-value:</span>
                        <strong>${analysis.p_value != null ? analysis.p_value.toFixed(4) : '--'}</strong>
                    </div>
                    <div>
                        <span class="text-muted">Winner:</span>
                        <strong class="text-success">${analysis.recommended_winner ? 'v' + this._esc(String(analysis.recommended_winner)) : 'None yet'}</strong>
                    </div>
                </div>
            </div>`;

        container.insertAdjacentHTML('beforeend', resultHtml);
    }

    // =========================================================================
    // Data Loading Methods (delegate to dataService)
    // =========================================================================

    async loadDriftMetrics() {
        if (!this.currentDriftModel) return;
        try {
            const data = await this.dataService.getDriftMetrics(this.currentDriftModel);
            this.renderDriftMetrics(data);
        } catch (error) {
            console.error('Failed to load drift metrics:', error);
        }
    }

    async updateDriftChart() {
        if (!this.currentDriftModel) return;
        try {
            const history = await this.dataService.getDriftHistory(this.currentDriftModel);
            this.renderDriftChart(history);
        } catch (error) {
            console.error('Failed to load drift chart:', error);
        }
    }

    async refreshModels() {
        try {
            const models = await this.dataService.getModels(true);
            this.renderModels(models);
            if (this.currentDriftModel) {
                this.loadDriftMetrics();
                this.updateDriftChart();
            }
        } catch (error) {
            console.error('Failed to refresh models:', error);
            this.showAlert('danger', 'Failed to load models. Please try again.');
        }
    }

    async refreshTrainingHistory() {
        try {
            const data = await this.dataService.getTrainingHistory();
            this.renderTrainingHistory(data);
        } catch (error) {
            console.error('Failed to refresh training history:', error);
        }
    }

    // =========================================================================
    // Event Handlers (to be connected to main controller)
    // =========================================================================

    onTrainNewModel() {
        // Emit event for controller to handle
        window.dispatchEvent(new CustomEvent('ml:train-new-model'));
    }

    onRetrainModel(modelName) {
        window.dispatchEvent(new CustomEvent('ml:retrain-model', { detail: { modelName } }));
    }

    onActivateModel(modelName, version) {
        window.dispatchEvent(new CustomEvent('ml:activate-model', { detail: { modelName, version } }));
    }

    onCancelTraining() {
        window.dispatchEvent(new CustomEvent('ml:cancel-training'));
    }

    onTriggerRetraining() {
        if (this.currentDriftModel) {
            window.dispatchEvent(new CustomEvent('ml:retrain-model', { 
                detail: { modelName: this.currentDriftModel } 
            }));
        }
    }

    onViewDriftHistory() {
        if (!this.currentDriftModel) {
            this.showAlert('warning', 'Please select a model first.');
            return;
        }
        this.showAlert('info', 'Drift history chart is displayed below.');
    }

    onRunJob(jobId) {
        window.dispatchEvent(new CustomEvent('ml:run-job', { detail: { jobId } }));
    }

    onToggleJob(jobId, enable) {
        window.dispatchEvent(new CustomEvent('ml:toggle-job', { detail: { jobId, enable } }));
    }

    onStartScheduler() {
        window.dispatchEvent(new CustomEvent('ml:start-scheduler'));
    }

    onStopScheduler() {
        window.dispatchEvent(new CustomEvent('ml:stop-scheduler'));
    }

    onStartMonitoring() {
        window.dispatchEvent(new CustomEvent('ml:start-monitoring'));
    }

    onStopMonitoring() {
        window.dispatchEvent(new CustomEvent('ml:stop-monitoring'));
    }

    onRefreshInsights() {
        window.dispatchEvent(new CustomEvent('ml:refresh-insights'));
    }

    onValidateData() {
        window.dispatchEvent(new CustomEvent('ml:validate-data'));
    }

    onRefreshTrainingData() {
        window.dispatchEvent(new CustomEvent('ml:refresh-training-data'));
    }

    onCheckAllReadiness() {
        window.dispatchEvent(new CustomEvent('ml:check-all-readiness'));
    }

    // =========================================================================
    // Utilities
    // =========================================================================

    formatDate(dateString) {
        if (!dateString) return '--';
        return new Date(dateString).toLocaleDateString();
    }

    formatDateTime(dateString) {
        if (!dateString) return '--';
        return new Date(dateString).toLocaleString();
    }

    // =========================================================================
    // Cleanup
    // =========================================================================

    destroy() {
        if (this.driftChart) {
            this.driftChart.destroy();
            this.driftChart = null;
        }
        if (this.comparisonChart) {
            this.comparisonChart.destroy();
            this.comparisonChart = null;
        }
        if (this.featureChart) {
            this.featureChart.destroy();
            this.featureChart = null;
        }
        if (this.diseaseTrendsChart) {
            this.diseaseTrendsChart.destroy();
            this.diseaseTrendsChart = null;
        }
        if (this.inlineComparisonChart) {
            this.inlineComparisonChart.destroy();
            this.inlineComparisonChart = null;
        }
        this.loadedSections.clear();
    }
}

// Export
window.MLUIManager = MLUIManager;
