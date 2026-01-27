/**
 * Temperature & Humidity Correlation Scatter Plot
 * ===============================================
 * 
 * Visualizes the relationship between temperature and humidity with:
 * - Scatter plot (temp on x-axis, humidity on y-axis)
 * - Points colored by VPD value
 * - Optimal VPD zone overlay
 * - Regression line showing correlation
 * - Correlation coefficient display
 * - Time slider to filter data by date range
 * 
 * Best Practice: Scatter plots are ideal for showing relationships 
 * between two continuous variables and identifying patterns/outliers.
 * 
 * @module TempHumidityCorrelation
 */

class TempHumidityCorrelation {
  constructor(canvasId, options = {}) {
    this.canvasId = canvasId;
    this.canvas = document.getElementById(canvasId);
    
    if (!this.canvas) {
      console.error(`Canvas with id "${canvasId}" not found`);
      return;
    }
    
    this.ctx = this.canvas.getContext('2d');
    this.chart = null;
    this.rawData = [];
    this.filteredData = [];
    
    // Configuration
    this.options = {
      updateInterval: options.updateInterval || 60000, // 1 minute
      maxDataPoints: options.maxDataPoints || 1000,
      defaultDays: options.defaultDays || 7,
      showRegressionLine: options.showRegressionLine !== false,
      showVPDZone: options.showVPDZone !== false,
      enableTimeSlider: options.enableTimeSlider !== false,
      ...options
    };
    
    this.unitId = null;
    this.updateTimer = null;
    this.loading = false;
    
    // VPD Zone boundaries - use shared constants if available
    const zones = window.VPD_ZONES || {};
    this.vpdZones = {
      optimal: { min: zones.OPTIMAL?.min ?? 0.8, max: zones.OPTIMAL?.max ?? 1.2, color: zones.OPTIMAL?.backgroundColor ?? 'rgba(76, 175, 80, 0.1)' },
      vegetative: { min: zones.VEGETATIVE?.min ?? 0.4, max: zones.VEGETATIVE?.max ?? 0.8, color: zones.VEGETATIVE?.backgroundColor ?? 'rgba(139, 195, 74, 0.1)' },
      lateFlower: { min: zones.LATE_FLOWER?.min ?? 1.2, max: zones.LATE_FLOWER?.max ?? 1.6, color: zones.LATE_FLOWER?.backgroundColor ?? 'rgba(255, 193, 7, 0.1)' }
    };
    
    this.init();
  }
  
  /**
   * Initialize the chart
   */
  init() {
    this.createChart();
    this.setupEventListeners();
    
    // Auto-refresh
    if (this.options.updateInterval > 0) {
      this.updateTimer = setInterval(() => this.refresh(), this.options.updateInterval);
    }
  }
  
  /**
   * Create Chart.js scatter plot
   */
  createChart() {
    const config = {
      type: 'scatter',
      data: {
        datasets: []
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          title: {
            display: true,
            text: 'Temperature vs Humidity Correlation',
            font: { size: 16, weight: 'bold' },
            color: '#333'
          },
          legend: {
            display: true,
            position: 'top',
            labels: {
              usePointStyle: true,
              generateLabels: (chart) => this.generateLegendLabels(chart)
            }
          },
          tooltip: {
            enabled: true,
            mode: 'point',
            callbacks: {
              title: (context) => {
                const point = context[0].raw;
                return point.timestamp || '';
              },
              label: (context) => {
                const point = context.raw;
                return [
                  `Temp: ${point.x.toFixed(1)}°C`,
                  `Humidity: ${point.y.toFixed(1)}%`,
                  `VPD: ${point.vpd.toFixed(2)} kPa`
                ];
              }
            }
          },
          annotation: {
            annotations: this.createAnnotations()
          }
        },
        scales: {
          x: {
            type: 'linear',
            position: 'bottom',
            title: {
              display: true,
              text: 'Temperature (°C)',
              font: { size: 14 }
            },
            grid: {
              color: 'rgba(0, 0, 0, 0.05)'
            }
          },
          y: {
            type: 'linear',
            position: 'left',
            title: {
              display: true,
              text: 'Humidity (%)',
              font: { size: 14 }
            },
            min: 0,
            max: 100,
            grid: {
              color: 'rgba(0, 0, 0, 0.05)'
            }
          }
        },
        interaction: {
          mode: 'point',
          intersect: true
        }
      }
    };
    
    this.chart = new Chart(this.ctx, config);
  }
  
  /**
   * Create annotation for optimal VPD zone overlay
   */
  createAnnotations() {
    if (!this.options.showVPDZone) {
      return {};
    }
    
    // Calculate temp/humidity combinations that fall in optimal VPD range
    // For simplicity, we'll show a rectangular approximation
    // Real optimal zone would be curved based on VPD formula
    return {
      optimalZone: {
        type: 'box',
        xMin: 20,
        xMax: 28,
        yMin: 50,
        yMax: 70,
        backgroundColor: this.vpdZones.optimal.color,
        borderColor: 'rgba(76, 175, 80, 0.5)',
        borderWidth: 1,
        label: {
          display: true,
          content: 'Optimal VPD Zone',
          position: 'center',
          color: '#4caf50',
          font: {
            size: 11
          }
        }
      }
    };
  }
  
  /**
   * Setup event listeners
   */
  setupEventListeners() {
    // Listen for unit changes
    document.addEventListener('unitChanged', (e) => {
      this.setUnit(e.detail.unitId);
    });
    
    // Time slider (if enabled)
    if (this.options.enableTimeSlider) {
      const slider = document.getElementById(`${this.canvasId}-time-slider`);
      if (slider) {
        slider.addEventListener('input', (e) => {
          this.filterDataByDays(parseInt(e.target.value));
        });
      }
    }
  }
  
  /**
   * Set unit and load data
   */
  async setUnit(unitId) {
    this.unitId = unitId;
    await this.loadData();
  }
  
  /**
   * Load temperature and humidity history
   */
  async loadData() {
    if (!this.unitId) return;
    
    this.setLoading(true);
    
    try {
      const days = this.options.defaultDays;
      const end = new Date();
      const start = new Date(end.getTime() - days * 24 * 60 * 60 * 1000);

      const result = await API.Analytics.getSensorsHistory({
        unit_id: this.unitId,
        start: start.toISOString(),
        end: end.toISOString(),
        limit: this.options.maxDataPoints
      });

      const chartData = result?.data || result;
      const timestamps = Array.isArray(chartData?.timestamps) ? chartData.timestamps : [];
      const temperatures = Array.isArray(chartData?.temperature) ? chartData.temperature : [];
      const humidities = Array.isArray(chartData?.humidity) ? chartData.humidity : [];

      const series = timestamps.map((timestamp, idx) => ({
        timestamp,
        temperature: temperatures[idx],
        humidity: humidities[idx]
      }));

      if (series.length > 0) {
        this.rawData = this.processData(series);
        this.filteredData = [...this.rawData];
        this.updateChart();
      } else {
        console.error('Failed to load correlation data');
        this.showError('Failed to load data');
      }
    } catch (error) {
      console.error('Error loading correlation data:', error);
      this.showError('Failed to load correlation data');
    } finally {
      this.setLoading(false);
    }
  }
  
  /**
   * Process raw data into scatter plot points
   */
  processData(series) {
    const points = [];
    
    // Group data by timestamp
    const dataByTime = {};
    
    series.forEach(reading => {
      const timestamp = reading.timestamp;
      if (!dataByTime[timestamp]) {
        dataByTime[timestamp] = { timestamp };
      }
      dataByTime[timestamp].temperature = reading.temperature;
      dataByTime[timestamp].humidity = reading.humidity;
    });
    
    // Create scatter points where both temp and humidity exist
    Object.values(dataByTime).forEach(record => {
      if (record.temperature != null && record.humidity != null) {
        const vpd = this.calculateVPD(record.temperature, record.humidity);
        
        points.push({
          x: record.temperature,
          y: record.humidity,
          vpd: vpd,
          timestamp: new Date(record.timestamp).toLocaleString(),
          timestampRaw: new Date(record.timestamp)
        });
      }
    });
    
    return points;
  }
  
  /**
   * Calculate VPD from temperature and humidity
   * VPD = SVP * (1 - RH/100)
   * where SVP = 0.6108 * exp(17.27 * T / (T + 237.3))
   */
  calculateVPD(tempC, humidity) {
    const svp = 0.6108 * Math.exp((17.27 * tempC) / (tempC + 237.3));
    const vpd = svp * (1 - humidity / 100);
    return vpd;
  }
  
  /**
   * Filter data by number of days
   */
  filterDataByDays(days) {
    const cutoffDate = new Date();
    cutoffDate.setDate(cutoffDate.getDate() - days);
    
    this.filteredData = this.rawData.filter(point => 
      point.timestampRaw >= cutoffDate
    );
    
    this.updateChart();
    this.updateTimeSliderLabel(days);
  }
  
  /**
   * Update time slider label
   */
  updateTimeSliderLabel(days) {
    const label = document.getElementById(`${this.canvasId}-time-label`);
    if (label) {
      label.textContent = `Last ${days} day${days !== 1 ? 's' : ''}`;
    }
  }
  
  /**
   * Update chart with current data
   */
  updateChart() {
    if (!this.chart || !this.filteredData.length) return;
    
    // Color points by VPD value
    const datasets = [{
      label: 'Data Points',
      data: this.filteredData,
      backgroundColor: this.filteredData.map(p => this.getVPDColor(p.vpd)),
      borderColor: this.filteredData.map(p => this.getVPDColor(p.vpd, 1)),
      borderWidth: 1,
      pointRadius: 4,
      pointHoverRadius: 6
    }];
    
    // Add regression line if enabled
    if (this.options.showRegressionLine && this.filteredData.length > 2) {
      const regression = this.calculateRegression();
      datasets.push({
        label: `Regression (R² = ${regression.r2.toFixed(3)})`,
        data: regression.line,
        type: 'line',
        borderColor: 'rgba(33, 150, 243, 0.8)',
        borderWidth: 2,
        borderDash: [5, 5],
        fill: false,
        pointRadius: 0,
        pointHoverRadius: 0
      });
      
      // Update correlation display
      this.updateCorrelationDisplay(regression.r, regression.r2);
    }
    
    this.chart.data.datasets = datasets;
    this.chart.update('none'); // No animation for performance
  }
  
  /**
   * Get color based on VPD value
   */
  getVPDColor(vpd, alpha = 0.6) {
    if (vpd < 0.4) {
      // Too low - blue
      return `rgba(33, 150, 243, ${alpha})`;
    } else if (vpd >= 0.4 && vpd < 0.8) {
      // Vegetative - light green
      return `rgba(139, 195, 74, ${alpha})`;
    } else if (vpd >= 0.8 && vpd <= 1.2) {
      // Optimal flowering - green
      return `rgba(76, 175, 80, ${alpha})`;
    } else if (vpd > 1.2 && vpd <= 1.6) {
      // Late flowering - yellow
      return `rgba(255, 193, 7, ${alpha})`;
    } else {
      // Too high - red
      return `rgba(244, 67, 54, ${alpha})`;
    }
  }
  
  /**
   * Calculate linear regression
   * Returns: { slope, intercept, r, r2, line }
   */
  calculateRegression() {
    const n = this.filteredData.length;
    const xValues = this.filteredData.map(p => p.x);
    const yValues = this.filteredData.map(p => p.y);
    
    const sumX = xValues.reduce((a, b) => a + b, 0);
    const sumY = yValues.reduce((a, b) => a + b, 0);
    const sumXY = xValues.reduce((sum, x, i) => sum + x * yValues[i], 0);
    const sumX2 = xValues.reduce((sum, x) => sum + x * x, 0);
    const sumY2 = yValues.reduce((sum, y) => sum + y * y, 0);
    
    const slope = (n * sumXY - sumX * sumY) / (n * sumX2 - sumX * sumX);
    const intercept = (sumY - slope * sumX) / n;
    
    // Correlation coefficient
    const r = (n * sumXY - sumX * sumY) / 
              Math.sqrt((n * sumX2 - sumX * sumX) * (n * sumY2 - sumY * sumY));
    const r2 = r * r;
    
    // Generate line points
    const minX = Math.min(...xValues);
    const maxX = Math.max(...xValues);
    const line = [
      { x: minX, y: slope * minX + intercept },
      { x: maxX, y: slope * maxX + intercept }
    ];
    
    return { slope, intercept, r, r2, line };
  }
  
  /**
   * Update correlation coefficient display
   */
  updateCorrelationDisplay(r, r2) {
    const display = document.getElementById(`${this.canvasId}-correlation`);
    if (display) {
      const strength = Math.abs(r) > 0.7 ? 'Strong' :
                      Math.abs(r) > 0.4 ? 'Moderate' : 'Weak';
      const direction = r > 0 ? 'Positive' : 'Negative';
      
      display.innerHTML = `
        <div class="correlation-stats">
          <div class="stat">
            <span class="label">Correlation:</span>
            <span class="value">${r.toFixed(3)}</span>
          </div>
          <div class="stat">
            <span class="label">R²:</span>
            <span class="value">${r2.toFixed(3)}</span>
          </div>
          <div class="stat">
            <span class="label">Relationship:</span>
            <span class="value">${strength} ${direction}</span>
          </div>
        </div>
      `;
    }
  }
  
  /**
   * Generate custom legend labels
   */
  generateLegendLabels(chart) {
    const labels = [
      { text: 'Too Low (< 0.4 kPa)', fillStyle: this.getVPDColor(0.3) },
      { text: 'Vegetative (0.4-0.8 kPa)', fillStyle: this.getVPDColor(0.6) },
      { text: 'Optimal Flower (0.8-1.2 kPa)', fillStyle: this.getVPDColor(1.0) },
      { text: 'Late Flower (1.2-1.6 kPa)', fillStyle: this.getVPDColor(1.4) },
      { text: 'Too High (> 1.6 kPa)', fillStyle: this.getVPDColor(1.8) }
    ];
    
    return labels.map(l => ({
      text: l.text,
      fillStyle: l.fillStyle,
      strokeStyle: l.fillStyle,
      lineWidth: 0,
      hidden: false,
      pointStyle: 'circle'
    }));
  }
  
  /**
   * Refresh data
   */
  async refresh() {
    if (!this.loading && this.unitId) {
      await this.loadData();
    }
  }
  
  /**
   * Show loading state
   */
  setLoading(loading) {
    this.loading = loading;
    const container = this.canvas.closest('.chart-container');
    if (container) {
      container.classList.toggle('loading', loading);
    }
  }
  
  /**
   * Show error message
   */
  showError(message) {
    const container = this.canvas.closest('.chart-container');
    if (container) {
      let errorDiv = container.querySelector('.chart-error');
      if (!errorDiv) {
        errorDiv = document.createElement('div');
        errorDiv.className = 'chart-error';
        container.appendChild(errorDiv);
      }
      errorDiv.textContent = message;
      errorDiv.style.display = 'block';
      
      setTimeout(() => {
        errorDiv.style.display = 'none';
      }, 5000);
    }
  }
  
  /**
   * Destroy chart and cleanup
   */
  destroy() {
    if (this.updateTimer) {
      clearInterval(this.updateTimer);
      this.updateTimer = null;
    }
    
    if (this.chart) {
      this.chart.destroy();
      this.chart = null;
    }
  }
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
  module.exports = TempHumidityCorrelation;
}
