# ML/AI API Documentation

Complete API reference for SYSGrow AI and Machine Learning endpoints.

**Base URL:** `/api/ml`

---

## Table of Contents

- [Base Endpoints](#base-endpoints)
- [Predictions](#predictions)
  - [Disease Predictions](#disease-predictions)
  - [Growth Predictions](#growth-predictions)
  - [Climate Optimization](#climate-optimization)
  - [Health Recommendations](#health-recommendations)
  - [Irrigation Predictions](#irrigation-predictions)
- [Models Management](#models-management)
- [Monitoring](#monitoring)
- [Analytics](#analytics)
- [Retraining](#retraining)
- [Readiness & Activation](#readiness--activation)
- [A/B Testing](#ab-testing)
- [Continuous Monitoring](#continuous-monitoring)
- [Personalized Learning](#personalized-learning)
- [Training Data](#training-data)
- [Analysis](#analysis)

---

## Base Endpoints

### GET /api/ml/health

**Description:** Check ML service health and availability

**Response:**
```json
{
  "status": "healthy",
  "services": {
    "disease_predictor": "ready",
    "climate_optimizer": "ready",
    "growth_predictor": "ready",
    "irrigation_predictor": "ready"
  },
  "models_loaded": 15,
  "last_training": "2026-02-14T10:00:00Z"
}
```

---

### GET /api/ml/training/history

**Description:** Get model training history

**Query Parameters:**
- `model_type` (optional) - Filter by model type
- `limit` (optional, default: 50) - Number of results
- `since` (optional) - ISO datetime filter

**Response:**
```json
{
  "history": [
    {
      "model_type": "climate_optimizer",
      "version": "1.2.0",
      "trained_at": "2026-02-14T03:00:00Z",
      "accuracy": 0.91,
      "training_samples": 1523,
      "duration": 45.2
    }
  ],
  "total": 142
}
```

---

### POST /api/ml/training/cancel

**Description:** Cancel an in-progress training job

**Request:**
```json
{
  "training_id": "train-12345"
}
```

---

## Predictions

### Disease Predictions

#### POST /api/ml/predictions/disease/risk

**Description:** Predict disease risk for a unit

**Request:**
```json
{
  "unit_id": 1,
  "environmental_data": {
    "temperature": 24.5,
    "humidity": 65,
    "light_hours": 16
  },
  "symptoms": ["yellowing_leaves", "spots"]
}
```

**Response:**
```json
{
  "predictions": [
    {
      "disease": "powdery_mildew",
      "probability": 0.72,
      "severity": "moderate",
      "matched_symptoms": ["white_powdery_coating"],
      "recommended_actions": [
        "Increase air circulation",
        "Apply neem oil spray"
      ]
    }
  ],
  "overall_risk": "medium"
}
```

---

#### GET /api/ml/predictions/disease/risks

**Description:** Get all disease risks across units

**Query Parameters:**
- `min_probability` (optional, default: 0.5) - Minimum risk threshold
- `unit_ids` (optional) - Comma-separated unit IDs

**Response:**
```json
{
  "risks": [
    {
      "unit_id": 1,
      "diseases": [...],
      "highest_risk": 0.72
    }
  ],
  "high_risk_count": 3,
  "medium_risk_count": 5
}
```

---

#### GET /api/ml/predictions/disease/alerts

**Description:** Get active disease alerts

**Response:**
```json
{
  "alerts": [
    {
      "id": 123,
      "unit_id": 1,
      "disease": "powdery_mildew",
      "probability": 0.72,
      "detected_at": "2026-02-14T10:30:00Z",
      "status": "active"
    }
  ]
}
```

---

### Growth Predictions

#### GET /api/ml/predictions/growth/{stage}

**Description:** Get predictions for a specific growth stage

**Path Parameters:**
- `stage` - Growth stage (seedling, vegetative, flowering, etc.)

**Response:**
```json
{
  "stage": "vegetative",
  "avg_duration_days": 21,
  "optimal_conditions": {
    "temperature": [20, 26],
    "humidity": [50, 70],
    "light_hours": 18
  },
  "transition_indicators": [...]
}
```

---

#### GET /api/ml/predictions/growth/stages/all

**Description:** Get all growth stage predictions

**Response:**
```json
{
  "stages": [
    {
      "name": "seedling",
      "typical_duration": 7,
      "conditions": {...}
    }
  ]
}
```

---

#### POST /api/ml/predictions/growth/transition-analysis

**Description:** Analyze growth stage transition timing

**Request:**
```json
{
  "plant_id": 123,
  "current_stage": "vegetative",
  "days_in_stage": 18,
  "environmental_history": [...]
}
```

**Response:**
```json
{
  "current_stage": "vegetative",
  "predicted_transition_days": 3,
  "confidence": 0.85,
  "next_stage": "flowering",
  "recommended_adjustments": [
    "Reduce light hours to 12/12",
    "Lower temperature to 20-24°C"
  ]
}
```

---

#### POST /api/ml/predictions/growth/compare

**Description:** Compare growth between plants

**Request:**
```json
{
  "plant_ids": [1, 2, 3],
  "metrics": ["growth_rate", "health_score"]
}
```

---

#### GET /api/ml/predictions/growth/status

**Description:** Get overall growth prediction status

---

### Climate Optimization

#### GET /api/ml/predictions/climate/{growth_stage}

**Description:** Get climate recommendations for a growth stage

**Response:**
```json
{
  "growth_stage": "vegetative",
  "optimal_ranges": {
    "temperature": [20, 26],
    "humidity": [50, 70],
    "co2": [800, 1200]
  },
  "day_night_differential": {
    "temperature": 4,
    "humidity": 10
  }
}
```

---

#### GET /api/ml/predictions/climate/{unit_id}/recommendations

**Description:** Get ML-powered climate recommendations for a unit

**Response:**
```json
{
  "unit_id": 1,
  "current_score": 68.5,
  "optimized_score": 82.3,
  "recommendations": [
    {
      "parameter": "temperature",
      "current": 28.5,
      "recommended": 24.0,
      "priority": "high",
      "impact": "+8.2 points"
    }
  ]
}
```

---

#### GET /api/ml/predictions/climate/{unit_id}/watering-issues

**Description:** Detect watering-related environmental issues

---

#### GET /api/ml/predictions/climate/forecast

**Description:** Get environmental forecast predictions

**Query Parameters:**
- `unit_id` (required)
- `hours` (optional, default: 24) - Forecast horizon

---

### Health Recommendations

#### GET /api/ml/predictions/health/{unit_id}/recommendations

**Description:** Get AI-powered health recommendations

**Response:**
```json
{
  "unit_id": 1,
  "recommendations": [
    {
      "category": "irrigation",
      "action": "Increase watering frequency",
      "priority": "high",
      "confidence": 0.87,
      "rationale": "Soil moisture declining faster than expected"
    }
  ]
}
```

---

#### POST /api/ml/predictions/health/observation

**Description:** Submit health observation for ML learning

**Request:**
```json
{
  "unit_id": 1,
  "observation_type": "symptom",
  "description": "yellowing_leaves",
  "severity": "moderate",
  "affected_area": "lower_leaves"
}
```

---

#### POST /api/ml/predictions/what-if

**Description:** Run what-if simulation for environmental changes

**Request:**
```json
{
  "unit_id": 1,
  "scenario": "increase_temperature",
  "changes": {
    "temperature": 26.0,
    "humidity": 60
  },
  "duration_hours": 48
}
```

**Response:**
```json
{
  "scenario": "increase_temperature",
  "predicted_impact": {
    "growth_rate": "+12%",
    "disease_risk": "+5%",
    "energy_cost": "+15%"
  },
  "recommendation": "proceed_with_caution",
  "confidence": 0.78
}
```

---

### Irrigation Predictions

#### GET /api/ml/predictions/irrigation/{unit_id}

**Description:** Get comprehensive irrigation prediction

**Response:**
```json
{
  "unit_id": 1,
  "should_irrigate": true,
  "confidence": 0.89,
  "threshold": {
    "learned_threshold": 32.5,
    "default_threshold": 30.0,
    "threshold_confidence": 0.85
  },
  "timing": {
    "recommended_time": "06:30",
    "avoid_periods": ["12:00-15:00"]
  },
  "duration": {
    "predicted_seconds": 180,
    "confidence": 0.82
  }
}
```

---

#### GET /api/ml/predictions/irrigation/{unit_id}/threshold

**Description:** Get learned irrigation threshold

**Response:**
```json
{
  "unit_id": 1,
  "learned_threshold": 32.5,
  "confidence": 0.85,
  "adjustment_history": [
    {"date": "2026-02-10", "threshold": 30.0},
    {"date": "2026-02-14", "threshold": 32.5}
  ]
}
```

---

#### GET /api/ml/predictions/irrigation/{unit_id}/timing

**Description:** Get optimal irrigation timing prediction

---

#### GET /api/ml/predictions/irrigation/{unit_id}/response

**Description:** Get plant response to irrigation prediction

---

#### GET /api/ml/predictions/irrigation/{unit_id}/duration

**Description:** Get optimal irrigation duration prediction

---

#### GET /api/ml/predictions/irrigation/{unit_id}/next

**Description:** Get next irrigation prediction

**Response:**
```json
{
  "unit_id": 1,
  "next_irrigation_time": "2026-02-15T06:30:00Z",
  "confidence": 0.87,
  "rationale": "Based on soil moisture decline rate and plant uptake patterns"
}
```

---

## Models Management

### GET /api/ml/models

**Description:** List all registered models

**Response:**
```json
{
  "models": [
    {
      "model_type": "climate_optimizer",
      "version": "1.2.0",
      "status": "active",
      "accuracy": 0.91,
      "last_trained": "2026-02-14T03:00:00Z"
    }
  ]
}
```

---

### GET /api/ml/models/{model_name}/versions

**Description:** Get version history for a model

**Response:**
```json
{
  "model_name": "climate_optimizer",
  "versions": [
    {
      "version": "1.2.0",
      "status": "active",
      "created_at": "2026-02-14T03:00:00Z",
      "metrics": {
        "accuracy": 0.91,
        "f1_score": 0.89
      }
    },
    {
      "version": "1.1.0",
      "status": "archived",
      "created_at": "2026-02-07T03:00:00Z",
      "metrics": {
        "accuracy": 0.87,
        "f1_score": 0.85
      }
    }
  ]
}
```

---

### GET /api/ml/models/{model_name}

**Description:** Get model details

---

### POST /api/ml/models/{model_name}/promote

**Description:** Promote a model version to active

**Request:**
```json
{
  "version": "1.2.0"
}
```

---

### GET /api/ml/models/{model_name}/metadata

**Description:** Get model metadata

**Response:**
```json
{
  "model_type": "climate_optimizer",
  "version": "1.2.0",
  "feature_names": ["temperature", "humidity", "co2", "light_intensity"],
  "feature_count": 12,
  "training_samples": 1523,
  "training_duration": 45.2,
  "algorithm": "RandomForestRegressor",
  "hyperparameters": {...}
}
```

---

### GET /api/ml/models/status

**Description:** Get status of all models

---

### GET /api/ml/models/{model_name}/drift

**Description:** Check model drift

**Response:**
```json
{
  "model_name": "climate_optimizer",
  "drift_detected": false,
  "drift_score": 0.12,
  "threshold": 0.15,
  "recommendation": "ok",
  "last_checked": "2026-02-14T10:00:00Z"
}
```

---

### GET /api/ml/models/{model_name}/drift/history

**Description:** Get drift detection history

---

### GET /api/ml/models/{model_name}/features

**Description:** Get feature importance

**Response:**
```json
{
  "model_name": "climate_optimizer",
  "features": [
    {
      "name": "temperature",
      "importance": 0.35,
      "rank": 1
    },
    {
      "name": "humidity",
      "importance": 0.28,
      "rank": 2
    }
  ]
}
```

---

### POST /api/ml/models/compare

**Description:** Compare model versions

**Request:**
```json
{
  "model_type": "climate_optimizer",
  "version_a": "1.1.0",
  "version_b": "1.2.0",
  "test_data_id": 123
}
```

---

### POST /api/ml/models/{model_name}/retrain

**Description:** Trigger manual model retraining

**Request:**
```json
{
  "force": true,
  "min_samples": 100
}
```

---

### POST /api/ml/models/{model_name}/activate

**Description:** Activate a model for use

---

## Monitoring

### GET /api/ml/monitoring/drift/{model_name}

**Description:** Check drift for a specific model

---

### GET /api/ml/monitoring/insights/{unit_id}

**Description:** Get continuous monitoring insights

**Query Parameters:**
- `limit` (optional, default: 10)
- `min_level` (optional) - Filter by alert level

**Response:**
```json
{
  "unit_id": 1,
  "insights": [
    {
      "type": "disease_risk",
      "severity": "high",
      "timestamp": "2026-02-14T10:30:00Z",
      "data": {
        "disease": "powdery_mildew",
        "probability": 0.72
      }
    }
  ]
}
```

---

### GET /api/ml/monitoring/insights/critical

**Description:** Get all critical insights

---

### GET /api/ml/monitoring/training/history

**Description:** Get training history with monitoring data

---

## Analytics

### GET /api/ml/analytics/disease/statistics

**Description:** Get disease prediction statistics

**Response:**
```json
{
  "total_predictions": 1523,
  "diseases_detected": 12,
  "most_common": "powdery_mildew",
  "accuracy": 0.87,
  "false_positive_rate": 0.08
}
```

---

### GET /api/ml/analytics/disease/trends

**Description:** Get disease trend analysis

**Query Parameters:**
- `days` (optional, default: 30)

---

### GET /api/ml/analytics/energy/actuator/{actuator_id}/dashboard

**Description:** Get energy analytics dashboard

---

### GET /api/ml/analytics/energy/actuator/{actuator_id}/predict-failure

**Description:** Predict actuator failure risk

**Response:**
```json
{
  "actuator_id": 1,
  "failure_probability": 0.15,
  "predicted_days_to_failure": 45,
  "confidence": 0.72,
  "indicators": [
    "Power consumption increasing",
    "Cycle count high"
  ]
}
```

---

## Retraining

### GET /api/ml/retraining/jobs

**Description:** Get all retraining jobs

**Response:**
```json
{
  "jobs": [
    {
      "job_id": "job-1",
      "model_type": "climate_optimizer",
      "schedule_type": "weekly",
      "schedule_config": {
        "day": 2,
        "time": "03:00"
      },
      "last_run": "2026-02-12T03:00:00Z",
      "next_run": "2026-02-19T03:00:00Z",
      "enabled": true
    }
  ]
}
```

---

### POST /api/ml/retraining/jobs

**Description:** Create a new retraining job

**Request:**
```json
{
  "model_type": "climate_optimizer",
  "schedule_type": "weekly",
  "schedule_day": 2,
  "schedule_time": "03:00",
  "min_samples": 100,
  "enabled": true
}
```

---

### DELETE /api/ml/retraining/jobs/{job_id}

**Description:** Delete a retraining job

---

### POST /api/ml/retraining/jobs/{job_id}/enable

**Description:** Enable a retraining job

---

### POST /api/ml/retraining/jobs/{job_id}/disable

**Description:** Disable a retraining job

---

### POST /api/ml/retraining/jobs/{job_id}/run

**Description:** Manually trigger a retraining job

---

### POST /api/ml/retraining/jobs/{job_id}/pause

**Description:** Pause an active retraining job

---

### POST /api/ml/retraining/jobs/{job_id}/resume

**Description:** Resume a paused retraining job

---

### POST /api/ml/retraining/trigger

**Description:** Trigger ad-hoc retraining

**Request:**
```json
{
  "model_type": "climate_optimizer",
  "trigger_reason": "manual",
  "force": true
}
```

---

### GET /api/ml/retraining/events

**Description:** Get retraining event history

---

### POST /api/ml/retraining/scheduler/start

**Description:** Start the retraining scheduler

---

### POST /api/ml/retraining/scheduler/stop

**Description:** Stop the retraining scheduler

---

### GET /api/ml/retraining/status

**Description:** Get retraining service status

---

## Readiness & Activation

### GET /api/ml/readiness/irrigation/{unit_id}

**Description:** Check irrigation ML readiness for a unit

**Response:**
```json
{
  "unit_id": 1,
  "overall_ready": true,
  "models": {
    "threshold": {
      "ready": true,
      "confidence": 0.85,
      "data_points": 45
    },
    "timing": {
      "ready": true,
      "confidence": 0.78,
      "data_points": 38
    },
    "duration": {
      "ready": false,
      "confidence": 0.45,
      "data_points": 12
    }
  }
}
```

---

### POST /api/ml/readiness/irrigation/{unit_id}/activate/{model_name}

**Description:** Activate an irrigation ML model

**Request:**
```json
{
  "override_checks": false
}
```

---

### POST /api/ml/readiness/irrigation/{unit_id}/deactivate/{model_name}

**Description:** Deactivate an irrigation ML model

---

### GET /api/ml/readiness/irrigation/{unit_id}/status

**Description:** Get activation status of irrigation models

---

### POST /api/ml/readiness/check-all

**Description:** Check readiness of all units

---

## A/B Testing

### GET /api/ml/ab-testing/tests

**Description:** Get all A/B tests

**Response:**
```json
{
  "tests": [
    {
      "test_id": "test-1",
      "name": "Climate Optimizer v1.2 vs v1.3",
      "model_type": "climate_optimizer",
      "version_a": "1.2.0",
      "version_b": "1.3.0",
      "status": "active",
      "started_at": "2026-02-01T00:00:00Z",
      "traffic_split": 0.5
    }
  ]
}
```

---

### POST /api/ml/ab-testing/tests

**Description:** Create a new A/B test

**Request:**
```json
{
  "name": "Climate Optimizer v1.2 vs v1.3",
  "model_type": "climate_optimizer",
  "version_a": "1.2.0",
  "version_b": "1.3.0",
  "traffic_split": 0.5,
  "duration_days": 14
}
```

---

### GET /api/ml/ab-testing/tests/{test_id}

**Description:** Get A/B test details

---

### GET /api/ml/ab-testing/tests/{test_id}/analysis

**Description:** Get statistical analysis of A/B test results

**Response:**
```json
{
  "test_id": "test-1",
  "version_a_performance": {
    "accuracy": 0.87,
    "sample_count": 523
  },
  "version_b_performance": {
    "accuracy": 0.91,
    "sample_count": 531
  },
  "statistical_significance": 0.95,
  "winner": "version_b",
  "improvement": "+4.6%"
}
```

---

### POST /api/ml/ab-testing/tests/{test_id}/select-version

**Description:** Select which model version to use for a prediction

---

### POST /api/ml/ab-testing/tests/{test_id}/record-result

**Description:** Record A/B test result

**Request:**
```json
{
  "version_used": "version_b",
  "outcome": "success",
  "metrics": {
    "accuracy": 0.92,
    "response_time": 0.15
  }
}
```

---

### POST /api/ml/ab-testing/tests/{test_id}/complete

**Description:** Complete an A/B test and promote winner

---

### POST /api/ml/ab-testing/tests/{test_id}/cancel

**Description:** Cancel an A/B test

---

## Continuous Monitoring

### GET /api/ml/continuous/status

**Description:** Get continuous monitoring status

**Response:**
```json
{
  "running": true,
  "monitored_units": [1, 2, 3],
  "check_interval_seconds": 300,
  "total_insights_generated": 1523
}
```

---

### POST /api/ml/continuous/start

**Description:** Start continuous monitoring

**Request:**
```json
{
  "unit_ids": [1, 2, 3]
}
```

---

### POST /api/ml/continuous/stop

**Description:** Stop continuous monitoring

---

### POST /api/ml/continuous/units/{unit_id}/add

**Description:** Add a unit to continuous monitoring

---

### POST /api/ml/continuous/units/{unit_id}/remove

**Description:** Remove a unit from continuous monitoring

---

### GET /api/ml/continuous/insights

**Description:** Get all continuous monitoring insights

**Query Parameters:**
- `limit` (optional)
- `severity` (optional)

---

### GET /api/ml/continuous/insights/{unit_id}

**Description:** Get insights for a specific unit

---

### GET /api/ml/continuous/insights/critical

**Description:** Get only critical insights

---

## Personalized Learning

### GET /api/ml/personalized/profiles/{unit_id}

**Description:** Get personalized profile for a unit

**Response:**
```json
{
  "unit_id": 1,
  "user_id": 1,
  "learning_enabled": true,
  "learned_preferences": {
    "irrigation_style": "conservative",
    "temperature_preference": 22.5,
    "success_rate": 0.89
  }
}
```

---

### POST /api/ml/personalized/profiles

**Description:** Create a new personalized profile

---

### PUT /api/ml/personalized/profiles/{unit_id}

**Description:** Update personalized profile

---

### GET /api/ml/personalized/condition-profiles

**Description:** Get all condition profiles

**Query Parameters:**
- `plant_type` (optional)
- `growth_stage` (optional)
- `visibility` (optional) - "public", "shared", "private"

---

### GET /api/ml/personalized/condition-profiles/user/{user_id}

**Description:** Get user's condition profiles

---

### GET /api/ml/personalized/condition-profiles/selector

**Description:** Get organized condition profiles for selector UI

**Response:**
```json
{
  "sections": [
    {
      "title": "Your Profiles",
      "type": "user",
      "profiles": [...]
    },
    {
      "title": "Community Profiles",
      "type": "community",
      "profiles": [...]
    }
  ]
}
```

---

### POST /api/ml/personalized/condition-profiles

**Description:** Create a new condition profile

**Request:**
```json
{
  "name": "Tomato Flowering Stage",
  "plant_type": "tomato",
  "growth_stage": "flowering",
  "mode": "precise",
  "visibility": "private",
  "conditions": {
    "temperature_day": 24.0,
    "temperature_night": 20.0,
    "humidity": 65,
    "co2": 1000
  }
}
```

---

### POST /api/ml/personalized/condition-profiles/clone

**Description:** Clone an existing condition profile

---

### POST /api/ml/personalized/condition-profiles/share

**Description:** Share a condition profile

**Request:**
```json
{
  "profile_id": "prof-123",
  "share_type": "public"
}
```

---

### GET /api/ml/personalized/condition-profiles/shared/{token}

**Description:** Get a shared condition profile by token

---

### GET /api/ml/personalized/condition-profiles/shared

**Description:** Get all shared profiles

---

### POST /api/ml/personalized/condition-profiles/import

**Description:** Import a condition profile

**Request:**
```json
{
  "token": "share-abc123"
}
```

---

### POST /api/ml/personalized/successes

**Description:** Record a growing success

**Request:**
```json
{
  "unit_id": 1,
  "plant_type": "tomato",
  "growth_stage": "flowering",
  "success_type": "harvest",
  "yield_amount": 2.5,
  "conditions_used": {...}
}
```

---

### GET /api/ml/personalized/recommendations/{unit_id}

**Description:** Get personalized recommendations

---

### GET /api/ml/personalized/similar-growers/{unit_id}

**Description:** Find similar growers for collaborative filtering

**Response:**
```json
{
  "unit_id": 1,
  "similar_growers": [
    {
      "user_id": 42,
      "similarity_score": 0.87,
      "common_plants": ["tomato", "basil"],
      "success_rate": 0.91
    }
  ]
}
```

---

## Training Data

### GET /api/ml/training-data/summary

**Description:** Get training data summary

**Response:**
```json
{
  "total_samples": 15234,
  "by_model": {
    "climate_optimizer": 5234,
    "disease": 3521,
    "irrigation": 6479
  },
  "data_quality": {
    "complete": 0.95,
    "missing_values": 0.02,
    "outliers": 0.03
  }
}
```

---

### POST /api/ml/training-data/collect/disease

**Description:** Collect disease training data

**Request:**
```json
{
  "unit_id": 1,
  "disease": "powdery_mildew",
  "severity": "moderate",
  "symptoms": ["white_powdery_coating"],
  "environmental_conditions": {...}
}
```

---

### POST /api/ml/training-data/collect/climate

**Description:** Collect climate training data

---

### POST /api/ml/training-data/collect/growth

**Description:** Collect growth training data

---

### POST /api/ml/training-data/validate

**Description:** Validate training data quality

**Request:**
```json
{
  "dataset_type": "climate",
  "sample_ids": [1, 2, 3]
}
```

---

### GET /api/ml/training-data/quality/{dataset_type}

**Description:** Get data quality metrics

---

### POST /api/ml/training-data/plant-health/train

**Description:** Train plant health model

---

### GET /api/ml/training-data/plant-health/status

**Description:** Get plant health training status

---

## Analysis

### POST /api/ml/analysis/root-cause

**Description:** Analyze root causes for alert clusters

**Request:**
```json
{
  "clusters": [
    {
      "id": "cluster-0",
      "type": "sensor_anomaly",
      "severity": "critical",
      "alert_ids": [1, 2, 3]
    }
  ]
}
```

**Response:**
```json
{
  "analyses": [
    {
      "cluster_id": "cluster-0",
      "root_cause": "Temperature spike caused by ventilation failure",
      "confidence": 0.85,
      "recommendations": [
        "Check ventilation fan status",
        "Verify fan power connections"
      ]
    }
  ]
}
```

---

### GET /api/ml/analysis/patterns

**Description:** Detect patterns in historical data

**Query Parameters:**
- `unit_id` (required)
- `days` (optional, default: 30)

---

### GET /api/ml/analysis/correlations

**Description:** Analyze correlations between parameters

**Query Parameters:**
- `unit_id` (required)
- `parameters` (required) - Comma-separated list

---

## Error Responses

All endpoints return error responses in the following format:

```json
{
  "error": "Error message",
  "details": {
    "field": "Additional context"
  },
  "status": 400
}
```

**Common Status Codes:**
- `400` - Bad Request (invalid parameters)
- `401` - Unauthorized
- `404` - Resource not found
- `500` - Internal server error
- `503` - Service unavailable (ML service not enabled)

---

## Rate Limiting

ML endpoints may be rate-limited to prevent resource exhaustion:

- **Predictions:** 100 requests/minute per user
- **Training:** 10 requests/hour per user
- **Analytics:** 60 requests/minute per user

Rate limit headers:
```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 87
X-RateLimit-Reset: 1644844800
```

---

## Authentication

Most ML endpoints require authentication via session cookie or API key:

```bash
# Session cookie (web interface)
curl -X GET http://localhost:5000/api/ml/predictions/disease/risks \
  -H "Cookie: session=abc123..."

# API key (programmatic access)
curl -X GET http://localhost:5000/api/ml/predictions/disease/risks \
  -H "X-API-Key: your-api-key"
```

---

## WebSocket Events

Real-time ML events are broadcast via WebSocket:

```javascript
socket.on('ml_prediction', (data) => {
  console.log('New prediction:', data);
});

socket.on('ml_insight', (data) => {
  console.log('New insight:', data);
});

socket.on('ml_training_complete', (data) => {
  console.log('Training completed:', data);
});
```

---

## Related Documentation

- **[AI/ML Overview](../ai_ml/README.md)** - Complete AI features guide
- **[LLM Setup](../ai_ml/LLM_SETUP.md)** - ChatGPT, Claude, local model integration
- **[Quick Reference](../ai_ml/QUICK_REFERENCE.md)** - Code snippets
- **[Architecture](../architecture/AI_ARCHITECTURE.md)** - System design

---

**Last Updated:** February 14, 2026  
**API Version:** 1.1.0
