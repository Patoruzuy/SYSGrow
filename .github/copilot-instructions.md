<!-- Auto-generated guidance for AI coding agents working on SYSGrow -->
# GitHub Copilot Instructions — SYSGrow backend

Purpose: short, actionable guidance so an AI code assistant is immediately productive in this repository.

- **Big picture:** The backend is a modular Flask application. Key layers:
  - **Web / API layer:** [app/blueprints](app/blueprints) + Flask routes. Use `run_server.py` / `smart_agriculture_app.py` to run.
  - **Service layer:** [app/services](app/services) contains business logic (e.g., `GrowthService`, `DeviceService`, `MLService`). Prefer modifying/adding services here rather than placing business logic in controllers.
  - **Domain & models:** [app/models](app/models) and [app/schemas](app/schemas) define persistent state and API payloads.
  - **Infrastructure:** database and device integrations live under [infrastructure](infrastructure) and [app/extensions.py] (shared singletons).

- **Run / dev workflows (exact commands):**
  - Create venv and activate (Windows):
    ```powershell
    python -m venv .venv
    .venv\Scripts\Activate.ps1
    pip install -r requirements-essential.txt
    ```
  - Initialize DB:
    ```powershell
    python -c "from infrastructure.database.sqlite_handler import SQLiteDatabaseHandler; SQLiteDatabaseHandler('sysgrow.db').initialize_database()"
    ```
  - Run dev server (auto-reload): `python start_dev.py`
  - Production: see `deployment/DEPLOYMENT.md` for Docker, Raspberry Pi, and systemd setup.

- **Project conventions & patterns:**
  - Blueprints register routes; control loops under [app/control_loops] handle hardware PID/climate logic.
  - Shared extensions (DB, Cache, SocketIO) are in [app/extensions.py]; import and use those singletons rather than re-creating clients.
  - Configuration is centralized in [app/config.py] and [app/defaults.py]. Environment variables are expected (see `ops.env.example`).
  - ML code and training helpers live in the repo root (`train_sample_models.py`, `data/training`) and inference helpers under [app/services/ai]. See `app/services/ai/plant_health_scorer.py` for an example inference flow.
  - Tests live in `tests/`; run them with the normal pytest workflow inside the activated venv.

- **Integration points & external dependencies:**
  - IoT devices communicate via MQTT/HTTP; device handlers live under [app/hardware] and [integrations].
  - Real-time comms use Socket.IO: see [app/socketio] and [app/extensions.py] for initialization.
  - SQLite is the default local DB (infrastructure/database). For production deployments, confirm the DB adapter/config in [app/config.py].

- **When editing code, prefer:**
  - Adding a new `service` under [app/services] instead of expanding controllers.
  - Registering new endpoints via a blueprint in [app/blueprints] and keeping controllers small (validate -> call service -> return schema).
  - Using schema classes from [app/schemas] for request/response shapes.

- **Examples (patterns to follow):**
  - Add API: create `app/blueprints/my_feature.py` (blueprint), `app/services/my_feature.py` (business logic), and `app/schemas/my_feature.py` (payloads).
  - ML inference: follow `app/services/ai/plant_health_scorer.py`—load model from `data/training` or `models/`, run scorer in a service method, return domain-friendly score objects.

- **Files to read first for context:**
  - `README.md` for setup and high-level architecture
  - `app/extensions.py` for shared singletons
  - `app/config.py` and `ops.env.example` for runtime configuration
  - `app/services` to learn where business logic lives
  - `docs/INDEX.md` and `docs/architecture/ARCHITECTURE.md` for design rationale

- **Files to inspect first when onboarding:**
  - [README.md](README.md) for setup and high-level architecture
  - [app/extensions.py](app/extensions.py) for shared singletons
  - [app/config.py](app/config.py) and [ops.env.example](ops.env.example) for runtime configuration
  - [app/services](app/services) to learn where business logic lives
  - [docs/INDEX.md](docs/INDEX.md) and [docs/architecture/ARCHITECTURE.md](docs/architecture/ARCHITECTURE.md) for design rationale

- **Update documentation as you go**
Especially for new features or architectural changes. The `docs/` folder contains design docs, architecture decisions, and sprint reports that should be updated to reflect any significant changes.

- **What *not* to change without human review:**
  - Database schema migrations and table definitions under `infrastructure/database`.
  - Device protocol handlers and MQTT topics; these are integrated with physical devices.
  - CI/deploy scripts (`Dockerfile`, `docker-compose.yml`, `deployment/`) and systemd service files.

If any of these links point to missing files or you want more depth in a particular area (tests, ML pipeline, infra), tell me which area to expand and I will iterate.
