# Plant Health API - Quick Reference for Frontend

## 📝 Record Plant Illness

### Endpoint
```
POST /api/plants/{plant_id}/health/record
```

### Request Body
```typescript
{
  health_status: "stressed" | "healthy" | "diseased" | "pest_infestation" | "nutrient_deficiency" | "dying",
  symptoms: string[],  // e.g., ["yellowing_leaves", "wilting"]
  severity_level: 1 | 2 | 3 | 4 | 5,  // 1=minor, 5=critical
  affected_parts: string[],  // e.g., ["leaves", "stems"]
  disease_type?: "fungal" | "bacterial" | "viral" | "pest" | "nutrient_deficiency" | "environmental_stress",
  treatment_applied?: string,  // Optional: "Applied fungicide"
  notes: string,  // Required: User's observation
  growth_stage?: string,  // Optional: Auto-detected if not provided
  image_path?: string,  // Optional: Path to uploaded photo
  user_id?: number  // Optional: User who recorded it
}
```

### Response
```typescript
{
  ok: true,
  data: {
    health_id: string,
    plant_id: number,
    plant_name: string,
    plant_type: string,  // e.g., "Tomatoes"
    growth_stage: string,  // e.g., "Vegetative"
    observation_date: string,  // ISO 8601 timestamp
    correlations: [
      {
        factor: string,  // e.g., "temperature"
        strength: number,  // 0-1 (how strongly correlated)
        confidence: number,  // 0-1 (confidence in correlation)
        recommended_range: [number, number],  // Plant-specific optimal range
        current_value: number,  // Current environmental reading
        trend: "improving" | "stable" | "worsening"
      }
    ],
    message: string
  }
}
```

### Example Usage (JavaScript)
```javascript
async function recordPlantIllness(plantId, data) {
  const response = await fetch(`/api/plants/${plantId}/health/record`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      health_status: data.status,
      symptoms: data.symptoms,
      severity_level: data.severity,
      affected_parts: data.affectedParts,
      notes: data.notes,
      treatment_applied: data.treatment || null
    })
  });
  
  return await response.json();
}

// Usage
const result = await recordPlantIllness(123, {
  status: 'stressed',
  symptoms: ['yellowing_leaves', 'wilting'],
  severity: 3,
  affectedParts: ['leaves'],
  notes: 'Lower leaves showing yellowing',
  treatment: 'Reduced watering'
});

console.log(result.data.correlations);
// Shows which environmental factors are problematic
```

---

## 📜 Get Health History

### Endpoint
```
GET /api/plants/{plant_id}/health/history?days=7
```

### Query Parameters
- `days` (optional): Number of days of history (default: 7)

### Response
```typescript
{
  ok: true,
  data: {
    plant_id: number,
    plant_name: string,
    plant_type: string,
    observations: [
      {
        health_id: string,
        observation_date: string,
        health_status: string,
        symptoms: string,  // JSON string
        disease_type: string | null,
        severity_level: number,
        treatment_applied: string | null
      }
    ],
    count: number,
    days: number
  }
}
```

### Example Usage
```javascript
async function getPlantHealthHistory(plantId, days = 7) {
  const response = await fetch(`/api/plants/${plantId}/health/history?days=${days}`);
  return await response.json();
}

// Usage
const history = await getPlantHealthHistory(123, 14);
history.data.observations.forEach(obs => {
  const symptoms = JSON.parse(obs.symptoms);
  console.log(`${obs.observation_date}: ${obs.health_status} (severity ${obs.severity_level})`);
  console.log(`Symptoms: ${symptoms.join(', ')}`);
});
```

---

## 💡 Get Health Recommendations

### Endpoint
```
GET /api/plants/{plant_id}/health/recommendations
```

### Response
```typescript
{
  ok: true,
  data: {
    plant_id: number,
    plant_name: string,
    plant_type: string,
    growth_stage: string,
    recommendations: {
      status: string,
      plant_type: string,
      growth_stage: string,
      symptom_recommendations: [
        {
          issue: string,
          frequency: number,
          likely_causes: string[],
          recommended_actions: string[]
        }
      ],
      environmental_recommendations: [
        {
          factor: string,
          issue: string,
          current_value: number,
          recommended_range: [number, number],
          action: string,
          plant_specific: boolean  // true if using plant-specific thresholds
        }
      ],
      trend: "improving" | "stable" | "declining" | "insufficient_data"
    }
  }
}
```

### Example Usage
```javascript
async function getHealthRecommendations(plantId) {
  const response = await fetch(`/api/plants/${plantId}/health/recommendations`);
  return await response.json();
}

// Usage
const recommendations = await getHealthRecommendations(123);
const { symptom_recommendations, environmental_recommendations, trend } = recommendations.data.recommendations;

// Display symptom-based recommendations
symptom_recommendations.forEach(rec => {
  console.log(`Issue: ${rec.issue} (occurred ${rec.frequency} times)`);
  console.log(`Likely causes: ${rec.likely_causes.join(', ')}`);
  console.log(`Actions: ${rec.recommended_actions.join(', ')}`);
});

// Display environmental recommendations (plant-specific!)
environmental_recommendations.forEach(rec => {
  console.log(`${rec.factor}: ${rec.issue}`);
  console.log(`Current: ${rec.current_value}, Optimal: ${rec.recommended_range.join('-')}`);
  console.log(`Action: ${rec.action}`);
  if (rec.plant_specific) {
    console.log('(Using plant-specific thresholds for this species)');
  }
});
```

---

## 🔍 Get Available Symptoms

### Endpoint
```
GET /api/health/symptoms
```

### Response
```typescript
{
  ok: true,
  data: {
    symptoms: [
      {
        name: string,  // e.g., "yellowing_leaves"
        likely_causes: string[],
        environmental_factors: string[]
      }
    ],
    count: number
  }
}
```

### Example Usage
```javascript
async function getAvailableSymptoms() {
  const response = await fetch('/api/health/symptoms');
  return await response.json();
}

// Usage - populate symptom checkboxes
const { symptoms } = (await getAvailableSymptoms()).data;
const symptomCheckboxes = symptoms.map(symptom => ({
  value: symptom.name,
  label: symptom.name.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()),
  info: `Likely causes: ${symptom.likely_causes.join(', ')}`
}));
```

---

## 📋 Get Health Status Options

### Endpoint
```
GET /api/health/statuses
```

### Response
```typescript
{
  ok: true,
  data: {
    health_statuses: [
      { value: string, name: string }
    ],
    disease_types: [
      { value: string, name: string }
    ]
  }
}
```

### Example Usage
```javascript
async function getHealthStatuses() {
  const response = await fetch('/api/health/statuses');
  return await response.json();
}

// Usage - populate dropdowns
const { health_statuses, disease_types } = (await getHealthStatuses()).data;

// For health status dropdown
const statusOptions = health_statuses.map(s => ({
  value: s.value,
  label: s.name.replace(/_/g, ' ').toLowerCase().replace(/\b\w/g, l => l.toUpperCase())
}));

// For disease type dropdown
const diseaseOptions = disease_types.map(d => ({
  value: d.value,
  label: d.name.replace(/_/g, ' ').toLowerCase().replace(/\b\w/g, l => l.toUpperCase())
}));
```

---

## 🎨 Complete Example: Health Recording Form (React)

```tsx
import React, { useState, useEffect } from 'react';

interface HealthFormData {
  health_status: string;
  symptoms: string[];
  severity_level: number;
  affected_parts: string[];
  disease_type?: string;
  treatment_applied?: string;
  notes: string;
}

function PlantHealthForm({ plantId, onSuccess }: { plantId: number, onSuccess: () => void }) {
  const [symptoms, setSymptoms] = useState<any[]>([]);
  const [statuses, setStatuses] = useState<any[]>([]);
  const [diseaseTypes, setDiseaseTypes] = useState<any[]>([]);
  const [formData, setFormData] = useState<HealthFormData>({
    health_status: '',
    symptoms: [],
    severity_level: 3,
    affected_parts: [],
    notes: ''
  });

  // Load available options
  useEffect(() => {
    fetch('/api/health/symptoms')
      .then(r => r.json())
      .then(data => setSymptoms(data.data.symptoms));
    
    fetch('/api/health/statuses')
      .then(r => r.json())
      .then(data => {
        setStatuses(data.data.health_statuses);
        setDiseaseTypes(data.data.disease_types);
      });
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    const response = await fetch(`/api/plants/${plantId}/health/record`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(formData)
    });
    
    if (response.ok) {
      const result = await response.json();
      alert(`Health recorded! ${result.data.correlations.length} environmental correlations found.`);
      onSuccess();
    }
  };

  return (
    <form onSubmit={handleSubmit} className="health-form">
      {/* Health Status */}
      <div className="form-group">
        <label>Health Status *</label>
        <select 
          value={formData.health_status}
          onChange={e => setFormData({...formData, health_status: e.target.value})}
          required
        >
          <option value="">Select status</option>
          {statuses.map(s => (
            <option key={s.value} value={s.value}>
              {s.name.replace(/_/g, ' ')}
            </option>
          ))}
        </select>
      </div>

      {/* Symptoms */}
      <div className="form-group">
        <label>Symptoms *</label>
        <div className="checkbox-grid">
          {symptoms.map(symptom => (
            <label key={symptom.name}>
              <input 
                type="checkbox"
                checked={formData.symptoms.includes(symptom.name)}
                onChange={e => {
                  const newSymptoms = e.target.checked
                    ? [...formData.symptoms, symptom.name]
                    : formData.symptoms.filter(s => s !== symptom.name);
                  setFormData({...formData, symptoms: newSymptoms});
                }}
              />
              {symptom.name.replace(/_/g, ' ')}
            </label>
          ))}
        </div>
      </div>

      {/* Severity */}
      <div className="form-group">
        <label>Severity: {formData.severity_level}/5</label>
        <input 
          type="range" 
          min="1" 
          max="5" 
          value={formData.severity_level}
          onChange={e => setFormData({...formData, severity_level: parseInt(e.target.value)})}
        />
      </div>

      {/* Affected Parts */}
      <div className="form-group">
        <label>Affected Parts *</label>
        <div className="checkbox-grid">
          {['leaves', 'stems', 'roots', 'flowers', 'fruit'].map(part => (
            <label key={part}>
              <input 
                type="checkbox"
                checked={formData.affected_parts.includes(part)}
                onChange={e => {
                  const newParts = e.target.checked
                    ? [...formData.affected_parts, part]
                    : formData.affected_parts.filter(p => p !== part);
                  setFormData({...formData, affected_parts: newParts});
                }}
              />
              {part}
            </label>
          ))}
        </div>
      </div>

      {/* Disease Type (optional) */}
      <div className="form-group">
        <label>Disease Type (optional)</label>
        <select 
          value={formData.disease_type || ''}
          onChange={e => setFormData({...formData, disease_type: e.target.value || undefined})}
        >
          <option value="">Not sure</option>
          {diseaseTypes.map(d => (
            <option key={d.value} value={d.value}>
              {d.name.replace(/_/g, ' ')}
            </option>
          ))}
        </select>
      </div>

      {/* Treatment Applied */}
      <div className="form-group">
        <label>Treatment Applied</label>
        <input 
          type="text"
          value={formData.treatment_applied || ''}
          onChange={e => setFormData({...formData, treatment_applied: e.target.value})}
          placeholder="e.g., Applied fungicide, Adjusted watering"
        />
      </div>

      {/* Notes */}
      <div className="form-group">
        <label>Notes *</label>
        <textarea 
          value={formData.notes}
          onChange={e => setFormData({...formData, notes: e.target.value})}
          placeholder="Describe what you're observing..."
          required
          rows={4}
        />
      </div>

      <button type="submit">Record Health Observation</button>
    </form>
  );
}

export default PlantHealthForm;
```

---

## 🎯 Key Points for Frontend Developers

1. **Auto-Detection**: The backend automatically detects `plant_type` and `growth_stage` from `plant_id`, so you don't need to provide them (but you can if you want).

2. **Plant-Specific Thresholds**: Environmental correlations use plant-specific thresholds, so a temperature of 25°C might be:
   - ✅ Perfect for tomatoes (optimal: 22-28°C)
   - ⚠️ Too warm for lettuce (optimal: 18-24°C)

3. **Required Fields**:
   - `health_status`
   - `symptoms` (array)
   - `severity_level` (1-5)
   - `affected_parts` (array)
   - `notes`

4. **Optional but Recommended**:
   - `disease_type` - Helps with diagnosis
   - `treatment_applied` - Tracks what user tried
   - `image_path` - Visual record

5. **Response Correlations**: The response includes environmental correlations that show which factors are problematic for THIS specific plant species.

---

## 🚨 Error Handling

```javascript
async function recordHealthWithErrorHandling(plantId, data) {
  try {
    const response = await fetch(`/api/plants/${plantId}/health/record`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    
    const result = await response.json();
    
    if (!result.ok) {
      // API returned error
      throw new Error(result.error.message || 'Failed to record health');
    }
    
    return result;
  } catch (error) {
    console.error('Error recording health:', error);
    throw error;
  }
}
```

---

## 📱 Mobile App Integration (Flutter/Dart)

```dart
// Example for mobile-app/lib/services/
class PlantHealthService {
  Future<Map<String, dynamic>> recordPlantHealth(
    int plantId,
    Map<String, dynamic> data,
  ) async {
    final response = await http.post(
      Uri.parse('$apiUrl/plants/$plantId/health/record'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode(data),
    );
    
    return jsonDecode(response.body);
  }
  
  Future<List<dynamic>> getHealthHistory(int plantId, {int days = 7}) async {
    final response = await http.get(
      Uri.parse('$apiUrl/plants/$plantId/health/history?days=$days'),
    );
    
    final result = jsonDecode(response.body);
    return result['data']['observations'];
  }
}
```

This API is now ready for frontend integration! 🚀
