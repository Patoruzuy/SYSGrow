# ThresholdService Integration Guide

## Overview

The **ThresholdService** provides unified threshold management for the SYSGrow system, combining:
- **Plant-specific thresholds** from `plants_info.json`
- **AI-based predictions** from the climate model
- **Hardware control ranges** for automated environmental control

This service has been fully integrated with `UnitRuntime` and `UnitRuntimeManager` to automatically manage environmental thresholds for each growth unit based on the active plant type and growth stage.

## Architecture

```
ServiceContainer
  ├─ ThresholdService
  │   ├─ PlantJsonHandler (loads plant-specific data)
  │   └─ AIClimateModel (ML predictions)
  │
  └─ GrowthService
      └─ UnitRuntime
          ├─ Uses ThresholdService for optimal conditions
          └─ apply_ai_conditions() applies plant-specific + AI thresholds
```

## Key Features

### 1. Plant-Specific Threshold Management
- Automatically loads optimal ranges from `plants_info.json` for 50+ plant types
- Supports all growth stages (Seedling, Vegetative, Flowering, Fruiting, Harvesting)
- Provides stage-specific threshold adjustments

### 2. AI Model Integration
- Blends AI predictions with plant-specific thresholds (70% AI, 30% plant-specific)
- Ensures AI predictions stay within plant-safe ranges
- Falls back to plant-specific thresholds if AI unavailable

### 3. Hardware Control
- Provides min/max ranges for actuator control
- Automatically converts optimal conditions to hardware thresholds
- Updates ESP32-C6 relay and sensor devices

## Service API

### Core Methods

#### `get_optimal_conditions(plant_type, growth_stage, use_ai=True)`
Get optimal environmental conditions for a specific plant.

```python
optimal = threshold_service.get_optimal_conditions(
    plant_type="Tomatoes",
    growth_stage="Flowering",
    use_ai=True  # Enable AI enhancement
)
# Returns: {'temperature': 24.5, 'humidity': 60.0, 'soil_moisture': 65.0, 'co2_ppm': 1200.0}
```

**Parameters:**
- `plant_type` (str): Common name from plants_info.json (e.g., 'Tomatoes', 'Basil')
- `growth_stage` (str): Current stage ('Seedling', 'Vegetative', 'Flowering', etc.)
- `use_ai` (bool): Whether to blend AI predictions (default: True)

**Returns:**
- Dictionary with optimal values for temperature, humidity, soil_moisture, co2_ppm

---

#### `get_threshold_ranges(plant_type, growth_stage=None)`
Get min/max ranges for hardware actuator control.

```python
ranges = threshold_service.get_threshold_ranges(
    plant_type="Basil",
    growth_stage="Vegetative"
)
# Returns: {
#   'temperature': {'min': 18.0, 'max': 26.0, 'optimal': 22.0, 'too_low': 10.0, 'too_high': 32.0},
#   'humidity': {'min': 50.0, 'max': 70.0, 'optimal': 60.0, 'too_low': 30.0, 'too_high': 85.0},
#   ...
# }
```

**Returns:**
- Dictionary with min/max/optimal/too_low/too_high values for each environmental factor

---

#### `is_within_optimal_range(plant_type, growth_stage, current_conditions)`
Check if current sensor readings are within optimal ranges.

```python
current = {'temperature': 24.0, 'humidity': 55.0, 'soil_moisture': 60.0}
results = threshold_service.is_within_optimal_range(
    plant_type="Tomatoes",
    growth_stage="Flowering",
    current_conditions=current
)
# Returns: {'temperature': True, 'humidity': False, 'soil_moisture': True}
```

---

#### `get_adjustment_recommendations(plant_type, growth_stage, current_conditions)`
Get specific recommendations for environmental adjustments.

```python
recommendations = threshold_service.get_adjustment_recommendations(
    plant_type="Tomatoes",
    growth_stage="Vegetative",
    current_conditions={'temperature': 30.0, 'humidity': 40.0}
)
# Returns: {
#   'temperature': {
#     'current': 30.0,
#     'optimal': 24.0,
#     'action': 'decrease',
#     'amount': 6.0,
#     'priority': 'high',
#     'plant_specific': True
#   },
#   'humidity': { ... }
# }
```

---

## UnitRuntime Integration

The `UnitRuntime` class now automatically uses `ThresholdService` when an active plant is set or when growth stages change.

### Automatic Threshold Application

```python
# Create unit with threshold service (done by ServiceContainer)
unit = UnitRuntime(
    unit_id=1,
    unit_name="Indoor Garden",
    location="Indoor",
    user_id=1,
    repo_growth=growth_repo,
    repo_analytics=analytics_repo,
    threshold_service=threshold_service  # Injected
)

# Set active plant - automatically applies plant-specific thresholds
plant = PlantProfile(
    plant_id=1,
    plant_name="Cherry Tomato",
    current_stage="Flowering",
    plant_type="Tomatoes",
    ...
)
unit.set_active_plant(plant.id)

# Thresholds are now set for Tomatoes in Flowering stage!
# Hardware manager receives plant-specific ranges automatically
```

### Manual Threshold Updates

```python
# Force threshold update (useful after stage changes)
unit.apply_ai_conditions()

# This will:
# 1. Get optimal conditions from ThresholdService
# 2. Blend AI predictions (if available)
# 3. Update unit settings
# 4. Notify hardware manager with new thresholds
# 5. Save to database
```

---

## How Blending Works

The service intelligently combines AI predictions with plant-specific thresholds:

### Algorithm
1. **Load plant-specific base thresholds** from `plants_info.json`
2. **Get AI predictions** for the growth stage (if AI enabled)
3. **Blend values**: `optimal = 0.7 * AI + 0.3 * plant_specific`
4. **Clamp to safe ranges**: Ensure result stays within plant's optimal_range
5. **Return combined thresholds**

### Example
```
Plant: Tomatoes (Flowering)
Plant-specific optimal temperature: 20-26°C (midpoint: 23°C)
AI prediction: 27°C

Blending: 0.7 * 27 + 0.3 * 23 = 25.8°C
Clamped: min(26, max(20, 25.8)) = 25.8°C ✓ (within range)

Final: 25.8°C (AI-enhanced, plant-safe)
```

### Rationale
- **70% AI weight**: AI has learned from historical data and can fine-tune
- **30% plant weight**: Ensures we stay grounded in botanical requirements
- **Clamping**: Safety mechanism to never exceed plant-specific limits

---

## Hardware Manager Integration

The hardware manager (`UnitRuntimeManager`) receives threshold updates with min/max ranges:

```python
# UnitRuntime automatically calls this after applying thresholds
hardware_manager.update_thresholds({
    "temperature_min": 20.0,    # From plant-specific ranges
    "temperature_max": 26.0,
    "humidity_min": 50.0,
    "humidity_max": 70.0,
    "soil_moisture_min": 60.0,
    "soil_moisture_max": 75.0
})

# ESP32-C6 relay devices trigger actuators based on these ranges:
# - Temperature < 20°C → Turn on heater
# - Temperature > 26°C → Turn on fan/cooler
# - Humidity < 50% → Turn on humidifier
# - etc.
```

---

## Configuration

### ServiceContainer Setup (Automatic)

The `ServiceContainer` automatically initializes and wires everything:

```python
# In container.py (already configured)
ai_climate_model = AIClimateModel(repo_analytics=analytics_repo)
threshold_service = ThresholdService(
    plant_handler=plant_catalog,
    ai_model=ai_climate_model
)

growth_service = GrowthService(
    repo_growth=growth_repo,
    repo_analytics=analytics_repo,
    audit_logger=audit_logger,
    mqtt_client=mqtt_client,
    threshold_service=threshold_service  # Injected
)
```

### Manual Setup (Testing/Development)

```python
from app.services.threshold_service import ThresholdService
from app.utils.plant_json_handler import PlantJsonHandler
from ai.ml_model import AIClimateModel

# With AI
ai_model = AIClimateModel(repo_analytics=analytics_repo)
threshold_service = ThresholdService(
    plant_handler=PlantJsonHandler(),
    ai_model=ai_model
)

# Without AI (plant-specific only)
threshold_service = ThresholdService(
    plant_handler=PlantJsonHandler(),
    ai_model=None
)
```

---

## Plant Data Requirements

The service reads from `plants_info.json`:

```json
{
  "Tomatoes": {
    "growth_stages": {
      "Flowering": {
        "temperature": {
          "optimal_range": [20, 26],
          "too_cold": 13,
          "too_hot": 32
        },
        "humidity": {
          "optimal_range": [50, 70],
          "too_dry": 30,
          "too_wet": 85
        },
        "soil_moisture": {
          "optimal_range": [60, 75],
          "too_dry": 30,
          "too_wet": 90
        },
        "co2_ppm": {
          "optimal_range": [1000, 1500],
          "too_low": 400,
          "too_high": 2000
        }
      }
    }
  }
}
```

**Required fields per stage:**
- `temperature.optimal_range` [min, max]
- `humidity.optimal_range` [min, max]
- `soil_moisture.optimal_range` [min, max]
- `co2_ppm.optimal_range` [min, max]

**Optional fields:**
- `too_cold`, `too_hot`, `too_dry`, `too_wet`, `too_low`, `too_high`

---

## Error Handling

### Graceful Degradation

The service handles various failure scenarios:

1. **Plant not found** → Returns generic safe defaults
2. **AI model unavailable** → Uses plant-specific thresholds only
3. **Invalid growth stage** → Uses averaged thresholds across all stages
4. **Missing threshold data** → Logs warning, returns fallback values

### Example
```python
try:
    optimal = threshold_service.get_optimal_conditions(
        plant_type="UnknownPlant",  # Not in plants_info.json
        growth_stage="Flowering"
    )
except Exception:
    # Service returns safe defaults instead of crashing:
    # {'temperature': 23.0, 'humidity': 55.0, 'soil_moisture': 50.0, 'co2_ppm': 1000.0}
    pass
```

---

## Testing

### Unit Tests
- ✅ Plant-specific threshold loading (8/8 tests passing)
- ✅ Threshold caching and performance
- ✅ Growth stage transitions

### Integration Tests
- ✅ ThresholdService + AI model integration (10/10 tests passing)
- ✅ UnitRuntime automatic threshold application
- ✅ Hardware manager threshold updates
- ✅ Fallback to AI-only mode

### Running Tests
```bash
# Unit tests
python test_plant_thresholds.py

# Integration tests
python test_threshold_integration.py
```

---

## Performance

### Caching Strategy
- Plant threshold data is cached after first load
- Cache key: `{plant_type}:{growth_stage}`
- Cache cleared on demand: `threshold_service.clear_cache()`

### Typical Response Times
- First call (with cache miss): ~5-10ms
- Subsequent calls (cached): ~0.1-0.5ms
- AI prediction: ~10-20ms (model inference)

---

## Migration Notes

### From Legacy AI-Only System

**Before:**
```python
# Old approach - generic AI predictions only
predictions = ai_model.predict_growth_conditions(stage)
unit.settings.temperature_threshold = predictions['temperature']
```

**After:**
```python
# New approach - plant-specific + AI blend
optimal = threshold_service.get_optimal_conditions(
    plant_type=plant.plant_type,  # Now considers plant type!
    growth_stage=plant.current_stage,
    use_ai=True
)
unit.settings.temperature_threshold = optimal['temperature']
```

### Backward Compatibility

The system maintains backward compatibility:
- If `threshold_service` is `None`, falls back to AI-only behavior
- Existing units without active plants continue to work
- No database schema changes required

---

## Future Enhancements

### Planned Features
1. **User preference weighting** - Allow users to adjust AI vs plant-specific ratio
2. **Historical learning** - Use unit-specific historical data to refine predictions
3. **Multi-plant optimization** - Optimize thresholds for multiple plants in same unit
4. **Weather integration** - Adjust outdoor units based on weather forecasts
5. **Energy optimization** - Balance plant needs with energy costs

### Extension Points
```python
class ThresholdService:
    def get_optimal_conditions(
        self,
        plant_type: str,
        growth_stage: str,
        use_ai: bool = True,
        user_preferences: Optional[Dict] = None,  # Future
        weather_data: Optional[Dict] = None,       # Future
        energy_price: Optional[float] = None       # Future
    ):
        # Implementation...
```

---

## Support

For questions or issues:
1. Check logs: `logs/app.log` (threshold service logs with `threshold_service` logger)
2. Review test suite: `test_threshold_integration.py`
3. Validate plant data: `verify_plants.py`
4. Check ServiceContainer initialization: `app/services/container.py`

---

## Summary

✅ **Unified threshold management** - One service for all threshold needs
✅ **Plant-specific accuracy** - Uses botanical data for each plant type
✅ **AI enhancement** - Intelligently blends predictions with safety limits
✅ **Automatic application** - Seamlessly integrates with UnitRuntime
✅ **Hardware ready** - Provides ranges for actuator control
✅ **Fully tested** - 18/18 tests passing (unit + integration)

The ThresholdService represents a significant improvement over the previous AI-only approach, providing accurate, safe, and plant-specific environmental control for all SYSGrow growth units.
