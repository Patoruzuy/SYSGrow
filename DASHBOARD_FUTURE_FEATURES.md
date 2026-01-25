# Dashboard Future Features Roadmap

This document tracks planned enhancements for the SYSGrow dashboard.

## Current Dashboard Features (Implemented)

### Core Widgets
- ✅ **Sensor Cards** - Real-time temperature, humidity, soil moisture, light, CO₂, energy
- ✅ **VPD Gauge** - Visual vapor pressure deficit indicator with zones
- ✅ **System Health KPI** - Overall health score with status
- ✅ **Device KPI Cards** - Active devices, healthy plants, critical alerts, energy usage
- ✅ **AI Insights Carousel** - Photoperiod, DIF, GDD, targets, stress, data quality
- ✅ **Actuator Controls** - Quick toggle for relays/devices
- ✅ **Plants Grid** - Plant health cards with modal details
- ✅ **Recent Activity** - Activity feed with timestamps
- ✅ **Critical Alerts** - Alert timeline with severity
- ✅ **Device Connectivity** - Connection status with filters
- ✅ **Device State Changes** - Recent actuator state history
- ✅ **Unit Settings Summary** - Thresholds, schedules, sensors, actuators

### New Widgets (January 2026)
- ✅ **Quick Stats Summary** - Readings count, anomalies, uptime, averages, data quality
- ✅ **Automation Status Panel** - Active schedules, lights/fans/irrigation status
- ✅ **Environment Quality Score** - SVG ring chart with factor breakdown
- ✅ **Sensor Health Matrix** - Healthy/warning/offline counts with dot visualization
- ✅ **Recent Journal Widget** - Scrollable journal entries with icons

---

## Planned Features

### Priority 1: High Value / Low Effort

#### 1. Weather Forecast Widget
**Status:** 🔲 Not Started  
**Effort:** Medium  
**Dependencies:** External weather API (OpenWeatherMap, WeatherAPI)

**Description:**
Display local weather forecast to help plan indoor growing adjustments.

**Features:**
- Current conditions (temp, humidity, pressure)
- 5-day forecast with icons
- Sunrise/sunset times
- Weather alerts
- Outdoor vs indoor comparison

**UI Elements:**
```
┌─────────────────────────────────────┐
│ 🌤️ Local Weather                   │
├─────────────────────────────────────┤
│ Now: 18°C ☁️  Humidity: 65%         │
│ Feels like: 16°C  Wind: 12 km/h     │
├─────────────────────────────────────┤
│ Mon  Tue  Wed  Thu  Fri             │
│ 🌧️   ⛅   ☀️   ☀️   🌤️              │
│ 15°  18°  22°  24°  20°             │
└─────────────────────────────────────┘
```

---

#### 2. Harvest Timeline Widget
**Status:** 🔲 Not Started  
**Effort:** Low  
**Dependencies:** Existing harvest data

**Description:**
Visual timeline showing upcoming and past harvests.

**Features:**
- Timeline view of all plants
- Days until expected harvest
- Past harvest history with yields
- Quick harvest action button

**UI Elements:**
```
┌─────────────────────────────────────┐
│ 🌿 Harvest Timeline                 │
├─────────────────────────────────────┤
│ ──●──────────●───────●──────→       │
│   ↑          ↑       ↑              │
│   Tomato     Basil   Lettuce        │
│   3 days     12 days 28 days        │
├─────────────────────────────────────┤
│ Recent: Peppers (Dec 28) - 1.2kg    │
└─────────────────────────────────────┘
```

---

#### 3. Water/Nutrient Schedule Widget
**Status:** 🔲 Not Started  
**Effort:** Low  
**Dependencies:** Irrigation workflow service

**Description:**
Countdown timer for next watering/feeding with schedule overview.

**Features:**
- Next watering countdown
- Next feeding countdown
- Weekly schedule calendar
- Quick water/feed buttons
- History of recent applications

**UI Elements:**
```
┌─────────────────────────────────────┐
│ 💧 Watering & Nutrients             │
├─────────────────────────────────────┤
│ Next Water: 2h 15m                  │
│ Next Feed:  3d 8h                   │
├─────────────────────────────────────┤
│ Mon ● Tue ○ Wed ● Thu ○ Fri ●      │
│ (● = watering day)                  │
└─────────────────────────────────────┘
```

---

#### 4. Growth Stage Tracker
**Status:** 🔲 Not Started  
**Effort:** Low  
**Dependencies:** Plant lifecycle data

**Description:**
Visual progress bar showing current growth stage for selected plant.

**Features:**
- Stage progress (Seedling → Vegetative → Flowering → Harvest)
- Days in current stage
- Expected transition dates
- Stage-specific tips

**UI Elements:**
```
┌─────────────────────────────────────┐
│ 🌱 Growth Stage: Vegetative        │
├─────────────────────────────────────┤
│ ●────●────◐────○────○              │
│ Seed  Veg  Flower  Fruit  Harvest   │
│        ↑                            │
│   Day 23 of ~45                     │
│   "Increase light to 16h/day"       │
└─────────────────────────────────────┘
```

---

### Priority 2: Medium Value / Medium Effort

#### 5. Photo Gallery Widget
**Status:** 🔲 Not Started  
**Effort:** Medium  
**Dependencies:** Camera service, journal photos

**Description:**
Carousel of recent plant photos from journal entries.

**Features:**
- Recent photos grid/carousel
- Before/after comparisons
- Photo timeline by plant
- Quick photo capture button
- Timelapse generation

---

#### 6. Cost/Energy Analytics Widget
**Status:** 🔲 Not Started  
**Effort:** Medium  
**Dependencies:** Energy monitoring service

**Description:**
Visual breakdown of energy costs and consumption patterns.

**Features:**
- Daily/weekly/monthly cost trends
- Cost by device type (lights, fans, pumps)
- Peak usage hours
- Cost projections
- Savings recommendations

**UI Elements:**
```
┌─────────────────────────────────────┐
│ ⚡ Energy & Costs                   │
├─────────────────────────────────────┤
│ Today: €1.24  │  This Week: €8.42   │
├─────────────────────────────────────┤
│ █████████░░░░ Lights    68%         │
│ ███░░░░░░░░░ Fans       22%         │
│ █░░░░░░░░░░░ Pumps      10%         │
├─────────────────────────────────────┤
│ Trend: ↓12% vs last week            │
└─────────────────────────────────────┘
```

---

#### 7. Notification Center Widget
**Status:** 🔲 Not Started  
**Effort:** Medium  
**Dependencies:** Notifications service

**Description:**
Unified notification feed with filters and acknowledgment.

**Features:**
- All notifications in one place
- Filter by type (alert, reminder, insight)
- Mark as read/dismissed
- Notification preferences
- Push notification settings

---

#### 8. Comparison Charts Widget
**Status:** 🔲 Not Started  
**Effort:** Medium  
**Dependencies:** Analytics service, historical data

**Description:**
Compare current metrics against historical averages or different time periods.

**Features:**
- Today vs yesterday
- This week vs last week
- Current grow vs previous grow
- Overlay multiple metrics
- Anomaly highlighting

---

### Priority 3: High Value / High Effort

#### 9. ML Prediction Dashboard
**Status:** 🔲 Not Started  
**Effort:** High  
**Dependencies:** ML services (climate optimizer, disease predictor, growth predictor)

**Description:**
Dedicated panel showing AI-driven predictions and recommendations.

**Features:**
- Yield prediction with confidence
- Disease risk assessment
- Optimal harvest date prediction
- Climate optimization suggestions
- Growth anomaly detection
- Action recommendations

**UI Elements:**
```
┌─────────────────────────────────────┐
│ 🤖 AI Predictions                   │
├─────────────────────────────────────┤
│ Yield Forecast: 2.4kg (±0.3kg)      │
│ Confidence: 87%                     │
├─────────────────────────────────────┤
│ Disease Risk: LOW ●○○○○            │
│ Growth Rate: +12% vs expected       │
├─────────────────────────────────────┤
│ 💡 Recommendation:                  │
│ "Lower humidity to 55% for optimal  │
│  flowering conditions"              │
└─────────────────────────────────────┘
```

---

#### 10. Community Benchmarks Widget
**Status:** 🔲 Not Started  
**Effort:** High  
**Dependencies:** Community API, data sharing consent

**Description:**
Compare your metrics against anonymous community averages.

**Features:**
- Percentile rankings
- Best practices from top growers
- Strain-specific benchmarks
- Regional comparisons
- Achievement badges

---

#### 11. Multi-Zone Overview
**Status:** 🔲 Not Started  
**Effort:** High  
**Dependencies:** Multiple units support

**Description:**
Overview of all growth units in a single view for multi-zone setups.

**Features:**
- Grid view of all units
- Quick status indicators
- Cross-unit alerts
- Resource sharing insights
- Batch controls

---

#### 12. Interactive Plant Map
**Status:** 🔲 Not Started  
**Effort:** High  
**Dependencies:** Spatial data, plant positions

**Description:**
Visual map of plant positions within the grow space.

**Features:**
- Drag-and-drop plant positioning
- Heat map overlays (light, temp, humidity)
- Sensor coverage visualization
- Plant health indicators on map
- Spacing optimization suggestions

---

## Technical Considerations

### API Endpoints Needed

| Widget | Endpoint | Status |
|--------|----------|--------|
| Weather | `/api/weather/current`, `/api/weather/forecast` | 🔲 Not implemented |
| Harvest Timeline | `/api/harvests/timeline` | 🔲 Not implemented |
| Water Schedule | `/api/irrigation/schedule`, `/api/irrigation/next` | ✅ Exists |
| Growth Stage | `/api/plants/{id}/stage` | ✅ Exists |
| Photo Gallery | `/api/journal/photos` | 🔲 Not implemented |
| Energy Analytics | `/api/analytics/energy` | ✅ Exists |
| Notifications | `/api/notifications` | ✅ Exists |
| ML Predictions | `/api/ml/predictions/summary` | 🔲 Not implemented |
| Community | `/api/community/benchmarks` | 🔲 Not implemented |

### Frontend Components Needed

- `WeatherWidget` - Weather display component
- `TimelineChart` - Horizontal timeline visualization
- `CountdownTimer` - Live countdown with animations
- `ProgressTracker` - Multi-stage progress indicator
- `PhotoCarousel` - Image gallery with lightbox
- `CostChart` - Stacked bar/donut for costs
- `NotificationFeed` - Scrollable notification list
- `ComparisonChart` - Dual-axis line chart
- `HeatmapGrid` - Color-coded grid visualization

### CSS Design Tokens to Add

```css
/* Widget-specific tokens */
--widget-gap: var(--space-4);
--widget-padding: var(--space-4);
--widget-header-height: 48px;

/* Chart colors */
--chart-primary: var(--brand-500);
--chart-secondary: var(--accent-500);
--chart-tertiary: var(--supporting-teal);
--chart-quaternary: var(--supporting-amber);

/* Status indicators */
--status-excellent: var(--success-500);
--status-good: var(--success-400);
--status-fair: var(--warning-500);
--status-poor: var(--error-500);
```

---

## Implementation Order Recommendation

1. **Phase 1 (Quick Wins):**
   - Harvest Timeline Widget
   - Water/Nutrient Schedule Widget
   - Growth Stage Tracker

2. **Phase 2 (Analytics):**
   - Cost/Energy Analytics Widget
   - Comparison Charts Widget
   - Photo Gallery Widget

3. **Phase 3 (External Integration):**
   - Weather Forecast Widget
   - Notification Center Widget

4. **Phase 4 (AI/ML):**
   - ML Prediction Dashboard
   - Community Benchmarks Widget

5. **Phase 5 (Advanced):**
   - Multi-Zone Overview
   - Interactive Plant Map

---

## Contributing

When implementing a new widget:

1. Create the HTML structure in `templates/dashboard.html`
2. Add CSS styles in `static/css/dashboard.css`
3. Add element caching in `ui-manager.js` constructor
4. Add data loading method in `data-service.js`
5. Add update/render methods in `ui-manager.js`
6. Wire up refresh button events
7. Add API endpoint if needed
8. Test responsive breakpoints
9. Update this document

---

*Last updated: January 4, 2026*
