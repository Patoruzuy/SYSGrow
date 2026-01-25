# ML/AI API Consolidation Summary

## Overview

Consolidated all machine learning and AI endpoints under a unified `/api/ml/*` structure. This organization improves maintainability, reduces duplication, and provides clear domain separation.

## New Structure

```
app/blueprints/api/ml_ai/
├── __init__.py          # Module exports
├── predictions.py       # AI predictions endpoints
├── models.py            # Model management endpoints
├── analytics.py         # Performance analytics endpoints
├── monitoring.py        # Monitoring and drift detection
└── retraining.py        # Model retraining workflows
```

## Endpoint Migration Map

### Predictions API (`/api/ml/predictions/*`)

**Disease Predictions:**
- `POST /api/ml/predictions/disease/risk` - Predict disease risk for specific plant
- `GET /api/ml/predictions/disease/risks` - Get disease risks with filtering (by unit_id)
- `GET /api/ml/predictions/disease/alerts` - Get active disease alerts

**Growth Stage Predictions:**
- `GET /api/ml/predictions/growth/<stage>` - Predict growth stage for plant
- `POST /api/ml/predictions/growth/transition-analysis` - Analyze growth stage transitions
- `GET /api/ml/predictions/growth/status` - Get growth prediction status

**Climate Optimization:**
- `GET /api/ml/predictions/climate/<stage>` - Get optimal climate conditions

**Health Monitoring:**
- `GET /api/ml/predictions/health/<unit_id>/recommendations` - Get health recommendations
- `POST /api/ml/predictions/health/observation` - Record health observation

### Models API (`/api/ml/models/*`)

- `GET /api/ml/models/` - List all available models
- `GET /api/ml/models/<model_name>/versions` - Get model version history
- `POST /api/ml/models/<model_name>/promote` - Promote model version to production
- `GET /api/ml/models/<model_name>/metadata` - Get model metadata
- `GET /api/ml/models/status` - Get overall model status

### Analytics API (`/api/ml/analytics/*`)

**Disease Statistics:**
- `GET /api/ml/analytics/disease/statistics` - Disease trends and statistics

**Energy Analytics:**
- `GET /api/ml/analytics/energy/actuator/<id>/dashboard` - Energy monitoring dashboard
- `GET /api/ml/analytics/energy/actuator/<id>/predict-failure` - Predict actuator failures

### Monitoring API (`/api/ml/monitoring/*`)

**Drift Detection:**
- `GET /api/ml/monitoring/drift/<model_name>` - Get model drift metrics

**Continuous Insights:**
- `GET /api/ml/monitoring/insights/<unit_id>` - Get unit-specific insights
- `GET /api/ml/monitoring/insights/critical` - Get critical insights across all units

### Retraining API (`/api/ml/retraining/*`)

- `GET /api/ml/retraining/jobs` - List all retraining jobs
- `POST /api/ml/retraining/jobs` - Schedule new retraining job
- `DELETE /api/ml/retraining/jobs/<id>` - Cancel retraining job
- `POST /api/ml/retraining/trigger` - Manually trigger retraining
- `GET /api/ml/retraining/status` - Get retraining system status

## Legacy Endpoints (Deprecated)

These endpoints remain functional but will be phased out:

### From `ai_predictions.py`:
- `/api/ai/*` - All endpoints migrated to `/api/ml/predictions/*`

### From `disease.py`:
- `/api/disease/risks` → `/api/ml/predictions/disease/risks`
- `/api/disease/alerts` → `/api/ml/predictions/disease/alerts`
- `/api/disease/statistics` → `/api/ml/analytics/disease/statistics`

### From `growth_stages.py`:
- `/api/growth-stages/predict/<stage>` → `/api/ml/predictions/growth/<stage>`
- `/api/growth-stages/transition-analysis` → `/api/ml/predictions/growth/transition-analysis`
- `/api/growth-stages/status` → `/api/ml/predictions/growth/status`

### From `insights.py`:
- `/api/insights/analytics/actuators/<id>/dashboard` → `/api/ml/analytics/energy/actuator/<id>/dashboard`
- `/api/insights/analytics/predictions/` → `/api/ml/analytics/energy/actuator/<id>/predict-failure`

### From `retraining.py`:
- `/api/retraining/*` → `/api/ml/retraining/*`

## Separation of Concerns

### What Stays Where

**Hardware Control (climate.py):**
- `/api/climate/*` - Remains separate as it's hardware control, not AI/ML

**WebSocket Events (ml_websocket.py):**
- `/ml/*` namespace - Real-time events remain in separate module

**Health API (health.py):**
- `/api/health/*` - Remains separate as it combines hardware + AI

## Implementation Details

### Dependency Injection
All endpoints use ServiceContainer for dependency injection:

```python
def _container() -> ServiceContainer:
    """Get service container from app context."""
    return current_app.config["CONTAINER"]
```

### Error Handling
Consistent error response format:

```python
def _fail(message: str, status: int = 400) -> tuple:
    """Return error response."""
    return jsonify({"error": message}), status
```

### Success Responses
Standardized success format:

```python
def _success(data, status: int = 200) -> tuple:
    """Return success response."""
    return jsonify(data), status
```

## Testing Migration

### Verification Checklist

1. **Predictions Endpoints:**
   - [ ] Disease risk prediction works
   - [ ] Growth stage prediction works
   - [ ] Climate optimization works
   - [ ] Health observation recording works

2. **Models Endpoints:**
   - [ ] Model listing works
   - [ ] Version history retrieval works
   - [ ] Model promotion works

3. **Analytics Endpoints:**
   - [ ] Disease statistics work
   - [ ] Energy dashboard works
   - [ ] Failure prediction works

4. **Monitoring Endpoints:**
   - [ ] Drift detection works
   - [ ] Unit insights work
   - [ ] Critical insights work

5. **Retraining Endpoints:**
   - [ ] Job listing works
   - [ ] Job scheduling works
   - [ ] Manual triggering works

## Benefits

1. **Clear Organization:** All ML/AI endpoints under `/api/ml/*`
2. **Domain Separation:** Predictions, models, analytics, monitoring, retraining
3. **Reduced Duplication:** Consolidated overlapping functionality
4. **Better Discoverability:** Intuitive URL structure
5. **Easier Maintenance:** Related code grouped together
6. **Consistent Patterns:** All blueprints follow same structure

## Next Steps

1. Update frontend/mobile app to use new endpoints
2. Add deprecation warnings to legacy endpoints
3. Monitor usage of legacy vs new endpoints
4. Update API documentation
5. Create client migration guide
6. Set sunset date for legacy endpoints (after 2-3 months)
7. Remove legacy endpoints after migration period

## Breaking Changes

None - all legacy endpoints remain functional during migration period.

## Rollback Plan

If issues arise:
1. Legacy endpoints remain functional
2. Can revert app/__init__.py registration
3. No data migration required
4. Services unchanged (only API routes affected)
