# Plants Hub Integration Guide

## Quick Start

### 1. Import API.js in your HTML template

```html
<!-- Make sure api.js is loaded BEFORE plants.js -->
<script src="{{ url_for('static', filename='js/api.js') }}"></script>
<script type="module" src="{{ url_for('static', filename='js/plants.js') }}"></script>
```

### 2. Initialize the Plants Hub

```javascript
// In your plants.html or main.js
import { PlantsHub } from './plants.js';

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.plantsHub = new PlantsHub();
});
```

### 3. Add Required HTML Elements

See `PLANTS_HUB_HTML_COMPONENTS.html` for complete HTML structure and CSS.

Key elements needed:
- `#ai-status` - For AI retraining status
- `#growth-stage-recommendations` - For growth stage cards
- `#transition-alert` - For stage transition alerts
- `#plant-details-modal` - Modal for plant details
- `#plant-details-content` - Content area within modal

---

## Common Issues & Solutions

### Issue 1: "API is not defined"
**Cause**: `api.js` not loaded before `plants.js`

**Solution**:
```html
<!-- Correct order -->
<script src="{{ url_for('static', filename='js/api.js') }}"></script>
<script type="module" src="{{ url_for('static', filename='js/plants.js') }}"></script>
```

### Issue 2: Growth stage recommendations not showing
**Cause**: Missing HTML container or plant data incomplete

**Solution**:
```html
<!-- Add this to your plant details modal -->
<div id="growth-stage-recommendations"></div>
<div id="transition-alert"></div>
```

**Verify plant data includes**:
```javascript
{
    plant_id: 1,
    name: "Tomato",
    current_stage: "vegetative",  // Required
    days_in_stage: 14,             // Required
    plant_type: "tomato"
}
```

### Issue 3: AI status not displaying
**Cause**: Backend service not running or endpoint not registered

**Solution**:
1. Verify service is running:
```python
from app import create_app
app = create_app()
container = app.config['CONTAINER']
print(container.automated_retraining.get_status())
```

2. Check blueprint is registered in `app/__init__.py`:
```python
from app.blueprints.api.retraining import retraining_api
app.register_blueprint(retraining_api)
```

### Issue 4: "Failed to fetch" errors in console
**Cause**: API endpoints not matching or CORS issues

**Solution**:
1. Check endpoint URLs in browser DevTools Network tab
2. Verify blueprint URL prefixes:
   - Growth Stages: `/api/growth-stages`
   - Retraining: `/api/retraining`

3. Test endpoints directly:
```bash
curl http://localhost:5000/api/growth-stages/status
curl http://localhost:5000/api/retraining/status
```

### Issue 5: Plant details modal not appearing
**Cause**: Modal HTML not added or onclick handler incorrect

**Solution**:
```html
<!-- Make sure modal exists -->
<div id="plant-details-modal" class="modal" style="display: none;">
    <div class="modal-content">
        <div class="modal-header">
            <h2>Plant Details</h2>
            <button class="close-btn" onclick="window.plantsHub.hideModal('plant-details-modal')">×</button>
        </div>
        <div class="modal-body">
            <div id="plant-details-content"></div>
        </div>
    </div>
</div>
```

```javascript
// In plant list item
onclick="window.plantsHub.showPlantDetails(${plant.plant_id})"
```

---

## Testing the Integration

### Test 1: Verify API Module Loaded
```javascript
// Open browser console
console.log(API);
console.log(API.GrowthStages);
console.log(API.Retraining);
// Should all return objects, not undefined
```

### Test 2: Test Growth Stages API
```javascript
// Get all stages
const stages = await API.GrowthStages.getAllStageConditions();
console.log(stages);

// Get specific stage
const veg = await API.GrowthStages.predictStageConditions('vegetative');
console.log(veg);
```

### Test 3: Test Retraining API
```javascript
// Get status
const status = await API.Retraining.getStatus();
console.log(status);

// Get jobs
const jobs = await API.Retraining.getJobs();
console.log(jobs);
```

### Test 4: Test Plant Details
```javascript
// Assuming you have plant with ID 1
window.plantsHub.showPlantDetails(1);
// Should open modal with plant details
```

### Test 5: Verify Data Loading
```javascript
// Check if data loaded correctly
console.log(window.plantsHub.data);
// Should show: plantsHealth, diseaseRisk, harvests, journal, retrainingStatus
```

---

## Advanced Usage

### Custom Growth Stage Display

```javascript
// Get current plant
const plant = {
    plant_id: 1,
    name: "My Tomato",
    current_stage: "flowering",
    days_in_stage: 7
};

// Get stage data
const stageData = await API.GrowthStages.predictStageConditions(
    plant.current_stage,
    plant.days_in_stage
);

// Custom display
console.log(`Optimal Temperature: ${stageData.conditions.temperature_min}°C - ${stageData.conditions.temperature_max}°C`);
console.log(`Recommendation: ${stageData.recommendation}`);
```

### Compare Current Conditions

```javascript
// Get current sensor readings
const currentConditions = {
    temperature: 24,
    humidity: 65,
    light_hours: 16,
    light_intensity: 600,
    co2_ppm: 400
};

// Compare with optimal
const comparison = await API.GrowthStages.compareConditions(
    'vegetative',
    currentConditions
);

console.log(comparison);
// Shows which conditions are good/bad and recommendations
```

### Monitor Stage Transition

```javascript
// Check if ready for next stage
const transition = await API.GrowthStages.analyzeTransition(
    'vegetative',  // current stage
    21,            // days in stage
    currentConditions
);

if (transition.transition.ready) {
    alert(`Ready to transition to ${transition.transition.next_stage}!`);
}
```

### Create Automated Retraining Job

```javascript
// Create a daily retraining job for climate model
const job = await API.Retraining.createJob({
    model_type: 'climate',
    schedule_type: 'daily',
    schedule_time: '02:00',
    min_samples: 100,
    enabled: true
});

console.log(`Job created: ${job.job_id}`);
```

### Manual Model Retraining

```javascript
// Trigger immediate retraining
const event = await API.Retraining.triggerRetraining('disease');
console.log(`Retraining triggered: ${event.event_id}`);

// Check recent events
const events = await API.Retraining.getEvents('disease', 10);
console.log('Recent retraining events:', events);
```

---

## Performance Tips

### 1. Use Caching
The data service already implements caching, but you can control it:

```javascript
// Clear cache to force refresh
window.plantsHub.ui.dataService.clearCache();
await window.plantsHub.loadData();
```

### 2. Lazy Load Growth Recommendations
Only load when plant details are viewed:

```javascript
// Growth recommendations are loaded on-demand when showPlantDetails() is called
// Not loaded for every plant in the list
```

### 3. Batch API Calls
```javascript
// Good: Load all data in parallel
const [stages, status, jobs] = await Promise.all([
    API.GrowthStages.getAllStageConditions(),
    API.Retraining.getStatus(),
    API.Retraining.getJobs()
]);

// Bad: Sequential loading
const stages = await API.GrowthStages.getAllStageConditions();
const status = await API.Retraining.getStatus();
const jobs = await API.Retraining.getJobs();
```

---

## Error Handling Best Practices

### Graceful Degradation

```javascript
async loadRetrainingStatus() {
    try {
        const result = await API.Retraining.getStatus();
        return result.data || result;
    } catch (error) {
        console.warn('Retraining service unavailable:', error);
        return null;  // Return null instead of failing
    }
}
```

### User-Friendly Error Messages

```javascript
try {
    const result = await API.Plant.addPlant(unitId, plantData);
    this.showSuccess('Plant added successfully');
} catch (error) {
    console.error('Error adding plant:', error);
    
    // Show user-friendly message
    if (error.message.includes('network')) {
        this.showError('Network error. Please check your connection.');
    } else if (error.message.includes('validation')) {
        this.showError('Invalid plant data. Please check your inputs.');
    } else {
        this.showError('Failed to add plant. Please try again.');
    }
}
```

---

## Debugging

### Enable Verbose Logging

```javascript
// Add to plants.js constructor
constructor() {
    this.debug = true;  // Enable debug mode
    // ...
}

// Add logging to methods
async loadData() {
    if (this.debug) console.log('Loading plants data...');
    const data = await this.ui.dataService.loadAllData();
    if (this.debug) console.log('Data loaded:', data);
    // ...
}
```

### Monitor API Calls

```javascript
// Override apiRequest to log all calls
const originalApiRequest = window.apiRequest;
window.apiRequest = async function(url, options) {
    console.log(`API Call: ${options?.method || 'GET'} ${url}`);
    const result = await originalApiRequest(url, options);
    console.log(`API Response:`, result);
    return result;
};
```

### Check Service Availability

```python
# In Flask shell or debug script
from app import create_app

app = create_app()
container = app.config['CONTAINER']

# Check growth predictor
print("Growth Predictor:", container.growth_predictor.get_status())

# Check retraining service
print("Retraining:", container.automated_retraining.get_status())

# Check model registry
print("Models:", container.model_registry.list_models())
```

---

## Production Checklist

- [ ] API.js loaded before plants.js
- [ ] All required HTML elements present
- [ ] CSS styles applied
- [ ] Modal functionality tested
- [ ] Growth stage recommendations display correctly
- [ ] Transition alerts working
- [ ] AI status card shows data
- [ ] Error handling implemented
- [ ] Loading states displayed
- [ ] Mobile responsive design verified
- [ ] Browser console shows no errors
- [ ] All API endpoints return 200
- [ ] Caching works correctly
- [ ] Auto-refresh functioning

---

## Support

If you encounter issues:

1. Check browser console for errors
2. Verify network requests in DevTools
3. Test API endpoints directly with curl
4. Check backend logs for errors
5. Verify all services initialized in container
6. Ensure blueprints registered correctly
7. Check HTML elements exist with correct IDs
8. Verify plant data has required fields

For more help, see:
- `PLANTS_HUB_UPDATES.md` - Complete changelog
- `PLANTS_HUB_HTML_COMPONENTS.html` - HTML/CSS reference
- `static/js/api.js` - API documentation
- `static/js/plants.js` - Implementation details
