# AI & Machine Learning Services

**Complete guide to SYSGrow's intelligent plant care system**

---

## 📚 Table of Contents

1. [Overview](#overview)
2. [Core AI Services](#core-ai-services)
3. [LLM Integration](#llm-integration)
4. [Model Management](#model-management)
5. [Quick Start](#quick-start)
6. [Service Reference](#service-reference)

---

## Overview

SYSGrow includes a comprehensive suite of AI and machine learning services designed to optimize plant growth, predict issues, and provide intelligent recommendations. The system is modular, with each service focusing on a specific aspect of plant care.

### Key Features

- **🤖 Predictive Analytics** — ML models for growth, disease, and irrigation optimization
- **💬 LLM-Powered Advice** — Natural language recommendations via ChatGPT, Claude, or local models
- **📊 Continuous Monitoring** — Real-time plant health analysis and alerting
- **🔄 Automated Retraining** — Self-improving models that learn from your grows
- **🎯 Personalized Learning** — Adaptive profiles based on your unique environment
- **⚙️ Production-Ready** — Designed for Raspberry Pi and resource-constrained devices

---

## Core AI Services

### 1. Plant Health Monitor

**Real-time disease detection and symptom analysis**

```python
from app.services.ai import PlantHealthMonitor

health_monitor = PlantHealthMonitor(
    health_data_repo=health_repo,
    threshold_service=threshold_service
)

# Analyze plant health
observation = health_monitor.analyze_plant_health(
    plant_id=1,
    unit_id=1,
    symptoms=["yellowing_leaves", "wilting"],
    environmental_data={"temperature": 28.0, "humidity": 85.0}
)

print(observation.health_status)  # "warning" | "critical" | "healthy"
print(observation.severity_score)  # 0-100
```

**Capabilities:**
- **12+ symptom patterns** — yellowing leaves, brown spots, wilting, pest damage, etc.
- **Environmental correlation** — links symptoms to sensor data anomalies
- **Disease prediction** — RandomForest classifier for common plant diseases
- **Treatment recommendations** — via integrated RecommendationProvider

---

### 2. Climate Optimizer

**ML-powered environmental control optimization**

```python
from app.services.ai import ClimateOptimizer

optimizer = ClimateOptimizer(
    model_registry=registry,
    feature_engineer=engineer
)

# Get optimization recommendations
analysis = optimizer.optimize_climate(
    unit_id=1,
    current_conditions={
        "temperature": 24.0,
        "humidity": 60.0,
        "co2": 800.0
    },
    plant_type="tomato",
    growth_stage="flowering"
)

print(analysis.recommendations)  # List[ClimateRecommendation]
print(analysis.predicted_impact)  # {"growth_rate": +12%, "health_score": +8%}
```

**Features:**
- **Day/night adjustments** — separate thresholds for different periods
- **Plant-specific optima** — 500+ species profiles
- **ML predictions** — RandomForest models trained on historical data
- **Energy-aware** — balances performance with power consumption

---

### 3. Irrigation Predictor

**Advanced ML-based watering optimization**

```python
from app.services.ai import IrrigationPredictor

predictor = IrrigationPredictor(
    irrigation_ml_repo=ml_repo,
    model_registry=registry
)

# Get intelligent irrigation prediction
prediction = predictor.predict_irrigation(unit_id=1)

print(prediction.threshold.optimal_threshold)  # 45.2%
print(prediction.duration.recommended_seconds)  # 120s
print(prediction.timing.preferred_time)  # "14:30"
print(prediction.user_response.most_likely)  # "accept" | "delay" | "cancel"
```

**Models:**
- **Threshold adjustment** — learns optimal soil moisture per plant
- **Duration prediction** — calculates precise watering time
- **Timing optimization** — suggests best irrigation schedule
- **User behavior** — predicts acceptance/rejection likelihood

---

### 4. Growth Stage Predictor

**AI-powered growth cycle tracking**

```python
from app.services.ai import PlantGrowthPredictor

predictor = PlantGrowthPredictor(
    model_registry=registry,
    threshold_service=threshold_service
)

# Predict next growth stage
transition = predictor.predict_stage_transition(
    plant_id=1,
    current_stage="vegetative",
    days_in_stage=14,
    environmental_history=sensor_data
)

print(transition.next_stage)  # "flowering"
print(transition.predicted_days)  # 3-5 days
print(transition.confidence)  # 0.87
```

**Features:**
- **6 growth stages** — seedling → vegetative → pre-flowering → flowering → fruiting → harvest
- **Dynamic thresholds** — integrates with ThresholdService for plant-specific ranges
- **Confidence scoring** — reliability metrics for each prediction

---

### 5. Recommendation Provider

**Pluggable recommendation engine with LLM support**

```python
from app.services.ai import RecommendationProvider, RecommendationContext

provider = container.ai.recommendation_provider  # Rule-based or LLM

context = RecommendationContext(
    plant_id=1,
    unit_id=1,
    plant_type="basil",
    growth_stage="vegetative",
    symptoms=["leaf_curl"],
    environmental_data={"temperature": 32.0}
)

recommendations = provider.get_recommendations(context)

for rec in recommendations:
    print(f"[{rec.priority}] {rec.action}")
    print(f"  Rationale: {rec.rationale}")
    print(f"  Confidence: {rec.confidence:.2f}")
```

**Two implementations:**
- **RuleBasedRecommendationProvider** — always available, uses SYMPTOM_DATABASE
- **LLMRecommendationProvider** — delegates to ChatGPT/Claude/local model, auto-fallback

---

### 6. Environmental Health Scorer

**Leaf health prediction from environmental stress**

```python
from app.services.ai import EnvironmentalLeafHealthScorer

scorer = EnvironmentalLeafHealthScorer(
    threshold_service=threshold_service
)

# Score environmental impact on leaves
score = scorer.score_environmental_health(
    plant_type="tomato",
    growth_stage="fruiting",
    temperature=28.0,
    humidity=45.0,
    light_intensity=800.0
)

print(score.overall_score)  # 0-100
print(score.stress_factors)  # {"heat_stress": 0.6, "low_humidity": 0.4}
print(score.predicted_symptoms)  # ["leaf_curl", "wilting"]
```

---

### 7. Bayesian Threshold Adjuster

**Self-learning soil moisture optimization**

```python
from app.services.ai import BayesianThresholdAdjuster

adjuster = BayesianThresholdAdjuster(
    irrigation_ml_repo=ml_repo,
    workflow_repo=workflow_repo,
    threshold_service=threshold_service,
    notification_callback=lambda unit_id, user_id, result: notify(result),
    notification_tolerance=3.0  # Fire callback if adjustment >= 3%
)

# Update beliefs from user feedback
result = adjuster.update_from_feedback(
    unit_id=1,
    user_id=1,
    accepted=False,  # User rejected irrigation
    feedback_type="too_early"
)

print(result.new_threshold)  # 42.5% (adjusted from 45%)
print(result.confidence)  # 0.82
```

**Features:**
- **Bayesian learning** — probabilistic belief updates
- **Feedback-driven** — learns from accept/reject/delay actions
- **Notification hooks** — alerts when thresholds shift significantly

---

### 8. Continuous Monitoring Service

**Background health surveillance**

```python
from app.services.ai import ContinuousMonitoringService

monitor = ContinuousMonitoringService(
    disease_predictor=disease_predictor,
    climate_optimizer=optimizer,
    health_monitor=health_monitor,
    growth_predictor=growth_predictor,
    environmental_health_scorer=env_scorer,
    recommendation_provider=rec_provider,
    analytics_repo=analytics_repo,
    check_interval=300  # 5 minutes
)

# Auto-starts in container_builder
monitor.start_monitoring()

# Generates real-time insights:
# - Disease risk alerts (when risk > 0.5)
# - Climate optimization suggestions
# - Growth stage transitions
# - Environmental stress warnings
# - Recommended actions
```

**Six Analysis Steps:**
1. **Disease prediction** — risk scoring per unit
2. **Climate optimization** — environmental adjustments
3. **Growth tracking** — stage transition detection
4. **Trend analysis** — long-term pattern recognition
5. **Environmental health** — leaf stress scoring
6. **Recommendations** — actionable care suggestions

---

### 9. Automated Retraining

**Self-improving ML models**

```python
from app.services.ai import AutomatedRetrainingService

retraining = AutomatedRetrainingService(
    model_registry=registry,
    drift_detector=drift_detector,
    ml_trainer=trainer
)

# Register retraining jobs
retraining.add_job(
    model_type="climate_optimizer",
    schedule_type="weekly",
    schedule_day=2,  # Wednesday
    schedule_time="03:00",
    min_samples=100
)

retraining.add_job(
    model_type="disease",
    schedule_type="on_drift",
    drift_threshold=0.15,
    min_samples=50
)
```

**Triggers:**
- **Scheduled** — daily/weekly/monthly
- **On drift** — when model accuracy drops
- **Manual** — via API endpoint

---

### 10. Personalized Learning

**User-specific growth profiles**

```python
from app.services.ai import PersonalizedLearningService

learning = PersonalizedLearningService(
    model_registry=registry,
    training_data_repo=training_repo,
    profiles_dir=Path("data/user_profiles")
)

# Build personalized model
profile = learning.build_user_profile(user_id=1, min_grows=3)

# Get personalized predictions
prediction = learning.get_personalized_prediction(
    user_id=1,
    plant_type="tomato",
    current_conditions=sensor_data
)
```

---

## LLM Integration

SYSGrow supports multiple LLM backends for natural language recommendations and decision-making.

### Architecture

```
LLMBackend (ABC)
├── OpenAIBackend         ← ChatGPT / GPT-4o-mini
├── AnthropicBackend      ← Claude 3.5 Haiku / Sonnet
└── LocalTransformersBackend  ← EXAONE 4.0 1.2B / any HuggingFace model

LLMRecommendationProvider  ← Uses any backend, auto-fallback to rules
LLMAdvisorService          ← Free-form Q&A, diagnoses, care plans
```

### Setup Guide

**See:** [LLM_SETUP.md](LLM_SETUP.md) for complete setup instructions

#### OpenAI (ChatGPT)

```bash
# .env or ops.env
LLM_PROVIDER=openai
LLM_API_KEY=sk-proj-...
LLM_MODEL=gpt-4o-mini  # or gpt-4o
LLM_MAX_TOKENS=512
LLM_TEMPERATURE=0.3
```

**Install:**
```bash
pip install openai
```

#### Anthropic (Claude)

```bash
LLM_PROVIDER=anthropic
LLM_API_KEY=sk-ant-...
LLM_MODEL=claude-3-5-haiku-latest  # or claude-sonnet-4-20250514
```

**Install:**
```bash
pip install anthropic
```

#### Local Model (EXAONE 4.0 1.2B)

```bash
LLM_PROVIDER=local
LLM_LOCAL_MODEL_PATH=LGAI-EXAONE/EXAONE-4.0-1.2B-Instruct
LLM_LOCAL_DEVICE=auto  # cpu | cuda | mps
LLM_LOCAL_QUANTIZE=true  # 4-bit quantization for Raspberry Pi
LLM_LOCAL_TORCH_DTYPE=float16
```

**Install:**
```bash
pip install torch transformers
# Optional: for quantization
pip install bitsandbytes
```

**Raspberry Pi 5 (8GB):**
- EXAONE 4.0 1.2B runs smoothly with 4-bit quantization
- ~3-4 seconds per recommendation
- No internet required after model download

### Using the LLM Advisor

```python
from app.services.ai import LLMAdvisorService, DecisionQuery

advisor = container.optional_ai.llm_advisor

# Ask free-form questions
response = advisor.ask(DecisionQuery(
    question="Should I water my basil now?",
    plant_type="basil",
    growth_stage="vegetative",
    environmental_data={
        "temperature": 26.0,
        "humidity": 55.0,
        "soil_moisture": 28.0
    }
))

print(response.answer)  # "Yes, water now. Soil moisture is low..."
print(response.confidence)  # 0.85
print(response.suggested_actions)  # ["Water immediately", "Check drainage"]
```

**Convenience methods:**
```python
# Diagnose symptoms
advisor.diagnose(
    symptoms=["yellowing_leaves", "brown_spots"],
    plant_type="tomato"
)

# Should I irrigate?
advisor.should_irrigate(
    plant_type="basil",
    environmental_data=sensor_data
)

# Generate care plan
advisor.care_plan(
    plant_type="tomato",
    growth_stage="flowering"
)
```

---

## Model Management

### Model Registry

**Centralized ML model versioning and lifecycle**

```python
from app.services.ai import ModelRegistry, ModelMetadata, ModelStatus

registry = ModelRegistry(storage_path=Path("models"))

# Register new model
metadata = ModelMetadata(
    model_type="climate",
    version="1.2.0",
    performance_metrics={"accuracy": 0.89, "f1": 0.87},
    feature_names=["temp", "humidity", "co2"],
    training_samples=1500
)
registry.register_model("climate", model_obj, metadata)

# Load best model
model = registry.load_model("climate", version="latest")

# List versions
versions = registry.list_versions("climate")
```

### Drift Detection

**Automatic model performance monitoring**

```python
from app.services.ai import ModelDriftDetectorService

detector = ModelDriftDetectorService(
    model_registry=registry,
    analytics_repo=analytics_repo
)

# Check for drift
metrics = detector.check_drift(
    model_type="climate",
    recent_predictions=predictions,
    recent_actuals=actuals,
    window_size=100
)

print(metrics.accuracy_drift)  # -0.12 (dropped 12%)
print(metrics.confidence_drift)  # -0.08
print(metrics.requires_retraining)  # True
```

### Feature Engineering

**Automated feature extraction**

```python
from app.services.ai import FeatureEngineer, EnvironmentalFeatureExtractor

engineer = FeatureEngineer(feature_extractor)

# Extract ML features from sensor data
features = engineer.engineer_features(
    sensor_readings=readings,
    window_size=24,  # 24 hours
    feature_set="environmental_v1"
)

print(features.feature_vector)  # [temp_avg, temp_std, humidity_rolling, ...]
print(features.feature_names)
```

---

## Quick Start

### 1. Enable AI Services

```bash
# .env or ops.env
ENABLE_CONTINUOUS_MONITORING=true
ENABLE_AUTOMATED_RETRAINING=true
ENABLE_PERSONALIZED_LEARNING=true
ENABLE_TRAINING_DATA_COLLECTION=true
```

### 2. Choose LLM Provider (Optional)

```bash
# For cloud AI (OpenAI)
LLM_PROVIDER=openai
LLM_API_KEY=sk-...

# For privacy (local model)
LLM_PROVIDER=local
LLM_LOCAL_QUANTIZE=true
```

### 3. Start Application

```bash
python smart_agriculture_app.py
```

### 4. Access AI Features

**Web UI:**
- Plant health dashboard: `http://localhost:5000/plants/{id}/health`
- Recommendations: `http://localhost:5000/recommendations`

**API:**
```bash
# Get recommendations
curl http://localhost:5000/api/v1/recommendations/unit/1

# Get plant health analysis
curl http://localhost:5000/api/v1/plants/1/health/analyze

# Ask LLM advisor (if enabled)
curl -X POST http://localhost:5000/api/v1/advisor/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "Should I water my tomatoes?"}'
```

---

## Service Reference

| Service | Purpose | API Docs |
|---------|---------|----------|
| **PlantHealthMonitor** | Disease detection & symptom analysis | [PLANT_HEALTH_MONITORING.md](PLANT_HEALTH_MONITORING.md) |
| **IrrigationPredictor** | ML-based watering optimization | [IRRIGATION_ML_OPERATIONS.md](IRRIGATION_ML_OPERATIONS.md) |
| **ClimateOptimizer** | Environmental control optimization | [CLIMATE_OPTIMIZER.md](CLIMATE_OPTIMIZER.md) |
| **LLMRecommendationProvider** | AI-powered care recommendations | [LLM_SETUP.md](LLM_SETUP.md) |
| **LLMAdvisorService** | Natural language Q&A | [LLM_ADVISOR.md](LLM_ADVISOR.md) |
| **BayesianThresholdAdjuster** | Self-learning irrigation | [BAYESIAN_LEARNING.md](BAYESIAN_LEARNING.md) |
| **ContinuousMonitoringService** | Real-time surveillance | [CONTINUOUS_MONITORING.md](CONTINUOUS_MONITORING.md) |
| **AutomatedRetrainingService** | Model lifecycle management | [AUTOMATED_RETRAINING.md](AUTOMATED_RETRAINING.md) |

---

## Performance Considerations

### Raspberry Pi Optimization

**Model quantization:**
```python
# container_builder automatically enables quantization for Pi
use_model_quantization = config.use_model_quantization  # True on Pi
```

**Concurrent predictions:**
```python
max_concurrent_predictions = 3  # Limit parallel inference
```

**Cache settings:**
```python
model_cache_predictions = True  # Cache results for 5 minutes
model_cache_ttl = 300
```

### Resource Usage

| Service | CPU | RAM | Notes |
|---------|-----|-----|-------|
| RuleBasedRecommendationProvider | <1% | ~50MB | Always available |
| LLMRecommendationProvider (OpenAI) | <1% | ~50MB | API call latency ~500ms |
| LLMRecommendationProvider (Local) | 30-50% | ~2GB | EXAONE 1.2B quantized |
| ContinuousMonitoring | 2-5% | ~200MB | Background service |
| IrrigationPredictor | <1% | ~100MB | On-demand inference |

---

## Troubleshooting

**LLM not working?**
```bash
# Check configuration
python -c "from app.config import AppConfig; c = AppConfig(); print(c.llm_provider, c.llm_api_key[:8] if c.llm_api_key else 'NONE')"

# Check backend availability
python -c "from app.services.ai.llm_backends import create_backend; b = create_backend('openai', api_key='sk-...'); print(b.is_available)"
```

**Models not loading?**
```bash
# Check model directory
ls -la models/

# Force model retraining
curl -X POST http://localhost:5000/api/v1/ai/retrain/climate
```

**High CPU usage?**
```bash
# Disable optional services
export ENABLE_CONTINUOUS_MONITORING=false
export ENABLE_PERSONALIZED_LEARNING=false

# Reduce monitoring interval
export CONTINUOUS_MONITORING_INTERVAL=600  # 10 minutes
```

---

## Next Steps

- **[LLM Setup Guide](LLM_SETUP.md)** — Detailed LLM configuration
- **[Plant Health API](PLANT_HEALTH_API_REFERENCE.md)** — Health monitoring endpoints
- **[Irrigation ML](IRRIGATION_ML_OPERATIONS.md)** — Advanced watering optimization
- **[Architecture](../architecture/AI_ARCHITECTURE.md)** — Deep dive into AI system design

---

**Questions?** Check the [FAQ](FAQ.md) or open an issue on GitHub.
