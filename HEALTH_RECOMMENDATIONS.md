# Health Metrics & Dashboard Recommendations

## Current State Analysis

### ✅ What's Already Implemented

1. **Backend Health Endpoints** (Just Added)
   - `/api/health/ping` - Liveness check
   - `/api/health/system` - Complete system health
   - `/api/health/units` - All units summary
   - `/api/health/units/{unit_id}` - Detailed unit view
   - `/api/health/devices` - Device aggregation
   - `/api/health/sensors/{sensor_id}` - Sensor health
   - Real data from: SensorPollingService, ClimateController, EventBus, DeviceHealthService

2. **Frontend Integration**
   - `dashboard.js` already calls `/api/health/system`
   - KPI cards ready in `index.html`:
     * System Health Score
     * Active Devices Count
     * Healthy Plants Count
     * Critical Alerts Count
     * Energy Today

3. **Existing Metric Classes**
   - `SystemHealthReport` (HealthMonitoringService)
   - `ControlMetrics` (ControlLogic)
   - `SensorMetrics` (SensorPollingService)
   - `ClimateMetrics` (EnvironmentService)

---

## 🎯 Key Recommendations

### 1. **Update Dashboard JavaScript to Use New Endpoints**

**Current Issue:**
```javascript
// dashboard.js line 420
const response = await this.api.Insights.getSystemHealth();
// Expects: response.health.overall_score
```

**New Response Format:**
```javascript
{
  "data": {
    "status": "healthy|degraded|critical",
    "units": {...},
    "summary": {
      "total_units": 2,
      "healthy_units": 2
    }
  }
}
```

**Recommended Fix:**
Update `dashboard.js` lines 418-435 to:

```javascript
async loadSystemHealth() {
    try {
        const response = await this.api.Insights.getSystemHealth();
        
        if (response && response.data) {
            // Calculate overall health score from status
            const statusToScore = {
                'healthy': 90,
                'degraded': 60,
                'critical': 30,
                'unknown': 0
            };
            
            const score = statusToScore[response.data.status] || 0;
            const healthyPercent = response.data.summary.total_units > 0
                ? (response.data.summary.healthy_units / response.data.summary.total_units) * 100
                : 0;
            
            this.updateHealthScore({
                overall_score: Math.round(healthyPercent),
                status: response.data.status
            });
            
            // Update KPIs from real data
            this.updateKPIsFromHealth(response.data);
        }
    } catch (error) {
        console.error('Error loading health metrics:', error);
        this.updateHealthScore({
            overall_score: 0,
            status: 'Unknown'
        });
    }
}
```

---

### 2. **Add New Method to Update KPIs from Health Data**

**Add to `dashboard.js`:**

```javascript
/**
 * Update KPI cards from health data
 */
updateKPIsFromHealth(healthData) {
    // System Health Score (already handled by updateHealthScore)
    
    // Active Devices Count
    if (this.elements.activeDevicesCount) {
        let activeCount = 0;
        Object.values(healthData.units || {}).forEach(unit => {
            if (unit.hardware_running) {
                activeCount++;
            }
        });
        this.animateValue(
            this.elements.activeDevicesCount,
            parseInt(this.elements.activeDevicesCount.textContent) || 0,
            activeCount,
            300
        );
    }
    
    // Update KPI card status classes
    this.updateKPICardStatus('active-devices', healthData.summary);
    
    // Log for debugging
    console.log('📊 KPIs updated from health data:', healthData.summary);
}

/**
 * Update KPI card status class based on health
 */
updateKPICardStatus(cardId, summary) {
    const card = document.querySelector(`#${cardId}-count`)?.closest('.kpi-card');
    if (!card) return;
    
    // Remove existing status classes
    card.classList.remove('info', 'success', 'warning', 'danger');
    
    // Add appropriate class based on health
    if (summary.offline_units > 0) {
        card.classList.add('danger');
    } else if (summary.degraded_units > 0) {
        card.classList.add('warning');
    } else {
        card.classList.add('success');
    }
}
```

---

### 3. **Create Dedicated Health Service API Methods**

**Add to `api.js` (InsightsAPI section):**

```javascript
const HealthAPI = {
    /**
     * Get overall system health
     * @returns {Promise<Object>} System health with all units
     */
    getSystemHealth() {
        return get('/api/health/system');
    },
    
    /**
     * Get health summary for all units
     * @returns {Promise<Object>} Units health summary
     */
    getUnitsHealth() {
        return get('/api/health/units');
    },
    
    /**
     * Get detailed health for specific unit
     * @param {number} unitId - Unit ID
     * @returns {Promise<Object>} Unit health details
     */
    getUnitHealth(unitId) {
        return get(`/api/health/units/${unitId}`);
    },
    
    /**
     * Get aggregated device health
     * @returns {Promise<Object>} Device health across all units
     */
    getDevicesHealth() {
        return get('/api/health/devices');
    },
    
    /**
     * Basic liveness check
     * @returns {Promise<Object>} Ping response
     */
    ping() {
        return get('/api/health/ping');
    }
};

// Export
window.HealthAPI = HealthAPI;
```

**Update API export:**
```javascript
export const API = {
    // ... existing APIs
    Health: HealthAPI,
    Insights: InsightsAPI,
    // ...
};
```

---

### 4. **Enhance KPI Cards with Real Device Data**

**Add new method to load device health:**

```javascript
/**
 * Load device health metrics
 */
async loadDeviceHealth() {
    try {
        const response = await this.api.Health.getDevicesHealth();
        
        if (response && response.data) {
            const devices = response.data;
            
            // Active Devices Count
            if (this.elements.activeDevicesCount) {
                const activeDevices = devices.sensors.healthy + devices.actuators.operational;
                this.animateValue(
                    this.elements.activeDevicesCount,
                    parseInt(this.elements.activeDevicesCount.textContent) || 0,
                    activeDevices,
                    300
                );
            }
            
            // Critical Alerts Count (devices with issues)
            if (this.elements.criticalAlertsCount) {
                const criticalCount = devices.sensors.offline + devices.actuators.failed;
                this.animateValue(
                    this.elements.criticalAlertsCount,
                    parseInt(this.elements.criticalAlertsCount.textContent) || 0,
                    criticalCount,
                    300
                );
                
                // Update card status
                const alertCard = this.elements.criticalAlertsCount.closest('.kpi-card');
                if (alertCard) {
                    alertCard.classList.remove('success', 'warning', 'danger');
                    if (criticalCount === 0) {
                        alertCard.classList.add('success');
                    } else if (criticalCount < 3) {
                        alertCard.classList.add('warning');
                    } else {
                        alertCard.classList.add('danger');
                    }
                }
            }
        }
    } catch (error) {
        console.error('Error loading device health:', error);
    }
}
```

**Call in `loadAllData()`:**
```javascript
loadAllData() {
    return Promise.all([
        this.loadRecentSensors(),
        this.loadSystemHealth(),
        this.loadDeviceHealth(), // NEW
        this.loadPlantHealth(),  // NEW (see below)
        this.loadRecentActivity(),
        this.loadCriticalAlerts(),
        this.loadRecentStates(),
        this.loadConnectivityEvents()
    ]);
}
```

---

### 5. **Add Plant Health Integration**

**New method:**

```javascript
/**
 * Load plant health metrics
 */
async loadPlantHealth() {
    try {
        const response = await this.api.get('/api/health/plants/summary');
        
        if (response && response.data && response.data.plants) {
            const plants = response.data.plants;
            const healthyCount = plants.filter(p => 
                p.current_health_status === 'healthy'
            ).length;
            
            // Update Healthy Plants Count
            if (this.elements.healthyPlantsCount) {
                this.animateValue(
                    this.elements.healthyPlantsCount,
                    parseInt(this.elements.healthyPlantsCount.textContent) || 0,
                    healthyCount,
                    300
                );
            }
            
            // Update plant cards in the UI
            plants.forEach(plant => {
                const plantCard = document.querySelector(`[data-plant-id="${plant.plant_id}"]`);
                if (plantCard) {
                    const moistureElement = plantCard.querySelector(`#moisture-${plant.plant_id}`);
                    if (moistureElement && plant.current_moisture) {
                        moistureElement.textContent = `${plant.current_moisture}%`;
                    }
                }
            });
        }
    } catch (error) {
        console.error('Error loading plant health:', error);
    }
}
```

---

### 6. **Add Health Monitoring Interval**

**Update periodic updates to include health checks:**

```javascript
startPeriodicUpdates() {
    // Existing sensor updates every 5 seconds
    this.updateInterval = setInterval(() => {
        this.loadRecentSensors();
    }, 5000);
    
    // Health metrics every 30 seconds
    this.healthInterval = setInterval(() => {
        this.loadSystemHealth();
        this.loadDeviceHealth();
    }, 30000);
    
    // Plant health every 60 seconds
    this.plantHealthInterval = setInterval(() => {
        this.loadPlantHealth();
    }, 60000);
}

// Update cleanup
destroy() {
    if (this.updateInterval) {
        clearInterval(this.updateInterval);
    }
    if (this.healthInterval) {
        clearInterval(this.healthInterval);
    }
    if (this.plantHealthInterval) {
        clearInterval(this.plantHealthInterval);
    }
    // ... existing cleanup
}
```

---

### 7. **Add Visual Health Status Indicators**

**Update HTML for better status visualization:**

```html
<!-- Add status badge to unit switcher -->
<div class="filter-group">
    <label class="muted" for="unit-switcher">Growth unit</label>
    <div class="flex gap-2 align-center">
        <select id="unit-switcher" name="unit_id" class="form-select">
            <!-- options -->
        </select>
        <span id="unit-health-badge" class="badge badge-success" style="display: none;">
            ● Healthy
        </span>
    </div>
</div>
```

**Add JavaScript to update badge:**

```javascript
updateUnitHealthBadge(status) {
    const badge = document.getElementById('unit-health-badge');
    if (!badge) return;
    
    badge.style.display = 'inline-block';
    badge.className = 'badge';
    
    switch (status) {
        case 'healthy':
            badge.classList.add('badge-success');
            badge.innerHTML = '● Healthy';
            break;
        case 'degraded':
            badge.classList.add('badge-warning');
            badge.innerHTML = '⚠ Degraded';
            break;
        case 'offline':
        case 'critical':
            badge.classList.add('badge-danger');
            badge.innerHTML = '✗ Offline';
            break;
        default:
            badge.style.display = 'none';
    }
}
```

---

### 8. **Create System Health Overview Modal**

**Add modal HTML at end of index.html:**

```html
<!-- System Health Modal -->
<div id="health-modal" class="modal" style="display: none;">
    <div class="modal-content">
        <div class="modal-header">
            <h2>System Health Details</h2>
            <button class="btn-close" onclick="closeHealthModal()">×</button>
        </div>
        <div class="modal-body">
            <div id="health-modal-content">
                Loading...
            </div>
        </div>
    </div>
</div>
```

**Add click handler to health KPI card:**

```javascript
// In init() method
const healthCard = document.querySelector('#health-score-value')?.closest('.kpi-card');
if (healthCard) {
    healthCard.style.cursor = 'pointer';
    healthCard.addEventListener('click', () => this.showHealthModal());
}

async showHealthModal() {
    const modal = document.getElementById('health-modal');
    const content = document.getElementById('health-modal-content');
    
    if (!modal || !content) return;
    
    modal.style.display = 'flex';
    content.innerHTML = '<div class="spinner">Loading...</div>';
    
    try {
        const health = await this.api.Health.getSystemHealth();
        
        if (health && health.data) {
            content.innerHTML = this.renderHealthDetails(health.data);
        }
    } catch (error) {
        content.innerHTML = '<p class="error">Failed to load health details</p>';
    }
}

renderHealthDetails(healthData) {
    return `
        <div class="health-summary">
            <div class="health-status ${healthData.status}">
                <h3>Overall Status: ${healthData.status.toUpperCase()}</h3>
            </div>
            
            <div class="health-stats">
                <div class="stat">
                    <span class="stat-label">Total Units</span>
                    <span class="stat-value">${healthData.summary.total_units}</span>
                </div>
                <div class="stat">
                    <span class="stat-label">Healthy</span>
                    <span class="stat-value success">${healthData.summary.healthy_units}</span>
                </div>
                <div class="stat">
                    <span class="stat-label">Degraded</span>
                    <span class="stat-value warning">${healthData.summary.degraded_units}</span>
                </div>
                <div class="stat">
                    <span class="stat-label">Offline</span>
                    <span class="stat-value danger">${healthData.summary.offline_units}</span>
                </div>
            </div>
            
            <h4>Unit Details</h4>
            <div class="units-list">
                ${Object.values(healthData.units).map(unit => `
                    <div class="unit-card ${unit.status}">
                        <h5>${unit.name}</h5>
                        <p>Status: <span class="badge badge-${unit.status}">${unit.status}</span></p>
                        <p>Hardware: ${unit.hardware_running ? '✓ Running' : '✗ Stopped'}</p>
                        ${unit.controller?.stale_sensors?.length > 0 ? 
                            `<p class="warning">⚠ ${unit.controller.stale_sensors.length} stale sensors</p>` 
                            : ''
                        }
                    </div>
                `).join('')}
            </div>
            
            <h4>Event Bus Metrics</h4>
            <div class="metrics-grid">
                <div class="metric">
                    <span class="metric-label">Queue Depth</span>
                    <span class="metric-value">${healthData.event_bus.queue_depth}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Subscribers</span>
                    <span class="metric-value">${healthData.event_bus.subscribers}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Dropped Events</span>
                    <span class="metric-value">${healthData.event_bus.dropped_events}</span>
                </div>
            </div>
        </div>
    `;
}
```

---

## 📊 Summary of Changes Needed

### Immediate (High Priority)

1. ✅ **Backend Health Endpoints** - DONE
2. 🔨 **Update `dashboard.js` loadSystemHealth()** - Parse new response format
3. 🔨 **Add `updateKPIsFromHealth()` method** - Use real health data
4. 🔨 **Add `loadDeviceHealth()` method** - Populate device counts
5. 🔨 **Add `loadPlantHealth()` method** - Show plant health status

### Enhancement (Medium Priority)

6. 📝 **Create HealthAPI in `api.js`** - Dedicated health methods
7. 📝 **Add health monitoring intervals** - Every 30 seconds
8. 📝 **Update KPI card status classes** - Visual feedback based on health

### Polish (Low Priority)

9. 🎨 **Add unit health badge** - Show status next to unit selector
10. 🎨 **Create health modal** - Detailed drill-down view
11. 🎨 **Add stale sensor warnings** - Visual indicators for degraded sensors

---

## 🚀 Implementation Priority

**Phase 1: Core Integration (30 min)**
- Update dashboard.js to use new health endpoints
- Add methods for device and plant health
- Update KPI cards with real data

**Phase 2: Enhanced Monitoring (20 min)**
- Add dedicated HealthAPI in api.js
- Implement periodic health checks
- Add status badge to UI

**Phase 3: Polish & UX (30 min)**
- Create health detail modal
- Add visual status indicators
- Improve error handling

**Total Estimated Time: 1.5 hours**

---

## 🔍 Testing Checklist

- [ ] System health loads on dashboard
- [ ] KPI cards update with real counts
- [ ] Device health shows online/offline status
- [ ] Plant health displays correctly
- [ ] Health updates every 30 seconds
- [ ] Status badges show correct colors
- [ ] Health modal displays detailed info
- [ ] Error handling works gracefully

---

## 📚 Additional Resources

- **Backend Doc**: `HEALTH_API_ENDPOINTS.md`
- **Health Service**: `app/services/utilities/health_monitoring_service.py`
- **Control Metrics**: `app/services/hardware/control_logic.py`
- **Sensor Metrics**: `app/services/hardware/sensor_polling_service.py`

All the backend infrastructure is in place and returning real data. The frontend just needs to be updated to consume the new endpoints properly!
