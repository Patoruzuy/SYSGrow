# ML Services Enhancement Plan

> Following completion of the 6-phase Irrigation ML Implementation, these enhancements will improve overall AI/ML integration across the SYSGrow platform.

## Status: ✅ ALL ENHANCEMENTS COMPLETE

| Enhancement | Priority | Complexity | Impact | Status |
|------------|----------|------------|--------|--------|
| 1. PersonalizedLearning → ClimateOptimizer/DiseasePredictor | High | Medium | High | ✅ COMPLETE |
| 2. DiseasePredictor ML Training | High | High | High | ✅ COMPLETE |
| 3. Plant-Specific Model Fine-tuning from Harvests | Medium | Medium | High | ✅ COMPLETE |
| 4. ContinuousMonitor → NotificationsService Integration | Medium | Low | Medium | ✅ COMPLETE |

---

## Enhancement 1: Wire PersonalizedLearningService Integration ✅ COMPLETE

### Current State Analysis
- **PersonalizedLearningService** (`personalized_learning.py`): Fully implemented with:
  - `EnvironmentProfile` creation and storage
  - `GrowingSuccess` recording
  - `get_personalized_recommendations()` method
  - Past success analysis and similar grower matching
  
- **ClimateOptimizer** (`climate_optimizer.py`): ✅ Now has personalized_learning DI
  - Added `get_personalized_conditions()` method
  - Applies user-specific adjustments with confidence boost
  
- **DiseasePredictor** (`disease_predictor.py`): ✅ Now has personalized_learning DI
  - Added `_get_historical_risk_multipliers()` method
  - Applies risk multipliers based on user's challenge history
  - Missing: Historical success/failure pattern integration

### Proposed Changes

#### A. Update ClimateOptimizer to use PersonalizedLearningService

```python
# In ClimateOptimizer.__init__()
def __init__(
    self,
    analytics_repo: "AnalyticsRepository",
    model_registry: Optional["ModelRegistry"] = None,
    personalized_learning: Optional["PersonalizedLearningService"] = None,  # NEW
):
    self.personalized_learning = personalized_learning
```

```python
# New method in ClimateOptimizer
def get_personalized_conditions(
    self,
    unit_id: int,
    plant_type: str,
    plant_stage: str,
    current_conditions: Dict[str, float]
) -> Optional[ClimateConditions]:
    """Get personalized climate conditions using user profile."""
    
    # Get base prediction
    base_conditions = self.predict_conditions(plant_stage)
    
    if not self.personalized_learning:
        return base_conditions
    
    # Get personalized adjustments
    personalized = self.personalized_learning.get_personalized_recommendations(
        unit_id=unit_id,
        plant_type=plant_type,
        growth_stage=plant_stage,
        current_conditions=current_conditions
    )
    
    if base_conditions and personalized:
        return ClimateConditions(
            temperature=personalized.get('temperature', base_conditions.temperature),
            humidity=personalized.get('humidity', base_conditions.humidity),
            soil_moisture=personalized.get('soil_moisture', base_conditions.soil_moisture),
            confidence=base_conditions.confidence * 1.2  # Boost confidence with personalization
        )
    
    return base_conditions
```

#### B. Update DiseasePredictor to use PersonalizedLearningService

```python
# In DiseasePredictor.__init__()
def __init__(
    self,
    repo_health: "AIHealthDataRepository",
    model_registry: Optional["ModelRegistry"] = None,
    personalized_learning: Optional["PersonalizedLearningService"] = None,  # NEW
):
    self.personalized_learning = personalized_learning
```

```python
# New method in DiseasePredictor
def _get_historical_disease_patterns(self, unit_id: int, plant_type: str) -> Dict[str, Any]:
    """Get historical disease issues from user's environment profile."""
    if not self.personalized_learning:
        return {}
    
    profile = self.personalized_learning.get_profile(unit_id)
    if not profile:
        return {}
    
    # Check challenge areas for disease-related issues
    disease_history = {
        'recurring_issues': [],
        'risk_multipliers': {}
    }
    
    for challenge in profile.challenge_areas:
        if 'fungal' in challenge.lower():
            disease_history['recurring_issues'].append('fungal')
            disease_history['risk_multipliers']['fungal'] = 1.3
        elif 'bacterial' in challenge.lower():
            disease_history['recurring_issues'].append('bacterial')
            disease_history['risk_multipliers']['bacterial'] = 1.3
        elif 'pest' in challenge.lower():
            disease_history['recurring_issues'].append('pest')
            disease_history['risk_multipliers']['pest'] = 1.3
    
    return disease_history
```

#### C. Update service_factory.py to wire dependencies

```python
# In service creation
personalized_learning = PersonalizedLearningService(
    model_registry=model_registry,
    training_data_repo=training_data_repo
)

climate_optimizer = ClimateOptimizer(
    analytics_repo=analytics_repo,
    model_registry=model_registry,
    personalized_learning=personalized_learning  # NEW
)

disease_predictor = DiseasePredictor(
    repo_health=health_repo,
    model_registry=model_registry,
    personalized_learning=personalized_learning  # NEW
)
```

---

## Enhancement 2: DiseasePredictor ML Training ✅ COMPLETE

### Implementation Summary
- ✅ Created Migration 029 (`029_disease_tracking.py`) with:
  - `DiseaseOccurrence` table with full environmental snapshot
  - `DiseasePredictionFeedback` table for accuracy tracking
  - 7 indexes for efficient querying
  
- ✅ Added AITrainingDataRepository methods:
  - `get_disease_occurrence_training_data()` - Query disease data for ML
  - `get_disease_prediction_feedback()` - Get prediction outcomes
  - `save_disease_occurrence()` - Record new disease incidents
  - `save_disease_prediction_feedback()` - Store prediction results
  - `get_disease_prediction_accuracy()` - Calculate precision/recall/F1

- ✅ Implemented `train_disease_model()` in MLTrainerService:
  - Uses DiseaseOccurrence data as positive examples
  - Generates synthetic healthy period samples as negatives
  - Trains GradientBoostingClassifier
  - Reports accuracy, CV scores, per-class metrics

- ✅ Updated DiseasePredictor with hybrid ML+rules approach:
  - `_predict_with_ml()` - ML-based prediction
  - Falls back to rule-based if no ML model
  - Avoids duplicate risk assessments
  - Added `_get_recommendations_for_disease()` helper

### Current State Analysis
- **DiseasePredictor** is currently ~90% rule-based:
  - `_assess_fungal_risk()` - hardcoded thresholds (humidity > 80, etc.)
  - `_assess_bacterial_risk()` - hardcoded thresholds
  - `_assess_pest_risk()` - hardcoded thresholds
  - No ML model training in `MLTrainerService`
  - `load_models()` attempts to load from registry but no training exists

### Proposed Changes

#### A. Add Disease Training Data Collection (Migration 029)

```sql
-- New table for disease occurrence tracking
CREATE TABLE disease_occurrences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    unit_id INTEGER NOT NULL,
    plant_id INTEGER,
    disease_type TEXT NOT NULL,  -- fungal, bacterial, pest, nutrient
    severity TEXT NOT NULL,  -- mild, moderate, severe
    detected_at TIMESTAMP NOT NULL,
    environmental_snapshot JSON,  -- temp, humidity, etc. at detection
    confirmed_by_user BOOLEAN DEFAULT FALSE,
    treatment_applied TEXT,
    resolved_at TIMESTAMP,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (unit_id) REFERENCES units(id),
    FOREIGN KEY (plant_id) REFERENCES plants(id)
);

-- Predicted vs actual tracking for model improvement
CREATE TABLE disease_prediction_feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prediction_id TEXT UNIQUE,  -- UUID
    unit_id INTEGER NOT NULL,
    predicted_disease_type TEXT,
    predicted_risk_level TEXT,
    predicted_risk_score REAL,
    prediction_timestamp TIMESTAMP,
    actual_disease_occurred BOOLEAN,
    actual_disease_type TEXT,
    feedback_timestamp TIMESTAMP,
    days_to_occurrence INTEGER,  -- if disease occurred, how many days later
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### B. Add Training Methods to MLTrainerService

```python
def train_disease_classifier_model(self) -> Optional[str]:
    """
    Train disease type classifier from historical occurrences.
    
    Features: temp_avg, humidity_avg, soil_moisture_avg, temp_variance, 
              humidity_variance, days_in_stage, season
    Target: disease_type (fungal, bacterial, pest, none)
    """
    
def train_disease_risk_model(self) -> Optional[str]:
    """
    Train disease risk scorer using prediction feedback.
    
    Features: environmental features + predicted_risk
    Target: actual_disease_occurred (binary)
    Model: GradientBoostingClassifier for calibrated probabilities
    """
```

#### C. Add Hybrid Prediction in DiseasePredictor

```python
def predict_disease_risk(self, ...):
    """Hybrid: ML prediction + rule-based fallback."""
    
    # Try ML prediction first
    if self._ml_model_available():
        ml_risks = self._predict_with_ml(unit_id, current_conditions)
        # Combine with rule-based for robustness
        rule_risks = self._predict_with_rules(...)
        return self._merge_predictions(ml_risks, rule_risks)
    
    # Fallback to pure rule-based
    return self._predict_with_rules(...)
```

---

## Enhancement 3: Plant-Specific Model Fine-tuning from Harvests ✅ COMPLETE

### Implementation Summary
- ✅ Added AITrainingDataRepository methods:
  - `get_harvest_training_data()` - Fetches harvest outcomes with conditions
  - `get_optimal_conditions_by_plant_type()` - Calculates optimal ranges from top harvests

- ✅ Implemented MLTrainerService fine-tuning:
  - `fine_tune_for_plant_type()` - Entry point for plant-specific tuning
  - `_fine_tune_climate_model()` - Learns optimal conditions from best harvests
  - `_fine_tune_growth_model()` - Learns growth duration from conditions
  - `fine_tune_all_plant_types()` - Batch fine-tune for all eligible plants

- ✅ Updated ClimateOptimizer to use plant-specific models:
  - `predict_conditions()` accepts `plant_type` parameter
  - `_try_load_specialized_model()` checks for plant-specific models
  - Falls back to general model if no specialization exists

### Current State Analysis
- **GrowingSuccess** dataclass exists in `PersonalizedLearningService`
- `record_success()` saves harvest outcomes to disk (JSON)
- No connection to model training pipeline
- Harvest data includes: `total_yield`, `quality_rating`, `growth_conditions`

### Proposed Changes

#### A. Create Harvest Outcome Repository Methods

```python
# In AITrainingDataRepository
def get_harvest_training_data(
    self,
    plant_type: Optional[str] = None,
    min_quality: int = 3,
    days_limit: int = 365
) -> pd.DataFrame:
    """
    Get harvest outcomes for model fine-tuning.
    
    Returns DataFrame with:
    - plant_type, variety
    - growth_conditions (expanded to columns)
    - yield_grams, quality_rating
    - days_to_harvest
    - user conditions adjustments
    """
```

#### B. Add Plant-Specific Fine-tuning in MLTrainerService

```python
def fine_tune_for_plant_type(
    self,
    base_model_name: str,
    plant_type: str,
    min_samples: int = 10
) -> Optional[str]:
    """
    Fine-tune a base model using plant-specific harvest outcomes.
    
    This creates personalized models like:
    - climate_optimizer_tomato
    - irrigation_predictor_pepper
    - growth_predictor_lettuce
    
    Args:
        base_model_name: Base model to fine-tune (e.g., 'climate_optimizer')
        plant_type: Plant type to specialize for
        min_samples: Minimum harvest records needed
        
    Returns:
        Fine-tuned model name or None if insufficient data
    """
    # Get harvest data for this plant type
    harvest_data = self.training_data_repo.get_harvest_training_data(
        plant_type=plant_type,
        min_quality=3  # Only learn from successful grows
    )
    
    if len(harvest_data) < min_samples:
        logger.info(f"Insufficient data for {plant_type} fine-tuning: {len(harvest_data)}/{min_samples}")
        return None
    
    # Load base model
    base_model = self.model_registry.load_model(base_model_name)
    
    # Fine-tune (transfer learning approach)
    # ... sklearn partial_fit or new model with pretrained weights
```

#### C. Model Selection at Prediction Time

```python
# In ClimateOptimizer.predict_conditions()
def predict_conditions(self, plant_stage: str, plant_type: Optional[str] = None, ...):
    # Try plant-specific model first
    if plant_type:
        specialized_model = self.model_registry.load_model(f"climate_optimizer_{plant_type}")
        if specialized_model:
            return self._predict_with_model(specialized_model, plant_stage)
    
    # Fall back to general model
    return self._predict_with_model(self._model, plant_stage)
```

---

## Enhancement 4: ContinuousMonitor → NotificationsService Integration ✅ COMPLETE

### Implementation Summary
- **ContinuousMonitoringService** (`continuous_monitor.py`):
  - ✅ Added `set_notification_service()` method
  - ✅ Added `_send_critical_notification()` for urgent alerts
  - ✅ Added `_send_insight_notification()` for warnings (respects throttling)
  - ✅ Wired to NotificationsService in `container_builder.py`

- **NotificationsService** (`notifications_service.py`):
  - ✅ Now receives AI-generated insights
  - Uses existing `plant_health_warning` notification type
  - Respects user preferences, quiet hours, throttling

### Proposed Changes

#### A. Add Notification Callback in ContinuousMonitor Initialization

```python
# In ContinuousMonitoringService
def set_notification_callback(
    self,
    notifications_service: "NotificationsService",
    user_resolver: Callable[[int], Optional[int]]  # unit_id -> user_id
):
    """
    Wire up notifications service for alert delivery.
    
    Args:
        notifications_service: The notifications service instance
        user_resolver: Function to get user_id from unit_id
    """
    self._notifications_service = notifications_service
    self._user_resolver = user_resolver
    
    # Set callbacks
    self._on_critical_alert = self._send_critical_notification
    self._on_new_insight = self._send_insight_notification
```

#### B. Add Notification Sending Methods

```python
def _send_critical_notification(self, insight: GrowingInsight):
    """Send critical alert as push notification."""
    if not self._notifications_service:
        return
    
    user_id = self._user_resolver(insight.unit_id)
    if not user_id:
        return
    
    self._notifications_service.send_notification(
        user_id=user_id,
        notification_type="plant_health_warning",
        title=f"🚨 {insight.title}",
        message=insight.description,
        severity="critical",
        source_type="ai_monitor",
        unit_id=insight.unit_id,
        requires_action=True,
        action_type="view_insight",
        action_data={"insight_data": insight.data}
    )

def _send_insight_notification(self, insight: GrowingInsight):
    """Send non-critical insights (respects throttling)."""
    if not self._notifications_service:
        return
    
    # Only notify for warnings and above
    if insight.alert_level == AlertLevel.INFO:
        return
    
    user_id = self._user_resolver(insight.unit_id)
    if not user_id:
        return
    
    severity = "warning" if insight.alert_level == AlertLevel.WARNING else "info"
    
    self._notifications_service.send_notification(
        user_id=user_id,
        notification_type="plant_health_warning",
        title=insight.title,
        message=insight.description,
        severity=severity,
        source_type="ai_monitor",
        unit_id=insight.unit_id,
        requires_action=len(insight.action_items) > 0,
        action_type="view_insight" if insight.action_items else None,
        action_data={"insight_data": insight.data} if insight.data else None
    )
```

#### C. Wire in Service Factory

```python
# After creating both services
continuous_monitor.set_notification_callback(
    notifications_service=notifications_service,
    user_resolver=lambda unit_id: unit_repo.get_user_id_for_unit(unit_id)
)
```

---

## Implementation Order

Recommended sequence based on dependencies and impact:

### Phase A: Quick Win (Enhancement 4) ✅ COMPLETE
**ContinuousMonitor → NotificationsService Integration**
- ✅ Added `set_notification_service()` method
- ✅ Added `_send_critical_notification()` and `_send_insight_notification()`
- ✅ Wired in `container_builder.py` with user resolver

### Phase B: Core Integration (Enhancement 1) ✅ COMPLETE
**PersonalizedLearning → ClimateOptimizer/DiseasePredictor**
- ✅ Added `personalized_learning` DI to both services
- ✅ Added `get_personalized_conditions()` to ClimateOptimizer
- ✅ Added `_get_historical_risk_multipliers()` to DiseasePredictor
- ✅ Wired in `container_builder.py`

### Phase C: Harvest Learning (Enhancement 3) 🔵 READY
**Plant-Specific Model Fine-tuning**
- Medium complexity
- Requires harvest data collection improvements
- Creates specialized models
- Estimated: 6-8 hours

### Phase D: Advanced ML (Enhancement 2) 🔵 READY
**DiseasePredictor ML Training**
- Highest complexity
- Requires new database migration
- New training pipeline
- Estimated: 8-12 hours

---

## Files Modified

| File | Enhancement(s) | Status |
|------|---------------|--------|
| `app/services/ai/climate_optimizer.py` | 1 | ✅ PersonalizedLearning DI, `get_personalized_conditions()` |
| `app/services/ai/disease_predictor.py` | 1 | ✅ PersonalizedLearning DI, history multipliers |
| `app/services/ai/continuous_monitor.py` | 4 | ✅ NotificationsService integration |
| `app/services/container_builder.py` | 1, 4 | ✅ Service wiring |
| `app/services/ai/continuous_monitor.py` | 4 | Add notification callbacks |
| `app/services/ai/personalized_learning.py` | 3 | Connect to harvest outcomes |
| `app/services/ai/ml_trainer.py` | 2, 3 | Add disease training, fine-tuning methods |
| `infrastructure/database/repositories/ai.py` | 2, 3 | Add training data queries |
| `app/core/service_factory.py` | 1, 4 | Wire new dependencies |
| `infrastructure/database/migrations/029_*.py` | 2 | Disease tracking tables |

---

## Success Metrics

After implementation, measure:

1. **Personalization Adoption**: % of units with EnvironmentProfile
2. **Prediction Accuracy**: Disease prediction vs actual occurrences
3. **Fine-tuning Coverage**: % of plant types with specialized models
4. **Notification Engagement**: Open rate for AI-generated alerts
5. **User Retention**: Compare active users before/after enhancements
