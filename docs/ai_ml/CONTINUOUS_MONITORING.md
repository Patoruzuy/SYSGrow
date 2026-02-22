# Continuous Monitoring Service

**Real-time plant health surveillance and alerting**

---

## Overview

The Continuous Monitoring Service runs in the background, performing automated health checks every 5 minutes. It executes six analysis steps: disease prediction, climate optimization, growth tracking, trend analysis, environmental health scoring, and recommendation generation. All insights are stored in the analytics database for review and notification.

---

## Key Features

- **Automated surveillance** — Runs every 5 minutes (configurable)
- **Six analysis steps** — Comprehensive multi-layer health checks
- **Real-time alerting** — Immediate notifications for critical issues
- **Historical tracking** — All insights stored in database
- **Low overhead** — ~2-5% CPU usage on Raspberry Pi
- **Graceful degradation** — Continues running even if one step fails

---

## Quick Start

### Enabling Continuous Monitoring

```bash
# .env or ops.env
ENABLE_CONTINUOUS_MONITORING=true
CONTINUOUS_MONITORING_INTERVAL=300  # 5 minutes (in seconds)
```

### Checking Status

```python
from app.services.ai import ContinuousMonitoringService

monitor = container.optional_ai.continuous_monitor

if monitor:
    print(f"Status: {monitor.status}")  # "running" | "stopped"
    print(f"Last check: {monitor.last_check_time}")
    print(f"Checks performed: {monitor.check_count}")
else:
    print("Continuous monitoring not enabled")
```

---

## Six Analysis Steps

### Step 1: Disease Risk Prediction

**Purpose:** Identify units at risk of disease based on environmental conditions and symptoms

```python
# Pseudo-code for disease prediction step
for unit in active_units:
    # Get disease prediction
    risk = disease_predictor.predict_diseases(
        unit_id=unit.id,
        environmental_data=unit.current_conditions
    )
    
    # Alert if high risk
    if risk.probability > 0.5:
        analytics_repo.store_insight(
            type="disease_risk",
            severity="high",
            unit_id=unit.id,
            data={
                "disease": risk.disease_name,
                "probability": risk.probability,
                "matched_symptoms": risk.matched_symptoms,
                "recommended_actions": risk.recommended_actions
            }
        )
        
        # Send real-time notification
        socketio.emit('health_alert', {
            "unit_id": unit.id,
            "alert_type": "disease_risk",
            "disease": risk.disease_name,
            "probability": risk.probability
        })
```

**Triggers alert when:**
- Disease probability > 0.5
- Critical environmental anomaly detected
- Multiple symptoms match known disease pattern

---

### Step 2: Climate Optimization

**Purpose:** Generate environmental adjustment recommendations

```python
# Pseudo-code for climate optimization step
for unit in active_units:
    # Get optimization analysis
    analysis = climate_optimizer.optimize_climate(
        unit_id=unit.id,
        current_conditions=unit.current_conditions,
        plant_type=unit.plant_type,
        growth_stage=unit.growth_stage
    )
    
    # Store if improvements possible
    if analysis.optimized_score > analysis.current_score + 10:
        analytics_repo.store_insight(
            type="climate_optimization",
            severity="medium",
            unit_id=unit.id,
            data={
                "current_score": analysis.current_score,
                "optimized_score": analysis.optimized_score,
                "recommendations": [r.to_dict() for r in analysis.recommendations]
            }
        )
```

**Stores insight when:**
- Optimized score > current score + 10 points
- High-priority recommendations available
- Significant environmental deviation detected

---

### Step 3: Growth Stage Tracking

**Purpose:** Detect imminent growth stage transitions

```python
# Pseudo-code for growth tracking step
for plant in active_plants:
    # Predict stage transition
    transition = growth_predictor.predict_stage_transition(
        plant_id=plant.id,
        current_stage=plant.growth_stage,
        days_in_stage=plant.days_in_current_stage,
        environmental_history=plant.sensor_history
    )
    
    # Alert if transition imminent (within 3 days)
    if transition.predicted_days <= 3:
        analytics_repo.store_insight(
            type="growth_stage_change",
            severity="info",
            unit_id=plant.unit_id,
            data={
                "plant_id": plant.id,
                "current_stage": plant.growth_stage,
                "next_stage": transition.next_stage,
                "predicted_days": transition.predicted_days,
                "confidence": transition.confidence,
                "care_adjustments": transition.recommended_care_changes
            }
        )
```

**Triggers alert when:**
- Stage transition predicted within 3 days
- Confidence > 0.7
- Care adjustments recommended

---

### Step 4: Trend Analysis

**Purpose:** Identify long-term environmental patterns and anomalies

```python
# Pseudo-code for trend analysis step
for unit in active_units:
    # Analyze 24-hour trends
    trends = _analyze_trends(
        sensor_history=unit.sensor_readings_24h,
        window_hours=24
    )
    
    # Check for anomalies
    anomalies = []
    
    if trends.temperature_trend_slope > 0.5:  # Rapid warming
        anomalies.append({
            "parameter": "temperature",
            "trend": "increasing",
            "rate": trends.temperature_trend_slope,
            "concern": "heat stress risk"
        })
    
    if trends.humidity_trend_slope < -2.0:  # Rapid drying
        anomalies.append({
            "parameter": "humidity",
            "trend": "decreasing",
            "rate": trends.humidity_trend_slope,
            "concern": "dehydration risk"
        })
    
    # Store if anomalies detected
    if anomalies:
        analytics_repo.store_insight(
            type="environmental_trend",
            severity="medium",
            unit_id=unit.id,
            data={"anomalies": anomalies}
        )
```

**Anomaly detection criteria:**
- Temperature increase > 0.5°C/hour
- Humidity decrease > 2%/hour
- Soil moisture decrease > 5%/hour
- CO2 level fluctuation > 200ppm/hour

---

### Step 5: Environmental Health Scoring

**Purpose:** Score leaf health based on environmental stress

```python
# Pseudo-code for environmental health step
for unit in active_units:
    # Score environmental impact
    score = environmental_health_scorer.score_environmental_health(
        plant_type=unit.plant_type,
        growth_stage=unit.growth_stage,
        temperature=unit.temperature,
        humidity=unit.humidity,
        light_intensity=unit.light_intensity
    )
    
    # Alert if score is low (< 60)
    if score.overall_score < 60:
        analytics_repo.store_insight(
            type="environmental_stress",
            severity="high" if score.overall_score < 40 else "medium",
            unit_id=unit.id,
            data={
                "overall_score": score.overall_score,
                "stress_factors": score.stress_factors,
                "predicted_symptoms": score.predicted_symptoms,
                "urgency": "immediate" if score.overall_score < 40 else "moderate"
            }
        )
```

**Alert thresholds:**
- Score < 40: High severity (immediate action needed)
- Score 40-60: Medium severity (monitor closely)
- Score 60-80: Low severity (minor adjustments)
- Score > 80: Healthy (no action needed)

---

### Step 6: Recommendation Generation

**Purpose:** Generate actionable care recommendations

```python
# Pseudo-code for recommendation step
for unit in active_units:
    # Build context from previous steps
    context = RecommendationContext(
        unit_id=unit.id,
        plant_type=unit.plant_type,
        growth_stage=unit.growth_stage,
        environmental_data=unit.current_conditions,
        symptoms=unit.detected_symptoms,  # From Step 1
        recent_insights=unit.recent_insights  # From Steps 1-5
    )
    
    # Get recommendations
    recommendations = recommendation_provider.get_recommendations(context)
    
    # Store high-priority recommendations
    for rec in recommendations:
        if rec.priority == "high":
            analytics_repo.store_insight(
                type="recommendation",
                severity="high",
                unit_id=unit.id,
                data={
                    "action": rec.action,
                    "priority": rec.priority,
                    "rationale": rec.rationale,
                    "confidence": rec.confidence,
                    "category": rec.category
                }
            )
```

---

## Service Lifecycle

### Startup

```python
# In container_builder.py
if config.enable_continuous_monitoring:
    monitor = ContinuousMonitoringService(
        disease_predictor=disease_predictor,
        climate_optimizer=climate_optimizer,
        health_monitor=health_monitor,
        growth_predictor=growth_predictor,
        environmental_health_scorer=environmental_health_scorer,
        recommendation_provider=recommendation_provider,
        analytics_repo=analytics_repo,
        check_interval=config.continuous_monitoring_interval
    )
    
    # Start background thread
    monitor.start_monitoring()
```

### Monitoring Loop

```python
def _monitoring_loop(self):
    """Background thread that performs continuous monitoring"""
    
    while self._running:
        try:
            # Perform all 6 analysis steps
            self._perform_monitoring_cycle()
            
            # Update counters
            self.check_count += 1
            self.last_check_time = datetime.now()
            
            # Sleep until next check
            time.sleep(self.check_interval)
            
        except Exception as e:
            logger.error(f"Monitoring cycle error: {e}")
            # Continue running despite errors
            time.sleep(self.check_interval)
```

### Shutdown

```python
# Graceful shutdown
monitor.stop_monitoring()  # Stops background thread
```

---

## Querying Insights

### Get Recent Insights

```python
from app.repositories import AnalyticsRepository

analytics_repo = container.analytics_repo

# Get all insights for a unit (last 24 hours)
insights = analytics_repo.get_insights(
    unit_id=1,
    time_range="last_24h"
)

for insight in insights:
    print(f"[{insight.type}] {insight.severity}: {insight.data}")
```

### Filter by Type

```python
# Get only disease risk alerts
disease_risks = analytics_repo.get_insights(
    unit_id=1,
    insight_type="disease_risk",
    time_range="last_7d"
)

# Get only high-severity insights
critical_insights = analytics_repo.get_insights(
    unit_id=1,
    severity="high",
    time_range="last_24h"
)
```

### Group by Category

```python
# Group insights by type
insight_counts = {}
insights = analytics_repo.get_insights(unit_id=1, time_range="last_7d")

for insight in insights:
    insight_counts[insight.type] = insight_counts.get(insight.type, 0) + 1

print(insight_counts)
# {"disease_risk": 3, "climate_optimization": 12, "environmental_stress": 5, ...}
```

---

## Real-Time Notifications

### SocketIO Integration

```python
from flask_socketio import emit

def _send_alert(self, unit_id: int, alert_type: str, data: dict):
    """Send real-time alert via SocketIO"""
    
    # Emit to unit-specific room
    emit('health_alert', {
        "unit_id": unit_id,
        "alert_type": alert_type,
        "timestamp": datetime.now().isoformat(),
        "data": data
    }, room=f'unit_{unit_id}')
    
    # Also emit to all users monitoring this unit
    unit = growth_service.get_unit(unit_id)
    for user_id in unit.subscribed_users:
        emit('health_alert', {
            "unit_id": unit_id,
            "alert_type": alert_type,
            "data": data
        }, room=f'user_{user_id}')
```

### Frontend Integration

```javascript
// Subscribe to continuous monitoring alerts
const socket = io();

socket.on('health_alert', (alert) => {
  console.log(`Alert for unit ${alert.unit_id}:`, alert.data);
  
  if (alert.alert_type === 'disease_risk') {
    showNotification('⚠️ Disease Risk Detected', 
      `${alert.data.disease}: ${(alert.data.probability * 100).toFixed(0)}% probability`);
  } else if (alert.alert_type === 'environmental_stress') {
    showNotification('🌡️ Environmental Stress', 
      `Health score: ${alert.data.overall_score}/100`);
  }
});
```

---

## Configuration

### Environment Variables

```bash
# Enable continuous monitoring
ENABLE_CONTINUOUS_MONITORING=true

# Check interval (seconds)
CONTINUOUS_MONITORING_INTERVAL=300  # 5 minutes

# Alert thresholds
DISEASE_RISK_THRESHOLD=0.5          # Alert if probability > 0.5
CLIMATE_SCORE_THRESHOLD=10          # Alert if potential improvement > 10 pts
HEALTH_SCORE_THRESHOLD=60           # Alert if score < 60
GROWTH_TRANSITION_THRESHOLD=3       # Alert if transition within 3 days

# Performance limits
MAX_CONCURRENT_MONITORING_UNITS=10  # Process units in batches
MONITORING_TIMEOUT=60               # Max time per monitoring cycle (seconds)
```

### Runtime Configuration

```python
from app.config import AppConfig

config = AppConfig()

print(f"Monitoring enabled: {config.enable_continuous_monitoring}")
print(f"Check interval: {config.continuous_monitoring_interval}s")
```

---

## Performance Considerations

### Resource Usage

**Raspberry Pi 5 (8GB):**
- CPU: 2-5% (during monitoring cycle)
- Memory: ~200MB resident
- Disk I/O: ~10 writes/minute (insight storage)

**Monitoring cycle time:**
- 5 units: ~2-3 seconds
- 10 units: ~5-7 seconds
- 20 units: ~10-15 seconds

**Recommendation:** Set `MAX_CONCURRENT_MONITORING_UNITS=5` on Pi to avoid CPU spikes.

---

### Optimization Tips

**1. Increase interval on resource-constrained devices:**
```bash
CONTINUOUS_MONITORING_INTERVAL=600  # 10 minutes instead of 5
```

**2. Limit concurrent processing:**
```bash
MAX_CONCURRENT_MONITORING_UNITS=3  # Process 3 units at a time
```

**3. Disable specific steps:**
```python
# In container_builder.py
monitor = ContinuousMonitoringService(
    disease_predictor=None,  # Disable disease prediction
    climate_optimizer=climate_optimizer,
    # ... other services
)
```

**4. Cache sensor data:**
```bash
MODEL_CACHE_PREDICTIONS=true
MODEL_CACHE_TTL=300  # 5 minutes
```

---

## API Endpoints

### GET /api/v1/monitoring/status

**Description:** Get continuous monitoring status

**Response:**
```json
{
  "enabled": true,
  "status": "running",
  "check_interval": 300,
  "last_check_time": "2026-02-14T10:35:00Z",
  "check_count": 142,
  "active_units": 8,
  "last_cycle_duration": 4.2
}
```

### GET /api/v1/insights/unit/{unit_id}

**Description:** Get insights for a specific unit

**Query Parameters:**
- `type` (optional) — Filter by insight type
- `severity` (optional) — Filter by severity
- `time_range` (optional) — "last_24h" | "last_7d" | "last_30d"
- `limit` (optional) — Max results (default: 100)

**Response:**
```json
{
  "insights": [
    {
      "id": 1234,
      "type": "disease_risk",
      "severity": "high",
      "unit_id": 1,
      "timestamp": "2026-02-14T10:30:00Z",
      "data": {
        "disease": "powdery_mildew",
        "probability": 0.72,
        "matched_symptoms": ["white_powdery_coating"],
        "recommended_actions": ["Increase air circulation", "Apply neem oil"]
      }
    },
    {
      "id": 1235,
      "type": "climate_optimization",
      "severity": "medium",
      "unit_id": 1,
      "timestamp": "2026-02-14T10:35:00Z",
      "data": {
        "current_score": 68.5,
        "optimized_score": 82.3,
        "recommendations": [...]
      }
    }
  ],
  "total": 2
}
```

### POST /api/v1/monitoring/acknowledge/{insight_id}

**Description:** Acknowledge an insight (mark as read)

**Response:**
```json
{
  "insight_id": 1234,
  "acknowledged": true,
  "acknowledged_by": 1,
  "acknowledged_at": "2026-02-14T10:40:00Z"
}
```

---

## Troubleshooting

### Issue: Monitoring not running

**Check configuration:**
```bash
python -c "from app.config import AppConfig; c = AppConfig(); \
  print('Enabled:', c.enable_continuous_monitoring)"
```

**Check service status:**
```python
monitor = container.optional_ai.continuous_monitor
if not monitor:
    print("Continuous monitoring not initialized (check config)")
elif monitor.status != "running":
    print(f"Monitoring status: {monitor.status}")
    print(f"Last error: {monitor.last_error}")
```

---

### Issue: High CPU usage

**Check monitoring cycle time:**
```python
monitor = container.optional_ai.continuous_monitor
print(f"Last cycle duration: {monitor.last_cycle_duration:.2f}s")
print(f"Active units: {monitor.active_unit_count}")
```

**Solutions:**
```bash
# Increase interval
CONTINUOUS_MONITORING_INTERVAL=600  # 10 minutes

# Limit concurrent processing
MAX_CONCURRENT_MONITORING_UNITS=3

# Disable expensive steps
# (Edit container_builder.py to pass None for specific services)
```

---

### Issue: Too many alerts

**Adjust thresholds:**
```bash
# Make alerts less sensitive
DISEASE_RISK_THRESHOLD=0.7          # Up from 0.5
HEALTH_SCORE_THRESHOLD=50           # Down from 60
CLIMATE_SCORE_THRESHOLD=15          # Up from 10
```

**Filter alerts by severity:**
```python
# Only show high-severity insights
high_priority = analytics_repo.get_insights(
    unit_id=1,
    severity="high",
    time_range="last_24h"
)
```

---

## Best Practices

### 1. Monitor Monitoring Performance

```python
from app.workers import ScheduledTask

@ScheduledTask(interval=86400)  # Daily
def review_monitoring_performance():
    """Check if monitoring is performing well"""
    
    monitor = container.optional_ai.continuous_monitor
    
    # Check cycle duration
    if monitor.last_cycle_duration > 30:
        logger.warning(f"Slow monitoring cycle: {monitor.last_cycle_duration:.2f}s")
    
    # Check error rate
    if monitor.error_count > monitor.check_count * 0.1:
        logger.error(f"High error rate: {monitor.error_count}/{monitor.check_count}")
```

### 2. Archive Old Insights

```python
@ScheduledTask(interval=604800)  # Weekly
def archive_old_insights():
    """Archive insights older than 30 days"""
    
    cutoff_date = datetime.now() - timedelta(days=30)
    
    archived = analytics_repo.archive_insights_before(cutoff_date)
    logger.info(f"Archived {archived} old insights")
```

### 3. Prioritize Critical Insights

```python
# Query insights with priority order
insights = analytics_repo.get_insights(
    unit_id=1,
    time_range="last_24h",
    order_by="severity DESC, timestamp DESC"
)

# Process critical insights first
for insight in insights:
    if insight.severity == "high":
        handle_critical_insight(insight)
```

---

## Related Documentation

- **[AI Services Overview](README.md)** — Complete AI feature guide
- **[Climate Optimizer](CLIMATE_OPTIMIZER.md)** — Environmental optimization
- **[Plant Health Monitoring](PLANT_HEALTH_MONITORING.md)** — Disease detection
- **[Architecture](../architecture/AI_ARCHITECTURE.md)** — System design

---

**Questions?** Check the [FAQ](FAQ.md) or open an issue on GitHub.
