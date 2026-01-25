# 🏗️ SYSGrow Architecture Refactoring Plan
## From Monolithic to Service-Based Architecture

> **Senior Engineer Assessment & Implementation Guide**
> 
> Date: November 2025
> Status: Planning & Implementation Phase

---

## 📊 Executive Summary

### Current State Analysis

**Monolithic Structure Issues:**
- ❌ 584 lines in `GrowthUnit` class (too large!)
- ❌ 216 lines in `GrowthUnitManager` (mixed concerns)
- ❌ Direct database coupling in domain models
- ❌ No user context/multi-tenancy support
- ❌ Business logic mixed with infrastructure
- ❌ Hard to test independently
- ❌ Difficult to scale

**Good Foundations:**
- ✅ Event bus pattern already in place
- ✅ Threading safety considerations
- ✅ Clear plant lifecycle management
- ✅ Database abstraction layer exists

### Target Architecture

```
Service-Based Clean Architecture
├── Presentation Layer (UI/API)
│   ├── blueprints/api/ (RESTful endpoints)
│   ├── blueprints/ui/ (Web views)
│   └── templates/ (Jinja2 templates)
├── Application Layer (Services)
│   ├── services/unit_service.py
│   ├── services/plant_service.py
│   ├── services/device_service.py
│   ├── services/camera_service.py
│   └── services/schedule_service.py
├── Domain Layer (Business Logic)
│   ├── models/growth_unit.py
│   ├── models/plant.py
│   ├── models/device.py
│   └── events/event_bus.py
└── Infrastructure Layer (Data Access)
    ├── repositories/unit_repository.py
    ├── repositories/plant_repository.py
    └── database/database_handler.py
```

---

## 🎯 Key Improvements

### 1. **Smart User Routing** ✅ PRIORITY 1

**Business Requirement:**
- User with 1 unit → Auto-navigate to dashboard
- User with multiple units → Show unit selector
- New user (0 units) → Create default unit + go to dashboard

**Implementation:**
```python
# In unit_service.py
def determine_landing_page(user_id):
    units = get_user_units(user_id)
    
    if len(units) == 0:
        # Create default unit
        unit_id = create_unit(user_id, "My First Growth Unit")
        return {"route": "dashboard", "unit_id": unit_id}
    
    elif len(units) == 1:
        # Single unit - straight to dashboard
        return {"route": "dashboard", "unit_id": units[0]["unit_id"]}
    
    else:
        # Multiple units - show selector
        return {"route": "unit_selector", "units": units}
```

### 2. **Visual Unit Selector** ✅ CREATED

**Features:**
- 📸 Custom image or default placeholder
- 📏 Dimensional display (W×H×D cm, Volume L)
- 📍 Location badge
- 🎥 Camera live stream button (if available)
- 🌱 Plant preview cards (max 6)
- 💧 Moisture indicator rings around plants
  - Color coding: Too Wet → Wet → Normal → Dry → Too Dry
  - Percentage display

**Template:** `templates/unit_selector.html` ✅ Created

### 3. **Per-Unit Configuration** ✅ SERVICE LAYER

**UnitSettings DataClass:**
```python
@dataclass
class UnitSettings:
    temperature_threshold: float = 24.0
    humidity_threshold: float = 50.0
    soil_moisture_threshold: float = 40.0
    light_start_time: str = "08:00"
    light_end_time: str = "20:00"
```

**Benefits:**
- Independent settings per unit
- Type safety
- Easy validation
- Default values
- Serialization built-in

---

## 🔨 Refactoring Steps

### Phase 1: Service Layer Creation ✅ IN PROGRESS

**Files to Create:**

#### 1.1 Unit Service ✅ DONE
```
app/services/unit_service.py
- UnitService class
- get_user_units(user_id)
- create_unit(user_id, name, location, dimensions)
- update_unit(unit_id, ...)
- delete_unit(unit_id, user_id)
- determine_landing_page(user_id)
- get_unit_card_data(unit_id)
```

#### 1.2 Plant Service (TODO)
```python
app/services/plant_service.py
```
```python
class PlantService:
    def add_plant_to_unit(unit_id, plant_name, plant_type, stage)
    def remove_plant_from_unit(unit_id, plant_id)
    def update_plant_stage(plant_id, new_stage, days_in_stage)
    def get_plants_in_unit(unit_id)
    def link_plant_to_sensor(plant_id, sensor_id)
    def update_plant_moisture(plant_id, moisture_level)
    def advance_plant_growth(plant_id)  # Daily cron job
```

#### 1.3 Device Service (TODO)
```python
app/services/device_service.py
```
```python
class DeviceService:
    def link_sensor_to_unit(unit_id, sensor_id)
    def link_actuator_to_unit(unit_id, actuator_id)
    def get_unit_devices(unit_id)
    def remove_device_from_unit(unit_id, device_id)
    def get_sensor_reading(sensor_id)
    def control_actuator(actuator_id, state)
```

#### 1.4 Camera Service (TODO)
```python
app/services/camera_service.py
```
```python
class CameraService:
    def start_camera(unit_id)
    def stop_camera(unit_id)
    def capture_photo(unit_id)
    def get_camera_status(unit_id)
    def get_camera_stream_url(unit_id)
```

#### 1.5 Schedule Service (TODO)
```python
app/services/schedule_service.py
```
```python
class ScheduleService:
    def set_device_schedule(unit_id, device_name, start_time, end_time)
    def set_lighting_schedule(unit_id, start_time, end_time)
    def get_unit_schedules(unit_id)
    def execute_scheduled_tasks()  # Background worker
```

### Phase 2: Slim Down Domain Models

**Current:** 584 lines in GrowthUnit
**Target:** ~150 lines (pure domain logic only)

**What to Extract:**

```python
# FROM: grow_room/growth_unit.py

# MOVE TO services/climate_service.py:
- climate_controller logic
- sensor polling logic
- actuator control logic

# MOVE TO services/device_service.py:
- sensor_manager
- actuator_manager
- device_observers

# MOVE TO services/camera_service.py:
- camera_manager

# MOVE TO services/schedule_service.py:
- task_scheduler

# KEEP IN models/growth_unit.py:
- unit_id, name, location
- growth_unit_settings
- plants dictionary
- active_plant reference
- Basic getters/setters
```

**Refactored GrowthUnit Model:**
```python
# models/growth_unit.py (NEW - lightweight)
from dataclasses import dataclass
from typing import Dict, Optional

@dataclass
class GrowthUnit:
    """Lightweight domain model for growth units"""
    unit_id: int
    user_id: int
    name: str
    location: str
    settings: UnitSettings
    dimensions: Optional[UnitDimensions] = None
    custom_image: Optional[str] = None
    is_active: bool = True
    
    def to_dict(self) -> Dict:
        return {
            "unit_id": self.unit_id,
            "name": self.name,
            "location": self.location,
            "settings": self.settings.to_dict(),
            "dimensions": self.dimensions.to_dict() if self.dimensions else None,
            "custom_image": self.custom_image,
            "is_active": self.is_active
        }
```

### Phase 3: Database Layer Updates

**Add Multi-Tenancy:**

```sql
-- Migrate growth_units table
ALTER TABLE growth_units ADD COLUMN user_id INTEGER;
ALTER TABLE growth_units ADD COLUMN dimensions JSON;
ALTER TABLE growth_units ADD COLUMN custom_image TEXT;
ALTER TABLE growth_units ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
ALTER TABLE growth_units ADD COLUMN updated_at TIMESTAMP;

-- Add indexes
CREATE INDEX idx_growth_units_user_id ON growth_units(user_id);
CREATE INDEX idx_growth_units_active ON growth_units(is_active);

-- Add foreign key
ALTER TABLE growth_units 
ADD CONSTRAINT fk_growth_units_user 
FOREIGN KEY (user_id) REFERENCES users(user_id) 
ON DELETE CASCADE;
```

**New Database Methods:**

```python
# database/database_handler.py

def get_user_growth_units(user_id: int) -> List[Dict]:
    """Get all units for a user"""
    
def insert_growth_unit_with_user(user_id: int, name: str, location: str, data: Dict) -> int:
    """Create unit with user association"""
    
def count_plants_in_unit(unit_id: int) -> int:
    """Count plants in a unit"""
    
def count_sensors_in_unit(unit_id: int) -> int:
    """Count sensors in a unit"""
    
def is_camera_active(unit_id: int) -> bool:
    """Check if camera is active"""
    
def get_unit_last_activity(unit_id: int) -> Optional[datetime]:
    """Get last activity timestamp"""
```

### Phase 4: API Endpoint Updates

**Update UI Routes:**

```python
# app/blueprints/ui/routes.py

@ui_bp.route("/")
@login_required
def index():
    """Smart landing page"""
    user_id = get_current_user_id()
    routing = unit_service.determine_landing_page(user_id)
    
    if routing["route"] == "unit_selector":
        return redirect(url_for('ui.unit_selector'))
    else:
        session["selected_unit"] = routing["unit_id"]
        return redirect(url_for('ui.dashboard'))

@ui_bp.route("/units/select")
@login_required
def unit_selector():
    """Show unit selection page"""
    user_id = get_current_user_id()
    units = unit_service.get_user_units(user_id)
    
    # Enrich with card data
    unit_cards = [
        unit_service.get_unit_card_data(unit["unit_id"])
        for unit in units
    ]
    
    return render_template("unit_selector.html", units=unit_cards)

@ui_bp.post("/api/session/select-unit")
@login_required
def select_unit():
    """Store selected unit in session"""
    data = request.get_json()
    session["selected_unit"] = data["unit_id"]
    return jsonify({"success": True})
```

**Update Growth API:**

```python
# app/blueprints/api/growth.py

# Add user context to all operations

@growth_api.post("/units")
def create_unit():
    """Create unit with user association"""
    user_id = get_current_user_id()
    data = request.get_json()
    
    unit_id = unit_service.create_unit(
        user_id=user_id,
        name=data.get("name"),
        location=data.get("location"),
        dimensions=data.get("dimensions"),
        custom_image=data.get("custom_image")
    )
    
    return _success({"unit_id": unit_id})

@growth_api.get("/units")
def list_units():
    """List user's units"""
    user_id = get_current_user_id()
    units = unit_service.get_user_units(user_id)
    return _success(units)
```

### Phase 5: Background Workers

**Daily Growth Processing:**

```python
# tasks/growth_worker.py

from apscheduler.schedulers.background import BackgroundScheduler

scheduler = BackgroundScheduler()

@scheduler.scheduled_job('cron', hour=0, minute=0)  # Daily at midnight
def process_daily_growth():
    """Advance plant growth stages daily"""
    plant_service = PlantService(db)
    
    all_plants = plant_service.get_all_active_plants()
    for plant in all_plants:
        plant_service.advance_plant_growth(plant["plant_id"])

@scheduler.scheduled_job('interval', minutes=5)
def execute_schedules():
    """Execute scheduled tasks every 5 minutes"""
    schedule_service = ScheduleService(db)
    schedule_service.execute_scheduled_tasks()

scheduler.start()
```

---

## 📝 Migration Checklist

### Database Migration
- [ ] Add user_id column to growth_units
- [ ] Add dimensions, custom_image columns
- [ ] Create indexes
- [ ] Add foreign key constraints
- [ ] Migrate existing data (assign to default user)
- [ ] Test data integrity

### Service Layer
- [x] Create unit_service.py
- [ ] Create plant_service.py
- [ ] Create device_service.py
- [ ] Create camera_service.py
- [ ] Create schedule_service.py
- [ ] Add unit tests for each service

### Domain Models
- [ ] Create lightweight models/growth_unit.py
- [ ] Create models/plant.py
- [ ] Create models/device.py
- [ ] Move event_bus to events/

### API Updates
- [x] Update growth.py with user context
- [ ] Add session management endpoints
- [ ] Update all endpoints to use services
- [ ] Add API documentation

### UI Updates
- [x] Create unit_selector.html
- [ ] Create unit_selector.css
- [ ] Update base navigation
- [ ] Update index route with smart routing
- [ ] Test responsive design

### Background Jobs
- [ ] Create growth_worker.py
- [ ] Implement daily growth processing
- [ ] Implement schedule execution
- [ ] Add error handling and logging
- [ ] Configure APScheduler

### Testing
- [ ] Unit tests for services
- [ ] Integration tests for API
- [ ] E2E tests for UI flow
- [ ] Performance tests
- [ ] Load tests (multi-user)

### Documentation
- [x] Architecture documentation
- [ ] API documentation (Swagger/OpenAPI)
- [ ] User guide updates
- [ ] Developer onboarding guide

---

## 🎨 UI/UX Improvements

### Unit Selector Design

**Card Layout:**
```
┌────────────────────────────────────┐
│  [Custom Image or Default]         │
│  [Edit] [Camera]                   │
├────────────────────────────────────┤
│  Greenhouse A          📍 Indoor   │
│  120×180×80 cm (1728L)             │
│  🌱 5 plants  ⏰ 48h uptime       │
├────────────────────────────────────┤
│  [Plant1] [Plant2] [Plant3]        │
│  🍅 70%   🥬 45%   🌿 30%          │
│  (moisture rings around icons)     │
├────────────────────────────────────┤
│     [→ Open Dashboard]              │
└────────────────────────────────────┘
```

**Moisture Ring Colors:**
- Too Wet (80-100%): #0066cc (Dark Blue)
- Wet (60-80%): #00aaff (Light Blue)
- Normal (30-60%): #28a745 (Green)
- Dry (15-30%): #ffc107 (Yellow)
- Too Dry (0-15%): #dc3545 (Red)

### Responsive Breakpoints
- Desktop (>1200px): 3-column grid
- Tablet (768-1200px): 2-column grid
- Mobile (<768px): 1-column stack

---

## 🚀 Performance Optimization

### Caching Strategy
```python
# Redis caching for unit data
@cached(ttl=300)  # 5 minutes
def get_unit_card_data(unit_id):
    # Fetch from DB if not in cache
    pass

# Clear cache on updates
def update_unit(unit_id, data):
    result = db.update_unit(unit_id, data)
    cache.delete(f"unit:{unit_id}")
    return result
```

### Database Optimization
- Add indexes on frequently queried columns
- Use connection pooling
- Implement read replicas for scaling
- Use materialized views for statistics

### Lazy Loading
- Load plant details on demand
- Paginate large unit lists
- Defer non-critical data

---

## 🔐 Security Considerations

### Authorization
```python
def authorize_unit_access(user_id, unit_id):
    """Ensure user owns the unit"""
    unit = db.get_growth_unit(unit_id)
    if not unit or unit['user_id'] != user_id:
        raise UnauthorizedError()
```

### Input Validation
- Validate all user inputs
- Sanitize file uploads
- Check URL parameters
- Prevent SQL injection
- XSS protection

---

## 📊 Monitoring & Logging

### Key Metrics
- User login patterns
- Unit selection frequency
- API response times
- Background job execution
- Error rates

### Logging
```python
logger.info(f"User {user_id} created unit {unit_id}")
logger.warning(f"Unit {unit_id} threshold exceeded")
logger.error(f"Failed to update unit {unit_id}: {error}")
```

---

## 🎯 Success Criteria

### Phase 1 Complete When:
- ✅ Unit service fully functional
- ✅ Smart routing implemented
- ✅ Unit selector UI working
- ✅ Multi-user support enabled
- ✅ All tests passing

### Phase 2 Complete When:
- [ ] All services created
- [ ] Domain models refactored
- [ ] < 200 lines per class
- [ ] 90%+ test coverage

### Final Success When:
- [ ] All phases complete
- [ ] Performance benchmarks met
- [ ] User acceptance testing passed
- [ ] Documentation complete
- [ ] Production deployment successful

---

## 💡 Recommendations

### Immediate Actions (This Week)
1. ✅ Create unit_service.py (DONE)
2. Update database schema with user_id
3. Test unit selector UI
4. Implement smart routing

### Short Term (This Month)
1. Create remaining services
2. Refactor domain models
3. Add comprehensive tests
4. Deploy to staging

### Long Term (Next Quarter)
1. Performance optimization
2. Mobile app integration
3. Advanced analytics
4. Multi-language support

---

## 📞 Support & Questions

For technical questions or clarifications:
- Review this document
- Check inline code comments
- Consult architecture diagrams
- Ask senior engineering team

---

**Document Version**: 1.0
**Last Updated**: November 6, 2025
**Status**: Implementation In Progress
**Next Review**: After Phase 1 completion
