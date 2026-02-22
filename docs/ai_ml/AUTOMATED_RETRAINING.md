# Automated Retraining Service

**Model lifecycle management and scheduled retraining**

---

## Overview

The Automated Retraining Service manages the lifecycle of ML models, automatically retraining them when performance degrades or on a scheduled basis. It integrates with ModelRegistry and DriftDetector to ensure models remain accurate as plant data evolves.

---

## Key Features

- **Scheduled retraining** — Daily, weekly, or monthly schedules
- **Drift-triggered retraining** — Automatic when model accuracy drops
- **Manual retraining** — On-demand via API
- **Model versioning** — Automatic version bumps with metadata
- **Performance tracking** — Compare new vs old model accuracy
- **Rollback support** — Revert to previous version if new model underperforms

---

## Quick Start

### Enabling Automated Retraining

```bash
# .env or ops.env
ENABLE_AUTOMATED_RETRAINING=true
```

### Scheduling Retraining Jobs

```python
from app.services.ai import AutomatedRetrainingService

retraining = container.optional_ai.automated_retraining

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
    drift_threshold=0.15,  # Retrain if accuracy drops >15%
    min_samples=50
)
```

---

## API Reference

### add_job()

**Purpose:** Register a retraining job (scheduled or drift-triggered)

**Parameters:**
- `model_type` (str) — Model to retrain
  - `"climate_optimizer"`, `"disease"`, `"irrigation_threshold"`, `"irrigation_duration"`, `"irrigation_timing"`, `"growth_stage"`
- `schedule_type` (str) — Trigger type
  - `"daily"` — Every day at specified time
  - `"weekly"` — Every week on specified day
  - `"monthly"` — First day of month
  - `"on_drift"` — When drift detected
- `schedule_day` (int, optional) — Day of week (0=Monday, for weekly jobs)
- `schedule_time` (str, optional) — Time in "HH:MM" format (for scheduled jobs)
- `drift_threshold` (float, optional) — Accuracy drop threshold (for drift jobs)
- `min_samples` (int) — Minimum training samples required

**Returns:** `job_id` (int)

**Example:**
```python
# Daily retraining at 2 AM
job_id = retraining.add_job(
    model_type="climate_optimizer",
    schedule_type="daily",
    schedule_time="02:00",
    min_samples=100
)
print(f"Scheduled job {job_id}")
```

---

### retrain_model()

**Purpose:** Manually trigger model retraining

**Parameters:**
- `model_type` (str) — Model to retrain
- `force` (bool, optional) — Skip drift check (default: False)
- `min_samples` (int, optional) — Minimum samples required

**Returns:** `RetrainingResult`
- `model_type` (str) — Model that was retrained
- `old_version` (str) — Previous model version
- `new_version` (str) — New model version
- `old_metrics` (dict) — Previous performance metrics
- `new_metrics` (dict) — New performance metrics
- `improvement` (float) — Accuracy improvement (%)
- `training_samples` (int) — Number of samples used
- `training_duration` (float) — Training time (seconds)

**Example:**
```python
result = retraining.retrain_model(
    model_type="climate_optimizer",
    force=True  # Retrain even if no drift detected
)

print(f"Retrained {result.model_type}: v{result.old_version} → v{result.new_version}")
print(f"Accuracy: {result.old_metrics['accuracy']:.2%} → {result.new_metrics['accuracy']:.2%}")
print(f"Improvement: {result.improvement:.1f}%")
print(f"Training time: {result.training_duration:.1f}s")
```

---

### get_retraining_schedule()

**Purpose:** List all scheduled retraining jobs

**Returns:** `List[RetrainingJob]`
- `job_id` (int)
- `model_type` (str)
- `schedule_type` (str)
- `schedule_config` (dict)
- `last_run` (datetime)
- `next_run` (datetime)

**Example:**
```python
jobs = retraining.get_retraining_schedule()

for job in jobs:
    print(f"[{job.job_id}] {job.model_type}: {job.schedule_type}")
    print(f"  Last run: {job.last_run}")
    print(f"  Next run: {job.next_run}")
```

---

### remove_job()

**Purpose:** Delete a scheduled retraining job

**Parameters:**
- `job_id` (int) — Job to remove

**Example:**
```python
retraining.remove_job(job_id=5)
print("Retraining job removed")
```

---

## Retraining Workflow

### Step 1: Check Trigger

**Scheduled jobs:**
```python
current_time = datetime.now()

for job in scheduled_jobs:
    if job.next_run <= current_time:
        # Trigger retraining
        _execute_retraining_job(job)
```

**Drift-triggered jobs:**
```python
for job in drift_jobs:
    # Check model drift
    drift_metrics = drift_detector.check_drift(
        model_type=job.model_type,
        recent_predictions=predictions,
        recent_actuals=actuals
    )
    
    if drift_metrics.accuracy_drift > job.drift_threshold:
        # Trigger retraining
        _execute_retraining_job(job)
```

---

### Step 2: Fetch Training Data

```python
# Get training samples from repository
training_data = training_data_repo.fetch_samples(
    model_type=model_type,
    min_samples=job.min_samples,
    time_range="last_90d"  # Use recent data only
)

if len(training_data) < job.min_samples:
    logger.warning(f"Insufficient samples: {len(training_data)} < {job.min_samples}")
    return  # Skip retraining
```

---

### Step 3: Feature Engineering

```python
# Extract features from raw data
features = feature_engineer.engineer_features(
    raw_data=training_data,
    feature_set=f"{model_type}_v1"
)

X = features.feature_matrix  # (n_samples, n_features)
y = training_data['target_variable']
```

---

### Step 4: Train Model

```python
# Train new model
new_model, metrics = ml_trainer.train_model(
    X=X,
    y=y,
    model_type=model_type,
    hyperparameters=model_config
)

# Validate on hold-out set
validation_metrics = ml_trainer.validate_model(
    model=new_model,
    X_val=X_validation,
    y_val=y_validation
)
```

---

### Step 5: Register New Model

```python
# Generate version number
old_version = model_registry.get_latest_version(model_type)
new_version = _bump_version(old_version)  # e.g., "1.2.0" → "1.3.0"

# Create metadata
metadata = ModelMetadata(
    model_type=model_type,
    version=new_version,
    performance_metrics=validation_metrics,
    feature_names=features.feature_names,
    training_samples=len(training_data),
    training_duration=training_end_time - training_start_time
)

# Register new model
model_registry.register_model(model_type, new_model, metadata)
```

---

### Step 6: Archive Old Model

```python
# Set old model status to "archived"
model_registry.set_model_status(
    model_type=model_type,
    version=old_version,
    status=ModelStatus.ARCHIVED
)

# Keep for potential rollback
logger.info(f"Archived {model_type} v{old_version}")
```

---

### Step 7: Notification

```python
# Send notification
notification = {
    "type": "model_retrained",
    "model_type": model_type,
    "old_version": old_version,
    "new_version": new_version,
    "old_accuracy": old_metrics['accuracy'],
    "new_accuracy": new_metrics['accuracy'],
    "improvement": (new_metrics['accuracy'] - old_metrics['accuracy']) * 100
}

notification_service.send(
    channel="admin",
    message=f"Model retrained: {model_type} v{new_version} (accuracy: {new_metrics['accuracy']:.2%})"
)
```

---

## Retraining Job Types

### Daily Retraining

**Use case:** High-velocity data (e.g., disease predictions)

```python
retraining.add_job(
    model_type="disease",
    schedule_type="daily",
    schedule_time="03:00",  # 3 AM
    min_samples=50
)
```

**Best for:**
- Models with fast-changing data
- High prediction volume
- Critical accuracy requirements

---

### Weekly Retraining

**Use case:** Standard production models

```python
retraining.add_job(
    model_type="climate_optimizer",
    schedule_type="weekly",
    schedule_day=2,  # Wednesday
    schedule_time="03:00",
    min_samples=100
)
```

**Best for:**
- Climate optimization
- Growth stage prediction
- Standard prediction models

**Recommended days:**
- Wednesday (mid-week, good data coverage)
- Sunday (off-peak, less resource contention)

---

### Monthly Retraining

**Use case:** Slow-changing models

```python
retraining.add_job(
    model_type="personalized_growth",
    schedule_type="monthly",
    schedule_time="03:00",
    min_samples=200
)
```

**Best for:**
- Personalized learning models
- Long-term trend models
- Models with slow feature drift

---

### Drift-Triggered Retraining

**Use case:** Adaptive retraining based on performance

```python
retraining.add_job(
    model_type="climate_optimizer",
    schedule_type="on_drift",
    drift_threshold=0.15,  # Retrain if accuracy drops >15%
    min_samples=100
)
```

**Best for:**
- Production-critical models
- Models with unpredictable drift
- Adaptive systems

**Drift detection runs:** Every 24 hours (configurable)

---

## Model Versioning

### Version Scheme

**Format:** `MAJOR.MINOR.PATCH`

**Examples:**
- `1.0.0` — Initial model
- `1.1.0` — Feature addition or minor improvement
- `1.2.0` — Scheduled retraining (weekly)
- `2.0.0` — Major architecture change

**Automatic bumping:**
```python
def _bump_version(old_version: str, bump_type: str = "minor") -> str:
    major, minor, patch = map(int, old_version.split('.'))
    
    if bump_type == "major":
        return f"{major + 1}.0.0"
    elif bump_type == "minor":
        return f"{major}.{minor + 1}.0"
    else:  # patch
        return f"{major}.{minor}.{patch + 1}"
```

---

### Rollback Strategy

**When to rollback:**
- New model accuracy < old model accuracy - 5%
- New model fails validation
- Production errors after deployment

**How to rollback:**
```python
# Revert to previous version
old_version = model_registry.get_previous_version(model_type, current_version)

model_registry.set_model_status(model_type, current_version, ModelStatus.ARCHIVED)
model_registry.set_model_status(model_type, old_version, ModelStatus.ACTIVE)

logger.warning(f"Rolled back {model_type}: v{current_version} → v{old_version}")
```

---

## Integration Examples

### Scheduled Retraining (Daily Cron)

```python
from app.workers import ScheduledTask

@ScheduledTask(interval=3600)  # Check every hour
def check_retraining_jobs():
    """Check and execute scheduled retraining jobs"""
    
    retraining = app.container.optional_ai.automated_retraining
    
    if not retraining:
        return
    
    # Check all jobs
    retraining.check_and_execute_jobs()
```

---

### Drift Detection (Daily)

```python
@ScheduledTask(interval=86400)  # Daily
def check_model_drift():
    """Check all models for drift and trigger retraining if needed"""
    
    drift_detector = app.container.ai.drift_detector
    retraining = app.container.optional_ai.automated_retraining
    
    model_types = ["climate_optimizer", "disease", "irrigation_threshold"]
    
    for model_type in model_types:
        # Check drift
        metrics = drift_detector.check_drift(
            model_type=model_type,
            recent_predictions=get_recent_predictions(model_type),
            recent_actuals=get_recent_actuals(model_type)
        )
        
        if metrics.requires_retraining:
            logger.info(f"Drift detected in {model_type} (drift: {metrics.accuracy_drift:.2%})")
            
            # Trigger retraining
            result = retraining.retrain_model(model_type=model_type, force=True)
            
            logger.info(f"Retrained {model_type}: accuracy {result.new_metrics['accuracy']:.2%}")
```

---

## API Endpoints

### POST /api/v1/ai/retrain/{model_type}

**Description:** Manually trigger model retraining

**Parameters:**
- `model_type` (path) — Model to retrain
- `force` (query, optional) — Skip drift check (default: false)

**Response:**
```json
{
  "model_type": "climate_optimizer",
  "old_version": "1.2.0",
  "new_version": "1.3.0",
  "old_metrics": {
    "accuracy": 0.87,
    "f1_score": 0.85
  },
  "new_metrics": {
    "accuracy": 0.91,
    "f1_score": 0.89
  },
  "improvement": 4.6,
  "training_samples": 1523,
  "training_duration": 45.2
}
```

### GET /api/v1/ai/retraining/schedule

**Description:** List all scheduled retraining jobs

**Response:**
```json
{
  "jobs": [
    {
      "job_id": 1,
      "model_type": "climate_optimizer",
      "schedule_type": "weekly",
      "schedule_config": {
        "day": 2,
        "time": "03:00"
      },
      "last_run": "2026-02-12T03:00:00Z",
      "next_run": "2026-02-19T03:00:00Z"
    },
    {
      "job_id": 2,
      "model_type": "disease",
      "schedule_type": "on_drift",
      "schedule_config": {
        "drift_threshold": 0.15
      },
      "last_run": "2026-02-10T04:15:00Z",
      "next_run": null
    }
  ]
}
```

### POST /api/v1/ai/retraining/schedule

**Description:** Add a new retraining job

**Request:**
```json
{
  "model_type": "climate_optimizer",
  "schedule_type": "weekly",
  "schedule_day": 2,
  "schedule_time": "03:00",
  "min_samples": 100
}
```

**Response:**
```json
{
  "job_id": 3,
  "message": "Retraining job scheduled"
}
```

### DELETE /api/v1/ai/retraining/schedule/{job_id}

**Description:** Remove a scheduled job

**Response:**
```json
{
  "message": "Retraining job removed"
}
```

---

## Performance Considerations

### Training Time

**Climate Optimizer (RandomForest):**
- 100 samples: ~5 seconds
- 500 samples: ~20 seconds
- 1000 samples: ~45 seconds

**Disease Predictor (RandomForest):**
- 100 samples: ~3 seconds
- 500 samples: ~15 seconds
- 1000 samples: ~35 seconds

**Irrigation Models (Gradient Boosting):**
- 100 samples: ~8 seconds
- 500 samples: ~30 seconds
- 1000 samples: ~60 seconds

---

### Resource Usage

**Raspberry Pi 5:**
- CPU: 50-70% during training
- Memory: ~500MB peak
- **Recommendation:** Schedule retraining during off-peak hours (2-4 AM)

**Desktop:**
- CPU: 20-40% during training
- Memory: ~300MB peak
- Can train anytime without performance impact

---

## Best Practices

### 1. Start with Weekly Retraining

```python
# Good default for production
retraining.add_job(
    model_type="climate_optimizer",
    schedule_type="weekly",
    schedule_day=2,  # Wednesday
    schedule_time="03:00",
    min_samples=100
)
```

### 2. Combine Scheduled + Drift-Triggered

```python
# Scheduled retraining as baseline
retraining.add_job(
    model_type="climate_optimizer",
    schedule_type="weekly",
    schedule_day=2,
    schedule_time="03:00",
    min_samples=100
)

# Drift-triggered as safety net
retraining.add_job(
    model_type="climate_optimizer",
    schedule_type="on_drift",
    drift_threshold=0.20,  # Higher threshold to avoid duplicate retraining
    min_samples=100
)
```

### 3. Monitor Retraining Results

```python
@ScheduledTask(interval=604800)  # Weekly
def review_retraining_results():
    """Review model retraining outcomes"""
    
    results = analytics_repo.get_insights(
        type="model_retrained",
        time_range="last_7d"
    )
    
    for result in results:
        improvement = result.data['improvement']
        
        if improvement < 0:
            logger.warning(f"Model {result.data['model_type']} degraded: {improvement:.1f}%")
        elif improvement > 10:
            logger.info(f"Significant improvement in {result.data['model_type']}: {improvement:.1f}%")
```

---

## Troubleshooting

### Issue: Retraining fails with insufficient samples

**Check available samples:**
```python
training_data = training_data_repo.fetch_samples(
    model_type="climate_optimizer",
    time_range="last_90d"
)
print(f"Available samples: {len(training_data)}")
```

**Solutions:**
- Reduce `min_samples` requirement
- Extend time range (90d → 180d)
- Enable training data collection: `ENABLE_TRAINING_DATA_COLLECTION=true`

---

### Issue: New model performs worse than old model

**Compare metrics:**
```python
result = retraining.retrain_model(model_type="climate_optimizer")

if result.improvement < -5:
    logger.error(f"Model degradation: {result.improvement:.1f}%")
    
    # Rollback to previous version
    model_registry.set_model_status(
        model_type="climate_optimizer",
        version=result.new_version,
        status=ModelStatus.ARCHIVED
    )
    model_registry.set_model_status(
        model_type="climate_optimizer",
        version=result.old_version,
        status=ModelStatus.ACTIVE
    )
```

---

## Related Documentation

- **[Model Registry](../architecture/AI_ARCHITECTURE.md#model-registry)** — Model versioning
- **[Drift Detection](../architecture/AI_ARCHITECTURE.md#drift-detection)** — Performance monitoring
- **[AI Services Overview](README.md)** — Complete AI feature guide
- **[FAQ](FAQ.md)** — Common questions

---

**Questions?** Check the [FAQ](FAQ.md) or open an issue on GitHub.
