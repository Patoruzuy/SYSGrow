# Device UI Refactoring Plan

**Date:** December 9, 2025  
**Status:** 🔄 In Progress  
**Goal:** Consolidate all device management into devices.html with tabbed interface

## Overview

Move device management from settings.html to devices.html and organize by communication protocol.

## Current State

### devices.html
- GPIO device management (sensors, actuators)
- Zigbee2MQTT sensor cards (read-only display)
- Basic device health overview

### settings.html - Devices Tab
- ESP32-C6 device configuration (~450 lines)
- Zigbee2MQTT discovery and add device form (~200 lines)
- Complex provisioning workflows

## Proposed Structure

### New Tabbed Interface in devices.html

```
┌─────────────────────────────────────────────────────┐
│ Device Management                                    │
│ Add, remove, and monitor all devices                │
├─────────────────────────────────────────────────────┤
│ [Device Health Stats - 4 cards]                     │
├─────────────────────────────────────────────────────┤
│ ┌───────┬────────────┬───────────┬──────────────┐  │
│ │ GPIO  │ Zigbee2MQTT│ WiFi/MQTT │  ESP32-C6    │  │
│ └───────┴────────────┴───────────┴──────────────┘  │
│ ┌─────────────────────────────────────────────────┐│
│ │ [Active Tab Content]                             ││
│ │                                                   ││
│ │                                                   ││
│ └─────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────┘
```

### Tab 1: GPIO Devices (Existing)
**Content:**
- Add Actuator form (GPIO-based)
- Add Sensor form (GPIO-based)
- Active Actuators table
- Active Sensors table

**Status:** ✅ Already implemented

### Tab 2: Zigbee2MQTT Devices
**Content:**
- Device discovery button
- Discovered devices list (clickable)
- Add Zigbee device form (pre-fillable from discovery)
- Active Zigbee sensors cards (existing)

**To Move From:**
- `settings.html` lines ~800-950 (Zigbee2MQTT section)

**Updates Needed:**
- Merge with existing Zigbee sensor cards
- Add device removal capability
- Enhance with health metrics

### Tab 3: WiFi/MQTT Devices
**Content:**
- Add WiFi-connected device form
- MQTT broker configuration
- Device credentials management
- Active WiFi devices table

**Status:** 🆕 New section (for future WiFi-only devices)

### Tab 4: ESP32-C6 Devices
**Content:**
- Device discovery & provisioning
- Device configuration form
  - Communication settings
  - WiFi configuration
  - Power management
  - Irrigation control (conditional)
  - OTA updates
- Active ESP32-C6 devices list

**To Move From:**
- `settings.html` lines 256-800 (~550 lines)

**Includes:**
1. Device discovery/scanning
2. Device type selection (sensors/relays/irrigation/hybrid)
3. Connection mode (WiFi/Zigbee/BLE/Auto)
4. WiFi setup methods (SmartConfig/BLE/AP/WPS)
5. Power management settings
6. Irrigation-specific controls
7. OTA firmware update configuration

## Implementation Steps

### Phase 1: Create Tab Structure ✅
- [ ] Add tab navigation to devices.html
- [ ] Create tab panel containers
- [ ] Add tab switching JavaScript
- [ ] Style tabs to match existing theme

### Phase 2: Move Zigbee2MQTT Section
- [ ] Extract Zigbee discovery/add form from settings.html
- [ ] Move to Tab 2 in devices.html
- [ ] Merge with existing Zigbee sensor cards
- [ ] Update JavaScript event handlers
- [ ] Test discovery and add workflow

### Phase 3: Move ESP32-C6 Section
- [ ] Extract entire ESP32-C6 section from settings.html
- [ ] Move to Tab 4 in devices.html
- [ ] Preserve all form fields and validation
- [ ] Update form IDs to avoid conflicts
- [ ] Migrate JavaScript event handlers
- [ ] Test provisioning workflow

### Phase 4: Create WiFi/MQTT Tab
- [ ] Design WiFi device form
- [ ] Add MQTT configuration fields
- [ ] Create device list/table
- [ ] Implement add/remove functionality

### Phase 5: Update Settings.html
- [ ] Remove moved sections from settings.html
- [ ] Update tab navigation (remove Devices tab)
- [ ] Add redirect/link to devices.html if needed
- [ ] Clean up unused JavaScript

### Phase 6: JavaScript Updates
- [ ] Move device-related JS from settings.js to devices.js
- [ ] Update API endpoint calls
- [ ] Ensure tab persistence (URL hash or localStorage)
- [ ] Add tab-specific initialization logic

### Phase 7: Testing
- [ ] Test all device types in each tab
- [ ] Verify form submissions
- [ ] Check device discovery
- [ ] Test provisioning workflows
- [ ] Validate device removal
- [ ] Check responsive design

## Files to Modify

### Frontend Templates
- ✏️ `templates/devices.html` - Add tabs and move content
- ✏️ `templates/settings.html` - Remove device sections
- ✏️ `templates/macros.html` - Ensure all form macros work

### CSS
- ✏️ `static/css/devices.css` - Add tab styles
- ✏️ `static/css/settings.css` - Remove device-specific styles

### JavaScript
- ✏️ `static/js/devices_view.js` - Add tab logic and ESP32 handlers
- ✏️ `static/js/settings.js` - Remove device-related handlers

### Backend (if needed)
- ℹ️ No backend changes required (routes remain the same)

## Benefits

1. **Better Organization** - All device management in one place
2. **Protocol Separation** - Clear distinction between connection types
3. **Easier Navigation** - Users find devices by how they connect
4. **Reduced Settings Clutter** - Settings focused on app configuration
5. **Scalability** - Easy to add new device types (LoRa, Z-Wave, etc.)

## Migration Notes

### URL Updates
- Settings devices tab was at: `/settings#devices`
- New location will be: `/devices#esp32` or `/devices#zigbee`

### Backward Compatibility
- Add redirect in settings.html if user visits old URL
- Update all internal links to point to new locations

### User Communication
- Add notice in settings about device management move
- Update documentation/help text

## Success Criteria

- [ ] All device types accessible from devices.html
- [ ] Tab switching works smoothly
- [ ] All forms functional and validated
- [ ] Device discovery works for Zigbee and ESP32
- [ ] Provisioning workflows complete successfully
- [ ] No broken links or references
- [ ] Responsive design maintained
- [ ] JavaScript console error-free

## Next Steps

1. **Immediate:** Create tab structure in devices.html
2. **Short-term:** Move Zigbee2MQTT section (simpler)
3. **Medium-term:** Move ESP32-C6 section (more complex)
4. **Long-term:** Add WiFi/MQTT tab for future devices

---

**Status:** Ready to begin Phase 1
