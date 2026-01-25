# Phase 5 Quick Testing Guide

**Time Required:** 15-20 minutes  
**Server Status:** ✅ Running on `http://localhost:5000`

---

## Quick Test Sequence

### 1. Open ML Dashboard (1 min)
```
1. Navigate to: http://localhost:5000/ml-dashboard
2. Dashboard should load within 2 seconds
3. Look for green pulsing dot (top-right) - WebSocket connected
```

**✅ Pass Criteria:**
- Page loads successfully
- No JavaScript errors in console
- Connection indicator shows green/connected

---

### 2. Test WebSocket Connection (2 min)

**Open Browser Console (F12) and run:**

```javascript
// Check connection status
window.mlDashboard.socket.connected
// Expected: true

// Check subscriber count
console.log('Socket ID:', window.mlDashboard.socket.id);
// Expected: Random socket ID string

// Manually emit event
window.mlDashboard.socket.emit('request_training_status', {});
// Expected: 'training_status' event received
```

**✅ Pass Criteria:**
- `socket.connected` returns `true`
- Socket has valid ID
- Can emit and receive events

---

### 3. Test Model Comparison (3 min)

```
1. Click "📊 Compare Models" button (in Models Overview card)
2. Modal should open within 1 second
3. Chart should render within 2 seconds
4. Verify grouped bar chart with Accuracy & R² Score
5. Hover over bars to see tooltips
6. Click "Close" to dismiss
```

**✅ Pass Criteria:**
- Modal opens smoothly
- Chart renders with data
- Tooltips work on hover
- Modal closes cleanly

---

### 4. Test Feature Importance (3 min)

```
1. Find any model in the Models Overview list
2. Click "🔍 Features" button
3. Modal should open within 1 second
4. Horizontal bar chart should render
5. Verify top 15 features displayed
6. Check model name in chart title
7. Click "Close"
```

**✅ Pass Criteria:**
- Modal opens
- Feature chart renders (even if no data)
- Features sorted by importance
- Modal closes properly

---

### 5. Test Real-Time Training (5 min)

**Simulate Training Progress:**

```javascript
// Open console and run:
window.mlDashboard.updateTrainingProgress({
    model_name: 'climate_predictor',
    version: '2.0',
    progress: 25.0,
    metrics: {loss: 0.234, accuracy: 0.856}
});

// Wait 2 seconds, then run:
window.mlDashboard.updateTrainingProgress({
    model_name: 'climate_predictor',
    version: '2.0',
    progress: 50.0,
    metrics: {loss: 0.145, accuracy: 0.912}
});

// Wait 2 seconds, then run:
window.mlDashboard.updateTrainingProgress({
    model_name: 'climate_predictor',
    version: '2.0',
    progress: 100.0,
    metrics: {loss: 0.089, accuracy: 0.945}
});
```

**✅ Pass Criteria:**
- Progress bar appears in model list
- Bar animates from 25% → 50% → 100%
- Metrics display (Loss, Accuracy)
- Bar disappears 5 seconds after 100%

---

### 6. Test WebSocket Events (3 min)

**Emit Custom Events:**

```javascript
// Test training started
window.mlDashboard.socket.emit('ml_subscribe');

// Listen for events
window.mlDashboard.socket.on('ml_status', (data) => {
    console.log('ML Status:', data);
});

// Request drift update
window.mlDashboard.socket.emit('request_drift_update', {
    model_name: 'climate_predictor'
});

// Check console for 'drift_update' event
```

**✅ Pass Criteria:**
- Events emit successfully
- Responses received in console
- No errors in Network tab

---

### 7. Test Fallback to Polling (3 min)

```
1. Open DevTools > Network tab
2. Filter by "WS" (WebSocket)
3. Right-click WebSocket connection
4. Select "Close connection" or disconnect network
5. Verify status indicator turns orange
6. Wait 30 seconds
7. Verify dashboard still updates (polling mode)
```

**✅ Pass Criteria:**
- Status indicator changes to orange
- Dashboard continues to work
- Data refreshes every 30 seconds

---

### 8. Test Multiple Tabs (2 min)

```
1. Open ML Dashboard in 2nd browser tab
2. Verify both tabs connect (green dots)
3. In first tab, simulate training progress (use code from #5)
4. Check second tab receives same updates
5. Close one tab
6. Verify other tab unaffected
```

**✅ Pass Criteria:**
- Both tabs connect independently
- Events broadcast to all tabs
- Closing one doesn't affect others

---

## Test Results

### ✅ All Tests Passed
```
[x] Dashboard loads successfully
[x] WebSocket connects
[x] Model comparison works
[x] Feature importance works
[x] Training progress updates
[x] WebSocket events work
[x] Fallback to polling works
[x] Multiple tabs work
```

**Status:** Phase 5 COMPLETE ✅  
**Ready for Production:** YES

---

### ❌ Issues Found

_Document any issues here:_

**Issue #1:**
- Description:
- Steps to reproduce:
- Expected behavior:
- Actual behavior:

---

## Performance Benchmarks

Run these checks and record results:

### Page Load Time
```javascript
// In console after page load
performance.timing.loadEventEnd - performance.timing.navigationStart
// Expected: < 2000ms
```

**Result:** _______ ms

### WebSocket Connection Time
```javascript
// Check in Network tab
// WebSocket handshake time
// Expected: < 500ms
```

**Result:** _______ ms

### Chart Render Time
```
1. Open DevTools > Performance
2. Start recording
3. Click "Compare Models"
4. Stop recording when chart appears
5. Measure time
```

**Result:** _______ ms

---

## Browser Compatibility

Test in multiple browsers:

- [ ] Chrome/Edge (Chromium)
- [ ] Firefox
- [ ] Safari (if on Mac)
- [ ] Mobile Chrome (if testing mobile)
- [ ] Mobile Safari (if testing mobile)

---

## Next Steps After Testing

### If All Tests Pass:
1. ✅ Mark Phase 5 as COMPLETE
2. 📝 Update documentation with any findings
3. 🚀 Deploy to staging environment
4. 📊 Monitor for 24-48 hours
5. 🎯 Begin Phase 6 planning

### If Issues Found:
1. 🐛 Document all bugs in detail
2. 🔧 Fix critical issues first
3. ✅ Re-run tests
4. 📝 Update test results
5. 🔄 Repeat until all pass

---

## Testing Notes

**Tested By:** _____________  
**Date:** _____________  
**Browser:** _____________  
**OS:** _____________

**Additional Notes:**
_______________________________
_______________________________
_______________________________
