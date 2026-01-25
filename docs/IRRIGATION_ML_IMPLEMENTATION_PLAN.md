# Irrigation ML Learning System - Implementation Plan

## 📋 Executive Summary

This document outlines the complete implementation plan for integrating Machine Learning into the SYSGrow irrigation workflow. The system will learn from user behavior, feedback, and environmental conditions to optimize irrigation decisions automatically.

**Key Objectives:**
1. Create a dedicated `IrrigationPredictor` ML service
2. Connect irrigation workflow data to the ML training pipeline
3. Implement smart threshold adjustments using Bayesian learning
4. Add data readiness detection with user notifications
5. Enable model activation on user consent

---

## ✅ Implementation Progress

| Phase | Description | Status | Completed |
|-------|-------------|--------|-----------|
| Phase 1 | Data Collection Enhancement | ✅ COMPLETE | 2026-01 |
| Phase 2 | ML Readiness Service | ✅ COMPLETE | 2026-01 |
| Phase 3 | Irrigation Predictor Service | ✅ COMPLETE | 2026-01 |
| Phase 4 | Bayesian Threshold Adjustment | ✅ COMPLETE | 2026-01 |
| Phase 5 | Training Integration | ✅ COMPLETE | 2026-01 |
| Phase 6 | API & Scheduling | ✅ COMPLETE | 2026-01 |

### Phase 1 Deliverables (Completed)
- ✅ Migration 028: Added environmental context columns to `PendingIrrigationRequest`
- ✅ Added ML activation columns to `IrrigationWorkflowConfig`
- ✅ Updated `create_pending_irrigation_request` to accept ML context
- ✅ Created `IrrigationMLRepository` with training data access methods
- ✅ Updated `IrrigationWorkflowService.detect_irrigation_need()` with context
- ✅ Updated `ClimateControlService` to pass environmental context
- ✅ Updated `ControlLogic.control_soil_moisture()` to pass ML fields
- ✅ All tests passing

### Phase 2 Deliverables (Completed)
- ✅ Created `MLReadinessMonitorService` in `app/services/ai/ml_readiness_monitor.py`
- ✅ Added `ModelReadinessStatus` and `IrrigationMLReadiness` dataclasses
- ✅ Added notification types: `ML_MODEL_READY`, `ML_MODEL_ACTIVATED`
- ✅ Created API endpoints in `app/blueprints/api/ml_ai/readiness.py`
  - GET `/api/ml/readiness/irrigation/<unit_id>` - Check model readiness
  - POST `.../<unit_id>/activate/<model_name>` - Activate model
  - POST `.../<unit_id>/deactivate/<model_name>` - Deactivate model
  - GET `.../<unit_id>/status` - Get activation status
  - POST `/api/ml/readiness/check-all` - Check all units
- ✅ Registered `readiness_bp` blueprint in Flask app
- ✅ Added `ml_readiness_check_task` scheduled task (runs daily at 10:00)
- ✅ Task registered as `ml.readiness_check` in scheduler
- ✅ All imports and syntax validated

### Phase 3 Deliverables (Completed)
- ✅ Created `IrrigationPredictor` service in `app/services/ai/irrigation_predictor.py`
- ✅ Implemented dataclasses:
  - `IrrigationPrediction` - Comprehensive prediction result
  - `ThresholdPrediction` - Optimal soil moisture threshold
  - `DurationPrediction` - Optimal irrigation duration
  - `TimingPrediction` - Preferred irrigation time
  - `UserResponsePrediction` - User response probabilities
- ✅ Implemented prediction methods:
  - `predict_threshold()` - Bayesian threshold optimization from feedback
  - `predict_user_response()` - User behavior prediction
  - `predict_duration()` - Duration learning from before/after moisture
  - `predict_timing()` - Preferred time learning from approval patterns
  - `get_comprehensive_prediction()` - Combined prediction with recommendations
- ✅ Added `IRRIGATION_FEATURES_V1` to `FeatureEngineer`
- ✅ Added `create_irrigation_features()` method to `FeatureEngineer`
- ✅ Exported all classes from `app/services/ai/__init__.py`
- ✅ All imports and syntax validated

### Phase 4 Deliverables (Completed)
- ✅ Created `BayesianThresholdAdjuster` in `app/services/ai/bayesian_threshold.py`
- ✅ Implemented dataclasses:
  - `ThresholdBelief` - Bayesian belief with mean, variance, confidence
  - `AdjustmentResult` - Adjustment recommendation with reasoning
- ✅ Implemented Bayesian Normal-Normal conjugate prior updates:
  - `get_prior()` - Initialize from plant type + growth stage
  - `get_belief()` - Load/cache current belief state
  - `update_from_feedback()` - Posterior update from user feedback
  - `calculate_adaptive_adjustment()` - Confidence-scaled adjustments
- ✅ Key features:
  - Explore-exploit tradeoff: large adjustments when uncertain, small when confident
  - User consistency weighting: reliable users have more influence
  - Credible intervals for uncertainty quantification
  - Persistence to database for state recovery
- ✅ Migration 029: Added `threshold_belief_json`, `threshold_variance`, `threshold_sample_count` to `IrrigationUserPreference`
- ✅ Added `update_threshold_belief()` to database operations and repository
- ✅ Integrated with `IrrigationWorkflowService.handle_feedback()`:
  - Uses Bayesian adjuster when available (falls back to fixed ±5%)
  - Returns learning info in response (confidence, reasoning)
- ✅ Exported `BayesianThresholdAdjuster`, `ThresholdBelief`, `AdjustmentResult`
- ✅ All imports and syntax validated

### Phase 5 Deliverables (Completed)
- ✅ Added irrigation training methods to `MLTrainerService`:
  - `train_irrigation_threshold_model()` - Learns optimal thresholds from feedback
  - `train_irrigation_response_model()` - Predicts user approve/delay/cancel
  - `train_irrigation_duration_model()` - Learns optimal watering duration
- ✅ Added data collection helpers:
  - `_collect_irrigation_threshold_data()` - Gathers feedback + context
  - `_collect_irrigation_response_data()` - Gathers response patterns
  - `_collect_irrigation_duration_data()` - Gathers duration outcomes
  - `_calculate_optimal_threshold_from_feedback()` - Derives targets from feedback
- ✅ Added training data repository methods in `AITrainingDataRepository`:
  - `get_irrigation_threshold_training_data()` - SQL query for threshold model
  - `get_irrigation_response_training_data()` - SQL query for response model
  - `get_irrigation_duration_training_data()` - SQL query for duration model
- ✅ Updated `AutomatedRetrainingService._run_retraining()` with irrigation model types:
  - `irrigation_threshold`, `irrigation_response`, `irrigation_duration`
- ✅ Added `setup_irrigation_retraining_jobs()` method with default schedules:
  - Threshold: Weekly on Monday at 03:00
  - Response: Weekly on Monday at 03:30
  - Duration: Monthly on 1st at 04:00
- ✅ Updated `retrain_all_models()` to include irrigation models
- ✅ All imports and methods validated

### Phase 6 Deliverables (Completed)
- ✅ Added irrigation prediction API endpoints to `predictions.py`:
  - `GET /api/ml/predictions/irrigation/<unit_id>` - Comprehensive predictions
  - `GET /api/ml/predictions/irrigation/<unit_id>/threshold` - Threshold only
  - `GET /api/ml/predictions/irrigation/<unit_id>/timing` - Timing only
  - `GET /api/ml/predictions/irrigation/<unit_id>/response` - Response prediction
  - `GET /api/ml/predictions/irrigation/<unit_id>/duration` - Duration prediction
- ✅ Verified existing readiness endpoints in `readiness.py`:
  - `GET /api/ml/readiness/irrigation/<unit_id>` - ML readiness status
  - `POST /api/ml/readiness/irrigation/<unit_id>/activate/<model>` - Activate model
  - `POST /api/ml/readiness/irrigation/<unit_id>/deactivate/<model>` - Deactivate
  - `GET /api/ml/readiness/irrigation/<unit_id>/status` - Activation status
  - `POST /api/ml/readiness/check-all` - Check all units
- ✅ Verified scheduled task `ml.readiness_check` in `scheduled_tasks.py`:
  - Runs daily to check training data progress
  - Sends notifications when models are ready
  - Registered in `register_all_tasks()`
- ✅ Fixed syntax error in `ml_readiness_monitor.py`
- ✅ All endpoints validated and working

Additional endpoints:
- ✅ `GET /api/ml/predictions/irrigation/<unit_id>/next` - next irrigation prediction (dry-down model)

---

## ✅ Reliability + Manual Mode Additions (2026-01)

These changes improve diagnostics and make the workflow safe in production. They are implemented and now feed the ML roadmap.

- ✅ Added telemetry tables: `IrrigationExecutionLog`, `IrrigationEligibilityTrace`
- ✅ Added manual mode support: `ManualIrrigationLog`, `PlantIrrigationModel`
- ✅ Added concurrency safety: `claim_due_requests()` + `IrrigationLock`
- ✅ Non-blocking execution with completion + post-capture interval jobs
- ✅ Attribution logic to separate timing vs. volume issues
- ✅ Valve + pump safe sequence with interlocks
- ✅ Configurable stale reading window and cooldown (env overrides)

## 📊 Current Data Collection Status

### Data Already Being Collected ✅

| Data Point | Location | Status |
|------------|----------|--------|
| User response type (approve/delay/cancel) | `IrrigationUserPreference` | ✅ Collected |
| Response time (seconds) | `IrrigationUserPreference.avg_response_time_seconds` | ✅ Collected |
| Approval/delay/cancel counts | `IrrigationUserPreference` | ✅ Collected |
| Feedback (too_little/just_right/too_much + timing) | `IrrigationUserPreference` + feedback records | ✅ Collected |
| Preference score (-1 to +1) | `PendingIrrigationRequest.ml_preference_score` | ✅ Collected |
| Soil moisture + threshold at trigger | `PendingIrrigationRequest` + `IrrigationExecutionLog` | ✅ Collected |
| Execution duration (planned + actual) | `PendingIrrigationRequest` + `IrrigationExecutionLog` | ✅ Collected |
| Post-watering moisture + delta | `IrrigationExecutionLog.post_moisture` | ✅ Collected (duration optimizer uses this) |
| Eligibility decisions + skip reasons | `IrrigationEligibilityTrace` | ✅ Collected |
| Manual irrigation events | `ManualIrrigationLog` | ✅ Collected |
| Dry-down rate + confidence | `PlantIrrigationModel` | ✅ Collected |
| Environmental context (temp/humidity/VPD/lux) | `PendingIrrigationRequest.*_at_detection` | ✅ Collected (when provided) |

### Data NOT Yet Collected ❌

| Data Point | Purpose | Priority |
|------------|---------|----------|
| Execution log outcomes wired into training pipeline | Use actual post-moisture + volume | HIGH |
| Time since last irrigation (explicit feature) | Cycle frequency learning | HIGH |
| Moisture depletion rate windows (per-plant) | Predictive timing | MEDIUM |
| Valve state confirmation (if hardware supports) | Attribution accuracy | MEDIUM |
| Weather/season data | Outdoor unit optimization | LOW |

---

## 🎯 Minimum Data Thresholds for Model Activation

### Per-Model Data Requirements

| Model | Min Samples | Description | Notification Trigger |
|-------|-------------|-------------|---------------------|
| **User Response Predictor** | 20 responses | Predicts approve/delay/cancel | 20 total_requests |
| **Threshold Optimizer** | 30 feedback samples | Optimizes soil moisture threshold | 30 moisture_feedback_count |
| **Duration Optimizer** | 15 executed irrigations | Predicts optimal pump duration | 15 executions with `IrrigationExecutionLog.post_moisture` |
| **Timing Predictor** | 25 responses with time | Predicts preferred irrigation time | 25 requests with response patterns |

### Global Readiness Status

```
Model Readiness Formula:
- user_response_predictor: total_requests >= 20
- threshold_optimizer: moisture_feedback_count >= 30
- duration_optimizer: COUNT(executed AND execution_log.post_moisture IS NOT NULL) >= 15
- timing_predictor: total_requests >= 25 AND has_time_pattern_variance
```

---

## 🏗️ Implementation Phases

### Phase 1: Data Collection Enhancement (Week 1)

**Goal:** Ensure all required data is being captured correctly.

#### 1.1 Add Environmental Context to Irrigation Requests

**Files to modify:**
- `infrastructure/database/sqlite_handler.py` - Add columns
- `infrastructure/database/ops/irrigation_workflow.py` - Update operations
- `app/services/application/irrigation_workflow_service.py` - Capture context

**New Columns for `PendingIrrigationRequest`:**
```sql
ALTER TABLE PendingIrrigationRequest ADD COLUMN temperature_at_detection REAL;
ALTER TABLE PendingIrrigationRequest ADD COLUMN humidity_at_detection REAL;
ALTER TABLE PendingIrrigationRequest ADD COLUMN vpd_at_detection REAL;
ALTER TABLE PendingIrrigationRequest ADD COLUMN light_level_at_detection REAL;
ALTER TABLE PendingIrrigationRequest ADD COLUMN hours_since_last_irrigation REAL;
ALTER TABLE PendingIrrigationRequest ADD COLUMN plant_type TEXT;
ALTER TABLE PendingIrrigationRequest ADD COLUMN growth_stage TEXT;
```

#### 1.2 Create Irrigation Training Data Repository

**New file:** `infrastructure/database/repositories/irrigation_ml.py`

```python
class IrrigationMLRepository:
    """Repository for irrigation ML training data access."""
    
    def get_training_data_count(self, user_id: int, unit_id: int) -> Dict[str, int]:
        """Get counts of training data for model readiness checks."""
        
    def get_response_training_data(self, user_id: int, days: int = 90) -> pd.DataFrame:
        """Get training data for user response prediction."""
        
    def get_threshold_training_data(self, unit_id: int, days: int = 90) -> pd.DataFrame:
        """Get training data for threshold optimization."""
        
    def get_duration_training_data(self, unit_id: int, days: int = 90) -> pd.DataFrame:
        """Get training data for duration prediction."""
        
    def get_executed_irrigations_with_outcome(self, unit_id: int) -> List[Dict]:
        """Get irrigation events with before/after moisture readings."""
```

#### 1.3 Capture Post-Watering Moisture for Training

**Source:** `IrrigationExecutionLog.post_moisture` populated by post-capture job
**Usage:** Duration optimizer now reads execution logs instead of `PendingIrrigationRequest.soil_moisture_after`

After irrigation execution, schedule a delayed task (e.g., 30 minutes) to read soil moisture and update the record.

---

### Phase 2: ML Data Readiness Service (Week 2)

**Goal:** Create a service that monitors data collection and notifies users when models are ready.

#### 2.1 Create ML Readiness Monitor Service

**New file:** `app/services/ai/ml_readiness_monitor.py`

```python
@dataclass
class ModelReadinessStatus:
    """Status of a specific ML model's data readiness."""
    model_name: str
    model_display_name: str
    required_samples: int
    current_samples: int
    is_ready: bool
    is_activated: bool
    description: str
    benefits: List[str]
    
    @property
    def progress_percent(self) -> float:
        return min(100.0, (self.current_samples / self.required_samples) * 100)


@dataclass
class IrrigationMLReadiness:
    """Overall irrigation ML readiness status."""
    user_response_predictor: ModelReadinessStatus
    threshold_optimizer: ModelReadinessStatus
    duration_optimizer: ModelReadinessStatus
    timing_predictor: ModelReadinessStatus
    
    @property
    def any_ready_not_activated(self) -> bool:
        """Check if any model is ready but not yet activated."""


class MLReadinessMonitorService:
    """
    Monitors ML training data collection and notifies users
    when models have enough data for activation.
    """
    
    def __init__(
        self,
        irrigation_ml_repo: IrrigationMLRepository,
        notifications_service: NotificationsService,
        settings_service: SettingsService,
    ):
        """Initialize readiness monitor."""
        
    def check_irrigation_readiness(
        self, 
        user_id: int, 
        unit_id: Optional[int] = None
    ) -> IrrigationMLReadiness:
        """Check readiness of all irrigation ML models."""
        
    def check_and_notify(self, user_id: int, unit_id: int) -> None:
        """Check readiness and send notification if model became ready."""
        
    def send_model_ready_notification(
        self,
        user_id: int,
        unit_id: int,
        model_status: ModelReadinessStatus,
    ) -> None:
        """Send notification about model readiness."""
        
    def activate_model(
        self, 
        user_id: int, 
        unit_id: int, 
        model_name: str
    ) -> bool:
        """Activate a specific ML model for a user/unit."""
```

#### 2.2 Add Notification Type for ML Readiness

**Modify:** `app/services/application/notifications_service.py`

```python
class NotificationType:
    # ... existing types ...
    ML_MODEL_READY = "ml_model_ready"
    ML_MODEL_ACTIVATED = "ml_model_activated"
```

#### 2.3 Add ML Activation Status to Workflow Config

**Modify:** `IrrigationWorkflowConfig` table

```sql
ALTER TABLE IrrigationWorkflowConfig ADD COLUMN ml_response_predictor_enabled INTEGER DEFAULT 0;
ALTER TABLE IrrigationWorkflowConfig ADD COLUMN ml_threshold_optimizer_enabled INTEGER DEFAULT 0;
ALTER TABLE IrrigationWorkflowConfig ADD COLUMN ml_duration_optimizer_enabled INTEGER DEFAULT 0;
ALTER TABLE IrrigationWorkflowConfig ADD COLUMN ml_timing_predictor_enabled INTEGER DEFAULT 0;
ALTER TABLE IrrigationWorkflowConfig ADD COLUMN ml_models_notified TEXT DEFAULT '[]';
```

---

### Phase 3: Irrigation Predictor Service (Week 3)

**Goal:** Create the core ML prediction service for irrigation optimization.

#### 3.1 Create Irrigation Predictor Service

**New file:** `app/services/ai/irrigation_predictor.py`

```python
@dataclass
class IrrigationPrediction:
    """Prediction result for irrigation optimization."""
    optimal_threshold: float
    threshold_confidence: float
    predicted_user_response: Dict[str, float]  # {approve: 0.7, delay: 0.2, cancel: 0.1}
    recommended_duration_seconds: int
    duration_confidence: float
    optimal_irrigation_time: str  # "HH:MM"
    time_confidence: float
    recommendations: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response."""


class IrrigationPredictor:
    """
    ML-based irrigation optimization predictor.
    
    Provides predictions for:
    - Optimal soil moisture threshold (per plant type + user feedback)
    - User response probability (approve/delay/cancel)
    - Optimal irrigation duration
    - Preferred irrigation time
    """
    
    def __init__(
        self,
        model_registry: ModelRegistry,
        irrigation_ml_repo: IrrigationMLRepository,
        feature_engineer: FeatureEngineer,
    ):
        """Initialize irrigation predictor."""
        self._model_registry = model_registry
        self._repo = irrigation_ml_repo
        self._feature_engineer = feature_engineer
        
        # Model cache
        self._threshold_model = None
        self._response_model = None
        self._duration_model = None
        self._timing_model = None
        
    def predict_optimal_threshold(
        self,
        unit_id: int,
        plant_type: str,
        growth_stage: str,
        user_id: int,
    ) -> Tuple[float, float]:
        """
        Predict optimal soil moisture threshold.
        
        Uses Bayesian updating based on:
        - Plant type defaults
        - User feedback history
        - Environmental conditions
        
        Returns:
            (optimal_threshold, confidence)
        """
        
    def predict_user_response(
        self,
        user_id: int,
        unit_id: int,
        current_moisture: float,
        threshold: float,
        time_of_day: int,
        day_of_week: int,
    ) -> Dict[str, float]:
        """
        Predict probability of user response types.
        
        Returns:
            {"approve": 0.7, "delay": 0.2, "cancel": 0.1}
        """
        
    def predict_optimal_duration(
        self,
        unit_id: int,
        current_moisture: float,
        target_moisture: float,
        soil_type: Optional[str] = None,
    ) -> Tuple[int, float]:
        """
        Predict optimal irrigation duration.
        
        Returns:
            (duration_seconds, confidence)
        """
        
    def predict_preferred_time(
        self,
        user_id: int,
        unit_id: int,
        day_of_week: int,
    ) -> Tuple[str, float]:
        """
        Predict user's preferred irrigation time.
        
        Returns:
            (time_str "HH:MM", confidence)
        """
        
    def get_comprehensive_prediction(
        self,
        unit_id: int,
        user_id: int,
        plant_type: str,
        growth_stage: str,
        current_conditions: Dict[str, float],
    ) -> IrrigationPrediction:
        """Get comprehensive irrigation prediction."""
```

#### 3.2 Add Feature Engineering for Irrigation

**Modify:** `app/services/ai/feature_engineering.py`

```python
class FeatureEngineer:
    # ... existing code ...
    
    IRRIGATION_FEATURES_V1 = [
        # Current conditions
        "soil_moisture_current",
        "soil_moisture_threshold_ratio",  # current / threshold
        "temperature_current",
        "humidity_current",
        "vpd_current",
        
        # Historical
        "hours_since_last_irrigation",
        "moisture_depletion_rate_per_hour",
        "avg_irrigation_duration",
        
        # Temporal
        "hour_of_day_sin",
        "hour_of_day_cos",
        "day_of_week_sin", 
        "day_of_week_cos",
        "is_weekend",
        
        # User behavior
        "user_approval_rate",
        "user_avg_response_time_minutes",
        "user_delay_frequency",
        "user_cancel_frequency",
        
        # Plant context
        "plant_stage_vegetative",
        "plant_stage_flowering",
        "plant_stage_fruiting",
        "plant_age_days",
    ]
    
    @staticmethod
    def create_irrigation_features(
        current_conditions: Dict[str, float],
        irrigation_history: List[Dict],
        user_preferences: Dict[str, Any],
        plant_info: Dict[str, Any],
        current_time: Optional[datetime] = None,
    ) -> pd.DataFrame:
        """Create features for irrigation prediction models."""
```

---

### Phase 4: Bayesian Threshold Adjustment (Week 4)

**Goal:** Replace simple ±5% adjustment with intelligent Bayesian learning.

#### 4.1 Create Bayesian Threshold Adjuster

**New file:** `app/services/ai/bayesian_threshold.py`

```python
@dataclass
class ThresholdBelief:
    """Bayesian belief about optimal threshold."""
    mean: float
    variance: float
    sample_count: int
    last_updated: datetime
    
    @property
    def confidence(self) -> float:
        """Higher sample count = higher confidence."""
        return min(1.0, self.sample_count / 50)  # Max confidence at 50 samples
    
    @property
    def uncertainty(self) -> float:
        """Standard deviation of belief."""
        return math.sqrt(self.variance)


class BayesianThresholdAdjuster:
    """
    Bayesian approach to learning optimal soil moisture thresholds.
    
    Uses conjugate prior (Normal-Normal) for efficient updates:
    - Prior: Plant type default threshold with high uncertainty
    - Likelihood: User feedback (too_little/just_right/too_much)
    - Posterior: Updated belief about optimal threshold
    
    Benefits over fixed ±5%:
    - Adjustments shrink as confidence grows
    - Accounts for user consistency (noisy vs reliable feedback)
    - Handles conflicting feedback gracefully
    - Converges to optimal value over time
    """
    
    def __init__(
        self,
        irrigation_ml_repo: IrrigationMLRepository,
        default_variance: float = 100.0,  # High initial uncertainty
    ):
        """Initialize Bayesian adjuster."""
        self._repo = irrigation_ml_repo
        self._default_variance = default_variance
        self._beliefs: Dict[Tuple[int, int], ThresholdBelief] = {}  # (unit_id, user_id) -> belief
    
    def get_belief(
        self,
        unit_id: int,
        user_id: int,
        plant_type: str,
    ) -> ThresholdBelief:
        """Get current belief about optimal threshold."""
        
    def update_from_feedback(
        self,
        unit_id: int,
        user_id: int,
        feedback: str,  # too_little, just_right, too_much
        current_threshold: float,
        soil_moisture_at_request: float,
    ) -> float:
        """
        Update belief based on user feedback.
        
        Returns:
            New recommended threshold
        """
        belief = self.get_belief(unit_id, user_id, plant_type)
        
        # Convert feedback to observation
        if feedback == "too_little":
            # User wants more water -> threshold should be higher
            observed_optimal = current_threshold + self._estimate_adjustment(belief)
        elif feedback == "too_much":
            # User wants less water -> threshold should be lower  
            observed_optimal = current_threshold - self._estimate_adjustment(belief)
        else:  # just_right
            observed_optimal = current_threshold
        
        # Bayesian update (conjugate Normal-Normal)
        # Prior: N(belief.mean, belief.variance)
        # Likelihood: N(observed_optimal, observation_variance)
        # Posterior: N(new_mean, new_variance)
        
        observation_variance = self._get_observation_variance(
            user_consistency=self._calculate_user_consistency(user_id, unit_id)
        )
        
        # Precision-weighted update
        prior_precision = 1.0 / belief.variance
        observation_precision = 1.0 / observation_variance
        
        posterior_precision = prior_precision + observation_precision
        posterior_variance = 1.0 / posterior_precision
        
        posterior_mean = (
            prior_precision * belief.mean + 
            observation_precision * observed_optimal
        ) / posterior_precision
        
        # Update belief
        new_belief = ThresholdBelief(
            mean=posterior_mean,
            variance=posterior_variance,
            sample_count=belief.sample_count + 1,
            last_updated=datetime.now(),
        )
        
        self._beliefs[(unit_id, user_id)] = new_belief
        self._persist_belief(unit_id, user_id, new_belief)
        
        return posterior_mean
    
    def _estimate_adjustment(self, belief: ThresholdBelief) -> float:
        """
        Estimate adjustment magnitude based on confidence.
        
        Low confidence -> larger adjustments (explore)
        High confidence -> smaller adjustments (exploit)
        """
        base_adjustment = 5.0  # Maximum adjustment %
        confidence_factor = 1.0 - belief.confidence
        return base_adjustment * confidence_factor
    
    def _calculate_user_consistency(self, user_id: int, unit_id: int) -> float:
        """
        Calculate how consistent user feedback is.
        
        Returns:
            0.0 = very inconsistent (noisy)
            1.0 = very consistent (reliable)
        """
```

#### 4.2 Integrate Bayesian Adjuster into Workflow

**Modify:** `app/services/application/irrigation_workflow_service.py`

Replace simple threshold adjustment with Bayesian adjuster call.

---

### Phase 5: ML Training Integration (Week 5)

**Goal:** Connect irrigation models to the automated training pipeline.

#### 5.1 Add Irrigation Model to MLTrainerService

**Modify:** `app/services/ai/ml_trainer.py`

```python
class MLTrainerService:
    # ... existing code ...
    
    def train_irrigation_threshold_model(
        self,
        unit_id: Optional[int] = None,
        days: int = 90,
        save_model: bool = True,
    ) -> Dict[str, Any]:
        """
        Train model to predict optimal soil moisture threshold.
        
        Features:
        - Plant type/variety
        - Growth stage
        - Historical feedback patterns
        - Environmental conditions at feedback time
        - User consistency score
        
        Target:
        - Optimal threshold (derived from feedback)
        """
        
    def train_irrigation_response_model(
        self,
        user_id: Optional[int] = None,
        days: int = 90,
        save_model: bool = True,
    ) -> Dict[str, Any]:
        """
        Train model to predict user response to irrigation requests.
        
        Features:
        - Time of day, day of week
        - Current soil moisture
        - User historical patterns
        - Environmental conditions
        
        Target:
        - Response class (approve/delay/cancel)
        """
        
    def train_irrigation_duration_model(
        self,
        unit_id: Optional[int] = None,
        days: int = 90,
        save_model: bool = True,
    ) -> Dict[str, Any]:
        """
        Train model to predict optimal irrigation duration.
        
        Features:
        - Soil moisture before
        - Target moisture
        - Soil type (if known)
        - Temperature, humidity
        - Previous duration outcomes
        
        Target:
        - Duration in seconds
        - Soil moisture after (for validation)
        """
```

#### 5.2 Add to Automated Retraining Schedule

**Modify:** `app/services/ai/automated_retraining.py`

```python
# Add irrigation model jobs to default jobs
DEFAULT_RETRAINING_JOBS = [
    # ... existing jobs ...
    RetrainingJob(
        job_id="irrigation_threshold",
        model_type="irrigation_threshold",
        schedule_type="weekly",
        schedule_day=0,  # Monday
        schedule_time="03:00",
        min_samples=30,
        drift_threshold=0.20,
    ),
    RetrainingJob(
        job_id="irrigation_response",
        model_type="irrigation_response", 
        schedule_type="weekly",
        schedule_day=0,
        schedule_time="03:30",
        min_samples=20,
        drift_threshold=0.15,
    ),
    RetrainingJob(
        job_id="irrigation_duration",
        model_type="irrigation_duration",
        schedule_type="monthly",
        schedule_day=1,
        schedule_time="04:00",
        min_samples=15,
        drift_threshold=0.25,
    ),
]
```

---

### Phase 6: API & UI Integration (Week 6)

**Goal:** Expose ML features via API and handle user activation.

#### 6.1 Create ML Readiness API Endpoints

**New file:** `app/blueprints/api/ml_status/__init__.py`

```python
from flask import Blueprint, jsonify, request, g

ml_status_bp = Blueprint("ml_status", __name__, url_prefix="/api/ml")


@ml_status_bp.route("/readiness/<int:unit_id>", methods=["GET"])
def get_ml_readiness(unit_id: int):
    """Get ML model readiness status for a unit."""
    readiness = g.container.ml_readiness_monitor.check_irrigation_readiness(
        user_id=g.current_user.id,
        unit_id=unit_id,
    )
    return jsonify({
        "unit_id": unit_id,
        "models": {
            "user_response_predictor": readiness.user_response_predictor.to_dict(),
            "threshold_optimizer": readiness.threshold_optimizer.to_dict(),
            "duration_optimizer": readiness.duration_optimizer.to_dict(),
            "timing_predictor": readiness.timing_predictor.to_dict(),
        },
        "any_ready_not_activated": readiness.any_ready_not_activated,
    })


@ml_status_bp.route("/activate", methods=["POST"])
def activate_ml_model():
    """Activate a specific ML model for a unit."""
    data = request.get_json()
    unit_id = data.get("unit_id")
    model_name = data.get("model_name")
    
    success = g.container.ml_readiness_monitor.activate_model(
        user_id=g.current_user.id,
        unit_id=unit_id,
        model_name=model_name,
    )
    
    return jsonify({"success": success})


@ml_status_bp.route("/predictions/<int:unit_id>", methods=["GET"])
def get_irrigation_predictions(unit_id: int):
    """Get current ML predictions for irrigation."""
    prediction = g.container.irrigation_predictor.get_comprehensive_prediction(
        unit_id=unit_id,
        user_id=g.current_user.id,
        # ... plant info from unit ...
    )
    return jsonify(prediction.to_dict())
```

#### 6.2 Handle ML Readiness Notifications

Add notification action handler for ML model activation:

```python
# In notifications handling
if action_type == "activate_ml_model":
    model_name = action_data.get("model_name")
    unit_id = action_data.get("unit_id")
    g.container.ml_readiness_monitor.activate_model(
        user_id=user_id,
        unit_id=unit_id,
        model_name=model_name,
    )
```

---

### Phase 7: Scheduled Readiness Checks (Week 6)

**Goal:** Periodically check for model readiness and notify users.

#### 7.1 Add Scheduled Task for Readiness Check

**Modify:** `app/workers/scheduled_tasks.py`

```python
def ml_readiness_check_task(container: "ServiceContainer") -> Dict[str, Any]:
    """
    Check ML model data readiness and notify users when ready.
    
    This task runs daily to:
    - Check data collection progress for each user/unit
    - Send notification when a model becomes ready
    - Track which models have been notified
    
    Celery name: ml.readiness_check
    """
    readiness_monitor = getattr(container, "ml_readiness_monitor", None)
    if not readiness_monitor:
        return {"success": False, "error": "ML readiness monitor not available"}
    
    results = {
        "users_checked": 0,
        "notifications_sent": 0,
        "errors": [],
    }
    
    try:
        # Get all active users with units
        growth_service = container.growth_service
        units = growth_service.get_all_units()
        
        for unit in units:
            try:
                readiness_monitor.check_and_notify(
                    user_id=unit.get("user_id", 1),
                    unit_id=unit["unit_id"],
                )
                results["users_checked"] += 1
            except Exception as e:
                results["errors"].append(f"Unit {unit['unit_id']}: {str(e)}")
        
        return results
    except Exception as e:
        return {"success": False, "error": str(e)}


# In schedule_default_jobs():
scheduler.schedule_daily(
    "ml.readiness_check",
    time_of_day="10:00",  # Check mid-morning
    job_id="ml_readiness_check_daily",
)
```

---

## 📁 New Files Summary

| File | Purpose |
|------|---------|
| `infrastructure/database/repositories/irrigation_ml.py` | ML training data repository |
| `app/services/ai/irrigation_predictor.py` | Core irrigation ML predictor |
| `app/services/ai/ml_readiness_monitor.py` | Data readiness monitoring |
| `app/services/ai/bayesian_threshold.py` | Smart threshold adjustment |
| `app/blueprints/api/ml_status/__init__.py` | ML status API endpoints |

## 📝 Modified Files Summary

| File | Changes |
|------|---------|
| `infrastructure/database/sqlite_handler.py` | Add schema columns |
| `infrastructure/database/ops/irrigation_workflow.py` | Add new operations |
| `infrastructure/database/repositories/irrigation_workflow.py` | Add repository methods |
| `app/services/application/irrigation_workflow_service.py` | Capture context, use ML |
| `app/services/application/notifications_service.py` | Add notification types |
| `app/services/ai/feature_engineering.py` | Add irrigation features |
| `app/services/ai/ml_trainer.py` | Add irrigation model training |
| `app/services/ai/automated_retraining.py` | Add irrigation jobs |
| `app/workers/scheduled_tasks.py` | Add readiness check task |
| `app/services/container.py` | Add new services |
| `app/services/container_builder.py` | Wire up new services |

---

## 🔔 Notification Flow for Model Activation

```
┌─────────────────────────────────────────────────────────────┐
│                    Daily Readiness Check                     │
│                      (10:00 AM)                              │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────┐
│ For each user/unit:                                          │
│   Check data counts vs thresholds                            │
│   - total_requests >= 20? → Response Predictor ready         │
│   - moisture_feedback_count >= 30? → Threshold Optimizer     │
│   - executed_with_outcome >= 15? → Duration Optimizer        │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ▼
         ┌───────────────────┐
         │  Model Ready AND  │
         │  Not Yet Notified?│
         └────────┬──────────┘
                  │ Yes
                  ▼
┌─────────────────────────────────────────────────────────────┐
│            Send Notification to User                         │
│                                                              │
│  "🧠 AI Feature Ready!"                                      │
│                                                              │
│  "Your Irrigation Threshold Optimizer is ready to            │
│   activate! Based on 32 feedback responses, we can now       │
│   automatically optimize your soil moisture threshold."      │
│                                                              │
│  [Activate Now]  [Learn More]  [Not Now]                     │
│                                                              │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────┐
│              User Response Handling                          │
│                                                              │
│  [Activate Now] → Enable model, confirm notification         │
│  [Learn More]   → Open docs/help about the model             │
│  [Not Now]      → Snooze, check again in 7 days              │
└─────────────────────────────────────────────────────────────┘
```

---

## 📊 Model Activation Status Storage

### WorkflowConfig Extended Schema

```sql
-- Additional columns for ML activation status
ml_response_predictor_enabled INTEGER DEFAULT 0,
ml_threshold_optimizer_enabled INTEGER DEFAULT 0, 
ml_duration_optimizer_enabled INTEGER DEFAULT 0,
ml_timing_predictor_enabled INTEGER DEFAULT 0,
ml_response_predictor_notified_at TEXT,
ml_threshold_optimizer_notified_at TEXT,
ml_duration_optimizer_notified_at TEXT,
ml_timing_predictor_notified_at TEXT,
```

### Notification Deduplication

Track which models have been notified to avoid spamming users:
- Store `notified_at` timestamp per model
- Only re-notify if NULL or model was deactivated
- Add snooze mechanism (don't notify again for 7 days if user clicked "Not Now")

---

## 🧪 Testing Strategy

### Unit Tests

1. `test_irrigation_ml_repository.py` - Data retrieval tests
2. `test_irrigation_predictor.py` - Prediction logic tests
3. `test_bayesian_threshold.py` - Bayesian update tests
4. `test_ml_readiness_monitor.py` - Readiness check tests

### Integration Tests

1. End-to-end irrigation flow with ML predictions
2. Notification delivery on readiness
3. Model activation flow
4. Retraining pipeline with irrigation models

### Data Simulation

Create script to generate synthetic irrigation data for testing:
- Various user response patterns
- Different feedback distributions
- Edge cases (all approve, all cancel, etc.)

---

## 📅 Implementation Timeline

| Week | Phase | Key Deliverables |
|------|-------|------------------|
| 1 | Data Collection | Schema updates, environmental context capture |
| 2 | Readiness Monitor | MLReadinessMonitorService, notification integration |
| 3 | Irrigation Predictor | Core prediction service, feature engineering |
| 4 | Bayesian Threshold | Smart threshold adjustment, confidence tracking |
| 5 | Training Integration | ML pipeline connection, automated retraining |
| 6 | API & Scheduling | REST endpoints, readiness check task |

---

## 🚀 Quick Start Commands

After implementation, test with:

```bash
# Check ML readiness for a unit
curl -X GET http://localhost:5000/api/ml/readiness/1

# Activate a model
curl -X POST http://localhost:5000/api/ml/activate \
  -H "Content-Type: application/json" \
  -d '{"unit_id": 1, "model_name": "threshold_optimizer"}'

# Get predictions
curl -X GET http://localhost:5000/api/ml/predictions/1

# Manually trigger readiness check
python -c "from app.workers.scheduled_tasks import ml_readiness_check_task; ..."
```

---

## ✅ Success Criteria

1. **Data Collection**: All irrigation events capture full environmental context
2. **Readiness Detection**: System accurately identifies when models have enough data
3. **User Notification**: Users receive clear, actionable notifications
4. **Model Activation**: One-click activation from notification
5. **Prediction Quality**: Activated models provide measurably better recommendations
6. **Threshold Adjustment**: Bayesian approach converges faster than fixed adjustments
7. **Training Pipeline**: Irrigation models integrate with existing retraining infrastructure

---

## 🔗 Related Documentation

- [IRRIGATION_WORKFLOW.md](IRRIGATION_WORKFLOW.md) - Current workflow documentation
- [app/services/ai/improvement_plan.md](../app/services/ai/improvement_plan.md) - General AI improvement plan
- [app/services/ai/quick-reference-guide.md](../app/services/ai/quick-reference-guide.md) - AI services reference
