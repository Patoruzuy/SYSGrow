# API Migration Guide - Phase 5

## Overview
Phase 5 reorganizes the SYSGrow API structure for consistency, maintainability, and RESTful design. This guide helps you migrate client code to the new URL patterns.

**Date:** December 7, 2025  
**Status:** Active Migration Required  
**Backward Compatibility:** Breaking changes - clients must update

---

## Quick Reference

### URL Changes Summary

| API Section | Old URL | New URL | Status |
|-------------|---------|---------|--------|
| Sensors API | `/api/*` | `/api/sensors/*` | ✅ Changed |
| Disease API | `/api/*` | `/api/disease/*` | ✅ Changed |
| Agriculture API | `/api/v1/plants/*` | `/api/v1/agriculture/*` | ✅ Changed |
| ESP32 Devices | `/api/esp32-c3/*` | `/api/devices/esp32/*` | ✅ Changed |
| ESP32 Settings | `/api/settings/esp32-c3/*` | `/api/devices/esp32/*` | ✅ Consolidated |
| Health API | `/api/health/*` | `/api/health/*` | ✅ No change |

---

## Step 1: Sensors API Migration

### Old URLs (❌ No longer work)
```javascript
// List sensor history
GET /api/sensor_history?start_date=...&end_date=...
```

### New URLs (✅ Use these)
```javascript
// List sensor history
GET /api/sensors/sensor_history?start_date=...&end_date=...
```

### Migration Code Examples

#### JavaScript/TypeScript
```javascript
// OLD ❌
const response = await fetch('/api/sensor_history?start_date=2025-01-01');

// NEW ✅
const response = await fetch('/api/sensors/sensor_history?start_date=2025-01-01');
```

#### Python
```python
# OLD ❌
response = requests.get('/api/sensor_history', params={'start_date': '2025-01-01'})

# NEW ✅
response = requests.get('/api/sensors/sensor_history', params={'start_date': '2025-01-01'})
```

#### Dart (Flutter)
```dart
// OLD ❌
final response = await http.get(Uri.parse('$baseUrl/api/sensor_history?start_date=2025-01-01'));

// NEW ✅
final response = await http.get(Uri.parse('$baseUrl/api/sensors/sensor_history?start_date=2025-01-01'));
```

---

## Step 2: Disease API Migration

### Old URLs (❌ No longer work)
```
GET /api/disease/risks
POST /api/disease/analyze
```

### New URLs (✅ Use these)
```
GET /api/disease/disease/risks
POST /api/disease/analyze
```

### Migration Code Examples

#### JavaScript/TypeScript
```javascript
// OLD ❌
const risks = await fetch('/api/disease/risks');

// NEW ✅
const risks = await fetch('/api/disease/disease/risks');
```

---

## Step 3: Agriculture API Migration

### Old URLs (❌ No longer work)
```
GET /api/v1/plants/growth
POST /api/v1/plants/irrigation
```

### New URLs (✅ Use these)
```
GET /api/v1/agriculture/growth
POST /api/v1/agriculture/irrigation
```

### Migration Code Examples

#### JavaScript/TypeScript
```javascript
// OLD ❌
const growth = await fetch('/api/v1/plants/growth');
const result = await fetch('/api/v1/plants/irrigation', {
  method: 'POST',
  body: JSON.stringify({ duration: 30 })
});

// NEW ✅
const growth = await fetch('/api/v1/agriculture/growth');
const result = await fetch('/api/v1/agriculture/irrigation', {
  method: 'POST',
  body: JSON.stringify({ duration: 30 })
});
```

---

## Step 4: ESP32 Devices API Migration (Major Changes)

### Old URLs (❌ No longer work)
```
GET /api/esp32-c3/devices
POST /api/esp32-c3/devices
GET /api/esp32-c3/devices/<device_id>
PUT /api/esp32-c3/devices/<device_id>
DELETE /api/esp32-c3/devices/<device_id>

POST /api/esp32-c3/devices/<device_id>/status
POST /api/esp32-c3/devices/<device_id>/command
POST /api/esp32-c3/devices/<device_id>/restart

POST /api/esp32-c3/devices/<device_id>/sensors/read
POST /api/esp32-c3/devices/<device_id>/sensors/enable
POST /api/esp32-c3/devices/<device_id>/sensors/disable

POST /api/esp32-c3/devices/<device_id>/calibration
POST /api/esp32-c3/devices/<device_id>/calibration/soil/<idx>/dry
POST /api/esp32-c3/devices/<device_id>/calibration/soil/<idx>/wet
POST /api/esp32-c3/devices/<device_id>/calibration/lux

POST /api/esp32-c3/devices/<device_id>/power
POST /api/esp32-c3/devices/<device_id>/power/normal
POST /api/esp32-c3/devices/<device_id>/power/save
POST /api/esp32-c3/devices/<device_id>/power/sleep

GET /api/esp32-c3/devices/<device_id>/config
POST /api/esp32-c3/devices/<device_id>/config
GET /api/esp32-c3/devices/<device_id>/stats
GET /api/esp32-c3/devices/stats

ALSO REMOVED: /api/settings/esp32-c3/* (duplicate endpoints)
```

### New URLs (✅ Use these)
```
GET /api/devices/esp32/devices
POST /api/devices/esp32/devices
GET /api/devices/esp32/devices/<device_id>
PUT /api/devices/esp32/devices/<device_id>
DELETE /api/devices/esp32/devices/<device_id>

POST /api/devices/esp32/devices/<device_id>/status
POST /api/devices/esp32/devices/<device_id>/command
POST /api/devices/esp32/devices/<device_id>/restart

POST /api/devices/esp32/devices/<device_id>/sensors/read
POST /api/devices/esp32/devices/<device_id>/sensors/enable
POST /api/devices/esp32/devices/<device_id>/sensors/disable

POST /api/devices/esp32/devices/<device_id>/calibration
POST /api/devices/esp32/devices/<device_id>/calibration/soil/<idx>/dry
POST /api/devices/esp32/devices/<device_id>/calibration/soil/<idx>/wet
POST /api/devices/esp32/devices/<device_id>/calibration/lux

POST /api/devices/esp32/devices/<device_id>/power
POST /api/devices/esp32/devices/<device_id>/power/normal
POST /api/devices/esp32/devices/<device_id>/power/save
POST /api/devices/esp32/devices/<device_id>/power/sleep

GET /api/devices/esp32/devices/<device_id>/config
POST /api/devices/esp32/devices/<device_id>/config
GET /api/devices/esp32/devices/<device_id>/stats
GET /api/devices/esp32/stats
```

### Migration Pattern
```
/api/esp32-c3/*  →  /api/devices/esp32/*
/api/settings/esp32-c3/*  →  /api/devices/esp32/*
```

### Migration Code Examples

#### Device Registration
```javascript
// OLD ❌
const device = await fetch('/api/esp32-c3/devices', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    device_id: 'ESP32_001',
    unit_id: 1,
    device_name: 'Greenhouse Sensor',
    location: 'Unit 1'
  })
});

// NEW ✅
const device = await fetch('/api/devices/esp32/devices', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    device_id: 'ESP32_001',
    unit_id: 1,
    device_name: 'Greenhouse Sensor',
    location: 'Unit 1'
  })
});
```

#### Status Update (ESP32 Firmware)
```cpp
// OLD ❌
String url = "/api/esp32-c3/devices/" + deviceId + "/status";
http.POST(url, payload);

// NEW ✅
String url = "/api/devices/esp32/devices/" + deviceId + "/status";
http.POST(url, payload);
```

#### Calibration
```javascript
// OLD ❌
await fetch('/api/esp32-c3/devices/ESP32_001/calibration/soil/0/dry', {
  method: 'POST'
});

// NEW ✅
await fetch('/api/devices/esp32/devices/ESP32_001/calibration/soil/0/dry', {
  method: 'POST'
});
```

#### Power Management
```javascript
// OLD ❌
await fetch('/api/esp32-c3/devices/ESP32_001/power/sleep', {
  method: 'POST',
  body: JSON.stringify({ duration_minutes: 60 })
});

// NEW ✅
await fetch('/api/devices/esp32/devices/ESP32_001/power/sleep', {
  method: 'POST',
  body: JSON.stringify({ duration_minutes: 60 })
});
```

---

## Complete API Structure (Post-Migration)

```
/auth/*                           # Authentication
/status/*                         # System status

# Core APIs
/api/growth/*                     # Growth units
/api/plants/*                     # Plant management
/api/settings/*                   # System settings

# Fixed APIs (Phase 5)
/api/sensors/*                    # Sensor readings ✨ NEW PREFIX
/api/disease/*                    # Disease detection ✨ NEW PREFIX
/api/health/*                     # Health monitoring

# Devices API (Consolidated)
/api/devices/                     # Device management
  ├── sensors/*                   # Sensor devices
  ├── actuators/*                 # Actuator devices
  ├── zigbee/*                    # Zigbee integration
  └── esp32/*                     # ESP32 devices ✨ CONSOLIDATED

# Other APIs
/api/dashboard/*                  # Dashboard data
/api/climate/*                    # Climate control
/api/harvest/*                    # Harvest management
/api/insights/*                   # Data insights
/api/ml/*                         # ML metrics

# Versioned APIs
/api/v1/agriculture/*             # Agricultural operations ✨ RENAMED
```

---

## Migration Checklist

### Frontend (Web)
- [ ] Update all API service classes/modules
- [ ] Search & replace URL patterns
- [ ] Update API client configuration
- [ ] Test all affected features
- [ ] Update error handling for new endpoints

### Mobile App
- [ ] Update API service files
- [ ] Update base URL constants
- [ ] Test device management features
- [ ] Test sensor data display
- [ ] Update integration tests

### ESP32 Firmware
- [ ] Update hardcoded URLs in firmware
- [ ] Update status reporting endpoint
- [ ] Update calibration endpoints
- [ ] Update power management calls
- [ ] Test device registration
- [ ] Flash updated firmware to all devices

### Documentation
- [ ] Update API documentation
- [ ] Update Postman collections
- [ ] Update integration guides
- [ ] Update developer documentation
- [ ] Update deployment guides

### Testing
- [ ] Run integration tests
- [ ] Test all migrated endpoints
- [ ] Verify error responses
- [ ] Check CORS configuration
- [ ] Performance testing

---

## Search & Replace Patterns

Use these patterns to quickly update your codebase:

### Sensors API
```bash
# Search
/api/sensor_history

# Replace
/api/sensors/sensor_history
```

### Agriculture API
```bash
# Search
/api/v1/plants/

# Replace
/api/v1/agriculture/
```

### ESP32 Devices API
```bash
# Search
/api/esp32-c3/

# Replace
/api/devices/esp32/

# Also search and remove
/api/settings/esp32-c3/
# (These are now also at /api/devices/esp32/)
```

### Disease API
```bash
# Search (if routes were at root)
/api/disease/

# Review each case - some may need:
/api/disease/disease/
```

---

## Automated Migration Script

### JavaScript/TypeScript
```javascript
// migration.js - Update API URLs in codebase

const fs = require('fs');
const path = require('path');

const replacements = [
  ['/api/sensor_history', '/api/sensors/sensor_history'],
  ['/api/v1/plants/', '/api/v1/agriculture/'],
  ['/api/esp32-c3/', '/api/devices/esp32/'],
  ['/api/settings/esp32-c3/', '/api/devices/esp32/'],
];

function migrateFile(filePath) {
  let content = fs.readFileSync(filePath, 'utf8');
  let changed = false;
  
  replacements.forEach(([old, newUrl]) => {
    if (content.includes(old)) {
      content = content.replace(new RegExp(old, 'g'), newUrl);
      changed = true;
    }
  });
  
  if (changed) {
    fs.writeFileSync(filePath, content, 'utf8');
    console.log(`✅ Migrated: ${filePath}`);
  }
}

// Run on your src directory
// migrateFile('src/services/api.js');
```

---

## Testing After Migration

### 1. Verify Endpoints
```bash
# Test new ESP32 endpoint
curl http://localhost:5000/api/devices/esp32/devices

# Test new sensors endpoint
curl http://localhost:5000/api/sensors/sensor_history

# Test new agriculture endpoint
curl http://localhost:5000/api/v1/agriculture/growth
```

### 2. Check Frontend
- Navigate to all pages using affected APIs
- Verify data loads correctly
- Check console for 404 errors
- Test CRUD operations

### 3. Check Mobile App
- Test device management screens
- Verify sensor data display
- Test ESP32 device registration
- Check calibration flows

### 4. Check ESP32 Devices
- Verify devices can connect
- Check status reporting works
- Test command sending
- Verify calibration commands

---

## Rollback Plan

If issues arise, you can temporarily support both URLs:

### Option 1: Nginx Proxy Rewrites
```nginx
# Add to nginx config
location /api/esp32-c3/ {
    rewrite ^/api/esp32-c3/(.*)$ /api/devices/esp32/$1 break;
    proxy_pass http://backend;
}
```

### Option 2: Flask Route Aliases (Not recommended long-term)
```python
# Temporary compatibility routes
@app.route('/api/esp32-c3/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE'])
def esp32_c3_compat(path):
    return redirect(f'/api/devices/esp32/{path}', code=308)
```

---

## Support & Questions

If you encounter issues during migration:

1. Check this guide for the correct new URL
2. Verify your API base URL configuration
3. Check browser console for specific errors
4. Review server logs for endpoint issues
5. Test with curl/Postman first

---

## Timeline

**Phase 5 Step 1:** December 7, 2025 - Namespace fixes (sensors, disease, agriculture)  
**Phase 5 Step 2:** December 7, 2025 - ESP32 consolidation  
**Phase 5 Step 3:** December 7, 2025 - Documentation & migration guide (this document)  
**Migration Deadline:** TBD - All clients must update before old code removed

---

**Last Updated:** December 7, 2025  
**Version:** 1.0  
**Status:** Active - Breaking Changes in Effect
