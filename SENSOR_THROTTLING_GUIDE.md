# Sensor Data Throttling Configuration

## Overview

The sensor data throttling system intelligently manages how sensor readings are stored in the database to balance:
- **Database efficiency** - Avoid excessive writes that slow down the system
- **Data quality** - Capture meaningful changes and maintain sufficient resolution
- **Historical accuracy** - Keep enough data for meaningful analytics and charts

## Throttling Strategies

### 1. **Time-Only Strategy** (Conservative)
Stores readings at fixed time intervals regardless of value changes.

**Best for:**
- Stable environments with predictable conditions
- Minimizing database size
- Long-term historical trends

**Example:** Store temperature every 30 minutes, even if it hasn't changed.

### 2. **Hybrid Strategy** (Recommended)
Stores readings when **EITHER** time interval elapsed **OR** significant change detected.

**Best for:**
- Dynamic environments with occasional spikes
- Capturing important events (door openings, watering events)
- Balancing efficiency with responsiveness

**Example:** Store temperature if 30 minutes passed OR temperature changed by ≥1°C.

## Configuration Options

### Time Intervals (Minutes)
Controls minimum time between stored readings:
- `temp_humidity_minutes`: 30 (default) - Temperature and humidity readings
- `co2_voc_minutes`: 30 (default) - CO2 and VOC air quality readings
- `soil_moisture_minutes`: 60 (default) - Soil moisture readings

### Change Thresholds
Controls what constitutes a "significant change":
- `temp_celsius`: 1.0°C (default) - Temperature change threshold
- `humidity_percent`: 5.0% (default) - Humidity change threshold
- `soil_moisture_percent`: 10.0% (default) - Soil moisture change threshold
- `co2_ppm`: 100 ppm (default) - CO2 change threshold
- `voc_ppb`: 50 ppb (default) - VOC change threshold

### Feature Flags
- `throttling_enabled`: true/false - Enable/disable throttling entirely
- `debug_logging`: true/false - Log every throttle decision for debugging
- `use_hybrid_strategy`: true/false - Use hybrid vs time-only strategy

## API Endpoints

### GET /api/settings/throttle
Get current throttling configuration.

**Response:**
```json
{
  "success": true,
  "data": {
    "time_intervals": {
      "temp_humidity_minutes": 30,
      "co2_voc_minutes": 30,
      "soil_moisture_minutes": 60
    },
    "change_thresholds": {
      "temp_celsius": 1.0,
      "humidity_percent": 5.0,
      "soil_moisture_percent": 10.0,
      "co2_ppm": 100.0,
      "voc_ppb": 50.0
    },
    "strategy": "hybrid",
    "throttling_enabled": true,
    "debug_logging": false
  }
}
```

### PUT /api/settings/throttle
Update throttling configuration (partial updates supported).

**Request Examples:**

**Change only time intervals:**
```json
{
  "time_intervals": {
    "temp_humidity_minutes": 15
  }
}
```

**Change strategy to time-only:**
```json
{
  "strategy": "time_only"
}
```

**Disable throttling (store all readings):**
```json
{
  "throttling_enabled": false
}
```

**Adjust change thresholds:**
```json
{
  "change_thresholds": {
    "temp_celsius": 0.5,
    "humidity_percent": 3.0
  }
}
```

### POST /api/settings/throttle/reset
Reset configuration to factory defaults.

## Usage Examples

### Scenario 1: High-Precision Monitoring
You need detailed data for a critical growth phase:

```bash
curl -X PUT http://localhost:5000/api/settings/throttle \
  -H "Content-Type: application/json" \
  -d '{
    "time_intervals": {
      "temp_humidity_minutes": 5,
      "soil_moisture_minutes": 10
    },
    "change_thresholds": {
      "temp_celsius": 0.5,
      "soil_moisture_percent": 3.0
    }
  }'
```

### Scenario 2: Long-Term Storage Optimization
You want minimal database growth for stable long-term grows:

```bash
curl -X PUT http://localhost:5000/api/settings/throttle \
  -H "Content-Type: application/json" \
  -d '{
    "strategy": "time_only",
    "time_intervals": {
      "temp_humidity_minutes": 60,
      "co2_voc_minutes": 120,
      "soil_moisture_minutes": 180
    }
  }'
```

### Scenario 3: Debug Mode
Capture everything for troubleshooting:

```bash
curl -X PUT http://localhost:5000/api/settings/throttle \
  -H "Content-Type: application/json" \
  -d '{
    "throttling_enabled": false,
    "debug_logging": true
  }'
```

### Scenario 4: Reset to Defaults
Return to recommended settings:

```bash
curl -X POST http://localhost:5000/api/settings/throttle/reset
```

## Monitoring

Check throttling status in the health endpoint:

```bash
curl http://localhost:5000/status/health
```

Look for the `throttle_config` and `last_stored_values` sections to see:
- Current configuration
- Last stored sensor values
- Last insert timestamps
- How many readings were throttled

## Best Practices

1. **Start with defaults** - The hybrid strategy with default thresholds works well for most setups
2. **Monitor your database** - Check size growth over time
3. **Adjust based on environment** - More dynamic environments benefit from lower thresholds
4. **Use time-only for stable setups** - Save database space if conditions rarely change
5. **Enable debug logging temporarily** - When tuning thresholds, turn on debug to see throttle decisions
6. **Disable throttling for testing** - When validating sensor accuracy, turn off throttling temporarily

## Technical Details

### Data Flow
```
MQTT Sensor → MQTTSensorService → EventBus → ClimateController → Database
                                     ↓
                                 (emit only)        ↓
                                                (throttled insert)
```

1. **MQTTSensorService** - Receives sensor data, processes, and emits to EventBus
2. **EventBus** - Distributes sensor updates to subscribers
3. **ClimateController** - Applies throttling logic and stores to database
4. **Real-time updates** - Always emitted via Socket.IO (no throttling)
5. **Database storage** - Throttled based on configuration

### Throttling Algorithm (Hybrid Strategy)

```python
should_store = (
    # First reading
    last_stored_value is None
    OR
    # Time interval elapsed
    (current_time - last_insert_time) >= configured_interval
    OR
    # Significant change detected
    abs(current_value - last_stored_value) >= configured_threshold
)
```

### Throttling Algorithm (Time-Only Strategy)

```python
should_store = (
    # First reading
    last_stored_value is None
    OR
    # Time interval elapsed
    (current_time - last_insert_time) >= configured_interval
)
```

## Troubleshooting

**Problem:** Not seeing data in analytics charts

**Solution:** 
1. Check if throttling is too aggressive: `GET /api/settings/throttle`
2. Temporarily disable throttling: `PUT /api/settings/throttle {"throttling_enabled": false}`
3. Check if sensor values are actually changing
4. Enable debug logging to see throttle decisions

**Problem:** Database growing too fast

**Solution:**
1. Switch to time-only strategy: `PUT /api/settings/throttle {"strategy": "time_only"}`
2. Increase time intervals
3. Increase change thresholds (less sensitive)

**Problem:** Missing important events (door openings, watering)

**Solution:**
1. Use hybrid strategy (default)
2. Lower change thresholds (more sensitive)
3. Check thresholds match your sensor accuracy

## Future Enhancements

Planned features:
- [ ] Per-sensor throttling configuration
- [ ] Data quality tiers (high/medium/low resolution)
- [ ] Automatic threshold tuning based on sensor variance
- [ ] Time-of-day based throttling (more frequent during growth stages)
- [ ] Web UI for configuration management
