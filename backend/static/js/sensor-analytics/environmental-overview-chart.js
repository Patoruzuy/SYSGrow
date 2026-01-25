/**
 * Environmental Overview Chart with ML Forecast and Plant Health
 * 
 * Displays temperature, humidity, soil moisture, and plant health over time
 * Features:
 * - 24-hour historical data with environmental metrics
 * - Plant health score overlay (0-100)
 * - 6-hour ML forecast (when climate_optimizer model available)
 * - Confidence bands
 * - ML enhancement toggle
 * - Plant health trend indicators
 * - "Why this prediction?" tooltips
 */

class EnvironmentalOverviewChart {
  constructor(canvasId, options = {}) {
    this.canvasId = canvasId;
    this.canvas = document.getElementById(canvasId);
    if (!this.canvas) {
      console.error(`Canvas element with id "${canvasId}" not found`);
      return;
    }
    
    this.chart = null;
    this.unitId = options.unitId || null;
    this.mlEnabled = false;
    this.mlModelAvailable = false;
    this.forecastData = null;
    this.historicalData = null;
    this.plantHealthData = null;
    this.selectedPlants = [];
    this.photoperiodSummary = null;
    this.historyMeta = { start: null, end: null, hours: null };

    this.showControls = options.showControls !== false;
    this.allowForecast = options.showForecast !== false;
    this.onDataLoaded = typeof options.onDataLoaded === 'function' ? options.onDataLoaded : null;

    this.timeRangeHours = Number.isFinite(options.timeRangeHours) ? options.timeRangeHours : 24;
    this.pointsPerHour = Number.isFinite(options.pointsPerHour) ? options.pointsPerHour : 12; // 5-min samples
    
    // UI elements
    this.toggleButton = null;
    this.statusIndicator = null;
    this.alignmentBadge = null;
    
    // Chart colors
    this.colors = {
      temperature: { main: '#ff6b6b', forecast: 'rgba(255, 107, 107, 0.4)', band: 'rgba(255, 107, 107, 0.1)' },
      humidity: { main: '#4dabf7', forecast: 'rgba(77, 171, 247, 0.4)', band: 'rgba(77, 171, 247, 0.1)' },
      soil_moisture: { main: '#8b5a2b', forecast: 'rgba(139, 90, 43, 0.4)', band: 'rgba(139, 90, 43, 0.1)' },
      plant_health: { main: '#51cf66', secondary: '#37b24d', tertiary: '#2f9e44' }
    };
  }

  async init(unitId) {
    this.unitId = unitId;
    
    // Check ML model availability (only when controls/forecast are enabled).
    if (this.showControls && this.allowForecast) {
      await this.checkMLAvailability();
    } else {
      this.mlModelAvailable = false;
    }
    
    // Create UI controls
    this.createControls();
    
    // Load historical data
    await this.loadHistoricalData(this.timeRangeHours);
    
    // Initialize chart
    this.renderChart();
    
    // Load forecast if ML enabled
    if (this.mlEnabled && this.mlModelAvailable) {
      await this.loadForecast();
    }
  }

  async checkMLAvailability() {
    try {
      // Use MLStatus if available (from ml_status.js)
      if (window.MLStatus) {
        await window.MLStatus.checkStatus();
        this.mlModelAvailable = window.MLStatus.isAvailable('climate_optimizer');
        
        const model = window.MLStatus.getModel('climate_optimizer');
        if (model && model.confidence) {
          console.log(`Climate optimizer available with ${(model.confidence * 100).toFixed(0)}% confidence`);
        }
      } else {
        // Fallback to direct API call
        const data = await API.ML.getModelsStatus();
        this.mlModelAvailable = data.models?.climate_optimizer?.active || false;
      }
    } catch (error) {
      console.error('Error checking ML availability:', error);
      this.mlModelAvailable = false;
    }
  }

  createControls() {
    const container = this.canvas.closest('.card');
    if (!container) return;
    
    const header = container.querySelector('.card-header');
    if (!header) return;

    const chartControls = header.querySelector('.chart-controls');
    
    // Create control group
    const controlGroup = document.createElement('div');
    controlGroup.className = 'ml-chart-controls';
    controlGroup.style.cssText = 'display: flex; align-items: center; gap: 12px;';

    // Photoperiod / schedule↔lux alignment badge (populated after history load)
    this.alignmentBadge = document.createElement('div');
    this.alignmentBadge.className = 'photoperiod-alignment-badge';
    this.alignmentBadge.style.cssText = [
      'display: none',
      'align-items: center',
      'gap: 6px',
      'font-size: 0.8rem',
      'line-height: 1.1',
      'padding: 3px 10px',
      'border-radius: 9999px',
      'border: 1px solid rgba(255, 193, 7, 0.35)',
      'background: rgba(255, 193, 7, 0.12)',
      'color: #b56b00'
    ].join('; ');
    this.alignmentBadge.innerHTML = `<i class="fas fa-sun"></i><span>Day/Night</span>`;
    controlGroup.appendChild(this.alignmentBadge);
    
    // ML status indicator
    if (this.showControls && this.allowForecast && this.mlModelAvailable) {
      this.statusIndicator = document.createElement('div');
      this.statusIndicator.className = 'ml-status-badge';
      this.statusIndicator.innerHTML = `
        <i class="fas fa-brain"></i>
        <span>ML Active</span>
      `;
      this.statusIndicator.style.cssText = 'font-size: 0.875rem; color: #28a745; display: flex; align-items: center; gap: 6px;';
      controlGroup.appendChild(this.statusIndicator);
      
      // Forecast toggle button
      this.toggleButton = document.createElement('button');
      this.toggleButton.type = 'button';
      this.toggleButton.className = 'btn btn-sm btn-outline-primary ml-forecast-toggle';
      this.toggleButton.innerHTML = `
        <i class="fas fa-chart-line"></i>
        <span>Show Forecast</span>
      `;
      this.toggleButton.addEventListener('click', () => this.toggleForecast());
      controlGroup.appendChild(this.toggleButton);
    } else if (this.showControls && this.allowForecast) {
      // Show "Train model" hint
      const hint = document.createElement('small');
      hint.className = 'text-muted';
      hint.innerHTML = `<i class="fas fa-info-circle"></i> Train climate model to enable forecast`;
      controlGroup.appendChild(hint);
    }

    // Keep all right-side controls grouped together on dashboards that use `.chart-controls`.
    const target = chartControls || header;
    if (!chartControls) {
      controlGroup.style.marginLeft = 'auto';
    }
    target.appendChild(controlGroup);
  }

  async loadHistoricalData(hours = this.timeRangeHours) {
    try {
      const params = new URLSearchParams({
        hours: hours,
        limit: Math.min(2000, Math.max(50, Math.round(hours * this.pointsPerHour)))
      });
      
      if (this.unitId) {
        params.append('unit_id', this.unitId);
      }
      
      let result = null;

      // Prefer enriched endpoint (photoperiod/day-night overlays).
      try {
        result = await API.Analytics.getSensorsHistoryEnriched({
          unit_id: this.unitId,
          hours: hours
        });
      } catch (_) {
        result = null;
      }

      if (!result || !result.data) {
        // Fallback to base history endpoint.
        result = await API.Analytics.getSensorsHistory({
          unit_id: this.unitId,
          hours: hours
        });
      }

      if (result && result.data) {
        this.historicalData = result.data;
        this.photoperiodSummary = result.photoperiod || null;
        this.historyMeta = {
          start: result.start || null,
          end: result.end || null,
          hours: hours,
        };
        this.updatePhotoperiodBadge();
      } else {
        const errorMsg = result?.error?.message || 'Unknown error';
        console.error('Failed to load historical data:', errorMsg);
        this.historicalData = { timestamps: [], temperature: [], humidity: [], soil_moisture: [] };
        this.photoperiodSummary = null;
        this.historyMeta = { start: null, end: null, hours: hours };
        this.updatePhotoperiodBadge();
      }
    } catch (error) {
      console.error('Error loading historical data:', error);
      this.historicalData = { timestamps: [], temperature: [], humidity: [], soil_moisture: [] };
      this.photoperiodSummary = null;
      this.historyMeta = { start: null, end: null, hours: hours };
      this.updatePhotoperiodBadge();
    }

    // Notify dashboards that want to compute additional insights from this payload.
    if (this.onDataLoaded) {
      try {
        this.onDataLoaded({
          unitId: this.unitId || null,
          start: this.historyMeta.start,
          end: this.historyMeta.end,
          hours: this.historyMeta.hours,
          data: this.historicalData,
          photoperiod: this.photoperiodSummary,
        });
      } catch (err) {
        console.warn('[EnvironmentalOverviewChart] onDataLoaded callback failed:', err);
      }
    }
    
    // Also load plant health data
    await this.loadPlantHealthData();
  }
  
  async loadPlantHealthData() {
    if (!this.unitId) {
      this.plantHealthData = null;
      return;
    }
    
    try {
      // First, get list of plants in this unit
      const plantsResult = await API.Plant.listPlantsInUnit(this.unitId);
      
      if (!plantsResult || !plantsResult.plants) {
        console.log('No plants in this unit');
        this.plantHealthData = null;
        return;
      }
      
      const plants = plantsResult.plants;
      if (plants.length === 0) {
        this.plantHealthData = null;
        return;
      }
      
      // Get health history for each plant (last 7 days to cover the 24h window)
      const healthPromises = plants.map(plant => 
        API.Plant.getHealthHistory(plant.plant_id, 7)
          .then(result => ({
            plant_id: plant.plant_id,
            plant_name: plant.plant_name,
            observations: result?.observations || []
          }))
          .catch(err => {
            console.warn(`Failed to load health for plant ${plant.plant_id}:`, err);
            return { plant_id: plant.plant_id, plant_name: plant.plant_name, observations: [] };
          })
      );
      
      const healthData = await Promise.all(healthPromises);
      
      // Combine and process health observations into time series
      this.plantHealthData = this.processPlantHealthData(healthData);
      this.selectedPlants = plants.map(p => p.plant_id);
      
    } catch (error) {
      console.error('Error loading plant health data:', error);
      this.plantHealthData = null;
    }
  }
  
  processPlantHealthData(healthDataArray) {
    // Combine all observations and group by timestamp (rounded to nearest 5 minutes)
    const timestampMap = new Map();
    
    healthDataArray.forEach(plantData => {
      plantData.observations.forEach(obs => {
        const timestamp = new Date(obs.timestamp || obs.recorded_at);
        const roundedTime = new Date(Math.round(timestamp.getTime() / 300000) * 300000); // Round to 5 min
        const timeKey = roundedTime.toISOString();
        
        if (!timestampMap.has(timeKey)) {
          timestampMap.set(timeKey, {
            timestamp: roundedTime,
            scores: [],
            plants: []
          });
        }
        
        const entry = timestampMap.get(timeKey);
        entry.scores.push(obs.health_score || obs.score || 75); // Default to 75 if missing
        entry.plants.push(plantData.plant_name);
      });
    });
    
    // Convert to sorted arrays
    const sortedEntries = Array.from(timestampMap.entries())
      .sort((a, b) => new Date(a[0]) - new Date(b[0]));
    
    const timestamps = sortedEntries.map(([_, entry]) => entry.timestamp);
    const scores = sortedEntries.map(([_, entry]) => {
      // Calculate average score for this timestamp
      return entry.scores.reduce((sum, s) => sum + s, 0) / entry.scores.length;
    });
    const plantCounts = sortedEntries.map(([_, entry]) => entry.plants.length);
    
    return { timestamps, scores, plantCounts };
  }

  async loadForecast() {
    if (!this.mlModelAvailable) return;
    
    try {
      const params = { hours_ahead: '6' };
      if (this.unitId) {
        params.unit_id = this.unitId;
      }
      
      const result = await API.ML.getClimateForecast(params);
      
      if (result) {
        this.forecastData = result;
        this.updateChartWithForecast();
      } else {
        console.warn('Forecast unavailable');
      }
    } catch (error) {
      console.error('Error loading forecast:', error);
    }
  }

  renderChart() {
    if (!this.historicalData) return;
    
    const ctx = this.canvas.getContext('2d');
    
    // Prepare datasets
    const datasets = this.buildHistoricalDatasets();
    
    // Chart configuration
    this.chart = new Chart(ctx, {
      type: 'line',
      data: {
        labels: this.historicalData.timestamps.map(ts => new Date(ts)),
        datasets: datasets
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: {
          mode: 'index',
          intersect: false
        },
        plugins: {
          legend: {
            position: 'bottom',
            labels: {
              usePointStyle: true,
              padding: 15,
              font: { size: 12 }
            }
          },
          tooltip: {
            filter: (context) => {
              // Keep tooltip focused on environmental metrics.
              return !context.dataset.isPhotoperiod;
            },
            callbacks: {
              title: (items) => {
                if (!items[0]) return '';
                const ts = items[0].parsed?.x;
                if (!Number.isFinite(ts)) return '';
                return new Date(ts).toLocaleString();
              },
              label: (context) => {
                let label = context.dataset.label || '';
                if (label) label += ': ';
                
                const value = context.parsed.y;
                if (value !== null && value !== undefined) {
                  label += value.toFixed(1);
                  
                  // Add units
                  if (context.dataset.label.includes('Temperature')) {
                    label += ' °C';
                  } else if (context.dataset.label.includes('Humidity') || context.dataset.label.includes('Moisture')) {
                    label += ' %';
                  } else if (context.dataset.label.includes('Plant Health')) {
                    label += '%';
                    // Add status indicator
                    if (value >= 80) {
                      label += ' 🌿 Excellent';
                    } else if (value >= 60) {
                      label += ' ✅ Good';
                    } else if (value >= 40) {
                      label += ' ⚠️ Fair';
                    } else {
                      label += ' ❌ Poor';
                    }
                  }
                  
                  // Add confidence for forecast
                  if (context.dataset.isForecast && this.forecastData?.confidence) {
                    label += ` (${(this.forecastData.confidence * 100).toFixed(0)}% confidence)`;
                  }
                }
                
                return label;
              },
              afterBody: (items) => {
                // Add "Why this prediction?" for forecast points
                if (items.length > 0 && items[0].dataset.isForecast && this.forecastData?.explanation) {
                  return `\n💡 ${this.forecastData.explanation}`;
                }
                return '';
              }
            }
          }
        },
        scales: {
          x: {
            type: 'time',
            time: {
              unit: 'hour',
              displayFormats: {
                hour: 'HH:mm'
              }
            },
            title: {
              display: true,
              text: 'Time'
            }
          },
          y: {
            type: 'linear',
            position: 'left',
            beginAtZero: false,
            title: {
              display: true,
              text: 'Temperature (°C) / Humidity (%) / Moisture (%)',
              font: { size: 11 }
            }
          },
          'y-health': {
            type: 'linear',
            position: 'right',
            min: 0,
            max: 100,
            title: {
              display: true,
              text: 'Plant Health Score',
              color: '#51cf66',
              font: { size: 11, weight: 'bold' }
            },
            ticks: {
              color: '#51cf66',
              callback: function(value) {
                return value + '%';
              }
            },
            grid: {
              drawOnChartArea: false // Don't draw grid lines for this axis
            }
          },
          'y-photoperiod': {
            type: 'linear',
            position: 'right',
            min: 0,
            max: 1,
            display: false,
            grid: {
              drawOnChartArea: false
            }
          }
        }
      }
    });
  }

  buildHistoricalDatasets() {
    const datasets = [];

    // Photoperiod / day-night shading overlay (0/1 series).
    if (Array.isArray(this.historicalData.is_day) && this.historicalData.is_day.length > 0) {
      const isDay = this.historicalData.is_day;
      const label = this.photoperiodSummary?.source === 'lux' ? 'Day/Night (Lux)' : 'Day/Night (Schedule)';

      datasets.push({
        label: label,
        data: isDay,
        borderColor: 'rgba(255, 193, 7, 0)',
        backgroundColor: 'rgba(255, 193, 7, 0.06)',
        borderWidth: 0,
        pointRadius: 0,
        stepped: true,
        fill: true,
        tension: 0,
        yAxisID: 'y-photoperiod',
        order: -100,
        isPhotoperiod: true
      });
    }
    
    if (this.historicalData.temperature?.length > 0) {
      datasets.push({
        label: 'Temperature',
        data: this.historicalData.temperature,
        borderColor: this.colors.temperature.main,
        backgroundColor: 'transparent',
        borderWidth: 2,
        pointRadius: 0,
        pointHoverRadius: 5,
        tension: 0.4,
        spanGaps: true,
        yAxisID: 'y'
      });
    }
    
    if (this.historicalData.humidity?.length > 0) {
      datasets.push({
        label: 'Humidity',
        data: this.historicalData.humidity,
        borderColor: this.colors.humidity.main,
        backgroundColor: 'transparent',
        borderWidth: 2,
        pointRadius: 0,
        pointHoverRadius: 5,
        tension: 0.4,
        spanGaps: true,
        yAxisID: 'y'
      });
    }
    
    if (this.historicalData.soil_moisture?.length > 0) {
      datasets.push({
        label: 'Soil Moisture',
        data: this.historicalData.soil_moisture,
        borderColor: this.colors.soil_moisture.main,
        backgroundColor: 'transparent',
        borderWidth: 2,
        pointRadius: 0,
        pointHoverRadius: 5,
        tension: 0.4,
        spanGaps: true,
        yAxisID: 'y'
      });
    }
    
    // Add plant health if available
    if (this.plantHealthData && this.plantHealthData.scores.length > 0) {
      // Map plant health timestamps to chart data points
      const healthData = this.historicalData.timestamps.map(ts => {
        const timestamp = new Date(ts);
        // Find closest health observation
        let closestIndex = -1;
        let closestDiff = Infinity;
        
        this.plantHealthData.timestamps.forEach((healthTs, idx) => {
          const diff = Math.abs(healthTs - timestamp);
          if (diff < closestDiff && diff < 600000) { // Within 10 minutes
            closestDiff = diff;
            closestIndex = idx;
          }
        });
        
        return closestIndex >= 0 ? this.plantHealthData.scores[closestIndex] : null;
      });
      
      datasets.push({
        label: 'Plant Health Score',
        data: healthData,
        borderColor: this.colors.plant_health.main,
        backgroundColor: 'rgba(81, 207, 102, 0.1)',
        borderWidth: 3,
        pointRadius: 4,
        pointHoverRadius: 6,
        pointBackgroundColor: this.colors.plant_health.main,
        pointBorderColor: '#fff',
        pointBorderWidth: 2,
        tension: 0.4,
        yAxisID: 'y-health',
        order: 0 // Draw on top
      });
    }
    
    return datasets;
  }

  updatePhotoperiodBadge() {
    if (!this.alignmentBadge) return;

    const summary = this.photoperiodSummary;
    const agreementRate = summary?.agreement_rate;
    const schedulePresent = summary?.schedule_present;
    const sensorEnabled = summary?.sensor_enabled;

    if (!schedulePresent || !sensorEnabled || agreementRate === null || agreementRate === undefined) {
      this.alignmentBadge.style.display = 'none';
      return;
    }

    const pct = Math.round(Number(agreementRate) * 100);
    const startOffset = summary?.start_offset_minutes;
    const endOffset = summary?.end_offset_minutes;

    const fmtOffset = (value) => {
      const n = Number(value);
      if (!Number.isFinite(n)) return null;
      const rounded = Math.round(n);
      const sign = rounded > 0 ? '+' : '';
      return `${sign}${rounded}m`;
    };

    const parts = [`Align ${pct}%`];
    const startText = fmtOffset(startOffset);
    const endText = fmtOffset(endOffset);
    if (startText !== null) parts.push(`start ${startText}`);
    if (endText !== null) parts.push(`end ${endText}`);

    this.alignmentBadge.style.display = 'inline-flex';
    this.alignmentBadge.innerHTML = `<i class="fas fa-adjust"></i><span>${parts.join(' · ')}</span>`;

    const scheduleWindow = `${summary?.schedule_day_start || '--:--'}–${summary?.schedule_day_end || '--:--'}`;
    const luxThreshold = summary?.lux_threshold;
    const dif = summary?.dif_c;
    const difText = Number.isFinite(Number(dif)) ? `DIF ${Number(dif).toFixed(2)}°C` : null;

    const titleLines = [
      `Schedule window: ${scheduleWindow} (${summary?.schedule_enabled ? 'enabled' : 'disabled'})`,
      `Lux threshold: ${luxThreshold ?? 'n/a'}`,
      `Agreement: ${pct}%`,
      startText !== null ? `Start offset: ${startText}` : null,
      endText !== null ? `End offset: ${endText}` : null,
      difText
    ].filter(Boolean);
    this.alignmentBadge.title = titleLines.join('\\n');
  }

  updateChartWithForecast() {
    if (!this.chart || !this.forecastData) return;
    
    const historicalLength = this.historicalData.timestamps.length;
    
    // Generate forecast timestamps (6 hours ahead, hourly intervals)
    const lastTimestamp = new Date(this.historicalData.timestamps[historicalLength - 1]);
    const forecastTimestamps = [];
    for (let i = 1; i <= 6; i++) {
      const forecastTime = new Date(lastTimestamp.getTime() + i * 60 * 60 * 1000);
      forecastTimestamps.push(forecastTime);
    }
    
    // Update labels
    this.chart.data.labels = [
      ...this.historicalData.timestamps.map(ts => new Date(ts)),
      ...forecastTimestamps
    ];

    // Extend photoperiod overlay to match new label length.
    const photoperiodDataset = this.chart.data.datasets.find(ds => ds.isPhotoperiod);
    if (photoperiodDataset && Array.isArray(this.historicalData.is_day)) {
      photoperiodDataset.data = this.historicalData.is_day.concat(Array(forecastTimestamps.length).fill(null));
    }
    
    // Add forecast datasets
    if (this.forecastData.temperature) {
      const forecastData = Array(historicalLength).fill(null).concat(this.forecastData.temperature);
      
      this.chart.data.datasets.push({
        label: 'Temperature Forecast',
        data: forecastData,
        borderColor: this.colors.temperature.forecast,
        backgroundColor: this.colors.temperature.band,
        borderWidth: 2,
        borderDash: [5, 5],
        pointRadius: 3,
        pointHoverRadius: 6,
        pointStyle: 'circle',
        fill: true,
        tension: 0.4,
        yAxisID: 'y',
        isForecast: true
      });
    }
    
    if (this.forecastData.humidity) {
      const forecastData = Array(historicalLength).fill(null).concat(this.forecastData.humidity);
      
      this.chart.data.datasets.push({
        label: 'Humidity Forecast',
        data: forecastData,
        borderColor: this.colors.humidity.forecast,
        backgroundColor: this.colors.humidity.band,
        borderWidth: 2,
        borderDash: [5, 5],
        pointRadius: 3,
        pointHoverRadius: 6,
        pointStyle: 'circle',
        fill: true,
        tension: 0.4,
        yAxisID: 'y',
        isForecast: true
      });
    }
    
    if (this.forecastData.soil_moisture) {
      const forecastData = Array(historicalLength).fill(null).concat(this.forecastData.soil_moisture);
      
      this.chart.data.datasets.push({
        label: 'Soil Moisture Forecast',
        data: forecastData,
        borderColor: this.colors.soil_moisture.forecast,
        backgroundColor: this.colors.soil_moisture.band,
        borderWidth: 2,
        borderDash: [5, 5],
        pointRadius: 3,
        pointHoverRadius: 6,
        pointStyle: 'circle',
        fill: true,
        tension: 0.4,
        yAxisID: 'y',
        isForecast: true
      });
    }
    
    this.chart.update();
  }

  removeForecastFromChart() {
    if (!this.chart) return;
    
    // Remove forecast datasets
    this.chart.data.datasets = this.chart.data.datasets.filter(ds => !ds.isForecast);
    
    // Restore original labels
    this.chart.data.labels = this.historicalData.timestamps.map(ts => new Date(ts));

    // Restore photoperiod overlay length.
    const photoperiodDataset = this.chart.data.datasets.find(ds => ds.isPhotoperiod);
    if (photoperiodDataset && Array.isArray(this.historicalData.is_day)) {
      photoperiodDataset.data = this.historicalData.is_day;
    }
    
    this.chart.update();
  }

  async setTimeRange(hours) {
    const parsed = parseInt(hours, 10);
    if (!Number.isFinite(parsed) || parsed <= 0) {
      return;
    }
    this.timeRangeHours = parsed;
    await this.refresh();
  }

  async toggleForecast() {
    if (!this.allowForecast || !this.mlModelAvailable) return;
    
    this.mlEnabled = !this.mlEnabled;
    
    if (this.mlEnabled) {
      // Show forecast
      this.toggleButton.innerHTML = `
        <i class="fas fa-eye-slash"></i>
        <span>Hide Forecast</span>
      `;
      this.toggleButton.classList.add('active');
      
      if (!this.forecastData) {
        await this.loadForecast();
      } else {
        this.updateChartWithForecast();
      }
    } else {
      // Hide forecast
      this.toggleButton.innerHTML = `
        <i class="fas fa-chart-line"></i>
        <span>Show Forecast</span>
      `;
      this.toggleButton.classList.remove('active');
      
      this.removeForecastFromChart();
    }
  }

  async refresh(unitId = null) {
    if (unitId !== null) {
      this.unitId = unitId;
    }
    
    await this.loadHistoricalData();
    
    if (this.chart) {
      // Rebuild datasets
      this.chart.data.labels = this.historicalData.timestamps.map(ts => new Date(ts));
      this.chart.data.datasets = this.buildHistoricalDatasets();
      
      // Reload forecast if enabled
      if (this.allowForecast && this.mlEnabled && this.mlModelAvailable) {
        await this.loadForecast();
      }
      
      this.chart.update();
    } else {
      this.renderChart();
    }
  }

  destroy() {
    if (this.chart) {
      this.chart.destroy();
      this.chart = null;
    }
  }
}

// Expose globally for dashboards that reference `window.EnvironmentalOverviewChart`.
try {
  if (typeof window !== 'undefined') {
    window.EnvironmentalOverviewChart = EnvironmentalOverviewChart;
  }
} catch (_) {
  // no-op
}

// Export for use in main.js
if (typeof module !== 'undefined' && module.exports) {
  module.exports = EnvironmentalOverviewChart;
}
