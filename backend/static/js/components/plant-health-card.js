/**
 * Plant Health Card Component
 * ============================================================================
 * A reusable plant health card for displaying plant info, growth stage,
 * health status, and days since planting.
 *
 * Usage:
 *   const card = new PlantHealthCard('plant-card-1', {
 *     onClick: (plantId) => { ... },
 *     showHealthBar: true
 *   });
 *   card.update(plantData);
 */
(function() {
  'use strict';

  class PlantHealthCard {
    constructor(containerId, options = {}) {
      this.containerId = containerId;
      this.container = document.getElementById(containerId);

      if (!this.container) {
        // Container might be created dynamically
        this.container = null;
      }

      this.options = {
        onClick: options.onClick || null,
        showHealthBar: options.showHealthBar !== false,
        showDays: options.showDays !== false,
        showStage: options.showStage !== false,
        compact: options.compact || false,
        ...options
      };

      this.plantData = null;

      // Growth stage icons and colors
      this.stageConfig = {
        seedling: { icon: 'fas fa-seedling', color: 'var(--stage-seedling, #22c55e)', label: 'Seedling' },
        vegetative: { icon: 'fas fa-leaf', color: 'var(--stage-vegetative, #10b981)', label: 'Vegetative' },
        flowering: { icon: 'fas fa-spa', color: 'var(--stage-flowering, #8b5cf6)', label: 'Flowering' },
        fruiting: { icon: 'fas fa-apple-alt', color: 'var(--stage-fruiting, #f59e0b)', label: 'Fruiting' },
        harvest: { icon: 'fas fa-hand-holding-seedling', color: 'var(--stage-harvest, #ef4444)', label: 'Ready' },
        dormant: { icon: 'fas fa-moon', color: 'var(--stage-dormant, #6b7280)', label: 'Dormant' },
        default: { icon: 'fas fa-leaf', color: 'var(--text-secondary)', label: 'Growing' }
      };

      // Health status config
      this.healthConfig = {
        excellent: { color: 'var(--health-excellent, #22c55e)', label: 'Excellent', min: 90 },
        good: { color: 'var(--health-good, #84cc16)', label: 'Good', min: 70 },
        fair: { color: 'var(--health-fair, #eab308)', label: 'Fair', min: 50 },
        poor: { color: 'var(--health-poor, #f97316)', label: 'Poor', min: 25 },
        critical: { color: 'var(--health-critical, #ef4444)', label: 'Critical', min: 0 }
      };
    }

    /**
     * Set the container element
     */
    setContainer(element) {
      this.container = element;
    }

    /**
     * Update the card with plant data
     * @param {Object} plant - Plant data object
     */
    update(plant) {
      if (!plant) return;

      this.plantData = plant;
      this.render();
    }

    /**
     * Render the plant card
     */
    render() {
      if (!this.container || !this.plantData) return;

      const plant = this.plantData;
      const html = this.options.compact
        ? this._renderCompact(plant)
        : this._renderFull(plant);

      this.container.innerHTML = html;
      this._bindEvents();
    }

    /**
     * Render compact card (for dashboard grid)
     */
    _renderCompact(plant) {
      const id = plant.id || plant.plant_id;
      const name = window.escapeHtml(plant.name || plant.plant_name || 'Plant');
      const species = window.escapeHtml((plant.species || plant.plant_type || 'Unknown').toString());
      const stage = window.escapeHtml((plant.current_stage || plant.growth_stage || plant.stage || '').toString());
      const subtitle = stage ? `${species} - ${stage}` : species;

      const rawHealth = String(plant.health_status || plant.current_health_status || '').toLowerCase();
      let healthClass = rawHealth;
      if (!healthClass) {
        const score = Number(plant.health_score ?? plant.health);
        if (Number.isFinite(score)) {
          healthClass = this._getHealthStatus(score).key;
        }
      }
      if (!healthClass) healthClass = 'unknown';

      const healthLabelMap = {
        healthy: 'EXCELLENT',
        excellent: 'EXCELLENT',
        good: 'GOOD',
        fair: 'FAIR',
        poor: 'POOR',
        critical: 'CRITICAL',
        unknown: 'UNKNOWN'
      };
      const healthLabel = healthLabelMap[healthClass] || 'UNKNOWN';

      const moistureRaw = plant.moisture_percent ?? plant.moisture ?? plant.moisture_level;
      const moistureValue = (moistureRaw === null || moistureRaw === undefined || moistureRaw === '')
        ? null
        : Number(moistureRaw);
      const hasMoisture = Number.isFinite(moistureValue);
      const moistureDisplay = hasMoisture ? `${Math.round(moistureValue)}%` : '--';
      const moisturePct = hasMoisture ? Math.max(0, Math.min(100, Math.round(moistureValue))) : 0;

      const imageUrl = window.escapeHtml(
        plant.custom_image || plant.image || plant.image_url || '/static/img/plant-placeholder.svg'
      );
      const lastWatered = window.escapeHtml(plant.last_watered || 'N/A');
      const daysInStage = plant.days_in_stage ? `${Number(plant.days_in_stage)} days in stage` : '';

      return `
        <article class="plant-card-lg" data-plant-id="${id}">
          <div class="plant-card__image">
            <img src="${imageUrl}" alt="${name}" loading="lazy">
          </div>

          <div class="plant-card__status-pill ${healthClass}">${healthLabel}</div>

          <div class="plant-card__body">
            <div class="plant-card__title">${name}</div>
            <div class="plant-card__subtitle">${subtitle}</div>

            <div class="plant-card__metric">
              <div class="metric-label">Moisture</div>
              <div class="metric-value">${moistureDisplay}</div>
            </div>

            <div class="plant-card__progress">
              <div class="progress-track"><div class="progress-fill" style="width: ${moisturePct}%"></div></div>
            </div>
          </div>

          <div class="plant-card__footer">
            <span class="plant-card__footer-left">Last watered: ${lastWatered}</span>
            ${daysInStage ? `<span class="plant-card__footer-right">${daysInStage}</span>` : ''}
          </div>
        </article>
      `;
    }

    /**
     * Render full card (for plant details)
     */
    _renderFull(plant) {
      const id = plant.id || plant.plant_id;
      const name = plant.name || plant.plant_name || 'Unknown Plant';
      const species = plant.species || plant.plant_type || '';
      const stage = (plant.growth_stage || plant.stage || 'vegetative').toLowerCase();
      const stageConfig = this.stageConfig[stage] || this.stageConfig.default;
      const days = this._calculateDays(plant);
      const health = plant.health_score || plant.health || 100;
      const healthStatus = this._getHealthStatus(health);
      const imageUrl = plant.image_url || plant.image || null;

      return `
        <div class="plant-health-card" data-plant-id="${id}">
          <div class="plant-health-card__header">
            ${imageUrl ? `
              <div class="plant-health-card__image">
                <img src="${window.escapeHtml(imageUrl)}" alt="${window.escapeHtml(name)}" loading="lazy">
              </div>
            ` : `
              <div class="plant-health-card__icon" style="background: ${stageConfig.color}20; color: ${stageConfig.color}">
                <i class="${stageConfig.icon}"></i>
              </div>
            `}
            <div class="plant-health-card__title">
              <h4>${window.escapeHtml(name)}</h4>
              ${species ? `<span class="species">${window.escapeHtml(species)}</span>` : ''}
            </div>
          </div>

          <div class="plant-health-card__body">
            <div class="plant-health-card__stats">
              ${this.options.showStage ? `
                <div class="stat">
                  <span class="stat-label">Stage</span>
                  <span class="stat-value" style="color: ${stageConfig.color}">
                    <i class="${stageConfig.icon}"></i> ${stageConfig.label}
                  </span>
                </div>
              ` : ''}
              ${this.options.showDays && days !== null ? `
                <div class="stat">
                  <span class="stat-label">Age</span>
                  <span class="stat-value">${days} days</span>
                </div>
              ` : ''}
            </div>

            ${this.options.showHealthBar ? `
              <div class="plant-health-card__health">
                <div class="health-header">
                  <span class="health-label">Health</span>
                  <span class="health-value" style="color: ${healthStatus.color}">${health}%</span>
                </div>
                <div class="health-bar-container">
                  <div class="health-bar" style="width: ${health}%; background: ${healthStatus.color}"></div>
                </div>
                <span class="health-status" style="color: ${healthStatus.color}">${healthStatus.label}</span>
              </div>
            ` : ''}
          </div>

          ${plant.last_watered || plant.next_action ? `
            <div class="plant-health-card__footer">
              ${plant.last_watered ? `
                <span class="plant-action"><i class="fas fa-tint"></i> ${window.formatTimeAgo(plant.last_watered, { short: true })}</span>
              ` : ''}
              ${plant.next_action ? `
                <span class="plant-next">${window.escapeHtml(plant.next_action)}</span>
              ` : ''}
            </div>
          ` : ''}
        </div>
      `;
    }

    /**
     * Calculate days since planting
     */
    _calculateDays(plant) {
      const startDate = plant.planted_date || plant.start_date || plant.created_at;
      if (!startDate) return null;

      const start = new Date(startDate);
      const now = new Date();
      const diffTime = Math.abs(now - start);
      const diffDays = Math.floor(diffTime / (1000 * 60 * 60 * 24));

      return diffDays;
    }

    /**
     * Get health status from score
     */
    _getHealthStatus(score) {
      if (score >= 90) return { ...this.healthConfig.excellent, key: 'excellent' };
      if (score >= 70) return { ...this.healthConfig.good, key: 'good' };
      if (score >= 50) return { ...this.healthConfig.fair, key: 'fair' };
      if (score >= 25) return { ...this.healthConfig.poor, key: 'poor' };
      return { ...this.healthConfig.critical, key: 'critical' };
    }



    /**
     * Bind click events
     */
    _bindEvents() {
      if (!this.container || !this.options.onClick) return;

      const card = this.container.querySelector('[data-plant-id]');
      if (card) {
        card.style.cursor = 'pointer';
        card.addEventListener('click', () => {
          const plantId = card.dataset.plantId;
          this.options.onClick(plantId, this.plantData);
        });
      }
    }



    /**
     * Get plant data
     */
    getData() {
      return this.plantData;
    }
  }

  /**
   * PlantHealthGrid - Manages a grid of plant cards
   */
  class PlantHealthGrid {
    constructor(containerId, options = {}) {
      this.containerId = containerId;
      this.container = document.getElementById(containerId);
      this.options = {
        onClick: options.onClick || null,
        compact: options.compact !== false,
        emptyMessage: options.emptyMessage || 'No plants in this unit',
        maxVisible: options.maxVisible || 12,
        ...options
      };
      this.cards = new Map();
    }

    /**
     * Update the grid with plant data
     * @param {Array} plants - Array of plant objects
     */
    update(plants) {
      if (!this.container) return;

      if (!plants || plants.length === 0) {
        this.container.innerHTML = `<div class="empty-message">${this.options.emptyMessage}</div>`;
        this.cards.clear();
        return;
      }

      const visiblePlants = plants.slice(0, this.options.maxVisible);

      this.container.innerHTML = visiblePlants.map(plant => {
        const id = plant.id || plant.plant_id;
        return `<div id="plant-card-${id}" class="plant-card-wrapper"></div>`;
      }).join('');

      // Show "more" indicator if there are more plants
      if (plants.length > this.options.maxVisible) {
        const remaining = plants.length - this.options.maxVisible;
        this.container.insertAdjacentHTML('beforeend', `
          <div class="plant-card-more">
            <span>+${remaining} more</span>
          </div>
        `);
      }

      // Create card instances
      this.cards.clear();
      visiblePlants.forEach(plant => {
        const id = plant.id || plant.plant_id;
        const wrapper = this.container.querySelector(`#plant-card-${id}`);
        if (wrapper) {
          const card = new PlantHealthCard(`plant-card-${id}`, {
            onClick: this.options.onClick,
            compact: this.options.compact
          });
          card.setContainer(wrapper);
          card.update(plant);
          this.cards.set(String(id), card);
        }
      });
    }

    /**
     * Update a single plant card
     */
    updatePlant(plantId, plantData) {
      const card = this.cards.get(String(plantId));
      if (card) {
        card.update(plantData);
      }
    }

    /**
     * Get health summary for all plants
     */
    getHealthSummary() {
      const summary = {
        total: this.cards.size,
        excellent: 0,
        good: 0,
        fair: 0,
        poor: 0,
        critical: 0,
        averageHealth: 0
      };

      let totalHealth = 0;
      this.cards.forEach(card => {
        const data = card.getData();
        if (data) {
          const health = data.health_score || data.health || 100;
          totalHealth += health;

          if (health >= 90) summary.excellent++;
          else if (health >= 70) summary.good++;
          else if (health >= 50) summary.fair++;
          else if (health >= 25) summary.poor++;
          else summary.critical++;
        }
      });

      summary.averageHealth = summary.total > 0
        ? Math.round(totalHealth / summary.total)
        : 0;

      return summary;
    }
  }

  // Export to window
  window.PlantHealthCard = PlantHealthCard;
  window.PlantHealthGrid = PlantHealthGrid;
})();
