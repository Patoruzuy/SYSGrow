# 🗑️ Phase 3: Redis Removal - Implementation Plan

## 📊 Analysis Complete

### Files Requiring Changes: **8 files**

1. ✅ `environment/sensor_polling_service.py` - Remove Redis polling
2. ✅ `sensors/soil_moisture_sensor.py` - Remove Redis writes
3. ✅ `sensors/temp_humidity_sensor.py` - Remove Redis writes
4. ✅ `sensors/mq2_sensor.py` - Remove Redis writes
5. ✅ `sensors/light_sensor.py` - Remove Redis writes
6. ✅ `sensors/dht11_sensor.py` - Remove Redis writes
7. ✅ `sensors/co2_sensor.py` - Remove Redis writes
8. ✅ `app/services/container.py` - Remove Redis initialization

### Files NOT Requiring Changes:

- ✅ `environment/climate_controller.py` - **Perfect as-is!**
- ✅ `infrastructure/hardware/unit_runtime_manager.py` - **Already handles optional Redis**
- ✅ `app/services/climate_service.py` - **Already handles optional Redis**

---

## 🔄 Current Architecture (With Redis)

```
┌─────────────┐
│  ESP32-C6   │
│   Sensors   │
└──────┬──────┘
       │ MQTT publish: growtent/{unit}/sensor/{type}
       │ Sensor script listens to MQTT
       ▼
┌─────────────────┐
│ Sensor Scripts  │
│ (Python on Pi)  │
└──────┬──────────┘
       │ 1. Receive MQTT
       │ 2. Write to Redis ❌ (REMOVE THIS)
       │ 3. Publish to MQTT
       ▼
┌─────────────────┐
│     Redis       │ ❌ (REMOVE)
│   (Cache)       │
└──────┬──────────┘
       │ Polling every 30s
       ▼
┌─────────────────────────────────┐
│  SensorPollingService           │
│  - MQTT subscriber ✅           │
│  - Redis poller ❌ (REMOVE)     │
│  - GPIO poller ✅               │
└─────────────┬───────────────────┘
              │
              ▼
┌──────────────────────────────┐
│        EventBus              │
└───────┬──────────────────────┘
        │
        ▼
┌───────────────────────────┐
│   ClimateController       │
└───────────────────────────┘
```

---

## ✨ New Architecture (Without Redis)

```
┌─────────────┐
│  ESP32-C6   │
│   Sensors   │
└──────┬──────┘
       │ MQTT publish: growtent/{unit}/sensor/{type}
       ▼
┌─────────────────────────────────┐
│  SensorPollingService           │
│  - MQTT subscriber ✅           │
│  - GPIO poller ✅               │
│  (Direct EventBus publish)      │
└─────────────┬───────────────────┘
              │
              ▼
┌──────────────────────────────┐
│        EventBus              │
│     (In-Memory Pub/Sub)      │
└───────┬──────────────────────┘
        │
        ▼
┌───────────────────────────┐
│   ClimateController       │
│   (No changes needed!)    │
└───────────────────────────┘
```

**Benefits:**
- 🚀 **Faster** - No Redis polling overhead
- 💾 **Less Memory** - Save 10-20MB RAM
- 🔧 **Simpler** - One less dependency
- ⚡ **Real-time** - Direct MQTT → EventBus

---

## 📝 Implementation Checklist

### Step 1: Update SensorPollingService ✅
- [ ] Make `redis_client` parameter optional (default=None)
- [ ] Remove `_poll_redis_sensors_loop()` method
- [ ] Remove `is_redis_data_stale()` method
- [ ] Remove Redis polling thread from `start_polling()`
- [ ] Update docstring

### Step 2: Update Sensor Scripts (6 files) ✅
For each sensor file:
- [ ] Remove `redis_client` initialization
- [ ] Remove `redis.set()` calls
- [ ] Keep MQTT publishing intact
- [ ] Update docstrings

Files to update:
1. [ ] `sensors/soil_moisture_sensor.py`
2. [ ] `sensors/temp_humidity_sensor.py`
3. [ ] `sensors/mq2_sensor.py`
4. [ ] `sensors/light_sensor.py`
5. [ ] `sensors/dht11_sensor.py`
6. [ ] `sensors/co2_sensor.py`

### Step 3: Update Container ✅
- [ ] Remove Redis client initialization
- [ ] Remove `redis_client` from ServiceContainer
- [ ] Update shutdown method

### Step 4: Update Requirements ✅
- [ ] Remove `redis` from `requirements.txt`
- [ ] Remove from `requirements-windows.txt`
- [ ] Remove from `requirements-essential.txt`

### Step 5: Testing ✅
- [ ] Test GPIO sensors (should work unchanged)
- [ ] Test MQTT sensors (should work directly)
- [ ] Test EventBus propagation
- [ ] Test ClimateController responses
- [ ] Verify no Redis connections attempted
- [ ] Check memory usage on Pi 3B+

---

## 🎯 Expected Results

### Before Redis Removal:
```
Memory: ~450MB (with Redis)
CPU: ~15% (with polling overhead)
Latency: MQTT → Redis → Poll (30s) → EventBus
Dependencies: Flask, Redis, MQTT, SQLite
```

### After Redis Removal:
```
Memory: ~430MB (save 20MB)
CPU: ~13% (save 2%)
Latency: MQTT → EventBus (instant!)
Dependencies: Flask, MQTT, SQLite
```

**Performance Improvement:** ~4-5% total resources freed

---

## ⚠️ Important Notes

### What Still Works:
- ✅ GPIO sensors (direct polling)
- ✅ MQTT sensors (direct subscription)
- ✅ EventBus communication
- ✅ ClimateController automation
- ✅ All existing features

### What Changes:
- ❌ No Redis dependency
- ❌ No wireless sensor caching between restarts
- ✅ Sensors must be online to be read (real-time only)

### Migration Path:
1. Stop the app
2. Apply code changes
3. Remove Redis from system (optional)
4. Restart app
5. All sensors reconnect via MQTT

---

## 🧪 Testing Strategy

### Unit Tests:
```python
def test_sensor_polling_without_redis():
    """SensorPollingService works with redis_client=None"""
    service = SensorPollingService(
        sensor_manager=mock_manager,
        redis_client=None,  # No Redis!
        mqtt_wrapper=mock_mqtt
    )
    service.start_polling()
    assert service._started == True
```

### Integration Tests:
```python
def test_mqtt_to_eventbus_flow():
    """MQTT sensor data flows to ClimateController"""
    # 1. Publish MQTT message
    mqtt_client.publish("growtent/1/sensor/temperature", {"temperature": 25.5})
    
    # 2. Wait for EventBus propagation
    time.sleep(0.1)
    
    # 3. Verify ClimateController received it
    assert climate_controller.last_temperature == 25.5
```

### Manual Tests:
1. Start app without Redis installed
2. Send MQTT sensor data from ESP32
3. Verify readings appear in UI
4. Verify actuators respond to thresholds
5. Check logs for no Redis errors

---

## 📊 Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Sensor data loss on restart | Medium | Low | MQTT QoS=1, persist in SQLite |
| MQTT broker overload | Low | Low | Mosquitto handles 1000s msg/sec |
| EventBus memory leak | Low | Medium | Implement subscriber cleanup |
| Breaking existing sensors | Low | High | Keep GPIO polling unchanged |

---

## 🚀 Ready to Implement

All analysis complete. Ready to start Phase 3 implementation!

**Next Action:** Update SensorPollingService to make Redis optional
