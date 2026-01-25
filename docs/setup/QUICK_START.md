# 🚀 Quick Start Guide
## Implementing the Unit Selector Feature

> **Step-by-Step Implementation Guide**
> 
> Get the new service-based architecture up and running in your SYSGrow system

---

## 📋 Prerequisites

Before you begin, ensure you have:

- ✅ Python 3.8+ installed
- ✅ Flask application running
- ✅ SQLite database (`sysgrow.db`)
- ✅ Basic understanding of Flask blueprints
- ✅ Access to the backend codebase

---

## 🎯 What You're Building

### User Experience Flow

```
User logs in
     ↓
Landing page (/)
     ↓
┌────────────────────────────────┐
│  UnitService.determine_       │
│  landing_page(user_id)         │
└────────────────────────────────┘
     ↓
┌────────────────┬────────────────┬────────────────┐
│ 0 units        │ 1 unit         │ 2+ units       │
│ Create default │ Go to dashboard│ Show selector  │
│ → dashboard    │                │                │
└────────────────┴────────────────┴────────────────┘
```

### Visual Result

**Multiple Units (2+):**
- Beautiful grid of unit cards
- Custom images with overlay buttons
- Plant preview with moisture rings
- Responsive design (3→2→1 columns)

**Single Unit:**
- Skip selector, go straight to dashboard
- Seamless UX, no extra clicks

**New User:**
- Auto-create "My First Growth Unit"
- Go to dashboard immediately

---

## 📦 What's Already Done

### ✅ Created Files

```
backend/
├── app/
│   └── services/
│       └── unit_service.py ✅ DONE
├── static/
│   └── css/
│       └── unit-selector.css ✅ DONE (1000+ lines)
├── templates/
│   └── unit_selector.html ✅ DONE
├── migrations/
│   └── add_user_id_to_growth_units.sql ✅ DONE
├── REFACTORING_PLAN.md ✅ DONE
├── IMPLEMENTATION_COMPLETE.md ✅ DONE
└── DESIGN_GUIDE.md ✅ DONE
```

### ✅ Existing Files Updated

```
templates/base.html - Navigation already has Growth Units link ✅
app/blueprints/api/growth.py - 25 endpoints consolidated ✅
```

---

## 🔧 Step-by-Step Implementation

### Step 1: Database Migration (15 minutes)

#### 1.1 Backup Your Database
```bash
# Create backup
cp sysgrow.db sysgrow.db.backup.$(date +%Y%m%d_%H%M%S)

# Verify backup exists
ls -lh sysgrow.db*
```

#### 1.2 Run Migration Script
```bash
# Option A: Using sqlite3 command line
sqlite3 sysgrow.db < migrations/add_user_id_to_growth_units.sql

# Option B: Using Python
python3 << 'EOF'
import sqlite3
conn = sqlite3.connect('sysgrow.db')
with open('migrations/add_user_id_to_growth_units.sql', 'r') as f:
    conn.executescript(f.read())
conn.close()
print("✅ Migration complete!")
EOF
```

#### 1.3 Verify Migration
```bash
sqlite3 sysgrow.db << 'EOF'
-- Check table structure
PRAGMA table_info(growth_units);

-- Check indexes
SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='growth_units';

-- Check data
SELECT unit_id, name, user_id, dimensions FROM growth_units;
EOF
```

**Expected Output:**
```
unit_id | name           | user_id | dimensions
--------|----------------|---------|------------------------------------------
1       | Main Unit      | 1       | {"width":120,"length":180,"height":80}
```

### Step 2: Update Database Handler (20 minutes)

#### 2.1 Open `database/database_handler.py`

#### 2.2 Add New Methods

```python
# Add these methods to DatabaseHandler class

def get_user_growth_units(self, user_id: int) -> List[Dict]:
    """Get all growth units for a specific user"""
    cursor = self.conn.cursor()
    cursor.execute("""
        SELECT 
            unit_id, 
            name, 
            location, 
            dimensions, 
            custom_image,
            is_active,
            camera_active,
            created_at,
            updated_at
        FROM growth_units 
        WHERE user_id = ? AND is_active = 1
        ORDER BY created_at DESC
    """, (user_id,))
    
    columns = [desc[0] for desc in cursor.description]
    results = [dict(zip(columns, row)) for row in cursor.fetchall()]
    
    # Parse JSON dimensions
    import json
    for unit in results:
        if unit['dimensions']:
            unit['dimensions'] = json.loads(unit['dimensions'])
    
    return results

def insert_growth_unit_with_user(self, user_id: int, name: str, 
                                 location: str, data: Dict) -> int:
    """Create a new growth unit with user association"""
    import json
    cursor = self.conn.cursor()
    
    dimensions_json = json.dumps(data.get('dimensions')) if data.get('dimensions') else None
    
    cursor.execute("""
        INSERT INTO growth_units 
        (user_id, name, location, dimensions, custom_image, 
         is_active, created_at)
        VALUES (?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
    """, (user_id, name, location, dimensions_json, 
          data.get('custom_image')))
    
    self.conn.commit()
    return cursor.lastrowid

def count_plants_in_unit(self, unit_id: int) -> int:
    """Count active plants in a unit"""
    cursor = self.conn.cursor()
    cursor.execute("""
        SELECT COUNT(*) 
        FROM plants 
        WHERE unit_id = ? AND active = 1
    """, (unit_id,))
    return cursor.fetchone()[0]

def count_sensors_in_unit(self, unit_id: int) -> int:
    """Count sensors linked to a unit"""
    cursor = self.conn.cursor()
    cursor.execute("""
        SELECT COUNT(*) 
        FROM device_unit_links 
        WHERE unit_id = ? AND device_type = 'sensor'
    """, (unit_id,))
    result = cursor.fetchone()
    return result[0] if result else 0

def is_camera_active(self, unit_id: int) -> bool:
    """Check if camera is active for a unit"""
    cursor = self.conn.cursor()
    cursor.execute("""
        SELECT camera_active 
        FROM growth_units 
        WHERE unit_id = ?
    """, (unit_id,))
    result = cursor.fetchone()
    return bool(result[0]) if result else False

def get_unit_last_activity(self, unit_id: int) -> Optional[str]:
    """Get last activity timestamp for a unit"""
    cursor = self.conn.cursor()
    cursor.execute("""
        SELECT MAX(timestamp) 
        FROM sensor_data 
        WHERE unit_id = ?
    """, (unit_id,))
    result = cursor.fetchone()
    return result[0] if result and result[0] else None
```

#### 2.3 Test Database Methods

```python
# test_db_methods.py
from database.database_handler import DatabaseHandler

db = DatabaseHandler()

# Test get user units
units = db.get_user_growth_units(user_id=1)
print(f"✅ Found {len(units)} units for user 1")

# Test create unit
unit_id = db.insert_growth_unit_with_user(
    user_id=1,
    name="Test Unit",
    location="Indoor",
    data={
        "dimensions": {"width": 120, "length": 180, "height": 80},
        "custom_image": None
    }
)
print(f"✅ Created unit with ID: {unit_id}")

# Test count methods
plant_count = db.count_plants_in_unit(unit_id)
sensor_count = db.count_sensors_in_unit(unit_id)
print(f"✅ Unit has {plant_count} plants and {sensor_count} sensors")
```

### Step 3: Update UI Routes (25 minutes)

#### 3.1 Open `app/blueprints/ui/routes.py`

#### 3.2 Add Imports
```python
from flask import session, redirect, url_for
from app.services.unit_service import UnitService
```

#### 3.3 Add Helper Function
```python
def get_current_user_id():
    """Get current user ID from session"""
    # TODO: Update this based on your auth system
    user = session.get('user')
    if user:
        # If you store user ID in session
        return session.get('user_id', 1)
    return 1  # Default user for now
```

#### 3.4 Update Index Route
```python
@ui_bp.route("/")
@login_required
def index():
    """Smart landing page - routes based on unit count"""
    from database.database_handler import DatabaseHandler
    
    user_id = get_current_user_id()
    db = DatabaseHandler()
    unit_service = UnitService(db)
    
    # Determine where to route the user
    routing = unit_service.determine_landing_page(user_id)
    
    if routing["route"] == "unit_selector":
        # Multiple units - show selector
        return redirect(url_for('ui.unit_selector'))
    else:
        # Single unit or new user - go to dashboard
        session["selected_unit"] = routing["unit_id"]
        return redirect(url_for('ui.dashboard'))
```

#### 3.5 Add Unit Selector Route
```python
@ui_bp.route("/units/select")
@login_required
def unit_selector():
    """Show unit selection page for users with multiple units"""
    from database.database_handler import DatabaseHandler
    
    user_id = get_current_user_id()
    db = DatabaseHandler()
    unit_service = UnitService(db)
    
    # Get all user's units
    units = unit_service.get_user_units(user_id)
    
    # Enrich with card data for visual display
    unit_cards = []
    for unit in units:
        try:
            card_data = unit_service.get_unit_card_data(unit["unit_id"])
            unit_cards.append(card_data)
        except Exception as e:
            print(f"Error getting card data for unit {unit['unit_id']}: {e}")
            # Add basic unit info as fallback
            unit_cards.append(unit)
    
    return render_template("unit_selector.html", units=unit_cards)
```

#### 3.6 Add Session Management Endpoint
```python
@ui_bp.route("/api/session/select-unit", methods=["POST"])
@login_required
def select_unit():
    """Store selected unit in session"""
    from flask import jsonify
    from database.database_handler import DatabaseHandler
    
    data = request.get_json()
    unit_id = data.get("unit_id")
    
    if not unit_id:
        return jsonify({"error": "unit_id required"}), 400
    
    # Verify user owns this unit
    user_id = get_current_user_id()
    db = DatabaseHandler()
    unit_service = UnitService(db)
    
    try:
        unit = unit_service.get_unit_details(unit_id, user_id)
        if not unit:
            return jsonify({"error": "Unauthorized"}), 403
        
        session["selected_unit"] = unit_id
        return jsonify({
            "success": True, 
            "unit_id": unit_id,
            "redirect_url": url_for('ui.dashboard')
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500
```

### Step 4: Update API Endpoints (15 minutes)

#### 4.1 Open `app/blueprints/api/growth.py`

#### 4.2 Update Unit Endpoints

```python
from flask import session
from app.services.unit_service import UnitService

def get_current_user_id():
    """Get current user ID from session"""
    return session.get('user_id', 1)

# Update/add these endpoints:

@growth_api.route("/units", methods=["POST"])
def create_unit():
    """Create a new growth unit"""
    user_id = get_current_user_id()
    data = request.get_json()
    
    db = DatabaseHandler()
    unit_service = UnitService(db)
    
    try:
        unit_id = unit_service.create_unit(
            user_id=user_id,
            name=data.get("name", "New Growth Unit"),
            location=data.get("location", "Indoor"),
            dimensions=data.get("dimensions"),
            custom_image=data.get("custom_image")
        )
        
        return jsonify({
            "success": True,
            "unit_id": unit_id,
            "message": "Unit created successfully"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@growth_api.route("/units", methods=["GET"])
def list_units():
    """List all units for current user"""
    user_id = get_current_user_id()
    
    db = DatabaseHandler()
    unit_service = UnitService(db)
    
    units = unit_service.get_user_units(user_id)
    return jsonify({"success": True, "units": units})

@growth_api.route("/units/<int:unit_id>", methods=["GET"])
def get_unit(unit_id):
    """Get unit details"""
    user_id = get_current_user_id()
    
    db = DatabaseHandler()
    unit_service = UnitService(db)
    
    unit = unit_service.get_unit_details(unit_id, user_id)
    if not unit:
        return jsonify({"error": "Unit not found"}), 404
    
    return jsonify({"success": True, "unit": unit})

@growth_api.route("/units/<int:unit_id>", methods=["PUT"])
def update_unit(unit_id):
    """Update unit configuration"""
    user_id = get_current_user_id()
    data = request.get_json()
    
    db = DatabaseHandler()
    unit_service = UnitService(db)
    
    success = unit_service.update_unit(unit_id, user_id, data)
    if not success:
        return jsonify({"error": "Update failed"}), 400
    
    return jsonify({"success": True, "message": "Unit updated"})

@growth_api.route("/units/<int:unit_id>", methods=["DELETE"])
def delete_unit(unit_id):
    """Delete a growth unit"""
    user_id = get_current_user_id()
    
    db = DatabaseHandler()
    unit_service = UnitService(db)
    
    success = unit_service.delete_unit(unit_id, user_id)
    if not success:
        return jsonify({"error": "Delete failed"}), 400
    
    return jsonify({"success": True, "message": "Unit deleted"})
```

### Step 5: Update Base Template (5 minutes)

#### 5.1 Add CSS Link

Open `templates/base.html` and add:

```html
<head>
    <!-- Existing CSS links -->
    <link rel="stylesheet" href="{{ url_for('static', filename='css/styles.css') }}">
    <link rel="stylesheet" href="{{ url_for('static', filename='css/dashboard.css') }}">
    <link rel="stylesheet" href="{{ url_for('static', filename='css/navigation.css') }}">
    
    <!-- Add this line: -->
    <link rel="stylesheet" href="{{ url_for('static', filename='css/unit-selector.css') }}">
</head>
```

### Step 6: Test the Implementation (20 minutes)

#### 6.1 Start the Server
```bash
python smart_agriculture_app.py
# or
flask run
```

#### 6.2 Test Scenarios

**Scenario 1: New User (0 units)**
1. Login as new user
2. Navigate to `/`
3. ✅ Should create default unit
4. ✅ Should redirect to dashboard

**Scenario 2: Single Unit**
1. Login as user with 1 unit
2. Navigate to `/`
3. ✅ Should redirect directly to dashboard
4. ✅ Selected unit should be in session

**Scenario 3: Multiple Units**
1. Create a second unit via API or UI
2. Logout and login again
3. Navigate to `/`
4. ✅ Should redirect to `/units/select`
5. ✅ Should show unit selector page
6. ✅ Cards should display with images, plants, etc.
7. Click "Open Dashboard" on a unit
8. ✅ Should navigate to dashboard with that unit selected

#### 6.3 Test API Endpoints

```bash
# List units
curl -X GET http://localhost:5000/api/growth/units \
  -H "Cookie: session=YOUR_SESSION_COOKIE"

# Create unit
curl -X POST http://localhost:5000/api/growth/units \
  -H "Content-Type: application/json" \
  -H "Cookie: session=YOUR_SESSION_COOKIE" \
  -d '{
    "name": "Greenhouse B",
    "location": "Outdoor",
    "dimensions": {
      "width": 150,
      "length": 200,
      "height": 100
    }
  }'

# Get unit details
curl -X GET http://localhost:5000/api/growth/units/1 \
  -H "Cookie: session=YOUR_SESSION_COOKIE"

# Update unit
curl -X PUT http://localhost:5000/api/growth/units/1 \
  -H "Content-Type: application/json" \
  -H "Cookie: session=YOUR_SESSION_COOKIE" \
  -d '{
    "name": "Updated Name",
    "location": "Indoor"
  }'

# Delete unit
curl -X DELETE http://localhost:5000/api/growth/units/1 \
  -H "Cookie: session=YOUR_SESSION_COOKIE"
```

---

## 🐛 Troubleshooting

### Issue: "Unit selector shows but no units appear"

**Solution:**
```python
# Check if user_id is correct
from database.database_handler import DatabaseHandler
db = DatabaseHandler()
units = db.get_user_growth_units(user_id=1)
print(f"Units for user 1: {units}")
```

### Issue: "Database error: no such column: user_id"

**Solution:**
```bash
# Migration didn't run correctly. Re-run:
sqlite3 sysgrow.db < migrations/add_user_id_to_growth_units.sql
```

### Issue: "Plants not showing in unit cards"

**Solution:**
```python
# Check if plants have unit_id
db = DatabaseHandler()
plants = db.get_plants_by_unit(unit_id=1)
print(f"Plants in unit 1: {plants}")

# If empty, link plants to units:
db.update_plant(plant_id=1, updates={"unit_id": 1})
```

### Issue: "CSS not loading"

**Solution:**
```bash
# Clear browser cache (Ctrl+Shift+R)
# Verify file exists:
ls -lh static/css/unit-selector.css

# Check Flask routing:
curl http://localhost:5000/static/css/unit-selector.css
```

### Issue: "Smart routing not working"

**Solution:**
```python
# Check session management
from flask import session
print(f"User ID in session: {session.get('user_id')}")
print(f"Selected unit: {session.get('selected_unit')}")

# Verify UnitService logic
from app.services.unit_service import UnitService
from database.database_handler import DatabaseHandler

db = DatabaseHandler()
service = UnitService(db)
routing = service.determine_landing_page(user_id=1)
print(f"Routing result: {routing}")
```

---

## ✅ Verification Checklist

After implementation, verify:

### Database
- [ ] `growth_units` table has `user_id` column
- [ ] `growth_units` table has `dimensions` column
- [ ] `growth_units` table has `custom_image` column
- [ ] Indexes created on `user_id` and `is_active`
- [ ] Foreign key constraint exists (optional)
- [ ] Existing units have `user_id = 1`

### Backend
- [ ] `DatabaseHandler` has new methods
- [ ] `UnitService` imported in routes
- [ ] Index route has smart routing logic
- [ ] Unit selector route exists
- [ ] Session management endpoint works
- [ ] API endpoints include user context

### Frontend
- [ ] `unit_selector.html` exists in templates
- [ ] `unit-selector.css` exists in static/css
- [ ] CSS linked in `base.html`
- [ ] Navigation has "Growth Units" link

### Functionality
- [ ] Login redirects correctly based on unit count
- [ ] Unit selector displays all user's units
- [ ] Unit cards show images, dimensions, plants
- [ ] Moisture rings display with colors
- [ ] Create unit modal works
- [ ] Edit unit modal works
- [ ] Select unit stores in session
- [ ] Dashboard uses selected unit

### User Experience
- [ ] Responsive design works (desktop/tablet/mobile)
- [ ] Hover effects work on cards and buttons
- [ ] Loading states display during API calls
- [ ] Error messages display for failures
- [ ] Empty state shows for new users
- [ ] Keyboard navigation works
- [ ] Screen reader compatible

---

## 📚 Next Steps

### Immediate (Week 1)
1. ✅ Complete this quick start implementation
2. Test with real users
3. Gather feedback
4. Fix any bugs

### Short Term (Week 2-3)
1. Implement `PlantService`
2. Implement `DeviceService`
3. Add camera streaming to unit cards
4. Add real-time updates via WebSocket

### Long Term (Month 2+)
1. Mobile app integration
2. Advanced analytics per unit
3. Multi-language support
4. Unit templates (presets)
5. Unit sharing between users

---

## 💡 Pro Tips

### Performance
- Cache unit data for 5 minutes
- Lazy load plant images
- Paginate if >20 units
- Use database indexes

### Security
- Always verify user ownership
- Sanitize file uploads
- Validate JSON dimensions
- Use CSRF tokens

### UX
- Show loading spinners
- Provide helpful error messages
- Add empty states
- Use optimistic UI updates

### Maintenance
- Log all user actions
- Monitor API response times
- Track unit creation patterns
- Backup database daily

---

## 🎓 Learning Resources

### Code Examples
- Check `app/services/unit_service.py` for service pattern
- Check `templates/unit_selector.html` for UI patterns
- Check `static/css/unit-selector.css` for design system

### Documentation
- `REFACTORING_PLAN.md` - Architecture overview
- `IMPLEMENTATION_COMPLETE.md` - Detailed implementation status
- `DESIGN_GUIDE.md` - Visual design specifications

---

## 📞 Need Help?

### Common Questions

**Q: How do I add more users?**
A: Use your existing user registration system. The `user_id` will automatically link units to users.

**Q: Can users share units?**
A: Not yet. Implement a `unit_permissions` table for sharing in the future.

**Q: How do I change the default unit dimensions?**
A: Edit the dimensions in `UnitService.create_unit()` method.

**Q: Can I use PostgreSQL instead of SQLite?**
A: Yes! Update `DatabaseHandler` connection and adjust SQL syntax.

---

**Guide Version**: 1.0  
**Estimated Time**: 90-120 minutes  
**Difficulty**: Intermediate  
**Status**: Production Ready
