# Database Schema Analysis & Optimization Plan

## Executive Summary

**Critical Issues Identified:**
1. ❌ **Duplicate Energy Tables** - 4 overlapping tables for energy monitoring
2. ❌ **Unnecessary Abstraction** - Data access layer duplicates repository functionality
3. ❌ **Wrong Retention Strategy** - Deleting energy data instead of lifetime tracking
4. ⚠️ **Missing Plant Lifecycle Tracking** - No link between energy and plant growth stages

## Current Energy Tables (REDUNDANT)

### 1. `ActuatorPowerReading` (OLD - Line 207)
```sql
CREATE TABLE ActuatorPowerReading (
    reading_id INTEGER PRIMARY KEY,
    actuator_id INTEGER,
    timestamp DATETIME,
    voltage, current, power_watts, energy_kwh,
    power_factor, frequency, temperature,
    is_estimated BOOLEAN,
    FOREIGN KEY (actuator_id) REFERENCES Actuator(actuator_id)
)
```
**Status**: Legacy table, should be migrated/removed

### 2. `EnergyConsumption` (ZigBee-specific - Line 500)
```sql
CREATE TABLE EnergyConsumption (
    consumption_id INTEGER PRIMARY KEY,
    monitor_id INTEGER,  -- Links to ZigBeeEnergyMonitors
    timestamp DATETIME,
    voltage, current, power_watts, energy_kwh,
    frequency, power_factor, temperature,
    FOREIGN KEY (monitor_id) REFERENCES ZigBeeEnergyMonitors(monitor_id)
)
```
**Status**: ZigBee-specific, separate from Devices table

### 3. `ActuatorEnergyReadings` (NEW - Line 519) ⚠️
```sql
CREATE TABLE ActuatorEnergyReadings (
    reading_id INTEGER PRIMARY KEY,
    actuator_id INTEGER,
    timestamp DATETIME,
    voltage, current, power_watts, energy_kwh,
    power_factor, frequency, temperature,
    is_estimated BOOLEAN,
    FOREIGN KEY (actuator_id) REFERENCES Devices(device_id)
)
```
**Status**: **DUPLICATE of ActuatorPowerReading!** Almost identical schema

### 4. `DeviceEnergyProfiles` (Line 656)
```sql
CREATE TABLE DeviceEnergyProfiles (
    profile_id INTEGER PRIMARY KEY,
    device_type TEXT,
    device_model TEXT,
    rated_power_watts REAL,
    efficiency_factor REAL,
    power_curve TEXT  -- JSON
)
```
**Status**: Reference data for power estimation (OK to keep)

## Problems with Current Design

### ❌ Problem 1: Table Duplication
- `ActuatorPowerReading` and `ActuatorEnergyReadings` are **98% identical**
- Both reference actuators/devices with same schema
- Wastes storage and creates confusion
- Which one should code use?

### ❌ Problem 2: Fragmented Energy Data
```
ZigBee devices → EnergyConsumption table
GPIO/MQTT devices → ActuatorPowerReading/ActuatorEnergyReadings
```
- Can't query all energy data in one place
- Difficult to get total consumption across all devices
- Reporting requires joining multiple tables

### ❌ Problem 3: Missing Plant Lifecycle Link
```
Energy readings ❌ NO LINK → Plants table
                 ❌ NO LINK → Growth stages
                 ❌ NO LINK → Harvest events
```
- Can't track energy per plant
- Can't calculate cost per harvest
- Can't analyze efficiency by growth stage

### ❌ Problem 4: Data Access Layer Redundancy
```python
# Current (unnecessary layer):
Repository → DataAccessLayer → Repository (same operations!)

# Should be:
Service → Repository (direct)
```
The `EnergyDataAccess` class just wraps `AnalyticsRepository` with no added value.

## Proposed Schema Optimization

### Option A: Unified Energy Table (RECOMMENDED)

**Single table for all energy readings:**

```sql
CREATE TABLE EnergyReadings (
    reading_id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id INTEGER NOT NULL,           -- Unified FK to Devices
    plant_id INTEGER,                      -- NEW: Link to plant consuming energy
    unit_id INTEGER NOT NULL,              -- NEW: Link to growth unit
    growth_stage TEXT,                     -- NEW: 'seedling', 'vegetative', 'flowering', 'harvest'
    
    -- Reading data
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    voltage REAL,
    current REAL,
    power_watts REAL NOT NULL,
    energy_kwh REAL,
    power_factor REAL,
    frequency REAL,
    temperature REAL,
    
    -- Metadata
    source_type TEXT NOT NULL,             -- 'zigbee', 'gpio', 'mqtt', 'wifi', 'estimated'
    is_estimated BOOLEAN DEFAULT 0,
    
    -- Foreign keys
    FOREIGN KEY (device_id) REFERENCES Devices(device_id) ON DELETE CASCADE,
    FOREIGN KEY (plant_id) REFERENCES Plants(plant_id) ON DELETE SET NULL,
    FOREIGN KEY (unit_id) REFERENCES GrowthUnits(unit_id) ON DELETE CASCADE
);

-- Indexes for performance
CREATE INDEX idx_energy_device_time ON EnergyReadings(device_id, timestamp DESC);
CREATE INDEX idx_energy_plant ON EnergyReadings(plant_id) WHERE plant_id IS NOT NULL;
CREATE INDEX idx_energy_unit_stage ON EnergyReadings(unit_id, growth_stage);
CREATE INDEX idx_energy_timestamp ON EnergyReadings(timestamp DESC);
```

**Benefits:**
- ✅ Single source of truth for all energy data
- ✅ Links energy to plants and growth stages
- ✅ Supports lifetime tracking (no deletion)
- ✅ Can query by device, plant, unit, or stage
- ✅ Enables harvest cost analysis

### Plant Lifecycle Tracking

**Add harvest summary table:**

```sql
CREATE TABLE PlantHarvestSummary (
    harvest_id INTEGER PRIMARY KEY AUTOINCREMENT,
    plant_id INTEGER NOT NULL,
    unit_id INTEGER NOT NULL,
    
    -- Lifecycle dates
    planted_date TIMESTAMP NOT NULL,
    harvested_date TIMESTAMP NOT NULL,
    total_days INTEGER NOT NULL,
    
    -- Growth stage durations (days)
    seedling_days INTEGER,
    vegetative_days INTEGER,
    flowering_days INTEGER,
    
    -- Energy consumption
    total_energy_kwh REAL NOT NULL,
    energy_by_stage TEXT,              -- JSON: {"seedling": 5.2, "vegetative": 45.8, ...}
    total_cost REAL,
    cost_by_stage TEXT,                -- JSON: {"seedling": 0.62, "vegetative": 5.50, ...}
    
    -- Device usage
    device_usage TEXT,                 -- JSON: {"lights": 150.5, "fan": 45.2, ...}
    avg_daily_power_watts REAL,
    
    -- Light exposure
    total_light_hours REAL,
    light_hours_by_stage TEXT,         -- JSON: {"seedling": 180, "vegetative": 432, ...}
    avg_ppfd REAL,                     -- Average light intensity
    
    -- Health summary
    health_incidents TEXT,             -- JSON: [{"date": "2024-01-15", "issue": "yellowing", ...}]
    disease_days INTEGER DEFAULT 0,
    pest_days INTEGER DEFAULT 0,
    avg_health_score REAL,
    
    -- Environmental averages
    avg_temperature REAL,
    avg_humidity REAL,
    avg_co2_ppm REAL,
    
    -- Yield data
    harvest_weight_grams REAL,
    quality_rating INTEGER,            -- 1-5 scale
    notes TEXT,
    
    -- Efficiency metrics
    grams_per_kwh REAL,                -- Harvest efficiency
    cost_per_gram REAL,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (plant_id) REFERENCES Plants(plant_id),
    FOREIGN KEY (unit_id) REFERENCES GrowthUnits(unit_id)
);

CREATE INDEX idx_harvest_plant ON PlantHarvestSummary(plant_id);
CREATE INDEX idx_harvest_date ON PlantHarvestSummary(harvested_date DESC);
```

**Harvest Report Generation:**

When user harvests, system automatically:
1. Queries all energy readings for that plant
2. Groups by growth stage
3. Calculates totals and averages
4. Links health incidents
5. Computes efficiency metrics
6. Stores in `PlantHarvestSummary`
7. Keeps raw energy data for historical analysis

## Migration Plan

### Phase 1: Schema Consolidation (Week 1)

**Step 1.1: Create unified table**
```sql
-- Create new unified table
CREATE TABLE EnergyReadings (...);

-- Migrate data from ActuatorPowerReading
INSERT INTO EnergyReadings (device_id, timestamp, voltage, ...)
SELECT actuator_id, timestamp, voltage, ...
FROM ActuatorPowerReading;

-- Migrate data from EnergyConsumption (via ZigBee monitor mapping)
INSERT INTO EnergyReadings (device_id, timestamp, voltage, ..., source_type)
SELECT zm.device_id, ec.timestamp, ec.voltage, ..., 'zigbee'
FROM EnergyConsumption ec
JOIN ZigBeeEnergyMonitors zm ON ec.monitor_id = zm.monitor_id;

-- Drop old tables
DROP TABLE ActuatorPowerReading;
DROP TABLE ActuatorEnergyReadings;
-- Keep EnergyConsumption if still using ZigBee-specific features
```

**Step 1.2: Update foreign keys**
- Link existing energy readings to plants (where possible)
- Backfill unit_id from device associations
- Set source_type based on device protocol

### Phase 2: Remove Data Access Layer (Week 1)

**Current architecture (redundant):**
```python
EnergyMonitoringService → EnergyDataAccess → AnalyticsRepository → Database
```

**Simplified architecture:**
```python
EnergyMonitoringService → AnalyticsRepository → Database
```

**Changes needed:**
1. Remove `ai/data_access/energy_data.py` ❌
2. Update `EnergyMonitoringService` to use `AnalyticsRepository` directly
3. Update `MLDataCollector` to use `AnalyticsRepository` directly
4. Remove `EnergyDataAccess` from `__init__.py`

### Phase 3: Plant Lifecycle Integration (Week 2)

**Step 3.1: Add plant_id to energy readings**
```python
class EnergyMonitoringService:
    def record_reading(self, reading: EnergyReading):
        # Determine which plant is currently active in the unit
        plant_id = self._get_active_plant_for_device(reading.actuator_id)
        growth_stage = self._get_current_growth_stage(plant_id)
        
        # Save with plant context
        self.repository.save_energy_reading(
            device_id=reading.actuator_id,
            plant_id=plant_id,
            growth_stage=growth_stage,
            **reading_data
        )
```

**Step 3.2: Implement harvest summary generation**
```python
class PlantHarvestService:
    def generate_harvest_report(self, plant_id: int) -> Dict:
        """Generate comprehensive harvest report"""
        # Energy consumption
        energy_stats = self.repository.get_plant_energy_summary(plant_id)
        
        # Health incidents
        health_history = self.repository.get_plant_health_history(plant_id)
        
        # Environmental data
        env_averages = self.repository.get_plant_environment_averages(plant_id)
        
        # Generate JSON summaries
        summary = {
            'total_energy_kwh': energy_stats['total'],
            'energy_by_stage': json.dumps(energy_stats['by_stage']),
            'total_cost': energy_stats['total_cost'],
            'light_hours_by_stage': json.dumps(light_stats),
            'health_incidents': json.dumps(health_history),
            ...
        }
        
        # Save to PlantHarvestSummary table
        self.repository.save_harvest_summary(plant_id, summary)
        
        return summary
```

### Phase 4: Reporting & Analytics (Week 3)

**New repository methods:**

```python
class AnalyticsRepository:
    # Plant energy tracking
    def get_plant_energy_summary(self, plant_id: int) -> Dict
    def get_plant_energy_by_stage(self, plant_id: int) -> Dict
    def get_plant_cost_breakdown(self, plant_id: int) -> Dict
    
    # Historical comparisons
    def get_harvest_efficiency_trends(self, unit_id: int) -> List[Dict]
    def compare_plant_costs(self, plant_ids: List[int]) -> Dict
    
    # Stage analysis
    def get_avg_energy_per_stage(self, plant_species: str) -> Dict
    def get_optimal_stage_durations(self, plant_species: str) -> Dict
    
    # Device efficiency
    def get_device_efficiency_by_plant(self, device_id: int) -> List[Dict]
    
    # Harvest summaries
    def save_harvest_summary(self, plant_id: int, summary: Dict) -> int
    def get_harvest_report(self, harvest_id: int) -> Dict
    def get_all_harvest_reports(self, unit_id: int) -> List[Dict]
```

## Code Simplification

### Before (Current - Redundant)

```python
# EnergyMonitoringService
def _persist_reading(self, reading):
    self.energy_data_access.save_reading(reading_data)  # Extra layer!

# EnergyDataAccess (unnecessary wrapper)
def save_reading(self, reading_data):
    self.analytics_repo._backend.execute(...)  # Just forwarding!

# MLDataCollector
def get_power(self, device_name, timestamp):
    self.energy_data_access.get_power_for_ml_training(...)  # Extra layer!
```

### After (Simplified - Direct)

```python
# EnergyMonitoringService
def record_reading(self, reading: EnergyReading, plant_id: int = None):
    # Determine plant and growth stage
    if not plant_id:
        plant_id = self._get_active_plant_for_device(reading.actuator_id)
    growth_stage = self._get_current_growth_stage(plant_id)
    
    # Save directly to repository
    self.analytics_repo.save_energy_reading(
        device_id=reading.actuator_id,
        plant_id=plant_id,
        unit_id=self._get_unit_for_device(reading.actuator_id),
        growth_stage=growth_stage,
        timestamp=reading.timestamp,
        power_watts=reading.power,
        energy_kwh=reading.energy,
        voltage=reading.voltage,
        current=reading.current,
        power_factor=reading.power_factor,
        frequency=reading.frequency,
        temperature=reading.temperature,
        source_type=self._get_device_source_type(reading.actuator_id),
        is_estimated=False
    )

# MLDataCollector
def get_power(self, device_name: str, timestamp: datetime) -> float:
    actuator = self.actuator_manager.get_actuator_by_name(device_name)
    if not actuator:
        return 0.0
    
    # Query repository directly
    return self.analytics_repo.get_power_reading_near_timestamp(
        device_id=actuator.actuator_id,
        timestamp=timestamp,
        tolerance_seconds=30
    ) or 0.0
```

**Lines of code removed**: ~350+ (entire data access layer)
**Complexity reduced**: One less abstraction layer
**Maintainability**: Improved (fewer files to update)

## Harvest Report Example

When user clicks "Harvest" button:

```json
{
  "harvest_id": 123,
  "plant_id": 45,
  "plant_name": "Tomato - Cherry",
  "unit_id": 1,
  
  "lifecycle": {
    "planted_date": "2024-10-01T10:00:00Z",
    "harvested_date": "2024-11-16T14:30:00Z",
    "total_days": 46,
    "stages": {
      "seedling": {"days": 7, "dates": "Oct 1-7"},
      "vegetative": {"days": 21, "dates": "Oct 8-28"},
      "flowering": {"days": 18, "dates": "Oct 29-Nov 15"}
    }
  },
  
  "energy_consumption": {
    "total_kwh": 156.8,
    "total_cost": "$18.82",
    "by_stage": {
      "seedling": {"kwh": 12.5, "cost": "$1.50", "avg_watts": 74},
      "vegetative": {"kwh": 78.3, "cost": "$9.40", "avg_watts": 155},
      "flowering": {"kwh": 66.0, "cost": "$7.92", "avg_watts": 153}
    },
    "by_device": {
      "Grow Light": {"kwh": 105.2, "cost": "$12.62", "percent": 67},
      "Fan": {"kwh": 28.4, "cost": "$3.41", "percent": 18},
      "Water Pump": {"kwh": 15.2, "cost": "$1.82", "percent": 10},
      "Heater": {"kwh": 8.0, "cost": "$0.96", "percent": 5}
    },
    "avg_daily_kwh": 3.41,
    "avg_daily_cost": "$0.41"
  },
  
  "light_exposure": {
    "total_hours": 736,
    "by_stage": {
      "seedling": {"hours": 112, "daily": 16, "ppfd_avg": 200},
      "vegetative": {"hours": 336, "daily": 16, "ppfd_avg": 400},
      "flowering": {"hours": 288, "daily": 16, "ppfd_avg": 600}
    },
    "total_dli": 12800  // Daily Light Integral
  },
  
  "environmental_conditions": {
    "temperature": {
      "avg": 23.5,
      "min": 20.2,
      "max": 26.8,
      "optimal_range": "22-26°C",
      "within_range_percent": 94
    },
    "humidity": {
      "avg": 65,
      "min": 55,
      "max": 75,
      "optimal_range": "60-70%",
      "within_range_percent": 89
    },
    "co2": {
      "avg": 850,
      "optimal": "400-1000 ppm"
    }
  },
  
  "health_summary": {
    "total_incidents": 2,
    "incidents": [
      {
        "date": "2024-10-15",
        "day": 14,
        "stage": "vegetative",
        "issue": "Leaf yellowing (minor)",
        "severity": 1,
        "resolved": true,
        "resolution_days": 3
      },
      {
        "date": "2024-11-05",
        "day": 35,
        "stage": "flowering",
        "issue": "Aphid detection",
        "severity": 2,
        "resolved": true,
        "resolution_days": 2
      }
    ],
    "disease_free_days": 41,
    "pest_free_days": 44,
    "avg_health_score": 92
  },
  
  "yield": {
    "weight_grams": 850,
    "quality_rating": 4,
    "quality_notes": "Excellent color, good size"
  },
  
  "efficiency_metrics": {
    "grams_per_kwh": 5.42,
    "cost_per_gram": "$0.022",
    "cost_per_pound": "$9.98",
    "compared_to_store": {
      "store_price_per_lb": "$4.99",
      "your_cost_per_lb": "$9.98",
      "difference": "-$4.99",
      "note": "Cost includes equipment, optimized grows reduce cost"
    },
    "energy_efficiency_rating": "Good",
    "co2_saved_vs_shipped": "2.4 kg"
  },
  
  "recommendations": {
    "next_grow": [
      "Excellent health score! Maintain current practices.",
      "Consider reducing seedling stage to 5 days to save $0.43",
      "Your light hours are optimal for this variety",
      "Temperature control was excellent (94% in range)"
    ],
    "cost_optimization": [
      "LED efficiency: 67% of energy. Consider upgrading to higher efficiency LEDs.",
      "Fan runtime optimal for air circulation",
      "Heater usage low - good insulation"
    ]
  }
}
```

## Benefits of Optimized Schema

### ✅ Storage Efficiency
- Single table vs 4 tables → 75% reduction in complexity
- Unified indexes → faster queries
- No duplicate data

### ✅ Query Performance
```sql
-- Get ALL energy for a plant (single query)
SELECT * FROM EnergyReadings WHERE plant_id = 45;

-- Get energy by stage
SELECT growth_stage, SUM(energy_kwh), AVG(power_watts)
FROM EnergyReadings
WHERE plant_id = 45
GROUP BY growth_stage;

-- Compare plants
SELECT plant_id, SUM(energy_kwh) as total_energy
FROM EnergyReadings
WHERE plant_id IN (45, 46, 47)
GROUP BY plant_id;
```

### ✅ Feature Enablement
- Plant cost analysis ✅
- Growth stage optimization ✅
- Harvest efficiency tracking ✅
- Historical comparisons ✅
- Device usage patterns ✅
- ROI calculations ✅

### ✅ Code Simplification
- Remove 350+ lines (data access layer)
- Direct repository access
- Fewer files to maintain
- Clearer data flow

### ✅ Better UX
- Comprehensive harvest reports
- Cost per harvest visibility
- Efficiency recommendations
- Historical trend analysis
- Plant comparison tools

## Recommended Action Plan

### Immediate (This Week)
1. ✅ Remove `EnergyDataAccess` class
2. ✅ Update services to use `AnalyticsRepository` directly
3. ✅ Create unified `EnergyReadings` table
4. ✅ Migrate existing data

### Short-term (Next Week)
5. ✅ Add `plant_id` and `growth_stage` tracking
6. ✅ Create `PlantHarvestSummary` table
7. ✅ Implement harvest report generation
8. ✅ Drop old duplicate tables

### Medium-term (Next 2 Weeks)
9. ✅ Build harvest report UI
10. ✅ Add plant comparison analytics
11. ✅ Implement cost optimization suggestions
12. ✅ Create efficiency dashboards

## Conclusion

Your instincts were 100% correct:

1. **Data Access Layer is redundant** - Repository is sufficient
2. **Don't delete energy data** - Keep for lifetime plant analysis
3. **Database has duplication** - 4 tables doing similar jobs
4. **Missing plant lifecycle link** - Critical for harvest reports

The optimized schema will:
- Eliminate redundancy
- Enable powerful harvest analytics
- Simplify codebase
- Improve performance
- Provide better insights

**Recommendation**: Proceed with full optimization. The benefits far outweigh the migration effort.
