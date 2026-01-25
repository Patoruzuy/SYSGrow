# SYSGrow Architecture Refactoring Plan

**Created**: 2025-01-27  
**Updated**: 2026-01-03  
**Status**: Phase 9 Complete

---

## Executive Summary

Comprehensive analysis of 50+ services across AI, Application, Hardware, and Utilities layers revealed systemic issues requiring phased refactoring. This document provides an actionable implementation plan.

### Progress Tracker

| Phase | Description | Status |
|-------|-------------|--------|
| **1** | Enum Consolidation | ✅ Complete |
| **2** | Constants Consolidation | ✅ Complete |
| **3** | Additional Enum Consolidation | ✅ Complete |
| **4** | Domain Object Extraction + Notification Refactoring | ✅ Complete |
| **5** | Additional Domain Object Extraction | ✅ Complete |
| **6** | Additional Domain Object Extraction | ✅ Complete |
| **7** | Repository Pattern Fixes | ✅ Complete |
| **8** | Service Splits (EmailService) | ✅ Complete |
| **9** | State Persistence | ✅ Complete |
| **10** | Further Service Splits (GrowthService) | 🔄 Pending |

### Critical Findings

| Category | Count | Priority |
|----------|-------|----------|
| Duplicate Enums/Constants | 12 | HIGH |
| Magic Strings Needing Enums | 8 categories | HIGH |
| Domain Objects in Wrong Layer | 13 objects | MEDIUM |
| Mixed Concerns / God Services | 4 services | MEDIUM |
| Repository Pattern Violations | 3 services | MEDIUM |
| In-Memory State Not Persisted | 2 services | LOW |

---

## Phase 1: Enum Consolidation (HIGH Priority)

### 1.1 Create Centralized Enum Module

## Phase 1: Enum Consolidation ✅ COMPLETE

### 1.1 Created `app/enums/common.py`

New enums added to existing `app/enums/` structure:
- `RiskLevel` - Consolidated from disease_predictor and plant_health_monitor
- `HealthLevel` - System health states
- `DriftRecommendation` - ML drift actions
- `TrainingDataType` - ML training categories
- `AnomalyType` - Sensor anomaly types (moved from anomaly_detection_service)
- `RequestStatus` - Workflow states
- `MQTTSource` - MQTT message sources

### 1.2 Updated `app/enums/__init__.py`

All new enums exported for easy import: `from app.enums import RiskLevel, AnomalyType`

### 1.3 Migration Completed

| Service | Change |
|---------|--------|
| `disease_predictor.py` | Removed local `RiskLevel`, imports from `app.enums` |
| `anomaly_detection_service.py` | Removed local `AnomalyType`, imports from `app.enums` |

---

## Phase 2: Constants Consolidation ✅ COMPLETE

### 2.1 Created `app/constants.py`

Consolidated constants:
- `IRRIGATION_THRESHOLDS` - Default soil moisture by plant type
- `GROWTH_STAGE_MOISTURE_ADJUSTMENTS` - Stage-based threshold adjustments
- `IRRIGATION_DURATIONS` - Default durations by soil type
- `MetricType` - Sensor metric identifiers
- `CacheKeys` - Standardized cache key patterns
- `MQTT_TOPIC_PATTERNS` - MQTT topic patterns
- `BAYESIAN_DEFAULTS` - Bayesian learning parameters

### 2.2 Migration Completed

| Service | Change |
|---------|--------|
| `bayesian_threshold.py` | Uses `IRRIGATION_THRESHOLDS`, `GROWTH_STAGE_MOISTURE_ADJUSTMENTS`, `BAYESIAN_DEFAULTS` |
| `irrigation_predictor.py` | Uses `IRRIGATION_THRESHOLDS`, `IRRIGATION_DURATIONS`, `GROWTH_STAGE_MOISTURE_ADJUSTMENTS` |

---

## Phase 3: Enum Consolidation Round 2 ✅ COMPLETE

### 3.1 Additional Enums Added to `app/enums/common.py`

- `DiseaseType` - Disease classification (consolidated from disease_predictor + plant_health_monitor)
- `PlantHealthStatus` - Plant health states (moved from plant_health_monitor)
- `ControlStrategy` - Control loop strategies (moved from control_logic)
- `SensorState` - Sensor health states (moved from sensor_polling_service)

### 3.2 Updated `app/enums/growth.py`

- Added `GERMINATION` to `PlantStage` enum for growth prediction compatibility

### 3.3 Services Updated

| Service | Change |
|---------|--------|
| `disease_predictor.py` | Uses shared `DiseaseType` from `app.enums` |
| `plant_health_monitor.py` | Uses shared `DiseaseType`, `PlantHealthStatus` from `app.enums` |
| `plant_growth_predictor.py` | Uses `PlantStage` from `app.enums` (aliased as `GrowthStage`) |
| `control_logic.py` | Uses shared `ControlStrategy` from `app.enums` |
| `sensor_polling_service.py` | Uses shared `SensorState` from `app.enums` |

---

## Phase 4: Notification System Refactoring ✅ COMPLETE

### 4.1 Added Notification Enums to `app/enums/common.py`

- `NotificationType` - 11 notification types (LOW_BATTERY, PLANT_NEEDS_WATER, IRRIGATION_CONFIRM, etc.)
- `NotificationSeverity` - INFO, WARNING, CRITICAL
- `NotificationChannel` - EMAIL, IN_APP, BOTH
- `IrrigationFeedback` - TOO_LITTLE, JUST_RIGHT, TOO_MUCH, SKIPPED

### 4.2 Moved `NotificationSettings` to `app/domain/notification_settings.py`

Domain object extracted from `notifications_service.py` to proper domain layer.

### 4.3 Updated Services

| File | Change |
|------|--------|
| `notifications_service.py` | Imports enums from `app.enums`, imports `NotificationSettings` from `app.domain` |
| `notifications.py` (blueprint) | Imports from `app.enums` and `app.domain` |
| `app/enums/__init__.py` | Exports new notification enums |
| `app/domain/__init__.py` | Exports `NotificationSettings` |

### 4.4 Backward Compatibility

- `IrrigationFeedbackResponse` alias maintained for existing code

---

## Phase 5: Domain Object Extraction ✅ COMPLETE

### 5.1 Created Domain Files

| File | Classes | Source |
|------|---------|--------|
| `app/domain/energy.py` | `EnergyReading`, `PowerProfile`, `ConsumptionStats` | `energy_monitoring.py` |
| `app/domain/control.py` | `ControlConfig`, `ControlMetrics` | `control_logic.py` |
| `app/domain/anomaly.py` | `Anomaly` | `anomaly_detection_service.py` |

### 5.2 Services Updated

| Service | Change |
|---------|--------|
| `energy_monitoring.py` | Imports from `app.domain.energy` (removed 70+ lines) |
| `control_logic.py` | Imports from `app.domain.control` (removed 55+ lines) |
| `anomaly_detection_service.py` | Imports from `app.domain.anomaly` (removed 12 lines) |
| `app/hardware/actuators/__init__.py` | Imports domain classes from `app.domain.energy` |

### 5.3 Updated `app/domain/__init__.py`

Exports:
- `Anomaly`
- `ControlConfig`, `ControlMetrics`
- `EnergyReading`, `PowerProfile`, `ConsumptionStats`
- `EnvironmentalThresholds`
- `NotificationSettings`
- `PlantProfile`
- `UnitRuntime`, `UnitSettings`, `UnitDimensions`

---

## Phase 6: Additional Domain Extraction ✅ COMPLETE

### 6.1 New Domain Files Created

| File | Classes | Source |
|------|---------|--------|
| `app/domain/system.py` (extended) | `SystemHealthReport` | `system_health_service.py` |
| `app/domain/irrigation.py` | `PredictionConfidence`, `UserResponsePrediction`, `ThresholdPrediction`, `DurationPrediction`, `TimingPrediction`, `IrrigationPrediction` | `irrigation_predictor.py` |
| `app/domain/plant_health.py` | `PlantHealthObservation`, `EnvironmentalCorrelation` | `plant_health_monitor.py` |

### 6.2 Services Updated

| Service | Lines Removed |
|---------|---------------|
| `system_health_service.py` | ~12 lines |
| `irrigation_predictor.py` | ~120 lines |
| `plant_health_monitor.py` | ~40 lines |

### 6.3 Updated `app/domain/__init__.py`

Now exports 22 domain objects across 9 domain modules.

---

## Phase 7: Repository Pattern Fixes ✅ COMPLETE

### 7.1 PlantHealthMonitor File I/O → Repository

**Issue**: Direct file writes to `data/correlations/{unit_id}_correlations.jsonl`

**Solution**: Added methods to `AIHealthDataRepository`:
- `save_environmental_correlation()` - Stores correlations in `PlantHealthLogs` table
- `get_correlations_for_unit()` - Retrieves correlations from database

**Updated**: `plant_health_monitor.py`
- `_store_correlations()` now uses repository instead of file writes
- Removed unused imports: `os`, `uuid`, `dataclasses.asdict`

### 7.2 ControlLogic CSV Logging → Repository

**Issue**: Direct CSV file writes via `_log_data()` method

**Solution**: Added methods to `AIHealthDataRepository`:
- `save_control_log()` - Stores control state in `MLTrainingData` table
- `get_control_logs()` - Retrieves control logs from database

**Updated**: `control_logic.py`
- Removed `csv` import
- Removed `log_file` constructor parameter
- Removed `_init_csv_log()` method
- Added `ai_repo` constructor parameter
- `_log_data()` now uses repository (graceful fallback to debug log if no repo)

**Updated**: `growth_service.py`
- Added `ai_health_repo` constructor parameter
- Passes `ai_repo` when instantiating `ControlLogic`

**Updated**: `container_builder.py`
- Passes `ai_health_repo=infra.ai_health_repo` to `GrowthService`

---

## Phase 8: Service Splits (EmailService) ✅ COMPLETE

### 8.1 Created `app/services/utilities/email_service.py`

Extracted email functionality from NotificationsService for:
- Single responsibility (email delivery only)
- Reusability across services
- Easier testing and mocking

**New Classes**:
- `EmailConfig` - SMTP configuration dataclass
- `EmailMessage` - Email message dataclass with MIME conversion
- `EmailService` - Email sending service with TLS support

**Methods**:
- `send()` - Send raw email message
- `send_notification_email()` - Send formatted notification with HTML template

### 8.2 Updated NotificationsService

- Removed direct `smtplib` and `email.mime` imports
- Added `email_service` constructor parameter
- `_send_email()` now delegates to EmailService
- Reduced coupling and improved testability

### 8.3 Updated Container Builder

- Creates EmailService instance
- Injects into NotificationsService

---

## Phase 9: State Persistence ✅ COMPLETE

### 9.1 New Database Tables

Added to `sqlite_handler.py`:

**ABTests Table**:
- test_id, model_name, version_a, version_b
- split_ratio, start_date, end_date, status
- min_samples, winner

**ABTestResults Table**:
- result_id, test_id, version
- timestamp, predicted, actual, error

**DriftMetrics Table**:
- metric_id, model_name, timestamp
- prediction, actual, confidence, error

### 9.2 Repository Methods Added

Added to `AIHealthDataRepository`:

**A/B Testing**:
- `save_ab_test()` - Persist test configuration
- `get_ab_test()` - Get single test
- `get_active_ab_tests()` - Get all running tests
- `save_ab_test_result()` - Persist prediction result
- `get_ab_test_results()` - Get all results for a test

**Drift Metrics**:
- `save_drift_metric()` - Persist drift tracking metric
- `get_drift_metrics()` - Get recent metrics for model
- `cleanup_old_drift_metrics()` - Prune old records

### 9.3 Updated ABTestingService

- Added `ai_repo` constructor parameter
- `_load_active_tests()` - Load tests on startup
- `_persist_test()` - Save test state changes
- `create_test()` - Now persists to database
- `record_result()` - Now persists results
- `complete_test()` - Persists completion status
- `cancel_test()` - Persists cancellation status

### 9.4 Updated ModelDriftDetectorService

- Added `ai_health_repo` constructor parameter
- `track_prediction()` - Now persists metrics to database

### 9.5 Updated Container Builder

- Passes `ai_health_repo` to DriftDetector and ABTestingService

---

## Phase 10: Further Service Splits (PENDING)

### 7.1 Duplicate Constants to Merge

| Constant | Locations | Resolution |
|----------|-----------|------------|
| `DEFAULT_THRESHOLDS` | `irrigation_predictor.py`, `bayesian_threshold.py` | Keep in `bayesian_threshold.py` as FALLBACK, remove from predictor |
| `GROWTH_STAGE_ADJUSTMENTS` | `irrigation_predictor.py`, `bayesian_threshold.py`, `climate_optimizer.py` | Create `domain/growth_adjustments.py` |
| Severity constants | 4 services | Replace with `Severity` enum |

### 3.2 Create Shared Constants Module

**Create**: `app/constants.py`

```python
"""
Shared constants for the SYSGrow system.
Domain-specific constants that are used across multiple services.
"""

# Growth Stage Threshold Adjustments (moisture percentage adjustments)
GROWTH_STAGE_ADJUSTMENTS = {
    "germination": {"moisture_min": 5, "moisture_max": 10},
    "seedling": {"moisture_min": 3, "moisture_max": 5},
    "vegetative": {"moisture_min": 0, "moisture_max": 0},
    "flowering": {"moisture_min": -5, "moisture_max": -3},
    "fruiting": {"moisture_min": -3, "moisture_max": 0},
    "harvest": {"moisture_min": -10, "moisture_max": -5},
}

# Metric types used across services
METRIC_TYPES = {
    "TEMPERATURE": "temperature",
    "HUMIDITY": "humidity",
    "SOIL_MOISTURE": "soil_moisture",
    "LIGHT": "light",
    "CO2": "co2_ppm",
    "VOC": "voc_ppb",
    "PRESSURE": "pressure",
    "WATER_LEVEL": "water_level",
    "PH": "ph",
    "EC": "ec",
}

# Cache key patterns
class CacheKeys:
    SENSOR_PREFIX = "sensor:{unit_id}:{sensor_id}"
    ACTUATOR_PREFIX = "actuator:{unit_id}:{actuator_id}"
    READINGS_PREFIX = "readings:{unit_id}:{sensor_id}"
```

---

## Phase 4: Mixed Concerns Separation (MEDIUM Priority)

### 4.1 GrowthService Split (1306 lines → 3 services)

**Current**: `app/services/application/growth_service.py` (God Service)

**Split Into**:
1. `GrowthPredictionService` - ML predictions, growth analysis
2. `GrowthTrackingService` - Event logging, milestone tracking
3. `GrowthDataService` - Data retrieval, statistics

### 4.2 NotificationsService Split (951 lines → 2 services)

**Current**: `app/services/application/notifications_service.py`

**Split Into**:
1. `NotificationService` - Notification CRUD, delivery
2. `EmailService` - Email template rendering, SMTP delivery

### 4.3 ClimateControlService Cleanup (1096 lines)

**Extract**:
- Database persistence → `ClimateDataPersistenceService`
- Throttling logic → Move to sensor processor pipeline

### 4.4 ControlLogic Cleanup (755 lines)

**Extract**:
- CSV logging → `ControlLoggerService`
- Metrics tracking → `ControlMetricsService`

---

## Phase 5: Repository Pattern Fixes

### 5.1 Direct SQL Violations

| Service | Violation | Fix |
|---------|-----------|-----|
| `PlantHarvestService._compute_top_performers()` | Raw SQL queries | Create `HarvestRepository` methods |
| `PlantHealthMonitor` | Writes to `.sysgrow/correlations.json` | Create `CorrelationRepository` |
| `PersonalizedLearning` | Writes to `.sysgrow/profiles/` | Create `ProfileRepository` |
| `TrainingDataCollector` | Writes to `.sysgrow/training_data/` | Create `TrainingDataRepository` |

### 5.2 Create Missing Repositories

```python
# app/repositories/correlation_repository.py
class CorrelationRepository:
    """Manages plant health correlation data persistence."""
    
    def save_correlations(self, plant_id: int, correlations: dict) -> None: ...
    def load_correlations(self, plant_id: int) -> dict | None: ...

# app/repositories/profile_repository.py
class ProfileRepository:
    """Manages personalized learning profile persistence."""
    
    def save_profile(self, user_id: int, profile: dict) -> None: ...
    def load_profile(self, user_id: int) -> dict | None: ...

# app/repositories/training_data_repository.py
class TrainingDataRepository:
    """Manages ML training data persistence."""
    
    def save_training_data(self, data_type: str, data: dict) -> None: ...
    def load_training_data(self, data_type: str) -> list[dict]: ...
```

---

## Phase 6: State Persistence

### 6.1 In-Memory State to Persist

| Service | State | Solution |
|---------|-------|----------|
| `ABTestingService._experiments` | Dict of experiments | Create `experiments` table or JSON file |
| `DriftDetector._metrics_history` | Deque of metrics | Create `drift_metrics` table |
| `EnergyMonitoringService._power_records` | Power history | Already persisted? Verify |

---

## Implementation Order

### Sprint 1: Foundation (1-2 days)
- [ ] Create `app/enums/` with all enums
- [ ] Update all imports to use centralized enums
- [ ] Run tests, fix any breaks

### Sprint 2: Domain Extraction (1-2 days)
- [ ] Create new domain files (`control.py`, `energy.py`, etc.)
- [ ] Move dataclasses to domain layer
- [ ] Update imports across codebase

### Sprint 3: Constants & Magic Strings (1 day)
- [ ] Create `app/constants.py`
- [ ] Replace magic strings with enum values
- [ ] Replace duplicate constants with imports

### Sprint 4: Service Splits (2-3 days)
- [ ] Split `GrowthService` into 3 services
- [ ] Split `NotificationsService` into 2 services
- [ ] Update container_builder.py
- [ ] Update all usages

### Sprint 5: Repository Fixes (1-2 days)
- [ ] Create missing repositories
- [ ] Migrate file-based persistence to repositories
- [ ] Remove direct SQL from services

### Sprint 6: State Persistence (1 day)
- [ ] Add persistence for ABTestingService
- [ ] Add persistence for DriftDetector
- [ ] Verify EnergyMonitoringService persistence

---

## Validation Checklist

After each sprint:
- [ ] All tests pass
- [ ] No circular imports
- [ ] Container builds successfully
- [ ] API endpoints work correctly
- [ ] WebSocket events fire correctly

---

## Files to Modify Summary

### New Files to Create
- `app/domain/enums.py`
- `app/domain/control.py`
- `app/domain/energy.py`
- `app/domain/anomaly.py`
- `app/domain/health.py`
- `app/domain/config.py`
- `app/domain/utilities.py`
- `app/domain/constants.py`
- `app/repositories/correlation_repository.py`
- `app/repositories/profile_repository.py`
- `app/repositories/training_data_repository.py`
- `app/services/application/growth_prediction_service.py`
- `app/services/application/growth_tracking_service.py`
- `app/services/application/growth_data_service.py`
- `app/services/application/email_service.py`

### Files to Modify (Enum Imports)
- `app/services/ai/disease_predictor.py`
- `app/services/ai/plant_health_monitor.py`
- `app/services/ai/plant_growth_predictor.py`
- `app/services/ai/irrigation_predictor.py`
- `app/services/ai/bayesian_threshold.py`
- `app/services/ai/climate_optimizer.py`
- `app/services/ai/drift_detector.py`
- `app/services/ai/training_data_collector.py`
- `app/services/application/alert_service.py`
- `app/services/application/notifications_service.py`
- `app/services/application/activity_logger.py`
- `app/services/application/irrigation_workflow_service.py`
- `app/services/hardware/control_logic.py`
- `app/services/hardware/sensor_polling_service.py`
- `app/services/hardware/mqtt_sensor_service.py`
- `app/services/utilities/anomaly_detection_service.py`
- `app/services/utilities/system_health_service.py`

### Files to Split
- `app/services/application/growth_service.py` → 3 files
- `app/services/application/notifications_service.py` → 2 files

---

## Appendix: Detailed Analysis Reports

### A. AI Services Analysis

| Service | Lines | Issues |
|---------|-------|--------|
| `model_registry.py` | 312 | ✅ Clean |
| `disease_predictor.py` | 441 | ⚠️ Duplicate RiskLevel enum |
| `climate_optimizer.py` | 389 | ⚠️ Duplicate GROWTH_STAGE_ADJUSTMENTS |
| `ml_trainer.py` | 287 | ✅ Clean |
| `inference_engine.py` | 156 | ✅ Clean |
| `irrigation_predictor.py` | 298 | ⚠️ Duplicate DEFAULT_THRESHOLDS |
| `bayesian_threshold.py` | 245 | ✅ Fixed (ThresholdService integration) |
| `plant_growth_predictor.py` | 412 | ⚠️ GrowthStage should be in domain |
| `plant_health_monitor.py` | 523 | ⚠️ Duplicate RiskLevel, file writes |
| `personalized_learning.py` | 367 | ⚠️ File writes to .sysgrow/ |
| `recommendation_engine.py` | 278 | ✅ Clean |
| `ab_testing_service.py` | 234 | ⚠️ In-memory state |
| `drift_detector.py` | 312 | ⚠️ In-memory state, magic strings |
| `automated_retraining.py` | 289 | ⚠️ Threading in service |
| `training_data_collector.py` | 198 | ⚠️ File writes |
| `continuous_monitoring.py` | 445 | ⚠️ Threading in service |
| `model_versioning_service.py` | 187 | ✅ Clean |

### B. Application Services Analysis

| Service | Lines | Issues |
|---------|-------|--------|
| `growth_service.py` | 1306 | ❌ GOD SERVICE - split required |
| `notifications_service.py` | 951 | ⚠️ Mixed email + notifications |
| `alert_service.py` | 423 | ⚠️ Magic string constants |
| `activity_logger.py` | 287 | ⚠️ Duplicate severity |
| `irrigation_workflow_service.py` | 534 | ⚠️ Magic string status values |
| `threshold_service.py` | 198 | ✅ Fixed (common_name param) |
| `plant_harvest_service.py` | 445 | ⚠️ Direct SQL |
| `unit_management_service.py` | 312 | ✅ Clean |
| `analytics_service.py` | 567 | ✅ Clean |
| `settings_service.py` | 234 | ✅ Clean |
| `plant_image_service.py` | 187 | ✅ Clean |
| `plant_template_service.py` | 156 | ✅ Clean |
| `unified_scheduler.py` | 678 | ✅ Clean |
| `backup_restore_service.py` | 345 | ✅ Clean |
| `discovery_service.py` | 289 | ✅ Clean |
| `calibration_settings_service.py` | 198 | ✅ Clean |

### C. Hardware Services Analysis

| Service | Lines | Issues |
|---------|-------|--------|
| `sensor_management_service.py` | 697 | ⚠️ Protocol magic strings |
| `actuator_management_service.py` | 716 | ⚠️ Reason magic strings |
| `climate_control_service.py` | 1096 | ⚠️ Mixed concerns |
| `mqtt_sensor_service.py` | 727 | ⚠️ ExponentialBackoff should be utility |
| `camera_service.py` | 335 | ⚠️ Camera type magic strings |
| `safety_service.py` | 142 | ✅ Clean |
| `scheduling_service.py` | 92 | ✅ Clean |
| `state_tracking_service.py` | 140 | ⚠️ Overlaps with energy |
| `control_algorithms.py` | 99 | ✅ Clean |
| `control_logic.py` | 755 | ⚠️ Domain objects, mixed concerns |
| `energy_monitoring.py` | 468 | ⚠️ Domain objects to extract |
| `sensor_polling_service.py` | 500 | ⚠️ Domain objects, magic strings |
| `throttle_config.py` | 131 | ⚠️ Should be in domain/config |

### D. Utilities Services Analysis

| Service | Lines | Issues |
|---------|-------|--------|
| `anomaly_detection_service.py` | 314 | ⚠️ Domain objects to extract |
| `calibration_service.py` | 232 | ✅ Clean |
| `system_health_service.py` | 890 | ⚠️ Health status overlap |

---

*Document generated from comprehensive codebase analysis. Update as implementation progresses.*
