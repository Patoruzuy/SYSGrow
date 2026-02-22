# AI Services Quick Reference

**Essential commands and code snippets for SYSGrow AI features**

---

## 🚀 Quick Setup

### Enable AI Features
```bash
# .env or ops.env
ENABLE_CONTINUOUS_MONITORING=true
ENABLE_AUTOMATED_RETRAINING=true
ENABLE_TRAINING_DATA_COLLECTION=true
```

### Choose LLM Provider
```bash
# OpenAI (Cloud)
LLM_PROVIDER=openai
LLM_API_KEY=sk-proj-...
LLM_MODEL=gpt-4o-mini

# Anthropic (Cloud)
LLM_PROVIDER=anthropic
LLM_API_KEY=sk-ant-...
LLM_MODEL=claude-3-5-haiku-latest

# Local (Privacy)
LLM_PROVIDER=local
LLM_LOCAL_MODEL_PATH=LGAI-EXAONE/EXAONE-4.0-1.2B-Instruct
LLM_LOCAL_QUANTIZE=true

# None (Rules Only)
LLM_PROVIDER=none
```

---

## 🤖 Service Access

### Get AI Container
```python
from flask import current_app

# In request context
ai = current_app.container.ai
optional_ai = current_app.container.optional_ai
```

---

## 💊 Plant Health

### Analyze Plant Health
```python
from app.services.ai import PlantHealthMonitor

health_monitor = ai.health_monitor

observation = health_monitor.analyze_plant_health(
    plant_id=1,
    unit_id=1,
    symptoms=["yellowing_leaves", "wilting"],
    environmental_data={
        "temperature": 28.0,
        "humidity": 85.0,
        "soil_moisture": 32.0
    }
)

print(f"Status: {observation.health_status}")  # "warning" | "critical" | "healthy"
print(f"Severity: {observation.severity_score}/100")
print(f"Issues: {observation.detected_issues}")
```

### Get Disease Predictions
```python
from app.services.ai import DiseasePredictionService

disease_predictor = ai.disease_predictor

predictions = disease_predictor.predict_diseases(
    unit_id=1,
    symptoms=["yellowing_leaves", "brown_spots"],
    environmental_data=sensor_data
)

for pred in predictions:
    print(f"{pred.disease_name}: {pred.probability:.1%}")
    print(f"  Symptoms: {pred.matched_symptoms}")
```

---

## 🌡️ Climate Optimization

### Get Climate Recommendations
```python
from app.services.ai import ClimateOptimizer

optimizer = ai.climate_optimizer

analysis = optimizer.optimize_climate(
    unit_id=1,
    current_conditions={
        "temperature": 24.0,
        "humidity": 60.0,
        "co2": 800.0,
        "light_intensity": 600.0
    },
    plant_type="tomato",
    growth_stage="flowering"
)

for rec in analysis.recommendations:
    print(f"{rec.parameter}: {rec.suggested_value} (currently {rec.current_value})")
    print(f"  Impact: {rec.predicted_impact}")
```

---

## 💧 Irrigation

### Get ML Irrigation Prediction
```python
from app.services.ai import IrrigationPredictor

predictor = ai.irrigation_predictor

prediction = predictor.predict_irrigation(unit_id=1)

print(f"Optimal threshold: {prediction.threshold.optimal_threshold}%")
print(f"Recommended duration: {prediction.duration.recommended_seconds}s")
print(f"Best time: {prediction.timing.preferred_time}")
print(f"User likely to: {prediction.user_response.most_likely}")
```

### Update Bayesian Threshold
```python
from app.services.ai import BayesianThresholdAdjuster

adjuster = optional_ai.bayesian_adjuster

result = adjuster.update_from_feedback(
    unit_id=1,
    user_id=1,
    accepted=False,  # User rejected irrigation
    feedback_type="too_early"  # "too_early" | "too_late" | "delay"
)

print(f"New threshold: {result.new_threshold}%")
print(f"Adjustment: {result.adjustment:.1f}%")
print(f"Confidence: {result.confidence:.2f}")
```

---

## 🌱 Growth Prediction

### Predict Stage Transition
```python
from app.services.ai import PlantGrowthPredictor

growth_predictor = ai.growth_predictor

transition = growth_predictor.predict_stage_transition(
    plant_id=1,
    current_stage="vegetative",
    days_in_stage=14,
    environmental_history=sensor_readings
)

print(f"Next stage: {transition.next_stage}")
print(f"Predicted in: {transition.predicted_days} days")
print(f"Confidence: {transition.confidence:.2f}")
```

---

## 📝 Recommendations

### Get Recommendations (Auto LLM/Rules)
```python
from app.services.ai import RecommendationContext

rec_provider = ai.recommendation_provider

context = RecommendationContext(
    plant_id=1,
    unit_id=1,
    plant_type="basil",
    growth_stage="vegetative",
    symptoms=["leaf_curl"],
    environmental_data={
        "temperature": 32.0,
        "humidity": 45.0,
        "soil_moisture": 25.0
    }
)

recommendations = rec_provider.get_recommendations(context)

for rec in recommendations:
    print(f"[{rec.priority}] {rec.action}")
    print(f"  {rec.rationale}")
    print(f"  Confidence: {rec.confidence:.2f}")
    print(f"  Category: {rec.category}")
```

---

## 💬 LLM Advisor

### Ask Free-Form Questions
```python
from app.services.ai import LLMAdvisorService, DecisionQuery

advisor = optional_ai.llm_advisor

if advisor:
    response = advisor.ask(DecisionQuery(
        question="My basil leaves are curling. What should I do?",
        plant_type="basil",
        growth_stage="vegetative",
        environmental_data={
            "temperature": 28.0,
            "humidity": 55.0
        }
    ))
    
    print(response.answer)
    print(f"Confidence: {response.confidence:.2f}")
    for action in response.suggested_actions:
        print(f"  • {action}")
else:
    print("LLM advisor not available (set LLM_PROVIDER)")
```

### Diagnose Symptoms
```python
diagnosis = advisor.diagnose(
    symptoms=["yellowing_leaves", "wilting", "brown_spots"],
    plant_type="tomato",
    environmental_data={"temperature": 30.0}
)
print(diagnosis.answer)
```

### Irrigation Decision
```python
decision = advisor.should_irrigate(
    plant_type="basil",
    environmental_data={
        "soil_moisture": 25.0,
        "temperature": 26.0
    }
)
print(decision.answer)  # "Yes, water now..." or "Wait, soil is adequate..."
```

### Generate Care Plan
```python
care_plan = advisor.care_plan(
    plant_type="tomato",
    growth_stage="flowering",
    environmental_data=sensor_data
)
print(care_plan.answer)  # Detailed daily care instructions
```

---

## 🔄 Model Management

### Load Model
```python
from app.services.ai import ModelRegistry

registry = ai.model_registry

model = registry.load_model("climate", version="latest")
# Or specific version: version="1.2.0"
```

### List Model Versions
```python
versions = registry.list_versions("climate")
print(versions)  # ["1.0.0", "1.1.0", "1.2.0"]
```

### Register New Model
```python
from app.services.ai import ModelMetadata

metadata = ModelMetadata(
    model_type="climate",
    version="1.3.0",
    performance_metrics={
        "accuracy": 0.91,
        "f1_score": 0.89
    },
    feature_names=["temp_mean", "humidity_mean", "co2_mean"],
    training_samples=2000
)

registry.register_model("climate", trained_model, metadata)
```

---

## 📊 Drift Detection

### Check Model Drift
```python
from app.services.ai import ModelDriftDetectorService

drift_detector = ai.drift_detector

metrics = drift_detector.check_drift(
    model_type="climate",
    recent_predictions=predictions,
    recent_actuals=actuals,
    window_size=100
)

print(f"Accuracy drift: {metrics.accuracy_drift:.2%}")
print(f"Confidence drift: {metrics.confidence_drift:.2%}")
print(f"Requires retraining: {metrics.requires_retraining}")
```

---

## 🏋️ Model Retraining

### Trigger Manual Retraining
```python
from app.services.ai import AutomatedRetrainingService

retraining = optional_ai.automated_retraining

result = retraining.retrain_model(
    model_type="climate_optimizer",
    force=True  # Skip drift check
)

print(f"New version: {result.new_version}")
print(f"Accuracy: {result.new_metrics['accuracy']:.2%}")
print(f"Training samples: {result.training_samples}")
```

### Schedule Retraining Job
```python
# Weekly retraining (Wednesdays at 3 AM)
retraining.add_job(
    model_type="climate_optimizer",
    schedule_type="weekly",
    schedule_day=2,  # 0=Monday, 6=Sunday
    schedule_time="03:00",
    min_samples=100
)

# Drift-triggered retraining
retraining.add_job(
    model_type="disease",
    schedule_type="on_drift",
    drift_threshold=0.15,  # 15% accuracy drop
    min_samples=50
)
```

---

## 🎯 Personalized Learning

### Build User Profile
```python
from app.services.ai import PersonalizedLearningService

learning = optional_ai.personalized_learning

if learning:
    profile = learning.build_user_profile(
        user_id=1,
        min_grows=3  # Requires 3+ completed grows
    )
    
    if profile:
        print(f"Profile ready: {profile.model_ready}")
        print(f"Total grows: {profile.grows_analyzed}")
```

### Get Personalized Prediction
```python
prediction = learning.get_personalized_prediction(
    user_id=1,
    plant_type="tomato",
    current_conditions=sensor_data,
    prediction_type="growth_rate"
)

print(f"Predicted growth rate: {prediction.value} cm/day")
print(f"Using personalized model: {prediction.is_personalized}")
```

---

## 📈 Feature Engineering

### Extract Environmental Features
```python
from app.services.ai import FeatureEngineer

engineer = ai.feature_engineer

features = engineer.engineer_features(
    sensor_readings=readings,
    window_size=24,  # 24 hours
    feature_set="environmental_v1"
)

print(features.feature_vector)  # [23.5, 1.2, 65.0, ...]
print(features.feature_names)   # ["temp_mean_24h", "temp_std_24h", ...]
```

---

## 🔧 Configuration

### Check Current Config
```python
from app.config import AppConfig

config = AppConfig()

print(f"Continuous monitoring: {config.enable_continuous_monitoring}")
print(f"LLM provider: {config.llm_provider}")
print(f"Model quantization: {config.use_model_quantization}")
```

### Runtime Feature Checks
```python
# Check if LLM is available
if optional_ai.llm_advisor:
    print("LLM advisor available")
else:
    print("Using rule-based recommendations only")

# Check if personalized learning is enabled
if optional_ai.personalized_learning:
    print("Personalized learning active")
```

---

## 🌐 API Endpoints

### Health Analysis
```bash
POST /api/v1/plants/{plant_id}/health/analyze
Content-Type: application/json

{
  "symptoms": ["yellowing_leaves", "wilting"],
  "environmental_data": {
    "temperature": 28.0,
    "humidity": 85.0
  }
}
```

### Climate Optimization
```bash
GET /api/v1/units/{unit_id}/climate/optimize
```

### Irrigation Prediction
```bash
GET /api/v1/units/{unit_id}/irrigation/predict
```

### Recommendations
```bash
GET /api/v1/recommendations/unit/{unit_id}?include_llm=true
```

### LLM Advisor
```bash
POST /api/v1/advisor/ask
Content-Type: application/json

{
  "question": "Should I water my tomatoes?",
  "plant_id": 1,
  "plant_type": "tomato",
  "environmental_data": {
    "soil_moisture": 30.0
  }
}
```

### Model Retraining
```bash
POST /api/v1/ai/retrain/{model_type}
```

### Model Status
```bash
GET /api/v1/ai/models/{model_type}/status
```

---

## 🐛 Debugging

### Check Backend Availability
```python
# Test LLM backend
from app.services.ai.llm_backends import create_backend

backend = create_backend(
    provider="openai",
    api_key="sk-...",
    model="gpt-4o-mini"
)

print(f"Available: {backend.is_available}")
print(f"Provider: {backend.provider_name}")
```

### Test Recommendation Provider
```python
# Get provider type
print(type(ai.recommendation_provider).__name__)
# Output: "LLMRecommendationProvider" or "RuleBasedRecommendationProvider"

# Check if LLM is being used
if hasattr(ai.recommendation_provider, '_backend'):
    print("Using LLM backend")
else:
    print("Using rule-based only")
```

### View Model Metadata
```python
metadata = registry.get_model_metadata("climate", version="latest")
print(f"Version: {metadata.version}")
print(f"Accuracy: {metadata.performance_metrics['accuracy']:.2%}")
print(f"Training samples: {metadata.training_samples}")
print(f"Created: {metadata.created_at}")
```

---

## 📚 Common Patterns

### Pattern 1: Health Check with Recommendations
```python
# 1. Analyze health
observation = health_monitor.analyze_plant_health(...)

# 2. Get recommendations
context = RecommendationContext(
    plant_id=observation.plant_id,
    symptoms=observation.detected_issues,
    environmental_data=sensor_data
)
recommendations = rec_provider.get_recommendations(context)

# 3. Store insights
analytics_repo.store_insight(
    type="health_check",
    severity=observation.health_status,
    data={
        "observation": observation.to_dict(),
        "recommendations": [r.to_dict() for r in recommendations]
    }
)
```

### Pattern 2: Irrigation Decision Pipeline
```python
# 1. Get ML prediction
prediction = irrigation_predictor.predict_irrigation(unit_id)

# 2. Ask LLM advisor (if available)
if advisor:
    decision = advisor.should_irrigate(
        plant_type=unit.plant_type,
        environmental_data=sensor_data
    )
    print(decision.answer)

# 3. Update threshold from feedback
if user_accepted:
    adjuster.update_from_feedback(
        unit_id=unit_id,
        user_id=user_id,
        accepted=True
    )
```

### Pattern 3: Continuous Monitoring Insights
```python
# Query recent insights from continuous monitoring
insights = analytics_repo.get_insights(
    unit_id=1,
    insight_type="disease_risk",
    time_range="last_24h"
)

for insight in insights:
    print(f"{insight.timestamp}: {insight.data['disease']}")
    print(f"  Probability: {insight.data['probability']:.1%}")
```

---

## ⚡ Performance Tips

### Raspberry Pi Optimization
```bash
# Use quantized models
USE_MODEL_QUANTIZATION=true

# Cache predictions
MODEL_CACHE_PREDICTIONS=true
MODEL_CACHE_TTL=300

# Reduce monitoring frequency
CONTINUOUS_MONITORING_INTERVAL=600  # 10 minutes

# Use local LLM or disable
LLM_PROVIDER=local
LLM_LOCAL_QUANTIZE=true
```

### Desktop Optimization
```bash
# Disable quantization (use GPU)
USE_MODEL_QUANTIZATION=false

# Aggressive monitoring
CONTINUOUS_MONITORING_INTERVAL=300  # 5 minutes

# Use cloud LLM for best quality
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o
```

---

## 📖 Further Reading

- **[AI Services Overview](README.md)** — Complete feature guide
- **[LLM Setup](LLM_SETUP.md)** — Detailed LLM configuration
- **[Architecture](../architecture/AI_ARCHITECTURE.md)** — Deep dive into AI system design
- **[Plant Health API](PLANT_HEALTH_API_REFERENCE.md)** — Health monitoring reference
- **[Irrigation ML](IRRIGATION_ML_OPERATIONS.md)** — ML-based watering optimization

---

**Need help?** Check the [FAQ](FAQ.md) or open an issue on GitHub.
