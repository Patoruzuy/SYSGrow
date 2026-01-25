# Socket.IO Namespace Architecture

## Overview

The SYSGrow platform uses Socket.IO namespaces to organize real-time communication channels. This document describes the namespace structure and usage patterns.

## Namespaces

### `/sensors` - Real-Time Sensor Data

**Purpose**: Broadcasting live sensor readings from all sources (GPIO, I2C, MQTT, Zigbee2MQTT)

**Events**:
- `zigbee_sensor_data` - Zigbee2MQTT sensor updates
- `sensor_update` - GPIO/I2C sensor updates
- `request_zigbee_data` - Client→Server: Request initial Zigbee data

**Backend Implementation**:
```python
# workers/sensor_polling_service.py
socketio.emit('zigbee_sensor_data', payload, namespace='/sensors')
socketio.emit('sensor_update', payload, namespace='/sensors')
```

**Frontend Usage**:
```javascript
// Connect to /sensors namespace
const socket = io('/sensors');

// Listen for Zigbee sensor updates
socket.on('zigbee_sensor_data', function(data) {
    // data format: { friendly_name, temperature, humidity, battery, linkquality, ... }
    updateSensorDisplay(data);
});

// Listen for GPIO/I2C sensor updates
socket.on('sensor_update', function(data) {
    // data format: { unit_id, sensor_id, sensor_type, temperature, humidity, ... }
    updateSensorDisplay(data);
});
```

**Pages Using This Namespace**:
- `devices.html` - Device management page (Zigbee sensors)
- `fullscreen.html` - Fullscreen sensor display
- Future: Dashboard, analytics, monitoring pages

### `/notifications` - System Notifications (Future)

**Purpose**: Broadcasting system notifications, alerts, and messages

**Events** (Planned):
- `alert` - System alerts (critical, warning, info)
- `notification` - User notifications
- `system_event` - System-level events

**Backend Implementation** (When implemented):
```python
socketio.emit('alert', {
    'level': 'warning',
    'message': 'Temperature threshold exceeded',
    'timestamp': iso_now()
}, namespace='/notifications')
```

**Frontend Usage** (When implemented):
```javascript
const notificationSocket = io('/notifications');

notificationSocket.on('alert', function(data) {
    showAlert(data.level, data.message);
});

notificationSocket.on('notification', function(data) {
    showNotification(data);
});
```

## Architecture Benefits

### Separation of Concerns
- Sensor data is isolated from notifications/alerts
- Each namespace has a clear, single responsibility
- Easier to debug and monitor specific channels

### Scalability
- Clients can subscribe only to namespaces they need
- Reduces unnecessary data transfer
- Better performance for large-scale deployments

### Maintainability
- Clear organization makes code easier to understand
- New features can be added without affecting existing ones
- Backward compatible - can add new namespaces without breaking existing clients

## Data Flow

```
Hardware Layer (Adapters)
        ↓
Workers/sensor_polling_service.py
        ↓
Socket.IO Namespaces
        ├─→ /sensors (real-time sensor data)
        └─→ /notifications (future: alerts & notifications)
        ↓
Frontend (HTML/JavaScript)
        ├─→ devices.html
        ├─→ fullscreen.html
        └─→ dashboard.html (future)
```

## Migration Notes

### Old Architecture (Deprecated)
```javascript
// ❌ Old: Default namespace
const socket = io();
socket.on('sensor_data', ...);
```

### New Architecture (Current)
```javascript
// ✅ New: Explicit namespace
const socket = io('/sensors');
socket.on('sensor_update', ...);
socket.on('zigbee_sensor_data', ...);
```

## Adding New Namespaces

When adding a new namespace:

1. **Define the namespace constant** in the worker/service:
```python
NAMESPACE = '/your_namespace'
```

2. **Emit events with namespace**:
```python
socketio.emit('event_name', payload, namespace=NAMESPACE)
```

3. **Update frontend**:
```javascript
const socket = io('/your_namespace');
socket.on('event_name', callback);
```

4. **Document in this file**:
- Purpose
- Events
- Data formats
- Example usage

## Best Practices

### Backend
- Always specify namespace when emitting
- Centralize emissions in workers/services (not adapters)
- Use descriptive event names
- Include timestamp in all payloads
- Handle errors gracefully

### Frontend
- Connect to specific namespaces (avoid default)
- Use meaningful variable names (`sensorSocket`, `notificationSocket`)
- Clean up connections on page unload
- Handle connection/disconnection gracefully
- Display connection status to users

## Testing

Test each namespace independently:

```bash
# Test /sensors namespace
curl http://localhost:5001/api/devices/v2/zigbee2mqtt/discover
# Watch browser console for 'zigbee_sensor_data' events

# Test connectivity
# Open browser dev tools → Network → WS
# Look for Socket.IO handshake on /sensors namespace
```

## Future Enhancements

- `/actuators` - Real-time actuator control and status
- `/camera` - Live camera feed and snapshots
- `/system` - System health, logs, and diagnostics
- `/chat` - User-to-user or user-to-system messaging
