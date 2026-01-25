# 🔧 Implementation Steps for Unit Selector
## Exact Code Changes for SQLiteHandler Architecture

---

## Step 1: Update Container (5 minutes)

**File:** `app/services/container.py`

Add this import at the top:
```python
from app.services.unit_service import UnitService
```

Update the `@dataclass` class to include unit_service:
```python
@dataclass
class ServiceContainer:
    """Aggregate and manage core backend services."""

    config: AppConfig
    database: SQLiteDatabaseHandler
    settings_repo: SettingsRepository
    growth_repo: GrowthRepository
    device_repo: DeviceRepository
    analytics_repo: AnalyticsRepository
    audit_logger: AuditLogger
    plant_catalog: PlantJsonHandler
    auth_manager: UserAuthManager
    growth_service: GrowthService
    settings_service: SettingsService
    unit_service: UnitService  # ADD THIS LINE
    redis_client: Optional[redis.Redis]
    mqtt_client: Optional[MQTTClientWrapper]
```

Update the `build()` method to instantiate unit_service:
```python
@classmethod
def build(cls, config: AppConfig) -> "ServiceContainer":
    audit_logger = AuditLogger(config.audit_log_path, config.log_level)
    database = SQLiteDatabaseHandler(config.database_path)
    database.init_app(None)

    settings_repo = SettingsRepository(database)
    growth_repo = GrowthRepository(database)
    device_repo = DeviceRepository(database)
    analytics_repo = AnalyticsRepository(database)

    plant_catalog = PlantJsonHandler()

    redis_client: Optional[redis.Redis] = None
    if config.enable_redis:
        redis_client = redis.Redis.from_url(config.redis_url, decode_responses=True)

    mqtt_client: Optional[MQTTClientWrapper] = None
    if config.enable_mqtt:
        mqtt_client = MQTTClientWrapper(broker=config.mqtt_broker_host, port=config.mqtt_broker_port)

    auth_manager = UserAuthManager(database_handler=database, audit_logger=audit_logger)
    growth_service = GrowthService(repository=growth_repo, audit_logger=audit_logger)
    settings_service = SettingsService(repository=settings_repo)
    unit_service = UnitService(database=database)  # ADD THIS LINE

    return cls(
        config=config,
        database=database,
        settings_repo=settings_repo,
        growth_repo=growth_repo,
        device_repo=device_repo,
        analytics_repo=analytics_repo,
        audit_logger=audit_logger,
        plant_catalog=plant_catalog,
        auth_manager=auth_manager,
        growth_service=growth_service,
        settings_service=settings_service,
        unit_service=unit_service,  # ADD THIS LINE
        redis_client=redis_client,
        mqtt_client=mqtt_client,
    )
```

---

## Step 2: Update UI Routes (15 minutes)

**File:** `app/blueprints/ui/routes.py`

### 2A: Update the index route

**Replace the existing `index()` function with:**

```python
@ui_bp.route("/")
@login_required
def index():
    """Smart landing page with unit routing"""
    # Get current user ID from session (default to 1 if not using auth yet)
    user_id = session.get('user_id', 1)
    
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

### 2B: Add unit selector route

**Add these two new routes (you can add them after the `index()` route):**

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
    from flask import jsonify
    
    data = request.get_json() or {}
    unit_id = data.get("unit_id")
    
    if not unit_id:
        return jsonify({"error": "unit_id required"}), 400
    
    # Verify user owns this unit
    user_id = session.get('user_id', 1)
    unit_service = _container().unit_service
    
    try:
        unit = unit_service.get_unit_details(unit_id, user_id)
        if not unit:
            return jsonify({"error": "Unauthorized or unit not found"}), 403
        
        session["selected_unit"] = unit_id
        return jsonify({
            "success": True,
            "unit_id": unit_id,
            "redirect_url": url_for('ui.index')
        })
    except Exception as e:
        current_app.logger.error(f"Error selecting unit: {e}")
        return jsonify({"error": str(e)}), 500
```

---

## Step 3: Update Base Template (2 minutes)

**File:** `templates/base.html`

Find the `<head>` section and add the unit selector CSS:

```html
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}SYSGrow{% endblock %}</title>
    
    <!-- Existing CSS -->
    <link rel="stylesheet" href="{{ url_for('static', filename='css/styles.css') }}">
    <link rel="stylesheet" href="{{ url_for('static', filename='css/dashboard.css') }}">
    
    <!-- ADD THIS LINE: -->
    <link rel="stylesheet" href="{{ url_for('static', filename='css/unit-selector.css') }}">
    
    {% block extra_css %}{% endblock %}
</head>
```

---

## Step 4: Run Database Migration (10 minutes)

Open PowerShell in the backend directory and run:

```powershell
cd e:\Work\SYSGrow\backend

# Run migration (it will create backup automatically)
python infrastructure\database\migrations\run_migration.py sysgrow.db
```

**Expected output:**
```
╔══════════════════════════════════════════════════════════╗
║          Database Migration Tool                         ║
║          Add Multi-User Growth Unit Support              ║
╚══════════════════════════════════════════════════════════╝

Database: e:\Work\SYSGrow\backend\sysgrow.db
Size: 124.5 KB

Current schema for GrowthUnits table:
... (shows current columns)

This migration will:
  ✓ Add user_id column (multi-user support)
  ✓ Add dimensions column (JSON format)
  ✓ Add custom_image column
  ✓ Add camera_active column
  ✓ Add created_at/updated_at timestamps
  ✓ Create indexes for performance
  ✓ Preserve all existing data

Proceed with migration? (yes/no): yes

Creating backup: sysgrow.db.backup_20241215_143022
Backup created successfully!

Running migration...
✓ Migration completed successfully!

Verifying new schema...
✓ All expected columns present
✓ Indexes created successfully

Migration Results:
  Before: 5 columns
  After: 11 columns
  Growth units migrated: 3
  All units assigned to user_id=1

Migration completed successfully! ✅
```

---

## Step 5: Test the Implementation (15 minutes)

### 5A: Start the server

```powershell
python smart_agriculture_app.py
```

### 5B: Test scenarios

**Scenario 1: Single Unit User**
1. Open browser: `http://localhost:5000`
2. Login
3. **Expected:** Goes directly to dashboard (no selector)

**Scenario 2: Create Second Unit**
1. In dashboard, create a new growth unit
2. Navigate to home: `http://localhost:5000`
3. **Expected:** Redirects to `/units/select`
4. Should see unit selector with:
   - Two unit cards
   - Plant previews with moisture rings
   - Dimensions
   - "Open Dashboard" buttons

**Scenario 3: Select a Unit**
1. Click "Open Dashboard" on any unit
2. **Expected:** 
   - Redirects to `/`
   - Shows dashboard for selected unit
   - Unit stays selected in session

### 5C: Test API endpoint

```powershell
# Get your session cookie from browser DevTools (F12 → Application → Cookies)
# Then test the API:

curl -X POST http://localhost:5000/api/session/select-unit `
  -H "Content-Type: application/json" `
  -H "Cookie: session=YOUR_SESSION_COOKIE_HERE" `
  -d '{"unit_id": 1}'

# Expected response:
# {
#   "success": true,
#   "unit_id": 1,
#   "redirect_url": "/"
# }
```

---

## Troubleshooting

### Problem: "unit_service not found"

**Check container.py:**
```python
# Make sure you added:
from app.services.unit_service import UnitService

# In the dataclass:
unit_service: UnitService

# In build() method:
unit_service = UnitService(database=database)

# In return statement:
unit_service=unit_service,
```

### Problem: "No such column: user_id"

**Re-run migration:**
```powershell
python infrastructure\database\migrations\run_migration.py sysgrow.db
```

### Problem: CSS not loading

**Check these:**
1. File exists: `ls static\css\unit-selector.css`
2. Added to base.html: `<link rel="stylesheet" href="{{ url_for('static', filename='css/unit-selector.css') }}">`
3. Clear browser cache: `Ctrl+Shift+R`
4. Check DevTools Console for 404 errors

### Problem: "Plants not showing in cards"

**Check database:**
```powershell
sqlite3 sysgrow.db

# Check if plants are linked to units:
SELECT * FROM GrowthUnitPlants WHERE unit_id = 1;

# If empty, the plants table might not be populated
# Check if plants exist:
SELECT * FROM Plants LIMIT 5;
```

---

## Quick Verification

After implementing, run through this checklist:

### Database
- [ ] Migration ran successfully
- [ ] GrowthUnits has `user_id` column
- [ ] Existing units have `user_id = 1`
- [ ] Indexes exist on `user_id` and `created_at`

### Backend
- [ ] `container.py` imports UnitService
- [ ] `container.py` has `unit_service` field
- [ ] `container.py` instantiates unit_service in `build()`
- [ ] `routes.py` index route uses smart routing
- [ ] `routes.py` has `unit_selector()` route
- [ ] `routes.py` has `api_select_unit()` endpoint

### Frontend  
- [ ] `templates/unit_selector.html` exists
- [ ] `static/css/unit-selector.css` exists
- [ ] `templates/base.html` links to unit-selector.css

### Testing
- [ ] Server starts without errors
- [ ] Single unit → goes to dashboard
- [ ] Multiple units → shows selector
- [ ] Can select a unit from selector
- [ ] Selected unit persists in session
- [ ] Unit cards display correctly
- [ ] Plant moisture rings show up

---

## Complete File List

Files you need to modify:
1. ✏️ `app/services/container.py` - Add UnitService
2. ✏️ `app/blueprints/ui/routes.py` - Add smart routing + new routes
3. ✏️ `templates/base.html` - Add CSS link

Files already created:
1. ✅ `app/services/unit_service.py`
2. ✅ `templates/unit_selector.html`
3. ✅ `static/css/unit-selector.css`
4. ✅ `infrastructure/database/ops/growth.py` (updated with 10 new methods)
5. ✅ `infrastructure/database/migrations/add_multi_user_support.sql`
6. ✅ `infrastructure/database/migrations/run_migration.py`

Database:
1. 🔄 `sysgrow.db` - Run migration

---

## Next Steps After Implementation

Once everything works:

1. **Add Unit Management UI**
   - Create/Edit/Delete unit forms
   - Upload custom images
   - Edit dimensions

2. **Enhance Unit Selector**
   - Sorting options (recent, alphabetical)
   - Search/filter
   - Favorites

3. **Multi-User Auth**
   - Ensure `user_id` comes from auth system
   - Add user registration/login
   - User-specific unit isolation

4. **Analytics**
   - Unit activity tracking
   - Most-used unit
   - Plant health across units

---

**Implementation Time:** ~45 minutes
**Difficulty:** Intermediate
**Status:** Ready to implement ✅
