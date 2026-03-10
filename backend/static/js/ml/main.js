/**
 * ML Dashboard Main Controller
 * Entry point for ML dashboard - coordinates data service, UI, and WebSocket
 * 
 * @module ml/main
 */

class MLDashboard {
    constructor() {
        this.dataService = window.MLDataService;
        this.uiManager = null;
        this.socket = null;
        this.refreshInterval = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        
        // Active training state
        this.activeTrainingModelName = null;
        this.activeTrainingVersion = null;
    }

    // =========================================================================
    // Initialization
    // =========================================================================

    /**
     * Initialize the ML dashboard
     */
    init() {
        console.log('🚀 Initializing ML Dashboard...');

        // Initialize UI Manager
        this.uiManager = new MLUIManager(this.dataService);
        this.uiManager.init();

        // Attach custom event listeners
        this.attachCustomEventListeners();

        // Initial data load
        this.loadInitialData();

        // Initialize WebSocket connection
        this.initWebSocket();

        // Set up polling fallback
        this.refreshInterval = setInterval(() => {
            if (!this.socket || !this.socket.connected) {
                console.log('WebSocket disconnected, using polling fallback');
                this.checkHealth();
                this.uiManager.loadDriftMetrics();
                this.loadSchedulerStatus();
            }
        }, 30000);

        console.log('✅ ML Dashboard initialized');
    }

    /**
     * Load initial data
     */
    async loadInitialData() {
        try {
            const [, models, jobsData] = await Promise.all([
                this.checkHealth(),
                this.loadModels(),
                this.loadRetrainingJobs(),
                this.loadTrainingHistory(),
                this.loadSchedulerStatus()
            ]);

            // Update KPI row from collected data
            this.updateKPIs(models, jobsData);
        } catch (error) {
            console.error('Error loading initial data:', error);
        }
    }

    /**
     * Update KPI cards with aggregated data
     */
    updateKPIs(models, jobsData) {
        try {
            const modelList = models || [];
            const activeModels = modelList.filter(m => m.active).length;
            const bestAccuracy = modelList.reduce((best, m) => {
                const acc = m.accuracy || 0;
                return acc > best ? acc : best;
            }, 0) || null;
            const jobCount = (jobsData?.jobs || []).length;

            this.uiManager.renderKPIs({
                activeModels,
                bestAccuracy,
                jobCount,
                healthStatus: true // updated by checkHealth separately
            });
        } catch {
            // KPIs are non-critical
        }
    }

    /**
     * Attach custom event listeners from UI Manager
     */
    attachCustomEventListeners() {
        window.addEventListener('ml:train-new-model', () => this.trainNewModel());
        window.addEventListener('ml:retrain-model', (e) => this.retrainModel(e.detail.modelName));
        window.addEventListener('ml:activate-model', (e) => this.activateModel(e.detail.modelName, e.detail.version));
        window.addEventListener('ml:cancel-training', () => this.cancelTraining());
        window.addEventListener('ml:run-job', (e) => this.runJob(e.detail.jobId));
        window.addEventListener('ml:toggle-job', (e) => this.toggleJob(e.detail.jobId, e.detail.enable));

        // Scheduler controls
        window.addEventListener('ml:start-scheduler', () => this.startScheduler());
        window.addEventListener('ml:stop-scheduler', () => this.stopScheduler());

        // Continuous monitoring controls
        window.addEventListener('ml:start-monitoring', () => this.startMonitoring());
        window.addEventListener('ml:stop-monitoring', () => this.stopMonitoring());
        window.addEventListener('ml:refresh-insights', () => this.loadContinuousSection());

        // Training data controls
        window.addEventListener('ml:validate-data', () => this.validateTrainingData());
        window.addEventListener('ml:refresh-training-data', () => this.loadTrainingDataSection());

        // ML Readiness controls (Phase C)
        window.addEventListener('ml:check-all-readiness', () => this.checkAllReadiness());
        window.addEventListener('ml:activate-readiness-model', (e) => this.activateReadinessModel(e.detail.modelName));
        window.addEventListener('ml:deactivate-readiness-model', (e) => this.deactivateReadinessModel(e.detail.modelName));

        // A/B Testing controls (Phase C)
        window.addEventListener('ml:analyze-ab-test', (e) => this.analyzeABTest(e.detail.testId));
        window.addEventListener('ml:complete-ab-test', (e) => this.completeABTest(e.detail.testId));
        window.addEventListener('ml:cancel-ab-test', (e) => this.cancelABTest(e.detail.testId));

        // Lazy section expansion
        window.addEventListener('ml:section-expand', (e) => this.onSectionExpand(e.detail.section));
    }

    // =========================================================================
    // WebSocket Management
    // =========================================================================

    /**
     * Initialize WebSocket connection
     */
    initWebSocket() {
        try {
            this.socket = io('/system', {
                transports: ['polling'],
                reconnection: true,
                reconnectionAttempts: this.maxReconnectAttempts,
                reconnectionDelay: 2000
            });

            // Connection events
            this.socket.on('connect', () => {
                console.log('✅ WebSocket connected to ML namespace');
                this.reconnectAttempts = 0;
                this.uiManager.updateConnectionStatus(true);
                this.socket.emit('ml_subscribe');
            });

            this.socket.on('disconnect', () => {
                console.log('❌ WebSocket disconnected');
                this.uiManager.updateConnectionStatus(false);
            });

            this.socket.on('connect_error', (error) => {
                console.error('WebSocket connection error:', error);
                this.reconnectAttempts++;
                if (this.reconnectAttempts >= this.maxReconnectAttempts) {
                    this.uiManager.showAlert('warning', 'Real-time updates unavailable. Using polling mode.');
                }
            });

            // ML event handlers
            this.socket.on('ml_status', (data) => {
                this.uiManager.updateConnectionStatus(data.connected);
            });

            this.socket.on('training_started', (data) => {
                this.activeTrainingModelName = data.model_name || this.activeTrainingModelName;
                this.activeTrainingVersion = data.version || this.activeTrainingVersion;
                const versionLabel = data.version ? ` v${data.version}` : '';
                this.uiManager.showAlert('info', `Training started: ${data.model_name}${versionLabel}`);
                this.loadModels();
                this.loadTrainingHistory();
            });

            this.socket.on('training_progress', (data) => {
                this.activeTrainingModelName = data.model_name || this.activeTrainingModelName;
                this.activeTrainingVersion = data.version || this.activeTrainingVersion;
                this.uiManager.updateTrainingProgress(data);
            });

            this.socket.on('training_complete', (data) => {
                const versionLabel = data.version ? ` v${data.version}` : '';
                this.uiManager.showAlert('success', `Training completed: ${data.model_name}${versionLabel}`);
                this.activeTrainingModelName = null;
                this.activeTrainingVersion = null;
                this.dataService.onTrainingComplete(data);
                this.loadModels();
                this.loadTrainingHistory();
            });

            this.socket.on('training_cancelled', (data) => {
                this.uiManager.hideTrainingProgress();
                this.activeTrainingModelName = null;
                this.activeTrainingVersion = null;
                const message = data.message || 'Training cancelled';
                this.uiManager.showAlert('info', `${message}: ${data.model_name || ''}`.trim());
                this.loadModels();
                this.loadTrainingHistory();
            });

            this.socket.on('training_failed', (data) => {
                this.activeTrainingModelName = null;
                this.activeTrainingVersion = null;
                this.uiManager.hideTrainingProgress();
                this.uiManager.showAlert('danger', `Training failed: ${data.model_name} - ${data.error}`);
                this.loadTrainingHistory();
            });

            this.socket.on('drift_detected', (data) => {
                this.uiManager.showAlert('warning', `Drift detected in ${data.model_name}!`);
                this.dataService.onDriftDetected(data);
                this.uiManager.loadDriftMetrics();
                this.uiManager.updateDriftChart();
            });

            this.socket.on('drift_update', (data) => {
                if (data.model_name === this.uiManager.currentDriftModel) {
                    this.dataService.onDriftDetected(data);
                    this.uiManager.loadDriftMetrics();
                    this.uiManager.updateDriftChart();
                }
            });

            this.socket.on('retraining_scheduled', (data) => {
                this.uiManager.showAlert('info', `Retraining scheduled for ${data.model_name}`);
                this.loadRetrainingJobs();
            });

            this.socket.on('model_activated', (data) => {
                this.uiManager.showAlert('success', `Model activated: ${data.model_name} v${data.version}`);
                this.dataService.onModelActivated(data);
                this.loadModels();
            });

            this.socket.on('continuous_insight', (data) => {
                // If the continuous section is already loaded, refresh it
                if (this.uiManager.loadedSections.has('continuous')) {
                    this.loadContinuousSection();
                }
            });

            this.socket.on('scheduler_status', (data) => {
                this.uiManager.renderSchedulerStatus(data);
            });

            this.socket.on('error', (data) => {
                console.error('WebSocket error:', data);
                this.uiManager.showAlert('error', data.message || 'An error occurred');
            });

        } catch (error) {
            console.error('Failed to initialize WebSocket:', error);
            this.uiManager.showAlert('warning', 'Real-time updates unavailable. Using polling mode.');
        }
    }

    // =========================================================================
    // Data Loading
    // =========================================================================

    async checkHealth() {
        try {
            const data = await this.dataService.getHealth();
            this.uiManager.updateHealthIndicator(
                data.healthy, 
                data.healthy ? 'All Systems Operational' : 'System Issues Detected'
            );
            
            if (!data.healthy) {
                this.uiManager.showAlert('warning', 'ML infrastructure health check failed. Some features may be unavailable.');
            }
        } catch (error) {
            console.error('Health check failed:', error);
            this.uiManager.updateHealthIndicator(false, 'Connection Error');
        }
    }

    async loadModels() {
        try {
            const models = await this.dataService.getModels();
            this.uiManager.renderModels(models);
            
            // Load drift for first model if needed
            if (!this.uiManager.currentDriftModel && models.length > 0) {
                this.uiManager.currentDriftModel = models[0].name;
                this.uiManager.loadDriftMetrics();
                this.uiManager.updateDriftChart();
            }
            return models;
        } catch (error) {
            console.error('Failed to load models:', error);
            this.uiManager.showAlert('danger', 'Failed to load models. Please try again.');
            return [];
        }
    }

    async loadRetrainingJobs() {
        try {
            const data = await this.dataService.getRetrainingJobs();
            this.uiManager.renderJobs(data);
            return data;
        } catch (error) {
            console.error('Failed to load retraining jobs:', error);
            return { jobs: [] };
        }
    }

    async loadTrainingHistory() {
        try {
            const data = await this.dataService.getTrainingHistory();
            this.uiManager.renderTrainingHistory(data);
        } catch (error) {
            console.error('Failed to load training history:', error);
        }
    }

    // =========================================================================
    // Actions
    // =========================================================================

    async trainNewModel() {
        const modelTypes = [
            { name: 'climate_predictor', label: 'Climate Predictor', description: 'Predicts optimal climate conditions' },
            { name: 'disease_classifier', label: 'Disease Classifier', description: 'Detects plant diseases' },
            { name: 'irrigation_optimizer', label: 'Irrigation Optimizer', description: 'Optimizes watering schedules' }
        ];

        if (!confirm('Train a new model?\n\nNote: This requires sufficient training data.')) return;

        const modelName = modelTypes[0].name;
        const days = 90;

        this.uiManager.showAlert('info', `Training ${modelName}... This may take a few minutes.`);

        try {
            const data = await this.dataService.retrainModel(modelName, {
                training_config: { days: days }
            });

            if (data.success) {
                this.uiManager.showAlert('info', data.message || `Training started for ${modelName}.`);
            } else {
                const message = data.message || data.error || 'Training failed';
                this.uiManager.showAlert('warning', message);
            }
            this.loadModels();
            this.loadTrainingHistory();
        } catch (error) {
            console.error('Training failed:', error);
            this.uiManager.showAlert('danger', 'Training request failed. Please try again.');
        }
    }

    async retrainModel(modelName) {
        if (!confirm(`Retrain ${modelName}?`)) return;

        this.uiManager.showAlert('info', `Retraining ${modelName}...`);

        try {
            const data = await this.dataService.retrainModel(modelName, {
                training_config: { days: 90 }
            });

            if (data.success) {
                this.uiManager.showAlert('info', data.message || `Retraining started for ${modelName}.`);
                this.loadModels();
                this.loadTrainingHistory();
            } else {
                const message = data.message || data.error || 'Retraining failed';
                this.uiManager.showAlert('danger', `Retraining failed: ${message}`);
            }
        } catch (error) {
            console.error('Retraining failed:', error);
            this.uiManager.showAlert('danger', 'Retraining request failed. Please try again.');
        }
    }

    async activateModel(modelName, version) {
        if (!confirm(`Activate ${modelName} version ${version}?`)) return;

        try {
            const data = await this.dataService.activateModel(modelName, version);

            if (data.success || data.status === 'promoted') {
                this.uiManager.showAlert('success', `${modelName} v${version} is now active.`);
                this.loadModels();
            } else {
                const message = data.message || data.error || 'Activation failed';
                this.uiManager.showAlert('danger', `Activation failed: ${message}`);
            }
        } catch (error) {
            console.error('Activation failed:', error);
            this.uiManager.showAlert('danger', 'Activation request failed. Please try again.');
        }
    }

    async cancelTraining() {
        if (!confirm('Cancel the current training job?')) return;

        try {
            const modelName = this.activeTrainingModelName;
            const data = await this.dataService.cancelTraining(modelName);

            if (data.success === false) {
                throw new Error(data.error || data.message || 'Failed to cancel training');
            }

            this.activeTrainingModelName = null;
            this.activeTrainingVersion = null;
            this.uiManager.hideTrainingProgress();
            this.uiManager.showAlert('info', 'Cancellation requested. Training will stop shortly.');
            this.loadModels();
        } catch (error) {
            console.error('Failed to cancel training:', error);
            this.uiManager.showAlert('danger', error.message || 'Failed to cancel training');
        }
    }

    async runJob(jobId) {
        try {
            const data = await this.dataService.runJob(jobId);

            if (data.success) {
                this.uiManager.showAlert('success', 'Retraining job started successfully.');
                this.loadRetrainingJobs();
            } else {
                this.uiManager.showAlert('danger', `Failed to run job: ${data.message}`);
            }
        } catch (error) {
            console.error('Failed to run job:', error);
            this.uiManager.showAlert('danger', 'Failed to start retraining job.');
        }
    }

    async toggleJob(jobId, enable) {
        try {
            const data = await this.dataService.toggleJob(jobId, enable);

            if (data.success) {
                this.uiManager.showAlert('success', `Job ${enable ? 'enabled' : 'disabled'} successfully.`);
                this.loadRetrainingJobs();
            } else {
                this.uiManager.showAlert('danger', `Failed to ${enable ? 'enable' : 'disable'} job: ${data.message}`);
            }
        } catch (error) {
            console.error('Failed to toggle job:', error);
            this.uiManager.showAlert('danger', 'Failed to update job status.');
        }
    }

    // =========================================================================
    // Scheduler Controls
    // =========================================================================

    async loadSchedulerStatus() {
        try {
            const data = await this.dataService.getRetrainingStatus();
            this.uiManager.renderSchedulerStatus(data);
        } catch (error) {
            console.error('Failed to load scheduler status:', error);
        }
    }

    async startScheduler() {
        try {
            const data = await this.dataService.startScheduler();
            if (data.success || data.status === 'started') {
                this.uiManager.showAlert('success', 'Retraining scheduler started.');
            } else {
                this.uiManager.showAlert('warning', data.message || 'Could not start scheduler.');
            }
            this.loadSchedulerStatus();
        } catch (error) {
            console.error('Failed to start scheduler:', error);
            this.uiManager.showAlert('danger', 'Failed to start scheduler.');
        }
    }

    async stopScheduler() {
        try {
            const data = await this.dataService.stopScheduler();
            if (data.success || data.status === 'stopped') {
                this.uiManager.showAlert('info', 'Retraining scheduler stopped.');
            } else {
                this.uiManager.showAlert('warning', data.message || 'Could not stop scheduler.');
            }
            this.loadSchedulerStatus();
        } catch (error) {
            console.error('Failed to stop scheduler:', error);
            this.uiManager.showAlert('danger', 'Failed to stop scheduler.');
        }
    }

    // =========================================================================
    // Continuous Monitoring Controls
    // =========================================================================

    async startMonitoring() {
        try {
            const data = await this.dataService.startContinuousMonitoring();
            if (data.success || data.status === 'started') {
                this.uiManager.showAlert('success', 'Continuous monitoring started.');
                this.loadContinuousSection();
            } else {
                this.uiManager.showAlert('warning', data.message || 'Could not start monitoring.');
            }
        } catch (error) {
            console.error('Failed to start monitoring:', error);
            this.uiManager.showAlert('danger', 'Failed to start continuous monitoring.');
        }
    }

    async stopMonitoring() {
        try {
            const data = await this.dataService.stopContinuousMonitoring();
            if (data.success || data.status === 'stopped') {
                this.uiManager.showAlert('info', 'Continuous monitoring stopped.');
                this.loadContinuousSection();
            } else {
                this.uiManager.showAlert('warning', data.message || 'Could not stop monitoring.');
            }
        } catch (error) {
            console.error('Failed to stop monitoring:', error);
            this.uiManager.showAlert('danger', 'Failed to stop continuous monitoring.');
        }
    }

    // =========================================================================
    // Training Data Actions
    // =========================================================================

    async validateTrainingData() {
        this.uiManager.showAlert('info', 'Validating training data...');
        try {
            const types = ['disease', 'climate', 'growth'];
            const results = await Promise.allSettled(
                types.map(t => this.dataService.validateTrainingData(t))
            );
            const failed = results.filter(r => r.status === 'rejected' || r.value?.success === false);
            if (failed.length === 0) {
                this.uiManager.showAlert('success', 'Training data validation complete.');
            } else {
                this.uiManager.showAlert('warning', `Validation complete with ${failed.length} issue(s).`);
            }
            this.loadTrainingDataSection();
        } catch (error) {
            console.error('Validation failed:', error);
            this.uiManager.showAlert('danger', 'Training data validation failed.');
        }
    }

    // =========================================================================
    // Lazy Section Loading
    // =========================================================================

    /**
     * Handle section expand — load data for the section
     * @param {string} section - Section key
     */
    onSectionExpand(section) {
        switch (section) {
            case 'continuous':
                this.loadContinuousSection();
                break;
            case 'training-data':
                this.loadTrainingDataSection();
                break;
            case 'disease-trends':
                this.loadDiseaseTrendsSection();
                break;
            case 'model-comparison':
                this.loadModelComparisonSection();
                break;
            case 'ml-readiness':
                this.loadMLReadinessSection();
                break;
            case 'irrigation-ml':
                this.loadIrrigationMLSection();
                break;
            case 'ab-testing':
                this.loadABTestingSection();
                break;
            default:
                console.warn('Unknown lazy section:', section);
        }
    }

    async loadContinuousSection() {
        try {
            const [status, insights] = await Promise.all([
                this.dataService.getContinuousStatus(),
                this.dataService.getCriticalInsights()
            ]);
            this.uiManager.renderContinuousInsights(status, insights);
        } catch (error) {
            console.error('Failed to load continuous monitoring:', error);
        }
    }

    async loadTrainingDataSection() {
        try {
            const [summary, quality] = await Promise.all([
                this.dataService.getTrainingDataSummary(),
                this.dataService.getDataQuality()
            ]);
            this.uiManager.renderTrainingDataQuality(summary, quality);
        } catch (error) {
            console.error('Failed to load training data quality:', error);
        }
    }

    async loadDiseaseTrendsSection() {
        try {
            const data = await this.dataService.getDiseaseTrends(30);
            this.uiManager.renderDiseaseTrends(data);
        } catch (error) {
            console.error('Failed to load disease trends:', error);
        }
    }

    async loadModelComparisonSection() {
        try {
            const models = await this.dataService.getModels();
            const modelNames = models.map(m => m.name).filter(Boolean);
            if (modelNames.length < 2) {
                this.uiManager.renderModelComparisonInline({ comparison: [] });
                return;
            }
            const data = await this.dataService.compareModels(modelNames);
            this.uiManager.renderModelComparisonInline(data);
        } catch (error) {
            console.error('Failed to load model comparison:', error);
        }
    }

    // =========================================================================
    // Phase C — ML Readiness
    // =========================================================================

    /**
     * Get the active unit ID from page context.
     * Falls back to unit 1 when the dashboard has no unit context.
     */
    _getActiveUnitId() {
        return parseInt(document.body.dataset.activeUnitId, 10) || 1;
    }

    async loadMLReadinessSection() {
        const unitId = this._getActiveUnitId();
        try {
            const data = await this.dataService.getIrrigationReadiness(unitId);
            this.uiManager.renderMLReadiness(data);
        } catch (error) {
            console.error('Failed to load ML readiness:', error);
        }
    }

    async checkAllReadiness() {
        this.uiManager.showAlert('info', 'Checking readiness for all units…');
        try {
            const result = await this.dataService.checkAllReadiness();
            const count = result?.units_checked || 0;
            this.uiManager.showAlert('success', `Checked ${count} unit(s). Refreshing…`);
            await this.loadMLReadinessSection();
        } catch (error) {
            console.error('Check-all readiness failed:', error);
            this.uiManager.showAlert('danger', 'Failed to check readiness for all units.');
        }
    }

    async activateReadinessModel(modelName) {
        const unitId = this._getActiveUnitId();
        if (!confirm(`Activate ${modelName} for unit ${unitId}?`)) return;

        try {
            const result = await this.dataService.activateMLModel(unitId, modelName);
            if (result?.activated) {
                this.uiManager.showAlert('success', `${modelName} activated for unit ${unitId}.`);
            } else {
                this.uiManager.showAlert('warning', result?.message || 'Activation returned unexpected result.');
            }
            await this.loadMLReadinessSection();
        } catch (error) {
            console.error('Activate readiness model failed:', error);
            this.uiManager.showAlert('danger', `Failed to activate ${modelName}.`);
        }
    }

    async deactivateReadinessModel(modelName) {
        const unitId = this._getActiveUnitId();
        if (!confirm(`Deactivate ${modelName} for unit ${unitId}?`)) return;

        try {
            const result = await this.dataService.deactivateMLModel(unitId, modelName);
            if (result?.deactivated) {
                this.uiManager.showAlert('info', `${modelName} deactivated for unit ${unitId}.`);
            } else {
                this.uiManager.showAlert('warning', result?.message || 'Deactivation returned unexpected result.');
            }
            await this.loadMLReadinessSection();
        } catch (error) {
            console.error('Deactivate readiness model failed:', error);
            this.uiManager.showAlert('danger', `Failed to deactivate ${modelName}.`);
        }
    }

    // =========================================================================
    // Phase C — Irrigation ML Overview
    // =========================================================================

    async loadIrrigationMLSection() {
        const unitId = this._getActiveUnitId();
        try {
            const [requestsData, configData] = await Promise.all([
                this.dataService.getIrrigationRequests(),
                this.dataService.getIrrigationConfig(unitId)
            ]);
            this.uiManager.renderIrrigationOverview(requestsData, configData);
        } catch (error) {
            console.error('Failed to load irrigation ML overview:', error);
        }
    }

    // =========================================================================
    // Phase C — A/B Testing
    // =========================================================================

    async loadABTestingSection() {
        try {
            const data = await this.dataService.getABTests();
            this.uiManager.renderABTests(data);
        } catch (error) {
            console.error('Failed to load A/B tests:', error);
        }
    }

    async analyzeABTest(testId) {
        this.uiManager.showAlert('info', 'Analyzing A/B test…');
        try {
            const data = await this.dataService.getABTestAnalysis(testId);
            this.uiManager.renderABTestAnalysis(data);
        } catch (error) {
            console.error('A/B test analysis failed:', error);
            this.uiManager.showAlert('danger', 'Failed to analyze A/B test.');
        }
    }

    async completeABTest(testId) {
        if (!confirm('Complete this A/B test and deploy the winner?')) return;

        try {
            const result = await this.dataService.completeABTest(testId);
            if (result?.success !== false) {
                this.uiManager.showAlert('success', 'A/B test completed. Winner deployed.');
            } else {
                this.uiManager.showAlert('warning', result?.message || 'Completion returned unexpected result.');
            }
            await this.loadABTestingSection();
        } catch (error) {
            console.error('Complete A/B test failed:', error);
            this.uiManager.showAlert('danger', 'Failed to complete A/B test.');
        }
    }

    async cancelABTest(testId) {
        if (!confirm('Cancel this A/B test? Results will be discarded.')) return;

        try {
            const result = await this.dataService.cancelABTest(testId);
            if (result?.success !== false) {
                this.uiManager.showAlert('info', 'A/B test cancelled.');
            } else {
                this.uiManager.showAlert('warning', result?.message || 'Cancellation returned unexpected result.');
            }
            await this.loadABTestingSection();
        } catch (error) {
            console.error('Cancel A/B test failed:', error);
            this.uiManager.showAlert('danger', 'Failed to cancel A/B test.');
        }
    }

    // =========================================================================
    // Cleanup
    // =========================================================================

    destroy() {
        if (this.refreshInterval) {
            clearInterval(this.refreshInterval);
        }
        
        if (this.uiManager) {
            this.uiManager.destroy();
        }
        
        if (this.socket) {
            this.socket.emit('ml_unsubscribe');
            this.socket.disconnect();
            console.log('WebSocket disconnected and cleaned up');
        }
    }
}

// =========================================================================
// Global Instance & Lifecycle
// =========================================================================

// Create singleton instance
const mlDashboard = new MLDashboard();

// Expose to global scope for compatibility
window.mlDashboard = mlDashboard;

// Initialize on DOMContentLoaded
document.addEventListener('DOMContentLoaded', () => {
    mlDashboard.init();
});

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
    mlDashboard.destroy();
});
