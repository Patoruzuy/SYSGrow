/**
 * Plant Details Modal Component
  * =============================================================================
  * Fetches plant details from the API and renders them inside a modal.
  *
  * Default wiring expects:
  * - API.Plant.getPlant(plantId, unitId) available (from static/js/api.js)
  * - Existing modal markup with:
  *   - #plant-details-modal
  *   - #plant-details-title
  *   - #plant-details-content
 *
 * If the markup is missing, the component will create it dynamically.
 */
(function () {
  'use strict';

  class PlantDetailsModal {
    constructor(options = {}) {
      this.modalId = options.modalId || 'plant-details-modal';
      this.titleId = options.titleId || 'plant-details-title';
      this.contentId = options.contentId || 'plant-details-content';
      this.fetchPlant =
        options.fetchPlant ||
        (async ({ plantId, unitId }) => {
          const api = window.API;
          if (!api?.Plant?.getPlant) {
            throw new Error('Plant API not available (API.Plant.getPlant missing)');
          }
          return api.Plant.getPlant(plantId, unitId);
        });

      this._requestId = 0;
      this._currentPlantId = null;
      this._currentUnitId = null;

      this._ensureModal();
      this._ensureLinkModals();
      this._wireCloseHandlers();
      this._wireActionHandlers();
    }

    open({ plantId, unitId = null, plantSummary = null } = {}) {
      const resolvedPlantId = Number(plantId);
      if (!Number.isFinite(resolvedPlantId)) return;

      const resolvedUnitId = this._resolveUnitId(unitId, plantSummary);
      this._currentPlantId = resolvedPlantId;
      this._currentUnitId = resolvedUnitId;
      this._show();

      this._setLoading({ plantId: resolvedPlantId, unitId: resolvedUnitId, plantSummary });

      const requestId = ++this._requestId;
      Promise.resolve()
        .then(() => this.fetchPlant({ plantId: resolvedPlantId, unitId: resolvedUnitId }))
        .then((plant) => {
          if (requestId !== this._requestId) return;
          this.render(plant);
        })
        .catch((error) => {
          if (requestId !== this._requestId) return;
          this._setError(error);
        });
    }

    close() {
      if (!this.modalEl) return;
      
      // Blur active element to avoid aria-hidden focus warning
      if (document.activeElement && document.activeElement !== document.body) {
        const focusedElement = document.activeElement;
        if (this.modalEl.contains(focusedElement)) {
          focusedElement.blur();
        }
      }
      
      this.modalEl.hidden = true;
      this.modalEl.classList.remove('visible');
      this.modalEl.classList.remove('is-open');
      this.modalEl.classList.remove('active');
      this.modalEl.setAttribute('aria-hidden', 'true');

      this._unlockBodyScrollIfNoModals();
    }

    render(plant) {
      if (!this.titleEl || !this.contentEl) return;

      const name = plant?.name || plant?.plant_name || `Plant ${plant?.plant_id ?? ''}`.trim();
      this.titleEl.innerHTML = `<i class="fas fa-seedling"></i> ${window.escapeHtml(name || 'Plant Details')}`;

      const fields = this._buildFieldList(plant);
      const detailsHtml = fields
        .map(
          ({ label, valueHtml }) => `
            <div class="detail-item">
              <strong>${window.escapeHtml(label)}</strong>
              <div>${valueHtml}</div>
            </div>
          `
        )
        .join('');

      const rawJson = window.escapeHtml(JSON.stringify(plant ?? {}, null, 2));

      const actionsHtml = `
        <div class="modal-actions-group">
          <button class="modal-action action-link-sensor" data-plant-id="${window.escapeHtmlAttr(plant?.plant_id)}" data-unit-id="${window.escapeHtmlAttr(plant?.unit_id)}" title="Manage Sensors">
            <i class="fas fa-link"></i> Sensors
          </button>
          <button class="modal-action action-link-actuator" data-plant-id="${window.escapeHtmlAttr(plant?.plant_id)}" data-unit-id="${window.escapeHtmlAttr(plant?.unit_id)}" title="Manage Actuators">
            <i class="fas fa-water"></i> Actuators
          </button>
          <button class="modal-action action-delete" data-plant-id="${window.escapeHtmlAttr(plant?.plant_id)}" data-unit-id="${window.escapeHtmlAttr(plant?.unit_id)}" title="Delete Plant">
            <i class="fas fa-trash-alt"></i> Delete
          </button>
        </div>
      `;

      const actionsEl = this.modalEl ? this.modalEl.querySelector(`#${window.escapeHtmlAttr(this.modalId)}-actions`) : null;
      if (actionsEl) {
        actionsEl.innerHTML = actionsHtml;
      }

      // Include actions in content if not in header (fallback)
      const actionsInContent = !actionsEl ? actionsHtml : '';

      this.contentEl.innerHTML = `
        ${actionsInContent}
        <div class="plant-details-grid">
          ${detailsHtml}
        </div>

        <section class="plant-devices-section">
          <div class="devices-tabs">
            <button class="device-tab active" data-tab="sensors">
              <i class="fas fa-link"></i> Linked Sensors
            </button>
            <button class="device-tab" data-tab="actuators">
              <i class="fas fa-water"></i> Linked Actuators
            </button>
          </div>
          
          <div class="device-tab-content active" id="sensors-content">
            <div id="plant-sensors-list" class="devices-list">
              <div class="loading">Loading sensors...</div>
            </div>
          </div>
          
          <div class="device-tab-content" id="actuators-content">
            <div id="plant-actuators-list" class="devices-list">
              <div class="loading">Loading actuators...</div>
            </div>
          </div>
        </section>

        <section class="plant-observations-section">
          <div class="observations-header">
            <h4>Observations</h4>
            <div class="observations-actions">
              <button class="btn btn-sm view-observations" data-plant-id="${window.escapeHtmlAttr(plant?.plant_id)}">View Observations</button>
              <button class="btn btn-sm add-observation" data-plant-id="${window.escapeHtmlAttr(plant?.plant_id)}">Add Observation</button>
            </div>
          </div>
          <div id="plant-observations-list" class="observations-list">
            <div class="loading">No observations loaded</div>
          </div>
        </section>

        <details class="plant-details-raw">
          <summary>Raw details</summary>
          <pre>${rawJson}</pre>
        </details>
      `;
      
      // Load linked devices asynchronously
      this._loadLinkedDevices(plant?.plant_id);
    }

    _wireActionHandlers() {
      if (!this.modalEl) return;
      if (this.modalEl.dataset.actionsWired === 'true') return;
      this.modalEl.dataset.actionsWired = 'true';

      this.modalEl.addEventListener('click', (e) => {
        const editBtn = e.target.closest('.action-edit');
        const deleteBtn = e.target.closest('.action-delete');
        const linkBtn = e.target.closest('.action-link-sensor');
        const viewObs = e.target.closest('.view-observations');
        const addObs = e.target.closest('.add-observation');

        if (editBtn) {
          e.preventDefault();
          const plantId = editBtn.dataset.plantId;
          // Prefer UI manager API if available
          if (window.plantsHub && window.plantsHub.uiManager && typeof window.plantsHub.uiManager.openPlantDetails === 'function') {
            window.plantsHub.uiManager.openPlantDetails(Number(plantId));
          } else if (window.plantsHub && typeof window.plantsHub.showPlantDetails === 'function') {
            window.plantsHub.showPlantDetails(plantId);
          } else {
            alert('Edit plant feature coming soon');
          }
          return;
        }

        if (deleteBtn) {
          e.preventDefault();
          const plantId = deleteBtn.dataset.plantId;
          const unitId = deleteBtn.dataset.unitId;
          if (!confirm('Delete this plant?')) return;
          (async () => {
            try {
              if (!window.API || !window.API.Plant || !window.API.Plant.removePlant) throw new Error('Delete API not available');
              await window.API.Plant.removePlant(Number(unitId), Number(plantId));
              // Refresh via available hub/UI manager
              if (window.plantsHub && window.plantsHub.uiManager && typeof window.plantsHub.uiManager.loadAndRender === 'function') {
                try { window.plantsHub.uiManager.dataService.clearCache?.(); } catch (err) {}
                await window.plantsHub.uiManager.loadAndRender();
              } else if (window.plantsHub && typeof window.plantsHub.loadData === 'function') {
                try { window.plantsHub.dataService.clearCache?.(); } catch (err) {}
                await window.plantsHub.loadData();
              } else {
                window.location.reload();
              }
              this.close();
            } catch (err) {
              console.error('Failed to delete plant', err);
              alert('Failed to delete plant');
            }
          })();
          return;
        }

        if (linkBtn) {
          e.preventDefault();
          const plantId = linkBtn.dataset.plantId;
          const unitId = linkBtn.dataset.unitId;
          this._openSensorLinkModal(Number(plantId), Number(unitId));
          return;
        }

        // Link actuator
        const linkActuatorBtn = e.target.closest('.action-link-actuator');
        if (linkActuatorBtn) {
          e.preventDefault();
          const plantId = linkActuatorBtn.dataset.plantId;
          const unitId = linkActuatorBtn.dataset.unitId;
          this._openActuatorLinkModal(Number(plantId), Number(unitId));
          return;
        }

        // Unlink sensor
        const unlinkSensorBtn = e.target.closest('[data-action="unlink-sensor"]');
        if (unlinkSensorBtn) {
          e.preventDefault();
          const plantId = unlinkSensorBtn.dataset.plantId;
          const sensorId = unlinkSensorBtn.dataset.sensorId;
          this._handleUnlinkSensor(plantId, sensorId);
          return;
        }

        // Unlink actuator
        const unlinkActuatorBtn = e.target.closest('[data-action="unlink-actuator"]');
        if (unlinkActuatorBtn) {
          e.preventDefault();
          const plantId = unlinkActuatorBtn.dataset.plantId;
          const actuatorId = unlinkActuatorBtn.dataset.actuatorId;
          this._handleUnlinkActuator(plantId, actuatorId);
          return;
        }

        // Device tabs
        const deviceTab = e.target.closest('.device-tab');
        if (deviceTab) {
          e.preventDefault();
          this._switchDeviceTab(deviceTab.dataset.tab);
          return;
        }

        if (viewObs) {
          e.preventDefault();
          const plantId = viewObs.dataset.plantId;
          this._loadAndRenderObservations(plantId);
          return;
        }

        if (addObs) {
          e.preventDefault();
          const plantId = addObs.dataset.plantId;
          // Try UI manager path first
          if (window.plantsHub && window.plantsHub.uiManager && typeof window.plantsHub.uiManager.openObservationModal === 'function') {
            window.plantsHub.uiManager.openObservationModal(Number(plantId));
            return;
          }

          if (window.plantsHub && typeof window.plantsHub.showAddObservationModal === 'function') {
            window.plantsHub.showAddObservationModal(plantId);
            return;
          }

          // Fallback: show the add-observation-modal and preselect plant
          const obsModal = document.getElementById('add-observation-modal');
          const select = document.getElementById('observation-plant');
          if (select && plantId) select.value = String(plantId);
          if (obsModal) obsModal.hidden = false;
          return;
        }
      });
    }

    async _loadAndRenderObservations(plantId, days = 30) {
      const container = this.modalEl ? this.modalEl.querySelector('#plant-observations-list') : null;
      if (!container) return;
      container.innerHTML = `<div class="loading"><i class="fas fa-spinner fa-spin"></i> Loading observations…</div>`;

      try {
        if (!window.API || !window.API.Plant || !window.API.Plant.getHealthHistory) {
          container.innerHTML = `<div class="empty-state">Observations API not available</div>`;
          return;
        }

        const data = await window.API.Plant.getHealthHistory(plantId, days);
        const observations = data?.observations || data?.entries || [];

        if (!observations || observations.length === 0) {
          container.innerHTML = `<div class="empty-state">No observations found for this plant.</div>`;
          return;
        }

        container.innerHTML = observations
          .map(o => `
            <div class="obs-item">
              <div class="obs-header"><strong>${window.escapeHtml(o.health_status || o.status || 'Observation')}</strong>
                <span class="obs-date">${window.escapeHtml(o.created_at || o.timestamp || '')}</span></div>
              <div class="obs-content">${window.escapeHtml(o.notes || o.notes_text || o.content || '')}</div>
            </div>
          `).join('');
      } catch (err) {
        console.error('Failed to load observations', err);
        container.innerHTML = `<div class="empty-state">Failed to load observations</div>`;
      }
    }

    // -------------------------------------------------------------------------
    // Device Management
    // -------------------------------------------------------------------------

    async _loadLinkedDevices(plantId) {
      if (!plantId) return;
      
      try {
        // Load sensors
        const sensorsResp = await window.API.Plant.getPlantSensors(plantId);
        const sensors = sensorsResp?.data?.sensors || sensorsResp?.sensors || [];
        this._renderLinkedSensors(sensors, plantId);
        
        // Load actuators
        const actuatorsResp = await window.API.Plant.getPlantActuators(plantId);
        const actuators = actuatorsResp?.data?.actuators || actuatorsResp?.actuators || [];
        this._renderLinkedActuators(actuators, plantId);
        
      } catch (error) {
        console.error('Failed to load linked devices:', error);
      }
    }

    _renderLinkedSensors(sensors, plantId) {
      const container = document.getElementById('plant-sensors-list');
      if (!container) return;
      
      if (!sensors || sensors.length === 0) {
        container.innerHTML = '<div class="empty-state">No sensors linked</div>';
        return;
      }
      
      container.innerHTML = sensors.map(sensor => `
        <div class="device-item">
          <div class="device-info">
            <i class="fas fa-thermometer-half"></i>
            <div>
              <strong>${window.escapeHtml(sensor.name || `Sensor ${sensor.sensor_id}`)}</strong>
              <small>${window.escapeHtml(sensor.type || 'Unknown')}</small>
            </div>
          </div>
          <button class="btn-icon btn-unlink" 
                  data-action="unlink-sensor"
                  data-plant-id="${window.escapeHtmlAttr(plantId)}"
                  data-sensor-id="${window.escapeHtmlAttr(sensor.sensor_id)}"
                  title="Unlink sensor">
            <i class="fas fa-unlink"></i>
          </button>
        </div>
      `).join('');
    }

    _renderLinkedActuators(actuators, plantId) {
      const container = document.getElementById('plant-actuators-list');
      if (!container) return;
      
      if (!actuators || actuators.length === 0) {
        container.innerHTML = '<div class="empty-state">No actuators linked</div>';
        return;
      }
      
      container.innerHTML = actuators.map(actuator => `
        <div class="device-item">
          <div class="device-info">
            <i class="fas fa-tint"></i>
            <div>
              <strong>${window.escapeHtml(actuator.name || `Actuator ${actuator.actuator_id}`)}</strong>
              <small>${window.escapeHtml(actuator.type || 'Unknown')}</small>
            </div>
          </div>
          <button class="btn-icon btn-unlink"
                  data-action="unlink-actuator"
                  data-plant-id="${window.escapeHtmlAttr(plantId)}"
                  data-actuator-id="${window.escapeHtmlAttr(actuator.actuator_id)}"
                  title="Unlink actuator">
            <i class="fas fa-unlink"></i>
          </button>
        </div>
      `).join('');
    }

    async _handleUnlinkSensor(plantId, sensorId) {
      if (!confirm('Unlink this sensor from the plant?')) return;
      
      try {
        await window.API.Plant.unlinkPlantFromSensor(Number(plantId), Number(sensorId));
        
        // Refresh both the main modal and link modal if open
        await this._loadLinkedDevices(plantId);
        const linkModal = document.getElementById('plant-sensor-link-modal');
        if (linkModal && !linkModal.hidden) {
          const unitId = this._currentUnitId;
          await this._loadSensorLinkData(plantId, unitId);
        }
        
        this._showToast('Sensor unlinked successfully', 'success');
      } catch (error) {
        console.error('Failed to unlink sensor:', error);
        this._showToast('Failed to unlink sensor', 'error');
      }
    }

    async _handleUnlinkActuator(plantId, actuatorId) {
      if (!confirm('Unlink this actuator from the plant?')) return;
      
      try {
        await window.API.Plant.unlinkPlantFromActuator(Number(plantId), Number(actuatorId));
        
        // Refresh both the main modal and link modal if open
        await this._loadLinkedDevices(plantId);
        const linkModal = document.getElementById('plant-actuator-link-modal');
        if (linkModal && !linkModal.hidden) {
          const unitId = this._currentUnitId;
          await this._loadActuatorLinkData(plantId, unitId);
        }
        
        this._showToast('Actuator unlinked successfully', 'success');
      } catch (error) {
        console.error('Failed to unlink actuator:', error);
        this._showToast('Failed to unlink actuator', 'error');
      }
    }

    _switchDeviceTab(tabName) {
      if (!this.modalEl) return;
      const tabs = this.modalEl.querySelectorAll('.device-tab');
      const contents = this.modalEl.querySelectorAll('.device-tab-content');
      
      tabs.forEach(tab => {
        tab.classList.toggle('active', tab.dataset.tab === tabName);
      });
      
      contents.forEach(content => {
        content.classList.toggle('active', content.id === `${tabName}-content`);
      });
    }

    _showToast(message, type = 'info') {
      const toast = document.createElement('div');
      toast.className = `toast toast-${type}`;
      toast.innerHTML = `<i class="fas fa-${type === 'success' ? 'check-circle' : type === 'error' ? 'exclamation-circle' : 'info-circle'}"></i> ${window.escapeHtml(message)}`;
      document.body.appendChild(toast);
      setTimeout(() => {
        toast.style.opacity = '0';
        setTimeout(() => toast.remove(), 300);
      }, 3000);
    }

    // -------------------------------------------------------------------------
    // Link Modals Management
    // -------------------------------------------------------------------------

    _ensureLinkModals() {
      if (!document.getElementById('plant-sensor-link-modal')) {
        this._createSensorLinkModal();
      }
      
      if (!document.getElementById('plant-actuator-link-modal')) {
        this._createActuatorLinkModal();
      }
    }

    _createSensorLinkModal() {
      const modal = document.createElement('div');
      modal.id = 'plant-sensor-link-modal';
      modal.className = 'modal';
      modal.hidden = true;
      modal.setAttribute('aria-hidden', 'true');
      modal.innerHTML = `
        <div class="modal-overlay"></div>
        <div class="modal-content">
          <div class="modal-header">
            <h2 class="modal-title">
              <i class="fas fa-link"></i> Manage Sensors
            </h2>
            <button type="button" class="modal-close" aria-label="Close">
              <i class="fas fa-times"></i>
            </button>
          </div>
          <div class="modal-body">
            <div class="device-management-section">
              <h3>Currently Linked Sensors</h3>
              <div id="current-sensors-list" class="devices-list">
                <div class="loading">Loading...</div>
              </div>
            </div>
            
            <div class="device-management-section">
              <h3>Link New Sensor</h3>
              <form id="sensor-link-form">
                <input type="hidden" name="plant_id" id="sensor-plant-id">
                <div class="form-field">
                  <label for="sensor-select">Available Sensors</label>
                  <select id="sensor-select" name="sensor_id" required>
                    <option value="">Loading...</option>
                  </select>
                </div>
                <div class="form-actions">
                  <button type="button" class="btn btn-secondary modal-close">Cancel</button>
                  <button type="submit" class="btn btn-primary">Link Sensor</button>
                </div>
              </form>
            </div>
          </div>
        </div>
      `;
      document.body.appendChild(modal);
      
      const form = modal.querySelector('#sensor-link-form');
      form.addEventListener('submit', (e) => this._handleSensorLinkSubmit(e));

      // Backdrop click: close when clicking the modal container itself
      modal.addEventListener('click', (e) => {
        if (e.target === modal) this._closeLinkModal(modal);
      });

      // Stop propagation inside the dialog
      const content = modal.querySelector('.modal-content');
      if (content) {
        content.addEventListener('click', (e) => e.stopPropagation());
      }

      modal.querySelectorAll('.modal-close').forEach(btn => {
        btn.addEventListener('click', () => this._closeLinkModal(modal));
      });
    }

    _createActuatorLinkModal() {
      const modal = document.createElement('div');
      modal.id = 'plant-actuator-link-modal';
      modal.className = 'modal';
      modal.hidden = true;
      modal.setAttribute('aria-hidden', 'true');
      modal.innerHTML = `
        <div class="modal-overlay"></div>
        <div class="modal-content">
          <div class="modal-header">
            <h2 class="modal-title">
              <i class="fas fa-water"></i> Manage Actuators
            </h2>
            <button type="button" class="modal-close" aria-label="Close">
              <i class="fas fa-times"></i>
            </button>
          </div>
          <div class="modal-body">
            <div class="device-management-section">
              <h3>Currently Linked Actuators</h3>
              <div id="current-actuators-list" class="devices-list">
                <div class="loading">Loading...</div>
              </div>
            </div>
            
            <div class="device-management-section">
              <h3>Link New Actuator</h3>
              <form id="actuator-link-form">
                <input type="hidden" name="plant_id" id="actuator-plant-id">
                <div class="form-field">
                  <label for="actuator-select">Available Actuators (Pumps/Valves)</label>
                  <select id="actuator-select" name="actuator_id" required>
                    <option value="">Loading...</option>
                  </select>
                </div>
                <div class="form-actions">
                  <button type="button" class="btn btn-secondary modal-close">Cancel</button>
                  <button type="submit" class="btn btn-primary">Link Actuator</button>
                </div>
              </form>
            </div>
          </div>
        </div>
      `;
      document.body.appendChild(modal);
      
      const form = modal.querySelector('#actuator-link-form');
      form.addEventListener('submit', (e) => this._handleActuatorLinkSubmit(e));

      // Backdrop click: close when clicking the modal container itself
      modal.addEventListener('click', (e) => {
        if (e.target === modal) this._closeLinkModal(modal);
      });

      // Stop propagation inside the dialog
      const content = modal.querySelector('.modal-content');
      if (content) {
        content.addEventListener('click', (e) => e.stopPropagation());
      }

      modal.querySelectorAll('.modal-close').forEach(btn => {
        btn.addEventListener('click', () => this._closeLinkModal(modal));
      });
    }

    _closeLinkModal(modal) {
      if (document.activeElement && modal.contains(document.activeElement)) {
        document.activeElement.blur();
      }
      modal.hidden = true;
      modal.classList.remove('is-open', 'visible');
      modal.setAttribute('aria-hidden', 'true');

      this._unlockBodyScrollIfNoModals();
    }

    async _openSensorLinkModal(plantId, unitId) {
      const modal = document.getElementById('plant-sensor-link-modal');
      if (!modal) return;
      
      modal.dataset.unitId = unitId;
      const hiddenInput = modal.querySelector('#sensor-plant-id');
      if (hiddenInput) hiddenInput.value = plantId;
      
      modal.hidden = false;
      modal.classList.add('is-open');
      modal.setAttribute('aria-hidden', 'false');

      this._lockBodyScroll();
      
      await this._loadSensorLinkData(plantId, unitId);
    }

    async _openActuatorLinkModal(plantId, unitId) {
      const modal = document.getElementById('plant-actuator-link-modal');
      if (!modal) return;
      
      modal.dataset.unitId = unitId;
      const hiddenInput = modal.querySelector('#actuator-plant-id');
      if (hiddenInput) hiddenInput.value = plantId;
      
      modal.hidden = false;
      modal.classList.add('is-open');
      modal.setAttribute('aria-hidden', 'false');

      this._lockBodyScroll();
      
      await this._loadActuatorLinkData(plantId, unitId);
    }

    async _loadSensorLinkData(plantId, unitId) {
      const currentList = document.getElementById('current-sensors-list');
      const select = document.getElementById('sensor-select');
      
      console.log('[PlantDetailsModal] Loading sensor link data for plant:', plantId, 'unit:', unitId);
      
      try {
        const linkedResp = await window.API.Plant.getPlantSensors(plantId);
        console.log('[PlantDetailsModal] Linked sensors response:', linkedResp);
        const linkedSensors = linkedResp?.data?.sensors || linkedResp?.sensors || [];
        const linkedIds = new Set(linkedSensors.map(s => Number(s.sensor_id)));
        
        if (currentList) {
          if (linkedSensors.length === 0) {
            currentList.innerHTML = '<div class="empty-state">No sensors linked</div>';
          } else {
            currentList.innerHTML = linkedSensors.map(sensor => `
              <div class="device-item">
                <div class="device-info">
                  <i class="fas fa-thermometer-half"></i>
                  <div>
                    <strong>${window.escapeHtml(sensor.name || `Sensor ${sensor.sensor_id}`)}</strong>
                    <small>${window.escapeHtml(sensor.type || 'Unknown')}</small>
                  </div>
                </div>
                <button class="btn-icon btn-unlink" 
                        data-action="unlink-sensor"
                        data-plant-id="${window.escapeHtmlAttr(plantId)}"
                        data-sensor-id="${window.escapeHtmlAttr(sensor.sensor_id)}"
                        title="Unlink sensor">
                  <i class="fas fa-unlink"></i>
                </button>
              </div>
            `).join('');
          }
        }
        
        const availableResp = await window.API.Plant.getAvailableSensors(unitId);
        console.log('[PlantDetailsModal] Available sensors response:', availableResp);
        const allSensors = availableResp?.data?.sensors || availableResp?.sensors || [];
        console.log('[PlantDetailsModal] All sensors:', allSensors, 'Linked IDs:', Array.from(linkedIds));
        const availableSensors = allSensors.filter(s => !linkedIds.has(Number(s.sensor_id)));
        console.log('[PlantDetailsModal] Available sensors after filtering:', availableSensors);
        
        if (select) {
          if (availableSensors.length === 0) {
            select.innerHTML = '<option value="">No sensors available</option>';
          } else {
            select.innerHTML = '<option value="">-- Select sensor --</option>' + 
              availableSensors.map(s => 
                `<option value="${s.sensor_id}">${window.escapeHtml(s.name || s.sensor_id)} (${window.escapeHtml(s.type || '')})</option>`
              ).join('');
          }
        }
      } catch (error) {
        console.error('[PlantDetailsModal] Failed to load sensor data:', error);
        if (currentList) currentList.innerHTML = '<div class="error-state">Failed to load sensors</div>';
        if (select) select.innerHTML = '<option value="">Error loading sensors</option>';
      }
    }

    async _loadActuatorLinkData(plantId, unitId) {
      const currentList = document.getElementById('current-actuators-list');
      const select = document.getElementById('actuator-select');
      
      try {
        const linkedResp = await window.API.Plant.getPlantActuators(plantId);
        const linkedActuators = linkedResp?.data?.actuators || linkedResp?.actuators || [];
        const linkedIds = new Set(linkedActuators.map(a => Number(a.actuator_id)));
        
        if (currentList) {
          if (linkedActuators.length === 0) {
            currentList.innerHTML = '<div class="empty-state">No actuators linked</div>';
          } else {
            currentList.innerHTML = linkedActuators.map(actuator => `
              <div class="device-item">
                <div class="device-info">
                  <i class="fas fa-tint"></i>
                  <div>
                    <strong>${window.escapeHtml(actuator.name || `Actuator ${actuator.actuator_id}`)}</strong>
                    <small>${window.escapeHtml(actuator.type || 'Unknown')}</small>
                  </div>
                </div>
                <button class="btn-icon btn-unlink"
                        data-action="unlink-actuator"
                        data-plant-id="${window.escapeHtmlAttr(plantId)}"
                        data-actuator-id="${window.escapeHtmlAttr(actuator.actuator_id)}"
                        title="Unlink actuator">
                  <i class="fas fa-unlink"></i>
                </button>
              </div>
            `).join('');
          }
        }
        
        const availableResp = await window.API.Plant.getAvailableActuators(unitId, 'pump');
        const allActuators = availableResp?.data?.actuators || availableResp?.actuators || [];
        const availableActuators = allActuators.filter(a => !linkedIds.has(Number(a.actuator_id)));
        
        if (select) {
          if (availableActuators.length === 0) {
            select.innerHTML = '<option value="">No actuators available</option>';
          } else {
            select.innerHTML = '<option value="">-- Select actuator --</option>' + 
              availableActuators.map(a => 
                `<option value="${a.actuator_id}">${window.escapeHtml(a.name || a.actuator_id)} (${window.escapeHtml(a.type || 'pump')})</option>`
              ).join('');
          }
        }
      } catch (error) {
        console.error('Failed to load actuator data:', error);
        if (currentList) currentList.innerHTML = '<div class="error-state">Failed to load actuators</div>';
        if (select) select.innerHTML = '<option value="">Error loading actuators</option>';
      }
    }

    async _handleSensorLinkSubmit(e) {
      e.preventDefault();
      const form = e.target;
      const plantId = form.plant_id?.value;
      const sensorId = form.sensor_id?.value;
      
      if (!plantId || !sensorId) {
        this._showToast('Please select a sensor', 'error');
        return;
      }
      
      try {
        await window.API.Plant.linkPlantToSensor(Number(plantId), Number(sensorId));
        this._showToast('Sensor linked successfully', 'success');
        
        const modal = document.getElementById('plant-sensor-link-modal');
        const unitId = modal?.dataset?.unitId;
        await this._loadSensorLinkData(plantId, unitId);
        
        if (!this.modalEl?.hidden) {
          await this._loadLinkedDevices(plantId);
        }
      } catch (error) {
        console.error('Failed to link sensor:', error);
        this._showToast('Failed to link sensor', 'error');
      }
    }

    async _handleActuatorLinkSubmit(e) {
      e.preventDefault();
      const form = e.target;
      const plantId = form.plant_id?.value;
      const actuatorId = form.actuator_id?.value;
      
      if (!plantId || !actuatorId) {
        this._showToast('Please select an actuator', 'error');
        return;
      }
      
      try {
        await window.API.Plant.linkPlantToActuator(Number(plantId), Number(actuatorId));
        this._showToast('Actuator linked successfully', 'success');
        
        const modal = document.getElementById('plant-actuator-link-modal');
        const unitId = modal?.dataset?.unitId;
        await this._loadActuatorLinkData(plantId, unitId);
        
        if (!this.modalEl?.hidden) {
          await this._loadLinkedDevices(plantId);
        }
      } catch (error) {
        console.error('Failed to link actuator:', error);
        this._showToast('Failed to link actuator', 'error');
      }
    }

    // -------------------------------------------------------------------------
    // Internals
    // -------------------------------------------------------------------------

    _ensureModal() {
      this.modalEl = document.getElementById(this.modalId);
      this.titleEl = document.getElementById(this.titleId);
      this.contentEl = document.getElementById(this.contentId);

      if (this.modalEl && this.titleEl && this.contentEl) return;

      // Create modal markup if a page doesn't provide one (e.g., dashboard usage)
      const modal = document.createElement('div');
      modal.id = this.modalId;
      modal.className = 'modal';
      modal.hidden = true;
      modal.setAttribute('aria-hidden', 'true');

      modal.innerHTML = `
        <div class="modal-overlay"></div>
        <div class="modal-content large">
          <div class="modal-header">
            <h2 class="modal-title" id="${window.escapeHtmlAttr(this.titleId)}">
              <i class="fas fa-seedling"></i>
              Plant Details
            </h2>
            <div id="${window.escapeHtmlAttr(this.modalId)}-actions" class="modal-header-actions"></div>
            <button type="button" class="modal-close" aria-label="Close">
              <i class="fas fa-times"></i>
            </button>
          </div>
          <div class="modal-body" id="${window.escapeHtmlAttr(this.contentId)}"></div>
        </div>
      `;

      document.body.appendChild(modal);

      this.modalEl = modal;
      this.titleEl = document.getElementById(this.titleId);
      this.contentEl = document.getElementById(this.contentId);
    }

    _wireCloseHandlers() {
      if (!this.modalEl) return;
      if (this.modalEl.dataset.handlersSetup === 'true') return;
      this.modalEl.dataset.handlersSetup = 'true';

      // Close modal when clicking outside content (on modal backdrop)
      this.modalEl.addEventListener('click', (e) => {
        // Only close if clicking directly on the modal container, not content
        if (e.target === this.modalEl) {
          e.preventDefault();
          this.close();
        }
      });

      // Stop propagation on modal content to prevent closing when clicking inside
      const content = this.modalEl.querySelector('.modal-content');
      if (content) {
        content.addEventListener('click', (e) => {
          e.stopPropagation();
        });
      }

      const closeBtn = this.modalEl.querySelector('.modal-close, [data-modal-close]');
      if (closeBtn) {
        closeBtn.addEventListener('click', (e) => {
          e.preventDefault();
          e.stopPropagation();
          this.close();
        });
      }
    }

    _show() {
      if (!this.modalEl) return;
      this.modalEl.hidden = false;
      this.modalEl.classList.add('visible');
      this.modalEl.classList.add('is-open');
      this.modalEl.setAttribute('aria-hidden', 'false');

      this._lockBodyScroll();
    }

    _lockBodyScroll() {
      try {
        document.body.classList.add('modal-open');
      } catch {
        // ignore
      }
    }

    _unlockBodyScrollIfNoModals() {
      try {
        const anyOpen = Boolean(document.querySelector('.modal.visible, .modal.is-open, .modal.active'));
        if (!anyOpen) document.body.classList.remove('modal-open');
      } catch {
        // ignore
      }
    }

    _setLoading({ plantId, unitId, plantSummary }) {
      if (!this.titleEl || !this.contentEl) return;

      const fallbackLabel = Number.isFinite(Number(unitId)) ? `Plant ${plantId} (Unit ${unitId})` : `Plant ${plantId}`;
      const name = plantSummary?.name || plantSummary?.plant_name || fallbackLabel;
      this.titleEl.innerHTML = `<i class="fas fa-seedling"></i> ${window.escapeHtml(name)}`;
      this.contentEl.innerHTML = `
        <div class="loading-spinner">
          <i class="fas fa-spinner fa-spin"></i>
          <p>Loading plant details…</p>
        </div>
      `;
    }

    _setError(error) {
      if (!this.contentEl) return;
      const message = error?.message || 'Failed to load plant details';
      this.contentEl.innerHTML = `
        <div class="empty-state">
          <i class="fas fa-exclamation-triangle"></i>
          <p>${window.escapeHtml(message)}</p>
        </div>
      `;
    }

    _buildFieldList(plant) {
      const fields = [];

      const push = (label, value, opts = {}) => {
        const valueHtml = this._formatValue(value, opts);
        if (opts.includeWhenEmpty !== true && this._isEmptyValue(value)) return;
        fields.push({ label, valueHtml });
      };

      push('Plant ID', plant?.plant_id, { includeWhenEmpty: true });
      push('Name', plant?.name || plant?.plant_name, { includeWhenEmpty: true });
      push('Unit', plant?.unit_name);
      push('Unit ID', plant?.unit_id);

      push('Plant Type', plant?.plant_type);
      push('Strain / Variety', plant?.strain_variety || plant?.plant_variety);
      push('Growth Stage', plant?.current_stage || plant?.growth_stage);
      push('Days In Stage', plant?.days_in_stage, { includeWhenEmpty: true });
      push('Health Status', plant?.current_health_status, { badge: 'health' });

      push('Moisture Level', plant?.moisture_level);
      push('Planted Date', plant?.planted_date);
      push('Created At', plant?.created_at);

      push('Pot Size (L)', plant?.pot_size_liters);
      push('Pot Material', plant?.pot_material);
      push('Growing Medium', plant?.growing_medium);
      push('Medium pH', plant?.medium_ph);

      push('Expected Yield (g)', plant?.expected_yield_grams);
      push('Light Distance (cm)', plant?.light_distance_cm);

      push('Linked Sensors', plant?.linked_sensor_ids, { chips: true });

      // Any additional keys not covered above, rendered as a compact JSON string.
      const shownKeys = new Set([
        'plant_id',
        'name',
        'plant_name',
        'unit_name',
        'unit_id',
        'plant_type',
        'strain_variety',
        'plant_variety',
        'current_stage',
        'growth_stage',
        'days_in_stage',
        'current_health_status',
        'moisture_level',
        'planted_date',
        'created_at',
        'pot_size_liters',
        'pot_material',
        'growing_medium',
        'medium_ph',
        'expected_yield_grams',
        'light_distance_cm',
        'linked_sensor_ids',
      ]);

      const extra = Object.entries(plant ?? {})
        .filter(([key, value]) => !shownKeys.has(key) && !this._isEmptyValue(value))
        .sort(([a], [b]) => a.localeCompare(b));

      extra.forEach(([key, value]) => push(this._humanizeKey(key), value));

      return fields;
    }

    _formatValue(value, opts = {}) {
      if (opts.badge === 'health') {
        const status = String(value ?? '').toLowerCase();
        const badgeClass =
          status === 'healthy'
            ? 'badge-success'
            : status === 'stressed'
              ? 'badge-warning'
              : status === 'diseased'
                ? 'badge-danger'
                : 'badge-info';

        return value
          ? `<span class="badge ${badgeClass}">${window.escapeHtml(value)}</span>`
          : '<span class="badge badge-info">unknown</span>';
      }

      if (opts.chips && Array.isArray(value)) {
        if (value.length === 0) return '—';
        return value
          .map((v) => `<span class="chip">${window.escapeHtml(v)}</span>`)
          .join(' ');
      }

      if (Array.isArray(value)) {
        if (value.length === 0) return '—';
        return window.escapeHtml(value.join(', '));
      }

      if (typeof value === 'boolean') return value ? 'Yes' : 'No';
      if (typeof value === 'number') return Number.isFinite(value) ? window.escapeHtml(value) : '—';

      if (value && typeof value === 'object') {
        return `<pre style="margin: 0">${window.escapeHtml(JSON.stringify(value, null, 2))}</pre>`;
      }

      return this._isEmptyValue(value) ? '—' : window.escapeHtml(value);
    }

    _isEmptyValue(value) {
      return value === null || value === undefined || value === '';
    }

    _humanizeKey(key) {
      return String(key)
        .replace(/_/g, ' ')
        .replace(/([a-z])([A-Z])/g, '$1 $2')
        .replace(/\b\w/g, (c) => c.toUpperCase());
    }

    _resolveUnitId(unitId, plantSummary) {
      const candidate = unitId ?? plantSummary?.unit_id ?? plantSummary?.unitId ?? null;
      const parsed = candidate !== null && candidate !== undefined && candidate !== '' ? Number(candidate) : null;
      if (Number.isFinite(parsed) && parsed > 0) return parsed;

      const raw = typeof document !== 'undefined' ? document.body?.dataset?.activeUnitId : null;
      const fromBody = raw !== null && raw !== '' ? parseInt(raw, 10) : null;
      return Number.isFinite(fromBody) && fromBody > 0 ? fromBody : null;
    }




  }

  window.PlantDetailsModal = PlantDetailsModal;
})();
