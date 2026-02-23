<div align="center">

# 🌱 SYSGrow

**Intelligent IoT agriculture platform for monitoring, automating, and optimising plant growth environments.**

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)](https://www.python.org)
[![Flask](https://img.shields.io/badge/Flask-3.x-000000?logo=flask)](https://flask.palletsprojects.com)
[![License: MIT](https://img.shields.io/badge/license-MIT-yellow.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-416%20passed-brightgreen)](#testing)
[![Code style: Ruff](https://img.shields.io/badge/code%20style-ruff-261230.svg)](https://docs.astral.sh/ruff/)
[![SQLite](https://img.shields.io/badge/database-SQLite%20WAL-003B57?logo=sqlite)](https://sqlite.org)
[![Socket.IO](https://img.shields.io/badge/realtime-Socket.IO-010101?logo=socketdotio)](https://socket.io)
[![ESP32](https://img.shields.io/badge/hardware-ESP32--C3%2FC6-E7352C?logo=espressif)](https://www.espressif.com)

[Quick Start](#quick-start) · [Features](#features) · [Architecture](#architecture) · [Documentation](docs/INDEX.md) · [Contributing](#contributing)

</div>

---

## Overview

SYSGrow is a modular Flask backend that turns a Raspberry Pi (or any Python host) into a full-featured smart agriculture controller. It connects to ESP32-based sensors and actuators, collects environmental data, runs ML models for predictive insights, and exposes both a web UI and a REST/WebSocket API.

**Key highlights:**

- **Multi-unit management** — run several independent growing spaces from one instance.
- **15+ ML models** — irrigation prediction, disease detection, climate optimisation, Bayesian threshold learning.
- **LLM integration** — natural-language plant advice via ChatGPT, Claude, or local models.
- **Real-time dashboards** — live sensor data, energy profiling, and device health via Socket.IO.
- **Automated device scheduling** — time-based relay/pump/light control with midnight-crossing support.
- **Extensive hardware support** — WiFi, ZigBee, BLE, MQTT, OTA firmware updates.

---

## Quick Start

> **Prerequisites:** Python 3.11+, Git, SQLite 3 (bundled with Python).

```bash
# 1. Clone
git clone https://github.com/Patoruzuy/SYSGrow.git
cd SYSGrow

# 2. Virtual environment
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux / macOS
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements-essential.txt

# 4. Initialise database
python -c "from infrastructure.database.sqlite_handler import SQLiteDatabaseHandler; \
           SQLiteDatabaseHandler('sysgrow.db').initialize_database()"

# 5. Run
python start_dev.py
```

Open **http://localhost:5000** — the web interface and API docs at `/api/docs` are ready.

For detailed setup (Windows tips, production deployment, Docker, Raspberry Pi) see the **[Installation Guide](docs/setup/INSTALLATION_GUIDE.md)**.

---

## Features

### 🌿 Growth Management
Multi-unit support · 500+ plant profiles · growth-stage tracking · custom grow cycles · harvest logging · condition profiles.

### 🔌 Device & IoT Control
ESP32-C3/C6 integration · relay scheduling with midnight crossing · sensor calibration · OTA firmware updates · WiFi / ZigBee / BLE / MQTT protocols.

### 🧠 AI & Machine Learning
Irrigation predictor (4 models) · disease detection (RandomForest) · climate optimiser · Bayesian threshold learning · continuous monitoring pipeline · automated retraining & drift detection · A/B testing · personalised learning profiles.

### 💬 LLM Advisor
ChatGPT, Claude, or local model integration for natural-language plant care advice, diagnosis, and growth recommendations.

### 📊 Analytics & Monitoring
Real-time dashboards · historical data & trends · energy consumption profiling · anomaly detection with persistence · camera integration (ESP32-CAM, USB).

### 🔒 Security
CSRF protection · session-based auth · encrypted credentials · login-required routes.

> **Deep dives:** each feature area has dedicated documentation under [`docs/`](docs/INDEX.md).

---

## Architecture

```
                    ┌──────────────────────────────────┐
                    │         Web / API Layer           │
                    │  Flask Blueprints · Socket.IO     │
                    └──────────────┬───────────────────┘
                                   │
                    ┌──────────────┴───────────────────┐
                    │         Service Layer             │
                    │  GrowthService · PlantService     │
                    │  DeviceService · MLService        │
                    │  IrrigationPredictor · LLM …      │
                    └──────────────┬───────────────────┘
                                   │
          ┌────────────────────────┼────────────────────────┐
          │                        │                        │
┌─────────┴─────────┐  ┌──────────┴──────────┐  ┌──────────┴──────────┐
│    Database        │  │    Event Bus        │  │    MQTT / IoT       │
│  SQLite (WAL)      │  │  In-process pub/sub │  │  ESP32 devices      │
│  Repositories      │  │  Activity Logger    │  │  ZigBee sensors     │
└────────────────────┘  └─────────────────────┘  └─────────────────────┘
```

| Layer | Responsibilities |
|-------|-----------------|
| **Blueprints** | HTTP routes, request validation, response formatting |
| **Services** | Business logic, orchestration, ML inference |
| **Repositories** | Data access — all SQL lives here, never in controllers |
| **Infrastructure** | Database migrations, MQTT transport, hardware drivers |

> Full architecture docs: **[docs/architecture/ARCHITECTURE.md](docs/architecture/ARCHITECTURE.md)**

---

## Technology Stack

| Category | Technologies |
|----------|-------------|
| **Runtime** | Python 3.11–3.13, Flask 3.x, Gunicorn |
| **Database** | SQLite 3 (WAL mode), migration-managed schema |
| **Real-time** | Flask-SocketIO, WebSockets |
| **IoT** | MQTT (paho), ESP32-C3/C6, ZigBee, BLE |
| **ML / AI** | scikit-learn, NumPy, pandas, joblib |
| **LLM** | OpenAI API, Anthropic API, local model support |
| **Testing** | pytest (416 tests), coverage |
| **Deployment** | Docker, systemd, Nginx reverse proxy |

---

## Project Layout

```
backend/
├── app/
│   ├── blueprints/       # API & UI route definitions
│   ├── services/         # Business logic (application, hardware, AI)
│   ├── domain/           # Domain models & entities
│   ├── schemas/          # Pydantic request/response schemas
│   ├── enums/            # Shared enumerations
│   ├── hardware/         # Device drivers & sensor factories
│   ├── config.py         # Centralised configuration
│   └── extensions.py     # Shared singletons (DB, cache, SocketIO)
├── infrastructure/
│   └── database/         # SQLite handler, migrations, repositories
├── docs/                 # Full documentation (setup, API, architecture, AI/ML)
├── tests/                # pytest test suite
├── data/                 # Training data, user profiles, plant DB
├── models/               # Serialised ML models & registry
└── templates/            # Jinja2 HTML templates
```

---

## Documentation

All in-depth documentation lives in **[`docs/`](docs/INDEX.md)**:

| Area | Link |
|------|------|
| Installation & setup | [docs/setup/](docs/setup/QUICK_START.md) |
| System architecture | [docs/architecture/](docs/architecture/ARCHITECTURE.md) |
| API reference | [docs/api/](docs/api/API_UPDATES_SUMMARY.md) |
| AI & ML services | [docs/ai_ml/](docs/ai_ml/README.md) |
| Hardware guides | [docs/hardware/](docs/hardware/sensors.md) |
| Development & contributing | [docs/development/](docs/development/SERVICES.md) |
| Persistence strategy | [docs/architecture/PERSISTENCE_STRATEGY.md](docs/architecture/PERSISTENCE_STRATEGY.md) |

---

## Testing

```bash
# Run all tests
pytest

# With coverage
pytest --cov=app --cov-report=html

# Single file
pytest tests/test_growth_service.py -v
```

Current baseline: **416 passed · 3 skipped**.

---

## Deployment

SYSGrow supports multiple deployment strategies:

```bash
# Development (auto-reload)
python start_dev.py

# Production — Gunicorn
gunicorn -w 4 -b 0.0.0.0:8000 smart_agriculture_app:app

# Docker
docker build -t sysgrow .
docker run -d -p 5000:5000 sysgrow
```

For systemd, Nginx, and Raspberry Pi deployment see **[deployment/DEPLOYMENT.md](deployment/DEPLOYMENT.md)**.

---

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Write tests and update documentation
4. Run `pytest` — all tests must pass
5. Open a Pull Request

### Conventions

- **Style:** PEP 8, type hints on all public signatures, docstrings on public methods.
- **Commits:** `type(scope): subject` — types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`.
- **Architecture:** business logic in services (`app/services/`), not in blueprints; SQL in repositories, not in controllers.

---

## Roadmap

| Version | Highlights |
|---------|-----------|
| **v3.0** ✅ | 15+ ML models, LLM integration, energy monitoring, ESP32-C3/C6, anomaly persistence |
| **v3.1** 🔧 | Weather API integration, cloud backup, multi-user roles, enhanced camera (time-lapse) |
| **v3.2** 📋 | Voice assistant integration, community plant profiles, LSTM predictions |

---

## License

Released under the [MIT License](LICENSE).

---

<div align="center">

**Made with 💚 for smart agriculture**

[Documentation](docs/INDEX.md) · [Issues](https://github.com/patoruzuy/SYSGrow/issues) · [Contact](mailto:patoruzuy@tutanota.com)

</div>
