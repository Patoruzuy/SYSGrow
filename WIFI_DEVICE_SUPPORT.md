# WiFi Sensor & Actuator Support Analysis
**Date**: December 18, 2025  
**Topic**: WiFi Smart Switches and WiFi Sensors - Polling vs. Event-Driven

---

## Question: Do WiFi Sensors/Actuators Need Polling?

### Answer: **It Depends on the Protocol!**

WiFi devices can use two primary communication methods:

### 1. **MQTT-based WiFi Devices** (Event-Driven - NO polling needed ✅)

**Examples**:
- Tasmota devices (smart switches, sensors)
- ESPHome devices
- Shelly devices (with MQTT enabled)
- Your ESP32-C6 modules

**Characteristics**:
- Publish data to MQTT broker when state changes
- Subscribe to MQTT topics for commands
- Already event-driven via MQTT broker
- No polling required - broker handles message routing

**Your Current Architecture** (from code):
```python
# ESP32-C6 modules publish to MQTT
# Topics: growtent/<unit_id>/sensor/<sensor_type>/<sensor_id>
# Already handled by SensorPollingService._on_mqtt_message()

# WiFi relay sends HTTP or MQTT commands
class WiFiRelay(RelayBase):
    def _send_request(self, state: str):
        """HTTP request to WiFi relay"""
        url = f"http://{self.ip}/relay/{state}"
        response = requests.get(url, timeout=5)  # Polling required!
```

**Recommendation**: Use MQTT for WiFi devices whenever possible (no polling needed)

---

### 2. **HTTP REST API WiFi Devices** (Polling Required ⚠️)

**Examples**:
- WiFi relays with HTTP-only interfaces
- IP cameras with REST APIs
- Some smart plugs (no MQTT support)
- ESP8266/ESP32 with custom HTTP servers

**Characteristics**:
- Require periodic HTTP GET/POST requests to:
  - Check state
  - Send commands
  - Get sensor readings
- No push notifications - must poll
- Higher latency than MQTT

**Your Current Implementation**:
```python
# WiFiRelay uses HTTP polling for commands
class WiFiRelay(RelayBase):
    def _send_request(self, state: str):
        url = f"http://{self.ip}/relay/{state}"
        response = requests.get(url, timeout=5)
```

**Recommendation**: Create HTTPPollingService for HTTP-only WiFi devices

---

## Proposed Architecture for WiFi Devices

### Option A: MQTT-First Approach (Recommended ✅)

**For WiFi Smart Switches**:
1. Configure device to use MQTT (Tasmota, ESPHome, etc.)
2. Device publishes state changes to broker
3. ZigbeeManagementService or ESP32MQTTService handles events
4. No polling required

**Example Configuration**:
```yaml
# Tasmota WiFi switch configuration
topic: growtent/actuator/light/1
mqtt_host: mqtt-broker.local
mqtt_port: 1883
state_topic: growtent/actuator/light/1/state
command_topic: growtent/actuator/light/1/set
```

**Benefits**:
- Real-time updates (no polling delay)
- Lower network traffic
- Lower power consumption
- Scalable (MQTT broker handles load)

---

### Option B: HTTP Polling Service (For HTTP-Only Devices)

**When to Use**:
- Device only supports HTTP REST API
- Cannot upgrade firmware to MQTT
- Legacy WiFi devices

**Implementation** (NEW service needed):
```python
class HTTPPollingService:
    """
    Polling service for HTTP-based WiFi devices.
    
    Polls HTTP REST APIs at configurable intervals to:
    - Get sensor readings
    - Check actuator states
    - Monitor device health
    """
    
    def __init__(self, device_manager, poll_interval: int = 30):
        self.device_manager = device_manager
        self.poll_interval = poll_interval  # seconds
        self.event_bus = EventBus()
        self._stop_event = threading.Event()
        self._thread = None
    
    def start_polling(self):
        """Start HTTP polling thread"""
        self._thread = threading.Thread(
            target=self._poll_http_devices_loop,
            daemon=True,
            name="HTTP-Poller"
        )
        self._thread.start()
    
    def _poll_http_devices_loop(self):
        """Poll HTTP devices periodically"""
        while not self._stop_event.is_set():
            try:
                http_devices = self._get_http_devices()
                
                for device in http_devices:
                    if device.device_type == 'sensor':
                        self._poll_http_sensor(device)
                    elif device.device_type == 'actuator':
                        self._poll_http_actuator(device)
                
            except Exception as e:
                logger.error(f"HTTP polling error: {e}")
            
            self._stop_event.wait(self.poll_interval)
    
    def _poll_http_sensor(self, sensor):
        """Poll HTTP sensor for readings"""
        url = f"http://{sensor.ip_address}/api/sensor"
        try:
            response = requests.get(url, timeout=5)
            data = response.json()
            
            # Publish to EventBus
            self.event_bus.publish(
                SensorEvent.TEMPERATURE_UPDATE,
                {
                    'sensor_id': sensor.id,
                    'temperature': data.get('temperature'),
                    'timestamp': iso_now()
                }
            )
        except Exception as e:
            logger.error(f"Failed to poll sensor {sensor.id}: {e}")
    
    def _poll_http_actuator(self, actuator):
        """Poll HTTP actuator for state"""
        url = f"http://{actuator.ip_address}/api/state"
        try:
            response = requests.get(url, timeout=5)
            data = response.json()
            
            # Update actuator state if changed
            if data.get('state') != actuator.state:
                actuator.update_state(data.get('state'))
        except Exception as e:
            logger.error(f"Failed to poll actuator {actuator.id}: {e}")
    
    def _get_http_devices(self):
        """Get list of HTTP-based devices"""
        all_devices = self.device_manager.get_all_devices()
        return [d for d in all_devices if d.protocol == 'HTTP' or d.protocol == 'WIFI_HTTP']
```

---

## Recommendation Summary

### For Your SYSGrow System:

1. **WiFi Smart Switches** (Actuators):
   - ✅ **Use MQTT** (Tasmota, ESPHome, Shelly)
   - ✅ Handled by ESP32MQTTService (from optimization plan)
   - ❌ Avoid HTTP-only devices if possible

2. **WiFi Sensors**:
   - ✅ **Use MQTT** (ESP32-C6 modules, Tasmota sensors)
   - ✅ Already handled by existing MQTT infrastructure
   - ⚠️ If HTTP-only: Create HTTPPollingService

3. **Existing WiFiRelay Class**:
   - Keep for backward compatibility
   - Add MQTT support as primary method
   - Use HTTP as fallback

---

## Updated Architecture with WiFi Support

```
┌─────────────────────────────────────────────────────────────┐
│                    WiFi Device Support                       │
└─────────────────────────────────────────────────────────────┘

                         ┌──────────────┐
                         │ MQTT Broker  │
                         └──────────────┘
                                │
                ┌───────────────┼───────────────┐
                │               │               │
        ┌───────▼──────┐ ┌──────▼──────┐ ┌─────▼─────┐
        │ ESP32-C6     │ │ Tasmota     │ │ Shelly    │
        │ Sensors      │ │ Switches    │ │ Devices   │
        └──────────────┘ └─────────────┘ └───────────┘
                │               │               │
                └───────────────┼───────────────┘
                                │
                    ┌───────────▼───────────┐
                    │ ESP32MQTTService      │
                    │ (Event-Driven)        │
                    └───────────┬───────────┘
                                │
                    ┌───────────▼───────────┐
                    │ EventBus              │
                    └───────────────────────┘


           HTTP-Only WiFi Devices (Polling Required)

        ┌──────────────┐ ┌──────────────┐
        │ HTTP Sensor  │ │ HTTP Actuator│
        │ (WiFi)       │ │ (WiFi Relay) │
        └──────────────┘ └──────────────┘
                │               │
                └───────────────┤
                                │
                    ┌───────────▼───────────┐
                    │ HTTPPollingService    │
                    │ (Polling Required)    │
                    └───────────┬───────────┘
                                │
                    ┌───────────▼───────────┐
                    │ EventBus              │
                    └───────────────────────┘
```

---

## Implementation Priority

### Phase 1: MQTT WiFi Support (Week 1) ✅
- Already implemented for ESP32-C6
- Extend ESP32MQTTService to support Tasmota/Shelly
- Document MQTT topic structure for WiFi devices

### Phase 2: WiFiRelay MQTT Enhancement (Week 1)
- Add MQTT primary method to WiFiRelay class
- Keep HTTP as fallback
- Auto-detect protocol (MQTT vs HTTP)

### Phase 3: HTTPPollingService (Week 2) - Only if needed
- Create HTTP polling service for legacy devices
- Configurable poll interval per device
- Health monitoring and backoff

---

## Final Answer

**WiFi Sensors**: 
- ✅ **MQTT-based**: No polling needed (event-driven via broker)
- ⚠️ **HTTP-only**: Polling required (create HTTPPollingService)

**WiFi Smart Switches**:
- ✅ **MQTT-based**: No polling needed (send commands via MQTT)
- ⚠️ **HTTP-only**: Polling required for state monitoring

**Recommendation**: Configure all WiFi devices to use MQTT for optimal performance and scalability. Only use HTTP polling as last resort for legacy devices that cannot be upgraded.
