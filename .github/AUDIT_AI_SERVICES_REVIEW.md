# AI Services Layer — Full Audit Report

> **Auditor:** Senior Chief Engineer (AI/ML Systems)
> **Scope:** `app/services/ai/` (20 files) + integration points
> **Date:** Session 6
> **Baseline:** 271 tests passing, 1 pre-existing failure, 19 pre-existing errors

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [File Inventory & ML Readiness Matrix](#2-file-inventory--ml-readiness-matrix)
3. [Architecture Map](#3-architecture-map)
4. [Critical Findings](#4-critical-findings)
5. [Per-File Findings](#5-per-file-findings)
6. [Integration Gap Analysis](#6-integration-gap-analysis)
7. [Prioritised Action Plan](#7-prioritised-action-plan)
8. [Condition Profiles — Design Notes](#8-condition-profiles--design-notes)
9. [soil_moisture_threshold Removal Scope](#9-soil_moisture_threshold-removal-scope)
10. [Notification-Driven Decision Pattern](#10-notification-driven-decision-pattern)

---

## 1. Executive Summary

The AI services package contains **20 Python files** (~12,500 LOC) providing ML model management, disease prediction, climate optimisation, irrigation prediction, health scoring, personalised learning, and supporting infrastructure (A/B testing, drift detection, retraining, feature engineering, training data collection).

### Overall Assessment

| Aspect | Rating | Notes |
|--------|--------|-------|
| **ML-first design** | ⚠️ Partial | irrigation_predictor & disease_predictor follow ML-first pattern well; climate_optimizer & recommendation_provider are primarily algorithmic |
| **Day/night awareness** | ❌ Missing | No service differentiates between light-on/light-off thresholds |
| **Season/sun awareness** | ❌ Missing | `SunTimesService` exists in `utilities/` but zero AI services consume it |
| **Unit dimensions (m²)** | ❌ Missing | `UnitDimensions` domain object exists but no AI service reads it |
| **Condition profiles integration** | ⚠️ Partial | `personalized_learning.py` has full CRUD, but `climate_optimizer` and `recommendation_provider` ignore profiles |
| **soil_moisture at unit level** | ⚠️ Still present | `threshold_service._sanitize_unit_thresholds()` still includes `soil_moisture_threshold`; `UnitSettings` does NOT have it (good) |
| **Notification-driven decisions** | ⚠️ Partial | `ml_readiness_monitor` uses notifications; `threshold_service` proposes via EventBus; climate_optimizer & recommendation_provider do not notify |
| **Inter-service coordination** | ❌ Weak | Services mostly operate in isolation; `continuous_monitor` is the only orchestrator but calls services simplistically |
| **Test coverage** | ⚠️ Unknown for AI | Tests exist in `tests/` but coverage of AI-specific logic not measured |

### Key Metrics

- **Files following ML-first pattern:** 6/20 (30%)
- **Files purely algorithmic:** 4/20 (20%) — need ML path added
- **Files infrastructure/support:** 7/20 (35%) — model_registry, trainer, retraining, drift, A/B, feature_eng, training_data
- **Files with hardcoded thresholds that should use ThresholdService/profiles:** 3 (climate_optimizer, recommendation_provider, environmental_health_scorer)

---

## 2. File Inventory & ML Readiness Matrix

| # | File | LOC | ML Model? | Algo Fallback? | Uses ThresholdService? | Uses Profiles? | Day/Night? | Sun/Season? | Notifications? |
|---|------|-----|-----------|----------------|----------------------|----------------|------------|-------------|----------------|
| 1 | `climate_optimizer.py` | 564 | scaffold only | **PRIMARY** ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| 2 | `recommendation_provider.py` | 699 | LLM placeholder | **PRIMARY** ❌ | ❌ hardcoded | ❌ | ❌ | ❌ | ❌ |
| 3 | `personalized_learning.py` | 1296 | N/A (data mgmt) | N/A | ❌ | **IS** profiles | ❌ | ❌ | callback only |
| 4 | `bayesian_threshold.py` | 832 | Bayesian ✅ | prior from constants | ✅ (for prior) | ❌ | ❌ | ❌ | ❌ |
| 5 | `disease_predictor.py` | 898 | ✅ classifier | ✅ rule-based | ❌ | ❌ (reads history) | ❌ | ❌ | ❌ |
| 6 | `continuous_monitor.py` | 674 | N/A (orchestrator) | N/A | ❌ | ❌ | ❌ | ❌ | has callbacks |
| 7 | `environmental_health_scorer.py` | 515 | ❌ | **PRIMARY** | ✅ partial | ❌ | ❌ | ❌ | ❌ |
| 8 | `plant_health_scorer.py` | 1102 | ✅ ensemble | ✅ weighted | ✅ | ❌ | ❌ | ❌ | ❌ |
| 9 | `plant_health_monitor.py` | 526 | ❌ | **PRIMARY** | ✅ | ❌ | ❌ | ❌ | ❌ |
| 10 | `plant_growth_predictor.py` | 537 | ✅ (registry) | ✅ defaults | ❌ | ❌ | ❌ | ❌ | ❌ |
| 11 | `irrigation_predictor.py` | 1581 | ✅ 4 models | ✅ Bayesian | ❌ indirect | ❌ | ❌ | ❌ | ❌ |
| 12 | `model_registry.py` | 743 | N/A (infra) | N/A | N/A | N/A | N/A | N/A | N/A |
| 13 | `ml_trainer.py` | 2491 | N/A (infra) | N/A | N/A | N/A | N/A | N/A | N/A |
| 14 | `feature_engineering.py` | 1885 | N/A (infra) | N/A | N/A | N/A | N/A | N/A | N/A |
| 15 | `training_data_collector.py` | 591 | N/A (infra) | N/A | N/A | N/A | N/A | N/A | N/A |
| 16 | `ab_testing.py` | 499 | N/A (infra) | N/A | N/A | N/A | N/A | N/A | N/A |
| 17 | `automated_retraining.py` | 692 | N/A (infra) | N/A | N/A | N/A | N/A | N/A | N/A |
| 18 | `drift_detector.py` | 347 | N/A (infra) | N/A | N/A | N/A | N/A | N/A | N/A |
| 19 | `ml_readiness_monitor.py` | 476 | N/A (infra) | N/A | N/A | N/A | N/A | N/A | ✅ |
| 20 | `__init__.py` | 159 | N/A (exports) | N/A | N/A | N/A | N/A | N/A | N/A |

---

## 3. Architecture Map

### 3.1 Current Data Flow

```
                    ┌──────────────────────────────────┐
                    │      UnitRuntime (domain)         │
                    │   apply_ai_conditions()           │
                    │   → ThresholdService              │
                    │     .get_optimal_conditions()     │
                    │     (70% AI / 30% plant JSON)     │
                    │   → EventBus: THRESHOLDS_PROPOSED │
                    └────────────┬─────────────────────┘
                                 │
        ┌────────────────────────▼─────────────────────────┐
        │                ThresholdService                    │
        │  get_thresholds() → plants_info.json + profiles   │
        │  get_optimal_conditions() → + ClimateOptimizer    │
        │  get_threshold_ranges() → min/max/optimal         │
        └──────────┬──────────────────────┬────────────────┘
                   │                      │
    ┌──────────────▼───────┐   ┌──────────▼──────────────┐
    │  ClimateOptimizer    │   │ PersonalizedLearning     │
    │  predict_conditions()│   │ condition profiles       │
    │  (ML scaffold →      │   │ environment profiles     │
    │   DEFAULT_CONDITIONS) │   │ success/failure tracking │
    └──────────────────────┘   └──────────────────────────┘

    ┌──────────────────────────────────────────────────────┐
    │              ContinuousMonitoringService              │
    │  _monitor_unit() → every 5 min per unit:             │
    │    1. DiseasePredictor.predict_disease_risk()         │
    │    2. ClimateOptimizer.get_recommendations()          │
    │    3. PlantGrowthPredictor.analyze_stage_transition() │
    │    4. Trend analysis (internal)                       │
    │  → GrowingInsight → callbacks                        │
    └──────────────────────────────────────────────────────┘

    DISCONNECTED (should be connected):
    ┌─────────────────────┐  ┌────────────────────────┐
    │ RecommendationProv. │  │ BayesianThreshold      │
    │ (hardcoded rules)   │  │ (soil moisture only)   │
    │ NOT called by       │  │ NOT called by          │
    │ continuous_monitor   │  │ climate or recommend.  │
    └─────────────────────┘  └────────────────────────┘

    ┌──────────────────────┐  ┌────────────────────────┐
    │ EnvHealthScorer      │  │ PlantHealthScorer      │
    │ (own thresholds)     │  │ (ML + rule-based)      │
    │ NOT called by        │  │ standalone scoring     │
    │ continuous_monitor   │  │ NOT integrated with    │
    └──────────────────────┘  │ recommendation_prov.   │
                              └────────────────────────┘
```

### 3.2 Desired Data Flow (Target Architecture)

```
    ┌───────────────────────────────────────────────────────────────────┐
    │                ContinuousMonitoringService (ORCHESTRATOR)          │
    │  For each unit, every 5 min:                                      │
    │                                                                   │
    │  1. Get context: SunTimesService.is_daytime() + UnitDimensions    │
    │  2. Get profile: PersonalizedLearning.get_condition_profile()     │
    │  3. Get thresholds: ThresholdService.get_threshold_ranges()       │
    │     (already profile-aware, needs day/night split)                │
    │  4. Run scorers:                                                  │
    │     - PlantHealthScorer.score_plant_health()                      │
    │     - EnvironmentalLeafHealthScorer.score_current_health()        │
    │  5. Run predictors (ML-first):                                    │
    │     - ClimateOptimizer.predict_optimal() → ML model or fallback  │
    │     - DiseasePredictor.predict_disease_risk()                     │
    │     - IrrigationPredictor.predict() (via BayesianThreshold)      │
    │  6. Generate recommendations:                                     │
    │     - RecommendationProvider.get_recommendations(context)         │
    │       (consumes all predictions, profile, day/night, dimensions)  │
    │  7. Compare vs current → produce changes list                     │
    │  8. Send via NotificationsService:                                │
    │     - Climate changes → user notification                         │
    │     - Recommendations → user notification                         │
    │     - Urgent actions → immediate alert                            │
    │  9. Log for ML training → TrainingDataCollector                   │
    └───────────────────────────────────────────────────────────────────┘
```

---

## 4. Critical Findings

### Finding C1: climate_optimizer.py is Algorithmic, Not ML-Driven

**Severity:** 🔴 Critical
**Location:** `climate_optimizer.py` lines 31-60 (`DEFAULT_CONDITIONS`), lines 117-190 (`predict_conditions`)

The `predict_conditions()` method has ML scaffolding but in practice always falls back to `DEFAULT_CONDITIONS` — a hardcoded dict of 6 growth stages with single-value temperature/humidity/soil_moisture. The ML model loading is present but there's no training pipeline that produces a `climate_optimizer` model type.

**Impact:** The core climate control system operates on static lookup tables, not learning from the user's actual environment, feedback, or outcomes.

**Recommendation:** See [Action Item A1](#a1-rewrite-climateoptimizer-as-ml-first).

---

### Finding C2: No Day/Night Threshold Differentiation

**Severity:** 🔴 Critical
**Affects:** `climate_optimizer.py`, `recommendation_provider.py`, `environmental_health_scorer.py`, `threshold_service.py`

All thresholds are single values applied 24/7. The user explicitly stated: *"temperature should be lower at night"*. Plants require different environmental conditions during light-on (photosynthesis) vs light-off (respiration) periods.

**What exists but is unused:**
- `SunTimesService` in `app/services/utilities/` provides `is_daytime()`, sunrise/sunset times, day length
- `UnitSettings` has a `timezone` field
- Device schedules have light on/off times (`get_light_hours()` in `app/utils/schedules.py`)

**Impact:** Temperature and humidity targets are suboptimal during night cycles. Experienced growers know to drop temperature by 2-5°C and adjust humidity at night.

**Recommendation:** See [Action Item A2](#a2-day-night-threshold-split).

---

### Finding C3: climate_optimizer Not Connected to Recommendation or Notification Pipelines

**Severity:** 🔴 Critical
**Location:** `climate_optimizer.py` — no notification sends; `recommendation_provider.py` — no climate_optimizer import

The climate optimizer operates in isolation. It doesn't:
- Feed into `RecommendationProvider` (which has its own hardcoded environmental checks)
- Send notifications when conditions change
- Consult user via notification before applying changes

The user wants: *"notify the user for new climate changes instead be called to predict the climate"* and *"plug it in recommendation_provider.py and personalized_learning.py"*.

**Recommendation:** See [Action Items A1, A5](#a5-wire-climate-optimizer-into-recommendation-pipeline).

---

### Finding C4: Unit Dimensions Not Used by Any AI Service

**Severity:** 🟡 Major
**Location:** `UnitDimensions` dataclass exists in `unit_runtime.py` (lines 45-68) with width/height/depth/volume_liters, but zero AI services access it.

The user stated: *"climate_optimizer.py should take the unit measures 'dimensions' (maybe by calculating the m²)"*.

Unit dimensions affect:
- Air volume → how quickly temperature/humidity change
- Light coverage (lux per m²)
- CO2 requirements (ppm scales with volume)
- Humidity management (surface area vs volume ratio)

**Recommendation:** See [Action Item A3](#a3-unit-dimensions-awareness).

---

### Finding C5: Condition Profiles Not Consumed by Climate or Recommendations

**Severity:** 🟡 Major
**Location:** `personalized_learning.py` has a complete `PlantStageConditionProfile` system (CRUD, sharing, import, rating) but:
- `climate_optimizer.py` only calls `get_personalized_recommendations()` which returns generic adjustments, not the profile's actual thresholds
- `recommendation_provider.py` has zero profile awareness — uses hardcoded thresholds (`temp >32/<15`, `humidity >80/<30`, `soil_moisture <25/>85`)
- `ThresholdService.get_thresholds()` DOES merge profile data ✅ but climate_optimizer bypasses ThresholdService for its predictions

The user wants: *"the user can create tested environmental conditions with high rating for the plants, so they don't need to adjust anything"*

**Recommendation:** Ensure all threshold lookups go through `ThresholdService` (which already integrates profiles) rather than using local hardcoded values. See [Action Item A4](#a4-profile-integration).

---

### Finding C6: soil_moisture_threshold Still in Unit-Level Code

**Severity:** 🟡 Major
**Scope:** The user stated soil_moisture_threshold should be removed from unit level (it's now plant-level, managed by `BayesianThresholdAdjuster`).

Current state:
- ✅ `UnitSettings` does NOT have `soil_moisture_threshold`
- ❌ `ThresholdService._sanitize_unit_thresholds()` (line ~350) still includes `"soil_moisture_threshold"` in its output
- ❌ `EnvironmentalThresholds` domain object has a `soil_moisture` field (used by `get_thresholds()` which IS plant-level, so this is OK)
- ❌ `GrowthOperations.create_unit()` — needs verification
- ❌ Database `GrowthUnits` schema — needs verification for column presence

**Recommendation:** See [Action Item A6](#a6-remove-soil_moisture_threshold-from-unit-level).

---

### Finding C7: RecommendationProvider Uses Hardcoded Thresholds

**Severity:** 🟡 Major
**Location:** `recommendation_provider.py` lines 400-500 (`_check_environmental_conditions`)

```python
if temperature > 32:  # Hardcoded
    ...
if humidity > 80:  # Hardcoded
    ...
if soil_moisture < 25:  # Hardcoded
```

These should use `ThresholdService.get_threshold_ranges()` which returns min/max/optimal values per plant type and growth stage, and is already profile-aware.

**Recommendation:** Inject `ThresholdService` into `RuleBasedRecommendationProvider` and replace all hardcoded thresholds. See [Action Item A4](#a4-profile-integration).

---

## 5. Per-File Findings

### 5.1 `climate_optimizer.py` (564 LOC) — ❌ Needs Major Rewrite

**Current purpose:** Predict optimal climate conditions per growth stage
**Current reality:** Hardcoded `DEFAULT_CONDITIONS` dict with ML scaffolding that never activates

| Issue | Severity | Detail |
|-------|----------|--------|
| `DEFAULT_CONDITIONS` is primary path | 🔴 | ML model never trained, always falls back |
| No day/night split | 🔴 | Single temp/humidity per stage |
| No `SunTimesService` integration | 🔴 | Cannot determine photoperiod |
| No `UnitDimensions` | 🟡 | Cannot factor in unit volume |
| `detect_watering_issues()` reads unit-level AI log | 🟡 | Should be plant-level via BayesianThreshold |
| `get_personalized_conditions()` bypasses ThresholdService | 🟡 | Calls personalized_learning directly instead of ThresholdService which already blends profiles |
| `get_recommendations()` returns dict, not notification | 🟡 | User wants notification-driven decisions |
| `MOISTURE_THRESHOLD=5.0` hardcoded | 🟡 | Should use ThresholdService tolerance |

### 5.2 `recommendation_provider.py` (699 LOC) — ⚠️ Needs Integration

**Current purpose:** ABC for recommendation providers with rule-based and LLM implementations
**Strength:** Good ABC design, `SYMPTOM_DATABASE` (12 symptoms), `TREATMENT_MAP`, irrigation recommendation conversion

| Issue | Severity | Detail |
|-------|----------|--------|
| Hardcoded environmental thresholds in `_check_environmental_conditions()` | 🟡 | Should use ThresholdService |
| No ClimateOptimizer integration | 🟡 | Climate recommendations are separate |
| No profile awareness | 🟡 | Doesn't know about user's condition profiles |
| `LLMRecommendationProvider` is a stub | ℹ️ | Falls back to rule-based, which is fine for now |
| No day/night context | 🟡 | Same recommendations regardless of photoperiod |

### 5.3 `personalized_learning.py` (1296 LOC) — ✅ Well Designed, Needs Consumers

**Current purpose:** User-specific learning profiles, condition profile management
**Strength:** Full CRUD for condition profiles (create/read/update/clone/share/import/rate), file-based persistence, callback system for profile updates

| Issue | Severity | Detail |
|-------|----------|--------|
| `_get_base_recommendation()` has its own hardcoded defaults | 🟡 | Should delegate to ThresholdService |
| `get_personalized_recommendations()` returns hardcoded base values | 🟡 | Should use ThresholdService.get_thresholds() |
| `_detect_location_characteristics()` is placeholder | ℹ️ | Returns hardcoded dict |
| `_profile_equipment()` is placeholder | ℹ️ | Returns hardcoded dict |
| `_calculate_environment_similarity()` is simplistic | ℹ️ | Only 3 factors, could be richer |
| `soil_moisture_threshold` in `PlantStageConditionProfile` | ✅ | This is correct — profiles are plant-level |

### 5.4 `bayesian_threshold.py` (832 LOC) — ✅ Well Implemented

**Current purpose:** Bayesian learning for optimal soil moisture thresholds
**Strength:** Proper conjugate Normal-Normal update, user consistency weighting, explore-exploit tradeoff, persistence to DB

| Issue | Severity | Detail |
|-------|----------|--------|
| Only handles soil moisture | ℹ️ | Could be generalised to other thresholds but user says soil moisture is plant-level ✅ |
| No notification on threshold change | 🟡 | When Bayesian update shifts threshold significantly, user should be notified |
| `_belief_key` doesn't include user_id | ℹ️ | Cache key uses `(unit_id, user_id, belief_key)` tuple, which is correct |

### 5.5 `disease_predictor.py` (898 LOC) — ✅ Good ML-First Pattern

**Current purpose:** Predict disease risk from environmental patterns
**Strength:** Loads ML classifier from registry, falls back to rule-based assessment, history multipliers for user-specific risk

| Issue | Severity | Detail |
|-------|----------|--------|
| Rule-based thresholds are hardcoded | 🟡 | Fungal: humidity>80, temp 15-25; bacterial: humidity>75; pest: temp>28 |
| No profile awareness | 🟡 | Doesn't use user's known challenge areas from PersonalizedLearning |
| No day/night context | ℹ️ | Disease risk doesn't vary much by photoperiod |
| No notification on high risk detection | 🟡 | ContinuousMonitor generates insights but doesn't send notifications |

### 5.6 `continuous_monitor.py` (674 LOC) — ⚠️ Key Orchestrator, Needs Enhancement

**Current purpose:** Background monitoring thread, calls AI services and generates insights
**Strength:** Threading model, unit-based monitoring, insight storage with alerting callbacks

| Issue | Severity | Detail |
|-------|----------|--------|
| `_on_critical_alert` / `_on_new_insight` callbacks are manually set | 🟡 | Should integrate with NotificationsService directly |
| Has `_notifications_service` field but never uses it | 🔴 | Dead code — declared but never called |
| Doesn't call RecommendationProvider | 🟡 | Has its own simple recommendation generation |
| Doesn't call EnvironmentalLeafHealthScorer | 🟡 | Missing environmental scoring |
| Doesn't call PlantHealthScorer | 🟡 | Missing per-plant health scoring |
| No day/night context passed to services | 🟡 | All calls lack photoperiod info |
| Climate analysis calls `climate_optimizer.get_recommendations()` which is algorithmic | 🟡 | Cascade of the C1 issue |

### 5.7 `environmental_health_scorer.py` (515 LOC) — ⚠️ Algorithmic, Needs ML Path

**Current purpose:** Score leaf health from environmental sensor data
**Strength:** Good VPD calculations, stress accumulation tracking, integration with ThresholdService (partial)

| Issue | Severity | Detail |
|-------|----------|--------|
| No ML model integration | 🟡 | Purely rule-based scoring |
| Hardcoded stress thresholds (temp <15/>32, humidity >85/<30, moisture <30/>90) | 🟡 | Should use ThresholdService ranges |
| VPD ranges hardcoded per stage | ℹ️ | Acceptable as VPD is physics-based |
| No connection to PlantHealthScorer | 🟡 | PlantHealthScorer could consume this |

### 5.8 `plant_health_scorer.py` (1102 LOC) — ✅ Good ML-First Pattern

**Current purpose:** Per-plant health scoring with ensemble ML + rule-based fallback
**Strength:** Regressor + classifier ensemble, feature_extractor integration, `ThresholdService` for thresholds, comprehensive `PlantHealthScore` dataclass

| Issue | Severity | Detail |
|-------|----------|--------|
| `DEFAULT_THRESHOLDS` fallback should use ThresholdService more consistently | ℹ️ | Already uses ThresholdService when available |
| `RECOMMENDATION_THRESHOLDS` (18 entries from prior session fix) | ✅ | Config-driven thresholds |
| Doesn't use condition profiles for scoring | 🟡 | Could use profile thresholds for more accurate scoring |

### 5.9 `plant_health_monitor.py` (526 LOC) — ⚠️ Algorithmic

**Current purpose:** Record health observations and correlate with environment
**Strength:** Clean `PlantHealthObservation` flow, `EnvironmentalCorrelation` analysis, delegates to PlantJournalService for storage

| Issue | Severity | Detail |
|-------|----------|--------|
| Correlation analysis is purely rule-based | 🟡 | Could use ML for pattern recognition |
| Duplicate `SYMPTOM_DATABASE` and `TREATMENT_MAP` (also in recommendation_provider) | 🟡 | DRY violation |
| No notification on health observation | 🟡 | Recording happens silently |

### 5.10 `plant_growth_predictor.py` (537 LOC) — ✅ Good Pattern

**Current purpose:** Predict optimal growth conditions per stage, analyse stage transitions
**Strength:** ML from ModelRegistry with science-backed defaults, validation ranges, stage transition analysis

| Issue | Severity | Detail |
|-------|----------|--------|
| `DEFAULT_CONDITIONS` duplicates climate_optimizer's defaults | 🟡 | Should be unified with ThresholdService |
| No day/night conditions | 🟡 | Same as other services |
| `STAGE_MIN_DAYS` hardcoded | ℹ️ | Acceptable as biological minimum |

### 5.11 `irrigation_predictor.py` (1581 LOC) — ✅ Best ML Implementation

**Current purpose:** ML-based irrigation with 4 sub-models (threshold, response, duration, timing)
**Strength:** Quality gates, model bundle loading, feature alignment, comprehensive prediction pipeline, Bayesian fallback

| Issue | Severity | Detail |
|-------|----------|--------|
| No day/night timing context | 🟡 | Timing predictor could factor in photoperiod |
| No notification integration | 🟡 | Predictions don't trigger notifications directly |
| Feature engineering is well-versioned (V1/V2) | ✅ | Good practice |

### 5.12 `model_registry.py` (743 LOC) — ✅ Solid Infrastructure

**Current purpose:** ML model versioning, save/load/deploy lifecycle
**Assessment:** Clean design, supports legacy and new formats, model caching, production symlinks

### 5.13 `ml_trainer.py` (2491 LOC) — ✅ Infrastructure

**Current purpose:** Training orchestration with cross-validation
**Assessment:** Proper sklearn integration, feature engineering, data cleaning, model evaluation
**Note:** No climate_optimizer training pipeline exists — only disease and irrigation models are trained.

### 5.14 `feature_engineering.py` (1885 LOC) — ✅ Well Designed

**Current purpose:** Shared feature extraction for ML models
**Strength:** Versioned feature sets, DIF (day-night temp difference) features defined but unused

| Issue | Severity | Detail |
|-------|----------|--------|
| `CLIMATE_FEATURES_V1` includes `season_spring/summer/fall/winter` | ✅ | Features defined but no service passes season info |
| DIF feature (day-night temp diff) defined | ✅ | Good, but no consumer uses it |

### 5.15 `training_data_collector.py` (591 LOC) — ✅ Infrastructure

**Purpose:** Automated data collection pipeline for ML training
**Assessment:** Collects disease and growth training examples with quality scoring

### 5.16 `ab_testing.py` (499 LOC) — ✅ Infrastructure

**Purpose:** A/B testing framework for model comparison
**Assessment:** Clean design with database persistence

### 5.17 `automated_retraining.py` (692 LOC) — ✅ Infrastructure

**Purpose:** Scheduled and drift-triggered model retraining
**Assessment:** Job-based retraining with irrigation model defaults, integrated with UnifiedScheduler

### 5.18 `drift_detector.py` (347 LOC) — ✅ Infrastructure

**Purpose:** Model performance degradation detection
**Assessment:** Proper sliding window metrics, retrain/monitor/ok recommendations

### 5.19 `ml_readiness_monitor.py` (476 LOC) — ✅ Good Notification Pattern

**Purpose:** Track ML data collection and notify users when models are ready
**Assessment:** **Best example of the notification-driven pattern the user wants.** Uses `NotificationsService` to inform users about model readiness and get consent for activation.

### 5.20 `__init__.py` (159 LOC) — ✅ Clean Exports

**Assessment:** Properly exports all public classes

---

## 6. Integration Gap Analysis

### 6.1 Services That Should Be Connected But Aren't

| From | To | Gap |
|------|----|-----|
| `ClimateOptimizer` | `RecommendationProvider` | Climate predictions not fed into recommendation pipeline |
| `ClimateOptimizer` | `NotificationsService` | Climate changes not notified to user |
| `ClimateOptimizer` | `PersonalizedLearning` (profiles) | Doesn't use condition profiles for predictions |
| `ClimateOptimizer` | `SunTimesService` | No photoperiod/season awareness |
| `ClimateOptimizer` | `UnitDimensions` | No unit volume/area in predictions |
| `RecommendationProvider` | `ThresholdService` | Uses hardcoded thresholds instead |
| `RecommendationProvider` | `ClimateOptimizer` | Could consume climate predictions |
| `ContinuousMonitor` | `NotificationsService` | Has field but doesn't call it |
| `ContinuousMonitor` | `PlantHealthScorer` | Missing per-plant scoring |
| `ContinuousMonitor` | `EnvironmentalLeafHealthScorer` | Missing environmental scoring |
| `ContinuousMonitor` | `RecommendationProvider` | Has own simple recommendations instead |
| `BayesianThreshold` | `NotificationsService` | Significant threshold changes not notified |
| `DiseasePredictor` | `PersonalizedLearning` (challenge_areas) | Doesn't use user's known challenges |
| `PlantGrowthPredictor` | `ThresholdService` | Has own `DEFAULT_CONDITIONS` instead |

### 6.2 Duplicate Threshold Definitions

The same default conditions appear in multiple places:

| Location | temp | humidity | soil_moisture |
|----------|------|----------|---------------|
| `climate_optimizer.DEFAULT_CONDITIONS["Vegetative"]` | 24 | 60 | 70 |
| `plant_growth_predictor.DEFAULT_CONDITIONS["Vegetative"]` | 25 | 65 | 75 |
| `personalized_learning._get_base_recommendation("Vegetative")` | 24 | 65 | 75 |
| `recommendation_provider._check_environmental_conditions()` | hardcoded (>32/<15) | hardcoded (>80/<30) | hardcoded (<25/>85) |
| `environmental_health_scorer._calculate_stress_score()` | <15 or >32 | >85 or <30 | <30 or >90 |
| `ThresholdService.generic_thresholds` | 24 | 55 | 50 |
| `plants_info.json` (Tomatoes/Vegetative) | stage-specific ranges | stage-specific ranges | stage-specific targets |

**These should all resolve through `ThresholdService.get_thresholds()` as single source of truth.**

### 6.3 Duplicate Symptom/Treatment Databases

| Location | Entries |
|----------|---------|
| `recommendation_provider.SYMPTOM_DATABASE` | 12 symptoms |
| `plant_health_monitor.SYMPTOM_DATABASE` | 8 symptoms |
| `recommendation_provider.TREATMENT_MAP` | 12 treatments |
| `plant_health_monitor.TREATMENT_MAP` | 5 treatments |

**Should be unified into a single module (e.g., `app/domain/plant_symptoms.py`).**

---

## 7. Prioritised Action Plan

### Sprint 1: Foundation (Climate Optimizer + Day/Night)

#### A1: Rewrite ClimateOptimizer as ML-First

**Priority:** 🔴 P0
**Effort:** L (Large)
**Files:** `climate_optimizer.py`, `ml_trainer.py`, `feature_engineering.py`, `training_data_collector.py`

1. **ML model training pipeline:**
   - Add `collect_climate_training_data()` to `training_data_collector.py`
   - Add `train_climate_model()` to `ml_trainer.py` — predicts (temperature, humidity) given (plant_type, growth_stage, is_daytime, season, unit_volume_m3, day_length_hours, current_conditions)
   - Use `CLIMATE_FEATURES_V1` from `feature_engineering.py` (already defined!)
   - Register trained model as `"climate_optimizer"` in `ModelRegistry`

2. **Rewrite `predict_conditions()`:**
   ```
   def predict_optimal(plant_type, growth_stage, *, is_daytime, unit_dimensions, season, current_conditions):
       # 1. Try ML model from registry
       # 2. Fallback to ThresholdService.get_optimal_conditions()
       # 3. Apply day/night adjustment (see A2)
       # 4. Apply unit dimension scaling (see A3)
   ```

3. **Remove `DEFAULT_CONDITIONS` dict** — replaced by ThresholdService
4. **Remove `detect_watering_issues()` and `analyze_climate_control()`** — irrigation is handled by `irrigation_predictor.py` + `bayesian_threshold.py`
5. **Change from "called to predict" to "monitor and notify"** — see [A5](#a5-wire-climate-optimizer-into-recommendation-pipeline)

#### A2: Day/Night Threshold Split

**Priority:** 🔴 P0
**Effort:** M (Medium)
**Files:** `threshold_service.py`, `climate_optimizer.py`, `recommendation_provider.py`, `environmental_health_scorer.py`, `continuous_monitor.py`

1. **Extend `ThresholdService`:**
   - Add `get_thresholds_for_period(plant_type, growth_stage, is_daytime: bool)` method
   - Day thresholds = current plant_info values
   - Night thresholds = `plants_info.json` night values if present, else apply default adjustments:
     - Temperature: -2 to -5°C (configurable per plant type)
     - Humidity: +5 to +10% (lower transpiration at night)
     - Lux: 0 (lights off)
   - Use `SunTimesService.is_daytime()` or device schedule light-on/off times

2. **Extend `ConditionProfile`** (in `personalized_learning.py`):
   - Add `night_environment_thresholds` field to `PlantStageConditionProfile`
   - Profile stores both day and night targets

3. **Update consumers:**
   - `ContinuousMonitor._monitor_unit()`: pass `is_daytime` to all analysis calls
   - `ClimateOptimizer`: accept `is_daytime` parameter
   - `RecommendationProvider`: pass `is_daytime` in `RecommendationContext`
   - `EnvironmentalLeafHealthScorer`: adjust scoring based on photoperiod

#### A3: Unit Dimensions Awareness

**Priority:** 🟡 P1
**Effort:** S (Small)
**Files:** `climate_optimizer.py`, `continuous_monitor.py`

1. `ContinuousMonitor` passes `unit_dimensions` to ClimateOptimizer
2. ClimateOptimizer uses volume to scale:
   - CO2 requirements (ppm * volume_liters → total CO2 needed)
   - Air exchange rate recommendations
   - Humidity management (small volumes change faster)
3. `UnitDimensions.area_m2` property:
   ```python
   @property
   def area_m2(self) -> float:
       return (self.width * self.depth) / 10000  # cm² → m²
   ```

---

### Sprint 2: Integration (Profiles + Recommendations + Notifications)

#### A4: Profile Integration Across All AI Services

**Priority:** 🟡 P1
**Effort:** M (Medium)
**Files:** `recommendation_provider.py`, `climate_optimizer.py`, `disease_predictor.py`, `environmental_health_scorer.py`

1. **`RecommendationProvider`:**
   - Inject `ThresholdService`
   - Replace all hardcoded thresholds in `_check_environmental_conditions()` with `ThresholdService.get_threshold_ranges()`
   - Add `condition_profile` to `RecommendationContext`

2. **`ClimateOptimizer`:**
   - Use `ThresholdService.get_optimal_conditions()` (already profile-aware) instead of own defaults
   - Remove `get_personalized_conditions()` → ThresholdService already handles profile blending

3. **`DiseasePredictor`:**
   - Consume `PersonalizedLearning.get_profile(unit_id).challenge_areas` for risk multiplier
   - Already has `_get_historical_risk_multipliers()` — extend to include profile data

4. **`EnvironmentalLeafHealthScorer`:**
   - `_get_thresholds()` already uses ThresholdService ✅
   - Extend to also use condition profile day/night thresholds (after A2)

#### A5: Wire Climate Optimizer into Recommendation Pipeline

**Priority:** 🟡 P1
**Effort:** M (Medium)
**Files:** `continuous_monitor.py`, `recommendation_provider.py`, `climate_optimizer.py`, `notifications_service.py`

1. **New flow in `ContinuousMonitor._monitor_unit()`:**
   ```
   climate_prediction = climate_optimizer.predict_optimal(...)
   context = RecommendationContext(
       ...,
       climate_prediction=climate_prediction,
       is_daytime=is_daytime,
       condition_profile=active_profile,
   )
   recommendations = recommendation_provider.get_recommendations(context)

   # Compare climate_prediction vs current → if significant change:
   notifications_service.send_notification(
       user_id=...,
       notification_type="climate_change",
       title="Climate Adjustment Recommended",
       message=recommendation_summary,
       requires_action=True,
       action_type="confirm_climate_change",
       action_data={"proposed": climate_prediction.to_dict(), ...}
   )
   ```

2. **Extend `RecommendationContext`** with:
   - `climate_prediction: Optional[ClimateConditions]`
   - `is_daytime: bool`
   - `condition_profile: Optional[PlantStageConditionProfile]`
   - `unit_dimensions: Optional[UnitDimensions]`

3. **`RuleBasedRecommendationProvider`** consumes climate_prediction:
   - If climate model says temp should be X but it's currently Y → generate recommendation
   - Combines with profile thresholds for validation

#### A6: Remove soil_moisture_threshold from Unit Level

**Priority:** 🟡 P1
**Effort:** S (Small)
**Files:** `threshold_service.py`, `GrowthOperations` (if present), DB schema

1. Remove `"soil_moisture_threshold"` from `_sanitize_unit_thresholds()` output
2. Verify `GrowthOperations.create_unit()` doesn't set soil_moisture_threshold
3. Verify `GrowthUnits` table: if column exists, leave it (backward compat) but stop writing to it
4. `get_unit_thresholds_dict()` already pops it ✅
5. Soil moisture remains in:
   - `EnvironmentalThresholds` domain object (used by plant-level ThresholdService) ✅
   - `PlantStageConditionProfile.soil_moisture_threshold` ✅
   - `BayesianThresholdAdjuster` (plant/user specific) ✅

---

### Sprint 3: ML Pipeline & Orchestration

#### A7: Unify Symptom/Treatment Databases

**Priority:** 🟢 P2
**Effort:** S (Small)
**Files:** New `app/domain/plant_symptoms.py`, `recommendation_provider.py`, `plant_health_monitor.py`

Extract shared `SYMPTOM_DATABASE` and `TREATMENT_MAP` into a domain module.

#### A8: Enhance ContinuousMonitor as Full Orchestrator

**Priority:** 🟢 P2
**Effort:** L (Large)
**Files:** `continuous_monitor.py`

1. Add missing service calls:
   - `PlantHealthScorer.score_plant_health()` for each plant in unit
   - `EnvironmentalLeafHealthScorer.score_current_health()`
   - `RecommendationProvider.get_recommendations()` (replaces internal logic)
2. Wire `NotificationsService` properly (currently dead code)
3. Pass `is_daytime`, `unit_dimensions`, `condition_profile` to all calls
4. Log insights to `TrainingDataCollector` for ML training data

#### A9: Unify Default Conditions

**Priority:** 🟢 P2
**Effort:** S (Small)
**Files:** `climate_optimizer.py`, `plant_growth_predictor.py`, `personalized_learning.py`

Remove all `DEFAULT_CONDITIONS` dicts from individual services. They should all use `ThresholdService.get_thresholds()` → `plants_info.json` + profiles as the single source of truth.

#### A10: Add Climate Model Training Pipeline

**Priority:** 🟢 P2
**Effort:** L (Large)
**Files:** `ml_trainer.py`, `training_data_collector.py`, `automated_retraining.py`

1. `collect_climate_training_data()`: sensor readings + outcomes (growth success, health scores)
2. `train_climate_model()`: predict optimal conditions from historical data
3. Add `"climate_optimizer"` to automated retraining jobs
4. Integrate with drift detection

#### A11: Bayesian Threshold Notification

**Priority:** 🟢 P2
**Effort:** S (Small)
**Files:** `bayesian_threshold.py`

When `update_from_feedback()` shifts the recommended threshold by more than the tolerance, send a notification to the user explaining the change and asking for confirmation.

---

## 8. Condition Profiles — Design Notes

The current `PlantStageConditionProfile` design is **solid** for the user's vision. Key attributes:

| Field | Purpose |
|-------|---------|
| `environment_thresholds` | Day thresholds (temperature, humidity, CO2, VOC, lux, air_quality) |
| `soil_moisture_threshold` | Plant-level moisture target |
| `mode` | ACTIVE (controlling) or TEMPLATE (reference) |
| `visibility` | PRIVATE, LINK, PUBLIC for sharing |
| `shared_token` | URL token for sharing |
| `rating_count` / `rating_avg` | Community rating |
| `tags` | Searchable labels |

### What needs adding for day/night (Sprint 1, A2):

```python
@dataclass
class PlantStageConditionProfile:
    # ... existing fields ...
    night_environment_thresholds: Optional[Dict[str, float]] = None  # NEW
    # Keys: temperature_threshold, humidity_threshold, etc.
    # If None, apply default night adjustments from plant_info
```

### What needs adding for dimensions awareness (Sprint 1, A3):

Profiles are already plant-type + growth-stage scoped. Unit dimensions are separate (per-unit, not per-profile). ClimateOptimizer should accept dimensions as a parameter, not store them in profiles.

---

## 9. soil_moisture_threshold Removal Scope

### Already Correct ✅
- `UnitSettings` — no soil_moisture_threshold field
- `ThresholdService.get_unit_thresholds_dict()` — pops soil_moisture
- `PlantStageConditionProfile.soil_moisture_threshold` — plant-level ✅
- `BayesianThresholdAdjuster` — plant/user-level ✅

### Needs Cleanup ❌
- `ThresholdService._sanitize_unit_thresholds()` — includes soil_moisture_threshold in output
- `GrowthOperations.create_unit()` — verify and remove if present
- Database `GrowthUnits.soil_moisture_threshold` column — stop writing, optionally drop
- `EnvironmentalThresholds.soil_moisture` — keep (it's used at plant level too)

---

## 10. Notification-Driven Decision Pattern

### Pattern (follow `ml_readiness_monitor.py` as reference):

```python
# When AI/ML service detects something that needs user attention:
notifications_service.send_notification(
    user_id=user_id,
    notification_type=NotificationType.CLIMATE_CHANGE,  # New type needed
    title="Climate Adjustment Recommended",
    message="Based on current conditions and your Flowering profile, "
            "temperature should decrease from 26°C to 22°C for the night cycle.",
    severity=NotificationSeverity.INFO,
    unit_id=unit_id,
    requires_action=True,
    action_type="confirm_climate_change",
    action_data={
        "proposed_thresholds": {...},
        "current_thresholds": {...},
        "reason": "night_cycle_transition",
        "confidence": 0.85,
    },
)
```

### New NotificationTypes Needed:
- `CLIMATE_CHANGE` — Climate optimizer proposing new conditions
- `THRESHOLD_LEARNED` — Bayesian threshold significant update
- `PROFILE_RECOMMENDATION` — AI suggesting a condition profile adjustment
- `STAGE_TRANSITION_READY` — Growth predictor detected stage readiness

### These already exist and can be reused:
- `THRESHOLD_EXCEEDED` — Environmental threshold exceeded
- `PLANT_HEALTH_WARNING` — Health issue detected
- `ML_MODEL_READY` — Model ready for activation
- `IRRIGATION_REQUEST` — Irrigation recommendation

---

## Appendix: File Sizes & Complexity

| File | LOC | Classes | Methods | Cyclomatic Complexity |
|------|-----|---------|---------|-----------------------|
| `climate_optimizer.py` | 564 | 1 | 10 | Low (simple branches) |
| `recommendation_provider.py` | 699 | 3 | 15 | Medium |
| `personalized_learning.py` | 1296 | 1 | 30+ | Medium |
| `bayesian_threshold.py` | 832 | 1 | 12 | Medium (math) |
| `disease_predictor.py` | 898 | 1 | 15 | Medium |
| `continuous_monitor.py` | 674 | 1 | 15 | Low |
| `environmental_health_scorer.py` | 515 | 1 | 12 | Medium |
| `plant_health_scorer.py` | 1102 | 1 | 20+ | High |
| `plant_health_monitor.py` | 526 | 1 | 10 | Low |
| `plant_growth_predictor.py` | 537 | 1 | 8 | Low |
| `irrigation_predictor.py` | 1581 | 1 | 25+ | High |
| `model_registry.py` | 743 | 1 | 15 | Medium |
| `ml_trainer.py` | 2491 | 1 | 20+ | High |
| `feature_engineering.py` | 1885 | 3 | 25+ | Medium |
| `training_data_collector.py` | 591 | 1 | 10 | Low |
| `ab_testing.py` | 499 | 1 | 10 | Low |
| `automated_retraining.py` | 692 | 1 | 12 | Medium |
| `drift_detector.py` | 347 | 1 | 6 | Low |
| `ml_readiness_monitor.py` | 476 | 1 | 8 | Low |
| `__init__.py` | 159 | 0 | 0 | N/A |
| **TOTAL** | **~16,600** | **~22** | **~280** | — |

---

*End of AI Services Audit Report*
