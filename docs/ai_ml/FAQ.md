# AI & ML Frequently Asked Questions

**Common questions about SYSGrow's AI features**

---

## General Questions

### Q: Do I need AI features to use SYSGrow?

**A:** No! SYSGrow works perfectly without AI features enabled. All core functionality (device control, monitoring, scheduling) is available without ML models or LLM integration.

AI features are **optional enhancements** that provide:
- Predictive analytics
- Intelligent recommendations
- Natural language Q&A
- Self-learning optimization

To disable all AI features:
```bash
ENABLE_CONTINUOUS_MONITORING=false
ENABLE_AUTOMATED_RETRAINING=false
ENABLE_PERSONALIZED_LEARNING=false
LLM_PROVIDER=none
```

---

### Q: What's the difference between rule-based and LLM recommendations?

**A:** Two recommendation engines are available:

**RuleBasedRecommendationProvider** (always available):
- ✅ No dependencies (no API keys, no model downloads)
- ✅ Fast (<50ms response time)
- ✅ Predictable, consistent advice
- ✅ Works offline
- ❌ Limited to predefined symptom patterns
- ❌ No natural language understanding

**LLMRecommendationProvider** (optional):
- ✅ Understands complex scenarios
- ✅ Natural language explanations
- ✅ Contextual advice based on full plant history
- ✅ Learns from new plant knowledge (cloud models)
- ❌ Requires API key (OpenAI/Anthropic) or GPU (local)
- ❌ Slower (500ms-4s depending on provider)
- ❌ Costs money (cloud) or resources (local)

**Recommendation:** Start with rule-based, upgrade to LLM once you're comfortable.

---

### Q: Can I run this on a Raspberry Pi?

**A:** Yes! SYSGrow is optimized for Raspberry Pi.

**Raspberry Pi 5 (8GB) — Recommended:**
- ✅ All AI features work
- ✅ Local LLM models (EXAONE 4.0 1.2B with 4-bit quantization)
- ✅ Continuous monitoring
- ✅ Automated retraining
- ⚠️ Use quantization: `USE_MODEL_QUANTIZATION=true`

**Raspberry Pi 4 (4GB):**
- ✅ Core ML features (health monitoring, predictions)
- ⚠️ Disable continuous monitoring: `ENABLE_CONTINUOUS_MONITORING=false`
- ⚠️ Use cloud LLM instead of local: `LLM_PROVIDER=openai`

**Raspberry Pi 3 / Zero:**
- ✅ Core functionality works
- ❌ Disable all AI features (too slow)
- ❌ Use rule-based recommendations only

---

### Q: How much does LLM usage cost?

**A:** Depends on provider:

**OpenAI (gpt-4o-mini):**
- Per recommendation: ~$0.0003
- 1000 recommendations/day: ~$9/month
- Best for: Cloud-first users, best quality

**Anthropic (claude-3-5-haiku):**
- Per recommendation: ~$0.0018
- 1000 recommendations/day: ~$54/month
- Best for: Users who prefer Claude

**Local (EXAONE 4.0 1.2B):**
- One-time: Model download (~2GB bandwidth)
- Ongoing: Electricity (~$0.02/day on Pi)
- Monthly: **~$0.60**
- Best for: Privacy-conscious, offline operation

**Recommendation:** For hobby use, local models are most cost-effective. For commercial greenhouses, cloud LLMs provide best quality.

---

## LLM Integration

### Q: Which LLM provider should I choose?

**A:** Choose based on your needs:

**OpenAI (ChatGPT):**
- ✅ Best quality/cost ratio
- ✅ Fastest response times (~500ms)
- ✅ gpt-4o-mini is excellent for recommendations
- ✅ Reliable API uptime
- ❌ Requires internet
- ❌ Data sent to OpenAI servers

**Anthropic (Claude):**
- ✅ Excellent reasoning quality
- ✅ Strong at complex diagnostics
- ✅ Transparent pricing
- ❌ More expensive than OpenAI
- ❌ Requires internet
- ❌ Data sent to Anthropic servers

**Local (EXAONE/Llama/Qwen):**
- ✅ 100% private (data never leaves your device)
- ✅ Works offline
- ✅ No API costs
- ✅ Runs on Raspberry Pi 5 (8GB)
- ❌ Slower (3-4s per recommendation on Pi)
- ❌ Requires initial model download (~2GB)
- ❌ Lower quality than cloud models

**Recommendation:**
- **Hobby growers:** Local model (EXAONE 4.0 1.2B)
- **Commercial greenhouses:** OpenAI (gpt-4o-mini)
- **Privacy-critical:** Local model
- **Best quality:** OpenAI (gpt-4o) or Anthropic (Claude Sonnet)

---

### Q: How do I switch LLM providers?

**A:** Just change environment variables and restart:

```bash
# Switch to OpenAI
export LLM_PROVIDER=openai
export LLM_API_KEY=sk-proj-...
export LLM_MODEL=gpt-4o-mini

# Switch to Anthropic
export LLM_PROVIDER=anthropic
export LLM_API_KEY=sk-ant-...
export LLM_MODEL=claude-3-5-haiku-latest

# Switch to local
export LLM_PROVIDER=local
export LLM_LOCAL_MODEL_PATH=LGAI-EXAONE/EXAONE-4.0-1.2B-Instruct
export LLM_LOCAL_QUANTIZE=true

# Disable LLM (use rules only)
export LLM_PROVIDER=none

# Restart application
python smart_agriculture_app.py
```

No code changes required! The backend automatically switches.

---

### Q: Can I use my own LLM API endpoint?

**A:** Yes! Set `LLM_BASE_URL`:

```bash
# Azure OpenAI
LLM_PROVIDER=openai
LLM_BASE_URL=https://your-resource.openai.azure.com/
LLM_API_KEY=<azure-key>
LLM_MODEL=gpt-4o-mini

# Custom proxy
LLM_PROVIDER=openai
LLM_BASE_URL=https://your-proxy.com/v1
LLM_API_KEY=your-proxy-key

# Self-hosted Ollama
LLM_PROVIDER=openai  # Ollama is OpenAI-compatible
LLM_BASE_URL=http://localhost:11434/v1
LLM_API_KEY=dummy  # Ollama doesn't require key
LLM_MODEL=llama3.2:1b
```

---

### Q: My local model is too slow. How can I speed it up?

**A:** Try these optimizations:

**1. Enable 4-bit quantization:**
```bash
LLM_LOCAL_QUANTIZE=true
LLM_LOCAL_TORCH_DTYPE=float16
```

**2. Use a smaller model:**
```bash
# Switch from EXAONE 1.2B to Qwen 0.5B
LLM_LOCAL_MODEL_PATH=Qwen/Qwen2.5-0.5B-Instruct
```

**3. Reduce max tokens:**
```bash
LLM_MAX_TOKENS=256  # Instead of 512
```

**4. Use GPU if available:**
```bash
LLM_LOCAL_DEVICE=cuda  # NVIDIA GPU
LLM_LOCAL_DEVICE=mps   # Apple Silicon
```

**5. Cache predictions:**
```bash
MODEL_CACHE_PREDICTIONS=true
MODEL_CACHE_TTL=300  # 5 minutes
```

**6. Fallback to cloud for critical queries:**
```python
# Use local for routine recommendations
# Use OpenAI for complex diagnostics
if query_complexity == "high":
    use_cloud_llm()
else:
    use_local_llm()
```

---

## Model Training & Retraining

### Q: How are ML models trained?

**A:** Models are trained on historical sensor data + user feedback:

**Initial Training:**
- **Irrigation models:** Pre-trained on 500+ plant profiles
- **Climate optimizer:** Pre-trained on greenhouse datasets
- **Disease predictor:** Trained on symptom databases + environmental correlations

**Continuous Learning:**
- As you use SYSGrow, training data is collected
- Models retrain weekly (configurable) or on-drift
- User feedback (accept/reject irrigation) improves threshold models

**Data Collection:**
```bash
ENABLE_TRAINING_DATA_COLLECTION=true  # Enable data collection
ENABLE_AUTOMATED_RETRAINING=true      # Enable weekly retraining
```

---

### Q: What is model drift detection?

**A:** Drift detection monitors model performance over time:

**How it works:**
1. Store predictions + actual outcomes
2. Calculate recent accuracy (last 100 predictions)
3. Compare to baseline accuracy (training time)
4. If accuracy drops >15%, trigger retraining

**Example:**
```
Climate optimizer baseline: 89% accuracy
Recent predictions: 72% accuracy
Drift: -17% → TRIGGER RETRAINING
```

**Configuration:**
```bash
ENABLE_AUTOMATED_RETRAINING=true

# Drift threshold
DRIFT_DETECTION_THRESHOLD=0.15  # 15% accuracy drop

# Minimum samples before retraining
MIN_RETRAINING_SAMPLES=100
```

---

### Q: Can I manually retrain models?

**A:** Yes! Three ways:

**1. API endpoint:**
```bash
curl -X POST http://localhost:5000/api/v1/ai/retrain/climate_optimizer
```

**2. Python code:**
```python
from app.services.ai import AutomatedRetrainingService

retraining = app.container.optional_ai.automated_retraining
result = retraining.retrain_model(
    model_type="climate_optimizer",
    force=True
)
print(f"New version: {result.new_version}")
print(f"Accuracy: {result.new_metrics['accuracy']:.2%}")
```

**3. Scheduled job:**
```python
# Retrain every Wednesday at 3 AM
retraining.add_job(
    model_type="climate_optimizer",
    schedule_type="weekly",
    schedule_day=2,  # Wednesday
    schedule_time="03:00",
    min_samples=100
)
```

---

### Q: What is personalized learning?

**A:** Personalized learning builds user-specific models:

**How it works:**
1. User completes **3+ successful grows**
2. System extracts user-specific training data
3. Builds personalized model for that user
4. Future predictions use personalized model when available

**Benefits:**
- Adapts to your unique environment (climate, soil, etc.)
- Learns your preferences (watering frequency, tolerance for risk)
- Improves accuracy over time

**Enable:**
```bash
ENABLE_PERSONALIZED_LEARNING=true
```

**Check if profile is ready:**
```python
from app.services.ai import PersonalizedLearningService

learning = app.container.optional_ai.personalized_learning
profile = learning.get_user_profile(user_id=1)

if profile and profile.model_ready:
    print(f"Personalized model ready! ({profile.grows_analyzed} grows)")
else:
    print("Need more grows for personalization")
```

---

## Plant Health & Monitoring

### Q: How does disease detection work?

**A:** Three-layer approach:

**1. Symptom Pattern Matching:**
- User reports symptoms (yellowing leaves, brown spots, etc.)
- System matches against 12+ known symptom patterns
- Generates initial disease candidates

**2. Environmental Correlation:**
- Analyzes sensor data for anomalies
- Links symptoms to environmental stress (heat, humidity, etc.)
- Adjusts disease probabilities

**3. ML Prediction:**
- RandomForest classifier trained on historical data
- Predicts disease probability for each unit
- Confidence scoring (0-1)

**Example:**
```
Symptoms: yellowing_leaves, wilting
Environment: temp=32°C (above optimal 25°C)
            humidity=45% (below optimal 60%)

Pattern Match: Heat stress + low humidity
Correlation: Temperature anomaly +7°C
ML Prediction: Heat stress (0.89 probability)

Recommendation: Increase humidity, lower temperature
```

---

### Q: What is continuous monitoring?

**A:** Background service that runs every 5 minutes:

**Six analysis steps:**
1. **Disease prediction** — risk scoring per unit
2. **Climate optimization** — environmental adjustments
3. **Growth tracking** — stage transition detection
4. **Trend analysis** — long-term pattern recognition
5. **Environmental health** — leaf stress scoring
6. **Recommendations** — actionable care suggestions

**Insights stored in database:**
```python
# Query recent alerts
insights = analytics_repo.get_insights(
    unit_id=1,
    insight_type="disease_risk",
    severity="high",
    time_range="last_24h"
)
```

**Enable/disable:**
```bash
ENABLE_CONTINUOUS_MONITORING=true

# Adjust interval (seconds)
CONTINUOUS_MONITORING_INTERVAL=300  # 5 minutes
```

---

### Q: How accurate are the predictions?

**A:** Accuracy varies by model and data quality:

**Plant Health Monitor:**
- **Symptom detection:** 95%+ (rule-based patterns)
- **Environmental correlation:** 85-90% (statistical analysis)
- **Disease prediction:** 75-85% (ML classifier)

**Climate Optimizer:**
- **Optimal conditions:** 85-90% (RandomForest)
- **Impact prediction:** 70-80% (depends on plant variability)

**Irrigation Predictor:**
- **Threshold adjustment:** 80-85% (Bayesian learning)
- **Duration prediction:** 75-80% (RandomForest)
- **User response:** 65-75% (logistic regression)

**Growth Predictor:**
- **Stage transition:** 70-80% (depends on data quality)
- **Days to transition:** ±2-3 days (80% confidence interval)

**Factors affecting accuracy:**
- **Data quality** — more sensors = better predictions
- **Training data** — more grows = better models
- **User feedback** — accept/reject irrigation improves models
- **Plant variability** — some species are more predictable

---

## Performance & Optimization

### Q: My Raspberry Pi is running hot. How can I reduce CPU usage?

**A:** Try these optimizations:

**1. Disable optional services:**
```bash
ENABLE_CONTINUOUS_MONITORING=false
ENABLE_PERSONALIZED_LEARNING=false
ENABLE_AUTOMATED_RETRAINING=false
```

**2. Increase monitoring interval:**
```bash
CONTINUOUS_MONITORING_INTERVAL=600  # 10 minutes instead of 5
```

**3. Use cloud LLM instead of local:**
```bash
LLM_PROVIDER=openai  # Instead of "local"
```

**4. Enable model quantization:**
```bash
USE_MODEL_QUANTIZATION=true
```

**5. Cache predictions:**
```bash
MODEL_CACHE_PREDICTIONS=true
MODEL_CACHE_TTL=300
```

**6. Limit concurrent predictions:**
```bash
MAX_CONCURRENT_PREDICTIONS=1  # Instead of 3
```

---

### Q: Models are not loading. What should I check?

**A:** Troubleshooting checklist:

**1. Check model directory exists:**
```bash
ls -la models/
# Should contain: climate/, disease/, irrigation_threshold/, etc.
```

**2. Check model files:**
```bash
ls -la models/climate/
# Should contain: *.pkl and *_metadata.json files
```

**3. Force model retraining:**
```bash
curl -X POST http://localhost:5000/api/v1/ai/retrain/climate
```

**4. Check logs:**
```bash
tail -f logs/app.log | grep "ModelRegistry"
```

**5. Verify permissions:**
```bash
chmod -R 755 models/
```

**6. Test model loading:**
```python
from app.services.ai import ModelRegistry
from pathlib import Path

registry = ModelRegistry(storage_path=Path("models"))
try:
    model = registry.load_model("climate", version="latest")
    print("Model loaded successfully")
except Exception as e:
    print(f"Error: {e}")
```

---

### Q: How can I reduce memory usage?

**A:** Memory optimization strategies:

**1. Use 4-bit quantization (local LLM):**
```bash
LLM_LOCAL_QUANTIZE=true
# Memory: 1.2B model → 500MB (vs 2GB full precision)
```

**2. Use smaller LLM model:**
```bash
LLM_LOCAL_MODEL_PATH=Qwen/Qwen2.5-0.5B-Instruct
# Memory: ~400MB
```

**3. Disable model caching:**
```bash
MODEL_CACHE_PREDICTIONS=false
```

**4. Reduce cache TTL:**
```bash
MODEL_CACHE_TTL=60  # 1 minute instead of 5
```

**5. Limit monitoring services:**
```bash
ENABLE_CONTINUOUS_MONITORING=false
```

**6. Use cloud LLM:**
```bash
LLM_PROVIDER=openai  # No local model in memory
```

---

## Troubleshooting

### Q: LLM is not working. How do I debug?

**A:** Step-by-step debugging:

**1. Check configuration:**
```bash
python -c "from app.config import AppConfig; c = AppConfig(); \
  print('Provider:', c.llm_provider); \
  print('API Key:', c.llm_api_key[:10] + '...' if c.llm_api_key else 'NONE'); \
  print('Model:', c.llm_model)"
```

**2. Test backend availability:**
```bash
python -c "from app.services.ai.llm_backends import create_backend; \
  b = create_backend('openai', api_key='sk-...', model='gpt-4o-mini'); \
  print('Available:', b.is_available); \
  r = b.generate('You are helpful.', 'Say hello.'); \
  print('Response:', r.content)"
```

**3. Check dependencies:**
```bash
pip list | grep -E "openai|anthropic|torch|transformers"
```

**4. Check provider type:**
```python
from flask import current_app
ai = current_app.container.ai
print(type(ai.recommendation_provider).__name__)
# Should be: "LLMRecommendationProvider" or "RuleBasedRecommendationProvider"
```

**5. Check logs:**
```bash
tail -f logs/app.log | grep -E "LLM|Backend"
```

**Common errors:**

- **"Authentication failed"** → Check `LLM_API_KEY`
- **"Module not found: openai"** → Run `pip install openai`
- **"Model not found"** → Check `LLM_MODEL` name
- **"CUDA out of memory"** → Enable quantization: `LLM_LOCAL_QUANTIZE=true`
- **"Timeout after 30s"** → Increase `LLM_TIMEOUT=60`

---

### Q: How do I reset all AI models?

**A:** Complete AI reset:

**1. Stop application:**
```bash
pkill -f smart_agriculture_app.py
```

**2. Backup existing models:**
```bash
mv models models_backup_$(date +%Y%m%d)
```

**3. Delete model directory:**
```bash
rm -rf models/
mkdir models
```

**4. Clear analytics data (optional):**
```bash
sqlite3 sysgrow.db "DELETE FROM analytics WHERE type LIKE 'ai_%';"
```

**5. Restart application:**
```bash
python smart_agriculture_app.py
```

**6. Force retraining:**
```bash
curl -X POST http://localhost:5000/api/v1/ai/retrain/climate
curl -X POST http://localhost:5000/api/v1/ai/retrain/disease
curl -X POST http://localhost:5000/api/v1/ai/retrain/irrigation_threshold
```

---

### Q: Can I export AI recommendations to a file?

**A:** Yes! Several options:

**1. API endpoint:**
```bash
curl http://localhost:5000/api/v1/recommendations/unit/1 > recommendations.json
```

**2. Query database:**
```bash
sqlite3 sysgrow.db \
  "SELECT * FROM analytics WHERE type='recommendation' ORDER BY timestamp DESC LIMIT 100;" \
  -header -csv > recommendations.csv
```

**3. Python script:**
```python
from app.repositories import AnalyticsRepository
import json

repo = AnalyticsRepository()
insights = repo.get_insights(
    insight_type="recommendation",
    time_range="last_7d"
)

with open("recommendations.json", "w") as f:
    json.dump([i.to_dict() for i in insights], f, indent=2)
```

---

## Next Steps

- **[AI Services Overview](README.md)** — Complete feature guide
- **[LLM Setup](LLM_SETUP.md)** — Detailed LLM configuration
- **[Quick Reference](QUICK_REFERENCE.md)** — Code snippets & commands
- **[Architecture](../architecture/AI_ARCHITECTURE.md)** — Deep dive into AI system

---

**Still have questions?** Open an issue on GitHub!
