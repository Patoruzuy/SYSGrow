/**
 * ML Dashboard Data Service
 * Handles API calls and caching for ML dashboard
 * 
 * @module ml/data-service
 */

class MLDataService {
    constructor() {
        this.cache = new Map();
        this.cacheTTL = 60000; // 1 minute default TTL
        this.pendingRequests = new Map();
    }

    // =========================================================================
    // Cache Management
    // =========================================================================

    getFromCache(key) {
        const cached = this.cache.get(key);
        if (cached && Date.now() - cached.timestamp < this.cacheTTL) {
            return cached.data;
        }
        this.cache.delete(key);
        return null;
    }

    setCache(key, data, ttl = this.cacheTTL) {
        this.cache.set(key, { data, timestamp: Date.now(), ttl });
    }

    invalidateCache(key) {
        if (key.includes('*')) {
            const pattern = new RegExp(key.replace('*', '.*'));
            for (const k of this.cache.keys()) {
                if (pattern.test(k)) this.cache.delete(k);
            }
        } else {
            this.cache.delete(key);
        }
    }

    clearCache() {
        this.cache.clear();
    }

    async deduplicateRequest(key, requestFn) {
        if (this.pendingRequests.has(key)) {
            return this.pendingRequests.get(key);
        }
        const promise = requestFn().finally(() => {
            this.pendingRequests.delete(key);
        });
        this.pendingRequests.set(key, promise);
        return promise;
    }

    // =========================================================================
    // Health & Status
    // =========================================================================

    async getHealth() {
        const cached = this.getFromCache('health');
        if (cached) return cached;
        const data = await API.ML.getHealth();
        this.setCache('health', data, 30000);
        return data;
    }

    async getModelsStatus() {
        return this.deduplicateRequest('models-status', async () => {
            return await API.ML.getModelsStatus();
        });
    }

    // =========================================================================
    // Models Management
    // =========================================================================

    async getModels(forceRefresh = false) {
        const cacheKey = 'models';
        if (!forceRefresh) {
            const cached = this.getFromCache(cacheKey);
            if (cached) return cached;
        }
        const result = await API.ML.getModels();
        const models = result.models || result || [];
        this.setCache(cacheKey, models, 120000);
        return models;
    }

    async getModel(modelName) {
        const cacheKey = `model:${modelName}`;
        const cached = this.getFromCache(cacheKey);
        if (cached) return cached;
        const data = await API.ML.getModel(modelName);
        this.setCache(cacheKey, data);
        return data;
    }

    async getModelFeatures(modelName) {
        const cacheKey = `model-features:${modelName}`;
        const cached = this.getFromCache(cacheKey);
        if (cached) return cached;
        const data = await API.ML.getModelFeatures(modelName);
        this.setCache(cacheKey, data, 300000);
        return data;
    }

    async activateModel(modelName, version) {
        const result = await API.ML.activateModel(modelName, version);
        this.invalidateCache('models');
        this.invalidateCache(`model:${modelName}`);
        return result;
    }

    async retrainModel(modelName, options = {}) {
        return await API.ML.retrainModel(modelName, options);
    }

    // =========================================================================
    // Drift Monitoring
    // =========================================================================

    async getDriftMetrics(modelName) {
        if (!modelName) return null;
        const cacheKey = `drift:${modelName}`;
        const cached = this.getFromCache(cacheKey);
        if (cached) return cached;
        const data = await API.ML.getDrift(modelName);
        this.setCache(cacheKey, data, 60000);
        return data;
    }

    async getDriftHistory(modelName) {
        if (!modelName) return [];
        const cacheKey = `drift-history:${modelName}`;
        const cached = this.getFromCache(cacheKey);
        if (cached) return cached;
        const result = await API.ML.getDriftHistory(modelName);
        const history = result.history || result || [];
        this.setCache(cacheKey, history, 120000);
        return history;
    }

    // =========================================================================
    // Training & Retraining Jobs
    // =========================================================================

    async getTrainingHistory() {
        const cacheKey = 'training-history';
        const cached = this.getFromCache(cacheKey);
        if (cached) return cached;
        const data = await API.ML.getTrainingHistory();
        this.setCache(cacheKey, data, 60000);
        return data;
    }

    async getRetrainingJobs() {
        const cacheKey = 'retraining-jobs';
        const cached = this.getFromCache(cacheKey);
        if (cached) return cached;
        const data = await API.Retraining.getJobs();
        this.setCache(cacheKey, data, 60000);
        return data;
    }

    async cancelTraining(modelType = null) {
        const result = await API.ML.cancelTraining(modelType);
        this.invalidateCache('training-history');
        return result;
    }

    async runJob(jobId) {
        const result = await API.ML.runJob(jobId);
        this.invalidateCache('retraining-jobs');
        return result;
    }

    async toggleJob(jobId, enable) {
        const action = enable ? 'enable' : 'disable';
        const result = await API.ML.updateJob(jobId, action);
        this.invalidateCache('retraining-jobs');
        return result;
    }

    async scheduleRetraining(scheduleData) {
        const result = await API.ML.scheduleRetraining(scheduleData);
        this.invalidateCache('retraining-jobs');
        return result;
    }

    // =========================================================================
    // Retraining Scheduler Status (NEW)
    // =========================================================================

    async getRetrainingStatus() {
        const cacheKey = 'retraining-status';
        const cached = this.getFromCache(cacheKey);
        if (cached) return cached;
        const data = await API.Retraining.getStatus();
        this.setCache(cacheKey, data, 30000);
        return data;
    }

    async startScheduler() {
        const result = await API.Retraining.startScheduler();
        this.invalidateCache('retraining-status');
        return result;
    }

    async stopScheduler() {
        const result = await API.Retraining.stopScheduler();
        this.invalidateCache('retraining-status');
        return result;
    }

    // =========================================================================
    // Continuous Monitoring (NEW)
    // =========================================================================

    async getContinuousStatus() {
        const cacheKey = 'continuous-status';
        const cached = this.getFromCache(cacheKey);
        if (cached) return cached;
        const data = await API.Continuous.getStatus();
        this.setCache(cacheKey, data, 30000);
        return data;
    }

    async startContinuousMonitoring() {
        const result = await API.Continuous.start();
        this.invalidateCache('continuous-status');
        return result;
    }

    async stopContinuousMonitoring() {
        const result = await API.Continuous.stop();
        this.invalidateCache('continuous-status');
        return result;
    }

    async getCriticalInsights() {
        const cacheKey = 'critical-insights';
        const cached = this.getFromCache(cacheKey);
        if (cached) return cached;
        const data = await API.Continuous.getCriticalInsights();
        this.setCache(cacheKey, data, 30000);
        return data;
    }

    // =========================================================================
    // Training Data Quality (NEW)
    // =========================================================================

    async getTrainingDataSummary() {
        const cacheKey = 'training-data-summary';
        const cached = this.getFromCache(cacheKey);
        if (cached) return cached;
        const data = await API.TrainingData.getSummary();
        this.setCache(cacheKey, data, 120000);
        return data;
    }

    async getDataQuality() {
        const cacheKey = 'data-quality-metrics';
        const cached = this.getFromCache(cacheKey);
        if (cached) return cached;
        const data = await API.TrainingData.getQuality();
        this.setCache(cacheKey, data, 120000);
        return data;
    }

    async validateTrainingData(datasetType = 'disease') {
        const result = await API.TrainingData.validate({ dataset_type: datasetType });
        this.invalidateCache('data-quality*');
        this.invalidateCache('training-data*');
        return result;
    }

    // =========================================================================
    // Disease Trends (NEW)
    // =========================================================================

    async getDiseaseTrends(days = 30) {
        const cacheKey = `disease-trends:${days}`;
        const cached = this.getFromCache(cacheKey);
        if (cached) return cached;
        const data = await API.ML.getDiseaseTrends(days);
        this.setCache(cacheKey, data, 300000);
        return data;
    }

    // =========================================================================
    // Model Comparison (NEW — uses backend endpoint)
    // =========================================================================

    async compareModels(modelNames) {
        const result = await API.ML.compareModels(modelNames);
        return result;
    }

    // =========================================================================
    // ML Readiness (NEW — Phase C)
    // =========================================================================

    async getIrrigationReadiness(unitId) {
        const cacheKey = `readiness:${unitId}`;
        const cached = this.getFromCache(cacheKey);
        if (cached) return cached;
        const data = await API.MLReadiness.getIrrigationReadiness(unitId);
        this.setCache(cacheKey, data, 60000);
        return data;
    }

    async getActivationStatus(unitId) {
        const cacheKey = `activation-status:${unitId}`;
        const cached = this.getFromCache(cacheKey);
        if (cached) return cached;
        const data = await API.MLReadiness.getActivationStatus(unitId);
        this.setCache(cacheKey, data, 60000);
        return data;
    }

    async activateMLModel(unitId, modelName) {
        const result = await API.MLReadiness.activateModel(unitId, modelName);
        this.invalidateCache(`readiness:${unitId}`);
        this.invalidateCache(`activation-status:${unitId}`);
        return result;
    }

    async deactivateMLModel(unitId, modelName) {
        const result = await API.MLReadiness.deactivateModel(unitId, modelName);
        this.invalidateCache(`readiness:${unitId}`);
        this.invalidateCache(`activation-status:${unitId}`);
        return result;
    }

    async checkAllReadiness() {
        const result = await API.MLReadiness.checkAll();
        this.invalidateCache('readiness*');
        this.invalidateCache('activation-status*');
        return result;
    }

    // =========================================================================
    // Irrigation Recommendations (NEW — Phase C)
    // =========================================================================

    async getIrrigationRecommendations(plantId) {
        const cacheKey = `irrigation-recs:${plantId}`;
        const cached = this.getFromCache(cacheKey);
        if (cached) return cached;
        const data = await API.Irrigation.getRecommendations(plantId);
        this.setCache(cacheKey, data, 60000);
        return data;
    }

    async getIrrigationRequests(limit = 20) {
        const cacheKey = `irrigation-requests:${limit}`;
        const cached = this.getFromCache(cacheKey);
        if (cached) return cached;
        const data = await API.Irrigation.getPendingRequests(limit);
        this.setCache(cacheKey, data, 30000);
        return data;
    }

    async getIrrigationConfig(unitId) {
        const cacheKey = `irrigation-config:${unitId}`;
        const cached = this.getFromCache(cacheKey);
        if (cached) return cached;
        const data = await API.Irrigation.getConfig(unitId);
        this.setCache(cacheKey, data, 120000);
        return data;
    }

    // =========================================================================
    // A/B Testing (NEW — Phase C)
    // =========================================================================

    async getABTests(status = null) {
        const cacheKey = `ab-tests:${status || 'all'}`;
        const cached = this.getFromCache(cacheKey);
        if (cached) return cached;
        const data = await API.ABTesting.listTests(status);
        this.setCache(cacheKey, data, 60000);
        return data;
    }

    async getABTestAnalysis(testId) {
        const cacheKey = `ab-analysis:${testId}`;
        const cached = this.getFromCache(cacheKey);
        if (cached) return cached;
        const data = await API.ABTesting.getAnalysis(testId);
        this.setCache(cacheKey, data, 60000);
        return data;
    }

    async completeABTest(testId, winner = null) {
        const result = await API.ABTesting.completeTest(testId, winner);
        this.invalidateCache('ab-tests*');
        this.invalidateCache(`ab-analysis:${testId}`);
        return result;
    }

    async cancelABTest(testId) {
        const result = await API.ABTesting.cancelTest(testId);
        this.invalidateCache('ab-tests*');
        return result;
    }

    // =========================================================================
    // Event Handlers for Cache Invalidation
    // =========================================================================

    onTrainingComplete(data) {
        this.invalidateCache('models');
        this.invalidateCache('training-history');
        if (data.model_name) {
            this.invalidateCache(`model:${data.model_name}`);
            this.invalidateCache(`drift:${data.model_name}`);
            this.invalidateCache(`drift-history:${data.model_name}`);
        }
    }

    onModelActivated(data) {
        this.invalidateCache('models');
        if (data.model_name) {
            this.invalidateCache(`model:${data.model_name}`);
        }
    }

    onDriftDetected(data) {
        if (data.model_name) {
            this.invalidateCache(`drift:${data.model_name}`);
            this.invalidateCache(`drift-history:${data.model_name}`);
        }
    }
}

// Export singleton instance
window.MLDataService = new MLDataService();
