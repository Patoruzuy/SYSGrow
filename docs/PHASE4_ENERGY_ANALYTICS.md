# Phase 4: Advanced Energy Analytics & Monitoring

## Overview

Phase 4 enhances the actuator system with sophisticated energy analytics, optimization recommendations, anomaly detection, and comprehensive dashboard capabilities. This phase transforms raw power data into actionable insights for cost reduction and efficiency improvements.

## Features Implemented

### 1. **Energy Cost Trend Analysis**
Track and analyze energy costs over time with daily breakdowns and trend detection.

**Key Capabilities:**
- Daily energy consumption and cost calculations
- Trend detection (increasing/decreasing/stable)
- Historical data up to 365 days
- Automatic cost extrapolation

### 2. **Optimization Recommendations**
AI-driven recommendations to reduce energy consumption and costs.

**Detection Types:**
- High standby power consumption
- Unstable power consumption (high variance)
- Poor power factor
- High peak power demand
- Always-on devices that could be scheduled

### 3. **Power Anomaly Detection**
Real-time detection of unusual power consumption patterns.

**Anomaly Types:**
- Power spikes (3σ above average)
- Power drops (3σ below average)
- Sudden changes (>200% variation)
- Extended outages (>1 hour of zero power)

### 4. **Comparative Energy Analysis**
Cross-device energy comparison and efficiency rankings.

**Analysis Features:**
- Total power consumption across all devices
- Top energy consumers identification
- Efficiency rankings by device type
- Unit-level aggregation

### 5. **Energy Dashboard**
Comprehensive single-endpoint dashboard combining multiple analytics.

**Dashboard Components:**
- Current power status
- Daily and weekly cost summaries
- Top optimization recommendations
- Recent anomalies
- Trend indicators

## Architecture

### Data Flow
```
Power Readings (ActuatorPowerReading)
    ↓
DeviceService Analytics Methods
    ↓
├── get_energy_cost_trends()
├── get_energy_optimization_recommendations()
├── detect_power_anomalies()
├── get_comparative_energy_analysis()
└── Dashboard aggregation
    ↓
REST API Endpoints (/actuators/{id}/energy/*)
    ↓
Client Applications / Dashboards
```

### Service Layer Methods

#### `get_energy_cost_trends(actuator_id, days=7)`
```python
{
    "actuator_id": 1,
    "period_days": 7,
    "daily_costs": [
        {
            "date": "2024-01-15",
            "energy_kwh": 3.456,
            "cost": 0.41,
            "avg_power_watts": 144.0
        },
        ...
    ],
    "total_cost": 2.87,
    "total_energy_kwh": 23.92,
    "average_daily_cost": 0.41,
    "trend": "stable",
    "electricity_rate_kwh": 0.12
}
```

#### `get_energy_optimization_recommendations(actuator_id)`
```python
[
    {
        "type": "high_standby_power",
        "severity": "medium",
        "title": "High Standby Power Consumption",
        "description": "Device consumes 8.5W when idle. Consider using a smart plug to completely cut power.",
        "current_value": 8.5,
        "potential_savings_kwh": 74.46,
        "potential_savings_usd": 8.94
    },
    {
        "type": "always_on_device",
        "severity": "low",
        "title": "Device Always On",
        "description": "Device is on 95% of the time. Consider scheduling to reduce runtime.",
        "current_value": 0.95,
        "potential_savings_kwh": 131.4,
        "potential_savings_usd": 15.77
    }
]
```

#### `detect_power_anomalies(actuator_id, hours=24)`
```python
[
    {
        "type": "power_spike",
        "severity": "major",
        "timestamp": "2024-01-15T10:30:00",
        "value": 245.3,
        "expected_range": "120.5-165.8W",
        "deviation_percent": 68.5,
        "description": "Power spike detected: 245.3W (normal: 145.5W)"
    },
    {
        "type": "sudden_change",
        "severity": "minor",
        "timestamp": "2024-01-15T14:22:00",
        "value": 198.2,
        "previous_value": 45.1,
        "change_percent": 339.5,
        "description": "Sudden power change: 45.1W → 198.2W"
    }
]
```

## API Endpoints

### 1. Get Energy Cost Trends
```http
GET /api/devices/actuators/{id}/energy/cost-trends?days=7
```

**Query Parameters:**
- `days` (optional): Number of days to analyze (1-365, default: 7)

**Response:**
```json
{
    "status": "success",
    "data": {
        "actuator_id": 1,
        "period_days": 7,
        "daily_costs": [...],
        "total_cost": 2.87,
        "total_energy_kwh": 23.92,
        "average_daily_cost": 0.41,
        "trend": "stable"
    }
}
```

**Use Cases:**
- Monthly cost reports
- Budget planning
- Trend analysis
- Cost forecasting

---

### 2. Get Optimization Recommendations
```http
GET /api/devices/actuators/{id}/energy/recommendations
```

**Response:**
```json
{
    "status": "success",
    "data": {
        "actuator_id": 1,
        "recommendations": [...],
        "count": 3,
        "total_potential_savings": {
            "energy_kwh": 205.86,
            "cost_usd": 24.71
        }
    }
}
```

**Recommendation Types:**
| Type | Severity | Description |
|------|----------|-------------|
| `high_standby_power` | medium | Device uses >5W when idle |
| `high_power_variance` | low | Unstable power consumption |
| `low_power_factor` | medium | Power factor <0.85 |
| `high_peak_power` | low | Peak >2x average |
| `always_on_device` | low | On >90% of time |
| `optimal` | info | No issues detected |

**Use Cases:**
- Energy audits
- Cost reduction strategies
- Maintenance planning
- Device replacement decisions

---

### 3. Detect Power Anomalies
```http
GET /api/devices/actuators/{id}/energy/anomalies?hours=24
```

**Query Parameters:**
- `hours` (optional): Hours to analyze (1-720, default: 24)

**Response:**
```json
{
    "status": "success",
    "data": {
        "actuator_id": 1,
        "period_hours": 24,
        "anomalies": [...],
        "count": 5,
        "by_type": {
            "power_spike": [...],"sudden_change": [...]
        },
        "by_severity": {
            "critical": 0,
            "major": 2,
            "minor": 3,
            "info": 0
        }
    }
}
```

**Anomaly Detection Logic:**
- **Power Spike**: >3σ above average (major if >4.5σ)
- **Power Drop**: >3σ below average (only if device normally uses power)
- **Sudden Change**: >200% change between consecutive readings
- **Extended Outage**: >60 minutes of zero power (for active devices)

**Automatic Actions:**
- Critical/major anomalies automatically logged to ActuatorAnomaly table
- Event bus notifications for real-time alerts

**Use Cases:**
- Equipment failure detection
- Power quality monitoring
- Preventive maintenance
- Root cause analysis

---

### 4. Get Comparative Analysis
```http
GET /api/devices/actuators/energy/comparative-analysis?unit_id=1
```

**Query Parameters:**
- `unit_id` (optional): Filter by specific unit

**Response:**
```json
{
    "status": "success",
    "data": {
        "summary": {
            "total_actuators": 12,
            "monitored_actuators": 8,
            "total_power_consumption": 1245.5,
            "total_daily_cost": 3.59
        },
        "by_type": {
            "grow_light": {...},
            "fan": {...},
            "water_pump": {...}
        },
        "top_consumers": [
            {"actuator_id": 3, "name": "Main Grow Light", "power_watts": 285.5},
            {"actuator_id": 7, "name": "Heater", "power_watts": 455.2}
        ],
        "efficiency_rankings": [...]
    }
}
```

**Use Cases:**
- System-wide energy overview
- Identify energy hogs
- Benchmark device efficiency
- Unit-level cost allocation

---

### 5. Get Energy Dashboard
```http
GET /api/devices/actuators/{id}/energy/dashboard
```

**Response:**
```json
{
    "status": "success",
    "data": {
        "actuator_id": 1,
        "current_status": {
            "power_watts": 145.3,
            "voltage": 230.2,
            "current": 0.65,
            "timestamp": "2024-01-15T10:30:00"
        },
        "daily_summary": {
            "total_cost": 0.41,
            "total_energy_kwh": 3.42,
            "trend": "stable"
        },
        "weekly_summary": {
            "total_cost": 2.87,
            "total_energy_kwh": 23.92,
            "average_daily_cost": 0.41,
            "trend": "decreasing"
        },
        "optimization": {
            "recommendations_count": 3,
            "high_priority": 1,
            "total_potential_savings_usd": 24.71,
            "top_recommendations": [...]
        },
        "anomalies": {
            "count_24h": 5,
            "critical": 0,
            "major": 2,
            "recent": [...]
        }
    }
}
```

**Use Cases:**
- Single-page device overview
- Mobile app dashboard
- Quick health check
- Executive summaries

## Usage Examples

### Example 1: Weekly Cost Analysis
```python
import requests

# Get 7-day cost trends
response = requests.get('http://localhost:5000/api/devices/actuators/1/energy/cost-trends?days=7')
data = response.json()['data']

print(f"Total weekly cost: ${data['total_cost']:.2f}")
print(f"Trend: {data['trend']}")

for day in data['daily_costs']:
    print(f"{day['date']}: {day['energy_kwh']}kWh = ${day['cost']}")
```

**Output:**
```
Total weekly cost: $2.87
Trend: stable
2024-01-09: 3.42kWh = $0.41
2024-01-10: 3.38kWh = $0.41
2024-01-11: 3.45kWh = $0.41
...
```

---

### Example 2: Get Optimization Recommendations
```python
# Get recommendations
response = requests.get('http://localhost:5000/api/devices/actuators/1/energy/recommendations')
data = response.json()['data']

print(f"Found {data['count']} recommendations")
print(f"Total potential savings: ${data['total_potential_savings']['cost_usd']:.2f}/year")

for rec in data['recommendations']:
    print(f"\n{rec['title']} ({rec['severity']})")
    print(f"  {rec['description']}")
    if rec['potential_savings_usd'] > 0:
        print(f"  Potential savings: ${rec['potential_savings_usd']:.2f}/year")
```

**Output:**
```
Found 3 recommendations
Total potential savings: $24.71/year

High Standby Power Consumption (medium)
  Device consumes 8.5W when idle. Consider using a smart plug to completely cut power.
  Potential savings: $8.94/year

Device Always On (low)
  Device is on 95% of the time. Consider scheduling to reduce runtime.
  Potential savings: $15.77/year
```

---

### Example 3: Detect Recent Anomalies
```python
# Check for anomalies in last 48 hours
response = requests.get('http://localhost:5000/api/devices/actuators/1/energy/anomalies?hours=48')
data = response.json()['data']

print(f"Detected {data['count']} anomalies in {data['period_hours']} hours")
print(f"Critical: {data['by_severity']['critical']}, Major: {data['by_severity']['major']}")

for anomaly in data['anomalies']:
    if anomaly['severity'] in ['critical', 'major']:
        print(f"\n{anomaly['type'].upper()} - {anomaly['severity']}")
        print(f"  {anomaly['description']}")
        print(f"  Time: {anomaly['timestamp']}")
```

**Output:**
```
Detected 5 anomalies in 48 hours
Critical: 0, Major: 2

POWER_SPIKE - major
  Power spike detected: 245.3W (normal: 145.5W)
  Time: 2024-01-15T10:30:00

EXTENDED_OUTAGE - major
  Device was off/disconnected for 75 minutes
  Time: 2024-01-15T14:22:00
```

---

### Example 4: Energy Dashboard Widget
```python
# Get complete dashboard data
response = requests.get('http://localhost:5000/api/devices/actuators/1/energy/dashboard')
dashboard = response.json()['data']

# Display current status
current = dashboard['current_status']
print(f"Current Power: {current['power_watts']}W")
print(f"Voltage: {current['voltage']}V, Current: {current['current']}A")

# Display cost summaries
print(f"\nDaily Cost: ${dashboard['daily_summary']['total_cost']:.2f}")
print(f"Weekly Cost: ${dashboard['weekly_summary']['total_cost']:.2f}")
print(f"Trend: {dashboard['weekly_summary']['trend']}")

# Display optimization opportunities
opt = dashboard['optimization']
print(f"\n{opt['recommendations_count']} recommendations ({opt['high_priority']} high priority)")
print(f"Potential savings: ${opt['total_potential_savings_usd']:.2f}/year")

# Display anomaly alerts
anom = dashboard['anomalies']
print(f"\nAnomalies (24h): {anom['count_24h']} total")
if anom['critical'] + anom['major'] > 0:
    print(f"⚠️ {anom['critical']} critical, {anom['major']} major")
```

**Output:**
```
Current Power: 145.3W
Voltage: 230.2V, Current: 0.65A

Daily Cost: $0.41
Weekly Cost: $2.87
Trend: decreasing

3 recommendations (1 high priority)
Potential savings: $24.71/year

Anomalies (24h): 5 total
⚠️ 0 critical, 2 major
```

## Optimization Recommendations Logic

### High Standby Power Detection
```python
# Threshold: >5W when device is idle
avg_standby = average(power_readings where power < avg_power * 0.2)
if avg_standby > 5.0:
    annual_waste_kwh = (avg_standby * 24 * 365) / 1000
    annual_cost = annual_waste_kwh * electricity_rate
    # Recommend smart plug or power strip
```

### High Power Variance Detection
```python
# High variance indicates unstable operation
variance = sum((power - avg_power)² for power in readings) / len(readings)
if variance > avg_power * 0.5:
    # Recommend calibration check or mechanical inspection
```

### Low Power Factor Detection
```python
# Poor power factor increases electricity costs
avg_power_factor = average(power_factor_readings)
if avg_power_factor < 0.85:
    # Recommend power factor correction
    estimated_savings = avg_power * 0.05 * electricity_rate  # 5% savings estimate
```

### Always-On Device Detection
```python
# Devices on >90% of time could benefit from scheduling
on_time_percentage = len([p for p in readings if p > 10]) / len(readings)
if on_time_percentage > 0.9:
    # Recommend scheduling or automation
    potential_savings = (avg_power * 24 * 365 * 0.1) / 1000  # 10% reduction estimate
```

## Anomaly Detection Algorithms

### Statistical Outlier Detection (3-Sigma Rule)
```python
# Calculate baseline statistics
avg_power = mean(power_readings)
std_dev = standard_deviation(power_readings)

# Define thresholds
spike_threshold = avg_power + (3 * std_dev)
drop_threshold = max(0, avg_power - (3 * std_dev))

# Classify readings
for reading in power_readings:
    if reading > spike_threshold:
        severity = 'major' if reading > spike_threshold * 1.5 else 'minor'
        log_anomaly('power_spike', severity)
    elif reading < drop_threshold:
        log_anomaly('power_drop', 'minor')
```

### Sudden Change Detection
```python
# Detect rapid changes between consecutive readings
for i in range(1, len(readings)):
    current = readings[i]
    previous = readings[i-1]
    
    if previous > 0:
        change_percent = abs((current - previous) / previous) * 100
        
        if change_percent > 200:  # More than 200% change
            log_anomaly('sudden_change', 'minor')
```

### Extended Outage Detection
```python
# Track consecutive zero-power readings
zero_streak = 0
for reading in readings:
    if reading < 1.0:
        zero_streak += 1
    else:
        if zero_streak > 60:  # >1 hour
            log_anomaly('extended_outage', 'major')
        zero_streak = 0
```

## Cost Calculation

### Daily Energy Cost
```python
# From actual energy readings
if readings_have_cumulative_energy:
    daily_energy_kwh = readings[-1].energy - readings[0].energy
else:
    # Estimate from power readings
    avg_power_watts = sum(readings) / len(readings)
    hours_covered = len(readings) / 60  # Assuming 1-minute intervals
    daily_energy_kwh = (avg_power_watts * hours_covered) / 1000

daily_cost = daily_energy_kwh * electricity_rate_kwh
```

### Projected Annual Cost
```python
# Extrapolate from 24-hour data
daily_cost = calculate_daily_cost()
annual_cost = daily_cost * 365
```

### Trend Detection
```python
# Compare first half vs second half of period
mid_point = len(daily_costs) // 2
first_half_avg = average(daily_costs[:mid_point])
second_half_avg = average(daily_costs[mid_point:])

if second_half_avg > first_half_avg * 1.1:
    trend = 'increasing'
elif second_half_avg < first_half_avg * 0.9:
    trend = 'decreasing'
else:
    trend = 'stable'
```

## Performance Considerations

### Query Optimization
All analytics methods use indexed queries:
```sql
-- Power readings index (used in all queries)
CREATE INDEX idx_power_actuator_id ON ActuatorPowerReading(actuator_id);
CREATE INDEX idx_power_created_at ON ActuatorPowerReading(created_at);

-- Composite index for time-range queries
CREATE INDEX idx_power_actuator_time ON ActuatorPowerReading(actuator_id, created_at);
```

### Memory Management
- Limit query results (default: 1000-5000 readings)
- Process data in chunks for large datasets
- Cache dashboard data for frequently accessed devices

### Computation Complexity
| Operation | Complexity | Max Readings |
|-----------|------------|--------------|
| Cost Trends | O(n) | 10,000 |
| Recommendations | O(n) | 1,000 |
| Anomaly Detection | O(n) | 5,000 |
| Dashboard | O(n) | 5,000 |

### Response Time Targets
- Single endpoint: <500ms
- Dashboard (multiple queries): <2s
- Historical analysis (30+ days): <5s

## Integration with Existing Systems

### ActuatorManager Integration
Phase 4 builds on Phase 3 automatic persistence:
```python
# Power readings automatically saved in Phase 3
_persist_power_reading(actuator_id, reading)

# Phase 4 analyzes persisted data
cost_trends = device_service.get_energy_cost_trends(actuator_id)
recommendations = device_service.get_energy_optimization_recommendations(actuator_id)
anomalies = device_service.detect_power_anomalies(actuator_id)
```

### Event Bus Integration
```python
# Anomalies automatically trigger events
if anomaly['severity'] in ['critical', 'major']:
    event_bus.publish('power_anomaly_detected', {
        'actuator_id': actuator_id,
        'anomaly_type': anomaly['type'],
        'severity': anomaly['severity'],
        'details': anomaly
    })
```

### EnergyMonitoringService Integration
```python
# Phase 4 complements in-memory EnergyMonitoringService
# - EnergyMonitoringService: Real-time monitoring (memory)
# - Phase 4 Analytics: Historical analysis (database)

# Example: Compare real-time vs historical
current_power = energy_monitoring.get_latest_reading(actuator_id)
historical_avg = device_service.get_energy_cost_trends(actuator_id, days=30)
```

## Future Enhancements (Phase 5)

### Machine Learning Integration
- Predictive failure detection
- Automated anomaly classification
- Seasonal pattern recognition
- Cost forecasting models

### Advanced Optimizations
- AI-driven scheduling recommendations
- Load balancing suggestions
- Peak demand avoidance strategies
- Renewable energy integration

### Enhanced Analytics
- Carbon footprint calculation
- Comparative benchmarking (industry standards)
- Multi-device correlation analysis
- What-if scenario modeling

## Testing Phase 4

### Test 1: Cost Trends
```bash
# Add power readings over several days
for day in {1..7}; do
    curl -X POST http://localhost:5000/api/devices/actuators/1/power-readings \
        -H "Content-Type: application/json" \
        -d "{\"power_watts\": 145.5, \"energy_kwh\": 3.42}"
    sleep 86400  # Wait 1 day (or mock timestamp)
done

# Get cost trends
curl http://localhost:5000/api/devices/actuators/1/energy/cost-trends?days=7
```

### Test 2: Recommendations
```bash
# Add varied power readings (simulate different scenarios)
# High standby power
curl -X POST ... -d "{\"power_watts\": 8.5}"

# Get recommendations
curl http://localhost:5000/api/devices/actuators/1/energy/recommendations
```

### Test 3: Anomaly Detection
```bash
# Add normal readings
for i in {1..50}; do
    curl -X POST ... -d "{\"power_watts\": 145.0}"
done

# Add spike
curl -X POST ... -d "{\"power_watts\": 350.0}"

# Detect anomalies
curl http://localhost:5000/api/devices/actuators/1/energy/anomalies?hours=1
```

### Test 4: Dashboard
```bash
# Get complete dashboard
curl http://localhost:5000/api/devices/actuators/1/energy/dashboard
```

## Conclusion

Phase 4 transforms the actuator system from simple power monitoring into a comprehensive energy management platform. With cost tracking, optimization recommendations, anomaly detection, and unified dashboards, users can now:

- **Reduce Costs**: Identify wasteful consumption patterns
- **Improve Efficiency**: Implement data-driven optimizations
- **Prevent Failures**: Detect anomalies before they cause damage
- **Make Decisions**: Access actionable insights and recommendations

All analytics are accessible through simple REST API endpoints, enabling integration with dashboards, mobile apps, and automation systems.

## Related Documentation

- [Phase 1: Database Schema Migration](./ACTUATOR_SCHEMA_MIGRATION.md)
- [Phase 2: Service Layer & API Endpoints](./ACTUATOR_API_ENDPOINTS.md)
- [Phase 3: ActuatorManager Integration](./ACTUATOR_MANAGER_INTEGRATION.md)
- [Energy Monitoring Integration](./ENERGY_MONITORING_INTEGRATION.md)
