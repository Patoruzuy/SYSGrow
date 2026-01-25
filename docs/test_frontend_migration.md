# Frontend Migration Test Guide

## Changes Made

### 1. Backend Route Update
✅ **File**: `app/blueprints/ui/routes.py`
- Updated `settings()` and `settings_view()` routes
- Now passes `selected_unit_id` and `units` to template
- Enables unit selection in settings page

### 2. Settings Page HTML Updates
✅ **File**: `templates/settings.html`

#### Added Unit Selector
- New section at top of Automation tab
- Dropdown to select which growth unit's schedules to manage
- Shows all available units
- Displays helpful message if no units exist

#### Updated Schedule Forms
- Added "Enable Schedule" checkbox for both light and fan
- Checkbox allows disabling schedules without deleting them
- Forms now work with unit-specific schedules

### 3. JavaScript Updates
✅ **File**: `templates/settings.html` (script section)

#### New Variables
- `GROWTH_API`: New API base path for Growth endpoints
- `currentUnitId`: Tracks currently selected unit
- `unitSelector`: Reference to unit dropdown

#### New Functions
- `growthApiRequest()`: Makes requests to Growth API
- `loadDeviceSchedules()`: Loads all device schedules for selected unit
- Unit selector change handler: Reloads schedules when unit changes

#### Updated Functions
- `loadLightSchedule()`: Now calls `loadDeviceSchedules()`
- `loadFanSchedule()`: Now calls `loadDeviceSchedules()`
- Light form submit: Uses Growth API with unit_id
- Fan form submit: Uses Growth API with unit_id

---

## Testing Steps

### Prerequisites
1. Ensure server is running
2. Have at least one growth unit created
3. Be logged in

### Test 1: Page Load
1. Navigate to `/settings`
2. Click on "Automation" tab
3. **Expected**: See unit selector dropdown at top
4. **Expected**: See your unit(s) listed in dropdown
5. **Expected**: See light and fan schedule forms below

### Test 2: Unit Selection
1. If you have multiple units, select different units from dropdown
2. **Expected**: Message appears: "Switched to unit X"
3. **Expected**: Schedule forms update with that unit's data

### Test 3: Save Light Schedule
1. Select a unit
2. Set light start time: `06:00`
3. Set light end time: `22:00`
4. Check "Enable Light Schedule"
5. Click "Save Light Schedule"
6. **Expected**: Success message appears
7. Refresh page
8. **Expected**: Times are saved correctly

### Test 4: Disable Schedule
1. Uncheck "Enable Light Schedule"
2. Click "Save Light Schedule"
3. **Expected**: Success message
4. **Expected**: Schedule is disabled but not deleted

### Test 5: Fan Schedule
1. Set fan start time: `08:00`
2. Set fan end time: `20:00`
3. Check "Enable Fan Schedule"
4. Click "Save Fan Schedule"
5. **Expected**: Success message
6. Refresh page
7. **Expected**: Times are saved correctly

### Test 6: API Verification
Open browser DevTools (F12) and check Network tab:

#### When loading schedules:
```
Request: GET /api/growth/units/1/schedules
Response: {
  "ok": true,
  "data": {
    "device_schedules": {
      "light": {
        "start_time": "06:00",
        "end_time": "22:00",
        "enabled": true
      },
      "fan": {
        "start_time": "08:00",
        "end_time": "20:00",
        "enabled": true
      }
    }
  }
}
```

#### When saving schedule:
```
Request: POST /api/growth/units/1/schedules
Body: {
  "device_type": "light",
  "start_time": "06:00",
  "end_time": "22:00",
  "enabled": true
}
Response: {
  "ok": true,
  "message": "Schedule saved successfully"
}
```

---

## API Comparison

### OLD (Deprecated) ⚠️
```javascript
// Load
GET /api/settings/light
Response: {
  "start_time": "06:00",
  "end_time": "22:00",
  "_deprecated": true
}

// Save
PUT /api/settings/light
Body: {
  "start_time": "06:00",
  "end_time": "22:00"
}
```

### NEW (Current) ✅
```javascript
// Load all schedules for unit
GET /api/growth/units/1/schedules
Response: {
  "ok": true,
  "data": {
    "device_schedules": {
      "light": {...},
      "fan": {...}
    }
  }
}

// Save schedule
POST /api/growth/units/1/schedules
Body: {
  "device_type": "light",
  "start_time": "06:00",
  "end_time": "22:00",
  "enabled": true
}
```

---

## Benefits of New Approach

### 1. Unit-Specific Schedules
- Each growth unit has its own schedules
- Different units can have different timing
- Perfect for multiple grow spaces

### 2. Enable/Disable
- Temporarily disable schedules
- No need to delete and recreate
- Preserves timing settings

### 3. Extensible
- Easy to add new device types (pump, heater, etc.)
- Unified API for all devices
- Consistent data structure

### 4. Better Organization
- All schedules in one place
- Single API call to get all schedules
- Cleaner code structure

---

## Troubleshooting

### Issue: "No units available" message
**Solution**: Create a growth unit first from the Units page

### Issue: Schedules not loading
**Check**: 
1. Browser console for errors
2. Network tab for failed requests
3. Make sure unit_id is valid

### Issue: "Please select a growth unit first"
**Solution**: Select a unit from dropdown before saving

### Issue: Old API still being called
**Solution**: 
1. Clear browser cache
2. Hard refresh (Ctrl+Shift+R)
3. Check that changes are deployed

---

## Migration Complete! 🎉

The frontend now uses:
✅ Unit-specific schedules via Growth API
✅ Enable/disable functionality
✅ Modern RESTful endpoints
✅ Backward-compatible (old API still works)
✅ Better user experience with unit selector

Old deprecated endpoints (`/api/settings/light`, `/api/settings/fan`) still work but return deprecation warnings.
