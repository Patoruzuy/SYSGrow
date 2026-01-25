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

    /**
     * Get cached data if not expired
     * @param {string} key - Cache key
     * @returns {*} Cached data or null
     */
    getFromCache(key) {
        const cached = this.cache.get(key);
        if (cached && Date.now() - cached.timestamp < this.cacheTTL) {
            return cached.data;
        }
        this.cache.delete(key);
        return null;
    }

    /**
     * Store data in cache
     * @param {string} key - Cache key
     * @param {*} data - Data to cache
     * @param {number} [ttl] - Optional TTL override
     */
    setCache(key, data, ttl = this.cacheTTL) {
        this.cache.set(key, {
            data,
            timestamp: Date.now(),
            ttl
        });
    }

    /**
     * Invalidate cache entry
     * @param {string} key - Cache key or pattern
     */
    invalidateCache(key) {
        if (key.includes('*')) {
            const pattern = new RegExp(key.replace('*', '.*'));
            for (const k of this.cache.keys()) {
                if (pattern.test(k)) {
                    this.cache.delete(k);
                }
            }
        } else {
            this.cache.delete(key);
        }
    }

    /**
     * Clear all cache
     */
    clearCache() {
        this.cache.clear();
    }

    /**
     * Deduplicate concurrent requests
     * @param {string} key - Request key
     * @param {Function} requestFn - Request function
     * @returns {Promise<*>} Request result
     */
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

    /**
     * Check ML system health
     * @returns {Promise<Object>} Health status
     */
    async getHealth() {
        const cached = this.getFromCache('health');
        if (cached) return cached;

        const data = await API.ML.getHealth();
        this.setCache('health', data, 30000); // 30s cache
        return data;
    }

    /**
     * Get all models status summary
     * @returns {Promise<Object>} Models status
     */
    async getModelsStatus() {
        return this.deduplicateRequest('models-status', async () => {
            const data = await API.ML.getModelsStatus();
            return data;
        });
    }

    // =========================================================================
    // Models Management
    // =========================================================================

    /**
     * Get all registered models
     * @param {boolean} [forceRefresh=false] - Bypass cache
     * @returns {Promise<Array>} List of models
     */
    async getModels(forceRefresh = false) {
        const cacheKey = 'models';
        
        if (!forceRefresh) {
            const cached = this.getFromCache(cacheKey);
            if (cached) return cached;
        }

        const result = await API.ML.getModels();
        const models = result.models || result || [];
        this.setCache(cacheKey, models, 120000); // 2 min cache
        return models;
    }

    /**
     * Get specific model details
     * @param {string} modelName - Model name
     * @returns {Promise<Object>} Model details
     */
    async getModel(modelName) {
        const cacheKey = `model:${modelName}`;
        const cached = this.getFromCache(cacheKey);
        if (cached) return cached;

        const data = await API.ML.getModel(modelName);
        this.setCache(cacheKey, data);
        return data;
    }

    /**
     * Get model features/importance
     * @param {string} modelName - Model name
     * @returns {Promise<Object>} Model features
     */
    async getModelFeatures(modelName) {
        const cacheKey = `model-features:${modelName}`;
        const cached = this.getFromCache(cacheKey);
        if (cached) return cached;

        const data = await API.ML.getModelFeatures(modelName);
        this.setCache(cacheKey, data, 300000); // 5 min cache
        return data;
    }

    /**
     * Activate a model version
     * @param {string} modelName - Model name
     * @param {string} version - Version to activate
     * @returns {Promise<Object>} Activation result
     */
    async activateModel(modelName, version) {
        const result = await API.ML.activateModel(modelName, version);
        this.invalidateCache('models');
        this.invalidateCache(`model:${modelName}`);
        return result;
    }

    /**
     * Retrain a model
     * @param {string} modelName - Model name
     * @param {Object} [options] - Training options
     * @returns {Promise<Object>} Training result
     */
    async retrainModel(modelName, options = {}) {
        const result = await API.ML.retrainModel(modelName, options);
        // Don't invalidate cache immediately - wait for training complete event
        return result;
    }

    // =========================================================================
    // Drift Monitoring
    // =========================================================================

    /**
     * Get drift metrics for a model
     * @param {string} modelName - Model name
     * @returns {Promise<Object>} Drift metrics
     */
    async getDriftMetrics(modelName) {
        if (!modelName) return null;

        const cacheKey = `drift:${modelName}`;
        const cached = this.getFromCache(cacheKey);
        if (cached) return cached;

        const data = await API.ML.getDrift(modelName);
        this.setCache(cacheKey, data, 60000); // 1 min cache
        return data;
    }

    /**
     * Get drift history for a model
     * @param {string} modelName - Model name
     * @returns {Promise<Array>} Drift history
     */
    async getDriftHistory(modelName) {
        if (!modelName) return [];

        const cacheKey = `drift-history:${modelName}`;
        const cached = this.getFromCache(cacheKey);
        if (cached) return cached;

        const result = await API.ML.getDriftHistory(modelName);
        const history = result.history || result || [];
        this.setCache(cacheKey, history, 120000); // 2 min cache
        return history;
    }

    // =========================================================================
    // Training & Retraining Jobs
    // =========================================================================

    /**
     * Get training history
     * @returns {Promise<Object>} Training history
     */
    async getTrainingHistory() {
        const cacheKey = 'training-history';
        const cached = this.getFromCache(cacheKey);
        if (cached) return cached;

        const data = await API.ML.getTrainingHistory();
        this.setCache(cacheKey, data, 60000);
        return data;
    }

    /**
     * Get retraining jobs
     * @returns {Promise<Object>} Retraining jobs
     */
    async getRetrainingJobs() {
        const cacheKey = 'retraining-jobs';
        const cached = this.getFromCache(cacheKey);
        if (cached) return cached;

        const data = await API.Retraining.getJobs();
        this.setCache(cacheKey, data, 60000);
        return data;
    }

    /**
     * Cancel training
     * @param {string} [modelType] - Optional model type
     * @returns {Promise<Object>} Cancellation result
     */
    async cancelTraining(modelType = null) {
        const result = await API.ML.cancelTraining(modelType);
        this.invalidateCache('training-history');
        return result;
    }

    /**
     * Run a retraining job immediately
     * @param {string} jobId - Job ID
     * @returns {Promise<Object>} Job result
     */
    async runJob(jobId) {
        const result = await API.ML.runJob(jobId);
        this.invalidateCache('retraining-jobs');
        return result;
    }

    /**
     * Toggle job enabled/disabled
     * @param {string} jobId - Job ID
     * @param {boolean} enable - Enable or disable
     * @returns {Promise<Object>} Update result
     */
    async toggleJob(jobId, enable) {
        const action = enable ? 'enable' : 'disable';
        const result = await API.ML.updateJob(jobId, action);
        this.invalidateCache('retraining-jobs');
        return result;
    }

    /**
     * Schedule a new retraining job
     * @param {Object} scheduleData - Schedule configuration
     * @returns {Promise<Object>} Schedule result
     */
    async scheduleRetraining(scheduleData) {
        const result = await API.ML.scheduleRetraining(scheduleData);
        this.invalidateCache('retraining-jobs');
        return result;
    }

    // =========================================================================
    // Event Handlers for Cache Invalidation
    // =========================================================================

    /**
     * Handle training complete event - invalidate caches
     * @param {Object} data - Event data
     */
    onTrainingComplete(data) {
        this.invalidateCache('models');
        this.invalidateCache('training-history');
        if (data.model_name) {
            this.invalidateCache(`model:${data.model_name}`);
            this.invalidateCache(`drift:${data.model_name}`);
            this.invalidateCache(`drift-history:${data.model_name}`);
        }
    }

    /**
     * Handle model activated event
     * @param {Object} data - Event data
     */
    onModelActivated(data) {
        this.invalidateCache('models');
        if (data.model_name) {
            this.invalidateCache(`model:${data.model_name}`);
        }
    }

    /**
     * Handle drift detected event
     * @param {Object} data - Event data
     */
    onDriftDetected(data) {
        if (data.model_name) {
            this.invalidateCache(`drift:${data.model_name}`);
            this.invalidateCache(`drift-history:${data.model_name}`);
        }
    }
}

// Export singleton instance
window.MLDataService = new MLDataService();
