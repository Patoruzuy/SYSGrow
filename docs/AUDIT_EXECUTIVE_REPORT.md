# SYSGrow Backend — Comprehensive Code Audit: Executive Report

> **Date:** 15 February 2026
> **Scope:** ~400 Python files · ~130K LOC · Flask/Jinja2 · SQLite · Raspberry Pi target
> **Tools used:** radon (CC + MI), pyflakes, bandit, manual review

---

## 1. Executive Summary

The SYSGrow backend is a feature-rich smart-agriculture platform with strong domain
modelling, an excellent event-bus architecture, and well-engineered hardware
extensibility. However, it carries significant technical debt concentrated in
**security**, **test coverage**, **database abstraction**, and **tooling enforcement**.

| Category | Grade | One-Line Verdict |
|----------|:-----:|-----------------|
| 1 · Architectural Review | **C+** | Sound layered design undermined by fat blueprints and god services |
| 2 · Code Quality | **C+** | Healthy average CC but dangerous tail (9 F-grade functions, 13 undefined-name bugs) |
| 3 · Modularity & Abstraction | **C+** | Rich domain & event system; near-zero infrastructure abstraction |
| 4 · Performance & Efficiency | **C** | SQLite memory over-allocation critical on Pi; N+1 queries; zero HTTP compression |
| 5 · Maintainability | **C−** | Good docstrings; catastrophic test gap (48/64 services untested); zero tooling |
| 6 · Security & Best Practices | **D+** | 90% routes unprotected; 125 f-string SQL; 324 raw error leaks |
| 7 · Scalability & Extensibility | **C+** | Excellent EventBus & plugin patterns; no DB abstraction; no API versioning |
| **Composite** | **C** | |

### Strengths (keep & build on)
- **EventBus** — 83 typed event types, 535 usage sites, bounded worker pool
- **Hardware adaptability** — auto-detected Pi3/4/5/Desktop profiles, 7 sensor adapters, 5 relay types, registry/factory pattern
- **Plugin patterns** — 5 registries, ABC-based sensor/actuator/LLM extensibility
- **Consistent API responses** — 1,127 `_success()`/`_fail()` calls, zero raw `jsonify`
- **Lazy ML imports** — 521 deferred heavy-lib imports (numpy, sklearn, pandas)
- **Rate limiting** — configurable, centralised middleware with ML-aware throttle
- **Domain richness** — 15 rich entities vs 7 anemic (B+ ratio)

### Critical Weaknesses (fix first)
- **Authorisation** — 136 write endpoints (OTA update, device restart, plant delete) open to any LAN client
- **SQL injection surface** — 125 f-string SQL queries vs 33 parameterised (3.8 : 1 ratio)
- **Error leakage** — 324 endpoints return raw `str(e)` to clients
- **Test coverage** — 48 of 64 services untested; entire ML layer (20 files) has zero tests
- **Tooling** — zero linters, formatters, type checkers, CI, pre-commit, or lock files
- **Database coupling** — no abstract interface; SQLite hardwired throughout; no connection pool

---

## 2. Codebase Metrics

| Layer | Files | Lines | Role |
|-------|------:|------:|------|
| Services | 64 | 48,015 | Business logic & AI |
| Blueprints | 71 | 26,021 | HTTP/API routes |
| Infrastructure | 65 | 21,284 | Repositories, migrations, DB |
| Hardware | 56 | 10,615 | Physical device drivers |
| Tests | 55 | 8,916 | Test suite |
| Domain | 31 | 5,047 | Domain entities |
| Controllers | 7 | 2,184 | Climate/control loops |
| Schemas | 12 | 2,352 | API payloads |
| **Total** | **~400** | **~130K** | |

---

## 3. Category-by-Category Scorecards

### 3.1 — Architectural Review  (C+)

| Aspect | Grade | Finding |
|--------|:-----:|---------|
| Layered architecture | ✅ A | Blueprints → Services → Repos → SQLite; EventBus for cross-cutting |
| Fat blueprints | 🔴 D | `dashboard.py` CC=115, `predictions.py` 1,642 LOC inline ML |
| Layer violations | ⚠️ C | ~20 direct repo imports from blueprints |
| God services | ⚠️ D | `analytics_service` 2,768, `ml_trainer` 2,490, `irrigation_workflow` 2,167 LOC |
| DI container | B+ | Manual `ServiceContainer` via `ContainerBuilder` (1,179 LOC); clean grouping |
| Controller naming | ✅ | `app/control_loops/` = hardware control loops (renamed from `app/controllers/`) |

### 3.2 — Code Quality  (C+)

| Aspect | Grade | Finding |
|--------|:-----:|---------|
| Cyclomatic Complexity avg | A | 4.39 average across 3,328 blocks |
| CC tail risk | 🔴 D | 59 functions at D+ grade, 9 at F-grade (CC 37–63) |
| Maintainability Index | 🔴 D | 11 files at C-grade (MI < 10); 5 files at MI = 0.00 |
| Undefined name bugs | 🔴 | **13 runtime crash risks** (ml_trainer 5, irrigation __init__ 1, personalized 2, units 1, predictor 1, scheduler_cli 3) |
| Unused imports | ⚠️ | 252 — waste startup time on Pi |
| SOLID principles | C+ | SRP=C, OCP=B, LSP=A, ISP=B, DIP=B |
| Error handling | D+ | 82% broad `except Exception`; only 8 custom exceptions |

### 3.3 — Modularity & Abstraction  (C+)

| Aspect | Grade | Finding |
|--------|:-----:|---------|
| Interface coverage | D | 9 Protocol/ABC for ~400 files |
| Repository abstraction | F | 17 concrete repos, zero `BaseRepository`, no swappability |
| Encapsulation | C+ | AI services 67–83% private; hardware services 0–11% |
| Cross-module coupling | A− | Service sub-packages barely cross-reference; AI fully isolated |
| Domain richness | B+ | 15 rich entities vs 7 anemic |
| Schema adoption | C | ~70% of routes use schemas; dashboard/system bypass them |
| Event system | B | Well-typed enums, 83 event types; underused outside hardware |

### 3.4 — Performance & Efficiency  (C)

| Aspect | Grade | Finding |
|--------|:-----:|---------|
| SQLite memory | 🔴 F | 320 MB hardcoded (cache 64 MB + mmap 256 MB) = 32% of Pi's 1 GB |
| N+1 queries | D | 25 instances, zero batch repo methods, only 2 `executemany` |
| Caching | C+ | Good TTLCache design but only 6/56 services use it |
| ML imports | A | 521 lazy imports — excellent for Pi startup |
| SQLite tuning | A− | WAL mode, NORMAL sync, thread-local connections |
| HTTP optimisation | F | Zero compression, ETags, or Cache-Control headers |
| Pagination | C | ~7 routes paginated; ~13 `get_all_*` routes unbounded |
| Thread safety | C+ | Global locks in growth/irrigation could block all units |
| Rate limiting | A | Configurable, centralised, ML-aware throttle |
| Background tasks | A− | 15 tasks, well-distributed intervals (30s–daily) |

### 3.5 — Maintainability  (C−)

| Aspect | Grade | Finding |
|--------|:-----:|---------|
| Docstring coverage | B | Services 89%, Infra 73%; 7 large functions (621 LOC) undocumented |
| Test coverage | 🔴 D | 48/64 services untested; entire ML layer (20 files) zero tests; no conftest.py |
| Type annotations | B− | Services 88% return types; blueprints **4%**; no mypy/pyright |
| Naming consistency | B− | AI vs. application naming split; 36× `to_dict` duplicates |
| Logging hygiene | D+ | 64% eager f-string anti-pattern (1,379); 89 `print()` calls |
| Documentation health | C− | 84 docs but 17 stale; no CHANGELOG.md; zero deprecation lifecycle |
| Constants/magic numbers | D | 463-line constants file used by 5/59 services |
| Maintainability Index | D | 11 files MI < 10; 5 at MI = 0.00 |
| Error handling | D+ | 82% broad except; 8 custom exceptions for 130K LOC |
| Tooling & enforcement | 🔴 F | Zero linters, formatters, type checkers, CI, pre-commit, lock files |

### 3.6 — Security & Best Practices  (D+)

| Aspect | Grade | Finding |
|--------|:-----:|---------|
| Bandit findings | C+ | 71 findings; 2 HIGH (deprecated pyCrypto imports) |
| Cryptography | D | AES-CBC unauthenticated, 128-bit, hardcoded fallback key |
| Auth & sessions | B− | bcrypt ✅, session fixation ✅; no brute-force protection, no Secure flag |
| SQL injection | D+ | 125 f-string SQL vs 33 parameterised (3.8 : 1) |
| Authorisation | 🔴 F | 384/428 routes (90%) unprotected; 136 write endpoints open |
| CSRF | D | Middleware exists but exempts every API blueprint |
| Error leakage | D | 324 endpoints return raw `str(e)` to clients |
| Input validation | D+ | ~25% schema coverage; 17 uncaught `int()` casts |
| HTTP headers | F | Zero security response headers |
| Deserialization | C | `joblib.load` without integrity checks; local-only mitigates |
| Infrastructure | C− | MQTT plaintext, SocketIO unauthed, CORS `*`, no upload limits |

### 3.7 — Scalability & Extensibility  (C+)

| Aspect | Grade | Finding |
|--------|:-----:|---------|
| Concurrency model | C | Single-process, GIL-bound; Celery migration path documented but unused |
| Database scalability | D+ | No pool, no abstract interface, SQLite-coupled; 73 tables, 2 executemany |
| Event-driven architecture | A− | 83 event types, 535 refs, bounded workers — excellent |
| Plugin/extension patterns | B+ | 5 registries, 7 sensor adapters, 3 LLM backends; manual registration |
| API versioning & docs | F | Only actuator CRUD has `/v2/`; zero OpenAPI/Swagger |
| Config & feature flags | B | 12+ toggles, hardware profiles; 75 hardcoded limits undermine it |
| Horizontal scaling | D | 108 singletons, 71 in-memory dicts, zero external state store |
| Caching architecture | C+ | CacheRegistry for observability; all process-local, manual invalidation |
| Hardware adaptability | A− | Auto-detected profiles, adaptive features, rich driver ecosystem |
| Operational readiness | B− | Health/readiness probes good; zero `signal`/`atexit` shutdown hooks |

---

## 4. Consolidated Risk Matrix

### 🔴 Critical (immediate action)

| # | Issue | Category | Impact | Effort |
|---|-------|----------|--------|--------|
| 1 | **13 undefined-name bugs** — runtime crashes in ml_trainer, irrigation, personalized, units, scheduler_cli | 2 | Runtime crashes | 2 hours |
| 2 | **SQLite 320 MB on 1 GB Pi** — hardcoded cache_size + mmap_size | 4 | OOM risk | Low |
| 3 | **136 unprotected write endpoints** — including OTA update, device restart | 6 | Full system compromise on LAN | 1 day |
| 4 | **324 raw `str(e)` error leaks** — internal paths, SQL, module names to clients | 6 | Information disclosure | 2 days |
| 5 | **Zero tooling enforcement** — no linter, formatter, CI, pre-commit, lock file | 5 | Quality regression | 1 day |

### 🟠 High (next sprint)

| # | Issue | Category | Impact | Effort |
|---|-------|----------|--------|--------|
| 6 | **125 f-string SQL** vs 33 parameterised (3.8 : 1) | 6 | SQL injection surface | 3 days |
| 7 | **48/64 services untested**; entire ML layer zero tests | 5 | Silent regression | 2 weeks |
| 8 | **Zero HTTP security headers** (X-Frame, CSP, HSTS, nosniff) | 6 | Browser-level attacks | 2 hours |
| 9 | **25 N+1 query patterns**, zero batch repo methods | 4 | DB contention | Medium |
| 10 | **Fat blueprints** — dashboard.py CC=115, predictions.py 1,642 LOC | 1 | Unmaintainable | 2–3 days each |
| 11 | **God services** — analytics 2,768, ml_trainer 2,490, irrigation_workflow 2,167 | 1, 3 | SRP violation | 3–5 days |
| 12 | **Zero HTTP compression** — no gzip/brotli on Pi WiFi | 4 | 60–80% wasted bandwidth | 15 min |
| 13 | **Zero API documentation** — no OpenAPI/Swagger for 428 routes | 7 | Frontend guesses | Medium |

### 🟡 Medium (planned work)

| # | Issue | Category | Impact | Effort |
|---|-------|----------|--------|--------|
| 14 | 252 unused imports — slow Pi startup | 2 | Performance | 15 min |
| 15 | 1,379 f-string logging (64% eager anti-pattern) | 5 | CPU waste on Pi | 2 days |
| 16 | 17 repos with no `BaseRepository` — zero DB swappability | 3 | Vendor lock-in | Medium |
| 17 | Login brute-force protection missing | 6 | Account compromise | 4 hours |
| 18 | CSRF exempts all API blueprints | 6 | CSRF on LAN | Medium |
| 19 | Add TTLCache to threshold/plant/device_health services | 4 | Hot-path latency | Low |
| 20 | AES-CBC unauthenticated, 128-bit, hardcoded fallback key | 6 | Crypto weakness | 1 day |
| 21 | `SensorReadingSummary` table written but never read | 4 | Wasted I/O | Low |
| 22 | 75 hardcoded limits/timeouts vs 1 configurable | 7 | Operational inflexibility | Medium |
| 23 | ~20 layer violations (blueprints → repos) | 1 | Tight coupling | 1 day |
| 24 | 82% broad `except Exception`; only 8 custom exceptions | 2, 5 | Poor error routing | 2 days |
| 25 | No signal/atexit handlers for clean shutdown | 7 | Container/systemd deploy | Low |

### 🟢 Low (tech-debt backlog)

| # | Issue | Category | Impact | Effort |
|---|-------|----------|--------|--------|
| 26 | 89 `print()` calls in production code | 5 | Log hygiene | 1 hour |
| 27 | Type annotation style split (50/50 old/new) | 5 | Inconsistency | 1 day |
| 28 | Blueprint return types at 4% | 5 | Refactoring blind spots | Medium |
| 29 | Rename `controllers/` → `control_loops/` | 1 | Onboarding clarity | 30 min |
| 30 | 17 stale doc files referencing deleted modules | 5 | Documentation trust | 1 day |
| 31 | Domain→service violation (irrigation_calculator → PlantViewService) | 3 | Bidirectional dependency | Low |
| 32 | `__init__.py` barrel exports 82 AI symbols | 3 | Coupling fan-out | Low |
| 33 | Add plugin auto-discovery (importlib/entry_points) | 7 | Third-party extensions | Medium |
| 34 | Document singletons holding mutable state (108 instances) | 7 | Scale-out planning | Low |
| 35 | API version prefix (`/api/v1/`) for all 26 blueprints | 7 | Future versioning | Low |

---

## 5. Recommended Fix Order (Sprint Plan)

### Sprint 0 — "Stop the Bleeding" (1–2 days)

| Task | Ref # | Effort |
|------|:-----:|--------|
| Fix 13 undefined-name bugs | 1 | 2 hours |
| Add `ruff` config + `pre-commit` hooks | 5 | 2 hours |
| Add security response headers middleware | 8 | 2 hours |
| Add `Flask-Compress` for gzip | 12 | 15 min |
| Remove 252 unused imports (`ruff --fix`) | 14 | 15 min |
| Make SQLite cache_size/mmap_size configurable (Pi defaults) | 2 | 1 hour |
| Use `hmac.compare_digest` for CSRF comparison | — | 15 min |
| Pin dependencies + add lock file | — | 1 hour |
| **Total** | | **~1 day** |

### Sprint 1 — "Secure the Perimeter" (3–5 days)

| Task | Ref # | Effort |
|------|:-----:|--------|
| Decide auth strategy & protect write endpoints | 3 | 1 day |
| Replace `_fail(str(e))` with generic messages | 4 | 2 days |
| Add login rate limiting + account lockout | 17 | 4 hours |
| Add `MAX_CONTENT_LENGTH` | — | 15 min |
| Upgrade AES to AES-GCM 256-bit, remove fallback key | 20 | 4 hours |
| **Total** | | **~4 days** |

### Sprint 2 — "Query Discipline" (3–5 days)

| Task | Ref # | Effort |
|------|:-----:|--------|
| Migrate top-25 f-string SQL → parameterised queries | 6 | 3 days |
| Add batch repo methods (executemany) for top-5 N+1 patterns | 9 | 2 days |
| Wire/remove SensorReadingSummary reads | 21 | 2 hours |
| **Total** | | **~5 days** |

### Sprint 3 — "Test Foundation" (1–2 weeks)

| Task | Ref # | Effort |
|------|:-----:|--------|
| Create shared `conftest.py` with DB, service, and mock fixtures | 7 | 1 day |
| Add tests for top-5 god services | 7 | 3 days |
| Add tests for ML layer (at least integration/smoke) | 7 | 3 days |
| Add tests for hardware services | 7 | 2 days |
| Wire `ruff` + `pytest` into CI pipeline | 5 | 1 day |
| **Total** | | **~10 days** |

### Sprint 4 — "Architecture Cleanup" (1–2 weeks)

| Task | Ref # | Effort |
|------|:-----:|--------|
| Extract `dashboard.py` logic → `DashboardService` | 10 | 2 days |
| Extract `predictions.py` logic → service methods | 10 | 2 days |
| Split `AnalyticsService` (2,768 LOC) | 11 | 3 days |
| Split `IrrigationWorkflowService` (2,167 LOC) | 11 | 2 days |
| Remove ~20 layer violations (blueprint → repo imports) | 23 | 1 day |
| **Total** | | **~10 days** |

### Sprint 5 — "Extensibility & Observability" (1 week)

| Task | Ref # | Effort |
|------|:-----:|--------|
| Create `BaseRepository(Protocol)` + refactor 17 repos | 16 | 3 days |
| Add OpenAPI/Swagger (flask-smorest or apispec) | 13 | 2 days |
| Add API version prefix `/api/v1/` | 35 | 1 day |
| Register `signal`/`atexit` shutdown handlers | 25 | 2 hours |
| Externalize 75 hardcoded limits to AppConfig | 22 | 2 days |
| **Total** | | **~8 days** |

### Ongoing / Tech-Debt Backlog

| Task | Ref # |
|------|:-----:|
| Convert 1,379 f-string logs → lazy `%` format | 15 |
| Narrow 82% broad `except Exception` handlers | 24 |
| Add TTLCache to hot-path services | 19 |
| Increase encapsulation of hardware services | — |
| Blueprint return-type annotations | 28 |
| Purge 17 stale doc files + add CHANGELOG.md | 30 |
| Rename `controllers/` → `control_loops/` | 29 |
| Templates scan — audit all Jinja2 templates for consistency, dead references, accessibility | — |

---

## 6. Metric Targets

| Metric | Current | Sprint 0 Target | Sprint 5 Target |
|--------|---------|----------------|-----------------|
| Undefined-name bugs | 13 | **0** | 0 |
| Unused imports | 252 | **0** | 0 |
| Unprotected write endpoints | 136 | 136 | **< 10** |
| F-string SQL queries | 125 | 125 | **< 10** |
| `str(e)` error leaks | 324 | 324 | **0** |
| Test coverage (services) | 25% | 25% | **> 70%** |
| Security headers | 0/6 | **6/6** | 6/6 |
| HTTP compression | ❌ | **✅** | ✅ |
| SQLite memory (Pi) | 320 MB | **~40 MB** | ~40 MB |
| Linter/CI enforcement | ❌ | **✅** | ✅ |
| OpenAPI documentation | ❌ | ❌ | **✅** |
| API versioning | 1/26 blueprints | 1/26 | **26/26** |

---

## 7. Architecture Diagram (Current State)

```
┌─────────────────────────────────────────────────────────┐
│                    Flask Application                     │
├──────────────────┬──────────────────────────────────────┤
│   Middleware      │  Rate Limit · CSRF · Health · CORS   │
├──────────────────┼──────────────────────────────────────┤
│   Blueprints     │  26 blueprints · 428 routes           │
│   (HTTP layer)   │  ⚠️ Fat: dashboard, predictions       │
│                  │  ⚠️ 20 direct repo imports             │
├──────────────────┼──────────────────────────────────────┤
│   ServiceContainer (53 fields, ContainerBuilder 1179L)   │
├──────────┬───────┼──────────┬───────────┬──────────────┤
│ Services │  AI   │ Hardware │  Infra    │  Domain      │
│ 64 files │20 file│ 56 files │ 65 files  │  31 files    │
│ 48K LOC  │15K LOC│ 10K LOC  │ 21K LOC   │  5K LOC      │
├──────────┴───────┴──────────┴───────────┴──────────────┤
│   EventBus (83 types · 535 refs) ←→ SocketIO            │
├─────────────────────────────────────────────────────────┤
│   SQLite (WAL · 73 tables · 28 migrations)               │
│   ⚠️ No abstract interface · No pool · Thread-local      │
└─────────────────────────────────────────────────────────┘
     ↕ MQTT/GPIO/Modbus/Zigbee         ↕ HTTP/WS
┌─────────────────────┐    ┌─────────────────────────────┐
│  Hardware Devices    │    │  Web Frontend / Mobile       │
│  ESP32 · Sensors     │    │  (Jinja2 templates)          │
│  Actuators · Relays  │    │                              │
└─────────────────────┘    └─────────────────────────────┘
```

---

*End of audit. Begin Sprint 0 when ready.*
