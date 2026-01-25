# Project Reorganization - November 2025

## Overview

This document details the comprehensive project reorganization completed to improve code maintainability, follow clean architecture principles, and organize related functionality into logical groups.

## Changes Summary

### 1. Scripts Organization

**Created:** `scripts/` folder  
**Purpose:** Centralize utility scripts and developer tools

**Files Moved (6):**
- `debug_server.py` - Debug server with detailed logging
- `debug_socketio.py` - SocketIO debugging utilities
- `demo_enhanced_features.py` - Enhanced features demonstration
- `network_hotspot.py` - Network hotspot configuration
- `ota_updater.py` - Over-the-air update manager
- `sync_enhanced_plants.py` - Plant data synchronization

### 2. Workers Organization

**Created:** `workers/` folder  
**Purpose:** Group background services and worker processes  
**Previous Location:** `environment/` folder (now removed)

**Files Moved (6):**
- `task_scheduler.py` - Task scheduling and orchestration
- `sensor_polling_service.py` - Sensor data polling service
- `climate_controller.py` - Climate control automation (PID loops)
- `control_algorithms.py` - Control algorithm implementations
- `control_logic.py` - Control logic and decision making
- `environment_collector.py` - Environment data collection

**Added:** `workers/__init__.py` with module documentation

### 3. Domain Models Organization

**Location:** `app/models/`  
**Previous Location:** `grow_room/` folder (now removed)

**Files Moved (2):**
- `unit_runtime.py` - Growth unit runtime state and operations
- `plant_profile.py` - Plant growth tracking and stage management

**Note:** Files were moved directly into `app/models/`, not into a `grow_room` subdirectory.

### 4. Tests Organization

**Location:** `tests/` folder  
**Previous Location:** Scattered in root directory

**Files Moved (24):** All `test_*.py` files relocated to organized test directory

## Import Updates

All import statements were updated across the codebase to reflect the new structure:

### Workers Module Imports

**Before:**
```python
from environment.sensor_polling_service import SensorPollingService
from environment.climate_controller import ClimateController
from environment.environment_collector import EnvironmentInfoCollector
from task_scheduler import TaskScheduler
```

**After:**
```python
from workers.sensor_polling_service import SensorPollingService
from workers.climate_controller import ClimateController
from workers.environment_collector import EnvironmentInfoCollector
from workers.task_scheduler import TaskScheduler
```

### Domain Models Imports

**Before:**
```python
from grow_room.unit_runtime import UnitRuntime, UnitSettings
from grow_room.plant_profile import PlantProfile
```

**After:**
```python
from app.models.unit_runtime import UnitRuntime, UnitSettings
from app.models.plant_profile import PlantProfile
```

## Files Updated

### Infrastructure Layer
- `infrastructure/hardware/unit_runtime_manager.py`

### Service Layer
- `app/services/growth.py`
- `app/services/container.py`

### API Layer
- `app/blueprints/api/growth.py`
- `app/blueprints/api/insights.py`

### Workers
- `workers/task_scheduler.py`
- `workers/climate_controller.py`
- `workers/control_logic.py`

### Domain Models
- `app/models/unit_runtime.py`

### Scripts
- `scripts/demo_enhanced_features.py`

### Tests
- `tests/test_refactored_architecture.py`

## Architecture Rationale

### Why `workers/` at Root Level?

**Decision:** Background services belong at root level, not inside `app/`

**Reasoning:**
1. **Separation of Concerns:** Workers are infrastructure/operational components, not part of the web application
2. **Independent Execution:** These services run as separate processes/threads independent of Flask
3. **Industry Standard:** Similar to job queues (Celery, RQ), task schedulers sit outside the web app
4. **Scalability:** Easier to deploy workers separately from the web application

### Why `app/models/` for Domain Models?

**Decision:** Domain models moved from `grow_room/` to `app/models/`

**Reasoning:**
1. **Application Layer:** Models are fundamental application components
2. **Clean Architecture:** Domain models belong in the application layer
3. **Flask Convention:** Models typically reside in `app/models/` in Flask projects
4. **Logical Grouping:** Groups all data models together with other application models

## Project Structure

```
backend/
├── app/                          # Flask application
│   ├── models/                   # Domain models ← grow_room/* moved here
│   │   ├── unit_runtime.py
│   │   ├── plant_profile.py
│   │   └── ... (other models)
│   ├── blueprints/               # API routes
│   ├── services/                 # Business logic services
│   └── ...
├── infrastructure/               # Infrastructure layer
│   ├── database/                 # Database operations
│   ├── hardware/                 # Hardware interfaces
│   └── ...
├── workers/                      # Background services ← environment/* moved here
│   ├── __init__.py
│   ├── task_scheduler.py
│   ├── sensor_polling_service.py
│   ├── climate_controller.py
│   ├── control_algorithms.py
│   ├── control_logic.py
│   └── environment_collector.py
├── scripts/                      # Utility scripts ← NEW
│   ├── debug_server.py
│   ├── demo_enhanced_features.py
│   ├── network_hotspot.py
│   ├── ota_updater.py
│   └── ...
├── tests/                        # All test files ← test_*.py moved here
├── docs/                         # Documentation
│   ├── setup/                    # Installation guides
│   ├── architecture/             # Design documents
│   ├── api/                      # API documentation
│   ├── development/              # Development guides
│   └── legacy/                   # Historical documentation
└── ...
```

## Clean Architecture Layers

The reorganization follows clean architecture principles:

### 1. Domain Layer (`app/models/`)
- Pure business logic
- No external dependencies
- Core entities: `UnitRuntime`, `PlantProfile`

### 2. Application Layer (`app/`)
- Use cases and orchestration
- Services: `GrowthService`, `ClimateService`, `ContainerService`
- Web interface: Flask blueprints

### 3. Infrastructure Layer
- External systems integration
- Database: `infrastructure/database/`
- Hardware: `infrastructure/hardware/`
- Background workers: `workers/`

### 4. Presentation Layer
- API endpoints: `app/blueprints/api/`
- Web UI: `app/blueprints/ui/`
- Templates: `templates/`

## Benefits

### 1. **Improved Organization**
- Related files grouped together
- Clear separation of concerns
- Easier navigation

### 2. **Better Maintainability**
- Logical structure makes code easier to find
- Clear boundaries between layers
- Reduced cognitive load

### 3. **Scalability**
- Workers can be deployed independently
- Services can be split into microservices if needed
- Clear interfaces between components

### 4. **Developer Experience**
- Intuitive folder structure
- Consistent import patterns
- Self-documenting organization

## Migration Notes

### No Breaking Changes
All import statements have been updated. The application should work exactly as before.

### Testing
Run the test suite to verify everything works:
```bash
python -m pytest tests/
```

### Import Verification
All imports have been updated and verified. No unresolved imports remain in Python code files.

## Related Documentation

- [Architecture Overview](../architecture/REFACTORING_ANALYSIS.md)
- [Documentation Organization](DOCUMENTATION_REORGANIZATION.md)
- [Tests Organization](TESTS_ORGANIZATION.md)
- [Project Summary](../../PROJECT_SUMMARY.md)

## Date

November 9, 2025

## Author

Project reorganization completed as part of ongoing architectural improvements.
