# 🚀 Quick Start: Multi-User Unit Selector
## Implementation Guide for SQLiteHandler Architecture

> **Updated for Container Pattern + SQLiteHandler**
> 
> Date: December 2024

---

## 📋 What's Already Done

✅ **Service Layer Created**
- `app/services/unit_service.py` - Complete with smart routing
- All database methods added to `GrowthOperations`
- Multi-user support implemented

✅ **UI Components Ready**
- `templates/unit_selector.html` - Visual unit selector
- `static/css/unit-selector.css` - Professional styling
- SVG moisture rings, responsive design

✅ **Database Methods Added**
- `get_user_growth_units()` 
- `insert_growth_unit_with_user()`
- `count_plants_in_unit()`
- `count_sensors_in_unit()`
- `count_actuators_in_unit()`
- `is_camera_active()`
- `get_unit_last_activity()`
- `get_unit_uptime_hours()`
- `get_plants_in_unit()`
- `update_unit_settings()`

---

## 🎯 Implementation Steps

### Step 1: Run Database Migration (10 minutes)

#### Option A: Using Python Script (Recommended)

```powershell
# Navigate to backend directory
cd e:\Work\SYSGrow\backend

# Run migration script
python infrastructure\database\migrations\run_migration.py sysgrow.db
```

**The script will:**
1. ✅ Show database info
2. ✅ Ask for confirmation
3. ✅ Create automatic backup with timestamp
4. ✅ Run migration SQL
5. ✅ Verify all columns added
6. ✅ Show results

#### Option B: Manual SQL Execution

```powershell
# Create backup first!
copy sysgrow.db "sysgrow.db.backup_$(Get-Date -Format 'yyyyMMdd_HHmmss')"

# Run SQL migration
sqlite3 sysgrow.db < infrastructure\database\migrations\add_multi_user_support.sql
```

#### Verify Migration

```powershell
sqlite3 sysgrow.db "PRAGMA table_info(GrowthUnits);"
```

**Expected new columns:**
- ✅ `user_id` - INTEGER NOT NULL DEFAULT 1
- ✅ `dimensions` - TEXT (JSON format)
- ✅ `custom_image` - TEXT  
- ✅ `created_at` - TIMESTAMP
- ✅ `updated_at` - TIMESTAMP
- ✅ `camera_active` - INTEGER DEFAULT 0

---

### Step 2: Register UnitService in Container (5 minutes)

Your project uses dependency injection. Find your container configuration file and add `UnitService`:

```python
# In your container configuration (likely app/container.py or similar)

from app.services.unit_service import UnitService

# In the container setup:
def create_container(db_handler):
    container = Container()
    
    # Existing services
    container.growth_service = GrowthService(db_handler)
    # ... other services ...
    
    # Add UnitService
    container.unit_service = UnitService(db_handler)
    
    return container
```

---

### Step 3: Add Smart Routing to Index Route (10 minutes)

Update `app/blueprints/ui/routes.py`:

```python
@ui_bp.route("/")
@login_required
def index():
    """Smart landing page with unit routing"""
    # Get current user ID from session
    user_id = session.get('user_id', 1)  # Default to user 1
    
    # Use UnitService for smart routing
    unit_service = _container().unit_service
    routing = unit_service.determine_landing_page(user_id)
    
    if routing["route"] == "unit_selector":
        # Multiple units - show selector
        return redirect(url_for('ui.unit_selector'))
    else:
        # Single unit or new user - go to dashboard
        session["selected_unit"] = routing["unit_id"]
        # Continue with existing dashboard logic
        selected_unit_id, units = _ensure_selected_unit()
        selected_unit = None
        plants = []
        thresholds = {}

        if selected_unit_id is not None:
            selected_unit = _container().growth_service.get_unit(selected_unit_id)
            plants = _container().growth_service.list_plants(selected_unit_id)
            thresholds = _container().growth_service.get_thresholds(selected_unit_id)

        return render_template(
            "index.html",
            units=units,
            selected_unit=selected_unit,
            plants=plants,
            thresholds=thresholds,
        )
```

---

### Step 4: Add Unit Selector Route (10 minutes)

Add this new route to `app/blueprints/ui/routes.py`:

```python
@ui_bp.route("/units/select")
@login_required
def unit_selector():
    """Show unit selection page for users with multiple units"""
    user_id = session.get('user_id', 1)
    
    unit_service = _container().unit_service
    units = unit_service.get_user_units(user_id)
    
    # Enrich with card data for visual display
    unit_cards = []
    for unit in units:
        try:
            card_data = unit_service.get_unit_card_data(unit["unit_id"])
            unit_cards.append(card_data)
        except Exception as e:
            current_app.logger.error(f"Error getting card data for unit {unit['unit_id']}: {e}")
            # Use basic unit data as fallback
            unit_cards.append(unit)
    
    return render_template("unit_selector.html", units=unit_cards)


@ui_bp.post("/api/session/select-unit")
@login_required
def api_select_unit():
    """API endpoint to store selected unit in session"""
    data = request.get_json() or {}
    unit_id = data.get("unit_id")
    
    if not unit_id:
        return {"error": "unit_id required"}, 400
    
    # Verify user owns this unit
    user_id = session.get('user_id', 1)
    unit_service = _container().unit_service
    
    try:
        unit = unit_service.get_unit_details(unit_id, user_id)
        if not unit:
            return {"error": "Unauthorized or unit not found"}, 403
        
        session["selected_unit"] = unit_id
        return {
            "success": True,
            "unit_id": unit_id,
            "redirect_url": url_for('ui.index')
        }
    except Exception as e:
        current_app.logger.error(f"Error selecting unit: {e}")
        return {"error": str(e)}, 500
```

---

### Step 5: Update Base Template CSS Link (2 minutes)

Add the unit selector CSS to `templates/base.html`:

```html
<head>
    <!-- Existing CSS -->
    <link rel="stylesheet" href="{{ url_for('static', filename='css/styles.css') }}">
    <link rel="stylesheet" href="{{ url_for('static', filename='css/dashboard.css') }}">
    
    <!-- Add this line: -->
    <link rel="stylesheet" href="{{ url_for('static', filename='css/unit-selector.css') }}">
</head>
```

---

### Step 6: Test the Implementation (15 minutes)

#### Test Scenario 1: New User (0 units)
```powershell
# Start the server
python smart_agriculture_app.py

# Login and navigate to /
# Expected: Creates "My First Growth Unit" → Redirects to dashboard
```

#### Test Scenario 2: Single Unit User  
```powershell
# Expected: Skips selector → Goes straight to dashboard
# Check session: print(session.get('selected_unit'))
```

#### Test Scenario 3: Multiple Units
```powershell
# Create a second unit via UI or API
# Navigate to /
# Expected: Redirects to /units/select
# Should see:
#   - Visual unit cards
#   - Custom images or gradients
#   - Plant previews with moisture rings
#   - Dimensions display
#   - "Open Dashboard" buttons
```

#### Test API Endpoints

```powershell
# Test get user units (adjust port if needed)
curl http://localhost:5000/api/growth/units `
  -H "Cookie: session=YOUR_SESSION"

# Test select unit
curl -X POST http://localhost:5000/api/session/select-unit `
  -H "Content-Type: application/json" `
  -H "Cookie: session=YOUR_SESSION" `
  -d '{"unit_id": 1}'
```

---

## 🐛 Troubleshooting

### Issue: "unit_service not found in container"

**Solution:**
```python
# Check your container setup
# Make sure UnitService is registered:
container.unit_service = UnitService(db_handler)
```

### Issue: "No such column: user_id"

**Solution:**
```powershell
# Migration didn't run. Re-run:
python infrastructure\database\migrations\run_migration.py sysgrow.db
```

### Issue: "Plants not showing in unit cards"

**Solution:**
```python
# Check if plants are linked to units
# In sqlite3:
SELECT * FROM GrowthUnitPlants WHERE unit_id = 1;

# If empty, link plants:
INSERT INTO GrowthUnitPlants (unit_id, plant_id) VALUES (1, 1);
```

### Issue: "CSS not loading"

**Solution:**
```powershell
# Verify file exists:
ls static\css\unit-selector.css

# Clear browser cache: Ctrl+Shift+R
# Check Flask is serving static files
```

---

## ✅ Verification Checklist

### Database
- [ ] Migration ran successfully
- [ ] GrowthUnits has `user_id` column
- [ ] GrowthUnits has `dimensions` column  
- [ ] GrowthUnits has `custom_image` column
- [ ] Indexes created on `user_id` and `created_at`
- [ ] Existing units have `user_id = 1`

### Backend
- [ ] `UnitService` registered in container
- [ ] All database methods work (test one)
- [ ] Index route has smart routing
- [ ] Unit selector route exists
- [ ] Session API endpoint works

### Frontend
- [ ] `unit_selector.html` exists
- [ ] `unit-selector.css` exists and linked
- [ ] CSS loads in browser (check DevTools)
- [ ] Unit cards display correctly
- [ ] Moisture rings show with colors

### Functionality
- [ ] Login redirects correctly based on unit count
- [ ] Unit selector displays for multiple units
- [ ] Can select a unit from selector
- [ ] Selected unit stored in session
- [ ] Dashboard loads with selected unit
- [ ] Can create new units
- [ ] Can edit unit details

---

## 📊 Quick Reference

### Project Structure

```
SYSGrow/backend/
├── app/
│   ├── services/
│   │   └── unit_service.py ✅
│   └── blueprints/
│       └── ui/
│           └── routes.py 🔄 UPDATE
├── infrastructure/
│   └── database/
│       ├── sqlite_handler.py ✅
│       ├── ops/
│       │   └── growth.py ✅ UPDATED
│       └── migrations/
│           ├── add_multi_user_support.sql ✅
│           └── run_migration.py ✅
├── templates/
│   ├── base.html 🔄 ADD CSS
│   └── unit_selector.html ✅
├── static/
│   └── css/
│       └── unit-selector.css ✅
└── sysgrow.db 🔄 MIGRATE
```

### New Database Methods Available

```python
# In GrowthOperations mixin:
db.get_user_growth_units(user_id)
db.insert_growth_unit_with_user(user_id, name, location, data)
db.update_unit_settings(unit_id, settings)
db.count_plants_in_unit(unit_id)
db.count_sensors_in_unit(unit_id)
db.count_actuators_in_unit(unit_id)
db.is_camera_active(unit_id)
db.get_unit_last_activity(unit_id)
db.get_unit_uptime_hours(unit_id)
db.get_plants_in_unit(unit_id)
```

### UnitService Methods Available

```python
from app.services.unit_service import UnitService

unit_service = UnitService(db_handler)

# Core operations
unit_service.get_user_units(user_id)
unit_service.get_unit_details(unit_id, user_id)
unit_service.create_unit(user_id, name, location, dimensions, custom_image)
unit_service.update_unit(unit_id, user_id, **updates)
unit_service.delete_unit(unit_id, user_id)

# Smart routing ⭐
routing = unit_service.determine_landing_page(user_id)
# Returns: {"route": "dashboard"|"unit_selector", "unit_id": int, ...}

# UI data
card_data = unit_service.get_unit_card_data(unit_id)
# Returns: {name, location, plants[], dimensions, camera_available, ...}

# Statistics
stats = unit_service.get_unit_statistics(unit_id)
# Returns: {plant_count, sensor_count, camera_active, uptime_hours, ...}
```

---

## 🎯 Expected Results

After completing all steps:

1. **New users** → Auto-create unit → Dashboard
2. **Single unit users** → Dashboard (no selector)
3. **Multi-unit users** → Beautiful selector → Choose → Dashboard
4. **Unit cards show:**
   - Custom image or gradient background
   - Dimensions (W×H×D, Volume)
   - Location badge
   - Plant count
   - Up to 6 plant previews with moisture rings
   - Camera indicator if available
   - "Open Dashboard" button

---

## 📞 Need Help?

### Common Questions

**Q: Where is the container configuration?**
A: Look for files like `app/container.py`, `app/di.py`, or check `smart_agriculture_app.py` for container setup.

**Q: How do I get user_id in session?**
A: Check your auth system. Typically set during login:
```python
session['user_id'] = user.id
```

**Q: Can I skip the unit selector for now?**
A: Yes! The existing code still works. The selector only shows when you have multiple units.

---

**Guide Version**: 2.0 (Updated for Container + SQLiteHandler)  
**Estimated Time**: 50-60 minutes  
**Difficulty**: Intermediate  
**Status**: Ready to implement
