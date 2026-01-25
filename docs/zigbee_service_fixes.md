# Zigbee Service Implementation Fixes

## Summary
This document outlines the critical bugs identified and fixed in the Zigbee service implementation, along with UI improvements to clarify the distinction between ESP32-C6 and native Zigbee2MQTT devices.

## Critical Bugs Fixed

### 1. Module-Level Singleton Crash
**Location:** `app/services/zigbee_service.py`  
**Issue:** `zigbee_service = ZigbeeService()` at module level crashed because `ZigbeeService.__init__` requires a `client` parameter.  
**Fix:** Changed to `Optional[ZigbeeService] = None` and moved instantiation to `get_zigbee_service()`.

### 2. Container Variable Scope Error
**Location:** `app/services/container.py`  
**Issue:** `zigbee_service` variable declared inside `if mqtt_enabled` block but referenced outside, causing `NameError`.  
**Fix:** Declared `zigbee_service: Optional[ZigbeeService] = None` before the if block, ensuring proper scope.

### 3. Duplicate MQTT Connection Call
**Location:** `app/services/zigbee_service.py:__init__`  
**Issue:** Called `self._client.connect()` in `__init__`, violating dependency injection pattern (container already connects).  
**Fix:** Removed the connect call; assume client is already connected when passed to constructor.

### 4. Threading Synchronization Issues
**Location:** Multiple methods in `zigbee_service.py`  
**Issue:** Used boolean flags with busy-wait loops (`while not self._response_received: time.sleep(0.1)`), causing race conditions.  
**Fix:** Replaced with `threading.Event` for proper event-driven synchronization using `.wait(timeout)`.

### 5. Redundant MQTT Loop Management
**Location:** Multiple methods in `zigbee_service.py`  
**Issue:** Repeatedly called `loop_start()` and `loop_stop()`, wasting resources and causing errors.  
**Fix:** Subscribe to topics once in `__init__`; rely on persistent MQTT loop from container.

### 6. Typo in Device Response Handling
**Location:** `zigbee_service.py:_on_bridge_devices`  
**Issue:** `friendy_name` instead of `friendly_name`.  
**Fix:** Corrected to `friendly_name`.

### 7. Missing Error Handling
**Location:** `zigbee_service.py:permit_device_join`  
**Issue:** No error handling when publishing to MQTT broker.  
**Fix:** Added check for `publish().rc` to detect failures.

## API Endpoint Improvements

### Discovery Endpoint Error Handling
**Location:** `app/blueprints/api/devices.py`  
**Changes:**
- `_zigbee_service()` helper returns `None` gracefully instead of raising exceptions
- Discovery endpoint checks for `None` service and returns HTTP 503 with helpful hint
- Added `TimeoutError` handling for HTTP 504 responses
- Error responses include `hint` field: "Set SYSGROW_ENABLE_MQTT=true and restart"

## UI/UX Improvements

### Device Type Clarification
**Location:** `templates/settings.html`  
**Changes:**
- Updated section title to "Add Generic Device (Zigbee2MQTT)"
- Added comprehensive explanation box:
  - **Native Zigbee2MQTT**: Commercial Zigbee sensors connecting directly to zigbee2mqtt bridge
  - **ESP32-C6 Zigbee**: Custom sensors on ESP32-C6 boards (managed in separate section)
- Updated button text to "Discover Zigbee2MQTT Devices"
- Enhanced field hints to clarify device type expectations

### Discovery Results Styling
**Location:** `static/css/settings.css`  
**Added CSS classes:**
- `.discover-results`: Scrollable container with border
- `.discover-result-item`: Individual device item with hover effect
- `.discover-result-info`: Container for device name/address
- `.discover-result-name`: Bold device name
- `.discover-result-addr`: Monospace IEEE address
- `.discover-error`: Warning box for errors with hint display
- `.device-type-explanation`: Info box for device type clarification

### JavaScript Discovery Enhancements
**Location:** `templates/settings.html` (JavaScript section)  
**Changes:**
- Proper error message parsing from backend (shows `error` and `hint` fields)
- Structured HTML using `discover-result-info` wrapper
- Updated success messages to say "Zigbee2MQTT devices"
- Error handling displays backend hints in styled error box
- Improved empty state message

## Testing Recommendations

### Manual Testing
1. **MQTT Disabled Scenario:**
   - Set `SYSGROW_ENABLE_MQTT=False`
   - Restart server
   - Visit settings page and click "Discover Zigbee2MQTT Devices"
   - Verify error message displays with hint about enabling MQTT

2. **MQTT Enabled, No Devices:**
   - Ensure zigbee2mqtt bridge is running
   - Remove all paired devices
   - Click discovery button
   - Verify "No Zigbee2MQTT devices discovered" message

3. **Successful Discovery:**
   - Pair at least one Zigbee device to zigbee2mqtt
   - Click discovery button
   - Verify device list renders with name, IEEE address, and "Add" button
   - Click "Add" and verify form pre-fills correctly

4. **Device Type Understanding:**
   - Read the explanation box in settings
   - Verify distinction between ESP32-C6 and native Zigbee2MQTT is clear
   - Check that ESP32-C6 section (above) doesn't mention native Zigbee sensors

### Automated Testing
```bash
# Test zigbee service initialization
pytest tests/test_zigbee_service.py -k initialization

# Test discovery endpoint
pytest tests/test_api.py -k zigbee_discovery

# Test MQTT disabled scenario
SYSGROW_ENABLE_MQTT=False pytest tests/test_api.py -k zigbee
```

## Architecture Notes

### Separation of Concerns
- **Management Service** (`app/services/zigbee_service.py`): Discovery, permit join, rename, remove operations
- **Runtime Adapters** (`infrastructure/hardware/zigbee_*.py`): I/O operations for reading sensor data
- **API Layer** (`app/blueprints/api/devices.py`): REST endpoints with error handling
- **Frontend** (`templates/settings.html`): Discovery UI with clear device type distinction

### MQTT Topic Structure
- **Native Zigbee2MQTT**: `zigbee2mqtt/*` topics (managed by zigbee2mqtt bridge)
- **ESP32-C6 Zigbee**: `growtent/esp32c6/*` topics (managed by ESP32-C6 firmware)

### Dependency Flow
```
Container (MQTT client connected)
  → ZigbeeService (receives pre-connected client)
    → Subscribe to bridge topics in __init__
    → Use threading.Event for synchronization
    → Never call connect/loop_start/loop_stop
```

## Files Modified

1. `app/services/zigbee_service.py` - Core service refactoring
2. `app/services/container.py` - Variable scope and initialization fixes
3. `app/blueprints/api/devices.py` - Error handling improvements
4. `templates/settings.html` - UI clarification and JavaScript enhancements
5. `static/css/settings.css` - Discovery results styling

## Deployment Checklist

- [ ] Restart Flask server after pulling changes
- [ ] Verify `SYSGROW_ENABLE_MQTT` is set to `true` in production
- [ ] Check MQTT broker connection in logs: "MQTT client connected successfully"
- [ ] Test discovery endpoint: `GET /api/devices/v2/zigbee2mqtt/discover`
- [ ] Verify settings page loads without JavaScript errors
- [ ] Test device discovery workflow end-to-end
- [ ] Confirm ESP32-C6 section and Zigbee2MQTT section are clearly distinct

## Related Documentation

- Repository Guidelines: `AGENTS.md`
- Enums & Schemas: `ENUMS_SCHEMAS_SUMMARY.md`
- Frontend Migration: `test_frontend_migration.md`
- Refactoring Example: `REFACTORING_EXAMPLE.md`
