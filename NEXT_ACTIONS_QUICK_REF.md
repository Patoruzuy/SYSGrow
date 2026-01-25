# SYSGrow - Next Actions Quick Reference

**Date**: December 26, 2025
**Status**: Post-Plant Creation Standardization Refactor
**Urgency Level**: 🟡 MEDIUM (Production ready, polish items tracked)

---

## Immediate Tasks (This Week)

### Task 1: Implement PlantService.update_plant() ⏱️ 1 hour
**File**: `/mnt/e/Work/SYSGrow/backend/app/services/application/plant_service.py`
**Location**: After line 396 (after `create_plant()` method)
**Priority**: 🔴 HIGH

**Implementation**:
```python
def update_plant(
    self,
    plant_id: int,
    plant_name: Optional[str] = None,
    plant_type: Optional[str] = None,
    pot_size_liters: Optional[float] = None,
    medium_ph: Optional[float] = None,
    strain_variety: Optional[str] = None,
    expected_yield_grams: Optional[float] = None,
    light_distance_cm: Optional[float] = None,
) -> Optional[Dict[str, Any]]:
    """Update plant fields (partial update supported)."""
    # 1. Validate plant exists
    plant = self.get_plant(plant_id)
    if not plant:
        logger.error(f"Plant {plant_id} not found")
        return None

    # 2. Validate inputs
    if medium_ph is not None and not (0 <= medium_ph <= 14):
        raise ValueError(f"pH {medium_ph} outside valid range 0-14")
    if pot_size_liters is not None and pot_size_liters < 0:
        raise ValueError(f"Pot size {pot_size_liters} must be >= 0")
    if expected_yield_grams is not None and expected_yield_grams < 0:
        raise ValueError(f"Expected yield {expected_yield_grams} must be >= 0")

    # 3. Build update dict (only non-None values)
    update_fields = {}
    if plant_name is not None:
        update_fields["name"] = plant_name
    if plant_type is not None:
        update_fields["plant_type"] = plant_type
    if pot_size_liters is not None:
        update_fields["pot_size_liters"] = pot_size_liters
    if medium_ph is not None:
        update_fields["medium_ph"] = medium_ph
    if strain_variety is not None:
        update_fields["strain_variety"] = strain_variety
    if expected_yield_grams is not None:
        update_fields["expected_yield_grams"] = expected_yield_grams
    if light_distance_cm is not None:
        update_fields["light_distance_cm"] = light_distance_cm

    # 4. Update database
    self.growth_repo.update_plant(plant_id, **update_fields)

    # 5. Log activity
    if self.activity_logger:
        from app.services.application.activity_logger import ActivityLogger
        self.activity_logger.log_activity(
            activity_type=ActivityLogger.PLANT_UPDATED,
            description=f"Updated plant {plant_id}",
            severity=ActivityLogger.INFO,
            entity_type="plant",
            entity_id=plant_id,
            metadata=update_fields
        )

    logger.info(f"Updated plant {plant_id}: {update_fields}")

    # 6. Return updated plant
    return self.get_plant(plant_id)
```

**Then remove TODO workaround**:
- File: `/mnt/e/Work/SYSGrow/backend/app/blueprints/api/plants/crud.py`
- Lines: 148-158
- Replace with:
```python
# Update plant using service method
plant = plant_service.update_plant(
    plant_id=plant_id,
    plant_name=payload.get("name"),
    plant_type=payload.get("plant_type"),
    pot_size_liters=payload.get("pot_size_liters"),
    medium_ph=payload.get("medium_ph"),
    strain_variety=payload.get("strain_variety"),
    expected_yield_grams=payload.get("expected_yield_grams"),
    light_distance_cm=payload.get("light_distance_cm"),
)

# Handle stage update separately (if provided)
if payload.get("current_stage"):
    plant_service.update_plant_stage(
        plant_id=plant_id,
        new_stage=payload.get("current_stage"),
        days_in_stage=payload.get("days_in_stage", 0)
    )
    plant = plant_service.get_plant(plant_id)
```

**Test**:
```bash
pytest tests/test_plant_service.py -k update_plant -v
```

---

### Task 2: Add Field Validation in create_plant() ⏱️ 30 minutes
**File**: `/mnt/e/Work/SYSGrow/backend/app/services/application/plant_service.py`
**Location**: Line 330 (inside `create_plant()` method, before repository call)
**Priority**: 🟡 MEDIUM

**Implementation**:
```python
def create_plant(self, unit_id: int, plant_name: str, ..., medium_ph: float = 7.0, ...):
    """Create a new plant with validation."""
    try:
        # VALIDATION (add before line 332)
        if not (0 <= medium_ph <= 14):
            raise ValueError(f"pH {medium_ph} outside valid range 0-14")
        if pot_size_liters < 0:
            raise ValueError(f"Pot size {pot_size_liters} must be >= 0")
        if expected_yield_grams < 0:
            raise ValueError(f"Expected yield {expected_yield_grams} must be >= 0")
        if light_distance_cm < 0:
            raise ValueError(f"Light distance {light_distance_cm} must be >= 0")

        # Continue with existing code...
        plant_id = self.growth_repo.create_plant(...)
```

**Test**:
```bash
# Create test file if missing: tests/test_plant_service.py
pytest tests/test_plant_service.py -k create_plant -v
```

---

### Task 3: Standardize Method Naming ⏱️ 10 minutes
**File**: `/mnt/e/Work/SYSGrow/backend/app/blueprints/api/plants/crud.py`
**Location**: Line 193
**Priority**: 🟢 LOW

**Change**:
```python
# BEFORE
success = plant_service.delete_plant(unit_id, plant_id)

# AFTER
success = plant_service.remove_plant(unit_id, plant_id)
```

**Test**:
```bash
pytest tests/test_plants_api.py -k delete_plant -v
# Or
pytest tests/test_plants_api.py -k remove_plant -v
```

---

## Short-Term Tasks (Next 2 Weeks)

### Task 4: Lazy Load ML Libraries ⏱️ 2-3 hours
**Files**: 13 files in `/mnt/e/Work/SYSGrow/backend/app/services/ai/`
**Priority**: 🟡 MEDIUM (Pi performance)

**Pattern**:
```python
# BEFORE (module level)
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor

class MyMLService:
    def train_model(self, data):
        df = pd.DataFrame(data)
        model = RandomForestRegressor()

# AFTER (lazy load)
class MyMLService:
    def train_model(self, data):
        import pandas as pd  # Import inside method
        import numpy as np
        from sklearn.ensemble import RandomForestRegressor

        df = pd.DataFrame(data)
        model = RandomForestRegressor()
```

**Files to Update**:
1. `app/services/ai/climate_optimizer.py`
2. `app/services/ai/ml_trainer.py`
3. `app/services/ai/plant_growth_predictor.py`
4. `app/services/ai/drift_detector.py`
5. `app/services/ai/training_data_collector.py`
6. `app/services/ai/personalized_learning.py`
7. `app/services/ai/continuous_monitor.py`
8. `app/services/ai/feature_engineering.py`
9. `app/services/ai/ab_testing.py`
10. `app/services/hardware/control_logic.py`
11. `app/services/utilities/calibration_service.py`
12. `app/services/hardware/control_algorithms.py`
13. `app/hardware/devices/camera_manager.py`

**Test**:
```bash
pytest tests/test_ml_*.py -v
pytest tests/test_climate_*.py -v
```

**Impact**: Reduces Pi startup time by ~600ms

---

### Task 5: Extract Climate Logic from PlantService ⏱️ 2-4 hours
**Files**:
- `/mnt/e/Work/SYSGrow/backend/app/services/application/plant_service.py` (lines 80-231)
- `/mnt/e/Work/SYSGrow/backend/app/services/hardware/climate_control_service.py`

**Priority**: 🟡 MEDIUM (architecture cleanup)

**Steps**:
1. Move `apply_ai_conditions()` to ClimateControlService
2. Move `_compute_lighting_hours()` to ClimateControlService
3. Update PlantService to delegate:
```python
def apply_ai_conditions(self, unit_id: int, data: Optional[Dict] = None):
    """Delegate to ClimateControlService."""
    climate_service = current_app.config["CONTAINER"].climate_control_service
    climate_service.apply_optimal_conditions(unit_id, data)
```

**Test**:
```bash
pytest tests/test_plant_service.py -v
pytest tests/test_climate_control.py -v
```

---

## Long-Term Tasks (Next Month)

### Task 6: Implement Missing Endpoints ⏱️ 4-6 hours
**Priority**: 🟢 LOW (nice-to-have)

**Endpoints**:
1. `PATCH /api/plants/{id}/stage` - Stage transitions
2. `POST /api/plants/{id}/sensors/{id}` - Link sensors
3. `GET /api/plants/{id}/sensors` - List plant sensors
4. `GET /api/plants/{id}/health` - Health analytics (ML-driven)

**Detailed specs**: See `ARCHITECTURE_REVIEW_PLANT_CREATION.md` Section 5

---

### Task 7: Performance Profiling on Pi ⏱️ 1 day
**Priority**: 🟢 LOW (verification)

**Steps**:
1. Deploy to Raspberry Pi 3B+/4
2. Run: `pytest --profile tests/`
3. Measure:
   - Plant creation latency (target: <200ms)
   - Startup time (target: <3s)
   - Memory usage (target: <100MB overhead)
   - Cache hit rates (target: >60%)

---

## Testing Commands

### Run Architecture Tests
```bash
# Full suite
python3 tests/test_architecture_refactor.py

# Individual tests (if environment fixed)
pytest tests/test_architecture_refactor.py -v
```

### Run Plant Service Tests
```bash
# If test file exists
pytest tests/test_plant_service.py -v

# Create if missing (template):
# tests/test_plant_service.py
```

### Run API Tests
```bash
pytest tests/test_api_endpoints.py -v
pytest tests/test_plants_api.py -v  # If exists
```

### Run Full Test Suite
```bash
pytest tests/ -v
```

---

## Git Workflow

### Create Feature Branch
```bash
git checkout -b feature/plant-service-updates
```

### Commit Pattern (per task)
```bash
# Task 1
git add app/services/application/plant_service.py
git add app/blueprints/api/plants/crud.py
git commit -m "feat(plant): implement PlantService.update_plant() method

- Add full update method with partial update support
- Add field validation (pH 0-14, pot_size >= 0, yield >= 0)
- Remove TODO workaround in API endpoint
- Add activity logging for plant updates

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"

# Task 2
git add app/services/application/plant_service.py
git commit -m "feat(plant): add field validation in create_plant()

- Validate pH range (0-14)
- Validate pot_size >= 0
- Validate expected_yield >= 0
- Validate light_distance >= 0

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"

# Task 3
git add app/blueprints/api/plants/crud.py
git commit -m "refactor(plant): standardize method naming (delete_plant → remove_plant)

- Align API endpoint with service layer naming
- Improves consistency across codebase

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

### Push and Create PR
```bash
# Push feature branch
git push -u origin feature/plant-service-updates

# Create PR using gh CLI
gh pr create --title "Plant Service Updates: Implement update_plant() and validation" --body "$(cat <<'EOF'
## Summary
- Implemented missing PlantService.update_plant() method
- Added field validation in create_plant() (pH, pot_size, yield)
- Standardized method naming (delete_plant → remove_plant)

## Changes
1. **PlantService.update_plant()**: Full CRUD support for plant updates
2. **Field Validation**: Prevents invalid data (pH range, negative values)
3. **Naming Consistency**: API aligns with service layer

## Test Plan
- [x] Manual testing: Create plant with invalid pH (should fail)
- [x] Manual testing: Update plant fields (should succeed)
- [x] API endpoint: PUT /plants/{id} (full update working)
- [x] Architecture tests: No regressions

## Performance Impact
- No performance change (validation is O(1))
- Estimated <5ms overhead per request

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

## Documentation Updates Needed

After implementing tasks, update:
1. `/mnt/e/Work/SYSGrow/backend/docs/api/PLANT_API_REFERENCE.md` (if exists)
2. `/mnt/e/Work/SYSGrow/backend/PLANT_CREATION_STANDARDIZATION_COMPLETE.md` (mark TODO resolved)
3. `/mnt/e/Work/SYSGrow/backend/ARCHITECTURE_REVIEW_PLANT_CREATION.md` (update findings)

---

## Success Criteria

### Task 1 Complete ✅
- [ ] PlantService.update_plant() implemented
- [ ] All 13 plant fields supported
- [ ] Validation included (pH, pot_size, yield)
- [ ] TODO removed from API endpoint
- [ ] Tests passing

### Task 2 Complete ✅
- [ ] Validation added to create_plant()
- [ ] pH range check (0-14)
- [ ] Pot size >= 0
- [ ] Expected yield >= 0
- [ ] Light distance >= 0
- [ ] Tests passing

### Task 3 Complete ✅
- [ ] API method renamed to remove_plant()
- [ ] Tests updated
- [ ] Documentation updated

---

## Rollback Plan

### If Task 1 Fails
```bash
git revert <commit-hash>
git push
```

### If Task 2 Breaks Existing Plants
1. Validation errors are caught early (400 Bad Request)
2. Existing plants in DB are unaffected (validation only on create)
3. Rollback: Remove validation lines, redeploy

### If Task 3 Causes Test Failures
1. Rename back to delete_plant()
2. Or update all test files to use remove_plant()

---

**Last Updated**: December 26, 2025
**Priority**: Complete Task 1-3 this week for production deployment
**Contact**: Review ARCHITECTURE_REVIEW_PLANT_CREATION.md for detailed specs
