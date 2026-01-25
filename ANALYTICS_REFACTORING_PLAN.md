# Analytics & Energy Endpoints Refactoring Plan

## Status: Medium Priority Recommendations

### Executive Summary
Analysis of analytics and energy endpoints revealed **extensive business logic in API layer** that should be moved to service layer. Optional AI services are properly integrated. This document outlines recommended refactorings to improve maintainability and testability.

---

## 1. Optional AI Services Integration ✅

### Status: **FULLY INTEGRATED**

All optional AI services are properly wired:
- ✅ **ContinuousMonitoringService**: Conditionally loaded via `enable_continuous_monitoring` flag
- ✅ **PersonalizedLearningService**: Conditionally loaded via `enable_personalized_learning` flag  
- ✅ **TrainingDataCollector**: Conditionally loaded via `enable_training_data_collection` flag
- ✅ **AutomatedRetrainingService**: Conditionally loaded via `enable_automated_retraining` flag

### Integration Points:
- **Container Builder** ([container_builder.py](e:\Work\SYSGrow\backend\app\services\container_builder.py) lines 447-550): Checks config flags and imports services only when enabled
- **API Endpoints**: 
  - [monitoring.py](e:\Work\SYSGrow\backend\app\blueprints\api\ml_ai\monitoring.py): Checks `hasattr(container, 'continuous_monitoring_service')` before using (lines 75, 100)
  - [training_data.py](e:\Work\SYSGrow\backend\app\blueprints\api\ml_ai\training_data.py): Uses `_get_training_data_collector()` helper with null checks (lines 50, 87, 131, 171, 216)
- **Configuration**: [raspberry_pi_optimizer.py](e:\Work\SYSGrow\backend\app\utils\raspberry_pi_optimizer.py) lines 218-221 sets flags based on RAM availability

**No action required** - implementation follows best practices with defensive programming.

---

## 2. Energy Endpoints Analysis

### Current Architecture
[energy.py](e:\Work\SYSGrow\backend\app\blueprints\api\devices\actuators\energy.py) (558 lines) delegates properly to services:
- ✅ Power readings: Uses `DeviceHealthService` 
- ✅ Energy stats: Uses `ActuatorManager.get_energy_stats()`
- ✅ Cost estimates: Uses `ActuatorManager.get_cost_estimate()`
- ✅ Advanced analytics: Uses `AnalyticsService` methods

### Energy Monitoring Service Usage
**Finding**: `EnergyMonitoringService` is accessed through `ActuatorManager`:
```python
actuator_manager.energy_monitoring.get_latest_reading(actuator_id)
```

**Status**: ✅ **Proper architecture** - energy monitoring is an internal dependency of ActuatorManager, not exposed directly to API layer.

---

## 3. Analytics Endpoints - Business Logic Extraction

### Problem Statement
Analytics endpoints contain **substantial business logic** that should reside in service layer for:
- Testability (can test calculations without HTTP layer)
- Reusability (other services can use same calculations)
- Separation of concerns (endpoints should orchestrate, not calculate)

### Affected Files

#### A. [efficiency.py](e:\Work\SYSGrow\backend\app\blueprints\api\analytics\efficiency.py) (397 lines)

**Functions with Business Logic**:

1. **`_calculate_environmental_stability()`** (lines ~44-100)
   - Calculates stability scores from temperature/humidity volatility
   - 60+ lines of statistical calculations
   - Should be: `AnalyticsService.calculate_environmental_stability()`

2. **`_calculate_energy_efficiency()`** (lines ~250-320)
   - Calculates energy efficiency scores from consumption patterns
   - Factors: state changes, runtime, anomalies
   - Should be: `AnalyticsService.calculate_energy_efficiency()`

3. **`_calculate_automation_effectiveness()`** (lines ~325-380)
   - Calculates automation quality scores
   - Analyzes manual interventions vs automated actions
   - Should be: `AnalyticsService.calculate_automation_effectiveness()`

**Recommendation**: Extract these 3 functions → `AnalyticsService` methods

---

#### B. [sensors.py](e:\Work\SYSGrow\backend\app\blueprints\api\analytics\sensors.py) (526 lines)

**Functions with Business Logic**:

1. **`_format_sensor_chart_data()`** (lines ~45-120)
   - Transforms raw sensor readings into chart-ready format
   - Handles photoperiod calculations (light duration)
   - Should be: `AnalyticsService.format_sensor_chart_data()`

2. **`_analyze_trends()`** (lines ~150-210)
   - Statistical trend detection (increasing/decreasing/stable)
   - Should be: `AnalyticsService.analyze_value_trends()`

3. **`_extract_lux_value()`** (lines ~85-95)
   - Domain logic for extracting lux from sensor readings
   - Should be: Utility method in sensor-related service

**Additional Logic**:
- `/sensors/comparison` endpoint (lines 240-310): Complex multi-sensor aggregation
- `/sensors/trends` endpoint (lines 312-380): Rolling average calculations

**Recommendation**: Extract utility functions + consider creating `SensorAnalyticsService` for sensor-specific analytics.

---

#### C. [actuators.py](e:\Work\SYSGrow\backend\app\blueprints\api\analytics\actuators.py) (296 lines)

**Key Endpoint**:
- `/actuators/energy-dashboard` (lines 85-200): Aggregates energy data across multiple actuators
  - Calculates total consumption, costs, trends
  - Groups by unit/device
  - Should be: `AnalyticsService.get_energy_dashboard_summary()`

**Recommendation**: Extract dashboard aggregation logic → `AnalyticsService` method

---

#### D. [dashboard.py](e:\Work\SYSGrow\backend\app\blueprints\api\analytics\dashboard.py) (149 lines)

**Status**: ✅ **Minimal logic** - mostly orchestrates calls to existing services. No extraction needed.

---

## 4. Proposed Service Architecture

### Option A: Keep Unified AnalyticsService (Recommended)
**Current**: [analytics_service.py](e:\Work\SYSGrow\backend\app\services\application\analytics_service.py) - 867 lines

**Action**: Add extracted methods to existing service
- Size after additions: ~1100-1200 lines
- Pro: Maintains single source of truth for analytics
- Pro: Existing methods already handle sensor/actuator analytics
- Con: Large file, but justifiable for comprehensive analytics

**New Methods**:
```python
class AnalyticsService:
    # From efficiency.py
    def calculate_environmental_stability(self, unit_id: int, hours: int = 24) -> Dict
    def calculate_energy_efficiency(self, unit_id: int, hours: int = 24) -> Dict
    def calculate_automation_effectiveness(self, unit_id: int, hours: int = 24) -> Dict
    
    # From sensors.py
    def format_sensor_chart_data(self, sensor_id: int, readings: List[Dict]) -> Dict
    def analyze_value_trends(self, values: List[float], timestamps: List[datetime]) -> str
    
    # From actuators.py
    def get_energy_dashboard_summary(self, unit_id: Optional[int] = None) -> Dict
```

---

### Option B: Split into Domain Services
**Alternative**: Create specialized services

```
SensorAnalyticsService (new)
├── format_sensor_chart_data()
├── analyze_value_trends()
├── calculate_sensor_comparison()
└── calculate_environmental_stability()

ActuatorAnalyticsService (new)
├── calculate_energy_efficiency()
├── calculate_automation_effectiveness()
├── get_energy_dashboard_summary()
└── detect_power_anomalies()
```

**Pro**: Smaller, focused services  
**Con**: Potential code duplication for shared analytics logic  
**Con**: More dependency injection complexity

---

## 5. Implementation Priority

### High Priority (Do First)
1. ✅ **Optional AI Services**: Already properly integrated
2. ✅ **Energy Endpoints**: Already use proper service delegation

### Medium Priority (This Phase)
3. **Extract efficiency.py calculation functions** → `AnalyticsService`
   - Impact: 3 complex functions, ~150 lines of business logic
   - Risk: Low (pure calculation functions)
   - Test coverage: Add unit tests for extracted methods

4. **Extract sensors.py utility functions** → `AnalyticsService`
   - Impact: 2-3 helper functions, ~80 lines
   - Risk: Low (formatting/trend analysis)

### Low Priority (Future)
5. **Consider service split** (only if AnalyticsService exceeds 1500 lines)
   - Currently 867 lines
   - After extraction: ~1100-1200 lines
   - Decision point: 1500+ lines

---

## 6. Implementation Steps

### Phase 1: Extract Efficiency Calculations (2-3 hours)
1. Add 3 new methods to `AnalyticsService`:
   - `calculate_environmental_stability()`
   - `calculate_energy_efficiency()`
   - `calculate_automation_effectiveness()`
2. Update [efficiency.py](e:\Work\SYSGrow\backend\app\blueprints\api\analytics\efficiency.py) to call service methods
3. Add unit tests for new methods
4. Verify existing endpoints still work

### Phase 2: Extract Sensor Utilities (1-2 hours)
1. Add methods to `AnalyticsService`:
   - `format_sensor_chart_data()`
   - `analyze_value_trends()`
2. Update [sensors.py](e:\Work\SYSGrow\backend\app\blueprints\api\analytics\sensors.py) to call service methods
3. Add unit tests

### Phase 3: Extract Actuator Dashboard (1 hour)
1. Add `get_energy_dashboard_summary()` to `AnalyticsService`
2. Update [actuators.py](e:\Work\SYSGrow\backend\app\blueprints\api\analytics\actuators.py)
3. Add unit tests

---

## 7. Testing Strategy

### Unit Tests (Add to `tests/services/application/test_analytics_service.py`)
```python
def test_calculate_environmental_stability():
    # Test with stable readings
    # Test with volatile readings
    # Test edge cases (no data, single reading)

def test_calculate_energy_efficiency():
    # Test high efficiency scenario
    # Test low efficiency scenario
    # Test with anomalies

def test_format_sensor_chart_data():
    # Test various sensor types
    # Test photoperiod calculation
    # Test data gaps
```

### Integration Tests
- Verify existing endpoints still return same results
- Performance testing (calculations should be fast)

---

## 8. Rollback Plan

If issues arise:
1. Keep original endpoint functions as `_legacy_*()` for 1 sprint
2. Feature flag to switch between service/endpoint calculations
3. Compare outputs in test environment before full cutover

---

## 9. Benefits

### Code Quality
- ✅ Testable business logic (no HTTP mocking needed)
- ✅ Reusable calculations (other services can use)
- ✅ Single source of truth for analytics algorithms

### Maintainability
- ✅ Clear separation: Endpoints = orchestration, Services = logic
- ✅ Easier to optimize (cache in service layer)
- ✅ Simpler to add new analytics features

### Performance
- ✅ Can add service-level caching
- ✅ Easier to profile/optimize calculation bottlenecks

---

## 10. Questions for Product Owner

1. **Service Split**: Do you want to split AnalyticsService now, or wait until it exceeds 1500 lines?
   - **Recommendation**: Keep unified for now (867 → ~1200 lines is manageable)

2. **Priority**: Should we do all phases at once, or phase by phase?
   - **Recommendation**: Phase by phase (extract efficiency.py first as proof of concept)

3. **Testing**: Do you want integration tests that compare old vs new output?
   - **Recommendation**: Yes for critical calculations (efficiency scores)

---

## Conclusion

**Current State**: 
- ✅ Optional AI services fully integrated
- ✅ Energy endpoints properly delegated
- ⚠️ Analytics endpoints contain ~230 lines of business logic

**Recommended Action**:
- Extract calculation functions from analytics endpoints → `AnalyticsService`
- Maintain unified service architecture (no split needed yet)
- Prioritize efficiency.py extraction (highest complexity)

**Estimated Effort**: 4-6 hours for all phases  
**Risk Level**: Low (pure function extraction)  
**Impact**: High (improved testability and maintainability)
