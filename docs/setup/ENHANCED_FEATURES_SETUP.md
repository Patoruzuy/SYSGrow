# Advanced Insights Setup Guide for SYSGrow

## Overview
This document outlines the advanced insights features added to SYSGrow for comprehensive IoT plant monitoring with ML capabilities.

## New Features

### 1. ZigBee Energy Monitor Integration
- **Real-time energy consumption monitoring** for all connected devices
- **Device-specific power consumption estimation** (lights, fans, extractors, heaters, etc.)
- **Cost calculation** based on local electricity rates
- **Energy efficiency analysis** and recommendations

### 2. Plant Health Monitoring & Disease Detection
- **Symptom tracking** with photo documentation
- **Disease identification** (fungal, bacterial, viral, pest)
- **Environmental correlation analysis** 
- **Treatment recommendations** based on symptoms
- **Health trend analysis** over time

### 3. Enhanced Environment Information Collection
- **Room dimensions and volume** calculation
- **Insulation and ventilation** quality assessment
- **Climate-specific adjustments** for different locations
- **Energy requirement estimation** based on environment
- **Optimization recommendations** for efficiency

### 4. Automated ML Training System
- **Scheduled nightly training** (3 AM default) with comprehensive data
- **Multi-target prediction models** (temperature, humidity, soil moisture, power consumption)
- **Device control prediction** (when to turn on/off devices)
- **Plant health prediction** based on environmental conditions
- **Cross-validation** and model performance tracking

## Python Dependencies

Add these to your requirements.txt:

```
# Enhanced ML and Data Science
scikit-learn>=1.3.0
pandas>=2.0.0
numpy>=1.24.0
joblib>=1.3.0

# Scheduling
schedule>=1.2.0

# ZigBee Communication
zigpy>=0.59.0
zigpy-znp>=0.11.0  # For TI CC2652/CC1352 coordinators
zigpy-deconz>=0.21.0  # For ConBee/RaspBee coordinators

# Additional ML libraries (optional but recommended)
matplotlib>=3.7.0  # For plotting training results
seaborn>=0.12.0    # For advanced visualizations
```

## Installation Instructions

### 1. Install Python Dependencies
```bash
pip install -r requirements.txt
```

### 2. Install ZigBee Coordinator Support
Choose based on your ZigBee coordinator:

**For Texas Instruments CC2652/CC1352:**
```bash
pip install zigpy-znp
```

**For Dresden Elektronik ConBee/RaspBee:**
```bash
pip install zigpy-deconz
```

**For Ember/Silicon Labs coordinators:**
```bash
pip install bellows
```

### 3. Database Schema Upgrade
Run the database upgrade script:
```bash
python database/schema_upgrade.py
```

### 4. Configuration Files
Create the ZigBee configuration file:
```bash
mkdir -p config
# Edit config/zigbee_config.json with your coordinator settings
```

## ZigBee Energy Monitor Setup

### Hardware Requirements
- ZigBee 3.0 coordinator (USB dongle)
- ZigBee energy monitoring smart plugs/switches
- Compatible devices: Sonoff S31, Aqara Smart Plug, etc.

### Configuration
1. **Connect ZigBee Coordinator**
   - Plug in USB coordinator
   - Note the device path (e.g., `/dev/ttyUSB0` on Linux, `COM3` on Windows)

2. **Update Configuration**
   ```json
   {
     "device_path": "/dev/ttyUSB0",
     "pan_id": "0x1234",
     "extended_pan_id": "00:11:22:33:44:55:66:77",
     "network_key": "11:22:33:44:55:66:77:88:99:AA:BB:CC:DD:EE:FF:00",
     "scan_channels": [11, 15, 20, 25],
     "permit_join_duration": 60
   }
   ```

3. **Pair Energy Monitors**
   - Put energy monitoring devices in pairing mode
   - Use the `/api/energy/discover` endpoint to scan for devices
   - Assign devices to specific grow units

## Environment Information Setup

### Required Information per Grow Unit
- **Room Dimensions**: Width, length, height (meters)
- **Insulation Quality**: Poor, average, good, excellent
- **Ventilation Type**: Natural, forced, HVAC
- **Window Area**: Square meters of windows
- **Light Source**: LED, HPS, fluorescent, natural
- **Climate Location**: Tropical, temperate, arid, cold
- **Electricity Cost**: Local kWh rate

### API Usage
```javascript
// Save environment information
POST /api/environment/{unit_id}
{
  "room_width": 3.0,
  "room_length": 4.0,
  "room_height": 2.5,
  "insulation_type": "good",
  "ventilation_type": "forced",
  "window_area": 2.0,
  "light_source_type": "led",
  "ambient_light_hours": 8.0,
  "location_climate": "temperate",
  "outdoor_temperature_avg": 20.0,
  "outdoor_humidity_avg": 60.0,
  "electricity_cost_per_kwh": 0.12
}
```

## Plant Health Monitoring

### Usage Workflow
1. **Record Observations**
   - Document symptoms (yellowing leaves, spots, wilting, etc.)
   - Take photos of affected plants
   - Specify severity (1-5 scale)
   - Note environmental conditions

2. **Get Recommendations**
   - System analyzes symptoms vs. environmental data
   - Provides likely causes and treatments
   - Tracks effectiveness over time

### API Usage
```javascript
// Record health observation
POST /api/plant-health/observation
{
  "unit_id": 1,
  "health_status": "stressed",
  "symptoms": ["yellowing_leaves", "brown_spots"],
  "disease_type": "fungal",
  "severity_level": 3,
  "affected_parts": ["leaves"],
  "environmental_factors": {
    "high_humidity": true,
    "poor_air_circulation": true
  },
  "notes": "Lower leaves showing yellowing with brown spots",
  "treatment_applied": "Improved ventilation, reduced watering"
}
```

## ML Training System

### Automatic Training Schedule
- **Daily Training**: 3:00 AM (configurable)
- **Data Collection**: Every hour
- **Energy Monitoring**: Every 15 minutes
- **Health Checks**: 9:00 AM daily

### Manual Training
```javascript
// Trigger immediate training
POST /api/ml/train
{
  "unit_id": 1  // Optional: specific unit, omit for global
}
```

### Training Data Requirements
- **Minimum Samples**: 100 data points for reliable training
- **Data Quality**: Automatic filtering of outliers and invalid readings
- **Features**: 20+ environmental, energy, and context features
- **Targets**: Temperature, humidity, soil moisture, device states, plant health

## Integration with Existing System

### 1. Update Main Application
```python
from app.blueprints.api.insights import init_insights_routes
from task_scheduler import TaskScheduler

# Initialize advanced insights features
init_insights_routes(app, database_handler)

# Initialize insights scheduler
scheduler = TaskScheduler(database_handler)
```

### 2. Frontend Integration
Add new sections to settings.html:
- Environment information form
- Plant health recording interface
- Energy monitoring dashboard
- ML training status and controls

### 3. MQTT Integration
New MQTT topics:
- `sysgrow/energy/{unit_id}/consumption`
- `sysgrow/health/{unit_id}/status`
- `sysgrow/ml/training/status`
- `sysgrow/environment/{unit_id}/analysis`

## Usage Examples

### Energy Monitoring
```python
# Get energy consumption for unit 1
response = requests.get('/api/energy/consumption/1?hours=24')
data = response.json()

print(f"Daily cost: ${data['cost_estimate']['daily_cost']}")
print(f"Power consumption: {data['consumption_history'][0]['power_watts']}W")
```

### Plant Health Tracking
```python
# Get health recommendations
response = requests.get('/api/plant-health/recommendations/1')
recommendations = response.json()

if recommendations['status'] != 'healthy':
    print(f"Health issue detected: {recommendations['status']}")
    for rec in recommendations['symptom_recommendations']:
        print(f"Issue: {rec['issue']}")
        print(f"Actions: {rec['recommended_actions']}")
```

### Environment Analysis
```python
# Get comprehensive environment analysis
response = requests.get('/api/environment/analysis/1')
analysis = response.json()

print(f"Air changes per hour: {analysis['climate_metrics']['air_changes_per_hour']}")
print(f"Energy density: {analysis['energy_estimates']['watts_per_m3']} W/m³")
```

## Troubleshooting

### Common Issues

1. **ZigBee Coordinator Not Found**
   - Check device path in configuration
   - Ensure USB permissions on Linux: `sudo usermod -a -G dialout $USER`
   - Verify coordinator compatibility

2. **ML Training Fails**
   - Check minimum data requirements (100+ samples)
   - Verify database contains sensor readings
   - Check log files for specific errors

3. **Energy Monitoring No Data**
   - Ensure ZigBee devices are paired correctly
   - Check network connectivity
   - Verify device compatibility

### Log Files
- `task_scheduler.log`: Scheduled task execution
- `zigbee_energy.log`: Energy monitoring activities
- `ml_training.log`: ML training sessions
- `plant_health.log`: Health monitoring events

## Performance Considerations

- **Database Size**: Enable periodic cleanup of old training data
- **ML Training**: Large datasets may require longer training times
- **Memory Usage**: Monitor memory consumption during training
- **Network Traffic**: ZigBee monitoring generates regular data

## Security Considerations

- **ZigBee Network**: Use strong network keys
- **Database**: Encrypt sensitive environment information
- **API Access**: Implement authentication for insights endpoints
- **File Uploads**: Validate plant health images for security

## Future Enhancements

Potential additions:
- **Weather API Integration**: Automatic outdoor condition updates
- **Advanced ML Models**: Deep learning for image-based plant health
- **Multi-Zone Control**: Support for multiple growing areas
- **Cloud Backup**: Remote data synchronization
- **Mobile App Integration**: Real-time notifications and control
