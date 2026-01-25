# Sensor Analytics Page Consolidation

**Date:** December 21, 2025

## Summary

Consolidated three separate sensor analytics pages (`sensor_data.html`, `data_graph.html`, and related JS files) into one unified **Sensor Analytics** page with modular JavaScript architecture matching the dashboard pattern.

## Changes Made

### 1. Created New Unified Page
- **Template:** `templates/sensor_analytics.html`
- **CSS:** `static/css/sensor-analytics.css`
- **JavaScript Modules:**
  - `static/js/sensor-analytics/data-service.js` - Data fetching with caching
  - `static/js/sensor-analytics/ui-manager.js` - UI management, charts, statistics
  - `static/js/sensor-analytics/main.js` - Bootstrap and initialization
  - `static/js/sensor-analytics/README.md` - Complete documentation

### 2. Updated Routes
Both `/sensor-data` and `/data-graph` now serve the unified `sensor_analytics.html` template:
- `app/blueprints/ui/routes.py` - Updated `sensor_data()` and `data_graph()` functions

### 3. Updated Navigation
- Merged "Sensor Data" and "Data Graphs" menu items into single "Sensor Analytics" link
- Updated `templates/base.html` navigation section

### 4. Fixed API Issues
Corrected API method calls in `data-service.js`:
- ✅ `api.Growth.listUnits()` (was incorrectly `api.Unit.getUnits()`)
- ✅ `api.Device.getAllSensors()` / `api.Device.getSensorsByUnit(unitId)`
- ✅ `api.Plant.getPlantsByUnit(unitId)`
- ✅ `api.Status.getStatus()`

### 5. Archived Old Files
Renamed old files with `.old` extension:
- `templates/sensor_data.html.old`
- `templates/data_graph.html.old`
- `static/js/data_graph.js.old`
- `static/js/sensor_dashboard.js.old`
- `static/js/sensor_analytics.js.old`

## Features

The unified Sensor Analytics page includes:

### Data Visualization
- **Time-Series Analysis** - Multi-metric line charts with date range selection
- **Multi-Sensor Comparison** - Compare multiple sensors side-by-side
- **Sensor Trends** - Statistical bar charts (avg, min, max)

### Filters and Controls
- Unit selection (inherited from page context)
- Sensor selection (all or specific)
- Sensor type filter
- Metric selection (temperature, humidity, soil moisture, CO2, VOC, etc.)
- Time range selection (1h, 6h, 24h, 3d, 7d)
- Data grouping (by minute, hour, day)
- Plant overlay for health correlation

### Advanced Features
- **Saved Views** - Save and restore filter combinations
- **Custom Alerts** - Set thresholds and get notifications
- **Statistics** - Automatic calculation of avg, min, max, std dev, trends
- **Anomaly Detection** - Visual indicators for unusual readings
- **Real-time Updates** - Socket.IO integration for live data
- **CSV Export** - Download data for external analysis

### Data Table
- Recent sensor readings with quality indicators
- Load more pagination
- Sortable columns

## Architecture

Follows modular pattern from dashboard:

```
sensor-analytics/
├── data-service.js    → API calls, caching, data fetching
├── ui-manager.js      → DOM manipulation, charts, event handlers
└── main.js            → Initialization, dependency checking
```

### Dependencies
- Chart.js 4.4.0 for visualizations
- CacheService for 30-second TTL caching
- BaseManager for event management
- Socket.IO for real-time updates
- window.API for backend communication

## Testing

After clearing browser cache, verify:

1. ✅ Page loads without errors
2. ✅ Units dropdown populates
3. ✅ Sensors dropdown populates when unit selected
4. ✅ Charts render with data
5. ✅ Real-time updates work
6. ✅ Filters update data correctly
7. ✅ Statistics calculate properly
8. ✅ CSV export works

## Debugging

Enable debug logging in browser console:
```javascript
localStorage.setItem('sensor-analytics:debug', '1');
```

Check console for:
- `[SensorAnalyticsDataService] loadUnits response:` - Shows API responses
- `[SensorAnalyticsDataService] loadSensors response:` - Shows sensor data
- `[SensorAnalyticsUIManager]` - Shows UI operations

## Rollback

If issues occur, restore old files:
```bash
cd E:\Work\SYSGrow\backend
mv templates/sensor_data.html.old templates/sensor_data.html
mv templates/data_graph.html.old templates/data_graph.html
# Revert routes.py and base.html changes
```

## Next Steps

1. Test all features thoroughly
2. Add more chart types if needed
3. Consider adding export to PDF
4. Add more alert types (email, SMS)
5. Implement advanced anomaly detection algorithms
