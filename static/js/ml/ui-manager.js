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
        this.currentDriftModel = null;
        
        // DOM element cache
        this.elements = {};
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
            comparisonModal: document.getElementById('comparison-modal'),
            modelComparisonChart: document.getElementById('model-comparison-chart'),
            featuresModal: document.getElementById('features-modal'),
            featureImportanceChart: document.getElementById('feature-importance-chart')
        };
    }

    /**
     * Attach event listeners
     */
    attachEventListeners() {
        // Static buttons
        this.addClickListener('btn-train-new-model', () => this.onTrainNewModel());
        this.addClickListener('btn-compare-models', () => this.showComparisonModal());
        this.addClickListener('btn-refresh-models', () => this.refreshModels());
        this.addClickListener('btn-view-drift-history', () => this.onViewDriftHistory());
        this.addClickListener('btn-refresh-training-history', () => this.refreshTrainingHistory());
        this.addClickListener('btn-cancel-training', () => this.onCancelTraining());
        this.addClickListener('btn-trigger-retraining', () => this.onTriggerRetraining());

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
        document.querySelectorAll('.btn-close-comparison-modal').forEach(btn => {
            btn.addEventListener('click', () => this.closeComparisonModal());
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

        return `
            <li class="model-item" data-model-name="${model.name}">
                <div class="model-header">
                    <span class="model-name">${model.name}</span>
                    <span class="card-badge ${statusClass}">${statusText}</span>
                </div>
                <div class="model-version">Version: ${model.latest_version}</div>
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
                                ${job.model_name}
                                <span class="card-badge ${statusClass}">${statusText}</span>
                            </div>
                            <div class="job-schedule">${job.schedule_description || 'Custom schedule'}</div>
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
                        <td><strong>${event.model_name}</strong></td>
                        <td>v${event.version}</td>
                        <td>${event.accuracy ? (event.accuracy * 100).toFixed(1) + '%' : '--'}</td>
                        <td>${event.mae ? event.mae.toFixed(3) : '--'}</td>
                        <td>${event.data_points || '--'}</td>
                        <td><span class="timestamp">${this.formatDateTime(event.trained_at)}</span></td>
                        <td><span class="card-badge ${statusClass}">${event.status}</span></td>
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
                <span>${message}</span>
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
                <h4>${modelName}</h4>
                <p><strong>Status:</strong> ${data.active ? 'Active' : 'Inactive'}</p>
                <p><strong>Latest Version:</strong> ${data.latest_version}</p>
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
                            <strong>Version ${v.version}</strong> - ${this.formatDateTime(v.trained_at)}
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
     * Show model comparison modal
     */
    async showComparisonModal() {
        const modal = this.elements.comparisonModal;
        if (!modal) return;

        modal.style.display = 'block';
        modal.classList.add('show');
        document.body.classList.add('modal-open');

        await this.loadModelComparison();
    }

    /**
     * Load and render model comparison
     */
    async loadModelComparison() {
        try {
            const models = await this.dataService.getModels();
            const container = this.elements.modelComparisonChart;

            if (models.length === 0) {
                if (container) {
                    container.innerHTML = '<div class="alert alert-info">No models available for comparison.</div>';
                }
                return;
            }

            const modelsWithMetrics = models.filter(m => m.accuracy || m.r2 || m.mae);

            if (modelsWithMetrics.length > 0) {
                this.renderModelComparison(modelsWithMetrics);
            } else if (container) {
                container.innerHTML = '<div class="alert alert-info">No model metrics available for comparison.</div>';
            }
        } catch (error) {
            console.error('Error loading model comparison:', error);
            if (this.elements.modelComparisonChart) {
                this.elements.modelComparisonChart.innerHTML = '<div class="alert alert-danger">Failed to load model comparison.</div>';
            }
        }
    }

    /**
     * Render model comparison chart
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

        new Chart(canvas.getContext('2d'), {
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

        new Chart(canvas.getContext('2d'), {
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
     * Close comparison modal
     */
    closeComparisonModal() {
        const modal = this.elements.comparisonModal;
        if (modal) {
            modal.style.display = 'none';
            modal.classList.remove('show');
            document.body.classList.remove('modal-open');
        }
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
    }
}

// Export
window.MLUIManager = MLUIManager;
