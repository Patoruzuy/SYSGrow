/**
 * DashboardUIManager
 * ============================================================================
 * UI layer responsibilities:
 *  - Index DOM elements once for performance
 *  - Render initial dashboard data
 *  - Subscribe to real-time socket updates
 *  - Batch frequent real-time sensor DOM writes via requestAnimationFrame
 *
 * Notes:
 *  - Avoid repeated querySelector calls in hot paths (sensor updates).
 *  - Avoid overlapping periodic refreshes.
 */
(function () {
  'use strict';

  class DashboardUIManager extends BaseManager {
    constructor(dataService) {
      super('DashboardUIManager');

      if (!dataService) throw new Error('dataService is required for DashboardUIManager');

      this.dataService = dataService;
      this.socketManager = window.socketManager;

      // Debug toggle (optional): localStorage.setItem('dashboard:debug','1')
      this.debugEnabled = localStorage.getItem('dashboard:debug') === '1';

      this.unsubscribeFunctions = [];
      this.actuatorLookup = {};

      this.ALL_SENSOR_TYPES = [
        'temperature', 'humidity', 'soil_moisture', 'co2', 'air_quality',
        'ec', 'ph', 'smoke', 'voc', 'pressure', 'lux', 'full_spectrum',
        'infrared', 'visible', 'energy_usage'
      ];
      this.KNOWN_STATUSES = ['normal', 'warning', 'critical', 'low', 'high', 'unknown', 'error', 'offline'];
      this.ARROWS = { up: '↗', down: '↘', neutral: '→' };

      // Internal: sensors DOM index
      this.sensorCardsByType = new Map();

      // Internal: rAF batching for sensor updates
      this._pendingSensorUpdates = new Map(); // type -> payload
      this._sensorFlushScheduled = false;

      // Internal: periodic refresh
      this._destroyed = false;
      this._periodicTimer = null;
      this._periodicInFlight = false;

      // Smooth counters with rAF
      this._counterAnims = new WeakMap();

      // Component instances
      this._vpdGauge = null;
      this._actuatorPanel = null;
      this._plantGrid = null;
      this._plantDetailsModal = null;
      this._alertTimeline = null;
      this._alertSummary = null;

      // Dashboard insight state (fed by `/api/dashboard/summary` + EnvironmentalOverviewChart callback)
      this._insights = {
        activePlant: null,
        latestSensors: {},
        history: null,
        photoperiod: null,
        hours: null,
        start: null,
        end: null,
      };

      // Cache common DOM elements
      this.elements = {
        connectionStatus: document.getElementById('connection-status'),
        lastUpdateTime: document.getElementById('last-update-time'),
        refreshBtn: document.getElementById('refresh-sensors'),

        healthScoreValue: document.getElementById('health-score-value'),
        healthScoreText: document.getElementById('health-score-text'),

        criticalAlertsCount: document.getElementById('critical-alerts-count'),
        activeDevicesCount: document.getElementById('active-devices-count'),
        healthyPlantsCount: document.getElementById('healthy-plants-count'),
        energyUsageToday: document.getElementById('energy-usage-today'),

        recentActivityList: document.getElementById('recent-activity-list'),
        criticalAlertsList: document.getElementById('critical-alerts-list'),
        recentStateList: document.getElementById('recent-state-list'),

        refreshStateBtn: document.getElementById('refresh-state-feed'),
        connectivityList: document.getElementById('connectivity-list'),
        refreshConnectivityBtn: document.getElementById('refresh-connectivity'),
        connectivityTypeFilter: document.getElementById('connectivity-type-filter'),

        // Your template has this pill already:
        connectivityLastStatus: document.getElementById('connectivity-last-status'),

        aiOverallScore: document.getElementById('ai-overall-score'),
        aiHealthStatus: document.getElementById('ai-health-status'),
        aiHealthBanner: document.getElementById('ai-health-banner'),
        aiInsightText: document.getElementById('ai-insight-text'),

        // Insights cards
        insightPhotoperiodValue: document.getElementById('insight-photoperiod-value'),
        insightPhotoperiodMeta: document.getElementById('insight-photoperiod-meta'),
        insightDifValue: document.getElementById('insight-dif-value'),
        insightDifMeta: document.getElementById('insight-dif-meta'),
        insightGddValue: document.getElementById('insight-gdd-value'),
        insightGddMeta: document.getElementById('insight-gdd-meta'),
        insightTargetsValue: document.getElementById('insight-targets-value'),
        insightTargetsMeta: document.getElementById('insight-targets-meta'),
        insightStressValue: document.getElementById('insight-stress-value'),
        insightStressMeta: document.getElementById('insight-stress-meta'),
        insightQualityValue: document.getElementById('insight-quality-value'),
        insightQualityMeta: document.getElementById('insight-quality-meta'),
        insightAlignmentValue: document.getElementById('insight-alignment-value'),
        insightAlignmentMeta: document.getElementById('insight-alignment-meta'),

        // Insights carousel
        insightsCarouselTrack: document.getElementById('insights-carousel-track'),
        insightsCarouselPrev: document.getElementById('insights-carousel-prev'),
        insightsCarouselNext: document.getElementById('insights-carousel-next'),

        // Unit settings
        unitSettingsEmpty: document.getElementById('unit-settings-empty'),
        unitSettingsContent: document.getElementById('unit-settings-content'),
        unitThresholdsList: document.getElementById('unit-thresholds-list'),
        unitSchedulesList: document.getElementById('unit-schedules-list'),
        unitSensorsCount: document.getElementById('unit-sensors-count'),
        unitSensorsList: document.getElementById('unit-sensors-list'),
        unitActuatorsCount: document.getElementById('unit-actuators-count'),
        unitActuatorsList: document.getElementById('unit-actuators-list'),

        // Quick Stats section
        statReadingsCount: document.getElementById('stat-readings-count'),
        statAnomaliesCount: document.getElementById('stat-anomalies-count'),
        statSystemUptime: document.getElementById('stat-system-uptime'),
        statAvgTemp: document.getElementById('stat-avg-temp'),
        statAvgHumidity: document.getElementById('stat-avg-humidity'),
        statDataQuality: document.getElementById('stat-data-quality'),
        statReadingsTrend: document.getElementById('stat-readings-trend'),
        statAnomaliesTrend: document.getElementById('stat-anomalies-trend'),

        // Automation Status section
        automationMainStatus: document.getElementById('automation-main-status'),
        automationSchedulesSummary: document.getElementById('automation-schedules-summary'),
        activeSchedulesList: document.getElementById('active-schedules-list'),
        autoStatLights: document.getElementById('auto-stat-lights'),
        autoStatFans: document.getElementById('auto-stat-fans'),
        autoStatIrrigation: document.getElementById('auto-stat-irrigation'),
        refreshAutomation: document.getElementById('refresh-automation'),

        // Environment Quality section
        envQualityRingProgress: document.getElementById('env-quality-ring-progress'),
        envQualityScore: document.getElementById('env-quality-score'),
        envQualityBadge: document.getElementById('env-quality-badge'),
        qualityTempScore: document.getElementById('quality-temp-score'),
        qualityTempBar: document.getElementById('quality-temp-bar'),
        qualityHumidityScore: document.getElementById('quality-humidity-score'),
        qualityHumidityBar: document.getElementById('quality-humidity-bar'),
        qualityVpdScore: document.getElementById('quality-vpd-score'),
        qualityVpdBar: document.getElementById('quality-vpd-bar'),
        qualityCo2Score: document.getElementById('quality-co2-score'),
        qualityCo2Bar: document.getElementById('quality-co2-bar'),
        envQualitySummary: document.getElementById('env-quality-summary'),

        // Sensor Health section
        sensorsHealthyCount: document.getElementById('sensors-healthy-count'),
        sensorsWarningCount: document.getElementById('sensors-warning-count'),
        sensorsOfflineCount: document.getElementById('sensors-offline-count'),
        sensorHealthMatrix: document.getElementById('sensor-health-matrix'),
        refreshSensorHealth: document.getElementById('refresh-sensor-health'),

        // Recent Journal section
        recentJournalList: document.getElementById('recent-journal-list'),
        refreshJournal: document.getElementById('refresh-journal'),

        // Growth Stage Tracker section
        growthStageBadge: document.getElementById('growth-stage-badge'),
        growthStageProgress: document.getElementById('growth-stage-progress'),
        growthCurrentStage: document.getElementById('growth-current-stage'),
        growthDaysInStage: document.getElementById('growth-days-in-stage'),
        growthDaysTotal: document.getElementById('growth-days-total'),
        growthStageTip: document.getElementById('growth-stage-tip'),

        // Harvest Timeline section
        harvestTimelineItems: document.getElementById('harvest-timeline-items'),
        harvestRecentValue: document.getElementById('harvest-recent-value'),
        refreshHarvestTimeline: document.getElementById('refresh-harvest-timeline'),

        // Water Schedule section
        nextWaterCountdown: document.getElementById('next-water-countdown'),
        nextFeedCountdown: document.getElementById('next-feed-countdown'),
        waterScheduleDays: document.getElementById('water-schedule-days'),
        btnWaterNow: document.getElementById('btn-water-now'),
        btnFeedNow: document.getElementById('btn-feed-now'),
        refreshIrrigation: document.getElementById('refresh-irrigation'),

        // Irrigation Status section
        irrigationLastRun: document.getElementById('irrigation-last-run'),
        irrigationSoilBar: document.getElementById('irrigation-soil-bar'),
        irrigationSoilValue: document.getElementById('irrigation-soil-value'),

        // Irrigation Recommendations section
        irrigationPlantSelect: document.getElementById('irrigation-plant-select'),
        irrigationRecBanner: document.getElementById('irrigation-rec-banner'),
        irrigationRecAction: document.getElementById('irrigation-rec-action'),
        irrigationRecReason: document.getElementById('irrigation-rec-reason'),
        irrigationRecUrgency: document.getElementById('irrigation-rec-urgency'),
        irrPreviewVolume: document.getElementById('irr-preview-volume'),
        irrPreviewDuration: document.getElementById('irr-preview-duration'),
        irrPreviewConfidence: document.getElementById('irr-preview-confidence'),
        irrPreviewReasoning: document.getElementById('irr-preview-reasoning'),
        btnIrrigateNow: document.getElementById('btn-irrigate-now'),
        btnCalibratePump: document.getElementById('btn-calibrate-pump'),
        irrigationTelemetryRefresh: document.getElementById('refresh-irrigation-telemetry'),
        irrigationTelemetryTabs: document.getElementById('irrigation-telemetry-tabs'),
        irrigationTelemetryList: document.getElementById('irrigation-telemetry-list'),
        irrigationTelemetryFootnote: document.getElementById('irrigation-telemetry-footnote'),
      };

      this._telemetryDays = 7;
      this._telemetryTab = 'executions';

      // Insights carousel internal state
      this._insightsCarousel = {
        cards: [],
        index: 0,
        observer: null,
      };
    }

    // Optional: gate BaseManager logging if debugEnabled is off
    log(...args) { if (this.debugEnabled) super.log(...args); }
    debug(...args) { if (this.debugEnabled) super.debug(...args); }

    async init() {
      // Performance: build sensor DOM index once.
      this.indexSensorCards();

      // Initialize reusable components
      this.initComponents();

      // Small UX enhancements (no data required)
      this.initInsightsCarousel();

      this.setupSocketListeners();
      this.buildQuickActionMap();

      await this.loadAndRender();

      this.bindEvents();
      this.initNewSectionHandlers();
      this.startPeriodicUpdates();
    }

    /**
     * Initialize reusable component instances
     */
    initComponents() {
      // VPD Gauge component
      if (window.VPDGauge && document.getElementById('vpd-gauge')) {
        this._vpdGauge = new window.VPDGauge('vpd-gauge', {
          valueElementId: 'vpd-value',
          zoneElementId: 'vpd-zone'
        });
        this._vpdGauge.init();
      }

      // Actuator Panel component
      if (window.ActuatorPanel && document.getElementById('quick-actions')) {
        this._actuatorPanel = new window.ActuatorPanel('quick-actions', {
          onToggle: async (actuatorId, newState) => {
            await this.toggleDevice('relay', Number(actuatorId));
          },
          showEnergy: true
        });
      }

      // Plant Health Grid component
      if (window.PlantHealthGrid && document.getElementById('plants-container')) {
        if (window.PlantDetailsModal && !this._plantDetailsModal) {
          this._plantDetailsModal = new window.PlantDetailsModal();
        }

        this._plantGrid = new window.PlantHealthGrid('plants-container', {
          compact: true,
          onClick: (plantId, plantSummary) => {
            // Navigate to full detail page
            window.location.href = `/plants/${plantId}/my-detail`;
          },
        });
      }

      // Energy Summary component
      if (window.EnergySummary) {
        this._energySummary = new window.EnergySummary({
          powerElementId: 'total-power',
          costElementId: 'daily-cost'
        });
      }

      // Alert Timeline component
      if (window.AlertTimeline && document.getElementById('critical-alerts-list')) {
        this._alertTimeline = new window.AlertTimeline('critical-alerts-list', {
          maxVisible: 5,
          showActions: true,
          onDismiss: async (alertId) => {
            try {
              await this.dataService.dismissAlert(alertId);
              this.showNotification('Alert dismissed', 'success');
            } catch (error) {
              this.showNotification('Failed to dismiss alert', 'error');
            }
          },
          onAction: (alertId, action) => {
            this.handleAlertAction(alertId, action);
          }
        });
      }

      // Alert Summary component
      if (window.AlertSummary) {
        this._alertSummary = new window.AlertSummary({
          countElementId: 'critical-alerts-count',
          statusElementId: 'alert-status'
        });
      }
    }

    /**
     * Index sensor cards for O(1) updates during real-time feeds.
     */
    indexSensorCards() {
      this.sensorCardsByType.clear();

      for (const type of this.ALL_SENSOR_TYPES) {
        const cards = Array.from(document.querySelectorAll(`[data-sensor="${type}"]`));
        this.sensorCardsByType.set(
          type,
          cards.map((card) => ({
            card,
            valueEl: card.querySelector('.sensor-value'),
            statusEl: card.querySelector('.sensor-status'),
            trendEl: card.querySelector('.sensor-trend'),
            trendPill: card.querySelector('.trend-pill'),
            sparklinePoly: card.querySelector('.trend-sparkline polyline'),
            // Template uses: <span class="last-update-value">
            timeValueEl: card.querySelector('.last-update-value'),
          }))
        );
      }
    }

    bindEvents() {
      // Unit switcher -> clear UI + invalidate caches + full reload
      const unitSwitcher = document.getElementById('unit-switcher');
      if (unitSwitcher) {
        // Avoid double-binding if init runs twice for any reason
        if (!unitSwitcher.dataset.bound) {
          unitSwitcher.dataset.bound = '1';
          this.addEventListener(unitSwitcher, 'change', () => this.handleUnitSwitch());
        }
      }      
      // Manual refresh (bypass cache)
      if (this.elements.refreshBtn) {
        this.addEventListener(this.elements.refreshBtn, 'click', (e) => {
          e.preventDefault();
          this.refresh();
        });
      }

      // State feed refresh
      if (this.elements.refreshStateBtn) {
        this.addEventListener(this.elements.refreshStateBtn, 'click', () => this.loadActuatorStates({ force: true }));
      }

      // Connectivity refresh + filter
      if (this.elements.refreshConnectivityBtn) {
        this.addEventListener(this.elements.refreshConnectivityBtn, 'click', () => this.loadConnectivity({ force: true }));
      }
      if (this.elements.connectivityTypeFilter) {
        this.addEventListener(this.elements.connectivityTypeFilter, 'change', () => this.loadConnectivity({ force: true }));
      }

      // Delegated: quick actions device toggle
      this.addDelegatedListener(document, 'click', '[data-device-toggle]', async (e) => {
        const btn = e.target.closest('[data-device-toggle]');
        if (!btn) return;

        const deviceType = btn.dataset.deviceToggle;
        const actuatorId = btn.dataset.actuatorId ? Number(btn.dataset.actuatorId) : null;

        await this.toggleDevice(deviceType, actuatorId);
      });

      // AI details
      const viewAIDetailsBtn = document.getElementById('view-ai-details');
      if (viewAIDetailsBtn) {
        this.addEventListener(viewAIDetailsBtn, 'click', () => {
          window.location.href = '/system-health';
        });
      }
    }

    async handleUnitSwitch() {
        const unitSelect = document.getElementById('unit-switcher');
        if (!unitSelect) return;

        const nextUnitIdRaw = unitSelect.value;
        const nextUnitId = nextUnitIdRaw ? Number(nextUnitIdRaw) : null;

        try {
            this.log(`Switching to unit: ${nextUnitIdRaw || '(all)'}`);

            // Persist unit for socket.js and other pages BEFORE clearing cache
            // This ensures consistency across page reload
            try {
                const raw = unitSelect.value;
                if (raw) localStorage.setItem('selected_unit_id', raw);
                else localStorage.removeItem('selected_unit_id');
            } catch (err) {
                // Non-fatal, but log for debugging
                this.warn('Failed to persist unit selection to localStorage:', err);
            }

            // Clear unit-sensitive cached data so next page load cannot reuse stale values.
            // This is defensive even with unit-scoped keys.
            this.dataService?.invalidateSensorCache?.();
            this.dataService?.invalidateHealthCache?.();
            this.dataService?.invalidateActivityCache?.();

            // Reset UI so user sees an immediate change (prevents "looks stuck" perception).
            this.ALL_SENSOR_TYPES.forEach(t => this.resetSensorCard(t));

            // Submit form (full page reload expected)
            const form = document.getElementById('unit-switcher-form');
            if (form) {
                // Give the browser one frame to paint the cleared UI before navigating
                requestAnimationFrame(() => form.submit());
            } else {
                this.warn('Unit switcher form not found, attempting page reload');
                window.location.reload();
            }
        } catch (error) {
            this.error('Failed to switch unit:', error);
            this.showNotification('Failed to switch unit', 'error');
        }
    }

    // --------------------------------------------------------------------------
    // Socket.IO setup
    // --------------------------------------------------------------------------

    setupSocketListeners() {
      if (!this.socketManager) {
        this.warn('SocketManager not available');
        return;
      }

      this.unsubscribeFunctions.push(
        this.socketManager.on('connection_status', (data) => {
          this.updateConnectionStatus(Boolean(data?.connected));
        })
      );

      this.unsubscribeFunctions.push(
        this.socketManager.on('device_status_update', (data) => this.handleDeviceUpdate(data))
      );

      this.unsubscribeFunctions.push(
        this.socketManager.on('alert_created', (data) => this.handleNewAlert(data))
      );

      this.unsubscribeFunctions.push(
        this.socketManager.on('system_activity', () => this.loadActivityAndAlerts())
      );

      this.unsubscribeFunctions.push(
        this.socketManager.on('health_metric_update', () => this.loadHealthData())
      );

      // NEW: Dashboard snapshot from /dashboard namespace (priority-selected metrics)
      // This is the preferred way to receive dashboard updates
      this.unsubscribeFunctions.push(
        this.socketManager.on('dashboard_snapshot', (data) => {
          this.handleDashboardSnapshot(data);
        })
      );
    }

    /**
     * Handle dashboard_snapshot events from /dashboard namespace.
     * These contain priority-selected metrics for the unit.
     *
     * Payload shape (DashboardSnapshotPayload):
     * {
     *   schema_version: 1,
     *   unit_id: 1,
     *   timestamp: "2026-01-01T12:00:00Z",
     *   metrics: {
     *     temperature: { value: 22.5, unit: "°c", source: {...} },
     *     humidity: { value: 65.0, unit: "%", source: {...} },
     *     ...
     *   }
     * }
     */
    handleDashboardSnapshot(data) {
      try {
        if (!data || typeof data !== 'object') return;

        const unitId = data.unit_id;
        const selectedUnit = this.dataService?.getSelectedUnitId?.();

        // Filter by selected unit
        if (selectedUnit !== null && selectedUnit !== undefined && Number(unitId) !== Number(selectedUnit)) {
          return;
        }

        const metrics = data.metrics || {};
        const timestamp = data.timestamp || new Date().toISOString();

        this.log(`Dashboard snapshot received: unit=${unitId} metrics=${Object.keys(metrics).join(',')}`);

        // Update each metric in the dashboard
        for (const [metricName, metricData] of Object.entries(metrics)) {
          if (!metricData || typeof metricData !== 'object') continue;

          const value = metricData.value;
          const unit = metricData.unit || '';
          const source = metricData.source || {};

          // Queue sensor update for batched DOM write
          // Include backend-provided trend data
          this.queueSensorUpdate(metricName, {
            value: value,
            unit: unit,
            status: source.status || 'success',
            timestamp: timestamp,
            sensorId: source.sensor_id,
            sensorName: source.sensor_name,
            isAnomaly: source.is_anomaly || false,
            trend: metricData.trend || null,
            trend_delta: metricData.trend_delta ?? null,
          });
        }

        // Update last update time
        this.updateLastUpdateTime();
      } catch (err) {
        this.warn('Error handling dashboard_snapshot:', err);
      }
    }

    /**
     * Update the dashboard "Last update" UI element.
     */
    updateLastUpdateTime() {
      try {
        if (this.elements && this.elements.lastUpdateTime) {
          this.elements.lastUpdateTime.textContent = new Date().toLocaleTimeString();
        }
      } catch (err) {
        // Defensive: don't let UI helper throw and break socket handling
        this.warn('Failed to update last update time:', err);
      }
    }

    /**
     * Handle any of the sensor events we may receive.
     * This normalizes payload shapes into your internal {value, unit, status, timestamp} format.
     *
     * Supported payload shapes:
     * 1) sensor_reading:
     *    { unit_id, sensor_id, readings:{temperature:..}, units:{temperature:"°C"}, timestamp }
     *
     * 2) zigbee_sensor_data (client-side emitted/logged):
     *    { unit_id, sensor_id, temperature:.., humidity:.., temperature_unit:"celsius", ... }
     *
     * 3) temperature_update / humidity_update:
     *    { unit_id, sensor_id, temperature:.., timestamp } etc
     */
    handleSensorSocketEvent(eventName, data) {
    try {
        if (!data || typeof data !== 'object') return;

        // Unit filtering (avoid cross-unit noise) - be defensive about dataService state
        const selectedUnit = this.dataService?.getSelectedUnitId?.();
        
        // Only filter if we have a specific unit selected (null/undefined = show all)
        if (selectedUnit !== null && selectedUnit !== undefined) {
          const payloadUnit = data.unit_id !== undefined && data.unit_id !== null ? Number(data.unit_id) : null;
          const payloadUnitId = Number.isFinite(payloadUnit) ? payloadUnit : null;

          // Skip if this is for a different unit
          if (payloadUnitId !== null && payloadUnitId !== selectedUnit) {
            if (this.debugEnabled) {
              this.log(`Filtering socket event ${eventName}: payload unit=${payloadUnitId}, selected=${selectedUnit}`);
            }
            return;
          }
        }

        // Timestamp (best-effort)
        const timestamp = data.timestamp || new Date().toISOString();

        // 1) Preferred: backend "sensor_reading" format
        if (data.readings && typeof data.readings === 'object') {
        const readings = data.readings;
        const units = (data.units && typeof data.units === 'object') ? data.units : {};

        for (const [k, v] of Object.entries(readings)) {
            const type = this.normalizeSensorType(k);
            if (!this.ALL_SENSOR_TYPES.includes(type)) continue;

            const unit = this._coerceUnit(type, units[k] ?? data[`${k}_unit`] ?? '');
            const value = this.toNumberOrValue(v);
            const status = data.status || this.deriveStatusFromValue(type, value) || 'Normal';

            this.queueSensorUpdate(type, { value, unit, status, timestamp });
        }

        // Keep header clock in sync
        if (this.elements.lastUpdateTime) {
            this.elements.lastUpdateTime.textContent = new Date().toLocaleTimeString();
        }

        this.dataService?.invalidateSensorCache?.();
        return;
        }

        // 2) Single-metric update events (temperature_update, humidity_update, etc.)
        const eventMetric = this._metricFromEventName(eventName);
        if (eventMetric && data[eventMetric] !== undefined) {
        const type = this.normalizeSensorType(eventMetric);
        if (this.ALL_SENSOR_TYPES.includes(type)) {
            const unitHint = data[`${eventMetric}_unit`] || '';
            const unit = this._coerceUnit(type, unitHint);
            const value = this.toNumberOrValue(data[eventMetric]);
            const status = data.status || this.deriveStatusFromValue(type, value) || 'Normal';
            this.queueSensorUpdate(type, { value, unit, status, timestamp });
            this.dataService?.invalidateSensorCache?.();
            return;
        }
        }

        // 3) Zigbee-style flat payload: scan keys for known sensors
        for (const [k, v] of Object.entries(data)) {
        const type = this.normalizeSensorType(k);
        if (!this.ALL_SENSOR_TYPES.includes(type)) continue;

        const unitHint = data[`${k}_unit`] || data.temperature_unit || '';
        const unit = this._coerceUnit(type, unitHint);
        const value = this.toNumberOrValue(v);
        const status = data.status || this.deriveStatusFromValue(type, value) || 'Normal';

        this.queueSensorUpdate(type, { value, unit, status, timestamp });
        }

        this.dataService?.invalidateSensorCache?.();
    } catch (error) {
        this.warn('handleSensorSocketEvent failed:', error, { eventName, data });
    }
    }

    /**
     * Convert event name like "temperature_update" into a metric key "temperature".
     */
    _metricFromEventName(eventName) {
    const name = String(eventName || '').toLowerCase();
    if (!name.endsWith('_update')) return null;
    return name.replace('_update', '');
    }

    /**
     * Coerce units into the units your cards expect.
     * Handles Zigbee: "celsius" => "°C"
     */
    _coerceUnit(sensorType, unitValue) {
    const raw = String(unitValue || '').toLowerCase().trim();

    // Prefer server-provided "°C" when available
    if (sensorType === 'temperature') {
        if (raw === 'celsius' || raw === 'c' || raw === '°c') return ' °C';
        return unitValue || ' °C';
    }

    if (sensorType === 'humidity' || sensorType === 'soil_moisture') return unitValue || ' %';
    if (sensorType === 'lux') return unitValue || ' lux';
    if (sensorType === 'co2') return unitValue || ' ppm';
    if (sensorType === 'energy_usage') return unitValue || ' W';

    return unitValue || '';
    }

    // --------------------------------------------------------------------------
    // Data loading
    // --------------------------------------------------------------------------

    async loadAndRender(options = {}) {
      try {
        // Try loading the unified summary endpoint first (faster)
        const summary = await this.loadDashboardSummary(options);

        if (summary && Object.keys(summary).length > 0) {
          // Render all summary data
          this.renderDashboardSummary(summary);
        } else {
          // Fallback to individual API calls
          await this.loadSensorData(options);
        }

        // Load additional panels in parallel
        await Promise.all([
          this.loadActivityAndAlerts(options),
          this.loadActuatorStates(options),
          this.loadConnectivity(options),
          this.loadQuickStats(options),
          this.loadAutomationStatus(options),
          this.loadEnvironmentQuality(options),
          this.loadSensorHealth(options),
          this.loadRecentJournal(options),
          this.loadGrowthStage(options),
          this.loadHarvestTimeline(options),
          this.loadWaterSchedule(options),
          this.loadIrrigationStatus(options),
          this.loadIrrigationRecommendations(options),
          this.loadIrrigationTelemetry(options),
        ]);
      } catch (error) {
        this.error('Failed to load dashboard data:', error);
        this.showNotification('Failed to load dashboard data', 'error');
      }
    }

    /**
     * Load the unified dashboard summary endpoint
     */
    async loadDashboardSummary({ force = false } = {}) {
      try {
        return await this.dataService.loadDashboardSummary({ force });
      } catch (error) {
        this.warn('loadDashboardSummary failed, falling back to individual calls:', error);
        return null;
      }
    }

    /**
     * Render all dashboard data from the unified summary
     */
    renderDashboardSummary(summary) {
      if (!summary) return;

      // 1. Update sensor cards
      if (summary.sensors) {
        this.updateSensorCards(summary.sensors);
      }

      // 2. Update VPD gauge
      if (summary.vpd) {
        this.updateVPDGauge(summary.vpd);
      }

      // 3. Update system health score
      if (summary.system) {
        this.updateSystemHealthKPI(summary.system);
      }

      // 4. Update plant cards
      if (summary.plants) {
        // Cache plants data for irrigation recommendations
        this._cachedPlantsData = Array.isArray(summary.plants) ? summary.plants : [];
        this.updatePlantsGrid(summary.plants);
        // Also update AI Health Banner from plants data
        this.updateAIHealthBanner({ plants: summary.plants });
        // Enhance banner with AI-generated insight text
        this.loadAIInsight();
        // Update irrigation plant selector
        this.updateIrrigationPlantSelector(summary.plants);
      }

      // 5. Update alerts summary
      if (summary.alerts) {
        this.updateAlertsSummary(summary.alerts);
      }

      // 6. Update devices count
      if (summary.devices) {
        this.updateDevicesKPI(summary.devices);
      }

      // 7. Update actuator controls
      if (summary.actuators) {
        this.updateActuatorControls(summary.actuators);
      }

      // 8. Update energy summary
      if (summary.energy) {
        this.updateEnergySummary(summary.energy);
      }

      // 9. Update insights baseline state (active plant + latest sensors)
      this._insights.activePlant = summary.active_plant || null;
      this._insights.latestSensors = summary.sensors || {};
      this.renderInsights();

      // 10. Unit settings snapshot (thresholds, schedules, sensors, actuators)
      this.updateUnitSettingsSummary(summary.unit_settings || null);

      // Update last update time
      if (this.elements.lastUpdateTime) {
        this.elements.lastUpdateTime.textContent = new Date().toLocaleTimeString();
      }
    }

    // --------------------------------------------------------------------------
    // Insights carousel
    // --------------------------------------------------------------------------

    initInsightsCarousel() {
      const track = this.elements.insightsCarouselTrack;
      const prev = this.elements.insightsCarouselPrev;
      const next = this.elements.insightsCarouselNext;

      if (!track || !prev || !next) return;

      const cards = Array.from(track.querySelectorAll('.insight-card'));
      if (!cards.length) return;

      this._insightsCarousel.cards = cards;
      this._insightsCarousel.index = 0;

      const clamp = (value, min, max) => Math.min(max, Math.max(min, value));

      const setNav = () => {
        const idx = this._insightsCarousel.index;
        prev.disabled = idx <= 0;
        next.disabled = idx >= cards.length - 1;
      };

      const scrollToIndex = (idx) => {
        const nextIndex = clamp(idx, 0, cards.length - 1);
        this._insightsCarousel.index = nextIndex;
        setNav();

        const target = cards[nextIndex];
        target?.scrollIntoView?.({ behavior: 'smooth', block: 'nearest', inline: 'start' });
      };

      this.addEventListener(prev, 'click', () => scrollToIndex(this._insightsCarousel.index - 1));
      this.addEventListener(next, 'click', () => scrollToIndex(this._insightsCarousel.index + 1));

      this.addEventListener(track, 'keydown', (e) => {
        if (e.key === 'ArrowLeft') {
          e.preventDefault();
          scrollToIndex(this._insightsCarousel.index - 1);
        }
        if (e.key === 'ArrowRight') {
          e.preventDefault();
          scrollToIndex(this._insightsCarousel.index + 1);
        }
      });

      // Keep nav in sync when users scroll manually.
      if (typeof IntersectionObserver !== 'undefined') {
        try {
          const observer = new IntersectionObserver(
            (entries) => {
              let best = null;
              for (const entry of entries) {
                if (!entry.isIntersecting) continue;
                if (!best || entry.intersectionRatio > best.intersectionRatio) best = entry;
              }
              if (!best) return;

              const idx = cards.indexOf(best.target);
              if (idx >= 0 && idx !== this._insightsCarousel.index) {
                this._insightsCarousel.index = idx;
                setNav();
              }
            },
            { root: track, threshold: [0.6, 0.75] }
          );

          cards.forEach((card) => observer.observe(card));
          this._insightsCarousel.observer = observer;
        } catch (err) {
          this.warn('Failed to initialize insights carousel observer:', err);
        }
      }

      setNav();
    }

    // --------------------------------------------------------------------------
    // Unit settings snapshot
    // --------------------------------------------------------------------------

    updateUnitSettingsSummary(unitSettings) {
      const empty = this.elements.unitSettingsEmpty;
      const content = this.elements.unitSettingsContent;

      if (!content) return;

      if (!unitSettings) {
        if (empty) empty.hidden = false;
        content.hidden = true;
        return;
      }

      if (empty) empty.hidden = true;
      content.hidden = false;

      const formatNumber = (value, decimals = 0) => {
        if (value === null || value === undefined) return '--';
        const n = Number(value);
        if (!Number.isFinite(n)) return '--';
        return decimals ? n.toFixed(decimals) : String(Math.round(n));
      };

      // Thresholds
      const thresholdsEl = this.elements.unitThresholdsList;
      if (thresholdsEl) {
        thresholdsEl.innerHTML = '';

        const t = unitSettings.thresholds || {};
        const rows = [
          ['Temp', `${formatNumber(t.temperature_threshold, 1)}°C`],
          ['Humidity', `${formatNumber(t.humidity_threshold, 1)}%`],
          ['CO₂', `${formatNumber(t.co2_threshold, 0)} ppm`],
          ['VOC', `${formatNumber(t.voc_threshold, 0)} ppb`],
          ['Light', `${formatNumber(t.lux_threshold, 0)} lux`],
          ['Air Quality', `${formatNumber(t.air_quality_threshold || t.aqi_threshold, 0)}`],
        ];

        const fragment = document.createDocumentFragment();
        rows.forEach(([label, value]) => {
          const dt = document.createElement('dt');
          dt.textContent = label;
          const dd = document.createElement('dd');
          dd.textContent = value;
          fragment.appendChild(dt);
          fragment.appendChild(dd);
        });
        thresholdsEl.appendChild(fragment);
      }

      // Schedules
      const schedulesEl = this.elements.unitSchedulesList;
      if (schedulesEl) {
        schedulesEl.innerHTML = '';

        const schedules = unitSettings.device_schedules || unitSettings.schedules || {};
        const entries = schedules && typeof schedules === 'object' ? Object.entries(schedules) : [];
        const items = [];

        entries.forEach(([deviceType, scheduleGroup]) => {
          if (Array.isArray(scheduleGroup)) {
            scheduleGroup.forEach((schedule) => items.push({ deviceType, schedule }));
          } else if (scheduleGroup) {
            items.push({ deviceType, schedule: scheduleGroup });
          }
        });

        if (!items.length) {
          schedulesEl.innerHTML = '<div class="empty-message">No schedules configured</div>';
        } else {
          const fragment = document.createDocumentFragment();
          const typeLabels = {
            simple: 'Time-based',
            interval: 'Interval',
            photoperiod: 'Photoperiod',
            automatic: 'Plant Stage',
          };
          const typeIcons = {
            simple: 'S',
            interval: 'I',
            photoperiod: 'P',
            automatic: 'A',
          };
          const formatTypeLabel = (value) => {
            if (!value) return '';
            return value
              .replace(/_/g, ' ')
              .replace(/\b\w/g, (char) => char.toUpperCase());
          };

          items.forEach(({ deviceType, schedule }) => {
            const start = schedule?.start_time || '--:--';
            const end = schedule?.end_time || '--:--';
            const enabled = schedule?.enabled !== false;
            const rawType = typeof schedule?.schedule_type === 'string' ? schedule.schedule_type : '';
            const normalizedType = rawType.trim().toLowerCase();
            const typeLabel = typeLabels[normalizedType] || formatTypeLabel(normalizedType) || 'Schedule';
            const typeIcon = typeIcons[normalizedType] || 'S';
            const displayName = schedule?.name || deviceType;

            const row = document.createElement('div');
            row.className = `unit-schedule-pill${enabled ? '' : ' unit-schedule-pill--disabled'}`;

            const meta = document.createElement('div');
            meta.className = 'unit-schedule-pill__meta';

            const icon = document.createElement('span');
            icon.className = 'unit-schedule-pill__icon';
            icon.dataset.type = normalizedType || 'schedule';
            icon.textContent = typeIcon;
            icon.classList.add(
              enabled
                ? 'unit-schedule-pill__icon--enabled'
                : 'unit-schedule-pill__icon--disabled'
            );

            const name = document.createElement('span');
            name.className = 'unit-schedule-pill__name';
            name.textContent = String(displayName || deviceType || 'device');

            const type = document.createElement('span');
            type.className = 'unit-schedule-pill__type';
            type.textContent = typeLabel;

            const time = document.createElement('span');
            time.className = 'unit-schedule-pill__time';
            time.textContent = `${start} → ${end}${enabled ? '' : ' (off)'}`;

            meta.appendChild(icon);
            meta.appendChild(name);
            meta.appendChild(type);
            row.appendChild(meta);
            row.appendChild(time);
            fragment.appendChild(row);
          });

          schedulesEl.appendChild(fragment);
        }
      }

      // Sensors & Actuators
      const sensors = Array.isArray(unitSettings.sensors) ? unitSettings.sensors : [];
      const actuators = Array.isArray(unitSettings.actuators) ? unitSettings.actuators : [];

      if (this.elements.unitSensorsCount) {
        this.elements.unitSensorsCount.textContent = `${sensors.length}`;
      }
      if (this.elements.unitActuatorsCount) {
        this.elements.unitActuatorsCount.textContent = `${actuators.length}`;
      }

      const renderDeviceList = (container, items, { nameKey, typeKey, activeKey }) => {
        if (!container) return;
        container.innerHTML = '';

        if (!items.length) {
          container.innerHTML = '<li><span>None</span><span>—</span></li>';
          return;
        }

        const fragment = document.createDocumentFragment();
        items.forEach((item) => {
          const name = item?.[nameKey] || item?.name || 'Device';
          const type = item?.[typeKey] || item?.type || 'unknown';
          const isActive = item?.[activeKey] !== false;

          const li = document.createElement('li');

          const left = document.createElement('span');
          left.textContent = String(name);

          const right = document.createElement('span');
          right.textContent = `${type}${isActive ? '' : ' (inactive)'}`;

          li.appendChild(left);
          li.appendChild(right);
          fragment.appendChild(li);
        });

        container.appendChild(fragment);
      };

      renderDeviceList(this.elements.unitSensorsList, sensors, {
        nameKey: 'name',
        typeKey: 'sensor_type',
        activeKey: 'is_active',
      });

      renderDeviceList(this.elements.unitActuatorsList, actuators, {
        nameKey: 'name',
        typeKey: 'actuator_type',
        activeKey: 'is_active',
      });
    }

    /**
     * EnvironmentalOverviewChart callback (dashboard only).
     */
    updateInsightsFromEnvironmentalPayload(payload) {
      if (!payload || typeof payload !== 'object') return;

      this._insights.history = payload.data || null;
      this._insights.photoperiod = payload.photoperiod || null;
      this._insights.hours = payload.hours || null;
      this._insights.start = payload.start || null;
      this._insights.end = payload.end || null;

      this.renderInsights();
    }

    renderInsights() {
      // If the template doesn't include these, exit quietly.
      if (!this.elements.insightPhotoperiodValue) return;

      const setText = (el, text) => { if (el) el.textContent = text; };
      const setMeta = (el, text) => { if (el) el.textContent = text; };
      const setCardStatus = (cardId, statusToken) => {
        const el = document.getElementById(cardId);
        if (!el) return;
        el.classList.remove('good', 'warning', 'critical');
        if (statusToken) el.classList.add(statusToken);
      };

      const asNumber = (value) => {
        if (typeof value === 'number' && Number.isFinite(value)) return value;
        if (value === null || value === undefined) return null;
        const parsed = Number(value);
        return Number.isFinite(parsed) ? parsed : null;
      };

      const formatSigned = (value, decimals = 1) => {
        const n = asNumber(value);
        if (n === null) return '--';
        const sign = n > 0 ? '+' : '';
        return `${sign}${n.toFixed(decimals)}`;
      };

      const formatHours = (hours) => {
        const n = asNumber(hours);
        if (n === null) return '--';
        return `${n.toFixed(1)}h`;
      };

      const safeStage = (stage) => String(stage || 'Unknown');

      const history = this._insights.history;
      const photoperiod = this._insights.photoperiod;
      const hours = asNumber(this._insights.hours) || 24;

      const timestamps = Array.isArray(history?.timestamps) ? history.timestamps : [];
      const temps = Array.isArray(history?.temperature) ? history.temperature : [];
      const humidities = Array.isArray(history?.humidity) ? history.humidity : [];
      const mask = Array.isArray(history?.is_day) ? history.is_day : [];

      const parsedTimes = timestamps.map((t) => {
        const dt = new Date(t);
        return Number.isNaN(dt.getTime()) ? null : dt;
      });

      const computeMaskHours = (maskValues) => {
        if (!Array.isArray(maskValues) || parsedTimes.length < 2) return { dayHours: null, nightHours: null };

        let daySeconds = 0;
        let nightSeconds = 0;

        for (let i = 0; i < parsedTimes.length - 1; i++) {
          const t0 = parsedTimes[i];
          const t1 = parsedTimes[i + 1];
          if (!t0 || !t1) continue;

          const deltaSeconds = Math.max(0, (t1.getTime() - t0.getTime()) / 1000);
          const v = maskValues[i];
          if (v === 1) daySeconds += deltaSeconds;
          else if (v === 0) nightSeconds += deltaSeconds;
        }

        return { dayHours: daySeconds / 3600, nightHours: nightSeconds / 3600 };
      };

      const computeOutOfRangeHours = (values, minVal, maxVal) => {
        const minN = asNumber(minVal);
        const maxN = asNumber(maxVal);
        if (parsedTimes.length < 2 || (!Number.isFinite(minN) && !Number.isFinite(maxN))) {
          return { below: null, above: null, total: null };
        }

        let belowSeconds = 0;
        let aboveSeconds = 0;

        for (let i = 0; i < parsedTimes.length - 1; i++) {
          const t0 = parsedTimes[i];
          const t1 = parsedTimes[i + 1];
          if (!t0 || !t1) continue;

          const deltaSeconds = Math.max(0, (t1.getTime() - t0.getTime()) / 1000);
          const v0 = asNumber(values[i]);
          const v1 = asNumber(values[i + 1]);
          const v = v0 !== null && v1 !== null ? (v0 + v1) / 2 : v0;
          if (v === null) continue;

          if (Number.isFinite(minN) && v < minN) belowSeconds += deltaSeconds;
          else if (Number.isFinite(maxN) && v > maxN) aboveSeconds += deltaSeconds;
        }

        const below = belowSeconds / 3600;
        const above = aboveSeconds / 3600;
        return { below, above, total: below + above };
      };

      const computeVpdRange = (stageName) => {
        const s = String(stageName || '').toLowerCase();
        if (s.includes('germ') || s.includes('seed') || s.includes('clone')) return { min: 0.4, max: 0.8 };
        if (s.includes('veg')) return { min: 0.8, max: 1.2 };
        if (s.includes('flow') || s.includes('fruit') || s.includes('bloom')) return { min: 1.0, max: 1.5 };
        return { min: 0.8, max: 1.2 };
      };

      const computeVpdStressHours = (stageName) => {
        if (parsedTimes.length < 2) return { below: null, above: null, total: null };

        const range = computeVpdRange(stageName);
        let belowSeconds = 0;
        let aboveSeconds = 0;

        for (let i = 0; i < parsedTimes.length - 1; i++) {
          const t0 = parsedTimes[i];
          const t1 = parsedTimes[i + 1];
          if (!t0 || !t1) continue;

          const deltaSeconds = Math.max(0, (t1.getTime() - t0.getTime()) / 1000);
          const temp = asNumber(temps[i]);
          const rh = asNumber(humidities[i]);
          if (temp === null || rh === null) continue;

          const svp = 0.6108 * Math.exp((17.27 * temp) / (temp + 237.3));
          const vpd = svp * (1 - rh / 100.0);
          if (!Number.isFinite(vpd)) continue;

          if (vpd < range.min) belowSeconds += deltaSeconds;
          else if (vpd > range.max) aboveSeconds += deltaSeconds;
        }

        const below = belowSeconds / 3600;
        const above = aboveSeconds / 3600;
        return { below, above, total: below + above, range };
      };

      const computeGdd = (baseTempC) => {
        const base = asNumber(baseTempC);
        if (base === null || parsedTimes.length < 2) return null;

        let gdd = 0;
        for (let i = 0; i < parsedTimes.length - 1; i++) {
          const t0 = parsedTimes[i];
          const t1 = parsedTimes[i + 1];
          if (!t0 || !t1) continue;

          const deltaDays = Math.max(0, (t1.getTime() - t0.getTime()) / (1000 * 60 * 60 * 24));
          if (deltaDays === 0) continue;

          const v0 = asNumber(temps[i]);
          const v1 = asNumber(temps[i + 1]);
          const avg = v0 !== null && v1 !== null ? (v0 + v1) / 2 : v0;
          if (avg === null) continue;

          gdd += Math.max(avg - base, 0) * deltaDays;
        }

        return gdd;
      };

      const computeDataQuality = () => {
        if (parsedTimes.length < 2) {
          return { status: 'warning', label: 'No data', meta: 'No recent readings' };
        }

        const deltasMin = [];
        for (let i = 0; i < parsedTimes.length - 1; i++) {
          const t0 = parsedTimes[i];
          const t1 = parsedTimes[i + 1];
          if (!t0 || !t1) continue;
          const minutes = (t1.getTime() - t0.getTime()) / 60000;
          if (minutes > 0 && Number.isFinite(minutes)) deltasMin.push(minutes);
        }

        deltasMin.sort((a, b) => a - b);
        const median = deltasMin.length
          ? deltasMin[Math.floor(deltasMin.length / 2)]
          : null;
        const maxGap = deltasMin.length ? deltasMin[deltasMin.length - 1] : null;

        const last = parsedTimes[parsedTimes.length - 1];
        const ageMin = last ? (Date.now() - last.getTime()) / 60000 : null;

        let status = 'good';
        let label = 'Good';
        if (ageMin !== null && ageMin > 30) {
          status = 'warning';
          label = 'Stale';
        } else if (maxGap !== null && maxGap > 60) {
          status = 'warning';
          label = 'Gaps';
        }

        const metaParts = [];
        if (last) metaParts.push(`Last: ${this.formatTimeAgo(last)}`);
        if (median !== null) metaParts.push(`Median: ${median.toFixed(0)}m`);
        if (maxGap !== null) metaParts.push(`Max gap: ${maxGap.toFixed(0)}m`);
        metaParts.push(`Samples: ${parsedTimes.length}`);

        return { status, label, meta: metaParts.join(' • ') };
      };

      // ------------------------------------------------------------------
      // 1) Photoperiod card (day/night + hours)
      // ------------------------------------------------------------------
      const { dayHours, nightHours } = computeMaskHours(mask);
      const lastMask = [...mask].reverse().find((v) => v === 0 || v === 1);
      const nowLabel = lastMask === 1 ? 'Day' : lastMask === 0 ? 'Night' : '--';

      setText(this.elements.insightPhotoperiodValue, nowLabel);
      setMeta(
        this.elements.insightPhotoperiodMeta,
        `Day ${formatHours(dayHours)} • Night ${formatHours(nightHours)} • Window ${hours}h`
      );
      setCardStatus('insight-photoperiod', dayHours !== null ? 'good' : 'warning');

      // ------------------------------------------------------------------
      // 2) DIF card
      // ------------------------------------------------------------------
      const dif = asNumber(photoperiod?.dif_c);
      const dayAvg = asNumber(photoperiod?.day_temperature_avg_c);
      const nightAvg = asNumber(photoperiod?.night_temperature_avg_c);

      setText(this.elements.insightDifValue, dif !== null ? `${formatSigned(dif, 1)}°C` : '--');
      setMeta(
        this.elements.insightDifMeta,
        (dayAvg !== null && nightAvg !== null)
          ? `Day avg ${dayAvg.toFixed(1)}°C • Night avg ${nightAvg.toFixed(1)}°C`
          : `Window ${hours}h`
      );
      setCardStatus('insight-dif', dif !== null ? 'good' : 'warning');

      // ------------------------------------------------------------------
      // 3) GDD card (active plant)
      // ------------------------------------------------------------------
      const activePlant = this._insights.activePlant;
      const baseTemp = asNumber(activePlant?.gdd_base_temp_c);
      const gdd = baseTemp !== null ? computeGdd(baseTemp) : null;
      const baseSource = activePlant?.gdd_base_temp_source ? String(activePlant.gdd_base_temp_source) : 'unknown';

      if (!activePlant) {
        setText(this.elements.insightGddValue, '--');
        setMeta(this.elements.insightGddMeta, 'No active plant');
        setCardStatus('insight-gdd', 'warning');
      } else if (gdd === null) {
        setText(this.elements.insightGddValue, '--');
        setMeta(this.elements.insightGddMeta, `Stage: ${safeStage(activePlant.current_stage)} • Base temp unavailable`);
        setCardStatus('insight-gdd', 'warning');
      } else {
        setText(this.elements.insightGddValue, `${gdd.toFixed(2)} °C·d`);
        setMeta(
          this.elements.insightGddMeta,
          `Base ${baseTemp.toFixed(1)}°C (${baseSource}) • ${safeStage(activePlant.current_stage)}`
        );
        setCardStatus('insight-gdd', 'good');
      }

      // ------------------------------------------------------------------
      // 4) Stage targets card
      // ------------------------------------------------------------------
      const tMin = activePlant?.targets?.temperature_c?.min;
      const tMax = activePlant?.targets?.temperature_c?.max;
      const hMin = activePlant?.targets?.humidity_percent?.min;
      const hMax = activePlant?.targets?.humidity_percent?.max;
      const stagePhotoperiodTarget = asNumber(activePlant?.targets?.photoperiod_hours);

      const tempNow = asNumber(this._insights.latestSensors?.temperature?.value);
      const rhNow = asNumber(this._insights.latestSensors?.humidity?.value);

      const tempInRange = (asNumber(tMin) === null || (tempNow !== null && tempNow >= asNumber(tMin)))
        && (asNumber(tMax) === null || (tempNow !== null && tempNow <= asNumber(tMax)));
      const rhInRange = (asNumber(hMin) === null || (rhNow !== null && rhNow >= asNumber(hMin)))
        && (asNumber(hMax) === null || (rhNow !== null && rhNow <= asNumber(hMax)));

      let targetStatus = 'warning';
      let targetLabel = '--';
      if (activePlant && tempNow !== null && rhNow !== null) {
        targetLabel = tempInRange && rhInRange ? 'On target' : 'Off target';
        targetStatus = tempInRange && rhInRange ? 'good' : 'warning';
      } else if (activePlant) {
        targetLabel = 'Targets set';
        targetStatus = 'warning';
      }

      const targetParts = [];
      if (activePlant) targetParts.push(`${safeStage(activePlant.current_stage)}`);
      if (Number.isFinite(asNumber(tMin)) || Number.isFinite(asNumber(tMax))) {
        targetParts.push(`Temp ${asNumber(tMin) !== null ? asNumber(tMin).toFixed(0) : '--'}–${asNumber(tMax) !== null ? asNumber(tMax).toFixed(0) : '--'}°C`);
      }
      if (Number.isFinite(asNumber(hMin)) || Number.isFinite(asNumber(hMax))) {
        targetParts.push(`RH ${asNumber(hMin) !== null ? asNumber(hMin).toFixed(0) : '--'}–${asNumber(hMax) !== null ? asNumber(hMax).toFixed(0) : '--'}%`);
      }
      if (stagePhotoperiodTarget !== null && dayHours !== null) {
        const diff = dayHours - stagePhotoperiodTarget;
        targetParts.push(`Light ${formatSigned(diff, 1)}h vs target`);
      } else if (stagePhotoperiodTarget !== null) {
        targetParts.push(`Light target ${stagePhotoperiodTarget.toFixed(0)}h`);
      }

      setText(this.elements.insightTargetsValue, targetLabel);
      setMeta(this.elements.insightTargetsMeta, targetParts.length ? targetParts.join(' • ') : 'No active plant');
      setCardStatus('insight-targets', targetStatus);

      // ------------------------------------------------------------------
      // 5) Stress hours card (temp + RH + VPD)
      // ------------------------------------------------------------------
      if (!activePlant) {
        setText(this.elements.insightStressValue, '--');
        setMeta(this.elements.insightStressMeta, 'No active plant');
        setCardStatus('insight-stress', 'warning');
      } else {
        const tempStress = computeOutOfRangeHours(temps, tMin, tMax);
        const rhStress = computeOutOfRangeHours(humidities, hMin, hMax);
        const vpdStress = computeVpdStressHours(activePlant.current_stage);

        const total = (asNumber(tempStress.total) || 0) + (asNumber(rhStress.total) || 0) + (asNumber(vpdStress.total) || 0);

        let stressToken = 'good';
        if (total > 0.5) stressToken = 'warning';
        if (total > 3) stressToken = 'critical';

        setText(this.elements.insightStressValue, `${total.toFixed(1)}h`);

        const stressParts = [];
        if (asNumber(tempStress.total) !== null) stressParts.push(`Temp ${tempStress.total.toFixed(1)}h`);
        if (asNumber(rhStress.total) !== null) stressParts.push(`RH ${rhStress.total.toFixed(1)}h`);
        if (asNumber(vpdStress.total) !== null) stressParts.push(`VPD ${vpdStress.total.toFixed(1)}h`);

        setMeta(this.elements.insightStressMeta, stressParts.length ? stressParts.join(' • ') : `Window ${hours}h`);
        setCardStatus('insight-stress', stressToken);
      }

      // ------------------------------------------------------------------
      // 6) Data quality card
      // ------------------------------------------------------------------
      const quality = computeDataQuality();
      setText(this.elements.insightQualityValue, quality.label);
      setMeta(this.elements.insightQualityMeta, quality.meta);
      setCardStatus('insight-quality', quality.status);

      // ------------------------------------------------------------------
      // 7) Schedule ↔ Lux alignment card
      // ------------------------------------------------------------------
      const schedulePresent = Boolean(photoperiod?.schedule_present);
      const sensorEnabled = Boolean(photoperiod?.sensor_enabled);
      const agreement = asNumber(photoperiod?.agreement_rate);

      if (!schedulePresent) {
        setText(this.elements.insightAlignmentValue, sensorEnabled ? 'Lux only' : 'No schedule');
        setMeta(this.elements.insightAlignmentMeta, sensorEnabled ? 'No light schedule configured' : 'Add a light schedule or lux sensor');
        setCardStatus('insight-alignment', 'warning');
      } else if (!sensorEnabled) {
        setText(this.elements.insightAlignmentValue, 'Schedule only');
        setMeta(this.elements.insightAlignmentMeta, 'No lux sensor readings detected');
        setCardStatus('insight-alignment', 'warning');
      } else if (agreement === null) {
        setText(this.elements.insightAlignmentValue, '--');
        setMeta(this.elements.insightAlignmentMeta, 'Insufficient lux data');
        setCardStatus('insight-alignment', 'warning');
      } else {
        const pct = Math.round(agreement * 100);
        const startOffset = asNumber(photoperiod?.start_offset_minutes);
        const endOffset = asNumber(photoperiod?.end_offset_minutes);

        let token = 'good';
        if (pct < 80) token = 'warning';
        if (pct < 60) token = 'critical';

        setText(this.elements.insightAlignmentValue, `${pct}%`);

        const parts = [];
        parts.push(`Source: ${String(photoperiod?.source || 'schedule')}`);
        if (startOffset !== null) parts.push(`Start ${formatSigned(startOffset, 0)}m`);
        if (endOffset !== null) parts.push(`End ${formatSigned(endOffset, 0)}m`);

        setMeta(this.elements.insightAlignmentMeta, parts.join(' • '));
        setCardStatus('insight-alignment', token);
      }
    }

    /**
     * Update VPD gauge display using the VPDGauge component
     */
    updateVPDGauge(vpd) {
      // Use the VPDGauge component if available
      if (this._vpdGauge) {
        this._vpdGauge.update(vpd);
        return;
      }

      // Fallback to inline update if component not available
      const valueEl = document.getElementById('vpd-value');
      const zoneEl = document.getElementById('vpd-zone');

      if (valueEl) {
        valueEl.textContent = vpd.value !== null ? `${vpd.value} kPa` : '-- kPa';
      }

      if (zoneEl) {
        const zoneLabels = {
          'seedling': 'Seedling Zone',
          'vegetative': 'Vegetative Zone',
          'flowering': 'Flowering Zone',
          'too_low': 'Too Low',
          'too_high': 'Too High',
          'unknown': 'No Data'
        };
        zoneEl.textContent = zoneLabels[vpd.zone] || vpd.zone || 'Unknown';
        zoneEl.className = `vpd-zone ${vpd.status || 'unknown'}`;
      }
    }

    /**
     * Update system health KPI card
     */
    updateSystemHealthKPI(system) {
      if (this.elements.healthScoreValue) {
        this.animateCounter(this.elements.healthScoreValue, system.health_score || 0, 0);
      }
      if (this.elements.healthScoreText) {
        const statusLabels = {
          'healthy': 'Excellent',
          'good': 'Good',
          'fair': 'Fair',
          'poor': 'Needs Attention'
        };
        this.elements.healthScoreText.textContent = statusLabels[system.status] || system.status || 'Unknown';
      }
    }

    /**
     * Update plants grid with mini cards using PlantHealthGrid component
     */
    updatePlantsGrid(plants) {
      // Count healthy plants for KPI
      if (Array.isArray(plants)) {
        const healthyCount = plants.filter(p =>
          p.health_status === 'healthy' || p.health_score >= 70
        ).length;

        if (this.elements.healthyPlantsCount) {
          this.animateCounter(this.elements.healthyPlantsCount, healthyCount, 0);
        }
      }

      // Use the PlantHealthGrid component if available
      if (this._plantGrid) {
        this._plantGrid.update(plants);
        return;
      }

      // Fallback to inline rendering
      const container = document.getElementById('plants-container');
      if (!container) return;

      if (!Array.isArray(plants) || plants.length === 0) {
        container.innerHTML = '<div class="empty-message">No plants in this unit</div>';
        return;
      }

      container.innerHTML = plants.map(plant => this.renderPlantMiniCard(plant)).join('');
    }

    /**
     * Render a mini plant card (fallback)
     */
    renderPlantMiniCard(plant) {
      const rawHealth = String(plant.health_status || plant.current_health_status || '').toLowerCase();
      let healthClass = rawHealth;
      if (!healthClass) {
        const score = Number(plant.health_score ?? plant.health);
        if (Number.isFinite(score)) {
          if (score >= 90) healthClass = 'excellent';
          else if (score >= 70) healthClass = 'good';
          else if (score >= 50) healthClass = 'fair';
          else if (score >= 25) healthClass = 'poor';
          else healthClass = 'critical';
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

      const species = this.escapeHTML((plant.species || plant.plant_type || 'Unknown').toString());
      const stage = this.escapeHTML((plant.current_stage || plant.growth_stage || plant.stage || '').toString());
      const subtitle = stage ? `${species} - ${stage}` : species;
      const name = this.escapeHTML(plant.name || plant.plant_name || 'Plant');
      const imageUrl = this.escapeHTML(
        plant.custom_image || plant.image || plant.image_url || '/static/img/plant-placeholder.svg'
      );
      const lastWatered = this.escapeHTML(plant.last_watered || 'N/A');
      const daysInStage = plant.days_in_stage ? `${plant.days_in_stage} days in stage` : '';
      const plantId = plant.plant_id || plant.id || '';

      return `
        <article class="plant-card-lg" data-plant-id="${plantId}">
          <div class="plant-card__image">
            <img src="${imageUrl}" alt="${name}" loading="lazy" />
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
     * Update alerts summary KPI
     */
    updateAlertsSummary(alerts) {
      const alertCount = alerts.count || 0;
      const criticalCount = alerts.critical || 0;

      if (this.elements.criticalAlertsCount) {
        this.animateCounter(this.elements.criticalAlertsCount, alertCount, 0);
      }

      // Update KPI card styling based on severity
      const alertCard = document.querySelector('.kpi-card--alerts');
      if (alertCard) {
        alertCard.classList.remove('warning', 'critical');
        if (criticalCount > 0) {
          alertCard.classList.add('critical');
        } else if (alertCount > 0) {
          alertCard.classList.add('warning');
        }
      }

      // Show/hide alerts section
      const alertsSection = document.getElementById('alerts-section');
      if (alertsSection) {
        alertsSection.style.display = criticalCount > 0 ? 'block' : 'none';
      }

      // Render critical alerts list
      if (alerts.recent && alerts.recent.length > 0) {
        this.updateCriticalAlerts(alerts.recent);
      }
    }

    /**
     * Update devices KPI
     */
    updateDevicesKPI(devices) {
      if (this.elements.activeDevicesCount) {
        this.animateCounter(this.elements.activeDevicesCount, devices.active || 0, 0);
      }
    }

    /**
     * Update actuator controls panel using ActuatorPanel component
     */
    updateActuatorControls(actuators) {
      // Use the ActuatorPanel component if available
      if (this._actuatorPanel) {
        this._actuatorPanel.update(actuators);
        return;
      }

      // Fallback to inline rendering
      const container = document.getElementById('quick-actions');
      if (!container) return;

      if (!Array.isArray(actuators) || actuators.length === 0) {
        container.innerHTML = '<div class="empty-message">No actuators configured</div>';
        return;
      }

      container.innerHTML = actuators.map(actuator => this.renderActuatorControl(actuator)).join('');

      // Bind toggle events
      container.querySelectorAll('.actuator-control__toggle').forEach(toggle => {
        toggle.addEventListener('click', async (e) => {
          const actuatorId = Number(e.target.dataset.actuatorId);
          const actuatorType = e.target.dataset.actuatorType || 'relay';
          await this.toggleDevice(actuatorType, actuatorId);
        });
      });
    }

    /**
     * Render an actuator control (fallback)
     */
    renderActuatorControl(actuator) {
      const isOn = actuator.state === 'on' || actuator.state === true || actuator.state === 1;
      const toggleClass = isOn ? 'on' : '';
      const powerText = actuator.power_watts ? `${actuator.power_watts} W` : '0 W';
      const typeIcons = {
        light: 'fas fa-lightbulb',
        grow_light: 'fas fa-lightbulb',
        fan: 'fas fa-fan',
        pump: 'fas fa-faucet',
        irrigation: 'fas fa-tint',
        heater: 'fas fa-fire',
        relay: 'fas fa-plug'
      };
      const icon = typeIcons[actuator.type] || 'fas fa-toggle-on';

      return `
        <div class="actuator-control ${isOn ? 'actuator--on' : 'actuator--off'}" data-actuator-id="${actuator.actuator_id}">
          <div class="actuator-control__icon"><i class="${icon}"></i></div>
          <div class="actuator-control__info">
            <span class="actuator-control__name">${this.escapeHTML(actuator.name || 'Actuator')}</span>
            ${isOn && actuator.power_watts ? `<span class="actuator-control__power">${powerText}</span>` : ''}
          </div>
          <div class="actuator-control__toggle-wrapper">
            <button class="actuator-control__toggle ${toggleClass}"
                    data-actuator-id="${actuator.actuator_id}"
                    data-actuator-type="${actuator.type || 'relay'}"
                    aria-label="Toggle ${actuator.name || 'Actuator'}">
              <span class="toggle-track"><span class="toggle-thumb"></span></span>
            </button>
          </div>
        </div>
      `;
    }

    /**
     * Update energy summary footer using EnergySummary component
     */
    updateEnergySummary(energy) {
      // Update the KPI card
      if (this.elements.energyUsageToday) {
        const watts = energy?.current_power_watts ?? 0;
        // Convert to kWh (assuming current power for display)
        const kWh = watts > 0 ? (watts / 1000).toFixed(2) : '0.00';
        this.elements.energyUsageToday.textContent = `${kWh} kWh`;
      }

      // Use the EnergySummary component if available
      if (this._energySummary) {
        this._energySummary.update({
          totalPower: energy?.current_power_watts || 0,
          dailyCost: energy?.daily_cost
        });
        return;
      }

      // Fallback to inline update
      const powerEl = document.getElementById('total-power');
      const costEl = document.getElementById('daily-cost');

      if (powerEl) {
        const watts = energy?.current_power_watts || 0;
        powerEl.textContent = watts > 1000 ? `${(watts / 1000).toFixed(2)} kW` : `${watts} W`;
      }

      if (costEl) {
        const cost = energy?.daily_cost || 0;
        costEl.textContent = `$${cost.toFixed(2)}`;
      }
    }

    async refresh() {
      await this.loadAndRender({ force: true });
      this.showNotification('Dashboard refreshed', 'success');
    }

    async loadSensorData({ force = false } = {}) {
      try {
        const data = await this.dataService.loadSensorData({ force });
        this.updateSensorCards(data);
      } catch (error) {
        this.error('Failed to load sensor data:', error);
      }
    }

    async loadSystemStats({ force = false } = {}) {
      try {
        const stats = await this.dataService.loadSystemStats({ force });
        this.updateSystemStats(stats);
      } catch (error) {
        this.error('Failed to load system stats:', error);
      }
    }

    async loadActivityAndAlerts({ force = false } = {}) {
      try {
        const [activity, alerts] = await Promise.all([
          this.dataService.loadRecentActivity({ force }),
          this.dataService.loadCriticalAlerts({ force }),
        ]);

        this.updateActivityFeed(activity);
        this.updateCriticalAlerts(alerts);
      } catch (error) {
        this.error('Failed to load activity/alerts:', error);
      }
    }

    async loadActuatorStates({ force = false } = {}) {
      try {
        const states = await this.dataService.loadRecentActuatorStates(20, { force });
        this.updateRecentStateFeed(states);
      } catch (error) {
        this.error('Failed to load actuator states:', error);
      }
    }

    async loadHealthData({ force = false } = {}) {
      try {
        const [systemHealth, , plantHealth] = await Promise.all([
          this.dataService.loadSystemHealth({ force }),
          this.dataService.loadDeviceHealth({ force }),
          this.dataService.loadPlantHealth({ force }),
        ]);

        if (systemHealth) {
          this.updateHealthScore(systemHealth);
          this.updateKPIsFromHealth(systemHealth);
          this.updateStaleSensorIndicators(systemHealth);
        }

        if (plantHealth) {
          this.updateAIHealthBanner(plantHealth);
          // Enhance banner with AI-generated insight text
          this.loadAIInsight();
        }
      } catch (error) {
        this.error('Failed to load health data:', error);
      }
    }

    async loadConnectivity({ force = false } = {}) {
      try {
        const type = this.elements.connectivityTypeFilter?.value || '';
        const rows = await this.dataService.loadConnectivityHistory(20, type, { force });

        this.updateConnectivityFeed(rows);
        this.updateConnectivityStatusPill(rows);
      } catch (error) {
        this.error('Failed to load connectivity:', error);
      }
    }

    // --------------------------------------------------------------------------
    // Sensors (initial render)
    // --------------------------------------------------------------------------

    updateSensorCards(sensorData) {
      if (!sensorData || Object.keys(sensorData).length === 0) {
        // No data: reset all cards
        for (const t of this.ALL_SENSOR_TYPES) this.resetSensorCard(t);
        return;
      }

      // Reset missing sensor types
      for (const t of this.ALL_SENSOR_TYPES) {
        if (!sensorData[t]) this.resetSensorCard(t);
      }

      // Update provided sensor types
      for (const [rawType, payload] of Object.entries(sensorData)) {
        const type = this.normalizeSensorType(rawType);
        if (!type || !this.ALL_SENSOR_TYPES.includes(type)) continue;
        this.updateSensorCard(type, payload);
      }
    }

    resetSensorCard(sensorType) {
      const nodes = this.sensorCardsByType.get(sensorType) || [];
      const defaultUnit = this.getSensorDefaultUnit(sensorType);

      for (const n of nodes) {
        if (n.valueEl) n.valueEl.textContent = `--${defaultUnit}`;

        if (n.statusEl) {
          n.statusEl.textContent = 'No data';
          n.statusEl.classList.remove(...this.KNOWN_STATUSES);
        }

        if (n.trendEl) n.trendEl.textContent = '--';

        if (n.trendPill) {
          n.trendPill.classList.remove('up', 'down');
          n.trendPill.classList.add('neutral');
        }

        if (n.sparklinePoly) n.sparklinePoly.setAttribute('points', '0,8 40,8');

        if (n.timeValueEl) n.timeValueEl.textContent = '--:--';

        n.card.classList.remove(...this.KNOWN_STATUSES);
        n.card.classList.add('no-data');
      }
    }

    updateSensorCard(sensorType, data) {
      const nodes = this.sensorCardsByType.get(sensorType) || [];
      const statusToken = this.safeToken(data?.status, 'unknown');

      for (const n of nodes) {
        n.card.classList.remove('no-data');

        // Value
        if (n.valueEl) {
          const unit = data?.unit || '';
          const hasValue = data?.value !== undefined && data?.value !== null;
          const unitSuffix = unit ? (String(unit).startsWith(' ') ? unit : ` ${unit}`) : '';
          n.valueEl.textContent = hasValue ? `${data.value}${unitSuffix}` : '--';
        }

        // Status
        if (n.statusEl) {
          n.statusEl.textContent = data?.status || 'Unknown';
          n.statusEl.classList.remove(...this.KNOWN_STATUSES);
          n.statusEl.classList.add(statusToken);
        }

        // Trend
        this.updateSensorTrendIndexed(n, data);

        // Card class
        n.card.classList.remove(...this.KNOWN_STATUSES);
        n.card.classList.add(statusToken);

        // Timestamp (template uses .last-update-value)
        if (n.timeValueEl) {
          const dt = data?.timestamp ? new Date(data.timestamp) : null;
          n.timeValueEl.textContent =
            dt && !Number.isNaN(dt.getTime()) ? dt.toLocaleTimeString() : '--:--';
        }
      }
    }

    updateSensorTrendIndexed(n, data) {
      if (!n.trendEl || !n.trendPill) return;

      let direction = 'neutral';
      let labelText = '';

      // Backend provides trend direction as string: "rising", "falling", "stable", "unknown"
      // and trend_delta as a number
      const trendStr = data?.trend;
      const delta = typeof data?.trend_delta === 'number' ? data.trend_delta : null;
      const unit = data?.trend_unit || data?.unit || '';

      // Map backend trend strings to UI direction
      if (typeof trendStr === 'string' && trendStr.trim()) {
        const t = trendStr.toLowerCase();
        if (t === 'rising' || t === 'up' || t === 'increasing') {
          direction = 'up';
        } else if (t === 'falling' || t === 'down' || t === 'decreasing') {
          direction = 'down';
        } else {
          // "stable" or "unknown" -> neutral
          direction = 'neutral';
        }
      }

      // Build label text with delta if available
      if (delta !== null && Number.isFinite(delta) && direction !== 'neutral') {
        const sign = delta > 0 ? '+' : '';
        const decimals = Math.abs(delta) < 1 ? 2 : 1;
        const deltaText = `${sign}${delta.toFixed(decimals)}${unit}`;
        labelText = `${this.ARROWS[direction]} ${deltaText}`;
      } else {
        labelText = this.ARROWS[direction];
      }

      // Remove all possible trend classes (both naming conventions)
      n.trendPill.classList.remove('up', 'down', 'neutral', 'positive', 'negative', 'stable');
      // Add both class names for CSS compatibility
      n.trendPill.classList.add(direction);
      if (direction === 'up') n.trendPill.classList.add('positive');
      else if (direction === 'down') n.trendPill.classList.add('negative');
      n.trendEl.textContent = labelText || this.ARROWS[direction];

      // Sparkline
      if (!n.sparklinePoly) return;

      let values = null;
      if (Array.isArray(data?.trend_points) && data.trend_points.length >= 2) {
        values = data.trend_points.filter((v) => Number.isFinite(v));
      } else if (Array.isArray(data?.history) && data.history.length >= 2) {
        values = data.history
          .map((p) => (typeof p?.value === 'number' ? p.value : null))
          .filter((v) => v !== null);
      }

      n.sparklinePoly.setAttribute(
        'points',
        values && values.length >= 2 ? this.computeSparklinePoints(values, 40, 16) : '0,8 40,8'
      );
    }

    computeSparklinePoints(values, width = 40, height = 16) {
      const min = Math.min(...values);
      const max = Math.max(...values);
      const range = max - min || 1;
      const step = width / (values.length - 1);

      return values
        .map((v, i) => {
          const x = i * step;
          const y = height - ((v - min) / range) * height;
          return `${x},${y}`;
        })
        .join(' ');
    }

    // --------------------------------------------------------------------------
    // Real-time sensor update batching (requestAnimationFrame)
    // --------------------------------------------------------------------------

    /**
     * Queue a sensor update and flush on next animation frame.
     * This prevents excessive DOM writes on high-frequency updates.
     * 
     * IMPORTANT: Only queue updates with valid values to prevent blank cards.
     */
    queueSensorUpdate(sensorType, payload) {
      if (!sensorType) return;
      
      // Validate payload has meaningful data before queueing
      if (!payload || typeof payload !== 'object') {
        if (this.debugEnabled) {
          this.warn(`Ignoring invalid sensor update for ${sensorType}:`, payload);
        }
        return;
      }
      
      // Must have a value or status to be meaningful
      const hasValue = payload.value !== undefined && payload.value !== null;
      const hasStatus = payload.status && String(payload.status).trim() !== '';
      
      if (!hasValue && !hasStatus) {
        if (this.debugEnabled) {
          this.warn(`Ignoring empty sensor update for ${sensorType}:`, payload);
        }
        return;
      }

      // If multiple updates arrive before flush, last write wins.
      this._pendingSensorUpdates.set(sensorType, payload);

      if (this._sensorFlushScheduled) return;
      this._sensorFlushScheduled = true;

      requestAnimationFrame(() => {
        this._sensorFlushScheduled = false;

        // Apply pending updates in one batch
        for (const [type, data] of this._pendingSensorUpdates.entries()) {
          this.updateSensorCard(type, data);
        }
        this._pendingSensorUpdates.clear();

        // UI feedback: update header "Last update"
        if (this.elements.lastUpdateTime) {
          this.elements.lastUpdateTime.textContent = new Date().toLocaleTimeString();
        }
      });
    }

    /**
     * Parse incoming socket payload and queue updates.
     * Includes unit filtering to avoid cross-unit noise.
     */
    handleSensorUpdate(data) {
      try {
        // Unit filtering - be defensive about dataService state
        const selectedUnit = this.dataService?.getSelectedUnitId?.();
        
        // Only filter if we have a selected unit (null = show all)
        if (selectedUnit !== null && selectedUnit !== undefined) {
          const payloadUnit = data?.unit_id !== undefined && data?.unit_id !== null ? Number(data.unit_id) : null;
          const payloadUnitId = Number.isFinite(payloadUnit) ? payloadUnit : null;

          // Skip if payload is for a different unit
          if (payloadUnitId !== null && payloadUnitId !== selectedUnit) {
            if (this.debugEnabled) {
              this.log(`Filtering out sensor update: payload unit=${payloadUnitId}, selected unit=${selectedUnit}`);
            }
            return;
          }
        }

        const baseTimestamp = data?.timestamp || new Date().toISOString();
        const trendFields = {
          trend: data?.trend,
          trend_delta: data?.trend_delta,
          trend_points: data?.trend_points,
          history: data?.history,
        };

        const recordMap = new Map();

        const record = (type, rawValue, unitHint) => {
          if (!type || rawValue === undefined || rawValue === null) return;

          const value = this.toNumberOrValue(rawValue);
          const unit = unitHint || this.getSensorDefaultUnit(type);
          const status = data?.status || this.deriveStatusFromValue(type, value) || 'Unknown';

          recordMap.set(type, { value, unit, status, timestamp: baseTimestamp, ...trendFields });
        };

        // Primary type + value
        const rawType = data?.sensor_type || data?.type || data?.sensor;
        const primaryType = this.normalizeSensorType(rawType);

        if (primaryType && this.ALL_SENSOR_TYPES.includes(primaryType)) {
          const primaryValue = data?.value ?? data?.[primaryType] ?? data?.reading ?? null;
          record(primaryType, primaryValue, data?.unit);
        }

        // Multi-sensor payload support: process other keys
        const meta = new Set([
          'unit_id', 'sensor_id', 'sensor_type', 'type', 'sensor', 'timestamp',
          'unit', 'reading', 'trend', 'trend_delta', 'trend_points', 'history'
        ]);

        for (const [k, v] of Object.entries(data || {})) {
          if (meta.has(k)) continue;
          const t = this.normalizeSensorType(k);
          if (this.ALL_SENSOR_TYPES.includes(t)) {
            record(t, v, data?.[`${k}_unit`] || data?.unit);
          }
        }

        // Queue updates
        for (const [type, payload] of recordMap.entries()) {
          this.queueSensorUpdate(type, payload);
        }

        // Cache invalidation (safe)
        this.dataService.invalidateSensorCache();
      } catch (error) {
        this.warn('handleSensorUpdate failed:', error);
      }
    }

    // --------------------------------------------------------------------------
    // KPI counters (smooth, cancellable)
    // --------------------------------------------------------------------------

    animateCounter(el, end, decimals = 0) {
      if (!el) return;

      const prev = this._counterAnims.get(el);
      if (prev) cancelAnimationFrame(prev);

      // Best-effort parse of current numeric display
      const start = Number.parseFloat(String(el.textContent).replace(/[^\d.-]/g, '')) || 0;
      const target = Number(end) || 0;
      const duration = 800;
      const startTime = performance.now();

      const step = (now) => {
        const t = Math.min(1, (now - startTime) / duration);
        const val = start + (target - start) * t;
        el.textContent = val.toFixed(decimals);

        if (t < 1) this._counterAnims.set(el, requestAnimationFrame(step));
      };

      this._counterAnims.set(el, requestAnimationFrame(step));
    }

    updateSystemStats(stats) {
      if (!stats) return;

      const activeDevices = Number(stats.active_devices || stats.activeDevices || stats.devices || 0);
      const healthyPlants = Number(stats.healthy_plants || stats.healthyPlants || stats.total_plants || stats.plants || 0);
      const criticalAlerts = Number(stats.critical_alerts || stats.criticalAlerts || stats.active_alerts || stats.alerts || 0);
      const energyUsage = Number(stats.energy_usage || stats.energyUsage || 0);

      if (this.elements.activeDevicesCount) this.animateCounter(this.elements.activeDevicesCount, activeDevices, 0);
      if (this.elements.healthyPlantsCount) this.animateCounter(this.elements.healthyPlantsCount, healthyPlants, 0);
      if (this.elements.criticalAlertsCount) this.animateCounter(this.elements.criticalAlertsCount, criticalAlerts, 0);
      if (this.elements.energyUsageToday) this.animateCounter(this.elements.energyUsageToday, energyUsage, 1);
    }

    updateHealthScore(health) {
      if (!health) return;

      const score = Number(health?.overall_score || health?.score || 0);
      const status = String(health?.overall_status || health?.status || 'unknown');
      const token = this.safeToken(status, 'unknown');

      if (this.elements.healthScoreValue) this.animateCounter(this.elements.healthScoreValue, score, 0);

      if (this.elements.healthScoreText) {
        this.elements.healthScoreText.textContent = status;
        this.elements.healthScoreText.className = `health-status health-status--${token}`;
      }
    }

    // --------------------------------------------------------------------------
    // Health KPI status + AI banner (kept from your logic, with safety)
    // --------------------------------------------------------------------------

    updateKPIsFromHealth(healthData) {
      if (!healthData?.kpis) return;

      const kpis = healthData.kpis;
      if (kpis.devices) this.updateKPICardStatus('active-devices', kpis.devices);
      if (kpis.plants) this.updateKPICardStatus('healthy-plants', kpis.plants);
      if (kpis.alerts) this.updateKPICardStatus('critical-alerts', kpis.alerts);
      if (kpis.energy) this.updateKPICardStatus('energy-usage', kpis.energy);
    }

    updateKPICardStatus(cardId, summary) {
      const card = document.querySelector(`[data-kpi="${cardId}"]`);
      if (!card) return;

      const status = this.safeToken(summary?.status, 'normal');
      card.classList.remove(...this.KNOWN_STATUSES);
      card.classList.add(status);

      const indicator = card.querySelector('.kpi-status-indicator');
      if (indicator) indicator.textContent = String(summary?.status_text || '');
    }

    updateStaleSensorIndicators(healthData) {
      if (!healthData?.stale_sensors) return;

      for (const sensor of healthData.stale_sensors) {
        const type = this.normalizeSensorType(sensor?.type);
        const id = sensor?.id;

        const card = document.querySelector(`[data-sensor="${type}"][data-sensor-id="${id}"]`);
        if (!card) continue;

        card.classList.add('stale');

        const indicator = card.querySelector('.stale-indicator');
        if (indicator) {
          const lastSeen = sensor?.last_seen ? new Date(sensor.last_seen) : null;
          indicator.textContent = lastSeen ? `Last seen: ${this.formatTimeAgo(lastSeen)}` : 'Last seen: --';
        }
      }
    }

    updateAIHealthBanner(plantHealth) {
      // Handle both wrapped {data: {plants: []}} and direct {plants: []} formats
      const plants = plantHealth?.data?.plants || plantHealth?.plants || [];
      if (!Array.isArray(plants)) {
        // No plants data - show default state
        if (this.elements.aiOverallScore) this.elements.aiOverallScore.textContent = '--';
        if (this.elements.aiHealthStatus) this.elements.aiHealthStatus.textContent = 'No plant data available';
        if (this.elements.aiInsightText) this.elements.aiInsightText.textContent = 'Add plants to start monitoring their health with AI analysis.';
        return;
      }

      const total = plants.length;
      if (total === 0) {
        if (this.elements.aiOverallScore) this.elements.aiOverallScore.textContent = '--';
        if (this.elements.aiHealthStatus) this.elements.aiHealthStatus.textContent = 'No plants in system';
        if (this.elements.aiInsightText) this.elements.aiInsightText.textContent = 'Add plants to start monitoring their health with AI analysis.';
        return;
      }

      const counts = { healthy: 0, stressed: 0, diseased: 0 };

      for (const plant of plants) {
        const status = String(plant?.current_health_status || plant?.health_status || 'healthy').toLowerCase();
        if (status === 'stressed' || status === 'warning') counts.stressed++;
        else if (status === 'diseased' || status === 'critical') counts.diseased++;
        else counts.healthy++;
      }

      const score = total > 0
        ? Math.round(((counts.healthy * 100) + (counts.stressed * 50)) / total)
        : 0;

      let statusMessage = '';
      let bannerClass = '';

      if (counts.diseased > 0) {
        statusMessage = `${counts.diseased} plant${counts.diseased > 1 ? 's' : ''} diseased`;
        if (counts.stressed > 0) statusMessage += `, ${counts.stressed} stressed`;
        bannerClass = 'critical';
      } else if (counts.stressed > 0) {
        statusMessage = `${counts.stressed} plant${counts.stressed > 1 ? 's' : ''} stressed`;
        bannerClass = 'warning';
      } else {
        statusMessage = `All ${total} plants healthy`;
        bannerClass = 'normal';
      }

      if (this.elements.aiOverallScore) this.animateCounter(this.elements.aiOverallScore, score, 0);
      if (this.elements.aiHealthStatus) this.elements.aiHealthStatus.textContent = statusMessage;

      if (this.elements.aiHealthBanner) {
        this.elements.aiHealthBanner.classList.remove('critical', 'warning', 'normal');
        this.elements.aiHealthBanner.classList.add(bannerClass);
      }

      // Update the inline insight text based on conditions
      if (this.elements.aiInsightText) {
        let insightText = '';
        if (counts.diseased > 0) {
          insightText = 'Immediate attention needed. Check affected plants for disease symptoms and treatment options.';
        } else if (counts.stressed > 0) {
          insightText = 'Some plants showing stress. Review environmental conditions and adjust as needed.';
        } else if (total > 0) {
          insightText = 'All systems optimal. Continue current care routine for best results.';
        } else {
          insightText = 'Add plants to start monitoring their health with AI analysis.';
        }
        this.elements.aiInsightText.textContent = insightText;
      }
    }

    // Load AI insight from API as a fallback/enhancement
    async loadAIInsight() {
      try {
        const unitId = this.dataService.getSelectedUnitId();
        if (!unitId) return;
        
        const result = await window.API?.AI?.getInsights?.(unitId, 1);
        const insight = result?.insights?.[0];
        
        if (insight && this.elements.aiInsightText) {
          this.elements.aiInsightText.textContent = insight.message || insight.title || insight.text || this.elements.aiInsightText.textContent;
        }
      } catch (e) {
        // Keep default text on error
        this.debug('AI insight load failed:', e);
      }
    }

    // --------------------------------------------------------------------------
    // Activity + alerts + state + connectivity feeds (safe, predictable)
    // --------------------------------------------------------------------------

    updateActivityFeed(items) {
      const el = this.elements.recentActivityList;
      if (!el) return;

      if (!Array.isArray(items) || items.length === 0) {
        el.innerHTML = '<div class="empty-message">No recent activity</div>';
        return;
      }

      el.innerHTML = items.map((a) => this.renderActivity(a)).join('');
    }

    renderActivity(a) {
      const typeToken = this.safeToken(a?.type, 'system');
      const icon = this.getActivityIcon(typeToken);

      const dt = a?.timestamp ? new Date(a.timestamp) : null;
      const time = dt && !Number.isNaN(dt.getTime()) ? this.formatTimeAgo(dt) : '--';

      const messageText = a?.message
        || a?.description
        || a?.detail
        || a?.title
        || a?.event
        || a?.activity
        || `Activity (${typeToken})`;

      const metaParts = [
        a?.device_name || a?.device,
        a?.sensor_name || a?.sensor,
        a?.unit_name || a?.unit,
      ].filter(Boolean);

      const valuePart = a?.value !== undefined && a?.value !== null
        ? `${a.value}${a.unit ? ` ${a.unit}` : ''}`
        : null;

      if (valuePart) metaParts.push(valuePart);

      const meta = metaParts.length ? `<div class="activity-meta">${this.escapeHTML(metaParts.join(' • '))}</div>` : '';
      const message = this.escapeHTML(messageText);

      return `
        <div class="activity-item activity-item--${typeToken}">
          <span class="activity-icon">${icon}</span>
          <div class="activity-content">
            <p class="activity-message">${message}</p>
            ${meta}
            <span class="activity-time">${time}</span>
          </div>
        </div>
      `;
    }

    updateCriticalAlerts(items) {
      // Use AlertTimeline component if available
      if (this._alertTimeline) {
        this._alertTimeline.update(items);

        // Update summary badge
        if (this._alertSummary) {
          this._alertSummary.update(this._alertTimeline.getSummary());
        }
        return;
      }

      // Fallback to inline rendering
      const el = this.elements.criticalAlertsList;
      if (!el) return;

      if (!Array.isArray(items) || items.length === 0) {
        el.innerHTML = '<div class="empty-message">No critical alerts</div>';
        return;
      }

      el.innerHTML = items.map((a) => this.renderAlert(a)).join('');
    }

    /**
     * Handle alert action button clicks
     */
    handleAlertAction(alertId, action) {
      switch (action) {
        case 'view':
        case 'details':
          // Navigate to alert details or sensor analytics
          window.location.href = `/sensor-analytics?alert=${alertId}`;
          break;
        case 'adjust':
          // Open threshold settings
          window.location.href = '/settings#thresholds';
          break;
        case 'calibrate':
          this.showNotification('Opening calibration wizard...', 'info');
          // TODO: Open calibration modal
          break;
        case 'restart':
          this.showNotification('Restarting device...', 'info');
          // TODO: Trigger device restart
          break;
        default:
          this.log('Unknown alert action:', action);
      }
    }

    renderAlert(a) {
      const sevToken = this.safeToken(a?.severity, 'warning');
      const icon = this.getAlertIcon(sevToken);

      const dt = a?.timestamp ? new Date(a.timestamp) : null;
      const time = dt && !Number.isNaN(dt.getTime()) ? this.formatTimeAgo(dt) : '--';

      const message = this.escapeHTML(a?.message || '');

      return `
        <div class="alert-item alert-item--${sevToken}">
          <span class="alert-icon">${icon}</span>
          <div class="alert-content">
            <p class="alert-message">${message}</p>
            <span class="alert-time">${time}</span>
          </div>
        </div>
      `;
    }

    updateRecentStateFeed(items) {
      const el = this.elements.recentStateList;
      if (!el) return;

      if (!Array.isArray(items) || items.length === 0) {
        el.innerHTML = '<div class="empty-message">No recent state changes</div>';
        return;
      }

      el.innerHTML = items.map((s) => {
        const dt = s?.timestamp ? new Date(s.timestamp) : null;
        const time = dt && !Number.isNaN(dt.getTime()) ? this.formatTimeAgo(dt) : '--';

        const name = this.escapeHTML(s?.actuator_name || s?.name || 'Actuator');
        const newStateRaw = s?.new_state || s?.state || s?.value || 'unknown';
        const newState = this.escapeHTML(newStateRaw);
        const stateToken = this.safeToken(newStateRaw, 'unknown');
        const stateClass = stateToken === 'on' ? 'on' : (stateToken === 'off' ? 'off' : 'error');

        return `
          <div class="state-item ${stateClass}">
            <span class="state-item__icon"><i class="fas fa-toggle-${stateClass === 'on' ? 'on' : 'off'}"></i></span>
            <div class="state-item__content">
              <div class="state-item__device">${name}</div>
              <div class="state-item__change">State: <strong>${newState}</strong></div>
              <div class="state-item__time">${time}</div>
            </div>
          </div>
        `;
      }).join('');
    }

    updateConnectivityFeed(rows) {
      const el = this.elements.connectivityList;
      if (!el) return;

      if (!Array.isArray(rows) || rows.length === 0) {
        el.innerHTML = '<div class="empty-message">No connectivity events</div>';
        return;
      }

      el.innerHTML = rows.map((e) => {
        const dt = e?.timestamp ? new Date(e.timestamp) : null;
        const time = dt && !Number.isNaN(dt.getTime()) ? this.formatTimeAgo(dt) : '--';

        const typeLabelRaw = e?.type || e?.connection_type || 'connection';
        const typeLabel = this.escapeHTML(typeLabelRaw);
        const statusValue = String(e?.status || 'unknown').toLowerCase();
        const statusText = this.escapeHTML(e?.status || 'unknown');
        const statusClass = statusValue === 'connected' || statusValue === 'online'
          ? 'online'
          : (statusValue === 'disconnected' || statusValue === 'offline' ? 'offline' : 'warning');
        const name = this.escapeHTML(e?.device_name || e?.endpoint || e?.device_id || typeLabelRaw);
        const meta = this.escapeHTML([typeLabelRaw, time].filter(Boolean).join(' - '));
        const signal = this.escapeHTML(
          e?.endpoint
            ? `${e.endpoint}${e.port ? `:${e.port}` : ''}`
            : ''
        );
        const pillClass = statusClass === 'online' ? 'pill--ok' : (statusClass === 'offline' ? 'pill--bad' : '');
        const icon = statusClass === 'online'
          ? '<i class="fas fa-wifi"></i>'
          : (statusClass === 'offline' ? '<i class="fas fa-wifi"></i>' : '<i class="fas fa-wifi"></i>');

        return `
          <div class="connectivity-item ${statusClass}">
            <div class="connectivity-item__info">
              <span class="connectivity-item__icon">${icon}</span>
              <div>
                <div class="connectivity-item__name">${name}</div>
                <div class="connectivity-item__type">${meta}</div>
              </div>
            </div>
            <div class="connectivity-item__status">
              ${signal ? `<span class="connectivity-item__signal">${signal}</span>` : ''}
              <span class="pill ${pillClass}">${statusText}</span>
            </div>
          </div>
        `;
      }).join('');
    }

    updateConnectivityStatusPill(rows) {
      const pill = this.elements.connectivityLastStatus;
      if (!pill || !Array.isArray(rows) || rows.length === 0) return;

      const status = String(rows[0]?.status || '').toLowerCase();
      const healthy = status === 'connected' || status === 'online';

      pill.textContent = healthy ? 'Connected' : 'Disconnected';
      pill.classList.remove('pill--ok', 'pill--bad');
      pill.classList.add(healthy ? 'pill--ok' : 'pill--bad');
    }

    // --------------------------------------------------------------------------
    // Device actions / quick actions mapping
    // --------------------------------------------------------------------------

    async toggleDevice(deviceType, actuatorId = null) {
      const resolvedId = actuatorId || this.actuatorLookup[deviceType];
      if (!resolvedId) {
        this.showNotification(`No actuator configured for ${deviceType}`, 'warning');
        return;
      }

      try {
        const result = await this.dataService.toggleDevice(deviceType, resolvedId);
        const newState = result?.new_state || result?.state || 'toggled';

        this.showNotification(`Device ${deviceType} -> ${newState}`, 'success');

        // Force refresh stats (likely changed)
        await this.loadSystemStats({ force: true });
        await this.loadActuatorStates({ force: true });
      } catch (error) {
        const msg = error?.message || 'Failed to toggle device';
        this.error('toggleDevice failed:', error);
        this.showNotification(msg, 'error');
      }
    }

    buildQuickActionMap() {
      const container = document.getElementById('quick-actions');
      if (!container || !container.dataset.actuators) return;

      try {
        const actuators = JSON.parse(container.dataset.actuators);
        this.actuatorLookup = this.mapActuatorsToQuickActions(actuators);
        this.debug('Quick action actuator map:', this.actuatorLookup);
      } catch (error) {
        this.warn('Failed to parse actuators dataset:', error);
      }
    }

    mapActuatorsToQuickActions(actuators = []) {
      const lookup = {};
      const targets = {
        lights: ['light', 'grow_light', 'lamp'],
        fans: ['fan', 'vent'],
        irrigation: ['irrigation', 'pump', 'water'],
        heater: ['heater', 'heat'],
      };

      const norm = (text) => String(text || '').toLowerCase().replace(/[^a-z0-9]+/g, ' ');

      for (const actuator of actuators) {
        const fields = [
          actuator.actuator_type,
          actuator.type,
          actuator.device,
          actuator.name,
          actuator.label,
        ].map(norm).join(' ');

        for (const [key, keywords] of Object.entries(targets)) {
          if (lookup[key]) continue;
          if (keywords.some((k) => fields.includes(k))) {
            const id = actuator.actuator_id || actuator.id || actuator.actuatorId;
            if (id !== undefined && id !== null) lookup[key] = Number(id);
          }
        }
      }

      return lookup;
    }

    // --------------------------------------------------------------------------
    // Real-time non-sensor handlers
    // --------------------------------------------------------------------------

    handleDeviceUpdate(data) {
      const name = String(data?.device_name || 'Device');
      const status = String(data?.status || 'updated');
      this.showNotification(`${name} is now ${status}`, 'info');

      // Best-effort refresh relevant views
      this.loadHealthData();
      this.loadSystemStats();
    }

    handleNewAlert(data) {
      this.showNotification(String(data?.message || 'New alert'), this.safeToken(data?.severity, 'warning'));
      this.dataService.invalidateActivityCache();
      this.loadActivityAndAlerts({ force: true });
      this.loadSystemStats({ force: true });
    }

    // --------------------------------------------------------------------------
    // Connection status
    // --------------------------------------------------------------------------

    updateConnectionStatus(connected) {
      if (!this.elements.connectionStatus) return;

      // Update class on the container
      this.elements.connectionStatus.classList.toggle('connected', connected);
      this.elements.connectionStatus.classList.toggle('disconnected', !connected);

      // Update just the status text span, not the whole container
      const statusText = this.elements.connectionStatus.querySelector('.status-text');
      if (statusText) {
        statusText.textContent = connected ? 'Connected' : 'Disconnected';
      } else {
        // Fallback if no .status-text span exists
        this.elements.connectionStatus.textContent = connected ? 'Connected' : 'Disconnected';
      }

      if (this.elements.lastUpdateTime) {
        this.elements.lastUpdateTime.textContent = new Date().toLocaleTimeString();
      }
    }

    // --------------------------------------------------------------------------
    // Periodic updates (non-overlapping, pauses when tab is hidden)
    // --------------------------------------------------------------------------

    startPeriodicUpdates() {
      this.stopPeriodicUpdates();

      const tick = async () => {
        if (this._destroyed) return;

        // If tab hidden, reduce work
        if (document.hidden) {
          this._periodicTimer = setTimeout(tick, 60000);
          return;
        }

        // Prevent overlapping periodic calls
        if (this._periodicInFlight) {
          this._periodicTimer = setTimeout(tick, 60000);
          return;
        }

        this._periodicInFlight = true;
        try {
          await Promise.all([
            this.loadSystemStats(),
            this.loadHealthData(),
          ]);
        } catch (error) {
          this.warn('Periodic refresh failed:', error);
        } finally {
          this._periodicInFlight = false;
          this._periodicTimer = setTimeout(tick, 60000);
        }
      };

      tick();
    }

    stopPeriodicUpdates() {
      if (this._periodicTimer) clearTimeout(this._periodicTimer);
      this._periodicTimer = null;
      this._periodicInFlight = false;
    }

    // --------------------------------------------------------------------------
    // Helpers
    // --------------------------------------------------------------------------

    safeToken(input, fallback = 'unknown') {
      const t = String(input ?? '').toLowerCase().trim();
      return t ? t.replace(/[^a-z0-9_-]+/g, '-') : fallback;
    }

    escapeHTML(str) {
      const div = document.createElement('div');
      div.textContent = String(str ?? '');
      return div.innerHTML;
    }

    formatTimeAgo(date) {
      const now = new Date();
      const diff = Math.floor((now - date) / 1000);

      if (diff < 60) return 'Just now';
      if (diff < 3600) return `${Math.floor(diff / 60)} minutes ago`;
      if (diff < 86400) return `${Math.floor(diff / 3600)} hours ago`;
      return `${Math.floor(diff / 86400)} days ago`;
    }

    getActivityIcon(type) {
      const icons = {
        sensor: '<i class="fas fa-thermometer-half"></i>',
        'sensor-update': '<i class="fas fa-thermometer-half"></i>',
        'sensor_update': '<i class="fas fa-thermometer-half"></i>',
        device: '<i class="fas fa-microchip"></i>',
        'device-change': '<i class="fas fa-plug"></i>',
        'device_change': '<i class="fas fa-plug"></i>',
        alert: '<i class="fas fa-exclamation-triangle"></i>',
        warning: '<i class="fas fa-exclamation-triangle"></i>',
        error: '<i class="fas fa-exclamation-circle"></i>',
        system: '<i class="fas fa-cog"></i>',
        state: '<i class="fas fa-sitemap"></i>',
        user: '<i class="fas fa-user"></i>',
      };
      return icons[type] || '<i class="fas fa-info-circle"></i>';
    }

    getAlertIcon(severity) {
      const icons = {
        critical: '<i class="fas fa-exclamation-circle"></i>',
        warning: '<i class="fas fa-exclamation-triangle"></i>',
        info: '<i class="fas fa-info-circle"></i>',
      };
      return icons[severity] || '<i class="fas fa-info-circle"></i>';
    }

    normalizeSensorType(sensorType) {
      if (!sensorType) return '';
      const normalized = String(sensorType).toLowerCase();
    const aliases = {
        // common
        co2: 'co2',
        light: 'lux',
        soil: 'soil_moisture',
        moisture: 'soil_moisture',
        energy: 'energy_usage',
        power: 'energy_usage',

        // zigbee / mqtt naming
        illuminance: 'lux',
        illuminance_lux: 'lux',
        lux: 'lux',

        // sometimes used
        temp: 'temperature',
        hum: 'humidity',
    };

    return aliases[normalized] || normalized;
    }

    getSensorDefaultUnit(sensorType) {
      const units = {
        temperature: '°C',
        humidity: '%',
        soil_moisture: '%',
        lux: ' lux',
        co2: ' ppm',
        energy_usage: ' W',
      };
      return units[sensorType] || '';
    }

    toNumberOrValue(value) {
      if (value === null || value === undefined) return null;
      const numeric = Number(value);
      return Number.isFinite(numeric) ? numeric : value;
    }

    deriveStatusFromValue(sensorType, value) {
      const numeric = Number(value);
      if (!Number.isFinite(numeric)) return null;

      const thresholds = {
        temperature: { min: 18, max: 28 },
        humidity: { min: 40, max: 80 },
        soil_moisture: { min: 30, max: 70 },
        lux: { min: 200, max: 1500 },
        co2: { min: 300, max: 800 },
        energy_usage: { min: 0, max: 5 },
      };

      const range = thresholds[sensorType];
      if (!range) return null;
      if (numeric < range.min) return 'Low';
      if (numeric > range.max) return 'High';
      return 'Normal';
    }

    /**
     * Notification: create DOM nodes (avoid innerHTML injection).
     */
    showNotification(message, type = 'info') {
      try {
        const token = this.safeToken(type, 'info');

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
        closeBtn.setAttribute('aria-label', 'Close notification');
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
        // If notifications fail, do not break the dashboard.
        this.warn('showNotification failed:', error);
      }
    }

    // --------------------------------------------------------------------------
    // Quick Stats Section
    // --------------------------------------------------------------------------

    async loadQuickStats({ force = false } = {}) {
      try {
        const stats = await this.dataService.loadQuickStats({ force });
        this.updateQuickStats(stats);
      } catch (error) {
        this.warn('Failed to load quick stats:', error);
      }
    }

    updateQuickStats(stats) {
      if (!stats) return;

      // Readings count
      if (this.elements.statReadingsCount) {
        const readingsCount = stats.readings_count ?? stats.total_readings ?? 0;
        if (readingsCount > 0) {
          this.animateCounter(this.elements.statReadingsCount, readingsCount, 0);
        } else {
          this.elements.statReadingsCount.textContent = '--';
        }
      }
      if (this.elements.statReadingsTrend) {
        const trend = stats.readings_trend ?? 0;
        this.elements.statReadingsTrend.textContent = trend >= 0 ? `+${trend}%` : `${trend}%`;
        const trendClass = trend === 0 ? 'neutral' : (trend > 0 ? 'up' : 'down');
        this.elements.statReadingsTrend.className = `quick-stat__trend ${trendClass}`;
      }

      // Anomalies count
      if (this.elements.statAnomaliesCount) {
        this.animateCounter(this.elements.statAnomaliesCount, stats.anomalies_count ?? stats.anomalies ?? 0, 0);
      }
      if (this.elements.statAnomaliesTrend) {
        const trend = stats.anomalies_trend ?? 0;
        // For anomalies, negative is good
        this.elements.statAnomaliesTrend.textContent = trend >= 0 ? `+${trend}%` : `${trend}%`;
        const trendClass = trend === 0 ? 'neutral' : (trend <= 0 ? 'up' : 'down');
        this.elements.statAnomaliesTrend.className = `quick-stat__trend ${trendClass}`;
      }

      // System uptime
      if (this.elements.statSystemUptime) {
        const uptime = stats.system_uptime ?? stats.uptime ?? 99.9;
        this.elements.statSystemUptime.textContent = `${uptime}%`;
      }

      // Average temperature
      if (this.elements.statAvgTemp) {
        const temp = stats.avg_temperature ?? stats.avg_temp;
        if (temp != null && !isNaN(temp)) {
          this.elements.statAvgTemp.textContent = `${Number(temp).toFixed(1)}°C`;
        } else {
          this.elements.statAvgTemp.textContent = '--°C';
        }
      }

      // Average humidity
      if (this.elements.statAvgHumidity) {
        const humidity = stats.avg_humidity;
        if (humidity != null && !isNaN(humidity)) {
          this.elements.statAvgHumidity.textContent = `${Number(humidity).toFixed(0)}%`;
        } else {
          this.elements.statAvgHumidity.textContent = '--%';
        }
      }

      // Data quality
      if (this.elements.statDataQuality) {
        const quality = stats.data_quality ?? stats.quality ?? 98;
        this.elements.statDataQuality.textContent = `${quality}%`;
      }
    }

    // --------------------------------------------------------------------------
    // Automation Status Section
    // --------------------------------------------------------------------------

    async loadAutomationStatus({ force = false } = {}) {
      try {
        const unitId = this.dataService.getSelectedUnitId();
        const status = await this.dataService.loadAutomationStatus({ force, unitId });
        this.updateAutomationStatus(status);
      } catch (error) {
        this.warn('Failed to load automation status:', error);
      }
    }

    updateAutomationStatus(status) {
      if (!status) return;

      // Main status badge
      if (this.elements.automationMainStatus) {
        const isActive = status.is_active !== false;
        const statusText = isActive ? 'Active' : 'Paused';
        this.elements.automationMainStatus.textContent = statusText;
        this.elements.automationMainStatus.className = `automation-status-badge ${isActive ? 'active' : 'paused'}`;
      }

      // Schedules summary
      if (this.elements.automationSchedulesSummary) {
        const total = status.total_schedules || status.schedules_count || 0;
        const active = status.active_schedules_count || 0;
        this.elements.automationSchedulesSummary.textContent = `${active} of ${total} schedules running`;
      }

      // Active schedules list
      if (this.elements.activeSchedulesList) {
        const schedules = status.active_schedules || [];
        if (schedules.length === 0) {
          this.elements.activeSchedulesList.innerHTML = '<div class="empty-message">No active schedules</div>';
        } else {
          this.elements.activeSchedulesList.innerHTML = schedules.slice(0, 5).map(schedule => {
            const label = schedule.name || schedule.type || 'Schedule';
            const time = schedule.next_run || schedule.time || '--';
            const isActive = schedule.is_active !== false && schedule.enabled !== false;
            return `
              <div class="schedule-item ${isActive ? '' : 'inactive'}">
                <div class="schedule-item__info">
                  <span class="schedule-item__device">${this.escapeHTML(label)}</span>
                  <span class="schedule-item__time">${this.escapeHTML(time)}</span>
                </div>
                <span class="schedule-item__status ${isActive ? 'on' : 'off'}">
                  ${isActive ? 'On' : 'Off'}
                </span>
              </div>
            `;
          }).join('');
        }
      }

      // Quick stats
      if (this.elements.autoStatLights) {
        const lights = status.lights_on || status.lights || 0;
        this.elements.autoStatLights.textContent = lights;
      }
      if (this.elements.autoStatFans) {
        const fans = status.fans_on || status.fans || 0;
        this.elements.autoStatFans.textContent = fans;
      }
      if (this.elements.autoStatIrrigation) {
        const irrigation = status.irrigation_active || status.irrigation || 0;
        this.elements.autoStatIrrigation.textContent = irrigation;
      }
    }

    getScheduleIcon(type) {
      const icons = {
        light: '<i class="fas fa-lightbulb"></i>',
        lights: '<i class="fas fa-lightbulb"></i>',
        fan: '<i class="fas fa-fan"></i>',
        fans: '<i class="fas fa-fan"></i>',
        irrigation: '<i class="fas fa-tint"></i>',
        water: '<i class="fas fa-tint"></i>',
        temperature: '<i class="fas fa-thermometer-half"></i>',
        humidity: '<i class="fas fa-water"></i>',
      };
      return icons[type?.toLowerCase()] || '<i class="fas fa-clock"></i>';
    }

    // --------------------------------------------------------------------------
    // Environment Quality Section
    // --------------------------------------------------------------------------

    async loadEnvironmentQuality({ force = false } = {}) {
      try {
        const quality = await this.dataService.loadEnvironmentQuality({ force });
        this.updateEnvironmentQuality(quality);
      } catch (error) {
        this.warn('Failed to load environment quality:', error);
      }
    }

    updateEnvironmentQuality(quality) {
      if (!quality) {
        // Calculate from current sensor data if no dedicated endpoint
        this.calculateEnvironmentQualityFromSensors();
        return;
      }

      const score = quality.overall_score || quality.score || 85;
      this.renderEnvironmentQualityScore(score, quality);
    }

    calculateEnvironmentQualityFromSensors() {
      // Get latest sensor values from cached data
      const sensors = this._insights.latestSensors || {};
      
      // Calculate individual scores based on optimal ranges
      const tempScore = this.calculateFactorScore(sensors.temperature?.value, 20, 26, 15, 32);
      const humidityScore = this.calculateFactorScore(sensors.humidity?.value, 50, 70, 30, 90);
      const vpdScore = this.calculateVPDScore(sensors.temperature?.value, sensors.humidity?.value);
      const co2Score = this.calculateFactorScore(sensors.co2?.value, 400, 800, 300, 1200);

      const overall = Math.round((tempScore + humidityScore + vpdScore + co2Score) / 4);

      this.renderEnvironmentQualityScore(overall, {
        temperature: tempScore,
        humidity: humidityScore,
        vpd: vpdScore,
        co2: co2Score,
      });
    }

    calculateFactorScore(value, optimalMin, optimalMax, acceptableMin, acceptableMax) {
      if (value === null || value === undefined) return 75; // Default if no data

      const numValue = Number(value);
      if (!Number.isFinite(numValue)) return 75;

      // In optimal range = 100%
      if (numValue >= optimalMin && numValue <= optimalMax) return 100;

      // In acceptable range = scaled score
      if (numValue >= acceptableMin && numValue <= acceptableMax) {
        if (numValue < optimalMin) {
          return Math.round(70 + 30 * (numValue - acceptableMin) / (optimalMin - acceptableMin));
        } else {
          return Math.round(70 + 30 * (acceptableMax - numValue) / (acceptableMax - optimalMax));
        }
      }

      // Outside acceptable = poor score
      return Math.max(20, 50 - Math.abs(numValue - (optimalMin + optimalMax) / 2) * 2);
    }

    calculateVPDScore(temp, humidity) {
      if (temp === null || temp === undefined || humidity === null || humidity === undefined) return 75;

      const t = Number(temp);
      const h = Number(humidity);
      if (!Number.isFinite(t) || !Number.isFinite(h)) return 75;

      // Calculate VPD
      const svp = 0.6108 * Math.exp((17.27 * t) / (t + 237.3));
      const avp = svp * (h / 100);
      const vpd = svp - avp;

      // Optimal VPD range for plants: 0.8-1.2 kPa
      return this.calculateFactorScore(vpd, 0.8, 1.2, 0.4, 1.8);
    }

    renderEnvironmentQualityScore(score, factors) {
      // Update ring progress
      if (this.elements.envQualityRingProgress) {
        const circumference = 2 * Math.PI * 42; // radius = 42
        const offset = circumference - (score / 100) * circumference;
        this.elements.envQualityRingProgress.style.strokeDasharray = circumference;
        this.elements.envQualityRingProgress.style.strokeDashoffset = offset;
        
        // Color based on score
        if (score >= 80) {
          this.elements.envQualityRingProgress.style.stroke = 'var(--success-500)';
        } else if (score >= 60) {
          this.elements.envQualityRingProgress.style.stroke = 'var(--warning-500)';
        } else {
          this.elements.envQualityRingProgress.style.stroke = 'var(--error-500)';
        }
      }

      // Update score display
      if (this.elements.envQualityScore) {
        this.animateCounter(this.elements.envQualityScore, score, 0);
      }

      // Update badge
      if (this.elements.envQualityBadge) {
        let label = 'Poor';
        if (score >= 90) label = 'Excellent';
        else if (score >= 80) label = 'Good';
        else if (score >= 60) label = 'Fair';
        this.elements.envQualityBadge.textContent = label;
        this.elements.envQualityBadge.classList.remove('pill--ok', 'pill--bad');
        if (score >= 80) {
          this.elements.envQualityBadge.classList.add('pill--ok');
        } else if (score < 60) {
          this.elements.envQualityBadge.classList.add('pill--bad');
        }
      }

      // Update factor bars
      if (factors) {
        this.updateQualityFactor('temp', factors.temperature);
        this.updateQualityFactor('humidity', factors.humidity);
        this.updateQualityFactor('vpd', factors.vpd);
        this.updateQualityFactor('co2', factors.co2);
      }

      // Update summary text
      if (this.elements.envQualitySummary) {
        let summary = 'Environment conditions are optimal for plant growth.';
        if (score < 60) {
          summary = 'Environment needs attention. Check sensor readings.';
        } else if (score < 80) {
          summary = 'Environment is acceptable but could be improved.';
        }
        this.elements.envQualitySummary.textContent = summary;
      }
    }

    updateQualityFactor(type, score) {
      const scoreEl = this.elements[`quality${this.capitalize(type)}Score`];
      const barEl = this.elements[`quality${this.capitalize(type)}Bar`];

      if (scoreEl) {
        scoreEl.textContent = `${score || 0}%`;
      }
      if (barEl) {
        barEl.style.width = `${score || 0}%`;
        if (score >= 80) {
          barEl.style.backgroundColor = 'var(--success-500)';
        } else if (score >= 60) {
          barEl.style.backgroundColor = 'var(--warning-500)';
        } else {
          barEl.style.backgroundColor = 'var(--error-500)';
        }
      }
    }

    capitalize(str) {
      if (!str) return '';
      return str.charAt(0).toUpperCase() + str.slice(1);
    }

    // --------------------------------------------------------------------------
    // Sensor Health Section
    // --------------------------------------------------------------------------

    async loadSensorHealth({ force = false } = {}) {
      try {
        const health = await this.dataService.loadSensorHealth({ force });
        this.updateSensorHealth(health);
      } catch (error) {
        this.warn('Failed to load sensor health:', error);
      }
    }

    updateSensorHealth(health) {
      if (!health) {
        // Calculate from sensor cards if no dedicated endpoint
        this.calculateSensorHealthFromCards();
        return;
      }

      const healthy = health.healthy || health.online || 0;
      const warning = health.warning || health.degraded || health.stale || 0;
      const offline = health.offline || health.error || 0;

      this.renderSensorHealthStats(healthy, warning, offline);
      this.renderSensorHealthMatrix(health.sensors || []);
    }

    calculateSensorHealthFromCards() {
      let healthy = 0, warning = 0, offline = 0;
      const sensors = [];

      for (const [type, entries] of this.sensorCardsByType.entries()) {
        const card = Array.isArray(entries) ? entries[0]?.card : entries?.card;
        const status = card?.classList?.contains('offline') || card?.classList?.contains('error') ? 'offline'
          : card?.classList?.contains('warning') || card?.classList?.contains('stale') ? 'warning'
          : 'healthy';

        if (status === 'healthy') healthy++;
        else if (status === 'warning') warning++;
        else offline++;

        sensors.push({ type, status });
      }

      this.renderSensorHealthStats(healthy, warning, offline);
      this.renderSensorHealthMatrix(sensors);
    }

    renderSensorHealthStats(healthy, warning, offline) {
      if (this.elements.sensorsHealthyCount) {
        this.animateCounter(this.elements.sensorsHealthyCount, healthy, 0);
      }
      if (this.elements.sensorsWarningCount) {
        this.animateCounter(this.elements.sensorsWarningCount, warning, 0);
      }
      if (this.elements.sensorsOfflineCount) {
        this.animateCounter(this.elements.sensorsOfflineCount, offline, 0);
      }
    }

    renderSensorHealthMatrix(sensors) {
      if (!this.elements.sensorHealthMatrix) return;

      const renderDot = (name, status) => `
        <div class="sensor-health-dot ${status}">
          <span class="sensor-health-dot__indicator"></span>
          <span class="sensor-health-dot__name">${this.escapeHTML(name)}</span>
        </div>
      `;

      if (!sensors || sensors.length === 0) {
        // Generate from sensor types
        const allTypes = this.ALL_SENSOR_TYPES;
        this.elements.sensorHealthMatrix.innerHTML = allTypes.map(type => {
          const entries = this.sensorCardsByType.get(type);
          const card = Array.isArray(entries) ? entries[0]?.card : entries?.card;
          const status = card?.classList?.contains('offline') ? 'offline'
            : card?.classList?.contains('warning') ? 'warning'
            : 'healthy';
          return renderDot(type.replace('_', ' '), status);
        }).join('');
      } else {
        this.elements.sensorHealthMatrix.innerHTML = sensors.map(sensor => {
          const label = sensor.type || sensor.name || 'Sensor';
          const status = sensor.status || 'healthy';
          return renderDot(label, status);
        }).join('');
      }
    }

    // --------------------------------------------------------------------------
    // Recent Journal Section
    // --------------------------------------------------------------------------

    async loadRecentJournal({ force = false } = {}) {
      try {
        const entries = await this.dataService.loadRecentJournal({ force, days: 7, limit: 5 });
        this.updateRecentJournal(entries);
      } catch (error) {
        this.warn('Failed to load recent journal:', error);
      }
    }

    updateRecentJournal(entries) {
      if (!this.elements.recentJournalList) return;

      if (!entries || entries.length === 0) {
        this.elements.recentJournalList.innerHTML = `
          <div class="empty-message">No recent journal entries</div>
        `;
        return;
      }

      this.elements.recentJournalList.innerHTML = entries.map(entry => {
        const rawType = entry.entry_type || entry.type || entry.category || 'note';
        const normalizedType = String(rawType || '').toLowerCase();
        const typeMap = {
          nutrient: 'nutrients',
          nutrients: 'nutrients',
          feeding: 'nutrients',
          health: 'health',
          observation: 'observation',
          issue: 'issue',
          watering: 'watering',
        };
        const typeToken = typeMap[normalizedType] || this.safeToken(rawType, 'note');
        const plantName = entry.plant_name || entry.plant || entry.unit_name || 'Plant';
        const notes = entry.notes || entry.note || entry.title || 'Journal entry';
        return `
          <div class="journal-item ${typeToken}">
            <span class="journal-item__icon">${this.getJournalIcon(rawType)}</span>
            <div class="journal-item__content">
              <div class="journal-item__header">
                <span class="journal-item__plant">${this.escapeHTML(plantName)}</span>
                <span class="journal-item__time">${this.formatRelativeTime(entry.created_at || entry.date)}</span>
              </div>
              <div class="journal-item__type">${this.escapeHTML(String(rawType).replace('_', ' '))}</div>
              <div class="journal-item__notes">${this.escapeHTML(notes)}</div>
            </div>
          </div>
        `;
      }).join('');
    }

    getJournalIcon(type) {
      const icons = {
        observation: '<i class="fas fa-eye"></i>',
        watering: '<i class="fas fa-tint"></i>',
        feeding: '<i class="fas fa-seedling"></i>',
        pruning: '<i class="fas fa-cut"></i>',
        harvest: '<i class="fas fa-leaf"></i>',
        note: '<i class="fas fa-sticky-note"></i>',
        photo: '<i class="fas fa-camera"></i>',
        issue: '<i class="fas fa-exclamation-triangle"></i>',
      };
      return icons[type?.toLowerCase()] || '<i class="fas fa-book"></i>';
    }

    formatRelativeTime(dateString) {
      if (!dateString) return '';
      
      try {
        const date = new Date(dateString);
        const now = new Date();
        const diffMs = now - date;
        const diffMins = Math.floor(diffMs / 60000);
        const diffHours = Math.floor(diffMs / 3600000);
        const diffDays = Math.floor(diffMs / 86400000);

        if (diffMins < 1) return 'Just now';
        if (diffMins < 60) return `${diffMins}m ago`;
        if (diffHours < 24) return `${diffHours}h ago`;
        if (diffDays < 7) return `${diffDays}d ago`;
        return date.toLocaleDateString();
      } catch {
        return dateString;
      }
    }

    // --------------------------------------------------------------------------
    // Phase 1: Growth Stage Tracker
    // --------------------------------------------------------------------------

    async loadGrowthStage({ force = false } = {}) {
      try {
        const data = await this.dataService.loadGrowthStage({ force });
        this.updateGrowthStage(data);
      } catch (error) {
        this.warn('Failed to load growth stage:', error);
      }
    }

    updateGrowthStage(data) {
      if (!data) return;

      const stages = (data.stages && data.stages.length)
        ? data.stages
        : ['seedling', 'vegetative', 'flowering', 'fruiting', 'harvest'];
      const currentStage = data.current_stage || 'vegetative';
      const currentKey = currentStage.toLowerCase();
      const stageKeys = stages.map(stage => String(stage).toLowerCase());
      const stageIndex = stageKeys.indexOf(currentKey);
      const progress = data.progress != null
        ? data.progress
        : (stageIndex >= 0 ? ((stageIndex + 1) / stages.length) * 100 : 0);

      // Update progress bar
      if (this.elements.growthStageProgress) {
        const clamped = Math.max(0, Math.min(100, progress));
        this.elements.growthStageProgress.style.width = `${clamped}%`;
      }

      // Update stage badge
      if (this.elements.growthStageBadge) {
        this.elements.growthStageBadge.textContent = currentStage.charAt(0).toUpperCase() + currentStage.slice(1);
      }

      // Update stage markers
      const markersContainer = document.querySelector('.stage-markers');
      if (markersContainer) {
        const markers = Array.from(markersContainer.querySelectorAll('.stage-marker'));
        if (markers.length > 0) {
          markers.forEach(marker => {
            const markerStage = marker.dataset.stage || marker.textContent;
            const markerKey = String(markerStage || '').toLowerCase();
            const markerIndex = stageKeys.indexOf(markerKey);
            marker.classList.toggle('active', markerIndex === stageIndex);
            marker.classList.toggle('completed', markerIndex >= 0 && stageIndex >= 0 && markerIndex < stageIndex);
          });
        } else {
          markersContainer.innerHTML = stages.map((stage, i) => {
            const isActive = stageKeys[i] === currentKey;
            const isCompleted = i < stageIndex;
            const label = String(stage || '').trim();
            const markerLabel = label ? label.charAt(0).toUpperCase() : '?';
            return `<span class="stage-marker ${isActive ? 'active' : ''} ${isCompleted ? 'completed' : ''}" title="${stage}">${markerLabel}</span>`;
          }).join('');
        }
      }

      // Update info section
      if (this.elements.growthCurrentStage) {
        this.elements.growthCurrentStage.textContent = currentStage.charAt(0).toUpperCase() + currentStage.slice(1);
      }
      if (this.elements.growthDaysInStage) {
        this.elements.growthDaysInStage.textContent = data.days_in_stage ?? '--';
      }
      if (this.elements.growthDaysTotal) {
        this.elements.growthDaysTotal.textContent = data.days_total ?? '--';
      }

      // Update tip
      if (this.elements.growthStageTip) {
        const tips = {
          seedling: 'Keep humidity high and light gentle for delicate seedlings.',
          vegetative: 'Focus on nitrogen-rich feeding for strong vegetative growth.',
          flowering: 'Increase phosphorus and potassium. Watch for pest pressure.',
          fruiting: 'Support fruit development with steady nutrition and airflow.',
          harvest: 'Monitor trichomes and plan your harvest window.',
        };
        this.elements.growthStageTip.textContent = data.tip || tips[currentKey] || 'Keep monitoring your plants!';
      }

    }

    // --------------------------------------------------------------------------
    // Phase 1: Harvest Timeline
    // --------------------------------------------------------------------------

    async loadHarvestTimeline({ force = false } = {}) {
      try {
        const data = await this.dataService.loadHarvestTimeline({ force });
        this.updateHarvestTimeline(data);
      } catch (error) {
        this.warn('Failed to load harvest timeline:', error);
      }
    }

    updateHarvestTimeline(data) {
      if (!this.elements.harvestTimelineItems) return;

      const plants = data?.upcoming || [];
      
      if (plants.length === 0) {
        this.elements.harvestTimelineItems.innerHTML = `
          <div class="timeline-item">
            <div class="timeline-item__dot"><i class="fas fa-seedling"></i></div>
            <span class="timeline-item__name">No harvests scheduled</span>
          </div>
        `;
      } else {
        this.elements.harvestTimelineItems.innerHTML = plants.slice(0, 4).map(plant => {
          const daysLeft = plant.days_until_harvest ?? plant.days_left ?? 0;
          const statusClass = daysLeft <= 7 ? 'ready' : (daysLeft <= 14 ? 'soon' : '');
          return `
            <div class="timeline-item">
              <div class="timeline-item__dot ${statusClass}">
                ${daysLeft <= 7 ? '<i class="fas fa-check"></i>' : `${daysLeft}d`}
              </div>
              <span class="timeline-item__name">${this.escapeHTML(plant.name || plant.plant_name || 'Plant')}</span>
              <span class="timeline-item__days">${daysLeft > 0 ? `${daysLeft} days` : 'Ready!'}</span>
            </div>
          `;
        }).join('');
      }

      // Recent harvest
      if (this.elements.harvestRecentValue) {
        const recent = data?.recent_harvest;
        if (recent) {
          const date = new Date(recent.date || recent.harvested_at);
          this.elements.harvestRecentValue.textContent = `${recent.amount || recent.weight || '--'}g on ${date.toLocaleDateString()}`;
        } else {
          this.elements.harvestRecentValue.textContent = 'No recent harvests';
        }
      }
    }

    // --------------------------------------------------------------------------
    // Phase 1: Water/Feed Schedule
    // --------------------------------------------------------------------------

    async loadWaterSchedule({ force = false } = {}) {
      try {
        const data = await this.dataService.loadWaterSchedule({ force });
        this.updateWaterSchedule(data);
      } catch (error) {
        this.warn('Failed to load water schedule:', error);
      }
    }

    updateWaterSchedule(data) {
      // Update countdowns
      if (this.elements.nextWaterCountdown) {
        const hours = data?.next_water_hours ?? data?.water?.next_hours;
        if (hours === null || hours === undefined) {
          this.elements.nextWaterCountdown.textContent = '--';
        } else {
          this.elements.nextWaterCountdown.textContent = hours > 24 
            ? `${Math.floor(hours / 24)}d ${hours % 24}h`
            : `${hours}h`;
        }
      }
      if (this.elements.nextFeedCountdown) {
        const hours = data?.next_feed_hours ?? data?.feed?.next_hours;
        if (hours === null || hours === undefined) {
          this.elements.nextFeedCountdown.textContent = '--';
        } else {
          this.elements.nextFeedCountdown.textContent = hours > 24
            ? `${Math.floor(hours / 24)}d ${hours % 24}h`
            : `${hours}h`;
        }
      }

      // Update week view
      if (this.elements.waterScheduleDays) {
        const today = new Date().getDay();
        const dayNames = ['S', 'M', 'T', 'W', 'T', 'F', 'S'];
        const waterDays = Array.isArray(data?.water_days) ? data.water_days : [];
        const feedDays = Array.isArray(data?.feed_days) ? data.feed_days : [];

        this.elements.waterScheduleDays.innerHTML = dayNames.map((day, i) => {
          const isToday = i === today;
          const isWater = waterDays.includes(i);
          const isFeed = feedDays.includes(i);
          return `
            <div class="day-item ${isWater ? 'water' : ''} ${isFeed ? 'feed' : ''} ${isToday ? 'today' : ''}">
              ${day}
              ${isWater ? '<i class="fas fa-tint" style="font-size: 0.5rem;"></i>' : ''}
              ${isFeed ? '<i class="fas fa-leaf" style="font-size: 0.5rem;"></i>' : ''}
            </div>
          `;
        }).join('');
      }
    }

    // --------------------------------------------------------------------------
    // Phase 1: Irrigation Status
    // --------------------------------------------------------------------------

    async loadIrrigationStatus({ force = false } = {}) {
      try {
        const data = await this.dataService.loadIrrigationStatus({ force });
        this.updateIrrigationStatus(data);
      } catch (error) {
        this.warn('Failed to load irrigation status:', error);
      }
    }

    updateIrrigationStatus(data) {
      // Last run
      if (this.elements.irrigationLastRun) {
        const lastRun = data?.last_run || data?.last_irrigation;
        if (lastRun) {
          this.elements.irrigationLastRun.textContent = this.formatRelativeTime(lastRun);
        } else {
          this.elements.irrigationLastRun.textContent = '--';
        }
      }

      // Soil moisture bar
      if (this.elements.irrigationSoilBar) {
        const moisture = data?.soil_moisture ?? data?.current_moisture;
        if (moisture === null || moisture === undefined) {
          this.elements.irrigationSoilBar.style.width = '0%';
        } else {
          this.elements.irrigationSoilBar.style.width = `${Math.min(100, Math.max(0, moisture))}%`;
        }
      }
      if (this.elements.irrigationSoilValue) {
        const moisture = data?.soil_moisture ?? data?.current_moisture;
        this.elements.irrigationSoilValue.textContent = moisture === null || moisture === undefined
          ? '--%'
          : `${moisture}%`;
      }
    }

    // --------------------------------------------------------------------------
    // Irrigation Telemetry
    // --------------------------------------------------------------------------

    async loadIrrigationTelemetry({ force = false } = {}) {
      try {
        const data = await this.dataService.loadIrrigationTelemetry({
          force,
          days: this._telemetryDays || 7,
        });
        this.updateIrrigationTelemetry(data);
      } catch (error) {
        this.warn('Failed to load irrigation telemetry:', error);
      }
    }

    updateIrrigationTelemetry(data) {
      this._telemetryData = {
        executions: Array.isArray(data?.executions) ? data.executions : [],
        eligibility: Array.isArray(data?.eligibility) ? data.eligibility : [],
        manual: Array.isArray(data?.manual) ? data.manual : [],
      };

      this._renderTelemetryTab();
    }

    _renderTelemetryTab() {
      const tab = this._telemetryTab || 'executions';
      const data = this._telemetryData || { executions: [], eligibility: [], manual: [] };

      let items = [];
      let emptyText = 'No telemetry data';
      let renderer = null;

      if (tab === 'executions') {
        items = data.executions || [];
        emptyText = 'No execution logs';
        renderer = (item) => {
          const time = this._formatTelemetryTime(item.executed_at_utc || item.triggered_at_utc);
          const status = this.escapeHTML(item.execution_status || 'unknown');
          const duration = item.actual_duration_s ?? item.planned_duration_s;
          const volume = item.estimated_volume_ml;
          const recommendation = item.recommendation;

          const metaParts = [];
          metaParts.push(duration != null ? `${Math.round(duration)}s` : '--s');
          metaParts.push(volume != null ? `${Math.round(volume)}ml` : '--ml');
          if (recommendation) {
            metaParts.push(this.escapeHTML(recommendation));
          }

          return `
            <div class="telemetry-item">
              <div class="telemetry-main">
                <span>${status}</span>
                <span class="telemetry-time">${time}</span>
              </div>
              <div class="telemetry-meta">${metaParts.join(' · ')}</div>
            </div>
          `;
        };
      } else if (tab === 'eligibility') {
        items = data.eligibility || [];
        emptyText = 'No eligibility traces';
        renderer = (item) => {
          const time = this._formatTelemetryTime(item.evaluated_at_utc);
          const decision = this.escapeHTML(item.decision || 'unknown');
          const reason = item.skip_reason ? this.escapeHTML(item.skip_reason) : 'eligible';
          const moisture = item.moisture != null ? `${item.moisture}%` : '--';
          const threshold = item.threshold != null ? `${item.threshold}%` : '--';

          return `
            <div class="telemetry-item">
              <div class="telemetry-main">
                <span>${decision}</span>
                <span class="telemetry-time">${time}</span>
              </div>
              <div class="telemetry-meta">${reason} · ${moisture} / ${threshold}</div>
            </div>
          `;
        };
      } else {
        items = data.manual || [];
        emptyText = 'No manual logs';
        renderer = (item) => {
          const time = this._formatTelemetryTime(item.watered_at_utc);
          const amount = item.amount_ml != null ? `${Math.round(item.amount_ml)}ml` : '--ml';
          const delta = item.delta_moisture != null ? `${item.delta_moisture}%` : '--';

          return `
            <div class="telemetry-item">
              <div class="telemetry-main">
                <span>manual</span>
                <span class="telemetry-time">${time}</span>
              </div>
              <div class="telemetry-meta">${amount} · Δ ${delta}</div>
            </div>
          `;
        };
      }

      this._renderTelemetryList(
        this.elements.irrigationTelemetryList,
        items,
        renderer,
        emptyText
      );

      if (this.elements.irrigationTelemetryFootnote) {
        const count = Array.isArray(items) ? items.length : 0;
        const label = tab === 'executions' ? 'executions' : (tab === 'eligibility' ? 'traces' : 'manual logs');
        this.elements.irrigationTelemetryFootnote.textContent = count
          ? `Showing ${Math.min(count, 4)} of ${count} ${label}`
          : 'No data available for this range';
      }
    }

    _renderTelemetryList(container, items, renderItem, emptyText) {
      if (!container) return;
      if (!items || items.length === 0) {
        container.innerHTML = `<div class="empty-message">${emptyText}</div>`;
        return;
      }

      const sliced = items.slice(0, 4);
      container.innerHTML = sliced.map(renderItem).join('');
    }

    _formatTelemetryTime(value) {
      if (!value) return '--';
      try {
        return this.formatRelativeTime(value);
      } catch (e) {
        return '--';
      }
    }

    // --------------------------------------------------------------------------
    // Irrigation Recommendations
    // --------------------------------------------------------------------------

    /**
     * Load irrigation recommendations for the selected plant
     * @param {Object} options - Load options
     * @param {boolean} options.force - Force refresh bypassing cache
     */
    async loadIrrigationRecommendations({ force = false } = {}) {
      const plantId = this._getSelectedPlantId();
      if (!plantId) {
        this.updateIrrigationRecommendationsEmpty();
        return;
      }

      try {
        const data = await API.Irrigation.getRecommendations(plantId);
        this.updateIrrigationRecommendations(data);
      } catch (error) {
        this.warn('Failed to load irrigation recommendations:', error);
        this.updateIrrigationRecommendationsError(error);
      }
    }

    /**
     * Get the currently selected plant ID from the plant selector
     * @returns {number|null} Plant ID or null
     */
    _getSelectedPlantId() {
      // First check the explicitly selected plant ID from the dropdown
      if (this._selectedIrrigationPlantId) {
        return this._selectedIrrigationPlantId;
      }

      // Check the dropdown value
      if (this.elements.irrigationPlantSelect && this.elements.irrigationPlantSelect.value) {
        return parseInt(this.elements.irrigationPlantSelect.value, 10);
      }

      // Check URL params as fallback
      const urlParams = new URLSearchParams(window.location.search);
      const plantParam = urlParams.get('plant_id');
      return plantParam ? parseInt(plantParam, 10) : null;
    }

    /**
     * Populate the irrigation plant selector dropdown
     * @param {Array} plants - Array of plant objects
     */
    updateIrrigationPlantSelector(plants) {
      const select = this.elements.irrigationPlantSelect;
      if (!select) return;

      // Preserve current selection if exists
      const currentValue = select.value || this._selectedIrrigationPlantId;

      // Clear existing options (except the placeholder)
      select.innerHTML = '<option value="">Select a plant...</option>';

      if (!Array.isArray(plants) || plants.length === 0) {
        return;
      }

      // Add plant options
      for (const plant of plants) {
        const option = document.createElement('option');
        // Support both plant_id and id field names
        const plantId = plant.plant_id || plant.id;
        option.value = plantId;
        const species = plant.species || plant.plant_type || 'Unknown';
        const name = plant.plant_name || plant.name || `Plant ${plantId}`;
        option.textContent = `${name} (${species})`;
        select.appendChild(option);
      }

      // Restore previous selection if it exists in the new list
      if (currentValue) {
        const exists = plants.some(p => String(p.plant_id || p.id) === String(currentValue));
        if (exists) {
          select.value = currentValue;
          this._selectedIrrigationPlantId = parseInt(currentValue, 10);
        }
      }

      // If only one plant, auto-select it
      if (plants.length === 1) {
        const plantId = plants[0].plant_id || plants[0].id;
        select.value = plantId;
        this._selectedIrrigationPlantId = plantId;
        // Load recommendations for the auto-selected plant
        this.loadIrrigationRecommendations({ force: true });
      }
    }

    /**
     * Update irrigation recommendations UI
     * @param {Object} data - Recommendation data from API
     */
    updateIrrigationRecommendations(data) {
      if (!data) {
        this.updateIrrigationRecommendationsEmpty();
        return;
      }

      const recommendationPayload = data.recommendation || {};
      const recommendationAction = typeof recommendationPayload === 'string'
        ? recommendationPayload
        : recommendationPayload.action || data.recommendation || 'monitor';
      const recommendationReason = data.reason || recommendationPayload.reason;
      const recommendationUrgency = (data.urgency || recommendationPayload.urgency || 'low').toLowerCase();

      // Update recommendation banner
      if (this.elements.irrigationRecBanner) {
        this.elements.irrigationRecBanner.className = `irrigation-recommendation-banner ${recommendationAction}`;
      }

      // Update action text
      if (this.elements.irrigationRecAction) {
        const actionTexts = {
          water_now: 'Water Now',
          wait: 'Wait',
          monitor: 'Monitor'
        };
        this.elements.irrigationRecAction.textContent = actionTexts[recommendationAction] || 'Analyzing...';
      }

      // Update reason text
      if (this.elements.irrigationRecReason) {
        this.elements.irrigationRecReason.textContent = recommendationReason || 'Checking soil moisture levels';
      }

      // Update urgency badge
      if (this.elements.irrigationRecUrgency) {
        this.elements.irrigationRecUrgency.textContent = recommendationUrgency.charAt(0).toUpperCase() + recommendationUrgency.slice(1);
        this.elements.irrigationRecUrgency.className = `urgency-badge ${recommendationUrgency}`;
      }

      // Update calculation preview
      const calc = data.calculation || {};
      
      if (this.elements.irrPreviewVolume) {
        const volume = calc.water_volume_ml || calc.volume_ml || calc.volume;
        this.elements.irrPreviewVolume.textContent = volume ? `${Math.round(volume)}` : '--';
      }

      if (this.elements.irrPreviewDuration) {
        const duration = calc.duration_seconds || calc.duration;
        this.elements.irrPreviewDuration.textContent = duration ? `${Math.round(duration)}` : '--';
      }

      if (this.elements.irrPreviewConfidence) {
        const confidence = calc.confidence;
        this.elements.irrPreviewConfidence.textContent = confidence != null ? `${Math.round(confidence * 100)}%` : '--';
      }

      if (this.elements.irrPreviewReasoning) {
        const rawReasoning = calc.reasoning || recommendationPayload.reasoning || data.reasoning;
        const reasoningList = Array.isArray(rawReasoning)
          ? rawReasoning
          : rawReasoning
            ? [rawReasoning]
            : [];

        if (reasoningList.length > 0) {
          this.elements.irrPreviewReasoning.innerHTML = reasoningList
            .map(r => `<span class="reasoning-item">• ${this.escapeHTML(r)}</span>`)
            .join('');
        } else {
          this.elements.irrPreviewReasoning.innerHTML = '<span class="reasoning-item">No additional reasoning available</span>';
        }
      }

      // Enable/disable irrigate button based on recommendation
      if (this.elements.btnIrrigateNow) {
        const canIrrigate = recommendationAction === 'water_now' || recommendationUrgency === 'high';
        this.elements.btnIrrigateNow.disabled = !canIrrigate;
        
        // Store calculation for use when button is clicked
        this.elements.btnIrrigateNow.dataset.volumeMl = calc.water_volume_ml || calc.volume_ml || calc.volume || 0;
        this.elements.btnIrrigateNow.dataset.durationSeconds = calc.duration_seconds || calc.duration || 0;
      }
    }

    /**
     * Update UI when no plant is selected or data is empty
     */
    updateIrrigationRecommendationsEmpty() {
      if (this.elements.irrigationRecBanner) {
        this.elements.irrigationRecBanner.className = 'irrigation-recommendation-banner';
      }
      if (this.elements.irrigationRecAction) {
        this.elements.irrigationRecAction.textContent = 'Select a plant';
      }
      if (this.elements.irrigationRecReason) {
        this.elements.irrigationRecReason.textContent = 'Choose a plant from the dropdown to get AI-powered irrigation recommendations';
      }
      if (this.elements.irrigationRecUrgency) {
        this.elements.irrigationRecUrgency.textContent = '-';
        this.elements.irrigationRecUrgency.className = 'urgency-badge';
      }
      if (this.elements.irrPreviewVolume) {
        this.elements.irrPreviewVolume.textContent = '--';
      }
      if (this.elements.irrPreviewDuration) {
        this.elements.irrPreviewDuration.textContent = '--';
      }
      if (this.elements.irrPreviewConfidence) {
        this.elements.irrPreviewConfidence.textContent = '--';
      }
      if (this.elements.irrPreviewReasoning) {
        this.elements.irrPreviewReasoning.innerHTML = '<small class="text-muted">Select a plant to see AI-powered calculations</small>';
      }
      if (this.elements.btnIrrigateNow) {
        this.elements.btnIrrigateNow.disabled = true;
      }
    }

    /**
     * Update UI on error
     * @param {Error} error - The error that occurred
     */
    updateIrrigationRecommendationsError(error) {
      if (this.elements.irrigationRecAction) {
        this.elements.irrigationRecAction.textContent = 'Error';
      }
      if (this.elements.irrigationRecReason) {
        this.elements.irrigationRecReason.textContent = 'Failed to load recommendations';
      }
      if (this.elements.irrigationRecUrgency) {
        this.elements.irrigationRecUrgency.textContent = '--';
        this.elements.irrigationRecUrgency.className = 'urgency-badge';
      }
      if (this.elements.btnIrrigateNow) {
        this.elements.btnIrrigateNow.disabled = true;
      }
    }

    /**
     * Handle irrigate now button click
     */
    async handleIrrigateNow() {
      const plantId = this._getSelectedPlantId();
      if (!plantId) {
        this.showNotification('No plant selected', 'warning');
        return;
      }

      const btn = this.elements.btnIrrigateNow;
      if (!btn || btn.disabled) return;

      const volumeMl = parseFloat(btn.dataset.volumeMl) || 0;
      const durationSeconds = parseFloat(btn.dataset.durationSeconds) || 0;

      if (volumeMl <= 0 || durationSeconds <= 0) {
        this.showNotification('Invalid irrigation parameters', 'error');
        return;
      }

      try {
        btn.disabled = true;
        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Irrigating...';
        
        // TODO: Call actual irrigation trigger endpoint when available
        // For now, show confirmation and refresh
        this.showNotification(`Irrigation started: ${volumeMl}ml for ${durationSeconds}s`, 'success');
        
        // Refresh recommendations after a delay
        setTimeout(() => this.loadIrrigationRecommendations({ force: true }), 3000);
      } catch (error) {
        this.warn('Failed to trigger irrigation:', error);
        this.showNotification('Failed to start irrigation', 'error');
      } finally {
        btn.innerHTML = '<i class="fas fa-tint"></i> Irrigate Now';
        // Re-enable will happen on next recommendations load
      }
    }

    /**
     * Handle calibrate pump button click
     */
    handleCalibratePump() {
      // Navigate to settings page with pump calibration section
      window.location.href = '/settings#pump-calibration';
    }

    // --------------------------------------------------------------------------
    // Initialize new section event handlers
    // --------------------------------------------------------------------------

    initNewSectionHandlers() {
      // Automation refresh
      if (this.elements.refreshAutomation) {
        this.elements.refreshAutomation.addEventListener('click', () => this.loadAutomationStatus({ force: true }));
      }

      // Sensor health refresh
      if (this.elements.refreshSensorHealth) {
        this.elements.refreshSensorHealth.addEventListener('click', () => this.loadSensorHealth({ force: true }));
      }

      // Journal refresh
      if (this.elements.refreshJournal) {
        this.elements.refreshJournal.addEventListener('click', () => this.loadRecentJournal({ force: true }));
      }

      // Harvest timeline refresh
      if (this.elements.refreshHarvestTimeline) {
        this.elements.refreshHarvestTimeline.addEventListener('click', () => this.loadHarvestTimeline({ force: true }));
      }

      // Unified Irrigation Control refresh
      if (this.elements.refreshIrrigation) {
        this.elements.refreshIrrigation.addEventListener('click', () => {
          this.loadWaterSchedule({ force: true });
          this.loadIrrigationStatus({ force: true });
          this.loadIrrigationRecommendations({ force: true });
          this.loadIrrigationTelemetry({ force: true });
        });
      }

      if (this.elements.irrigationTelemetryRefresh) {
        this.elements.irrigationTelemetryRefresh.addEventListener('click', () => {
          this.loadIrrigationTelemetry({ force: true });
        });
      }

      document.querySelectorAll('.telemetry-range [data-days]').forEach((btn) => {
        btn.addEventListener('click', () => {
          const days = parseInt(btn.dataset.days, 10);
          if (!Number.isNaN(days)) {
            this._telemetryDays = days;
            document.querySelectorAll('.telemetry-range [data-days]').forEach((el) => {
              el.classList.toggle('active', el === btn);
            });
            this.loadIrrigationTelemetry({ force: true });
          }
        });
      });

      if (this.elements.irrigationTelemetryTabs) {
        this.elements.irrigationTelemetryTabs.querySelectorAll('[data-tab]').forEach((btn) => {
          btn.addEventListener('click', () => {
            const tab = btn.dataset.tab;
            if (!tab) return;
            this._telemetryTab = tab;
            this.elements.irrigationTelemetryTabs.querySelectorAll('[data-tab]').forEach((el) => {
              el.classList.toggle('active', el === btn);
            });
            this._renderTelemetryTab();
          });
        });
      }

      // Irrigation plant selector
      if (this.elements.irrigationPlantSelect) {
        this.elements.irrigationPlantSelect.addEventListener('change', (e) => {
          this._selectedIrrigationPlantId = e.target.value ? parseInt(e.target.value, 10) : null;
          this.loadIrrigationRecommendations({ force: true });
        });
      }

      // Quick action buttons
      if (this.elements.btnWaterNow) {
        this.elements.btnWaterNow.addEventListener('click', () => this.triggerQuickAction('water'));
      }
      if (this.elements.btnFeedNow) {
        this.elements.btnFeedNow.addEventListener('click', () => this.triggerQuickAction('feed'));
      }

      // Irrigation Recommendations section
      if (this.elements.btnIrrigateNow) {
        this.elements.btnIrrigateNow.addEventListener('click', () => this.handleIrrigateNow());
      }
      if (this.elements.btnCalibratePump) {
        this.elements.btnCalibratePump.addEventListener('click', () => this.handleCalibratePump());
      }
    }

    async triggerQuickAction(action) {
      try {
        this.showNotification(`${action.charAt(0).toUpperCase() + action.slice(1)} action triggered`, 'info');
        // Future: Call actual API endpoint
        // await API.Automation.triggerAction(action);
      } catch (error) {
        this.warn(`Failed to trigger ${action} action:`, error);
        this.showNotification(`Failed to trigger ${action}`, 'error');
      }
    }

    // --------------------------------------------------------------------------
    // Cleanup
    // --------------------------------------------------------------------------

    destroy() {
      this._destroyed = true;
      this.stopPeriodicUpdates();

      // Clean up component instances
      if (this._vpdGauge) {
        this._vpdGauge.destroy();
        this._vpdGauge = null;
      }
      this._actuatorPanel = null;
      this._plantGrid = null;
      this._energySummary = null;
      this._alertTimeline = null;
      this._alertSummary = null;

      for (const unsub of this.unsubscribeFunctions) {
        try { unsub(); } catch {}
      }
      this.unsubscribeFunctions = [];

      super.destroy();
    }
  }

  window.DashboardUIManager = DashboardUIManager;
})();
