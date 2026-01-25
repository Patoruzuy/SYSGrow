# AI Integration Architecture Review

**Date**: December 14, 2025  
**Perspective**: Senior Engineer Review

## Executive Summary

**YES, integrating AI into the app is a good idea** — but the current structure needs significant refactoring. Your instinct about removing the data access layer and creating repositories is **correct**. This document provides a comprehensive architectural strategy.

---

## Current State Analysis

### ✅ What's Working Well

1. **Separation of Concerns**: AI models, trainers, and predictors are logically separated
2. **Type Safety**: Good use of type hints and `TYPE_CHECKING` for dependency injection
3. **Dataclasses**: Clean data structures (DiseaseRisk, ClimateConditions, etc.)
4. **Enums**: Well-defined domain concepts (DiseaseType, RiskLevel, HealthStatus)
5. **Logging**: Comprehensive logging infrastructure in place

### ❌ Critical Issues

1. **Data Access Layer Redundancy**
   - Each AI module has its own data access class (DiseaseDataAccess, PlantHealthDataAccess, MLTrainingDataAccess)
   - These duplicate query logic that already exists in repositories (analytics.py, devices.py, growth.py)
   - Violates DRY principle and creates maintenance burden

2. **Architectural Mismatch**
   - AI lives at `backend/ai/` (top-level)
   - App infrastructure uses `infrastructure/database/repositories/` pattern
   - No integration point between the two systems
   - AI modules can't easily be used by app services

3. **Dependency Injection Issues**
   - AI modules import TYPE_CHECKING but manually manage dependencies
   - No container management (you have `app/services/container.py` but AI doesn't use it)
   - Tight coupling to data access implementations

4. **Missing Service Layer**
   - AI logic is scattered across predictor, trainer, and monitor classes
   - No clear services that the API/UI can consume
   - No standardized input/output contracts

5. **Model Management**
   - Models stored in `backend/models/` (not version controlled)
   - No model registry or versioning metadata
   - Training/loading logic intertwined with prediction logic

---

## Recommended Architecture

### Phase 1: Repository Pattern for AI Data

**Location**: `infrastructure/database/repositories/ai.py` (or split by domain)

```
infrastructure/database/repositories/
├── analytics.py          (existing - sensor/environment data)
├── devices.py            (existing - device info)
├── growth.py             (existing - growth metrics)
├── settings.py           (existing)
└── ai.py                 (NEW - unified AI data access)
    ├── AIHealthDataRepository      (queries for health/disease)
    ├── AITrainingDataRepository    (queries for ML training)
    └── AIModelRepository           (model metadata & versioning)
```

**Key Benefits**:
- Reuses existing DB handler patterns
- Follows project conventions
- Single source of truth for queries
- Easy to test with mock repository

**Example Structure**:

```python
class AIHealthDataRepository:
    """Provides domain-specific queries for health/disease prediction."""
    
    def get_plant_sensor_history(self, unit_id: int, hours: int) -> List[Dict]:
        """Get sensor readings for disease pattern analysis."""
        # Query from existing sensor data tables
        
    def get_health_observations(self, unit_id: int, days: int) -> List[Dict]:
        """Get historical health labels for training."""
        # Query from health observations
```

**What to Remove**:
- ❌ `ai/data_access/disease_data.py`
- ❌ `ai/data_access/ml_training_data.py`
- ❌ `ai/data_access/plant_health_data.py`
- ❌ `ai/data_access/energy_data.py`
- ❌ `ai/data_access/environment_data.py`

---

### Phase 2: Convert Models to Services

**Location**: `app/services/ai/` (new domain)

```
app/services/
├── application/           (existing)
├── hardware/             (existing)
├── ai/                   (NEW)
│   ├── __init__.py
│   ├── disease_prediction_service.py
│   ├── plant_health_service.py
│   ├── climate_optimization_service.py
│   ├── ml_training_service.py
│   ├── model_registry_service.py
│   └── model_drift_service.py
```

**Conversion Rules**:

| Old Module | New Service | Responsibility |
|---|---|---|
| `disease_predictor.py` | `DiseasePredictor` | Predict disease risk from sensor data |
| `plant_health_monitor.py` | `PlantHealthMonitor` | Track plant health status |
| `ml_model.py` | `ClimateOptimizer` | Predict optimal climate conditions |
| `ml_trainer.py` | `MLTrainer` | Handle model training & retraining |
| `model_drift_detector.py` | `ModelDriftDetector` | Monitor model performance drift |
| `model_registry.py` | `ModelRegistry` | Manage model versioning & storage |

**Service Contract Example**:

```python
class DiseasePredictor:
    """Predicts disease risk for plants."""
    
    def __init__(
        self, 
        repo_ai: "AIHealthDataRepository",
        repo_analytics: "AnalyticsRepository",
        model_registry: "ModelRegistry"
    ):
        self.repo_ai = repo_ai
        self.repo_analytics = repo_analytics
        self.models = model_registry
    
    async def predict_disease_risk(
        self, 
        unit_id: int
    ) -> DiseaseRiskAssessment:
        """
        Predict disease risk for a unit.
        
        Returns:
            DiseaseRiskAssessment with disease type, risk level, and recommendations
        """
        # Load sensor history from repo
        # Run through ML model
        # Return typed result
```

**Key Principles**:
- Services depend on repositories, NOT data access classes
- Services are registered in `app/services/container.py`
- All I/O through typed dataclasses
- Services handle business logic; repositories handle data access

---

### Phase 3: Model Management Refactoring

**Current Problem**:
- Models stored as `.pkl` files in `backend/models/`
- No versioning, metadata, or lifecycle tracking
- Training logic scattered across files

**Proposed Structure**:

```
models/
├── registry.json          (model inventory & versions)
├── v1/
│   ├── disease_predictor.pkl
│   ├── metadata.json      (training date, metrics, features)
│   └── scaler.pkl
├── v2/
│   ├── disease_predictor.pkl
│   ├── metadata.json
│   └── scaler.pkl
└── current -> v2          (symlink to active version)
```

**ModelRegistry Service** (`model_registry_service.py`):
```python
class ModelRegistry:
    """Manages model versioning, loading, and lifecycle."""
    
    def load_model(self, model_name: str) -> Any:
        """Load current active model version."""
        
    def save_model(self, name: str, model: Any, metrics: Dict) -> str:
        """Save model and return version ID."""
        
    def list_versions(self, model_name: str) -> List[ModelMetadata]:
        """List all versions of a model."""
        
    def promote_version(self, model_name: str, version: str) -> None:
        """Promote a version to production."""
```

---

### Phase 4: Data Pipeline & Training Orchestration

**New Service**: `MLTrainingService`

```python
class MLTrainingService:
    """Orchestrates ML model training and retraining."""
    
    def __init__(
        self,
        repo_ai: "AITrainingDataRepository",
        model_registry: "ModelRegistry",
        config_service: "ConfigService"
    ):
        pass
    
    async def train_disease_model(self, retrain: bool = False) -> TrainingResult:
        """
        Collect data, train model, validate, save version.
        
        Returns:
            TrainingResult with metrics and version ID
        """
        # Collect training data from repository
        # Feature engineering
        # Train/validate
        # Save to registry
        # Return result
    
    async def schedule_periodic_training(self) -> None:
        """Run on schedule (once per week, etc.)."""
```

---

## Integration Points

### 1. API Endpoints

**New Blueprint**: `app/blueprints/ai_predictions.py`

```python
@bp.post('/units/<int:unit_id>/health/disease-risk')
def predict_disease_risk(unit_id: int):
    """Predict disease risk for a unit."""
    predictor = container.get(DiseasePredictor)
    result = predictor.predict_disease_risk(unit_id)
    return result.to_dict(), 200
```

### 2. WebSocket Events

**New Handler**: `app/socketio_handlers.py` extension

```python
@socketio.on('request_health_analysis', namespace='/health')
def analyze_health(data):
    """Real-time health analysis via WebSocket."""
    analyzer = container.get(PlantHealthMonitor)
    result = analyzer.analyze(data['unit_id'])
    emit('health_analysis_result', result.to_dict())
```

### 3. Worker Tasks

**New Worker**: `app/workers/ai_training_worker.py`

```python
@schedule_task(cron='0 2 * * 0')  # Weekly at 2 AM
def retrain_models():
    """Periodic retraining task."""
    trainer = container.get(MLTrainingService)
    result = trainer.train_disease_model(retrain=True)
    log_training_result(result)
```

---

## File Migration Strategy

### Step 1: Create Repository Layer
```
✓ Create infrastructure/database/repositories/ai.py
✓ Implement AIHealthDataRepository with methods from disease_data.py
✓ Implement AITrainingDataRepository with methods from ml_training_data.py
```

### Step 2: Create Service Layer
```
✓ Create app/services/ai/ directory
✓ Move disease_predictor.py → DiseasePredictor service
✓ Move plant_health_monitor.py → PlantHealthMonitor service
✓ Move ml_model.py → ClimateOptimizer service
✓ Update imports to use repositories instead of data_access
```

### Step 3: Model Management
```
✓ Create ModelRegistry service
✓ Migrate models to versioned structure
✓ Update all model loading/saving calls
```

### Step 4: Container Wiring
```
✓ Register all services in app/services/container.py
✓ Inject repositories into services
✓ Test dependency resolution
```

### Step 5: API Integration
```
✓ Create API blueprints using services
✓ Add WebSocket handlers
✓ Add background workers
```

### Step 6: Cleanup
```
✓ Delete old ai/data_access/ directory
✓ Keep ai/ directory for model storage & utility functions
✓ Consider renaming to app/modules/ai/ or similar for consistency
```

---

## Why This Approach is Better

### 1. **Single Responsibility**
   - Repositories: Data access only
   - Services: Business logic only
   - Models: Pure ML code
   - Follows your existing patterns (you already have this with analytics repository)

### 2. **Testability**
   - Mock repositories easily
   - Test services independently
   - No database calls in unit tests

### 3. **Reusability**
   - Services can be used by APIs, WebSockets, workers, or other services
   - Models can be shared across multiple services

### 4. **Maintainability**
   - Changes to data access isolated to repository
   - Changes to business logic isolated to service
   - Clear interfaces and contracts

### 5. **Scalability**
   - Easy to add new AI features as new services
   - Model registry supports A/B testing and canary deployments
   - Background workers can handle long-running training

### 6. **Consistency**
   - Matches your existing architecture (repositories + services)
   - Uses same patterns as hardware, analytics, devices
   - Developers have clear mental model

---

## Risk Mitigation

### High Priority
1. **Database Schema Compatibility**
   - Ensure AI queries work with existing tables
   - May need to add indexes for performance
   - Test query performance with large datasets

2. **Model Backward Compatibility**
   - Current models must load with new registry
   - Plan migration path for existing trained models
   - Version all models before refactoring

3. **Feature Consistency**
   - Feature engineering in ml_trainer.py must match predictor.py
   - Create shared feature engineering module: `app/services/ai/feature_engineering.py`
   - Unit test feature consistency

### Medium Priority
1. **Performance**
   - AI predictions may need caching
   - Consider Redis for frequently accessed predictions
   - Profile query performance with realistic data

2. **Model Training Time**
   - Long training could block workers
   - Use async/background jobs
   - Set timeout limits

3. **Data Quality**
   - Ensure sufficient training data before first run
   - Monitor for data drift
   - Implement data validation in repository

---

## Implementation Checklist

- [ ] **Phase 1**: Create AIRepository
  - [ ] Define `AIHealthDataRepository` interface
  - [ ] Define `AITrainingDataRepository` interface
  - [ ] Implement methods from existing data_access classes
  - [ ] Add unit tests for repository methods

- [ ] **Phase 2**: Create Services
  - [ ] Create `DiseasePredictor` service
  - [ ] Create `PlantHealthMonitor` service
  - [ ] Create `ClimateOptimizer` service
  - [ ] Create `MLTrainer` service
  - [ ] Create `ModelRegistry` service
  - [ ] Add unit tests for each service

- [ ] **Phase 3**: Model Management
  - [ ] Create model versioning structure
  - [ ] Implement `ModelRegistry` with CRUD
  - [ ] Migrate existing models to v1
  - [ ] Test model loading from new structure

- [ ] **Phase 4**: Container & DI
  - [ ] Register services in container
  - [ ] Test dependency resolution
  - [ ] Verify container initialization

- [ ] **Phase 5**: API Integration
  - [ ] Create AI prediction blueprint
  - [ ] Add health analysis endpoints
  - [ ] Add model management endpoints
  - [ ] Test end-to-end

- [ ] **Phase 6**: Cleanup
  - [ ] Delete old data_access directory
  - [ ] Update documentation
  - [ ] Run full test suite

---

## Conclusion

Your instinct is **spot-on**. Removing the data access layer and creating a proper repository + service architecture will:

✅ Eliminate redundancy  
✅ Improve testability  
✅ Align with existing patterns  
✅ Make the code more reusable  
✅ Facilitate future scaling  

The effort is moderate (2-3 days of focused work), but the payoff is significant: a clean, maintainable AI integration that feels native to your app architecture.

Start with Phase 1 (repositories) — that's the foundation everything else depends on. Then tackle services phase by phase. The beauty of this approach is that you can do it incrementally without breaking anything.
