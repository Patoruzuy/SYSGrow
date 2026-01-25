# Frontend Implementation Plan for New Features

## Executive Summary
This document outlines the comprehensive plan to integrate all new backend features developed today into the frontend UI. The plan covers plant health monitoring, energy analytics, device health monitoring, failure predictions, and sensor statistics.

---

## 📊 Current State Assessment

### ✅ Completed Backend Work
- **ThresholdService**: Unified threshold management with AI integration
- **PlantHealthMonitor**: Health tracking with environmental correlations
- **API Endpoints**: 155 documented endpoints across 11 API modules
- **API.js**: Complete frontend API client (1800+ lines, all paths updated)

### 🎨 Current Frontend Architecture
- **Template Engine**: Jinja2 with Flask
- **Real-time Updates**: Socket.io integration (base.html)
- **Charting**: Chart.js (dashboard.html)
- **Navigation**: 4 sections - Dashboard, Plant Management, Monitoring, Configuration
- **Styling**: Modern responsive design with CSS Grid/Flexbox
- **Current Pages**: 23 templates (dashboard, units, devices, add_plant, sensor_data, etc.)

### 🆕 New Features Requiring Frontend Integration

#### 1. **Plant Health Monitoring** (8 new endpoints)
   - Record health observations
   - View health history with filtering
   - Get health recommendations
   - Display available symptoms
   - Show health status indicators

#### 2. **Energy Analytics Dashboard** (InsightsAPI - 16 endpoints)
   - Actuator energy consumption tracking
   - Cost trend analysis
   - Failure prediction alerts
   - Energy efficiency metrics
   - Power usage visualizations

#### 3. **Device Health Monitoring** (DeviceAPI expansion - 40+ new endpoints)
   - Device health status indicators
   - Anomaly detection alerts
   - Connectivity monitoring
   - Device statistics
   - Zigbee2MQTT integration

#### 4. **Sensor Analytics** (InsightsAPI)
   - Advanced sensor statistics
   - Historical data analysis
   - Sensor health indicators
   - Data quality metrics

#### 5. **System Dashboards**
   - Comprehensive overview dashboard
   - Energy summary
   - Health summary
   - Predictive maintenance alerts

---

## 🎯 Implementation Strategy

### Phase 1: Navigation & Structure Updates (2-3 hours)
**Goal**: Add new navigation items and page scaffolds

#### 1.1 Update `base.html` Navigation
**Location**: `templates/base.html` - Sidebar navigation section

**Changes Needed**:
```html
<!-- Add new section between "Monitoring" and "Configuration" -->
<nav class="sidebar-section">
    <h3 class="sidebar-section-title">Analytics & Health</h3>
    <ul class="sidebar-menu">
        <li>
            <a href="{{ url_for('ui.plant_health') }}" class="sidebar-link">
                <i class="fas fa-heartbeat"></i>
                <span>Plant Health</span>
            </a>
        </li>
        <li>
            <a href="{{ url_for('ui.energy_analytics') }}" class="sidebar-link">
                <i class="fas fa-bolt"></i>
                <span>Energy Analytics</span>
            </a>
        </li>
        <li>
            <a href="{{ url_for('ui.device_health') }}" class="sidebar-link">
                <i class="fas fa-microchip"></i>
                <span>Device Health</span>
            </a>
        </li>
        <li>
            <a href="{{ url_for('ui.sensor_analytics') }}" class="sidebar-link">
                <i class="fas fa-chart-area"></i>
                <span>Sensor Analytics</span>
            </a>
        </li>
    </ul>
</nav>
```

**Update existing "Monitoring" section**:
- Add badge indicators for alerts/anomalies
- Update "System Status" to show predictions

#### 1.2 Create Flask Routes (Backend)
**Location**: `app/blueprints/ui/__init__.py` or create new `app/blueprints/ui/analytics.py`

**New Routes Needed**:
```python
@ui_blueprint.route('/plant-health')
def plant_health():
    """Plant health monitoring dashboard"""
    return render_template('plant_health.html')

@ui_blueprint.route('/energy-analytics')
def energy_analytics():
    """Energy analytics and cost tracking"""
    return render_template('energy_analytics.html')

@ui_blueprint.route('/device-health')
def device_health():
    """Device health monitoring and diagnostics"""
    return render_template('device_health.html')

@ui_blueprint.route('/sensor-analytics')
def sensor_analytics():
    """Advanced sensor statistics and analysis"""
    return render_template('sensor_analytics.html')

@ui_blueprint.route('/system-overview')
def system_overview():
    """Comprehensive system dashboard"""
    return render_template('system_overview.html')
```

---

### Phase 2: Plant Health Monitoring Pages (4-6 hours)

#### 2.1 Create `plant_health.html`
**Purpose**: Main plant health monitoring dashboard

**Template Structure**:
```html
{% extends 'base.html' %}

{% block content %}
<div class="main-content">
    <div class="dashboard-header">
        <h1 class="dashboard-title">🌿 Plant Health Monitoring</h1>
        <div class="header-actions">
            <button onclick="openRecordObservationModal()" class="btn btn-primary">
                <i class="fas fa-plus"></i> Record Observation
            </button>
            <button onclick="refreshHealthData()" class="btn btn-outline">
                <i class="fas fa-sync"></i> Refresh
            </button>
        </div>
    </div>

    <!-- Health Status Overview Cards -->
    <section class="stats-grid" id="health-overview">
        <div class="stat-card healthy">
            <div class="stat-icon">✅</div>
            <div class="stat-content">
                <div class="stat-value" id="healthy-count">0</div>
                <div class="stat-label">Healthy Plants</div>
            </div>
        </div>
        <div class="stat-card warning">
            <div class="stat-icon">⚠️</div>
            <div class="stat-content">
                <div class="stat-value" id="stressed-count">0</div>
                <div class="stat-label">Stressed Plants</div>
            </div>
        </div>
        <div class="stat-card danger">
            <div class="stat-icon">🔴</div>
            <div class="stat-content">
                <div class="stat-value" id="diseased-count">0</div>
                <div class="stat-label">Diseased Plants</div>
            </div>
        </div>
        <div class="stat-card info">
            <div class="stat-icon">📊</div>
            <div class="stat-content">
                <div class="stat-value" id="observations-count">0</div>
                <div class="stat-label">Total Observations</div>
            </div>
        </div>
    </section>

    <!-- Plants Health Status Grid -->
    <section class="management-section">
        <h2 class="section-title">
            <i class="fas fa-leaf"></i> Plants by Health Status
        </h2>
        
        <div class="filter-controls">
            <select id="health-status-filter" onchange="filterByHealthStatus()">
                <option value="all">All Statuses</option>
                <option value="healthy">Healthy</option>
                <option value="stressed">Stressed</option>
                <option value="diseased">Diseased</option>
                <option value="recovering">Recovering</option>
            </select>
            
            <select id="unit-filter" onchange="filterByHealthStatus()">
                <option value="all">All Units</option>
                <!-- Populated dynamically -->
            </select>
        </div>

        <div class="plants-health-grid" id="plants-health-grid">
            <!-- Populated dynamically via JavaScript -->
        </div>
    </section>

    <!-- Recent Health Observations -->
    <section class="management-section">
        <h2 class="section-title">
            <i class="fas fa-history"></i> Recent Health Observations
        </h2>
        
        <div class="table-container">
            <table class="modern-table" id="health-observations-table">
                <thead>
                    <tr>
                        <th>Timestamp</th>
                        <th>Plant</th>
                        <th>Status</th>
                        <th>Symptoms</th>
                        <th>Severity</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody id="observations-tbody">
                    <!-- Populated dynamically -->
                </tbody>
            </table>
        </div>
    </section>

    <!-- Health Recommendations Panel -->
    <section class="management-section">
        <h2 class="section-title">
            <i class="fas fa-lightbulb"></i> Health Recommendations
        </h2>
        
        <div id="recommendations-container" class="recommendations-grid">
            <!-- Populated dynamically -->
        </div>
    </section>
</div>

<!-- Record Observation Modal -->
<div class="modal" id="recordObservationModal">
    <div class="modal-content">
        <div class="modal-header">
            <h2>Record Health Observation</h2>
            <button class="modal-close" onclick="closeModal('recordObservationModal')">&times;</button>
        </div>
        <form id="recordObservationForm">
            <div class="form-group">
                <label>Select Plant</label>
                <select id="observation-plant-id" name="plant_id" required>
                    <!-- Populated dynamically -->
                </select>
            </div>
            
            <div class="form-group">
                <label>Health Status</label>
                <select id="observation-status" name="status" required>
                    <option value="healthy">Healthy</option>
                    <option value="stressed">Stressed</option>
                    <option value="diseased">Diseased</option>
                    <option value="recovering">Recovering</option>
                </select>
            </div>
            
            <div class="form-group">
                <label>Symptoms (select multiple)</label>
                <select id="observation-symptoms" name="symptoms" multiple size="6">
                    <!-- Populated dynamically via API.Plant.getAvailableSymptoms() -->
                </select>
            </div>
            
            <div class="form-group">
                <label>Severity</label>
                <input type="range" id="observation-severity" name="severity" min="1" max="5" value="3">
                <span id="severity-value">3</span>
            </div>
            
            <div class="form-group">
                <label>Notes</label>
                <textarea id="observation-notes" name="notes" rows="4"></textarea>
            </div>
            
            <div class="form-actions">
                <button type="button" class="btn btn-outline" onclick="closeModal('recordObservationModal')">Cancel</button>
                <button type="submit" class="btn btn-primary">Save Observation</button>
            </div>
        </form>
    </div>
</div>
{% endblock %}

{% block scripts %}
<script src="{{ url_for('static', filename='js/plant_health.js') }}"></script>
{% endblock %}
```

#### 2.2 Create `plant_health.js`
**Location**: `static/js/plant_health.js`

**Key Functions**:
```javascript
// Load all health data
async function loadHealthData() {
    try {
        // Get all plants with their health status
        const plantsResponse = await API.Plant.getAllPlants();
        const plants = plantsResponse.data;
        
        // Get health statuses
        const healthStatuses = await Promise.all(
            plants.map(plant => API.Plant.getHealthStatus(plant.id))
        );
        
        // Update overview cards
        updateHealthOverview(healthStatuses);
        
        // Populate plants health grid
        populatePlantsHealthGrid(plants, healthStatuses);
        
        // Load recent observations
        await loadRecentObservations();
        
    } catch (error) {
        console.error('Failed to load health data:', error);
        showToast('Failed to load health data', 'error');
    }
}

// Record new health observation
async function recordObservation(event) {
    event.preventDefault();
    const formData = new FormData(event.target);
    
    const observationData = {
        plant_id: parseInt(formData.get('plant_id')),
        status: formData.get('status'),
        symptoms: Array.from(formData.getAll('symptoms')),
        severity: parseInt(formData.get('severity')),
        notes: formData.get('notes'),
        environmental_conditions: await getCurrentEnvironmentalData()
    };
    
    try {
        await API.Plant.recordHealthObservation(
            observationData.plant_id, 
            observationData
        );
        
        showToast('Health observation recorded successfully', 'success');
        closeModal('recordObservationModal');
        loadHealthData(); // Refresh
        
    } catch (error) {
        showToast('Failed to record observation', 'error');
    }
}

// Get health recommendations for a plant
async function showRecommendations(plantId) {
    try {
        const response = await API.Plant.getHealthRecommendations(plantId);
        const recommendations = response.data;
        
        displayRecommendationsModal(recommendations);
        
    } catch (error) {
        showToast('Failed to load recommendations', 'error');
    }
}

// View health history for a plant
async function viewHealthHistory(plantId) {
    try {
        const response = await API.Plant.getHealthHistory(plantId);
        const history = response.data;
        
        // Open modal with history chart
        displayHealthHistoryModal(plantId, history);
        
    } catch (error) {
        showToast('Failed to load health history', 'error');
    }
}

// Initialize page
document.addEventListener('DOMContentLoaded', function() {
    loadHealthData();
    loadAvailableSymptoms();
    loadUnitsForFilter();
    
    // Setup form handlers
    document.getElementById('recordObservationForm')
        .addEventListener('submit', recordObservation);
    
    // Severity slider
    document.getElementById('observation-severity')
        .addEventListener('input', function() {
            document.getElementById('severity-value').textContent = this.value;
        });
    
    // Auto-refresh every 5 minutes
    setInterval(loadHealthData, 300000);
});
```

#### 2.3 Create `plant_health_history.html`
**Purpose**: Detailed health history view for a specific plant

**Features**:
- Timeline visualization of health observations
- Environmental correlation charts
- Symptom progression tracking
- Treatment effectiveness analysis

---

### Phase 3: Energy Analytics Dashboard (4-6 hours)

#### 3.1 Create `energy_analytics.html`

**Template Structure**:
```html
{% extends 'base.html' %}

{% block content %}
<div class="main-content">
    <div class="dashboard-header">
        <h1 class="dashboard-title">⚡ Energy Analytics & Cost Tracking</h1>
    </div>

    <!-- Energy Summary Cards -->
    <section class="stats-grid" id="energy-overview">
        <div class="stat-card primary">
            <div class="stat-icon">⚡</div>
            <div class="stat-content">
                <div class="stat-value" id="total-consumption">-- kWh</div>
                <div class="stat-label">Total Consumption</div>
                <div class="stat-trend" id="consumption-trend">--</div>
            </div>
        </div>
        <div class="stat-card success">
            <div class="stat-icon">💰</div>
            <div class="stat-content">
                <div class="stat-value" id="total-cost">$--</div>
                <div class="stat-label">Total Cost</div>
                <div class="stat-trend" id="cost-trend">--</div>
            </div>
        </div>
        <div class="stat-card warning">
            <div class="stat-icon">📊</div>
            <div class="stat-content">
                <div class="stat-value" id="avg-efficiency">--%</div>
                <div class="stat-label">Efficiency</div>
            </div>
        </div>
        <div class="stat-card danger">
            <div class="stat-icon">⚠️</div>
            <div class="stat-content">
                <div class="stat-value" id="predictions-count">0</div>
                <div class="stat-label">Failure Predictions</div>
            </div>
        </div>
    </section>

    <!-- Energy Dashboard Charts -->
    <section class="management-section">
        <h2 class="section-title">
            <i class="fas fa-chart-line"></i> Energy Consumption Over Time
        </h2>
        
        <div class="chart-controls">
            <select id="timeframe-selector" onchange="updateEnergyCharts()">
                <option value="24h">Last 24 Hours</option>
                <option value="7d" selected>Last 7 Days</option>
                <option value="30d">Last 30 Days</option>
                <option value="90d">Last 90 Days</option>
            </select>
            
            <button onclick="exportEnergyData()" class="btn btn-outline">
                <i class="fas fa-download"></i> Export Data
            </button>
        </div>

        <div class="chart-container">
            <canvas id="energy-consumption-chart"></canvas>
        </div>
    </section>

    <!-- Actuator Energy Breakdown -->
    <section class="management-section">
        <h2 class="section-title">
            <i class="fas fa-bolt"></i> Energy by Actuator
        </h2>
        
        <div class="actuators-grid" id="actuators-energy-grid">
            <!-- Populated dynamically -->
        </div>
    </section>

    <!-- Cost Trends Analysis -->
    <section class="management-section">
        <h2 class="section-title">
            <i class="fas fa-dollar-sign"></i> Cost Trends & Predictions
        </h2>
        
        <div class="chart-container">
            <canvas id="cost-trends-chart"></canvas>
        </div>
        
        <div class="cost-breakdown" id="cost-breakdown">
            <!-- Cost breakdown table -->
        </div>
    </section>

    <!-- Failure Predictions -->
    <section class="management-section">
        <h2 class="section-title">
            <i class="fas fa-exclamation-triangle"></i> Predictive Maintenance Alerts
        </h2>
        
        <div class="predictions-list" id="predictions-list">
            <!-- Populated dynamically -->
        </div>
    </section>
</div>
{% endblock %}

{% block scripts %}
<script src="{{ url_for('static', filename='js/energy_analytics.js') }}"></script>
{% endblock %}
```

#### 3.2 Create `energy_analytics.js`

**Key Functions**:
```javascript
// Load energy dashboard data
async function loadEnergyDashboard() {
    try {
        // Get actuator energy dashboard
        const dashboard = await API.Insights.getActuatorEnergyDashboard();
        
        // Update overview cards
        updateEnergyOverview(dashboard.data);
        
        // Load consumption chart
        await loadEnergyConsumptionChart();
        
        // Load cost trends
        await loadCostTrends();
        
        // Load failure predictions
        await loadFailurePredictions();
        
    } catch (error) {
        console.error('Failed to load energy dashboard:', error);
        showToast('Failed to load energy data', 'error');
    }
}

// Create energy consumption chart
async function loadEnergyConsumptionChart() {
    const timeframe = document.getElementById('timeframe-selector').value;
    
    try {
        // Get energy data for timeframe
        const response = await API.Insights.getActuatorEnergyDashboard(timeframe);
        const data = response.data;
        
        const ctx = document.getElementById('energy-consumption-chart').getContext('2d');
        new Chart(ctx, {
            type: 'line',
            data: {
                labels: data.timestamps,
                datasets: data.actuators.map((actuator, index) => ({
                    label: actuator.name,
                    data: actuator.consumption,
                    borderColor: CHART_COLORS[index],
                    backgroundColor: CHART_COLORS_ALPHA[index],
                    tension: 0.4
                }))
            },
            options: {
                responsive: true,
                plugins: {
                    title: {
                        display: true,
                        text: 'Energy Consumption by Actuator'
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                return context.dataset.label + ': ' + 
                                       context.parsed.y.toFixed(2) + ' kWh';
                            }
                        }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        title: {
                            display: true,
                            text: 'Energy (kWh)'
                        }
                    }
                }
            }
        });
        
    } catch (error) {
        console.error('Failed to load consumption chart:', error);
    }
}

// Load cost trends
async function loadCostTrends() {
    try {
        const response = await API.Insights.getActuatorCostTrends();
        const trends = response.data;
        
        // Create cost trend chart
        const ctx = document.getElementById('cost-trends-chart').getContext('2d');
        new Chart(ctx, {
            type: 'bar',
            data: {
                labels: trends.periods,
                datasets: [{
                    label: 'Actual Cost',
                    data: trends.actual_costs,
                    backgroundColor: 'rgba(59, 130, 246, 0.7)'
                }, {
                    label: 'Predicted Cost',
                    data: trends.predicted_costs,
                    backgroundColor: 'rgba(251, 146, 60, 0.7)'
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    title: {
                        display: true,
                        text: 'Cost Trends Analysis'
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        title: {
                            display: true,
                            text: 'Cost ($)'
                        }
                    }
                }
            }
        });
        
        // Populate cost breakdown
        populateCostBreakdown(trends);
        
    } catch (error) {
        console.error('Failed to load cost trends:', error);
    }
}

// Load failure predictions
async function loadFailurePredictions() {
    try {
        const actuators = await API.Device.listActuators();
        const predictions = [];
        
        for (const actuator of actuators.data) {
            const prediction = await API.Insights.predictActuatorFailure(actuator.id);
            if (prediction.data.risk_level !== 'low') {
                predictions.push({
                    actuator: actuator,
                    prediction: prediction.data
                });
            }
        }
        
        displayFailurePredictions(predictions);
        
    } catch (error) {
        console.error('Failed to load predictions:', error);
    }
}

// Initialize
document.addEventListener('DOMContentLoaded', function() {
    loadEnergyDashboard();
    
    // Auto-refresh every 5 minutes
    setInterval(loadEnergyDashboard, 300000);
});
```

---

### Phase 4: Device Health Monitoring (3-4 hours)

#### 4.1 Update `devices.html`

**Add health indicators to existing device tables**:
```html
<!-- Update Active Actuators Table -->
<table class="devices-table">
    <thead>
        <tr>
            <th>ID</th>
            <th>Name</th>
            <th>Health</th> <!-- NEW -->
            <th>Status</th> <!-- NEW -->
            <th>PIN</th>
            <th>IP Address</th>
            <th>Actions</th>
        </tr>
    </thead>
    <tbody>
        {% for data in db_actuators %}
        <tr data-device-id="{{ data.id }}">
            <td>{{ data.id }}</td>
            <td>{{ data.name }}</td>
            <td>
                <span class="health-badge" id="health-{{ data.id }}">
                    <i class="fas fa-spinner fa-spin"></i>
                </span>
            </td>
            <td>
                <span class="status-badge" id="status-{{ data.id }}">--</span>
            </td>
            <td>{{ data.gpio }}</td>
            <td>{{ data.ip_address or '-' }}</td>
            <td>
                <div class="action-buttons">
                    <button class="btn-action btn-info" onclick="showDeviceDetails('{{ data.id }}')">
                        Details
                    </button>
                    <button class="btn-action btn-on" onclick="controlActuator('{{ data.actuator_type }}', 'activate')">On</button>
                    <button class="btn-action btn-off" onclick="controlActuator('{{ data.actuator_type }}', 'deactivate')">Off</button>
                    <button class="btn-action btn-remove" onclick="removeActuator('{{ data.name }}')">Remove</button>
                </div>
            </td>
        </tr>
        {% endfor %}
    </tbody>
</table>
```

**Add JavaScript for health monitoring**:
```javascript
// Load device health status
async function loadDeviceHealthStatus() {
    try {
        const actuators = await API.Device.listActuators();
        
        for (const actuator of actuators.data) {
            const health = await API.Device.getDeviceHealth(actuator.id);
            updateDeviceHealthBadge(actuator.id, health.data);
            
            // Check for anomalies
            const anomalies = await API.Device.detectAnomalies(actuator.id, {
                window_minutes: 60
            });
            
            if (anomalies.data.anomalies_detected) {
                showAnomalyAlert(actuator.id, anomalies.data);
            }
        }
        
    } catch (error) {
        console.error('Failed to load device health:', error);
    }
}

// Update health badge
function updateDeviceHealthBadge(deviceId, healthData) {
    const badge = document.getElementById(`health-${deviceId}`);
    const statusBadge = document.getElementById(`status-${deviceId}`);
    
    if (!badge || !statusBadge) return;
    
    // Health indicator
    const healthClass = healthData.status === 'healthy' ? 'success' :
                       healthData.status === 'degraded' ? 'warning' : 'danger';
    
    badge.className = `health-badge badge-${healthClass}`;
    badge.innerHTML = `<i class="fas fa-${healthData.status === 'healthy' ? 'check' : 'exclamation'}"></i> ${healthData.status}`;
    
    // Connection status
    const isOnline = healthData.last_seen_minutes < 5;
    statusBadge.className = `status-badge badge-${isOnline ? 'success' : 'secondary'}`;
    statusBadge.textContent = isOnline ? 'Online' : 'Offline';
}

// Show device details modal
async function showDeviceDetails(deviceId) {
    try {
        const health = await API.Device.getDeviceHealth(deviceId);
        const stats = await API.Device.getDeviceStatistics(deviceId, {
            hours: 24
        });
        
        // Open modal with details
        displayDeviceDetailsModal(deviceId, health.data, stats.data);
        
    } catch (error) {
        showToast('Failed to load device details', 'error');
    }
}
```

#### 4.2 Create `device_health.html`

**Purpose**: Dedicated device health monitoring dashboard

**Key Sections**:
- Device health overview cards
- Anomaly detection alerts
- Device uptime statistics
- Power consumption per device
- Connectivity history
- Maintenance schedule

---

### Phase 5: Sensor Analytics Dashboard (3-4 hours)

#### 5.1 Update `sensor_data.html`

**Add advanced analytics section**:
```html
<!-- Add after existing sensor data table -->
<section class="management-section">
    <h2 class="section-title">
        <i class="fas fa-chart-area"></i> Sensor Analytics
    </h2>
    
    <!-- Sensor Selection -->
    <div class="form-group">
        <label>Select Sensor for Analysis:</label>
        <select id="sensor-analytics-selector" onchange="loadSensorAnalytics()">
            <!-- Populated dynamically -->
        </select>
    </div>
    
    <!-- Statistics Cards -->
    <div class="stats-grid" id="sensor-stats-grid">
        <div class="stat-card">
            <div class="stat-label">Average</div>
            <div class="stat-value" id="sensor-avg">--</div>
        </div>
        <div class="stat-card">
            <div class="stat-label">Min/Max</div>
            <div class="stat-value" id="sensor-range">--</div>
        </div>
        <div class="stat-card">
            <div class="stat-label">Std Deviation</div>
            <div class="stat-value" id="sensor-stddev">--</div>
        </div>
        <div class="stat-card">
            <div class="stat-label">Data Quality</div>
            <div class="stat-value" id="sensor-quality">--%</div>
        </div>
    </div>
    
    <!-- Analytics Chart -->
    <div class="chart-container">
        <canvas id="sensor-analytics-chart"></canvas>
    </div>
</section>
```

**JavaScript implementation**:
```javascript
async function loadSensorAnalytics() {
    const sensorId = document.getElementById('sensor-analytics-selector').value;
    if (!sensorId) return;
    
    try {
        // Get sensor statistics
        const stats = await API.Insights.getSensorStatistics(sensorId, {
            hours: 24
        });
        
        // Update statistics cards
        document.getElementById('sensor-avg').textContent = 
            stats.data.average.toFixed(2);
        document.getElementById('sensor-range').textContent = 
            `${stats.data.min.toFixed(2)} - ${stats.data.max.toFixed(2)}`;
        document.getElementById('sensor-stddev').textContent = 
            stats.data.std_deviation.toFixed(2);
        document.getElementById('sensor-quality').textContent = 
            `${(stats.data.data_quality * 100).toFixed(1)}%`;
        
        // Create analytics chart
        await createSensorAnalyticsChart(sensorId, stats.data);
        
    } catch (error) {
        console.error('Failed to load sensor analytics:', error);
        showToast('Failed to load sensor analytics', 'error');
    }
}
```

---

### Phase 6: System Overview Dashboard (2-3 hours)

#### 6.1 Create `system_overview.html`

**Purpose**: Comprehensive system health and analytics dashboard

**Key Sections**:
1. **System Health Summary**
   - Overall system health score
   - Active alerts count
   - System uptime
   - Resource utilization

2. **Quick Stats Grid**
   - Total energy consumption (today/week/month)
   - Number of healthy/stressed/diseased plants
   - Active devices count
   - Failed predictions count

3. **Real-time Monitoring**
   - Live sensor readings
   - Active actuators status
   - Current environmental conditions

4. **Recent Activity Feed**
   - Health observations
   - Anomaly detections
   - System events
   - User actions

5. **Predictive Insights**
   - Upcoming maintenance
   - Energy cost predictions
   - Plant health trends
   - Resource optimization suggestions

---

### Phase 7: Existing Page Updates (2-3 hours)

#### 7.1 Update `dashboard.html`

**Add alert indicators**:
```html
<!-- Add at top of dashboard -->
<section class="alerts-banner" id="alerts-banner" style="display: none;">
    <div class="alert-item critical">
        <i class="fas fa-exclamation-circle"></i>
        <span id="critical-alerts-text">0 critical alerts</span>
        <button onclick="viewAlerts('critical')">View</button>
    </div>
    <div class="alert-item warning">
        <i class="fas fa-exclamation-triangle"></i>
        <span id="warning-alerts-text">0 warnings</span>
        <button onclick="viewAlerts('warning')">View</button>
    </div>
    <div class="alert-item prediction">
        <i class="fas fa-crystal-ball"></i>
        <span id="predictions-text">0 predictions</span>
        <button onclick="viewPredictions()">View</button>
    </div>
</section>
```

**Load alerts on page load**:
```javascript
async function loadSystemAlerts() {
    try {
        // Get health summary
        const healthSummary = await API.Insights.getHealthSummary();
        
        // Get dashboard overview
        const overview = await API.Insights.getDashboardOverview();
        
        updateAlertsBanner(healthSummary.data, overview.data);
        
    } catch (error) {
        console.error('Failed to load alerts:', error);
    }
}
```

#### 7.2 Update `units.html`

**Add energy consumption indicators**:
```html
<!-- Add to unit card stats -->
<div class="unit-stats">
    <div class="stat-item">
        <span class="stat-value" id="plants-count-{{ unit.unit_id }}">0</span>
        <span class="stat-label">Plants</span>
    </div>
    <div class="stat-item">
        <span class="stat-value" id="sensors-count-{{ unit.unit_id }}">0</span>
        <span class="stat-label">Sensors</span>
    </div>
    <div class="stat-item">
        <span class="stat-value" id="actuators-count-{{ unit.unit_id }}">0</span>
        <span class="stat-label">Actuators</span>
    </div>
    <!-- NEW: Energy consumption -->
    <div class="stat-item energy">
        <span class="stat-value" id="energy-{{ unit.unit_id }}">-- kWh</span>
        <span class="stat-label">Energy (24h)</span>
    </div>
</div>
```

#### 7.3 Update `add_plant.html`

**Add health status section**:
```html
<!-- Add after stage selection -->
<div class="form-group">
    <label for="initial_health_status" class="form-label">Initial Health Status:</label>
    <select id="initial_health_status" name="initial_health_status" class="form-select">
        <option value="healthy" selected>Healthy</option>
        <option value="stressed">Stressed</option>
        <option value="diseased">Diseased</option>
        <option value="recovering">Recovering</option>
    </select>
</div>

<div class="form-group">
    <label for="initial_notes" class="form-label">Initial Health Notes:</label>
    <textarea id="initial_notes" name="initial_notes" class="form-textarea" rows="3" 
              placeholder="Any observations about the plant's initial condition..."></textarea>
</div>
```

---

## 🎨 CSS Styling Guidelines

### New CSS Classes Needed

#### Health Status Badges
```css
/* Health status colors */
.health-badge {
    padding: 4px 12px;
    border-radius: 12px;
    font-size: 0.85rem;
    font-weight: 600;
    display: inline-flex;
    align-items: center;
    gap: 4px;
}

.health-badge.badge-success {
    background: #d1fae5;
    color: #065f46;
}

.health-badge.badge-warning {
    background: #fef3c7;
    color: #92400e;
}

.health-badge.badge-danger {
    background: #fee2e2;
    color: #991b1b;
}

.health-badge.badge-info {
    background: #dbeafe;
    color: #1e40af;
}
```

#### Energy Cards
```css
.energy-card {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    padding: 20px;
    border-radius: 12px;
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
}

.energy-card .value {
    font-size: 2rem;
    font-weight: 700;
    margin: 10px 0;
}

.energy-card .trend {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 0.9rem;
    opacity: 0.9;
}

.energy-card .trend.up {
    color: #fca5a5;
}

.energy-card .trend.down {
    color: #86efac;
}
```

#### Prediction Alerts
```css
.prediction-alert {
    background: #fff7ed;
    border-left: 4px solid #f59e0b;
    padding: 16px;
    margin-bottom: 12px;
    border-radius: 6px;
}

.prediction-alert.critical {
    background: #fef2f2;
    border-left-color: #ef4444;
}

.prediction-alert .risk-level {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 0.75rem;
    font-weight: 600;
    text-transform: uppercase;
}

.prediction-alert .risk-level.high {
    background: #fee2e2;
    color: #991b1b;
}

.prediction-alert .risk-level.medium {
    background: #fef3c7;
    color: #92400e;
}

.prediction-alert .risk-level.low {
    background: #d1fae5;
    color: #065f46;
}
```

---

## 📝 Implementation Checklist

### Phase 1: Structure (Day 1)
- [ ] Update `base.html` navigation
- [ ] Create Flask routes for new pages
- [ ] Test navigation links
- [ ] Create page scaffolds (empty templates)

### Phase 2: Plant Health (Day 2)
- [ ] Create `plant_health.html`
- [ ] Create `plant_health.js`
- [ ] Implement health observation recording
- [ ] Implement health status display
- [ ] Implement recommendations display
- [ ] Test all plant health features

### Phase 3: Energy Analytics (Day 3)
- [ ] Create `energy_analytics.html`
- [ ] Create `energy_analytics.js`
- [ ] Implement energy consumption charts
- [ ] Implement cost trends visualization
- [ ] Implement failure predictions display
- [ ] Test energy analytics features

### Phase 4: Device Health (Day 4)
- [ ] Update `devices.html` with health indicators
- [ ] Create device health monitoring JavaScript
- [ ] Create `device_health.html` (detailed view)
- [ ] Implement anomaly detection alerts
- [ ] Test device health features

### Phase 5: Sensor Analytics (Day 4-5)
- [ ] Update `sensor_data.html`
- [ ] Create sensor analytics charts
- [ ] Implement statistics display
- [ ] Test sensor analytics features

### Phase 6: System Overview (Day 5)
- [ ] Create `system_overview.html`
- [ ] Implement comprehensive dashboard
- [ ] Create real-time monitoring widgets
- [ ] Test system overview

### Phase 7: Updates & Integration (Day 5-6)
- [ ] Update `dashboard.html` with alerts
- [ ] Update `units.html` with energy data
- [ ] Update `add_plant.html` with health fields
- [ ] Add CSS for all new components
- [ ] Cross-browser testing
- [ ] Mobile responsiveness testing
- [ ] Performance optimization

---

## 🧪 Testing Strategy

### Unit Testing
- Test all JavaScript functions individually
- Test API integration with mock data
- Test form validation

### Integration Testing
- Test navigation flow between pages
- Test real-time data updates
- Test chart rendering
- Test modal interactions

### User Acceptance Testing
- Test complete workflows (record observation → view history → get recommendations)
- Test energy analytics workflow
- Test device health monitoring
- Test system overview dashboard

### Performance Testing
- Test page load times
- Test chart rendering with large datasets
- Test real-time updates (Socket.io)
- Test auto-refresh intervals

---

## 📊 Success Metrics

### Feature Completeness
- ✅ All 155 API endpoints integrated
- ✅ All new features accessible via UI
- ✅ All forms functional and validated
- ✅ All charts rendering correctly

### User Experience
- ✅ Page load time < 2 seconds
- ✅ Real-time updates working
- ✅ Mobile responsive on all pages
- ✅ Intuitive navigation
- ✅ Clear error messages

### Data Visualization
- ✅ Charts update in real-time
- ✅ Color coding consistent
- ✅ Tooltips informative
- ✅ Legends clear

---

## 🚀 Deployment Strategy

### Development Phase
1. Create feature branches for each phase
2. Test locally with backend running
3. Commit after each completed feature
4. Merge to development branch

### Testing Phase
1. Deploy to staging environment
2. Run full test suite
3. Fix bugs and issues
4. User acceptance testing

### Production Deployment
1. Merge to main branch
2. Create release tag
3. Deploy to production
4. Monitor for errors
5. Gather user feedback

---

## 📚 Documentation Requirements

### User Documentation
- Create user guide for plant health monitoring
- Create user guide for energy analytics
- Create user guide for device health
- Create FAQ section

### Developer Documentation
- Document new API usage patterns
- Document JavaScript modules
- Document CSS classes
- Document component structure

---

## ⏱️ Timeline Estimate

**Total Time: 5-6 days (40-48 hours)**

- **Phase 1**: 2-3 hours
- **Phase 2**: 4-6 hours
- **Phase 3**: 4-6 hours
- **Phase 4**: 3-4 hours
- **Phase 5**: 3-4 hours
- **Phase 6**: 2-3 hours
- **Phase 7**: 2-3 hours
- **Testing**: 4-6 hours
- **Documentation**: 2-3 hours
- **Bug Fixes**: 4-6 hours (buffer)

---

## 🎯 Priority Order

### Must-Have (Week 1)
1. Plant Health Monitoring
2. Energy Analytics Dashboard
3. Navigation updates
4. Basic device health indicators

### Should-Have (Week 2)
1. Advanced sensor analytics
2. System overview dashboard
3. Failure prediction alerts
4. Complete device health monitoring

### Nice-to-Have (Week 3)
1. Export functionality
2. Advanced filtering
3. Customizable dashboards
4. Email notifications
5. Mobile app integration

---

## 🔄 Next Steps

1. **Review and approve** this implementation plan
2. **Set up development environment** with backend running
3. **Start with Phase 1** (navigation structure)
4. **Iterate through phases** sequentially
5. **Test after each phase** completion
6. **Deploy to staging** after Phase 7
7. **Production deployment** after successful testing

---

## 📞 Support & Resources

### API Documentation
- Reference: `API_UPDATE_SUMMARY.txt`
- API.js: `static/js/api.js`
- Backend APIs: `app/api/blueprints/`

### Design Resources
- Chart.js: https://www.chartjs.org/
- Font Awesome: https://fontawesome.com/
- CSS Grid Guide: https://css-tricks.com/snippets/css/complete-guide-grid/

### Testing Tools
- Browser DevTools
- Lighthouse for performance
- WAVE for accessibility

---

*This implementation plan is designed to be executed systematically over 5-6 days with clear milestones and deliverables at each phase.*
