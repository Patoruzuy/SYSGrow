/**
 * Settings UI Manager
 *
 * Manages UI interactions, form handling, DOM manipulation,
 * plus enterprise-grade UX patterns:
 * - Sticky Save Bar when forms are "dirty"
 * - Discard changes (revert to last loaded/saved state)
 * - More robust form hydration + change tracking (checkbox/radio/select)
 */

class SettingsUIManager extends BaseManager {
  constructor(dataService) {
    super('SettingsUIManager');

    if (!dataService) throw new Error('SettingsDataService is required');
    this.dataService = dataService;

    this.statusTimeout = null;
    this.elements = {};

    // Dirty tracking + Save Bar
    this.formBaselines = new Map(); // formEl -> baseline state object
    this.dirtyForms = new Set(); // Set<formEl>
    this.lastEditedForm = null;

    this.saveBar = {
      root: null,
      title: null,
      summary: null,
      saveBtn: null,
      discardBtn: null
    };

    this.TOAST_MS = 4000;

    // Device schedules (keyed by device_type)
    this.deviceSchedulesByType = new Map();
    this.activeScheduleDeviceType = null;
  }

  // ============================================================================
  // INIT
  // ============================================================================

  async init() {
    this.cacheElements();
    this.initTabs();
    this.initSaveBar();
    this.attachEventListeners();
    this.updateConditionalFields();

    // Sync unit selector with initial selectedUnitId from server
    const initialUnitId = this.dataService.selectedUnitId;
    if (initialUnitId) {
      if (this.elements.unitSelector) {
        this.elements.unitSelector.value = String(initialUnitId);
      }
      if (this.elements.databaseUnitSelector) {
        this.elements.databaseUnitSelector.value = String(initialUnitId);
      }
      console.log('[SettingsUI] Synced unit selector with initial unit:', initialUnitId);
    }

    await this.loadAllSettings();

    // Start tracking after initial hydration
    this.initDirtyTracking();
    this.refreshSaveBar();
  }

  cacheElements() {
    this.elements = {
      statusElement: document.getElementById('settings-status'),
      unitSelector: document.getElementById('schedule-unit-selector'),
      databaseUnitSelector: document.getElementById('database-unit-selector'),
      settingsPage: document.querySelector('.settings-page'),

      // Forms
      environmentForm: document.getElementById('environment-form'),
      scheduleForm: document.getElementById('device-schedule-form'),
      hotspotForm: document.getElementById('hotspot-form'),
      esp32Form: document.getElementById('esp32-device-form'),
      cameraForm: document.getElementById('camera-form'),
      energyForm: document.getElementById('energy-config-form'),
      alertsForm: document.getElementById('alerts-config-form'),
      dataForm: document.getElementById('data-management-form'),

      // Database / throttle
      throttleForm: document.getElementById('throttle-form'),
      throttleResetButton: document.getElementById('throttle-reset-btn'),

      // Device schedule fields
      scheduleDeviceSelector: document.getElementById('schedule-device-selector'),
      scheduleStart: document.getElementById('schedule-start'),
      scheduleEnd: document.getElementById('schedule-end'),
      scheduleEnabled: document.getElementById('schedule-enabled'),

      // Buttons
      suggestButton: document.getElementById('suggest-thresholds'),
      scanWiFiButton: document.getElementById('scan-wifi'),
      sendWiFiButton: document.getElementById('send-wifi-config'),
      broadcastWiFiButton: document.getElementById('broadcast-wifi'),
      deviceScanButton: document.getElementById('device-scan'),
      checkFirmwareButton: document.getElementById('check-firmware'),
      provisionButton: document.getElementById('provision-device'),
      zigbeeDiscoverButton: document.getElementById('zigbee-discover'),
      exportDataButton: document.getElementById('export-data-btn'),

      // Other elements
      deviceList: document.getElementById('device-list'),
      cameraType: document.getElementById('camera-type'),
      connectionMode: document.getElementById('connection-mode'),
      deviceType: document.getElementById('device-type'),
      commSelect: document.getElementById('communication-type-add'),
      zigbeeFields: document.getElementById('zigbee-fields-add'),
      addDeviceForm: document.getElementById('add-device-form'),

      // Irrigation workflow elements
      irrigationWorkflowForm: document.getElementById('irrigation-workflow-form'),
      irrigationUnitId: document.getElementById('irrigation-unit-id'),
      irrigationWorkflowEnabled: document.getElementById('irrigation-workflow-enabled'),
      irrigationRequireApproval: document.getElementById('irrigation-require-approval'),
      irrigationScheduledTime: document.getElementById('irrigation-scheduled-time'),
      irrigationDelayMinutes: document.getElementById('irrigation-delay-minutes'),
      irrigationMaxDelay: document.getElementById('irrigation-max-delay'),
      irrigationSendReminder: document.getElementById('irrigation-send-reminder'),
      irrigationReminderMinutes: document.getElementById('irrigation-reminder-minutes'),
      irrigationRequestFeedback: document.getElementById('irrigation-request-feedback'),
      irrigationMlLearning: document.getElementById('irrigation-ml-learning'),

      // Pump calibration elements
      calibrationPumpSelect: document.getElementById('calibration-pump-select'),
      calibrationStatusDisplay: document.getElementById('calibration-status-display'),
      calibrationInstructions: document.getElementById('calibration-instructions'),
      calibrationForm: document.getElementById('pump-calibration-form'),
      calibrationActualMl: document.getElementById('calibration-actual-ml'),
      calibrationDuration: document.getElementById('calibration-duration'),
      startCalibrationBtn: document.getElementById('start-calibration-btn'),
      completeCalibrationBtn: document.getElementById('complete-calibration-btn'),
      cancelCalibrationBtn: document.getElementById('cancel-calibration-btn'),
      calibrationHistory: document.getElementById('calibration-history'),
      calibrationHistoryBody: document.getElementById('calibration-history-body')
    };
  }

  // ============================================================================
  // STATUS / TOAST
  // ============================================================================

  displayMessage(message, type = 'success') {
    const el = this.elements.statusElement;
    if (!el) return;

    // Keep it simple but consistent
    el.textContent = message;
    el.className = `settings-status settings-status--${type}`;

    // Scroll only for errors (less jarring)
    if (type === 'error') {
      el.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }

    clearTimeout(this.statusTimeout);
    if (type !== 'error') {
      this.statusTimeout = setTimeout(() => {
        el.textContent = '';
        el.className = 'settings-status';
      }, this.TOAST_MS);
    }
  }

  normalizeError(error) {
    if (!error) return 'Unknown error';
    if (typeof error === 'string') return error;
    return error.message || 'Unknown error';
  }

  safeNumber(value) {
    const parsed = parseFloat(value);
    return Number.isFinite(parsed) ? parsed : null;
  }

  getCheckboxBool(formData, name) {
    return formData.get(name) === 'on';
  }

  getNumber(formData, name, fallback = null) {
    const val = this.safeNumber(formData.get(name));
    return val !== null ? val : fallback;
  }

  setButtonLoading(button, isLoading, loadingText = 'Loading...') {
    if (!button) return;
    if (isLoading) {
      button.disabled = true;
      button.setAttribute('aria-busy', 'true');
      button.dataset.originalHtml = button.innerHTML;
      button.innerHTML = `<div class="progress-spinner" aria-hidden="true"></div> ${loadingText}`;
    } else {
      button.disabled = false;
      button.removeAttribute('aria-busy');
      button.innerHTML = button.dataset.originalHtml || button.innerHTML;
    }
  }

  // ============================================================================
  // CONDITIONAL UI
  // ============================================================================

  updateConditionalFields() {
    // Camera type conditional fields
    if (this.elements.cameraType) {
      const type = this.elements.cameraType.value;
      document.querySelectorAll('.conditional-field[data-camera]').forEach(field => {
        const show = field.dataset.camera.split(',').includes(type);
        field.style.display = show ? '' : 'none';
      });
    }

    // Device type conditional fields
    if (this.elements.deviceType) {
      const type = this.elements.deviceType.value;
      document.querySelectorAll('.conditional-field[data-device]').forEach(field => {
        const show = field.dataset.device.split(',').includes(type);
        field.style.display = show ? '' : 'none';
      });
    }

    // Connection mode conditional fields
    if (this.elements.connectionMode) {
      const mode = this.elements.connectionMode.value;
      document.querySelectorAll('.conditional-field[data-connection]').forEach(field => {
        const show = field.dataset.connection.split(',').includes(mode);
        field.style.display = show ? '' : 'none';
      });
    }
  }

  toggleZigbeeFields() {
    if (!this.elements.commSelect || !this.elements.zigbeeFields) return;
    this.elements.zigbeeFields.style.display = (this.elements.commSelect.value === 'zigbee') ? '' : 'none';
  }

  // ============================================================================
  // SAVE BAR + DIRTY TRACKING
  // ============================================================================

  initSaveBar() {
    // Create if not present
    let root = document.getElementById('settings-savebar');
    if (!root) {
      root = document.createElement('div');
      root.id = 'settings-savebar';
      root.className = 'settings-savebar';
      root.setAttribute('role', 'region');
      root.setAttribute('aria-label', 'Unsaved changes');
      root.style.display = 'none';
      root.innerHTML = `
        <div class="settings-savebar__inner">
          <div class="settings-savebar__text">
            <div class="settings-savebar__title" id="settings-savebar-title">Unsaved changes</div>
            <div class="settings-savebar__summary" id="settings-savebar-summary">You have changes that haven’t been saved.</div>
          </div>
          <div class="settings-savebar__actions">
            <button type="button" class="btn btn-primary btn-sm" id="settings-savebar-save">Save</button>
            <button type="button" class="btn btn-secondary btn-sm" id="settings-savebar-discard">Discard</button>
          </div>
        </div>
      `;

      // Append near end of page so it can be fixed/sticky via CSS
      const host = document.querySelector('.page-shell') || document.body;
      host.appendChild(root);
    }

    this.saveBar.root = root;
    this.saveBar.title = document.getElementById('settings-savebar-title');
    this.saveBar.summary = document.getElementById('settings-savebar-summary');
    this.saveBar.saveBtn = document.getElementById('settings-savebar-save');
    this.saveBar.discardBtn = document.getElementById('settings-savebar-discard');

    // Wire actions
    if (this.saveBar.saveBtn) {
      this.addEventListener(this.saveBar.saveBtn, 'click', () => this.saveLastEditedDirtyForm());
    }
    if (this.saveBar.discardBtn) {
      this.addEventListener(this.saveBar.discardBtn, 'click', () => this.discardLastEditedDirtyForm());
    }

    // Keyboard affordance: Escape discards last edited dirty form (optional but useful)
    this.addEventListener(document, 'keydown', (e) => {
      if (e.key === 'Escape' && this.dirtyForms.size > 0) {
        this.discardLastEditedDirtyForm();
      }
    });
  }

  hasUnsavedChanges() {
  return this.dirtyForms && this.dirtyForms.size > 0;
  }

  initDirtyTracking() {
    const forms = this.getAllManagedForms();

    // Establish baselines (if not already set by loaders)
    forms.forEach(form => {
      if (form && !this.formBaselines.has(form)) {
        this.markFormPristine(form);
      }
    });

    // Track user edits (event delegation per form)
    forms.forEach(form => {
      if (!form) return;

      const onEdit = () => {
        this.lastEditedForm = form;

        // Compute dirty based on baseline comparison
        if (this.isFormDirty(form)) {
          this.dirtyForms.add(form);
        } else {
          this.dirtyForms.delete(form);
        }
        this.refreshSaveBar();
      };

      // input covers text; change covers select/checkbox/radio
      this.addEventListener(form, 'input', onEdit);
      this.addEventListener(form, 'change', onEdit);
    });
  }

  getAllManagedForms() {
    return [
      this.elements.environmentForm,
      this.elements.scheduleForm,
      this.elements.hotspotForm,
      this.elements.cameraForm,
      this.elements.throttleForm,
      this.elements.energyForm,
      this.elements.alertsForm,
      this.elements.dataForm,
      this.elements.esp32Form,
      this.elements.addDeviceForm
    ].filter(Boolean);
  }

  getFormLabel(form) {
    if (!form) return 'Settings';

    // Prefer a nearby card header title if present
    const card = form.closest('.settings-card');
    if (card) {
      const h3 = card.querySelector('.card-header h3');
      if (h3 && h3.textContent) return h3.textContent.trim();
    }

    return form.getAttribute('id') || 'Settings';
  }

  snapshotFormState(form) {
    // Robust snapshot of all inputs/selects/textareas in the form
    const state = {};
    if (!form) return state;

    const fields = Array.from(form.querySelectorAll('input, select, textarea'))
      .filter(el => !el.disabled && el.type !== 'submit' && el.type !== 'button');

    // Handle radios by group name/id
    const radioGroups = new Map(); // key -> Array<radio>

    for (const el of fields) {
      const key = (el.name || el.id || '').trim();
      if (!key) continue;

      if (el.type === 'radio') {
        if (!radioGroups.has(key)) radioGroups.set(key, []);
        radioGroups.get(key).push(el);
        continue;
      }

      if (el.type === 'checkbox') {
        state[key] = Boolean(el.checked);
        continue;
      }

      state[key] = (el.value ?? '').toString();
    }

    // Radios: store selected value (or empty string)
    for (const [key, radios] of radioGroups.entries()) {
      const selected = radios.find(r => r.checked);
      state[key] = selected ? (selected.value ?? '').toString() : '';
    }

    return state;
  }

  applyFormState(form, state) {
    if (!form || !state) return;

    const fields = Array.from(form.querySelectorAll('input, select, textarea'))
      .filter(el => !el.disabled && el.type !== 'submit' && el.type !== 'button');

    // First pass: non-radios
    for (const el of fields) {
      const key = (el.name || el.id || '').trim();
      if (!key || !(key in state)) continue;

      if (el.type === 'checkbox') {
        el.checked = Boolean(state[key]);
      } else if (el.type === 'radio') {
        // radios handled below
      } else {
        el.value = state[key];
      }
    }

    // Second pass: radios (set checked by value)
    const radios = fields.filter(el => el.type === 'radio');
    const grouped = new Map();
    for (const r of radios) {
      const key = (r.name || r.id || '').trim();
      if (!key) continue;
      if (!grouped.has(key)) grouped.set(key, []);
      grouped.get(key).push(r);
    }

    for (const [key, group] of grouped.entries()) {
      if (!(key in state)) continue;
      const targetVal = (state[key] ?? '').toString();
      group.forEach(r => {
        r.checked = (r.value ?? '').toString() === targetVal;
      });
    }
  }

  markFormPristine(form) {
    if (!form) return;
    const baseline = this.snapshotFormState(form);
    this.formBaselines.set(form, baseline);
    this.dirtyForms.delete(form);
    this.refreshSaveBar();
  }

  isFormDirty(form) {
    if (!form) return false;
    const baseline = this.formBaselines.get(form);
    if (!baseline) return false;

    const current = this.snapshotFormState(form);

    const keys = new Set([...Object.keys(baseline), ...Object.keys(current)]);
    for (const k of keys) {
      if ((baseline[k] ?? '') !== (current[k] ?? '')) return true;
    }
    return false;
  }

  refreshSaveBar() {
    const root = this.saveBar.root;
    if (!root) return;

    if (this.dirtyForms.size === 0) {
      root.style.display = 'none';
      return;
    }

    const count = this.dirtyForms.size;
    const activeForm = this.lastEditedForm || Array.from(this.dirtyForms)[0];
    const label = this.getFormLabel(activeForm);

    if (this.saveBar.title) {
      this.saveBar.title.textContent = 'Unsaved changes';
    }
    if (this.saveBar.summary) {
      this.saveBar.summary.textContent =
        (count === 1)
          ? `${label} has unsaved changes.`
          : `You have ${count} sections with unsaved changes. Last edited: ${label}.`;
    }

    root.style.display = '';
  }

  async saveLastEditedDirtyForm() {
    const form = this.lastEditedForm && this.dirtyForms.has(this.lastEditedForm)
      ? this.lastEditedForm
      : Array.from(this.dirtyForms)[0];

    if (!form) return;

    // Prefer native submission path so your existing submit listeners run
    if (typeof form.requestSubmit === 'function') {
      form.requestSubmit();
    } else {
      // fallback
      form.dispatchEvent(new Event('submit', { cancelable: true, bubbles: true }));
    }
  }

  discardLastEditedDirtyForm() {
    const form = this.lastEditedForm && this.dirtyForms.has(this.lastEditedForm)
      ? this.lastEditedForm
      : Array.from(this.dirtyForms)[0];

    if (!form) return;

    const baseline = this.formBaselines.get(form);
    if (!baseline) return;

    this.applyFormState(form, baseline);
    this.dirtyForms.delete(form);

    // Ensure conditional UI is refreshed after reverting
    this.updateConditionalFields();

    this.refreshSaveBar();
    this.displayMessage(`Discarded changes in ${this.getFormLabel(form)}`, 'success');
  }

  // ============================================================================
  // TAB MANAGEMENT
  // ============================================================================

  initTabs() {
    const tabButtons = document.querySelectorAll('.tab-button');
    const tabPanels = document.querySelectorAll('.tab-panel');

    tabButtons.forEach(button => {
      this.addEventListener(button, 'click', () => {
        const targetTab = button.dataset.tab;

        tabButtons.forEach(btn => {
          btn.classList.remove('active');
          btn.setAttribute('aria-selected', 'false');
          btn.setAttribute('tabindex', '-1');
        });

        button.classList.add('active');
        button.setAttribute('aria-selected', 'true');
        button.setAttribute('tabindex', '0');

        tabPanels.forEach(panel => {
          panel.classList.remove('active');
          panel.setAttribute('aria-hidden', 'true');
        });

        const targetPanel = document.getElementById(`${targetTab}-panel`);
        if (targetPanel) {
          targetPanel.classList.add('active');
          targetPanel.setAttribute('aria-hidden', 'false');
          // Accessibility: move focus to the panel container
          targetPanel.focus?.();
        }

        localStorage.setItem('activeSettingsTab', targetTab);
      });
    });

    // Keyboard navigation
    const focusTab = (newIndex) => {
      if (newIndex < 0) newIndex = tabButtons.length - 1;
      if (newIndex >= tabButtons.length) newIndex = 0;
      tabButtons[newIndex].focus();
      tabButtons[newIndex].click();
    };

    tabButtons.forEach((btn, index) => {
      this.addEventListener(btn, 'keydown', (e) => {
        let newIndex = index;
        switch (e.key) {
          case 'ArrowLeft':
            e.preventDefault();
            newIndex = index - 1;
            break;
          case 'ArrowRight':
            e.preventDefault();
            newIndex = index + 1;
            break;
          case 'Home':
            e.preventDefault();
            newIndex = 0;
            break;
          case 'End':
            e.preventDefault();
            newIndex = tabButtons.length - 1;
            break;
          default:
            return;
        }
        focusTab(newIndex);
      });
    });

    // Restore active tab
    const savedTab = localStorage.getItem('activeSettingsTab');
    if (savedTab) {
      const savedButton = document.querySelector(`[data-tab="${savedTab}"]`);
      if (savedButton) savedButton.click();
    }
  }

  // ============================================================================
  // LOAD ALL SETTINGS
  // ============================================================================

  async loadAllSettings() {
    try {
      await Promise.all([
        this.loadEnvironment(),
        this.loadDeviceSchedules(),
        this.loadSchedulesV3(),  // Load v3 schedules
        this.loadHotspotSettings(),
        this.loadCameraSettings(),
        this.loadAnalyticsSettings(),
        this.loadThrottleConfig(),
        this.loadIrrigationWorkflow(),  // Load irrigation workflow settings
        this.loadSecuritySettings()  // Load security settings (recovery codes count)
      ]);
    } catch (error) {
      this.displayMessage(`Some settings failed to load: ${this.normalizeError(error)}`, 'error');
    }
  }

  // ============================================================================
  // DATABASE THROTTLING
  // ============================================================================

  async loadThrottleConfig({ force = false } = {}) {
    try {
      const config = await this.dataService.loadThrottleConfig({ force });
      if (!config) return;

      const unitId = this.dataService.selectedUnitId;
      if (this.elements.unitSelector && unitId) this.elements.unitSelector.value = String(unitId);
      if (this.elements.databaseUnitSelector && unitId) this.elements.databaseUnitSelector.value = String(unitId);

      const enabledEl = document.getElementById('throttle-enabled');
      const strategyEl = document.getElementById('throttle-strategy');
      const debugEl = document.getElementById('throttle-debug');

      if (enabledEl) enabledEl.checked = config.throttling_enabled !== false;
      if (strategyEl && config.strategy) strategyEl.value = config.strategy;
      if (debugEl) debugEl.checked = config.debug_logging === true;

      const time = config.time_intervals || {};
      const thresholds = config.change_thresholds || {};

      const setNumber = (id, value) => {
        const el = document.getElementById(id);
        if (!el) return;
        el.value = (value === null || value === undefined) ? '' : String(value);
      };

      setNumber('throttle-temp-humidity-min', time.temp_humidity_minutes);
      setNumber('throttle-co2-voc-min', time.co2_voc_minutes);
      setNumber('throttle-soil-min', time.soil_moisture_minutes);

      setNumber('throttle-temp-delta', thresholds.temp_celsius);
      setNumber('throttle-humidity-delta', thresholds.humidity_percent);
      setNumber('throttle-soil-delta', thresholds.soil_moisture_percent);
      setNumber('throttle-co2-delta', thresholds.co2_ppm);
      setNumber('throttle-voc-delta', thresholds.voc_ppb);

      // Baseline after hydration
      if (this.elements.throttleForm) this.markFormPristine(this.elements.throttleForm);
    } catch (error) {
      console.error('[SettingsUIManager] loadThrottleConfig failed:', error);
      this.displayMessage(`Failed to load throttle settings: ${this.normalizeError(error)}`, 'error');
    }
  }

  async handleThrottleSubmit(event) {
    event.preventDefault();

    try {
      if (!this.dataService.selectedUnitId) {
        this.displayMessage('Select a unit first', 'error');
        return;
      }

      const formData = new FormData(event.target);

      const payload = {
        throttling_enabled: this.getCheckboxBool(formData, 'throttling_enabled'),
        debug_logging: this.getCheckboxBool(formData, 'debug_logging'),
        strategy: formData.get('strategy') || 'hybrid',
        time_intervals: {
          temp_humidity_minutes: this.getNumber(formData, 'temp_humidity_minutes', 0),
          co2_voc_minutes: this.getNumber(formData, 'co2_voc_minutes', 0),
          soil_moisture_minutes: this.getNumber(formData, 'soil_moisture_minutes', 0)
        },
        change_thresholds: {
          temp_celsius: this.getNumber(formData, 'temp_celsius', 0),
          humidity_percent: this.getNumber(formData, 'humidity_percent', 0),
          soil_moisture_percent: this.getNumber(formData, 'soil_moisture_percent', 0),
          co2_ppm: this.getNumber(formData, 'co2_ppm', 0),
          voc_ppb: this.getNumber(formData, 'voc_ppb', 0)
        }
      };

      await this.dataService.saveThrottleConfig(payload);
      await this.loadThrottleConfig({ force: true });

      // Clear dirty after successful save
      this.markFormPristine(event.target);
      this.displayMessage('Throttle settings saved', 'success');
    } catch (error) {
      console.error('[SettingsUIManager] handleThrottleSubmit failed:', error);
      this.displayMessage(`Failed to save throttle settings: ${this.normalizeError(error)}`, 'error');
    }
  }

  async handleThrottleReset() {
    try {
      if (!this.dataService.selectedUnitId) {
        this.displayMessage('Select a unit first', 'error');
        return;
      }

      await this.dataService.resetThrottleConfig();
      await this.loadThrottleConfig({ force: true });

      if (this.elements.throttleForm) this.markFormPristine(this.elements.throttleForm);
      this.displayMessage('Throttle settings reset to defaults', 'success');
    } catch (error) {
      console.error('[SettingsUIManager] handleThrottleReset failed:', error);
      this.displayMessage(`Failed to reset throttle settings: ${this.normalizeError(error)}`, 'error');
    }
  }

  async applyUnitSelection(unitId) {
    this.dataService.setSelectedUnit(unitId);

    if (this.elements.unitSelector) this.elements.unitSelector.value = String(unitId);
    if (this.elements.databaseUnitSelector) this.elements.databaseUnitSelector.value = String(unitId);

    this.displayMessage('Loading unit data...', 'info');

    await Promise.all([
      this.loadEnvironment(),
      this.loadDeviceSchedules(),
      this.loadSchedulesV3(),  // Reload v3 schedules when unit changes
      this.loadThrottleConfig({ force: true }),
      this.loadIrrigationWorkflow()  // Reload irrigation when unit changes
    ]);

    this.displayMessage('Unit data loaded', 'success');

    // New unit -> treat freshly loaded values as baseline
    if (this.elements.environmentForm) this.markFormPristine(this.elements.environmentForm);
    if (this.elements.scheduleForm) this.markFormPristine(this.elements.scheduleForm);
    if (this.elements.throttleForm) this.markFormPristine(this.elements.throttleForm);
    if (this.elements.irrigationWorkflowForm) this.markFormPristine(this.elements.irrigationWorkflowForm);
  }

  // ============================================================================
  // ENVIRONMENT SETTINGS
  // ============================================================================

  async loadEnvironment() {
    try {
      const data = await this.dataService.loadEnvironment();
      if (!data) return;

      const tempInput = document.getElementById('env-temperature');
      const humidityInput = document.getElementById('env-humidity');
      const co2Input = document.getElementById('env-co2');
      const vocInput = document.getElementById('env-voc');
      const luxInput = document.getElementById('env-lux');
      const aqiInput = document.getElementById('env-aqi');

      if (tempInput && data.temperature_threshold !== undefined) tempInput.value = data.temperature_threshold;
      if (humidityInput && data.humidity_threshold !== undefined) humidityInput.value = data.humidity_threshold;
      if (co2Input && data.co2_threshold !== undefined) co2Input.value = data.co2_threshold;
      if (vocInput && data.voc_threshold !== undefined) vocInput.value = data.voc_threshold;
      if (luxInput && data.lux_threshold !== undefined) luxInput.value = data.lux_threshold;
      if (aqiInput && data.aqi_threshold !== undefined) aqiInput.value = data.aqi_threshold;

      if (this.elements.environmentForm) this.markFormPristine(this.elements.environmentForm);
    } catch (error) {
      this.warn('Failed to load environment settings:', error);
    }
  }

  async handleEnvironmentSubmit(event) {
    event.preventDefault();

    const payload = {
      temperature_threshold: this.safeNumber(document.getElementById('env-temperature')?.value),
      humidity_threshold: this.safeNumber(document.getElementById('env-humidity')?.value)
    };

    const co2 = this.safeNumber(document.getElementById('env-co2')?.value);
    if (co2 !== null) payload.co2_threshold = co2;

    const voc = this.safeNumber(document.getElementById('env-voc')?.value);
    if (voc !== null) payload.voc_threshold = voc;

    const lux = this.safeNumber(document.getElementById('env-lux')?.value);
    if (lux !== null) payload.lux_threshold = lux;

    const aqi = this.safeNumber(document.getElementById('env-aqi')?.value);
    if (aqi !== null) payload.aqi_threshold = aqi;

    try {
      await this.dataService.saveEnvironment(payload);
      this.markFormPristine(event.target);
      this.displayMessage('Environment settings saved successfully', 'success');
    } catch (error) {
      this.displayMessage(`Failed to save environment settings: ${this.normalizeError(error)}`, 'error');
    }
  }

  async handleSuggestThresholds() {
    const button = this.elements.suggestButton;
    this.setButtonLoading(button, true, 'Analyzing...');

    try {
      const suggestions = await this.dataService.suggestThresholds();

      if (suggestions.temperature !== undefined) {
        const el = document.getElementById('env-temperature');
        if (el) el.value = suggestions.temperature;
      }
      if (suggestions.humidity !== undefined) {
        const el = document.getElementById('env-humidity');
        if (el) el.value = suggestions.humidity;
      }
      if (suggestions.soil_moisture !== undefined) {
        const el = document.getElementById('env-soil');
        if (el) el.value = suggestions.soil_moisture;
      }
      if (suggestions.co2 !== undefined) {
        const el = document.getElementById('env-co2');
        if (el) el.value = suggestions.co2;
      }
      if (suggestions.voc !== undefined) {
        const el = document.getElementById('env-voc');
        if (el) el.value = suggestions.voc;
      }
      if (suggestions.lux !== undefined) {
        const el = document.getElementById('env-lux');
        if (el) el.value = suggestions.lux;
      }
      if (suggestions.aqi !== undefined) {
        const el = document.getElementById('env-aqi');
        if (el) el.value = suggestions.aqi;
      }

      // Programmatic changes don’t trigger input events -> force dirty detection
      if (this.elements.environmentForm) {
        this.lastEditedForm = this.elements.environmentForm;
        if (this.isFormDirty(this.elements.environmentForm)) {
          this.dirtyForms.add(this.elements.environmentForm);
        }
        this.refreshSaveBar();
      }

      this.displayMessage('Thresholds suggested based on plant data', 'success');
    } catch (error) {
      this.displayMessage(`Failed to suggest thresholds: ${this.normalizeError(error)}`, 'error');
    } finally {
      this.setButtonLoading(button, false);
    }
  }

  // ============================================================================
  // DEVICE SCHEDULES
  // ============================================================================

  getSelectedScheduleDeviceType() {
    const raw = this.elements.scheduleDeviceSelector?.value;
    const value = (raw ?? '').toString().trim();
    return value || null;
  }

  hydrateScheduleForm(deviceType, { markPristine = true } = {}) {
    if (!this.elements.scheduleForm) return;

    const schedule = deviceType ? this.deviceSchedulesByType.get(deviceType) : null;

    if (this.elements.scheduleStart) this.elements.scheduleStart.value = schedule?.start_time || '';
    if (this.elements.scheduleEnd) this.elements.scheduleEnd.value = schedule?.end_time || '';
    if (this.elements.scheduleEnabled) this.elements.scheduleEnabled.checked = schedule?.enabled !== false;

    if (markPristine) this.markFormPristine(this.elements.scheduleForm);
  }

  async loadDeviceSchedules({ force = false } = {}) {
    try {
      const schedules = await this.dataService.loadDeviceSchedules({ force });

      this.deviceSchedulesByType = new Map();
      if (Array.isArray(schedules)) {
        schedules.forEach((schedule) => {
          if (!schedule || typeof schedule !== 'object') return;
          const deviceType = schedule.device_type;
          if (!deviceType) return;
          this.deviceSchedulesByType.set(deviceType, schedule);
        });
      }

      const select = this.elements.scheduleDeviceSelector;
      let deviceType = this.getSelectedScheduleDeviceType() || this.activeScheduleDeviceType;

      if (!deviceType && select?.options?.length) {
        deviceType = select.options[0].value;
      }

      if (select && deviceType) select.value = deviceType;
      this.activeScheduleDeviceType = deviceType;

      this.hydrateScheduleForm(deviceType, { markPristine: true });
    } catch (error) {
      this.warn('Failed to load device schedules:', error);
    }
  }

  handleScheduleDeviceChange() {
    const nextDeviceType = this.getSelectedScheduleDeviceType();
    if (!nextDeviceType) return;

    const scheduleForm = this.elements.scheduleForm;
    if (scheduleForm && this.isFormDirty(scheduleForm)) {
      const ok = window.confirm('You have unsaved changes in this schedule. Discard them and switch device?');
      if (!ok) {
        if (this.elements.scheduleDeviceSelector && this.activeScheduleDeviceType) {
          this.elements.scheduleDeviceSelector.value = this.activeScheduleDeviceType;
        }
        return;
      }
    }

    this.activeScheduleDeviceType = nextDeviceType;
    this.hydrateScheduleForm(nextDeviceType, { markPristine: true });
  }

  async handleScheduleSubmit(event) {
    event.preventDefault();

    if (!this.dataService.selectedUnitId) {
      this.displayMessage('Please select a growth unit first', 'error');
      return;
    }

    const deviceType = this.getSelectedScheduleDeviceType();
    if (!deviceType) {
      this.displayMessage('Please select a device type first', 'error');
      return;
    }

    const payload = {
      start_time: this.elements.scheduleStart?.value || '',
      end_time: this.elements.scheduleEnd?.value || '',
      enabled: Boolean(this.elements.scheduleEnabled?.checked)
    };

    try {
      await this.dataService.saveDeviceSchedule(deviceType, payload);
      await this.loadDeviceSchedules({ force: true });
      this.markFormPristine(event.target);
      this.displayMessage(`${deviceType.charAt(0).toUpperCase() + deviceType.slice(1)} schedule saved successfully`, 'success');
    } catch (error) {
      this.displayMessage(`Failed to save ${deviceType} schedule: ${this.normalizeError(error)}`, 'error');
    }
  }

  // ============================================================================
  // V3 SCHEDULE MANAGEMENT (Enhanced Features)
  // ============================================================================

  /**
   * Load and render all schedules using v3 API
   */
  async loadSchedulesV3({ force = false } = {}) {
    const listContainer = document.getElementById('schedules-list');
    const summaryContainer = document.getElementById('schedule-summary-content');
    
    if (!this.dataService.selectedUnitId) {
      if (listContainer) listContainer.innerHTML = '<div class="empty-state">Select a unit to view schedules</div>';
      return;
    }

    try {
      // Load schedules and summary in parallel
      const [schedules, summary] = await Promise.all([
        this.dataService.loadSchedulesV3({ force }),
        this.dataService.getScheduleSummary({ force })
      ]);

      // Render summary
      if (summaryContainer && summary) {
        this.renderScheduleSummary(summary, summaryContainer);
      }

      // Render schedule list
      if (listContainer) {
        this.renderSchedulesList(schedules, listContainer);
      }

      // Store schedules for editing
      this.schedulesById = new Map();
      schedules.forEach(s => {
        if (s.schedule_id) this.schedulesById.set(s.schedule_id, s);
      });

    } catch (error) {
      console.error('[SettingsUI] loadSchedulesV3 failed:', error);
      this.displayMessage('Failed to load schedules', 'error');
    }
  }

  /**
   * Render schedule summary stats
   */
  renderScheduleSummary(summary, container) {
    const html = `
      <div class="summary-stat">
        <span class="stat-value">${summary.total_schedules || 0}</span>
        <span class="stat-label">Total Schedules</span>
      </div>
      <div class="summary-stat">
        <span class="stat-value">${summary.enabled_schedules || 0}</span>
        <span class="stat-label">Enabled</span>
      </div>
      <div class="summary-stat">
        <span class="stat-value">${summary.light_hours?.toFixed(1) || '0.0'}h</span>
        <span class="stat-label">Light Hours</span>
      </div>
      <div class="summary-stat">
        <span class="stat-value">${Object.keys(summary.by_device_type || {}).length}</span>
        <span class="stat-label">Device Types</span>
      </div>
    `;
    container.innerHTML = html;
  }

  /**
   * Render the list of schedules
   */
  renderSchedulesList(schedules, container) {
    if (!schedules || schedules.length === 0) {
      container.innerHTML = `
        <div class="empty-state">
          <i class="fas fa-calendar-times"></i>
          <p>No schedules configured</p>
          <button type="button" class="btn btn-primary btn-sm" id="add-first-schedule">
            <i class="fas fa-plus"></i> Add First Schedule
          </button>
        </div>
      `;
      const btn = container.querySelector('#add-first-schedule');
      if (btn) btn.addEventListener('click', () => this.openScheduleModal());
      return;
    }

    const html = schedules.map(schedule => this.renderScheduleCard(schedule)).join('');
    container.innerHTML = `<div class="schedules-grid">${html}</div>`;

    // Attach event listeners
    container.querySelectorAll('[data-action="edit-schedule"]').forEach(btn => {
      btn.addEventListener('click', () => this.openScheduleModal(parseInt(btn.dataset.scheduleId)));
    });
    container.querySelectorAll('[data-action="toggle-schedule"]').forEach(btn => {
      btn.addEventListener('click', () => this.toggleSchedule(parseInt(btn.dataset.scheduleId), btn.dataset.enabled !== 'true'));
    });
    container.querySelectorAll('[data-action="delete-schedule"]').forEach(btn => {
      btn.addEventListener('click', () => this.deleteSchedule(parseInt(btn.dataset.scheduleId)));
    });
    container.querySelectorAll('[data-action="view-execution-log"]').forEach(btn => {
      btn.addEventListener('click', () => this.showExecutionLog(parseInt(btn.dataset.scheduleId)));
    });
  }

  /**
   * Render a single schedule card
   */
  renderScheduleCard(schedule) {
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
    
    // Format days of week
    const dayNames = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
    const daysDisplay = schedule.days_of_week?.length === 7 ? 'Every day' :
      schedule.days_of_week?.map(d => dayNames[d]).join(', ') || 'Every day';

    return `
      <div class="schedule-card ${statusClass}" data-schedule-id="${schedule.schedule_id}">
        <div class="schedule-header">
          <div class="schedule-icon"><i class="${icon}"></i></div>
          <div class="schedule-info">
            <h4 class="schedule-name">${schedule.name || schedule.device_type}</h4>
            <span class="schedule-device">${schedule.device_type}</span>
          </div>
          <span class="schedule-status">${statusText}</span>
        </div>
        <div class="schedule-details">
          <div class="schedule-time">
            <i class="fas fa-clock"></i>
            <span>${schedule.start_time} - ${schedule.end_time}</span>
          </div>
          <div class="schedule-days">
            <i class="fas fa-calendar-week"></i>
            <span>${daysDisplay}</span>
          </div>
          ${schedule.priority ? `<div class="schedule-priority"><i class="fas fa-sort-numeric-up"></i> Priority: ${schedule.priority}</div>` : ''}
          ${schedule.value ? `<div class="schedule-value"><i class="fas fa-sliders-h"></i> Value: ${schedule.value}%</div>` : ''}
        </div>
        <div class="schedule-actions">
          <button type="button" class="btn btn-sm btn-outline-primary" data-action="edit-schedule" data-schedule-id="${schedule.schedule_id}" title="Edit">
            <i class="fas fa-edit"></i>
          </button>
          <button type="button" class="btn btn-sm btn-outline-${schedule.enabled ? 'warning' : 'success'}" data-action="toggle-schedule" data-schedule-id="${schedule.schedule_id}" data-enabled="${schedule.enabled}" title="${schedule.enabled ? 'Disable' : 'Enable'}">
            <i class="fas fa-${schedule.enabled ? 'pause' : 'play'}"></i>
          </button>
          <button type="button" class="btn btn-sm btn-outline-secondary" data-action="view-execution-log" data-schedule-id="${schedule.schedule_id}" title="Execution Log">
            <i class="fas fa-list-alt"></i>
          </button>
          <button type="button" class="btn btn-sm btn-outline-danger" data-action="delete-schedule" data-schedule-id="${schedule.schedule_id}" title="Delete">
            <i class="fas fa-trash"></i>
          </button>
        </div>
      </div>
    `;
  }

  /**
   * Open schedule modal for creating/editing
   */
  openScheduleModal(scheduleId = null) {
    const modal = document.getElementById('schedule-form-modal');
    const title = document.getElementById('schedule-form-title');
    const form = document.getElementById('device-schedule-form');
    
    if (!modal || !form) return;

    // Reset form
    form.reset();
    document.getElementById('edit-schedule-id').value = '';
    const scheduleTypeSelect = document.getElementById('schedule-schedule-type');
    if (scheduleTypeSelect) {
      delete scheduleTypeSelect.dataset.autoDefaultApplied;
    }
    
    // Check all days by default
    form.querySelectorAll('input[name="days_of_week"]').forEach(cb => cb.checked = true);

    if (scheduleId && this.schedulesById?.has(scheduleId)) {
      const schedule = this.schedulesById.get(scheduleId);
      title.innerHTML = '<i class="fas fa-calendar-edit me-2"></i>Edit Schedule';
      document.getElementById('edit-schedule-id').value = scheduleId;
      
      // Populate form
      this.setInputValue('schedule-name', schedule.name || '');
      this.setInputValue('schedule-device-type', schedule.device_type || '');
      this.setInputValue('schedule-schedule-type', schedule.schedule_type || 'simple');
      this.setInputValue('schedule-start', schedule.start_time || '');
      this.setInputValue('schedule-end', schedule.end_time || '');
      this.setInputValue('schedule-priority', schedule.priority || 50);
      this.setInputValue('schedule-value', schedule.value || '');
      this.setInputValue('schedule-interval-minutes', schedule.interval_minutes || '');
      this.setInputValue('schedule-duration-minutes', schedule.duration_minutes || '');
      
      const enabledCb = document.getElementById('schedule-enabled');
      if (enabledCb) enabledCb.checked = schedule.enabled !== false;
      
      // Set days of week
      form.querySelectorAll('input[name="days_of_week"]').forEach(cb => {
        cb.checked = (schedule.days_of_week || [0,1,2,3,4,5,6]).includes(parseInt(cb.value));
      });
      
      // Photoperiod settings
      if (schedule.photoperiod) {
        this.setInputValue('schedule-photoperiod-source', schedule.photoperiod.source || 'schedule');
        this.setInputValue('schedule-sensor-threshold', schedule.photoperiod.sensor_threshold || '');
      }
    } else {
      title.innerHTML = '<i class="fas fa-calendar-plus me-2"></i>Add Schedule';
    }

    // Show/hide photoperiod settings based on type
    this.updatePhotoperiodVisibility();
    
    // Update schedule type options based on device type
    this.updateScheduleTypeOptions();
    
    // Show modal
    modal.classList.remove('hidden');
    modal.classList.add('active');
    
    // Scroll modal to top
    const modalForm = modal.querySelector('.settings-form');
    if (modalForm) modalForm.scrollTop = 0;
  }

  setInputValue(id, value) {
    const el = document.getElementById(id);
    if (el) el.value = value;
  }

  updatePhotoperiodVisibility() {
    const typeSelect = document.getElementById('schedule-schedule-type');
    const photoperiodSection = document.getElementById('photoperiod-settings');
    const intervalSection = document.getElementById('interval-settings');
    
    if (typeSelect && photoperiodSection) {
      photoperiodSection.classList.toggle('hidden', typeSelect.value !== 'photoperiod');
    }
    if (typeSelect && intervalSection) {
      intervalSection.classList.toggle('hidden', typeSelect.value !== 'interval');
    }
    this.updateScheduleTimeRequirements();
  }

  /**
   * Show/hide automatic schedule option based on device type.
   * Automatic schedules are only available for lights.
   */
  updateScheduleTypeOptions() {
    const deviceTypeSelect = document.getElementById('schedule-device-type');
    const scheduleTypeSelect = document.getElementById('schedule-schedule-type');
    
    if (!deviceTypeSelect || !scheduleTypeSelect) return;

    const automaticOption = scheduleTypeSelect.querySelector('option[value="automatic"]');
    const photoperiodOption = scheduleTypeSelect.querySelector('option[value="photoperiod"]');
    
    const deviceType = deviceTypeSelect.value;
    const isLight = deviceType === 'light';

    // Show/hide automatic option (only for lights)
    if (automaticOption) {
      automaticOption.style.display = isLight ? '' : 'none';
      automaticOption.disabled = !isLight;
    }

    // Show/hide photoperiod option (only for lights)
    if (photoperiodOption) {
      photoperiodOption.style.display = isLight ? '' : 'none';
      photoperiodOption.disabled = !isLight;
    }

    // If current selection is automatic or photoperiod and device is not light, reset to simple
    if (!isLight && (scheduleTypeSelect.value === 'automatic' || scheduleTypeSelect.value === 'photoperiod')) {
      scheduleTypeSelect.value = 'simple';
      this.updatePhotoperiodVisibility();
    }
    const scheduleId = document.getElementById('edit-schedule-id')?.value;
    const autoDefaultApplied = scheduleTypeSelect.dataset.autoDefaultApplied === 'true';
    if (
      isLight
      && !scheduleId
      && !autoDefaultApplied
      && (!scheduleTypeSelect.value || scheduleTypeSelect.value === 'simple')
    ) {
      scheduleTypeSelect.value = 'automatic';
      scheduleTypeSelect.dataset.autoDefaultApplied = 'true';
      this.updatePhotoperiodVisibility();
    }
    this.updateScheduleTimeRequirements();
  }

  updateScheduleTimeRequirements() {
    const deviceTypeSelect = document.getElementById('schedule-device-type');
    const scheduleTypeSelect = document.getElementById('schedule-schedule-type');
    const endTimeInput = document.getElementById('schedule-end');
    const startTimeInput = document.getElementById('schedule-start');
    const photoperiodSource = document.getElementById('schedule-photoperiod-source')?.value;

    if (!endTimeInput || !startTimeInput) return;

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

  closeScheduleModal() {
    const modal = document.getElementById('schedule-form-modal');
    if (modal) {
      modal.classList.remove('active');
      modal.classList.add('hidden');
    }
  }

  /**
   * Handle schedule form submission (v3 API)
   */
  async handleScheduleFormSubmitV3(event) {
    event.preventDefault();

    if (!this.dataService.selectedUnitId) {
      this.displayMessage('No unit selected. Please select a growth unit from the dropdown above.', 'error');
      return;
    }

    const form = event.target;
    const scheduleId = document.getElementById('edit-schedule-id')?.value;

    // Validate required fields with user-friendly messages
    const deviceType = document.getElementById('schedule-device-type')?.value;
    const scheduleType = document.getElementById('schedule-schedule-type')?.value;
    const photoperiodSource = document.getElementById('schedule-photoperiod-source')?.value;
    const startTime = document.getElementById('schedule-start')?.value;
    const endTime = document.getElementById('schedule-end')?.value;
    const isAutomaticLight = deviceType === 'light' && scheduleType === 'automatic';
    const isSensorBasedPhotoperiod =
      scheduleType === 'photoperiod'
      && (photoperiodSource === 'sensor' || photoperiodSource === 'sun_api');

    if (!deviceType) {
      this.displayMessage('Please select a device type (e.g., Light, Fan, Pump)', 'error');
      document.getElementById('schedule-device-type')?.focus();
      return;
    }

    if (!startTime && !isSensorBasedPhotoperiod) {
      this.displayMessage('Please enter a start time for the schedule', 'error');
      document.getElementById('schedule-start')?.focus();
      return;
    }

    if (!endTime && !isAutomaticLight && !isSensorBasedPhotoperiod) {
      this.displayMessage('Please enter an end time for the schedule', 'error');
      document.getElementById('schedule-end')?.focus();
      return;
    }

    if (scheduleType === 'interval') {
      const intervalMinutes = parseInt(document.getElementById('schedule-interval-minutes')?.value);
      const durationMinutes = parseInt(document.getElementById('schedule-duration-minutes')?.value);
      if (!intervalMinutes || !durationMinutes) {
        this.displayMessage('Please enter interval and duration minutes for repeating schedules', 'error');
        return;
      }
      if (durationMinutes > intervalMinutes) {
        this.displayMessage('Duration must be less than or equal to interval', 'error');
        return;
      }
    }
    
    // Collect days of week
    const daysOfWeek = [];
    form.querySelectorAll('input[name="days_of_week"]:checked').forEach(cb => {
      daysOfWeek.push(parseInt(cb.value));
    });

    const payload = {
      name: document.getElementById('schedule-name')?.value || '',
      device_type: document.getElementById('schedule-device-type')?.value || '',
      schedule_type: scheduleType || 'simple',
      start_time: document.getElementById('schedule-start')?.value || '',
      end_time: document.getElementById('schedule-end')?.value || '',
      days_of_week: daysOfWeek.length > 0 ? daysOfWeek : [0,1,2,3,4,5,6],
      priority: parseInt(document.getElementById('schedule-priority')?.value) || 50,
      enabled: document.getElementById('schedule-enabled')?.checked !== false
    };

    // Add value if set
    const valueInput = document.getElementById('schedule-value');
    if (valueInput && valueInput.value) {
      payload.value = parseFloat(valueInput.value);
    }

    // Add photoperiod config if applicable
    if (payload.schedule_type === 'photoperiod') {
      payload.photoperiod = {
        source: photoperiodSource || 'schedule',
        sensor_threshold: parseInt(document.getElementById('schedule-sensor-threshold')?.value) || null
      };
    }

    if (payload.schedule_type === 'interval') {
      const intervalMinutes = parseInt(document.getElementById('schedule-interval-minutes')?.value);
      const durationMinutes = parseInt(document.getElementById('schedule-duration-minutes')?.value);
      payload.interval_minutes = intervalMinutes || null;
      payload.duration_minutes = durationMinutes || null;
    }

    if (payload.schedule_type === 'photoperiod' && (photoperiodSource === 'sensor' || photoperiodSource === 'sun_api')) {
      payload.start_time = '00:00';
      payload.end_time = '00:00';
    }

    try {
      if (scheduleId) {
        await this.dataService.updateScheduleV3(parseInt(scheduleId), payload);
        this.displayMessage('Schedule updated successfully', 'success');
      } else {
        await this.dataService.createScheduleV3(payload);
        this.displayMessage('Schedule created successfully', 'success');
      }

      this.closeScheduleModal();
      await this.loadSchedulesV3({ force: true });
    } catch (error) {
      this.displayMessage(`Failed to save schedule: ${this.normalizeError(error)}`, 'error');
    }
  }

  /**
   * Toggle schedule enabled state
   */
  async toggleSchedule(scheduleId, enabled) {
    try {
      await this.dataService.toggleScheduleV3(scheduleId, enabled);
      this.displayMessage(`Schedule ${enabled ? 'enabled' : 'disabled'}`, 'success');
      await this.loadSchedulesV3({ force: true });
    } catch (error) {
      this.displayMessage(`Failed to toggle schedule: ${this.normalizeError(error)}`, 'error');
    }
  }

  /**
   * Delete a schedule
   */
  async deleteSchedule(scheduleId) {
    if (!confirm('Are you sure you want to delete this schedule?')) return;

    try {
      await this.dataService.deleteScheduleV3(scheduleId);
      this.displayMessage('Schedule deleted', 'success');
      await this.loadSchedulesV3({ force: true });
    } catch (error) {
      this.displayMessage(`Failed to delete schedule: ${this.normalizeError(error)}`, 'error');
    }
  }

  /**
   * Show schedule preview modal
   */
  async showSchedulePreview() {
    const modal = document.getElementById('schedule-preview-modal');
    const content = document.getElementById('schedule-preview-content');
    
    if (!modal || !content) return;
    
    content.innerHTML = '<div class="loading"><i class="fas fa-spinner fa-spin"></i> Loading preview...</div>';
    modal.classList.remove('hidden');
    modal.classList.add('active');

    try {
      const data = await this.dataService.previewSchedules({ hours: 24 });
      
      if (!data.events || data.events.length === 0) {
        content.innerHTML = '<div class="empty-state"><i class="fas fa-calendar-check"></i><p>No events scheduled in the next 24 hours</p></div>';
        return;
      }

      const html = data.events.map(event => {
        const time = new Date(event.event_time).toLocaleString();
        const icon = event.event_type === 'activate' ? 'fa-play text-success' : 'fa-stop text-danger';
        return `
          <div class="preview-event">
            <i class="fas ${icon}"></i>
            <div class="event-details">
              <strong>${event.schedule_name}</strong>
              <span class="event-device">${event.device_type}</span>
              <span class="event-time">${time}</span>
            </div>
            <span class="event-type">${event.event_type}</span>
          </div>
        `;
      }).join('');

      content.innerHTML = `<div class="preview-events">${html}</div>`;
    } catch (error) {
      content.innerHTML = `<div class="error-state">Failed to load preview: ${this.normalizeError(error)}</div>`;
    }
  }

  /**
   * Show conflicts modal
   */
  async showConflicts() {
    const modal = document.getElementById('schedule-conflicts-modal');
    const content = document.getElementById('schedule-conflicts-content');
    
    if (!modal || !content) return;
    
    content.innerHTML = '<div class="loading"><i class="fas fa-spinner fa-spin"></i> Checking conflicts...</div>';
    modal.classList.remove('hidden');
    modal.classList.add('active');

    try {
      const data = await this.dataService.detectConflicts();
      
      if (!data.has_conflicts) {
        content.innerHTML = '<div class="success-state"><i class="fas fa-check-circle text-success"></i><p>No conflicts detected!</p></div>';
        return;
      }

      const html = data.conflicts.map(conflict => `
        <div class="conflict-item">
          <div class="conflict-schedules">
            <strong>${conflict.schedule_a_name}</strong>
            <span class="vs">vs</span>
            <strong>${conflict.schedule_b_name}</strong>
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
      content.innerHTML = `<div class="error-state">Failed to check conflicts: ${this.normalizeError(error)}</div>`;
    }
  }

  /**
   * Show history modal
   */
  async showHistory() {
    const modal = document.getElementById('schedule-history-modal');
    const content = document.getElementById('schedule-history-content');
    
    if (!modal || !content) return;
    
    content.innerHTML = '<div class="loading"><i class="fas fa-spinner fa-spin"></i> Loading history...</div>';
    modal.classList.remove('hidden');
    modal.classList.add('active');

    try {
      const data = await this.dataService.getScheduleHistory({ limit: 50 });
      
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
              ${entry.reason ? `<span class="entry-reason">${entry.reason}</span>` : ''}
            </div>
            <span class="entry-time">${time}</span>
          </div>
        `;
      }).join('');

      content.innerHTML = `<div class="history-list">${html}</div>`;
    } catch (error) {
      content.innerHTML = `<div class="error-state">Failed to load history: ${this.normalizeError(error)}</div>`;
    }
  }

  /**
   * Show execution log for a schedule
   */
  async showExecutionLog(scheduleId) {
    const modal = document.getElementById('schedule-history-modal');
    const content = document.getElementById('schedule-history-content');
    const title = modal?.querySelector('.modal-header h3');
    
    if (!modal || !content) return;
    
    if (title) title.innerHTML = '<i class="fas fa-list-alt me-2"></i>Execution Log';
    content.innerHTML = '<div class="loading"><i class="fas fa-spinner fa-spin"></i> Loading execution log...</div>';
    modal.classList.remove('hidden');
    modal.classList.add('active');

    try {
      const data = await this.dataService.getExecutionLog(scheduleId, { limit: 50 });
      
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
              ${entry.error_message ? `<span class="entry-error">${entry.error_message}</span>` : ''}
            </div>
            <span class="entry-time">${time}</span>
          </div>
        `;
      }).join('');

      content.innerHTML = `<div class="execution-list">${html}</div>`;
    } catch (error) {
      content.innerHTML = `<div class="error-state">Failed to load execution log: ${this.normalizeError(error)}</div>`;
    }
  }

  closeModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
      modal.classList.remove('active');
      modal.classList.add('hidden');
    }
  }

  /**
   * Filter schedules by device type
   */
  filterSchedules(deviceType) {
    const cards = document.querySelectorAll('.schedule-card');
    cards.forEach(card => {
      if (deviceType === 'all' || !deviceType) {
        card.classList.remove('hidden');
      } else {
        const scheduleDevice = card.querySelector('.schedule-device')?.textContent;
        card.classList.toggle('hidden', scheduleDevice !== deviceType);
      }
    });
  }

  /**
   * Auto-generate schedules based on plant stage
   */
  async handleAutoGenerateSchedules() {
    if (!this.dataService.selectedUnitId) {
      this.displayMessage('Please select a unit first', 'error');
      return;
    }

    // Confirm with user
    const confirmed = confirm(
      'This will generate schedules based on the current plant stage.\n\n' +
      'Existing automatic schedules will be replaced.\n\n' +
      'Continue?'
    );

    if (!confirmed) return;

    this.displayMessage('Generating schedules...', 'info');

    const result = await this.dataService.autoGenerateSchedules({
      replace_existing: true
    });

    if (result.ok) {
      const count = result.data?.schedules_created || result.data?.created?.length || 0;
      this.displayMessage(`Generated ${count} schedule${count !== 1 ? 's' : ''} successfully`, 'success');
      // Reload schedules
      await this.loadSchedules();
    } else {
      this.displayMessage(result.error || 'Failed to generate schedules', 'error');
    }
  }

  /**
   * Show schedule templates modal
   */
  async showScheduleTemplates() {
    // Create modal if it doesn't exist
    let modal = document.getElementById('schedule-templates-modal');
    if (!modal) {
      modal = document.createElement('div');
      modal.id = 'schedule-templates-modal';
      modal.className = 'modal-overlay hidden';
      modal.innerHTML = `
        <div class="modal-content">
          <div class="modal-header">
            <h3><i class="fas fa-file-alt me-2"></i>Schedule Templates</h3>
            <button class="modal-close" aria-label="Close">&times;</button>
          </div>
          <div class="modal-body" id="schedule-templates-content">
            <p class="templates-description">
              These templates are based on the current plant's growth stage requirements. 
              Select the templates you want to apply.
            </p>
            <div id="templates-list" class="templates-grid">
              <div class="loading"><i class="fas fa-spinner fa-spin"></i> Loading templates...</div>
            </div>
          </div>
          <div class="modal-footer">
            <button type="button" class="btn btn-primary" id="apply-templates-btn">
              <i class="fas fa-check me-1"></i> Apply Selected
            </button>
            <button type="button" class="btn btn-secondary modal-close">Cancel</button>
          </div>
        </div>
      `;
      document.body.appendChild(modal);

      // Add event listeners
      modal.querySelectorAll('.modal-close').forEach(btn => {
        this.addEventListener(btn, 'click', () => this.closeModal('schedule-templates-modal'));
      });

      const applyBtn = modal.querySelector('#apply-templates-btn');
      if (applyBtn) {
        this.addEventListener(applyBtn, 'click', () => this.handleApplyTemplates());
      }
    }

    const content = document.getElementById('templates-list');
    if (!content) return;

    content.innerHTML = '<div class="loading"><i class="fas fa-spinner fa-spin"></i> Loading templates...</div>';
    modal.classList.remove('hidden');
    modal.classList.add('active');

    try {
      const data = await this.dataService.getScheduleTemplates();

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

      const deviceIcons = {
        light: 'fas fa-lightbulb',
        fan: 'fas fa-fan',
        pump: 'fas fa-tint',
        heater: 'fas fa-fire',
        cooler: 'fas fa-snowflake'
      };

      const html = data.templates.map((template, idx) => {
        const icon = deviceIcons[template.device_type] || 'fas fa-clock';
        return `
          <div class="template-item" data-template-index="${idx}">
            <label class="template-checkbox">
              <input type="checkbox" name="template_${idx}" value="${idx}" checked>
            </label>
            <div class="template-info">
              <div class="template-header">
                <i class="${icon}"></i>
                <strong>${template.name || template.device_type}</strong>
              </div>
              <div class="template-details">
                <span><i class="far fa-clock"></i> ${template.start_time} - ${template.end_time}</span>
                ${template.value ? `<span><i class="fas fa-sliders-h"></i> ${template.value}%</span>` : ''}
              </div>
              <div class="template-meta">
                <span class="badge">automatic</span>
                ${data.plant_info?.stage ? `<span class="badge badge-secondary">${data.plant_info.stage} stage</span>` : ''}
              </div>
            </div>
          </div>
        `;
      }).join('');

      const plantInfo = data.plant_info ? `
        <div class="plant-info-banner mb-3">
          <i class="fas fa-seedling"></i>
          <span><strong>${data.plant_info.name}</strong> - ${data.plant_info.stage} stage</span>
        </div>
      ` : '';

      content.innerHTML = plantInfo + html;
    } catch (error) {
      content.innerHTML = `<div class="error-state">Failed to load templates: ${this.normalizeError(error)}</div>`;
    }
  }

  /**
   * Apply selected templates to create schedules
   */
  async handleApplyTemplates() {
    if (!this.currentTemplates) {
      this.displayMessage('No templates to apply', 'error');
      return;
    }

    const templatesList = document.getElementById('templates-list');
    const checkboxes = templatesList?.querySelectorAll('input[type="checkbox"]:checked');

    if (!checkboxes || checkboxes.length === 0) {
      this.displayMessage('Please select at least one template', 'warning');
      return;
    }

    // Get selected template indices
    const selectedIndices = Array.from(checkboxes).map(cb => parseInt(cb.value));
    const selectedTemplates = selectedIndices.map(idx => this.currentTemplates[idx]).filter(Boolean);

    this.displayMessage('Creating schedules...', 'info');

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

      const result = await this.dataService.createScheduleV3(payload);
      if (result.ok) {
        successCount++;
      } else {
        errorCount++;
        console.error(`Failed to create schedule for ${template.device_type}:`, result.error);
      }
    }

    // Close modal and show result
    this.closeModal('schedule-templates-modal');
    this.currentTemplates = null;

    if (successCount > 0) {
      this.displayMessage(`Created ${successCount} schedule${successCount !== 1 ? 's' : ''} successfully`, 'success');
      await this.loadSchedules();
    }
    if (errorCount > 0) {
      this.displayMessage(`Failed to create ${errorCount} schedule${errorCount !== 1 ? 's' : ''}`, 'error');
    }
  }

  // ============================================================================
  // WIFI FUNCTIONS
  // ============================================================================

  async handleScanWiFi() {
    const button = this.elements.scanWiFiButton;
    const ssidSelect = document.getElementById('setup-ssid');
    if (!ssidSelect) return;

    this.setButtonLoading(button, true, 'Scanning...');

    try {
      const networks = await this.dataService.scanWiFiNetworks({ force: true });

      ssidSelect.innerHTML = '<option value="">Select a network...</option>';

      if (networks && networks.length > 0) {
        networks.forEach(network => {
          const option = document.createElement('option');
          option.value = network.ssid || network;
          option.textContent = network.ssid || network;
          if (network.signal) option.textContent += ` (Signal: ${network.signal})`;
          ssidSelect.appendChild(option);
        });
        this.displayMessage(`Found ${networks.length} networks`, 'success');
      } else {
        const option = document.createElement('option');
        option.disabled = true;
        option.textContent = 'No networks found';
        ssidSelect.appendChild(option);
      }
    } catch (error) {
      this.displayMessage(`WiFi scan failed: ${this.normalizeError(error)}`, 'error');
    } finally {
      this.setButtonLoading(button, false);
    }
  }

  async handleSendWiFiConfig() {
    const deviceId = document.getElementById('device-id')?.value || '';
    const ssid = document.getElementById('setup-ssid')?.value || '';
    const password = document.getElementById('setup-password')?.value || '';
    const setupMethod = document.getElementById('wifi-setup-method')?.value || '';

    if (!deviceId) {
      this.displayMessage('Please select a device first', 'error');
      return;
    }
    if (!ssid) {
      this.displayMessage('Please select a WiFi network', 'error');
      return;
    }

    const button = this.elements.sendWiFiButton;
    this.setButtonLoading(button, true, 'Sending...');

    try {
      const payload = { device_id: deviceId, ssid, password, method: setupMethod };
      await this.dataService.sendWiFiConfig(payload);
      this.displayMessage('WiFi configuration sent successfully', 'success');

      const pw = document.getElementById('setup-password');
      if (pw) pw.value = '';
    } catch (error) {
      this.displayMessage(`Failed to send WiFi configuration: ${this.normalizeError(error)}`, 'error');
    } finally {
      this.setButtonLoading(button, false);
    }
  }

  async handleBroadcastWiFi() {
    const ssid = document.getElementById('setup-ssid')?.value || '';
    const password = document.getElementById('setup-password')?.value || '';
    const setupMethod = document.getElementById('wifi-setup-method')?.value || '';

    if (!ssid) {
      this.displayMessage('Please select a WiFi network', 'error');
      return;
    }

    const button = this.elements.broadcastWiFiButton;
    this.setButtonLoading(button, true, 'Broadcasting...');

    try {
      const payload = { ssid, password, method: setupMethod, broadcast: true };
      const response = await this.dataService.broadcastWiFiConfig(payload);
      this.displayMessage(`WiFi configuration broadcast to ${response?.deviceCount || 'all'} devices`, 'success');

      const pw = document.getElementById('setup-password');
      if (pw) pw.value = '';
    } catch (error) {
      this.displayMessage(`Failed to broadcast WiFi configuration: ${this.normalizeError(error)}`, 'error');
    } finally {
      this.setButtonLoading(button, false);
    }
  }

  // ============================================================================
  // ESP32 DEVICE MANAGEMENT (unchanged behavior)
  // ============================================================================

  async handleScanDevices() {
    const button = this.elements.deviceScanButton;
    const deviceList = this.elements.deviceList;
    if (!deviceList) return;

    this.setButtonLoading(button, true, 'Scanning...');

    try {
      const devices = await this.dataService.scanESP32Devices({ force: true });
      deviceList.innerHTML = '';

      if (devices && devices.length > 0) {
        devices.forEach(device => {
          const option = document.createElement('option');
          option.value = device.id;
          option.textContent = `${device.name || device.id} (${device.type || 'Unknown'})`;
          option.dataset.deviceInfo = JSON.stringify(device);
          deviceList.appendChild(option);
        });
        this.displayMessage(`Found ${devices.length} devices`, 'success');
      } else {
        const option = document.createElement('option');
        option.disabled = true;
        option.textContent = 'No devices found';
        deviceList.appendChild(option);
      }
    } catch (error) {
      this.displayMessage(`Device scan failed: ${this.normalizeError(error)}`, 'error');
      deviceList.innerHTML = '';
      const option = document.createElement('option');
      option.disabled = true;
      option.textContent = 'Scan failed - try again';
      deviceList.appendChild(option);
    } finally {
      this.setButtonLoading(button, false);
    }
  }

  async handleLoadDeviceInfo() {
    const deviceList = this.elements.deviceList;
    if (!deviceList) return;

    const selectedOption = deviceList.options[deviceList.selectedIndex];
    if (selectedOption && selectedOption.dataset.deviceInfo) {
      const device = JSON.parse(selectedOption.dataset.deviceInfo);

      const idEl = document.getElementById('device-id');
      const typeEl = document.getElementById('device-type');
      const nameEl = document.getElementById('device-name');

      if (idEl) idEl.value = device.id || '';
      if (typeEl) typeEl.value = device.type || 'sensor';
      if (nameEl) nameEl.value = device.name || '';

      await this.loadESP32DeviceSettings(device.id);
    }
  }

  async loadESP32DeviceSettings(deviceId) {
    if (!deviceId) return;

    try {
      const data = await this.dataService.loadESP32Device(deviceId);

      const fieldMap = {
        'connection-mode': data.connection_mode || 'wifi',
        'mqtt-broker': data.mqtt_broker || '',
        'mqtt-port': data.mqtt_port || 8883,
        'mqtt-username': data.mqtt_username || '',
        'sleep-duration': data.sleep_duration || 5,
        'battery-threshold': data.battery_threshold || 3.3
      };

      Object.entries(fieldMap).forEach(([id, value]) => {
        const element = document.getElementById(id);
        if (element) element.value = value;
      });

      this.updateConditionalFields();

      if (this.elements.esp32Form) this.markFormPristine(this.elements.esp32Form);
    } catch (error) {
      this.warn('Failed to load ESP32 device settings:', error);
    }
  }

  async handleCheckFirmware() {
    const deviceId = document.getElementById('device-id')?.value || '';
    if (!deviceId) {
      this.displayMessage('Please select a device first', 'error');
      return;
    }

    const button = this.elements.checkFirmwareButton;
    this.setButtonLoading(button, true, 'Checking...');

    try {
      const result = await this.dataService.checkFirmwareUpdate(deviceId);
      if (result.updateAvailable) {
        this.displayMessage(`Firmware update available: ${result.version}`, 'success');
      } else {
        this.displayMessage('Firmware is up to date', 'success');
      }
    } catch (error) {
      this.displayMessage(`Failed to check firmware: ${this.normalizeError(error)}`, 'error');
    } finally {
      this.setButtonLoading(button, false);
    }
  }

  async handleProvisionDevice() {
    const deviceId = document.getElementById('device-id')?.value || '';
    if (!deviceId) {
      this.displayMessage('Please select a device first', 'error');
      return;
    }

    const button = this.elements.provisionButton;
    this.setButtonLoading(button, true, 'Provisioning...');

    try {
      await this.dataService.provisionDevice(deviceId);
      this.displayMessage('Device provisioned successfully', 'success');
    } catch (error) {
      this.displayMessage(`Failed to provision device: ${this.normalizeError(error)}`, 'error');
    } finally {
      this.setButtonLoading(button, false);
    }
  }

  async handleESP32FormSubmit(event) {
    event.preventDefault();

    const deviceId = document.getElementById('device-id')?.value || '';
    if (!deviceId) {
      this.displayMessage('Please select a device first', 'error');
      return;
    }

    const formData = new FormData(event.target);
    const payload = Object.fromEntries(formData.entries());

    payload.auto_irrigation = this.getCheckboxBool(formData, 'enable_auto_irrigation');
    payload.enable_flow_sensor = this.getCheckboxBool(formData, 'enable_flow_sensor');
    payload.enable_emergency_stop = this.getCheckboxBool(formData, 'enable_emergency_stop');

    const numericFields = [
      'mqtt_port', 'water_pump_pin', 'mist_blower_pin', 'pump_duration',
      'mist_duration', 'irrigation_interval', 'moisture_threshold',
      'max_pump_runtime', 'flow_sensor_pin', 'emergency_stop_pin',
      'sleep_duration', 'battery_threshold', 'sensor_interval', 'ota_check_interval'
    ];

    numericFields.forEach(field => {
      payload[field] = this.getNumber(formData, field);
    });

    try {
      await this.dataService.saveESP32Device(deviceId, payload);
      this.markFormPristine(event.target);
      this.displayMessage('ESP32 device settings saved successfully', 'success');
    } catch (error) {
      this.displayMessage(`Failed to save ESP32 settings: ${this.normalizeError(error)}`, 'error');
    }
  }

  // ============================================================================
  // HOTSPOT SETTINGS
  // ============================================================================

  async loadHotspotSettings() {
    try {
      const data = await this.dataService.loadHotspotSettings();

      const ssidInput = document.getElementById('hotspot-ssid');
      if (ssidInput && data?.ssid) ssidInput.value = data.ssid;

      if (this.elements.hotspotForm) this.markFormPristine(this.elements.hotspotForm);
    } catch (error) {
      this.warn('Failed to load hotspot settings:', error);
    }
  }

  async handleHotspotSubmit(event) {
    event.preventDefault();

    const ssid = (document.getElementById('hotspot-ssid')?.value || '').trim();
    const password = (document.getElementById('hotspot-password')?.value || '').trim();

    if (!ssid) {
      this.displayMessage('SSID is required', 'error');
      return;
    }

    const payload = { ssid };
    if (password) payload.password = password;

    try {
      await this.dataService.saveHotspotSettings(payload);
      this.markFormPristine(event.target);
      this.displayMessage('Hotspot settings saved successfully', 'success');

      const pw = document.getElementById('hotspot-password');
      if (pw) pw.value = '';
    } catch (error) {
      this.displayMessage(`Failed to save hotspot settings: ${this.normalizeError(error)}`, 'error');
    }
  }

  // ============================================================================
  // CAMERA SETTINGS
  // ============================================================================

  async loadCameraSettings() {
    try {
      const data = await this.dataService.loadCameraSettings();

      const fieldMap = {
        'camera-type': data.camera_type || 'esp32_wireless',
        'camera-ip': data.ip_address || '',
        'camera-usb-index': data.usb_cam_index || 0,
        'camera-resolution': data.resolution || 800,
        'camera-quality': data.quality || 10,
        'camera-brightness': data.brightness || 0,
        'camera-contrast': data.contrast || 0,
        'camera-saturation': data.saturation || 0,
        'camera-flip': data.flip || 0
      };

      Object.entries(fieldMap).forEach(([id, value]) => {
        const element = document.getElementById(id);
        if (element) element.value = value;
      });

      this.updateConditionalFields();

      if (this.elements.cameraForm) this.markFormPristine(this.elements.cameraForm);
    } catch (error) {
      this.warn('Failed to load camera settings:', error);
    }
  }

  async handleCameraSubmit(event) {
    event.preventDefault();

    const payload = {
      camera_type: document.getElementById('camera-type')?.value,
      ip_address: (document.getElementById('camera-ip')?.value || '').trim() || null,
      usb_cam_index: this.safeNumber(document.getElementById('camera-usb-index')?.value),
      resolution: this.safeNumber(document.getElementById('camera-resolution')?.value),
      quality: this.safeNumber(document.getElementById('camera-quality')?.value),
      brightness: this.safeNumber(document.getElementById('camera-brightness')?.value),
      contrast: this.safeNumber(document.getElementById('camera-contrast')?.value),
      saturation: this.safeNumber(document.getElementById('camera-saturation')?.value),
      flip: this.safeNumber(document.getElementById('camera-flip')?.value) ?? 0
    };

    Object.keys(payload).forEach(key => {
      if (payload[key] === null || payload[key] === undefined) delete payload[key];
    });

    try {
      await this.dataService.saveCameraSettings(payload);
      this.markFormPristine(event.target);
      this.displayMessage('Camera settings saved successfully', 'success');
    } catch (error) {
      this.displayMessage(`Failed to save camera settings: ${this.normalizeError(error)}`, 'error');
    }
  }

  // ============================================================================
  // ANALYTICS SETTINGS (FIXED ID MISMATCHES)
  // ============================================================================

  async loadAnalyticsSettings() {
    try {
      const settings = await this.dataService.loadAnalyticsSettings();
      if (!settings) return;

      // Energy
      if (settings.energy) {
        const rateInput = document.getElementById('energy-rate');
        const currencyInput = document.getElementById('currency-code');
        const showEstimatesInput = document.getElementById('show-cost-estimates');

        if (rateInput && settings.energy.rate !== undefined) rateInput.value = settings.energy.rate;
        if (currencyInput && settings.energy.currency) currencyInput.value = settings.energy.currency;
        if (showEstimatesInput) showEstimatesInput.checked = Boolean(settings.energy.showEstimates);
      }

      // Alerts (support both old method names and current HTML IDs)
      if (settings.alerts) {
        const tempInput = document.getElementById('critical-temp-threshold');
        const humidityInput = document.getElementById('critical-humidity-threshold');
        const frequencyInput = document.getElementById('alert-frequency');

        if (tempInput && settings.alerts.criticalTemp !== undefined) tempInput.value = settings.alerts.criticalTemp;
        if (humidityInput && settings.alerts.criticalHumidity !== undefined) humidityInput.value = settings.alerts.criticalHumidity;
        if (frequencyInput && settings.alerts.frequency) frequencyInput.value = settings.alerts.frequency;

        const methodMap = new Map([
          ['in_app', 'alert-in-app'],
          ['dashboard', 'alert-in-app'],
          ['browser', 'alert-in-app'],
          ['email', 'alert-email'],
          ['push', 'alert-push']
        ]);

        // Clear first, then apply
        ['alert-in-app', 'alert-email', 'alert-push'].forEach(id => {
          const cb = document.getElementById(id);
          if (cb) cb.checked = false;
        });

        const methods = Array.isArray(settings.alerts.methods) ? settings.alerts.methods : [];
        methods.forEach(method => {
          const id = methodMap.get(method);
          const cb = id ? document.getElementById(id) : null;
          if (cb) cb.checked = true;
        });
      }

      // Data
      if (settings.data) {
        const retentionInput = document.getElementById('data-retention');
        const autoBackupInput = document.getElementById('auto-backup');

        // Export format radios: select by name/value
        if (settings.data.exportFormat) {
          const radio = document.querySelector(`input[name="export-format"][value="${settings.data.exportFormat}"]`);
          if (radio) radio.checked = true;
        }

        if (retentionInput && settings.data.retention !== undefined) retentionInput.value = String(settings.data.retention);
        if (autoBackupInput) autoBackupInput.checked = Boolean(settings.data.autoBackup);
      }

      if (this.elements.energyForm) this.markFormPristine(this.elements.energyForm);
      if (this.elements.alertsForm) this.markFormPristine(this.elements.alertsForm);
      if (this.elements.dataForm) this.markFormPristine(this.elements.dataForm);
    } catch (error) {
      this.warn('Failed to load analytics settings:', error);
    }
  }

  async handleAnalyticsSubmit(event, section) {
    event.preventDefault();

    try {
      const settings = {};

      if (section === 'energy') {
        settings.energy = {
          rate: parseFloat(document.getElementById('energy-rate')?.value) || 0.12,
          currency: document.getElementById('currency-code')?.value || 'USD',
          showEstimates: Boolean(document.getElementById('show-cost-estimates')?.checked)
        };
      }

      if (section === 'alerts') {
        const methods = [];

        // Align with your current HTML IDs
        if (document.getElementById('alert-in-app')?.checked) methods.push('in_app');
        if (document.getElementById('alert-email')?.checked) methods.push('email');
        if (document.getElementById('alert-push')?.checked) methods.push('push');

        settings.alerts = {
          criticalTemp: parseFloat(document.getElementById('critical-temp-threshold')?.value) || 35,
          criticalHumidity: parseFloat(document.getElementById('critical-humidity-threshold')?.value) || 85,
          methods,
          frequency: document.getElementById('alert-frequency')?.value || 'immediate'
        };
      }

      if (section === 'data') {
        const formatRadio = document.querySelector('input[name="export-format"]:checked');
        settings.data = {
          exportFormat: formatRadio ? formatRadio.value : 'csv',
          retention: parseInt(document.getElementById('data-retention')?.value, 10) || 90,
          autoBackup: Boolean(document.getElementById('auto-backup')?.checked)
        };
      }

      await this.dataService.saveAnalyticsSettings(settings);

      this.markFormPristine(event.target);
      this.displayMessage(`${section.charAt(0).toUpperCase() + section.slice(1)} settings saved successfully`, 'success');
    } catch (error) {
      this.displayMessage(`Failed to save ${section} settings: ${this.normalizeError(error)}`, 'error');
    }
  }

  async handleExportData() {
    const button = this.elements.exportDataButton;
    this.setButtonLoading(button, true, 'Exporting...');

    try {
      const formatRadio = document.querySelector('input[name="export-format"]:checked');
      const format = formatRadio ? formatRadio.value : 'csv';

      const result = await this.dataService.exportAnalyticsData(format);

      if (result?.url) {
        window.location.href = result.url;
        this.displayMessage('Data exported successfully', 'success');
      } else {
        this.displayMessage('Export initiated - check downloads', 'success');
      }
    } catch (error) {
      this.displayMessage(`Failed to export data: ${this.normalizeError(error)}`, 'error');
    } finally {
      this.setButtonLoading(button, false);
    }
  }

  // ============================================================================
  // ZIGBEE DISCOVERY (unchanged behavior)
  // ============================================================================

  async handleDiscoverZigbee() {
    const listContainer = document.getElementById('zigbee-discover-list');
    const button = this.elements.zigbeeDiscoverButton;
    if (!listContainer || !button) return;

    this.setButtonLoading(button, true, 'Discovering...');
    listContainer.innerHTML = '';

    try {
      const devices = await this.dataService.discoverZigbeeDevices({ force: true });

      if (devices && devices.length > 0) {
        devices.forEach(device => {
          const deviceCard = document.createElement('div');
          deviceCard.className = 'device-card';
          deviceCard.innerHTML = `
            <div class="device-info">
              <strong>${device.friendly_name || device.ieee_address}</strong>
              <span class="device-type">${device.type || 'Unknown'}</span>
              <span class="device-model">${device.model || ''}</span>
            </div>
            <button class="btn btn-sm btn-primary add-device-btn" data-device='${JSON.stringify(device)}'>
              Add Device
            </button>
          `;
          listContainer.appendChild(deviceCard);
        });

        listContainer.querySelectorAll('.add-device-btn').forEach(btn => {
          this.addEventListener(btn, 'click', () => {
            const device = JSON.parse(btn.dataset.device);
            this.handleAddZigbeeDevice(device);
          });
        });

        this.displayMessage(`Found ${devices.length} Zigbee devices`, 'success');
      } else {
        listContainer.innerHTML = '<p class="text-muted">No Zigbee devices found</p>';
      }
    } catch (error) {
      listContainer.innerHTML = '<p class="text-error">Discovery failed - try again</p>';
      this.displayMessage(`Zigbee discovery failed: ${this.normalizeError(error)}`, 'error');
    } finally {
      this.setButtonLoading(button, false);
    }
  }

  async handleAddZigbeeDevice(device) {
    try {
      const nameEl = document.getElementById('device-name-add');
      const commEl = document.getElementById('communication-type-add');
      const topicEl = document.getElementById('mqtt-topic-add');

      if (nameEl) nameEl.value = device.friendly_name || '';
      if (commEl) commEl.value = 'zigbee2mqtt';
      if (topicEl) topicEl.value = `zigbee2mqtt/${device.friendly_name}`;

      this.displayMessage('Device info loaded - review and click Add Device to save', 'success');

      // Mark add-device form dirty if present
      if (this.elements.addDeviceForm) {
        this.lastEditedForm = this.elements.addDeviceForm;
        if (this.isFormDirty(this.elements.addDeviceForm)) this.dirtyForms.add(this.elements.addDeviceForm);
        this.refreshSaveBar();
      }
    } catch (error) {
      this.displayMessage(`Failed to load device info: ${this.normalizeError(error)}`, 'error');
    }
  }

  async handleAddDeviceSubmit(event) {
    event.preventDefault();

    const formData = new FormData(event.target);
    const deviceData = Object.fromEntries(formData.entries());

    try {
      await this.dataService.addDevice(deviceData);
      event.target.reset();

      this.markFormPristine(event.target);
      this.displayMessage('Device added successfully', 'success');
    } catch (error) {
      this.displayMessage(`Failed to add device: ${this.normalizeError(error)}`, 'error');
    }
  }

  // ============================================================================
  // EVENT LISTENERS
  // ============================================================================

  attachEventListeners() {
    // Unit selectors (keep in sync)
    if (this.elements.unitSelector) {
      this.addEventListener(this.elements.unitSelector, 'change', async (e) => {
        const unitId = parseInt(e.target.value, 10);
        if (Number.isFinite(unitId)) {
          await this.applyUnitSelection(unitId);
          this.displayMessage('Unit selected', 'success');
        }
      });
    }

    if (this.elements.databaseUnitSelector) {
      this.addEventListener(this.elements.databaseUnitSelector, 'change', async (e) => {
        const unitId = parseInt(e.target.value, 10);
        if (Number.isFinite(unitId)) {
          await this.applyUnitSelection(unitId);
          this.displayMessage('Unit selected', 'success');
        }
      });
    }

    // Forms
    if (this.elements.environmentForm) {
      this.addEventListener(this.elements.environmentForm, 'submit', (e) => this.handleEnvironmentSubmit(e));
    }

    if (this.elements.suggestButton) {
      this.addEventListener(this.elements.suggestButton, 'click', () => this.handleSuggestThresholds());
    }

    if (this.elements.scheduleDeviceSelector) {
      this.activeScheduleDeviceType = this.getSelectedScheduleDeviceType() || this.activeScheduleDeviceType;
      this.addEventListener(this.elements.scheduleDeviceSelector, 'change', () => this.handleScheduleDeviceChange());
    }

    if (this.elements.scheduleForm) {
      this.addEventListener(this.elements.scheduleForm, 'submit', (e) => this.handleScheduleSubmit(e));
    }

    // V3 Schedule Management Event Listeners
    const deviceScheduleForm = document.getElementById('device-schedule-form');
    if (deviceScheduleForm) {
      this.addEventListener(deviceScheduleForm, 'submit', (e) => this.handleScheduleFormSubmitV3(e));
    }

    const addScheduleBtn = document.getElementById('add-schedule-btn');
    if (addScheduleBtn) {
      this.addEventListener(addScheduleBtn, 'click', () => this.openScheduleModal());
    }

    const previewSchedulesBtn = document.getElementById('preview-schedules-btn');
    if (previewSchedulesBtn) {
      this.addEventListener(previewSchedulesBtn, 'click', () => this.showSchedulePreview());
    }

    const checkConflictsBtn = document.getElementById('check-conflicts-btn');
    if (checkConflictsBtn) {
      this.addEventListener(checkConflictsBtn, 'click', () => this.showConflicts());
    }

    const viewHistoryBtn = document.getElementById('view-history-btn');
    if (viewHistoryBtn) {
      this.addEventListener(viewHistoryBtn, 'click', () => this.showHistory());
    }

    // Auto-generate schedules button
    const autoGenerateBtn = document.getElementById('auto-generate-btn');
    if (autoGenerateBtn) {
      this.addEventListener(autoGenerateBtn, 'click', () => this.handleAutoGenerateSchedules());
    }

    // View templates button
    const viewTemplatesBtn = document.getElementById('view-templates-btn');
    if (viewTemplatesBtn) {
      this.addEventListener(viewTemplatesBtn, 'click', (e) => {
        e.preventDefault();
        this.showScheduleTemplates();
      });
    }

    // Dropdown toggle handling
    document.querySelectorAll('.dropdown-toggle-split').forEach(toggle => {
      this.addEventListener(toggle, 'click', (e) => {
        e.preventDefault();
        e.stopPropagation();  // Prevent document click from closing immediately
        const btnGroup = toggle.closest('.btn-group');
        const menu = btnGroup?.querySelector('.dropdown-menu');
        if (menu) {
          document.querySelectorAll('.dropdown-menu.show').forEach(m => {
            if (m !== menu) m.classList.remove('show');
          });
          menu.classList.toggle('show');
        }
      });
    });

    // Close dropdowns when clicking outside
    this.addEventListener(document, 'click', (e) => {
      if (!e.target.closest('.btn-group')) {
        document.querySelectorAll('.dropdown-menu.show').forEach(m => m.classList.remove('show'));
      }
    });

    // Also close dropdown when clicking on dropdown items
    document.querySelectorAll('.dropdown-item').forEach(item => {
      this.addEventListener(item, 'click', () => {
        document.querySelectorAll('.dropdown-menu.show').forEach(m => m.classList.remove('show'));
      });
    });

    // Device type change - show/hide automatic option for light only
    const deviceTypeSelect = document.getElementById('schedule-device-type');
    if (deviceTypeSelect) {
      this.addEventListener(deviceTypeSelect, 'change', () => this.updateScheduleTypeOptions());
    }

    // Schedule type change to toggle photoperiod settings
    const scheduleTypeSelect = document.getElementById('schedule-schedule-type');
    if (scheduleTypeSelect) {
      this.addEventListener(scheduleTypeSelect, 'change', () => this.updatePhotoperiodVisibility());
    }

    const photoperiodSourceSelect = document.getElementById('schedule-photoperiod-source');
    if (photoperiodSourceSelect) {
      this.addEventListener(photoperiodSourceSelect, 'change', () => this.updateScheduleTimeRequirements());
    }

    // Schedule modal close button
    const closeScheduleModalBtn = document.getElementById('close-schedule-modal');
    if (closeScheduleModalBtn) {
      this.addEventListener(closeScheduleModalBtn, 'click', () => this.closeScheduleModal());
    }

    // Modal close buttons (generic)
    document.querySelectorAll('[data-action="close-modal"]').forEach(btn => {
      this.addEventListener(btn, 'click', () => {
        const modal = btn.closest('.modal-overlay, .settings-modal');
        if (modal) this.closeModal(modal.id);
      });
    });

    // Other modal close buttons
    document.querySelectorAll('.modal-close').forEach(btn => {
      this.addEventListener(btn, 'click', () => {
        const modal = btn.closest('.modal-overlay, .settings-modal');
        if (modal) this.closeModal(modal.id);
      });
    });

    // Schedule filter buttons
    const scheduleFilters = document.getElementById('schedule-filter');
    if (scheduleFilters) {
      this.addEventListener(scheduleFilters, 'change', () => this.filterSchedules(scheduleFilters.value));
    }

    if (this.elements.hotspotForm) {
      this.addEventListener(this.elements.hotspotForm, 'submit', (e) => this.handleHotspotSubmit(e));
    }

    if (this.elements.esp32Form) {
      this.addEventListener(this.elements.esp32Form, 'submit', (e) => this.handleESP32FormSubmit(e));
    }

    if (this.elements.cameraForm) {
      this.addEventListener(this.elements.cameraForm, 'submit', (e) => this.handleCameraSubmit(e));
    }

    if (this.elements.throttleForm) {
      this.addEventListener(this.elements.throttleForm, 'submit', (e) => this.handleThrottleSubmit(e));
    }

    if (this.elements.throttleResetButton) {
      this.addEventListener(this.elements.throttleResetButton, 'click', () => this.handleThrottleReset());
    }

    if (this.elements.energyForm) {
      this.addEventListener(this.elements.energyForm, 'submit', (e) => this.handleAnalyticsSubmit(e, 'energy'));
    }

    if (this.elements.alertsForm) {
      this.addEventListener(this.elements.alertsForm, 'submit', (e) => this.handleAnalyticsSubmit(e, 'alerts'));
    }

    if (this.elements.dataForm) {
      this.addEventListener(this.elements.dataForm, 'submit', (e) => this.handleAnalyticsSubmit(e, 'data'));
    }

    if (this.elements.addDeviceForm) {
      this.addEventListener(this.elements.addDeviceForm, 'submit', (e) => this.handleAddDeviceSubmit(e));
    }

    // Buttons
    if (this.elements.scanWiFiButton) {
      this.addEventListener(this.elements.scanWiFiButton, 'click', () => this.handleScanWiFi());
    }

    if (this.elements.sendWiFiButton) {
      this.addEventListener(this.elements.sendWiFiButton, 'click', () => this.handleSendWiFiConfig());
    }

    if (this.elements.broadcastWiFiButton) {
      this.addEventListener(this.elements.broadcastWiFiButton, 'click', () => this.handleBroadcastWiFi());
    }

    if (this.elements.deviceScanButton) {
      this.addEventListener(this.elements.deviceScanButton, 'click', () => this.handleScanDevices());
    }

    if (this.elements.deviceList) {
      this.addEventListener(this.elements.deviceList, 'change', () => this.handleLoadDeviceInfo());
    }

    if (this.elements.checkFirmwareButton) {
      this.addEventListener(this.elements.checkFirmwareButton, 'click', () => this.handleCheckFirmware());
    }

    if (this.elements.provisionButton) {
      this.addEventListener(this.elements.provisionButton, 'click', () => this.handleProvisionDevice());
    }

    if (this.elements.zigbeeDiscoverButton) {
      this.addEventListener(this.elements.zigbeeDiscoverButton, 'click', () => this.handleDiscoverZigbee());
    }

    if (this.elements.exportDataButton) {
      this.addEventListener(this.elements.exportDataButton, 'click', () => this.handleExportData());
    }

    // Conditional fields
    if (this.elements.cameraType) {
      this.addEventListener(this.elements.cameraType, 'change', () => this.updateConditionalFields());
    }

    if (this.elements.connectionMode) {
      this.addEventListener(this.elements.connectionMode, 'change', () => this.updateConditionalFields());
    }

    if (this.elements.deviceType) {
      this.addEventListener(this.elements.deviceType, 'change', () => this.updateConditionalFields());
    }

    if (this.elements.commSelect) {
      this.addEventListener(this.elements.commSelect, 'change', () => this.toggleZigbeeFields());
    }

    // Password toggles
    document.querySelectorAll('.toggle-password').forEach(button => {
      this.addEventListener(button, 'click', this.handleTogglePassword.bind(this));
    });

    // Irrigation workflow form
    if (this.elements.irrigationWorkflowForm) {
      this.addEventListener(this.elements.irrigationWorkflowForm, 'submit', (e) => this.handleIrrigationWorkflowSubmit(e));
    }

    // Pump calibration
    if (this.elements.calibrationPumpSelect) {
      this.addEventListener(this.elements.calibrationPumpSelect, 'change', () => this.handlePumpSelect());
    }

    if (this.elements.startCalibrationBtn) {
      this.addEventListener(this.elements.startCalibrationBtn, 'click', () => this.handleStartCalibration());
    }

    if (this.elements.completeCalibrationBtn) {
      this.addEventListener(this.elements.completeCalibrationBtn, 'click', () => this.handleCompleteCalibration());
    }

    if (this.elements.cancelCalibrationBtn) {
      this.addEventListener(this.elements.cancelCalibrationBtn, 'click', () => this.handleCancelCalibration());
    }

    // Security settings event listeners
    this.initSecurityEventListeners();
  }

  handleTogglePassword(event) {
    const targetId = event.currentTarget.dataset.target;
    const input = document.getElementById(targetId);
    const icon = event.currentTarget.querySelector('svg');
    if (!input) return;

    const isPassword = input.type === 'password';
    input.type = isPassword ? 'text' : 'password';

    if (icon) {
      icon.innerHTML = isPassword
        ? `<path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"></path><line x1="1" y1="1" x2="23" y2="23"></line>`
        : `<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle>`;
    }

    const btn = event.currentTarget;
    btn.setAttribute('aria-pressed', (!isPassword).toString());
    btn.setAttribute('aria-label', isPassword ? 'Hide password' : 'Show password');
  }

  // Backward-compatible alias (your code had both)
  async handleUnitChange(unitId) {
    await this.applyUnitSelection(unitId);
  }

  // ============================================================================
  // IRRIGATION WORKFLOW HANDLERS
  // ============================================================================

  async loadIrrigationWorkflow() {
    try {
      const config = await this.dataService.loadIrrigationConfig();
      if (config) {
        this.hydrateIrrigationForm(config);
      }
      // Also load pumps for calibration
      await this.loadPumpActuators();
    } catch (error) {
      console.error('[SettingsUI] Failed to load irrigation config:', error);
    }
  }

  hydrateIrrigationForm(config) {
    const el = this.elements;

    if (el.irrigationUnitId) {
      el.irrigationUnitId.value = this.dataService.selectedUnitId || '';
    }

    if (el.irrigationWorkflowEnabled) {
      el.irrigationWorkflowEnabled.checked = config.workflow_enabled !== false;
    }

    if (el.irrigationRequireApproval) {
      el.irrigationRequireApproval.checked = config.require_approval !== false;
    }

    if (el.irrigationScheduledTime && config.default_scheduled_time) {
      el.irrigationScheduledTime.value = config.default_scheduled_time;
    }

    if (el.irrigationDelayMinutes && config.delay_increment_minutes != null) {
      el.irrigationDelayMinutes.value = config.delay_increment_minutes;
    }

    if (el.irrigationMaxDelay && config.max_delay_hours != null) {
      el.irrigationMaxDelay.value = config.max_delay_hours;
    }

    if (el.irrigationSendReminder) {
      el.irrigationSendReminder.checked = config.send_reminder_before_execution !== false;
    }

    if (el.irrigationReminderMinutes && config.reminder_minutes_before != null) {
      el.irrigationReminderMinutes.value = config.reminder_minutes_before;
    }

    if (el.irrigationRequestFeedback) {
      el.irrigationRequestFeedback.checked = config.request_feedback_enabled !== false;
    }

    if (el.irrigationMlLearning) {
      el.irrigationMlLearning.checked = config.ml_learning_enabled !== false;
    }

    console.log('[SettingsUI] Irrigation form hydrated');
  }

  async handleIrrigationWorkflowSubmit(event) {
    event.preventDefault();

    if (!this.dataService.selectedUnitId) {
      this.displayMessage('Please select a unit first', 'error');
      return;
    }

    const formData = new FormData(this.elements.irrigationWorkflowForm);

    const config = {
      workflow_enabled: this.getCheckboxBool(formData, 'workflow_enabled'),
      require_approval: this.getCheckboxBool(formData, 'require_approval'),
      default_scheduled_time: formData.get('default_scheduled_time') || '21:00',
      delay_increment_minutes: this.getNumber(formData, 'delay_increment_minutes', 60),
      max_delay_hours: this.getNumber(formData, 'max_delay_hours', 24),
      send_reminder_before_execution: this.getCheckboxBool(formData, 'send_reminder_before_execution'),
      reminder_minutes_before: this.getNumber(formData, 'reminder_minutes_before', 30),
      request_feedback_enabled: this.getCheckboxBool(formData, 'request_feedback_enabled'),
      ml_learning_enabled: this.getCheckboxBool(formData, 'ml_learning_enabled'),
    };

    const submitBtn = this.elements.irrigationWorkflowForm.querySelector('button[type="submit"]');
    this.setButtonLoading(submitBtn, true, 'Saving...');

    try {
      await this.dataService.saveIrrigationConfig(config);
      this.displayMessage('Irrigation workflow settings saved', 'success');
    } catch (error) {
      this.displayMessage(`Failed to save: ${this.normalizeError(error)}`, 'error');
    } finally {
      this.setButtonLoading(submitBtn, false);
    }
  }

  // ============================================================================
  // PUMP CALIBRATION HANDLERS
  // ============================================================================

  // State for active calibration session
  calibrationSession = {
    active: false,
    actuatorId: null,
    durationSeconds: null,
  };

  async loadPumpActuators() {
    const select = this.elements.calibrationPumpSelect;
    if (!select) return;

    try {
      const pumps = await this.dataService.loadUnitPumps();

      // Clear existing options except placeholder
      select.innerHTML = '<option value="">Select a pump...</option>';

      if (pumps.length === 0) {
        select.innerHTML += '<option value="" disabled>No pumps found for this unit</option>';
        if (this.elements.startCalibrationBtn) {
          this.elements.startCalibrationBtn.disabled = true;
        }
        return;
      }

      pumps.forEach(pump => {
        const option = document.createElement('option');
        option.value = pump.actuator_id || pump.id;
        option.textContent = pump.name || pump.actuator_name || `Pump ${pump.actuator_id || pump.id}`;
        select.appendChild(option);
      });

      console.log('[SettingsUI] Loaded', pumps.length, 'pump actuators');
    } catch (error) {
      console.error('[SettingsUI] Failed to load pumps:', error);
    }
  }

  async handlePumpSelect() {
    const select = this.elements.calibrationPumpSelect;
    const actuatorId = select?.value ? parseInt(select.value, 10) : null;

    // Reset calibration UI state
    this.resetCalibrationUI();

    if (!actuatorId) {
      this.updateCalibrationStatus(null);
      return;
    }

    // Enable start button
    if (this.elements.startCalibrationBtn) {
      this.elements.startCalibrationBtn.disabled = false;
    }

    // Show instructions
    if (this.elements.calibrationInstructions) {
      this.elements.calibrationInstructions.classList.remove('hidden');
    }

    // Load existing calibration data
    try {
      const calData = await this.dataService.loadPumpCalibration(actuatorId);
      this.updateCalibrationStatus(calData);
      this.updateCalibrationHistory(calData);
    } catch (error) {
      console.error('[SettingsUI] Failed to load pump calibration:', error);
      this.updateCalibrationStatus(null);
    }
  }

  updateCalibrationStatus(calData) {
    const display = this.elements.calibrationStatusDisplay;
    if (!display) return;

    if (!calData || !calData.flow_rate_ml_per_second) {
      display.innerHTML = '<span class="text-muted">Not calibrated</span>';
      return;
    }

    const flowRate = calData.flow_rate_ml_per_second.toFixed(2);
    const confidence = calData.calibration_confidence != null
      ? (calData.calibration_confidence * 100).toFixed(0)
      : 'N/A';
    const lastCal = calData.calibrated_at
      ? new Date(calData.calibrated_at).toLocaleDateString()
      : 'Unknown';

    display.innerHTML = `
      <div class="d-flex flex-column">
        <span><strong>Flow Rate:</strong> ${flowRate} ml/s</span>
        <span><strong>Confidence:</strong> ${confidence}%</span>
        <span class="text-muted small">Last calibrated: ${lastCal}</span>
      </div>
    `;
  }

  updateCalibrationHistory(calData) {
    const historySection = this.elements.calibrationHistory;
    const tbody = this.elements.calibrationHistoryBody;

    if (!historySection || !tbody) return;

    const history = calData?.calibration_history || [];

    if (history.length === 0) {
      historySection.classList.add('hidden');
      return;
    }

    historySection.classList.remove('hidden');
    tbody.innerHTML = '';

    history.slice(0, 5).forEach(entry => {
      const row = document.createElement('tr');
      const date = entry.calibrated_at ? new Date(entry.calibrated_at).toLocaleDateString() : '-';
      const flowRate = entry.flow_rate_ml_per_second?.toFixed(2) || '-';
      const confidence = entry.confidence != null ? (entry.confidence * 100).toFixed(0) + '%' : '-';
      const method = entry.method ? entry.method.replace(/_/g, ' ') : '-';

      row.innerHTML = `
        <td>${date}</td>
        <td>${flowRate} ml/s</td>
        <td>${confidence}</td>
        <td>${method}</td>
      `;
      tbody.appendChild(row);
    });
  }

  async handleStartCalibration() {
    const select = this.elements.calibrationPumpSelect;
    const actuatorId = select?.value ? parseInt(select.value, 10) : null;

    if (!actuatorId) {
      this.displayMessage('Please select a pump first', 'error');
      return;
    }

    const durationSeconds = this.safeNumber(this.elements.calibrationDuration?.value);
    const durationValue = durationSeconds > 0 ? durationSeconds : null;

    this.setButtonLoading(this.elements.startCalibrationBtn, true, 'Starting...');

    try {
      const result = await this.dataService.startPumpCalibration(actuatorId, durationValue);

      // Store session info
      this.calibrationSession = {
        active: true,
        actuatorId,
        durationSeconds: result?.duration_seconds || durationValue,
      };

      if (this.elements.calibrationDuration && result?.duration_seconds) {
        this.elements.calibrationDuration.value = result.duration_seconds;
      }

      // Update UI to show calibration in progress
      this.showCalibrationInProgress();
      this.displayMessage('Calibration started - pump is running', 'success');

    } catch (error) {
      this.displayMessage(`Failed to start calibration: ${this.normalizeError(error)}`, 'error');
    } finally {
      this.setButtonLoading(this.elements.startCalibrationBtn, false);
    }
  }

  showCalibrationInProgress() {
    // Hide start button, show form and complete/cancel buttons
    if (this.elements.startCalibrationBtn) {
      this.elements.startCalibrationBtn.classList.add('hidden');
    }
    if (this.elements.calibrationForm) {
      this.elements.calibrationForm.classList.remove('hidden');
    }
    if (this.elements.completeCalibrationBtn) {
      this.elements.completeCalibrationBtn.classList.remove('hidden');
    }
    if (this.elements.cancelCalibrationBtn) {
      this.elements.cancelCalibrationBtn.classList.remove('hidden');
    }

    // Clear actual ml field for user input
    if (this.elements.calibrationActualMl) {
      this.elements.calibrationActualMl.value = '';
      this.elements.calibrationActualMl.focus();
    }

    // Disable pump selector during calibration
    if (this.elements.calibrationPumpSelect) {
      this.elements.calibrationPumpSelect.disabled = true;
    }
  }

  async handleCompleteCalibration() {
    if (!this.calibrationSession.active) {
      this.displayMessage('No active calibration session', 'error');
      return;
    }

    const measuredMl = parseFloat(this.elements.calibrationActualMl?.value);
    if (!measuredMl || measuredMl <= 0) {
      this.displayMessage('Please enter the measured volume', 'error');
      return;
    }

    this.setButtonLoading(this.elements.completeCalibrationBtn, true, 'Completing...');

    try {
      const result = await this.dataService.completePumpCalibration(
        this.calibrationSession.actuatorId,
        measuredMl
      );

      this.displayMessage(
        result.message || `Calibration complete! Flow rate: ${result.flow_rate_ml_per_second?.toFixed(2) || 'N/A'} ml/s`,
        'success'
      );

      // Reset and refresh
      this.resetCalibrationUI();
      await this.handlePumpSelect(); // Reload calibration data

    } catch (error) {
      this.displayMessage(`Failed to complete calibration: ${this.normalizeError(error)}`, 'error');
    } finally {
      this.setButtonLoading(this.elements.completeCalibrationBtn, false);
    }
  }

  handleCancelCalibration() {
    this.resetCalibrationUI();
    this.displayMessage('Calibration cancelled', 'info');
  }

  resetCalibrationUI() {
    this.calibrationSession = {
      active: false,
      actuatorId: null,
      durationSeconds: null,
    };

    // Reset button visibility
    if (this.elements.startCalibrationBtn) {
      this.elements.startCalibrationBtn.classList.remove('hidden');
    }
    if (this.elements.calibrationForm) {
      this.elements.calibrationForm.classList.add('hidden');
    }
    if (this.elements.completeCalibrationBtn) {
      this.elements.completeCalibrationBtn.classList.add('hidden');
    }
    if (this.elements.cancelCalibrationBtn) {
      this.elements.cancelCalibrationBtn.classList.add('hidden');
    }

    // Re-enable pump selector
    if (this.elements.calibrationPumpSelect) {
      this.elements.calibrationPumpSelect.disabled = false;
    }

    // Clear form fields
    if (this.elements.calibrationActualMl) {
      this.elements.calibrationActualMl.value = '';
    }
    if (this.elements.calibrationDuration) {
      this.elements.calibrationDuration.value = '';
    }
  }

  // ============================================================================
  // SECURITY SETTINGS
  // ============================================================================

  async loadSecuritySettings() {
    try {
      const count = await this.dataService.getRecoveryCodeCount();
      this.updateRecoveryCodeCount(count);
    } catch (error) {
      this.warn('Failed to load security settings:', error);
    }
  }

  updateRecoveryCodeCount(count) {
    const countEl = document.getElementById('recovery-code-count');
    const warningEl = document.getElementById('recovery-codes-warning');

    if (countEl) {
      countEl.textContent = count;
      // Update badge color based on count
      countEl.classList.remove('bg-primary', 'bg-warning', 'bg-danger');
      if (count === 0) {
        countEl.classList.add('bg-danger');
      } else if (count <= 3) {
        countEl.classList.add('bg-warning');
      } else {
        countEl.classList.add('bg-primary');
      }
    }

    if (warningEl) {
      if (count <= 3 && count > 0) {
        warningEl.classList.remove('hidden');
      } else {
        warningEl.classList.add('hidden');
      }
    }
  }

  async handleGenerateRecoveryCodes(event) {
    event.preventDefault();

    const passwordInput = document.getElementById('recovery-current-password');
    const password = passwordInput?.value?.trim();

    if (!password) {
      this.displayMessage('Password is required to generate recovery codes', 'error');
      return;
    }

    const button = document.getElementById('generate-codes-btn');
    this.setButtonLoading(button, true, 'Generating...');

    try {
      const result = await this.dataService.generateRecoveryCodes(password);

      if (result.ok && result.codes) {
        this.displayRecoveryCodes(result.codes);
        this.updateRecoveryCodeCount(result.codes.length);
        this.displayMessage('Recovery codes generated successfully. Save them now!', 'success');
        // Clear password field
        if (passwordInput) passwordInput.value = '';
      } else {
        this.displayMessage(result.error || 'Failed to generate recovery codes', 'error');
      }
    } catch (error) {
      this.displayMessage(`Failed to generate codes: ${this.normalizeError(error)}`, 'error');
    } finally {
      this.setButtonLoading(button, false);
    }
  }

  displayRecoveryCodes(codes) {
    const container = document.getElementById('generated-codes-container');
    const codesList = document.getElementById('generated-codes-list');

    if (!container || !codesList) return;

    // Build the codes grid
    codesList.innerHTML = codes.map((code, index) => `
      <div class="recovery-code-item">
        <span class="code-number">${index + 1}.</span>
        <code class="code-value">${code}</code>
      </div>
    `).join('');

    // Show the container
    container.classList.remove('hidden');

    // Store codes for copy/download
    container.dataset.codes = JSON.stringify(codes);
  }

  handleCopyRecoveryCodes() {
    const container = document.getElementById('generated-codes-container');
    if (!container || !container.dataset.codes) {
      this.displayMessage('No codes to copy', 'error');
      return;
    }

    try {
      const codes = JSON.parse(container.dataset.codes);
      const text = 'SYSGrow Recovery Codes\n' +
        '========================\n\n' +
        codes.map((code, i) => `${i + 1}. ${code}`).join('\n') +
        '\n\nKeep these codes in a safe place. Each code can only be used once.';

      navigator.clipboard.writeText(text).then(() => {
        this.displayMessage('Recovery codes copied to clipboard', 'success');
      }).catch(() => {
        // Fallback for older browsers
        const textarea = document.createElement('textarea');
        textarea.value = text;
        document.body.appendChild(textarea);
        textarea.select();
        document.execCommand('copy');
        document.body.removeChild(textarea);
        this.displayMessage('Recovery codes copied to clipboard', 'success');
      });
    } catch (error) {
      this.displayMessage('Failed to copy codes', 'error');
    }
  }

  handleDownloadRecoveryCodes() {
    const container = document.getElementById('generated-codes-container');
    if (!container || !container.dataset.codes) {
      this.displayMessage('No codes to download', 'error');
      return;
    }

    try {
      const codes = JSON.parse(container.dataset.codes);
      const text = 'SYSGrow Recovery Codes\n' +
        '========================\n' +
        `Generated: ${new Date().toLocaleString()}\n\n` +
        codes.map((code, i) => `${i + 1}. ${code}`).join('\n') +
        '\n\n' +
        'IMPORTANT:\n' +
        '- Keep these codes in a safe place\n' +
        '- Each code can only be used once\n' +
        '- Use these codes to recover your account if you forget your password';

      const blob = new Blob([text], { type: 'text/plain' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `sysgrow-recovery-codes-${new Date().toISOString().split('T')[0]}.txt`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);

      this.displayMessage('Recovery codes downloaded', 'success');
    } catch (error) {
      this.displayMessage('Failed to download codes', 'error');
    }
  }

  initSecurityEventListeners() {
    // Generate recovery codes form
    const generateForm = document.getElementById('generate-recovery-codes-form');
    if (generateForm) {
      this.addEventListener(generateForm, 'submit', (e) => this.handleGenerateRecoveryCodes(e));
    }

    // Copy codes button
    const copyBtn = document.getElementById('copy-codes-btn');
    if (copyBtn) {
      this.addEventListener(copyBtn, 'click', () => this.handleCopyRecoveryCodes());
    }

    // Download codes button
    const downloadBtn = document.getElementById('download-codes-btn');
    if (downloadBtn) {
      this.addEventListener(downloadBtn, 'click', () => this.handleDownloadRecoveryCodes());
    }
  }
}

// Export for module usage
if (typeof window !== 'undefined') {
  window.SettingsUIManager = SettingsUIManager;
}
