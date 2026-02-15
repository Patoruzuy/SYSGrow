/**
 * AI Insights Manager
 * Manages AI-powered features on the dashboard
 * 
 * Features:
 * - Real-time insights from continuous monitoring
 * - Disease risk predictions
 * - Growth stage tracking
 * - Harvest forecasting
 * - Personalized recommendations
 * - 7-day environmental forecasts
 */

class AIInsightsManager {
    constructor(apiClient, socketManager) {
        this.api = apiClient;
        this.socket = socketManager;
        this.selectedUnitId = null;
        this.refreshInterval = null;
        
        // Cache elements
        this.elements = {
            // AI Health Banner
            aiHealthScore: document.getElementById('ai-overall-score'),
            aiHealthStatus: document.getElementById('ai-health-status'),
            viewDetailsBtn: document.getElementById('view-ai-details'),
            
            // Insights Carousel
            insightsCarousel: document.getElementById('ai-insights-carousel'),
            insightsCountBadge: document.getElementById('insights-count-badge'),
            
            // Disease Risk
            diseaseRiskMeter: document.getElementById('disease-risk-meter'),
            diseaseRiskLevel: document.getElementById('disease-risk-level'),
            diseaseRiskScore: document.getElementById('disease-risk-score'),
            diseaseRiskDetails: document.getElementById('disease-risk-details'),
            
            // Growth Stage
            currentStageLabel: document.getElementById('current-stage-label'),
            daysInStage: document.getElementById('days-in-stage'),
            nextStageEstimate: document.getElementById('next-stage-estimate'),
            
            // Harvest Forecast
            harvestDaysRemaining: document.getElementById('harvest-days-remaining'),
            estimatedHarvestDate: document.getElementById('estimated-harvest-date'),
            harvestConfidence: document.getElementById('harvest-confidence'),
            
            // Optimization
            optimizationRingProgress: document.getElementById('optimization-ring-progress'),
            optimizationScoreValue: document.getElementById('optimization-score-value'),
            optimizationStatus: document.getElementById('optimization-status'),
            optimizationActions: document.getElementById('optimization-quick-actions'),
            
            // Recommendations
            successList: document.getElementById('success-list'),
            attentionList: document.getElementById('attention-list'),
            learningStats: document.getElementById('learning-stats'),
            
            // Forecast
            forecastTimeline: document.getElementById('forecast-timeline'),
            
            // Community
            communitySection: document.getElementById('community-insights-section'),
            similarGrowersGrid: document.getElementById('similar-growers-grid')
        };
        
        this.init();
    }
    
    init() {
        console.log('🤖 Initializing AI Insights Manager...');
        
        // Get selected unit
        const pageShell = document.querySelector('.page-shell');
        if (pageShell) {
            const unitId = pageShell.dataset.selectedUnitId;
            this.selectedUnitId = unitId && unitId !== '' ? parseInt(unitId) : null;
        }
        
        // Load initial data
        if (this.selectedUnitId) {
            this.loadAllInsights();
        } else {
            this.showNoUnitSelected();
        }
        
        // Setup event listeners
        this.setupEventListeners();
        
        // Setup Socket.IO listeners for real-time updates
        this.setupSocketListeners();
        
        // Start periodic refresh (every 5 minutes)
        this.startPeriodicRefresh();
        
        console.log('✅ AI Insights Manager initialized');
    }
    
    /**
     * Load all AI insights
     */
    async loadAllInsights() {
        if (!this.selectedUnitId) return;
        
        try {
            await Promise.all([
                this.loadInsightsCarousel(),
                this.loadDiseaseRisk(),
                this.loadGrowthProgress(),
                this.loadHarvestForecast(),
                this.loadOptimizationScore(),
                this.loadPersonalizedRecommendations(),
                this.loadForecast(),
                this.loadSimilarGrowers()
            ]);
        } catch (error) {
            console.error('❌ Error loading AI insights:', error);
        }
    }
    
    /**
     * Load insights carousel (from continuous monitoring)
     */
    async loadInsightsCarousel() {
        try {
            const result = await API.AI.getInsights(this.selectedUnitId, 5);
            const insights = result?.insights || [];
            this.renderInsights(insights);
            this.updateInsightsCount(insights.length);
            
        } catch (error) {
            console.error('Error loading insights:', error);
            this.showInsightsError();
        }
    }
    
    /**
     * Render insights carousel
     */
    renderInsights(insights) {
        if (!this.elements.insightsCarousel) return;
        
        if (insights.length === 0) {
            this.elements.insightsCarousel.innerHTML = `
                <div class="insight-card info">
                    <div class="insight-header">
                        <span class="insight-icon">✨</span>
                        <div>
                            <h4 class="insight-title">All Clear!</h4>
                        </div>
                    </div>
                    <p class="insight-message">
                        Your growing conditions look great. AI is continuously monitoring for any changes.
                    </p>
                </div>
            `;
            return;
        }
        
        const html = insights.map(insight => this.createInsightCard(insight)).join('');
        this.elements.insightsCarousel.innerHTML = html;
    }
    
    /**
     * Create insight card HTML
     */
    createInsightCard(insight) {
        const alertClass = insight.alert_level || 'info';
        const icon = this.getInsightIcon(insight.insight_type, alertClass);
        const time = this.formatTimeAgo(new Date(insight.timestamp));
        
        return `
            <div class="insight-card ${alertClass}">
                <div class="insight-header">
                    <span class="insight-icon">${icon}</span>
                    <div>
                        <h4 class="insight-title">${this.escapeHtml(insight.title)}</h4>
                        <span class="insight-time">${time}</span>
                    </div>
                </div>
                <p class="insight-message">${this.escapeHtml(insight.description)}</p>
                ${insight.action_items && insight.action_items.length > 0 ? `
                    <ul class="insight-actions">
                        ${insight.action_items.slice(0, 3).map(action => 
                            `<li><i class="fas fa-check-circle"></i> ${this.escapeHtml(action)}</li>`
                        ).join('')}
                    </ul>
                ` : ''}
            </div>
        `;
    }
    
    /**
     * Load disease risk prediction
     */
    async loadDiseaseRisk() {
        try {
            const result = await API.AI.getDiseaseRisk(this.selectedUnitId);
            const risks = result?.risks || [];
            
            // Get highest risk
            const highestRisk = risks.length > 0 ? 
                risks.reduce((max, risk) => risk.risk_score > max.risk_score ? risk : max) : 
                null;
            
            this.renderDiseaseRisk(highestRisk);
            
        } catch (error) {
            console.error('Error loading disease risk:', error);
            this.showDiseaseRiskError();
        }
    }
    
    /**
     * Render disease risk
     */
    renderDiseaseRisk(risk) {
        if (!risk) {
            // Low risk default
            this.updateRiskMeter(5, 'Low', '5%');
            if (this.elements.diseaseRiskDetails) {
                this.elements.diseaseRiskDetails.innerHTML = '<p class="muted">No significant disease risks detected</p>';
            }
            return;
        }
        
        this.updateRiskMeter(risk.risk_score, risk.risk_level, risk.risk_score);
        
        if (this.elements.diseaseRiskDetails) {
            const topFactors = risk.contributing_factors?.slice(0, 2) || [];
            const html = `
                <div>
                    <strong>${this.escapeHtml(risk.disease_type.replace('_', ' '))}</strong>
                    ${topFactors.length > 0 ? `
                        <ul style="margin: 0.5rem 0 0 0; padding-left: 1.5rem; font-size: 0.875rem;">
                            ${topFactors.map(f => `<li>${this.escapeHtml(f.factor)}: ${this.escapeHtml(f.impact)}</li>`).join('')}
                        </ul>
                    ` : ''}
                </div>
            `;
            this.elements.diseaseRiskDetails.innerHTML = html;
        }
    }
    
    /**
     * Update risk meter display
     */
    updateRiskMeter(score, level, displayScore) {
        const meterFill = this.elements.diseaseRiskMeter?.querySelector('.risk-meter-fill');
        if (meterFill) {
            meterFill.style.width = `${score}%`;
        }
        
        if (this.elements.diseaseRiskLevel) {
            this.elements.diseaseRiskLevel.textContent = level;
            this.elements.diseaseRiskLevel.className = `risk-level ${level.toLowerCase()}`;
        }
        
        if (this.elements.diseaseRiskScore) {
            this.elements.diseaseRiskScore.textContent = `${Math.round(displayScore)}%`;
        }
    }
    
    /**
     * Load growth progress
     */
    async loadGrowthProgress() {
        try {
            const result = await API.AI.getGrowthProgress(this.selectedUnitId);
            const progress = result || {};
            this.renderGrowthProgress(progress);
            
        } catch (error) {
            console.error('Error loading growth progress:', error);
            this.showGrowthProgressError();
        }
    }
    
    /**
     * Render growth progress
     */
    renderGrowthProgress(progress) {
        if (this.elements.currentStageLabel) {
            this.elements.currentStageLabel.textContent = progress.current_stage || 'Unknown';
        }
        
        if (this.elements.daysInStage) {
            const days = progress.days_in_stage || 0;
            this.elements.daysInStage.textContent = `Day ${days}`;
        }
        
        if (this.elements.nextStageEstimate) {
            if (progress.ready_for_next_stage) {
                this.elements.nextStageEstimate.textContent = `Ready for ${progress.next_stage}!`;
            } else {
                const daysRemaining = progress.estimated_days_to_next_stage || 'unknown';
                this.elements.nextStageEstimate.textContent = `~${daysRemaining} days to ${progress.next_stage}`;
            }
        }
        
        // Update stage timeline visualization
        this.updateStageTimeline(progress);
    }
    
    /**
     * Update stage timeline visualization
     */
    updateStageTimeline(progress) {
        const stageOrder = ['Germination', 'Seedling', 'Vegetative', 'Flowering', 'Fruiting', 'Harvest'];
        const currentIndex = stageOrder.indexOf(progress.current_stage);
        
        // Update markers and labels
        const markers = document.querySelectorAll('.stage-marker');
        const labels = document.querySelectorAll('.stage-label');
        
        if (currentIndex >= 0 && markers.length >= 3 && labels.length >= 3) {
            // Show previous, current, and next stages
            const prevStage = currentIndex > 0 ? stageOrder[currentIndex - 1] : stageOrder[0];
            const currentStage = stageOrder[currentIndex];
            const nextStage = currentIndex < stageOrder.length - 1 ? stageOrder[currentIndex + 1] : stageOrder[currentIndex];
            
            labels[0].textContent = prevStage;
            labels[1].textContent = currentStage;
            labels[2].textContent = nextStage;
        }
    }
    
    /**
     * Load harvest forecast
     */
    async loadHarvestForecast() {
        try {
            const result = await API.AI.getHarvestForecast(this.selectedUnitId);
            const forecast = result || {};
            this.renderHarvestForecast(forecast);
            
        } catch (error) {
            console.error('Error loading harvest forecast:', error);
            this.showHarvestForecastError();
        }
    }
    
    /**
     * Render harvest forecast
     */
    renderHarvestForecast(forecast) {
        if (this.elements.harvestDaysRemaining) {
            const days = forecast.days_remaining || 0;
            const numberEl = this.elements.harvestDaysRemaining.querySelector('.countdown-number');
            if (numberEl) {
                numberEl.textContent = days;
            }
        }
        
        if (this.elements.estimatedHarvestDate) {
            if (forecast.estimated_date) {
                const date = new Date(forecast.estimated_date);
                this.elements.estimatedHarvestDate.textContent = date.toLocaleDateString('en-US', {
                    month: 'short',
                    day: 'numeric',
                    year: 'numeric'
                });
            } else {
                this.elements.estimatedHarvestDate.textContent = 'Calculating...';
            }
        }
        
        if (this.elements.harvestConfidence) {
            const confidence = Math.round((forecast.confidence || 0) * 100);
            this.elements.harvestConfidence.innerHTML = `
                <i class="fas fa-chart-line"></i> ${confidence}% confidence
            `;
        }
    }
    
    /**
     * Load optimization score
     */
    async loadOptimizationScore() {
        try {
            const result = await API.AI.getOptimization(this.selectedUnitId);
            const optimization = result || {};
            this.renderOptimization(optimization);
            
        } catch (error) {
            console.error('Error loading optimization:', error);
            this.showOptimizationError();
        }
    }
    
    /**
     * Render optimization score
     */
    renderOptimization(optimization) {
        const score = optimization.score || 0;
        
        // Update ring progress
        if (this.elements.optimizationRingProgress) {
            const circumference = 2 * Math.PI * 45; // radius = 45
            const offset = circumference - (score / 100) * circumference;
            this.elements.optimizationRingProgress.style.strokeDashoffset = offset;
        }
        
        // Update score value
        if (this.elements.optimizationScoreValue) {
            this.elements.optimizationScoreValue.textContent = Math.round(score);
        }
        
        // Update status
        if (this.elements.optimizationStatus) {
            let status = 'Needs Improvement';
            if (score >= 90) status = 'Excellent';
            else if (score >= 75) status = 'Good';
            else if (score >= 60) status = 'Fair';
            
            this.elements.optimizationStatus.textContent = status;
        }
        
        // Update quick actions
        if (this.elements.optimizationActions && optimization.quick_actions) {
            const esc = window.escapeHtmlAttr || this.escapeHtml;
            const html = optimization.quick_actions.slice(0, 3).map(action => `
                <a href="#" class="quick-action-btn" data-action="${esc(action.type)}">
                    <span>${this.escapeHtml(action.label)}</span>
                    <i class="fas fa-arrow-right"></i>
                </a>
            `).join('');
            this.elements.optimizationActions.innerHTML = html;
        }
    }
    
    /**
     * Load personalized recommendations
     */
    async loadPersonalizedRecommendations() {
        try {
            const result = await API.AI.getRecommendations(this.selectedUnitId);
            const recommendations = result || {};
            this.renderRecommendations(recommendations);
            
        } catch (error) {
            console.error('Error loading recommendations:', error);
            this.showRecommendationsError();
        }
    }
    
    /**
     * Render personalized recommendations
     */
    renderRecommendations(recommendations) {
        // Success patterns
        if (this.elements.successList) {
            const successes = recommendations.success_factors || [];
            if (successes.length > 0) {
                this.elements.successList.innerHTML = successes.map(s => 
                    `<li>${this.escapeHtml(s)}</li>`
                ).join('');
            } else {
                this.elements.successList.innerHTML = '<li>Building success profile...</li>';
            }
        }
        
        // Attention areas
        if (this.elements.attentionList) {
            const attention = recommendations.attention_areas || [];
            if (attention.length > 0) {
                this.elements.attentionList.innerHTML = attention.map(a => 
                    `<li>${this.escapeHtml(a)}</li>`
                ).join('');
            } else {
                this.elements.attentionList.innerHTML = '<li>No issues detected</li>';
            }
        }
        
        // Learning stats
        if (this.elements.learningStats) {
            const stats = recommendations.learning_stats || {};
            const html = `
                <div class="learning-stat">
                    <span class="learning-stat-label">Grow Cycles Analyzed</span>
                    <span class="learning-stat-value">${stats.cycles_analyzed || 0}</span>
                </div>
                <div class="learning-stat">
                    <span class="learning-stat-label">Success Rate</span>
                    <span class="learning-stat-value">${stats.success_rate || 0}%</span>
                </div>
                <div class="learning-stat">
                    <span class="learning-stat-label">Environment Profile</span>
                    <span class="learning-stat-value">${stats.profile_completeness || 0}%</span>
                </div>
            `;
            this.elements.learningStats.innerHTML = html;
        }
    }
    
    /**
     * Load 7-day forecast
     */
    async loadForecast() {
        try {
            const result = await API.AI.getForecast(this.selectedUnitId, 7);
            const forecast = result?.forecast || [];
            this.renderForecast(forecast);
            
        } catch (error) {
            console.error('Error loading forecast:', error);
            this.showForecastError();
        }
    }
    
    /**
     * Render 7-day forecast
     */
    renderForecast(forecast) {
        if (!this.elements.forecastTimeline) return;
        
        if (forecast.length === 0) {
            this.elements.forecastTimeline.innerHTML = `
                <div class="forecast-loading">
                    <p>Forecast not available yet</p>
                </div>
            `;
            return;
        }
        
        const html = forecast.map(day => this.createForecastDay(day)).join('');
        this.elements.forecastTimeline.innerHTML = html;
    }
    
    /**
     * Create forecast day card
     */
    createForecastDay(day) {
        const date = new Date(day.date);
        const dayName = date.toLocaleDateString('en-US', { weekday: 'short' });
        const dateStr = date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
        
        const hasAlert = day.predicted_issues && day.predicted_issues.length > 0;
        
        return `
            <div class="forecast-day">
                <div class="forecast-day-header">
                    <div class="forecast-day-name">${dayName}</div>
                    <div class="forecast-day-date">${dateStr}</div>
                </div>
                <div class="forecast-conditions">
                    <div class="forecast-metric">
                        <span>🌡️ Temp</span>
                        <span class="forecast-metric-value">${Math.round(day.temperature)}°C</span>
                    </div>
                    <div class="forecast-metric">
                        <span>💧 Humidity</span>
                        <span class="forecast-metric-value">${Math.round(day.humidity)}%</span>
                    </div>
                    <div class="forecast-metric">
                        <span>🌱 Moisture</span>
                        <span class="forecast-metric-value">${Math.round(day.soil_moisture)}%</span>
                    </div>
                </div>
                ${hasAlert ? `
                    <div class="forecast-alert">
                        ⚠️ ${this.escapeHtml(day.predicted_issues[0].issue)}
                    </div>
                ` : ''}
            </div>
        `;
    }
    
    /**
     * Load similar growers (community insights)
     */
    async loadSimilarGrowers() {
        try {
            const result = await API.AI.getSimilarGrowers(this.selectedUnitId, 3);
            const growers = result?.similar_growers || [];
            
            if (growers.length > 0) {
                this.renderSimilarGrowers(growers);
                if (this.elements.communitySection) {
                    this.elements.communitySection.style.display = 'block';
                }
            } else {
                if (this.elements.communitySection) {
                    this.elements.communitySection.style.display = 'none';
                }
            }
            
        } catch (error) {
            console.error('Error loading similar growers:', error);
            if (this.elements.communitySection) {
                this.elements.communitySection.style.display = 'none';
            }
        }
    }
    
    /**
     * Render similar growers
     */
    renderSimilarGrowers(growers) {
        if (!this.elements.similarGrowersGrid) return;
        
        const html = growers.map(grower => this.createSimilarGrowerCard(grower)).join('');
        this.elements.similarGrowersGrid.innerHTML = html;
    }
    
    /**
     * Create similar grower card
     */
    createSimilarGrowerCard(grower) {
        const similarity = Math.round(grower.similarity_score * 100);
        const success = grower.success_data;
        
        return `
            <div class="similar-grower-card">
                <div class="similarity-badge">
                    <i class="fas fa-users"></i>
                    ${similarity}% similar setup
                </div>
                <div class="grower-info">
                    <div class="grower-plant">${this.escapeHtml(success.plant_type)}</div>
                    <div class="grower-stats">
                        <div class="grower-stat">
                            <span>Quality</span>
                            <span>${'⭐'.repeat(success.quality_rating)}</span>
                        </div>
                        <div class="grower-stat">
                            <span>Days to harvest</span>
                            <span>${success.days_to_harvest}</span>
                        </div>
                    </div>
                </div>
                <div class="key-tips">
                    <h5>Key Tips:</h5>
                    <ul>
                        ${grower.key_conditions ? Object.entries(grower.key_conditions)
                            .slice(0, 3)
                            .map(([key, value]) => `<li>${this.escapeHtml(key)}: ${this.escapeHtml(String(value))}</li>`)
                            .join('') : '<li>No specific tips available</li>'}
                    </ul>
                </div>
            </div>
        `;
    }
    
    /**
     * Setup event listeners
     */
    setupEventListeners() {
        // View details button
        if (this.elements.viewDetailsBtn) {
            this.elements.viewDetailsBtn.addEventListener('click', () => {
                this.showAIDetailsModal();
            });
        }
        
        // Prediction card action buttons
        document.addEventListener('click', (e) => {
            const actionBtn = e.target.closest('[data-action]');
            if (actionBtn) {
                e.preventDefault();
                this.handleActionClick(actionBtn.dataset.action);
            }
        });
    }
    
    /**
     * Setup Socket.IO listeners for real-time updates
     */
    setupSocketListeners() {
        // Listen for new insights
        this.socket.on('ai_insight_created', (data) => {
            console.log('🤖 New AI insight received:', data);
            this.loadInsightsCarousel();
        });
        
        // Listen for risk updates
        this.socket.on('disease_risk_update', (data) => {
            console.log('🦠 Disease risk updated:', data);
            this.loadDiseaseRisk();
        });
        
        // Listen for growth stage changes
        this.socket.on('growth_stage_changed', (data) => {
            console.log('🌱 Growth stage changed:', data);
            this.loadGrowthProgress();
            this.showNotification(`Plant entered ${data.new_stage} stage!`, 'success');
        });
    }
    
    /**
     * Handle action button clicks
     */
    handleActionClick(action) {
        switch (action) {
            case 'view-disease-details':
                window.location.href = `/analytics/disease-risk?unit=${this.selectedUnitId}`;
                break;
            case 'view-growth-details':
                window.location.href = `/analytics/growth-tracking?unit=${this.selectedUnitId}`;
                break;
            case 'view-harvest-details':
                window.location.href = `/analytics/harvest-forecast?unit=${this.selectedUnitId}`;
                break;
            case 'view-optimization-details':
                window.location.href = `/analytics/optimization?unit=${this.selectedUnitId}`;
                break;
            default:
                console.log('Unknown action:', action);
        }
    }
    
    /**
     * Show AI details modal
     */
    showAIDetailsModal() {
        // Implementation depends on your modal system
        console.log('Show AI details modal');
        // Could navigate to dedicated AI insights page or show modal
        window.location.href = `/analytics/ai-insights?unit=${this.selectedUnitId}`;
    }
    
    /**
     * Start periodic refresh
     */
    startPeriodicRefresh() {
        // Refresh AI insights every 5 minutes
        this.refreshInterval = setInterval(() => {
            if (this.selectedUnitId) {
                this.loadAllInsights();
            }
        }, 5 * 60 * 1000);
    }
    
    /**
     * Update insights count badge
     */
    updateInsightsCount(count) {
        if (this.elements.insightsCountBadge) {
            this.elements.insightsCountBadge.textContent = count > 0 ? `${count} new` : 'All clear';
            this.elements.insightsCountBadge.className = count > 0 ? 'pill pill-warning' : 'pill pill-success';
        }
    }
    
    /**
     * Error handlers
     */
    showInsightsError() {
        if (this.elements.insightsCarousel) {
            this.elements.insightsCarousel.innerHTML = `
                <div class="insight-card warning">
                    <p>Unable to load insights. Please refresh the page.</p>
                </div>
            `;
        }
    }
    
    showDiseaseRiskError() {
        if (this.elements.diseaseRiskDetails) {
            this.elements.diseaseRiskDetails.innerHTML = '<p class="muted">Unable to load risk data</p>';
        }
    }
    
    showGrowthProgressError() {
        if (this.elements.daysInStage) {
            this.elements.daysInStage.textContent = '--';
        }
        if (this.elements.nextStageEstimate) {
            this.elements.nextStageEstimate.textContent = 'Unable to calculate';
        }
    }
    
    showHarvestForecastError() {
        if (this.elements.estimatedHarvestDate) {
            this.elements.estimatedHarvestDate.textContent = 'Unable to forecast';
        }
    }
    
    showOptimizationError() {
        if (this.elements.optimizationStatus) {
            this.elements.optimizationStatus.textContent = 'Unable to calculate';
        }
    }
    
    showRecommendationsError() {
        if (this.elements.successList) {
            this.elements.successList.innerHTML = '<li>Unable to load recommendations</li>';
        }
    }
    
    showForecastError() {
        if (this.elements.forecastTimeline) {
            this.elements.forecastTimeline.innerHTML = `
                <div class="forecast-loading">
                    <p>Unable to load forecast</p>
                </div>
            `;
        }
    }
    
    showNoUnitSelected() {
        // Show message that unit needs to be selected
        console.log('No unit selected for AI insights');
    }
    
    /**
     * Utility: Get icon for insight type
     */
    getInsightIcon(type, alertLevel) {
        const icons = {
            temperature: '🌡️',
            humidity: '💧',
            light: '💡',
            soil_moisture: '🌱',
            disease: '🦠',
            pest: '🐛',
            growth: '📈',
            nutrient: '🧪',
            general: '✨'
        };
        
        if (alertLevel === 'critical' || alertLevel === 'warning') {
            return '⚠️';
        }
        
        return icons[type] || '📊';
    }
    
    /**
     * Utility: Format time ago
     */
    formatTimeAgo(date) {
        const now = new Date();
        const seconds = Math.floor((now - date) / 1000);
        
        if (seconds < 60) return 'Just now';
        if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
        if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
        return `${Math.floor(seconds / 86400)}d ago`;
    }
    
    /**
     * Utility: Escape HTML
     */
    escapeHtml(text) {
        if (window.escapeHtml) return window.escapeHtml(text);
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    /**
     * Show notification
     */
    showNotification(message, type = 'info') {
        // Implementation depends on your notification system
        console.log(`[${type.toUpperCase()}] ${message}`);
    }
    
    /**
     * Cleanup
     */
    destroy() {
        if (this.refreshInterval) {
            clearInterval(this.refreshInterval);
        }
    }
}
        