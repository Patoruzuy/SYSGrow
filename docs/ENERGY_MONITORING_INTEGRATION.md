# Energy Monitoring & Zigbee2MQTT Discovery Integration

Complete integration of power monitoring and smart device discovery for the SYSGrow system.

## 🎯 Overview

The system now supports:
- ✅ **Real-time power monitoring** from Zigbee2MQTT smart switches/plugs
- ✅ **Automatic device discovery** via Zigbee2MQTT bridge
- ✅ **Energy consumption tracking** and statistics
- ✅ **Cost estimation** (daily/weekly/monthly/yearly)
- ✅ **Power profiling** for different actuator types
- ✅ **Per-unit energy management** (each growth unit tracks independently)

---

## 📦 Components

### 1. EnergyMonitoringService
**Location**: `infrastructure/hardware/actuators/energy_monitoring.py`

Tracks power consumption for actuators with built-in monitoring capabilities.

**Features**:
- Real-time power readings from smart switches
- Power consumption estimation for non-monitored devices
- Energy usage statistics (kWh, runtime, average/peak power)
- Cost calculations based on electricity rates
- Power threshold alerts
- Efficiency metrics (power factor, voltage stability)

**Data Structures**:
```python
EnergyReading:
    - voltage (V)
    - current (A)
    - power (W)
    - energy (kWh cumulative)
    - power_factor
    - frequency (Hz)
    - temperature (device temp)

PowerProfile:
    - rated_power_watts
    - standby_power_watts
    - efficiency_factor
    - power_curve (level -> watts mapping)

ConsumptionStats:
    - total_energy_kwh
    - average_power_watts
    - peak_power_watts
    - runtime_hours
    - cost_estimate
```

### 2. Zigbee2MQTTDiscoveryService
**Location**: `infrastructure/hardware/actuators/zigbee2mqtt_discovery.py`

Auto-discovers Zigbee2MQTT devices and their capabilities.

**Features**:
- Automatic device discovery via MQTT bridge
- Capability detection (switching, dimming, power monitoring)
- Device state monitoring (real-time updates)
- Command sending to devices
- Power monitoring detection and setup

**MQTT Topics**:
```
zigbee2mqtt/bridge/devices        → Device list
zigbee2mqtt/bridge/info           → Bridge information
zigbee2mqtt/{device}/state        → Device state
zigbee2mqtt/{device}              → Device data (includes power)
zigbee2mqtt/{device}/set          → Send commands
```

**Device Capabilities Detected**:
- Binary (on/off switch)
- Numeric (dimming, level control)
- Enum (mode selection)
- Power monitoring (voltage, current, power, energy)

### 3. ActuatorManager Integration
**Location**: `infrastructure/hardware/actuators/manager.py`

Enhanced with energy monitoring and discovery.

**New Methods**:
```python
# Energy Monitoring
manager.record_power_reading(reading)
manager.get_power_consumption(actuator_id) → float
manager.get_energy_stats(actuator_id, hours=24) → dict
manager.get_cost_estimate(actuator_id, period="monthly") → dict
manager.get_total_power() → float

# Zigbee2MQTT Discovery
manager.get_discovered_devices() → list
manager.send_zigbee2mqtt_command(friendly_name, command) → bool
```

**Initialization Parameters**:
```python
ActuatorManager(
    mqtt_client=mqtt_client,
    event_bus=event_bus,
    enable_energy_monitoring=True,      # Enable power tracking
    enable_zigbee2mqtt_discovery=True,  # Enable device discovery
    electricity_rate_kwh=0.12           # Cost per kWh
)
```

---

## 🔄 Architecture Flow

### Power Monitoring Flow
```
Zigbee2MQTT Smart Switch
    ↓ MQTT: zigbee2mqtt/{device}
    ↓ Publishes: {power: 150, voltage: 230, current: 0.65, energy: 3.5}
Zigbee2MQTTDiscoveryService
    ↓ Subscribes to device topics
    ↓ Detects power monitoring capability
    ↓ Registers state callback
ActuatorManager._on_device_state_update()
    ↓ Extracts power data
    ↓ Creates EnergyReading
EnergyMonitoringService.record_reading()
    ↓ Stores in memory (1000 readings per actuator)
    ↓ Calculates statistics
    ↓ Updates cost estimates
API: GET /api/devices/actuators/{id}/power
    ↓ Returns current power consumption
```

### Discovery Flow
```
Zigbee2MQTT Bridge
    ↓ MQTT: zigbee2mqtt/bridge/devices
    ↓ Publishes: [{ieee_address, model, vendor, definition}]
Zigbee2MQTTDiscoveryService._on_devices_message()
    ↓ Parses device list
    ↓ Extracts capabilities (exposes)
    ↓ Detects device type (switch, light, plug)
    ↓ Checks for power monitoring
    ↓ Creates DiscoveredDevice
ActuatorManager._on_device_discovered()
    ↓ Logs discovery
    ↓ Registers power monitoring callback (if supported)
    ↓ Notifies discovery callbacks
```

---

## 🌐 API Endpoints

### Energy Monitoring Endpoints

#### `GET /api/devices/actuators/{actuator_id}/power`
Get current power consumption for an actuator.

**Response**:
```json
{
  "ok": true,
  "data": {
    "actuator_id": 1,
    "power_watts": 150.5,
    "is_estimated": false,
    "timestamp": "2025-11-15T10:30:00"
  }
}
```

#### `GET /api/devices/actuators/{actuator_id}/energy?hours=24`
Get energy consumption statistics.

**Query Parameters**:
- `hours` (optional): Number of hours to analyze (default: 24)

**Response**:
```json
{
  "ok": true,
  "data": {
    "actuator_id": 1,
    "total_energy_kwh": 3.6,
    "average_power_watts": 150.0,
    "peak_power_watts": 180.0,
    "runtime_hours": 24.0,
    "cost_estimate": 0.43,
    "last_updated": "2025-11-15T10:30:00"
  }
}
```

#### `GET /api/devices/actuators/{actuator_id}/cost?period=monthly`
Get electricity cost estimates.

**Query Parameters**:
- `period` (optional): `daily`, `weekly`, `monthly`, `yearly` (default: monthly)

**Response**:
```json
{
  "ok": true,
  "data": {
    "actuator_id": 1,
    "cost": 13.00,
    "energy_kwh": 108.0,
    "period": "monthly"
  }
}
```

#### `GET /api/devices/actuators/total-power`
Get total power consumption across all actuators.

**Response**:
```json
{
  "ok": true,
  "data": {
    "total_power_watts": 450.5,
    "unit_breakdown": [
      {
        "unit_id": 1,
        "unit_name": "Greenhouse 1",
        "power_watts": 300.0,
        "actuator_count": 3
      }
    ],
    "timestamp": "2025-11-15T10:30:00"
  }
}
```

### Zigbee2MQTT Discovery Endpoints

#### `GET /api/devices/zigbee2mqtt/devices`
Get all discovered Zigbee2MQTT devices across all units.

**Response**:
```json
{
  "ok": true,
  "data": {
    "devices": [
      {
        "ieee_address": "0x00124b001234abcd",
        "friendly_name": "smart_plug_1",
        "model": "TS011F",
        "vendor": "TuYa",
        "description": "Smart plug (with power monitoring)",
        "device_type": "switch",
        "supports_power_monitoring": true,
        "endpoints": [1],
        "discovered_at": "2025-11-15T10:00:00",
        "unit_id": 1,
        "unit_name": "Greenhouse 1",
        "capabilities": [
          {
            "name": "state",
            "type": "binary",
            "property": "state",
            "access": 7,
            "readable": true,
            "writable": true
          },
          {
            "name": "power",
            "type": "numeric",
            "property": "power",
            "access": 1,
            "readable": true,
            "writable": false
          }
        ]
      }
    ],
    "count": 1
  }
}
```

#### `GET /api/devices/zigbee2mqtt/devices/unit/{unit_id}`
Get discovered devices for a specific unit.

**Response**:
```json
{
  "ok": true,
  "data": {
    "unit_id": 1,
    "devices": [...],
    "count": 3
  }
}
```

#### `POST /api/devices/zigbee2mqtt/command`
Send command to a Zigbee2MQTT device.

**Request Body**:
```json
{
  "unit_id": 1,
  "friendly_name": "smart_plug_1",
  "command": {
    "state": "ON"
  }
}
```

**Response**:
```json
{
  "ok": true,
  "data": {
    "success": true,
    "message": "Command sent to smart_plug_1"
  }
}
```

---

## ⚡ Default Power Profiles

Pre-configured power profiles for common actuators:

| Actuator Type | Rated Power | Standby Power | Efficiency | Power Curve |
|--------------|-------------|---------------|------------|-------------|
| Grow Light   | 150W        | 2W            | 90%        | -           |
| Water Pump   | 50W         | 1W            | 85%        | -           |
| Fan          | 30W         | 0.5W          | 90%        | ✓ (0-100%)  |
| Heater       | 1500W       | 5W            | 98%        | -           |
| Humidifier   | 40W         | 1W            | 88%        | -           |

**Fan Power Curve Example**:
- 0%: 0.5W (standby)
- 25%: 10W
- 50%: 18W
- 75%: 24W
- 100%: 30W

---

## 🔧 Configuration

### Per-Unit Configuration
Energy monitoring and discovery are configured per unit in `UnitRuntimeManager`:

```python
self.actuator_manager = ActuatorManager(
    mqtt_client=mqtt_client,
    event_bus=self.event_bus,
    enable_energy_monitoring=True,
    enable_zigbee2mqtt_discovery=True,
    electricity_rate_kwh=0.12  # Configurable per region
)
```

### Custom Power Profiles
Register custom power profiles for specific devices:

```python
energy_service = actuator_manager.energy_monitoring

energy_service.register_power_profile(
    actuator_type='custom_led_array',
    rated_power_watts=200.0,
    standby_power_watts=3.0,
    efficiency_factor=0.92,
    power_curve={
        0: 3.0,
        20: 50.0,
        40: 90.0,
        60: 130.0,
        80: 170.0,
        100: 200.0
    }
)
```

---

## 📊 Use Cases

### 1. Monitor Grow Light Power Usage
```bash
# Get current power
GET /api/devices/actuators/1/power

# Get 24-hour energy stats
GET /api/devices/actuators/1/energy?hours=24

# Get monthly cost estimate
GET /api/devices/actuators/1/cost?period=monthly
```

### 2. Discover Smart Plugs
```bash
# List all discovered devices
GET /api/devices/zigbee2mqtt/devices

# List devices for unit 1
GET /api/devices/zigbee2mqtt/devices/unit/1
```

### 3. Control Smart Switch
```bash
POST /api/devices/zigbee2mqtt/command
{
  "unit_id": 1,
  "friendly_name": "grow_light_plug",
  "command": {"state": "ON"}
}
```

### 4. Track Total Power Consumption
```bash
# Get total power across all units
GET /api/devices/actuators/total-power
```

---

## 🔌 Supported Devices

### Smart Switches with Power Monitoring
- **TuYa TS011F** - Smart plug with power monitoring
- **Sonoff S31** - Zigbee smart plug
- **BlitzWolf BW-SHP13** - Zigbee smart plug
- **Nous A1Z** - Smart plug with energy monitoring

### Requirements
- Device must support Zigbee2MQTT
- Must report `power`, `voltage`, `current`, and/or `energy`
- Must have writable `state` capability

---

## 🛠️ Testing

### Manual Testing

1. **Start Zigbee2MQTT bridge**
2. **Pair a smart plug** with power monitoring
3. **Check discovery**:
   ```bash
   GET /api/devices/zigbee2mqtt/devices
   ```
4. **Turn on the plug**:
   ```bash
   POST /api/devices/zigbee2mqtt/command
   {
     "unit_id": 1,
     "friendly_name": "test_plug",
     "command": {"state": "ON"}
   }
   ```
5. **Monitor power consumption**:
   ```bash
   GET /api/devices/actuators/1/power
   ```

---

## 📈 Future Enhancements

1. **Database Persistence**
   - Store energy readings in database for long-term history
   - Historical charts and trend analysis

2. **Power Alerts**
   - Configurable power threshold alerts
   - Anomaly detection for unusual power consumption

3. **Cost Optimization**
   - Time-of-use rate support
   - Cost-aware scheduling

4. **Energy Reports**
   - Daily/weekly/monthly energy reports
   - PDF export functionality

5. **Frontend Dashboard**
   - Real-time power gauges
   - Energy usage charts
   - Cost calculator widget
   - Device discovery interface

---

## 🐛 Troubleshooting

### No Power Data Appearing
1. Check if Zigbee2MQTT is running
2. Verify device supports power monitoring
3. Check MQTT connection
4. Ensure device is paired and active

### Discovery Not Working
1. Verify MQTT client is connected
2. Check Zigbee2MQTT bridge topic: `zigbee2mqtt/bridge/devices`
3. Ensure `enable_zigbee2mqtt_discovery=True`
4. Check logs for discovery messages

### Inaccurate Power Estimates
1. Verify power profile is registered for actuator type
2. Update power profile with accurate values
3. Use devices with built-in power monitoring for accurate data

---

## 📝 Summary

The energy monitoring and Zigbee2MQTT discovery integration provides comprehensive power tracking and smart device management for the SYSGrow system. Each growth unit independently tracks power consumption, discovers devices, and calculates costs, enabling precise energy management and cost optimization.

**Key Benefits**:
- ✅ Real-time power monitoring
- ✅ Automatic device discovery
- ✅ Cost tracking and estimation
- ✅ Per-unit energy management
- ✅ RESTful API for integration
- ✅ Extensible power profiling system
