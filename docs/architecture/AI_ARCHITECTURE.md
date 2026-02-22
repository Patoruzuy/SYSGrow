# AI Services Architecture

**Deep dive into SYSGrow's machine learning and AI systems**

---

## System Overview

SYSGrow's AI architecture is built around three core principles:

1. **Modularity** — Each AI service is independent and composable
2. **Gradual enhancement** — Features work without AI, improve with AI
3. **Resource awareness** — Designed for Raspberry Pi and edge devices

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                      Application Layer                          │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐   │
│  │ Web Controllers│  │ API Endpoints  │  │ Background Jobs│   │
│  └───────┬────────┘  └───────┬────────┘  └───────┬────────┘   │
└──────────┼───────────────────┼───────────────────┼─────────────┘
           │                   │                   │
┌──────────▼───────────────────▼───────────────────▼─────────────┐
│                      Service Orchestration                      │
│  ┌────────────────────────────────────────────────────────┐    │
│  │          ContainerBuilder (DI Container)               │    │
│  │  • Builds AI components based on config                │    │
│  │  • Manages dependencies between services               │    │
│  │  • Handles feature flags                               │    │
│  └────────────────────┬───────────────────────────────────┘    │
│                       │                                          │
│      ┌────────────────┼────────────────┐                        │
│      │ AIComponents   │ OptionalAI     │                        │
│      │ (Core)         │ (Feature-gated)│                        │
│      └───────┬────────┴───────┬────────┘                        │
└──────────────┼────────────────┼─────────────────────────────────┘
               │                │
┌──────────────▼────────────────▼─────────────────────────────────┐
│                      AI Service Layer                           │
│                                                                  │
│  ┌──────────────────────────────────────────────────────┐      │
│  │             Core Prediction Services                  │      │
│  │  ┌──────────────┐  ┌──────────────┐  ┌────────────┐ │      │
│  │  │PlantHealth   │  │Climate       │  │Irrigation  │ │      │
│  │  │Monitor       │  │Optimizer     │  │Predictor   │ │      │
│  │  └──────────────┘  └──────────────┘  └────────────┘ │      │
│  └──────────────────────────────────────────────────────┘      │
│                                                                  │
│  ┌──────────────────────────────────────────────────────┐      │
│  │             LLM Integration Layer                     │      │
│  │  ┌──────────────────────────────────────────────┐    │      │
│  │  │  LLMBackend (ABC)                            │    │      │
│  │  │  ├─ OpenAIBackend                            │    │      │
│  │  │  ├─ AnthropicBackend                         │    │      │
│  │  │  └─ LocalTransformersBackend                 │    │      │
│  │  └──────────────┬───────────────────────────────┘    │      │
│  │                 │                                     │      │
│  │  ┌──────────────▼───────────┐  ┌─────────────────┐  │      │
│  │  │LLMRecommendationProvider │  │LLMAdvisorService│  │      │
│  │  └──────────────────────────┘  └─────────────────┘  │      │
│  └──────────────────────────────────────────────────────┘      │
│                                                                  │
│  ┌──────────────────────────────────────────────────────┐      │
│  │             Continuous Learning Services              │      │
│  │  ┌──────────────┐  ┌──────────────┐  ┌────────────┐ │      │
│  │  │Bayesian      │  │Continuous    │  │Automated   │ │      │
│  │  │Threshold     │  │Monitoring    │  │Retraining  │ │      │
│  │  │Adjuster      │  │Service       │  │Service     │ │      │
│  │  └──────────────┘  └──────────────┘  └────────────┘ │      │
│  └──────────────────────────────────────────────────────┘      │
└──────────────────────────────┬──────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────┐
│                     Model Management Layer                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │ModelRegistry │  │DriftDetector │  │FeatureEngineer       │  │
│  │• Versioning  │  │• Performance │  │• Extraction          │  │
│  │• Storage     │  │• Monitoring  │  │• Transformation      │  │
│  └──────────────┘  └──────────────┘  └──────────────────────┘  │
└──────────────────────────────┬──────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────┐
│                      Data & Storage Layer                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │Training Data │  │Model Files   │  │Analytics DB          │  │
│  │Repository    │  │(models/)     │  │(sensor history)      │  │
│  └──────────────┘  └──────────────┘  └──────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Core AI Components

### 1. Prediction Services

#### PlantHealthMonitor
**Purpose:** Real-time disease detection and symptom analysis

**Data Flow:**
```
Sensor Data → EnvironmentalLeafHealthScorer → Symptom Detection
     ↓                                              ↓
ThresholdService ←──────────────────────── DiseasePrediction
     ↓                                              ↓
HealthObservation ←──────────────────────── Recommendations
```

**Key Features:**
- **12 symptom patterns** (yellowing leaves, wilting, brown spots, etc.)
- **Disease prediction** using RandomForest classifier
- **Environmental correlation** (links symptoms to sensor anomalies)
- **Treatment recommendations** via RecommendationProvider integration

**Dependencies:**
- `HealthDataRepository` — persistence
- `ThresholdService` — optimal ranges per plant
- `DiseasePredictionService` — ML classifier
- `RecommendationProvider` — care suggestions

---

#### ClimateOptimizer
**Purpose:** ML-powered environmental control optimization

**Data Flow:**
```
Current Conditions + Plant Type → Feature Engineering
                                          ↓
                           ClimateOptimizerModel (RandomForest)
                                          ↓
                    Predicted Optimal Conditions
                                          ↓
           Gap Analysis → Recommendations (temp/humidity/co2 adjustments)
```

**Key Features:**
- **Day/night profiles** — separate thresholds for light/dark periods
- **Plant-specific optimization** — 500+ species profiles
- **Energy-aware** — balances performance with power consumption
- **Predictive impact** — estimates growth rate / health score improvements

**Model Training:**
```python
# Feature vector (per unit, 24h window)
[
    temp_mean, temp_std, temp_min, temp_max,
    humidity_mean, humidity_std,
    co2_mean, co2_std,
    light_hours,
    vpd_mean,  # Vapor Pressure Deficit
    day_night_temp_delta
]

# Target labels
optimal_conditions = {
    "growth_rate": float,  # cm/day
    "health_score": float  # 0-100
}
```

---

#### IrrigationPredictor
**Purpose:** Advanced ML-based watering optimization

**Four Sub-Models:**

1. **Threshold Adjustment Model**
   - **Input:** Plant type, growth stage, 7-day moisture history, user feedback
   - **Output:** Optimal soil moisture threshold (%)
   - **Algorithm:** Gradient Boosting Regressor

2. **Duration Prediction Model**
   - **Input:** Unit size, soil type, current moisture, target moisture
   - **Output:** Recommended watering duration (seconds)
   - **Algorithm:** Random Forest Regressor

3. **Timing Optimization Model**
   - **Input:** Plant type, weather forecast, last irrigation timestamp
   - **Output:** Preferred irrigation time (HH:MM)
   - **Algorithm:** Time-series LSTM

4. **User Response Prediction Model**
   - **Input:** User history, recommended threshold, time of day
   - **Output:** Probability distribution (accept | delay | cancel)
   - **Algorithm:** Logistic Regression

**Workflow:**
```
Sensor Data → Threshold Model → Duration Model → Timing Model
                   ↓                  ↓               ↓
            Should irrigate?   How long?       When is best?
                   ↓
            User Response Predictor → Confidence Score
```

---

#### PlantGrowthPredictor
**Purpose:** Growth stage transition forecasting

**Growth Stages:**
1. Seedling
2. Vegetative
3. Pre-flowering
4. Flowering
5. Fruiting
6. Harvest-ready

**Prediction Logic:**
```
Current Stage + Days in Stage + Environmental History
                        ↓
           FeatureEngineer.extract_growth_features()
                        ↓
            GrowthStageModel (RandomForest)
                        ↓
        Next Stage + Predicted Days + Confidence
                        ↓
    ThresholdService.update_for_new_stage()
```

**Integration:**
- Automatically adjusts thresholds when stage transitions occur
- Triggers notifications via `growth_stage_change` event
- Feeds into `AutomatedRetrainingService` for model updates

---

### 2. LLM Integration Layer

#### Architecture

```
RecommendationProvider (Interface)
         ├─ RuleBasedRecommendationProvider (Always available)
         └─ LLMRecommendationProvider (Optional, requires LLM backend)
                        ↓
              LLMBackend (ABC)
        ├─ OpenAIBackend
        ├─ AnthropicBackend
        └─ LocalTransformersBackend
```

#### LLMBackend (Abstract Base Class)

```python
class LLMBackend(ABC):
    @abstractmethod
    def initialize(self) -> None:
        """Lazy initialization (load model, check API key)"""
        
    @abstractmethod
    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 512,
        temperature: float = 0.3,
        json_mode: bool = False
    ) -> LLMResponse:
        """Generate completion"""
        
    @property
    @abstractmethod
    def is_available(self) -> bool:
        """Check if backend is ready"""
        
    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Backend identifier"""
```

---

#### OpenAIBackend

**Features:**
- Lazy imports (`import openai` only when needed)
- Supports: GPT-4o, GPT-4o-mini, GPT-3.5-turbo
- Custom `base_url` for Azure OpenAI or proxies
- JSON mode support (`response_format={"type": "json_object"}`)

**Initialization:**
```python
backend = OpenAIBackend(
    api_key="sk-...",
    model="gpt-4o-mini",
    base_url=None  # Optional
)
backend.initialize()  # Downloads nothing, just validates API key
```

**Generation:**
```python
response = backend.generate(
    system_prompt="You are a plant disease expert.",
    user_prompt="What causes yellowing leaves in tomatoes?",
    max_tokens=512,
    temperature=0.3,
    json_mode=False
)
print(response.content)  # "Yellowing leaves in tomatoes can be caused by..."
print(response.token_usage)  # {"input": 45, "output": 287}
print(response.latency_ms)  # 623
```

---

#### AnthropicBackend

**Features:**
- Lazy imports (`import anthropic` only when needed)
- Supports: Claude 3.5 Haiku, Claude Sonnet 4, Claude Opus
- Custom `base_url` for proxies
- Automatic prompt caching (saves costs)

**Initialization:**
```python
backend = AnthropicBackend(
    api_key="sk-ant-...",
    model="claude-3-5-haiku-latest",
    base_url=None
)
backend.initialize()
```

**Generation:**
```python
response = backend.generate(
    system_prompt="You are an expert in plant nutrition.",
    user_prompt="Explain nitrogen deficiency symptoms.",
    max_tokens=512,
    temperature=0.3,
    json_mode=False  # Anthropic uses structured output differently
)
```

---

#### LocalTransformersBackend

**Features:**
- Lazy imports (`torch`, `transformers`, `bitsandbytes`)
- Supports: Any HuggingFace causal-LM model
- **Default:** EXAONE 4.0 1.2B Instruct (optimized for Raspberry Pi)
- 4-bit quantization (`BitsAndBytesConfig`)
- Device auto-detection: `cuda` > `mps` > `cpu`

**Initialization:**
```python
backend = LocalTransformersBackend(
    model_path="LGAI-EXAONE/EXAONE-4.0-1.2B-Instruct",
    device="auto",  # Auto-detects best device
    quantize=True,  # 4-bit quantization
    torch_dtype="float16"
)
backend.initialize()  # Downloads model on first run (~2GB)
```

**Model Download:**
- Automatic on first use
- Cached to: `~/.cache/huggingface/hub/`
- One-time download per model

**Quantization:**
```python
# 4-bit config (Raspberry Pi)
quantization_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_compute_dtype=torch.float16,
    bnb_4bit_use_double_quant=True,
    bnb_4bit_quant_type="nf4"
)
# Memory: 1.2B model → 500MB (vs 2GB full precision)
```

**Generation:**
```python
response = backend.generate(
    system_prompt="You are a helpful plant care assistant.",
    user_prompt="Should I water my basil today?",
    max_tokens=256,
    temperature=0.3,
    json_mode=False
)
# Latency: 3-4s on Raspberry Pi 5, <1s on desktop GPU
```

---

#### LLMRecommendationProvider

**Purpose:** Generate plant care recommendations using LLM

**Prompt Structure:**
```
SYSTEM PROMPT:
You are an expert agricultural AI assistant specializing in plant health, 
environmental control, and precision agriculture...

USER PROMPT:
{
  "plant_id": 1,
  "plant_type": "tomato",
  "growth_stage": "flowering",
  "symptoms": ["yellowing_leaves", "brown_spots"],
  "environmental_data": {
    "temperature": 32.0,
    "humidity": 45.0,
    "soil_moisture": 28.0
  },
  "optimal_ranges": {...}
}

Please provide 3-5 actionable recommendations in JSON format:
[
  {
    "action": "...",
    "priority": "high|medium|low",
    "rationale": "...",
    "confidence": 0.0-1.0,
    "category": "irrigation|climate|nutrients|pest_control|general"
  }
]
```

**Response Parsing:**
```python
# Primary: JSON extraction
recommendations = _parse_recommendations(llm_response.content)

# Fallback 1: Freeform text parsing (regex patterns)
if not recommendations:
    recommendations = _parse_freeform(llm_response.content)

# Fallback 2: Rule-based provider
if not recommendations:
    recommendations = rule_based_provider.get_recommendations(context)
```

**Auto-Fallback:**
```python
# In container_builder.py
if llm_backend and llm_backend.is_available:
    rec_provider = LLMRecommendationProvider(
        backend=llm_backend,
        threshold_service=threshold_service
    )
else:
    rec_provider = RuleBasedRecommendationProvider(
        threshold_service=threshold_service
    )
```

---

#### LLMAdvisorService

**Purpose:** Free-form Q&A and decision-making

**Methods:**

1. **ask()** — General questions
   ```python
   response = advisor.ask(DecisionQuery(
       question="Should I water my tomatoes now?",
       plant_type="tomato",
       environmental_data={...}
   ))
   ```

2. **diagnose()** — Symptom analysis
   ```python
   diagnosis = advisor.diagnose(
       symptoms=["yellowing_leaves", "wilting"],
       plant_type="basil"
   ))
   ```

3. **should_irrigate()** — Irrigation decisions
   ```python
   decision = advisor.should_irrigate(
       plant_type="basil",
       environmental_data={...}
   )
   ```

4. **care_plan()** — Daily care instructions
   ```python
   plan = advisor.care_plan(
       plant_type="tomato",
       growth_stage="flowering"
   )
   ```

**System Prompt:**
```
You are an expert agricultural advisor AI. Your role is to provide 
clear, actionable plant care advice based on environmental data, 
symptoms, and best practices.

Response format:
{
  "answer": "Direct answer to the question",
  "confidence": 0.0-1.0,
  "suggested_actions": ["action1", "action2", ...],
  "warnings": ["warning1", "warning2", ...] (if any)
}
```

---

### 3. Continuous Learning Services

#### BayesianThresholdAdjuster
**Purpose:** Self-learning irrigation thresholds from user feedback

**Algorithm:**
```
Prior Belief: threshold = 45%, confidence = 0.5

User Feedback: "Too early" (rejected irrigation)
               ↓
Bayesian Update: P(threshold|feedback) = P(feedback|threshold) × P(threshold)
               ↓
Posterior: threshold = 42%, confidence = 0.65
               ↓
Store in IrrigationMLRepository
               ↓
If adjustment >= notification_tolerance:
    → Fire notification_callback(unit_id, user_id, result)
```

**Feedback Types:**
- **accept** → Threshold was correct, increase confidence
- **too_early** → Threshold too high, decrease by 3-5%
- **too_late** → Threshold too low, increase by 3-5%
- **delay** → User preference, slight decrease (1-2%)

**Notification Callback:**
```python
adjuster = BayesianThresholdAdjuster(
    notification_callback=lambda unit_id, user_id, result: 
        send_notification(
            user_id=user_id,
            title="Irrigation Threshold Updated",
            message=f"New optimal moisture: {result.new_threshold:.1f}%"
        ),
    notification_tolerance=3.0  # Fire if change >= 3%
)
```

---

#### ContinuousMonitoringService
**Purpose:** Real-time plant health surveillance

**Six Analysis Steps (every 5 minutes):**

1. **Disease Risk Prediction**
   ```python
   for unit in active_units:
       risk = disease_predictor.predict(unit.sensor_data)
       if risk.probability > 0.5:
           analytics_repo.store_insight(
               type="disease_risk",
               severity="high",
               data={"disease": risk.disease_name, "probability": risk.probability}
           )
   ```

2. **Climate Optimization**
   ```python
   analysis = climate_optimizer.optimize_climate(
       unit_id=unit.id,
       current_conditions=unit.current_conditions,
       plant_type=unit.plant_type
   )
   if analysis.recommendations:
       analytics_repo.store_insight(type="climate_optimization", ...)
   ```

3. **Growth Tracking**
   ```python
   transition = growth_predictor.predict_stage_transition(...)
   if transition.predicted_days <= 3:
       analytics_repo.store_insight(type="growth_stage_change", ...)
   ```

4. **Trend Analysis**
   ```python
   trends = _analyze_trends(unit.sensor_history, window_hours=24)
   if trends.anomalies:
       analytics_repo.store_insight(type="environmental_trend", ...)
   ```

5. **Environmental Health**
   ```python
   score = env_scorer.score_environmental_health(...)
   if score.overall_score < 60:
       analytics_repo.store_insight(type="environmental_stress", ...)
   ```

6. **Recommendations**
   ```python
   recommendations = rec_provider.get_recommendations(context)
   for rec in recommendations:
       if rec.priority == "high":
           analytics_repo.store_insight(type="recommendation", ...)
   ```

**Background Execution:**
```python
# In container_builder.py
if config.enable_continuous_monitoring:
    monitor = ContinuousMonitoringService(...)
    monitor.start_monitoring()  # Spawns background thread
```

---

#### AutomatedRetrainingService
**Purpose:** Model lifecycle management and scheduled retraining

**Job Types:**

1. **Scheduled Retraining**
   ```python
   service.add_job(
       model_type="climate_optimizer",
       schedule_type="weekly",
       schedule_day=2,  # Wednesday
       schedule_time="03:00",
       min_samples=100
   )
   ```

2. **Drift-Triggered Retraining**
   ```python
   service.add_job(
       model_type="disease",
       schedule_type="on_drift",
       drift_threshold=0.15,  # Retrain if accuracy drops >15%
       min_samples=50
   )
   ```

3. **Manual Retraining**
   ```bash
   curl -X POST /api/v1/ai/retrain/climate_optimizer
   ```

**Retraining Workflow:**
```
Check Schedule / Drift Detection
            ↓
Fetch Training Data (min_samples required)
            ↓
FeatureEngineer.extract_features()
            ↓
MLTrainer.train_model(data, model_type)
            ↓
ModelRegistry.register_model(new_model, metadata)
            ↓
ModelRegistry.set_model_status(old_model, "archived")
            ↓
Notification: "Model retrained successfully"
```

---

#### PersonalizedLearningService
**Purpose:** User-specific growth profiles

**Workflow:**
```
User completes >= 3 successful grows
            ↓
Extract user-specific training data
            ↓
Build personalized model (user_id specific)
            ↓
Store in: data/user_profiles/{user_id}/model.pkl
            ↓
Use for predictions when available
```

**Prediction Logic:**
```python
# Check for personalized model
user_profile = learning_service.get_user_profile(user_id)
if user_profile and user_profile.model_ready:
    prediction = user_profile.model.predict(features)
else:
    # Fallback to global model
    prediction = global_model.predict(features)
```

---

## Model Management Layer

### ModelRegistry

**Purpose:** Centralized ML model versioning and storage

**Directory Structure:**
```
models/
├── climate/
│   ├── v1.0.0_20240101_120000.pkl
│   ├── v1.1.0_20240215_030000.pkl (active)
│   ├── v1.0.0_20240101_120000_metadata.json
│   └── v1.1.0_20240215_030000_metadata.json
├── disease/
│   ├── v2.0.0_20240301_040000.pkl (active)
│   └── v2.0.0_20240301_040000_metadata.json
└── irrigation_threshold/
    └── ...
```

**Metadata Format:**
```json
{
  "model_type": "climate",
  "version": "1.1.0",
  "created_at": "2024-02-15T03:00:00Z",
  "status": "active",
  "performance_metrics": {
    "accuracy": 0.89,
    "precision": 0.87,
    "recall": 0.91,
    "f1_score": 0.89
  },
  "feature_names": ["temp_mean", "humidity_mean", ...],
  "training_samples": 1500,
  "training_duration_seconds": 45.2
}
```

**Operations:**
```python
# Register new model
registry.register_model("climate", model_obj, metadata)

# Load latest
model = registry.load_model("climate", version="latest")

# List versions
versions = registry.list_versions("climate")  # ["1.0.0", "1.1.0"]

# Set status
registry.set_model_status("climate", "1.0.0", ModelStatus.ARCHIVED)
```

---

### ModelDriftDetectorService

**Purpose:** Automatic performance monitoring

**Detection Methods:**

1. **Accuracy Drift**
   ```python
   recent_accuracy = evaluate(recent_predictions, recent_actuals)
   baseline_accuracy = model_metadata.performance_metrics["accuracy"]
   drift = baseline_accuracy - recent_accuracy
   if drift > threshold:
       trigger_retraining()
   ```

2. **Confidence Drift**
   ```python
   recent_confidence = mean([p.confidence for p in predictions])
   if recent_confidence < baseline_confidence - threshold:
       trigger_retraining()
   ```

3. **Feature Distribution Drift**
   ```python
   # Kolmogorov-Smirnov test
   for feature in features:
       statistic, p_value = ks_2samp(
           training_distribution[feature],
           recent_distribution[feature]
       )
       if p_value < 0.05:  # Significant drift
           trigger_retraining()
   ```

---

### FeatureEngineer

**Purpose:** Automated feature extraction for ML models

**Feature Sets:**

1. **Environmental Features (v1)**
   ```python
   features = [
       "temp_mean_24h", "temp_std_24h", "temp_min_24h", "temp_max_24h",
       "humidity_mean_24h", "humidity_std_24h",
       "co2_mean_24h", "co2_std_24h",
       "light_hours_24h",
       "vpd_mean_24h",  # Vapor Pressure Deficit
       "day_night_temp_delta",
       "soil_moisture_mean_24h", "soil_moisture_std_24h"
   ]
   ```

2. **Growth Features (v1)**
   ```python
   features = [
       "days_in_stage",
       "total_days_since_planting",
       "growth_rate_cm_per_day",
       "cumulative_light_hours",
       "cumulative_heat_units",  # Growing Degree Days
       "watering_frequency_per_week",
       "avg_temp_last_7d",
       "avg_humidity_last_7d"
   ]
   ```

3. **Irrigation Features (v1)**
   ```python
   features = [
       "current_soil_moisture",
       "soil_moisture_trend_24h",  # Slope
       "time_since_last_irrigation_hours",
       "avg_daily_water_loss",
       "plant_transpiration_rate",  # Estimated
       "vpd_mean",
       "temperature_mean",
       "growth_stage_encoded"  # One-hot
   ]
   ```

---

## Data Flow Examples

### Example 1: User Waters Plant Manually

```
User clicks "Water Now" button
         ↓
IrrigationController.trigger_irrigation()
         ↓
DeviceService.activate_device(pump_id, duration=120s)
         ↓
SensorReadings updated (soil_moisture increases)
         ↓
[Background] BayesianThresholdAdjuster.update_from_feedback(
    user_id=1,
    accepted=True,  # Implicit acceptance
    feedback_type="manual"
)
         ↓
ThresholdService.update_threshold(unit_id, new_threshold=44.5%)
         ↓
[Background] ContinuousMonitoringService detects moisture increase
         ↓
AnalyticsRepo.store_insight(type="irrigation_event", data={...})
```

---

### Example 2: Continuous Monitor Detects Disease Risk

```
[Background Thread] ContinuousMonitoringService runs every 5 minutes
         ↓
DiseasePredictionService.predict_diseases(unit_id=1)
         ↓
ML Model Output: {"disease": "powdery_mildew", "probability": 0.72}
         ↓
risk.probability > 0.5 → ALERT
         ↓
AnalyticsRepo.store_insight(
    type="disease_risk",
    severity="high",
    unit_id=1,
    data={"disease": "powdery_mildew", "probability": 0.72}
)
         ↓
RecommendationProvider.get_recommendations(context)
         ↓
LLMBackend generates: [
    {action: "Increase air circulation", priority: "high", ...},
    {action: "Apply neem oil spray", priority: "medium", ...}
]
         ↓
SocketIO emits "health_alert" event to frontend
         ↓
User receives real-time notification
```

---

### Example 3: Model Drift Detection & Retraining

```
[Daily Cron Job] AutomatedRetrainingService.check_retraining_jobs()
         ↓
ModelDriftDetectorService.check_drift(model_type="climate")
         ↓
Fetch last 100 predictions + actuals from AnalyticsRepo
         ↓
Calculate accuracy: recent=0.72, baseline=0.89 → drift=0.17
         ↓
drift > threshold (0.15) → TRIGGER RETRAINING
         ↓
TrainingDataRepository.fetch_samples(model_type="climate", min_samples=100)
         ↓
FeatureEngineer.engineer_features(raw_data)
         ↓
MLTrainer.train_model(features, labels, model_type="climate")
         ↓
New model trained: accuracy=0.91
         ↓
ModelRegistry.register_model("climate", new_model, metadata)
         ↓
ModelRegistry.set_model_status("climate", old_version, "archived")
         ↓
Notification: "Climate optimizer model retrained (v1.2.0, accuracy: 91%)"
```

---

## Configuration & Feature Flags

### AI Service Configuration

```python
# app/config.py
class AppConfig:
    # Core AI features
    enable_continuous_monitoring: bool = os.getenv("ENABLE_CONTINUOUS_MONITORING", "true").lower() == "true"
    enable_automated_retraining: bool = os.getenv("ENABLE_AUTOMATED_RETRAINING", "false").lower() == "true"
    enable_personalized_learning: bool = os.getenv("ENABLE_PERSONALIZED_LEARNING", "false").lower() == "true"
    enable_training_data_collection: bool = os.getenv("ENABLE_TRAINING_DATA_COLLECTION", "true").lower() == "true"
    
    # Model optimization
    use_model_quantization: bool = os.getenv("USE_MODEL_QUANTIZATION", "auto") == "true"
    model_cache_predictions: bool = os.getenv("MODEL_CACHE_PREDICTIONS", "true").lower() == "true"
    model_cache_ttl: int = int(os.getenv("MODEL_CACHE_TTL", "300"))  # 5 minutes
    
    # LLM configuration
    llm_provider: str = os.getenv("LLM_PROVIDER", "none")  # "openai" | "anthropic" | "local" | "none"
    llm_api_key: Optional[str] = os.getenv("LLM_API_KEY")
    llm_model: str = os.getenv("LLM_MODEL", "gpt-4o-mini")
    llm_max_tokens: int = int(os.getenv("LLM_MAX_TOKENS", "512"))
    llm_temperature: float = float(os.getenv("LLM_TEMPERATURE", "0.3"))
```

### Environment Variables

```bash
# === Core AI Features ===
ENABLE_CONTINUOUS_MONITORING=true
ENABLE_AUTOMATED_RETRAINING=false  # Disable for Pi to save resources
ENABLE_PERSONALIZED_LEARNING=false
ENABLE_TRAINING_DATA_COLLECTION=true

# === Model Optimization ===
USE_MODEL_QUANTIZATION=true  # 4-bit quantization for Pi
MODEL_CACHE_PREDICTIONS=true
MODEL_CACHE_TTL=300  # Cache predictions for 5 minutes

# === LLM Configuration ===
LLM_PROVIDER=local  # "openai" | "anthropic" | "local" | "none"
LLM_LOCAL_MODEL_PATH=LGAI-EXAONE/EXAONE-4.0-1.2B-Instruct
LLM_LOCAL_DEVICE=auto
LLM_LOCAL_QUANTIZE=true
```

---

## Performance Benchmarks

### Raspberry Pi 5 (8GB)

| Service | CPU | RAM | Latency | Notes |
|---------|-----|-----|---------|-------|
| PlantHealthMonitor | <1% | ~50MB | <100ms | Always available |
| ClimateOptimizer | <1% | ~100MB | ~200ms | RandomForest inference |
| IrrigationPredictor | <1% | ~120MB | ~250ms | 4 models in sequence |
| GrowthPredictor | <1% | ~80MB | ~150ms | RandomForest |
| RuleBasedRecommendations | <1% | ~40MB | <50ms | No ML dependencies |
| LLMRecommendations (Local) | 30-50% | ~600MB | 3-4s | EXAONE 1.2B quantized |
| LLMRecommendations (OpenAI) | <1% | ~50MB | ~500ms | API call latency |
| ContinuousMonitoring | 2-5% | ~200MB | N/A | Background service |

### Desktop (Intel i7 / NVIDIA RTX 3060)

| Service | CPU | GPU | Latency | Notes |
|---------|-----|-----|---------|-------|
| All ML Services | <5% | <10% | <100ms | GPU-accelerated |
| LLMRecommendations (Local) | <5% | 30% | <1s | EXAONE 1.2B full precision |

---

## Troubleshooting

### Issue: High CPU Usage on Pi

**Symptoms:**
- CPU consistently >80%
- System sluggish
- Delayed sensor readings

**Solutions:**
```bash
# 1. Disable optional services
export ENABLE_CONTINUOUS_MONITORING=false
export ENABLE_PERSONALIZED_LEARNING=false

# 2. Increase monitoring interval
export CONTINUOUS_MONITORING_INTERVAL=600  # 10 minutes instead of 5

# 3. Enable model quantization
export USE_MODEL_QUANTIZATION=true

# 4. Use rule-based recommendations only
export LLM_PROVIDER=none
```

---

### Issue: Models Not Loading

**Symptoms:**
```
FileNotFoundError: [Errno 2] No such file or directory: 'models/climate/v1.0.0.pkl'
```

**Solutions:**
```bash
# 1. Check model directory
ls -la models/

# 2. Force model retraining
curl -X POST http://localhost:5000/api/v1/ai/retrain/climate

# 3. Check logs
tail -f logs/app.log | grep "ModelRegistry"
```

---

### Issue: LLM Not Working

**Symptoms:**
- Recommendations are rule-based only
- `llm_advisor` is None
- "LLM backend not available" errors

**Solutions:**
```bash
# 1. Check configuration
python -c "from app.config import AppConfig; c = AppConfig(); \
  print('Provider:', c.llm_provider); \
  print('API Key:', c.llm_api_key[:10] if c.llm_api_key else 'NONE')"

# 2. Test backend directly
python -c "from app.services.ai.llm_backends import create_backend; \
  b = create_backend('openai', api_key='sk-...', model='gpt-4o-mini'); \
  print('Available:', b.is_available)"

# 3. Check dependencies
pip list | grep -E "openai|anthropic|torch|transformers"
```

---

## Next Steps

- **[LLM Setup Guide](LLM_SETUP.md)** — Configure ChatGPT, Claude, or local models
- **[Plant Health API](PLANT_HEALTH_API_REFERENCE.md)** — Health monitoring endpoints
- **[Irrigation ML](IRRIGATION_ML_OPERATIONS.md)** — Advanced watering optimization
- **[Main README](README.md)** — AI services overview

---

**Questions?** Check the [FAQ](FAQ.md) or open an issue on GitHub.
