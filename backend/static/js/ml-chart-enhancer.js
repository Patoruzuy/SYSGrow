/**
 * ML Chart Enhancer
 * ==================
 * Adds ML-powered features to existing Chart.js charts:
 * - Anomaly markers with severity indicators
 * - Correlation lines between related sensors
 * - Smart annotations with AI insights
 * - Predictive confidence bands
 * - Real-time anomaly detection overlays
 * 
 * Works with window.ML_AVAILABLE global state
 */

class MLChartEnhancer {
    constructor() {
        this.mlAvailable = false;
        this.anomalies = [];
        this.correlations = new Map();
        this.annotations = [];
        this.confidenceBands = new Map();
        
        // Configuration
        this.config = {
            anomalyThreshold: 0.7,
            correlationThreshold: 0.6,
            minConfidence: 0.65,
            showAnomalies: true,
            showCorrelations: true,
            showAnnotations: true,
            showConfidenceBands: false,
        };
        
        // Load saved preferences
        this.loadPreferences();
    }
    
    /**
     * Initialize enhancer and check ML availability
     */
    async init() {
        try {
            await this.checkMLAvailability();
            console.log('ML Chart Enhancer initialized', { mlAvailable: this.mlAvailable });
        } catch (error) {
            console.error('Failed to initialize ML Chart Enhancer:', error);
        }
    }
    
    /**
     * Check if ML models are available
     */
    async checkMLAvailability() {
        try {
            if (window.ML_AVAILABLE === undefined) {
                // ML status not loaded yet, wait a bit
                await new Promise(resolve => setTimeout(resolve, 1000));
            }
            
            this.mlAvailable = window.ML_AVAILABLE === true;
            
            if (this.mlAvailable && window.ML_MODELS) {
                // Check specific model availability
                const continuousMonitor = window.ML_MODELS['continuous_monitor'];
                if (continuousMonitor && !continuousMonitor.trained) {
                    this.mlAvailable = false;
                }
            }
        } catch (error) {
            console.warn('ML availability check failed:', error);
            this.mlAvailable = false;
        }
    }
    
    /**
     * Enhance a Chart.js chart with ML features
     * @param {Chart} chart - Chart.js instance
     * @param {Object} options - Enhancement options
     */
    async enhanceChart(chart, options = {}) {
        if (!chart) return;
        
        const enhanceOptions = {
            chartType: options.chartType || 'timeseries',
            sensorIds: options.sensorIds || [],
            timeRange: options.timeRange || { start: null, end: null },
            metrics: options.metrics || [],
            unitId: options.unitId || null,
            ...this.config,
            ...options
        };
        
        try {
            // Load ML data
            if (this.mlAvailable) {
                await Promise.all([
                    this.loadAnomalies(enhanceOptions),
                    this.loadCorrelations(enhanceOptions),
                    this.loadAnnotations(enhanceOptions),
                    this.loadConfidenceBands(enhanceOptions)
                ]);
            }
            
            // Apply enhancements to chart
            this.applyAnomalyMarkers(chart, enhanceOptions);
            this.applyCorrelationIndicators(chart, enhanceOptions);
            this.applySmartAnnotations(chart, enhanceOptions);
            this.applyConfidenceBands(chart, enhanceOptions);
            
            // Update chart
            chart.update('none'); // Update without animation
            
        } catch (error) {
            console.error('Failed to enhance chart:', error);
        }
    }
    
    /**
     * Load anomaly data from API
     */
    async loadAnomalies(options) {
        if (!this.config.showAnomalies) return;
        
        try {
            const params = {
                hours: this.getHoursFromTimeRange(options.timeRange),
            };
            
            if (options.unitId) params.unit_id = options.unitId;
            if (options.sensorIds.length > 0) {
                params.sensor_ids = options.sensorIds.join(',');
            }
            
            const result = await API.Analytics.getSensorsAnomalies(params);
            this.anomalies = result?.anomalies || [];
            
        } catch (error) {
            console.warn('Failed to load anomalies:', error);
            this.anomalies = [];
        }
    }
    
    /**
     * Load correlation data from API
     */
    async loadCorrelations(options) {
        if (!this.config.showCorrelations || !this.mlAvailable) return;
        
        try {
            const params = {
                hours: this.getHoursFromTimeRange(options.timeRange),
                threshold: this.config.correlationThreshold,
            };
            
            if (options.unitId) params.unit_id = options.unitId;
            if (options.metrics.length > 0) {
                params.metrics = options.metrics.join(',');
            }
            
            const result = await API.Analytics.getSensorsCorrelations(params);
            
            // Convert to map for quick lookup
            this.correlations.clear();
            (result?.correlations || []).forEach(corr => {
                const key = `${corr.metric1}_${corr.metric2}`;
                this.correlations.set(key, corr);
            });
            
        } catch (error) {
            console.warn('Failed to load correlations:', error);
            this.correlations.clear();
        }
    }
    
    /**
     * Load AI-generated annotations from API
     */
    async loadAnnotations(options) {
        if (!this.config.showAnnotations || !this.mlAvailable) return;
        
        try {
            const params = {
                hours: this.getHoursFromTimeRange(options.timeRange),
                min_confidence: this.config.minConfidence,
            };
            
            if (options.unitId) params.unit_id = options.unitId;
            if (options.sensorIds.length > 0) {
                params.sensor_ids = options.sensorIds.join(',');
            }
            
            const result = await API.ML.getAnnotations(params);
            this.annotations = result?.annotations || [];
            
        } catch (error) {
            console.warn('Failed to load annotations:', error);
            this.annotations = [];
        }
    }
    
    /**
     * Load predictive confidence bands
     */
    async loadConfidenceBands(options) {
        if (!this.config.showConfidenceBands || !this.mlAvailable) return;
        
        try {
            const params = {
                hours: this.getHoursFromTimeRange(options.timeRange),
            };
            
            if (options.unitId) params.unit_id = options.unitId;
            if (options.metrics.length > 0) {
                params.metrics = options.metrics.join(',');
            }
            
            const result = await API.ML.getConfidenceBands(params);
            
            // Convert to map for quick lookup
            this.confidenceBands.clear();
            (result?.bands || []).forEach(band => {
                this.confidenceBands.set(band.metric, band);
            });
            
        } catch (error) {
            console.warn('Failed to load confidence bands:', error);
            this.confidenceBands.clear();
        }
    }
    
    /**
     * Apply anomaly markers to chart
     */
    applyAnomalyMarkers(chart, options) {
        if (!this.config.showAnomalies || this.anomalies.length === 0) return;
        
        // Initialize plugins array if needed
        if (!chart.options.plugins) chart.options.plugins = {};
        if (!chart.options.plugins.annotation) chart.options.plugins.annotation = { annotations: {} };
        
        const annotations = chart.options.plugins.annotation.annotations || {};
        
        // Add anomaly markers
        this.anomalies.forEach((anomaly, index) => {
            const timestamp = new Date(anomaly.timestamp).getTime();
            const severity = anomaly.severity || 'warning';
            
            // Add vertical line for anomaly
            annotations[`anomaly_${index}`] = {
                type: 'line',
                xMin: timestamp,
                xMax: timestamp,
                borderColor: this.getAnomalySeverityColor(severity),
                borderWidth: 2,
                borderDash: [6, 6],
                label: {
                    content: `Anomaly: ${anomaly.message || 'Detected'}`,
                    enabled: true,
                    position: 'start',
                    backgroundColor: this.getAnomalySeverityColor(severity),
                    color: '#fff',
                    font: {
                        size: 10
                    },
                    padding: 4,
                    rotation: -90,
                }
            };
            
            // Add point marker
            annotations[`anomaly_point_${index}`] = {
                type: 'point',
                xValue: timestamp,
                yValue: anomaly.value || 0,
                backgroundColor: this.getAnomalySeverityColor(severity),
                borderColor: '#fff',
                borderWidth: 2,
                radius: 6,
            };
        });
        
        chart.options.plugins.annotation.annotations = annotations;
    }
    
    /**
     * Apply correlation indicators to chart
     */
    applyCorrelationIndicators(chart, options) {
        if (!this.config.showCorrelations || this.correlations.size === 0) return;
        
        // Add correlation info to chart subtitle
        const correlationTexts = [];
        this.correlations.forEach((corr, key) => {
            const strength = Math.abs(corr.correlation).toFixed(2);
            const direction = corr.correlation > 0 ? 'positive' : 'negative';
            correlationTexts.push(
                `${corr.metric1} ↔ ${corr.metric2}: ${strength} (${direction})`
            );
        });
        
        if (correlationTexts.length > 0 && chart.options.plugins.subtitle) {
            chart.options.plugins.subtitle.text = correlationTexts.slice(0, 3).join(' | ');
            chart.options.plugins.subtitle.display = true;
        }
    }
    
    /**
     * Apply smart annotations to chart
     */
    applySmartAnnotations(chart, options) {
        if (!this.config.showAnnotations || this.annotations.length === 0) return;
        
        const annotations = chart.options.plugins.annotation.annotations || {};
        
        this.annotations.forEach((annotation, index) => {
            const timestamp = new Date(annotation.timestamp).getTime();
            
            annotations[`insight_${index}`] = {
                type: 'label',
                xValue: timestamp,
                yValue: annotation.y_position || 'max',
                content: annotation.message,
                backgroundColor: 'rgba(13, 110, 253, 0.9)',
                color: '#fff',
                font: {
                    size: 11,
                    weight: 'bold'
                },
                padding: 6,
                borderRadius: 4,
                callout: {
                    enabled: true,
                    borderColor: 'rgba(13, 110, 253, 0.9)',
                    borderWidth: 1,
                }
            };
        });
        
        chart.options.plugins.annotation.annotations = annotations;
    }
    
    /**
     * Apply confidence bands to chart
     */
    applyConfidenceBands(chart, options) {
        if (!this.config.showConfidenceBands || this.confidenceBands.size === 0) return;
        
        // Add confidence band datasets
        const confidenceDatasets = [];
        
        this.confidenceBands.forEach((band, metric) => {
            // Upper bound
            confidenceDatasets.push({
                label: `${metric} (upper bound)`,
                data: band.upper_bound,
                borderColor: 'rgba(13, 110, 253, 0.3)',
                backgroundColor: 'transparent',
                borderDash: [5, 5],
                borderWidth: 1,
                pointRadius: 0,
                fill: false,
                tension: 0.4,
            });
            
            // Lower bound
            confidenceDatasets.push({
                label: `${metric} (lower bound)`,
                data: band.lower_bound,
                borderColor: 'rgba(13, 110, 253, 0.3)',
                backgroundColor: 'rgba(13, 110, 253, 0.1)',
                borderDash: [5, 5],
                borderWidth: 1,
                pointRadius: 0,
                fill: '-1', // Fill to previous dataset (upper bound)
                tension: 0.4,
            });
        });
        
        // Add to chart datasets
        chart.data.datasets.push(...confidenceDatasets);
    }
    
    /**
     * Get color based on anomaly severity
     */
    getAnomalySeverityColor(severity) {
        const colors = {
            critical: '#dc3545',
            high: '#fd7e14',
            warning: '#ffc107',
            low: '#17a2b8',
            info: '#6c757d',
        };
        return colors[severity] || colors.warning;
    }
    
    /**
     * Get hours from time range
     */
    getHoursFromTimeRange(timeRange) {
        if (!timeRange.start || !timeRange.end) return 24;
        
        const start = new Date(timeRange.start);
        const end = new Date(timeRange.end);
        return Math.ceil((end - start) / (1000 * 60 * 60));
    }
    
    /**
     * Toggle enhancement feature
     */
    toggleFeature(feature, enabled) {
        if (this.config.hasOwnProperty(feature)) {
            this.config[feature] = enabled;
            this.savePreferences();
        }
    }
    
    /**
     * Get current configuration
     */
    getConfig() {
        return { ...this.config };
    }
    
    /**
     * Update configuration
     */
    updateConfig(updates) {
        Object.assign(this.config, updates);
        this.savePreferences();
    }
    
    /**
     * Save preferences to localStorage
     */
    savePreferences() {
        try {
            localStorage.setItem('ml-chart-enhancer:config', JSON.stringify(this.config));
        } catch (error) {
            console.warn('Failed to save ML enhancer preferences:', error);
        }
    }
    
    /**
     * Load preferences from localStorage
     */
    loadPreferences() {
        try {
            const saved = localStorage.getItem('ml-chart-enhancer:config');
            if (saved) {
                const parsed = JSON.parse(saved);
                Object.assign(this.config, parsed);
            }
        } catch (error) {
            console.warn('Failed to load ML enhancer preferences:', error);
        }
    }
    
    /**
     * Clear all enhancements from chart
     */
    clearEnhancements(chart) {
        if (!chart) return;
        
        // Remove annotation plugin data
        if (chart.options.plugins?.annotation) {
            chart.options.plugins.annotation.annotations = {};
        }
        
        // Remove confidence band datasets
        chart.data.datasets = chart.data.datasets.filter(ds => 
            !ds.label?.includes('upper bound') && 
            !ds.label?.includes('lower bound')
        );
        
        chart.update('none');
    }
    
    /**
     * Create control panel HTML
     */
    createControlPanel() {
        return `
            <div class="ml-enhancer-controls">
                <div class="controls-header">
                    <h6><i class="fas fa-brain"></i> ML Enhancements</h6>
                    <span class="ml-status ${this.mlAvailable ? 'active' : 'inactive'}">
                        <i class="fas fa-circle"></i> 
                        ${this.mlAvailable ? 'Active' : 'Unavailable'}
                    </span>
                </div>
                <div class="controls-body">
                    <div class="form-check form-switch">
                        <input class="form-check-input" type="checkbox" id="ml-show-anomalies" 
                            ${this.config.showAnomalies ? 'checked' : ''}>
                        <label class="form-check-label" for="ml-show-anomalies">
                            Show Anomaly Markers
                        </label>
                    </div>
                    <div class="form-check form-switch">
                        <input class="form-check-input" type="checkbox" id="ml-show-correlations" 
                            ${this.config.showCorrelations ? 'checked' : ''} 
                            ${!this.mlAvailable ? 'disabled' : ''}>
                        <label class="form-check-label" for="ml-show-correlations">
                            Show Correlations
                        </label>
                    </div>
                    <div class="form-check form-switch">
                        <input class="form-check-input" type="checkbox" id="ml-show-annotations" 
                            ${this.config.showAnnotations ? 'checked' : ''}
                            ${!this.mlAvailable ? 'disabled' : ''}>
                        <label class="form-check-label" for="ml-show-annotations">
                            Show AI Insights
                        </label>
                    </div>
                    <div class="form-check form-switch">
                        <input class="form-check-input" type="checkbox" id="ml-show-bands" 
                            ${this.config.showConfidenceBands ? 'checked' : ''}
                            ${!this.mlAvailable ? 'disabled' : ''}>
                        <label class="form-check-label" for="ml-show-bands">
                            Show Confidence Bands
                        </label>
                    </div>
                </div>
            </div>
        `;
    }
    
    /**
     * Attach control panel event listeners
     */
    attachControlPanelListeners(container, onUpdate) {
        const checkboxes = container.querySelectorAll('input[type="checkbox"]');
        
        checkboxes.forEach(checkbox => {
            checkbox.addEventListener('change', (e) => {
                const feature = {
                    'ml-show-anomalies': 'showAnomalies',
                    'ml-show-correlations': 'showCorrelations',
                    'ml-show-annotations': 'showAnnotations',
                    'ml-show-bands': 'showConfidenceBands',
                }[e.target.id];
                
                if (feature) {
                    this.toggleFeature(feature, e.target.checked);
                    if (onUpdate) onUpdate();
                }
            });
        });
    }
}

// Export for use in other modules
window.MLChartEnhancer = MLChartEnhancer;
