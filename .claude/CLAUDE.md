# CLAUDE.md
# SYSGrow Code Guide for Claude

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

SYSGrow is a lightweight smart agriculture IoT platform optimized for Raspberry Pi, designed for monitoring and automating plant growth environments. It integrates ESP32 devices, sensors, actuators, and machine learning models through a Flask-based web application.

**Critical Context**: This is a **Raspberry Pi-first** application. All architectural decisions prioritize low resource usage, edge computing, and efficient memory management. Future migration to server infrastructure (Redis, PostgreSQL, Celery, React) is planned but NOT the current focus.

**Tech Stack**: Python 3.8+, Flask 3.0, SQLite, SocketIO, MQTT, ESP32 (C3/C6), scikit-learn, Jinja2 templates

**Hardware Constraints**:
- Target: Raspberry Pi 3B+ / 4 (1-4GB RAM)
- SQLite (not PostgreSQL) for minimal overhead
- No heavy caching layers (Redis comes later)
- No async task queues (Celery comes later)
- Minimal JavaScript dependencies

## Quick Reference

**Most Common Commands** (for new developers):

```bash
# 1. Start development server
$env:SYSGROW_ENABLE_MQTT="true" ; python run_server.py
# → Access at http://localhost:5001

# 2. Run all tests
pytest

# 3. Run specific test file
pytest tests/test_api_endpoints.py

# 4. Initialize database
python -c "from infrastructure.database.sqlite_handler import SQLiteDatabaseHandler; SQLiteDatabaseHandler('sysgrow.db').initialize_database()"

# 5. View database schema
sqlite3 sysgrow.db ".schema" | less
```

**Quick Troubleshooting**:
- **MQTT errors?** → Check `mosquitto` is running: `systemctl status mosquitto`
- **Database locked?** → Close all connections and restart server
- **Import errors?** → Install dependencies: `pip install -r requirements-essential.txt` (Windows) or `pip install -r requirements.txt` (Pi/Linux)

---

## Common Development Commands 
### Running the Application

```bash
# Development server with auto-reload (recommended)
$env:SYSGROW_ENABLE_MQTT="true" ; python run_server.py

# Production server (for Pi deployment)
python smart_agriculture_app.py

# Windows quick start
start_server.bat
```

The dev server runs on `http://localhost:5001` by default.

### Testing

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_api_endpoints.py

# Run with verbose output
pytest -v

# Run with coverage
pytest --cov=app --cov-report=html

# Quick smoke tests (for CI/Pi validation)
pytest tests/test_minimal.py tests/test_startup.py
```

**Important**: Tests use `pytest` framework. Never skip or disable tests—fix them instead.

### Database Operations

```bash
# Initialize database from scratch
python -c "from infrastructure.database.sqlite_handler import SQLiteDatabaseHandler; SQLiteDatabaseHandler('sysgrow.db').initialize_database()"

# Run migrations
python infrastructure/database/migrations/run_migration.py

# Verify database schema
python tests/verify_new_schema.py

# Backup database (important on Pi!)
cp sysgrow.db sysgrow.db.backup_$(date +%Y%m%d_%H%M%S)
```

Database file: `sysgrow.db` (SQLite) - uses WAL mode for better concurrency

### ESP32 Firmware

```bash
cd ../ESP32-C6-Firmware
platformio run --target upload
```

## Architecture

### Layered Architecture

```
┌─────────────────────────────────────────┐
│    Flask Blueprints (API + UI Routes)  │
│     app/blueprints/api/*, ui/*          │
└──────────────────┬──────────────────────┘
                   │
┌──────────────────┴──────────────────────┐
│      Application Services Layer         │
│     app/services/application/*          │
│  (GrowthService, PlantService, etc.)    │
└──────────────────┬──────────────────────┘
                   │
┌──────────────────┴──────────────────────┐
│  Domain Models & Hardware Services      │
│    app/domain/*, app/services/          │
│         hardware/*, app/hardware/*      │
└──────────────────┬──────────────────────┘
                   │
┌──────────────────┴──────────────────────┐
│    Infrastructure Layer                 │
│  infrastructure/database/*, hardware/*  │
│   (SQLiteHandler, Repositories, MQTT)   │
└─────────────────────────────────────────┘
```

### Performance Considerations

**Memory Management**:
- SQLite connection pooling limits set in config
- Sensor readings archived/pruned after 30 days by default
- In-memory caches use LRU eviction (max 100 items typical)
- No large dataset loading; always paginate queries
- SocketIO message batching for real-time updates

**CPU Optimization**:
- ML model inference throttled (max 1/min per model)
- Sensor polling intervals configurable (default 60s)
- Background tasks use lightweight threading (not multiprocessing)
- Lazy loading for heavy modules (scikit-learn, etc.)

**I/O Efficiency**:
- SQLite WAL mode for better write concurrency
- MQTT QoS 1 (not 2) for performance/reliability balance
- Static assets served with far-future cache headers
- Minimal logging levels in production (WARNING+)

### Key Components

**Service Container** (`app/services/container.py`):
- Dependency injection container managing all services
- Built once at application startup via `ServiceContainer.build()`
- Access services through `flask_app.config["CONTAINER"]`
- Singleton pattern to avoid duplicate initializations

**Core Services** (`app/services/application/`):
- `GrowthService` - Growth unit management and orchestration
- `PlantService` - Plant profiles and health tracking
- `DeviceCoordinator` - Device management and coordination
- `ThresholdService` - Environmental threshold management
- `SettingsService` - System configuration
- `HarvestService` - Harvest tracking and analytics
- `AnalyticsService` - System analytics and reporting

**Hardware Layer** (`app/hardware/`, `app/services/hardware/`):
- `ActuatorManager` - Controls relays, pumps, fans
- `SensorManagementService` - Sensor polling and readings (throttled)
- `ActuatorManagementService` - Actuator control logic
- `ClimateControlService` - PID-based climate automation
- `MQTTClientWrapper` - MQTT broker communication for ESP32 devices
- `SensorPollingService` - Background sensor data collection

**Infrastructure** (`infrastructure/`):
- `SQLiteDatabaseHandler` - Database connection and operations (with pooling)
- `*Repository` classes - Data access layer (growth, devices, analytics, etc.)
- `AuditLogger` - Audit trail logging (minimal overhead)
- `EventBus` - In-process event system (no external broker)

**Domain Models** (`app/domain/`):
- `SensorEntity`, `ActuatorEntity` - Hardware abstractions
- `SensorReading`, `SensorConfig` - Sensor data structures
- `HealthStatus` - Device health tracking
- `EnvironmentalThresholds` - Threshold configurations

### Entry Points

- `smart_agriculture_app.py` - WSGI entry point (production)
- `start_dev.py` - Development server with hot-reload
- `app/__init__.py:create_app()` - Flask app factory
- `app/services/container.py:ServiceContainer.build()` - Service initialization

## Frontend Architecture

### Template Structure

All templates extend `templates/base.html` which provides the common layout structure.

**Page Wrappers**: Every page must use one of:
- `.dashboard-page` - Dashboard and monitoring pages
- `.units-page` - Growth units and management
- `.status-page` - System status and health
- `.auth-page` - Login and authentication
- `.analytics-page` - Analytics and reporting pages

### CSS Organization

```
static/css/
├── theme.css         # Design tokens (colors, spacing) - AUTHORITATIVE
├── tokens.css        # Layout tokens (sidebar width, etc.)
├── base.css          # Reset, typography, shared components
├── layout.css        # Header, sidebar, footer shell
├── navigation.css    # Navigation components
├── forms.css         # Form elements
├── components.css    # Shared UI components (cards, badges, pills)
├── dashboard.css     # Dashboard-specific styles
├── units.css         # Growth units page
├── analytics.css     # Analytics pages
└── status.css        # Status page styles
```

**CSS Rules**:
- All colors MUST come from `theme.css` CSS variables (`--brand-*`, `--bg-*`, `--text-*`, etc.)
- NO inline styles in templates - use CSS classes only
- Support both light and dark themes via `:root[data-theme="light|dark"]`
- Use shared component classes: `.btn`, `.card`, `.badge`, `.kpi-card`, `.sensor-card`, etc.
- Keep CSS files small and focused; load only what's needed per page

### JavaScript Structure

```
static/js/
├── api.js                     # Centralized API client (all endpoints)
├── base.js                    # Global utilities and SocketIO setup
├── socket.js                  # SocketIO event handlers
├── dashboard/                 # Dashboard module
│   ├── main.js               # Entry point
│   ├── data-service.js       # API communication layer
│   └── ui-manager.js         # UI updates and DOM manipulation
├── devices/                   # Devices module (similar structure)
├── plants/                    # Plants module (similar structure)
├── sensor-analytics/          # Sensor analytics module
│   ├── main.js
│   ├── data-service.js
│   ├── ui-manager.js
│   └── environmental-overview-chart.js
└── utils/                     # Shared utilities
    ├── base-manager.js       # Base class for managers
    ├── cache-service.js      # Client-side caching (localStorage)
    └── modal.js              # Modal utilities
```

**JavaScript Patterns**:
- **No heavy frameworks**: Vanilla JS only (no React, Vue, Angular)
- **Modular structure**: Each page uses `main.js`, `data-service.js`, `ui-manager.js`
- **API client**: Use centralized `api.js` for all backend calls
- **SocketIO for real-time**: Only for sensor updates and alerts
- **Client-side caching**: Minimize API calls with `cache-service.js`
- **Progressive enhancement**: Core functionality works without JS

**Performance Rules**:
- Minimize DOM manipulations (batch updates)
- Use event delegation for dynamic content
- Debounce/throttle expensive operations
- Lazy load charts and heavy components
- Keep bundle sizes small (no Webpack/build step)

## API Structure

All API endpoints are organized under `app/blueprints/api/`:

```
/api/devices/*           # Device management (ESP32, sensors, actuators)
/api/dashboard/*         # Dashboard data aggregation
/api/plants/*            # Plant CRUD and health
/api/growth/*            # Growth units and schedules
/api/settings/*          # System settings
/api/sensors/*           # Sensor readings and configuration
/api/analytics/*         # Analytics, trends, and correlations
/api/health/*            # System and device health
/api/harvest/*           # Harvest tracking
/api/ml_ai/*             # ML models, predictions, training
/api/retraining/*        # Model retraining and drift detection
```

**API Patterns**:
- All endpoints return JSON with consistent structure: `{ok: bool, data: any, error?: {message: str}}`
- Use HTTP status codes correctly (200, 201, 400, 404, 500)
- Pagination for list endpoints: `?limit=X&offset=Y`
- Filtering via query params: `?unit_id=X&sensor_type=Y`
- Date ranges: ISO 8601 format (`?start=2025-01-01T00:00:00Z`)

## Database Schema

SQLite database with 15+ core tables:

**Core Tables**:
- `GrowthUnits` - Growth unit configurations
- `Plants` - Plant instances linked to units
- `Users` - User authentication (bcrypt hashing)
- `Settings` - System configuration key-value store

**Device Tables**:
- `Devices` - Unified IoT device registry
- `Sensors` - Sensor configurations (GPIO, MQTT, ZigBee)
- `Relays` - Actuator configurations
- `SensorReadings` - Time-series sensor data (auto-pruned)
- `DeviceStateHistory` - Actuator state changes

**Analytics Tables**:
- `Analytics` - System-wide analytics cache
- `EnergyConsumption` - Power monitoring (actuator-level)
- `PlantHealthLogs` - Disease/pest detection logs
- `HarvestReports` - Harvest tracking and yield data

**ML Tables**:
- `MLTrainingData` - Training datasets
- `MLModelRegistry` - Model versions and metadata
- `MLDriftDetection` - Model drift monitoring

**Performance Indexes** (defined in schema):
- `SensorReadings`: `(unit_id, timestamp)`, `(sensor_id, timestamp)`
- `DeviceStateHistory`: `(actuator_id, changed_at)`
- `PlantHealthLogs`: `(plant_id, recorded_at)`

Access via repositories in `infrastructure/database/repositories/`.

## Development Patterns

### Adding a New API Endpoint

1. Create route in appropriate blueprint (`app/blueprints/api/`)
2. Access services via `current_app.config["CONTAINER"]`
3. Use repository pattern for database access
4. Return JSON responses with proper status codes
5. Add error handling with descriptive messages
6. **Always paginate** list endpoints (default limit=50, max=500)

Example:
```python
from flask import Blueprint, current_app, jsonify, request

@my_blueprint.route('/my-endpoint', methods=['GET'])
def my_endpoint():
    container = current_app.config["CONTAINER"]
    service = container.my_service
    
    # Pagination
    limit = min(int(request.args.get('limit', 50)), 500)
    offset = int(request.args.get('offset', 0))

    try:
        result = service.get_data(limit=limit, offset=offset)
        return jsonify({
            "ok": True,
            "data": result,
            "pagination": {
                "limit": limit,
                "offset": offset,
                "total": service.count_data()
            }
        }), 200
    except ValueError as e:
        return jsonify({"ok": False, "error": {"message": str(e)}}), 400
    except Exception as e:
        current_app.logger.error(f"Error in my_endpoint: {e}")
        return jsonify({"ok": False, "error": {"message": "Internal server error"}}), 500
```

### Adding a New Service

1. Create service class in `app/services/application/` or `app/services/hardware/`
2. Add to `ServiceContainer` in `app/services/container.py`
3. Initialize in `ServiceContainer.build()` method
4. Inject dependencies via constructor
5. Add type hints for all methods
6. Keep services **stateless** (use database for persistence)
7. **Avoid heavy imports** at module level (lazy load if possible)

Example:
```python
from typing import Optional, List
from infrastructure.database.repositories.my_repo import MyRepository

class MyService:
    """Lightweight service with minimal dependencies."""
    
    def __init__(self, repository: MyRepository):
        self._repo = repository
    
    def get_data(self, limit: int = 50, offset: int = 0) -> List[dict]:
        """Fetch data with pagination."""
        return self._repo.fetch_paginated(limit, offset)
    
    def count_data(self) -> int:
        """Get total count for pagination."""
        return self._repo.count_all()
```

### Working with Hardware

**Sensors**:
- GPIO sensors: `app/hardware/adapters/sensors/gpio_adapter.py`
- MQTT sensors: `app/hardware/adapters/sensors/mqtt_adapter.py`
- ZigBee sensors: `app/hardware/adapters/sensors/zigbee_adapter.py`
- Polling managed by `SensorPollingService` (configurable intervals)

**Actuators**:
- Relay control: `app/hardware/actuators/relays/`
- MQTT actuators: `app/hardware/adapters/actuators/mqtt_adapter.py`
- ZigBee actuators: `app/hardware/adapters/actuators/zigbee_adapter.py`

**Pattern**: Use adapter pattern for different communication protocols. Keep hardware code isolated and testable.

**Hardware Performance Tips**:
- Batch MQTT messages when possible (QoS 1)
- Use persistent MQTT connections (not one-shot)
- Implement exponential backoff for reconnections
- Set reasonable timeouts (5-10s for network operations)
- Log hardware errors but don't crash the app

### Event System

The application uses an in-process event bus for loose coupling:

```python
from app.utils.event_bus import EventBus

# Publishing events
EventBus.publish("sensor.reading", {"sensor_id": 1, "value": 25.5})

# Subscribing to events
EventBus.subscribe("sensor.reading", my_callback_function)

# Unsubscribe when done (prevent memory leaks!)
EventBus.unsubscribe("sensor.reading", my_callback_function)
```

**Event Bus Best Practices**:
- Keep event handlers **fast** (no blocking I/O)
- Use events for cross-module communication (not direct imports)
- Document event payloads in domain models
- Always unsubscribe in cleanup/teardown

Common events defined in `app/enums/events.py`.

## Configuration

### Environment Variables

- `SYSGROW_SECRET_KEY` - Flask secret key (auto-generated in dev)
- `FLASK_ENV` - Environment (development/production)
- `FLASK_DEBUG` - Enable debug mode (set to 0 for Pi deployment)
- `DATABASE_PATH` - Database file path (default: sysgrow.db)
- `SYSGROW_HOST` - Server host (default: 0.0.0.0)
- `SYSGROW_PORT` - Server port (default: 5001/8000)
- `LOG_LEVEL` - Logging level (default: INFO, use WARNING for Pi)
- `MQTT_BROKER_HOST` - MQTT broker address (default: localhost)
- `MQTT_BROKER_PORT` - MQTT broker port (default: 1883)

### Configuration File

Main config: `app/config.py`
Default values: `app/defaults.py`

**Raspberry Pi Tuning** (in `app/config.py`):
- `SQLALCHEMY_POOL_SIZE = 5` (not 20)
- `SQLALCHEMY_MAX_OVERFLOW = 10` (not 50)
- `SENSOR_POLLING_INTERVAL = 60` (seconds)
- `ML_INFERENCE_THROTTLE = 60` (seconds)
- `SENSOR_RETENTION_DAYS = 30` (auto-prune old data)
- `LOG_LEVEL = 'WARNING'` (production on Pi)

## Important File Locations

- **Plant Database**: `plants_info.json` - 500+ plant species profiles (loaded once at startup)
- **ML Models**: `models/` - Trained ML models and configs (lazy loaded)
- **Migrations**: `infrastructure/database/migrations/`
- **ESP32 Firmware**: `../ESP32-C6-Firmware/`
- **Documentation**: `docs/` - Comprehensive docs organized by topic
- **Database**: `sysgrow.db` - Main SQLite database (backup regularly!)
- **Logs**: `logs/` - Application logs (rotate daily, keep 7 days)

## Testing Patterns

Tests are located in `tests/` directory:

- Use `pytest` fixtures for setup/teardown
- Mock external dependencies (hardware, MQTT, filesystem)
- Test files follow `test_*.py` naming convention
- **Smoke tests**: `test_minimal.py`, `test_startup.py` (run first)
- **Unit tests**: Fast, isolated, no external dependencies
- **Integration tests**: Database, API endpoints, service layer
- **Hardware tests**: Conditional (skip on CI if no GPIO)

**Test Performance**:
- Use in-memory SQLite for unit tests (`:memory:`)
- Mock slow operations (ML inference, hardware polling)
- Parallelize with `pytest-xdist` (but watch memory on Pi)

Example test:
```python
import pytest
from unittest.mock import Mock, patch

def test_sensor_reading_service(app_context):
    """Test sensor reading with mocked hardware."""
    with patch('app.hardware.adapters.sensors.gpio_adapter.GPIOAdapter') as mock_gpio:
        mock_gpio.return_value.read.return_value = 25.5
        
        service = app_context.config["CONTAINER"].sensor_management_service
        reading = service.read_sensor(sensor_id=1)
        
        assert reading is not None
        assert reading['value'] == 25.5
```

## Common Gotchas

1. **Database Locked**: SQLite doesn't handle high concurrency well. Use WAL mode (enabled by default). If locked, check for long-running transactions.

2. **MQTT Connection**: Ensure MQTT broker (`mosquitto`) is running before starting the app. Check with `systemctl status mosquitto`.

3. **Hardware Dependencies**: On Windows/non-Pi, install `requirements-essential.txt` (excludes GPIO). On Pi, use full `requirements.txt`.

4. **SocketIO**: Server uses `socketio.run()` not `app.run()` for WebSocket support. Don't mix both.

5. **Template Caching**: In dev mode, template auto-reload is enabled but may require server restart for Jinja macro changes.

6. **CSS Variables**: Always use CSS variables from `theme.css` - never hardcode colors. Check both light and dark themes.

7. **Memory on Pi**: Watch memory usage with `htop`. If OOM, reduce polling intervals, increase retention pruning, or disable ML features temporarily.

8. **Import Time**: Heavy modules (scikit-learn, pandas) slow startup. Lazy load them inside functions, not at module level.

9. **SQLite Pragmas**: Ensure WAL mode is enabled (`PRAGMA journal_mode=WAL`). Check with SQLite CLI.

10. **MQTT QoS**: Use QoS 1 (not 2) for better performance. QoS 2 adds significant overhead.

## Raspberry Pi Optimization Checklist

When developing for Pi deployment:

- [ ] Use `LOG_LEVEL=WARNING` in production
- [ ] Enable SQLite WAL mode (`PRAGMA journal_mode=WAL`)
- [ ] Set conservative connection pool sizes (5-10, not 20-50)
- [ ] Lazy load heavy modules (ML, pandas, numpy)
- [ ] Implement sensor data auto-pruning (30 days default)
- [ ] Use in-memory caching (LRU, max 100 items)
- [ ] Throttle ML inference (1/min per model)
- [ ] Paginate all list queries (max 500 items)
- [ ] Batch MQTT messages when possible
- [ ] Set reasonable timeouts (5-10s for network)
- [ ] Monitor memory with `htop` during development
- [ ] Test on actual Pi hardware before major releases
- [ ] Use `systemd` for production deployment
- [ ] Enable log rotation (daily, keep 7 days)
- [ ] Backup database regularly (cron job recommended)

## Documentation Resources

- **[Architecture Guide](docs/architecture/ARCHITECTURE.md)** - System architecture
- **[API Documentation](docs/api/)** - API references
- **[Setup Guides](docs/setup/)** - Installation and configuration
- **[Development Guide](docs/development/SERVICES.md)** - Service layer details
- **[Performance Guide](docs/PERFORMANCE_OPTIMIZATION.md)** - Raspberry Pi tuning
- **[Index](docs/INDEX.md)** - Complete documentation catalog

Additional resources:
- **[ESP32 Firmware Docs](../ESP32-C6-Firmware/docs/)** - ESP32-specific documentation
- **[Plant Database Docs](docs/plants/PLANT_DATABASE.md)** - Plant profiles and data structure
- **[ML Model Docs](docs/ml/ML_MODELS.md)** - Machine learning integration details

## Philosophy

- **Raspberry Pi First**: Optimize for low-resource environments; scale later
- **Incremental progress over big bangs**: Small changes that compile and pass tests
- **Learning from existing code**: Study patterns before implementing
- **Pragmatic over dogmatic**: Adapt to project reality
- **Clear intent over clever code**: Be boring and obvious (especially important on constrained hardware)
- **Composition over inheritance**: Use dependency injection
- **Explicit over implicit**: Clear data flow
- **Test-driven when possible**: Never disable tests, fix them
- **Fail fast** with descriptive error messages
- **Edge computing**: Process data locally; minimize external dependencies

## Important Reminders

**NEVER**:
- Use `--no-verify` to bypass commit hooks
- Disable tests instead of fixing them
- Commit code that doesn't compile or pass tests
- Add inline styles to templates
- Hardcode colors (use CSS variables from `theme.css`)
- Introduce heavy dependencies without strong justification and Pi testing
- Load large datasets into memory (always paginate)
- Block the main thread with expensive operations
- Use QoS 2 for MQTT (use QoS 1)
- Ignore memory usage on Raspberry Pi

**ALWAYS**:
- Commit working code incrementally
- Follow existing patterns and conventions
- Use type hints for function signatures
- Add docstrings for public methods
- Update documentation when changing APIs
- Test both light and dark themes for UI changes
- Ensure page wrappers are present in templates
- Paginate list queries (default 50, max 500)
- Lazy load heavy modules (ML, pandas, numpy)
- Monitor memory usage during development
- Test on actual Raspberry Pi before releases
- Use WAL mode for SQLite
- Implement proper error handling and logging
- Think about edge cases and resource constraints

## Future Migration Path

When eventually moving to server infrastructure:

1. **Database**: SQLite → PostgreSQL (with pgBouncer for connection pooling)
2. **Caching**: In-memory → Redis (with eviction policies)
3. **Task Queue**: Threading → Celery (with Redis broker)
4. **Frontend**: Vanilla JS → React (with SSR for SEO)
5. **ML Pipeline**: In-process → Dedicated ML service (FastAPI/PyTorch)
6. **Monitoring**: Logs → Prometheus + Grafana
7. **Deployment**: Systemd → Docker/Kubernetes

But for now, **stay focused on Raspberry Pi optimization**. Don't prematurely introduce complexity.