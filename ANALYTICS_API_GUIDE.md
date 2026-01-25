# Analytics API Guide

## Overview

The Analytics API provides comprehensive endpoints for environmental monitoring, energy tracking, and plant health insights. It consolidates analytics functionality from multiple locations into a unified, well-organized API.

## New Architecture

### Before
- Analytics endpoints scattered across multiple blueprints:
  - `/api/insights/analytics/*` (insights.py)
  - `/api/devices/analytics/*` (devices/actuators/analytics.py)
  - `/api/ml/analytics/*` (ml_ai/analytics.py)
  - `/api/dashboard/*` (dashboard.py)
  - `/api/sensors/*` (sensors.py)

### After
- **Unified endpoint**: `/api/analytics/*`
- Clear organization by category
- Consistent response formats
- Better documentation
- Enhanced chart data formatting

## Endpoint Categories

### 1. Sensor Analytics
Environmental monitoring and historical data analysis.

#### Get Sensors Overview
```javascript
// Get latest readings for all sensors
const overview = await API.Analytics.getSensorsOverview();

// Filter by unit
const unitOverview = await API.Analytics.getSensorsOverview(unitId);
```

**Response:**
```json
{
  "unit_id": 1,
  "latest_reading": {
    "timestamp": "2025-12-21T10:30:00Z",
    "temperature": 24.5,
    "humidity": 65.2,
    "soil_moisture": 45.0,
    "co2_ppm": 450,
    "voc_ppb": 120
  },
  "total_sensors": 5,
  "sensors": [...]
}
```

#### Get Sensor History (Time-Series)
```javascript
// Perfect for charts and graphs
const history = await API.Analytics.getSensorsHistory({
  start: '2025-12-20T00:00:00Z',
  end: '2025-12-21T00:00:00Z',
  unit_id: 1,
  limit: 500,
  interval: '1h'  // Optional aggregation
});
```

**Response:**
```json
{
  "start": "2025-12-20T00:00:00Z",
  "end": "2025-12-21T00:00:00Z",
  "count": 288,
  "data": {
    "timestamps": ["2025-12-20T00:00:00Z", ...],
    "temperature": [24.1, 24.3, 24.5, ...],
    "humidity": [64.2, 65.0, 65.8, ...],
    "soil_moisture": [43.5, 44.0, 45.0, ...],
    "co2": [440, 445, 450, ...],
    "voc": [115, 118, 120, ...]
  }
}
```

#### Get Sensor Statistics
```javascript
// Statistical analysis for insights
const stats = await API.Analytics.getSensorsStatistics({
  hours: 24,
  unit_id: 1
});
```

**Response:**
```json
{
  "period_hours": 24,
  "statistics": {
    "temperature": {
      "count": 288,
      "min": 22.1,
      "max": 26.3,
      "avg": 24.5,
      "median": 24.4,
      "std_dev": 1.2
    },
    "humidity": {...},
    "soil_moisture": {...}
  }
}
```

#### Get Sensor Trends
```javascript
// Identify patterns and trends
const trends = await API.Analytics.getSensorsTrends({
  days: 7,
  unit_id: 1
});
```

**Response:**
```json
{
  "period_days": 7,
  "trends": {
    "temperature": {
      "trend": "stable",
      "volatility": "low",
      "average": 24.5,
      "std_dev": 0.8,
      "change": 0.2
    },
    "humidity": {
      "trend": "rising",
      "volatility": "medium",
      "average": 65.0,
      "change": 3.5
    }
  }
}
```

#### Get Sensor Correlations
```javascript
// Understand relationships between factors
const correlations = await API.Analytics.getSensorsCorrelations({
  days: 7,
  unit_id: 1
});
```

**Response:**
```json
{
  "period_days": 7,
  "correlations": {
    "temp_humidity_correlation": -0.742,
    "correlation_interpretation": "strong",
    "vpd_average": 0.85,
    "vpd_status": "optimal_vegetative",
    "sample_size": 2016
  }
}
```

### 2. Actuator Energy Analytics
Power consumption monitoring and optimization.

#### Get Actuators Overview
```javascript
// Get all actuators with analytics
const overview = await API.Analytics.getActuatorsOverview();

// Filter by unit
const unitActuators = await API.Analytics.getActuatorsOverview(unitId);
```

#### Get Actuator Dashboard
```javascript
// Complete dashboard for a single actuator
const dashboard = await API.Analytics.getActuatorDashboard(actuatorId);
```

**Response:**
```json
{
  "actuator_id": 1,
  "dashboard": {
    "current_status": {
      "state": "on",
      "power_watts": 150.0,
      "runtime_hours": 142.5
    },
    "cost_trends": {
      "daily_costs": [...],
      "total_cost": 12.45,
      "trend": "stable"
    },
    "recommendations": [
      {
        "type": "schedule_optimization",
        "severity": "medium",
        "potential_savings": 2.15,
        "description": "Run during off-peak hours"
      }
    ],
    "anomalies": [...],
    "failure_prediction": {
      "risk_score": 0.12,
      "risk_level": "low"
    }
  }
}
```

#### Get Energy Costs
```javascript
// Detailed cost breakdown
const costs = await API.Analytics.getActuatorEnergyCosts(actuatorId, 30);
```

#### Get Recommendations
```javascript
// Optimization suggestions
const recommendations = await API.Analytics.getActuatorRecommendations(actuatorId);
```

#### Detect Anomalies
```javascript
// Power consumption anomalies
const anomalies = await API.Analytics.getActuatorAnomalies(actuatorId, 24);
```

#### Predict Failure
```javascript
// Predictive maintenance
const prediction = await API.Analytics.predictActuatorFailure(actuatorId, 7);
```

**Response:**
```json
{
  "actuator_id": 1,
  "prediction": {
    "risk_score": 0.68,
    "risk_level": "high",
    "confidence": 0.85,
    "factors": [
      "Increased power consumption variance",
      "Runtime exceeds typical patterns",
      "Multiple anomalies detected"
    ],
    "recommendation": "Schedule maintenance within 7 days. Consider backup plan.",
    "days_ahead": 7
  }
}
```

### 3. Comparative Analytics
Compare performance across units and devices.

#### Get Unit Comparison
```javascript
// Compare devices within a unit
const comparison = await API.Analytics.getUnitComparison(unitId);
```

#### Get Multi-Unit Comparison
```javascript
// Compare across all units
const comparison = await API.Analytics.getMultiUnitComparison();
```

**Response:**
```json
{
  "units": [
    {
      "unit_id": 1,
      "unit_name": "Vegetative Room",
      "environment": {
        "temperature": 24.5,
        "humidity": 65.0,
        "vpd": 0.85
      },
      "energy": {
        "total_cost": 45.20,
        "top_consumer": "Grow Light",
        "efficiency_score": 0.85
      }
    },
    {
      "unit_id": 2,
      "unit_name": "Flowering Room",
      "environment": {...},
      "energy": {...}
    }
  ]
}
```

### 4. Batch Operations
Perform operations across multiple devices.

#### Get Batch Failure Predictions
```javascript
// Find all high-risk devices
const predictions = await API.Analytics.getBatchFailurePredictions({
  threshold: 0.5,
  risk_level: 'high'
});

// Filter by unit
const unitPredictions = await API.Analytics.getBatchFailurePredictions({
  unit_id: 1,
  threshold: 0.3
});
```

**Response:**
```json
{
  "unit_id": 1,
  "threshold": 0.5,
  "predictions": [
    {
      "actuator_id": 3,
      "actuator_name": "Exhaust Fan",
      "actuator_type": "fan",
      "prediction": {
        "risk_score": 0.85,
        "risk_level": "critical",
        "factors": [...]
      }
    }
  ],
  "count": 3,
  "high_risk_count": 2
}
```

### 5. Dashboard Summaries
Quick summaries for dashboard cards.

#### Get Environmental Summary
```javascript
// Dashboard card data
const summary = await API.Analytics.getEnvironmentalSummary(unitId);
```

**Response:**
```json
{
  "unit_id": 1,
  "current": {
    "temperature": 24.5,
    "humidity": 65.0,
    "soil_moisture": 45.0,
    "vpd": 0.85
  },
  "daily_stats": {
    "temperature": {
      "avg": 24.3,
      "min": 22.1,
      "max": 26.0
    }
  },
  "timestamp": "2025-12-21T10:30:00Z"
}
```

#### Get Energy Summary
```javascript
// Energy dashboard card
const summary = await API.Analytics.getEnergySummary({
  unit_id: 1,
  days: 7
});
```

**Response:**
```json
{
  "unit_id": 1,
  "period_days": 7,
  "total_cost": 45.20,
  "total_devices": 8,
  "top_consumers": [
    {
      "actuator_id": 1,
      "name": "Grow Light",
      "type": "light",
      "cost": 28.50
    },
    {
      "actuator_id": 2,
      "name": "Dehumidifier",
      "type": "dehumidifier",
      "cost": 12.30
    }
  ],
  "timestamp": "2025-12-21T10:30:00Z"
}
```

## Chart Integration Examples

### Temperature Chart (Line Chart)
```javascript
const history = await API.Analytics.getSensorsHistory({
  start: '2025-12-20T00:00:00Z',
  end: '2025-12-21T00:00:00Z',
  unit_id: 1,
  limit: 288
});

// Direct integration with Chart.js
const chartData = {
  labels: history.data.timestamps,
  datasets: [{
    label: 'Temperature (°C)',
    data: history.data.temperature,
    borderColor: 'rgb(255, 99, 132)',
    tension: 0.1
  }]
};
```

### Energy Cost Breakdown (Bar Chart)
```javascript
const summary = await API.Analytics.getEnergySummary({
  unit_id: 1,
  days: 7
});

const chartData = {
  labels: summary.top_consumers.map(d => d.name),
  datasets: [{
    label: 'Cost ($)',
    data: summary.top_consumers.map(d => d.cost),
    backgroundColor: 'rgba(54, 162, 235, 0.5)'
  }]
};
```

### VPD Gauge Chart
```javascript
const correlations = await API.Analytics.getSensorsCorrelations({
  days: 1,
  unit_id: 1
});

// Display VPD status with color coding
const vpd = correlations.vpd_average;
const status = correlations.vpd_status;

// Color coding
const colors = {
  'too_low': 'blue',
  'optimal_vegetative': 'green',
  'optimal_flowering': 'lightgreen',
  'late_flowering': 'yellow',
  'too_high': 'red'
};
```

### Multi-Unit Comparison (Radar Chart)
```javascript
const comparison = await API.Analytics.getMultiUnitComparison();

const chartData = {
  labels: ['Temperature', 'Humidity', 'VPD', 'Energy Efficiency', 'Health Score'],
  datasets: comparison.units.map((unit, i) => ({
    label: unit.unit_name,
    data: [
      unit.environment.temperature / 30,  // Normalize to 0-1
      unit.environment.humidity / 100,
      unit.environment.vpd / 2,
      unit.energy.efficiency_score,
      unit.health_score || 0.8
    ]
  }))
};
```

## Migration Guide

### Deprecated Endpoints

These endpoints are now available under `/api/analytics`:

| Old Endpoint | New Endpoint |
|-------------|--------------|
| `/api/insights/analytics/sensors/{id}/history` | `/api/analytics/sensors/history?sensor_id={id}` |
| `/api/insights/analytics/actuators/{id}/dashboard` | `/api/analytics/actuators/{id}/dashboard` |
| `/api/devices/analytics/actuators/{id}/predict-failure` | `/api/analytics/actuators/{id}/predict-failure` |
| `/api/dashboard/timeseries` | `/api/analytics/sensors/history` |
| `/api/sensors/sensor_history` | `/api/analytics/sensors/history` |

### Frontend Migration

**Before:**
```javascript
const history = await fetch('/api/insights/analytics/sensors/1/history?hours=24')
  .then(r => r.json());
```

**After:**
```javascript
const history = await API.Analytics.getSensorsHistory({
  sensor_id: 1,
  hours: 24
});
```

### Key Improvements

1. **Unified Location**: All analytics in one place
2. **Better Organization**: Clear categories (sensors, actuators, comparisons)
3. **Enhanced Data**: More detailed responses with metadata
4. **Chart-Ready**: Data formatted for popular chart libraries
5. **Consistent Responses**: Standardized error handling and response structure
6. **Better Filtering**: Consistent filtering across all endpoints

## Best Practices

### 1. Use Appropriate Time Windows
```javascript
// For real-time dashboards: short windows
const recent = await API.Analytics.getSensorsHistory({
  hours: 1,
  limit: 60
});

// For trend analysis: longer windows
const trends = await API.Analytics.getSensorsTrends({
  days: 30
});
```

### 2. Leverage Caching
```javascript
// Cache environmental summaries (updated every 30s)
let cachedSummary = null;
let cacheTime = 0;

async function getEnvironmentalData() {
  const now = Date.now();
  if (cachedSummary && (now - cacheTime) < 30000) {
    return cachedSummary;
  }
  
  cachedSummary = await API.Analytics.getEnvironmentalSummary();
  cacheTime = now;
  return cachedSummary;
}
```

### 3. Handle Unit Filtering
```javascript
// Get currently selected unit from session
const selectedUnit = sessionStorage.getItem('selected_unit_id');

// Use throughout app
const overview = await API.Analytics.getSensorsOverview(selectedUnit);
const summary = await API.Analytics.getEnvironmentalSummary(selectedUnit);
```

### 4. Error Handling
```javascript
try {
  const data = await API.Analytics.getActuatorDashboard(actuatorId);
  renderDashboard(data);
} catch (error) {
  console.error('Analytics error:', error);
  showErrorMessage('Unable to load analytics data');
}
```

## Chart Examples Gallery

### 1. Real-Time Temperature Monitor
```javascript
async function updateTemperatureChart() {
  const data = await API.Analytics.getSensorsHistory({
    hours: 1,
    limit: 60,
    unit_id: currentUnit
  });
  
  temperatureChart.data.labels = data.data.timestamps;
  temperatureChart.data.datasets[0].data = data.data.temperature;
  temperatureChart.update();
}

// Update every 30 seconds
setInterval(updateTemperatureChart, 30000);
```

### 2. 7-Day Trend Chart
```javascript
const trends = await API.Analytics.getSensorsTrends({
  days: 7,
  unit_id: currentUnit
});

// Show trend indicators
document.getElementById('temp-trend').textContent = 
  `${trends.temperature.trend} (±${trends.temperature.change}°C)`;
```

### 3. Energy Cost Comparison
```javascript
const comparison = await API.Analytics.getUnitComparison(unitId);

// Bar chart of device costs
const costs = comparison.devices.map(d => ({
  device: d.name,
  cost: d.total_cost,
  efficiency: d.efficiency_score
}));
```

### 4. Failure Risk Heatmap
```javascript
const predictions = await API.Analytics.getBatchFailurePredictions({
  threshold: 0.0
});

// Create heatmap of risk scores
predictions.predictions.forEach(pred => {
  const cell = document.getElementById(`device-${pred.actuator_id}`);
  cell.style.backgroundColor = getRiskColor(pred.prediction.risk_score);
  cell.title = `Risk: ${(pred.prediction.risk_score * 100).toFixed(0)}%`;
});
```

## Future Enhancements

Planned features for future releases:

1. **Predictive Yield Estimation**: Based on environmental conditions
2. **AI-Powered Anomaly Detection**: Machine learning for better anomaly detection
3. **Custom Alert Thresholds**: User-configurable thresholds per unit
4. **Export Capabilities**: Download analytics data as CSV/Excel
5. **Scheduled Reports**: Email daily/weekly analytics summaries
6. **Mobile Push Notifications**: For critical alerts and predictions
7. **Advanced Correlations**: More sophisticated environmental factor analysis
8. **Cost Optimization Automation**: Automatically adjust schedules to minimize costs

## Support

For questions or issues with the Analytics API:
- Check the [API Reference](./API_REFERENCE.md)
- Review [Analytics Service](./app/services/application/analytics_service.py)
- See [State Tracking](./app/services/hardware/state_tracking_service.py)
- Check [Energy Monitoring](./app/services/hardware/energy_monitoring.py)
