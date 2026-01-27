/**
 * Energy Trends Component
 * ============================================================================
 * Historical energy cost and consumption tracking with trend analysis.
 *
 * Features:
 * - Current power consumption display
 * - Daily/weekly/monthly cost tracking
 * - Trend comparison (vs previous period)
 * - Per-actuator breakdown
 * - Cost projections
 *
 * Usage:
 *   const trends = new EnergyTrends('energy-container', {
 *     ratePerKwh: 0.12,
 *     currency: '$'
 *   });
 *   trends.update(energyData);
 */
(function() {
  'use strict';

  class EnergyTrends {
    constructor(containerId, options = {}) {
      this.containerId = containerId;
      this.container = document.getElementById(containerId);

      if (!this.container) {
        console.warn(`[EnergyTrends] Container element "${containerId}" not found`);
        return;
      }

      this.options = {
        ratePerKwh: options.ratePerKwh || 0.12,
        currency: options.currency || '$',
        showBreakdown: options.showBreakdown !== false,
        showProjection: options.showProjection !== false,
        compactMode: options.compactMode || false,
        ...options
      };

      this.data = null;
      this.chart = null;
    }

    /**
     * Update with energy data
     * @param {Object} data - Energy data object
     */
    update(data) {
      if (!this.container || !data) return;

      this.data = data;
      this.render();
    }

    /**
     * Render the energy trends display
     */
    render() {
      if (!this.container || !this.data) return;

      const html = this.options.compactMode
        ? this._renderCompact()
        : this._renderFull();

      this.container.innerHTML = html;
    }

    /**
     * Render compact view (for dashboard card)
     */
    _renderCompact() {
      const current = this.data.current_power_watts || 0;
      const dailyCost = this.data.daily_cost || this._calculateDailyCost(current);
      const trend = this.data.trend || this._calculateTrend();

      const trendClass = trend.direction === 'up' ? 'negative' : trend.direction === 'down' ? 'positive' : 'neutral';
      const trendIcon = trend.direction === 'up' ? '↑' : trend.direction === 'down' ? '↓' : '→';

      return `
        <div class="energy-compact">
          <div class="energy-compact__power">
            <span class="energy-compact__value">${this._formatPower(current)}</span>
            <span class="energy-compact__label">Current</span>
          </div>
          <div class="energy-compact__divider"></div>
          <div class="energy-compact__cost">
            <span class="energy-compact__value">${this.options.currency}${dailyCost.toFixed(2)}</span>
            <span class="energy-compact__label">Est. Today</span>
          </div>
          <div class="energy-compact__trend ${trendClass}">
            <span class="trend-icon">${trendIcon}</span>
            <span class="trend-value">${Math.abs(trend.percent).toFixed(1)}%</span>
          </div>
        </div>
      `;
    }

    /**
     * Render full view (for energy analytics page)
     */
    _renderFull() {
      const current = this.data.current_power_watts || 0;
      const dailyCost = this.data.daily_cost || this._calculateDailyCost(current);
      const weeklyCost = this.data.weekly_cost || dailyCost * 7;
      const monthlyCost = this.data.monthly_cost || dailyCost * 30;
      const trend = this.data.trend || this._calculateTrend();
      const breakdown = this.data.breakdown || [];

      return `
        <div class="energy-trends">
          <div class="energy-trends__summary">
            <div class="energy-stat energy-stat--primary">
              <div class="energy-stat__icon"><i class="fas fa-bolt"></i></div>
              <div class="energy-stat__content">
                <span class="energy-stat__value">${this._formatPower(current)}</span>
                <span class="energy-stat__label">Current Power</span>
              </div>
            </div>

            <div class="energy-stat">
              <div class="energy-stat__content">
                <span class="energy-stat__value">${this.options.currency}${dailyCost.toFixed(2)}</span>
                <span class="energy-stat__label">Today (Est.)</span>
              </div>
              ${this._renderTrendBadge(trend)}
            </div>

            <div class="energy-stat">
              <div class="energy-stat__content">
                <span class="energy-stat__value">${this.options.currency}${weeklyCost.toFixed(2)}</span>
                <span class="energy-stat__label">This Week</span>
              </div>
            </div>

            <div class="energy-stat">
              <div class="energy-stat__content">
                <span class="energy-stat__value">${this.options.currency}${monthlyCost.toFixed(2)}</span>
                <span class="energy-stat__label">This Month</span>
              </div>
            </div>
          </div>

          ${this.options.showBreakdown && breakdown.length > 0 ? this._renderBreakdown(breakdown) : ''}

          ${this.options.showProjection ? this._renderProjection() : ''}
        </div>
      `;
    }

    /**
     * Render trend badge
     */
    _renderTrendBadge(trend) {
      const trendClass = trend.direction === 'up' ? 'negative' : trend.direction === 'down' ? 'positive' : 'neutral';
      const trendIcon = trend.direction === 'up' ? 'fa-arrow-up' : trend.direction === 'down' ? 'fa-arrow-down' : 'fa-minus';

      return `
        <span class="energy-trend-badge ${trendClass}" title="${trend.label || 'vs. yesterday'}">
          <i class="fas ${trendIcon}"></i>
          ${Math.abs(trend.percent).toFixed(1)}%
        </span>
      `;
    }

    /**
     * Render per-actuator breakdown
     */
    _renderBreakdown(breakdown) {
      const total = breakdown.reduce((sum, item) => sum + (item.power_watts || 0), 0);

      return `
        <div class="energy-breakdown">
          <h4 class="energy-breakdown__title">
            <i class="fas fa-chart-pie"></i> Power Breakdown
          </h4>
          <div class="energy-breakdown__list">
            ${breakdown.map(item => {
              const power = item.power_watts || 0;
              const percent = total > 0 ? (power / total) * 100 : 0;
              const isOn = item.is_on || item.state === 'on';
              const cost = this._calculateDailyCost(power);

              return `
                <div class="energy-breakdown__item ${isOn ? 'active' : 'inactive'}">
                  <div class="energy-breakdown__info">
                    <span class="energy-breakdown__name">
                      <i class="${this._getActuatorIcon(item.type)}"></i>
                      ${this._escapeHtml(item.name || 'Device')}
                    </span>
                    <span class="energy-breakdown__status ${isOn ? 'on' : 'off'}">
                      ${isOn ? 'ON' : 'OFF'}
                    </span>
                  </div>
                  <div class="energy-breakdown__bar">
                    <div class="energy-breakdown__fill" style="width: ${percent}%"></div>
                  </div>
                  <div class="energy-breakdown__values">
                    <span class="energy-breakdown__power">${this._formatPower(power)}</span>
                    <span class="energy-breakdown__cost">${this.options.currency}${cost.toFixed(2)}/day</span>
                  </div>
                </div>
              `;
            }).join('')}
          </div>
          <div class="energy-breakdown__total">
            <span>Total Active:</span>
            <strong>${this._formatPower(total)}</strong>
          </div>
        </div>
      `;
    }

    /**
     * Render cost projection
     */
    _renderProjection() {
      const current = this.data.current_power_watts || 0;
      const hoursRemaining = 24 - new Date().getHours();
      const projectedDaily = this._calculateDailyCost(current);
      const projectedMonthly = projectedDaily * 30;

      return `
        <div class="energy-projection">
          <h4 class="energy-projection__title">
            <i class="fas fa-chart-line"></i> Projections
          </h4>
          <div class="energy-projection__grid">
            <div class="energy-projection__item">
              <span class="energy-projection__label">End of Day</span>
              <span class="energy-projection__value">${this.options.currency}${projectedDaily.toFixed(2)}</span>
              <span class="energy-projection__note">${hoursRemaining}h at current rate</span>
            </div>
            <div class="energy-projection__item">
              <span class="energy-projection__label">Monthly Estimate</span>
              <span class="energy-projection__value">${this.options.currency}${projectedMonthly.toFixed(2)}</span>
              <span class="energy-projection__note">Based on today's usage</span>
            </div>
          </div>
        </div>
      `;
    }

    /**
     * Calculate daily cost from power
     */
    _calculateDailyCost(powerWatts) {
      const kWh = (powerWatts / 1000) * 24;
      return kWh * this.options.ratePerKwh;
    }

    /**
     * Calculate trend vs previous period
     */
    _calculateTrend() {
      const current = this.data.current_power_watts || 0;
      const previous = this.data.previous_power_watts || this.data.yesterday_avg || current;

      if (previous === 0) {
        return { direction: 'neutral', percent: 0, label: 'vs. yesterday' };
      }

      const change = ((current - previous) / previous) * 100;

      return {
        direction: change > 5 ? 'up' : change < -5 ? 'down' : 'neutral',
        percent: change,
        label: 'vs. yesterday'
      };
    }

    /**
     * Format power value
     */
    _formatPower(watts) {
      if (watts >= 1000) {
        return `${(watts / 1000).toFixed(2)} kW`;
      }
      return `${Math.round(watts)} W`;
    }

    /**
     * Get icon for actuator type
     */
    _getActuatorIcon(type) {
      const icons = {
        light: 'fas fa-lightbulb',
        grow_light: 'fas fa-lightbulb',
        fan: 'fas fa-fan',
        pump: 'fas fa-faucet',
        irrigation: 'fas fa-tint',
        heater: 'fas fa-fire',
        cooler: 'fas fa-snowflake',
        humidifier: 'fas fa-cloud-rain',
        dehumidifier: 'fas fa-wind'
      };
      return icons[type] || 'fas fa-plug';
    }

    /**
     * Escape HTML
     */
    _escapeHtml(text) {
      if (!text) return '';
      const div = document.createElement('div');
      div.textContent = text;
      return div.innerHTML;
    }

    /**
     * Set electricity rate
     */
    setRate(ratePerKwh) {
      this.options.ratePerKwh = ratePerKwh;
      this.render();
    }

    /**
     * Get current data
     */
    getData() {
      return this.data;
    }
  }

  /**
   * EnergyMiniCard - Compact energy display for dashboard
   */
  class EnergyMiniCard {
    constructor(options = {}) {
      this.powerElementId = options.powerElementId || 'current-power';
      this.costElementId = options.costElementId || 'daily-cost';
      this.trendElementId = options.trendElementId || 'energy-trend';
      this.ratePerKwh = options.ratePerKwh || 0.12;
      this.currency = options.currency || '$';
    }

    /**
     * Update the mini card display
     */
    update(data) {
      const powerEl = document.getElementById(this.powerElementId);
      const costEl = document.getElementById(this.costElementId);
      const trendEl = document.getElementById(this.trendElementId);

      const power = data.current_power_watts || 0;
      const dailyCost = data.daily_cost || this._calculateDailyCost(power);
      const trend = data.trend_percent || 0;

      if (powerEl) {
        powerEl.textContent = power >= 1000
          ? `${(power / 1000).toFixed(2)} kW`
          : `${Math.round(power)} W`;
      }

      if (costEl) {
        costEl.textContent = `${this.currency}${dailyCost.toFixed(2)}`;
      }

      if (trendEl) {
        const direction = trend > 5 ? 'up' : trend < -5 ? 'down' : 'neutral';
        const icon = direction === 'up' ? '↑' : direction === 'down' ? '↓' : '→';
        const trendClass = direction === 'up' ? 'negative' : direction === 'down' ? 'positive' : 'neutral';

        trendEl.textContent = `${icon} ${Math.abs(trend).toFixed(1)}%`;
        trendEl.className = `energy-trend ${trendClass}`;
      }
    }

    _calculateDailyCost(powerWatts) {
      const kWh = (powerWatts / 1000) * 24;
      return kWh * this.ratePerKwh;
    }
  }

  // Export to window
  window.EnergyTrends = EnergyTrends;
  window.EnergyMiniCard = EnergyMiniCard;
})();
