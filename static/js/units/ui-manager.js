/**
 * UnitsUIManager
 * ============================================================================
 * Handles all DOM manipulation, rendering, and user interactions for the
 * growth units page. Uses UnitsDataService for data operations.
 */
(function () {
  'use strict';

  // Environmental metrics configuration
  const ENV_METRICS = [
    { key: 'temperature', label: 'Temp', unit: '\u00b0C', icon: 'thermometer-half' },
    { key: 'humidity', label: 'Humidity', unit: '%', icon: 'tint' },
    { key: 'soil_moisture', label: 'Soil', unit: '%', icon: 'water' },
    { key: 'light', label: 'Light', unit: 'lux', icon: 'sun' },
    { key: 'co2', label: 'CO2', unit: 'ppm', icon: 'cloud' },
    { key: 'vpd', label: 'VPD', unit: 'kPa', icon: 'leaf' }
  ];

  class UnitsUIManager {
    constructor(dataService) {
      this.dataService = dataService;

      // State
      this.state = {
        currentUnitId: null,
        scheduleCounter: 0,
        currentUnitPlantsById: {},
        linkDeviceKind: 'sensor',
        expandedUnits: new Set(),
        cameraStreaming: new Set()
      };

      // DOM element references
      this.elements = {
        unitsGrid: null,
        overviewStats: null,
        createUnitForm: null,
        scheduleForm: null,
        linkDeviceForm: null,
        addPlantForm: null,
        thresholdsForm: null
      };

      // Bind methods
      this._bindMethods();
    }

    _bindMethods() {
      this.handleCreateUnit = this.handleCreateUnit.bind(this);
      this.handleDeleteUnit = this.handleDeleteUnit.bind(this);
      this.handleSaveSchedule = this.handleSaveSchedule.bind(this);
      this.handleDeleteSchedule = this.handleDeleteSchedule.bind(this);
      this.handleLinkDevice = this.handleLinkDevice.bind(this);
      this.handleUnlinkDevice = this.handleUnlinkDevice.bind(this);
      this.handleAddPlant = this.handleAddPlant.bind(this);
      this.handleRemovePlant = this.handleRemovePlant.bind(this);
      this.handleUpdateThresholds = this.handleUpdateThresholds.bind(this);
    }

    // --------------------------------------------------------------------------
    // Initialization
    // --------------------------------------------------------------------------

    init() {
      this._cacheElements();
      this._setupEventListeners();
      this._initUnitProfileSelector();
      this._initUnitPlantProfileSelector();
      this.loadUnitsOverview();
    }

    _cacheElements() {
      // Match template's element IDs
      this.elements.unitsGrid = document.getElementById('unitsContainer');
      this.elements.overviewStats = document.getElementById('unitsOverview');

      // Forms - try template IDs first, then fallback
      this.elements.createUnitForm = document.getElementById('createUnitForm') ||
                                     document.getElementById('create-unit-form');
      this.elements.scheduleForm = document.getElementById('deviceScheduleForm') ||
                                   document.getElementById('schedule-form');
      this.elements.linkDeviceForm = document.getElementById('linkDeviceForm') ||
                                     document.getElementById('link-device-form');
      this.elements.addPlantForm = document.getElementById('addPlantForm') ||
                                   document.getElementById('add-plant-form');
      this.elements.thresholdsForm = document.getElementById('thresholdsForm') ||
                                     document.getElementById('thresholds-form');

      this.elements.unitProfileSelector = document.getElementById('unitProfileSelector');
      this.elements.unitProfileSelectable = document.getElementById('unitProfileSelectable');
      this.elements.unitProfileSelectionSummary = document.getElementById('unitProfileSelectionSummary');
      this.elements.unitProfileChip = document.getElementById('unitProfileChip');
      this.elements.unitProfilePlantType = document.getElementById('unitProfilePlantType');
      this.elements.unitProfileStage = document.getElementById('unitProfileStage');
      this.elements.unitProfileImportToken = document.getElementById('unitProfileImportToken');
      this.elements.unitConditionProfileId = document.getElementById('unitConditionProfileId');
      this.elements.unitConditionProfileMode = document.getElementById('unitConditionProfileMode');
      this.elements.unitProfileCloneName = document.getElementById('unitProfileCloneName');

      this.elements.unitPlantProfileSelector = document.getElementById('unitPlantProfileSelector');
      this.elements.unitPlantProfileSelectable = document.getElementById('unitPlantProfileSelectable');
      this.elements.unitPlantProfileSelectionSummary = document.getElementById('unitPlantProfileSelectionSummary');
      this.elements.unitPlantProfileChip = document.getElementById('unitPlantProfileChip');
      this.elements.unitPlantProfileImportToken = document.getElementById('unitPlantProfileImportToken');
      this.elements.unitPlantConditionProfileId = document.getElementById('unitPlantConditionProfileId');
      this.elements.unitPlantConditionProfileMode = document.getElementById('unitPlantConditionProfileMode');

      // Cache overview stat elements
      this.elements.totalUnits = document.getElementById('totalUnits');
      this.elements.activePlants = document.getElementById('activePlants');
      this.elements.connectedDevices = document.getElementById('connectedDevices');
      this.elements.activeCameras = document.getElementById('activeCameras');
    }

    // --------------------------------------------------------------------------
    // Loading Indicators
    // --------------------------------------------------------------------------

    showLoading(container) {
      if (!container) return;
      container.classList.add('loading');
      const existing = container.querySelector('.loading-spinner');
      if (!existing) {
        const spinner = document.createElement('div');
        spinner.className = 'loading-spinner';
        spinner.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
        container.appendChild(spinner);
      }
    }

    hideLoading(container) {
      if (!container) return;
      container.classList.remove('loading');
      const spinner = container.querySelector('.loading-spinner');
      if (spinner) spinner.remove();
    }

    // --------------------------------------------------------------------------
    // Modal Handling
    // --------------------------------------------------------------------------

    openModal(modalId) {
      const modal = document.getElementById(modalId);
      if (!modal) return;

      modal.classList.add('active');
      document.body.style.overflow = 'hidden';

      if (modalId === 'createUnitModal') {
        this._loadUnitProfileSelector();
      }

      // Focus trap
      const focusable = modal.querySelectorAll('button, input, select, textarea, [tabindex]:not([tabindex="-1"])');
      if (focusable.length) {
        focusable[0].focus();
        this._trapFocus(modal, focusable);
      }
    }

    closeModal(modalId) {
      const modal = document.getElementById(modalId);
      if (!modal) return;

      modal.classList.remove('active');
      document.body.style.overflow = '';

      // Reset forms within modal
      const forms = modal.querySelectorAll('form');
      forms.forEach(form => form.reset());
      if (modalId === 'createUnitModal') {
        this._resetUnitProfileSelection();
      }
      if (modalId === 'addPlantModal') {
        this._resetUnitPlantProfileSelection();
      }
    }

    closeAllModals() {
      document.querySelectorAll('.modal.active').forEach(modal => {
        modal.classList.remove('active');
      });
      document.body.style.overflow = '';
    }

    _trapFocus(modal, focusableElements) {
      const first = focusableElements[0];
      const last = focusableElements[focusableElements.length - 1];

      const handler = (e) => {
        if (e.key !== 'Tab') return;

        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      };

      modal.addEventListener('keydown', handler);
      modal._focusTrapHandler = handler;
    }

    // --------------------------------------------------------------------------
    // Units Overview
    // --------------------------------------------------------------------------

    async loadUnitsOverview() {
      const grid = this.elements.unitsGrid;
      if (!grid) return;

      this.showLoading(grid);

      try {
        const units = await this.dataService.loadUnits({ force: true });

        // Load device counts for each unit in parallel
        const deviceCountPromises = units.map(async (unit) => {
          const unitId = unit.unit_id || unit.id;
          try {
            const [sensors, actuators] = await Promise.all([
              this.dataService.loadSensors(unitId),
              this.dataService.loadActuators(unitId)
            ]);
            unit.sensor_count = sensors?.length || 0;
            unit.actuator_count = actuators?.length || 0;
          } catch (e) {
            console.warn(`[UnitsUIManager] Failed to load device counts for unit ${unitId}:`, e);
            unit.sensor_count = 0;
            unit.actuator_count = 0;
          }
        });

        await Promise.all(deviceCountPromises);

        this.renderUnitsGrid(units);
        this.updateOverviewStats(units);

        // Also load environmental data for all units
        this.refreshAllEnvironmentalData();
      } catch (error) {
        console.error('[UnitsUIManager] loadUnitsOverview failed:', error);
        this.showError(grid, 'Failed to load units');
      } finally {
        this.hideLoading(grid);
      }
    }

    renderUnitsGrid(units) {
      const grid = this.elements.unitsGrid;
      if (!grid) return;

      if (!units || units.length === 0) {
        grid.innerHTML = `
          <div class="empty-state">
            <i class="fas fa-seedling"></i>
            <p>No growth units yet</p>
            <button class="btn btn-primary" onclick="window.unitsUI.openModal('create-unit-modal')">
              Create Your First Unit
            </button>
          </div>
        `;
        return;
      }

      // Update existing unit cards with data instead of replacing them
      // Template already renders cards server-side, we just need to populate data
      units.forEach(unit => {
        const unitId = unit.unit_id || unit.id;
        this._updateUnitCardData(unitId, unit);
      });
    }

    /**
     * Update data in an existing unit card rendered by template
     */
    _updateUnitCardData(unitId, unit) {
      // Update counts
      const plantsCount = document.getElementById(`plants-count-${unitId}`);
      const sensorsCount = document.getElementById(`sensors-count-${unitId}`);
      const actuatorsCount = document.getElementById(`actuators-count-${unitId}`);

      if (plantsCount) {
        plantsCount.textContent = unit.plant_count || unit.plants_count || 0;
      }
      if (sensorsCount) {
        sensorsCount.textContent = unit.sensor_count || unit.sensors_count || 0;
      }
      if (actuatorsCount) {
        actuatorsCount.textContent = unit.actuator_count || unit.actuators_count || 0;
      }

      // Update health score
      const healthScore = document.getElementById(`health-score-${unitId}`);
      if (healthScore && unit.health_score !== undefined) {
        healthScore.textContent = Math.round(unit.health_score) + '%';
      }

      // Update environmental chips
      this._updateEnvChips(unitId, unit);

      // Show camera indicator if camera is configured
      const cameraIndicator = document.getElementById(`camera-indicator-${unitId}`);
      if (cameraIndicator) {
        if (unit.camera_enabled || unit.has_camera) {
          cameraIndicator.classList.remove('hidden');
        }
      }
    }

    /**
     * Update environmental chips for a unit
     */
    _updateEnvChips(unitId, unit) {
      const container = document.getElementById(`env-chips-${unitId}`);
      if (!container) return;

      const temp = unit.temperature ?? unit.current_temperature;
      const humidity = unit.humidity ?? unit.current_humidity;
      const soil = unit.soil_moisture ?? unit.current_soil_moisture;
      const vpd = unit.vpd ?? unit.current_vpd;

      let chipsHtml = '';

      if (temp !== undefined && temp !== null) {
        chipsHtml += `
          <span class="env-chip" title="Temperature">
            <i class="fas fa-thermometer-half" aria-hidden="true"></i>
            <span class="env-chip-value">${parseFloat(temp).toFixed(1)}°C</span>
          </span>
        `;
      } else {
        chipsHtml += `
          <span class="env-chip is-muted" title="Temperature">
            <i class="fas fa-thermometer-half" aria-hidden="true"></i>
            <span class="env-chip-value">--°C</span>
          </span>
        `;
      }

      if (humidity !== undefined && humidity !== null) {
        chipsHtml += `
          <span class="env-chip" title="Humidity">
            <i class="fas fa-tint" aria-hidden="true"></i>
            <span class="env-chip-value">${parseFloat(humidity).toFixed(1)}%</span>
          </span>
        `;
      } else {
        chipsHtml += `
          <span class="env-chip is-muted" title="Humidity">
            <i class="fas fa-tint" aria-hidden="true"></i>
            <span class="env-chip-value">--%</span>
          </span>
        `;
      }

      if (soil !== undefined && soil !== null) {
        chipsHtml += `
          <span class="env-chip" title="Soil Moisture">
            <i class="fas fa-water" aria-hidden="true"></i>
            <span class="env-chip-value">${parseFloat(soil).toFixed(0)}%</span>
          </span>
        `;
      }

      if (vpd !== undefined && vpd !== null) {
        chipsHtml += `
          <span class="env-chip" title="VPD">
            <i class="fas fa-leaf" aria-hidden="true"></i>
            <span class="env-chip-value">${parseFloat(vpd).toFixed(2)} kPa</span>
          </span>
        `;
      }

      container.innerHTML = chipsHtml;
    }

    _renderUnitCard(unit) {
      const isExpanded = this.state.expandedUnits.has(unit.id);
      const statusClass = unit.status === 'active' ? 'status-active' : 'status-inactive';
      const plantCount = unit.plant_count || unit.plants?.length || 0;
      const sensorCount = unit.sensor_count || unit.sensors?.length || 0;
      const actuatorCount = unit.actuator_count || unit.actuators?.length || 0;

      return `
        <div class="unit-card ${isExpanded ? 'expanded' : ''}" data-unit-id="${unit.id}">
          <div class="unit-card-header">
            <div class="unit-info">
              <h3 class="unit-name">${this._escapeHtml(unit.name)}</h3>
              <span class="unit-status ${statusClass}">${this._escapeHtml(unit.status || 'active')}</span>
            </div>
            <div class="unit-actions">
              <button class="btn btn-icon btn-toggle-details" data-action="toggle-details" title="Toggle details">
                <i class="fas fa-chevron-${isExpanded ? 'up' : 'down'}"></i>
              </button>
              <button class="btn btn-icon btn-camera" data-action="toggle-camera" title="Camera">
                <i class="fas fa-camera"></i>
              </button>
              <button class="btn btn-icon btn-delete" data-action="delete-unit" title="Delete unit">
                <i class="fas fa-trash"></i>
              </button>
            </div>
          </div>

          <div class="unit-card-summary">
            <div class="summary-item">
              <i class="fas fa-leaf"></i>
              <span>${plantCount} plant${plantCount !== 1 ? 's' : ''}</span>
            </div>
            <div class="summary-item">
              <i class="fas fa-thermometer-half"></i>
              <span>${sensorCount} sensor${sensorCount !== 1 ? 's' : ''}</span>
            </div>
            <div class="summary-item">
              <i class="fas fa-plug"></i>
              <span>${actuatorCount} actuator${actuatorCount !== 1 ? 's' : ''}</span>
            </div>
          </div>

          <div class="unit-environmental-chips" data-unit-env="${unit.id}">
            <!-- Environmental data loaded dynamically -->
          </div>

          <div class="unit-card-details" ${isExpanded ? '' : 'style="display:none"'}>
            <div class="details-loading">
              <i class="fas fa-spinner fa-spin"></i> Loading details...
            </div>
          </div>
        </div>
      `;
    }

    updateOverviewStats(units) {
      // Update the template's existing stat elements
      const totalUnits = units.length;
      const totalPlants = units.reduce((sum, u) => sum + (u.plant_count || u.plants_count || 0), 0);
      const totalSensors = units.reduce((sum, u) => sum + (u.sensor_count || u.sensors_count || 0), 0);
      const totalActuators = units.reduce((sum, u) => sum + (u.actuator_count || u.actuators_count || 0), 0);
      const activeCameras = units.filter(u => u.camera_enabled || u.has_camera).length;

      if (this.elements.totalUnits) {
        this.elements.totalUnits.textContent = totalUnits;
      }
      if (this.elements.activePlants) {
        this.elements.activePlants.textContent = totalPlants;
      }
      if (this.elements.connectedDevices) {
        this.elements.connectedDevices.textContent = totalSensors + totalActuators;
      }
      if (this.elements.activeCameras) {
        this.elements.activeCameras.textContent = activeCameras;
      }
    }

    // --------------------------------------------------------------------------
    // Unit Details
    // --------------------------------------------------------------------------

    async toggleUnitDetails(unitId) {
      const card = document.querySelector(`.unit-card[data-unit-id="${unitId}"]`);
      if (!card) return;

      const isExpanded = this.state.expandedUnits.has(unitId);

      // Template uses different element structures
      const detailsContainer = document.getElementById(`details-${unitId}`) ||
                               card.querySelector('.unit-card-details') ||
                               card.querySelector('.unit-details');
      const toggleBtn = card.querySelector('.unit-toggle') ||
                        card.querySelector('.btn-toggle-details');
      const toggleIcon = toggleBtn?.querySelector('i');
      const toggleText = toggleBtn?.querySelector('.toggle-text');

      if (isExpanded) {
        // Collapse
        this.state.expandedUnits.delete(unitId);
        card.classList.remove('expanded');
        if (detailsContainer) {
          detailsContainer.style.display = 'none';
          detailsContainer.classList.add('hidden');
        }
        if (toggleIcon) toggleIcon.className = 'fas fa-chevron-down';
        if (toggleText) toggleText.textContent = 'Show Details';
      } else {
        // Expand and load details
        this.state.expandedUnits.add(unitId);
        card.classList.add('expanded');
        if (detailsContainer) {
          detailsContainer.style.display = 'block';
          detailsContainer.classList.remove('hidden');
        }
        if (toggleIcon) toggleIcon.className = 'fas fa-chevron-up';
        if (toggleText) toggleText.textContent = 'Hide Details';

        await this.loadUnitDetails(unitId);
      }
    }

    async loadUnitDetails(unitId) {
      const card = document.querySelector(`.unit-card[data-unit-id="${unitId}"]`);
      if (!card) return;

      this.state.currentUnitId = unitId;

      try {
        // Load all unit data in parallel
        const [unit, plants, sensors, actuators, schedules] = await Promise.all([
          this.dataService.loadUnit(unitId, { force: true }),
          this.dataService.loadPlants(unitId),
          this.dataService.loadSensors(unitId),
          this.dataService.loadActuators(unitId),
          this.dataService.loadSchedules(unitId)
        ]);

        // Cache plants by ID for quick lookup
        this.state.currentUnitPlantsById = {};
        if (plants) {
          plants.forEach(p => {
            this.state.currentUnitPlantsById[p.plant_id || p.id] = p;
          });
        }

        // Update template's existing containers
        const plantsContainer = document.getElementById(`plants-list-${unitId}`);
        const devicesContainer = document.getElementById(`devices-list-${unitId}`);
        const thresholdsContainer = document.getElementById(`thresholds-list-${unitId}`);

        if (plantsContainer) {
          plantsContainer.innerHTML = this._renderPlantsList(plants, unitId);
        }
        if (devicesContainer) {
          devicesContainer.innerHTML = this._renderDevicesGrid(sensors, actuators, unitId);
        }
        if (thresholdsContainer) {
          thresholdsContainer.innerHTML = this._renderThresholdsSummary(unit?.thresholds);
        }

        // Also update the card counters
        this._updateUnitCardData(unitId, {
          ...unit,
          plant_count: plants?.length || 0,
          sensor_count: sensors?.length || 0,
          actuator_count: actuators?.length || 0
        });

        // Fallback: if no template containers found, try to render to general details container
        const detailsContainer = document.getElementById(`details-${unitId}`) ||
                                 card.querySelector('.unit-card-details') ||
                                 card.querySelector('.unit-details');

        if (detailsContainer && !plantsContainer && !devicesContainer) {
          detailsContainer.innerHTML = this._renderUnitDetails(unit, plants, sensors, actuators, schedules);
        }

      } catch (error) {
        console.error(`[UnitsUIManager] loadUnitDetails(${unitId}) failed:`, error);
        const detailsContainer = document.getElementById(`details-${unitId}`) ||
                                 card.querySelector('.unit-details');
        if (detailsContainer) {
          detailsContainer.innerHTML = `
            <div class="error-state">
              <i class="fas fa-exclamation-triangle"></i>
              <p>Failed to load unit details</p>
            </div>
          `;
        }
      }
    }

    _renderUnitDetails(unit, plants, sensors, actuators, schedules) {
      const unitId = unit?.id || this.state.currentUnitId;

      return `
        <div class="unit-details-content">
          <!-- Plants Section -->
          <div class="details-section">
            <div class="section-header">
              <h4><i class="fas fa-leaf"></i> Plants</h4>
              <button class="btn btn-sm btn-primary" data-action="add-plant" data-unit-id="${unitId}">
                <i class="fas fa-plus"></i> Add
              </button>
            </div>
            <div class="plants-list">
              ${this._renderPlantsList(plants, unitId)}
            </div>
          </div>

          <!-- Devices Section -->
          <div class="details-section">
            <div class="section-header">
              <h4><i class="fas fa-microchip"></i> Devices</h4>
              <button class="btn btn-sm btn-primary" data-action="link-device" data-unit-id="${unitId}">
                <i class="fas fa-link"></i> Link
              </button>
            </div>
            <div class="devices-grid">
              ${this._renderDevicesGrid(sensors, actuators, unitId)}
            </div>
          </div>

          <!-- Schedules Section -->
          <div class="details-section">
            <div class="section-header">
              <h4><i class="fas fa-clock"></i> Schedules</h4>
              <button class="btn btn-sm btn-primary" data-action="add-schedule" data-unit-id="${unitId}">
                <i class="fas fa-plus"></i> Add
              </button>
            </div>
            <div class="schedules-list">
              ${this._renderSchedulesList(schedules, unitId)}
            </div>
          </div>

          <!-- Thresholds Section -->
          <div class="details-section">
            <div class="section-header">
              <h4><i class="fas fa-sliders-h"></i> Thresholds</h4>
              <button class="btn btn-sm btn-secondary" data-action="edit-thresholds" data-unit-id="${unitId}">
                <i class="fas fa-edit"></i> Edit
              </button>
            </div>
            <div class="thresholds-summary">
              ${this._renderThresholdsSummary(unit?.thresholds)}
            </div>
          </div>
        </div>
      `;
    }

    _renderPlantsList(plants, unitId) {
      if (!plants || plants.length === 0) {
        return '<p class="empty-message">No plants added yet</p>';
      }

      return plants.map(plant => `
        <div class="plant-item ${plant.is_active ? 'active' : ''}" data-plant-id="${plant.plant_id || plant.id}">
          <div class="plant-info">
            <span class="plant-name">${this._escapeHtml(plant.name || plant.plant_name)}</span>
            <span class="plant-stage badge">${plant.current_stage || 'seedling'}</span>
          </div>
          <div class="plant-actions">
            ${!plant.is_active ? `
              <button class="btn btn-xs btn-secondary" data-action="set-active-plant" data-plant-id="${plant.plant_id || plant.id}" data-unit-id="${unitId}">
                Set Active
              </button>
            ` : '<span class="badge badge-success">Active</span>'}
            <button class="btn btn-xs btn-icon btn-danger" data-action="remove-plant" data-plant-id="${plant.plant_id || plant.id}" data-unit-id="${unitId}">
              <i class="fas fa-times"></i>
            </button>
          </div>
        </div>
      `).join('');
    }

    _renderDevicesGrid(sensors, actuators, unitId) {
      const allDevices = [];

      if (sensors) {
        sensors.forEach(s => allDevices.push({ ...s, type: 'sensor' }));
      }
      if (actuators) {
        actuators.forEach(a => allDevices.push({ ...a, type: 'actuator' }));
      }

      if (allDevices.length === 0) {
        return '<p class="empty-message">No devices linked</p>';
      }

      return allDevices.map(device => {
        const id = device.sensor_id || device.actuator_id || device.id;
        const name = device.name || device.sensor_name || device.actuator_name || `Device ${id}`;
        const typeLabel = device.type === 'sensor' ? 'Sensor' : 'Actuator';
        const icon = device.type === 'sensor' ? 'fa-thermometer-half' : 'fa-plug';

        return `
          <div class="device-chip" data-device-type="${device.type}" data-device-id="${id}">
            <i class="fas ${icon}"></i>
            <span class="device-name">${this._escapeHtml(name)}</span>
            <span class="device-type-badge">${typeLabel}</span>
            <button class="btn btn-xs btn-icon" data-action="unlink-device" data-device-type="${device.type}" data-device-id="${id}" data-unit-id="${unitId}">
              <i class="fas fa-unlink"></i>
            </button>
          </div>
        `;
      }).join('');
    }

    _renderSchedulesList(schedules, unitId) {
      if (!schedules || schedules.length === 0) {
        return '<p class="empty-message">No schedules configured</p>';
      }

      return schedules.map(schedule => {
        const isActive = schedule.is_active !== false;
        return `
          <div class="schedule-item ${isActive ? '' : 'inactive'}" data-schedule-id="${schedule.schedule_id || schedule.id}">
            <div class="schedule-info">
              <span class="schedule-name">${this._escapeHtml(schedule.name || 'Schedule')}</span>
              <span class="schedule-time">${schedule.start_time || '00:00'} - ${schedule.end_time || '23:59'}</span>
              <span class="schedule-days">${this._formatDays(schedule.days_of_week)}</span>
            </div>
            <div class="schedule-actions">
              <button class="btn btn-xs btn-icon" data-action="edit-schedule" data-schedule-id="${schedule.schedule_id || schedule.id}" data-unit-id="${unitId}">
                <i class="fas fa-edit"></i>
              </button>
              <button class="btn btn-xs btn-icon btn-danger" data-action="delete-schedule" data-schedule-id="${schedule.schedule_id || schedule.id}" data-unit-id="${unitId}">
                <i class="fas fa-trash"></i>
              </button>
            </div>
          </div>
        `;
      }).join('');
    }

    _renderThresholdsSummary(thresholds) {
      if (!thresholds) {
        return '<p class="empty-message">Using default thresholds</p>';
      }

      const items = [];
      if (thresholds.temperature) {
        items.push(`Temp: ${thresholds.temperature.min || '?'}-${thresholds.temperature.max || '?'}\u00b0C`);
      }
      if (thresholds.humidity) {
        items.push(`Humidity: ${thresholds.humidity.min || '?'}-${thresholds.humidity.max || '?'}%`);
      }
      if (thresholds.soil_moisture) {
        items.push(`Soil: ${thresholds.soil_moisture.min || '?'}-${thresholds.soil_moisture.max || '?'}%`);
      }

      return items.length > 0 ? items.map(i => `<span class="threshold-badge">${i}</span>`).join(' ') : '<p class="empty-message">No thresholds set</p>';
    }

    _formatDays(days) {
      if (!days) return 'Every day';
      if (typeof days === 'string') {
        try {
          days = JSON.parse(days);
        } catch {
          return days;
        }
      }
      if (Array.isArray(days)) {
        if (days.length === 7) return 'Every day';
        if (days.length === 0) return 'No days';
        const dayNames = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
        return days.map(d => dayNames[d] || d).join(', ');
      }
      return 'Every day';
    }

    // --------------------------------------------------------------------------
    // Environmental Data
    // --------------------------------------------------------------------------

    async refreshEnvironmentalData(unitId) {
      // Template uses id="env-chips-{unitId}" for the container
      const container = document.getElementById(`env-chips-${unitId}`) ||
                        document.querySelector(`[data-unit-env="${unitId}"]`);
      if (!container) return;

      try {
        const metrics = await this.dataService.loadEnvironmentalMetrics(unitId, { force: true });
        this._renderEnvironmentalChips(container, metrics);

        // Also update health data
        await this.loadUnitHealthMetrics(unitId);
      } catch (error) {
        console.error(`[UnitsUIManager] refreshEnvironmentalData(${unitId}) failed:`, error);
      }
    }

    _renderEnvironmentalChips(container, metrics) {
      if (!container) return;

      if (!metrics) {
        container.innerHTML = `
          <span class="env-chip is-muted" title="Temperature">
            <i class="fas fa-thermometer-half" aria-hidden="true"></i>
            <span class="env-chip-value">--°C</span>
          </span>
          <span class="env-chip is-muted" title="Humidity">
            <i class="fas fa-tint" aria-hidden="true"></i>
            <span class="env-chip-value">--%</span>
          </span>
        `;
        return;
      }

      const chips = [];
      ENV_METRICS.forEach(m => {
        const value = metrics[m.key];
        const hasMutedClass = value === undefined || value === null;
        const displayValue = hasMutedClass ? '--' : (typeof value === 'number' ? value.toFixed(1) : value);
        const mutedClass = hasMutedClass ? 'is-muted' : '';

        chips.push(`
          <span class="env-chip ${mutedClass}" title="${m.label}" data-metric="${m.key}">
            <i class="fas fa-${m.icon}" aria-hidden="true"></i>
            <span class="env-chip-value">${displayValue}${m.unit}</span>
          </span>
        `);
      });

      // Only show first 4 metrics to avoid clutter
      container.innerHTML = chips.slice(0, 4).join('');
    }

    async refreshAllEnvironmentalData() {
      // Get all unit cards and find their unit IDs
      const unitCards = document.querySelectorAll('.unit-card[data-unit-id]');
      const promises = Array.from(unitCards).map(card => {
        const unitId = card.dataset.unitId;
        if (unitId) return this.refreshEnvironmentalData(unitId);
        return Promise.resolve();
      });
      await Promise.all(promises);
    }

    // --------------------------------------------------------------------------
    // Health Metrics
    // --------------------------------------------------------------------------

    async loadUnitHealthMetrics(unitId) {
      try {
        const metrics = await this.dataService.loadHealthMetrics(unitId);
        this.updateHealthDisplay(unitId, metrics);
      } catch (error) {
        console.error(`[UnitsUIManager] loadUnitHealthMetrics(${unitId}) failed:`, error);
      }
    }

    updateHealthDisplay(unitId, metrics) {
      // API returns: { status, hardware_running, sensors[], actuators[], plants[], controller{}, polling{} }
      // Template structure:
      // - health-score-{unitId}: Overall health score
      // - plant-health-{unitId}: Plant health indicator
      // - device-health-{unitId}: Device health indicator
      // - env-health-{unitId}: Environmental health indicator

      if (!metrics) return;

      // Calculate health scores from API response
      const status = metrics.status || 'unknown';
      const isRunning = metrics.hardware_running;

      // Overall health score based on status
      let overallScore = 0;
      if (status === 'healthy' || status === 'HealthLevel.HEALTHY') overallScore = 100;
      else if (status === 'degraded' || status === 'HealthLevel.DEGRADED') overallScore = 60;
      else if (status === 'offline' || status === 'HealthLevel.OFFLINE') overallScore = 0;

      // Update overall health score
      const healthScoreEl = document.getElementById(`health-score-${unitId}`);
      if (healthScoreEl) {
        healthScoreEl.textContent = overallScore > 0 ? `${overallScore}%` : '--';
        healthScoreEl.className = `health-score ${this._getHealthClass(overallScore)}`;
      }

      // Update plant health indicator - based on number of plants and active plant
      const plantHealth = document.getElementById(`plant-health-${unitId}`);
      if (plantHealth) {
        const plants = metrics.plants || [];
        const activePlant = metrics.active_plant;
        const plantScore = plants.length > 0 ? (activePlant ? 100 : 50) : 0;
        const valueEl = plantHealth.querySelector('.indicator-value');
        if (valueEl) {
          valueEl.textContent = plants.length > 0 ? `${plants.length}` : '--';
        }
        plantHealth.className = `health-indicator ${plantScore > 0 ? (plantScore >= 80 ? 'health-good' : 'health-warning') : ''}`;
      }

      // Update device health indicator - based on sensors and actuators
      const deviceHealth = document.getElementById(`device-health-${unitId}`);
      if (deviceHealth) {
        const sensors = metrics.sensors || [];
        const actuators = metrics.actuators || [];
        const totalDevices = sensors.length + actuators.length;
        const onlineDevices = sensors.filter(s => s.is_active !== false).length +
                              actuators.filter(a => a.is_active !== false).length;
        const deviceScore = totalDevices > 0 ? Math.round((onlineDevices / totalDevices) * 100) : 0;
        const valueEl = deviceHealth.querySelector('.indicator-value');
        if (valueEl) {
          valueEl.textContent = totalDevices > 0 ? `${onlineDevices}/${totalDevices}` : '--';
        }
        deviceHealth.className = `health-indicator ${this._getHealthClass(deviceScore)}`;
      }

      // Update environmental health indicator - based on controller status
      const envHealth = document.getElementById(`env-health-${unitId}`);
      if (envHealth) {
        const controller = metrics.controller || {};
        const staleSensors = controller.stale_sensors || [];
        const envScore = isRunning ? (staleSensors.length === 0 ? 100 : 60) : 0;
        const valueEl = envHealth.querySelector('.indicator-value');
        if (valueEl) {
          valueEl.textContent = isRunning ? (staleSensors.length === 0 ? 'OK' : 'Stale') : '--';
        }
        envHealth.className = `health-indicator ${this._getHealthClass(envScore)}`;
      }
    }

    _getHealthClass(score) {
      if (!score || score === 0) return '';
      if (score >= 80) return 'health-good';
      if (score >= 50) return 'health-warning';
      return 'health-danger';
    }

    // --------------------------------------------------------------------------
    // Create Unit
    // --------------------------------------------------------------------------

    async handleCreateUnit(e) {
      e.preventDefault();
      const form = e.target;
      const formData = new FormData(form);
      const data = Object.fromEntries(formData.entries());
      const profileId = data.condition_profile_id || null;
      const profileMode = data.condition_profile_mode || 'active';
      const profileName = data.condition_profile_name || null;

      delete data.condition_profile_id;
      delete data.condition_profile_mode;
      delete data.condition_profile_name;
      delete data.profile_plant_type;
      delete data.profile_growth_stage;

      const submitBtn = form.querySelector('button[type="submit"]');
      if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Creating...';
      }

      try {
        const result = await this.dataService.createUnit(data);

        if (result.ok) {
          const unit = result.data || {};
          const unitId = unit.unit_id || unit.id || unit.unitId;
          if (profileId && unitId) {
            await API.PersonalizedLearning.applyConditionProfileToUnit(unitId, {
              profile_id: profileId,
              mode: profileMode,
              name: profileName || undefined,
            });
          }
          this.closeModal('createUnitModal');
          await this.loadUnitsOverview();
          this.showToast('Unit created successfully', 'success');
        } else {
          this.showToast(result.error || 'Failed to create unit', 'error');
        }
      } catch (error) {
        console.error('[UnitsUIManager] handleCreateUnit failed:', error);
        this.showToast('Failed to create unit', 'error');
      } finally {
        if (submitBtn) {
          submitBtn.disabled = false;
          submitBtn.innerHTML = '<i class="fas fa-plus"></i> Create Unit';
        }
      }
    }

    _getUserId() {
      const raw = document.body?.dataset?.userId;
      const parsed = raw ? parseInt(raw, 10) : NaN;
      return Number.isFinite(parsed) ? parsed : 1;
    }

    _toggleProfileSelectable(container, hasProfiles) {
      if (!container) return;
      container.hidden = !hasProfiles;
    }

    _handleUnitProfileLoad(payload) {
      const hasProfiles = Boolean(payload?.hasProfiles);
      if (!hasProfiles) {
        const hasFilters = Boolean(
          this.elements.unitProfilePlantType?.value?.trim() ||
          this.elements.unitProfileStage?.value?.trim()
        );
        if (hasFilters) {
          this._toggleProfileSelectable(this.elements.unitProfileSelectable, true);
          return;
        }
      }
      this._toggleProfileSelectable(this.elements.unitProfileSelectable, hasProfiles);
    }

    _handleUnitPlantProfileLoad(payload) {
      const hasProfiles = Boolean(payload?.hasProfiles);
      if (!hasProfiles) {
        const plantType = document.querySelector('#addPlantForm [name="plant_type"]')?.value?.trim();
        const stage = document.querySelector('#addPlantForm [name="current_stage"]')?.value?.trim();
        if (plantType || stage) {
          this._toggleProfileSelectable(this.elements.unitPlantProfileSelectable, true);
          return;
        }
      }
      this._toggleProfileSelectable(this.elements.unitPlantProfileSelectable, hasProfiles);
    }

    _initUnitProfileSelector() {
      if (!this.elements.unitProfileSelector || !window.ProfileSelector) {
        return;
      }
      this.unitProfileSelector = new window.ProfileSelector(
        this.elements.unitProfileSelector,
        {
          onSelect: async (profile, sectionType) => {
            let selectedProfile = profile;
            if (sectionType === 'public' && profile.shared_token) {
              const imported = await API.PersonalizedLearning.importSharedConditionProfile({
                user_id: this._getUserId(),
                token: profile.shared_token,
                name: profile.name || undefined,
                mode: 'active',
              });
              const payload = imported?.data || imported || {};
              if (payload.already_imported) {
                this.showToast('Profile already in your library. Selected existing profile.', 'info');
              }
              selectedProfile = payload.profile || imported?.profile || profile;
            }
            const mode = sectionType === 'template' ? 'active' : (profile.mode || 'active');
            this._setUnitProfileSelection(selectedProfile, mode);
            return selectedProfile;
          },
          onLoad: (payload) => this._handleUnitProfileLoad(payload),
        }
      );

      if (this.elements.unitProfilePlantType) {
        this.elements.unitProfilePlantType.addEventListener('input', () => {
          this._loadUnitProfileSelector();
        });
      }
      if (this.elements.unitProfileStage) {
        this.elements.unitProfileStage.addEventListener('change', () => {
          this._loadUnitProfileSelector();
        });
      }
    }

    _loadUnitProfileSelector() {
      if (!this.unitProfileSelector) return;
      const plantType = this.elements.unitProfilePlantType?.value?.trim();
      const growthStage = this.elements.unitProfileStage?.value?.trim();
      this.unitProfileSelector.load({
        user_id: this._getUserId(),
        plant_type: plantType || undefined,
        growth_stage: growthStage || undefined,
        target_type: 'unit',
      });
    }

    _setUnitProfileSelection(profile, mode) {
      if (this.elements.unitConditionProfileId) {
        this.elements.unitConditionProfileId.value = profile?.profile_id || '';
      }
      if (this.elements.unitConditionProfileMode) {
        this.elements.unitConditionProfileMode.value = mode || 'active';
      }
      if (this.elements.unitProfileSelectionSummary) {
        this.elements.unitProfileSelectionSummary.textContent = profile
          ? `Selected: ${profile.name || profile.profile_id}`
          : 'No profile selected';
      }
      if (this.elements.unitProfileChip) {
        this.elements.unitProfileChip.textContent = profile ? (profile.name || 'Profile selected') : 'No profile';
        this.elements.unitProfileChip.classList.toggle('active', Boolean(profile));
      }
    }

    _resetUnitProfileSelection() {
      this._setUnitProfileSelection(null, 'active');
      if (this.unitProfileSelector) {
        this.unitProfileSelector.setSelected('');
      }
    }

    async handleImportUnitProfile() {
      if (!this.elements.unitProfileImportToken) return;
      const token = this.elements.unitProfileImportToken.value.trim();
      if (!token) {
        this.showToast('Paste a share token first', 'error');
        return;
      }
      try {
        const imported = await API.PersonalizedLearning.importSharedConditionProfile({
          user_id: this._getUserId(),
          token,
          mode: 'active',
        });
        const payload = imported?.data || imported || {};
        if (payload.already_imported) {
          this.showToast('Profile already in your library. Selected existing profile.', 'info');
        }
        const profile = payload.profile || imported?.profile;
        if (profile) {
          this._setUnitProfileSelection(profile, 'active');
          this.unitProfileSelector.setSelected(profile.profile_id);
          this.showToast('Profile imported', 'success');
          this._loadUnitProfileSelector();
        }
      } catch (error) {
        console.error('[UnitsUIManager] import profile failed:', error);
        this.showToast('Failed to import profile', 'error');
      }
    }

    _initUnitPlantProfileSelector() {
      if (!this.elements.unitPlantProfileSelector || !window.ProfileSelector) {
        return;
      }
      this.unitPlantProfileSelector = new window.ProfileSelector(
        this.elements.unitPlantProfileSelector,
        {
          onSelect: async (profile, sectionType) => {
            let selectedProfile = profile;
            if (sectionType === 'public' && profile.shared_token) {
              const imported = await API.PersonalizedLearning.importSharedConditionProfile({
                user_id: this._getUserId(),
                token: profile.shared_token,
                name: profile.name || undefined,
                mode: 'active',
              });
              const payload = imported?.data || imported || {};
              if (payload.already_imported) {
                this.showToast('Profile already in your library. Selected existing profile.', 'info');
              }
              selectedProfile = payload.profile || imported?.profile || profile;
            }
            const mode = sectionType === 'template' ? 'active' : (profile.mode || 'active');
            this._setUnitPlantProfileSelection(selectedProfile, mode);
            return selectedProfile;
          },
          onLoad: (payload) => this._handleUnitPlantProfileLoad(payload),
        }
      );
      const plantTypeInput = document.querySelector('#addPlantForm [name="plant_type"]');
      if (plantTypeInput) {
        plantTypeInput.addEventListener('input', () => this._loadUnitPlantProfileSelector());
      }
      const stageInput = document.querySelector('#addPlantForm [name="current_stage"]');
      if (stageInput) {
        stageInput.addEventListener('change', () => this._loadUnitPlantProfileSelector());
      }
    }

    _loadUnitPlantProfileSelector() {
      if (!this.unitPlantProfileSelector) {
        this._initUnitPlantProfileSelector();
      }
      if (!this.unitPlantProfileSelector) return;
      const plantType = document.querySelector('#addPlantForm [name="plant_type"]')?.value?.trim();
      const stage = document.querySelector('#addPlantForm [name="current_stage"]')?.value?.trim();
      this.unitPlantProfileSelector.load({
        user_id: this._getUserId(),
        plant_type: plantType || undefined,
        growth_stage: stage || undefined,
        target_type: 'plant',
      });
    }

    _setUnitPlantProfileSelection(profile, mode) {
      if (this.elements.unitPlantConditionProfileId) {
        this.elements.unitPlantConditionProfileId.value = profile?.profile_id || '';
      }
      if (this.elements.unitPlantConditionProfileMode) {
        this.elements.unitPlantConditionProfileMode.value = mode || 'active';
      }
      if (this.elements.unitPlantProfileSelectionSummary) {
        this.elements.unitPlantProfileSelectionSummary.textContent = profile
          ? `Selected: ${profile.name || profile.profile_id}`
          : 'No profile selected';
      }
      if (this.elements.unitPlantProfileChip) {
        this.elements.unitPlantProfileChip.textContent = profile ? (profile.name || 'Profile selected') : 'No profile';
        this.elements.unitPlantProfileChip.classList.toggle('active', Boolean(profile));
      }
    }

    _resetUnitPlantProfileSelection() {
      this._setUnitPlantProfileSelection(null, 'active');
      if (this.unitPlantProfileSelector) {
        this.unitPlantProfileSelector.setSelected('');
      }
    }

    async handleImportUnitPlantProfile() {
      if (!this.elements.unitPlantProfileImportToken) return;
      const token = this.elements.unitPlantProfileImportToken.value.trim();
      if (!token) {
        this.showToast('Paste a share token first', 'error');
        return;
      }
      try {
          const imported = await API.PersonalizedLearning.importSharedConditionProfile({
            user_id: this._getUserId(),
            token,
            mode: 'active',
          });
          const payload = imported?.data || imported || {};
          if (payload.already_imported) {
            this.showToast('Profile already in your library. Selected existing profile.', 'info');
          }
          const profile = payload.profile || imported?.profile;
          if (profile) {
            this._setUnitPlantProfileSelection(profile, 'active');
            this.unitPlantProfileSelector?.setSelected(profile.profile_id);
            this.showToast('Profile imported', 'success');
            this._loadUnitPlantProfileSelector();
        }
      } catch (error) {
        console.error('[UnitsUIManager] import plant profile failed:', error);
        this.showToast('Failed to import profile', 'error');
      }
    }

    // --------------------------------------------------------------------------
    // Delete Unit
    // --------------------------------------------------------------------------

    async handleDeleteUnit(unitId) {
      if (!confirm('Are you sure you want to delete this unit? This action cannot be undone.')) {
        return;
      }

      try {
        const result = await this.dataService.deleteUnit(unitId);

        if (result.ok) {
          await this.loadUnitsOverview();
          this.showToast('Unit deleted successfully', 'success');
        } else {
          this.showToast(result.error || 'Failed to delete unit', 'error');
        }
      } catch (error) {
        console.error(`[UnitsUIManager] handleDeleteUnit(${unitId}) failed:`, error);
        this.showToast('Failed to delete unit', 'error');
      }
    }

    // --------------------------------------------------------------------------
    // Schedule Management
    // --------------------------------------------------------------------------

    async handleSaveSchedule(e) {
      e.preventDefault();
      const form = e.target;
      const formData = new FormData(form);
      const data = Object.fromEntries(formData.entries());

      const scheduleId = data.schedule_id;
      const unitId = data.unit_id || this.state.currentUnitId;

      // Build days array from checkboxes
      const days = [];
      form.querySelectorAll('input[name="days"]:checked').forEach(cb => {
        days.push(parseInt(cb.value, 10));
      });
      data.days_of_week = days;

      try {
        let result;
        if (scheduleId) {
          result = await this.dataService.updateSchedule(scheduleId, { ...data, unit_id: unitId });
        } else {
          result = await this.dataService.createSchedule({ ...data, unit_id: unitId });
        }

        if (result.ok) {
          this.closeModal('scheduleModal');
          // Also hide schedule form container if exists
          const formContainer = document.getElementById('scheduleFormContainer');
          if (formContainer) formContainer.classList.add('hidden');
          if (unitId) await this.loadUnitDetails(unitId);
          this.showToast('Schedule saved successfully', 'success');
        } else {
          this.showToast(result.error || 'Failed to save schedule', 'error');
        }
      } catch (error) {
        console.error('[UnitsUIManager] handleSaveSchedule failed:', error);
        this.showToast('Failed to save schedule', 'error');
      }
    }

    async handleDeleteSchedule(scheduleId, unitId) {
      if (!confirm('Delete this schedule?')) return;

      try {
        const result = await this.dataService.deleteSchedule(scheduleId, unitId);

        if (result.ok) {
          if (unitId) await this.loadUnitDetails(unitId);
          this.showToast('Schedule deleted', 'success');
        } else {
          this.showToast(result.error || 'Failed to delete schedule', 'error');
        }
      } catch (error) {
        console.error(`[UnitsUIManager] handleDeleteSchedule(${scheduleId}) failed:`, error);
        this.showToast('Failed to delete schedule', 'error');
      }
    }

    openScheduleModal(unitId, scheduleData = null) {
      this.state.currentUnitId = unitId;

      // Check for template's schedule form container first
      const formContainer = document.getElementById('scheduleFormContainer');
      if (formContainer) {
        formContainer.classList.remove('hidden');
        const form = document.getElementById('deviceScheduleForm');
        if (form) form.reset();
        const scheduleTypeSelect = document.getElementById('scheduleType');
        if (scheduleTypeSelect) {
          delete scheduleTypeSelect.dataset.autoDefaultApplied;
        }
        
        // Set title based on action
        const title = document.getElementById('scheduleFormTitle');
        if (title) {
          title.textContent = scheduleData ? 'Edit Device Schedule' : 'Add Device Schedule';
        }
        
        // Set unit ID
        const unitInput = document.getElementById('scheduleUnitId');
        if (unitInput) unitInput.value = unitId;
        
        // Populate if editing
        if (scheduleData) {
          this.populateScheduleForm(scheduleData);
        }
        return;
      }

      // Fallback to modal
      const modal = document.getElementById('scheduleModal') || document.getElementById('schedule-modal');
      if (!modal) return;

      const form = modal.querySelector('form');
      if (form) {
        form.reset();
        const scheduleTypeSelect = document.getElementById('scheduleType');
        if (scheduleTypeSelect) {
          delete scheduleTypeSelect.dataset.autoDefaultApplied;
        }

        // Set unit ID
        const unitInput = form.querySelector('[name="unit_id"]');
        if (unitInput) unitInput.value = unitId;

        // Populate if editing
        if (scheduleData) {
          const scheduleIdInput = form.querySelector('[name="schedule_id"]');
          if (scheduleIdInput) scheduleIdInput.value = scheduleData.schedule_id || scheduleData.id;

          const nameInput = form.querySelector('[name="name"]');
          if (nameInput) nameInput.value = scheduleData.name || '';

          const startInput = form.querySelector('[name="start_time"]');
          if (startInput) startInput.value = scheduleData.start_time || '';

          const endInput = form.querySelector('[name="end_time"]');
          if (endInput) endInput.value = scheduleData.end_time || '';

          // Days checkboxes
          const days = scheduleData.days_of_week || [];
          form.querySelectorAll('input[name="days"]').forEach(cb => {
            cb.checked = days.includes(parseInt(cb.value, 10));
          });
        }
      }

      this.openModal(modal.id);
    }

    /**
     * Populate schedule form with existing data
     */
    populateScheduleForm(scheduleData) {
      const setVal = (id, val) => {
        const el = document.getElementById(id);
        if (el) el.value = val || '';
      };
      
      setVal('scheduleId', scheduleData.schedule_id || scheduleData.id);
      setVal('scheduleName', scheduleData.name);
      setVal('scheduleDeviceType', scheduleData.device_type);
      setVal('scheduleType', scheduleData.schedule_type || 'simple');
      setVal('scheduleStartTime', scheduleData.start_time);
      setVal('scheduleEndTime', scheduleData.end_time);
      setVal('schedulePriority', scheduleData.priority || 50);
      setVal('scheduleValue', scheduleData.value);
      setVal('intervalMinutes', scheduleData.interval_minutes || '');
      setVal('durationMinutes', scheduleData.duration_minutes || '');
      
      const enabledCb = document.getElementById('scheduleEnabled');
      if (enabledCb) enabledCb.checked = scheduleData.enabled !== false;
      
      // Days of week
      const form = document.getElementById('deviceScheduleForm');
      const days = scheduleData.days_of_week || [0,1,2,3,4,5,6];
      form?.querySelectorAll('input[name="days_of_week"]').forEach(cb => {
        cb.checked = days.includes(parseInt(cb.value, 10));
      });
      
      // Photoperiod settings
      if (scheduleData.photoperiod) {
        setVal('photoperiodSource', scheduleData.photoperiod.source);
        setVal('sensorThreshold', scheduleData.photoperiod.sensor_threshold);
      }
      
      // Show/hide photoperiod section
      this.updatePhotoperiodVisibility();
    }

    closeScheduleForm() {
      const formContainer = document.getElementById('scheduleFormContainer');
      if (formContainer) {
        formContainer.classList.add('hidden');
      }
      
      const form = document.getElementById('deviceScheduleForm');
      if (form) form.reset();
    }

    updatePhotoperiodVisibility() {
      const typeSelect = document.getElementById('scheduleType');
      const photoperiodSection = document.getElementById('photoperiodSettings');
      const intervalSection = document.getElementById('intervalSettings');
      
      if (typeSelect && photoperiodSection) {
        photoperiodSection.classList.toggle('hidden', typeSelect.value !== 'photoperiod');
      }
      if (typeSelect && intervalSection) {
        intervalSection.classList.toggle('hidden', typeSelect.value !== 'interval');
      }
      this.updateScheduleTimeRequirements();
    }

    updateScheduleTimeRequirements() {
      const deviceTypeSelect = document.getElementById('scheduleDeviceType');
      const scheduleTypeSelect = document.getElementById('scheduleType');
      const endTimeInput = document.getElementById('scheduleEndTime');
      const startTimeInput = document.getElementById('scheduleStartTime');
      const photoperiodSource = document.getElementById('photoperiodSource')?.value;

      if (!endTimeInput || !scheduleTypeSelect || !startTimeInput) return;

      const scheduleId = document.getElementById('scheduleId')?.value;
      const autoDefaultApplied = scheduleTypeSelect.dataset.autoDefaultApplied === 'true';
      if (
        deviceTypeSelect?.value === 'light'
        && !scheduleId
        && !autoDefaultApplied
        && (!scheduleTypeSelect.value || scheduleTypeSelect.value === 'simple')
      ) {
        scheduleTypeSelect.value = 'automatic';
        scheduleTypeSelect.dataset.autoDefaultApplied = 'true';
      }

      const isAutomaticLight =
        deviceTypeSelect?.value === 'light' && scheduleTypeSelect?.value === 'automatic';
      const isSensorBasedPhotoperiod =
        scheduleTypeSelect?.value === 'photoperiod'
        && (photoperiodSource === 'sensor' || photoperiodSource === 'sun_api');

      if (isAutomaticLight || isSensorBasedPhotoperiod) {
        endTimeInput.removeAttribute('required');
      } else {
        endTimeInput.setAttribute('required', 'required');
      }
      if (isSensorBasedPhotoperiod) {
        startTimeInput.removeAttribute('required');
        startTimeInput.value = '00:00';
        endTimeInput.value = '00:00';
      } else {
        startTimeInput.setAttribute('required', 'required');
      }
    }

    // --------------------------------------------------------------------------
    // V3 Schedule Management (Enhanced Features)
    // --------------------------------------------------------------------------

    /**
     * Load and render schedules using v3 API
     */
    async loadSchedulesV3(unitId) {
      if (!unitId) unitId = this.state.currentUnitId;
      if (!unitId) return;

      const listContainer = document.getElementById('scheduleManagementContent');
      const summaryContainer = document.getElementById('schedulesSummary');

      try {
        // Load schedules and summary
        const [schedules, summary] = await Promise.all([
          this.dataService.loadSchedulesV3(unitId, { force: true }),
          this.dataService.getScheduleSummary(unitId, { force: true })
        ]);

        // Store for editing
        this.schedulesById = new Map();
        schedules.forEach(s => {
          if (s.schedule_id) this.schedulesById.set(s.schedule_id, s);
        });

        // Render summary
        if (summaryContainer) {
          this.renderScheduleSummary(summary, summaryContainer);
        }

        // Render list
        if (listContainer) {
          this.renderSchedulesListV3(schedules, unitId, listContainer);
        }

      } catch (error) {
        console.error('[UnitsUIManager] loadSchedulesV3 failed:', error);
      }
    }

    renderScheduleSummary(summary, container) {
      if (!summary) {
        container.innerHTML = '';
        return;
      }
      container.innerHTML = `
        <div class="summary-grid">
          <div class="summary-stat">
            <span class="stat-value">${summary.total_schedules || 0}</span>
            <span class="stat-label">Total</span>
          </div>
          <div class="summary-stat">
            <span class="stat-value">${summary.enabled_schedules || 0}</span>
            <span class="stat-label">Enabled</span>
          </div>
          <div class="summary-stat">
            <span class="stat-value">${summary.light_hours?.toFixed(1) || '0'}h</span>
            <span class="stat-label">Light Hours</span>
          </div>
        </div>
      `;
    }

    renderSchedulesListV3(schedules, unitId, container) {
      if (!schedules || schedules.length === 0) {
        container.innerHTML = `
          <div class="empty-state">
            <i class="fas fa-calendar-times"></i>
            <p>No schedules configured</p>
          </div>
        `;
        return;
      }

      const html = schedules.map(schedule => this.renderScheduleCardV3(schedule, unitId)).join('');
      container.innerHTML = `<div class="schedules-grid">${html}</div>`;

      // Attach event handlers
      container.querySelectorAll('[data-action="edit-schedule"]').forEach(btn => {
        btn.addEventListener('click', () => {
          const scheduleId = parseInt(btn.dataset.scheduleId);
          const schedule = this.schedulesById?.get(scheduleId);
          this.openScheduleModal(unitId, schedule);
        });
      });

      container.querySelectorAll('[data-action="toggle-schedule"]').forEach(btn => {
        btn.addEventListener('click', () => {
          const scheduleId = parseInt(btn.dataset.scheduleId);
          const enabled = btn.dataset.enabled !== 'true';
          this.toggleScheduleV3(unitId, scheduleId, enabled);
        });
      });

      container.querySelectorAll('[data-action="delete-schedule"]').forEach(btn => {
        btn.addEventListener('click', () => {
          const scheduleId = parseInt(btn.dataset.scheduleId);
          this.deleteScheduleV3(unitId, scheduleId);
        });
      });

      container.querySelectorAll('[data-action="view-execution-log"]').forEach(btn => {
        btn.addEventListener('click', () => {
          const scheduleId = parseInt(btn.dataset.scheduleId);
          this.showExecutionLog(unitId, scheduleId);
        });
      });
    }

    renderScheduleCardV3(schedule, unitId) {
      const deviceIcons = {
        light: 'fas fa-lightbulb',
        fan: 'fas fa-fan',
        pump: 'fas fa-tint',
        heater: 'fas fa-fire',
        cooler: 'fas fa-snowflake',
        humidifier: 'fas fa-cloud',
        dehumidifier: 'fas fa-wind'
      };
      const icon = deviceIcons[schedule.device_type] || 'fas fa-clock';
      const statusClass = schedule.enabled ? 'status-enabled' : 'status-disabled';
      const statusText = schedule.enabled ? 'Enabled' : 'Disabled';
      
      const typeLabels = {
        simple: 'Time-based',
        photoperiod: 'Photoperiod',
        interval: 'Interval',
        automatic: 'Plant Stage'
      };
      const typeLabel = typeLabels[schedule.schedule_type] || schedule.schedule_type || 'simple';
      const isAutomatic = schedule.schedule_type === 'automatic';
      
      const dayNames = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
      const daysDisplay = schedule.days_of_week?.length === 7 ? 'Every day' :
        schedule.days_of_week?.map(d => dayNames[d]).join(', ') || 'Every day';

      return `
        <div class="schedule-card ${statusClass} ${isAutomatic ? 'schedule-automatic' : ''}" data-schedule-id="${schedule.schedule_id}">
          <div class="schedule-select">
            <input type="checkbox" class="schedule-select-checkbox form-check-input" data-schedule-id="${schedule.schedule_id}" title="Select for bulk actions">
          </div>
          <div class="schedule-header">
            <div class="schedule-icon"><i class="${icon}"></i></div>
            <div class="schedule-info">
              <h4 class="schedule-name">${this._escapeHtml(schedule.name || schedule.device_type)}</h4>
              <span class="schedule-device">${schedule.device_type}</span>
              <span class="schedule-type-badge badge ${isAutomatic ? 'badge-info' : 'badge-secondary'}">${typeLabel}</span>
            </div>
            <span class="schedule-status badge ${schedule.enabled ? 'badge-success' : 'badge-secondary'}">${statusText}</span>
          </div>
          <div class="schedule-details">
            <div class="schedule-time"><i class="fas fa-clock"></i> ${schedule.start_time} - ${schedule.end_time}</div>
            <div class="schedule-days"><i class="fas fa-calendar-week"></i> ${daysDisplay}</div>
            ${schedule.priority ? `<div class="schedule-priority"><i class="fas fa-sort-numeric-up"></i> Priority: ${schedule.priority}</div>` : ''}
            ${schedule.value ? `<div class="schedule-value"><i class="fas fa-sliders-h"></i> Value: ${schedule.value}%</div>` : ''}
          </div>
          <div class="schedule-actions">
            <button type="button" class="btn btn-xs btn-icon" data-action="edit-schedule" data-schedule-id="${schedule.schedule_id}" data-unit-id="${unitId}" title="Edit">
              <i class="fas fa-edit"></i>
            </button>
            <button type="button" class="btn btn-xs btn-icon ${schedule.enabled ? 'btn-warning' : 'btn-success'}" data-action="toggle-schedule" data-schedule-id="${schedule.schedule_id}" data-enabled="${schedule.enabled}" title="${schedule.enabled ? 'Disable' : 'Enable'}">
              <i class="fas fa-${schedule.enabled ? 'pause' : 'play'}"></i>
            </button>
            <button type="button" class="btn btn-xs btn-icon" data-action="view-execution-log" data-schedule-id="${schedule.schedule_id}" title="Execution Log">
              <i class="fas fa-list-alt"></i>
            </button>
            <button type="button" class="btn btn-xs btn-icon btn-danger" data-action="delete-schedule" data-schedule-id="${schedule.schedule_id}" data-unit-id="${unitId}" title="Delete">
              <i class="fas fa-trash"></i>
            </button>
          </div>
        </div>
      `;
    }

    /**
     * Save schedule using v3 API
     */
    async handleSaveScheduleV3(e) {
      e.preventDefault();
      const form = e.target;
      const formData = new FormData(form);
      const data = Object.fromEntries(formData.entries());

      const scheduleId = data.schedule_id;
      const unitId = this.state.currentUnitId;
      const scheduleType = data.schedule_type || 'simple';
      const photoperiodSource = data.photoperiod_source || 'schedule';
      const isSensorBasedPhotoperiod =
        scheduleType === 'photoperiod'
        && (photoperiodSource === 'sensor' || photoperiodSource === 'sun_api');

      if (!unitId) {
        this.showToast('No unit selected', 'error');
        return;
      }

      // Build days array
      const days = [];
      form.querySelectorAll('input[name="days_of_week"]:checked').forEach(cb => {
        days.push(parseInt(cb.value, 10));
      });

      const payload = {
        name: data.name || '',
        device_type: data.device_type || '',
        schedule_type: scheduleType,
        start_time: data.start_time || '',
        end_time: data.end_time || '',
        days_of_week: days.length > 0 ? days : [0,1,2,3,4,5,6],
        priority: parseInt(data.priority) || 50,
        enabled: data.enabled === 'on' || data.enabled === true
      };

      if (data.value) payload.value = parseFloat(data.value);

      // Photoperiod config
      if (payload.schedule_type === 'photoperiod') {
        payload.photoperiod = {
          source: photoperiodSource,
          sensor_threshold: data.sensor_threshold ? parseInt(data.sensor_threshold) : null
        };
      }

      if (payload.schedule_type === 'interval') {
        const intervalMinutes = parseInt(data.interval_minutes || '', 10);
        const durationMinutes = parseInt(data.duration_minutes || '', 10);
        if (!intervalMinutes || !durationMinutes) {
          this.showToast('Interval schedules require interval and duration minutes', 'error');
          return;
        }
        if (durationMinutes > intervalMinutes) {
          this.showToast('Duration must be less than or equal to interval', 'error');
          return;
        }
        payload.interval_minutes = intervalMinutes;
        payload.duration_minutes = durationMinutes;
      }

      if (isSensorBasedPhotoperiod) {
        payload.start_time = '00:00';
        payload.end_time = '00:00';
      }

      try {
        let result;
        if (scheduleId) {
          result = await this.dataService.updateScheduleV3(unitId, parseInt(scheduleId), payload);
        } else {
          result = await this.dataService.createScheduleV3(unitId, payload);
        }

        if (result.ok) {
          this.closeScheduleForm();
          await this.loadSchedulesV3(unitId);
          this.showToast('Schedule saved successfully', 'success');
        } else {
          this.showToast(result.error || 'Failed to save schedule', 'error');
        }
      } catch (error) {
        console.error('[UnitsUIManager] handleSaveScheduleV3 failed:', error);
        this.showToast('Failed to save schedule', 'error');
      }
    }

    async toggleScheduleV3(unitId, scheduleId, enabled) {
      try {
        const result = await this.dataService.toggleScheduleV3(unitId, scheduleId, enabled);
        if (result.ok) {
          await this.loadSchedulesV3(unitId);
          this.showToast(`Schedule ${enabled ? 'enabled' : 'disabled'}`, 'success');
        } else {
          this.showToast(result.error || 'Failed to toggle schedule', 'error');
        }
      } catch (error) {
        console.error('[UnitsUIManager] toggleScheduleV3 failed:', error);
        this.showToast('Failed to toggle schedule', 'error');
      }
    }

    async deleteScheduleV3(unitId, scheduleId) {
      if (!confirm('Delete this schedule?')) return;

      try {
        const result = await this.dataService.deleteScheduleV3(unitId, scheduleId);
        if (result.ok) {
          await this.loadSchedulesV3(unitId);
          this.showToast('Schedule deleted', 'success');
        } else {
          this.showToast(result.error || 'Failed to delete schedule', 'error');
        }
      } catch (error) {
        console.error('[UnitsUIManager] deleteScheduleV3 failed:', error);
        this.showToast('Failed to delete schedule', 'error');
      }
    }

    /**
     * Show schedule preview panel
     */
    async showSchedulePreview() {
      const panel = document.getElementById('schedulePreviewPanel');
      const content = document.getElementById('schedulePreviewContent');
      const unitId = this.state.currentUnitId;

      if (!panel || !content || !unitId) return;

      content.innerHTML = '<div class="loading"><i class="fas fa-spinner fa-spin"></i> Loading...</div>';
      panel.classList.remove('hidden');

      try {
        const data = await this.dataService.previewSchedules(unitId, { hours: 24, force: true });

        if (!data.events || data.events.length === 0) {
          content.innerHTML = '<div class="empty-state"><i class="fas fa-calendar-check"></i><p>No events in the next 24 hours</p></div>';
          return;
        }

        const html = data.events.map(event => {
          const time = new Date(event.event_time).toLocaleString();
          const icon = event.event_type === 'activate' ? 'fa-play text-success' : 'fa-stop text-danger';
          return `
            <div class="preview-event">
              <i class="fas ${icon}"></i>
              <div class="event-details">
                <strong>${this._escapeHtml(event.schedule_name)}</strong>
                <span class="event-device">${event.device_type}</span>
              </div>
              <span class="event-time">${time}</span>
            </div>
          `;
        }).join('');

        content.innerHTML = `<div class="preview-events">${html}</div>`;
      } catch (error) {
        content.innerHTML = '<div class="error-state">Failed to load preview</div>';
      }
    }

    /**
     * Show conflicts panel
     */
    async showConflicts() {
      const panel = document.getElementById('scheduleConflictsPanel');
      const content = document.getElementById('scheduleConflictsContent');
      const unitId = this.state.currentUnitId;

      if (!panel || !content || !unitId) return;

      content.innerHTML = '<div class="loading"><i class="fas fa-spinner fa-spin"></i> Checking...</div>';
      panel.classList.remove('hidden');

      try {
        const data = await this.dataService.detectConflicts(unitId, { force: true });

        if (!data.has_conflicts) {
          content.innerHTML = '<div class="success-state"><i class="fas fa-check-circle text-success"></i><p>No conflicts detected!</p></div>';
          return;
        }

        const html = data.conflicts.map(conflict => `
          <div class="conflict-item">
            <div class="conflict-schedules">
              <strong>${this._escapeHtml(conflict.schedule_a_name)}</strong>
              <span class="vs">vs</span>
              <strong>${this._escapeHtml(conflict.schedule_b_name)}</strong>
            </div>
            <div class="conflict-details">
              <span>Overlap: ${conflict.overlap_start} - ${conflict.overlap_end}</span>
              <span>Resolution: ${conflict.resolution}</span>
            </div>
          </div>
        `).join('');

        content.innerHTML = `
          <div class="conflicts-warning">
            <i class="fas fa-exclamation-triangle"></i>
            <span>${data.count} conflict(s) found</span>
          </div>
          <div class="conflicts-list">${html}</div>
        `;
      } catch (error) {
        content.innerHTML = '<div class="error-state">Failed to check conflicts</div>';
      }
    }

    /**
     * Show history panel
     */
    async showScheduleHistory() {
      const panel = document.getElementById('scheduleHistoryPanel');
      const content = document.getElementById('scheduleHistoryContent');
      const unitId = this.state.currentUnitId;

      if (!panel || !content || !unitId) return;

      content.innerHTML = '<div class="loading"><i class="fas fa-spinner fa-spin"></i> Loading...</div>';
      panel.classList.remove('hidden');

      try {
        const data = await this.dataService.getScheduleHistory(unitId, { limit: 50, force: true });

        if (!data.history || data.history.length === 0) {
          content.innerHTML = '<div class="empty-state"><i class="fas fa-history"></i><p>No history available</p></div>';
          return;
        }

        const html = data.history.map(entry => {
          const time = new Date(entry.created_at).toLocaleString();
          const actionIcons = {
            created: 'fa-plus text-success',
            updated: 'fa-edit text-warning',
            deleted: 'fa-trash text-danger',
            enabled: 'fa-play text-success',
            disabled: 'fa-pause text-warning'
          };
          const icon = actionIcons[entry.action] || 'fa-clock';
          return `
            <div class="history-entry">
              <i class="fas ${icon}"></i>
              <div class="entry-details">
                <span class="entry-action">${entry.action}</span>
                <span class="entry-source">by ${entry.source || 'user'}</span>
              </div>
              <span class="entry-time">${time}</span>
            </div>
          `;
        }).join('');

        content.innerHTML = `<div class="history-list">${html}</div>`;
      } catch (error) {
        content.innerHTML = '<div class="error-state">Failed to load history</div>';
      }
    }

    /**
     * Show execution log for a specific schedule
     */
    async showExecutionLog(unitId, scheduleId) {
      const panel = document.getElementById('scheduleHistoryPanel');
      const content = document.getElementById('scheduleHistoryContent');
      const title = panel?.querySelector('h4');

      if (!panel || !content) return;

      if (title) title.innerHTML = '<i class="fas fa-list-alt"></i> Execution Log';
      content.innerHTML = '<div class="loading"><i class="fas fa-spinner fa-spin"></i> Loading...</div>';
      panel.classList.remove('hidden');

      try {
        const data = await this.dataService.getExecutionLog(unitId, scheduleId, { limit: 50, force: true });

        if (!data.execution_log || data.execution_log.length === 0) {
          content.innerHTML = '<div class="empty-state"><i class="fas fa-list-alt"></i><p>No execution history</p></div>';
          return;
        }

        const html = data.execution_log.map(entry => {
          const time = new Date(entry.execution_time).toLocaleString();
          const icon = entry.success ? 'fa-check-circle text-success' : 'fa-times-circle text-danger';
          return `
            <div class="execution-entry ${entry.success ? 'success' : 'failed'}">
              <i class="fas ${icon}"></i>
              <div class="entry-details">
                <span class="entry-action">${entry.action}</span>
                ${entry.retry_count > 0 ? `<span class="entry-retries">${entry.retry_count} retries</span>` : ''}
                ${entry.response_time_ms ? `<span class="entry-timing">${entry.response_time_ms}ms</span>` : ''}
              </div>
              <span class="entry-time">${time}</span>
            </div>
          `;
        }).join('');

        content.innerHTML = `<div class="execution-list">${html}</div>`;
      } catch (error) {
        content.innerHTML = '<div class="error-state">Failed to load execution log</div>';
      }
    }

    closePanel(panelId) {
      const panel = document.getElementById(panelId);
      if (panel) panel.classList.add('hidden');
    }

    // --------------------------------------------------------------------------
    // Auto-Generate & Templates
    // --------------------------------------------------------------------------

    /**
     * Auto-generate schedules based on plant stage
     */
    async handleAutoGenerateSchedules() {
      const unitId = this.state.currentUnitId;
      if (!unitId) {
        this.showToast('No unit selected', 'error');
        return;
      }

      // Confirm with user
      const confirmed = confirm(
        'This will generate schedules based on the current plant stage.\n\n' +
        'Existing automatic schedules will be replaced.\n\n' +
        'Continue?'
      );

      if (!confirmed) return;

      this.showToast('Generating schedules...', 'info');

      const result = await this.dataService.autoGenerateSchedules(unitId, {
        replace_existing: true
      });

      if (result.ok) {
        const count = result.data?.schedules_created || result.data?.created?.length || 0;
        this.showToast(`Generated ${count} schedule${count !== 1 ? 's' : ''} successfully`, 'success');
        // Reload schedules
        await this.loadScheduleTab(unitId);
      } else {
        this.showToast(result.error || 'Failed to generate schedules', 'error');
      }
    }

    /**
     * Show schedule templates panel
     */
    async showScheduleTemplates() {
      const panel = document.getElementById('scheduleTemplatesPanel');
      const content = document.getElementById('templatesList');
      const unitId = this.state.currentUnitId;

      if (!panel || !content || !unitId) return;

      content.innerHTML = '<div class="loading"><i class="fas fa-spinner fa-spin"></i> Loading templates...</div>';
      panel.classList.remove('hidden');

      try {
        const data = await this.dataService.getScheduleTemplates(unitId, { force: true });

        if (!data.templates || data.templates.length === 0) {
          content.innerHTML = `
            <div class="empty-state">
              <i class="fas fa-file-alt"></i>
              <p>No templates available</p>
              <small>Add a plant to the unit to see stage-based templates</small>
            </div>
          `;
          return;
        }

        // Store templates for applying
        this.currentTemplates = data.templates;

        const html = data.templates.map((template, idx) => {
          const deviceIcon = this._getDeviceIcon(template.device_type);
          return `
            <div class="template-item" data-template-index="${idx}">
              <label class="template-checkbox">
                <input type="checkbox" name="template_${idx}" value="${idx}" checked>
              </label>
              <div class="template-info">
                <div class="template-header">
                  <i class="fas ${deviceIcon}"></i>
                  <strong>${template.name || template.device_type}</strong>
                </div>
                <div class="template-details">
                  <span><i class="far fa-clock"></i> ${template.start_time} - ${template.end_time}</span>
                  ${template.value ? `<span><i class="fas fa-sliders-h"></i> ${template.value}%</span>` : ''}
                </div>
                <div class="template-meta">
                  <span class="badge">${template.schedule_type || 'automatic'}</span>
                  ${data.plant_info?.stage ? `<span class="badge badge-secondary">${data.plant_info.stage} stage</span>` : ''}
                </div>
              </div>
            </div>
          `;
        }).join('');

        const plantInfo = data.plant_info ? `
          <div class="plant-info-banner mb-2">
            <i class="fas fa-seedling"></i>
            <span><strong>${data.plant_info.name}</strong> - ${data.plant_info.stage} stage</span>
          </div>
        ` : '';

        content.innerHTML = plantInfo + `<div class="templates-grid">${html}</div>`;
      } catch (error) {
        console.error('Error loading templates:', error);
        content.innerHTML = '<div class="error-state">Failed to load templates</div>';
      }
    }

    /**
     * Apply selected templates to create schedules
     */
    async handleApplyTemplates() {
      const unitId = this.state.currentUnitId;
      if (!unitId || !this.currentTemplates) {
        this.showToast('No templates to apply', 'error');
        return;
      }

      const templatesList = document.getElementById('templatesList');
      const checkboxes = templatesList?.querySelectorAll('input[type="checkbox"]:checked');

      if (!checkboxes || checkboxes.length === 0) {
        this.showToast('Please select at least one template', 'warning');
        return;
      }

      // Get selected template indices
      const selectedIndices = Array.from(checkboxes).map(cb => parseInt(cb.value));
      const selectedTemplates = selectedIndices.map(idx => this.currentTemplates[idx]).filter(Boolean);

      this.showToast('Creating schedules...', 'info');

      // Create schedules from selected templates
      let successCount = 0;
      let errorCount = 0;

      for (const template of selectedTemplates) {
        const payload = {
          name: template.name || `${template.device_type} Schedule`,
          device_type: template.device_type,
          schedule_type: 'automatic',
          start_time: template.start_time,
          end_time: template.end_time,
          enabled: true,
          days_of_week: [0, 1, 2, 3, 4, 5, 6],
          priority: template.priority || 50,
          value: template.value || null
        };

        const result = await this.dataService.createScheduleV3(unitId, payload);
        if (result.ok) {
          successCount++;
        } else {
          errorCount++;
          console.error(`Failed to create schedule for ${template.device_type}:`, result.error);
        }
      }

      // Close panel and show result
      this.closePanel('scheduleTemplatesPanel');
      this.currentTemplates = null;

      if (successCount > 0) {
        this.showToast(`Created ${successCount} schedule${successCount !== 1 ? 's' : ''} successfully`, 'success');
        await this.loadScheduleTab(unitId);
      }
      if (errorCount > 0) {
        this.showToast(`Failed to create ${errorCount} schedule${errorCount !== 1 ? 's' : ''}`, 'error');
      }
    }

    // --------------------------------------------------------------------------
    // Bulk Schedule Operations
    // --------------------------------------------------------------------------

    /**
     * Handle bulk enable/disable/delete for schedules
     */
    async handleBulkScheduleAction(action) {
      const unitId = this.state.currentUnitId;
      if (!unitId) return;

      const checkboxes = document.querySelectorAll('.schedule-select-checkbox:checked');
      if (checkboxes.length === 0) {
        this.showToast('Please select at least one schedule', 'warning');
        return;
      }

      const scheduleIds = Array.from(checkboxes).map(cb => parseInt(cb.dataset.scheduleId));

      // Confirm delete action
      if (action === 'delete') {
        const confirmed = confirm(`Are you sure you want to delete ${scheduleIds.length} schedule${scheduleIds.length !== 1 ? 's' : ''}?`);
        if (!confirmed) return;
      }

      this.showToast(`${action === 'enable' ? 'Enabling' : action === 'disable' ? 'Disabling' : 'Deleting'} ${scheduleIds.length} schedule${scheduleIds.length !== 1 ? 's' : ''}...`, 'info');

      const result = await this.dataService.bulkUpdateSchedules(unitId, scheduleIds, action);

      if (result.ok) {
        const successCount = result.data?.results?.success?.length || scheduleIds.length;
        this.showToast(`${successCount} schedule${successCount !== 1 ? 's' : ''} ${action}d successfully`, 'success');
        // Reset selection and reload
        this.clearScheduleSelection();
        await this.loadScheduleTab(unitId);
      } else {
        this.showToast(result.error || `Failed to ${action} schedules`, 'error');
      }
    }

    /**
     * Clear schedule selection and hide bulk bar
     */
    clearScheduleSelection() {
      const checkboxes = document.querySelectorAll('.schedule-select-checkbox');
      checkboxes.forEach(cb => cb.checked = false);

      const selectAll = document.getElementById('selectAllSchedules');
      if (selectAll) selectAll.checked = false;

      const bulkBar = document.getElementById('scheduleBulkActions');
      if (bulkBar) bulkBar.classList.add('hidden');

      this.updateSelectedCount();
    }

    /**
     * Update selected schedule count display
     */
    updateSelectedCount() {
      const count = document.querySelectorAll('.schedule-select-checkbox:checked').length;
      const countEl = document.getElementById('selectedScheduleCount');
      if (countEl) {
        countEl.textContent = `${count} selected`;
      }

      // Show/hide bulk actions bar
      const bulkBar = document.getElementById('scheduleBulkActions');
      if (bulkBar) {
        if (count > 0) {
          bulkBar.classList.remove('hidden');
        } else {
          bulkBar.classList.add('hidden');
        }
      }
    }

    // --------------------------------------------------------------------------
    // Device Linking
    // --------------------------------------------------------------------------

    async handleLinkDevice(e) {
      e.preventDefault();
      const form = e.target;
      const formData = new FormData(form);
      const deviceId = formData.get('device_id');
      const unitId = formData.get('unit_id') || this.state.currentUnitId;
      const deviceType = this.state.linkDeviceKind;

      if (!deviceId || !unitId) {
        this.showToast('Please select a device', 'error');
        return;
      }

      try {
        let result;
        if (deviceType === 'sensor') {
          result = await this.dataService.linkSensor(deviceId, unitId);
        } else {
          result = await this.dataService.linkActuator(deviceId, unitId);
        }

        if (result.ok) {
          this.closeModal('linkDeviceModal');
          await this.loadUnitDetails(unitId);
          this.showToast('Device linked successfully', 'success');
        } else {
          this.showToast(result.error || 'Failed to link device', 'error');
        }
      } catch (error) {
        console.error('[UnitsUIManager] handleLinkDevice failed:', error);
        this.showToast('Failed to link device', 'error');
      }
    }

    async handleUnlinkDevice(deviceType, deviceId, unitId) {
      if (!confirm('Unlink this device from the unit?')) return;

      try {
        let result;
        if (deviceType === 'sensor') {
          result = await this.dataService.unlinkSensor(deviceId, unitId);
        } else {
          result = await this.dataService.unlinkActuator(deviceId, unitId);
        }

        if (result.ok) {
          await this.loadUnitDetails(unitId);
          this.showToast('Device unlinked', 'success');
        } else {
          this.showToast(result.error || 'Failed to unlink device', 'error');
        }
      } catch (error) {
        console.error(`[UnitsUIManager] handleUnlinkDevice failed:`, error);
        this.showToast('Failed to unlink device', 'error');
      }
    }

    async openLinkDeviceModal(unitId, deviceType = 'sensor') {
      this.state.currentUnitId = unitId;
      this.state.linkDeviceKind = deviceType;

      const modal = document.getElementById('linkDeviceModal') || document.getElementById('link-device-modal');
      if (!modal) return;

      const select = modal.querySelector('[name="device_id"]');
      const unitInput = modal.querySelector('[name="unit_id"]');

      if (unitInput) unitInput.value = unitId;

      // Load available devices
      if (select) {
        select.innerHTML = '<option value="">Loading...</option>';

        try {
          let devices;
          if (deviceType === 'sensor') {
            devices = await this.dataService.loadAllSensors({ force: true });
            // Filter to show only unlinked sensors
            devices = devices.filter(d => !d.unit_id);
          } else {
            devices = await this.dataService.loadAllActuators({ force: true });
            devices = devices.filter(d => !d.unit_id);
          }

          if (devices.length === 0) {
            select.innerHTML = `<option value="">No unlinked ${deviceType}s available</option>`;
          } else {
            select.innerHTML = `<option value="">Select a ${deviceType}</option>` +
              devices.map(d => {
                const id = d.sensor_id || d.actuator_id || d.id;
                const name = d.name || d.sensor_name || d.actuator_name || `${deviceType} ${id}`;
                return `<option value="${id}">${this._escapeHtml(name)}</option>`;
              }).join('');
          }
        } catch (error) {
          console.error('[UnitsUIManager] Failed to load devices:', error);
          select.innerHTML = `<option value="">Error loading ${deviceType}s</option>`;
        }
      }

      // Update modal title
      const title = modal.querySelector('.modal-title') || modal.querySelector('h2');
      if (title) title.textContent = `Link ${deviceType.charAt(0).toUpperCase() + deviceType.slice(1)}`;

      this.openModal(modal.id);
    }

    setLinkDeviceKind(kind) {
      this.state.linkDeviceKind = kind;

      // Update UI tabs
      const tabs = document.querySelectorAll('.device-type-tab');
      tabs.forEach(tab => {
        tab.classList.toggle('active', tab.dataset.kind === kind);
      });

      // Reload devices for new kind
      if (this.state.currentUnitId) {
        this.openLinkDeviceModal(this.state.currentUnitId, kind);
      }
    }

    // --------------------------------------------------------------------------
    // Plant Management
    // --------------------------------------------------------------------------

    async handleAddPlant(e) {
      e.preventDefault();
      const form = e.target;
      const formData = new FormData(form);
      const data = Object.fromEntries(formData.entries());

      const unitId = data.unit_id || this.state.currentUnitId;

      if (!data.condition_profile_id) delete data.condition_profile_id;
      if (!data.condition_profile_mode) delete data.condition_profile_mode;
      if (!data.condition_profile_name) delete data.condition_profile_name;

      try {
        const result = await this.dataService.addPlant({ ...data, unit_id: unitId });

        if (result.ok) {
          this.closeModal('addPlantModal');
          if (unitId) await this.loadUnitDetails(unitId);
          this.showToast('Plant added successfully', 'success');
        } else {
          this.showToast(result.error || 'Failed to add plant', 'error');
        }
      } catch (error) {
        console.error('[UnitsUIManager] handleAddPlant failed:', error);
        this.showToast('Failed to add plant', 'error');
      }
    }

    async handleRemovePlant(plantId, unitId) {
      if (!confirm('Remove this plant from the unit?')) return;

      try {
        const result = await this.dataService.removePlant(plantId, unitId);

        if (result.ok) {
          if (unitId) await this.loadUnitDetails(unitId);
          this.showToast('Plant removed', 'success');
        } else {
          this.showToast(result.error || 'Failed to remove plant', 'error');
        }
      } catch (error) {
        console.error(`[UnitsUIManager] handleRemovePlant(${plantId}) failed:`, error);
        this.showToast('Failed to remove plant', 'error');
      }
    }

    async handleSetActivePlant(plantId, unitId) {
      try {
        const result = await this.dataService.setActivePlant(unitId, plantId);

        if (result.ok) {
          await this.loadUnitDetails(unitId);
          this.showToast('Active plant updated', 'success');
        } else {
          this.showToast(result.error || 'Failed to set active plant', 'error');
        }
      } catch (error) {
        console.error(`[UnitsUIManager] handleSetActivePlant failed:`, error);
        this.showToast('Failed to set active plant', 'error');
      }
    }

    openAddPlantModal(unitId) {
      this.state.currentUnitId = unitId;
      const modalId = 'addPlantModal';
      const modal = document.getElementById(modalId) || document.getElementById('add-plant-modal');
      if (!modal) return;

      const form = modal.querySelector('form');
      if (form) {
        form.reset();
        const unitInput = form.querySelector('[name="unit_id"]');
        if (unitInput) unitInput.value = unitId;
      }

      this.openModal(modal.id);
      this._resetUnitPlantProfileSelection();
      this._loadUnitPlantProfileSelector();
    }

    // --------------------------------------------------------------------------
    // Thresholds
    // --------------------------------------------------------------------------

    async handleUpdateThresholds(e) {
      e.preventDefault();
      const form = e.target;
      const formData = new FormData(form);
      const unitId = formData.get('unit_id') || this.state.currentUnitId;

      // Build thresholds object
      const thresholds = {
        temperature: {
          min: parseFloat(formData.get('temp_min')) || null,
          max: parseFloat(formData.get('temp_max')) || null
        },
        humidity: {
          min: parseFloat(formData.get('humidity_min')) || null,
          max: parseFloat(formData.get('humidity_max')) || null
        },
        soil_moisture: {
          min: parseFloat(formData.get('soil_min')) || null,
          max: parseFloat(formData.get('soil_max')) || null
        }
      };

      try {
        const result = await this.dataService.updateThresholds(unitId, thresholds);

        if (result.ok) {
          this.closeModal('thresholdsModal');
          if (unitId) await this.loadUnitDetails(unitId);
          this.showToast('Thresholds updated', 'success');
        } else {
          this.showToast(result.error || 'Failed to update thresholds', 'error');
        }
      } catch (error) {
        console.error('[UnitsUIManager] handleUpdateThresholds failed:', error);
        this.showToast('Failed to update thresholds', 'error');
      }
    }

    async openThresholdsModal(unitId) {
      this.state.currentUnitId = unitId;
      const modal = document.getElementById('thresholdsModal') || document.getElementById('thresholds-modal');
      if (!modal) {
        // Template uses inline thresholds form in unitManagementModal
        this.openUnitManagementModal(unitId, 'thresholds');
        return;
      }

      // Load current unit to get thresholds
      const unit = await this.dataService.loadUnit(unitId);
      const thresholds = unit?.thresholds || {};

      const form = modal.querySelector('form');
      if (form) {
        form.reset();

        const unitInput = form.querySelector('[name="unit_id"]');
        if (unitInput) unitInput.value = unitId;

        // Populate existing values
        if (thresholds.temperature) {
          const minInput = form.querySelector('[name="temp_min"]');
          const maxInput = form.querySelector('[name="temp_max"]');
          if (minInput && thresholds.temperature.min != null) minInput.value = thresholds.temperature.min;
          if (maxInput && thresholds.temperature.max != null) maxInput.value = thresholds.temperature.max;
        }

        if (thresholds.humidity) {
          const minInput = form.querySelector('[name="humidity_min"]');
          const maxInput = form.querySelector('[name="humidity_max"]');
          if (minInput && thresholds.humidity.min != null) minInput.value = thresholds.humidity.min;
          if (maxInput && thresholds.humidity.max != null) maxInput.value = thresholds.humidity.max;
        }

        if (thresholds.soil_moisture) {
          const minInput = form.querySelector('[name="soil_min"]');
          const maxInput = form.querySelector('[name="soil_max"]');
          if (minInput && thresholds.soil_moisture.min != null) minInput.value = thresholds.soil_moisture.min;
          if (maxInput && thresholds.soil_moisture.max != null) maxInput.value = thresholds.soil_moisture.max;
        }
      }

      this.openModal(modal.id);
    }

    /**
     * Open the unit management modal with a specific tab
     */
    openUnitManagementModal(unitId, tab = 'plants') {
      this.state.currentUnitId = unitId;
      const modal = document.getElementById('unitManagementModal');
      if (!modal) return;

      this.openModal('unitManagementModal');

      // Switch to requested tab
      if (tab) {
        this.switchTab(tab);
      }

      // Load content for the tab
      this.loadManagementTabContent(unitId, tab);
    }

    switchTab(tabName) {
      // Update tab buttons
      document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.tab === tabName);
      });

      // Update tab contents
      document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.toggle('active', content.id === `${tabName}Tab`);
      });
    }

    async loadManagementTabContent(unitId, tab) {
      // Load appropriate content based on tab
      if (tab === 'plants') {
        const plants = await this.dataService.loadPlants(unitId);
        const container = document.getElementById('plantsManagementContent');
        if (container) {
          container.innerHTML = this._renderPlantsList(plants, unitId);
        }
      } else if (tab === 'devices') {
        const [sensors, actuators] = await Promise.all([
          this.dataService.loadSensors(unitId),
          this.dataService.loadActuators(unitId)
        ]);
        const container = document.getElementById('devicesManagementContent');
        if (container) {
          container.innerHTML = this._renderDevicesGrid(sensors, actuators, unitId);
        }
      } else if (tab === 'schedule') {
        const schedules = await this.dataService.loadSchedules(unitId);
        const container = document.getElementById('scheduleManagementContent');
        if (container) {
          container.innerHTML = this._renderSchedulesList(schedules, unitId);
        }
      }
    }

    // --------------------------------------------------------------------------
    // Camera
    // --------------------------------------------------------------------------

    async toggleCamera(unitId) {
      const isStreaming = this.state.cameraStreaming.has(unitId);

      if (isStreaming) {
        await this.stopCameraForUnit(unitId);
      } else {
        await this.startCameraForUnit(unitId);
      }
    }

    async startCameraForUnit(unitId) {
      try {
        const result = await this.dataService.startCamera(unitId);

        if (result.ok) {
          this.state.cameraStreaming.add(unitId);
          this.openCameraModal(unitId);
          this.showToast('Camera started', 'success');
        } else {
          this.showToast(result.error || 'Failed to start camera', 'error');
        }
      } catch (error) {
        console.error(`[UnitsUIManager] startCameraForUnit(${unitId}) failed:`, error);
        this.showToast('Failed to start camera', 'error');
      }
    }

    async stopCameraForUnit(unitId) {
      try {
        const result = await this.dataService.stopCamera(unitId);

        if (result.ok) {
          this.state.cameraStreaming.delete(unitId);
          this.closeModal('camera-modal');
          this.showToast('Camera stopped', 'success');
        } else {
          this.showToast(result.error || 'Failed to stop camera', 'error');
        }
      } catch (error) {
        console.error(`[UnitsUIManager] stopCameraForUnit(${unitId}) failed:`, error);
        this.showToast('Failed to stop camera', 'error');
      }
    }

    openCameraModal(unitId) {
      const modal = document.getElementById('camera-modal');
      if (!modal) return;

      const streamContainer = modal.querySelector('.camera-stream');
      if (streamContainer) {
        streamContainer.innerHTML = `<img src="/api/settings/camera/${unitId}/stream" alt="Camera stream" class="camera-feed" />`;
      }

      this.openModal('camera-modal');
    }

    // --------------------------------------------------------------------------
    // Event Listeners
    // --------------------------------------------------------------------------

    _setupEventListeners() {
      // Form submissions
      if (this.elements.createUnitForm) {
        this.elements.createUnitForm.addEventListener('submit', this.handleCreateUnit);
      }

      if (this.elements.scheduleForm) {
        // Use v3 API handler for new schedule form
        this.elements.scheduleForm.addEventListener('submit', (e) => this.handleSaveScheduleV3(e));
      }

      // Also listen to the new deviceScheduleForm (from template)
      const deviceScheduleForm = document.getElementById('deviceScheduleForm');
      if (deviceScheduleForm && deviceScheduleForm !== this.elements.scheduleForm) {
        deviceScheduleForm.addEventListener('submit', (e) => this.handleSaveScheduleV3(e));
      }

      // Schedule type change handler
      const scheduleTypeSelect = document.getElementById('scheduleType');
      if (scheduleTypeSelect) {
        scheduleTypeSelect.addEventListener('change', () => this.updatePhotoperiodVisibility());
      }

      const scheduleDeviceSelect = document.getElementById('scheduleDeviceType');
      if (scheduleDeviceSelect) {
        scheduleDeviceSelect.addEventListener('change', () => this.updateScheduleTimeRequirements());
      }

      const photoperiodSourceSelect = document.getElementById('photoperiodSource');
      if (photoperiodSourceSelect) {
        photoperiodSourceSelect.addEventListener('change', () => this.updateScheduleTimeRequirements());
      }

      if (this.elements.linkDeviceForm) {
        this.elements.linkDeviceForm.addEventListener('submit', this.handleLinkDevice);
      }

      if (this.elements.addPlantForm) {
        this.elements.addPlantForm.addEventListener('submit', this.handleAddPlant);
      }

      if (this.elements.thresholdsForm) {
        this.elements.thresholdsForm.addEventListener('submit', this.handleUpdateThresholds);
      }

      // Click delegation
      document.addEventListener('click', (e) => {
        const target = e.target.closest('[data-action]');
        if (!target) return;

        const action = target.dataset.action;
        const unitId = target.dataset.unitId;
        const plantId = target.dataset.plantId;
        const scheduleId = target.dataset.scheduleId;
        const deviceType = target.dataset.deviceType;
        const deviceId = target.dataset.deviceId;

        switch (action) {
          // Template's button actions
          case 'open-create-unit-modal':
            this.openModal('createUnitModal');
            break;

          case 'import-unit-profile':
            this.handleImportUnitProfile();
            break;

          case 'import-unit-plant-profile':
            this.handleImportUnitPlantProfile();
            break;

          case 'clear-unit-profile':
            this._resetUnitProfileSelection();
            break;

          case 'clear-unit-plant-profile':
            this._resetUnitPlantProfileSelection();
            break;

          case 'refresh-all-units':
            this.loadUnitsOverview();
            break;

          case 'open-unit-settings':
            // Open the unit management modal
            if (unitId) {
              this.openUnitManagementModal(unitId, 'plants');
            } else {
              const card = target.closest('.unit-card');
              if (card) this.openUnitManagementModal(card.dataset.unitId, 'plants');
            }
            break;

          case 'toggle-details':
          case 'toggle-unit-details':
            if (unitId) this.toggleUnitDetails(unitId);
            else {
              const card = target.closest('.unit-card');
              if (card) this.toggleUnitDetails(card.dataset.unitId);
            }
            break;

          case 'delete-unit':
            if (unitId) this.handleDeleteUnit(unitId);
            else {
              const card = target.closest('.unit-card');
              if (card) this.handleDeleteUnit(card.dataset.unitId);
            }
            break;

          case 'toggle-camera':
            if (unitId) this.toggleCamera(unitId);
            else {
              const card = target.closest('.unit-card');
              if (card) this.toggleCamera(card.dataset.unitId);
            }
            break;

          case 'add-plant':
            this.openAddPlantModal(unitId || this.state.currentUnitId);
            break;

          case 'remove-plant':
            this.handleRemovePlant(plantId, unitId || this.state.currentUnitId);
            break;

          case 'set-active-plant':
            this.handleSetActivePlant(plantId, unitId || this.state.currentUnitId);
            break;

          case 'link-device':
            this.openLinkDeviceModal(unitId || this.state.currentUnitId);
            break;

          case 'unlink-device':
            this.handleUnlinkDevice(deviceType, deviceId, unitId || this.state.currentUnitId);
            break;

          case 'add-schedule':
            this.openScheduleModal(unitId || this.state.currentUnitId);
            break;

          case 'edit-schedule':
            // Load schedule data from cache and open modal
            {
              const scheduleData = this.schedulesById?.get(parseInt(scheduleId));
              this.openScheduleModal(unitId || this.state.currentUnitId, scheduleData || { schedule_id: scheduleId });
            }
            break;

          case 'delete-schedule':
            this.handleDeleteSchedule(scheduleId, unitId || this.state.currentUnitId);
            break;

          // V3 Schedule Actions
          case 'preview-schedules':
            this.showSchedulePreview();
            break;

          case 'check-conflicts':
            this.showConflicts();
            break;

          case 'view-schedule-history':
            this.showScheduleHistory();
            break;

          case 'close-preview-panel':
            this.closePanel('schedulePreviewPanel');
            break;

          case 'close-conflicts-panel':
            this.closePanel('scheduleConflictsPanel');
            break;

          case 'close-history-panel':
            this.closePanel('scheduleHistoryPanel');
            break;

          case 'close-templates-panel':
            this.closePanel('scheduleTemplatesPanel');
            break;

          case 'auto-generate-schedules':
            this.handleAutoGenerateSchedules();
            break;

          case 'view-templates':
            this.showScheduleTemplates();
            break;

          case 'generate-from-template':
            this.showScheduleTemplates();
            break;

          case 'apply-templates':
            this.handleApplyTemplates();
            break;

          case 'bulk-enable':
            this.handleBulkScheduleAction('enable');
            break;

          case 'bulk-disable':
            this.handleBulkScheduleAction('disable');
            break;

          case 'bulk-delete':
            this.handleBulkScheduleAction('delete');
            break;

          case 'edit-thresholds':
            this.openThresholdsModal(unitId || this.state.currentUnitId);
            break;

          case 'switch-tab':
            const tab = target.dataset.tab;
            if (tab) {
              this.switchTab(tab);
              this.loadManagementTabContent(this.state.currentUnitId, tab);
            }
            break;

          case 'open-schedule-form':
            const scheduleFormContainer = document.getElementById('scheduleFormContainer');
            if (scheduleFormContainer) {
              scheduleFormContainer.classList.remove('hidden');
            }
            break;

          case 'close-schedule-form':
            const formContainer = document.getElementById('scheduleFormContainer');
            if (formContainer) {
              formContainer.classList.add('hidden');
            }
            break;

          case 'open-add-plant-form':
            this.openAddPlantModal(this.state.currentUnitId);
            break;

          case 'open-link-device-form':
            this.openLinkDeviceModal(this.state.currentUnitId);
            break;

          case 'close-modal':
            // Support both data-modal-id attribute and closest modal
            const modalId = target.dataset.modalId;
            if (modalId) {
              this.closeModal(modalId);
            } else {
              const modal = target.closest('.modal');
              if (modal) this.closeModal(modal.id);
            }
            break;
        }
      });

      // Modal backdrop clicks
      document.addEventListener('click', (e) => {
        if (e.target.classList.contains('modal') && e.target.classList.contains('active')) {
          this.closeModal(e.target.id);
        }
      });

      // Escape key closes modals
      document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
          this.closeAllModals();
        }
      });

      // Device type tabs
      document.querySelectorAll('.device-type-tab').forEach(tab => {
        tab.addEventListener('click', () => {
          this.setLinkDeviceKind(tab.dataset.kind);
        });
      });

      // Schedule selection checkboxes (delegated)
      document.addEventListener('change', (e) => {
        if (e.target.classList.contains('schedule-select-checkbox')) {
          this.updateSelectedCount();
        }
        if (e.target.id === 'selectAllSchedules') {
          const checkboxes = document.querySelectorAll('.schedule-select-checkbox');
          checkboxes.forEach(cb => cb.checked = e.target.checked);
          this.updateSelectedCount();
        }
      });

      // Dropdown toggle handling
      document.addEventListener('click', (e) => {
        const toggle = e.target.closest('.dropdown-toggle, .dropdown-toggle-split');
        if (toggle) {
          e.preventDefault();
          const btnGroup = toggle.closest('.btn-group');
          const menu = btnGroup?.querySelector('.dropdown-menu');
          if (menu) {
            // Close all other dropdowns first
            document.querySelectorAll('.dropdown-menu.show').forEach(m => {
              if (m !== menu) m.classList.remove('show');
            });
            menu.classList.toggle('show');
          }
          return;
        }
        // Close dropdowns when clicking outside
        if (!e.target.closest('.btn-group')) {
          document.querySelectorAll('.dropdown-menu.show').forEach(m => m.classList.remove('show'));
        }
      });

      // Keyboard shortcuts for schedule forms
      document.addEventListener('keydown', (e) => {
        // Ctrl+S to save current form
        if (e.ctrlKey && e.key === 's') {
          const activeModal = document.querySelector('.modal.active');
          if (activeModal) {
            const form = activeModal.querySelector('form');
            if (form) {
              e.preventDefault();
              form.dispatchEvent(new Event('submit', { cancelable: true, bubbles: true }));
            }
          }
        }
      });

      // SocketIO events for real-time updates
      if (window.socket) {
        window.socket.on('sensor_update', (data) => {
          if (data.unit_id) {
            this.refreshEnvironmentalData(data.unit_id);
          }
        });

        window.socket.on('unit_updated', (data) => {
          if (data.unit_id && this.state.expandedUnits.has(data.unit_id)) {
            this.loadUnitDetails(data.unit_id);
          }
        });
      }
    }

    // --------------------------------------------------------------------------
    // Utilities
    // --------------------------------------------------------------------------

    _escapeHtml(text) {
      if (window.escapeHtml) return window.escapeHtml(text);
      if (!text) return '';
      const div = document.createElement('div');
      div.textContent = text;
      return div.innerHTML;
    }

    _getDeviceIcon(deviceType) {
      const icons = {
        light: 'fa-lightbulb',
        fan: 'fa-fan',
        pump: 'fa-tint',
        heater: 'fa-fire',
        cooler: 'fa-snowflake',
        humidifier: 'fa-cloud',
        dehumidifier: 'fa-wind'
      };
      return icons[deviceType] || 'fa-clock';
    }

    showError(container, message) {
      if (!container) return;
      container.innerHTML = `
        <div class="error-state">
          <i class="fas fa-exclamation-triangle"></i>
          <p>${this._escapeHtml(message)}</p>
        </div>
      `;
    }

    showToast(message, type = 'info') {
      // Use existing toast system or create simple one
      if (window.showToast) {
        window.showToast(message, type);
        return;
      }

      const toast = document.createElement('div');
      toast.className = `toast toast-${type}`;
      toast.textContent = message;
      document.body.appendChild(toast);

      setTimeout(() => toast.classList.add('show'), 10);
      setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300);
      }, 3000);
    }
  }

  window.UnitsUIManager = UnitsUIManager;
})();
