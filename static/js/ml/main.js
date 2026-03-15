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
            }
        }, 30000);

        console.log('✅ ML Dashboard initialized');
    }

    /**
     * Load initial data
     */
    async loadInitialData() {
        try {
            await Promise.all([
                this.checkHealth(),
                this.loadModels(),
                this.loadRetrainingJobs(),
                this.loadTrainingHistory()
            ]);
        } catch (error) {
            console.error('Error loading initial data:', error);
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
                console.log('ML Status:', data);
                this.uiManager.updateConnectionStatus(data.connected);
            });

            this.socket.on('training_started', (data) => {
                console.log('Training started:', data);
                this.activeTrainingModelName = data.model_name || this.activeTrainingModelName;
                this.activeTrainingVersion = data.version || this.activeTrainingVersion;
                const versionLabel = data.version ? ` v${data.version}` : '';
                this.uiManager.showAlert('info', `Training started: ${data.model_name}${versionLabel}`);
                this.loadModels();
                this.loadTrainingHistory();
            });

            this.socket.on('training_progress', (data) => {
                console.log('Training progress:', data);
                this.activeTrainingModelName = data.model_name || this.activeTrainingModelName;
                this.activeTrainingVersion = data.version || this.activeTrainingVersion;
                this.uiManager.updateTrainingProgress(data);
            });

            this.socket.on('training_complete', (data) => {
                console.log('Training complete:', data);
                const versionLabel = data.version ? ` v${data.version}` : '';
                this.uiManager.showAlert('success', `Training completed: ${data.model_name}${versionLabel}`);
                this.activeTrainingModelName = null;
                this.activeTrainingVersion = null;
                this.dataService.onTrainingComplete(data);
                this.loadModels();
                this.loadTrainingHistory();
            });

            this.socket.on('training_cancelled', (data) => {
                console.log('Training cancelled:', data);
                this.uiManager.hideTrainingProgress();
                this.activeTrainingModelName = null;
                this.activeTrainingVersion = null;
                const message = data.message || 'Training cancelled';
                this.uiManager.showAlert('info', `${message}: ${data.model_name || ''}`.trim());
                this.loadModels();
                this.loadTrainingHistory();
            });

            this.socket.on('training_failed', (data) => {
                console.log('Training failed:', data);
                this.activeTrainingModelName = null;
                this.activeTrainingVersion = null;
                this.uiManager.hideTrainingProgress();
                this.uiManager.showAlert('danger', `Training failed: ${data.model_name} - ${data.error}`);
                this.loadTrainingHistory();
            });

            this.socket.on('drift_detected', (data) => {
                console.log('Drift detected:', data);
                this.uiManager.showAlert('warning', `Drift detected in ${data.model_name}!`);
                this.dataService.onDriftDetected(data);
                this.uiManager.loadDriftMetrics();
                this.uiManager.updateDriftChart();
            });

            this.socket.on('drift_update', (data) => {
                console.log('Drift update:', data);
                if (data.model_name === this.uiManager.currentDriftModel) {
                    this.dataService.onDriftDetected(data);
                    this.uiManager.loadDriftMetrics();
                    this.uiManager.updateDriftChart();
                }
            });

            this.socket.on('retraining_scheduled', (data) => {
                console.log('Retraining scheduled:', data);
                this.uiManager.showAlert('info', `Retraining scheduled for ${data.model_name}`);
                this.loadRetrainingJobs();
            });

            this.socket.on('model_activated', (data) => {
                console.log('Model activated:', data);
                this.uiManager.showAlert('success', `Model activated: ${data.model_name} v${data.version}`);
                this.dataService.onModelActivated(data);
                this.loadModels();
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
        } catch (error) {
            console.error('Failed to load models:', error);
            this.uiManager.showAlert('danger', 'Failed to load models. Please try again.');
        }
    }

    async loadRetrainingJobs() {
        try {
            const data = await this.dataService.getRetrainingJobs();
            this.uiManager.renderJobs(data);
        } catch (error) {
            console.error('Failed to load retraining jobs:', error);
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
