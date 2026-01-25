# Harvest Data Retention Strategy

## 🎯 Problem Statement

When harvesting a plant in a growth unit that contains multiple plants, we need to:
1. Generate a comprehensive harvest report (requires historical data)
2. Clean up plant-specific data (free up space)
3. **Preserve shared data** (needed for remaining plants' reports)

## ⚠️ Critical Constraint

**Multiple plants may share the same growth unit** and therefore share:
- Environmental sensor readings (temperature, humidity, CO2, etc.)
- Energy consumption data (devices serve all plants in unit)
- Device operation history (lights, fans, etc.)
- ML training data (system-wide learning)

**Deleting this shared data would make it impossible to generate accurate harvest reports for the remaining plants!**

## ✅ Solution: Selective Data Deletion

### Data Categories

#### 🗑️ **SAFE TO DELETE** (Plant-Specific)
These records are tied to a single plant and can be safely deleted:

1. **Plants Table Record**
   - The plant entry itself
   - No longer needed after harvest report is saved

2. **PlantHealth & PlantHealthLogs**
   - Health observations for this specific plant
   - Disease/pest incidents
   - Already captured in harvest report's `health_incidents` JSON

3. **PlantSensors** (Associations)
   - Links between plant and sensors
   - Not the sensor data itself

4. **GrowthUnitPlants** (Associations)
   - Links between plant and growth unit
   - Not the unit data itself

5. **AI_DecisionLogs** (Optional)
   - Decisions made for this specific plant
   - Could keep for ML learning purposes

#### 🔒 **MUST KEEP** (Shared/Historical)
These records are shared across plants or needed for system operation:

1. **EnergyReadings**
   - Shared: Multiple plants in same unit consume energy together
   - Historical: Needed for other plants' harvest reports
   - Solution: Plant association preserved via `plant_id` field

2. **SensorReading**
   - Shared: All plants in unit share environmental readings
   - Historical: Needed for environmental averages in reports

3. **ActuatorHistory**
   - Shared: Devices (lights, fans) affect all plants in unit
   - Historical: Needed to calculate energy costs

4. **MLTrainingData**
   - System-wide: Used for model improvement
   - Cross-plant: Benefits future grows

5. **GrowthUnits**
   - Container: May still have other active plants
   - Solution: Clear `active_plant_id` but keep the unit

6. **EnvironmentInfo**
   - Static: Room dimensions, insulation, etc.
   - Shared: Applies to entire unit

## 🔧 Implementation

### Method 1: Generate Report Only
```python
from app.services.harvest_service import PlantHarvestService

# Generate report without deleting plant data
report = harvest_service.generate_harvest_report(
    plant_id=123,
    harvest_weight_grams=250.0,
    quality_rating=4,
    notes="Excellent yield"
)

# Report saved to PlantHarvestSummary table
# Plant data remains in database
# harvest_id: 42
```

**Use when:**
- User wants to keep plant record for reference
- Reviewing harvest before final cleanup
- Troubleshooting or analysis

### Method 2: Cleanup After Harvest
```python
# Delete plant-specific data only
cleanup_results = harvest_service.cleanup_after_harvest(
    plant_id=123,
    delete_plant_data=True
)

# Returns:
# {
#     'plant_health_logs': 15,
#     'plant_sensors': 3,
#     'plant_unit_associations': 1,
#     'ai_decision_logs': 0,
#     'plant_record': 1
# }
```

**Use when:**
- Harvest report already generated
- Ready to free up space
- No longer need plant profile

### Method 3: Harvest and Cleanup (One Step)
```python
# Generate report AND cleanup in one call
result = harvest_service.harvest_and_cleanup(
    plant_id=123,
    harvest_weight_grams=250.0,
    quality_rating=4,
    notes="Excellent yield",
    delete_plant_data=True  # Set to False to keep plant data
)

# Returns:
# {
#     'harvest_report': {
#         'harvest_id': 42,
#         'plant_id': 123,
#         'total_energy_kwh': 58.9,
#         'efficiency_metrics': {...},
#         ...
#     },
#     'cleanup_results': {
#         'plant_health_logs': 15,
#         'plant_sensors': 3,
#         ...
#     },
#     'plant_data_deleted': True
# }
```

**Use when:**
- Standard harvest workflow
- User confirms harvest is final
- Want to clean up immediately

## 📊 Example Scenarios

### Scenario 1: Single Plant in Unit
```
Unit #1: Tomato Plant #123 (only plant)

On harvest:
✓ Generate report (energy: 58.9 kWh, all from this plant)
✓ Delete plant record
✓ Keep energy readings (may want to analyze unit efficiency)
✓ Keep sensor readings (may want to compare environments)
✓ Clear active_plant_id from Unit #1
```

### Scenario 2: Multiple Plants in Unit (First Harvest)
```
Unit #1: 
- Tomato #123 (ready to harvest) ← HARVESTING
- Pepper #124 (still growing)
- Basil #125 (still growing)

On harvest Plant #123:
✓ Generate report (energy: proportional estimate based on plant_id association)
✓ Delete plant #123 record
✗ KEEP energy readings (needed for Plants #124, #125)
✗ KEEP sensor readings (shared by all plants)
✓ Update unit: active_plant_id remains (still has Plants #124, #125)
```

### Scenario 3: Multiple Plants in Unit (Last Harvest)
```
Unit #1:
- Basil #125 (ready to harvest) ← HARVESTING (LAST PLANT)

On harvest Plant #125:
✓ Generate report (uses all historical data)
✓ Delete plant #125 record
✓ KEEP energy readings (may want historical analysis)
✓ KEEP sensor readings (may compare with future grows)
✓ Clear active_plant_id from Unit #1 (no active plants)
✓ Unit remains available for new plants
```

## 🧮 Energy Attribution

When multiple plants share a unit, energy is attributed using:

1. **Direct Association** (Best)
   - `EnergyReadings.plant_id` field
   - Energy recorded when only one plant in unit
   - Most accurate

2. **Proportional Estimate** (Good)
   - Based on plant size/stage at time of reading
   - Weighted by growth stage power requirements
   - Fair approximation

3. **Equal Split** (Fallback)
   - Divide energy equally among plants
   - Used when no other data available
   - Conservative estimate

**Example:**
```
Unit #1 has 3 plants:
- Tomato (flowering): 60% energy
- Pepper (vegetative): 30% energy  
- Basil (seedling): 10% energy

Total unit energy: 100 kWh
Tomato gets: 60 kWh in report
Pepper gets: 30 kWh in report
Basil gets: 10 kWh in report
```

## 📋 Deletion Order

When cleaning up plant data, delete in this order:

1. **Child records first** (foreign key constraints)
   - PlantHealth
   - PlantHealthLogs
   - PlantSensors
   - GrowthUnitPlants

2. **Update references** (avoid orphaned keys)
   - Clear `active_plant_id` in GrowthUnits

3. **Parent record last**
   - Plants table entry

## 🔍 Data Verification

Before deleting plant data:

```python
# Check if other plants depend on this data
def can_safely_delete_plant(plant_id: int) -> Dict:
    """Verify what will be deleted and what will be kept."""
    
    with db.connection() as conn:
        # Count plant-specific records
        health_logs = conn.execute(
            "SELECT COUNT(*) FROM PlantHealth WHERE plant_id = ?",
            (plant_id,)
        ).fetchone()[0]
        
        # Check if plant shares unit with others
        shared_unit = conn.execute(
            """
            SELECT COUNT(*) FROM GrowthUnitPlants 
            WHERE unit_id = (
                SELECT unit_id FROM GrowthUnitPlants WHERE plant_id = ?
            ) AND plant_id != ?
            """,
            (plant_id, plant_id)
        ).fetchone()[0]
        
        # Count shared energy readings
        shared_energy = conn.execute(
            """
            SELECT COUNT(*) FROM EnergyReadings 
            WHERE unit_id = (
                SELECT unit_id FROM GrowthUnitPlants WHERE plant_id = ?
            )
            """,
            (plant_id,)
        ).fetchone()[0]
        
    return {
        'will_delete': {
            'plant_record': 1,
            'health_logs': health_logs,
            'sensor_associations': 2
        },
        'will_keep': {
            'energy_readings': shared_energy,
            'reason': 'Shared with other plants' if shared_unit > 0 else 'Historical data'
        },
        'warnings': [
            f'{shared_unit} other plants in same unit - shared data will be kept'
        ] if shared_unit > 0 else []
    }
```

## 🎯 Best Practices

### 1. Always Generate Report First
```python
# CORRECT: Report before cleanup
report = harvest_service.generate_harvest_report(plant_id)
cleanup = harvest_service.cleanup_after_harvest(plant_id)

# WRONG: Cleanup before report
cleanup = harvest_service.cleanup_after_harvest(plant_id)
report = harvest_service.generate_harvest_report(plant_id)  # Will fail!
```

### 2. Confirm Before Deletion
```python
# Show user what will be deleted
preview = can_safely_delete_plant(plant_id)

# Ask confirmation
if user_confirms(preview):
    harvest_service.harvest_and_cleanup(
        plant_id=plant_id,
        delete_plant_data=True
    )
```

### 3. Archive Before Deletion (Optional)
```python
# For extra safety, copy plant data to archive table
with db.connection() as conn:
    conn.execute("""
        INSERT INTO Plants_Archive 
        SELECT *, CURRENT_TIMESTAMP as archived_at 
        FROM Plants WHERE plant_id = ?
    """, (plant_id,))
    
# Then proceed with harvest
harvest_service.harvest_and_cleanup(plant_id)
```

### 4. Keep Energy Data Forever
```python
# NEVER delete energy readings
# They're needed for:
# - Historical analysis
# - Other plants' reports
# - System efficiency trends
# - Cost tracking

# Energy readings have plant_id, so you can always filter
# by specific plant even after plant record is deleted
```

## 📱 API Examples

### REST API Endpoints

```python
# Generate report only (keep plant data)
POST /api/plants/{plant_id}/harvest
{
    "harvest_weight_grams": 250.0,
    "quality_rating": 4,
    "notes": "Great harvest!",
    "delete_plant_data": false
}

# Generate report and delete plant data
POST /api/plants/{plant_id}/harvest
{
    "harvest_weight_grams": 250.0,
    "quality_rating": 4,
    "notes": "Great harvest!",
    "delete_plant_data": true
}

# Preview what will be deleted
GET /api/plants/{plant_id}/harvest/preview

# Delete plant data after harvest (if not done during harvest)
DELETE /api/plants/{plant_id}?reason=harvested
```

## 🔒 Data Retention Policy

Recommended retention periods:

| Data Type | Retention | Reason |
|-----------|-----------|--------|
| EnergyReadings | Forever | Cost analysis, trends |
| SensorReading | 1 year+ | Environmental patterns |
| ActuatorHistory | 1 year+ | Device efficiency |
| PlantHarvestSummary | Forever | Historical yields |
| MLTrainingData | Forever | Model improvement |
| Plants (after harvest) | 0 days* | In harvest report |
| PlantHealth (after harvest) | 0 days* | In harvest report |

*Can be deleted immediately after harvest report is generated, since all relevant data is captured in the PlantHarvestSummary JSON fields.

## 🚨 Important Notes

1. **Harvest Report is Complete**
   - Contains ALL plant-specific data in JSON format
   - Energy by stage, health incidents, environmental conditions
   - No need to keep original records after report is generated

2. **Shared Data is Sacred**
   - Never delete energy readings (even for harvested plants)
   - Never delete sensor readings
   - Never delete device history
   - These affect OTHER plants' reports!

3. **Clean Up is Optional**
   - `delete_plant_data=False` keeps everything
   - `delete_plant_data=True` deletes only plant-specific records
   - User can choose based on their needs

4. **Foreign Keys**
   - Database constraints prevent orphaned records
   - Deletion order matters (child records first)
   - Some tables use ON DELETE CASCADE

## ✅ Summary

**When harvesting a plant:**

1. ✅ **DO**: Generate comprehensive harvest report first
2. ✅ **DO**: Save report to PlantHarvestSummary table
3. ✅ **DO**: Optionally delete plant-specific records (Plants, PlantHealth, etc.)
4. ❌ **DON'T**: Delete shared energy readings
5. ❌ **DON'T**: Delete shared sensor readings
6. ❌ **DON'T**: Delete growth unit or device history
7. ✅ **DO**: Clear `active_plant_id` from unit if this was the active plant
8. ✅ **DO**: Keep unit available for new plants

**Result:**
- Complete harvest report preserved forever
- Plant-specific data cleaned up (optional)
- Shared data preserved for other plants
- Unit ready for next grow cycle

 Data Aggregation for Harvest Reports

  1. Database Migration (infrastructure/database/migrations/047_sensor_reading_summary.py)

  Creates SensorReadingSummary table storing:
  - Daily min/max/avg/sum/count/stddev per sensor
  - Linked to sensor_id, unit_id, and sensor_type
  - Indexed for efficient queries by unit, sensor, and period

  2. Database Operations (infrastructure/database/ops/devices.py)

  Added aggregation methods:
  - aggregate_sensor_readings_for_period() - Creates summaries for a specific date range
  - aggregate_readings_by_days_old() - Aggregates data older than N days (before pruning)
  - get_sensor_summaries_for_unit() - Retrieves summaries for harvest reports
  - get_sensor_summary_stats_for_harvest() - Gets overall stats grouped by sensor type

  3. Scheduled Task (app/workers/scheduled_tasks.py)

  - maintenance.aggregate_sensor_data - Runs daily at 02:30 AM
  - Aggregates readings older than 25 days (5 days before the 30-day prune threshold)
  - Creates daily summaries preserving min/max/avg values

  4. Task Schedule Order

  02:15 AM - maintenance.prune_state_history (actuator states)
  02:30 AM - maintenance.aggregate_sensor_data (NEW - summarize before pruning)
  03:00 AM - maintenance.prune_old_data (sensor readings)
  03:30 AM - maintenance.purge_old_alerts

  5. API Endpoints (app/blueprints/api/harvest_routes.py)

  - GET /api/units/<unit_id>/sensor-summaries - List daily summaries with filters
  - GET /api/units/<unit_id>/harvest-environment - Get overall environmental stats for harvest report

  Flow

  1. Sensor readings are collected continuously
  2. At 02:30 AM, readings older than 25 days are aggregated into daily summaries
  3. At 03:00 AM, readings older than 30 days are pruned
  4. When generating a harvest report, the API uses the preserved summaries to show environmental conditions throughout
  the grow cycle