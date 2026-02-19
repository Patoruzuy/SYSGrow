# Changelog — SYSGrow Backend

All notable changes to the SYSGrow backend are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [Unreleased] — Code Audit & Quality Overhaul (Sprints 0–10)

### Ruff Cleanup & Security Hardening (2026-02-19)

#### Changed
- Completed full repo Ruff cleanup; `python -m ruff check .` now passes with zero findings.
- Standardized exception handling across hardware adapters/services with explicit exception chaining and selective `contextlib.suppress(...)` where intentional.
- Improved callback timeout/error paths in sensor/relay adapters to avoid silent failure patterns while preserving runtime resiliency.
- Refined several worker, schema, and analytics control-flow paths to remove lint-flagged ambiguity and improve maintainability.

#### Fixed
- Removed remaining lint blockers in domain, hardware adapter interfaces, scheduler task closure binding, database analytics ops, and integration/test helper modules.
- Resolved import/style issues that were causing pre-commit hook failures in follow-up commits.

### Remaining Tech-Debt Cleanup (2025-02-19)

#### Added
- `.editorconfig` — enforces consistent whitespace/encoding across editors (Python 4-space, JS/CSS/HTML 2-space, Makefile tabs)
- `.github/workflows/ci.yml` — GitHub Actions CI pipeline (Ruff lint → pytest → Bandit security scan)
- `Makefile` — developer task runner with `lint`, `format`, `check`, `test`, `security`, `run`, `install`, `clean`, `ci` targets
- `PlantDataProvider` / `WateringScheduleProvider` domain Protocols in `irrigation_calculator.py` — domain layer no longer imports service layer classes
- `bulk_update_plant_moisture()` batch method in `infrastructure/database/ops/growth.py` and `repositories/plants.py` — single-transaction multi-plant moisture updates via `executemany`
- TTLCache (15 s, 128 entries) on `DeviceHealthService.get_sensor_health()` — avoids redundant DB/service calls on dashboard polls

#### Changed
- **Per-unit locks in GrowthService**: replaced single global `_runtime_lock` with a lightweight `_registry_lock` (for dict add/remove) plus per-unit `_get_unit_lock(unit_id)` (for per-unit mutations) — eliminates cross-unit contention
- **N+1 moisture fix**: `PlantViewService._handle_soil_moisture_update` now calls `bulk_update_plant_moisture(plant_ids, moisture_level)` instead of looping `update_plant_moisture_by_id` per plant
- **Domain→Service violation**: `IrrigationCalculator` now types its constructor against `PlantDataProvider` Protocol instead of importing `PlantViewService` — clean dependency inversion

### Frontend Consistency & Final Polish (2025-02-19)

#### Changed
- Extracted inline `<style>` blocks from 3 templates (activity.html, notifications.html, system_health.html — 521 lines total) into dedicated CSS files
- Renamed 3 CSS files from snake_case to kebab-case (`ai_insights.css` → `ai-insights.css`, `ml_dashboard.css` → `ml-dashboard.css`, `system_health.css` → `system-health.css`)
- Standardized Jinja2 block names: `extra_css` → `styles`, `extra_js` → `scripts` across 7 templates + base.html
- Added `-> Response` return-type annotations to 425 API blueprint route functions across 62 files
- Added macro imports (`page_header`, `content_card`) to blog.html, blog_post.html, help_article.html

#### Fixed
- Added `aria-label` attributes to search/import inputs in plants_guide.html and settings.html
- Added descriptive `alt` text to blog_post.html hero image

#### Removed
- Deleted orphaned `templates/index.html` (501 lines — index route renders dashboard.html)
- Deleted `static/legacy/` directory (7 unused files)

---

### Logging Hygiene & Dead-Code Cleanup (2025-02-18)

#### Changed
- Converted 1,082 f-string logging calls to lazy `%`-format across the entire codebase (0 remaining)
- Audited all 11 `print()` calls — all confirmed legitimate (CLI scripts, debug utilities)

#### Removed
- Deleted 29 stale files from `docs/legacy/`
- Removed empty `app/controllers/` directory

---

### Blueprint Hardening & Coverage Baseline (2025-02-18)

#### Added
- `@safe_route` decorator applied to all 414 API routes (100% coverage, up from ~200)
- Test coverage tracking configured in `pyproject.toml` (`fail_under=35`, baseline 36.8%)

#### Removed
- Cleaned up 8 legacy template files

---

### Robustness & Error Handling (2025-02-17)

### Added
- **Custom exception hierarchy** (`app/domain/exceptions.py`): `SysGrowError` base
  class with 8 typed subclasses (`ValidationError`, `NotFoundError`,
  `ConflictError`, `ServiceError`, `RepositoryError`, `ExternalServiceError`,
  `DeviceError`, `ConfigurationError`) — each carries an `http_status` attribute.
- **`@safe_route` decorator** (`app/utils/http.py`): Standardised error handling
  for blueprint routes; maps `SysGrowError` to correct HTTP status, catches
  unhandled exceptions with a generic 500 response.
- **Global error handler** (`app/__init__.py`): Enhanced to recognise
  `SysGrowError` and surface 4xx messages to clients while using `safe_error()`
  for 5xx.

### Changed
- **Blueprint routes**: Applied `@safe_route` to 22 routes (10 dashboard,
  12 harvest), eliminating 21 bare `except Exception` blocks.
- **Service exception handling**: Narrowed 93 broad `except Exception` blocks
  to specific exception tuples across 5 top services (`dashboard_service`,
  `growth_service`, `plant_service`, `harvest_service`, `alert_service`).
  21 complex orchestration handlers left with `# TODO(narrow):` for future work.
- **Ad-hoc dict caches → TTLCache**: Converted 6 unbounded dict caches to the
  existing `TTLCache` utility (bounded, auto-expiring, thread-safe):
  - `dashboard_service._ts_cache` (30 s TTL, maxsize 64)
  - `threshold_service._threshold_cache` (300 s, maxsize 256)
  - `threshold_service._unit_threshold_cache` (300 s, maxsize 128)
  - `threshold_service._plant_override_cache` (300 s, maxsize 256)
  - `irrigation_workflow_service._config_cache` (300 s, maxsize 64)
  - `mqtt_sensor_service._friendly_name_cache` (300 s, maxsize 256)

### Removed
- Stale backup files: `analytics_service.py.bak`,
  `irrigation_workflow_service.py.bak`.

---

### Sprint 6 — Code Quality & Hygiene (2025-02-17)

### Changed
- Replaced `print()` calls with `logging` across the codebase.
- Converted eager f-string log messages to lazy `%s`-style formatting.
- Modernised `Optional[X]` annotations to `X | None`.
- Made AI barrel imports (`app/services/ai/__init__.py`) lazy.
- Renamed `app/controllers` → `app/control_loops` to reflect their purpose.

### Removed
- Stale / outdated documentation files.

---

### Sprint 5 — Schema & Payload Hardening (2025-02-16)

### Changed
- Added Pydantic response schemas for key API endpoints.
- Ensured consistent error-response shape across blueprints.

---

### Sprint 4 — Service Layer Refactoring (2025-02-16)

### Changed
- Split `IrrigationWorkflowService` (2,193 lines) into three focused
  sub-services: `IrrigationDetectionService`, `IrrigationExecutionService`,
  `IrrigationFeedbackService`. Original file kept as backward-compatible façade.

---

### Sprint 3 — Test Coverage & Stability (2025-02-15)

### Added
- New unit tests; baseline established at 402 passed / 13 pre-existing failures /
  3 skipped.

---

### Sprint 2 — Configuration Consolidation (2025-02-15)

### Changed
- Centralised configuration into `app/config.py` and `app/defaults.py`.
- Standardised environment variable usage via `ops.env.example`.

---

### Sprint 1 — Blueprint & Route Organisation (2025-02-14)

### Changed
- Organised API endpoints into cohesive blueprints under `app/blueprints/`.

---

### Sprint 0 — Initial Audit & Baseline (2025-02-14)

### Added
- Executive audit report (`docs/AUDIT_EXECUTIVE_REPORT.md`).
- Architecture documentation refresh.
