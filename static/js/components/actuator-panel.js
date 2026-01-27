/**
 * Actuator Panel Component
 * ============================================================================
 * A reusable actuator control panel with toggle switches and energy monitoring.
 *
 * Usage:
 *   const panel = new ActuatorPanel('actuators-container', {
 *     onToggle: async (actuatorId, newState) => { ... },
 *     showEnergy: true
 *   });
 *   panel.update(actuatorsArray);
 */
(function() {
  'use strict';

  class ActuatorPanel {
    constructor(containerId, options = {}) {
      this.containerId = containerId;
      this.container = document.getElementById(containerId);

      if (!this.container) {
        console.warn(`[ActuatorPanel] Container element "${containerId}" not found`);
        return;
      }

      this.options = {
        onToggle: options.onToggle || null,
        showEnergy: options.showEnergy !== false,
        showStatus: options.showStatus !== false,
        emptyMessage: options.emptyMessage || 'No actuators configured',
        maxVisible: options.maxVisible || 6,
        ...options
      };

      this.actuators = new Map();
      this.pendingToggles = new Set();

      // Actuator type icons
      this.typeIcons = {
        light: 'fas fa-lightbulb',
        grow_light: 'fas fa-lightbulb',
        fan: 'fas fa-fan',
        exhaust_fan: 'fas fa-fan',
        pump: 'fas fa-faucet',
        irrigation: 'fas fa-tint',
        heater: 'fas fa-fire',
        cooler: 'fas fa-snowflake',
        humidifier: 'fas fa-cloud-rain',
        dehumidifier: 'fas fa-wind',
        relay: 'fas fa-plug',
        default: 'fas fa-toggle-on'
      };

      // Status classes
      this.statusClasses = {
        on: 'actuator--on',
        off: 'actuator--off',
        error: 'actuator--error',
        offline: 'actuator--offline',
        pending: 'actuator--pending'
      };

      this._bindEvents();
    }

    /**
     * Bind event listeners
     */
    _bindEvents() {
      if (!this.container) return;

      this.container.addEventListener('click', (e) => {
        const toggle = e.target.closest('.actuator-control__toggle');
        if (toggle && !toggle.disabled) {
          const actuatorId = toggle.dataset.actuatorId;
          this._handleToggle(actuatorId);
        }
      });
    }

    /**
     * Handle toggle click
     */
    async _handleToggle(actuatorId) {
      if (this.pendingToggles.has(actuatorId)) return;

      const actuator = this.actuators.get(actuatorId);
      if (!actuator) return;

      const newState = !actuator.is_on;

      // Mark as pending
      this.pendingToggles.add(actuatorId);
      this._updateActuatorUI(actuatorId, { ...actuator, pending: true });

      try {
        if (this.options.onToggle) {
          await this.options.onToggle(actuatorId, newState);
        }

        // Optimistic update
        actuator.is_on = newState;
        this.actuators.set(actuatorId, actuator);
        this._updateActuatorUI(actuatorId, actuator);
      } catch (error) {
        console.error(`[ActuatorPanel] Toggle failed for ${actuatorId}:`, error);
        // Revert UI on failure
        this._updateActuatorUI(actuatorId, { ...actuator, error: true });
      } finally {
        this.pendingToggles.delete(actuatorId);
      }
    }

    /**
     * Update the panel with actuator data
     * @param {Array} actuators - Array of actuator objects
     */
    update(actuators) {
      if (!this.container) return;

      if (!actuators || actuators.length === 0) {
        this.container.innerHTML = `<div class="empty-message">${this.options.emptyMessage}</div>`;
        return;
      }

      // Update actuators map
      actuators.forEach(a => {
        const id = String(a.id || a.actuator_id);
        this.actuators.set(id, a);
      });

      this.render();
    }

    /**
     * Render the actuator panel
     */
    render() {
      if (!this.container) return;

      const actuatorsList = Array.from(this.actuators.values())
        .slice(0, this.options.maxVisible);

      if (actuatorsList.length === 0) {
        this.container.innerHTML = `<div class="empty-message">${this.options.emptyMessage}</div>`;
        return;
      }

      this.container.innerHTML = actuatorsList
        .map(actuator => this._renderActuator(actuator))
        .join('');
    }

    /**
     * Render a single actuator control
     */
    _renderActuator(actuator) {
      const id = String(actuator.id || actuator.actuator_id);
      const name = actuator.name || actuator.label || `Actuator ${id}`;
      const type = (actuator.type || actuator.actuator_type || 'relay').toLowerCase();
      const isOn = actuator.is_on || actuator.state === 'on' || actuator.state === true;
      const power = actuator.power_watts || actuator.power || 0;
      const isOnline = actuator.online !== false && actuator.status !== 'offline';
      const hasError = actuator.error || actuator.status === 'error';
      const isPending = actuator.pending || this.pendingToggles.has(id);

      const icon = this.typeIcons[type] || this.typeIcons.default;
      const statusClass = this._getStatusClass(isOn, isOnline, hasError, isPending);
      const toggleState = isOn ? 'on' : 'off';

      return `
        <div class="actuator-control ${statusClass}" data-actuator-id="${id}">
          <div class="actuator-control__icon">
            <i class="${icon}"></i>
          </div>
          <div class="actuator-control__info">
            <span class="actuator-control__name">${this._escapeHtml(name)}</span>
            ${this.options.showEnergy && isOn && power > 0 ? `
              <span class="actuator-control__power">${power}W</span>
            ` : ''}
          </div>
          <div class="actuator-control__toggle-wrapper">
            <button
              class="actuator-control__toggle ${toggleState}"
              data-actuator-id="${id}"
              ${!isOnline || isPending ? 'disabled' : ''}
              aria-label="Toggle ${name}"
              aria-pressed="${isOn}"
            >
              <span class="toggle-track">
                <span class="toggle-thumb"></span>
              </span>
              ${isPending ? '<span class="toggle-spinner"></span>' : ''}
            </button>
          </div>
        </div>
      `;
    }

    /**
     * Update a single actuator's UI
     */
    _updateActuatorUI(actuatorId, actuator) {
      const element = this.container.querySelector(`[data-actuator-id="${actuatorId}"].actuator-control`);
      if (!element) return;

      const isOn = actuator.is_on || actuator.state === 'on' || actuator.state === true;
      const isOnline = actuator.online !== false && actuator.status !== 'offline';
      const hasError = actuator.error || actuator.status === 'error';
      const isPending = actuator.pending || this.pendingToggles.has(actuatorId);

      // Update status class
      const statusClass = this._getStatusClass(isOn, isOnline, hasError, isPending);
      element.className = `actuator-control ${statusClass}`;

      // Update toggle button
      const toggle = element.querySelector('.actuator-control__toggle');
      if (toggle) {
        toggle.className = `actuator-control__toggle ${isOn ? 'on' : 'off'}`;
        toggle.disabled = !isOnline || isPending;
        toggle.setAttribute('aria-pressed', String(isOn));

        // Add/remove spinner
        const existingSpinner = toggle.querySelector('.toggle-spinner');
        if (isPending && !existingSpinner) {
          toggle.insertAdjacentHTML('beforeend', '<span class="toggle-spinner"></span>');
        } else if (!isPending && existingSpinner) {
          existingSpinner.remove();
        }
      }

      // Update power display
      const powerEl = element.querySelector('.actuator-control__power');
      const power = actuator.power_watts || actuator.power || 0;
      if (this.options.showEnergy && isOn && power > 0) {
        if (powerEl) {
          powerEl.textContent = `${power}W`;
        } else {
          const infoEl = element.querySelector('.actuator-control__info');
          if (infoEl) {
            infoEl.insertAdjacentHTML('beforeend', `<span class="actuator-control__power">${power}W</span>`);
          }
        }
      } else if (powerEl) {
        powerEl.remove();
      }
    }

    /**
     * Get status CSS class
     */
    _getStatusClass(isOn, isOnline, hasError, isPending) {
      if (isPending) return this.statusClasses.pending;
      if (hasError) return this.statusClasses.error;
      if (!isOnline) return this.statusClasses.offline;
      return isOn ? this.statusClasses.on : this.statusClasses.off;
    }

    /**
     * Escape HTML to prevent XSS
     */
    _escapeHtml(text) {
      const div = document.createElement('div');
      div.textContent = text;
      return div.innerHTML;
    }

    /**
     * Get total power consumption
     */
    getTotalPower() {
      let total = 0;
      this.actuators.forEach(actuator => {
        if (actuator.is_on || actuator.state === 'on' || actuator.state === true) {
          total += actuator.power_watts || actuator.power || 0;
        }
      });
      return total;
    }

    /**
     * Get count of active actuators
     */
    getActiveCount() {
      let count = 0;
      this.actuators.forEach(actuator => {
        if (actuator.is_on || actuator.state === 'on' || actuator.state === true) {
          count++;
        }
      });
      return count;
    }

    /**
     * Get actuator by ID
     */
    getActuator(id) {
      return this.actuators.get(String(id));
    }

    /**
     * Set actuator state programmatically
     */
    setActuatorState(id, state) {
      const actuator = this.actuators.get(String(id));
      if (actuator) {
        actuator.is_on = state;
        this._updateActuatorUI(String(id), actuator);
      }
    }
  }

  /**
   * EnergySummary - Companion component for energy display
   */
  class EnergySummary {
    constructor(options = {}) {
      this.powerElementId = options.powerElementId || 'total-power';
      this.costElementId = options.costElementId || 'daily-cost';
      this.ratePerKwh = options.ratePerKwh || 0.12; // Default $0.12/kWh
    }

    /**
     * Update energy summary display
     * @param {Object} data - Energy data
     * @param {number} data.totalPower - Total power in watts
     * @param {number} data.dailyCost - Daily cost (optional, will calculate if not provided)
     */
    update(data) {
      const powerEl = document.getElementById(this.powerElementId);
      const costEl = document.getElementById(this.costElementId);

      if (powerEl) {
        const power = data.totalPower || 0;
        powerEl.textContent = power > 1000
          ? `${(power / 1000).toFixed(2)} kW`
          : `${Math.round(power)} W`;
      }

      if (costEl) {
        const dailyCost = data.dailyCost !== undefined
          ? data.dailyCost
          : this.calculateDailyCost(data.totalPower || 0);
        costEl.textContent = `$${dailyCost.toFixed(2)}`;
      }
    }

    /**
     * Calculate daily cost from power
     */
    calculateDailyCost(powerWatts) {
      const kWh = (powerWatts / 1000) * 24;
      return kWh * this.ratePerKwh;
    }

    /**
     * Set electricity rate
     */
    setRate(ratePerKwh) {
      this.ratePerKwh = ratePerKwh;
    }
  }

  // Export to window
  window.ActuatorPanel = ActuatorPanel;
  window.EnergySummary = EnergySummary;
})();
