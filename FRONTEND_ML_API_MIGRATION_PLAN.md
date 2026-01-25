# Frontend ML/AI API Migration Plan

## Executive Summary

Migrate all web frontend API calls from legacy scattered endpoints to the new consolidated `/api/ml/*` structure. **No backward compatibility needed** - we'll update all endpoints in one go.

## Scope

### Frontend Locations
- `static/js/api.js` - Main API client with helper methods
- `static/js/dashboard.js` - Dashboard widgets and data fetching
- `templates/index.html` - Dashboard UI with inline fetch calls

### Mobile App Status
✅ **No changes needed** - Mobile app (`mobile-app/`) currently only handles:
- Device discovery (mDNS, BLE)
- Relay control
- MQTT messaging
- WiFi configuration

No AI/ML endpoints are currently used in the mobile app.

---

## API Endpoint Migration Map

### 1. Disease Predictions

#### Current Usage in `static/js/api.js`:
```javascript
getDiseaseRisks(unitId = null, riskLevel = null) {
    const params = new URLSearchParams();
    if (unitId) params.append('unit_id', unitId);
    if (riskLevel) params.append('risk_level', riskLevel);
    const query = params.toString();
    return get(`/api/disease/risks${query ? '?' + query : ''}`);
}
```

#### New Implementation:
```javascript
getDiseaseRisks(unitId = null, riskLevel = null) {
    const params = new URLSearchParams();
    if (unitId) params.append('unit_id', unitId);
    if (riskLevel) params.append('risk_level', riskLevel);
    const query = params.toString();
    return get(`/api/ml/predictions/disease/risks${query ? '?' + query : ''}`);
}
```

**Changes:**
- `/api/disease/risks` → `/api/ml/predictions/disease/risks`

---

### 2. Disease Alerts

#### Expected Current Usage:
```javascript
// May exist in dashboard.js or inline fetches
fetch('/api/disease/alerts')
```

#### New Implementation:
```javascript
getDiseaseAlerts(unitId = null) {
    const params = new URLSearchParams();
    if (unitId) params.append('unit_id', unitId);
    const query = params.toString();
    return get(`/api/ml/predictions/disease/alerts${query ? '?' + query : ''}`);
}
```

**Changes:**
- `/api/disease/alerts` → `/api/ml/predictions/disease/alerts`

---

### 3. Disease Statistics

#### Expected Usage (dashboard analytics):
```javascript
fetch('/api/disease/statistics?days=90')
```

#### New Implementation:
```javascript
getDiseaseStatistics(days = 90, unitId = null) {
    const params = new URLSearchParams({ days });
    if (unitId) params.append('unit_id', unitId);
    const query = params.toString();
    return get(`/api/ml/analytics/disease/statistics?${query}`);
}
```

**Changes:**
- `/api/disease/statistics` → `/api/ml/analytics/disease/statistics`

---

### 4. Growth Stage Predictions

#### Expected Current Usage:
```javascript
fetch('/api/growth-stages/predict/vegetative')
fetch('/api/growth-stages/status')
```

#### New Implementation:
```javascript
// Get optimal conditions for a growth stage
getGrowthConditions(stage, daysInStage = null) {
    const params = new URLSearchParams();
    if (daysInStage) params.append('days_in_stage', daysInStage);
    const query = params.toString();
    return get(`/api/ml/predictions/growth/${stage}${query ? '?' + query : ''}`);
}

// Get all growth stages
getAllGrowthStages() {
    return get('/api/ml/predictions/growth/stages/all');
}

// Get growth prediction status
getGrowthStatus() {
    return get('/api/ml/predictions/growth/status');
}

// Analyze growth transition
analyzeGrowthTransition(unitId, fromStage, toStage) {
    return post('/api/ml/predictions/growth/transition-analysis', {
        unit_id: unitId,
        from_stage: fromStage,
        to_stage: toStage
    });
}
```

**Changes:**
- `/api/growth-stages/predict/<stage>` → `/api/ml/predictions/growth/<stage>`
- `/api/growth-stages/all` → `/api/ml/predictions/growth/stages/all`
- `/api/growth-stages/status` → `/api/ml/predictions/growth/status`
- `/api/growth-stages/transition-analysis` → `/api/ml/predictions/growth/transition-analysis`

---

### 5. Climate Optimization

#### Expected Current Usage:
```javascript
fetch('/api/ai/climate/recommendations?unit_id=1')
```

#### New Implementation:
```javascript
// Get optimal climate for growth stage
getClimateConditions(growthStage) {
    return get(`/api/ml/predictions/climate/${growthStage}`);
}

// Get climate recommendations for specific unit
getClimateRecommendations(unitId) {
    return get(`/api/ml/predictions/climate/${unitId}/recommendations`);
}

// Check watering issues
getWateringIssues(unitId) {
    return get(`/api/ml/predictions/climate/${unitId}/watering-issues`);
}
```

**Changes:**
- `/api/ai/climate/recommendations` → `/api/ml/predictions/climate/<stage>` or `/api/ml/predictions/climate/<unit_id>/recommendations`

---

### 6. Health Monitoring

#### Expected Current Usage:
```javascript
fetch('/api/ai/health/recommendations?unit_id=1')
fetch('/api/ai/health/observation', { method: 'POST', ... })
```

#### New Implementation:
```javascript
// Get health recommendations
getHealthRecommendations(unitId, plantType = null, growthStage = null) {
    const params = new URLSearchParams();
    if (plantType) params.append('plant_type', plantType);
    if (growthStage) params.append('growth_stage', growthStage);
    const query = params.toString();
    return get(`/api/ml/predictions/health/${unitId}/recommendations${query ? '?' + query : ''}`);
}

// Record health observation
recordHealthObservation(observation) {
    return post('/api/ml/predictions/health/observation', observation);
}
```

**Changes:**
- `/api/ai/health/recommendations` → `/api/ml/predictions/health/<unit_id>/recommendations`
- `/api/ai/health/observation` → `/api/ml/predictions/health/observation`

---

### 7. Model Management

#### Expected Current Usage:
```javascript
fetch('/api/ai/models')
fetch('/api/ai/models/disease_v2/promote', { method: 'POST' })
```

#### New Implementation:
```javascript
// List all models
getModels() {
    return get('/api/ml/models/');
}

// Get model versions
getModelVersions(modelName) {
    return get(`/api/ml/models/${modelName}/versions`);
}

// Promote model to production
promoteModel(modelName, version) {
    return post(`/api/ml/models/${modelName}/promote`, { version });
}

// Get model metadata
getModelMetadata(modelName) {
    return get(`/api/ml/models/${modelName}/metadata`);
}

// Get overall model status
getModelsStatus() {
    return get('/api/ml/models/status');
}
```

**Changes:**
- `/api/ai/models` → `/api/ml/models/`
- `/api/ai/models/<name>/promote` → `/api/ml/models/<name>/promote`

---

### 8. Model Monitoring

#### New Functionality (may not exist yet):
```javascript
// Get model drift metrics
getModelDrift(modelName) {
    return get(`/api/ml/monitoring/drift/${modelName}`);
}

// Get continuous monitoring insights for unit
getMonitoringInsights(unitId) {
    return get(`/api/ml/monitoring/insights/${unitId}`);
}

// Get critical insights across all units
getCriticalInsights() {
    return get('/api/ml/monitoring/insights/critical');
}
```

**Changes:**
- New endpoints - no legacy equivalents

---

### 9. Analytics

#### Expected Current Usage:
```javascript
fetch('/api/insights/analytics/actuators/1/dashboard')
fetch('/api/insights/analytics/predictions/failure')
```

#### New Implementation:
```javascript
// Get energy dashboard for actuator
getActuatorEnergyDashboard(actuatorId, days = 7) {
    return get(`/api/ml/analytics/energy/actuator/${actuatorId}/dashboard?days=${days}`);
}

// Predict actuator failure
predictActuatorFailure(actuatorId) {
    return get(`/api/ml/analytics/energy/actuator/${actuatorId}/predict-failure`);
}
```

**Changes:**
- `/api/insights/analytics/actuators/<id>/dashboard` → `/api/ml/analytics/energy/actuator/<id>/dashboard`
- `/api/insights/analytics/predictions/` → `/api/ml/analytics/energy/actuator/<id>/predict-failure`

---

### 10. Model Retraining

#### Expected Current Usage:
```javascript
fetch('/api/retraining/jobs')
fetch('/api/retraining/trigger', { method: 'POST' })
```

#### New Implementation:
```javascript
// List retraining jobs
getRetrainingJobs() {
    return get('/api/ml/retraining/jobs');
}

// Schedule new retraining job
scheduleRetraining(modelName, config) {
    return post('/api/ml/retraining/jobs', { model_name: modelName, ...config });
}

// Cancel retraining job
cancelRetraining(jobId) {
    return del(`/api/ml/retraining/jobs/${jobId}`);
}

// Manually trigger retraining
triggerRetraining(modelName, force = false) {
    return post('/api/ml/retraining/trigger', { model_name: modelName, force });
}

// Get retraining system status
getRetrainingStatus() {
    return get('/api/ml/retraining/status');
}
```

**Changes:**
- `/api/retraining/*` → `/api/ml/retraining/*`

---

## Implementation Steps

### Phase 1: Update API Client (`static/js/api.js`)

1. **Search for all legacy endpoint calls**
   ```bash
   grep -r "api/ai/" static/js/
   grep -r "api/disease/" static/js/
   grep -r "api/growth-stages/" static/js/
   grep -r "api/retraining/" static/js/
   grep -r "api/insights/" static/js/
   ```

2. **Update helper methods in api.js**
   - Update `getDiseaseRisks()` method
   - Add missing helper methods for new endpoints
   - Remove deprecated methods

3. **Test API client**
   - Verify all methods return correct URLs
   - Check parameter handling

### Phase 2: Update Dashboard (`static/js/dashboard.js`)

1. **Find all direct fetch calls**
   ```bash
   grep "fetch('/api/" static/js/dashboard.js
   ```

2. **Replace with new API helper methods**
   - Use the updated methods from api.js
   - Ensure error handling remains consistent

3. **Update data transformations**
   - Check if response structure changed
   - Update any hardcoded field names

### Phase 3: Update HTML Templates

1. **Search templates for inline API calls**
   ```bash
   grep -r "fetch('/api/" templates/
   ```

2. **Replace inline fetch calls**
   - Move to api.js helpers where possible
   - Update URLs for remaining inline calls

3. **Update JavaScript in `<script>` tags**
   - Check event handlers
   - Update WebSocket subscriptions if needed

### Phase 4: Update WebSocket Handlers

1. **Check `static/js/websocket.js` or similar**
   - WebSocket events should remain at `/ml` namespace (no change needed)
   - Update any REST API fallbacks

2. **Verify event names**
   - Model training events
   - Drift alerts
   - Continuous monitoring updates

### Phase 5: Testing

1. **Unit Testing**
   - Test each API helper method
   - Verify parameter encoding
   - Check error handling

2. **Integration Testing**
   - Load dashboard and check console for errors
   - Verify all widgets load data correctly
   - Test disease risk cards
   - Test growth stage display
   - Test analytics charts

3. **End-to-End Testing**
   - Navigate through all dashboard sections
   - Trigger manual predictions
   - Test model management UI
   - Verify alerts display correctly

---

## File-by-File Changes

### File: `static/js/api.js`

**Current problematic code:**
```javascript
getDiseaseRisks(unitId = null, riskLevel = null) {
    const params = new URLSearchParams();
    if (unitId) params.append('unit_id', unitId);
    if (riskLevel) params.append('risk_level', riskLevel);
    const query = params.toString();
    return get(`/api/disease/risks${query ? '?' + query : ''}`);
}
```

**Updated code:**
```javascript
// ==================== ML/AI Predictions ====================

// Disease Predictions
getDiseaseRisks(unitId = null, riskLevel = null) {
    const params = new URLSearchParams();
    if (unitId) params.append('unit_id', unitId);
    if (riskLevel) params.append('risk_level', riskLevel);
    const query = params.toString();
    return get(`/api/ml/predictions/disease/risks${query ? '?' + query : ''}`);
},

getDiseaseAlerts(unitId = null) {
    const params = new URLSearchParams();
    if (unitId) params.append('unit_id', unitId);
    const query = params.toString();
    return get(`/api/ml/predictions/disease/alerts${query ? '?' + query : ''}`);
},

predictDiseaseRisk(unitId, plantType, growthStage, currentConditions = null) {
    return post('/api/ml/predictions/disease/risk', {
        unit_id: unitId,
        plant_type: plantType,
        growth_stage: growthStage,
        current_conditions: currentConditions
    });
},

// Growth Stage Predictions
getGrowthConditions(stage, daysInStage = null) {
    const params = new URLSearchParams();
    if (daysInStage) params.append('days_in_stage', daysInStage);
    const query = params.toString();
    return get(`/api/ml/predictions/growth/${stage}${query ? '?' + query : ''}`);
},

getAllGrowthStages() {
    return get('/api/ml/predictions/growth/stages/all');
},

getGrowthStatus() {
    return get('/api/ml/predictions/growth/status');
},

analyzeGrowthTransition(unitId, fromStage, toStage) {
    return post('/api/ml/predictions/growth/transition-analysis', {
        unit_id: unitId,
        from_stage: fromStage,
        to_stage: toStage
    });
},

// Climate Optimization
getClimateConditions(growthStage) {
    return get(`/api/ml/predictions/climate/${growthStage}`);
},

getClimateRecommendations(unitId) {
    return get(`/api/ml/predictions/climate/${unitId}/recommendations`);
},

getWateringIssues(unitId) {
    return get(`/api/ml/predictions/climate/${unitId}/watering-issues`);
},

// Health Monitoring
getHealthRecommendations(unitId, plantType = null, growthStage = null) {
    const params = new URLSearchParams();
    if (plantType) params.append('plant_type', plantType);
    if (growthStage) params.append('growth_stage', growthStage);
    const query = params.toString();
    return get(`/api/ml/predictions/health/${unitId}/recommendations${query ? '?' + query : ''}`);
},

recordHealthObservation(observation) {
    return post('/api/ml/predictions/health/observation', observation);
},

// ==================== Model Management ====================

getModels() {
    return get('/api/ml/models/');
},

getModelVersions(modelName) {
    return get(`/api/ml/models/${modelName}/versions`);
},

promoteModel(modelName, version) {
    return post(`/api/ml/models/${modelName}/promote`, { version });
},

getModelMetadata(modelName) {
    return get(`/api/ml/models/${modelName}/metadata`);
},

getModelsStatus() {
    return get('/api/ml/models/status');
},

// ==================== Analytics ====================

getDiseaseStatistics(days = 90, unitId = null) {
    const params = new URLSearchParams({ days });
    if (unitId) params.append('unit_id', unitId);
    const query = params.toString();
    return get(`/api/ml/analytics/disease/statistics?${query}`);
},

getActuatorEnergyDashboard(actuatorId, days = 7) {
    return get(`/api/ml/analytics/energy/actuator/${actuatorId}/dashboard?days=${days}`);
},

predictActuatorFailure(actuatorId) {
    return get(`/api/ml/analytics/energy/actuator/${actuatorId}/predict-failure`);
},

// ==================== Monitoring ====================

getModelDrift(modelName) {
    return get(`/api/ml/monitoring/drift/${modelName}`);
},

getMonitoringInsights(unitId) {
    return get(`/api/ml/monitoring/insights/${unitId}`);
},

getCriticalInsights() {
    return get('/api/ml/monitoring/insights/critical');
},

// ==================== Retraining ====================

getRetrainingJobs() {
    return get('/api/ml/retraining/jobs');
},

scheduleRetraining(modelName, config) {
    return post('/api/ml/retraining/jobs', { model_name: modelName, ...config });
},

cancelRetraining(jobId) {
    return del(`/api/ml/retraining/jobs/${jobId}`);
},

triggerRetraining(modelName, force = false) {
    return post('/api/ml/retraining/trigger', { model_name: modelName, force });
},

getRetrainingStatus() {
    return get('/api/ml/retraining/status');
}
```

---

## Breaking Changes

### Response Structure Changes

Most endpoints maintain the same response structure, but verify:

1. **Disease Risks Response** - Should be identical
2. **Growth Predictions** - Check `conditions` vs `prediction` field names
3. **Model Status** - Verify enum value formats

### Deprecation Strategy

Since we're doing a **clean cut** (no backward compatibility):

1. **Remove legacy endpoint registration** from `app/__init__.py`:
   - Comment out or remove old blueprint registrations
   - Keep only new `ml_ai` blueprints

2. **Update all frontend code simultaneously**
3. **Deploy both backend and frontend together**

---

## Rollback Plan

If critical issues arise after deployment:

1. **Backend:** Restore legacy blueprint registrations in `app/__init__.py`
2. **Frontend:** Revert `static/js/api.js` changes
3. **Cache:** Clear browser cache to ensure old JS loads

**Estimated rollback time:** < 5 minutes

---

## Testing Checklist

### Pre-Deployment
- [ ] All API helper methods updated in `api.js`
- [ ] Dashboard widgets tested locally
- [ ] Console shows no 404 errors
- [ ] Disease risk cards display correctly
- [ ] Growth stage predictions work
- [ ] Analytics charts load
- [ ] Model management UI functional

### Post-Deployment
- [ ] Monitor error logs for 404s
- [ ] Check browser console on production
- [ ] Verify all dashboard sections load
- [ ] Test on mobile/tablet views
- [ ] Verify WebSocket events still work

---

## Timeline

**Estimated Duration:** 2-4 hours

1. **Phase 1** (API Client): 30-45 min
2. **Phase 2** (Dashboard JS): 30-45 min
3. **Phase 3** (Templates): 15-30 min
4. **Phase 4** (WebSocket): 15 min
5. **Phase 5** (Testing): 45-60 min

---

## Next Steps

1. ✅ **Plan created** (this document)
2. ⏳ **Search for all current API usage**
3. ⏳ **Update `static/js/api.js`**
4. ⏳ **Update `static/js/dashboard.js`**
5. ⏳ **Update templates**
6. ⏳ **Test locally**
7. ⏳ **Deploy**
8. ⏳ **Monitor**

---

## Notes

- Mobile app requires **no changes** - only handles device control
- WebSocket namespace `/ml` remains unchanged
- Hardware control endpoints (`/api/climate/*`) stay separate (not AI predictions)
- Consider adding API version header for future migrations
