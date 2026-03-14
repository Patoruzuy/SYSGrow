/**
 * Sensor Correlation Matrix Component
 * ============================================================================
 * A heatmap showing correlations between all sensor types.
 *
 * Features:
 * - Color-coded correlation coefficients (-1 to +1)
 * - Hover tooltips with correlation details
 * - Educational explanations for correlations
 * - Responsive grid layout
 *
 * Usage:
 *   const matrix = new SensorCorrelationMatrix('matrix-container', {
 *     showLabels: true,
 *     showTooltips: true
 *   });
 *   matrix.update(correlationData);
 */
(function() {
  'use strict';

  class SensorCorrelationMatrix {
    constructor(containerId, options = {}) {
      this.containerId = containerId;
      this.container = document.getElementById(containerId);

      if (!this.container) {
        console.warn(`[SensorCorrelationMatrix] Container "${containerId}" not found`);
        return;
      }

      this.options = {
        showLabels: options.showLabels !== false,
        showTooltips: options.showTooltips !== false,
        showLegend: options.showLegend !== false,
        cellSize: options.cellSize || 40,
        animationDuration: options.animationDuration || 300,
        ...options
      };

      this.data = null;
      this.tooltip = null;

      // Sensor type definitions with icons and labels
      this.sensorTypes = {
        temperature: {
          label: 'Temp',
          fullLabel: 'Temperature',
          icon: 'fas fa-thermometer-half',
          unit: '°C'
        },
        humidity: {
          label: 'Humid',
          fullLabel: 'Humidity',
          icon: 'fas fa-tint',
          unit: '%'
        },
        soil_moisture: {
          label: 'Soil',
          fullLabel: 'Soil Moisture',
          icon: 'fas fa-water',
          unit: '%'
        },
        co2_level: {
          label: 'CO2',
          fullLabel: 'CO2 Level',
          icon: 'fas fa-cloud',
          unit: 'ppm'
        },
        light_level: {
          label: 'Light',
          fullLabel: 'Light Level',
          icon: 'fas fa-sun',
          unit: 'lux'
        },
        vpd: {
          label: 'VPD',
          fullLabel: 'Vapor Pressure Deficit',
          icon: 'fas fa-wind',
          unit: 'kPa'
        }
      };

      // Educational correlation explanations
      this.correlationExplanations = {
        'temperature_humidity': {
          positive: 'Unusual - typically inverse. May indicate external heat source affecting both.',
          negative: 'Expected - higher temperatures generally reduce relative humidity.',
          neutral: 'Little relationship detected between these sensors.'
        },
        'temperature_vpd': {
          positive: 'Expected - higher temperatures increase VPD (vapor pressure deficit).',
          negative: 'Unusual - may indicate measurement issues.',
          neutral: 'Little relationship detected.'
        },
        'humidity_vpd': {
          positive: 'Unusual - typically inverse relationship.',
          negative: 'Expected - higher humidity reduces VPD.',
          neutral: 'Little relationship detected.'
        },
        'light_level_temperature': {
          positive: 'Expected - grow lights generate heat, increasing temperature.',
          negative: 'May indicate effective cooling when lights are on.',
          neutral: 'Good thermal management or LED lights with minimal heat.'
        },
        'soil_moisture_humidity': {
          positive: 'May indicate irrigation affecting ambient humidity.',
          negative: 'Unusual - typically no direct inverse relationship.',
          neutral: 'Independent systems working as expected.'
        },
        'co2_level_light_level': {
          positive: 'May indicate CO2 enrichment during light period.',
          negative: 'Expected if plants actively consuming CO2 during photosynthesis.',
          neutral: 'No active CO2 enrichment or stable levels.'
        },
        'default': {
          positive: 'These sensors tend to increase together.',
          negative: 'When one increases, the other tends to decrease.',
          neutral: 'These sensors show little correlation.'
        }
      };

      this._initContainer();
      this._createTooltip();
    }

    /**
     * Initialize the container structure
     */
    _initContainer() {
      if (!this.container) return;

      this.container.innerHTML = `
        <div class="correlation-matrix">
          <div class="correlation-matrix__grid"></div>
          ${this.options.showLegend ? '<div class="correlation-matrix__legend"></div>' : ''}
        </div>
      `;

      this.gridEl = this.container.querySelector('.correlation-matrix__grid');
      this.legendEl = this.container.querySelector('.correlation-matrix__legend');

      if (this.legendEl) {
        this._renderLegend();
      }
    }

    /**
     * Create tooltip element
     */
    _createTooltip() {
      if (!this.options.showTooltips) return;

      this.tooltip = document.createElement('div');
      this.tooltip.className = 'correlation-tooltip';
      this.tooltip.style.display = 'none';
      document.body.appendChild(this.tooltip);
    }

    /**
     * Update with correlation data
     * @param {Object} data - Correlation matrix data
     *   Format: { temperature: { humidity: 0.85, soil_moisture: 0.12, ... }, ... }
     */
    update(data) {
      if (!this.container || !this.gridEl) return;

      this.data = data;
      this._renderMatrix(data);
    }

    /**
     * Render the correlation matrix
     */
    _renderMatrix(data) {
      if (!this.gridEl || !data) return;

      // Get list of sensor types from data
      const sensors = Object.keys(data).filter(key => this.sensorTypes[key]);

      if (sensors.length === 0) {
        this.gridEl.innerHTML = '<div class="correlation-empty">No correlation data available</div>';
        return;
      }

      // Build matrix HTML
      const gridSize = sensors.length + 1; // +1 for headers
      let html = '';

      // Header row
      html += '<div class="correlation-cell correlation-cell--corner"></div>';
      for (const sensor of sensors) {
        const config = this.sensorTypes[sensor];
        html += `
          <div class="correlation-cell correlation-cell--header" title="${config.fullLabel}">
            <i class="${config.icon}"></i>
            ${this.options.showLabels ? `<span>${config.label}</span>` : ''}
          </div>
        `;
      }

      // Data rows
      for (const rowSensor of sensors) {
        const rowConfig = this.sensorTypes[rowSensor];

        // Row header
        html += `
          <div class="correlation-cell correlation-cell--header correlation-cell--row-header" title="${rowConfig.fullLabel}">
            <i class="${rowConfig.icon}"></i>
            ${this.options.showLabels ? `<span>${rowConfig.label}</span>` : ''}
          </div>
        `;

        // Data cells
        for (const colSensor of sensors) {
          const correlation = this._getCorrelation(data, rowSensor, colSensor);
          const colorClass = this._getColorClass(correlation);
          const isDiagonal = rowSensor === colSensor;

          html += `
            <div class="correlation-cell correlation-cell--data ${colorClass} ${isDiagonal ? 'diagonal' : ''}"
                 data-row="${rowSensor}"
                 data-col="${colSensor}"
                 data-value="${correlation !== null ? correlation.toFixed(2) : 'N/A'}"
                 style="--correlation: ${correlation !== null ? Math.abs(correlation) : 0}">
              <span class="correlation-value">${correlation !== null ? correlation.toFixed(2) : '—'}</span>
            </div>
          `;
        }
      }

      this.gridEl.innerHTML = html;
      this.gridEl.style.setProperty('--grid-size', gridSize);

      // Add event listeners for tooltips
      if (this.options.showTooltips) {
        this._attachTooltipListeners();
      }
    }

    /**
     * Get correlation value between two sensors
     */
    _getCorrelation(data, sensor1, sensor2) {
      if (sensor1 === sensor2) return 1; // Self-correlation

      // Try both directions
      if (data[sensor1] && typeof data[sensor1][sensor2] === 'number') {
        return data[sensor1][sensor2];
      }
      if (data[sensor2] && typeof data[sensor2][sensor1] === 'number') {
        return data[sensor2][sensor1];
      }

      return null;
    }

    /**
     * Get color class based on correlation value
     */
    _getColorClass(correlation) {
      if (correlation === null) return 'no-data';
      if (correlation >= 0.7) return 'strong-positive';
      if (correlation >= 0.3) return 'moderate-positive';
      if (correlation > -0.3) return 'neutral';
      if (correlation > -0.7) return 'moderate-negative';
      return 'strong-negative';
    }

    /**
     * Get correlation strength description
     */
    _getStrengthDescription(correlation) {
      if (correlation === null) return 'No data';
      const abs = Math.abs(correlation);
      if (abs >= 0.7) return 'Strong';
      if (abs >= 0.3) return 'Moderate';
      return 'Weak';
    }

    /**
     * Attach tooltip event listeners
     */
    _attachTooltipListeners() {
      if (!this.tooltip) return;

      const cells = this.gridEl.querySelectorAll('.correlation-cell--data:not(.diagonal)');

      cells.forEach(cell => {
        cell.addEventListener('mouseenter', (e) => this._showTooltip(e, cell));
        cell.addEventListener('mouseleave', () => this._hideTooltip());
        cell.addEventListener('mousemove', (e) => this._positionTooltip(e));
      });
    }

    /**
     * Show tooltip for a cell
     */
    _showTooltip(event, cell) {
      if (!this.tooltip) return;

      const rowSensor = cell.dataset.row;
      const colSensor = cell.dataset.col;
      const value = parseFloat(cell.dataset.value);

      const rowConfig = this.sensorTypes[rowSensor];
      const colConfig = this.sensorTypes[colSensor];

      const strength = this._getStrengthDescription(value);
      const direction = value > 0 ? 'positive' : value < 0 ? 'negative' : 'neutral';
      const explanation = this._getExplanation(rowSensor, colSensor, direction);

      this.tooltip.innerHTML = `
        <div class="correlation-tooltip__header">
          <span class="sensor-pair">
            <i class="${rowConfig.icon}"></i> ${rowConfig.fullLabel}
            <span class="vs">↔</span>
            <i class="${colConfig.icon}"></i> ${colConfig.fullLabel}
          </span>
        </div>
        <div class="correlation-tooltip__value">
          <span class="coefficient">${isNaN(value) ? 'N/A' : value.toFixed(3)}</span>
          <span class="strength ${direction}">${strength} ${direction !== 'neutral' ? direction : ''}</span>
        </div>
        <div class="correlation-tooltip__explanation">
          <i class="fas fa-info-circle"></i>
          ${explanation}
        </div>
      `;

      this.tooltip.style.display = 'block';
      this._positionTooltip(event);
    }

    /**
     * Get explanation for a sensor pair
     */
    _getExplanation(sensor1, sensor2, direction) {
      const key1 = `${sensor1}_${sensor2}`;
      const key2 = `${sensor2}_${sensor1}`;

      const explanations = this.correlationExplanations[key1] ||
                          this.correlationExplanations[key2] ||
                          this.correlationExplanations.default;

      return explanations[direction] || explanations.neutral;
    }

    /**
     * Position tooltip near cursor
     */
    _positionTooltip(event) {
      if (!this.tooltip) return;

      const offset = 10;
      const tooltipRect = this.tooltip.getBoundingClientRect();
      const viewportWidth = window.innerWidth;
      const viewportHeight = window.innerHeight;

      let x = event.clientX + offset;
      let y = event.clientY + offset;

      // Adjust if tooltip would go off-screen
      if (x + tooltipRect.width > viewportWidth) {
        x = event.clientX - tooltipRect.width - offset;
      }
      if (y + tooltipRect.height > viewportHeight) {
        y = event.clientY - tooltipRect.height - offset;
      }

      this.tooltip.style.left = `${x}px`;
      this.tooltip.style.top = `${y}px`;
    }

    /**
     * Hide tooltip
     */
    _hideTooltip() {
      if (this.tooltip) {
        this.tooltip.style.display = 'none';
      }
    }

    /**
     * Render the legend
     */
    _renderLegend() {
      if (!this.legendEl) return;

      this.legendEl.innerHTML = `
        <div class="correlation-legend">
          <div class="legend-title">Correlation Strength</div>
          <div class="legend-scale">
            <div class="legend-gradient"></div>
            <div class="legend-labels">
              <span>-1</span>
              <span>0</span>
              <span>+1</span>
            </div>
          </div>
          <div class="legend-descriptions">
            <div class="legend-item">
              <span class="color-dot strong-negative"></span>
              <span>Strong Negative</span>
            </div>
            <div class="legend-item">
              <span class="color-dot neutral"></span>
              <span>No Correlation</span>
            </div>
            <div class="legend-item">
              <span class="color-dot strong-positive"></span>
              <span>Strong Positive</span>
            </div>
          </div>
        </div>
      `;
    }

    /**
     * Update with raw sensor data (calculates correlations)
     * @param {Object} sensorHistory - Object with sensor arrays
     *   Format: { temperature: [values], humidity: [values], ... }
     */
    updateFromSensorData(sensorHistory) {
      if (!sensorHistory) return;

      const correlations = this._calculateCorrelations(sensorHistory);
      this.update(correlations);
    }

    /**
     * Calculate Pearson correlations from sensor history
     */
    _calculateCorrelations(sensorHistory) {
      const numericCount = (arr) => arr.reduce((count, v) => count + (typeof v === 'number' && !isNaN(v) ? 1 : 0), 0);

      const sensors = Object.keys(sensorHistory).filter((key) => {
        const values = sensorHistory[key];
        return Array.isArray(values) && numericCount(values) > 1;
      });

      const correlations = {};

      for (const sensor1 of sensors) {
        correlations[sensor1] = {};

        for (const sensor2 of sensors) {
          if (sensor1 === sensor2) {
            correlations[sensor1][sensor2] = 1;
            continue;
          }

          const values1 = sensorHistory[sensor1];
          const values2 = sensorHistory[sensor2];

          correlations[sensor1][sensor2] = this._pearsonCorrelation(values1, values2);
        }
      }

      return correlations;
    }

    /**
     * Calculate Pearson correlation coefficient
     */
    _pearsonCorrelation(x, y) {
      const minLen = Math.min(x.length, y.length);
      if (minLen === 0) return null;

      let n = 0;
      let sumX = 0, sumY = 0, sumXY = 0;
      let sumX2 = 0, sumY2 = 0;

      for (let i = 0; i < minLen; i++) {
        const xiRaw = x[i];
        const yiRaw = y[i];

        const xi = typeof xiRaw === 'number' ? xiRaw : xiRaw?.value;
        const yi = typeof yiRaw === 'number' ? yiRaw : yiRaw?.value;

        if (typeof xi !== 'number' || typeof yi !== 'number') continue;
        if (isNaN(xi) || isNaN(yi)) continue;

        n += 1;
        sumX += xi;
        sumY += yi;
        sumXY += xi * yi;
        sumX2 += xi * xi;
        sumY2 += yi * yi;
      }

      if (n < 2) return null;

      const numerator = n * sumXY - sumX * sumY;
      const denominator = Math.sqrt(
        (n * sumX2 - sumX * sumX) * (n * sumY2 - sumY * sumY)
      );

      if (!isFinite(denominator) || denominator === 0) return 0;

      return numerator / denominator;
    }

    /**
     * Get summary statistics
     */
    getStats() {
      if (!this.data) return null;

      const correlations = [];
      const sensors = Object.keys(this.data);

      for (const sensor1 of sensors) {
        for (const sensor2 of sensors) {
          if (sensor1 !== sensor2) {
            const corr = this._getCorrelation(this.data, sensor1, sensor2);
            if (corr !== null) {
              correlations.push({
                pair: [sensor1, sensor2],
                value: corr
              });
            }
          }
        }
      }

      // Find strongest correlations
      const sorted = correlations.sort((a, b) => Math.abs(b.value) - Math.abs(a.value));

      return {
        strongestPositive: sorted.find(c => c.value > 0) || null,
        strongestNegative: sorted.find(c => c.value < 0) || null,
        avgAbsCorrelation: correlations.length > 0
          ? correlations.reduce((sum, c) => sum + Math.abs(c.value), 0) / correlations.length
          : 0,
        totalPairs: correlations.length / 2 // Divide by 2 to avoid counting both directions
      };
    }

    /**
     * Destroy the component
     */
    destroy() {
      if (this.tooltip && this.tooltip.parentNode) {
        this.tooltip.parentNode.removeChild(this.tooltip);
        this.tooltip = null;
      }
    }
  }

  // Export to window
  window.SensorCorrelationMatrix = SensorCorrelationMatrix;
})();
