# Database-Backed Energy Monitoring Implementation

## Overview

Implemented persistent energy monitoring with database storage for historical analysis and ML training. This upgrade provides a hybrid architecture combining in-memory caching for real-time access with database persistence for long-term data retention and analytics.

## Architecture

### Hybrid Approach

```
ActuatorManager
  └── EnergyMonitoringService
      ├── In-Memory Cache (last 1000 readings, fast access)
      └── Database Persistence (via EnergyDataAccess)
          └── ActuatorEnergyReadings table
              └── MLDataCollector queries for training
```

**Benefits:**
- ✅ **Persistent History**: Energy data survives system restarts
- ✅ **Fast Access**: In-memory cache for real-time operations
- ✅ **ML Training**: Historical data correlation with sensor readings
- ✅ **Single Source of Truth**: Database as authoritative source
- ✅ **Repository Pattern**: Clean separation of concerns

## Implementation Details

### 1. Database Schema

**File**: `infrastructure/database/sqlite_handler.py`

Created `ActuatorEnergyReadings` table:

```sql
CREATE TABLE ActuatorEnergyReadings (
    reading_id INTEGER PRIMARY KEY AUTOINCREMENT,
    actuator_id INTEGER NOT NULL,
    timestamp DATETIME NOT NULL,
    voltage REAL,
    current REAL,
    power_watts REAL,
    energy_kwh REAL,
    power_factor REAL,
    frequency REAL,
    temperature REAL,
    is_estimated INTEGER DEFAULT 0,
    FOREIGN KEY (actuator_id) REFERENCES Devices(device_id)
)
```

**Indexes for Performance:**
- `idx_actuator_energy_timestamp`: Timestamp-based queries
- `idx_actuator_energy_actuator`: Per-actuator queries
- `idx_actuator_energy_lookup`: Combined actuator_id + timestamp lookups

### 2. Data Access Layer

**File**: `ai/data_access/energy_data.py`

Created `EnergyDataAccess` class following repository pattern:

```python
class EnergyDataAccess:
    def __init__(self, analytics_repo: 'AnalyticsRepository')
    
    # Core operations
    def save_reading(reading_data: Dict) -> Optional[int]
    def get_latest_reading(actuator_id: int) -> Optional[Dict]
    def get_readings_for_period(actuator_id: int, start_time: datetime, 
                                 end_time: datetime) -> List[Dict]
    
    # Analytics
    def get_consumption_stats(actuator_id: int, start_time: datetime, 
                             end_time: datetime) -> Dict
    
    # ML-specific
    def get_power_for_ml_training(actuator_id: int, timestamp: datetime, 
                                  tolerance_seconds: int = 30) -> Optional[float]
    
    # Maintenance
    def delete_old_readings(days_to_keep: int = 90) -> int
```

**Key Features:**
- Timestamp-based queries with tolerance windows
- Aggregate statistics (avg, max, total consumption)
- ML-specific queries for historical correlation
- Automatic cleanup of old data

### 3. Energy Monitoring Service

**File**: `infrastructure/hardware/actuators/services/energy_monitoring.py`

Updated `EnergyMonitoringService` to persist readings:

**Changes:**
```python
def __init__(self, electricity_rate_kwh: float = 0.12, 
             energy_data_access = None):
    self.energy_data_access = energy_data_access
    # ... existing code

def record_reading(self, reading: EnergyReading) -> None:
    # Store in memory (existing behavior)
    self.readings[actuator_id].append(reading)
    
    # NEW: Persist to database if available
    if self.energy_data_access:
        self._persist_reading(reading)

def _persist_reading(self, reading: EnergyReading) -> None:
    """Convert EnergyReading to dict and save to database"""
    reading_data = {
        'actuator_id': reading.actuator_id,
        'timestamp': reading.timestamp,
        'voltage': reading.voltage,
        'current': reading.current,
        'power_watts': reading.power,
        'energy_kwh': reading.energy,
        'power_factor': reading.power_factor,
        'frequency': reading.frequency,
        'temperature': reading.temperature,
        'is_estimated': False
    }
    self.energy_data_access.save_reading(reading_data)
```

### 4. Actuator Manager Integration

**File**: `infrastructure/hardware/actuators/manager.py`

Updated `ActuatorManager` to create and pass `EnergyDataAccess`:

**Changes:**
```python
def __init__(self, ..., analytics_repo: Optional[Any] = None):
    # NEW: Create EnergyDataAccess if analytics_repo provided
    if enable_energy_monitoring:
        energy_data_access = None
        if analytics_repo:
            from ai.data_access import EnergyDataAccess
            energy_data_access = EnergyDataAccess(analytics_repo)
        
        self.energy_monitoring = EnergyMonitoringService(
            electricity_rate_kwh=electricity_rate_kwh,
            energy_data_access=energy_data_access  # NEW parameter
        )
```

### 5. Unit Runtime Manager

**File**: `app/models/unit_runtime_manager.py`

Updated to pass `analytics_repo` to `ActuatorManager`:

**Changes:**
```python
self.actuator_manager = ActuatorManager(
    mqtt_client=mqtt_client,
    event_bus=self.event_bus,
    enable_energy_monitoring=True,
    enable_zigbee2mqtt_discovery=True,
    electricity_rate_kwh=0.12,
    device_service=device_service,
    analytics_repo=repo_analytics  # NEW: Enable energy persistence
)
```

### 6. ML Data Collector

**File**: `ai/ml_trainer.py`

Updated `MLDataCollector` to query database for historical power data:

**Changes:**
```python
def __init__(self, data_access, actuator_manager, plant_health_monitor, 
             environment_collector, energy_data_access=None):
    self.energy_data_access = energy_data_access  # NEW parameter

def get_power(device_name: str) -> float:
    """Query database for power at sensor timestamp"""
    # NEW: Try database first (preferred for ML - historical data)
    if self.energy_data_access:
        power = self.energy_data_access.get_power_for_ml_training(
            actuator.actuator_id,
            timestamp,  # From sensor reading
            tolerance_seconds=30  # Allow 30s window
        )
        if power is not None:
            return power
    
    # Fallback to in-memory (real-time only)
    if self.actuator_manager.energy_monitoring:
        return self.actuator_manager.get_current_power(actuator_id)
    
    return 0.0
```

**Key Improvement:**
- Uses timestamp from sensor reading
- Queries database with 30-second tolerance window
- Correlates energy data with environmental conditions
- Falls back to in-memory if database unavailable

### 7. Task Scheduler

**File**: `workers/task_scheduler.py`

Updated to create and pass `EnergyDataAccess`:

**Changes:**
```python
def _init_features(self):
    from ai.data_access import (
        PlantHealthDataAccess,
        MLTrainingDataAccess,
        EnvironmentDataAccess,
        EnergyDataAccess  # NEW import
    )
    
    energy_data = EnergyDataAccess(self.analytics_repo)  # NEW
    
    self.data_collector = MLDataCollector(
        ml_training_data,
        self.actuator_manager,
        self.plant_health_monitor,
        self.environment_collector,
        energy_data  # NEW: Pass for historical queries
    )
```

## Data Flow

### Recording Energy Data

1. **Smart Switch Reading** → `EnergyMonitoringService.record_reading()`
2. **In-Memory Storage** → Append to `self.readings[actuator_id]`
3. **Database Persistence** → `_persist_reading()` → `EnergyDataAccess.save_reading()`
4. **SQLite Table** → `ActuatorEnergyReadings` table

### ML Training Data Collection

1. **Sensor Reading** → `MLDataCollector.collect_comprehensive_training_sample()`
2. **Get Timestamp** → Extract from sensor data
3. **Query Power** → `energy_data_access.get_power_for_ml_training(actuator_id, timestamp)`
4. **Database Query** → Find reading within 30-second window
5. **Training Sample** → Correlate power with environmental conditions

## Query Performance

### Optimized Lookups

**Time-based queries:**
```python
# Uses idx_actuator_energy_timestamp
get_readings_for_period(actuator_id, start_time, end_time)
```

**Latest reading:**
```python
# Uses idx_actuator_energy_actuator
get_latest_reading(actuator_id)
```

**ML training correlation:**
```python
# Uses idx_actuator_energy_lookup (composite index)
get_power_for_ml_training(actuator_id, timestamp, tolerance_seconds=30)
```

### Tolerance Window

ML training queries use a 30-second tolerance window to match sensor timestamps with energy readings:

```sql
WHERE actuator_id = ? 
  AND timestamp BETWEEN ? AND ?
ORDER BY ABS(julianday(timestamp) - julianday(?))
LIMIT 1
```

This finds the closest reading within ±30 seconds of the sensor timestamp.

## Data Maintenance

### Automatic Cleanup

```python
# Delete readings older than 90 days
deleted_count = energy_data_access.delete_old_readings(days_to_keep=90)
```

**Recommended Schedule:**
- Run monthly or quarterly
- Keeps database size manageable
- Configurable retention period

### Statistics Calculation

```python
stats = energy_data_access.get_consumption_stats(
    actuator_id=1,
    start_time=datetime.now() - timedelta(days=7),
    end_time=datetime.now()
)

# Returns:
# {
#     'avg_power': 150.5,
#     'max_power': 180.0,
#     'total_consumption_kwh': 25.2,
#     'reading_count': 1008
# }
```

## Testing Strategy

### Unit Tests

1. **EnergyDataAccess:**
   - Test save_reading()
   - Test get_power_for_ml_training() with tolerance window
   - Test get_consumption_stats() calculations

2. **EnergyMonitoringService:**
   - Test _persist_reading() calls data access
   - Test fallback when database unavailable

3. **MLDataCollector:**
   - Test database query before in-memory fallback
   - Test timestamp correlation logic

### Integration Tests

1. **End-to-End Flow:**
   - Record energy reading → Verify in database
   - Collect ML sample → Verify power query
   - Check timestamp correlation accuracy

2. **Performance:**
   - Query 1000+ readings
   - Measure index effectiveness
   - Test concurrent reads/writes

## Migration Notes

### Backward Compatibility

- ✅ In-memory cache still works without database
- ✅ `get_current_power()` unchanged for real-time use
- ✅ Existing energy monitoring features preserved
- ✅ Optional `energy_data_access` parameter (None by default)

### Breaking Changes

- None - All changes are additive

## Benefits Realized

### Before (In-Memory Only)
- ❌ Energy data lost on restart
- ❌ No historical analysis possible
- ❌ ML training used only real-time data
- ❌ No long-term trend analysis

### After (Hybrid Approach)
- ✅ **Persistent history** survives restarts
- ✅ **Historical analysis** with 90-day retention
- ✅ **ML training** correlates energy with conditions
- ✅ **Trend analysis** tracks consumption patterns
- ✅ **Fast access** via in-memory cache
- ✅ **Single source of truth** in database

## Performance Characteristics

### In-Memory Cache
- **Access Time**: O(1) - instant
- **Capacity**: Last 1000 readings per actuator
- **Use Case**: Real-time monitoring, dashboard display

### Database Storage
- **Access Time**: ~1-5ms with indexes
- **Capacity**: Limited by disk space (90-day default)
- **Use Case**: ML training, analytics, historical reports

### Hybrid Strategy
- Real-time operations → In-memory
- ML training → Database (historical correlation)
- Analytics → Database (aggregate queries)
- Monitoring → In-memory (fast display)

## Future Enhancements

### Potential Additions

1. **Time-series Analysis:**
   - Power consumption trends
   - Peak demand identification
   - Cost optimization recommendations

2. **Anomaly Detection:**
   - Unusual power spikes
   - Device malfunctions
   - Energy waste alerts

3. **Cost Tracking:**
   - Per-device cost breakdown
   - Monthly billing estimates
   - Cost vs. growth metrics

4. **Optimization:**
   - Schedule high-power tasks during off-peak hours
   - Predict energy needs
   - Recommend efficiency improvements

## Conclusion

Successfully implemented database-backed energy monitoring with:
- ✅ 0 errors across all modified files
- ✅ Repository pattern consistency maintained
- ✅ Backward compatibility preserved
- ✅ Performance optimized with indexes
- ✅ Clean separation of concerns
- ✅ ML training enhanced with historical data

The hybrid architecture provides the best of both worlds: fast in-memory access for real-time operations and persistent database storage for analytics and ML training.
