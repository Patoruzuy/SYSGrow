# Plants Hub Updates - December 14, 2025

## Summary
Updated the Plants Hub dashboard to integrate new AI services (Growth Stages and Automated Retraining) and migrated from direct `fetch` calls to the centralized `API.js` module for better maintainability.

---

## Changes Made

### 1. **API.js Enhancements**

#### Added Growth Stages API Module (`GrowthStagesAPI`)
- `predictStageConditions(stage, daysInStage)` - Get optimal conditions for a growth stage
- `getAllStageConditions()` - Get all stage conditions at once
- `compareConditions(stage, actualConditions)` - Compare actual vs optimal conditions
- `analyzeTransition(currentStage, daysInStage, actualConditions)` - Check readiness for stage transition
- `getStatus()` - Get growth predictor status

#### Added Retraining API Module (`RetrainingAPI`)
- `getJobs()` - List all retraining jobs
- `createJob(jobData)` - Create a new retraining schedule
- `deleteJob(jobId)` - Remove a job
- `enableJob(jobId, enabled)` - Enable/disable a job
- `triggerRetraining(modelType)` - Manually trigger retraining
- `getEvents(modelType, limit)` - Get retraining history
- `startScheduler()` - Start background scheduler
- `stopScheduler()` - Stop scheduler
- `getStatus()` - Get service status

#### Updated Exports
- Added `GrowthStagesAPI` and `RetrainingAPI` to global exports
- Available as `API.GrowthStages` and `API.Retraining`
- Also available as `window.GrowthStagesAPI` and `window.RetrainingAPI`

---

### 2. **Plants.js Refactoring**

#### Migrated to API.js (No More Direct Fetch)
Replaced direct `fetch()` calls with `API` module methods:

**Before:**
```javascript
const response = await fetch('/api/plants/health');
const json = await response.json();
```

**After:**
```javascript
const result = await API.Health.getPlantHealth();
```

#### Updated Methods:
- `loadPlantsHealth()` → Uses `API.Health.getPlantHealth()`
- `loadPlantsGuide()` → Uses `API.Agriculture.getAvailablePlants()`
- `loadDiseaseRisk()` → Uses `API.Health.getDiseaseRisks()`
- `loadHarvests()` → Uses `API.Plant.getHarvests()`
- `loadJournal()` → Uses `API.Health.getJournalEntries()`
- `handleAddPlant()` → Uses `API.Plant.addPlant()`
- `handleAddObservation()` → Uses `API.Plant.recordHealthObservation()`

#### New AI Features Added:

##### 1. **Growth Stage Recommendations**
```javascript
renderGrowthStageRecommendations(plant)
```
- Displays optimal environmental conditions for current growth stage
- Shows temperature, humidity, light hours, and light intensity ranges
- Provides AI-powered recommendations
- Shows confidence scores

##### 2. **Stage Transition Analysis**
```javascript
checkStageTransition(plant)
```
- Analyzes if plant is ready for next growth stage
- Shows readiness score
- Displays alerts when ready or almost ready
- Provides guidance on transition timing

##### 3. **AI Model Status Display**
```javascript
renderAIStatus(retrainingStatus)
```
- Shows automated retraining scheduler status
- Displays active jobs count
- Shows recent failure count
- Tracks total retraining events

##### 4. **Enhanced Plant Details**
```javascript
showPlantDetails(plantId)
```
- Now displays comprehensive plant information
- Shows growth stage recommendations automatically
- Checks and displays transition readiness
- Provides actionable insights

#### New Data Loading:
```javascript
loadRetrainingStatus()
```
- Loads AI retraining service status
- Integrated into main data loading pipeline
- Non-blocking (fails gracefully if unavailable)

---

### 3. **Error Handling Improvements**

#### Before:
```javascript
if (!response.ok) throw new Error('Failed to fetch');
```

#### After:
```javascript
try {
    const result = await API.Health.getPlantHealth();
    return result.data || result;
} catch (error) {
    console.warn('Failed to load:', error);
    return null;
}
```

Benefits:
- Better error messages with context
- Graceful degradation for optional features
- Consistent error handling across the app

---

## New UI Components

### Growth Stage Card
```html
<div class="growth-stage-card">
    <h4><i class="fas fa-seedling"></i> Optimal Conditions for [stage]</h4>
    <div class="conditions-grid">
        <!-- Temperature, Humidity, Light Hours, Light Intensity -->
    </div>
    <div class="recommendation-box">
        <!-- AI-powered recommendations -->
    </div>
    <div class="stage-info">
        <!-- Days in stage, confidence score -->
    </div>
</div>
```

### Transition Alert
```html
<div class="alert alert-success">
    <i class="fas fa-check-circle"></i>
    <div>
        <strong>Ready for Next Stage!</strong>
        <p>Your plant is ready to transition to [next_stage]</p>
        <p class="text-muted">Readiness: [score]%</p>
    </div>
</div>
```

### AI Status Card
```html
<div class="ai-status-card">
    <h4><i class="fas fa-robot"></i> AI Model Status</h4>
    <div class="ai-stats-grid">
        <!-- Scheduler status, job counts, failure counts -->
    </div>
</div>
```

---

## Usage Examples

### Getting Growth Stage Conditions
```javascript
// Get conditions for a specific stage
const data = await API.GrowthStages.predictStageConditions('flowering', 7);
console.log(data.conditions); // Temperature, humidity, light, etc.
console.log(data.recommendation); // AI recommendation

// Get all stages at once
const allStages = await API.GrowthStages.getAllStageConditions();
```

### Comparing Actual vs Optimal Conditions
```javascript
const actual = {
    temperature: 24,
    humidity: 65,
    light_hours: 16,
    light_intensity: 600
};

const comparison = await API.GrowthStages.compareConditions('vegetative', actual);
console.log(comparison); // Shows deviations and recommendations
```

### Checking Stage Transition Readiness
```javascript
const analysis = await API.GrowthStages.analyzeTransition(
    'vegetative',  // current stage
    21,            // days in stage
    actualConditions
);

if (analysis.transition.ready) {
    console.log('Ready for:', analysis.transition.next_stage);
}
```

### Managing Retraining Jobs
```javascript
// Create a daily retraining job
const job = await API.Retraining.createJob({
    model_type: 'climate',
    schedule_type: 'daily',
    schedule_time: '02:00',
    enabled: true
});

// Get all jobs
const jobs = await API.Retraining.getJobs();

// Trigger manual retraining
const event = await API.Retraining.triggerRetraining('disease');

// Get retraining history
const events = await API.Retraining.getEvents('climate', 50);
```

---

## Benefits

### 1. **Maintainability**
- Centralized API calls in `API.js`
- Single source of truth for endpoints
- Easy to update endpoints globally

### 2. **Type Safety**
- JSDoc comments provide IDE autocomplete
- Parameter validation in API layer
- Clear return type expectations

### 3. **Error Handling**
- Consistent error handling patterns
- Graceful degradation for optional features
- Better error messages for debugging

### 4. **Performance**
- Caching layer still works
- Parallel requests where appropriate
- Non-blocking AI features

### 5. **User Experience**
- Growth stage guidance for better plant care
- Proactive transition alerts
- AI model transparency

---

## Testing Checklist

- [x] App creates successfully
- [ ] Plants Hub loads without errors
- [ ] Plant health data displays correctly
- [ ] Disease risks show up
- [ ] Harvests and journal render
- [ ] Plant details modal works
- [ ] Growth stage recommendations display
- [ ] Transition analysis shows alerts
- [ ] AI status card appears
- [ ] Add plant form uses API.js
- [ ] Add observation form uses API.js
- [ ] Retraining status loads

---

## Next Steps

### Recommended Enhancements:
1. **Add CSS styling** for new components (growth-stage-card, ai-status-card, transition-alert)
2. **Create modals** for plant details and guide details
3. **Implement sensor data fetching** for real-time condition comparison
4. **Add retraining management UI** for creating/managing jobs
5. **Create growth stage transition workflow** with user confirmation
6. **Add charts** for growth stage progress over time

### Future Features:
- Growth stage timeline visualization
- Historical condition comparison
- Automated stage transitions based on AI recommendations
- Mobile-responsive growth stage cards
- Push notifications for stage transitions

---

## API Endpoints Reference

### Growth Stages API
- `GET /api/growth-stages/predict/<stage>?days_in_stage=<n>`
- `GET /api/growth-stages/all`
- `POST /api/growth-stages/compare`
- `POST /api/growth-stages/transition-analysis`
- `GET /api/growth-stages/status`

### Retraining API
- `GET /api/retraining/jobs`
- `POST /api/retraining/jobs`
- `DELETE /api/retraining/jobs/<id>`
- `POST /api/retraining/jobs/<id>/enable`
- `POST /api/retraining/trigger`
- `GET /api/retraining/events`
- `POST /api/retraining/scheduler/start`
- `POST /api/retraining/scheduler/stop`
- `GET /api/retraining/status`

---

## Files Modified

1. **static/js/api.js**
   - Added `GrowthStagesAPI` module (170 lines)
   - Added `RetrainingAPI` module (160 lines)
   - Updated exports

2. **static/js/plants.js**
   - Migrated 7 methods to use API.js
   - Added `renderGrowthStageRecommendations()`
   - Added `checkStageTransition()`
   - Added `renderAIStatus()`
   - Enhanced `showPlantDetails()`
   - Added `loadRetrainingStatus()`
   - Updated `loadAllData()` to include AI status

---

## Notes

- All changes are backward compatible
- Old fetch-based code removed for consistency
- Error handling improved throughout
- AI features fail gracefully if services unavailable
- Caching mechanism preserved and enhanced
