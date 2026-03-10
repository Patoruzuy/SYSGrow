/**
 * ML Status Manager
 * Centralized ML model availability checking and status management
 */

const MLStatus = {
    // Global ML availability state
    available: {
        disease_predictor: false,
        climate_optimizer: false,
        yield_predictor: false,
        personalized_learning: false,
        irrigation_optimizer: false
    },
    
    // Model metadata
    models: {},
    
    // Status check interval
    checkInterval: null,
    
    // Callbacks for status changes
    callbacks: [],
    
    // Confidence thresholds
    thresholds: {
        minimum_confidence: 0.7,
        minimum_accuracy: 0.7,
        minimum_samples: 100,
        minimum_data_quality: 0.6
    },
    
    /**
     * Initialize ML status checking
     */
    init: async function() {
        // Initial status check
        await this.checkStatus();
        
        // Set up periodic checks (every 5 minutes)
        this.checkInterval = setInterval(() => {
            this.checkStatus();
        }, 300000); // 5 minutes
    },
    
    /**
     * Check ML models availability status
     */
    checkStatus: async function() {
        try {
            const data = await API.ML.getModelsStatus();
            
            // Update availability flags
            Object.keys(this.available).forEach(modelType => {
                const model = data.models && data.models[modelType];
                
                if (model) {
                    // Check if model meets quality thresholds
                    this.available[modelType] = this.isModelUsable(model);
                    this.models[modelType] = model;
                } else {
                    this.available[modelType] = false;
                    this.models[modelType] = null;
                }
            });
            
            // Store in window for global access
            window.ML_AVAILABLE = this.available;
            window.ML_MODELS = this.models;
            
            // Trigger callbacks
            this.triggerCallbacks();
            
            return true;
        } catch (error) {
            console.error('Failed to check ML status:', error);
            // Set all to unavailable on error
            Object.keys(this.available).forEach(key => {
                this.available[key] = false;
            });
            window.ML_AVAILABLE = this.available;
            return false;
        }
    },
    
    /**
     * Check if a model meets quality thresholds for use
     */
    isModelUsable: function(model) {
        if (!model || !model.trained) {
            return false;
        }
        
        // Check accuracy threshold
        if (model.accuracy && model.accuracy < this.thresholds.minimum_accuracy) {
            console.warn(`Model ${model.name} accuracy too low: ${model.accuracy}`);
            return false;
        }
        
        // Check training samples
        if (model.training_samples && model.training_samples < this.thresholds.minimum_samples) {
            console.warn(`Model ${model.name} has insufficient samples: ${model.training_samples}`);
            return false;
        }
        
        // Check data quality
        if (model.data_quality && model.data_quality < this.thresholds.minimum_data_quality) {
            console.warn(`Model ${model.name} data quality too low: ${model.data_quality}`);
            return false;
        }
        
        // Check if model is active
        if (model.active === false) {
            return false;
        }
        
        return true;
    },
    
    /**
     * Check if a specific model type is available
     */
    isAvailable: function(modelType) {
        return this.available[modelType] === true;
    },
    
    /**
     * Get model metadata
     */
    getModel: function(modelType) {
        return this.models[modelType] || null;
    },
    
    /**
     * Get model confidence for a prediction
     */
    getConfidence: function(modelType) {
        const model = this.getModel(modelType);
        return model && model.confidence ? model.confidence : 0;
    },
    
    /**
     * Check if prediction confidence meets threshold
     */
    meetsConfidenceThreshold: function(confidence) {
        return confidence >= this.thresholds.minimum_confidence;
    },
    
    /**
     * Register a callback for status changes
     */
    onChange: function(callback) {
        if (typeof callback === 'function') {
            this.callbacks.push(callback);
        }
    },
    
    /**
     * Trigger all registered callbacks
     */
    triggerCallbacks: function() {
        this.callbacks.forEach(callback => {
            try {
                callback(this.available, this.models);
            } catch (error) {
                console.error('Callback error:', error);
            }
        });
    },
    
    /**
     * Get ML status badge HTML
     */
    getStatusBadge: function(modelType) {
        const available = this.isAvailable(modelType);
        const model = this.getModel(modelType);
        
        if (available && model) {
            const accuracy = model.accuracy ? (model.accuracy * 100).toFixed(0) : '--';
            return `<span class="badge badge-success ml-status-badge" title="ML Model Active: ${accuracy}% accuracy">
                🤖 ML Enhanced
            </span>`;
        } else {
            return `<span class="badge badge-secondary ml-status-badge" title="ML Model Not Available">
                📊 Statistical
            </span>`;
        }
    },
    
    /**
     * Show ML feature indicator
     */
    showFeatureIndicator: function(containerEl, modelType, featureName) {
        if (!containerEl) return;
        
        const available = this.isAvailable(modelType);
        const model = this.getModel(modelType);
        const esc = window.escapeHtml || function(t) { if (!t) return ''; const d = document.createElement('div'); d.textContent = t; return d.innerHTML; };
        
        const indicator = document.createElement('div');
        indicator.className = `ml-feature-indicator ${available ? 'ml-available' : 'ml-unavailable'}`;
        
        if (available && model) {
            indicator.innerHTML = `
                <i class="fas fa-robot"></i>
                <span>${esc(featureName)}</span>
                <small>Accuracy: ${(model.accuracy * 100).toFixed(0)}%</small>
            `;
        } else {
            indicator.innerHTML = `
                <i class="fas fa-chart-line"></i>
                <span>${esc(featureName)} (Statistical)</span>
                <small>ML model training...</small>
            `;
        }
        
        containerEl.appendChild(indicator);
    },
    
    /**
     * Get warning message for low confidence predictions
     */
    getConfidenceWarning: function(confidence, modelType) {
        if (confidence >= 0.8) {
            return null; // High confidence, no warning
        } else if (confidence >= 0.7) {
            return `⚠️ This prediction has moderate confidence (${(confidence * 100).toFixed(0)}%). Verify manually.`;
        } else {
            return `⚠️ This prediction has low confidence (${(confidence * 100).toFixed(0)}%). Use with caution.`;
        }
    },
    
    /**
     * Create ML explainability tooltip
     */
    createExplainabilityTooltip: function(prediction) {
        if (!prediction || !prediction.reasoning) {
            return '';
        }
        
        const esc = window.escapeHtml || function(t) { if (!t) return ''; const d = document.createElement('div'); d.textContent = t; return d.innerHTML; };
        let html = '<div class="ml-explainability-tooltip">';
        html += '<strong>Why this prediction?</strong>';
        html += '<ul>';
        
        if (Array.isArray(prediction.reasoning)) {
            prediction.reasoning.forEach(reason => {
                const weight = reason.weight ? ` (${(reason.weight * 100).toFixed(0)}%)` : '';
                html += `<li>${esc(reason.text)}${weight}</li>`;
            });
        }
        
        html += '</ul>';
        
        if (prediction.similar_situations) {
            html += `<small>Based on ${prediction.similar_situations} similar situations</small>`;
        }
        
        if (prediction.accuracy_when_similar) {
            html += `<small> with ${(prediction.accuracy_when_similar * 100).toFixed(0)}% accuracy</small>`;
        }
        
        html += '</div>';
        
        return html;
    },
    
    /**
     * Cleanup on page unload
     */
    destroy: function() {
        if (this.checkInterval) {
            clearInterval(this.checkInterval);
            this.checkInterval = null;
        }
        this.callbacks = [];
    }
};

// Initialize on DOM ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        MLStatus.init();
    });
} else {
    MLStatus.init();
}

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
    MLStatus.destroy();
});

// Expose to global scope
window.MLStatus = MLStatus;
