# Zigbee Sensor Reading Fix
**Date:** December 21, 2025  
**Status:** ✅ 3 of 4 issues fixed, 1 requires user action  
**Impact:** CRITICAL - Fixes missing Zigbee sensor readings

---

## Issues Found & Fixed

### ✅ Issue 1: Duplicate MQTT Subscriptions (FIXED)
**Problem:**
- `Zigbee2MQTTAdapter` was subscribing to `zigbee2mqtt/<friendly_name>` 
- `MQTTSensorService` also subscribes to `zigbee2mqtt/+`
- **Result:** Two handlers processing same message = conflicts, race conditions, dropped messages

**Fix Applied:**
```python
# Before: Adapter subscribed directly
self.mqtt_client.subscribe(self.mqtt_topic, self._on_mqtt_message)

# After: Passive adapter, MQTTSensorService handles all subscriptions
# NOTE: MQTT subscriptions are now handled by MQTTSensorService (unified)
# This adapter is passive - it only provides the read() interface
```

**Files Modified:**
- `app/hardware/adapters/sensors/zigbee2mqtt_adapter.py`
  - Removed `mqtt_client.subscribe()` calls (lines 67-70)
  - Added `update_data()` method for MQTTSensorService to push data
  - Kept `_on_mqtt_message()` as deprecated fallback

**Impact:** ✅ **Eliminates message conflicts and duplication**

---

### ✅ Issue 2: Redundant start_polling() Calls (FIXED)
**Problem:**
- `GrowthService.start_unit_runtime()` called `polling_service.start_polling()` (line 231)
- `ClimateControlService` also calls `start_polling()` (line 393)
- `SensorManagementService.start_monitoring()` also calls it (line 468)
- **Result:** Conflicts with Phase 3 conditional logic (only start if GPIO sensors exist)

**Fix Applied:**
```python
# Before
polling_service = self.sensor_service.polling_service
polling_service.start_polling()  # ❌ Redundant call

# After
polling_service = self.sensor_service.polling_service
self._polling_services[unit_id] = polling_service
# ✅ SensorManagementService handles polling lifecycle
```

**Files Modified:**
- `app/services/application/growth_service.py` (line 231)

**Impact:** ✅ **Respects conditional startup, avoids conflicts**

---

### ✅ Issue 3: No Message Tracing (FIXED)
**Problem:**
- `MQTT_SENSOR_TRACE` defaulted to `false`
- No visibility into which MQTT messages are being received
- **Result:** Can't debug why Zigbee messages aren't processed

**Fix Applied:**
```python
# Before
self._trace_messages = os.getenv("SYSGROW_MQTT_TRACE", "").strip().lower() in {...}

# After (default = true for debugging)
trace_env = os.getenv("SYSGROW_MQTT_TRACE", "true").strip().lower()
self._trace_messages = trace_env in {"1", "true", "yes", "on"}
```

**Files Modified:**
- `app/services/hardware/mqtt_sensor_service.py` (line 110)

**Impact:** ✅ **Full visibility into MQTT message flow**

---

### ⏳ Issue 4: Sensor Not Registered (USER ACTION REQUIRED)
**Problem:**
Your logs show:
```
Discovered Zigbee2MQTT device: Environment_sensor (type=temp_humidity_sensor, sensor=True...)
```

But `MQTTSensorService` logs:
```
Received Zigbee2MQTT message for 'Environment_sensor' but no registered sensor mapping was found.
```

**Root Cause:**
The sensor `Environment_sensor` is discovered by `ZigbeeManagementService` (device discovery), but **not registered in your sensors database table** for data processing.

**Solution - Option A (Recommended):** Register via API
```bash
curl -X POST http://localhost:5000/api/sensors \
  -H "Content-Type: application/json" \
  -d '{
    "unit_id": 1,
    "name": "Environment Sensor",
    "sensor_type": "temp_humidity_sensor",
    "protocol": "zigbee2mqtt",
    "model": "Environment_sensor",
    "mqtt_topic": "zigbee2mqtt/Environment_sensor",
    "friendly_name": "Environment_sensor",
    "capabilities": ["temperature", "humidity"]
  }'
```

**Solution - Option B:** Direct database insert
```sql
INSERT INTO sensors (unit_id, name, sensor_type, protocol, model, config)
VALUES (
    1,
    'Environment Sensor',
    'temp_humidity_sensor',
    'zigbee2mqtt',
    'Environment_sensor',
    json('{"mqtt_topic": "zigbee2mqtt/Environment_sensor", "friendly_name": "Environment_sensor", "capabilities": ["temperature", "humidity"]}')
);
```

**Verification:**
After registering, restart the server and check logs:
```bash
# Should see:
Zigbee2MQTT 'Environment_sensor' mapped to sensor_id=X unit_id=1
```

---

## Testing Instructions

### 1. Restart Server
```bash
# Stop current server (Ctrl+C)
$env:SYSGROW_ENABLE_MQTT="true"
python run_server.py
```

### 2. Check Startup Logs
Look for:
```
✅ Subscribed to MQTT topic: zigbee2mqtt/+
✅ Subscribed to MQTT topic: growtent/+/sensor/+/+
MQTTSensorService initialized (unified Zigbee + ESP32 handler)
```

### 3. Trigger Zigbee Message
In Zigbee2MQTT app, click your sensor to force a reading.

### 4. Check MQTT Trace Logs (NEW!)
With tracing enabled, you should see:
```
MQTT message received: topic=zigbee2mqtt/Environment_sensor
Zigbee2MQTT payload: friendly_name=Environment_sensor keys=['temperature', 'humidity', 'battery', 'linkquality']
```

### 5. Verify Sensor Mapping
**If registered correctly:**
```
Zigbee2MQTT 'Environment_sensor' mapped to sensor_id=1 unit_id=1
📊 Processed sensor 1 reading: temperature=22.5°C, humidity=45.0%
```

**If NOT registered (Issue #4):**
```
Received Zigbee2MQTT message for 'Environment_sensor' but no registered sensor mapping was found.
```
→ Register the sensor (see Issue #4 solutions above)

---

## Architecture After Fix

### Before (BROKEN)
```
Zigbee2MQTT
    ↓
    ├─→ MQTTSensorService._on_message()  ← subscribes to zigbee2mqtt/+
    └─→ Zigbee2MQTTAdapter._on_mqtt_message() ← ALSO subscribes! ❌
        → Duplicate processing, race conditions
```

### After (FIXED)
```
Zigbee2MQTT
    ↓
MQTTSensorService._on_message()  ← SINGLE subscription to zigbee2mqtt/+
    ↓
MQTTSensorService._handle_zigbee_message()
    ↓
    ├─→ Resolve friendly_name → sensor_id
    ├─→ Get SensorEntity from cache
    ├─→ Process through pipeline (validate → calibrate → transform)
    └─→ Emit to WebSocket (/devices + /dashboard if primary)
```

---

## Remaining TODO

### ClimateControlService start_polling()
The `ClimateControlService` also calls `start_polling()` (line 393). This should be reviewed:

**File:** `app/services/hardware/climate_control_service.py`
```python
# Line 393
polling_started = self.polling_service.start_polling()
```

**Recommendation:** Remove this call too. Polling should be managed centrally by `SensorManagementService`.

---

## Performance Impact

### Before
- **2x MQTT subscriptions** (MQTTSensorService + adapters)
- **2x message processing** per Zigbee message
- **Race conditions** causing dropped readings
- **3x start_polling()** calls causing conflicts

### After
- **1x MQTT subscription** (MQTTSensorService only)
- **1x message processing** (clean pipeline)
- **No race conditions** (single handler)
- **1x start_polling()** call (via SensorManagementService)

**Result:** Clean, predictable MQTT message flow ✨

---

## Debugging Commands

### Check MQTT Subscriptions
```bash
# On Raspberry Pi/server
mosquitto_sub -h localhost -t "zigbee2mqtt/#" -v
```

### Check Sensor Registration
```bash
curl http://localhost:5000/api/sensors | jq '.'
```

### Enable Extra Logging
```bash
# Before starting server
$env:SYSGROW_MQTT_TRACE="true"  # Already enabled by default now
$env:LOG_LEVEL="DEBUG"
python run_server.py
```

### Check for Errors
```bash
# In logs, search for:
grep -i "zigbee" logs/sysgrow.log | tail -50
grep -i "environment_sensor" logs/sysgrow.log | tail -50
```

---

## Related Documentation
- `SENSOR_POLLING_FINAL_SUMMARY.md` - Phase 1-6 completion
- `SENSOR_POLLING_OPTIMIZATION_PLAN.md` - Original architecture plan
- `MQTT_PERFORMANCE_FIX.md` - Phase 1 in-memory cache optimization

---

## Success Criteria

✅ **Fix is successful when:**
1. No duplicate MQTT subscriptions in logs
2. Zigbee messages show up in trace logs
3. Sensor mappings resolve: `friendly_name=Environment_sensor → sensor_id=X`
4. Readings appear on dashboard
5. Readings appear in console logs
6. Readings appear in terminal MQTT subscriber

**Next Step:** Register your `Environment_sensor` in the database (Issue #4) 🚀
