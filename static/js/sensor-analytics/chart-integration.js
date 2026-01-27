/**
 * Chart Integration Helper for Sensor Analytics
 * Wraps ChartService to provide sensor-specific chart configurations
 */

class SensorAnalyticsCharts {
  constructor() {
    this.charts = new Map();
    this.chartService = window.ChartService;
    
    if (!this.chartService) {
      console.warn('ChartService not found - charts may not render correctly');
    }
  }

  /**
   * Setup all charts for sensor analytics
   * @param {Object} elements - Object containing canvas elements
   */
  setupCharts(elements) {
    if (elements.comparisonChartCanvas) {
      this.setupComparisonChart(elements.comparisonChartCanvas);
    }

    if (elements.trendsChartCanvas) {
      this.setupTrendsChart(elements.trendsChartCanvas);
    }

    if (elements.dataGraphCanvas) {
      this.setupDataGraphChart(elements.dataGraphCanvas);
    }
  }

  /**
   * Setup comparison chart (multi-sensor line chart)
   */
  setupComparisonChart(canvas) {
    if (!this.chartService) {
      console.error('ChartService required for comparison chart');
      return null;
    }

    const options = {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: { title: { display: true, text: 'Time' } },
        y: { beginAtZero: true, title: { display: true, text: 'Value' } },
      },
      plugins: {
        legend: { position: 'bottom' },
        tooltip: {
          callbacks: {
            label: (ctx) => {
              return `${ctx.dataset.label}: ${ctx.parsed.y?.toFixed(2) || 'N/A'}`;
            }
          }
        }
      },
    };

    const chart = this.chartService.createLineChart(canvas, [], [], options);
    this.charts.set('comparison', chart);
    return chart;
  }

  /**
   * Setup trends chart (statistics bar chart)
   */
  setupTrendsChart(canvas) {
    if (!this.chartService) {
      console.error('ChartService required for trends chart');
      return null;
    }

    const options = {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        y: { beginAtZero: true, title: { display: true, text: 'Value' } },
      },
      plugins: {
        legend: { position: 'bottom' },
      },
    };

    const chart = this.chartService.createBarChart(canvas, [], [], options);
    this.charts.set('trends', chart);
    return chart;
  }

  /**
   * Setup data graph chart (timeseries with health overlay)
   */
  setupDataGraphChart(canvas) {
    if (!this.chartService) {
      console.error('ChartService required for data graph chart');
      return null;
    }

    const options = {
      responsive: true,
      maintainAspectRatio: false,
      parsing: false,
      normalized: true,
      scales: {
        x: {
          type: 'linear',
          title: { display: true, text: 'Time' },
        },
        metric: {
          type: 'linear',
          position: 'left',
          title: { display: true, text: 'Metrics' },
        },
      },
      plugins: {
        legend: { position: 'bottom' },
        tooltip: {
          callbacks: {
            title: (items) => {
              if (!items[0]) return '';
              const ts = items[0].parsed.x;
              return new Date(ts).toLocaleString();
            },
            label: (ctx) => {
              return `${ctx.dataset.label}: ${ctx.parsed.y?.toFixed(2) || 'N/A'}`;
            },
          },
        },
      },
    };

    const chart = this.chartService.createLineChart(canvas, [], [], options);
    this.charts.set('dataGraph', chart);
    return chart;
  }

  /**
   * Update charts with new data
   * @param {Array} seriesData - Array of sensor data series
   * @param {Array} plantHealth - Optional plant health data
   * @param {Function} buildDatasets - Function to build datasets from series data
   * @param {Function} buildHealthDataset - Function to build health dataset
   */
  updateCharts(seriesData, plantHealth, buildDatasets, buildHealthDataset) {
    if (!this.chartService) {
      console.error('ChartService required for updating charts');
      return;
    }

    const datasets = buildDatasets(seriesData);

    // Add plant health if present
    if (plantHealth && Array.isArray(plantHealth) && plantHealth.length > 0) {
      const healthDataset = buildHealthDataset(plantHealth);
      if (healthDataset) datasets.push(healthDataset);
    }

    // Update data graph chart
    const dataGraphChart = this.charts.get('dataGraph');
    if (dataGraphChart) {
      dataGraphChart.data.datasets = datasets;
      
      // Add health axis if needed
      const hasHealthAxis = datasets.some(ds => ds.yAxisID === 'health');
      if (hasHealthAxis && !dataGraphChart.options.scales.health) {
        dataGraphChart.options.scales.health = {
          type: 'linear',
          position: 'right',
          title: { display: true, text: 'Plant Health (score)' },
          min: 0,
          max: 100,
        };
      }
      
      this.chartService.updateChart(dataGraphChart);
    }
  }

  /**
   * Update comparison chart with new data
   * @param {Array} labels - X-axis labels
   * @param {Array} datasets - Chart datasets
   */
  updateComparisonChart(labels, datasets) {
    const chart = this.charts.get('comparison');
    if (chart && this.chartService) {
      chart.data.labels = labels;
      chart.data.datasets = datasets;
      this.chartService.updateChart(chart);
    }
  }

  /**
   * Update trends chart with new data
   * @param {Array} labels - X-axis labels
   * @param {Array} datasets - Chart datasets
   */
  updateTrendsChart(labels, datasets) {
    const chart = this.charts.get('trends');
    if (chart && this.chartService) {
      chart.data.labels = labels;
      chart.data.datasets = datasets;
      this.chartService.updateChart(chart);
    }
  }

  /**
   * Get color for sensor type using ChartService
   * @param {string} sensorType - Type of sensor (temperature, humidity, etc.)
   * @returns {string} Color hex code
   */
  getSensorColor(sensorType) {
    if (!this.chartService) {
      return '#6366f1'; // Default primary color
    }

    const colorMap = {
      temperature: this.chartService.getSensorColor('temperature'),
      humidity: this.chartService.getSensorColor('humidity'),
      soil_moisture: this.chartService.getSensorColor('soil_moisture'),
      light_level: this.chartService.getSensorColor('light'),
      co2_level: this.chartService.getSensorColor('co2'),
      voc_level: this.chartService.getSensorColor('voc'),
    };

    return colorMap[sensorType] || this.chartService.colors.primary;
  }

  /**
   * Destroy all charts
   */
  destroyCharts() {
    if (this.chartService) {
      this.charts.forEach((chart, key) => {
        this.chartService.destroyChart(chart);
      });
    }
    this.charts.clear();
  }

  /**
   * Get a specific chart by key
   * @param {string} key - Chart key (comparison, trends, dataGraph)
   * @returns {Chart|undefined} Chart instance
   */
  getChart(key) {
    return this.charts.get(key);
  }
}

// Export for module usage
if (typeof window !== 'undefined') {
  window.SensorAnalyticsCharts = SensorAnalyticsCharts;
}
