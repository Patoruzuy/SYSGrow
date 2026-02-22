# ESP32-C6 Irrigation Module Implementation

## Overview
This document outlines the complete implementation of ESP32-C6 irrigation module support in the SYSGrow application. The irrigation module is designed to control water pumps and mist blowers for automated plant irrigation and humidity control.

## Features Implemented

### 1. Device Type Selection
- Added "ESP32-C6 Irrigation" option to device type dropdown
- Conditional form sections that show/hide based on device type selection
- Proper JavaScript handling for dynamic form updates

### 2. GPIO Pin Configuration
- **Water Pump Pin**: GPIO pin selection for main irrigation pump control
- **Mist Blower Pin**: GPIO pin selection for mist blower/humidifier control
- GPIO options: 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 18, 19, 20, 21

### 3. Timing Controls
- **Pump Duration**: How long the water pump runs per irrigation cycle (1-300 seconds)
- **Mist Duration**: How long the mist blower operates (1-60 seconds)
- **Irrigation Interval**: Time between automatic irrigation cycles (1-1440 minutes)

### 4. Automation Features
- **Auto Irrigation**: Enable/disable automatic irrigation based on moisture levels
- **Moisture Threshold**: Soil moisture percentage that triggers automatic irrigation (0-100%)

### 5. Safety Features
- **Max Pump Runtime**: Maximum continuous pump operation time (60-600 seconds)
- **Flow Sensor**: Optional water flow monitoring
- **Emergency Stop**: Hardware emergency stop button support

### 6. Advanced Controls
- **Flow Sensor Pin**: GPIO pin for water flow sensor (when enabled)
- **Emergency Stop Pin**: GPIO pin for emergency stop button (when enabled)

## Technical Implementation

### Frontend (HTML/CSS/JavaScript)

#### HTML Structure
```html
<div class="settings-section conditional-field" data-device="irrigation">
    <!-- GPIO Pin Configuration -->
    <!-- Timing Settings -->
    <!-- Automation Settings -->
    <!-- Safety Features -->
</div>
```

#### CSS Features
- Conditional field display logic
- Modern form styling with grid layouts
- Visual indicators for safety features (⚠️ warning icons)
- Responsive design for mobile devices
- Professional styling consistent with existing UI

#### JavaScript Functionality
- Dynamic form field showing/hiding based on device type
- Form validation and data serialization
- API integration for saving/loading irrigation settings
- Real-time conditional field updates

### Backend Integration Points

#### API Endpoints (Recommended)
```
PUT /api/esp32/device/{device_id}
GET /api/esp32/device/{device_id}
POST /api/esp32/irrigation/test/{device_id}
```

#### Data Structure
```json
{
  "device_type": "irrigation",
  "water_pump_pin": 2,
  "mist_blower_pin": 3,
  "pump_duration": 30,
  "mist_duration": 10,
  "irrigation_interval": 60,
  "moisture_threshold": 30,
  "auto_irrigation": true,
  "max_pump_runtime": 300,
  "enable_flow_sensor": true,
  "flow_sensor_pin": 4,
  "enable_emergency_stop": true,
  "emergency_stop_pin": 5
}
```

## ESP32-C6 Firmware Requirements

### Core Functionality
1. **GPIO Control**: Digital output control for pumps and mist blowers
2. **Timing Management**: Precise timing control for irrigation cycles
3. **Sensor Reading**: Analog input for soil moisture sensors
4. **Safety Monitoring**: Flow sensor reading and emergency stop handling
5. **MQTT Communication**: Status reporting and remote control
6. **Configuration Storage**: EEPROM/Flash storage for settings

### Recommended Libraries
- **ESP32 Arduino Core**: Base framework
- **ArduinoJson**: Configuration management
- **PubSubClient**: MQTT communication
- **WiFiManager**: WiFi provisioning
- **EEPROM**: Settings persistence

### Safety Features Implementation
```cpp
// Pump safety cutoff
unsigned long pumpStartTime = millis();
if (millis() - pumpStartTime > maxPumpRuntime * 1000) {
    digitalWrite(WATER_PUMP_PIN, LOW);
    // Send alert via MQTT
}

// Emergency stop monitoring
if (digitalRead(EMERGENCY_STOP_PIN) == LOW) {
    digitalWrite(WATER_PUMP_PIN, LOW);
    digitalWrite(MIST_BLOWER_PIN, LOW);
    // Send emergency alert
}
```

## File Modifications Made

### 1. settings.html
- Added irrigation device type option
- Implemented comprehensive irrigation configuration form
- Added conditional field logic with `data-device="irrigation"`
- Updated JavaScript for device type handling
- Enhanced form submission to handle irrigation-specific data

### 2. styles.css
- Added conditional field styling for irrigation module
- Implemented subsection title styling
- Added checkbox styling improvements
- Added safety feature visual indicators
- Enhanced GPIO pin selection styling

## Usage Instructions

### For Administrators
1. Navigate to Settings → Devices tab
2. Click "Discover ESP32-C6 Devices" to scan for available modules
3. Select an irrigation module from the device list
4. Choose "ESP32-C6 Irrigation" as device type
5. Configure GPIO pins for water pump and mist blower
6. Set timing parameters and moisture thresholds
7. Enable safety features as needed
8. Save configuration and test functionality

### For Developers
1. Implement backend API endpoints for irrigation device management
2. Develop ESP32-C6 firmware with irrigation control logic
3. Add MQTT topics for irrigation status and control
4. Implement safety monitoring and alert systems
5. Test with actual hardware components

## Future Enhancements

### Possible Additions
1. **Multiple Zone Support**: Control multiple irrigation zones
2. **Weather Integration**: Adjust irrigation based on weather data
3. **Advanced Scheduling**: Calendar-based irrigation scheduling
4. **Nutrient Dosing**: Integration with fertilizer pumps
5. **Water Level Monitoring**: Tank level sensors
6. **Pressure Monitoring**: Water pressure sensors for pump health

### Scalability Considerations
- Support for irrigation controller networks
- Central irrigation management dashboard
- Historical irrigation data logging
- Machine learning for optimal irrigation scheduling

## Testing Checklist

### Frontend Testing
- [ ] Device type selection shows/hides irrigation fields correctly
- [ ] Form validation works for all input fields
- [ ] Settings save and load properly
- [ ] Responsive design works on mobile devices
- [ ] Accessibility features function correctly

### Backend Testing
- [ ] API endpoints handle irrigation data correctly
- [ ] Database storage and retrieval works
- [ ] MQTT integration functions properly
- [ ] Error handling is comprehensive

### Hardware Testing
- [ ] GPIO pins control pumps and mist blowers correctly
- [ ] Timing controls work accurately
- [ ] Safety features activate properly
- [ ] Moisture sensor readings are accurate
- [ ] Emergency stop functions immediately

## Conclusion

The ESP32-C6 irrigation module implementation provides a comprehensive solution for automated plant irrigation and humidity control. The system includes proper safety features, modern UI design, and extensible architecture for future enhancements.

The implementation follows modern web development practices with responsive design, accessibility compliance, and clean separation of concerns between frontend and backend components.