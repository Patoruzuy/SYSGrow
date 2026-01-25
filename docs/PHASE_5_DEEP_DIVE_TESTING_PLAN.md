# Phase 5 Deep Dive Testing Plan
# SYSGrow Smart Agriculture - ML Real-Time Infrastructure

**Date:** November 22, 2025  
**Phase:** 5 - WebSocket Integration & Advanced Visualizations  
**Status:** Testing In Progress  
**Tester:** [Your Name]

---

## Table of Contents

1. [Testing Overview](#testing-overview)
2. [Testing Environment Setup](#testing-environment-setup)
3. [Test Execution Phases](#test-execution-phases)
4. [Detailed Test Cases](#detailed-test-cases)
5. [Performance Benchmarks](#performance-benchmarks)
6. [Browser Compatibility Matrix](#browser-compatibility-matrix)
7. [Load Testing Procedures](#load-testing-procedures)
8. [Error Scenarios & Edge Cases](#error-scenarios--edge-cases)
9. [Regression Testing](#regression-testing)
10. [Test Results Documentation](#test-results-documentation)
11. [Bug Reporting Template](#bug-reporting-template)
12. [Sign-Off Criteria](#sign-off-criteria)

---

## Testing Overview

### Scope

This deep dive testing plan covers comprehensive validation of Phase 5 implementations:

- **WebSocket Real-Time Communication** - Flask-SocketIO on `/ml` namespace
- **Advanced Visualizations** - Chart.js model comparison and feature importance
- **Training Progress Tracking** - Real-time progress bars with metrics
- **Drift Monitoring** - Live drift detection updates
- **Connection Management** - Auto-reconnection and polling fallback
- **Multi-Client Broadcasting** - Concurrent connection handling
- **API Integration** - WebSocket broadcasts from training endpoints

### Testing Objectives

1. **Functional Correctness** - Verify all features work as designed
2. **Performance Validation** - Meet latency and throughput targets
3. **Reliability Testing** - Ensure stable operation under various conditions
4. **Usability Testing** - Confirm intuitive user experience
5. **Security Testing** - Validate secure WebSocket connections
6. **Compatibility Testing** - Cross-browser and cross-device support
7. **Regression Prevention** - Ensure existing features still work

### Testing Timeline

| Phase | Duration | Description |
|-------|----------|-------------|
| **Phase 1: Setup** | 30 min | Environment preparation, tool setup |
| **Phase 2: Functional** | 2-3 hours | All feature testing (50+ test cases) |
| **Phase 3: Performance** | 1-2 hours | Latency, throughput, load testing |
| **Phase 4: Compatibility** | 1 hour | Cross-browser testing |
| **Phase 5: Edge Cases** | 1-2 hours | Error handling, failure scenarios |
| **Phase 6: Regression** | 1 hour | Verify existing features |
| **Phase 7: Documentation** | 30 min | Results compilation, bug reports |
| **Total** | **7-10 hours** | Complete deep dive testing |

### Success Criteria

- ✅ **100% of critical test cases pass** (no blockers)
- ✅ **95%+ of all test cases pass** (max 5% acceptable failures in non-critical areas)
- ✅ **Performance benchmarks met** (see Performance Benchmarks section)
- ✅ **No regression in existing features**
- ✅ **Cross-browser compatibility verified** (Chrome, Firefox, Safari)
- ✅ **Zero console errors in production mode**

---

## Testing Environment Setup

### Prerequisites

#### Server Requirements

- ✅ Flask development server running
- ✅ Flask-SocketIO installed and configured
- ✅ ML models available (climate_predictor, anomaly_detector, resource_optimizer)
- ✅ SQLite database with sample data

**Start Server:**
```powershell
cd E:\Work\SYSGrow\backend
$env:FLASK_DEBUG='False'
python start_dev.py
```

**Verify Server:**
- URL: http://localhost:5000
- Check console for: "✅ ML WebSocket handlers registered at /ml namespace"
- Check for: "Socket.IO server started"

#### Browser Setup

**Primary Testing Browser: Chrome (Latest)**
- Install Socket.IO Inspector extension (optional): https://chrome.google.com/webstore
- Enable DevTools: F12
- Tabs needed: Console, Network, Performance

**Secondary Browsers:**
- Firefox (Latest)
- Safari (macOS/iOS only)
- Edge (Chromium-based)

**DevTools Configuration:**
```javascript
// Enable verbose Socket.IO logging (paste in console)
localStorage.debug = 'socket.io-client:*';
// Reload page to see debug logs
```

#### Testing Tools

1. **Browser DevTools**
   - Console: Error monitoring, manual commands
   - Network: WebSocket frame inspection, API monitoring
   - Performance: Profiling, timeline analysis

2. **Socket.IO Client** (for manual testing)
   ```javascript
   // Connect directly from console
   const testSocket = io('/ml', {
       transports: ['websocket', 'polling']
   });
   
   testSocket.on('connect', () => {
       console.log('✅ Test socket connected');
   });
   ```

3. **Performance Measurement Script**
   ```javascript
   // Paste in console to measure operations
   window.perfMonitor = {
       mark: (name) => performance.mark(name),
       measure: (name, start, end) => {
           performance.measure(name, start, end);
           const measures = performance.getEntriesByName(name);
           const latest = measures[measures.length - 1];
           console.log(`⏱️ ${name}: ${latest.duration.toFixed(2)}ms`);
           return latest.duration;
       }
   };
   ```

4. **Multi-Tab Testing Setup**
   - Tab 1: Main dashboard (http://localhost:5000/ml-dashboard)
   - Tab 2: Secondary dashboard (same URL)
   - Tab 3: API testing (http://localhost:5000/api/ml/models)
   - Tab 4: Backend logs (terminal window)

### Test Data Preparation

#### Create Test Models (if needed)

```python
# In Python console or script
from ai.climate_predictor import ClimatePredictor
from ai.anomaly_detector import AnomalyDetector

# Train models if not present
climate_model = ClimatePredictor()
climate_model.train()

anomaly_model = AnomalyDetector()
anomaly_model.train()
```

#### Verify Models Exist

```javascript
// In browser console on dashboard
fetch('/api/ml/models')
    .then(r => r.json())
    .then(data => {
        console.log('📦 Available models:', data.models.map(m => m.model_name));
    });
```

**Expected Output:**
```
📦 Available models: ["climate_predictor", "anomaly_detector", "resource_optimizer"]
```

### Environment Variables

```powershell
# Recommended settings for testing
$env:FLASK_DEBUG='False'           # Production mode for realistic testing
$env:SYSGROW_ENABLE_MQTT='False'   # Disable MQTT if not available
$env:SYSGROW_LOG_LEVEL='INFO'      # Normal logging
```

---

## Test Execution Phases

### Phase 1: Quick Smoke Test (5 minutes)

**Purpose:** Verify basic functionality before deep dive

1. ✅ Dashboard loads without errors
2. ✅ WebSocket connects (green dot visible)
3. ✅ Models list displays
4. ✅ "Compare Models" button exists
5. ✅ "Features" button exists on model cards

**Quick Validation Command:**
```javascript
// Paste in console
console.log('🔍 Quick Smoke Test');
console.log('WebSocket:', window.mlDashboard.socket?.connected ? '✅' : '❌');
console.log('Models:', document.querySelectorAll('.model-item').length);
console.log('Compare Button:', document.getElementById('compare-models-btn') ? '✅' : '❌');
```

**Expected Output:**
```
🔍 Quick Smoke Test
WebSocket: ✅
Models: 3
Compare Button: ✅
```

### Phase 2: Functional Testing (2-3 hours)

Execute all 50+ test cases in [Detailed Test Cases](#detailed-test-cases) section.

### Phase 3: Performance Testing (1-2 hours)

Execute performance benchmarks in [Performance Benchmarks](#performance-benchmarks) section.

### Phase 4: Browser Compatibility (1 hour)

Test on Chrome, Firefox, Safari using [Browser Compatibility Matrix](#browser-compatibility-matrix).

### Phase 5: Load Testing (1-2 hours)

Simulate concurrent users with [Load Testing Procedures](#load-testing-procedures).

### Phase 6: Edge Cases (1-2 hours)

Test error scenarios in [Error Scenarios & Edge Cases](#error-scenarios--edge-cases).

### Phase 7: Regression Testing (1 hour)

Verify existing features with [Regression Testing](#regression-testing).

---

## Detailed Test Cases

### Category 1: WebSocket Connection Management

#### TC-WS-001: Initial Connection on Page Load
**Priority:** CRITICAL  
**Preconditions:** Server running, dashboard not yet opened  

**Steps:**
1. Open browser DevTools (F12)
2. Navigate to http://localhost:5000/ml-dashboard
3. Wait 2 seconds
4. Check Network tab → WS filter → Look for `/socket.io/?EIO=...`

**Expected Results:**
- WebSocket connection established (Status 101 Switching Protocols)
- Green pulsing dot visible in top-right corner
- Console shows: "✅ WebSocket connected"
- No console errors

**Verification Command:**
```javascript
window.mlDashboard.socket.connected  // Should return true
```

**Status:** [ ] Pass [ ] Fail [ ] Blocked  
**Notes:** _______________________

---

#### TC-WS-002: Automatic Subscription to ML Updates
**Priority:** CRITICAL  
**Preconditions:** TC-WS-001 passed  

**Steps:**
1. Open browser console
2. Check WebSocket frames in Network tab
3. Look for `ml_subscribe` event sent to server

**Expected Results:**
- `ml_subscribe` event sent automatically on connection
- Client joins `ml_updates` room
- No errors in console

**Verification Command:**
```javascript
// Should see subscription confirmation
window.mlDashboard.socket.emit('request_training_status');
// Wait 1 second, check console for response
```

**Status:** [ ] Pass [ ] Fail [ ] Blocked  
**Notes:** _______________________

---

#### TC-WS-003: Reconnection After Disconnect
**Priority:** HIGH  
**Preconditions:** TC-WS-001 passed  

**Steps:**
1. Confirm WebSocket connected (green dot)
2. Simulate disconnect: `window.mlDashboard.socket.disconnect()`
3. Wait 2 seconds
4. Observe connection indicator
5. Wait 5 seconds (reconnection delay)
6. Check if reconnects automatically

**Expected Results:**
- Status dot turns orange immediately after disconnect
- Console shows: "⚠️ WebSocket disconnected, falling back to polling"
- After ~2-5 seconds, automatic reconnection attempt
- Green dot returns when reconnected
- Console shows: "✅ WebSocket reconnected"

**Verification Command:**
```javascript
// Disconnect
window.mlDashboard.socket.disconnect();
setTimeout(() => {
    console.log('Reconnected:', window.mlDashboard.socket.connected);
}, 10000);  // Wait 10 seconds
```

**Status:** [ ] Pass [ ] Fail [ ] Blocked  
**Notes:** _______________________

---

#### TC-WS-004: Max Reconnection Attempts (5)
**Priority:** MEDIUM  
**Preconditions:** Server stopped  

**Steps:**
1. Stop Flask server (Ctrl+C in terminal)
2. Disconnect client: `window.mlDashboard.socket.disconnect()`
3. Force reconnection: `window.mlDashboard.socket.connect()`
4. Wait 30 seconds
5. Count reconnection attempts in console

**Expected Results:**
- 5 reconnection attempts made
- Each attempt logged in console
- After 5 failed attempts, stops trying
- Status indicator shows orange (polling mode)
- Console shows: "❌ Max reconnection attempts reached"

**Verification Command:**
```javascript
window.mlDashboard.reconnectAttempts  // Should be 5
```

**Status:** [ ] Pass [ ] Fail [ ] Blocked  
**Notes:** _______________________

---

#### TC-WS-005: Graceful Degradation to Polling
**Priority:** CRITICAL  
**Preconditions:** Server running, WebSocket disconnected  

**Steps:**
1. Disconnect WebSocket: `window.mlDashboard.socket.disconnect()`
2. Wait 5 seconds
3. Check if polling is active
4. Verify dashboard still updates

**Expected Results:**
- Status indicator turns orange
- Console shows: "⚠️ WebSocket disconnected, falling back to polling"
- Dashboard continues to update every 30 seconds via REST API
- No loss of functionality (models, metrics still load)

**Verification Command:**
```javascript
// Check polling interval
window.mlDashboard.pollingInterval  // Should be set (not null)
```

**Status:** [ ] Pass [ ] Fail [ ] Blocked  
**Notes:** _______________________

---

### Category 2: Real-Time Training Updates

#### TC-TRAIN-001: Training Started Broadcast
**Priority:** CRITICAL  
**Preconditions:** WebSocket connected, climate_predictor model exists  

**Steps:**
1. Open dashboard
2. Click "🔄 Retrain" on climate_predictor model
3. Watch for real-time updates

**Expected Results:**
- Training starts immediately (API call succeeds)
- Within 500ms, receive `training_started` event
- Progress bar appears under the model card
- Progress shows "0% - Preparing data"
- Console shows: "🎓 Training started: climate_predictor v2.0"

**Verification Command:**
```javascript
// Manually trigger training via console
fetch('/api/ml/models/climate_predictor/retrain', {method: 'POST'})
    .then(r => r.json())
    .then(data => console.log('Training triggered:', data));
```

**Status:** [ ] Pass [ ] Fail [ ] Blocked  
**Notes:** _______________________

---

#### TC-TRAIN-002: Training Progress Updates (0-100%)
**Priority:** CRITICAL  
**Preconditions:** Training in progress  

**Steps:**
1. Trigger training (TC-TRAIN-001)
2. Watch progress bar
3. Monitor console for progress events

**Expected Results:**
- Progress bar updates smoothly (0% → 100%)
- At least 5 progress updates received
- Progress shows percentage, loss, and accuracy
- Example: "45% - Loss: 0.123, Accuracy: 87.5%"
- Progress bar color gradient animates

**Verification Command:**
```javascript
// Simulate progress update (for testing UI only)
window.mlDashboard.updateTrainingProgress({
    model_name: 'climate_predictor',
    version: '2.0',
    progress: 50.0,
    status: 'training',
    metrics: {loss: 0.123, accuracy: 0.875}
});
```

**Status:** [ ] Pass [ ] Fail [ ] Blocked  
**Notes:** _______________________

---

#### TC-TRAIN-003: Training Complete Broadcast
**Priority:** CRITICAL  
**Preconditions:** Training in progress  

**Steps:**
1. Wait for training to complete (~30 seconds)
2. Observe final broadcast
3. Check progress bar removal

**Expected Results:**
- Receive `training_complete` event
- Progress bar shows "100% - Complete"
- After 3 seconds, progress bar auto-removes
- Model card updates with new metrics (accuracy, MAE, RMSE, R²)
- Version number increments (e.g., 1.0 → 2.0)
- "Last Trained" timestamp updates
- Console shows: "✅ Training complete: climate_predictor v2.0 - Accuracy: 92.5%"

**Verification Command:**
```javascript
// Check if progress bar removed
document.querySelector('.training-progress-container')  // Should be null after 3 seconds
```

**Status:** [ ] Pass [ ] Fail [ ] Blocked  
**Notes:** _______________________

---

#### TC-TRAIN-004: Training Failed Broadcast
**Priority:** HIGH  
**Preconditions:** Ability to simulate training failure  

**Steps:**
1. Simulate training failure (manual server-side trigger or invalid data)
2. Observe error handling

**Expected Results:**
- Receive `training_failed` event
- Progress bar turns red
- Error message displayed: "Training failed: [error message]"
- Progress bar remains visible for 5 seconds with error
- Console shows: "❌ Training failed: climate_predictor - [error]"
- Model card shows previous metrics (not updated)

**Verification Command:**
```javascript
// Simulate failure (for testing UI only)
window.mlDashboard.socket.emit('training_failed', {
    model_name: 'climate_predictor',
    version: '2.0',
    error: 'Insufficient training data'
});
```

**Status:** [ ] Pass [ ] Fail [ ] Blocked  
**Notes:** _______________________

---

#### TC-TRAIN-005: Multiple Concurrent Training Sessions
**Priority:** MEDIUM  
**Preconditions:** At least 2 models available  

**Steps:**
1. Start training on climate_predictor
2. Immediately start training on anomaly_detector
3. Watch both progress bars

**Expected Results:**
- Both progress bars visible simultaneously
- Each shows independent progress
- No interference between training sessions
- Both complete successfully
- Console shows distinct logs for each model

**Verification Command:**
```javascript
// Trigger multiple trainings
fetch('/api/ml/models/climate_predictor/retrain', {method: 'POST'});
fetch('/api/ml/models/anomaly_detector/retrain', {method: 'POST'});
```

**Status:** [ ] Pass [ ] Fail [ ] Blocked  
**Notes:** _______________________

---

### Category 3: Drift Detection & Monitoring

#### TC-DRIFT-001: Drift Detected Broadcast
**Priority:** HIGH  
**Preconditions:** WebSocket connected, drift detection running  

**Steps:**
1. Wait for automatic drift detection (runs every 24 hours, or trigger manually)
2. If drift detected, observe broadcast

**Expected Results:**
- Receive `drift_detected` event
- Drift alert displayed in dashboard (red badge or notification)
- Console shows: "⚠️ Drift detected: climate_predictor - Severity: HIGH"
- Drift metrics update in Model Details modal

**Verification Command:**
```javascript
// Manually request drift update
window.mlDashboard.socket.emit('request_drift_update', {
    model_name: 'climate_predictor'
});
// Wait 1-2 seconds, check console for response
```

**Status:** [ ] Pass [ ] Fail [ ] Blocked  
**Notes:** _______________________

---

#### TC-DRIFT-002: Drift Metrics Update via WebSocket
**Priority:** MEDIUM  
**Preconditions:** WebSocket connected  

**Steps:**
1. Request drift update: `window.mlDashboard.socket.emit('request_drift_update', {model_name: 'climate_predictor'})`
2. Wait for response
3. Check dashboard for updated drift metrics

**Expected Results:**
- Receive `drift_update` event
- Drift metrics displayed (PSI score, drift severity)
- Console shows: "📊 Drift update: climate_predictor - PSI: 0.35"
- Model Details modal shows updated drift charts

**Verification Command:**
```javascript
window.mlDashboard.socket.on('drift_update', (data) => {
    console.log('Drift update received:', data);
});
```

**Status:** [ ] Pass [ ] Fail [ ] Blocked  
**Notes:** _______________________

---

### Category 4: Model Comparison Visualization

#### TC-VIZ-001: Open Model Comparison Modal
**Priority:** CRITICAL  
**Preconditions:** At least 2 models exist  

**Steps:**
1. Click "📊 Compare Models" button in Models Overview card
2. Wait for modal to open
3. Observe chart rendering

**Expected Results:**
- Modal opens within 500ms
- "Model Comparison" title visible
- Loading spinner shows briefly
- Chart.js grouped bar chart renders within 3 seconds
- X-axis: Model names
- Y-axis: Percentage (0-100%)
- 2 bar groups per model: Accuracy % (blue), R² Score % (green)
- Legend shows metric names
- Tooltips work on hover

**Verification Command:**
```javascript
// Trigger modal programmatically
window.mlDashboard.showModelComparison();
```

**Status:** [ ] Pass [ ] Fail [ ] Blocked  
**Notes:** _______________________

---

#### TC-VIZ-002: Model Comparison Chart Data Accuracy
**Priority:** HIGH  
**Preconditions:** TC-VIZ-001 passed  

**Steps:**
1. Open Model Comparison modal
2. Note accuracy values from dashboard model cards
3. Compare with chart bar heights

**Expected Results:**
- Chart data matches model card metrics exactly
- Accuracy percentages accurate to 1 decimal place
- R² scores converted to percentages correctly
- All models displayed (no missing models)

**Verification Command:**
```javascript
// Fetch comparison data directly
fetch('/api/ml/models/compare', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({models: ['climate_predictor', 'anomaly_detector']})
})
.then(r => r.json())
.then(data => console.table(data.comparison));
```

**Status:** [ ] Pass [ ] Fail [ ] Blocked  
**Notes:** _______________________

---

#### TC-VIZ-003: Model Comparison Chart Interactions
**Priority:** MEDIUM  
**Preconditions:** TC-VIZ-001 passed  

**Steps:**
1. Open Model Comparison modal
2. Hover over bars
3. Click legend items

**Expected Results:**
- **Hover:** Tooltip appears with exact values
  - Example: "climate_predictor - Accuracy: 92.5%"
- **Click legend:** Toggle dataset visibility
  - Click "Accuracy %" → hides accuracy bars
  - Click again → shows them again
- Smooth animations on interactions

**Status:** [ ] Pass [ ] Fail [ ] Blocked  
**Notes:** _______________________

---

#### TC-VIZ-004: Close Model Comparison Modal
**Priority:** LOW  
**Preconditions:** Modal open  

**Steps:**
1. Click "Close" button
2. Click outside modal (backdrop)
3. Press Escape key

**Expected Results:**
- All 3 methods close the modal
- Chart destroyed properly (no memory leak)
- Dashboard still functional after closing

**Verification Command:**
```javascript
// Close modal programmatically
window.mlDashboard.closeComparisonModal();
```

**Status:** [ ] Pass [ ] Fail [ ] Blocked  
**Notes:** _______________________

---

### Category 5: Feature Importance Visualization

#### TC-VIZ-005: Open Feature Importance Modal
**Priority:** CRITICAL  
**Preconditions:** climate_predictor model exists  

**Steps:**
1. Click "🔍 Features" button on climate_predictor model card
2. Wait for modal to open
3. Observe chart rendering

**Expected Results:**
- Modal opens within 500ms
- "Feature Importance: climate_predictor" title visible
- Loading spinner shows briefly
- Chart.js horizontal bar chart renders within 3 seconds
- Y-axis: Feature names (top 15)
- X-axis: Importance percentage (0-100%)
- Bars colored green (rgba(16, 185, 129, 0.7))
- Features sorted by importance (highest at top)

**Verification Command:**
```javascript
// Trigger modal programmatically
window.mlDashboard.showFeatureImportance('climate_predictor');
```

**Status:** [ ] Pass [ ] Fail [ ] Blocked  
**Notes:** _______________________

---

#### TC-VIZ-006: Feature Importance Data Accuracy
**Priority:** HIGH  
**Preconditions:** TC-VIZ-005 passed  

**Steps:**
1. Open Feature Importance modal for climate_predictor
2. Fetch feature importance data directly via API
3. Compare chart with API data

**Expected Results:**
- Top 15 features displayed
- Importance scores accurate (percentage format)
- Features sorted correctly (descending importance)
- Total features count shown in subtitle

**Verification Command:**
```javascript
// Fetch feature data directly
fetch('/api/ml/models/climate_predictor/features')
    .then(r => r.json())
    .then(data => {
        console.log('Total features:', data.total_features);
        console.table(data.features);
    });
```

**Status:** [ ] Pass [ ] Fail [ ] Blocked  
**Notes:** _______________________

---

#### TC-VIZ-007: Feature Importance Chart Interactions
**Priority:** MEDIUM  
**Preconditions:** TC-VIZ-005 passed  

**Steps:**
1. Open Feature Importance modal
2. Hover over bars
3. Scroll if more than 15 features

**Expected Results:**
- **Hover:** Tooltip shows exact importance percentage
  - Example: "temperature: 23.45%"
- Chart scales properly for different feature counts
- If total features > 15, subtitle shows: "Showing top 15 of X features"

**Status:** [ ] Pass [ ] Fail [ ] Blocked  
**Notes:** _______________________

---

#### TC-VIZ-008: Close Feature Importance Modal
**Priority:** LOW  
**Preconditions:** Modal open  

**Steps:**
1. Click "Close" button
2. Click outside modal (backdrop)
3. Press Escape key

**Expected Results:**
- All 3 methods close the modal
- Chart destroyed properly
- Dashboard functional after closing

**Verification Command:**
```javascript
window.mlDashboard.closeFeaturesModal();
```

**Status:** [ ] Pass [ ] Fail [ ] Blocked  
**Notes:** _______________________

---

### Category 6: Model Actions & WebSocket Broadcasts

#### TC-ACTION-001: Model Activation Triggers Broadcast
**Priority:** HIGH  
**Preconditions:** climate_predictor has version 2.0+ available  

**Steps:**
1. Open Model Details modal for climate_predictor
2. Click "Activate" on version 2.0
3. Confirm activation
4. Observe WebSocket broadcast

**Expected Results:**
- Activation succeeds (API returns success)
- Within 500ms, receive `model_activated` event
- Console shows: "✅ Model activated: climate_predictor v2.0"
- Model card updates to show v2.0 as active
- "Active Version" badge appears on v2.0 in history

**Verification Command:**
```javascript
// Activate version via API
fetch('/api/ml/models/climate_predictor/activate/2.0', {method: 'POST'})
    .then(r => r.json())
    .then(data => console.log('Activation result:', data));
```

**Status:** [ ] Pass [ ] Fail [ ] Blocked  
**Notes:** _______________________

---

#### TC-ACTION-002: Retraining Scheduled Broadcast
**Priority:** MEDIUM  
**Preconditions:** WebSocket connected  

**Steps:**
1. Open Model Details modal for climate_predictor
2. Click "Schedule Retraining" or use API
3. Set schedule (e.g., daily at midnight)
4. Confirm schedule

**Expected Results:**
- Schedule API call succeeds
- Within 500ms, receive `retraining_scheduled` event
- Console shows: "📅 Retraining scheduled: climate_predictor - daily at 00:00"
- Schedule visible in Model Details modal

**Verification Command:**
```javascript
// Schedule retraining via API
fetch('/api/ml/models/climate_predictor/schedule-retraining', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({schedule: 'daily', time: '00:00'})
})
.then(r => r.json())
.then(data => console.log('Schedule result:', data));
```

**Status:** [ ] Pass [ ] Fail [ ] Blocked  
**Notes:** _______________________

---

### Category 7: Multi-Client Broadcasting

#### TC-MULTI-001: Broadcast to Multiple Tabs
**Priority:** HIGH  
**Preconditions:** WebSocket available  

**Steps:**
1. Open dashboard in Tab 1
2. Open dashboard in Tab 2 (same URL)
3. Wait for both to connect (green dots)
4. In Tab 1, trigger training on climate_predictor
5. Watch Tab 2

**Expected Results:**
- Both tabs show green connection indicator
- Training progress appears in BOTH tabs simultaneously
- Progress updates in both tabs in real-time
- Training complete event received by both tabs
- Both tabs update model metrics after training

**Verification Command:**
```javascript
// In each tab, check connection
console.log('Tab connected:', window.mlDashboard.socket.connected);
```

**Status:** [ ] Pass [ ] Fail [ ] Blocked  
**Notes:** _______________________

---

#### TC-MULTI-002: Independent Tab Disconnection
**Priority:** MEDIUM  
**Preconditions:** 2 tabs open, both connected  

**Steps:**
1. In Tab 1, disconnect WebSocket: `window.mlDashboard.socket.disconnect()`
2. Observe Tab 1 (should turn orange, polling mode)
3. Observe Tab 2 (should remain green, WebSocket active)
4. In Tab 1, trigger training
5. Observe Tab 2

**Expected Results:**
- Tab 1 turns orange (polling mode)
- Tab 2 stays green (WebSocket active)
- Tab 1 receives updates via polling (30s delay)
- Tab 2 receives updates via WebSocket (real-time)
- Both tabs eventually show consistent data

**Status:** [ ] Pass [ ] Fail [ ] Blocked  
**Notes:** _______________________

---

### Category 8: Error Handling & Edge Cases

(See [Error Scenarios & Edge Cases](#error-scenarios--edge-cases) section for detailed test cases)

---

## Performance Benchmarks

### Benchmark 1: Page Load Time

**Target:** <2 seconds  
**Measurement:** Time from navigation to fully interactive

**Steps:**
1. Close all dashboard tabs
2. Clear browser cache (Ctrl+Shift+Delete)
3. Open DevTools → Performance tab
4. Click "Record" (circle icon)
5. Navigate to http://localhost:5000/ml-dashboard
6. Wait for page to fully load
7. Stop recording
8. Check "Load" event time

**Metrics:**
- **DOMContentLoaded:** <500ms
- **Load:** <1500ms
- **Fully Interactive (TTI):** <2000ms

**Result:** ______ ms [ ] Pass [ ] Fail

---

### Benchmark 2: WebSocket Connection Time

**Target:** <500ms  
**Measurement:** Time from page load to WebSocket connected

**Steps:**
1. Reload dashboard
2. In console, measure:
```javascript
window.perfMonitor.mark('ws-start');
window.mlDashboard.socket.on('connect', () => {
    window.perfMonitor.mark('ws-end');
    window.perfMonitor.measure('ws-connection', 'ws-start', 'ws-end');
});
```

**Metrics:**
- **Connection Time:** <500ms

**Result:** ______ ms [ ] Pass [ ] Fail

---

### Benchmark 3: Chart Render Time

**Target:** <3 seconds  
**Measurement:** Time from modal open to chart visible

**Steps:**
1. In console, measure:
```javascript
window.perfMonitor.mark('chart-start');
window.mlDashboard.showModelComparison();
setTimeout(() => {
    window.perfMonitor.mark('chart-end');
    window.perfMonitor.measure('chart-render', 'chart-start', 'chart-end');
}, 3000);
```

**Metrics:**
- **Model Comparison Chart:** <3000ms
- **Feature Importance Chart:** <3000ms

**Result (Comparison):** ______ ms [ ] Pass [ ] Fail  
**Result (Features):** ______ ms [ ] Pass [ ] Fail

---

### Benchmark 4: Training Progress Update Latency

**Target:** <100ms  
**Measurement:** Time from server emit to UI update

**Steps:**
1. Start training on any model
2. In Network tab → WS → Frames, timestamp first `training_progress` frame
3. In console, timestamp when progress bar updates
4. Calculate difference

**Metrics:**
- **Server → Client Latency:** <100ms

**Result:** ______ ms [ ] Pass [ ] Fail

---

### Benchmark 5: API Response Time

**Target:** <200ms (GET), <500ms (POST training)  
**Measurement:** Time from request to response

**Steps:**
1. In console, measure:
```javascript
const start = Date.now();
fetch('/api/ml/models')
    .then(r => r.json())
    .then(data => {
        console.log('GET /api/ml/models:', Date.now() - start, 'ms');
    });
```

**Metrics:**
- **GET /api/ml/models:** <200ms
- **GET /api/ml/models/<name>/features:** <300ms
- **POST /api/ml/models/compare:** <400ms
- **POST /api/ml/models/<name>/retrain:** <500ms (initial response, not training time)

**Results:**
- GET /models: ______ ms [ ] Pass [ ] Fail
- GET /features: ______ ms [ ] Pass [ ] Fail
- POST /compare: ______ ms [ ] Pass [ ] Fail
- POST /retrain: ______ ms [ ] Pass [ ] Fail

---

## Browser Compatibility Matrix

| Feature | Chrome 120+ | Firefox 121+ | Safari 17+ | Edge 120+ |
|---------|-------------|--------------|------------|-----------|
| **WebSocket Connection** | [ ] Pass | [ ] Pass | [ ] Pass | [ ] Pass |
| **Real-Time Updates** | [ ] Pass | [ ] Pass | [ ] Pass | [ ] Pass |
| **Chart.js Rendering** | [ ] Pass | [ ] Pass | [ ] Pass | [ ] Pass |
| **Bootstrap Modals** | [ ] Pass | [ ] Pass | [ ] Pass | [ ] Pass |
| **Training Progress** | [ ] Pass | [ ] Pass | [ ] Pass | [ ] Pass |
| **Connection Indicator** | [ ] Pass | [ ] Pass | [ ] Pass | [ ] Pass |
| **Polling Fallback** | [ ] Pass | [ ] Pass | [ ] Pass | [ ] Pass |
| **Console Errors** | [ ] None | [ ] None | [ ] None | [ ] None |

### Browser-Specific Notes

**Chrome:**
- Preferred browser for development
- Full Socket.IO support
- Best DevTools for WebSocket debugging

**Firefox:**
- Test WebSocket frame inspection
- Check CSS animations (pulsing dot)

**Safari:**
- Test on macOS Safari 17+
- Test on iOS Safari (mobile)
- Check for WebSocket connection issues

**Edge:**
- Chromium-based, similar to Chrome
- Quick compatibility check

---

## Load Testing Procedures

### Load Test 1: Concurrent Connections

**Objective:** Test 5+ concurrent WebSocket connections  
**Target:** All connections stable, no performance degradation

**Steps:**
1. Open 5 browser tabs (or use different browsers)
2. Load dashboard in each tab
3. Verify all show green connection indicator
4. Trigger training in Tab 1
5. Verify all tabs receive broadcasts

**Metrics:**
- **Connection Success Rate:** 100%
- **Broadcast Delivery Rate:** 100%
- **Latency Increase:** <50ms per additional connection

**Results:**
- Tabs connected: ______
- Broadcast success: ______%
- Latency: ______ ms

**Status:** [ ] Pass [ ] Fail

---

### Load Test 2: Rapid API Calls

**Objective:** Simulate rapid API requests (10 per second)  
**Target:** No errors, consistent response times

**Steps:**
```javascript
// In console
const results = [];
for (let i = 0; i < 50; i++) {
    const start = Date.now();
    fetch('/api/ml/models')
        .then(r => r.json())
        .then(data => {
            results.push(Date.now() - start);
            if (results.length === 50) {
                const avg = results.reduce((a,b)=>a+b,0) / results.length;
                console.log('Average response time:', avg, 'ms');
                console.log('Max:', Math.max(...results), 'ms');
                console.log('Min:', Math.min(...results), 'ms');
            }
        });
}
```

**Metrics:**
- **Average Response Time:** <300ms
- **Max Response Time:** <500ms
- **Error Rate:** 0%

**Results:**
- Avg: ______ ms
- Max: ______ ms
- Errors: ______

**Status:** [ ] Pass [ ] Fail

---

### Load Test 3: WebSocket Message Burst

**Objective:** Test handling of rapid WebSocket messages  
**Target:** No message loss, UI remains responsive

**Steps:**
1. Simulate 10 rapid progress updates:
```javascript
for (let i = 0; i <= 100; i += 10) {
    window.mlDashboard.updateTrainingProgress({
        model_name: 'climate_predictor',
        version: '2.0',
        progress: i,
        status: 'training',
        metrics: {loss: 0.5 - (i/200), accuracy: 0.5 + (i/200)}
    });
}
```

2. Verify progress bar updates smoothly
3. Check console for errors

**Metrics:**
- **Message Processing:** All 10 messages processed
- **UI Responsiveness:** No freezing
- **Animation Smoothness:** No stuttering

**Status:** [ ] Pass [ ] Fail

---

## Error Scenarios & Edge Cases

### Error Test 1: Server Unavailable on Page Load

**Scenario:** Server not running when dashboard loads  
**Expected Behavior:** Graceful error handling

**Steps:**
1. Stop Flask server (Ctrl+C)
2. Open dashboard in browser
3. Observe behavior

**Expected Results:**
- Page loads (HTML/CSS/JS served from cache or shows "Cannot connect")
- WebSocket connection fails
- Status indicator shows orange/red
- Console shows: "❌ Failed to connect to server"
- Polling attempts continue every 30 seconds
- No JavaScript errors crash the page

**Status:** [ ] Pass [ ] Fail [ ] Blocked  
**Notes:** _______________________

---

### Error Test 2: WebSocket Not Supported

**Scenario:** Browser doesn't support WebSocket (simulate by disabling)  
**Expected Behavior:** Automatic fallback to long-polling

**Steps:**
1. In console, disable WebSocket:
```javascript
// Before dashboard loads
window.io.transports = ['polling'];
```
2. Reload dashboard
3. Verify polling mode active

**Expected Results:**
- Dashboard loads successfully
- Connection indicator shows orange (polling mode)
- Dashboard updates every 30 seconds via REST API
- No WebSocket errors in console

**Status:** [ ] Pass [ ] Fail [ ] Blocked  
**Notes:** _______________________

---

### Error Test 3: Network Interruption Mid-Training

**Scenario:** Network disconnects while training in progress  
**Expected Behavior:** Connection recovers, training status synced

**Steps:**
1. Start training on climate_predictor
2. Disconnect network (airplane mode or unplug ethernet)
3. Wait 10 seconds
4. Reconnect network
5. Observe behavior

**Expected Results:**
- WebSocket disconnects (orange indicator)
- Progress bar shows last known state
- After reconnection, WebSocket reconnects automatically
- Progress bar updates to current training state
- Training completes successfully

**Status:** [ ] Pass [ ] Fail [ ] Blocked  
**Notes:** _______________________

---

### Error Test 4: Invalid Model Name in API Call

**Scenario:** Request features for non-existent model  
**Expected Behavior:** Graceful error message

**Steps:**
```javascript
fetch('/api/ml/models/nonexistent_model/features')
    .then(r => r.json())
    .then(data => console.log(data))
    .catch(err => console.error(err));
```

**Expected Results:**
- HTTP 404 Not Found
- JSON response: `{"error": "Model not found"}`
- No server crash
- Dashboard remains functional

**Status:** [ ] Pass [ ] Fail [ ] Blocked  
**Notes:** _______________________

---

### Error Test 5: Empty Model List

**Scenario:** No models available in database  
**Expected Behavior:** Empty state displayed

**Steps:**
1. Clear model registry (database manipulation)
2. Reload dashboard
3. Observe UI

**Expected Results:**
- Dashboard loads without errors
- "No models available" message displayed
- System Health shows 0 active models
- "Compare Models" button disabled or hidden
- No JavaScript errors

**Status:** [ ] Pass [ ] Fail [ ] Blocked  
**Notes:** _______________________

---

### Edge Case 1: Model with No Features

**Scenario:** Model has no feature importance data  
**Expected Behavior:** Graceful message

**Steps:**
1. Click "Features" on a model without feature importance
2. Observe modal

**Expected Results:**
- Modal opens
- Message: "No feature importance data available for this model"
- No chart displayed (or empty chart with message)
- No errors in console

**Status:** [ ] Pass [ ] Fail [ ] Blocked  
**Notes:** _______________________

---

### Edge Case 2: Training Completes in <1 Second

**Scenario:** Very fast training (small dataset)  
**Expected Behavior:** Progress bar still visible

**Steps:**
1. Train a model with minimal data (fast training)
2. Observe progress bar

**Expected Results:**
- Progress bar appears
- Updates visible (even if only 1-2 updates)
- Progress bar shows 100% briefly
- Auto-removes after 3 seconds

**Status:** [ ] Pass [ ] Fail [ ] Blocked  
**Notes:** _______________________

---

### Edge Case 3: Very Long Model Name

**Scenario:** Model name exceeds expected length  
**Expected Behavior:** UI handles gracefully

**Steps:**
1. Create model with long name (>50 characters)
2. View on dashboard
3. Open modals

**Expected Results:**
- Model name truncates with ellipsis (...)
- Tooltip shows full name on hover
- Charts display correctly
- No layout breakage

**Status:** [ ] Pass [ ] Fail [ ] Blocked  
**Notes:** _______________________

---

## Regression Testing

### Regression Test 1: Existing Dashboard Features

**Objective:** Ensure Phase 5 didn't break existing functionality

**Features to Verify:**
- [ ] Model list displays correctly
- [ ] Model cards show accurate metrics
- [ ] System Health panel works
- [ ] Model Details modal opens
- [ ] Version history displays
- [ ] Training history timeline works
- [ ] Manual training (without WebSocket) works via polling

**Status:** [ ] Pass [ ] Fail  
**Notes:** _______________________

---

### Regression Test 2: API Endpoints

**Objective:** All existing APIs still functional

**Endpoints to Test:**
```javascript
// Paste in console
const endpoints = [
    '/api/ml/models',
    '/api/ml/models/climate_predictor',
    '/api/ml/models/climate_predictor/versions',
    '/api/ml/drift-metrics',
    '/api/ml/retraining-events'
];

endpoints.forEach(url => {
    fetch(url)
        .then(r => {
            console.log(`${url}: ${r.ok ? '✅' : '❌'} (${r.status})`);
            return r.json();
        })
        .then(data => console.log(data))
        .catch(err => console.error(url, err));
});
```

**Expected Results:**
- All endpoints return 200 OK
- JSON data valid
- No server errors

**Status:** [ ] Pass [ ] Fail  
**Notes:** _______________________

---

### Regression Test 3: Other Dashboard Pages

**Objective:** Phase 5 changes didn't affect other pages

**Pages to Check:**
- [ ] `/` - Home page
- [ ] `/devices` - Devices page
- [ ] `/plant-health` - Plant health page
- [ ] `/settings` - Settings page

**Steps:**
1. Navigate to each page
2. Verify loads without errors
3. Check console for errors
4. Verify basic functionality

**Status:** [ ] Pass [ ] Fail  
**Notes:** _______________________

---

## Test Results Documentation

### Summary Template

**Test Execution Date:** _______________  
**Tester Name:** _______________  
**Environment:** _______________  
**Server Version:** _______________  
**Browser(s) Tested:** _______________

### Results Overview

| Category | Total Tests | Passed | Failed | Blocked | Pass Rate |
|----------|-------------|--------|--------|---------|-----------|
| WebSocket Connection | 5 | ___ | ___ | ___ | ___% |
| Real-Time Training | 5 | ___ | ___ | ___ | ___% |
| Drift Detection | 2 | ___ | ___ | ___ | ___% |
| Model Comparison | 4 | ___ | ___ | ___ | ___% |
| Feature Importance | 4 | ___ | ___ | ___ | ___% |
| Model Actions | 2 | ___ | ___ | ___ | ___% |
| Multi-Client | 2 | ___ | ___ | ___ | ___% |
| Error Handling | 5 | ___ | ___ | ___ | ___% |
| Edge Cases | 3 | ___ | ___ | ___ | ___% |
| Regression | 3 | ___ | ___ | ___ | ___% |
| **TOTAL** | **35+** | ___ | ___ | ___ | ___% |

### Performance Results

| Benchmark | Target | Actual | Status |
|-----------|--------|--------|--------|
| Page Load Time | <2s | ___s | [ ] Pass [ ] Fail |
| WebSocket Connection | <500ms | ___ms | [ ] Pass [ ] Fail |
| Chart Render (Comparison) | <3s | ___s | [ ] Pass [ ] Fail |
| Chart Render (Features) | <3s | ___s | [ ] Pass [ ] Fail |
| Training Update Latency | <100ms | ___ms | [ ] Pass [ ] Fail |
| API Response (GET) | <200ms | ___ms | [ ] Pass [ ] Fail |
| API Response (POST) | <500ms | ___ms | [ ] Pass [ ] Fail |

### Browser Compatibility Results

| Browser | Version | Status | Notes |
|---------|---------|--------|-------|
| Chrome | ___ | [ ] Pass [ ] Fail | ____________ |
| Firefox | ___ | [ ] Pass [ ] Fail | ____________ |
| Safari | ___ | [ ] Pass [ ] Fail | ____________ |
| Edge | ___ | [ ] Pass [ ] Fail | ____________ |

### Critical Issues Found

| Issue ID | Severity | Description | Steps to Reproduce | Status |
|----------|----------|-------------|-------------------|--------|
| BUG-001 | [ ] Critical [ ] High [ ] Medium [ ] Low | ____________ | ____________ | [ ] Open [ ] Fixed |
| BUG-002 | [ ] Critical [ ] High [ ] Medium [ ] Low | ____________ | ____________ | [ ] Open [ ] Fixed |
| BUG-003 | [ ] Critical [ ] High [ ] Medium [ ] Low | ____________ | ____________ | [ ] Open [ ] Fixed |

### Test Sign-Off

**Overall Result:** [ ] PASS [ ] FAIL (Conditional) [ ] FAIL (Blocked)

**Recommendation:**
- [ ] **Approved for Production** - All critical tests passed, minor issues acceptable
- [ ] **Approved with Conditions** - Fix listed issues before production
- [ ] **Not Approved** - Critical issues must be resolved

**Tester Signature:** _______________  
**Date:** _______________

---

## Bug Reporting Template

### Bug Report: BUG-XXX

**Reported By:** _______________  
**Date:** _______________  
**Environment:** _______________

**Severity:**
- [ ] Critical - Blocks core functionality, no workaround
- [ ] High - Major feature broken, workaround exists
- [ ] Medium - Feature works with issues
- [ ] Low - Cosmetic or minor issue

**Priority:**
- [ ] P0 - Fix immediately (production down)
- [ ] P1 - Fix before next release
- [ ] P2 - Fix in next sprint
- [ ] P3 - Fix when time permits

**Component:**
- [ ] WebSocket Connection
- [ ] Real-Time Updates
- [ ] Visualizations (Charts)
- [ ] API Integration
- [ ] UI/UX
- [ ] Performance
- [ ] Other: _______________

**Summary:**
_Brief one-line description_

**Description:**
_Detailed description of the issue_

**Steps to Reproduce:**
1. _Step 1_
2. _Step 2_
3. _Step 3_

**Expected Behavior:**
_What should happen_

**Actual Behavior:**
_What actually happens_

**Screenshots/Videos:**
_Attach if applicable_

**Console Errors:**
```
Paste console errors here
```

**Network Logs:**
_Relevant network activity_

**Browser & Version:**
_______________

**Workaround:**
_Temporary solution if available_

**Related Test Case:**
_e.g., TC-WS-003_

---

## Sign-Off Criteria

### Must Pass (Critical)

- ✅ **WebSocket Connection** - TC-WS-001, TC-WS-003 (100% pass)
- ✅ **Training Updates** - TC-TRAIN-001, TC-TRAIN-002, TC-TRAIN-003 (100% pass)
- ✅ **Model Comparison** - TC-VIZ-001, TC-VIZ-002 (100% pass)
- ✅ **Feature Importance** - TC-VIZ-005, TC-VIZ-006 (100% pass)
- ✅ **Multi-Client** - TC-MULTI-001 (100% pass)
- ✅ **Performance** - All benchmarks meet targets
- ✅ **Regression** - No existing features broken

### Should Pass (High Priority)

- ✅ **Reconnection** - TC-WS-004 (95%+ pass)
- ✅ **Polling Fallback** - TC-WS-005 (95%+ pass)
- ✅ **Error Handling** - All error tests (90%+ pass)
- ✅ **Browser Compatibility** - Chrome, Firefox (95%+ pass)

### Nice to Have (Medium Priority)

- ✅ **Chart Interactions** - TC-VIZ-003, TC-VIZ-007 (80%+ pass)
- ✅ **Edge Cases** - All edge case tests (80%+ pass)
- ✅ **Safari Compatibility** - (80%+ pass)

### Acceptable Failures

- Minor UI/UX issues (cosmetic)
- Non-critical edge cases
- Safari-specific minor issues (if documented)

### Blockers (Must Fix Before Production)

- Any critical test failure
- Performance benchmark misses target by >50%
- Regression in existing features
- Security vulnerabilities

---

## Next Steps After Testing

### If All Tests Pass ✅

1. **Mark Phase 5 as Complete**
   - Update `AI_INTEGRATION_ACTION_PLAN.md`
   - Mark "Phase 5: Testing & Validation" as ✅ Complete

2. **Deploy to Staging** (if available)
   - Test in staging environment
   - Monitor for 24-48 hours

3. **Prepare Phase 6**
   - Review Phase 6 requirements
   - Set up development environment
   - Schedule kickoff meeting

4. **Documentation**
   - Update `README.md` with Phase 5 features
   - Create user guide for WebSocket features
   - Update API documentation

### If Tests Fail ❌

1. **Triage Bugs**
   - Categorize by severity
   - Prioritize P0/P1 bugs

2. **Fix Critical Issues**
   - Assign bugs to developers
   - Fix and retest immediately

3. **Retest**
   - Run failed tests again
   - Run full regression suite

4. **Iterate**
   - Repeat until all critical tests pass

---

**End of Deep Dive Testing Plan**

**For Questions or Issues:**
- Review: `docs/PHASE_5_QUICK_TEST.md` for quick 15-20 min test
- Reference: `docs/PHASE_5_TESTING_AND_ROADMAP.md` for overview
- Contact: Project Lead or ML Team

**Good luck with testing! 🚀**
