# ML Dashboard API Review & Migration

## Current State Analysis

The `ml_dashboard.html` template loads `static/js/ml_dashboard.js` which makes **16 different API calls**, but they're using **non-existent endpoints** that don't match our new ML/AI API structure.

---

## 🚨 Critical Issues Found

### Issue 1: Wrong URL Prefix
**Current:** Uses `/api/ml/*` prefix  
**Should Be:** `/api/ml/models/*`, `/api/ml/monitoring/*`, `/api/ml/retraining/*`

### Issue 2: Non-existent Endpoints
Many endpoints don't exist in our new backend structure:
- `/api/ml/health` ❌
- `/api/ml/models/${model}/drift` ❌
- `/api/ml/models/${model}/drift/history` ❌
- `/api/ml/training/history` ❌
- `/api/ml/models/${model}/retrain` ❌
- `/api/ml/models/${model}/activate` ❌
- `/api/ml/models/compare` ❌
- `/api/ml/models/${model}/features` ❌
- `/api/ml/retraining/schedule` ❌
- `/api/ml/retraining/jobs/${id}/run` ❌
- `/api/ml/retraining/jobs/${id}/${action}` ❌

---

## Endpoint Mapping

### ✅ Endpoints That Exist (need URL updates)

| Current Call | Exists As | Status | Action Needed |
|-------------|-----------|---------|---------------|
| `GET /api/ml/models` | `GET /api/ml/models/` | ✅ Exists | Update URL |
| `GET /api/ml/retraining/jobs` | `GET /api/ml/retraining/jobs` | ✅ Exists | No change |

### ❌ Endpoints That Need Implementation

| Current Call | Should Map To | Implementation |
|-------------|---------------|----------------|
| `GET /api/ml/health` | `GET /api/ml/models/status` | ✅ Already exists |
| `GET /api/ml/models/${model}/drift` | `GET /api/ml/monitoring/drift/${model}` | ✅ Already exists |
| `GET /api/ml/models/${model}/drift/history` | ❌ Not implemented | **Need to add** |
| `GET /api/ml/training/history` | ❌ Not implemented | **Need to add** |
| `POST /api/ml/models/${model}/retrain` | `POST /api/ml/retraining/trigger` | ✅ Exists (different params) |
| `POST /api/ml/models/${model}/activate` | `POST /api/ml/models/${model}/promote` | ✅ Already exists |
| `GET /api/ml/models/${model}` | `GET /api/ml/models/${model}/metadata` | ✅ Already exists |
| `POST /api/ml/models/compare` | ❌ Not implemented | **Need to add** |
| `GET /api/ml/models/${model}/features` | ❌ Not implemented | **Need to add** |
| `POST /api/ml/retraining/schedule` | `POST /api/ml/retraining/jobs` | ✅ Already exists |
| `POST /api/ml/retraining/jobs/${id}/run` | ❌ Not implemented | **Need to add** |
| `POST /api/ml/retraining/jobs/${id}/{pause|resume|cancel}` | `DELETE /api/ml/retraining/jobs/${id}` | ⚠️ Partial |

---

## Required Backend Changes

### 1. Add Missing Endpoints to `models.py`

```python
@models_bp.get("/<string:model_name>/drift/history")
def get_drift_history(model_name: str):
    """Get historical drift metrics for a model."""
    try:
        container = _container()
        drift_detector = container.drift_detector
        
        days = request.args.get("days", 30, type=int)
        history = drift_detector.get_drift_history(model_name, days=days)
        
        return _success({"model": model_name, "history": history})
    except Exception as e:
        logger.error(f"Error getting drift history: {e}", exc_info=True)
        return _fail(str(e), 500)


@models_bp.get("/<string:model_name>/features")
def get_feature_importance(model_name: str):
    """Get feature importance for a model."""
    try:
        container = _container()
        model_registry = container.model_registry
        
        features = model_registry.get_feature_importance(model_name)
        
        if not features:
            return _fail("Feature importance not available", 404)
        
        return _success({"model": model_name, "features": features})
    except Exception as e:
        logger.error(f"Error getting feature importance: {e}", exc_info=True)
        return _fail(str(e), 500)


@models_bp.post("/compare")
def compare_models():
    """Compare performance metrics of multiple models."""
    try:
        data = request.get_json()
        model_names = data.get("models", [])
        
        if len(model_names) < 2:
            return _fail("At least 2 models required for comparison", 400)
        
        container = _container()
        model_registry = container.model_registry
        
        comparison = {}
        for model_name in model_names:
            metadata = model_registry.get_model_metadata(model_name)
            if metadata:
                comparison[model_name] = metadata
        
        return _success(comparison)
    except Exception as e:
        logger.error(f"Error comparing models: {e}", exc_info=True)
        return _fail(str(e), 500)
```

### 2. Add Training History Endpoint to `monitoring.py`

```python
@monitoring_bp.get("/training/history")
def get_training_history():
    """Get recent training history across all models."""
    try:
        container = _container()
        model_registry = container.model_registry
        
        days = request.args.get("days", 30, type=int)
        limit = request.args.get("limit", 50, type=int)
        
        # Get training events from registry
        history = model_registry.get_training_history(days=days, limit=limit)
        
        return _success({
            "events": history,
            "count": len(history)
        })
    except Exception as e:
        logger.error(f"Error getting training history: {e}", exc_info=True)
        return _fail(str(e), 500)
```

### 3. Add Job Control Endpoints to `retraining.py`

```python
@retraining_api.post("/jobs/<string:job_id>/run")
def run_job_now(job_id: str):
    """Immediately execute a scheduled retraining job."""
    try:
        container = _container()
        scheduler = container.retraining_scheduler
        
        result = scheduler.run_job_immediately(job_id)
        
        if not result:
            return _fail(f"Job {job_id} not found or failed to start", 404)
        
        return _success({
            "job_id": job_id,
            "status": "running",
            "message": "Job execution started"
        })
    except Exception as e:
        logger.error(f"Error running job {job_id}: {e}", exc_info=True)
        return _fail(str(e), 500)


@retraining_api.post("/jobs/<string:job_id>/pause")
def pause_job(job_id: str):
    """Pause a running retraining job."""
    try:
        container = _container()
        scheduler = container.retraining_scheduler
        
        result = scheduler.pause_job(job_id)
        
        if not result:
            return _fail(f"Job {job_id} not found or cannot be paused", 404)
        
        return _success({
            "job_id": job_id,
            "status": "paused",
            "message": "Job paused successfully"
        })
    except Exception as e:
        logger.error(f"Error pausing job {job_id}: {e}", exc_info=True)
        return _fail(str(e), 500)


@retraining_api.post("/jobs/<string:job_id>/resume")
def resume_job(job_id: str):
    """Resume a paused retraining job."""
    try:
        container = _container()
        scheduler = container.retraining_scheduler
        
        result = scheduler.resume_job(job_id)
        
        if not result:
            return _fail(f"Job {job_id} not found or cannot be resumed", 404)
        
        return _success({
            "job_id": job_id,
            "status": "active",
            "message": "Job resumed successfully"
        })
    except Exception as e:
        logger.error(f"Error resuming job {job_id}: {e}", exc_info=True)
        return _fail(str(e), 500)
```

---

## Frontend JavaScript Migration

### File: `static/js/ml_dashboard.js`

#### 1. Health Check Update

```javascript
// BEFORE
const response = await fetch('/api/ml/health');

// AFTER
const response = await fetch('/api/ml/models/status');
```

#### 2. Models List Update

```javascript
// BEFORE
const response = await fetch('/api/ml/models');

// AFTER  
const response = await fetch('/api/ml/models/');  // Note trailing slash
```

#### 3. Drift Metrics Update

```javascript
// BEFORE
const response = await fetch(`/api/ml/models/${this.currentDriftModel}/drift`);

// AFTER
const response = await fetch(`/api/ml/monitoring/drift/${this.currentDriftModel}`);
```

#### 4. Drift History Update

```javascript
// BEFORE
const response = await fetch(`/api/ml/models/${this.currentDriftModel}/drift/history`);

// AFTER
const response = await fetch(`/api/ml/models/${this.currentDriftModel}/drift/history`);
// Note: Need to add this endpoint to backend
```

#### 5. Retraining Jobs (No Change)

```javascript
// Already correct
const response = await fetch('/api/ml/retraining/jobs');
```

#### 6. Training History Update

```javascript
// BEFORE
const response = await fetch('/api/ml/training/history');

// AFTER
const response = await fetch('/api/ml/monitoring/training/history');
// Note: Need to add this endpoint to backend
```

#### 7. Trigger Retraining Update

```javascript
// BEFORE
const response = await fetch(`/api/ml/models/${modelName}/retrain`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({force: true})
});

// AFTER
const response = await fetch('/api/ml/retraining/trigger', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
        model_name: modelName,
        force: true
    })
});
```

#### 8. Activate Model Update

```javascript
// BEFORE
const response = await fetch(`/api/ml/models/${modelName}/activate`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'}
});

// AFTER
const response = await fetch(`/api/ml/models/${modelName}/promote`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({version: 'latest'})
});
```

#### 9. Get Model Details Update

```javascript
// BEFORE
const response = await fetch(`/api/ml/models/${modelName}`);

// AFTER
const response = await fetch(`/api/ml/models/${modelName}/metadata`);
```

#### 10. Run Job Update

```javascript
// BEFORE
const response = await fetch(`/api/ml/retraining/jobs/${jobId}/run`, {
    method: 'POST'
});

// AFTER
const response = await fetch(`/api/ml/retraining/jobs/${jobId}/run`, {
    method: 'POST'
});
// Note: Need to add this endpoint to backend
```

#### 11. Job Control (Pause/Resume/Cancel) Update

```javascript
// BEFORE
const response = await fetch(`/api/ml/retraining/jobs/${jobId}/${endpoint}`, {
    method: 'POST'
});

// AFTER
// For pause/resume - add new endpoints
const response = await fetch(`/api/ml/retraining/jobs/${jobId}/${action}`, {
    method: 'POST'
});

// For cancel - use existing DELETE
const response = await fetch(`/api/ml/retraining/jobs/${jobId}`, {
    method: 'DELETE'
});
```

#### 12. Schedule Retraining Update

```javascript
// BEFORE
const response = await fetch('/api/ml/retraining/schedule', {
    method: 'POST',
    body: JSON.stringify(config)
});

// AFTER
const response = await fetch('/api/ml/retraining/jobs', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(config)
});
```

#### 13. Compare Models Update

```javascript
// BEFORE
const compareResponse = await fetch('/api/ml/models/compare', {
    method: 'POST',
    body: JSON.stringify({models: selectedModels})
});

// AFTER
const compareResponse = await fetch('/api/ml/models/compare', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({models: selectedModels})
});
// Note: Need to add this endpoint to backend
```

#### 14. Feature Importance Update

```javascript
// BEFORE
const response = await fetch(`/api/ml/models/${modelName}/features`);

// AFTER
const response = await fetch(`/api/ml/models/${modelName}/features`);
// Note: Need to add this endpoint to backend
```

---

## Implementation Priority

### Phase 1: Critical (Breaks Dashboard)
1. ✅ Update health check: `/api/ml/health` → `/api/ml/models/status`
2. ✅ Update drift metrics: `/api/ml/models/${model}/drift` → `/api/ml/monitoring/drift/${model}`
3. ✅ Update model list: `/api/ml/models` → `/api/ml/models/`
4. ✅ Update retraining trigger params
5. ✅ Update model activation: `activate` → `promote`
6. ✅ Update model details: direct to `/metadata`

### Phase 2: Important (Missing Features)
7. ⚠️ **Add** drift history endpoint
8. ⚠️ **Add** training history endpoint
9. ⚠️ **Add** job run/pause/resume endpoints
10. ⚠️ **Add** model comparison endpoint
11. ⚠️ **Add** feature importance endpoint

### Phase 3: Enhancement
- Add response validation
- Add error recovery
- Improve loading states

---

## Testing Checklist

### Backend API Tests
- [ ] `GET /api/ml/models/status` returns model health
- [ ] `GET /api/ml/monitoring/drift/{model}` returns drift metrics
- [ ] `GET /api/ml/models/{model}/drift/history` returns historical data
- [ ] `GET /api/ml/monitoring/training/history` returns training events
- [ ] `POST /api/ml/retraining/trigger` accepts model_name param
- [ ] `POST /api/ml/models/{model}/promote` promotes model
- [ ] `POST /api/ml/models/compare` compares models
- [ ] `GET /api/ml/models/{model}/features` returns feature importance
- [ ] `POST /api/ml/retraining/jobs/{id}/run` executes job
- [ ] `POST /api/ml/retraining/jobs/{id}/pause` pauses job

### Frontend Dashboard Tests
- [ ] Dashboard loads without errors
- [ ] Models list displays correctly
- [ ] Drift metrics update in real-time
- [ ] Drift chart renders
- [ ] Training history displays
- [ ] Retraining jobs list works
- [ ] Model comparison modal works
- [ ] Feature importance modal works
- [ ] Job controls (run/pause/resume) work
- [ ] WebSocket updates reflect changes

---

## Next Steps

1. **Add missing backend endpoints** (Phase 2 from above)
2. **Update `ml_dashboard.js`** with correct API URLs
3. **Test each endpoint** individually
4. **Test dashboard** end-to-end
5. **Update documentation** with new endpoints

---

## Estimated Work

- **Backend changes:** 2-3 hours
- **Frontend changes:** 1-2 hours  
- **Testing:** 1-2 hours
- **Total:** 4-7 hours
