# Full Code Audit — Services Layer

**Date:** 2026-02-12
**Auditor:** Senior Chief Engineer (AI-assisted)
**Scope:** `app/services/` — 54 service files, ~28,000 LOC
**Tools:** radon (cyclomatic complexity), bandit (security), pytest, manual review
**Test result after fixes:** 271 passed, 19 skipped, 1 pre-existing failure

---

## Executive Summary

The services layer is the backbone of the SYSGrow backend: 54 files organized into 4 sub-packages (`application/`, `ai/`, `hardware/`, `utilities/`). The organization is thoughtful and documented. However, the layer suffers from **3 god classes**, **~350 lines of dead code** (now removed), **1 real bug in production** (lux feature extraction was silently broken), and **excessive defensive exception swallowing** in the alert dedup path.

| Metric | Value | Assessment |
|--------|-------|------------|
| Total service files | 54 | Well-organized |
| Average CC | B (5.49) | ✅ Healthy |
| F-grade functions | 5 | ⚠️ Needs attention |
| E-grade functions | 9 | ⚠️ Backlog |
| Bandit issues (medium+) | 1 (false positive) | ✅ Clean |
| Bandit issues (low) | 24 (mostly B110) | Acceptable |
| Files >2,000 LOC | 3 | 🔴 God classes |

### Fixes Applied During This Audit

| Fix | Impact |
|-----|--------|
| **Lux feature extraction bug** — `for candidate in (SensorField.LUX.value)` iterated over characters `'l','u','x'` instead of the string `"lux"`. All lux-based ML features were silently zero. | 🔴 CRITICAL — ML predictions affected |
| **~350 lines of dead code removed** from `IrrigationPredictor` — 3 unreachable rule-based fallback blocks after unconditional `return` statements. CC dropped: `predict_threshold` D(27)→C(19), `predict_user_response` E(35)→D(21), `predict_duration` removed from D+ list entirely. | 🟠 HIGH — Code clarity, misleading fallbacks |
| **SQL injection false positive suppressed** with `# nosec B608` in `harvest_service.py` (table name from compile-time tuple constant). | 🔵 LOW — Housekeeping |
| **Timezone bug fixed** — 3× `datetime.now()` in `predict_next_irrigation_time` replaced with `utc_now()`. Cutoff/prediction timestamps now match UTC DB data. | 🟡 MEDIUM — Correct moisture predictions |
| **Irrigation execution log duplication removed** — Extracted `_log_execution_result()` helper, replaced 5× copy-pasted 15-parameter `create_execution_log` calls. CC `_execute_irrigation` 36→26. | 🟡 MEDIUM — DRY, maintainability |
| **AlertService memory leak fixed** — `_alerts` dict converted to bounded `OrderedDict` with LRU eviction (maxsize 2048). Stale dedup index entries cleaned on eviction. | 🟡 MEDIUM — Memory safety |
| **AlertService dedup refactored** — 170+ lines of inline triple-layer dedup code extracted into `_try_deduplicate()`, `_compute_dedup_key()`, `_parse_alert_timestamp()`, `_increment_occurrences()`. CC `create_alert` 71→19. Exception handlers reduced from 27 to 3 well-placed boundaries. | 🟠 HIGH — Maintainability, observability |
| **HarvestService raw SQL moved to repository** — Added `PlantRepository.cleanup_plant_data()`. `HarvestService._cleanup_plant_data` now delegates to the repo (with raw SQL fallback for backwards compatibility). | 🟡 MEDIUM — Proper layering |

---

## 1. Architectural Review

### 1.1 Service Organization — ✅ Well-Structured

```
app/services/
├── application/    # 17 files — Singleton services (1 per app lifetime)
│   ├── alert_service.py, analytics_service.py, growth_service.py, ...
├── ai/             # 19 files — ML/prediction/training services
│   ├── irrigation_predictor.py, feature_engineering.py, ml_trainer.py, ...
├── hardware/       # 11 files — Per-unit runtime workers
│   ├── scheduling_service.py, sensor_management_service.py, ...
├── utilities/      # 5 files — Stateless helpers
│   ├── email_service.py, system_health_service.py, ...
├── container.py    # ServiceContainer dataclass
└── container_builder.py  # ContainerBuilder (1,076 LOC)
```

**Strengths:**
- Clear lifecycle contracts documented in `__init__.py`
- Container/Builder pattern separates construction from usage
- Builder decomposed into subsystem methods (`build_sensors`, `build_ai`, etc.)

**Concerns:**

| Issue | Severity | Detail |
|-------|----------|--------|
| **Deferred wiring with `None` sentinels** | MEDIUM | Services init with `None` deps, then monkey-patched later. Creates temporal coupling — if wiring order changes, silent `NoneType` errors at runtime. |
| **`Any` escape hatches** | ~~LOW~~ ✅ FIXED | ~~3 container fields use `Any` type with `# avoiding import cycle` comments.~~ Replaced with `TYPE_CHECKING` forward refs. |
| **Flat container** | LOW | 30+ fields in one dataclass. Could be grouped into sub-containers (`AIServices`, `HardwareServices`, etc.). |

### 1.2 Dependency & Layering

| Pattern | Assessment |
|---------|------------|
| Service → Repository | ✅ Clean. Services inject repos, never raw DB handles (except S-2 below). |
| Service → Service | ⚠️ `GrowthService` ↔ `PlantViewService` have a bidirectional dependency (guarded by runtime imports). |
| Service → Domain | ✅ Domain objects (`EnvironmentalThresholds`, `UnitSettings`) used correctly. |
| Service → Infrastructure | ✅ Mediated through repos. One exception: `harvest_service.py` reaches through `analytics_repo._backend.connection()`. |

**Recommendation:** ~~Break the `GrowthService` ↔ `PlantViewService` cycle with a `PlantStateReader` interface.~~ ✅ Done — `PlantStateReader` Protocol in `app/services/protocols.py`.

---

## 2. Code Quality & Complexity

### 2.1 Complexity Hotspots (F-grade, CC ≥ 41)

| Rank | Function | CC | File | Root Cause |
|------|----------|----|------|------------|
| 1 | `AlertService.create_alert` | **71** | alert_service.py | Triple-layered dedup with 27 nested exception handlers |
| 2 | `AnalyticsService.get_enriched_sensor_history` | **64** | analytics_service.py | 7-step pipeline encoded as monolith |
| 3 | `FeatureEngineer.create_irrigation_features` | **63** | feature_engineering.py | 40+ features built in single procedural block |
| 4 | `PlantViewService.create_plant` | **54** | plant_service.py | Condition profile + sensor linking + validation + event publishing |
| 5 | `ThresholdService.get_threshold_ranges` | **41** | threshold_service.py | Cache + catalog + stage filtering + profile overlay |

### 2.2 Complexity Hotspots (E-grade, CC 31–40)

| Function | CC | File |
|----------|----|------|
| `IrrigationPredictor.predict_timing` | 35 | irrigation_predictor.py |
| `IrrigationWorkflowService.build_irrigation_feature_inputs` | 35 | irrigation_workflow_service.py |
| `DeviceHealthService.get_sensor_health` | 37 | device_health_service.py |
| `RuleBasedRecommendationProvider._get_irrigation_recommendations` | 37 | recommendation_provider.py |
| `IrrigationWorkflowService._execute_irrigation` | 36 | irrigation_workflow_service.py |
| `IrrigationWorkflowService.handle_feedback` | 36 | irrigation_workflow_service.py |
| `PlantViewService.update_plant` | 33 | plant_service.py |
| `DeviceHealthService.check_all_devices_health_and_alert` | 33 | device_health_service.py | ✅ Refactored — offline/health logic extracted to helpers |
| `GrowthService.update_unit_settings` | 32 | growth_service.py |
| `PlantHealthScorer._generate_recommendations` | 31 | plant_health_scorer.py | ✅ Thresholds extracted to `RECOMMENDATION_THRESHOLDS` dict |

### 2.3 God Classes (>2,000 LOC)

| Class | LOC | Responsibilities (SRP violations) |
|-------|-----|-----------------------------------|
| `AnalyticsService` | **2,699** | Sensor analytics, actuator analytics, cost analysis, anomaly detection, predictive analytics, cache warming |
| `PlantViewService` | ~~2,559~~ **~1,800** | ✅ Refactored — now thin façade. Sensor/actuator linking → `PlantDeviceLinker`. Stage transitions/profiles → `PlantStageManager`. |
| `MLTrainerService` | **2,491** | Trains 8+ different model types with tightly-coupled feature engineering |

### 2.4 Dead Code (Fixed)

**~350 lines** of unreachable rule-based fallback code in `IrrigationPredictor`:
- `predict_threshold`: 88 lines after unconditional `return` (L546–L633) — **removed**
- `predict_user_response`: 81 lines (L742–L822) — **removed**
- `predict_duration`: 89 lines (L914–L1002) — **removed**

These were leftover from a refactoring that added ML-gated paths on top of original Bayesian logic. The dead blocks gave a false impression that heuristic fallbacks existed.

---

## 3. Security & Error Handling

### 3.1 Critical: Exception Swallowing in AlertService

`create_alert` contains **27 bare `except:` / `except Exception:` clauses** that all `pass` or `logger.debug()`. Any bug in the dedup logic (cache corruption, type errors, race conditions) is silently eaten. This makes dedup failures invisible — alerts either duplicate silently or vanish.

**Severity:** 🔴 HIGH
**Recommendation:** Consolidate the triple-layer dedup into a single `_try_deduplicate(key, metadata) -> Optional[int]` method with exactly one try/except boundary. Log at WARNING level on dedup failure so it's observable.
**Effort:** Medium (M)

### 3.2 Repository Bypass in HarvestService

`_cleanup_plant_data` accesses `self.analytics_repo._backend.connection()` to execute 6+ raw SQL statements. This violates the repository abstraction and creates a hidden SQLite coupling.

**Severity:** 🟠 MEDIUM
**Recommendation:** Add a `PlantCleanupRepository.delete_all_plant_data(plant_id)` method.
**Effort:** Small (S)

### 3.3 Bandit Summary

| ID | Count | Severity | Description |
|----|-------|----------|-------------|
| B608 | 1 | MEDIUM | SQL injection false positive (hardcoded table names) — suppressed with `# nosec` |
| B110 | 18 | LOW | `try/except/pass` — most are legitimate fallbacks for hardware/optional features |
| B112 | 2 | LOW | `try/except/continue` — loop resilience patterns |
| B105 | 2 | LOW | False positive: `password=` parameter names on non-secret values |
| B311 | 1 | LOW | `random.random()` in A/B testing — not security-critical |

### 3.4 Timezone Bug in IrrigationPredictor

`predict_next_irrigation_time` uses `datetime.now()` (naive local time) while DB timestamps are ISO-formatted UTC. This produces incorrect moisture decline predictions proportional to the server's UTC offset.

**Severity:** 🟠 MEDIUM
**Fix:** Replace `datetime.now()` with `utc_now()` from `app.utils.time`.
**Effort:** Small (S)

---

## 4. Performance & Scalability

### 4.1 N+1 Query Pattern — ✅ Fixed

~~`DeviceHealthService.check_all_devices_health_and_alert` iterates over all units, then for each unit iterates over all sensors, calling `get_sensor_health(sensor_id)` individually. For a farm with 10 units × 20 sensors, this is 200 DB round-trips.~~

Refactored to batch-fetch: live health from in-memory `SystemHealthService` (O(1) per sensor), plus a single `get_latest_health_batch(sensor_ids)` SQL query for sensors without live data. Also eliminated redundant `_get_sensor_unit_id()` calls since the sensor list already carries `unit_id`.

### 4.2 In-Memory Caching Patterns

| Service | Cache Type | Assessment |
|---------|-----------|------------|
| `AlertService` | Dict + TTLCache | ✅ Bounded `OrderedDict` with LRU eviction (maxsize 2048). Fixed. |
| `PlantViewService` | Dict with `threading.Lock` | ✅ Properly locked, bounded by unit count. |
| `SchedulingService` | Dict with `threading.Lock` | ✅ Properly locked. |
| `ThresholdService` | Dict | ✅ Bounded by unit count, has TTL logic. |

### 4.3 Concurrency Safety

| Service | Pattern | Assessment |
|---------|---------|------------|
| `SchedulingService` | `threading.Lock` on all reads/writes | ✅ Correct |
| `PlantViewService` | `threading.Lock` on plant cache | ✅ Correct |
| `MQTTSensorService` | No locks on dict writes | ⚠️ Safe under CPython GIL only. Document assumption. |
| `IrrigationWorkflowService` | `@with_lock` decorator | ✅ Correct |

---

## 5. Modularity & Abstraction

### 5.1 SRP Violations

| Class | Current Responsibilities | Proposed Split |
|-------|------------------------|----------------|
| `PlantViewService` | ~~CRUD + caching + profiles + events + sensors + stages~~ | ✅ Done — `PlantDeviceLinker` (sensor/actuator linking), `PlantStageManager` (stages/profiles/thresholds) + thin façade |
| `AnalyticsService` | Sensor + actuator + cost + anomaly + predictive analytics | `SensorAnalyticsService`, `ActuatorAnalyticsService`, `CostAnalyticsService` |
| `IrrigationPredictor` | 5 prediction models + model lifecycle | `ThresholdPredictor`, `ResponsePredictor`, `DurationPredictor`, `TimingPredictor` implementing a `Predictor` protocol |

### 5.2 Duplication

| Duplication | Location | Impact |
|-------------|----------|--------|
| Irrigation history timestamp parsing | `feature_engineering.py` + `irrigation_predictor.py` | Feature drift risk — two parsers may diverge |
| `_is_raspberry_pi()` | `raspberry_pi_optimizer.py` + `container_builder.py` | Maintainability — shared util needed |
| `_execute_irrigation` log creation | 4× copy-pasted 15-parameter repo call in `irrigation_workflow_service.py` | ✅ Fixed — extracted `_log_execution_result()` |
| Metric note building | 4× in `irrigation_predictor.py` gate-block handlers | Minor DRY violation |

### 5.3 Interfaces & Abstractions

| Pattern | Assessment |
|---------|------------|
| Repository interfaces | ⚠️ No abstract base classes — repos are concrete classes. Testability relies on DI, not interfaces. |
| `IDataProcessor` pipeline | ✅ Clean interface with `CompositeProcessor`, `PriorityProcessor` implementations. |
| Service protocols | ~~⚠️ None defined.~~ ✅ `PlantStateReader` Protocol defined in `app/services/protocols.py`. Used by `GrowthService`. |

---

## 6. Specific Bugs Found

| # | Bug | File | Severity | Status |
|---|-----|------|----------|--------|
| 1 | **Lux features always zero** — `for candidate in (SensorField.LUX.value)` iterates chars of `"lux"` | feature_engineering.py:908 | 🔴 CRITICAL | ✅ Fixed |
| 2 | **~350 lines dead code** — unreachable Bayesian fallbacks after `return` | irrigation_predictor.py | 🟠 HIGH | ✅ Fixed |
| 3 | **Timezone mismatch** — `datetime.now()` vs UTC timestamps | irrigation_predictor.py | 🟡 MEDIUM | ✅ Fixed |
| 4 | **Missing `stratify=y`** in `train_test_split` for 24-class timing model | ml_trainer.py | 🟡 MEDIUM | ✅ Already present |
| 5 | **Unbounded `_alerts` dict** — no eviction strategy | alert_service.py | 🟡 MEDIUM | ✅ Fixed |

---

## 7. Prioritized Recommendations

### Immediate (This Sprint)

| # | Action | Effort | Impact |
|---|--------|--------|--------|
| 1 | ~~Fix lux feature extraction bug~~ | S | ✅ Done |
| 2 | ~~Remove dead code in IrrigationPredictor~~ | S | ✅ Done |
| 3 | ~~Fix timezone bug in `predict_next_irrigation_time`~~ | S | ✅ Done |
| 4 | ~~Extract `_log_execution_result()` helper in `IrrigationWorkflowService`~~ | S | ✅ Done — CC 36→26 |
| 5 | ~~Add eviction (LRU/TTL) to `AlertService._alerts` dict~~ | S | ✅ Done — bounded OrderedDict, maxsize 2048 |

### Near-Term (Next 2 Sprints)

| # | Action | Effort | Impact |
|---|--------|--------|--------|
| 6 | ~~Refactor `AlertService.create_alert` — single-layer dedup with proper error boundaries~~ | M | ✅ Done — CC 71→19 |
| 7 | ~~Extract enriched history builder from `get_enriched_sensor_history`~~ | M | ✅ Done — CC 64→~15 per method. Extracted `_normalize_chart_timestamps`, `_resolve_photoperiod_config`, `_compute_photoperiod`, `_apply_temperature_dif` |
| 8 | ~~Split `PlantViewService` into focused services~~ | M | ✅ Done — Extracted `PlantDeviceLinker` (sensor/actuator linking, 11 methods) + `PlantStageManager` (stage transitions, condition profiles, threshold proposals). `PlantViewService` is now a thin façade. |
| 9 | ~~Move raw SQL from services into repository/ops layer~~ | M | ✅ Done — `AuthRepository` (14 methods), `get_plant_energy_summary` ops, `get_moisture_history` repo |
| 10 | ~~Add `stratify=y` to timing model `train_test_split`~~ | S | ✅ Already present in code |

### Long-Term (Backlog)

| # | Action | Effort | Impact |
|---|--------|--------|--------|
| 11 | Split `AnalyticsService` into bounded-context services | L | Maintainability |
| 12 | Split `IrrigationPredictor` into per-model predictor classes | L | Testability, SRP |
| 13 | Define repository interfaces (ABCs) for testability | M | Architecture |
| 14 | ~~Define service protocols (`PlantStateReader`, `AlertCreator`)~~ | M | ✅ Done — `PlantStateReader` Protocol created in `app/services/protocols.py` (5 read-only methods). `GrowthService` constructor typed with `PlantStateReader` instead of `Any`. |
| 15 | ~~Replace `Any` escape hatches in container with forward refs~~ | S | ✅ Done — 3 `Optional[object]` fields in `ServiceContainer` replaced with proper `TYPE_CHECKING` imports (`ContinuousMonitoringService`, `PersonalizedLearningService`, `TrainingDataCollector`). |
| 16 | ~~Add batch `get_sensors_health()` to eliminate N+1 queries~~ | M | ✅ Done — Added `get_latest_health_batch(sensor_ids)` to ops/repository layer. Refactored `check_all_devices_health_and_alert` to pre-fetch live + DB health in bulk. Extracted `_resolve_health_for_check`, `_normalize_raw_health`, `_check_sensor_offline` helpers. |
| 17 | ~~Drive `_generate_recommendations` thresholds from config table~~ | M | ✅ Done — Extracted 18 magic numbers into `RECOMMENDATION_THRESHOLDS` class-level dict. `_generate_recommendations` and `_determine_nutrient_status` now use `self.RECOMMENDATION_THRESHOLDS`. |

---

## 8. Files Modified in This Audit

| File | Change |
|------|--------|
| [feature_engineering.py](app/services/ai/feature_engineering.py) | 🔴 **Bug fix:** lux tuple iteration — added trailing comma + light aliases |
| [irrigation_predictor.py](app/services/ai/irrigation_predictor.py) | **Dead code removal:** ~350 lines unreachable fallback. **Bug fix:** 3× `datetime.now()` → `utc_now()`. **Raw SQL migrated:** moisture history query → `IrrigationMLRepository.get_moisture_history()` |
| [harvest_service.py](app/services/application/harvest_service.py) | **Housekeeping:** `# nosec B608`. **Refactor:** delegates plant cleanup to `PlantRepository`. **Raw SQL migrated:** `_get_energy_summary` → `analytics_repo.get_plant_energy_summary()` |
| [irrigation_workflow_service.py](app/services/application/irrigation_workflow_service.py) | **Refactor:** extracted `_log_execution_result()`, eliminated 5× copy-pasted 15-param calls. CC 36→26 |
| [alert_service.py](app/services/application/alert_service.py) | **Refactor:** extracted `_try_deduplicate()` + 3 helpers. CC 71→19. Added bounded `OrderedDict` eviction. |
| [auth_service.py](app/services/application/auth_service.py) | **Raw SQL migrated:** all 12 `UserAuthManager` methods delegate to `AuthRepository` (with raw SQL fallback) |
| [analytics_service.py](app/services/application/analytics_service.py) | **Refactor:** extracted 4 helpers from `get_enriched_sensor_history` — CC 64→~15 per method |
| [plants.py](infrastructure/database/repositories/plants.py) | **New method:** `cleanup_plant_data()` — plant harvest cleanup SQL moved here from service layer |
| [auth.py](infrastructure/database/repositories/auth.py) | **New file:** `AuthRepository` — 14 methods covering user lookup, password reset tokens, recovery codes |
| [irrigation_ml.py](infrastructure/database/repositories/irrigation_ml.py) | **New method:** `get_moisture_history()` — moisture readings query moved from predictor |
| [analytics.py (ops)](infrastructure/database/ops/analytics.py) | **New method:** `get_plant_energy_summary()` — fixes dangling delegation from `AnalyticsRepository` |
| [container_builder.py](app/services/container_builder.py) | **Wiring:** pass `plant_repo` to `HarvestService`, pass `auth_repo=AuthRepository(...)` to `UserAuthManager` |
| [test_ml_phase3_features.py](tests/test_ml_phase3_features.py) | **Test update:** 4 tests updated to mock `get_moisture_history()` instead of raw DB access |
| [plant_device_linker.py](app/services/application/plant_device_linker.py) | **New file:** `PlantDeviceLinker` — 11 sensor/actuator linking methods + helpers extracted from PlantViewService (#8) |
| [plant_stage_manager.py](app/services/application/plant_stage_manager.py) | **New file:** `PlantStageManager` — stage transitions, condition profiles, threshold proposals extracted from PlantViewService (#8) |
| [plant_service.py](app/services/application/plant_service.py) | **Refactor:** 20+ methods converted to thin delegation wrappers to PlantDeviceLinker/PlantStageManager (#8) |
| [container.py](app/services/container.py) | **Type safety:** 3 `Optional[object]` fields replaced with proper `TYPE_CHECKING` forward-ref typed fields (#15) |
| [plant_health_scorer.py](app/services/ai/plant_health_scorer.py) | **Refactor:** 18 magic numbers extracted to `RECOMMENDATION_THRESHOLDS` class dict. `_generate_recommendations` + `_determine_nutrient_status` refactored (#17) |
| [device_health_service.py](app/services/application/device_health_service.py) | **Performance:** `check_all_devices_health_and_alert` refactored to batch-fetch health data. Extracted `_resolve_health_for_check`, `_normalize_raw_health`, `_check_sensor_offline` (#16) |
| [devices.py (ops)](infrastructure/database/ops/devices.py) | **New method:** `get_latest_health_batch(sensor_ids)` — single-query batch health history lookup (#16) |
| [devices.py (repo)](infrastructure/database/repositories/devices.py) | **New method:** `get_latest_health_batch()` pass-through to ops layer (#16) |
| [protocols.py](app/services/protocols.py) | **New file:** `PlantStateReader` Protocol — 5 read-only methods for structural subtyping (#14) |
| [growth_service.py](app/services/application/growth_service.py) | **Type safety:** `plant_service` parameter typed as `PlantStateReader` instead of `Any` (#14) |

---

## Appendix A: Full Radon CC Breakdown (C+ Functions)

Total: **1,225 blocks analyzed**, average CC: **B (5.49)**

- F-grade (CC ≥ 41): **5 functions**
- E-grade (CC 31–40): **10 functions**
- D-grade (CC 21–30): **17 functions**
- C-grade (CC 11–20): **78 functions**
- B-grade and below: **1,115 functions** ✅

## Appendix B: Bandit Security Scan

- Total issues: **25** (1 MEDIUM false positive, 24 LOW)
- Zero HIGH or CRITICAL severity findings ✅
- No hardcoded secrets, no command injection, no path traversal
