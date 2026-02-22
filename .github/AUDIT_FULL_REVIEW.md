# Full Code Audit — SYSGrow Backend

**Date:** 2025-01-XX
**Auditor:** Senior Chief Engineer (AI-assisted)
**Scope:** All application code under `app/`, `infrastructure/`, selected helpers
**Tools:** radon (cyclomatic complexity), bandit (security), pytest, manual review

---

## Executive Summary

| Area | Before | After | Status |
|------|--------|-------|--------|
| **Worst CC (dashboard)** | F (115) | D (22) | ✅ Fixed |
| **Bare `except:` clauses** | 12 instances | 0 | ✅ Fixed |
| **HTTP calls without timeout** | 3 endpoints | 0 | ✅ Fixed |
| **Tests** | 4 passed | 4 passed | ✅ Green |
| **Remaining F-grade functions** | 9 across codebase | 8 (dashboard resolved) | ⚠️ Backlog |

---

## 1. Complexity Analysis

### 1.1 Dashboard Refactor (Primary Hotspot)

`app/blueprints/api/dashboard.py` · `get_dashboard_summary` was the single worst function in the codebase at **CC 115 (F-grade)**.

**Extraction summary — 9 helpers created:**

| Helper | CC | Purpose |
|--------|----|---------|
| `_build_snapshot_or_analytics` | D (21) | Analytics/snapshot data delegation |
| `_build_plants_summary` | E (35) | Active plant aggregation |
| `_build_alerts_summary` | B (7) | Alert counts |
| `_build_devices_summary` | B (10) | Sensor/actuator counts |
| `_build_energy_summary` | A (5) | Energy analytics |
| `_build_system_summary` | B (8) | System health + uptime |
| `_build_unit_settings_summary` | D (28) | Unit settings + metric formatting |
| `_build_active_plant_details` | C (12) | Active plant enrichment |
| `_snap_metric_from_metrics` | B (10) | Metric value extraction |

**Result:** `get_dashboard_summary` CC 115 → **22 (D)**. No behaviour change; 4 dashboard tests pass consistently.

### 1.2 Remaining F-Grade Functions (Not Addressed — Backlog)

These remain for future sprints. None are as extreme as the dashboard was:

| File | Function | CC |
|------|----------|----|
| `app/services/alert_service.py` | `AlertService.create_alert` | 71 |
| `app/services/analytics_service.py` | `AnalyticsService.get_enriched_sensor_history` | 64 |
| `app/services/ai/ml_trainer.py` | `FeatureEngineer.create_irrigation_features` | 63 |
| `app/services/application/plant_view_service.py` | `PlantViewService.create_plant` | 54 |
| `app/services/ai/ml_trainer.py` | `EnvironmentalFeatureExtractor.extract_all_features` | 47 |
| `app/blueprints/api/growth/condition_profiles.py` | `get_condition_profile_selector` | 42 |
| `app/blueprints/api/growth/thresholds.py` | `respond_to_threshold_proposal` | 41 |
| `app/services/application/threshold_service.py` | `ThresholdService.get_threshold_ranges` | 41 |

---

## 2. Security Fixes

### 2.1 Bare `except:` → Typed Exception Handlers

**Risk:** Bare `except:` catches `SystemExit`, `KeyboardInterrupt`, and `GeneratorExit`, masking shutdown signals and making debugging harder. Bandit flags this as B001.

**12 instances fixed across 7 files:**

| File | Line(s) | Replacement | Rationale |
|------|---------|-------------|-----------|
| `app/utils/raspberry_pi_optimizer.py` | 134, 290, 311 | `except Exception:` | Hardware-detect fallbacks; only real exceptions should be caught |
| `app/services/container_builder.py` | 1074 | `except Exception:` | Same RPi detection pattern |
| `app/services/application/plant_journal_service.py` | 465, 518 | `except (ValueError, TypeError):` | JSON parse; only those two exceptions are possible |
| `app/services/application/plant_journal_service.py` | 647 | `except Exception:` | Date-diff calculation fallback |
| `app/defaults.py` | 306 | `except Exception:` | I2C bus probe; keep `continue` |
| `app/blueprints/api/plants/crud.py` | 316 | `except (ValueError, IndexError):` | pH range string parsing; precise types |
| `app/blueprints/api/health/units.py` | 68, 170 | `except Exception:` | list_sensors/list_actuators calls |
| `app/blueprints/api/health/devices.py` | 102 | `except Exception:` | Sensor status check |

### 2.2 Missing HTTP Timeouts

**Risk:** `requests.get/post()` without `timeout=` can hang the server thread indefinitely.

| File | Fix |
|------|-----|
| `app/hardware/mqtt/mqtt_fcm_notifier.py` | Added `timeout=5` + `RequestException` handler |
| `app/hardware/devices/camera_manager.py` | Added `timeout=5` + `RequestException` handler (2 call sites) |

**Already safe (no action needed):**
- `sun_times_service.py` → `timeout=10` ✅
- `wifi_adapter.py` → `self.http_timeout` ✅
- `wireless_relay.py`, `wifi_relay.py`, `relay.py` → `timeout=5` ✅

### 2.3 Insecure `random` Usage (Informational — No Fix Needed)

All `random` / `np.random` usage in the codebase is for:
- ML training data augmentation (`ml_trainer.py`) — not security-sensitive
- A/B testing split ratios (`ab_testing.py`) — not cryptographic
- Mock/fallback model metrics (`models.py`, `predictions.py`) — development only

No `random` usage touches authentication tokens, session IDs, or cryptographic keys. **No action required.**

---

## 3. Pre-Existing Changes in Uncommitted Diff

These changes were already present when the audit began (not introduced by this audit). Reviewed for correctness:

### 3.1 Devhost WSGI Middleware (`app/__init__.py`, `app/config.py`, `run_server.py`)
- Adds `devhost_enabled` config flag and `DevhostWSGIMiddleware` wrapping
- `run_server.py` switched from `socketio.run()` to `run_flask()` from `devhost_cli`
- **Assessment:** Clean integration; gated behind config flag. ⚠️ Verify `devhost_cli` is in requirements.

### 3.2 Air Quality Threshold Default Fix
- Changed `air_quality_threshold` default from `1000.0` → `100.0` across:
  - `app/domain/environmental_thresholds.py`
  - `app/domain/unit_runtime.py`
  - `infrastructure/database/ops/growth.py`
  - `infrastructure/database/repositories/growth.py`
  - `infrastructure/database/repositories/units.py`
- **Assessment:** Correct. AQI 1000 is nonsensical (EPA scale tops at 500); 100 ("Moderate") is a reasonable default.

### 3.3 Threshold Sanitization (`app/services/application/threshold_service.py`)
- Added `_coerce_threshold()` and `_sanitize_unit_thresholds()` methods
- `get_unit_thresholds()` now catches `ValueError` from `EnvironmentalThresholds.from_dict()` and auto-clamps to valid ranges
- **Assessment:** Defensive and correct. Prevents crash from corrupted DB rows. Auto-persists corrected values.

### 3.4 Condition Profile Fallback (`thresholds.py`, `units.py` blueprints)
- Wraps `growth_service.update_unit_thresholds()` in try/except, falls back to `threshold_service.update_unit_thresholds()`
- **Assessment:** Reasonable resilience pattern. Consider logging the fallback.

### 3.5 SQLite Corruption Handling (`infrastructure/database/sqlite_handler.py`)
- Added `_open_connection()`, `_is_corruption_error()`, `_quarantine_corrupt_db()`
- On corruption, moves DB + WAL/SHM files to `database/corrupt/` with timestamp, then recreates
- **Assessment:** Excellent resilience improvement. Prevents irrecoverable crash from malformed DB. Quarantine preserves evidence for debugging.

### 3.6 Frontend Debug Logging (`static/js/components/plant-details-modal.js`)
- Added `console.log` statements for sensor link debugging
- Added modal header actions container
- **Assessment:** ⚠️ Debug `console.log` calls should be removed or gated before production release.

### 3.7 Growth Repository Param Fix (`infrastructure/database/repositories/growth.py`)
- Changed `aqi_threshold=aqi_threshold` → `air_quality_threshold=aqi_threshold` in the call to `create_unit()`
- **Assessment:** Correct bug fix — the underlying `GrowthOperations.create_unit()` expects `air_quality_threshold`, not `aqi_threshold`.

---

### 3.8 Soil_moisture_threshold should be removed from `GrowthOperations.create_unit()`, unit_runtime.py domain, database schema and other unit related modules.

This threshold is handle by the plants now as a individual plant threshold instead of a unit-wide threshold, so it doesn't make sense to have it in the unit creation flow or schema. Removing it would simplify the code and reduce confusion about where soil moisture thresholds are actually applied.
Climate_optimizer.py should also be reviewed to ensure it's not still referencing soil moisture thresholds at the unit level, and updated accordingly to reflect the new plant-level threshold approach. This would be a good cleanup task to add to the backlog after the immediate complexity and security fixes are addressed.

### 3.9 'climate_optimizer.py' should be reviewed for any remaining references to soil moisture thresholds at the unit level, and updated to reflect the new plant-level threshold approach.

This would be an important step to ensure consistency across the codebase and prevent any confusion about where soil moisture thresholds are applied. Removing any unit-level soil moisture threshold logic from the climate optimizer would align it with the new design and make it clearer that soil moisture thresholds are now a plant-specific concern rather than a unit-wide setting. This review and cleanup could be added to the backlog for future sprints after the immediate complexity and security issues are addressed.

### 3.10 'climate_optimizer.py' should be reviewed because is not aligned with the ML design changes.

The logic is algorihmically rather than ML driven, and  I have update other modules such as 'disease_predictor.py' to reflect the new ML design, so it would be good to review 'climate_optimizer.py' to ensure it's still aligned with the overall ML architecture and design principles. If there are any references to the old ML design or if the logic could be improved by leveraging the new ML components, those should be addressed in this review. This would help ensure that the climate optimizer is consistent with the rest of the codebase and takes advantage of the new ML capabilities where appropriate. Also, I would like to follow the other module principles where notify the user for new climate changes intead be called to predict the climate. Finally, plug it in recommendation_provider.py and personalized_leraning.py This review could also be added to the backlog for future sprints after the immediate complexity and security issues are addressed.

## 4. Recommendations

### Immediate (This Sprint)
1. ~~Fix dashboard CC 115~~ → ✅ Done (CC 22)
2. ~~Fix all bare `except:`~~ → ✅ Done (12/12)
3. ~~Add HTTP timeouts~~ → ✅ Done
4. Remove `console.log` debug statements from `plant-details-modal.js` before merging

### Near-Term (Next 2 Sprints)
5. **Reduce `_build_plants_summary` CC 35** — extract growth-stage resolution into its own helper
6. **Reduce `_build_unit_settings_summary` CC 28** — extract metric-building loops
7. **Tackle `AlertService.create_alert` CC 71** — decompose alert routing logic
8. **Add `devhost-cli`** to `requirements-essential.txt` if not already there
9. Consider adding `# noqa: B001` annotations for any intentional bare-except patterns in hardware code

### Long-Term (Backlog)
10. Address remaining F-grade functions (see §1.2)
11. Add integration tests for dashboard summary endpoint
12. Consider structured logging (`logging.getLogger(__name__)`) in all `print()` call sites
13. The `app/hardware/devices/camera_manager.py` line 125 `requests.get` for camera stream could benefit from a configurable timeout rather than hard-coded 5s

---

## 5. Files Modified in This Audit

| File | Change Type |
|------|-------------|
| `app/blueprints/api/dashboard.py` | Complexity refactor (9 helpers extracted) |
| `app/hardware/mqtt/mqtt_fcm_notifier.py` | Timeout + exception handling |
| `app/hardware/devices/camera_manager.py` | Timeout + exception handling |
| `app/utils/raspberry_pi_optimizer.py` | `except:` → `except Exception:` (×3) |
| `app/services/container_builder.py` | `except:` → `except Exception:` |
| `app/services/application/plant_journal_service.py` | `except:` → typed exceptions (×3) |
| `app/defaults.py` | `except:` → `except Exception:` |
| `app/blueprints/api/plants/crud.py` | `except:` → `except (ValueError, IndexError):` |
| `app/blueprints/api/health/units.py` | `except:` → `except Exception:` (×2) |
| `app/blueprints/api/health/devices.py` | `except:` → `except Exception:` |

---

### 6. Code Maintainability Indicators

- Check code readability and consistency
- Evaluate naming conventions and code documentation
- Assess test coverage and testability of components
- Identify areas with high maintenance complexity

## 7. Audit Artifacts (Can Be Deleted)

These files were generated during automated analysis and can be safely removed:

- `radon_cc_summary.txt` — Full radon CC report
- `radon_top_f.txt` — F-grade function index
- `radon_dashboard.json` — Dashboard CC snapshot
- `bandit_report.json` — Full bandit scan
- `bandit_app_only.json` — App-only bandit scan
- `bandit_app_summary.txt` — Bandit summary
- `scripts/parse_bandit_app.py` — Bandit report parser
