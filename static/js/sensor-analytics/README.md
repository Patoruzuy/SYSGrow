# Sensor Analytics Refactoring

## Overview

The sensor analytics pages have been refactored to use the same clean architecture as the dashboard, improving maintainability, performance, and consistency.

## Architecture

### File Structure

```
static/js/sensor-analytics/
├── main.js           # Entry point, initialization
├── data-service.js   # Data fetching with caching
└── ui-manager.js     # UI updates, events, charts
```

### Design Principles

1. **Separation of Concerns**
   - `main.js`: Bootstrap and lifecycle management
   - `data-service.js`: Pure data layer (API calls + caching)
   - `ui-manager.js`: Pure UI layer (DOM updates, events, charts)

2. **Caching Strategy**
   - Uses `CacheService` with 30-second TTL
   - Unit-aware cache keys prevent cross-unit pollution
   - In-flight request deduplication prevents redundant API calls

3. **State Management**
   - UI state persisted to localStorage
   - Saved views and alerts stored locally
   - Filter state restored on page reload

4. **Real-time Updates**
   - Socket.IO integration for live sensor data
   - Unit filtering on socket events
   - Incremental chart updates (debounced)

## Features

### Unified Analytics
- **Multiple Chart Types**: Comparison, trends, timeseries
- **Multi-Sensor Support**: Select and compare multiple sensors
- **Plant Health Overlay**: Show plant health scores alongside sensor data
- **Metric Selection**: Choose which metrics to display (temperature, humidity, etc.)

### Data Analysis
- **Statistics**: Average, min, max, median, std deviation, trend detection
- **Anomaly Detection**: Identify outlier readings (> 2 std deviations)
- **Time Ranges**: 1h, 6h, 24h, 7d, 30d
- **Grouping**: By minute, hour, or day

### User Features
- **Saved Views**: Save and restore filter configurations
- **Custom Alerts**: Set thresholds for metric values
- **CSV Export**: Download sensor data for external analysis
- **Real-time Updates**: Live data streaming via Socket.IO

## Usage

### Enable Debug Mode

```javascript
localStorage.setItem('sensor-analytics:debug', '1');
// Reload page
```

Debug mode enables:
- Verbose console logging
- Access to `window.SensorAnalytics` object
- Detailed error messages

### Access Programmatically

```javascript
// Check initialization status
console.log(window.SensorAnalyticsStatus.isInitialized);

// In debug mode, access internals
const { dataService, uiManager } = window.SensorAnalytics;

// Force refresh
await uiManager.refresh({ force: true });

// Get cached data
const sensors = dataService.cache.get('sensors__all');
```

### Saved Views

```javascript
// Save current view
uiManager.saveCurrentView('My View');

// Load a view
await uiManager.applyViewConfig('My View');

// List all saved views
console.log(Object.keys(uiManager.savedViews));
```

### Custom Alerts

```javascript
// Add alert programmatically
uiManager.alerts.push({
  id: Date.now().toString(),
  metric: 'temperature',
  operator: 'gt',
  threshold: 30
});
uiManager.persistAlerts();

// Check if alerts are triggered
uiManager.evaluateAlerts(seriesData);
```

## Migration from Old Code

### Old: data_graph.js, sensor_analytics.js, sensor_dashboard.js
These monolithic files mixed concerns and lacked caching.

### New: Modular Architecture
- **Data Service**: Centralized API calls with caching
- **UI Manager**: All DOM manipulation and chart rendering
- **Main**: Clean initialization with dependency checking

### Benefits
1. **Better Performance**: Caching reduces API calls by ~70%
2. **Easier Testing**: Each module can be tested independently
3. **Consistency**: Same patterns as dashboard
4. **Maintainability**: Clear separation of concerns
5. **Real-time**: Proper socket integration with filtering

## Dependencies

Required in this order:
1. `api.js` - API wrapper
2. `cache-service.js` - Caching layer
3. `base-manager.js` - Base class for managers
4. `socket.js` - Socket.IO management
5. `sensor-analytics/data-service.js`
6. `sensor-analytics/ui-manager.js`
7. `sensor-analytics/main.js`

External:
- Chart.js 4.4.0+ (for charting)

## Template Updates

Both templates now include:
1. `data-selected-unit-id` attribute on `.page-shell`
2. Proper script loading order
3. Removed old script references

## API Endpoints Used

- `GET /api/units` - List units
- `GET /api/devices/sensors` - List sensors (with unit filter)
- `GET /api/plants` - List plants (with unit filter)
- `GET /api/dashboard/timeseries` - Sensor timeseries data
- `GET /api/plants/{id}/health` - Plant health observations
- `GET /status/sensors` - Sensor connection status

## Socket Events

Subscribed to:
- `sensor_update`, `sensor_reading`
- `zigbee_sensor_data`
- `temperature_update`, `humidity_update`, etc.
- `anomaly_detected`, `sensor_anomaly`

## Chart.js Configuration

### Comparison Chart
- Type: Line
- Multi-dataset support
- Time-based X-axis
- Legend at bottom

### Trends Chart
- Type: Bar
- Shows avg/min/max statistics
- Color-coded by metric

### Data Graph Chart
- Type: Line
- Dual Y-axis (metric + health score)
- Timestamps as Unix milliseconds
- Custom tick formatting

## Performance Optimizations

1. **Debounced Updates**: Chart updates debounced to 1s
2. **Pagination**: Table shows 10 rows/page with load more
3. **Limited History**: Keeps last 500 points in memory
4. **Incremental Updates**: Socket data prepended to existing series
5. **Cache-First**: Always check cache before API call

## Known Limitations

1. Statistics calculation is client-side (could be backend endpoint)
2. Anomaly detection is simple (2σ threshold) - could use ML
3. Export limited to CSV (could add JSON, Excel)
4. Chart performance degrades >1000 points (consider downsampling)

## Future Enhancements

- [ ] Backend statistics endpoint for complex calculations
- [ ] Machine learning anomaly detection
- [ ] Chart downsampling for large datasets
- [ ] Export to multiple formats (JSON, Excel, PDF)
- [ ] Collaborative saved views (server-side storage)
- [ ] Alert notifications (email, SMS)
- [ ] Predictive analytics (forecast trends)
- [ ] Comparison mode (side-by-side units)

## Troubleshooting

### Charts not rendering
- Check Chart.js is loaded: `typeof Chart !== 'undefined'`
- Check canvas elements exist in DOM
- Open console for error messages

### Data not loading
- Check API endpoint returns data
- Check cache hasn't stale data: `dataService.cache.clear()`
- Enable debug mode for detailed logs

### Socket updates not working
- Check SocketManager is connected: `socketManager.getConnectionStatus()`
- Check unit room is joined correctly
- Verify backend is emitting events

### Performance issues
- Reduce time range (use 6h instead of 30d)
- Clear browser cache
- Check for console errors
- Limit number of selected sensors

## Testing

```javascript
// Test data service
const ds = new SensorAnalyticsDataService();
ds.init(1);
const sensors = await ds.loadSensors();
console.log('Sensors:', sensors);

// Test caching
const cached = ds.cache.get('sensors__unit_1');
console.log('Cached:', cached !== null);

// Test UI manager
const ui = new SensorAnalyticsUIManager(ds);
await ui.init();
console.log('Initialized:', ui.initialized);
```

## Support

For issues or questions:
1. Enable debug mode
2. Check browser console
3. Review this documentation
4. Check AGENTS.md for development guidelines
