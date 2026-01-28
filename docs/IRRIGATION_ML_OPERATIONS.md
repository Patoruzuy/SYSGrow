# Irrigation ML Operations Guide

**Date:** January 27, 2026

## Overview
The irrigation ML stack learns from user feedback, execution telemetry, and environmental context to optimize irrigation timing, thresholds, duration, and predicted responses.

**Core models:**
- **threshold_optimizer**: regression for optimal soil-moisture threshold
- **response_predictor**: classification for approve/delay/cancel likelihood
- **duration_optimizer**: regression for optimal irrigation duration (seconds)
- **timing_predictor**: classification (hour bucket) for preferred irrigation time
- **next_irrigation**: dry-down model (non-ML regression from telemetry)

## Training Data Sources
- **Threshold optimizer**: user feedback (too_little/just_right/too_much) from `PendingIrrigationRequest` and preference stats
- **Response predictor**: `PendingIrrigationRequest.user_response` (approve/delay/cancel)
- **Duration optimizer**: executed irrigations with before/after moisture deltas
- **Timing predictor**: delayed responses (`user_response='delay'`) with `delayed_until`
- **Next irrigation**: `PlantIrrigationModel` dry-down rate from moisture telemetry

## Feature Sources (Single Source of Truth)
All irrigation ML models share canonical feature lists in:
- `app/services/ai/feature_engineering.py` → `FeatureEngineer.get_irrigation_model_features()`

Feature alignment is enforced via:
- `FeatureEngineer.align_features(df, feature_list)`

## Timezone Handling (Timing Predictor)
Timing features are computed in the unit’s local timezone (IANA string from `GrowthUnits.timezone`):
- Training: `detected_at` and `delayed_until` are converted to unit-local time before extracting hour/day.\n+- Inference: the unit’s timezone is used to compute current hour/day for timing features.

## Metric Gating (Tolerances)
Models are only used when they meet minimum quality thresholds. If not, inference returns confidence **0.0** and a reasoning string indicating ML is not ready.

| Model | Metrics | Gate Condition |
|---|---|---|
| threshold_optimizer | MAE, R2 | **MAE ≤ 4.0** OR **R2/test_score ≥ 0.55** |
| response_predictor | macro_f1, balanced_accuracy | **macro_f1 ≥ 0.55** AND **balanced_accuracy ≥ 0.55** |
| duration_optimizer | MAE, MAPE | **MAE ≤ 25** AND **MAPE ≤ 0.40** |
| timing_predictor | top3_accuracy, MRR | **top3 ≥ 0.60** AND **MRR ≥ 0.55** |

**Important behavior:**
- **No heuristic fallbacks for irrigation ML predictions.** If ML doesn’t pass gating:\n+  - Timing returns `preferred_time="00:00"` with `confidence=0.0` and a reason.\n+  - Threshold returns the current threshold with `confidence=0.0` and a reason.\n+  - Duration returns the current default duration with `confidence=0.0`.\n+  - Response returns zeroed probabilities with `confidence=0.0`.

## Endpoints (Auth Required)
All irrigation ML endpoints require a valid session `user_id` (401 if missing):

- `GET /api/ml/predictions/irrigation/<unit_id>`
- `GET /api/ml/predictions/irrigation/<unit_id>/threshold`
- `GET /api/ml/predictions/irrigation/<unit_id>/response`
- `GET /api/ml/predictions/irrigation/<unit_id>/duration`
- `GET /api/ml/predictions/irrigation/<unit_id>/timing`
- `GET /api/ml/predictions/irrigation/<unit_id>/next`

### Response Metadata
Irrigation prediction endpoints include a `model_status` section:
- `ml_ready`: whether the model passes gating thresholds
- `model_version`: production model version (if available)
- `gating_metrics`: metrics used for gating (e.g., `macro_f1`, `mape`, `top3_accuracy`)

Readiness endpoints:
- `GET /api/ml/readiness/irrigation/<unit_id>`
- `POST /api/ml/readiness/irrigation/<unit_id>/activate/<model>`
- `POST /api/ml/readiness/irrigation/<unit_id>/deactivate/<model>`
- `GET /api/ml/readiness/irrigation/<unit_id>/status`

## Retraining Schedule
Automated retraining jobs are registered in `AutomatedRetrainingService`:

- **irrigation_threshold**: Weekly, Monday 03:00
- **irrigation_response**: Weekly, Monday 03:30
- **irrigation_duration**: Monthly, 1st at 04:00
- **irrigation_timing**: Weekly, Monday 04:30

## Recommendations Integration
`IrrigationPredictor` passes its full prediction object into the recommendation provider:
- `RecommendationContext.irrigation_prediction`

`RuleBasedRecommendationProvider` uses ML outputs to generate watering recommendations such as:
- Threshold adjustment suggestions
- Timing avoidance windows
- Duration increase/decrease guidance

## Key Files
- `app/services/ai/irrigation_predictor.py` — inference + gating
- `app/services/ai/ml_trainer.py` — training + metrics
- `app/services/ai/feature_engineering.py` — canonical feature lists
- `app/services/ai/automated_retraining.py` — schedules
- `app/blueprints/api/ml_ai/predictions.py` — irrigation endpoints
- `app/services/ai/recommendation_provider.py` — ML recommendation wiring

## Operational Notes
- Readiness is based on data volume; model **performance** gating is enforced at inference time.
- If metrics are missing, ML is treated as **not ready**.
