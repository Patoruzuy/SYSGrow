# Schedule Logic Documentation

**Version:** 1.0  
**Date:** January 2026  
**Author:** SYSGrow Development Team

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Domain Model](#domain-model)
3. [Repository Pattern](#repository-pattern)
4. [SchedulingService](#schedulingservice)
5. [Database Schema](#database-schema)
6. [Schedule Types](#schedule-types)
7. [Photoperiod Integration](#photoperiod-integration)
8. [Execution Flow](#execution-flow)
9. [API Endpoints](#api-endpoints)
10. [Usage Examples](#usage-examples)
11. [Migration Guide](#migration-guide)

---

## Architecture Overview

### Problem Statement

The original schedule system only supported **one schedule per device type** using a JSON column in the `GrowthUnits` table. This was limiting because:
- Users couldn't create multiple schedules (e.g., fan every 2 hours)
- No persistent schedule management
- No photoperiod support for smart light control
- No enable/disable without deletion

### Solution

A centralized, database-backed scheduling system with:
- **Multiple schedules per device** (unlimited)
- **Persistent storage** in dedicated `DeviceSchedules` table
- **Photoperiod support** for light schedules (schedule + sensor + hybrid modes)
- **Enable/disable toggles** (soft delete)
- **Repository pattern** for clean architecture
- **Automatic execution** via `UnifiedScheduler`

### Service Stack

```
┌─────────────────────────────────────────────┐
│     REST API (v3 Endpoints)                 │
│  GET/POST/PUT/DELETE /api/v3/schedules      │
└────────────────┬────────────────────────────┘
                 │
┌────────────────▼────────────────────────────┐
│     SchedulingService                        │
│  - CRUD operations                           │
│  - Schedule evaluation                       │
│  - Photoperiod logic                         │
│  - Caching                                   │
└────────────────┬────────────────────────────┘
                 │
┌────────────────▼────────────────────────────┐
│     ScheduleRepository (Protocol)            │
│  - Abstraction over persistence              │
│  - Caching decorator support                 │
└────────────────┬────────────────────────────┘
                 │
┌────────────────▼────────────────────────────┐
│     SQLiteDatabaseHandler                    │
│  - ScheduleOperations mixin                  │
│  - Low-level database operations             │
└─────────────────────────────────────────────┘
```

---

## Domain Model

### Schedule Entity

**File:** `app/domain/schedules/schedule_entity.py`

```python
@dataclass
class Schedule:
    """Represents a single schedule for a device in a growth unit."""
    
    unit_id: int                      # Which growth unit
    device_type: str                  # "light", "fan", "pump", etc.
    actuator_id: Optional[int]        # Which actuator to control
    name: str                         # Human-readable name
    
    # Time-based scheduling
    schedule_type: ScheduleType       # SIMPLE, INTERVAL, PHOTOPERIOD, AUTOMATIC
    start_time: str                   # "08:00" in HH:MM format
    end_time: str                     # "20:00" in HH:MM format
    interval_minutes: Optional[int]   # For INTERVAL schedules
    duration_minutes: Optional[int]   # For INTERVAL schedules
    days_of_week: List[int]           # 0=Monday, 6=Sunday
    
    # Control settings
    state_when_active: ScheduleState  # ON or OFF
    value: Optional[float]            # Dimmer level 0-100 (optional)
    priority: int                     # Conflict resolution (higher wins)
    
    # Metadata
    enabled: bool                     # Can be toggled without deletion
    photoperiod: Optional[PhotoperiodConfig]  # Smart light control
    
    # Database
    schedule_id: Optional[int]        # Set after creation
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    
    def validate(self) -> bool:
        """Validate schedule before persistence."""
        
    def is_active_at(self, check_time: Optional[datetime] = None) -> bool:
        """Check if schedule should be active at a given time."""
        
    def duration_hours(self) -> float:
        """Calculate daily light hours for light schedules."""
```

### Schedule Types

**File:** `app/enums/growth.py`

```python
class ScheduleType(Enum):
    """Type of schedule logic."""
    SIMPLE = "simple"           # Start time -> end time daily
    INTERVAL = "interval"       # Repeating cycles within a window
    PHOTOPERIOD = "photoperiod" # Smart light based on sensors
    AUTOMATIC = "automatic"     # Derived from active plant stage
```

### Photoperiod Configuration

```python
@dataclass
class PhotoperiodConfig:
    """Configuration for photoperiod-aware light scheduling."""
    
    source: PhotoperiodSource      # Where to get day/night info
    sensor_threshold: float        # Lux threshold for "day" (default 100)
    prefer_sensor: bool            # Use sensor over schedule when available
```

**Sources:**
- `SCHEDULE` - Use schedule times only (default)
- `SENSOR` - Use lux sensor to detect natural light
- `HYBRID` - Schedule window + sensor fine-tuning
- `SUN_API` - Use GPS coordinates for sunrise/sunset (future)

### Enums

```python
class ScheduleState(Enum):
    """State when schedule is active."""
    ON = "on"
    OFF = "off"

class PhotoperiodSource(Enum):
    """Where photoperiod information comes from."""
    SCHEDULE = "schedule"
    SENSOR = "sensor"
    HYBRID = "hybrid"
    SUN_API = "sun_api"

class DayOfWeek(Enum):
    """Days of the week for recurring schedules."""
    MONDAY = 0
    TUESDAY = 1
    # ... 6 = Sunday
```

---

## Repository Pattern

### Why Repository?

Before: `SchedulingService` imported `SQLiteDatabaseHandler` directly  
After: `SchedulingService` depends only on `ScheduleRepository` protocol

**Benefits:**
- ✅ Decoupled from infrastructure
- ✅ Easy to swap database implementations
- ✅ Testable with mock repositories
- ✅ Clean architecture (domain → application → infrastructure)

### ScheduleRepository Protocol

**File:** `app/domain/schedules/repository.py`

```python
class ScheduleRepository(Protocol):
    """Protocol (interface) for schedule persistence."""
    
    @abstractmethod
    def create(self, schedule: Schedule) -> Schedule: ...
    
    @abstractmethod
    def get_by_id(self, schedule_id: int) -> Optional[Schedule]: ...
    
    @abstractmethod
    def get_by_unit(self, unit_id: int) -> List[Schedule]: ...
    
    @abstractmethod
    def get_by_device_type(self, unit_id: int, device_type: str) -> List[Schedule]: ...
    
    @abstractmethod
    def get_by_actuator(self, actuator_id: int) -> List[Schedule]: ...
    
    @abstractmethod
    def update(self, schedule: Schedule) -> Optional[Schedule]: ...
    
    @abstractmethod
    def delete(self, schedule_id: int) -> bool: ...
    
    @abstractmethod
    def delete_by_unit(self, unit_id: int) -> int: ...
    
    @abstractmethod
    def set_enabled(self, schedule_id: int, enabled: bool) -> bool: ...
```

### Concrete Implementation

**File:** `infrastructure/database/repositories/schedules.py`

```python
class ScheduleRepository:
    """Concrete implementation wrapping ScheduleOperations mixin."""
    
    def __init__(self, backend: ScheduleOperations) -> None:
        """Initialize with database handler that implements ScheduleOperations."""
        self._backend = backend
    
    # All methods delegate to backend
    def create(self, schedule: Schedule) -> Optional[Schedule]:
        return self._backend.create_schedule(schedule)
```

### Caching

The repository uses `@repository_cache` decorators for performance:
- `get_by_id()` - Cached per schedule (256 entries)
- `get_by_unit()` - Cached per unit (64 entries)
- `get_by_device_type()` - Cached per type (128 entries)
- Caches auto-invalidate on create/update/delete

---

## SchedulingService

**File:** `app/services/hardware/scheduling_service.py`

Central service for all schedule operations. Provides:

### Initialization

```python
from infrastructure.database.repositories.schedules import ScheduleRepository

schedule_repo = ScheduleRepository(database)
scheduling_service = SchedulingService(
    repository=schedule_repo,
)
```

### CRUD Operations

```python
# Create schedule
schedule = Schedule(
    unit_id=1,
    device_type="light",
    name="Morning Light",
    schedule_type=ScheduleType.SIMPLE,
    start_time="08:00",
    end_time="20:00",
    state_when_active=ScheduleState.ON,
    enabled=True,
)
created = scheduling_service.create_schedule(schedule)

# Get schedule
schedule = scheduling_service.get_schedule(schedule_id=1)

# List schedules
schedules = scheduling_service.get_schedules_for_unit(unit_id=1)

# Filter by device type
lights = scheduling_service.get_schedules_for_unit(
    unit_id=1,
    device_type="light",
    enabled_only=True
)

# Update schedule
schedule.end_time = "21:00"
success = scheduling_service.update_schedule(schedule)

# Delete schedule
scheduling_service.delete_schedule(schedule_id=1)

# Toggle enable/disable (no deletion)
scheduling_service.set_schedule_enabled(schedule_id=1, enabled=False)
```

### Schedule Evaluation

```python
# Is device active now?
is_light_on = scheduling_service.is_device_active(
    unit_id=1,
    device_type="light"
)

# Get all active schedules
active = scheduling_service.get_active_schedules(unit_id=1)

# Get dimmer level
level = scheduling_service.get_device_value(
    unit_id=1,
    device_type="grow_light"
)  # Returns 0-100 or None
```

### Light Schedule Helpers

```python
# Get primary light schedule
light_schedule = scheduling_service.get_light_schedule(unit_id=1)

# Calculate daily light hours
hours = scheduling_service.get_light_hours(unit_id=1)  # Returns float

# Photoperiod-aware light check
is_on = scheduling_service.is_light_on(
    unit_id=1,
    check_time=datetime.now(),
    lux_reading=500.0  # Optional current sensor reading
)
```

### Auto-Generation Hooks

- **Unit creation:** If no schedules exist, plant-based schedules can be auto-generated.
- **Active plant change:** If no custom schedules exist, auto-generated schedules are refreshed.

### Schedule Summary

```python
summary = scheduling_service.get_schedule_summary(unit_id=1)
# Returns:
# {
#     "unit_id": 1,
#     "total_schedules": 5,
#     "enabled_schedules": 4,
#     "by_device_type": {
#         "light": {"total": 1, "enabled": 1},
#         "fan": {"total": 2, "enabled": 2}
#     },
#     "light_hours": 12.0
# }
```

---

## Database Schema

### DeviceSchedules Table

```sql
CREATE TABLE DeviceSchedules (
    schedule_id INTEGER PRIMARY KEY AUTOINCREMENT,
    unit_id INTEGER NOT NULL,
    device_type TEXT NOT NULL,
    actuator_id INTEGER,
    name TEXT NOT NULL,
    
    -- Schedule type
    schedule_type TEXT NOT NULL DEFAULT 'simple',
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL,
    interval_minutes INTEGER,
    duration_minutes INTEGER,
    
    -- Control settings
    state_when_active TEXT NOT NULL DEFAULT 'on',
    value REAL,
    priority INTEGER DEFAULT 0,
    
    -- Metadata
    enabled BOOLEAN DEFAULT 1,
    photoperiod_config TEXT,  -- JSON: PhotoperiodConfig
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (unit_id) REFERENCES GrowthUnits(unit_id),
    FOREIGN KEY (actuator_id) REFERENCES Actuators(actuator_id)
);

-- Indexes for common queries
CREATE INDEX idx_device_schedules_unit_id ON DeviceSchedules(unit_id);
CREATE INDEX idx_device_schedules_device_type ON DeviceSchedules(unit_id, device_type);
CREATE INDEX idx_device_schedules_actuator_id ON DeviceSchedules(actuator_id);
CREATE INDEX idx_device_schedules_enabled ON DeviceSchedules(enabled);
CREATE INDEX idx_device_schedules_unit_enabled ON DeviceSchedules(unit_id, enabled);
```

### Legacy Column (Deprecated)

The `GrowthUnits.device_schedules` JSON column still exists but is deprecated. Use the cleanup migration to remove it:

```bash
python migrations/cleanup_device_schedules.py --execute
```

---

## Schedule Types

### Simple Time-Based (Default)

**Use case:** Light on 8 AM - 8 PM daily

```python
Schedule(
    device_type="light",
    schedule_type=ScheduleType.SIMPLE,
    start_time="08:00",
    end_time="20:00",
    state_when_active=ScheduleState.ON,
    enabled=True,
)
```

**Behavior:** Checks if current time falls between start_time and end_time.

### Interval-Based

**Use case:** Fan runs 30 min every 2 hours

```python
Schedule(
    device_type="fan",
    schedule_type=ScheduleType.INTERVAL,
    interval_minutes=120,          # Run every 2 hours
    duration_minutes=30,           # For 30 minutes
    start_time="06:00",            # First run at 6 AM
    end_time="22:00",              # Stop adding at 10 PM
    state_when_active=ScheduleState.ON,
)
```

**Behavior:** Repeats every interval_minutes inside the start/end window.

### Photoperiod (Smart Light)

**Use case:** Supplemental light when natural light is insufficient

```python
Schedule(
    device_type="light",
    schedule_type=ScheduleType.PHOTOPERIOD,
    start_time="06:00",
    end_time="22:00",
    state_when_active=ScheduleState.ON,
    photoperiod=PhotoperiodConfig(
        source=PhotoperiodSource.HYBRID,
        sensor_threshold=100.0,  # Lux threshold
        prefer_sensor=True,
    ),
)
```

**Modes:**

| Source | Behavior |
|--------|----------|
| `SCHEDULE` | Light on within schedule window (ignores sensor) |
| `SENSOR` | Relies on lux sensor, ignores schedule times |
| `HYBRID` | Schedule window determines when to check; sensor fine-tunes |
| `SUN_API` | Use sunrise/sunset times (not yet implemented) |

---

### Automatic (Plant-Based)

**Use case:** Auto-generate light schedules from the active plant stage

```python
Schedule(
    device_type="light",
    schedule_type=ScheduleType.AUTOMATIC,
    start_time="08:00",
    end_time="20:00",
    state_when_active=ScheduleState.ON,
    enabled=True,
)
```

**Behavior:** Schedule times are computed from plant lighting requirements during creation.

## Photoperiod Integration

### How It Works

1. **Evaluate Schedule Time**
   - Is the current time within start_time and end_time?

2. **Get Sensor Data**
   - Fetch latest lux reading from AnalyticsService
   - Try multiple field names: `light_lux`, `lux`, `light_level`, etc.

3. **Apply Photoperiod Logic**
   ```python
   is_light_on = scheduling_service.is_light_on(
       unit_id=1,
       check_time=datetime.now(),
       lux_reading=500.0  # Current lux from sensor
   )
   ```

4. **Decision Tree**
   ```
   No light schedule?
   └─> OFF
   
   Has photoperiod config?
   ├─> SCHEDULE mode
   │   └─> ON if within schedule window
   │
   ├─> SENSOR mode
   │   ├─> Lux >= threshold?
   │   │   └─> ON (natural light sufficient)
   │   └─> Lux < threshold AND in schedule window?
   │       └─> ON (need supplemental light)
   │
   ├─> HYBRID mode
   │   ├─> Outside schedule window?
   │   │   └─> OFF
   │   ├─> prefer_sensor = true?
   │   │   └─> ON if lux < threshold
   │   └─> prefer_sensor = false?
   │       └─> ON (always on in window)
   │
   └─> SUN_API mode
       └─> OFF (not implemented)
   
   No photoperiod config?
   └─> ON if within schedule window
   ```

### Example: Grow Light with Hybrid Photoperiod

```python
# Create schedule
schedule = Schedule(
    unit_id=1,
    device_type="light",
    name="Hybrid Grow Light",
    schedule_type=ScheduleType.PHOTOPERIOD,
    start_time="06:00",
    end_time="22:00",
    state_when_active=ScheduleState.ON,
    photoperiod=PhotoperiodConfig(
        source=PhotoperiodSource.HYBRID,
        sensor_threshold=100.0,  # Lux
        prefer_sensor=True,      # Trust sensor over schedule
    ),
)

scheduling_service.create_schedule(schedule)

# Later, during check...
# Scenario 1: Sunny day (lux=800)
# Result: Light OFF (natural light sufficient)

# Scenario 2: Cloudy morning (lux=150, but in window)
# Result: Light ON (supplement natural light)

# Scenario 3: Night (lux=0, in window)
# Result: Light ON (full artificial light needed)

# Scenario 4: Evening (lux=50, outside schedule window)
# Result: Light OFF (outside window)
```

---

## Execution Flow

### Scheduled Task: `actuator_schedule_check_task`

**File:** `app/workers/scheduled_tasks.py`

Runs every 30 seconds via `UnifiedScheduler`:

```python
def actuator_schedule_check_task(container: ServiceContainer) -> Dict[str, Any]:
    """
    Check and execute actuator schedules from the database.
    
    1. Get all active unit IDs from GrowthService
    2. For each unit:
       a. Fetch enabled schedules from ScheduleRepository
       b. Get current lux reading from AnalyticsService
       c. For each schedule:
          - Light with photoperiod: use is_light_on()
          - Other schedules: use is_active_at()
    3. Track state transitions (on→off, off→on)
    4. Execute actuator commands on transition
    """
```

### State Tracking

The task uses a global dictionary to track schedule state:

```python
_schedule_last_state: Dict[int, bool] = {}  # schedule_id -> is_active
```

This ensures transitions are detected only when state **changes**, not every 30 seconds.

### Transition Logic

```
Previous State | Current State | Action
─────────────────────────────────────────
None (first check) | Any | Record state, no action
False | False | No change, no action
False | True | Turn ON → Call manager.turn_on()
True | False | Turn OFF → Call manager.turn_off()
True | True | No change, no action
```

### Execution Order

1. Get ActuatorManagementService → ActuatorManager → SchedulingService
2. Check if repository is available (fallback to legacy schedules)
3. Iterate units: `for unit_id in get_active_unit_ids()`
4. For each schedule: evaluate and execute transitions
5. Log results: `{units_checked, schedules_checked, transitions, errors}`

---

## API Endpoints

**Base URL:** `/api/v3/schedules`

### List All Schedules for Unit

```http
GET /api/v3/schedules/unit/{unit_id}
```

**Query Parameters:**
- `device_type` (optional) - Filter by device type
- `enabled_only` (optional) - Only return enabled schedules

**Response:**
```json
{
  "success": true,
  "data": {
    "schedules": [
      {
        "schedule_id": 1,
        "unit_id": 1,
        "device_type": "light",
        "name": "Morning Light",
        "schedule_type": "simple",
        "start_time": "08:00",
        "end_time": "20:00",
        "state_when_active": "on",
        "value": null,
        "priority": 0,
        "enabled": true,
        "photoperiod": null,
        "created_at": "2026-01-09T15:30:00",
        "updated_at": "2026-01-09T15:30:00"
      }
    ],
    "total": 1
  }
}
```

### Get Single Schedule

```http
GET /api/v3/schedules/{schedule_id}
```

### Create Schedule

```http
POST /api/v3/schedules
Content-Type: application/json

{
  "unit_id": 1,
  "device_type": "light",
  "actuator_id": 5,
  "name": "Evening Light",
  "schedule_type": "simple",
  "start_time": "18:00",
  "end_time": "22:00",
  "state_when_active": "on",
  "value": null,
  "priority": 0,
  "enabled": true,
  "photoperiod": null
}
```

### Update Schedule

```http
PUT /api/v3/schedules/{schedule_id}
Content-Type: application/json

{
  "end_time": "21:00"
}
```

### Delete Schedule

```http
DELETE /api/v3/schedules/{schedule_id}
```

### Toggle Enable/Disable

```http
PATCH /api/v3/schedules/{schedule_id}/toggle
```

**Response:**
```json
{
  "success": true,
  "data": {
    "schedule_id": 1,
    "enabled": false
  }
}
```

### Get Summary

```http
GET /api/v3/schedules/unit/{unit_id}/summary
```

**Response:**
```json
{
  "success": true,
  "data": {
    "unit_id": 1,
    "total_schedules": 5,
    "enabled_schedules": 4,
    "by_device_type": {
      "light": {"total": 1, "enabled": 1},
      "fan": {"total": 2, "enabled": 2},
      "pump": {"total": 2, "enabled": 1}
    },
    "light_hours": 12.0
  }
}
```

### Get Active Schedules

```http
GET /api/v3/schedules/unit/{unit_id}/active
```

Returns only schedules currently active (enabled and within time window).

---

## Usage Examples

### Example 1: Simple Light Schedule

```python
from app.domain.schedules import Schedule
from app.enums.growth import ScheduleType, ScheduleState

# Create a simple daily light schedule
light_schedule = Schedule(
    unit_id=1,
    device_type="light",
    actuator_id=10,
    name="Daily Light Cycle",
    schedule_type=ScheduleType.SIMPLE,
    start_time="06:00",
    end_time="22:00",
    state_when_active=ScheduleState.ON,
    value=None,
    priority=0,
    enabled=True,
    photoperiod=None,
)

created = scheduling_service.create_schedule(light_schedule)
print(f"Created schedule ID {created.schedule_id}")
```

### Example 2: Interval Schedule

```python
# Fan runs 20 minutes every 2 hours
fan_schedule = Schedule(
    unit_id=1,
    device_type="fan",
    actuator_id=15,
    name="Circulation Fan",
    schedule_type=ScheduleType.INTERVAL,
    interval_minutes=120,
    duration_minutes=20,
    start_time="06:00",
    end_time="22:00",
    state_when_active=ScheduleState.ON,
    priority=0,
    enabled=True,
)

created = scheduling_service.create_schedule(fan_schedule)
```

### Example 3: Automatic Light Schedule

```python
# Plant-based light schedule (times resolved during creation)
auto_light = Schedule(
    unit_id=1,
    device_type="light",
    actuator_id=10,
    name="Plant-Based Light",
    schedule_type=ScheduleType.AUTOMATIC,
    start_time="07:00",
    end_time="19:00",
    state_when_active=ScheduleState.ON,
    priority=0,
    enabled=True,
)

created = scheduling_service.create_schedule(auto_light)
```

### Example 4: Hybrid Photoperiod

```python
from app.domain.schedules import PhotoperiodConfig
from app.enums.growth import PhotoperiodSource

# Smart light with hybrid sensor mode
light_schedule = Schedule(
    unit_id=1,
    device_type="light",
    actuator_id=10,
    name="Smart Grow Light",
    schedule_type=ScheduleType.PHOTOPERIOD,
    start_time="05:00",
    end_time="23:00",
    state_when_active=ScheduleState.ON,
    priority=1,
    enabled=True,
    photoperiod=PhotoperiodConfig(
        source=PhotoperiodSource.HYBRID,
        sensor_threshold=100.0,
        prefer_sensor=True,
    ),
)

created = scheduling_service.create_schedule(light_schedule)
```

### Example 5: Dimmer with Schedule

```python
# Grow light that dims to 60% during evening
dimmer_schedule = Schedule(
    unit_id=1,
    device_type="grow_light",
    actuator_id=10,
    name="Evening Dimmed Light",
    schedule_type=ScheduleType.SIMPLE,
    start_time="18:00",
    end_time="20:00",
    state_when_active=ScheduleState.ON,
    value=60.0,  # Dim to 60%
    priority=1,  # Higher priority than main light
    enabled=True,
)

created = scheduling_service.create_schedule(dimmer_schedule)
```

### Example 6: Disable and Re-enable

```python
# Disable temporarily without deletion
scheduling_service.set_schedule_enabled(schedule_id=1, enabled=False)

# Check if still active
active = scheduling_service.is_device_active(unit_id=1, device_type="light")
# Returns: False

# Re-enable
scheduling_service.set_schedule_enabled(schedule_id=1, enabled=True)

active = scheduling_service.is_device_active(unit_id=1, device_type="light")
# Returns: True (if within schedule window)
```

### Example 6: List and Manage

```python
# Get all light schedules for a unit
light_schedules = scheduling_service.get_schedules_for_unit(
    unit_id=1,
    device_type="light",
    enabled_only=True
)

for schedule in light_schedules:
    print(f"{schedule.name}: {schedule.start_time}-{schedule.end_time}")
    print(f"  Enabled: {schedule.enabled}")
    print(f"  Priority: {schedule.priority}")

# Get summary
summary = scheduling_service.get_schedule_summary(unit_id=1)
print(f"Total schedules: {summary['total_schedules']}")
print(f"Light hours: {summary['light_hours']}")
```

---

## Migration Guide

### From Legacy JSON to DeviceSchedules

The migration is a two-step process:

#### Phase 2: Migrate Data

```bash
python migrations/migrate_device_schedules.py
```

This script:
1. Reads JSON from `GrowthUnits.device_schedules`
2. Converts to Schedule objects
3. Inserts into `DeviceSchedules` table
4. Preserves original data (doesn't delete JSON)

Options:
- `--dry-run` - Show what would be migrated
- `--validate` - Check if migration was successful
- `--rollback` - Delete from DeviceSchedules (restore JSON)

#### Phase 5: Cleanup

```bash
# Validate that migration is complete
python migrations/cleanup_device_schedules.py --validate

# Remove the legacy column
python migrations/cleanup_device_schedules.py --execute
```

This script:
1. Validates all data is in DeviceSchedules
2. Backs up the JSON column to `migrations/backups/device_schedules_backup.json`
3. Removes the deprecated column
4. Confirms with user before executing

### Updating Code

**Old code:**
```python
runtime.settings.device_schedules = set_schedule(
    runtime.settings.device_schedules,
    device_type="light",
    data={...}
)
```

**New code:**
```python
schedule = Schedule(
    unit_id=unit_id,
    device_type="light",
    # ... other fields
)
scheduling_service.create_schedule(schedule)
```

---

## Testing

### Unit Tests

```bash
pytest tests/unit/services/hardware/test_scheduling_service.py
pytest tests/unit/hardware/test_schedule_entity.py
```

### Integration Tests

```bash
pytest tests/integration/test_schedule_api.py
pytest tests/integration/test_actuator_schedule_execution.py
```

### Manual Testing

1. **Create a schedule via API:**
   ```bash
   curl -X POST http://localhost:5000/api/v3/schedules \
     -H "Content-Type: application/json" \
     -d '{"unit_id":1,"device_type":"light",...}'
   ```

2. **Check schedule execution:**
   - Monitor logs for `Schedule check:` entries
   - Verify actuator state changes at expected times

3. **Test photoperiod:**
   - Create HYBRID photoperiod schedule
   - Verify light responds to lux readings
   - Check in low-light vs high-light conditions

---

## Troubleshooting

### Schedule Not Executing

**Symptoms:** Schedule created but actuator not controlled

**Checklist:**
1. ✅ Is the schedule enabled? → `enabled=True`
2. ✅ Is it within the time window? → Check `start_time` and `end_time`
3. ✅ Is the actuator linked? → Check `actuator_id` is not None
4. ✅ Is the actuator registered? → Check in ActuatorManager
5. ✅ Is the scheduled task running? → Check logs for `Schedule check:` message every 30s

### Photoperiod Not Working

**Symptoms:** Light doesn't respond to sensor

**Checklist:**
1. ✅ Is photoperiod config present? → Check `schedule.photoperiod` is not None
2. ✅ Is lux sensor reporting data? → Check AnalyticsService
3. ✅ Correct source mode? → Try `SENSOR` mode first
4. ✅ Sensor threshold reasonable? → Default 300 lux (adjust if needed)

### Schedule State Stuck

**Symptoms:** Schedule state doesn't transition

**Solution:**
1. Check database for correct enabled status: `SELECT enabled FROM DeviceSchedules WHERE schedule_id=...`
2. Verify no errors in logs during check task
3. Restart the service to reset state tracking

### Performance Issues

**Symptoms:** Schedule checks taking too long

**Solution:**
1. Enable caching: `scheduling_service.set_cache_enabled(True)`
2. Reduce number of enabled schedules (disable unused ones)
3. Monitor cache hits: `CacheRegistry.get_instance().stats()`

---

## Performance Considerations

### Caching Strategy

- **Cache TTL:** 60 seconds (configurable)
- **Cache Size:** 64-256 entries per query type
- **Invalidation:** Automatic on create/update/delete

### Database Queries

Each 30-second check executes approximately:
- 1 query to list enabled schedules per unit
- 1 query to get lux reading (via AnalyticsService)
- Cached thereafter for 60 seconds

### Optimization Tips

1. Use `enabled_only=True` to skip disabled schedules
2. Limit number of active units (archive old ones)
3. Keep photoperiod sensor readings current
4. Monitor `actuator_schedule_check_task` in logs

---

## Future Enhancements

- [ ] Sun API integration for sunrise/sunset times
- [ ] Recurring schedules (e.g., different times on weekends)
- [ ] Schedule templates/presets
- [ ] Conflict resolution strategies (not just priority)
- [ ] Schedule suggestions based on plant growth stage
- [ ] Mobile app schedule notifications
- [ ] Schedule import/export (JSON/CSV)

---

## Support

For issues or questions:
1. Check troubleshooting section above
2. Review API endpoint documentation
3. Examine logs: `docker logs sysgrow-backend`
4. Contact development team with reproduction steps
