# SYSGrow — Backlog

> Living document. Items are grouped by track and roughly ordered by priority within each group.
> Current version: **v3.0.0** · Date: February 2026

---

## 🔴 Security (Critical)

| # | Item | Context | Effort |
|---|------|---------|--------|
| S-1 | **Enforce authentication on write endpoints** | Audit found 136 write endpoints (OTA update, device restart, plant delete, etc.) open to any LAN client. Progressive rollout: start with destructive endpoints, then actuator control, then read routes. | L |
| S-2 | **Eliminate f-string SQL queries** | 125 f-string SQL queries vs 33 parameterised — 3.8:1 risk ratio. Replace all with `?`-parameterised `execute()` calls. | M |
| S-3 | **Stop leaking exception strings to clients** | 324 endpoints return `str(e)` directly. Replace with structured error codes; log the real exception server-side. | M |
| S-4 | **Resolve open Bandit medium alerts** | 4 medium findings from `bandit_report.json` remain after the app-level clean. Review and fix or document acceptance. | S |

---

## 🟠 Infrastructure

| # | Item | Context | Effort |
|---|------|---------|--------|
| I-1 | **CI pipeline** | Zero CI currently. Minimum: GitHub Actions — install deps, run pytest, run ruff, run bandit. Gate PRs on red. | M |
| I-2 | **Database abstraction layer** | SQLite hardwired through ~800 direct `conn.execute()` calls. Introduce a `Repository` ABC so a future PostgreSQL adapter is a drop-in. Prerequisite for I-3. | XL |
| I-3 | **Connection pooling / WAL tuning** | SQLite in WAL mode is already enabled but `check_same_thread=False` risks data races. Proper pooling or a dedicated DB thread would be safer at production scale. | M |
| I-4 | **HTTP response compression** | Zero compression currently. Adding `flask-compress` on the API layer is a one-liner and meaningfully reduces payload size for sensor history / ML results. | S |
| I-5 | **Dependency lock file** | No `pip freeze`-style lock. Pin to `requirements.txt` exact versions or migrate to `pyproject.toml` + `pip-compile`. | S |

---

## 🟡 Testing

| # | Item | Context | Effort |
|---|------|---------|--------|
| T-1 | **Cover untested services** | 48 of 64 services had zero test coverage at the time of the Feb 2026 audit. Sprints 4–10 have improved this, but many service files (especially hardware adapters) remain untested. Target: ≥ 80% service coverage. | XL |
| T-2 | **Irrigation ML integration tests** | End-to-end tests that train on synthetic data, verify metrics gating, and assert the full predict → feedback → retrain cycle. | L |
| T-3 | **Hardware simulator for CI** | GPIO, MQTT, and sensor reads currently require real hardware or are skipped. A lightweight simulator fixture would let CI run the full hardware path. | L |
| T-4 | **Property-based tests for ML gating** | Use `hypothesis` to fuzz `_passes_gate()` with random metric dictionaries and verify no exceptions, only boolean results. | S |

---

## 🟢 Features — Roadmap

### v3.1 — Growth Stage Vision

| # | Item | Context | Effort |
|---|------|---------|--------|
| F-1 | **Growth stage CV model** | Image-based plant growth stage detector. Training pipeline already has a `train_growth_stage_model()` stub. Needs: dataset collection tool, MobileNetV2 fine-tune, `GrowthStagePredictor` service, API endpoints. | XL |
| F-2 | **Camera capture → training data** | Integrate the existing camera service with the CV training pipeline so in-unit photos can be labelled and fed into the growth stage model automatically. | L |

### v3.2 — Multi-Unit Coordination

| # | Item | Context | Effort |
|---|------|---------|--------|
| F-3 | **Cross-unit irrigation scheduler** | When multiple units share a water source, concurrent irrigation causes pressure drops. A coordinator that serialises pump activations across units. | L |
| F-4 | **Multi-unit analytics aggregation** | Dashboard view aggregating temperature, humidity, and moisture trends across all units in one chart. | M |

### v3.x — Intelligence Layer

| # | Item | Context | Effort |
|---|------|---------|--------|
| F-5 | **LLM advisor integration** | `app/services/ai/llm_advisor.py` and `llm_backends.py` are in place. Wire into the recommendations UI, add backend selection (Ollama / OpenAI / Claude), add streaming response support. See `docs/ai_ml/LLM_ADVISOR.md`. | L |
| F-6 | **Weather API integration** | Correlate outdoor weather with in-unit climate. Useful for predictive irrigation (rain expected → skip) and seasonal adjustment fine-tuning. OpenWeatherMap or Open-Meteo. | M |
| F-7 | **Cloud backup / sync** | Periodic SQLite WAL checkpoint + database export to S3-compatible storage. Opt-in, configurable retention. | M |

---

## ⚪ Technical Debt (Nice to Have)

| # | Item | Context | Effort |
|---|------|---------|--------|
| D-1 | **Migrate `GrowthService.determine_landing_page` test coverage** | The method was moved from controllers in the v3 architectural cleanup but test coverage for the new location is thin. | S |
| D-2 | **Audit `SocketIO` event names for consistency** | Mix of snake_case and camelCase event names across `app/socketio/`. Standardise to snake_case. | S |
| D-3 | **`enhanced_plant_template.json` → live plant catalog** | `docs/enhanced_plant_template.json` is a reference template. A tooling script that validates `plants_info.json` entries against it would prevent regressions. | S |
| D-4 | **Remove `_SERVER_START_TIME` references in tests** | Some tests still patch the old global. Update to use `SystemHealthService.get_uptime()` mock. | S |

---

## Effort Key

| Symbol | Estimate |
|--------|---------|
| S | < 1 day |
| M | 1–3 days |
| L | 3–7 days |
| XL | 1–3 weeks |
