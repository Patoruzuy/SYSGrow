# Climate Optimizer Service

**ML-powered environmental control optimization**

---

## Overview

The Climate Optimizer uses machine learning to analyze current environmental conditions and recommend optimal adjustments for temperature, humidity, CO2, and light levels. It considers plant type, growth stage, and predicted impact on plant health and growth rate.

---

## Key Features

- **Plant-specific optimization** — 500+ species profiles with optimal ranges
- **Growth stage awareness** — Different thresholds for vegetative, flowering, etc.
- **Day/night profiles** — Separate optimization for light and dark periods
- **Energy-aware** — Balances performance with power consumption
- **Predictive impact** — Estimates growth rate and health score improvements
- **ML-based predictions** — RandomForest models trained on historical data

---

## Quick Start

### Basic Usage

```python
from app.services.ai import ClimateOptimizer

optimizer = container.ai.climate_optimizer

analysis = optimizer.optimize_climate(
    unit_id=1,
    current_conditions={
        "temperature": 24.0,
        "humidity": 60.0,
        "co2": 800.0,
        "light_intensity": 600.0
    },
    plant_type="tomato",
    growth_stage="flowering"
)

print(f"Current score: {analysis.current_score}/100")
print(f"Potential score: {analysis.optimized_score}/100")

for rec in analysis.recommendations:
    print(f"{rec.parameter}: {rec.current_value} → {rec.suggested_value}")
    print(f"  Reason: {rec.rationale}")
    print(f"  Impact: {rec.predicted_impact}")
```

---

## API Reference

### optimize_climate()

**Purpose:** Analyze current conditions and generate optimization recommendations

**Parameters:**
- `unit_id` (int) — Growth unit identifier
- `current_conditions` (dict) — Current sensor readings
  - `temperature` (float) — Current temperature (°C)
  - `humidity` (float) — Current relative humidity (%)
  - `co2` (float, optional) — Current CO2 level (ppm)
  - `light_intensity` (float, optional) — Current light level (lux)
- `plant_type` (str) — Plant species (e.g., "tomato", "basil")
- `growth_stage` (str) — Current growth stage
  - `"seedling"`, `"vegetative"`, `"flowering"`, `"fruiting"`

**Returns:** `ClimateOptimizationAnalysis`
- `current_score` (float) — Current environmental score (0-100)
- `optimized_score` (float) — Predicted score with recommendations applied
- `recommendations` (List[ClimateRecommendation]) — Suggested adjustments
- `predicted_impact` (dict) — Estimated improvements
  - `growth_rate_delta` (float) — Expected growth rate change (%)
  - `health_score_delta` (float) — Expected health score change (%)
  - `energy_cost_delta` (float) — Expected energy cost change (%)

**Example:**
```python
analysis = optimizer.optimize_climate(
    unit_id=1,
    current_conditions={
        "temperature": 28.0,
        "humidity": 45.0,
        "co2": 600.0
    },
    plant_type="tomato",
    growth_stage="flowering"
)

# Check recommendations
if analysis.optimized_score > analysis.current_score + 10:
    print("Significant improvements possible!")
    for rec in analysis.recommendations:
        if rec.priority == "high":
            print(f"Priority: {rec.parameter} → {rec.suggested_value}")
```

---

## Recommendation Structure

### ClimateRecommendation

```python
@dataclass
class ClimateRecommendation:
    parameter: str              # "temperature" | "humidity" | "co2" | "light"
    current_value: float        # Current sensor reading
    suggested_value: float      # Recommended target value
    optimal_range: tuple        # (min, max) optimal range
    priority: str               # "high" | "medium" | "low"
    rationale: str              # Explanation for recommendation
    predicted_impact: str       # Expected outcome
    confidence: float           # 0.0-1.0
```

**Priority Levels:**
- **high** — Critical adjustment needed (>15% deviation from optimal)
- **medium** — Recommended adjustment (5-15% deviation)
- **low** — Minor optimization (0-5% deviation)

---

## Plant-Specific Profiles

### Optimal Ranges by Plant Type

**Tomato:**
```python
{
    "temperature": {
        "vegetative": {"day": (21, 27), "night": (16, 21)},
        "flowering": {"day": (18, 25), "night": (15, 20)},
        "fruiting": {"day": (20, 26), "night": (16, 21)}
    },
    "humidity": {
        "vegetative": (60, 75),
        "flowering": (50, 70),
        "fruiting": (55, 70)
    },
    "co2": (800, 1200),
    "light_intensity": (400, 600)  # µmol/m²/s
}
```

**Basil:**
```python
{
    "temperature": {
        "vegetative": {"day": (20, 25), "night": (16, 21)}
    },
    "humidity": (60, 80),
    "co2": (600, 1000),
    "light_intensity": (300, 500)
}
```

**Lettuce:**
```python
{
    "temperature": {
        "vegetative": {"day": (16, 22), "night": (12, 18)}
    },
    "humidity": (50, 70),
    "co2": (800, 1200),
    "light_intensity": (200, 400)
}
```

---

## ML Model Details

### Feature Engineering

**Input Features (per unit, 24-hour window):**
```python
features = [
    "temp_mean_24h",           # Average temperature
    "temp_std_24h",            # Temperature variability
    "temp_min_24h",            # Minimum temperature
    "temp_max_24h",            # Maximum temperature
    "humidity_mean_24h",       # Average humidity
    "humidity_std_24h",        # Humidity variability
    "co2_mean_24h",            # Average CO2 (if available)
    "co2_std_24h",             # CO2 variability
    "light_hours_24h",         # Total light hours
    "vpd_mean_24h",            # Vapor Pressure Deficit
    "day_night_temp_delta",    # Temperature difference
    "plant_type_encoded",      # One-hot encoded plant type
    "growth_stage_encoded"     # One-hot encoded stage
]
```

### Model Training

**Algorithm:** RandomForest Regressor

**Target Variables:**
- `growth_rate` — cm/day (measured from historical data)
- `health_score` — 0-100 (from PlantHealthMonitor)

**Training Data:**
- 500+ plant profiles
- 10,000+ historical grow cycles
- User feedback on environmental adjustments

**Performance Metrics:**
- MAE (Mean Absolute Error): 0.8 cm/day (growth rate)
- R² Score: 0.87 (growth rate prediction)
- Accuracy: 85-90% (health score prediction within ±5%)

---

## Day/Night Optimization

### Separate Profiles

```python
# Get day-specific recommendations
day_analysis = optimizer.optimize_climate(
    unit_id=1,
    current_conditions=sensor_data,
    plant_type="tomato",
    growth_stage="flowering",
    is_day=True  # Day period
)

# Get night-specific recommendations
night_analysis = optimizer.optimize_climate(
    unit_id=1,
    current_conditions=sensor_data,
    plant_type="tomato",
    growth_stage="flowering",
    is_day=False  # Night period
)
```

**Day vs Night Differences:**
- **Temperature:** Lower at night (stress recovery)
- **Humidity:** Higher at night (reduce transpiration)
- **CO2:** Lower at night (no photosynthesis)
- **Light:** Off at night (respiration period)

---

## Energy Optimization

### Power Consumption Awareness

```python
analysis = optimizer.optimize_climate(
    unit_id=1,
    current_conditions=sensor_data,
    plant_type="tomato",
    growth_stage="flowering",
    energy_priority="balanced"  # "performance" | "balanced" | "efficiency"
)

# Energy priority affects recommendations:
# - "performance": Max growth, ignore energy costs
# - "balanced": Optimize growth/energy trade-off
# - "efficiency": Minimize energy, maintain health
```

**Energy Cost Estimation:**
```python
for rec in analysis.recommendations:
    if rec.parameter == "temperature":
        # Heating/cooling cost
        cost_delta = rec.suggested_value - rec.current_value
        energy_kwh = abs(cost_delta) * 0.5  # Estimate
        print(f"Energy impact: {energy_kwh:.2f} kWh/day")
```

---

## Integration Examples

### Automated Climate Control

```python
from app.services.device import DeviceService

device_service = container.device_service

# Get optimization recommendations
analysis = optimizer.optimize_climate(
    unit_id=1,
    current_conditions=sensor_data,
    plant_type="tomato",
    growth_stage="flowering"
)

# Apply high-priority recommendations automatically
for rec in analysis.recommendations:
    if rec.priority == "high" and rec.confidence > 0.8:
        if rec.parameter == "temperature":
            # Activate heater or cooler
            if rec.suggested_value > rec.current_value:
                device_service.activate_device(heater_id, duration=300)
            else:
                device_service.activate_device(cooler_id, duration=300)
        
        elif rec.parameter == "humidity":
            # Activate humidifier or dehumidifier
            if rec.suggested_value > rec.current_value:
                device_service.activate_device(humidifier_id, duration=180)
```

### Scheduled Optimization

```python
from app.workers import ScheduledTask

# Run optimization every hour
@ScheduledTask(interval=3600)
def optimize_all_units():
    active_units = growth_service.get_active_units()
    
    for unit in active_units:
        analysis = optimizer.optimize_climate(
            unit_id=unit.id,
            current_conditions=unit.current_conditions,
            plant_type=unit.plant_type,
            growth_stage=unit.growth_stage
        )
        
        # Store recommendations in analytics
        analytics_repo.store_insight(
            type="climate_optimization",
            unit_id=unit.id,
            data={
                "current_score": analysis.current_score,
                "optimized_score": analysis.optimized_score,
                "recommendations": [r.to_dict() for r in analysis.recommendations]
            }
        )
```

---

## API Endpoints

### GET /api/v1/units/{unit_id}/climate/optimize

**Description:** Get climate optimization recommendations for a unit

**Parameters:**
- `unit_id` (path) — Growth unit ID
- `energy_priority` (query, optional) — "performance" | "balanced" | "efficiency"

**Response:**
```json
{
  "current_score": 72.5,
  "optimized_score": 88.3,
  "recommendations": [
    {
      "parameter": "temperature",
      "current_value": 28.0,
      "suggested_value": 24.0,
      "optimal_range": [21, 27],
      "priority": "high",
      "rationale": "Current temperature is 1°C above optimal range, reducing growth rate by ~8%",
      "predicted_impact": "Reduce temperature to increase growth rate by 12% and health score by 8%",
      "confidence": 0.89
    },
    {
      "parameter": "humidity",
      "current_value": 45.0,
      "suggested_value": 65.0,
      "optimal_range": [60, 75],
      "priority": "medium",
      "rationale": "Humidity below optimal range may cause water stress",
      "predicted_impact": "Increase humidity to reduce water stress and improve nutrient uptake",
      "confidence": 0.76
    }
  ],
  "predicted_impact": {
    "growth_rate_delta": 12.5,
    "health_score_delta": 8.2,
    "energy_cost_delta": 5.3
  }
}
```

---

## Performance Considerations

### Raspberry Pi Optimization

**Model size:** ~15MB (RandomForest)  
**Inference time:** ~150-200ms per unit  
**Memory usage:** ~80MB resident

**Tips for Pi:**
```bash
# Enable model caching
MODEL_CACHE_PREDICTIONS=true
MODEL_CACHE_TTL=300  # Cache for 5 minutes

# Limit concurrent optimizations
MAX_CONCURRENT_PREDICTIONS=1
```

### Desktop Performance

**Inference time:** <100ms per unit  
**Memory usage:** ~60MB resident

---

## Troubleshooting

### Issue: Recommendations seem incorrect

**Check plant profile:**
```python
from app.services.ai import ThresholdService

threshold_service = container.threshold_service

optimal_ranges = threshold_service.get_optimal_ranges(
    plant_type="tomato",
    growth_stage="flowering"
)
print(optimal_ranges)
```

**Verify sensor data quality:**
```python
# Check for sensor anomalies
if abs(sensor_data['temperature'] - prev_temp) > 10:
    print("Warning: Temperature spike detected")
```

### Issue: Low confidence scores

**Possible causes:**
- Insufficient historical data for plant type
- Unusual environmental conditions (outside training distribution)
- Sensor calibration issues

**Solutions:**
```python
# Collect more training data
ENABLE_TRAINING_DATA_COLLECTION=true

# Force model retraining
curl -X POST http://localhost:5000/api/v1/ai/retrain/climate_optimizer
```

---

## Related Documentation

- **[AI Services Overview](README.md)** — Complete AI feature guide
- **[Plant Health Monitoring](PLANT_HEALTH_MONITORING.md)** — Disease detection
- **[Continuous Monitoring](CONTINUOUS_MONITORING.md)** — Real-time surveillance
- **[Architecture](../architecture/AI_ARCHITECTURE.md)** — System design

---

**Questions?** Check the [FAQ](FAQ.md) or open an issue on GitHub.
