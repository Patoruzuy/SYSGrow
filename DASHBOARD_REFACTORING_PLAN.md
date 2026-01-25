# Dashboard & Analytics Utils Refactoring Plan

## Status: Phase 1 - Deep Analysis

### Executive Summary
**dashboard.py** (1211 lines) and **_utils.py** (286 lines) contain ~400 lines of business logic that should be moved to appropriate service layers. Your concern is valid - we should **NOT dump everything into AnalyticsService**. Logic should be distributed to:
- **DeviceHealthService**: Device health scoring, status calculations
- **EnergyMonitoringService**: Energy cost estimations, power calculations
- **AnalyticsService**: Trend analysis, statistical calculations
- **Utilities/Helpers**: Data formatting, parsing, caching (stay in API layer)

---

## 1. File: dashboard.py (1211 lines)

### 1.1 Business Logic to Extract (By Service)

#### A. DeviceHealthService Candidates (Lines: ~150)

**1. `_health_status_from_score()` (line 1172)**
```python
def _health_status_from_score(score: float) -> str:
    """Convert health score (0-100) to status string"""
    if score >= 80: return 'healthy'
    elif score >= 60: return 'good'
    elif score >= 40: return 'fair'
    else: return 'poor'
```
**Reason**: Health status interpretation is domain logic  
**Move to**: `DeviceHealthService.interpret_health_score(score: float) -> str`

---

**2. System Health Calculation (lines 745-785)**
```python
# 6. Calculate system health score
health_factors = []

# VPD status contributes
if summary['vpd'].get('status') == 'optimal':
    health_factors.append(100)
elif summary['vpd'].get('status') in ['low', 'high']:
    health_factors.append(70)

# Plant health average
if summary['system'].get('plant_health_avg'):
    health_factors.append(summary['system']['plant_health_avg'])

# Alerts impact
if summary['alerts']['critical'] > 0:
    health_factors.append(40)
elif summary['alerts']['warning'] > 0:
    health_factors.append(70)
else:
    health_factors.append(100)

# Device availability
if summary['devices']['total'] > 0:
    device_health = (summary['devices']['active'] / summary['devices']['total']) * 100
    health_factors.append(device_health)

if health_factors:
    avg_score = sum(health_factors) / len(health_factors)
    summary['system']['health_score'] = round(avg_score, 1)
    summary['system']['status'] = _health_status_from_score(avg_score)
```
**Reason**: Complex business logic for system health aggregation  
**Move to**: `DeviceHealthService.calculate_system_health(vpd_status, plant_health_avg, alerts, devices_active, devices_total) -> Dict`

---

**3. `get_status()` Threshold Logic (lines 1194-1211)**
```python
def get_status(value, sensor_type):
    """Determine sensor status based on value and thresholds"""
    thresholds = {
        'temperature': {'min': 18, 'max': 28},
        'humidity': {'min': 40, 'max': 80},
        'soil_moisture': {'min': 30, 'max': 70},
        'light_level': {'min': 200, 'max': 1500},
        'co2_level': {'min': 300, 'max': 800},
        'energy_usage': {'min': 0, 'max': 5}
    }
    
    threshold = thresholds.get(sensor_type, {'min': 0, 'max': 100})
    
    if value < threshold['min']: return 'Low'
    elif value > threshold['max']: return 'High'
    else: return 'Normal'
```
**Reason**: Threshold evaluation is device health logic  
**Move to**: `DeviceHealthService.evaluate_sensor_status(value: float, sensor_type: str) -> str`  
**Note**: Hardcoded thresholds should eventually come from unit settings

---

#### B. EnergyMonitoringService Candidates (Lines: ~40)

**1. `_estimate_daily_cost()` (line 1184)**
```python
def _estimate_daily_cost(power_watts: float, rate_per_kwh: float = 0.12) -> float:
    """Estimate daily electricity cost from current power consumption"""
    if not power_watts:
        return 0.0
    # Assume continuous operation for estimation
    daily_kwh = (power_watts * 24) / 1000
    return round(daily_kwh * rate_per_kwh, 2)
```
**Reason**: Energy cost calculation is domain logic  
**Move to**: `EnergyMonitoringService.estimate_daily_cost(power_watts: float) -> float`  
**Note**: Service already has `electricity_rate` attribute, should use that

---

**2. Energy Dashboard Logic (lines 585-593)**
```python
if energy_row:
    summary['energy'] = {
        'current_power_watts': energy_row.get('power_watts', 0),
        'daily_cost': _estimate_daily_cost(energy_row.get('power_watts', 0)),
        'trend': 'stable',
        'timestamp': energy_row.get('timestamp')
    }
```
**Reason**: Energy summary aggregation  
**Move to**: `EnergyMonitoringService.get_energy_summary(energy_row: Dict) -> Dict`

---

#### C. AnalyticsService Candidates (Lines: ~50)

**1. `_calculate_vpd()` (lines 1118-1165)**
```python
def _calculate_vpd(temperature: float, humidity: float) -> Dict[str, Any]:
    """
    Calculate Vapor Pressure Deficit (VPD) from temperature and humidity.
    
    VPD = SVP × (1 - RH/100)
    where SVP (Saturation Vapor Pressure) = 0.6108 × exp(17.27 × T / (T + 237.3))
    
    Optimal VPD zones:
    - Seedling/Clone: 0.4-0.8 kPa
    - Vegetative: 0.8-1.2 kPa
    - Flowering: 1.0-1.5 kPa
    """
    if temperature is None or humidity is None:
        return {'value': None, 'unit': 'kPa', 'status': 'unknown', 'zone': 'unknown', 'optimal_for': []}

    try:
        vpd_value = calculate_vpd_kpa(temperature, humidity)  # Uses utility function
        if vpd_value is None:
            raise ValueError("VPD inputs missing")

        vpd = round(float(vpd_value), 2)

        # Determine zone and optimal stage
        zone = 'unknown'
        optimal_for = []
        status = 'normal'

        if vpd < 0.4:
            zone = 'too_low'
            status = 'low'
            optimal_for = []
        elif vpd < 0.8:
            zone = 'seedling'
            status = 'optimal'
            optimal_for = ['seedling', 'clone', 'early_veg']
        elif vpd < 1.2:
            zone = 'vegetative'
            status = 'optimal'
            optimal_for = ['vegetative', 'late_veg']
        elif vpd < 1.5:
            zone = 'flowering'
            status = 'optimal'
            optimal_for = ['flowering', 'bloom']
        else:
            zone = 'too_high'
            status = 'high'
            optimal_for = []

        return {
            'value': vpd,
            'unit': 'kPa',
            'status': status,
            'zone': zone,
            'optimal_for': optimal_for,
            'temperature': temperature,
            'humidity': humidity
        }
    except Exception as e:
        logger.warning(f"Error calculating VPD: {e}")
        return {'value': None, 'unit': 'kPa', 'status': 'error', 'zone': 'unknown', 'optimal_for': []}
```
**Reason**: Environmental analysis with interpretation  
**Move to**: `AnalyticsService.calculate_vpd_with_zones(temperature: float, humidity: float) -> Dict`  
**Note**: Already uses `calculate_vpd_kpa()` utility, this adds zone interpretation

---

### 1.2 API Layer Utilities (Should Stay)

These are HTTP/presentation layer concerns, **NOT business logic**:

✅ **Caching Functions** (lines 43-79):
- `_cache_key()`, `_cache_get()`, `_cache_set()` - HTTP response caching
- Keep in API layer

✅ **Request Parameter Parsing** (lines 31-112):
- `_parse_iso8601()`, `_resolve_unit_id()`, `_normalize_stage_name()`, `_parse_date_value()`
- Keep in API layer (presentation concerns)

✅ **Data Formatting Helpers** (lines 388-411):
- `_build_metric()`, `_build_energy_metric()` - Format for JSON response
- Keep in API layer

✅ **Downsampling** (line 36):
- `_downsample()` - Reduce data for HTTP response
- Keep in API layer

✅ **Domain Lookups** (lines 113-150):
- `_select_active_plant()`, `_extract_stage_names()`, `_find_stage_details()`, `_find_stage_conditions()`
- These are data aggregation for endpoint responses, not business logic
- Keep in API layer

✅ **Schedule Helpers** (lines 154-186):
- `_hours_until_time()`, `_schedule_days()` - Format schedule data for display
- Keep in API layer

---

## 2. File: analytics/_utils.py (286 lines)

### 2.1 Business Logic to Extract (By Service)

#### A. AnalyticsService Candidates (Lines: ~200)

**1. `format_sensor_chart_data()` (lines 16-99)**
- **Current**: 84 lines of data aggregation logic
- **Purpose**: Merge sensor readings by timestamp, extract metrics
- **Move to**: `AnalyticsService.format_sensor_chart_data(readings: List[Dict], interval: Optional[str] = None) -> Dict`
- **Reason**: Data transformation and aggregation is analytics domain logic

---

**2. `analyze_trends()` (lines 120-187)**
- **Current**: 67 lines of trend analysis (stable/rising/falling, volatility)
- **Purpose**: Calculate trend direction and volatility from time series
- **Move to**: `AnalyticsService.analyze_metric_trends(readings: List[Dict], days: int) -> Dict`
- **Reason**: Statistical analysis is core analytics functionality

---

**3. `calculate_correlations()` (lines 190-253)**
- **Current**: 63 lines of Pearson correlation + VPD analysis
- **Purpose**: Calculate temp-humidity correlation and VPD zones
- **Move to**: `AnalyticsService.calculate_environmental_correlations(readings: List[Dict]) -> Dict`
- **Reason**: Complex statistical calculation with domain interpretation

---

### 2.2 Utility Functions (Should Stay or Move to Utils Module)

**1. `extract_lux_value()` (lines 102-113)**
- **Purpose**: Best-effort extraction of lux value from different payload formats
- **Decision**: Keep in `_utils.py` - simple data extraction utility
- **Alternative**: Could move to `app/utils/sensor_parsers.py` if we create sensor utilities module

**2. `mean()` (lines 116-118)**
- **Purpose**: Calculate mean with null safety
- **Decision**: Keep in `_utils.py` - trivial math utility
- **Alternative**: Could use `statistics.mean()` from stdlib

**3. `interpret_correlation()` (lines 256-262)**
- **Purpose**: Convert correlation coefficient to human label
- **Decision**: Move with `calculate_correlations()` to `AnalyticsService`

**4. `sqlite_timestamp()` (lines 265-271)**
- **Purpose**: Format datetime for SQLite queries
- **Decision**: Move to `app/utils/time.py` - database utility

**5. `volatility_ratio()` (lines 274-286)**
- **Purpose**: Calculate ratio of std_dev to average
- **Decision**: Move with `analyze_trends()` to `AnalyticsService`

---

## 3. Refactoring Strategy

### Phase 1: Extract High-Value Business Logic (4-6 hours)

**Priority 1: EnergyMonitoringService** (Easiest, Immediate Value)
1. Add `estimate_daily_cost()` method (uses existing `electricity_rate` attribute)
2. Add `get_energy_summary()` method for dashboard aggregation
3. Update dashboard.py to call service methods

**Priority 2: DeviceHealthService** (Clear Domain Boundaries)
1. Add `interpret_health_score()` method
2. Add `calculate_system_health()` method (aggregates health factors)
3. Add `evaluate_sensor_status()` method (threshold checks)
4. Update dashboard.py to call service methods

**Priority 3: AnalyticsService** (Most Complex)
1. Add `calculate_vpd_with_zones()` method
2. Add `format_sensor_chart_data()` method (from _utils.py)
3. Add `analyze_metric_trends()` method (from _utils.py)
4. Add `calculate_environmental_correlations()` method (from _utils.py)
5. Update dashboard.py and analytics endpoints to call service methods

---

### Phase 2: Consolidate Analytics Calculations (2-3 hours)

From previous analysis of efficiency.py:
1. Add `calculate_environmental_stability()` to AnalyticsService
2. Add `calculate_energy_efficiency()` to AnalyticsService
3. Add `calculate_automation_effectiveness()` to AnalyticsService

---

## 4. Service Method Signatures

### DeviceHealthService (app/services/application/device_health_service.py)

```python
class DeviceHealthService:
    # New methods:
    
    def interpret_health_score(self, score: float) -> str:
        """Convert health score (0-100) to human-readable status."""
        
    def calculate_system_health(
        self,
        vpd_status: str,
        plant_health_avg: Optional[float],
        critical_alerts: int,
        warning_alerts: int,
        devices_active: int,
        devices_total: int
    ) -> Dict[str, Any]:
        """
        Calculate overall system health score.
        
        Returns:
            {
                'health_score': 85.5,
                'status': 'healthy',
                'factors': {
                    'vpd': 100,
                    'plants': 82.3,
                    'alerts': 70,
                    'devices': 95.0
                }
            }
        """
        
    def evaluate_sensor_status(
        self,
        value: Optional[float],
        sensor_type: str,
        thresholds: Optional[Dict] = None
    ) -> str:
        """
        Evaluate sensor reading against thresholds.
        
        Args:
            value: Sensor reading value
            sensor_type: Type of sensor (temperature, humidity, etc.)
            thresholds: Optional custom thresholds, falls back to defaults
            
        Returns:
            Status string: 'Low', 'Normal', 'High', 'Unknown'
        """
```

---

### EnergyMonitoringService (app/services/hardware/energy_monitoring.py)

```python
class EnergyMonitoringService:
    # New methods:
    
    def estimate_daily_cost(self, power_watts: float) -> float:
        """
        Estimate daily electricity cost from current power consumption.
        Uses service's electricity_rate attribute.
        """
        if not power_watts:
            return 0.0
        daily_kwh = (power_watts * 24) / 1000
        return round(daily_kwh * self.electricity_rate, 2)
    
    def get_energy_summary(self, energy_reading: Optional[Dict]) -> Dict[str, Any]:
        """
        Build energy dashboard summary from latest reading.
        
        Returns:
            {
                'current_power_watts': 450.0,
                'daily_cost': 1.30,
                'trend': 'stable',
                'timestamp': '2025-01-07T12:00:00Z'
            }
        """
```

---

### AnalyticsService (app/services/application/analytics_service.py)

```python
class AnalyticsService:
    # New methods from dashboard.py:
    
    def calculate_vpd_with_zones(
        self,
        temperature: float,
        humidity: float
    ) -> Dict[str, Any]:
        """
        Calculate VPD with growth stage zone interpretation.
        
        Returns:
            {
                'value': 0.95,
                'unit': 'kPa',
                'status': 'optimal',
                'zone': 'vegetative',
                'optimal_for': ['vegetative', 'late_veg'],
                'temperature': 24.5,
                'humidity': 65.0
            }
        """
    
    # New methods from _utils.py:
    
    def format_sensor_chart_data(
        self,
        readings: List[Dict],
        interval: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Format sensor readings for chart visualization.
        Merges readings by timestamp and extracts metrics.
        """
    
    def analyze_metric_trends(
        self,
        readings: List[Dict],
        days: int
    ) -> Dict[str, Any]:
        """
        Analyze environmental trends (temperature, humidity, soil moisture).
        
        Returns:
            {
                'temperature': {
                    'trend': 'rising',
                    'volatility': 'low',
                    'average': 24.5,
                    'std_dev': 0.8,
                    'change': 0.3
                },
                ...
            }
        """
    
    def calculate_environmental_correlations(
        self,
        readings: List[Dict]
    ) -> Dict[str, Any]:
        """
        Calculate correlations between environmental factors.
        
        Returns:
            {
                'temp_humidity_correlation': -0.65,
                'correlation_interpretation': 'moderate',
                'vpd_average': 0.85,
                'vpd_status': 'optimal_vegetative',
                'sample_size': 150
            }
        """
    
    # From efficiency.py (previous plan):
    
    def calculate_environmental_stability(...) -> Dict:
        """Calculate stability scores from volatility."""
    
    def calculate_energy_efficiency(...) -> Dict:
        """Calculate energy efficiency scores."""
    
    def calculate_automation_effectiveness(...) -> Dict:
        """Calculate automation quality scores."""
```

---

## 5. Implementation Order (Recommended)

### Week 1: EnergyMonitoringService + DeviceHealthService
**Day 1-2**: EnergyMonitoringService
- ✅ Simplest extraction (2 methods, ~40 lines)
- ✅ No dependencies on other services
- ✅ Immediate value for dashboard

**Day 3-4**: DeviceHealthService
- ✅ Clear domain boundaries (3 methods, ~150 lines)
- ✅ Low risk - pure calculation functions
- ✅ High impact (used throughout dashboard)

---

### Week 2: AnalyticsService (Part 1 - Utils Extraction)
**Day 1-3**: Extract from _utils.py
- Extract `format_sensor_chart_data()` (84 lines)
- Extract `analyze_metric_trends()` (67 lines)
- Extract `calculate_environmental_correlations()` (63 lines)
- Extract `calculate_vpd_with_zones()` from dashboard.py (50 lines)

**Day 4-5**: Testing & Integration
- Unit tests for new service methods
- Integration tests for updated endpoints
- Performance validation

---

### Week 3: AnalyticsService (Part 2 - Efficiency Calculations)
**From efficiency.py** (previous plan):
- Extract `calculate_environmental_stability()`
- Extract `calculate_energy_efficiency()`
- Extract `calculate_automation_effectiveness()`

---

## 6. Expected Service Sizes After Refactoring

| Service | Current | Added Lines | Final Size | Status |
|---------|---------|-------------|------------|---------|
| DeviceHealthService | 1160 | +150 | ~1310 | ✅ Still manageable (facade pattern) |
| EnergyMonitoringService | 389 | +40 | ~430 | ✅ Perfect size |
| AnalyticsService | 867 | +350 | ~1220 | ✅ Large but justified (comprehensive analytics) |

**All services remain under 1500 lines** - No splitting needed yet.

---

## 7. Benefits Summary

### Code Quality
- ✅ **Clear separation**: API layer = orchestration, Services = business logic
- ✅ **Testable**: Can unit test calculations without HTTP mocking
- ✅ **Reusable**: Other services can use same calculations
- ✅ **Single source of truth**: One place for each calculation

### Maintainability
- ✅ **Easier to find**: All energy logic in EnergyMonitoringService
- ✅ **Easier to change**: Update calculation in one place
- ✅ **Easier to optimize**: Can add service-level caching

### Architecture
- ✅ **Proper layering**: Business logic in domain/service layer, not API layer
- ✅ **Domain-driven**: Logic grouped by domain (energy, health, analytics)
- ✅ **Testability**: 80%+ test coverage becomes achievable

---

## 8. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Breaking existing endpoints | Low | High | Comprehensive integration tests before deployment |
| Service method signatures change | Low | Medium | Version API responses separately from service methods |
| Performance degradation | Very Low | Medium | Profile before/after, service-level caching |
| Logic bugs during extraction | Low | High | Keep original functions as `_legacy_*()` for 1 sprint |

---

## 9. Questions for Decision

1. **Service Distribution**: Do you agree with the service assignment (Energy→EnergyMonitoringService, Health→DeviceHealthService, Stats→AnalyticsService)?
   - **Recommendation**: ✅ Yes, this follows domain-driven design

2. **Implementation Order**: Start with EnergyMonitoringService (easiest) or AnalyticsService (highest impact)?
   - **Recommendation**: Start with EnergyMonitoringService to build confidence

3. **Utility Functions**: Should `sqlite_timestamp()` move to `app/utils/time.py`?
   - **Recommendation**: ✅ Yes, consolidate time utilities

4. **Thresholds**: Should `evaluate_sensor_status()` eventually read from database?
   - **Recommendation**: ✅ Yes, but use hardcoded defaults for v1

5. **Testing**: Unit tests first or integration tests first?
   - **Recommendation**: Unit tests first (faster feedback loop)

---

## 10. Next Steps

**Ready to proceed?** Confirm the approach and I'll start with:

1. **Phase 1a**: Extract 2 methods to `EnergyMonitoringService`
2. **Phase 1b**: Extract 3 methods to `DeviceHealthService`
3. **Phase 1c**: Extract 4 methods to `AnalyticsService` (from dashboard.py + _utils.py)

**Total extraction**: ~9 methods, ~450 lines of business logic → proper service layer

**Estimated time**: 4-6 hours of focused refactoring  
**Risk**: Low (pure function extraction)  
**Impact**: High (major architecture improvement)
