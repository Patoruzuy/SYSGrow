/**
 * SensorAnalyticsUIManager
 * ============================================================================
 * UI layer responsibilities:
 *  - Chart rendering with Chart.js
 *  - Table updates
 *  - Filter management
 *  - Statistics calculation and display
 *  - Real-time socket updates
 *  - Saved views and alert management
 */
(function () {
  'use strict';

  class SensorAnalyticsUIManager extends BaseManager {
    constructor(dataService) {
      super('SensorAnalyticsUIManager');

      if (!dataService) throw new Error('dataService is required for SensorAnalyticsUIManager');

      this.dataService = dataService;
      this.socketManager = window.socketManager;

      // Debug toggle
      this.debugEnabled = localStorage.getItem('sensor-analytics:debug') === '1';

      // Charts
      this.charts = new Map();
      
      // Environmental Overview Chart (ML-enhanced)
      this.environmentalOverviewChart = null;
      
      // ML Chart Enhancer
      this.mlChartEnhancer = null;

      // Phase D: Sensor Analytics Components
      this.vpdZonesChart = null;
      this.correlationMatrix = null;
      this.anomalyPanel = null;

      // State
      this.state = {
        selectedUnit: null,
        selectedSensor: null,
        selectedPlant: null,
        metrics: new Set(['temperature', 'humidity', 'soil_moisture', 'lux']),
        sensorType: 'all',
        hours: 24,
        grouping: 'hour',
        dateRange: '24h',
        tablePage: 1,
        tablePageSize: 10,
        selectedSensors: [],
      };

      // Data caches
      this.units = [];
      this.sensors = [];
      this.plants = [];
      this.lastSeriesPayload = { series: [] };
      this.statistics = new Map();
      this.anomalies = [];

      // Saved views and alerts
      this.savedViews = {};
      this.alerts = [];

      this.unsubscribeFunctions = [];

      // Cache common DOM elements
      this.elements = {
        // Filters
        unitSelect: document.getElementById('unit-select'),
        sensorSelect: document.getElementById('sensor-select'),
        plantSelect: document.getElementById('plant-select'),
        sensorTypeSelect: document.getElementById('sensor-type'),
        rangeSelect: document.getElementById('range-select'),
        dateRangeSelect: document.getElementById('date-range'),
        groupingSelect: document.getElementById('grouping'),
        sensorMultiSelect: document.getElementById('sensor-select-multi'),

        // Metric selector
        metricContainer: document.getElementById('metric-multi'),
        metricToggle: document.getElementById('metric-toggle'),
        metricMenu: document.getElementById('metric-menu'),
        metricSummary: document.getElementById('metric-summary'),
        metricOptions: document.querySelectorAll('#metric-menu input[type="checkbox"]'),

        // Actions
        refreshBtn: document.getElementById('refresh-btn'),
        exportBtn: document.getElementById('export-btn'),

        // Charts
        comparisonChartCanvas: document.getElementById('comparison-chart'),
        trendsChartCanvas: document.getElementById('trends-chart'),
        dataGraphCanvas: document.getElementById('data-graph-canvas'),
        seriesMeta: document.getElementById('series-meta'),

        // Tables
        dataTableBody: document.getElementById('sensor-data-body'),
        recentReadings: document.getElementById('recent-readings'),
        tableCount: document.getElementById('table-count'),
        loadMoreBtn: document.getElementById('load-more-btn'),

        // Status/Info
        statisticsContainer: document.getElementById('statistics-container'),
        anomaliesContainer: document.getElementById('anomalies-container'),
        plantStatus: document.getElementById('plant-status'),
        sensorList: document.getElementById('sensorList'),

        // Phase D: New Component Containers
        vpdZonesContainer: document.getElementById('vpd-zones-container'),
        vpdZonesRange: document.getElementById('vpd-zones-range'),
        correlationMatrixContainer: document.getElementById('correlation-matrix-container'),

        // Saved views
        viewNameInput: document.getElementById('view-name-input'),
        saveViewBtn: document.getElementById('save-view-btn'),
        applyViewBtn: document.getElementById('apply-view-btn'),
        deleteViewBtn: document.getElementById('delete-view-btn'),
        savedViewSelect: document.getElementById('saved-view-select'),

        // Alerts
        alertMetricSelect: document.getElementById('alert-metric-select'),
        alertOperatorSelect: document.getElementById('alert-operator-select'),
        alertThresholdInput: document.getElementById('alert-threshold-input'),
        addAlertBtn: document.getElementById('add-alert-btn'),
        alertList: document.getElementById('alert-list'),
      };

      // Color palette for charts
      this.chartColors = [
        '#5B8FF9', '#61DDAA', '#65789B', '#F6BD16', '#7262fd',
        '#78D3F8', '#9661BC', '#F6903D', '#008685', '#F08BB4',
      ];
    }

    // Optional: gate BaseManager logging
    log(...args) { if (this.debugEnabled) super.log(...args); }
    debug(...args) { if (this.debugEnabled) super.debug(...args); }

    async init() {
      this.restoreSavedViews();
      this.restoreAlerts();
      this.restoreState();

      this.setupSocketListeners();
      this.bindEvents();
      this.setupCharts();
      
      // Initialize ML Chart Enhancer
      await this.setupMLChartEnhancer();
      
      // Initialize Environmental Overview Chart
      await this.setupEnvironmentalOverviewChart();

      // Initialize Phase D Components
      this.setupPhaseD_Components();

      await this.loadAndRender();
    }

    /**
     * Setup Phase D: Sensor Analytics Components
     */
    setupPhaseD_Components() {
      // VPD Zones Chart
      if (this.elements.vpdZonesContainer && typeof VPDZonesChart !== 'undefined') {
        this.vpdZonesChart = new VPDZonesChart('vpd-zones-container', {
          showLegend: true,
          showPercentages: true,
          showCenter: true
        });
        console.log('[UIManager] VPD Zones Chart initialized');
      }

      // Sensor Correlation Matrix
      if (this.elements.correlationMatrixContainer && typeof SensorCorrelationMatrix !== 'undefined') {
        this.correlationMatrix = new SensorCorrelationMatrix('correlation-matrix-container', {
          showLabels: true,
          showTooltips: true,
          showLegend: true
        });
        console.log('[UIManager] Correlation Matrix initialized');
      }

      // Intelligent Anomaly Panel (replaces basic anomaly display)
      if (this.elements.anomaliesContainer && typeof IntelligentAnomalyPanel !== 'undefined') {
        this.anomalyPanel = new IntelligentAnomalyPanel('anomalies-container', {
          showActions: true,
          showTrends: true,
          maxVisible: 10,
          onAction: (anomaly, action) => this.handleAnomalyAction(anomaly, action),
          onDismiss: (anomaly) => this.handleAnomalyDismiss(anomaly)
        });
        console.log('[UIManager] Intelligent Anomaly Panel initialized');
      }

      // VPD zones range selector event
      if (this.elements.vpdZonesRange) {
        this.addEventListener(this.elements.vpdZonesRange, 'change', () => {
          this.refreshVPDZonesChart();
        });
      }
    }

    /**
     * Handle anomaly action from IntelligentAnomalyPanel
     */
    handleAnomalyAction(anomaly, action) {
      switch (action) {
        case 'adjust_threshold':
          window.location.href = '/settings#thresholds';
          break;
        case 'view_history':
          if (anomaly.sensor_id) {
            this.state.selectedSensor = anomaly.sensor_id;
            if (this.elements.sensorSelect) {
              this.elements.sensorSelect.value = anomaly.sensor_id;
            }
            this.refresh();
          }
          break;
        case 'check_connection':
        case 'restart_sensor':
          this.showNotification(`Action "${action}" requires manual intervention`, 'info');
          break;
        case 'investigate':
          // Scroll to statistics section
          const statsSection = document.getElementById('statistics-heading');
          if (statsSection) {
            statsSection.scrollIntoView({ behavior: 'smooth' });
          }
          break;
        default:
          console.log('[UIManager] Unknown anomaly action:', action);
      }
    }

    /**
     * Handle anomaly dismiss from IntelligentAnomalyPanel
     */
    handleAnomalyDismiss(anomaly) {
      // Remove from local anomalies array
      this.anomalies = this.anomalies.filter(a =>
        !(a.sensor_id === anomaly.sensor_id && a.timestamp === anomaly.timestamp)
      );

      // Re-render the panel
      if (this.anomalyPanel) {
        this.anomalyPanel.update(this.anomalies);
      }

      this.showNotification('Anomaly dismissed', 'success');
    }

    bindEvents() {
      // Unit selection
      if (this.elements.unitSelect) {
        this.addEventListener(this.elements.unitSelect, 'change', async (e) => {
          this.state.selectedUnit = e.target.value || null;
          await this.loadSensors({ resetSelection: true });
          await this.loadPlants({ resetSelection: true });
          await this.refresh();
        });
      }

      // Sensor selection
      if (this.elements.sensorSelect) {
        this.addEventListener(this.elements.sensorSelect, 'change', async (e) => {
          this.state.selectedSensor = e.target.value || null;
          await this.refresh();
        });
      }

      // Multi-sensor selection
      if (this.elements.sensorMultiSelect) {
        this.addEventListener(this.elements.sensorMultiSelect, 'change', (e) => {
          this.state.selectedSensors = Array.from(e.target.selectedOptions).map(opt => opt.value);
          this.refresh();
        });
      }

      // Sensor type filter
      if (this.elements.sensorTypeSelect) {
        this.addEventListener(this.elements.sensorTypeSelect, 'change', (e) => {
          this.state.sensorType = e.target.value;
          this.refresh();
        });
      }

      // Plant selection
      if (this.elements.plantSelect) {
        this.addEventListener(this.elements.plantSelect, 'change', async (e) => {
          this.state.selectedPlant = e.target.value || null;
          await this.refresh();
        });
      }

      // Time range
      if (this.elements.rangeSelect) {
        this.addEventListener(this.elements.rangeSelect, 'change', async (e) => {
          this.state.hours = Number(e.target.value) || 24;
          await this.refresh();
        });
      }

      if (this.elements.dateRangeSelect) {
        this.addEventListener(this.elements.dateRangeSelect, 'change', () => {
          this.state.dateRange = this.elements.dateRangeSelect.value;
          this.refresh();
        });
      }

      // Grouping
      if (this.elements.groupingSelect) {
        this.addEventListener(this.elements.groupingSelect, 'change', () => {
          this.state.grouping = this.elements.groupingSelect.value;
          this.refresh();
        });
      }

      // Metric selector
      if (this.elements.metricToggle) {
        this.addEventListener(this.elements.metricToggle, 'click', () => this.toggleMetricMenu());
      }

      if (this.elements.metricMenu) {
        this.addEventListener(this.elements.metricMenu, 'keydown', (e) => {
          if (e.key === 'Escape') this.toggleMetricMenu(false);
        });
      }

      if (this.elements.metricOptions?.length) {
        this.elements.metricOptions.forEach(checkbox => {
          this.addEventListener(checkbox, 'change', () => {
            this.syncMetricsFromUI();
            this.refresh();
          });
        });
      }

      // Close metric menu on outside click
      this.addEventListener(document, 'click', (e) => {
        if (!this.elements.metricContainer?.contains(e.target)) {
          this.toggleMetricMenu(false);
        }
      });

      // Actions
      if (this.elements.refreshBtn) {
        this.addEventListener(this.elements.refreshBtn, 'click', () => this.loadAndRender({ force: true }));
      }

      if (this.elements.exportBtn) {
        this.addEventListener(this.elements.exportBtn, 'click', () => this.exportData());
      }

      // Table pagination
      if (this.elements.loadMoreBtn) {
        this.addEventListener(this.elements.loadMoreBtn, 'click', () => {
          this.state.tablePage++;
          this.renderTable(this.lastSeriesPayload);
        });
      }

      // Saved views
      if (this.elements.saveViewBtn) {
        this.addEventListener(this.elements.saveViewBtn, 'click', () => {
          const name = this.elements.viewNameInput?.value?.trim();
          if (name) this.saveCurrentView(name);
        });
      }

      if (this.elements.applyViewBtn) {
        this.addEventListener(this.elements.applyViewBtn, 'click', () => {
          this.applySelectedView().catch(err => this.error('Failed to apply view:', err));
        });
      }

      if (this.elements.deleteViewBtn) {
        this.addEventListener(this.elements.deleteViewBtn, 'click', () => this.deleteSelectedView());
      }

      if (this.elements.savedViewSelect) {
        this.addEventListener(this.elements.savedViewSelect, 'change', (e) => {
          const hasSelection = Boolean(e.target.value);
          if (this.elements.applyViewBtn) this.elements.applyViewBtn.disabled = !hasSelection;
          if (this.elements.deleteViewBtn) this.elements.deleteViewBtn.disabled = !hasSelection;
        });
      }

      // Alerts
      if (this.elements.addAlertBtn) {
        this.addEventListener(this.elements.addAlertBtn, 'click', () => this.addAlert());
      }

      if (this.elements.alertList) {
        this.addDelegatedListener(this.elements.alertList, 'click', '[data-alert-remove]', (e) => {
          const alertId = e.target.closest('[data-alert-remove]').dataset.alertRemove;
          if (alertId) this.removeAlert(alertId);
        });
      }

      this.syncMetricOptions();
    }

    // --------------------------------------------------------------------------
    // Socket.IO setup
    // --------------------------------------------------------------------------

    setupSocketListeners() {
      if (!this.socketManager) {
        this.warn('SocketManager not available');
        return;
      }

      // Sensor updates
      const sensorEvents = [
        'device_sensor_reading',
        'sensor_update', 'sensor_reading',
        'zigbee_sensor_data',
        'temperature_update', 'humidity_update',
        'soil_moisture_update', 'light_level_update',
        'co2_update', 'energy_update',
      ];

      for (const evt of sensorEvents) {
        this.unsubscribeFunctions.push(
          this.socketManager.on(evt, (data) => this.handleNewReading(data))
        );
      }

      // Anomaly detection
      this.unsubscribeFunctions.push(
        this.socketManager.on('anomaly_detected', (data) => this.handleAnomalyDetected(data))
      );

      this.unsubscribeFunctions.push(
        this.socketManager.on('sensor_anomaly', (data) => this.handleAnomalyDetected(data))
      );
    }

    // --------------------------------------------------------------------------
    // Data loading
    // --------------------------------------------------------------------------

    async loadAndRender({ force = false } = {}) {
      try {
        // Load metadata first
        await Promise.all([
          this.loadUnits({ force }),
          this.loadSensors({ force }),
          this.loadPlants({ force }),
        ]);

        // Load and render data
        await this.refresh({ force });
      } catch (error) {
        this.error('Failed to load sensor analytics data:', error);
        this.showNotification('Failed to load data', 'error');
      }
    }

    async refresh({ force = false } = {}) {
      try {
        this.showLoading();

        const params = this.buildTimeseriesParams();
        const seriesData = await this.dataService.loadTimeseries(params, { force });

        this.lastSeriesPayload = seriesData;

        // Load additional data
        const [plantHealth, sensorStatus] = await Promise.all([
          this.state.selectedPlant
            ? this.dataService.loadPlantHealth(this.state.selectedPlant, { force })
            : null,
          this.dataService.loadSensorStatus({ force }),
        ]);

        // Update UI
        this.updateCharts(seriesData, plantHealth);
        this.updateTable(seriesData);
        this.updateStatistics(seriesData);
        this.updateAnomalies(seriesData);
        this.updateSensorStatus(sensorStatus);
        this.updateMeta(seriesData);
        
        // Refresh Environmental Overview Chart
        await this.refreshEnvironmentalOverview();

        // Refresh Phase D Components
        await this.refreshPhaseD_Components(seriesData);

        // Evaluate alerts
        this.evaluateAlerts(seriesData);

        this.hideLoading();
      } catch (error) {
        this.error('Failed to refresh data:', error);
        this.showError('Failed to refresh data');
      }
    }

    async loadUnits({ force = false } = {}) {
      try {
        this.units = await this.dataService.loadUnits({ force });
        this.populateUnitSelect();
      } catch (error) {
        this.error('Failed to load units:', error);
      }
    }

    async loadSensors({ resetSelection = false, force = false } = {}) {
      try {
        this.sensors = await this.dataService.loadSensors({ force });
        this.populateSensorSelect(resetSelection);
      } catch (error) {
        this.error('Failed to load sensors:', error);
      }
    }

    async loadPlants({ resetSelection = false, force = false } = {}) {
      try {
        this.plants = await this.dataService.loadPlants({ force });
        this.populatePlantSelect(resetSelection);
      } catch (error) {
        this.error('Failed to load plants:', error);
      }
    }

    // --------------------------------------------------------------------------
    // UI Population
    // --------------------------------------------------------------------------

    populateUnitSelect() {
      if (!this.elements.unitSelect) return;

      const currentValue = this.elements.unitSelect.value;
      this.elements.unitSelect.innerHTML = '<option value="">All Units</option>';

      this.units.forEach(unit => {
        const opt = document.createElement('option');
        opt.value = unit.unit_id || unit.id;
        opt.textContent = unit.name || `Unit ${unit.unit_id || unit.id}`;
        this.elements.unitSelect.appendChild(opt);
      });

      if (currentValue) {
        // Restore previously selected value.
        this.elements.unitSelect.value = currentValue;
      } else if (this.units.length > 0 && !this.state.selectedUnit) {
        // Auto-select the first available unit so the readings table populates
        // immediately on page load without requiring manual filter selection.
        const firstUnit = this.units[0];
        const firstId = String(firstUnit.unit_id || firstUnit.id);
        this.elements.unitSelect.value = firstId;
        this.state.selectedUnit = firstId;
      }
    }

    populateSensorSelect(resetSelection = false) {
      if (!this.elements.sensorSelect) return;

      const currentValue = resetSelection ? '' : this.elements.sensorSelect.value;
      this.elements.sensorSelect.innerHTML = '<option value="">All Sensors</option>';

      this.sensors.forEach(sensor => {
        const opt = document.createElement('option');
        opt.value = sensor.sensor_id || sensor.id;
        opt.textContent = sensor.name || `Sensor ${sensor.sensor_id || sensor.id}`;
        this.elements.sensorSelect.appendChild(opt);
      });

      this.elements.sensorSelect.value = currentValue;

      // Also populate multi-select if present
      if (this.elements.sensorMultiSelect) {
        this.elements.sensorMultiSelect.innerHTML = '';
        this.sensors.slice(0, 10).forEach((sensor, idx) => {
          const opt = document.createElement('option');
          opt.value = sensor.sensor_id || sensor.id;
          opt.textContent = sensor.name || `Sensor ${sensor.sensor_id || sensor.id}`;
          opt.selected = idx < 3; // Select first 3 by default
          this.elements.sensorMultiSelect.appendChild(opt);
        });

        this.state.selectedSensors = Array.from(this.elements.sensorMultiSelect.selectedOptions)
          .map(opt => opt.value);
      }
    }

    populatePlantSelect(resetSelection = false) {
      if (!this.elements.plantSelect) return;

      const currentValue = resetSelection ? '' : this.elements.plantSelect.value;
      this.elements.plantSelect.innerHTML = '<option value="">No plant overlay</option>';

      this.plants.forEach(plant => {
        const opt = document.createElement('option');
        opt.value = plant.plant_id || plant.id;
        opt.textContent = plant.name || `Plant ${plant.plant_id || plant.id}`;
        this.elements.plantSelect.appendChild(opt);
      });

      this.elements.plantSelect.value = currentValue;
    }

    buildTimeseriesParams() {
      return {
        hours: this.state.hours,
        unit_id: this.state.selectedUnit || undefined,
        sensor_id: this.state.selectedSensor || undefined,
        limit: 500,
      };
    }

    // --------------------------------------------------------------------------
    // Chart Management
    // --------------------------------------------------------------------------

    setupCharts() {
      // Use SensorAnalyticsCharts helper for standardized chart setup
      if (window.SensorAnalyticsCharts) {
        this.chartHelper = new window.SensorAnalyticsCharts();
        this.chartHelper.setupCharts(this.elements);
        
        // Copy charts from helper to our charts Map for backward compatibility
        this.charts = this.chartHelper.charts;
      } else {
        console.warn('SensorAnalyticsCharts helper not found - falling back to manual chart setup');
        this.setupChartsManual();
      }
    }

    /**
     * Manual chart setup (fallback if chart helper is not available)
     */
    setupChartsManual() {
      // Comparison chart (multi-sensor)
      if (this.elements.comparisonChartCanvas) {
        const ctx = this.elements.comparisonChartCanvas.getContext('2d');
        this.charts.set('comparison', new Chart(ctx, {
          type: 'line',
          data: { labels: [], datasets: [] },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
              x: { title: { display: true, text: 'Time' } },
              y: { beginAtZero: true, title: { display: true, text: 'Value' } },
            },
            plugins: {
              legend: { position: 'bottom' },
            },
          },
        }));
      }

      // Trends chart (statistics)
      if (this.elements.trendsChartCanvas) {
        const ctx = this.elements.trendsChartCanvas.getContext('2d');
        this.charts.set('trends', new Chart(ctx, {
          type: 'bar',
          data: { labels: [], datasets: [] },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
              y: { beginAtZero: true },
            },
            plugins: {
              legend: { position: 'bottom' },
            },
          },
        }));
      }

      // Data graph chart (timeseries with health overlay)
      if (this.elements.dataGraphCanvas) {
        const ctx = this.elements.dataGraphCanvas.getContext('2d');
        this.charts.set('dataGraph', new Chart(ctx, {
          type: 'line',
          data: { datasets: [] },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            parsing: false,
            normalized: true,
            scales: {
              x: {
                type: 'linear',
                ticks: {
                  callback: (value) => this.formatTick(value),
                  maxTicksLimit: this.tickLimit(),
                },
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
          },
        }));
      }
    }

    updateCharts(seriesData, plantHealth = null) {
      const datasets = this.buildDatasets(seriesData);

      // Add plant health if present
      if (plantHealth && Array.isArray(plantHealth) && plantHealth.length > 0) {
        const healthDataset = this.buildHealthDataset(plantHealth);
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
            max: 5,
            grid: { drawOnChartArea: false },
          };
        }
        
        dataGraphChart.update();
      }

      // Update comparison chart if present
      this.updateComparisonChart(seriesData);
      
      // Update trends/statistics chart
      this.updateTrendsChart(seriesData);
      
      // Apply ML enhancements to all charts
      if (this.mlChartEnhancer) {
        this.enhanceAllCharts().catch(err => 
          console.warn('Failed to apply ML enhancements:', err)
        );
      }
    }

    buildDatasets(payload) {
      const series = payload?.series || [];
      const metrics = Array.from(this.state.metrics);
      const bySensorMetric = new Map();

      series.forEach(row => {
        const sensorId = row.sensor_id || 'unknown';
        metrics.forEach(metric => {
          const value = this.getMetricValue(row, metric);
          if (value !== null && value !== undefined) {
            const ts = new Date(row.timestamp).getTime();
            if (!Number.isFinite(ts)) return;
            const key = `${sensorId}:${metric}`;
            if (!bySensorMetric.has(key)) {
              bySensorMetric.set(key, { sensorId, metric, points: [] });
            }
            bySensorMetric.get(key).points.push({ x: ts, y: value });
          }
        });
      });

      const datasets = [];
      let colorIdx = 0;

      for (const entry of bySensorMetric.values()) {
        if (entry.points.length === 0) continue;

        const sensorName = this.lookupSensorName(entry.sensorId);
        entry.points.sort((a, b) => a.x - b.x);
        const color = this.chartColors[colorIdx % this.chartColors.length];
        colorIdx++;

        datasets.push({
          label: `${sensorName} - ${this.metricLabel(entry.metric)}`,
          data: entry.points,
          borderColor: color,
          backgroundColor: color + '33',
          tension: 0.15,
          pointRadius: 2,
          spanGaps: true,
          yAxisID: 'metric',
        });
      }

      return datasets;
    }

    buildHealthDataset(observations) {
      if (!observations || !observations.length) return null;

      const points = observations
        .map(obs => {
          const ts = obs.observation_date || obs.timestamp;
          const score = this.healthScore(obs);
          return ts && score !== null ? { x: new Date(ts).getTime(), y: score } : null;
        })
        .filter(Boolean)
        .sort((a, b) => a.x - b.x);

      if (!points.length) return null;

      return {
        label: 'Plant Health',
        data: points,
        borderColor: '#ff6b6b',
        backgroundColor: '#ff6b6b33',
        tension: 0.15,
        pointRadius: 2,
        yAxisID: 'health',
      };
    }

    updateComparisonChart(seriesData) {
      const chart = this.charts.get('comparison');
      if (!chart) return;

      // Group by sensor
      const series = seriesData?.series || [];
      const sensorGroups = new Map();

      series.forEach(row => {
        const sensorId = row.sensor_id || 'unknown';
        if (!sensorGroups.has(sensorId)) {
          sensorGroups.set(sensorId, []);
        }
        sensorGroups.get(sensorId).push(row);
      });

      const labels = [];
      const datasets = [];
      let colorIdx = 0;

      sensorGroups.forEach((readings, sensorId) => {
        const sensorName = this.lookupSensorName(sensorId);
        const values = readings.map(r => this.getMetricValue(r, this.state.sensorType));
        const timestamps = readings.map(r => new Date(r.timestamp).toLocaleTimeString());

        if (labels.length === 0) labels.push(...timestamps);

        datasets.push({
          label: sensorName,
          data: values,
          borderColor: this.chartColors[colorIdx % this.chartColors.length],
          backgroundColor: this.chartColors[colorIdx % this.chartColors.length] + '33',
          tension: 0.1,
        });

        colorIdx++;
      });

      chart.data.labels = labels;
      chart.data.datasets = datasets;
      chart.update();
    }

    updateTrendsChart(seriesData) {
      const chart = this.charts.get('trends');
      if (!chart) return;

      this.calculateStatistics(seriesData);

      const labels = [];
      const avgData = [];
      const minData = [];
      const maxData = [];

      this.statistics.forEach((stats, sensorId) => {
        labels.push(this.lookupSensorName(sensorId));
        avgData.push(stats.avg);
        minData.push(stats.min);
        maxData.push(stats.max);
      });

      chart.data.labels = labels;
      chart.data.datasets = [
        {
          label: 'Average',
          data: avgData,
          backgroundColor: '#5B8FF9',
        },
        {
          label: 'Minimum',
          data: minData,
          backgroundColor: '#61DDAA',
        },
        {
          label: 'Maximum',
          data: maxData,
          backgroundColor: '#F6BD16',
        },
      ];

      chart.update();
    }

    getMetricValue(row, metric) {
      if (metric === 'all') {
        const priority = [
          'temperature',
          'humidity',
          'soil_moisture',
          'light_level',
          'co2_level',
          'co2_ppm',
          'voc_ppb',
          'aqi',
          'pressure',
          'ph',
          'ec_us_cm',
        ];

        const preferred = Array.from(this.state?.metrics || [])
          .filter(m => priority.includes(m));

        const ordered = preferred.length > 0 ? preferred : priority;
        for (const candidate of ordered) {
          const candidateValue = this.getMetricValue(row, candidate);
          if (candidateValue !== null && candidateValue !== undefined) {
            return candidateValue;
          }
        }
        return null;
      }

      // Backend ALWAYS returns standardized field names via FIELD_ALIASES:
      // lux (not illuminance), co2 (not co2_ppm), voc (not tvoc), etc.
      // See: app/domain/sensors/fields.py -> FIELD_ALIASES
      // No fallback mappings needed - direct 1:1 lookup
      const metricKeyMap = {
        temperature: ['temperature'],
        humidity: ['humidity'],
        soil_moisture: ['soil_moisture'],
        lux: ['lux'],
        co2: ['co2'],
        voc: ['voc'],
        air_quality: ['air_quality'],
        pressure: ['pressure'],
        ph: ['ph'],
        ec: ['ec'],
        smoke: ['smoke'],
        full_spectrum: ['full_spectrum'],
        infrared: ['infrared'],
        visible: ['visible'],
      };

      const candidates = metricKeyMap[metric] || [metric];
      
      for (const key of candidates) {
        if (row[key] !== undefined && row[key] !== null) {
          const val = Number(row[key]);
          return Number.isFinite(val) ? val : null;
        }
      }

      // For "all", pick first numeric field
      if (metric === 'all') {
        const ignoreKeys = new Set(['timestamp', 'sensor_id', 'quality_score']);
        for (const [key, value] of Object.entries(row || {})) {
          if (ignoreKeys.has(key)) continue;
          const val = Number(value);
          if (Number.isFinite(val)) return val;
        }
      }

      return null;
    }

    // --------------------------------------------------------------------------
    // Statistics
    // --------------------------------------------------------------------------

    calculateStatistics(seriesData, metricOverride = this.state.sensorType) {
      this.statistics.clear();

      const series = seriesData?.series || [];
      const bySensor = new Map();
      const sensorMetric = new Map();

      series.forEach(row => {
        const sensorId = row.sensor_id || 'unknown';
        if (!bySensor.has(sensorId)) bySensor.set(sensorId, []);

        let metricKey = metricOverride;
        if (!metricKey) {
          metricKey = this.getPrimaryMetricForSensorId(sensorId, row) || this.getStatisticsMetric();
        }
        sensorMetric.set(sensorId, metricKey);

        const value = this.getMetricValue(row, metricKey);
        if (value !== null && Number.isFinite(value)) {
          bySensor.get(sensorId).push(value);
        }
      });

      bySensor.forEach((values, sensorId) => {
        if (values.length === 0) return;

        const min = Math.min(...values);
        const max = Math.max(...values);
        const sum = values.reduce((a, b) => a + b, 0);
        const avg = sum / values.length;

        const sorted = [...values].sort((a, b) => a - b);
        const median = sorted.length % 2 === 0
          ? (sorted[sorted.length / 2 - 1] + sorted[sorted.length / 2]) / 2
          : sorted[Math.floor(sorted.length / 2)];

        const squaredDiffs = values.map(v => Math.pow(v - avg, 2));
        const variance = squaredDiffs.reduce((a, b) => a + b, 0) / values.length;
        const stdDev = Math.sqrt(variance);

        const trend = this.detectTrend(values);

        this.statistics.set(sensorId, {
          count: values.length,
          min,
          max,
          avg,
          median,
          stdDev,
          range: max - min,
          trend,
          metric: sensorMetric.get(sensorId),
        });
      });
    }

    detectTrend(values) {
      if (values.length < 2) return 'stable';

      const midpoint = Math.floor(values.length / 2);
      const firstHalf = values.slice(0, midpoint);
      const secondHalf = values.slice(midpoint);

      const avgFirst = firstHalf.reduce((a, b) => a + b, 0) / firstHalf.length;
      const avgSecond = secondHalf.reduce((a, b) => a + b, 0) / secondHalf.length;

      const diff = avgSecond - avgFirst;
      const threshold = Math.abs(avgFirst) * 0.05;

      if (diff > threshold) return 'increasing';
      if (diff < -threshold) return 'decreasing';
      return 'stable';
    }

    getStatisticsMetric() {
      if (this.state.sensorType && this.state.sensorType !== 'all') {
        return this.state.sensorType;
      }

      const priority = ['temperature', 'humidity', 'soil_moisture', 'light_level', 'co2_level', 'co2_ppm', 'voc_ppb', 'aqi', 'pressure', 'ph', 'ec_us_cm'];
      const preferred = Array.from(this.state?.metrics || []).filter(metric => priority.includes(metric));
      if (preferred.length > 0) return preferred[0];
      return 'temperature';
    }

    async updateStatistics(seriesData) {
      if (!this.elements.statisticsContainer) return;

      const hours = this.state.hours || 24;
      const statsMetric = this.getStatisticsMetric();
      const usePrimaryPerSensor = this.state.sensorType === 'all';

      // Try to load backend statistics first (per-metric aggregates)
      if (!usePrimaryPerSensor) {
        const backendStats = await this.dataService.loadStatistics({ hours });

        // If backend returned metric-level stats, use them for the selected sensor type
        if (backendStats?.statistics && statsMetric) {
          const metricStats = backendStats.statistics[statsMetric];
          if (metricStats && metricStats.count > 0) {
            // Display backend stats for the selected metric
            this.renderBackendStatistics(metricStats, backendStats, statsMetric);
            return;
          }
        }
      }

      // Fallback: Calculate per-sensor statistics from timeseries (for detailed per-sensor view)
      this.calculateStatistics(seriesData, usePrimaryPerSensor ? null : statsMetric);

      if (this.statistics.size === 0) {
        this.elements.statisticsContainer.innerHTML = '<p class="text-muted">No statistics available</p>';
        return;
      }

      const html = Array.from(this.statistics.entries())
        .map(([sensorId, stats]) => {
          const sensorName = this.lookupSensorName(sensorId);
          const metricLabel = stats.metric ? this.metricLabel(stats.metric) : null;
          const trendIcon = stats.trend === 'increasing' ? '↗' : stats.trend === 'decreasing' ? '↘' : '→';

          return `
            <div class="stat-card">
              <h4>${this.escapeHTML(sensorName)}</h4>
              ${metricLabel ? `<div class="text-muted small">${this.escapeHTML(metricLabel)}</div>` : ''}
              <div class="stat-grid">
                <div class="stat-item">
                  <span class="stat-label">Count:</span>
                  <span class="stat-value">${stats.count}</span>
                </div>
                <div class="stat-item">
                  <span class="stat-label">Average:</span>
                  <span class="stat-value">${stats.avg.toFixed(2)}</span>
                </div>
                <div class="stat-item">
                  <span class="stat-label">Min:</span>
                  <span class="stat-value">${stats.min.toFixed(2)}</span>
                </div>
                <div class="stat-item">
                  <span class="stat-label">Max:</span>
                  <span class="stat-value">${stats.max.toFixed(2)}</span>
                </div>
                <div class="stat-item">
                  <span class="stat-label">Median:</span>
                  <span class="stat-value">${stats.median.toFixed(2)}</span>
                </div>
                <div class="stat-item">
                  <span class="stat-label">Std Dev:</span>
                  <span class="stat-value">${stats.stdDev.toFixed(2)}</span>
                </div>
                <div class="stat-item">
                  <span class="stat-label">Trend:</span>
                  <span class="stat-value">${trendIcon} ${stats.trend}</span>
                </div>
              </div>
            </div>
          `;
        })
        .join('');

      this.elements.statisticsContainer.innerHTML = html;
    }

    /**
     * Render statistics from backend API response
     */
    renderBackendStatistics(metricStats, backendStats, metricKey) {
      const trendIcon = metricStats.trend === 'increasing' ? '↗' : metricStats.trend === 'decreasing' ? '↘' : '→';
      const metricLabel = this.metricLabel(metricKey || this.state.sensorType);

      const html = `
        <div class="stat-card">
          <h4>${this.escapeHTML(metricLabel)} (All Sensors)</h4>
          <div class="stat-period">
            Period: ${backendStats.period_hours || 24} hours
          </div>
          <div class="stat-grid">
            <div class="stat-item">
              <span class="stat-label">Count:</span>
              <span class="stat-value">${metricStats.count}</span>
            </div>
            <div class="stat-item">
              <span class="stat-label">Average:</span>
              <span class="stat-value">${metricStats.avg}</span>
            </div>
            <div class="stat-item">
              <span class="stat-label">Min:</span>
              <span class="stat-value">${metricStats.min}</span>
            </div>
            <div class="stat-item">
              <span class="stat-label">Max:</span>
              <span class="stat-value">${metricStats.max}</span>
            </div>
            <div class="stat-item">
              <span class="stat-label">Median:</span>
              <span class="stat-value">${metricStats.median}</span>
            </div>
            <div class="stat-item">
              <span class="stat-label">Std Dev:</span>
              <span class="stat-value">${metricStats.std_dev}</span>
            </div>
            <div class="stat-item">
              <span class="stat-label">Range:</span>
              <span class="stat-value">${metricStats.range}</span>
            </div>
            <div class="stat-item">
              <span class="stat-label">Trend:</span>
              <span class="stat-value">${trendIcon} ${metricStats.trend}</span>
            </div>
          </div>
        </div>
      `;

      this.elements.statisticsContainer.innerHTML = html;
    }

    // --------------------------------------------------------------------------
    // Anomaly Detection
    // --------------------------------------------------------------------------

    async updateAnomalies(seriesData) {
      // Try to load anomalies from backend first
      const backendAnomalies = await this.dataService.loadAnomalies();

      if (backendAnomalies && backendAnomalies.length > 0) {
        // Use backend anomalies
        this.anomalies = backendAnomalies.map(a => ({
          sensor_id: a.sensor_id,
          timestamp: a.detected_at || a.timestamp,
          value: a.value,
          threshold: a.threshold,
          message: a.description || a.message || `Anomaly detected: ${a.anomaly_type || 'unknown'}`,
          severity: a.severity || 'warning'
        }));
        this.renderAnomalies();
        return;
      }

      // Fallback: Simple client-side anomaly detection (values > 2 std deviations)
      this.anomalies = [];
      const series = seriesData?.series || [];

      this.statistics.forEach((stats, sensorId) => {
        if (!stats.avg || !stats.stdDev) return;
        const threshold = stats.avg + (2 * stats.stdDev);

        series
          .filter(row => (row.sensor_id || 'unknown') === sensorId)
          .forEach(row => {
            const value = this.getMetricValue(row, this.state.sensorType);
            if (value !== null && value > threshold) {
              this.anomalies.push({
                sensor_id: sensorId,
                timestamp: row.timestamp,
                value,
                threshold,
                message: `High reading detected: ${value.toFixed(2)} (threshold: ${threshold.toFixed(2)})`,
              });
            }
          });
      });

      this.renderAnomalies();
    }

    renderAnomalies() {
      if (!this.elements.anomaliesContainer) return;

      if (this.anomalies.length === 0) {
        this.elements.anomaliesContainer.innerHTML = '<p class="text-muted">No anomalies detected</p>';
        return;
      }

      const html = this.anomalies
        .map(anomaly => {
          const sensorName = this.lookupSensorName(anomaly.sensor_id);
          const timestamp = new Date(anomaly.timestamp).toLocaleString();

          return `
            <div class="alert alert-warning">
              <strong>${this.escapeHTML(sensorName)}</strong>
              <p>${this.escapeHTML(anomaly.message)}</p>
              <small>${timestamp}</small>
            </div>
          `;
        })
        .join('');

      this.elements.anomaliesContainer.innerHTML = html;
    }

    // --------------------------------------------------------------------------
    // Table Rendering
    // --------------------------------------------------------------------------

    updateTable(seriesData) {
      // Determine which table to update
      if (this.elements.recentReadings) {
        this.renderTable(seriesData);
      } else if (this.elements.dataTableBody) {
        this.renderDataTable(seriesData);
      }
    }

    renderTable(payload) {
      const tbody = this.elements.recentReadings;
      if (!tbody) return;

      const series = payload?.series || [];
      const metrics = Array.from(this.state.metrics);

      if (series.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" class="text-center text-muted">No data available</td></tr>';
        return;
      }

      const sorted = [...series].sort((a, b) => 
        new Date(b.timestamp || 0) - new Date(a.timestamp || 0)
      );

      const rows = [];
      for (const row of sorted) {
        metrics.forEach(metric => {
          const value = this.getMetricValue(row, metric);
          if (value !== null) {
            rows.push({
              timestamp: row.timestamp,
              sensor_id: row.sensor_id,
              metric,
              value,
              quality: row.quality_score,
            });
          }
        });
      }

      const limit = this.state.tablePage * this.state.tablePageSize;
      const visibleRows = rows.slice(0, limit);

      tbody.innerHTML = visibleRows
        .map(r => `
          <tr>
            <td>${new Date(r.timestamp).toLocaleString()}</td>
            <td>${this.escapeHTML(this.lookupSensorName(r.sensor_id))}</td>
            <td>${this.metricLabel(r.metric)}</td>
            <td>${r.value.toFixed(2)}</td>
            <td>${r.quality !== undefined ? r.quality : 'N/A'}</td>
          </tr>
        `)
        .join('');

      this.updateLoadMoreState(rows.length, limit);
    }

    renderDataTable(seriesData) {
      const tbody = this.elements.dataTableBody;
      if (!tbody) return;

      const series = seriesData?.series || [];
      
      if (series.length === 0) {
        tbody.innerHTML = '<tr class="empty-row"><td colspan="7">No sensor data available</td></tr>';
        return;
      }

      const html = series
        .slice(0, 50) // Limit initial display
        .map(row => {
          const sensorName = this.lookupSensorName(row.sensor_id);
          const value = this.getMetricValue(row, this.state.sensorType);
          const timestamp = new Date(row.timestamp).toLocaleString();

          return `
            <tr>
              <td>${timestamp}</td>
              <td>${this.escapeHTML(sensorName)}</td>
              <td>${this.formatSensorType(this.state.sensorType)}</td>
              <td>${value !== null ? value.toFixed(2) : 'N/A'}</td>
              <td><span class="badge badge-success">Normal</span></td>
              <td>${row.min !== undefined ? row.min.toFixed(2) : 'N/A'}</td>
              <td>${row.max !== undefined ? row.max.toFixed(2) : 'N/A'}</td>
            </tr>
          `;
        })
        .join('');

      tbody.innerHTML = html;
    }

    updateLoadMoreState(totalRows, visibleRows) {
      if (!this.elements.loadMoreBtn || !this.elements.tableCount) return;

      if (totalRows > visibleRows) {
        this.elements.loadMoreBtn.classList.remove('hidden');
        this.elements.tableCount.textContent = `Showing ${visibleRows} of ${totalRows} readings`;
      } else {
        this.elements.loadMoreBtn.classList.add('hidden');
        this.elements.tableCount.textContent = `Showing all ${totalRows} readings`;
      }
    }

    // --------------------------------------------------------------------------
    // Sensor Status
    // --------------------------------------------------------------------------

    updateSensorStatus(statusData) {
      if (!this.elements.sensorList) return;

      const sensors = statusData || {};

      if (Object.keys(sensors).length === 0) {
        this.elements.sensorList.innerHTML = '<div class="alert alert-info">No active sensors found.</div>';
        return;
      }

      const html = Object.entries(sensors)
        .map(([key, value]) => {
          const statusClass = value.status === 'online' ? 'text-success' : 
                             value.status === 'offline' ? 'text-danger' : 
                             'text-secondary';

          return `
            <div class="sensor mb-3 p-3 bg-light rounded">
              <strong>${this.escapeHTML(key)}</strong><br>
              Last seen: ${this.escapeHTML(value.last_seen || 'Unknown')}<br>
              <span class="${statusClass}">${this.escapeHTML(value.status || 'unknown')}</span>
            </div>
          `;
        })
        .join('');

      this.elements.sensorList.innerHTML = html;
    }

    updateMeta(payload) {
      if (!this.elements.seriesMeta) return;

      const series = payload?.series || [];
      const start = payload?.start ? new Date(payload.start).toLocaleString() : 'N/A';
      const end = payload?.end ? new Date(payload.end).toLocaleString() : 'N/A';

      this.elements.seriesMeta.textContent = `${series.length} data points from ${start} to ${end}`;
    }

    // --------------------------------------------------------------------------
    // Real-time Updates
    // --------------------------------------------------------------------------

    normalizeLivePayload(data) {
      if (!data || typeof data !== 'object') return null;
      const readings = data.readings;
      if (!readings || typeof readings !== 'object') return data;
      return { ...data, ...readings };
    }

    handleNewReading(data) {
      const payload = this.normalizeLivePayload(data);
      if (!payload) return;

      // Unit filtering
      const selectedUnit = this.dataService?.getSelectedUnitId?.();
      if (selectedUnit !== null && selectedUnit !== undefined) {
        const payloadUnit = payload.unit_id !== undefined ? Number(payload.unit_id) : null;
        if (payloadUnit !== null && payloadUnit !== selectedUnit) return;
      }

      // Add to last series payload
      if (payload.timestamp && payload.sensor_id) {
        this.lastSeriesPayload.series = this.lastSeriesPayload.series || [];
        this.lastSeriesPayload.series.unshift(payload);
        
        // Keep only last 500 points
        if (this.lastSeriesPayload.series.length > 500) {
          this.lastSeriesPayload.series.pop();
        }

        // Incremental update (debounced)
        this.scheduleChartUpdate();
      }
    }

    scheduleChartUpdate() {
      if (this._chartUpdateScheduled) return;
      this._chartUpdateScheduled = true;

      setTimeout(() => {
        this._chartUpdateScheduled = false;
        this.updateCharts(this.lastSeriesPayload);
      }, 1000);
    }

    handleAnomalyDetected(data) {
      if (!data) return;

      this.anomalies.unshift({
        sensor_id: data.sensor_id,
        timestamp: data.timestamp || new Date().toISOString(),
        value: data.value,
        message: data.message || 'Anomaly detected',
      });

      // Keep only last 20 anomalies
      if (this.anomalies.length > 20) this.anomalies.pop();

      this.renderAnomalies();
      this.showNotification(data.message || 'Anomaly detected', 'warning');
    }

    // --------------------------------------------------------------------------
    // Saved Views
    // --------------------------------------------------------------------------

    restoreSavedViews() {
      try {
        const stored = localStorage.getItem('sensor-analytics:saved-views');
        this.savedViews = stored ? JSON.parse(stored) : {};
        this.renderSavedViews();
      } catch (err) {
        this.warn('Failed to restore saved views:', err);
      }
    }

    persistSavedViews() {
      try {
        localStorage.setItem('sensor-analytics:saved-views', JSON.stringify(this.savedViews));
        this.renderSavedViews();
      } catch (err) {
        this.warn('Failed to persist saved views:', err);
      }
    }

    renderSavedViews() {
      if (!this.elements.savedViewSelect) return;

      this.elements.savedViewSelect.innerHTML = '<option value="">Load saved view…</option>';

      Object.keys(this.savedViews).forEach(name => {
        const opt = document.createElement('option');
        opt.value = name;
        opt.textContent = name;
        this.elements.savedViewSelect.appendChild(opt);
      });
    }

    getCurrentViewConfig() {
      return {
        selectedUnit: this.state.selectedUnit,
        selectedSensor: this.state.selectedSensor,
        selectedPlant: this.state.selectedPlant,
        metrics: Array.from(this.state.metrics),
        hours: this.state.hours,
        sensorType: this.state.sensorType,
        dateRange: this.state.dateRange,
        grouping: this.state.grouping,
      };
    }

    saveCurrentView(name) {
      if (!name) return;
      
      this.savedViews[name] = this.getCurrentViewConfig();
      this.persistSavedViews();
      
      if (this.elements.viewNameInput) {
        this.elements.viewNameInput.value = '';
      }
      
      this.showNotification(`View "${name}" saved`, 'success');
    }

    async applySelectedView() {
      const name = this.elements.savedViewSelect?.value;
      if (!name) return;
      
      await this.applyViewConfig(name);
    }

    async applyViewConfig(name) {
      const config = this.savedViews[name];
      if (!config) return;

      this.state = { ...this.state, ...config };
      this.state.metrics = new Set(config.metrics);

      // Update UI elements
      if (this.elements.unitSelect) this.elements.unitSelect.value = config.selectedUnit || '';
      if (this.elements.sensorSelect) this.elements.sensorSelect.value = config.selectedSensor || '';
      if (this.elements.plantSelect) this.elements.plantSelect.value = config.selectedPlant || '';
      if (this.elements.rangeSelect) this.elements.rangeSelect.value = config.hours || 24;
      if (this.elements.sensorTypeSelect) this.elements.sensorTypeSelect.value = config.sensorType || 'all';
      if (this.elements.dateRangeSelect) this.elements.dateRangeSelect.value = config.dateRange || '24h';
      if (this.elements.groupingSelect) this.elements.groupingSelect.value = config.grouping || 'hour';

      this.syncMetricOptions();
      await this.refresh({ force: true });
      
      this.showNotification(`View "${name}" applied`, 'success');
    }

    deleteSelectedView() {
      const name = this.elements.savedViewSelect?.value;
      if (!name) return;

      delete this.savedViews[name];
      this.persistSavedViews();
      
      if (this.elements.savedViewSelect) {
        this.elements.savedViewSelect.value = '';
      }
      
      this.showNotification(`View "${name}" deleted`, 'success');
    }

    // --------------------------------------------------------------------------
    // Alerts
    // --------------------------------------------------------------------------

    restoreAlerts() {
      try {
        const stored = localStorage.getItem('sensor-analytics:alerts');
        this.alerts = stored ? JSON.parse(stored) : [];
        this.renderAlerts();
      } catch (err) {
        this.warn('Failed to restore alerts:', err);
      }
    }

    persistAlerts() {
      try {
        localStorage.setItem('sensor-analytics:alerts', JSON.stringify(this.alerts));
        this.renderAlerts();
      } catch (err) {
        this.warn('Failed to persist alerts:', err);
      }
    }

    addAlert() {
      const metric = this.elements.alertMetricSelect?.value;
      const operator = this.elements.alertOperatorSelect?.value;
      const threshold = Number(this.elements.alertThresholdInput?.value);

      if (!metric || !operator || !Number.isFinite(threshold)) {
        this.showNotification('Please fill all alert fields', 'warning');
        return;
      }

      const alert = {
        id: Date.now().toString(),
        metric,
        operator,
        threshold,
      };

      this.alerts.push(alert);
      this.persistAlerts();

      // Clear inputs
      if (this.elements.alertThresholdInput) {
        this.elements.alertThresholdInput.value = '';
      }

      this.showNotification('Alert added', 'success');
    }

    removeAlert(alertId) {
      this.alerts = this.alerts.filter(a => a.id !== alertId);
      this.persistAlerts();
      this.showNotification('Alert removed', 'success');
    }

    evaluateAlerts(seriesData) {
      if (this.alerts.length === 0) return;

      const series = seriesData?.series || [];
      const results = [];

      this.alerts.forEach(alert => {
        series.forEach(row => {
          const value = this.getMetricValue(row, alert.metric);
          if (value === null) return;

          let triggered = false;
          switch (alert.operator) {
            case 'gt': triggered = value > alert.threshold; break;
            case 'gte': triggered = value >= alert.threshold; break;
            case 'lt': triggered = value < alert.threshold; break;
            case 'lte': triggered = value <= alert.threshold; break;
          }

          if (triggered) {
            results.push({
              alert,
              value,
              timestamp: row.timestamp,
              sensor_id: row.sensor_id,
            });
          }
        });
      });

      if (results.length > 0) {
        this.renderAlertsStatus(results);
      }
    }

    renderAlerts() {
      if (!this.elements.alertList) return;

      if (this.alerts.length === 0) {
        this.elements.alertList.innerHTML = '<div class="text-muted small">No alerts configured.</div>';
        return;
      }

      const html = this.alerts
        .map(alert => {
          const opLabel = {
            gt: 'Above',
            gte: 'At or above',
            lt: 'Below',
            lte: 'At or below',
          }[alert.operator] || alert.operator;

          return `
            <div class="alert-item">
              <span>${this.metricLabel(alert.metric)} ${opLabel} ${alert.threshold}</span>
              <button type="button" class="btn-close" data-alert-remove="${alert.id}" aria-label="Remove alert"></button>
            </div>
          `;
        })
        .join('');

      this.elements.alertList.innerHTML = html;
    }

    renderAlertsStatus(results) {
      if (results.length === 0) return;

      // Show notification for triggered alerts
      const message = `${results.length} alert${results.length > 1 ? 's' : ''} triggered`;
      this.showNotification(message, 'warning');
    }

    // --------------------------------------------------------------------------
    // Metric Selection
    // --------------------------------------------------------------------------

    toggleMetricMenu(forceOpen) {
      if (!this.elements.metricMenu || !this.elements.metricToggle) return;

      const isOpen = forceOpen !== undefined 
        ? forceOpen 
        : this.elements.metricMenu.classList.contains('show');

      if (isOpen) {
        this.elements.metricMenu.classList.remove('show');
        this.elements.metricToggle.setAttribute('aria-expanded', 'false');
      } else {
        this.elements.metricMenu.classList.add('show');
        this.elements.metricToggle.setAttribute('aria-expanded', 'true');
        this.elements.metricMenu.focus();
      }
    }

    syncMetricsFromUI() {
      if (!this.elements.metricOptions) return;

      this.state.metrics.clear();
      this.elements.metricOptions.forEach(checkbox => {
        if (checkbox.checked) {
          this.state.metrics.add(checkbox.value);
        }
      });

      this.updateMetricSummary();
    }

    syncMetricOptions() {
      if (!this.elements.metricOptions) return;

      this.elements.metricOptions.forEach(checkbox => {
        checkbox.checked = this.state.metrics.has(checkbox.value);
      });

      this.updateMetricSummary();
    }

    updateMetricSummary() {
      if (!this.elements.metricSummary) return;

      const labels = Array.from(this.state.metrics).map(m => this.metricLabel(m));
      this.elements.metricSummary.textContent = labels.length > 0
        ? labels.join(', ')
        : 'No metrics selected';
    }

    // --------------------------------------------------------------------------
    // Export
    // --------------------------------------------------------------------------

    exportData() {
      const series = this.lastSeriesPayload?.series || [];
      
      if (series.length === 0) {
        this.showNotification('No data to export', 'warning');
        return;
      }

      const metrics = Array.from(this.state.metrics);
      const headers = ['Timestamp', 'Sensor', ...metrics, 'Quality'];
      
      const rows = [headers];
      
      series.forEach(row => {
        const sensorName = this.lookupSensorName(row.sensor_id);
        const timestamp = new Date(row.timestamp).toISOString();
        const values = metrics.map(m => {
          const v = this.getMetricValue(row, m);
          return v !== null ? v : '';
        });
        
        rows.push([timestamp, sensorName, ...values, row.quality_score || '']);
      });

      const csv = rows.map(r => r.join(',')).join('\n');
      const blob = new Blob([csv], { type: 'text/csv' });
      const url = URL.createObjectURL(blob);
      
      const a = document.createElement('a');
      a.href = url;
      a.download = `sensor-analytics-${Date.now()}.csv`;
      a.click();
      
      URL.revokeObjectURL(url);
      this.showNotification('Data exported', 'success');
    }

    // --------------------------------------------------------------------------
    // State Management
    // --------------------------------------------------------------------------

    restoreState() {
      try {
        const stored = localStorage.getItem('sensor-analytics:state');
        if (stored) {
          const state = JSON.parse(stored);
          this.state = { ...this.state, ...state };
          
          if (Array.isArray(state.metrics)) {
            this.state.metrics = new Set(state.metrics);
          }
        }
      } catch (err) {
        this.warn('Failed to restore state:', err);
      }
    }

    persistState() {
      try {
        const state = {
          ...this.state,
          metrics: Array.from(this.state.metrics),
        };
        localStorage.setItem('sensor-analytics:state', JSON.stringify(state));
      } catch (err) {
        this.warn('Failed to persist state:', err);
      }
    }

    // --------------------------------------------------------------------------
    // Helper Methods
    // --------------------------------------------------------------------------

    lookupSensor(sensorId) {
      return this.sensors.find(s =>
        (s.sensor_id || s.id) === sensorId ||
        String(s.sensor_id || s.id) === String(sensorId)
      );
    }

    lookupSensorName(sensorId) {
      const sensor = this.lookupSensor(sensorId);
      return sensor?.name || `Sensor ${sensorId}`;
    }

    getPrimaryMetricForSensorId(sensorId, row) {
      const sensor = this.lookupSensor(sensorId);
      return this.getPrimaryMetricForSensor(sensor, row);
    }

    getPrimaryMetricForSensor(sensor, row) {
      const rawType = String(sensor?.sensor_type || sensor?.type || '').toLowerCase();
      const rawModel = String(sensor?.model || '').toLowerCase();

      const hasValue = (metric) => this.getMetricValue(row || {}, metric) !== null;

      if (rawType.includes('soil') || rawType.includes('plant_sensor')) {
        return 'soil_moisture';
      }

      if (rawType.includes('temperature')) {
        return 'temperature';
      }

      if (rawType.includes('humidity')) {
        return 'humidity';
      }

      if (rawType.includes('lux') || rawType.includes('light')) {
        return 'light_level';
      }

      if (rawType.includes('co2') || rawType.includes('air_quality') || rawType.includes('voc')) {
        if (hasValue('co2_level')) return 'co2_level';
        if (hasValue('voc_ppb')) return 'voc_ppb';
        return 'co2_level';
      }

      if (rawType.includes('pressure')) {
        return 'pressure';
      }

      if (rawType.includes('ph')) {
        return 'ph';
      }

      if (rawType.includes('ec')) {
        return 'ec_us_cm';
      }

      if (rawType.includes('environment') || rawType.includes('combo') || rawType.includes('temp_humidity')) {
        if (hasValue('temperature')) return 'temperature';
        if (hasValue('humidity')) return 'humidity';
        if (hasValue('soil_moisture')) return 'soil_moisture';
        return this.inferMetricFromRow(row);
      }

      const airQualityModels = ['mh-z19', 'scd30', 'ens160', 'bme680', 'mq135', 'mq2'];
      if (airQualityModels.some(model => rawModel.includes(model))) {
        if (hasValue('co2_level')) return 'co2_level';
        if (hasValue('voc_ppb')) return 'voc_ppb';
        return 'co2_level';
      }

      return this.inferMetricFromRow(row);
    }

    inferMetricFromRow(row) {
      if (!row || typeof row !== 'object') return null;
      const priority = [
        'temperature',
        'humidity',
        'soil_moisture',
        'light_level',
        'co2_level',
        'voc_ppb',
        'aqi',
        'pressure',
        'ph',
        'ec_us_cm',
      ];

      for (const metric of priority) {
        const value = this.getMetricValue(row, metric);
        if (value !== null && value !== undefined) {
          return metric;
        }
      }
      return null;
    }

    metricLabel(metric) {
      const labels = {
        temperature: 'Temperature (°C)',
        humidity: 'Humidity (%)',
        soil_moisture: 'Soil Moisture (%)',
        light_level: 'Light Level (lux)',
        co2_level: 'CO₂ (ppm)',
        co2_ppm: 'CO₂ (ppm)',
        voc_ppb: 'VOC (ppb)',
        aqi: 'AQI',
        pressure: 'Pressure',
        ph: 'pH',
        ec_us_cm: 'EC (µS/cm)',
        ec: 'EC (µS/cm)',
      };
      return labels[metric] || metric;
    }

    formatSensorType(type) {
      return type.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
    }

    formatTick(value) {
      const date = new Date(value);
      const now = new Date();
      const diffMs = now - date;
      const diffHours = diffMs / (1000 * 60 * 60);

      if (diffHours < 24) {
        return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
      } else if (diffHours < 168) {
        return date.toLocaleDateString([], { weekday: 'short', hour: '2-digit' });
      } else {
        return date.toLocaleDateString([], { month: 'short', day: 'numeric' });
      }
    }

    tickLimit() {
      if (this.state.hours <= 6) return 12;
      if (this.state.hours <= 24) return 12;
      if (this.state.hours <= 72) return 12;
      return 14;
    }

    healthScore(obs) {
      if (obs.health_score !== undefined) return Number(obs.health_score);
      
      const status = String(obs.current_health_status || '').toLowerCase();
      if (status === 'healthy') return 5;
      if (status === 'stressed') return 3;
      if (status === 'diseased') return 1;
      
      return null;
    }

    showLoading() {
      if (this.elements.seriesMeta) {
        this.elements.seriesMeta.textContent = 'Loading data…';
      }
    }

    hideLoading() {
      // Loading text will be replaced by updateMeta
    }

    showError(message) {
      if (this.elements.seriesMeta) {
        this.elements.seriesMeta.textContent = `Error: ${message}`;
      }
    }

    escapeHTML(str) {
      const div = document.createElement('div');
      div.textContent = String(str ?? '');
      return div.innerHTML;
    }

    showNotification(message, type = 'info') {
      try {
        const token = type.toLowerCase();

        const root = document.createElement('div');
        root.className = `alert alert-${token}`;
        root.style.cssText =
          'position: fixed; top: 20px; right: 20px; z-index: 10000; min-width: 300px; animation: slideIn 0.3s ease-out;';

        const p = document.createElement('p');
        p.textContent = String(message ?? '');
        root.appendChild(p);

        const closeBtn = document.createElement('button');
        closeBtn.className = 'flash-close';
        closeBtn.title = 'Close';
        closeBtn.innerHTML = `
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="18" y1="6" x2="6" y2="18"></line>
            <line x1="6" y1="6" x2="18" y2="18"></line>
          </svg>
        `;
        closeBtn.addEventListener('click', () => root.remove());
        root.appendChild(closeBtn);

        document.body.appendChild(root);

        setTimeout(() => {
          root.style.animation = 'slideOut 0.3s ease-in';
          setTimeout(() => root.remove(), 300);
        }, 5000);
      } catch (error) {
        this.warn('showNotification failed:', error);
      }
    }

    // --------------------------------------------------------------------------
    // ML Chart Enhancer
    // --------------------------------------------------------------------------
    
    async setupMLChartEnhancer() {
      try {
        // Check if MLChartEnhancer is available
        if (typeof MLChartEnhancer === 'undefined') {
          console.warn('[UIManager] MLChartEnhancer not loaded');
          return;
        }
        
        // Initialize the enhancer
        this.mlChartEnhancer = new MLChartEnhancer();
        await this.mlChartEnhancer.init();
        
        // Add control panel to UI
        this.addMLControlPanel();
        
        console.log('[UIManager] ML Chart Enhancer initialized');
      } catch (error) {
        console.error('[UIManager] Failed to setup ML Chart Enhancer:', error);
      }
    }
    
    addMLControlPanel() {
      if (!this.mlChartEnhancer) return;
      
      // Find a suitable location (after filters, before charts)
      const filtersCard = document.querySelector('.card:has(#filters-heading)');
      if (!filtersCard) return;
      
      // Create control panel element
      const controlPanel = document.createElement('div');
      controlPanel.className = 'card ml-enhancer-panel';
      controlPanel.innerHTML = this.mlChartEnhancer.createControlPanel();
      
      // Insert after filters
      filtersCard.parentNode.insertBefore(controlPanel, filtersCard.nextSibling);
      
      // Attach event listeners
      this.mlChartEnhancer.attachControlPanelListeners(controlPanel, () => {
        // Re-enhance all charts when settings change
        this.enhanceAllCharts();
      });
    }
    
    async enhanceAllCharts() {
      if (!this.mlChartEnhancer) return;
      
      try {
        const enhanceOptions = {
          sensorIds: this.state.selectedSensor ? [this.state.selectedSensor] : [],
          metrics: Array.from(this.state.metrics),
          unitId: this.state.selectedUnit,
          timeRange: {
            start: null, // Will be calculated based on hours
            end: new Date()
          }
        };
        
        // Enhance data graph chart
        const dataGraphChart = this.charts.get('dataGraph');
        if (dataGraphChart) {
          await this.mlChartEnhancer.enhanceChart(dataGraphChart, {
            ...enhanceOptions,
            chartType: 'timeseries'
          });
        }
        
        // Enhance comparison chart
        const comparisonChart = this.charts.get('comparison');
        if (comparisonChart) {
          await this.mlChartEnhancer.enhanceChart(comparisonChart, {
            ...enhanceOptions,
            chartType: 'comparison'
          });
        }
        
        // Enhance trends chart
        const trendsChart = this.charts.get('trends');
        if (trendsChart) {
          await this.mlChartEnhancer.enhanceChart(trendsChart, {
            ...enhanceOptions,
            chartType: 'statistics'
          });
        }
        
        console.log('[UIManager] All charts enhanced with ML features');
      } catch (error) {
        console.error('[UIManager] Failed to enhance charts:', error);
      }
    }

    // --------------------------------------------------------------------------
    // Environmental Overview Chart (ML-Enhanced)
    // --------------------------------------------------------------------------
    
    async setupEnvironmentalOverviewChart() {
      try {
        // Check if EnvironmentalOverviewChart is available
        if (typeof EnvironmentalOverviewChart === 'undefined') {
          console.warn('[UIManager] EnvironmentalOverviewChart not loaded');
          return;
        }
        
        // Initialize the chart
        this.environmentalOverviewChart = new EnvironmentalOverviewChart('environmental-overview-canvas');
        
        // Load data with current unit selection
        await this.environmentalOverviewChart.init(this.state.selectedUnit);
        
        console.log('[UIManager] Environmental Overview Chart initialized');
      } catch (error) {
        console.error('[UIManager] Failed to setup Environmental Overview Chart:', error);
      }
    }
    
    async refreshEnvironmentalOverview() {
      if (this.environmentalOverviewChart) {
        try {
          await this.environmentalOverviewChart.refresh(this.state.selectedUnit);
        } catch (error) {
          console.error('[UIManager] Failed to refresh Environmental Overview:', error);
        }
      }
    }

    // --------------------------------------------------------------------------
    // Phase D: Component Refresh
    // --------------------------------------------------------------------------

    /**
     * Refresh all Phase D components with current data
     */
    async refreshPhaseD_Components(seriesData) {
      try {
        // Refresh VPD Zones Chart
        await this.refreshVPDZonesChart(seriesData);

        // Refresh Correlation Matrix
        this.refreshCorrelationMatrix(seriesData);

        // Refresh Anomaly Panel (if using IntelligentAnomalyPanel)
        this.refreshAnomalyPanel();
      } catch (error) {
        console.error('[UIManager] Failed to refresh Phase D components:', error);
      }
    }

    /**
     * Refresh VPD Zones Chart
     */
    async refreshVPDZonesChart(seriesData) {
      if (!this.vpdZonesChart) return;

      try {
        // Get VPD history data
        const hours = parseInt(this.elements.vpdZonesRange?.value || '168');
        const series = seriesData?.series || [];

        // Calculate VPD values from temperature and humidity
        const vpdHistory = [];

        for (const reading of series) {
          const temp = reading.temperature;
          const humidity = reading.humidity;

          // Prefer VPD from backend (enrichment processor adds it)
          let vpd = reading.vpd;

          // Fallback: calculate if backend didn't provide VPD
          if ((vpd === null || vpd === undefined) && typeof temp === 'number' && typeof humidity === 'number') {
            // Magnus formula: VPD = SVP × (1 - RH/100), SVP = 0.6108 × exp(17.27 × T / (T + 237.3))
            const satVP = 0.6108 * Math.exp((17.27 * temp) / (temp + 237.3));
            vpd = satVP * (1 - humidity / 100);
          }

          if (vpd !== null && vpd !== undefined && !isNaN(vpd)) {
            vpdHistory.push({
              timestamp: reading.timestamp,
              vpd: vpd
            });
          }
        }

        // Update the chart
        this.vpdZonesChart.update(vpdHistory);
      } catch (error) {
        console.error('[UIManager] Failed to refresh VPD Zones Chart:', error);
      }
    }

    /**
     * Refresh Sensor Correlation Matrix
     */
    refreshCorrelationMatrix(seriesData) {
      if (!this.correlationMatrix) return;

      try {
        const series = seriesData?.series || [];

        // Build aligned arrays (same indices -> same timestamp)
        const sensorHistory = {
          temperature: [],
          humidity: [],
          soil_moisture: [],
          co2_level: [],
          light_level: [],
          vpd: [],
        };

        const asNumberOrNull = (value) => (typeof value === 'number' && !isNaN(value) ? value : null);
        const numericCount = (arr) => arr.reduce((count, v) => count + (typeof v === 'number' && !isNaN(v) ? 1 : 0), 0);

        for (const reading of series) {
          const temp = asNumberOrNull(reading.temperature);
          const humidity = asNumberOrNull(reading.humidity);
          const soil = asNumberOrNull(reading.soil_moisture);

          const co2 = asNumberOrNull(reading.co2_level ?? reading.co2_ppm ?? reading.co2);
          const light = asNumberOrNull(reading.light_level ?? reading.lux ?? reading.illuminance);

          let vpd = null;
          if (temp !== null && humidity !== null) {
            const satVP = 0.6108 * Math.exp((17.27 * temp) / (temp + 237.3));
            const actualVP = satVP * (humidity / 100);
            vpd = asNumberOrNull(satVP - actualVP);
          }

          sensorHistory.temperature.push(temp);
          sensorHistory.humidity.push(humidity);
          sensorHistory.soil_moisture.push(soil);
          sensorHistory.co2_level.push(co2);
          sensorHistory.light_level.push(light);
          sensorHistory.vpd.push(vpd);
        }

        // Remove sensor types with insufficient numeric samples
        for (const [key, values] of Object.entries(sensorHistory)) {
          if (numericCount(values) < 2) delete sensorHistory[key];
        }

        // Update with calculated correlations
        this.correlationMatrix.updateFromSensorData(sensorHistory);
      } catch (error) {
        console.error('[UIManager] Failed to refresh Correlation Matrix:', error);
      }
    }

    /**
     * Refresh Intelligent Anomaly Panel
     */
    refreshAnomalyPanel() {
      if (!this.anomalyPanel) return;

      try {
        // Convert local anomalies to the format expected by IntelligentAnomalyPanel
        const enhancedAnomalies = this.anomalies.map(a => ({
          ...a,
          sensor_type: this.guessSensorType(a.sensor_id),
          type: this.classifyAnomalyType(a),
          severity: this.calculateSeverity(a),
          deviation: a.value && a.threshold ?
            ((a.value - a.threshold) / a.threshold) * 100 : undefined
        }));

        this.anomalyPanel.update(enhancedAnomalies);
      } catch (error) {
        console.error('[UIManager] Failed to refresh Anomaly Panel:', error);
      }
    }

    /**
     * Guess sensor type from sensor ID or name
     */
    guessSensorType(sensorId) {
      const sensor = this.sensors.find(s =>
        (s.sensor_id || s.id) === sensorId ||
        String(s.sensor_id || s.id) === String(sensorId)
      );

      if (sensor?.sensor_type) return sensor.sensor_type;
      if (sensor?.type) return sensor.type;

      // Try to guess from name
      const name = (sensor?.name || '').toLowerCase();
      if (name.includes('temp')) return 'temperature';
      if (name.includes('humid')) return 'humidity';
      if (name.includes('soil') || name.includes('moisture')) return 'soil_moisture';
      if (name.includes('co2')) return 'co2_level';
      if (name.includes('light') || name.includes('lux')) return 'light_level';

      return 'unknown';
    }

    /**
     * Classify anomaly type based on its characteristics
     */
    classifyAnomalyType(anomaly) {
      if (!anomaly) return 'unknown';

      const message = (anomaly.message || '').toLowerCase();

      if (message.includes('high') || message.includes('spike') || message.includes('above')) {
        return 'spike';
      }
      if (message.includes('low') || message.includes('drop') || message.includes('below')) {
        return 'drop';
      }
      if (message.includes('threshold') || message.includes('exceeded')) {
        return 'threshold_breach';
      }
      if (message.includes('drift')) {
        return 'sensor_drift';
      }
      if (message.includes('correlation')) {
        return 'correlation_break';
      }
      if (message.includes('offline') || message.includes('disconnect')) {
        return 'offline';
      }

      return 'pattern_anomaly';
    }

    /**
     * Calculate anomaly severity
     */
    calculateSeverity(anomaly) {
      if (!anomaly || !anomaly.value || !anomaly.threshold) return 'medium';

      const deviation = Math.abs(anomaly.value - anomaly.threshold) / anomaly.threshold;

      if (deviation > 0.5) return 'critical';
      if (deviation > 0.3) return 'high';
      if (deviation > 0.15) return 'medium';
      return 'low';
    }

    // --------------------------------------------------------------------------
    // Cleanup
    // --------------------------------------------------------------------------

    destroy() {
      // Persist state before cleanup
      this.persistState();

      // Destroy Environmental Overview Chart
      if (this.environmentalOverviewChart) {
        try {
          this.environmentalOverviewChart.destroy();
        } catch (error) {
          console.warn('[UIManager] Error destroying Environmental Overview Chart:', error);
        }
        this.environmentalOverviewChart = null;
      }

      // Destroy Phase D Components
      if (this.vpdZonesChart) {
        try { this.vpdZonesChart.destroy(); } catch {}
        this.vpdZonesChart = null;
      }
      if (this.correlationMatrix) {
        try { this.correlationMatrix.destroy(); } catch {}
        this.correlationMatrix = null;
      }
      if (this.anomalyPanel) {
        try { this.anomalyPanel.destroy(); } catch {}
        this.anomalyPanel = null;
      }

      // Destroy charts using chart helper if available
      if (this.chartHelper && typeof this.chartHelper.destroyCharts === 'function') {
        try {
          this.chartHelper.destroyCharts();
        } catch (error) {
          console.warn('[UIManager] Error destroying charts with helper:', error);
        }
      } else {
        // Fallback to manual chart destruction
        this.charts.forEach(chart => {
          try { chart.destroy(); } catch {}
        });
        this.charts.clear();
      }

      // Unsubscribe from socket events
      for (const unsub of this.unsubscribeFunctions) {
        try { unsub(); } catch {}
      }
      this.unsubscribeFunctions = [];

      super.destroy();
    }
  }

  window.SensorAnalyticsUIManager = SensorAnalyticsUIManager;
})();
