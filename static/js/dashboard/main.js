/**
 * Dashboard - Main entry point
 * ============================================================================
 * - DOMContentLoaded safe init
 * - Initializes DataService and UIManager
 * - Initializes Environmental Overview Chart
 * - Optional debugging via localStorage "dashboard:debug"
 */
(function () {
  'use strict';

  let dataService;
  let uiManager;
  let environmentalChart;
  let efficiencyScore;
  let alertTimeline;
  let alertRefreshInterval;

  const DEBUG = localStorage.getItem('dashboard:debug') === '1';

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init, { once: true });
  } else {
    init();
  }

  async function init() {
    try {
      const pageShell = document.querySelector('.page-shell');
      const raw = pageShell?.dataset?.selectedUnitId ?? null;

      const parsed = raw !== null && raw !== '' ? parseInt(raw, 10) : null;
      const selectedUnitId = Number.isFinite(parsed) ? parsed : null;

      dataService = new window.DashboardDataService();
      dataService.init(selectedUnitId);

      uiManager = new window.DashboardUIManager(dataService);
      await uiManager._safeInit();

      // Initialize Environmental Overview Chart if available
      await initEnvironmentalChart(selectedUnitId);

      // Setup chart time range selector
      setupChartControls(selectedUnitId);

      // Initialize System Efficiency Score component
      initEfficiencyScore(selectedUnitId);

      // Initialize Intelligent Alert Timeline component
      initAlertTimeline(selectedUnitId);

      // Expose only in debug mode to avoid accidental coupling.
      if (DEBUG) {
        window.Dashboard = { dataService, uiManager, environmentalChart, efficiencyScore, alertTimeline, version: '2.2.0' };
      }

      console.log('[Dashboard] Initialized');
    } catch (error) {
      window.SYSGrow.initError('Dashboard', error);
    }
  }

  /**
   * Initialize environmental overview chart
   */
  async function initEnvironmentalChart(unitId) {
    const canvas = document.getElementById('environmental-chart');
    if (!canvas) return;

    try {
      // Check if EnvironmentalOverviewChart class is available
      if (window.EnvironmentalOverviewChart) {
        environmentalChart = new window.EnvironmentalOverviewChart('environmental-chart', {
          unitId: unitId,
          showForecast: false,  // Disable forecast on dashboard for performance
          showControls: false,  // Hide controls on compact dashboard view
          onDataLoaded: (payload) => {
            try {
              uiManager?.updateInsightsFromEnvironmentalPayload?.(payload);
            } catch (err) {
              console.warn('[Dashboard] Failed to update insights from chart payload:', err);
            }
          }
        });
        await environmentalChart.init(unitId);
      } else {
        // Fallback: Create a simple line chart using Chart.js directly
        await createSimpleEnvironmentalChart(canvas, unitId);
      }
    } catch (error) {
      console.warn('[Dashboard] Environmental chart initialization failed:', error);
      // Create placeholder chart on error
      await createSimpleEnvironmentalChart(canvas, unitId);
    }
  }

  /**
   * Create a simple environmental chart as fallback
   */
  async function createSimpleEnvironmentalChart(canvas, unitId) {
    try {
      // Fetch timeseries data
      const hours = 24;
      const data = await API.Dashboard.getTimeseries({ hours, unit_id: unitId, limit: 500 });
      const series = data?.series || [];

      if (series.length === 0) {
        canvas.closest('.chart-container').innerHTML = '<div class="empty-message">No sensor data available</div>';
        return;
      }

      // Prepare datasets
      const labels = series.map(r => new Date(r.timestamp));
      const temperatures = series.map(r => r.temperature);
      const humidities = series.map(r => r.humidity);
      const soilMoistures = series.map(r => r.soil_moisture);

      const ctx = canvas.getContext('2d');

      const { cssVar } = window.SYSGrow;

      new Chart(ctx, {
        type: 'line',
        data: {
          labels: labels,
          datasets: [
            {
              label: 'Temperature (°C)',
              data: temperatures,
              borderColor: cssVar('--chart-temperature'),
              backgroundColor: cssVar('--chart-temperature-bg'),
              fill: false,
              tension: 0.4,
              pointRadius: 0,
              borderWidth: 2
            },
            {
              label: 'Humidity (%)',
              data: humidities,
              borderColor: cssVar('--chart-humidity'),
              backgroundColor: cssVar('--chart-humidity-bg'),
              fill: false,
              tension: 0.4,
              pointRadius: 0,
              borderWidth: 2
            },
            {
              label: 'Soil Moisture (%)',
              data: soilMoistures,
              borderColor: cssVar('--chart-soil'),
              backgroundColor: cssVar('--chart-soil-bg'),
              fill: false,
              tension: 0.4,
              pointRadius: 0,
              borderWidth: 2
            }
          ]
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
              position: 'top',
              labels: { usePointStyle: true, boxWidth: 6 }
            },
            tooltip: {
              callbacks: {
                title: (items) => {
                  const date = new Date(items[0].parsed.x);
                  return date.toLocaleString();
                }
              }
            }
          },
          scales: {
            x: {
              type: 'time',
              time: {
                unit: 'hour',
                displayFormats: { hour: 'HH:mm' }
              },
              grid: { display: false }
            },
            y: {
              beginAtZero: false,
              grid: { color: cssVar('--chart-grid') }
            }
          }
        }
      });

      window._dashboardEnvChart = canvas;
    } catch (error) {
      console.error('[Dashboard] Failed to create environmental chart:', error);
    }
  }

  /**
   * Setup chart time range controls
   */
  function setupChartControls(unitId) {
    const selector = document.getElementById('chart-timerange');
    if (!selector) return;

    selector.addEventListener('change', async (e) => {
      const hours = parseInt(e.target.value, 10);
      const canvas = document.getElementById('environmental-chart');

      if (environmentalChart && environmentalChart.setTimeRange) {
        // Use the chart's built-in method if available
        await environmentalChart.setTimeRange(hours);
      } else if (canvas) {
        // Recreate the simple chart with new time range
        await createSimpleEnvironmentalChart(canvas, unitId);
      }
    });
  }

  /**
   * Initialize System Efficiency Score component
   */
  function initEfficiencyScore(unitId) {
    const container = document.getElementById('system-efficiency-score-container');
    if (!container) return;

    try {
      if (typeof window.SystemEfficiencyScore !== 'undefined') {
        efficiencyScore = new window.SystemEfficiencyScore('system-efficiency-score-container', {
          updateInterval: 60000,
          enableMLSuggestions: true
        });
        efficiencyScore.init(unitId);
        console.log('[Dashboard] SystemEfficiencyScore initialized');
      } else {
        console.warn('[Dashboard] SystemEfficiencyScore class not available');
      }
    } catch (error) {
      console.error('[Dashboard] Failed to initialize SystemEfficiencyScore:', error);
    }
  }

  /**
   * Initialize Intelligent Alert Timeline component
   */
  function initAlertTimeline(unitId) {
    const container = document.getElementById('intelligent-alert-timeline-container');
    if (!container) return;

    try {
      if (typeof window.IntelligentAlertTimeline !== 'undefined') {
        alertTimeline = new window.IntelligentAlertTimeline('intelligent-alert-timeline-container', {
          unitId: unitId,
          maxItems: 10,
          autoRefresh: true,
          refreshInterval: 60000
        });
        alertTimeline.init();
        console.log('[Dashboard] IntelligentAlertTimeline initialized');
      } else if (typeof window.AlertTimeline !== 'undefined') {
        // Fallback to AlertTimeline component with action handlers
        alertTimeline = new window.AlertTimeline('intelligent-alert-timeline-container', {
          maxVisible: 10,
          showActions: true,
          onDismiss: handleAlertDismiss,
          onAction: handleAlertAction
        });
        
        // Add toolbar with clear all button
        addAlertToolbar(container);
        
        // Load initial alerts
        loadAndRenderAlerts(unitId);
        
        // Auto-refresh alerts (store ID for cleanup)
        alertRefreshInterval = setInterval(() => loadAndRenderAlerts(unitId), 60000);
        
        console.log('[Dashboard] AlertTimeline initialized with actions');
      } else {
        console.warn('[Dashboard] Alert Timeline components not available');
      }
    } catch (error) {
      console.error('[Dashboard] Failed to initialize Alert Timeline:', error);
    }
  }

  /**
   * Add toolbar with clear all button above alert timeline
   */
  function addAlertToolbar(container) {
    const toolbar = document.createElement('div');
    toolbar.className = 'alert-timeline-toolbar';
    toolbar.innerHTML = `
      <h3 class="section-title"><i class="fas fa-bell"></i> Alert Timeline</h3>
      <div class="toolbar-actions">
        <button class="btn btn-sm btn-secondary" id="refresh-alerts-btn" title="Refresh alerts">
          <i class="fas fa-sync-alt"></i> Refresh
        </button>
        <button class="btn btn-sm btn-danger" id="clear-all-alerts-btn" title="Clear all alerts">
          <i class="fas fa-trash-alt"></i> Clear All
        </button>
      </div>
    `;
    container.parentElement.insertBefore(toolbar, container);
    
    // Bind events
    document.getElementById('refresh-alerts-btn')?.addEventListener('click', () => {
      const unitId = document.querySelector('.page-shell')?.dataset?.selectedUnitId;
      loadAndRenderAlerts(unitId ? parseInt(unitId) : null);
    });
    
    document.getElementById('clear-all-alerts-btn')?.addEventListener('click', () => {
      if (confirm('Are you sure you want to clear all alerts? This action cannot be undone.')) {
        clearAllAlerts();
      }
    });
  }

  /**
   * Load alerts from API and render
   */
  async function loadAndRenderAlerts(unitId) {
    try {
      const options = { limit: 50 };
      if (unitId) options.unit_id = unitId;
      
      const data = await API.System.getAlerts(options);
      const alerts = data?.alerts || [];
      
      // Transform alerts to match AlertTimeline format
      const transformedAlerts = alerts.map(alert => ({
        id: alert.alert_id,
        severity: alert.severity || 'info',
        type: alert.alert_type || 'system',
        message: alert.title || alert.message || 'Alert',
        description: alert.message,
        timestamp: alert.timestamp,
        source: alert.source_type || 'system',
        source_name: alert.source_name,
        resolved: alert.resolved || false
      }));
      
      // Filter out resolved alerts
      const activeAlerts = transformedAlerts.filter(a => !a.resolved);
      
      if (alertTimeline && typeof alertTimeline.update === 'function') {
        alertTimeline.update(activeAlerts);
      }
    } catch (error) {
      console.error('[Dashboard] Failed to load alerts:', error);
    }
  }

  /**
   * Handle alert dismiss (resolve)
   */
  async function handleAlertDismiss(alertId) {
    try {
      await API.System.resolveAlert(alertId);
      console.log(`[Dashboard] Alert ${alertId} resolved`);
      // Refresh alerts
      const unitId = document.querySelector('.page-shell')?.dataset?.selectedUnitId;
      loadAndRenderAlerts(unitId ? parseInt(unitId) : null);
    } catch (error) {
      console.error('[Dashboard] Failed to resolve alert:', error);
      if (window.showNotification) {
        window.showNotification('Failed to resolve alert. Please try again.', 'error');
      }
    }
  }

  /**
   * Handle alert action button click
   */
  async function handleAlertAction(alertId, action) {
    console.log(`[Dashboard] Alert action: ${action} for alert ${alertId}`);
    
    switch (action) {
      case 'view':
      case 'details':
        // Navigate to relevant page based on alert type
        // For now, just log
        console.log(`View details for alert ${alertId}`);
        break;
      case 'calibrate':
        window.location.href = '/devices';
        break;
      case 'restart':
        window.location.href = '/devices';
        break;
      default:
        console.log(`Unknown action: ${action}`);
    }
  }

  /**
   * Clear all alerts
   */
  async function clearAllAlerts() {
    try {
      await API.System.clearAllAlerts();
      console.log('[Dashboard] All alerts cleared');
      // Clear timeline
      if (alertTimeline && typeof alertTimeline.clear === 'function') {
        alertTimeline.clear();
      }
      // Reload to confirm
      const unitId = document.querySelector('.page-shell')?.dataset?.selectedUnitId;
      setTimeout(() => loadAndRenderAlerts(unitId ? parseInt(unitId) : null), 500);
    } catch (error) {
      console.error('[Dashboard] Failed to clear all alerts:', error);
      if (window.showNotification) {
        window.showNotification('Failed to clear alerts. Please try again.', 'error');
      }
    }
  }

  window.addEventListener('beforeunload', () => {
    if (alertRefreshInterval) clearInterval(alertRefreshInterval);
    try { uiManager?.destroy?.(); } catch {}
    try { environmentalChart?.destroy?.(); } catch {}
    try { efficiencyScore?.destroy?.(); } catch {}
    try { alertTimeline?.destroy?.(); } catch {}
  });
})();
