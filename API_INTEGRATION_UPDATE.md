# System Health Dashboard - API Integration Update

**Date:** December 12, 2025  
**Status:** ✅ Complete

## Summary

Refactored the System Health Dashboard to use the centralized `api.js` module instead of direct `fetch()` calls, and fixed routing errors.

---

## Changes Made

### 1. Fixed Template Routing Error
**File:** `templates/system_health.html`

**Problem:** Reference to non-existent `ui.alerts` route causing 500 error
```python
werkzeug.routing.exceptions.BuildError: Could not build url for endpoint 'ui.alerts'
```

**Solution:** Changed to use settings page with anchor
```javascript
// BEFORE
window.location.href = "{{ url_for('ui.alerts') }}";

// AFTER
window.location.href = "{{ url_for('ui.settings') }}#alerts";
```

### 2. Enhanced api.js with Health & System APIs
**File:** `static/js/api.js`

**Added to HealthAPI:**
```javascript
getDetailed()          // /api/health/detailed
getInfrastructure()    // /api/health/infrastructure  
getStorage()           // /api/health/storage
getApiMetrics()        // /api/health/api-metrics
getDatabase()          // /api/health/database
```

**Added SystemAPI (new):**
```javascript
getAlerts()                      // /api/system/alerts
getActivities(limit)             // /api/system/activities
getUptime()                      // /api/system/uptime
acknowledgeAlert(alertId)        // POST /api/system/alerts/:id/acknowledge
resolveAlert(alertId)            // POST /api/system/alerts/:id/resolve
```

### 3. Refactored system_health.js
**File:** `static/js/system_health.js`

**Changed from direct fetch() to api.js:**

| Method | Old Approach | New Approach |
|--------|-------------|-------------|
| loadOverviewData() | `fetch('/api/insights/dashboard/overview')` | `window.InsightsAPI.getDashboardOverview()` |
| loadHealthScore() | `fetch('/api/health/detailed')` | `window.HealthAPI.getDetailed()` |
| loadHealthDetails() | `fetch('/api/health/infrastructure')` | `window.HealthAPI.getInfrastructure()` |
| loadHealthDetails() | `fetch('/api/health/api-metrics')` | `window.HealthAPI.getApiMetrics()` |
| loadUnitsStatus() | `fetch('/api/health/units')` | `window.HealthAPI.getUnitsHealth()` |
| loadDevicesSummary() | `fetch('/api/health/system')` | `window.HealthAPI.getSystemHealth()` |
| loadPerformanceData() | `fetch('/api/health/api-metrics')` | `window.HealthAPI.getApiMetrics()` |
| loadPerformanceData() | `fetch('/api/health/storage')` | `window.HealthAPI.getStorage()` |
| loadRecentActivity() | `fetch('/api/insights/dashboard/overview')` | `window.InsightsAPI.getDashboardOverview()` |
| loadAlerts() | `fetch('/api/insights/dashboard/overview')` | `window.InsightsAPI.getDashboardOverview()` |

**Total:** 10 fetch() calls replaced with api.js methods

---

## Benefits

### 1. **Centralized API Management**
- All API calls go through `api.js` module
- Easier to update endpoints globally
- Consistent error handling
- Type safety via JSDoc comments

### 2. **Better Code Maintainability**
- Single source of truth for API endpoints
- Reduced code duplication
- Easier debugging (all API calls in one place)

### 3. **Improved Error Handling**
- Standardized error responses
- Automatic success/data unwrapping
- Consistent error logging

### 4. **Future-Proof**
- Easy to add authentication headers
- Simple to add retry logic
- Can implement request caching
- Easier to mock for testing

---

## Testing

✅ **Template Rendering:** No routing errors  
✅ **Page Load:** Renders successfully (6,272 bytes)  
✅ **API Integration:** All calls use api.js module  
✅ **Error Handling:** Proper error messages in console  

---

## Usage Notes

### For Developers

When adding new API calls to the dashboard:

**DON'T DO THIS:**
```javascript
const response = await fetch('/api/new-endpoint');
const data = await response.json();
```

**DO THIS:**
```javascript
// 1. Add to api.js first
const HealthAPI = {
    // ... existing methods
    getNewData() {
        return get('/api/new-endpoint');
    }
};

// 2. Use in system_health.js
const data = await window.HealthAPI.getNewData();
```

### API Module Access

Since `api.js` is loaded globally via `<script>` tag, access APIs via `window`:

```javascript
window.HealthAPI.getDetailed()
window.InsightsAPI.getDashboardOverview()
window.SystemAPI.getAlerts()
window.GrowthAPI.listUnits()
window.DevicesAPI.listSensors()
// etc...
```

---

## Files Modified

| File | Lines Changed | Purpose |
|------|--------------|---------|
| `static/js/api.js` | +67 | Added health & system APIs |
| `static/js/system_health.js` | ~30 | Replaced fetch with api.js |
| `templates/system_health.html` | 1 | Fixed alert route |

---

## Next Steps (Optional Enhancements)

1. **Add Type Definitions:** Create TypeScript definitions for api.js
2. **Request Caching:** Implement caching for frequently accessed data
3. **Offline Support:** Add service worker for offline functionality
4. **Request Batching:** Batch multiple API calls into single request
5. **WebSocket Integration:** Replace polling with real-time updates

---

## Related Documentation

- [api.js Documentation](static/js/api.js) - Full API reference
- [System Health Dashboard](static/js/system_health.js) - Dashboard implementation
- [Phase 2 Complete](PHASE2_COMPLETE.md) - UI consolidation summary
- [Project Complete](PROJECT_COMPLETE.md) - Full project summary
