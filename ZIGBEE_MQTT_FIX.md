# Zigbee2MQTT Sensor Data Fix

## Problem Identified
You weren't seeing Zigbee sensor readings on the dashboard because the **sensor polling service wasn't subscribing to Zigbee2MQTT topics**.

## Root Cause Analysis

### Architecture Flow
```
Zigbee2MQTT → MQTT Broker → SensorPollingService → Socket.IO → Dashboard
```

### What Was Broken
1. **Zigbee2MQTTAdapter** (per-sensor adapter):
   - ✅ Subscribes to `zigbee2mqtt/<friendly_name>`
   - ✅ Receives and caches data in `_on_mqtt_message()`
   - ❌ **Never broadcasts to Socket.IO**
   - ❌ **Nobody polls the adapter's cached data**

2. **SensorPollingService** (central polling service):
   - ✅ Has `_broadcast_to_socketio()` method that emits both `sensor_update` and `zigbee_sensor_data` events
   - ✅ Broadcasts GPIO/I2C sensor readings correctly
   - ❌ **Only subscribed to `growtent/+/sensor/+` topics**
   - ❌ **Did NOT subscribe to `zigbee2mqtt/+` topics**

### Topic Pattern Mismatch
- **Zigbee2MQTT publishes to**: `zigbee2mqtt/Environment_sensor`
- **Polling service subscribed to**: `growtent/+/sensor/+` ❌

## Fix Applied

### 1. Added Zigbee2MQTT Subscription
**File**: `workers/sensor_polling_service.py`

```python
# Subscribe to MQTT sensor updates and reload trigger if MQTT is enabled
if self.mqtt_wrapper:
    self.mqtt_wrapper.subscribe("growtent/+/sensor/+", self._on_mqtt_message)
    self.mqtt_wrapper.subscribe("growtent/reload", self._on_mqtt_message)
    # Subscribe to Zigbee2MQTT topics for commercial Zigbee sensors
    self.mqtt_wrapper.subscribe("zigbee2mqtt/+", self._on_mqtt_message)  # ← NEW
```

### 2. Enhanced MQTT Message Handler
**File**: `workers/sensor_polling_service.py` - `_on_mqtt_message()`

Added Zigbee2MQTT topic parsing:
- Detects `zigbee2mqtt/<friendly_name>` topics
- Maps Zigbee2MQTT payload keys to internal format:
  - `temperature` / `temp` → `temperature`
  - `humidity` / `relative_humidity` → `humidity`
  - `soil_moisture` / `moisture` → `soil_moisture`
  - `illuminance` / `illuminance_lux` / `lux` → `illuminance`
  - `battery` / `battery_percent` → `battery`
  - `linkquality` / `link_quality` → `linkquality`
- Adds `friendly_name` to payload (critical for Socket.IO routing)
- Logs: `📥 Zigbee2MQTT sensor update → <friendly_name> (<sensor_type>)`

### 3. Data Flow Integration
With `friendly_name` present in the data:
1. `_on_mqtt_message()` → parses Zigbee2MQTT payload
2. `_publish_with_rate_limit()` → rate-limits updates
3. `_publish_sensor_data()` → publishes to event bus
4. `_broadcast_to_socketio()` → **detects `friendly_name`**
5. Emits: `socketio.emit('zigbee_sensor_data', payload, namespace='/sensors')`

## Expected Behavior After Fix

### Backend Logs (when Zigbee sensor sends data)
```
📥 Zigbee2MQTT sensor update → Environment_sensor (temperature)
📡 Socket.IO (/sensors): zigbee_sensor_data → Environment_sensor
```

### Frontend (Socket.IO events)
Dashboard should receive:
```javascript
socket.on('zigbee_sensor_data', (data) => {
    // data = {
    //   friendly_name: 'Environment_sensor',
    //   temperature: 23.5,
    //   humidity: 65.2,
    //   battery: 100,
    //   linkquality: 150,
    //   timestamp: '2025-12-02T21:30:00Z'
    // }
});
```

## Testing Checklist

### Prerequisites
- ✅ Zigbee2MQTT running and publishing to `zigbee2mqtt/<friendly_name>`
- ✅ MQTT broker accessible (check `SYSGROW_MQTT_BROKER` env var)
- ✅ Sensors registered in database with `protocol='zigbee2mqtt'`

### Verification Steps
1. **Check subscription**:
   ```bash
   # Look for log line during startup:
   # "SensorPollingService config: ..."
   # Followed by subscription logs
   ```

2. **Monitor MQTT traffic** (optional):
   ```bash
   mosquitto_sub -h localhost -t "zigbee2mqtt/#" -v
   ```

3. **Check backend logs for Zigbee updates**:
   ```
   📥 Zigbee2MQTT sensor update → Environment_sensor (temperature)
   📡 Socket.IO (/sensors): zigbee_sensor_data → Environment_sensor
   ```

4. **Open browser console on dashboard**:
   ```javascript
   // Should see Socket.IO events:
   SocketManager: Connected to /sensors namespace
   Received zigbee_sensor_data: { friendly_name: 'Environment_sensor', ... }
   ```

5. **Verify dashboard display**:
   - Sensor cards should update with live values
   - Timestamps should be recent
   - Battery and link quality indicators visible

## Troubleshooting

### No MQTT messages received
1. Check MQTT broker connection:
   ```python
   # Backend should log:
   "📡 MQTT listener active for wireless sensors"
   ```
2. Verify Zigbee2MQTT is publishing:
   ```bash
   mosquitto_sub -h <broker_ip> -t "zigbee2mqtt/+" -v
   ```

### Socket.IO not emitting
1. Check if `SOCKETIO_AVAILABLE` is True:
   ```python
   from app.extensions import socketio
   print(socketio)  # Should not be None
   ```
2. Check for Socket.IO errors in backend logs

### Dashboard not updating
1. Open browser console → Network → WS tab
2. Verify WebSocket connected to `ws://localhost:5000/socket.io/`
3. Check for Socket.IO events in console
4. Verify `static/js/socket.js` is loaded

## Related Files Modified
- `workers/sensor_polling_service.py`:
  - Added `zigbee2mqtt/+` subscription
  - Enhanced `_on_mqtt_message()` to parse Zigbee2MQTT payloads
  - Logs now differentiate Zigbee2MQTT from custom MQTT topics

## Architecture Notes

### Why Not Let Adapters Emit Directly?
- **Separation of concerns**: Adapters are data collectors, not broadcasters
- **Rate limiting**: Centralized broadcasting in polling service applies rate limits
- **Event bus integration**: Single entry point for all sensor data
- **Consistency**: All sensors (GPIO, I2C, MQTT, Zigbee) flow through same path

### Why polling service handles MQTT?
- The name "polling" is historical - it handles both:
  - **Active polling**: GPIO/I2C sensors (requires repeated reads)
  - **Passive listening**: MQTT/Zigbee sensors (event-driven)
- Could be renamed to `SensorDataService` for clarity

## Next Steps
1. Test with live Zigbee2MQTT sensors
2. Verify dashboard displays all sensor types correctly
3. Check rate limiting works (2-second coalesce window)
4. Monitor for any duplicate events or missing data
5. Consider adding Zigbee sensor health monitoring (stale data detection)
