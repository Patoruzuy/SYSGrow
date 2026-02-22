# Plant-Specific Health Monitoring System

## Overview

The plant health monitoring system has been enhanced to use **plant-specific environmental thresholds** based on plant type and growth stage. This means that instead of using generic hardcoded thresholds for all plants, the system now recognizes that different plant species (e.g., tomatoes vs. lettuce) have different optimal environmental conditions.

## Architecture

### Components

1. **PlantThresholdManager** (`ai/plant_threshold_manager.py`)
   - Loads plant-specific environmental thresholds from `plants_info.json`
   - Supports both plant-level and growth stage-level thresholds
   - Provides caching for performance
   - Falls back to generic thresholds when plant data unavailable

2. **PlantHealthMonitor** (`ai/plant_health_monitor.py`)
   - Records plant health observations
   - Analyzes environmental correlations with plant-specific thresholds
   - Provides health recommendations
   - Tracks health trends over time

3. **Plant Health API Endpoints** (`app/blueprints/api/plants.py`)
   - `POST /plants/<plant_id>/health/record` - Record illness
   - `GET /plants/<plant_id>/health/history` - View history
   - `GET /plants/<plant_id>/health/recommendations` - Get recommendations
   - `GET /health/symptoms` - List available symptoms
   - `GET /health/statuses` - List health status options

## Key Features

### 1. Plant-Specific Thresholds

Different plants have different optimal conditions:

**Example: Temperature Optimal Ranges**
- **Tomatoes**: 22-28°C (warmer)
- **Lettuce**: 18-24°C (cooler)
- **Peppers**: 22-28°C (warmer)

**Example: Humidity Optimal Ranges**
- **Tomatoes**: 40-60%
- **Lettuce**: 50-70% (higher)
- **Peppers**: 40-60%

### 2. Growth Stage-Specific Thresholds

Thresholds can vary by growth stage for the same plant:

**Example: Cannabis**
- **Seedling**: Higher humidity (60-70%), moderate temp
- **Vegetative**: Moderate humidity (50-60%), warmer temp
- **Flowering**: Lower humidity (40-50%), controlled temp

### 3. Intelligent Fallback

The system gracefully handles missing data:
1. **Best**: Plant-specific + growth stage thresholds
2. **Good**: Plant-specific averaged thresholds
3. **Fallback**: Generic thresholds

## API Usage

### Recording a Plant Illness

```bash
POST /plants/123/health/record
Content-Type: application/json

{
  "health_status": "stressed",
  "symptoms": ["yellowing_leaves", "wilting"],
  "disease_type": "environmental_stress",
  "severity_level": 3,
  "affected_parts": ["leaves"],
  "treatment_applied": "Adjusted watering schedule",
  "notes": "Lower leaves showing yellowing, possibly overwatered",
  "growth_stage": "Vegetative"
}
```

**Response:**
```json
{
  "ok": true,
  "data": {
    "health_id": "abc-123-def",
    "plant_id": 123,
    "plant_name": "Tomato Plant #1",
    "plant_type": "Tomatoes",
    "growth_stage": "Vegetative",
    "observation_date": "2024-01-15T10:30:00",
    "correlations": [
      {
        "factor": "soil_moisture",
        "strength": 0.75,
        "confidence": 0.8,
        "recommended_range": [60, 70],
        "current_value": 82,
        "trend": "worsening"
      },
      {
        "factor": "temperature",
        "strength": 0.2,
        "confidence": 0.6,
        "recommended_range": [22, 28],
        "current_value": 24,
        "trend": "stable"
      }
    ],
    "message": "Health observation recorded successfully"
  }
}
```

### Getting Health History

```bash
GET /plants/123/health/history?days=14
```

**Response:**
```json
{
  "ok": true,
  "data": {
    "plant_id": 123,
    "plant_name": "Tomato Plant #1",
    "plant_type": "Tomatoes",
    "observations": [
      {
        "health_id": "abc-123",
        "observation_date": "2024-01-15T10:30:00",
        "health_status": "stressed",
        "symptoms": ["yellowing_leaves", "wilting"],
        "severity_level": 3,
        "treatment_applied": "Adjusted watering"
      }
    ],
    "count": 1,
    "days": 14
  }
}
```

### Getting Health Recommendations

```bash
GET /plants/123/health/recommendations
```

**Response:**
```json
{
  "ok": true,
  "data": {
    "plant_id": 123,
    "plant_name": "Tomato Plant #1",
    "plant_type": "Tomatoes",
    "growth_stage": "Vegetative",
    "recommendations": {
      "status": "stressed",
      "plant_type": "Tomatoes",
      "growth_stage": "Vegetative",
      "symptom_recommendations": [
        {
          "issue": "yellowing_leaves",
          "frequency": 2,
          "likely_causes": ["overwatering", "nitrogen_deficiency", "root_rot"],
          "recommended_actions": [
            "Check drainage and reduce watering if overwatered",
            "Apply nitrogen fertilizer if deficiency suspected",
            "Inspect roots for rot and trim if necessary"
          ]
        }
      ],
      "environmental_recommendations": [
        {
          "factor": "soil_moisture",
          "issue": "soil_moisture too high",
          "current_value": 82,
          "recommended_range": [60, 70],
          "action": "Decrease soil_moisture",
          "plant_specific": true
        }
      ],
      "trend": "declining"
    }
  }
}
```

### Getting Available Symptoms

```bash
GET /health/symptoms
```

**Response:**
```json
{
  "ok": true,
  "data": {
    "symptoms": [
      {
        "name": "yellowing_leaves",
        "likely_causes": ["overwatering", "nitrogen_deficiency", "root_rot"],
        "environmental_factors": ["soil_moisture", "drainage", "nutrition"]
      },
      {
        "name": "brown_spots",
        "likely_causes": ["fungal_infection", "bacterial_spot", "nutrient_burn"],
        "environmental_factors": ["humidity", "air_circulation", "nutrition"]
      }
    ],
    "count": 8
  }
}
```

### Getting Health Status Options

```bash
GET /health/statuses
```

**Response:**
```json
{
  "ok": true,
  "data": {
    "health_statuses": [
      {"value": "healthy", "name": "HEALTHY"},
      {"value": "stressed", "name": "STRESSED"},
      {"value": "diseased", "name": "DISEASED"},
      {"value": "pest_infestation", "name": "PEST_INFESTATION"},
      {"value": "nutrient_deficiency", "name": "NUTRIENT_DEFICIENCY"},
      {"value": "dying", "name": "DYING"}
    ],
    "disease_types": [
      {"value": "fungal", "name": "FUNGAL"},
      {"value": "bacterial", "name": "BACTERIAL"},
      {"value": "viral", "name": "VIRAL"},
      {"value": "pest", "name": "PEST"},
      {"value": "nutrient_deficiency", "name": "NUTRIENT_DEFICIENCY"},
      {"value": "environmental_stress", "name": "ENVIRONMENTAL_STRESS"}
    ]
  }
}
```

## Frontend Integration

### Health Recording Form

The frontend should provide a user-friendly form with:

1. **Plant Selection** (dropdown of user's plants)
2. **Health Status** (dropdown: healthy, stressed, diseased, etc.)
3. **Symptoms** (multi-select checkboxes)
   - Use `GET /health/symptoms` to populate options
4. **Severity** (slider 1-5)
5. **Affected Parts** (multi-select: leaves, stems, roots, flowers, fruit)
6. **Disease Type** (optional dropdown)
7. **Treatment Applied** (text input)
8. **Notes** (text area)
9. **Photo Upload** (optional file upload)

### Health Dashboard

Display:
- **Current Health Status** (color-coded badge)
- **Recent Observations** (timeline)
- **Environmental Correlations** (chart showing deviations)
- **Recommended Actions** (actionable list)
- **Health Trend** (improving/stable/declining with chart)

### Example React Component Structure

```jsx
// HealthRecordingForm.jsx
import { useState, useEffect } from 'react';

function HealthRecordingForm({ plantId, onSuccess }) {
  const [symptoms, setSymptoms] = useState([]);
  const [statuses, setStatuses] = useState([]);
  const [formData, setFormData] = useState({
    health_status: '',
    symptoms: [],
    severity_level: 3,
    affected_parts: [],
    notes: ''
  });

  useEffect(() => {
    // Load available symptoms and statuses
    fetch('/api/health/symptoms').then(r => r.json())
      .then(data => setSymptoms(data.data.symptoms));
    
    fetch('/api/health/statuses').then(r => r.json())
      .then(data => setStatuses(data.data.health_statuses));
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    const response = await fetch(`/api/plants/${plantId}/health/record`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(formData)
    });
    
    if (response.ok) {
      const result = await response.json();
      onSuccess(result.data);
    }
  };

  return (
    <form onSubmit={handleSubmit}>
      {/* Health Status Dropdown */}
      <select 
        value={formData.health_status}
        onChange={e => setFormData({...formData, health_status: e.target.value})}
      >
        {statuses.map(s => (
          <option key={s.value} value={s.value}>{s.name}</option>
        ))}
      </select>

      {/* Symptoms Multi-Select */}
      <div>
        {symptoms.map(symptom => (
          <label key={symptom.name}>
            <input 
              type="checkbox"
              value={symptom.name}
              onChange={e => {
                const newSymptoms = e.target.checked
                  ? [...formData.symptoms, symptom.name]
                  : formData.symptoms.filter(s => s !== symptom.name);
                setFormData({...formData, symptoms: newSymptoms});
              }}
            />
            {symptom.name.replace('_', ' ')}
          </label>
        ))}
      </div>

      {/* Severity Slider */}
      <input 
        type="range" 
        min="1" 
        max="5" 
        value={formData.severity_level}
        onChange={e => setFormData({...formData, severity_level: parseInt(e.target.value)})}
      />
      <span>Severity: {formData.severity_level}/5</span>

      {/* Notes */}
      <textarea 
        value={formData.notes}
        onChange={e => setFormData({...formData, notes: e.target.value})}
        placeholder="Describe what you're observing..."
      />

      <button type="submit">Record Health Observation</button>
    </form>
  );
}
```

## Data Flow

```
User Records Illness (Frontend)
  ↓
POST /plants/<id>/health/record
  ↓
PlantHealthMonitor.record_health_observation()
  ↓
1. Get plant_type from plant_id
2. Get current growth_stage from plant
3. Load plant-specific thresholds (PlantThresholdManager)
4. Get recent environmental data
5. Analyze correlations using plant-specific thresholds
6. Store observation in PlantHealthLogs table
7. Return correlations and recommendations
  ↓
Frontend displays:
  - Confirmation
  - Environmental correlations
  - Recommended actions
```

## Database Schema

### PlantHealthLogs Table

```sql
CREATE TABLE PlantHealthLogs (
    health_id TEXT PRIMARY KEY,
    unit_id INTEGER NOT NULL,
    plant_id INTEGER,
    observation_date TEXT NOT NULL,
    health_status TEXT NOT NULL,
    symptoms TEXT,  -- JSON array
    disease_type TEXT,
    severity_level INTEGER,
    affected_parts TEXT,  -- JSON array
    environmental_factors TEXT,  -- JSON object
    treatment_applied TEXT,
    notes TEXT,
    image_path TEXT,
    user_id INTEGER,
    FOREIGN KEY (unit_id) REFERENCES GrowthUnits(unit_id),
    FOREIGN KEY (plant_id) REFERENCES Plants(plant_id)
);
```

### Plants Table (relevant fields)

```sql
CREATE TABLE Plants (
    plant_id INTEGER PRIMARY KEY,
    unit_id INTEGER NOT NULL,
    plant_name TEXT NOT NULL,
    plant_type TEXT NOT NULL,  -- e.g., 'Tomatoes', 'Lettuce'
    current_growth_stage TEXT,  -- e.g., 'Vegetative', 'Flowering'
    days_in_stage INTEGER,
    ...
);
```

## Benefits

### 1. Accurate Health Assessment
- **Before**: All plants compared to generic 20-26°C range
- **After**: Lettuce assessed against 18-24°C, Tomatoes against 22-28°C

### 2. Better Environmental Recommendations
- **Before**: Generic "increase temperature" advice
- **After**: "Temperature is 17°C, optimal for Lettuce is 18-24°C, increase by 1-2°C"

### 3. Improved Prediction Accuracy
- Environmental correlations are more meaningful
- Severity calculations are plant-specific
- Historical data can be analyzed per plant type

### 4. Growth Stage Awareness
- Different stages have different needs
- Seedlings need different conditions than flowering plants
- Recommendations adapt as plant matures

## Testing

Run the test suite:

```bash
cd backend
python test_plant_thresholds.py
```

**Test Coverage:**
- ✅ Generic threshold fallback
- ✅ Plant-specific threshold loading
- ✅ Growth stage-specific thresholds
- ✅ Multiple plant comparison
- ✅ Growth stage enumeration
- ✅ Threshold caching
- ✅ Threshold bound validation
- ✅ Stage-to-stage comparison

## Migration from Old System

### Code Changes Required

**Old Code:**
```python
monitor = PlantHealthMonitor(db_handler)
observation = PlantHealthObservation(
    unit_id=1,
    plant_id=None,  # No plant_type information
    ...
)
monitor.record_health_observation(observation)
```

**New Code:**
```python
monitor = PlantHealthMonitor(db_handler)
observation = PlantHealthObservation(
    unit_id=1,
    plant_id=123,  # System will auto-detect plant_type
    plant_type="Tomatoes",  # Or provide explicitly
    growth_stage="Vegetative",  # Optional but recommended
    ...
)
monitor.record_health_observation(observation)
```

### Backward Compatibility

The system is backward compatible:
- If `plant_type` is not provided, system tries to get it from `plant_id`
- If `plant_id` is not provided, system uses generic thresholds
- Existing health logs continue to work (they just used generic thresholds)

## Future Enhancements

1. **Machine Learning Integration**
   - Train models on historical plant-specific health data
   - Predict health issues before they become severe
   - Personalize thresholds based on user's environment

2. **User-Configurable Thresholds**
   - Allow users to override thresholds per plant
   - Learn from user's actual growing conditions
   - Adapt to local climate variations

3. **Photo Analysis**
   - AI-powered symptom detection from plant photos
   - Automatic disease identification
   - Visual health tracking over time

4. **Automated Treatments**
   - Link health recommendations to actuator controls
   - Auto-adjust environment when health issues detected
   - Schedule preventive maintenance

## Troubleshooting

### Plant Type Not Found
**Issue**: System falls back to generic thresholds
**Solution**: Verify plant name matches `plants_info.json` exactly
- Use `GET /health/symptoms` to see available plant types
- Check for typos in plant_type field

### Growth Stage Not Recognized
**Issue**: System uses averaged thresholds instead of stage-specific
**Solution**: Verify growth stage name matches plant's growth_stages
- Use `PlantThresholdManager.get_plant_growth_stages("PlantName")`
- Check spelling and capitalization

### Thresholds Seem Wrong
**Issue**: Unexpected threshold values
**Solution**: 
1. Check `plants_info.json` for plant's environmental data
2. Verify growth stage data exists for the stage
3. Test with `test_plant_thresholds.py`

## Summary

The plant-specific health monitoring system provides:
- ✅ Species-specific environmental thresholds
- ✅ Growth stage-aware assessments
- ✅ Intelligent fallback system
- ✅ User-friendly API endpoints
- ✅ Frontend-ready design
- ✅ Comprehensive testing
- ✅ Backward compatibility

This enhancement makes the health monitoring system significantly more accurate and useful for users growing different types of plants.
