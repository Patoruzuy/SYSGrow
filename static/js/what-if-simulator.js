/**
 * What-If Simulator Component
 * 
 * Interactive tool for testing parameter changes before applying them.
 * Shows predicted impacts on:
 * - Plant health score
 * - Energy consumption and costs
 * - VPD (Vapor Pressure Deficit)
 * - Growth rate
 * 
 * Uses ML models when available for accurate predictions.
 */

class WhatIfSimulator {
  constructor(containerId, options = {}) {
    this.containerId = containerId;
    this.container = document.getElementById(containerId);
    
    if (!this.container) {
      console.error(`Container with id "${containerId}" not found`);
      return;
    }
    
    this.options = {
      enableMLPredictions: options.enableMLPredictions !== false,
      showCostImpact: options.showCostImpact !== false,
      ...options
    };
    
    this.unitId = null;
    this.currentConditions = null;
    this.simulatedConditions = null;
    this.predictions = null;
    this.mlAvailable = false;
    
    // Parameter ranges
    this.ranges = {
      temperature: { min: 15, max: 35, step: 0.5, unit: '°C' },
      humidity: { min: 30, max: 90, step: 1, unit: '%' },
      light_hours: { min: 0, max: 24, step: 0.5, unit: 'hrs' },
      co2: { min: 400, max: 1500, step: 50, unit: 'ppm' }
    };
    
    this.render();
  }
  
  async init(unitId = null) {
    this.unitId = unitId;
    
    // Check ML availability
    await this.checkMLAvailability();
    
    // Load current conditions
    await this.loadCurrentConditions();
    
    // Initialize simulated conditions to current
    this.resetSimulation();
    
    // Update display
    this.updateDisplay();
  }
  
  async checkMLAvailability() {
    try {
      if (window.MLStatus) {
        await window.MLStatus.checkStatus();
        this.mlAvailable = window.MLStatus.isAvailable('climate_optimizer') || 
                          window.MLStatus.isAvailable('yield_predictor');
      } else {
        const data = await API.ML.getModelsStatus();
        this.mlAvailable = data.models?.climate_optimizer?.active || false;
      }
    } catch (error) {
      console.error('Error checking ML availability:', error);
      this.mlAvailable = false;
    }
  }
  
  async loadCurrentConditions() {
    try {
      const result = await API.Analytics.getSensorsOverview(this.unitId);
      
      if (result?.latest) {
        const latest = window.SensorFields ? window.SensorFields.standardize(result.latest) : result.latest;
        this.currentConditions = {
          temperature: latest.temperature || 22,
          humidity: latest.humidity || 60,
          light_hours: 16, // Default, would come from schedule
          co2: latest.co2 || latest.co2_ppm || 400
        };
      } else {
        this.currentConditions = {
          temperature: 22,
          humidity: 60,
          light_hours: 16,
          co2: 400
        };
      }
    } catch (error) {
      console.error('Error loading current conditions:', error);
      this.currentConditions = {
        temperature: 22,
        humidity: 60,
        light_hours: 16,
        co2: 400
      };
    }
  }
  
  render() {
    this.container.innerHTML = `
      <div class="what-if-simulator">
        <div class="simulator-header">
          <h3 class="simulator-title">
            <i class="fas fa-flask"></i>
            What-If Simulator
          </h3>
          <div class="simulator-status">
            <span class="ml-indicator">
              <i class="fas fa-brain"></i>
              <span class="ml-text">Checking ML...</span>
            </span>
          </div>
        </div>
        
        <div class="simulator-body">
          <div class="simulator-description">
            <p>Test parameter changes before applying them. See predicted impacts on plant health, energy costs, and growth.</p>
          </div>
          
          <!-- Parameter Controls -->
          <div class="simulator-controls">
            <h4 class="controls-title">Adjust Parameters</h4>
            
            <!-- Temperature -->
            <div class="control-group">
              <div class="control-header">
                <label for="sim-temperature" class="control-label">
                  <i class="fas fa-thermometer-half text-danger"></i>
                  Temperature
                </label>
                <div class="control-values">
                  <span class="current-value">Current: <strong id="current-temp">--</strong></span>
                  <span class="arrow">→</span>
                  <span class="simulated-value">New: <strong id="sim-temp-value">--</strong></span>
                </div>
              </div>
              <input type="range" id="sim-temperature" class="control-slider" 
                     min="15" max="35" step="0.5" value="22">
            </div>
            
            <!-- Humidity -->
            <div class="control-group">
              <div class="control-header">
                <label for="sim-humidity" class="control-label">
                  <i class="fas fa-tint text-primary"></i>
                  Humidity
                </label>
                <div class="control-values">
                  <span class="current-value">Current: <strong id="current-humidity">--</strong></span>
                  <span class="arrow">→</span>
                  <span class="simulated-value">New: <strong id="sim-humidity-value">--</strong></span>
                </div>
              </div>
              <input type="range" id="sim-humidity" class="control-slider"
                     min="30" max="90" step="1" value="60">
            </div>
            
            <!-- Light Hours -->
            <div class="control-group">
              <div class="control-header">
                <label for="sim-light" class="control-label">
                  <i class="fas fa-sun text-warning"></i>
                  Light Duration
                </label>
                <div class="control-values">
                  <span class="current-value">Current: <strong id="current-light">--</strong></span>
                  <span class="arrow">→</span>
                  <span class="simulated-value">New: <strong id="sim-light-value">--</strong></span>
                </div>
              </div>
              <input type="range" id="sim-light" class="control-slider"
                     min="0" max="24" step="0.5" value="16">
            </div>
            
            <!-- CO2 Level -->
            <div class="control-group">
              <div class="control-header">
                <label for="sim-co2" class="control-label">
                  <i class="fas fa-wind text-success"></i>
                  CO₂ Level
                </label>
                <div class="control-values">
                  <span class="current-value">Current: <strong id="current-co2">--</strong></span>
                  <span class="arrow">→</span>
                  <span class="simulated-value">New: <strong id="sim-co2-value">--</strong></span>
                </div>
              </div>
              <input type="range" id="sim-co2" class="control-slider"
                     min="400" max="1500" step="50" value="400">
            </div>
          </div>
          
          <!-- Predicted Impact -->
          <div class="simulator-results">
            <h4 class="results-title">
              <i class="fas fa-chart-line"></i>
              Predicted Impact
            </h4>
            
            <div class="results-grid">
              <!-- VPD -->
              <div class="result-card">
                <div class="result-icon vpd-icon">
                  <i class="fas fa-cloud"></i>
                </div>
                <div class="result-content">
                  <div class="result-label">VPD (Vapor Pressure Deficit)</div>
                  <div class="result-value">
                    <span id="vpd-current">--</span>
                    <span class="result-arrow">→</span>
                    <span id="vpd-predicted" class="predicted">--</span>
                  </div>
                  <div class="result-status" id="vpd-status">Calculating...</div>
                </div>
              </div>
              
              <!-- Plant Health -->
              <div class="result-card">
                <div class="result-icon health-icon">
                  <i class="fas fa-heart"></i>
                </div>
                <div class="result-content">
                  <div class="result-label">Plant Health Score</div>
                  <div class="result-value">
                    <span id="health-current">--</span>
                    <span class="result-arrow">→</span>
                    <span id="health-predicted" class="predicted">--</span>
                  </div>
                  <div class="result-change" id="health-change">--</div>
                </div>
              </div>
              
              <!-- Energy Cost -->
              <div class="result-card">
                <div class="result-icon energy-icon">
                  <i class="fas fa-bolt"></i>
                </div>
                <div class="result-content">
                  <div class="result-label">Energy Cost Impact</div>
                  <div class="result-value">
                    <span id="cost-current">--</span>
                    <span class="result-arrow">→</span>
                    <span id="cost-predicted" class="predicted">--</span>
                  </div>
                  <div class="result-change" id="cost-change">--</div>
                </div>
              </div>
              
              <!-- Growth Rate -->
              <div class="result-card">
                <div class="result-icon growth-icon">
                  <i class="fas fa-seedling"></i>
                </div>
                <div class="result-content">
                  <div class="result-label">Growth Rate</div>
                  <div class="result-value">
                    <span id="growth-current">--</span>
                    <span class="result-arrow">→</span>
                    <span id="growth-predicted" class="predicted">--</span>
                  </div>
                  <div class="result-change" id="growth-change">--</div>
                </div>
              </div>
            </div>
            
            <!-- Recommendations -->
            <div class="simulator-recommendations">
              <h5 class="recommendations-title">
                <i class="fas fa-lightbulb"></i>
                AI Recommendations
              </h5>
              <div class="recommendations-list" id="recommendations-list">
                <div class="text-muted">Adjust parameters to see recommendations</div>
              </div>
            </div>
          </div>
          
          <!-- Action Buttons -->
          <div class="simulator-actions">
            <button class="btn btn-outline simulator-reset" id="simulator-reset">
              <i class="fas fa-undo"></i>
              Reset
            </button>
            <button class="btn btn-primary simulator-apply" id="simulator-apply">
              <i class="fas fa-check"></i>
              Apply Changes
            </button>
          </div>
        </div>
      </div>
    `;
    
    // Bind events
    this.bindEvents();
  }
  
  bindEvents() {
    // Slider inputs
    const sliders = ['temperature', 'humidity', 'light', 'co2'];
    sliders.forEach(param => {
      const slider = document.getElementById(`sim-${param}`);
      if (slider) {
        slider.addEventListener('input', (e) => this.onParameterChange(param, e.target.value));
      }
    });
    
    // Reset button
    const resetBtn = document.getElementById('simulator-reset');
    if (resetBtn) {
      resetBtn.addEventListener('click', () => this.resetSimulation());
    }
    
    // Apply button
    const applyBtn = document.getElementById('simulator-apply');
    if (applyBtn) {
      applyBtn.addEventListener('click', () => this.applyChanges());
    }
  }
  
  onParameterChange(param, value) {
    const numValue = parseFloat(value);
    
    // Map parameter names
    const paramMap = {
      'temperature': 'temperature',
      'humidity': 'humidity',
      'light': 'light_hours',
      'co2': 'co2'
    };
    
    const actualParam = paramMap[param];
    this.simulatedConditions[actualParam] = numValue;
    
    // Update display value
    const valueElement = document.getElementById(`sim-${param}-value`);
    if (valueElement) {
      const range = this.ranges[actualParam];
      valueElement.textContent = `${numValue}${range.unit}`;
    }
    
    // Recalculate predictions
    this.calculatePredictions();
  }
  
  resetSimulation() {
    this.simulatedConditions = { ...this.currentConditions };
    
    // Reset sliders
    document.getElementById('sim-temperature').value = this.currentConditions.temperature;
    document.getElementById('sim-humidity').value = this.currentConditions.humidity;
    document.getElementById('sim-light').value = this.currentConditions.light_hours;
    document.getElementById('sim-co2').value = this.currentConditions.co2;
    
    // Update display
    this.updateDisplay();
    this.calculatePredictions();
  }
  
  updateDisplay() {
    if (!this.currentConditions) return;
    
    // Update current values
    document.getElementById('current-temp').textContent = `${this.currentConditions.temperature}°C`;
    document.getElementById('current-humidity').textContent = `${this.currentConditions.humidity}%`;
    document.getElementById('current-light').textContent = `${this.currentConditions.light_hours}hrs`;
    document.getElementById('current-co2').textContent = `${this.currentConditions.co2}ppm`;
    
    // Update simulated values
    document.getElementById('sim-temp-value').textContent = `${this.simulatedConditions.temperature}°C`;
    document.getElementById('sim-humidity-value').textContent = `${this.simulatedConditions.humidity}%`;
    document.getElementById('sim-light-value').textContent = `${this.simulatedConditions.light_hours}hrs`;
    document.getElementById('sim-co2-value').textContent = `${this.simulatedConditions.co2}ppm`;
    
    // Update ML indicator
    const mlIndicator = this.container.querySelector('.ml-indicator');
    const mlText = this.container.querySelector('.ml-text');
    if (mlIndicator && mlText) {
      if (this.mlAvailable) {
        mlIndicator.classList.add('ml-active');
        mlText.textContent = 'ML Predictions Active';
      } else {
        mlIndicator.classList.remove('ml-active');
        mlText.textContent = 'Statistical Estimates';
      }
    }
  }
  
  async calculatePredictions() {
    try {
      // Calculate VPD
      const currentVPD = this.calculateVPD(this.currentConditions.temperature, this.currentConditions.humidity);
      const predictedVPD = this.calculateVPD(this.simulatedConditions.temperature, this.simulatedConditions.humidity);
      
      document.getElementById('vpd-current').textContent = currentVPD.toFixed(2);
      document.getElementById('vpd-predicted').textContent = predictedVPD.toFixed(2);
      
      // VPD status
      const vpdStatus = this.getVPDStatus(predictedVPD);
      const vpdStatusElement = document.getElementById('vpd-status');
      vpdStatusElement.textContent = vpdStatus.text;
      vpdStatusElement.className = `result-status ${vpdStatus.class}`;
      
      // If ML is available, get predictions from API
      if (this.mlAvailable) {
        await this.getMLPredictions();
      } else {
        this.calculateStatisticalPredictions();
      }
      
      // Generate recommendations
      this.generateRecommendations();
      
    } catch (error) {
      console.error('Error calculating predictions:', error);
    }
  }
  
  async getMLPredictions() {
    try {
      const result = await API.ML.whatIfSimulation({
        unit_id: this.unitId,
        current: this.currentConditions,
        simulated: this.simulatedConditions
      });
      
      if (result) {
        this.predictions = result;
        this.updatePredictionDisplay();
      } else {
        this.calculateStatisticalPredictions();
      }
    } catch (error) {
      console.error('Error getting ML predictions:', error);
      this.calculateStatisticalPredictions();
    }
  }
  
  calculateStatisticalPredictions() {
    // Simple heuristic-based predictions
    const tempDelta = this.simulatedConditions.temperature - this.currentConditions.temperature;
    const humidityDelta = this.simulatedConditions.humidity - this.currentConditions.humidity;
    const lightDelta = this.simulatedConditions.light_hours - this.currentConditions.light_hours;
    const co2Delta = this.simulatedConditions.co2 - this.currentConditions.co2;
    
    // Health score impact (baseline 75)
    let healthChange = 0;
    const vpd = this.calculateVPD(this.simulatedConditions.temperature, this.simulatedConditions.humidity);
    if (vpd >= 0.8 && vpd <= 1.2) healthChange += 10; // Optimal VPD
    else if (vpd < 0.5 || vpd > 1.5) healthChange -= 10; // Poor VPD
    
    if (this.simulatedConditions.light_hours >= 14 && this.simulatedConditions.light_hours <= 18) healthChange += 5;
    if (this.simulatedConditions.co2 >= 800 && this.simulatedConditions.co2 <= 1200) healthChange += 5;
    
    // Energy cost impact (baseline $2/day)
    const baselineCost = 2.0;
    let costChange = 0;
    costChange += Math.abs(tempDelta) * 0.15; // Heating/cooling
    costChange += lightDelta * 0.10; // Lighting
    costChange += (co2Delta / 100) * 0.05; // CO2 injection
    
    // Growth rate impact (baseline 100%)
    let growthChange = 0;
    growthChange += tempDelta * 2; // Temperature effect
    growthChange += lightDelta * 3; // Light effect
    growthChange += (co2Delta / 100) * 2; // CO2 effect
    
    this.predictions = {
      health: {
        current: 75,
        predicted: Math.max(0, Math.min(100, 75 + healthChange)),
        change: healthChange
      },
      cost: {
        current: baselineCost,
        predicted: baselineCost + costChange,
        change: costChange
      },
      growth: {
        current: 100,
        predicted: Math.max(0, 100 + growthChange),
        change: growthChange
      }
    };
    
    this.updatePredictionDisplay();
  }
  
  updatePredictionDisplay() {
    if (!this.predictions) return;
    
    // Health
    document.getElementById('health-current').textContent = Math.round(this.predictions.health.current);
    document.getElementById('health-predicted').textContent = Math.round(this.predictions.health.predicted);
    const healthChange = this.predictions.health.change;
    document.getElementById('health-change').textContent = this.formatChange(healthChange, 'points');
    document.getElementById('health-change').className = `result-change ${this.getChangeClass(healthChange)}`;
    
    // Cost
    document.getElementById('cost-current').textContent = `$${this.predictions.cost.current.toFixed(2)}`;
    document.getElementById('cost-predicted').textContent = `$${this.predictions.cost.predicted.toFixed(2)}`;
    const costChange = this.predictions.cost.change;
    document.getElementById('cost-change').textContent = this.formatChange(costChange, '$/day', true);
    document.getElementById('cost-change').className = `result-change ${this.getChangeClass(-costChange)}`; // Negative cost increase is bad
    
    // Growth
    document.getElementById('growth-current').textContent = `${Math.round(this.predictions.growth.current)}%`;
    document.getElementById('growth-predicted').textContent = `${Math.round(this.predictions.growth.predicted)}%`;
    const growthChange = this.predictions.growth.change;
    document.getElementById('growth-change').textContent = this.formatChange(growthChange, '%');
    document.getElementById('growth-change').className = `result-change ${this.getChangeClass(growthChange)}`;
  }
  
  calculateVPD(temperature, humidity) {
    // VPD = (1 - RH/100) * SVP
    // Where SVP (Saturation Vapor Pressure) = 0.6108 * exp((17.27 * T) / (T + 237.3))
    const svp = 0.6108 * Math.exp((17.27 * temperature) / (temperature + 237.3));
    const vpd = (1 - humidity / 100) * svp;
    return vpd;
  }
  
  getVPDStatus(vpd) {
    if (vpd < 0.4) return { text: 'Too low - Risk of mold', class: 'status-danger' };
    if (vpd < 0.8) return { text: 'Low - Acceptable', class: 'status-warning' };
    if (vpd <= 1.2) return { text: 'Optimal range', class: 'status-success' };
    if (vpd <= 1.5) return { text: 'High - Monitor closely', class: 'status-warning' };
    return { text: 'Too high - Stress risk', class: 'status-danger' };
  }
  
  formatChange(value, unit, absolute = false) {
    const sign = value > 0 ? '+' : '';
    const absValue = absolute ? Math.abs(value) : value;
    return `${sign}${absValue.toFixed(value % 1 === 0 ? 0 : 1)}${unit}`;
  }
  
  getChangeClass(value) {
    if (value > 0) return 'positive';
    if (value < 0) return 'negative';
    return 'neutral';
  }
  
  generateRecommendations() {
    const recommendations = [];
    const vpd = this.calculateVPD(this.simulatedConditions.temperature, this.simulatedConditions.humidity);
    
    // VPD recommendations
    if (vpd < 0.8) {
      recommendations.push({
        priority: 'medium',
        text: 'Consider increasing temperature or decreasing humidity to optimize VPD'
      });
    } else if (vpd > 1.2) {
      recommendations.push({
        priority: 'medium',
        text: 'VPD is high. Increase humidity or lower temperature to reduce plant stress'
      });
    } else {
      recommendations.push({
        priority: 'low',
        text: 'VPD is in optimal range for healthy growth'
      });
    }
    
    // Temperature recommendations
    if (this.simulatedConditions.temperature < 18) {
      recommendations.push({
        priority: 'high',
        text: 'Temperature is too low. Most plants prefer 20-28°C'
      });
    } else if (this.simulatedConditions.temperature > 30) {
      recommendations.push({
        priority: 'high',
        text: 'Temperature is too high. Risk of heat stress above 30°C'
      });
    }
    
    // Light recommendations
    if (this.simulatedConditions.light_hours < 12) {
      recommendations.push({
        priority: 'medium',
        text: 'Low light duration may slow growth. Consider 14-18 hours for vegetative stage'
      });
    }
    
    // CO2 recommendations
    if (this.simulatedConditions.co2 > 1200) {
      recommendations.push({
        priority: 'medium',
        text: 'High CO₂ levels only beneficial with intense lighting (>600 PPFD)'
      });
    }
    
    // Cost efficiency
    if (this.predictions && this.predictions.cost.change > 1.0 && this.predictions.health.change < 5) {
      recommendations.push({
        priority: 'high',
        text: 'Cost increase may not justify small health improvement'
      });
    }
    
    this.displayRecommendations(recommendations);
  }
  
  displayRecommendations(recommendations) {
    const container = document.getElementById('recommendations-list');
    if (!container) return;
    
    if (recommendations.length === 0) {
      container.innerHTML = '<div class="text-success"><i class="fas fa-check-circle"></i> No issues detected</div>';
      return;
    }
    
    container.innerHTML = recommendations.map(rec => `
      <div class="recommendation-item priority-${rec.priority}">
        <i class="fas ${this.getPriorityIcon(rec.priority)}"></i>
        <span>${rec.text}</span>
      </div>
    `).join('');
  }
  
  getPriorityIcon(priority) {
    switch (priority) {
      case 'high': return 'fa-exclamation-circle';
      case 'medium': return 'fa-exclamation-triangle';
      case 'low': return 'fa-info-circle';
      default: return 'fa-lightbulb';
    }
  }
  
  async applyChanges() {
    if (!confirm('Apply these parameter changes to your system?')) {
      return;
    }
    
    try {
      const applyBtn = document.getElementById('simulator-apply');
      if (applyBtn) {
        applyBtn.disabled = true;
        applyBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Applying...';
      }
      
      alert('Scheduling is now handled via the Growth API. Use the Growth > Schedules view to apply changes.');
      return;
      
    } catch (error) {
      console.error('Error applying changes:', error);
      alert('Error applying changes. Check console for details.');
    } finally {
      const applyBtn = document.getElementById('simulator-apply');
      if (applyBtn) {
        applyBtn.disabled = false;
        applyBtn.innerHTML = '<i class="fas fa-check"></i> Apply Changes';
      }
    }
  }
  
  destroy() {
    // Cleanup if needed
  }
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
  module.exports = WhatIfSimulator;
}
