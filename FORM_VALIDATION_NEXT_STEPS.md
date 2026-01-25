# Next Steps: Form Validation & Chart Integration

This guide provides specific implementation steps for integrating form validation and chart standardization into the remaining templates.

## Priority 1: Device Forms Validation

### File: `templates/devices.html`
**Forms to validate:**
1. Sensor configuration form
2. Actuator configuration form
3. Device settings form

**Implementation:**

1. Create `static/js/devices/form-validations.js`:
```javascript
class DeviceFormValidations {
  constructor() {
    this.validationSchemas = {
      sensor: {
        device_name: { required: true, minLength: 1, maxLength: 50 },
        gpio_pin: { integer: true, range: { min: 0, max: 39 } },
        i2c_address: { pattern: /^0x[0-9A-Fa-f]{2}$/ },
        mqtt_topic: { required: true, pattern: /^[a-zA-Z0-9/_-]+$/ }
      },
      actuator: {
        device_name: { required: true, minLength: 1, maxLength: 50 },
        device_type: { required: true, oneOf: ['relay', 'servo', 'dimmer'] },
        gpio_pin: { integer: true, range: { min: 0, max: 39 } }
      }
    };
  }
  // ... implementation similar to settings form validations
}
```

2. Add to `templates/devices.html` scripts block:
```html
<script src="{{ url_for('static', filename='js/devices/form-validations.js') }}"></script>
```

## Priority 2: Plant Management Validation

### File: `templates/add_plant.html`
**Form to validate:**
- Plant creation form

**Validation rules:**
```javascript
{
  plant_name: { 
    required: true, 
    minLength: 1, 
    maxLength: 100 
  },
  species: { 
    minLength: 1, 
    maxLength: 100 
  },
  days_in_seedling: { 
    integer: true, 
    positive: true 
  },
  days_in_vegetative: { 
    integer: true, 
    positive: true 
  },
  days_in_flowering: { 
    integer: true, 
    positive: true 
  },
  days_in_ripening: { 
    integer: true, 
    positive: true 
  }
}
```

### File: `templates/plants.html`
**Forms to validate:**
1. Plant update form
2. Stage transition form

## Priority 3: Growth Unit Forms

### File: `templates/units.html`
**Forms to validate:**
1. Unit creation form
2. Unit settings form

**Validation rules:**
```javascript
{
  unit_name: { 
    required: true, 
    minLength: 1, 
    maxLength: 100 
  },
  location: { 
    maxLength: 200 
  },
  capacity: { 
    integer: true, 
    positive: true 
  }
}
```

## Chart Integration: Energy Analytics

### File: `templates/energy_analytics.html`

**Steps:**

1. Identify chart canvases:
```bash
# Search for canvas elements
grep -n "canvas" templates/energy_analytics.html
```

2. Create `static/js/energy-analytics/chart-integration.js`:
```javascript
class EnergyAnalyticsCharts {
  constructor() {
    this.charts = new Map();
    this.chartService = window.ChartService;
  }

  setupCharts(elements) {
    // Energy consumption bar chart
    if (elements.consumptionChart) {
      const config = {
        data: { labels: [], datasets: [] },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          scales: {
            y: { 
              beginAtZero: true,
              title: { display: true, text: 'kWh' }
            }
          }
        }
      };
      const chart = this.chartService.createBarChart(elements.consumptionChart, config);
      this.charts.set('consumption', chart);
    }

    // Cost trend line chart
    if (elements.costTrendChart) {
      const config = {
        data: { labels: [], datasets: [] },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          scales: {
            y: { 
              beginAtZero: true,
              title: { display: true, text: 'Cost' }
            }
          }
        }
      };
      const chart = this.chartService.createLineChart(elements.costTrendChart, config);
      this.charts.set('costTrend', chart);
    }
  }
}
```

3. Update energy analytics UI manager to use chart helper

4. Add script to template:
```html
<script src="{{ url_for('static', filename='js/energy-analytics/chart-integration.js') }}"></script>
```

## Chart Integration: ML Dashboard

### File: `templates/ml_dashboard.html`

**Charts to integrate:**
1. Model accuracy comparison (bar chart)
2. Training history (line chart)
3. Prediction confidence (doughnut chart)

**Implementation pattern:**
```javascript
class MLDashboardCharts {
  setupAccuracyChart(canvas) {
    return this.chartService.createBarChart(canvas, {
      data: { labels: [], datasets: [] },
      options: {
        scales: {
          y: { 
            beginAtZero: true, 
            max: 1,
            title: { display: true, text: 'Accuracy' }
          }
        }
      }
    });
  }

  setupTrainingHistoryChart(canvas) {
    return this.chartService.createLineChart(canvas, {
      data: { labels: [], datasets: [] },
      options: {
        scales: {
          y: { 
            beginAtZero: true,
            title: { display: true, text: 'Loss' }
          }
        }
      }
    });
  }

  setupConfidenceChart(canvas) {
    return this.chartService.createDoughnutChart(canvas, {
      data: { labels: [], datasets: [] },
      options: {
        responsive: true,
        maintainAspectRatio: false
      }
    });
  }
}
```

## Chart Integration: Main Dashboard

### File: `templates/dashboard.html` or `templates/index.html`

**Charts to integrate:**
1. Environmental overview (line chart)
2. Device status (doughnut chart)
3. Recent alerts (bar chart)

**Pattern:**
- Follow sensor analytics chart integration pattern
- Use sensor-specific colors from ChartService
- Ensure proper cleanup on page navigation

## Implementation Checklist

### Forms
- [ ] Create validation schema for each form
- [ ] Add submit event listener with validation
- [ ] Prevent submission if invalid
- [ ] Show error feedback with Bootstrap classes
- [ ] Display toast notification on validation failure
- [ ] Test with valid and invalid inputs

### Charts
- [ ] Identify all canvas elements in template
- [ ] Create chart integration helper class
- [ ] Update UI manager to use helper
- [ ] Add chart integration script to template
- [ ] Test chart rendering and updates
- [ ] Verify proper cleanup on navigation

## Testing Commands

```bash
# Check for form elements
grep -r "form id=" templates/

# Check for canvas elements
grep -r "canvas id=" templates/

# Check for Chart.js instantiation
grep -r "new Chart(" static/js/

# Check script loading
grep -r "form-validator" templates/
grep -r "chart-service" templates/
```

## Common Patterns

### Form Validation Pattern
```javascript
// 1. Define schema in class
this.validationSchemas = { formName: { ... } };

// 2. Attach listener
form.addEventListener('submit', (e) => {
  const isValid = FormValidator.validateForm(form, this.validationSchemas.formName);
  if (!isValid) {
    e.preventDefault();
    e.stopPropagation();
    NotificationUtils.show('Fix validation errors', 'error');
  }
});
```

### Chart Helper Pattern
```javascript
// 1. Create helper class
class PageCharts {
  constructor() {
    this.charts = new Map();
    this.chartService = window.ChartService;
  }
  
  setupCharts(elements) { /* ... */ }
  destroyCharts() {
    if (this.chartService) {
      this.charts.forEach(chart => this.chartService.destroyChart(chart));
    }
    this.charts.clear();
  }
}

// 2. Use in UI manager
this.chartHelper = new PageCharts();
this.chartHelper.setupCharts(this.elements);
```

## Files to Create

1. `static/js/devices/form-validations.js`
2. `static/js/plants/form-validations.js`
3. `static/js/units/form-validations.js`
4. `static/js/energy-analytics/chart-integration.js`
5. `static/js/ml-dashboard/chart-integration.js`
6. `static/js/dashboard/chart-integration.js`

## Files to Update

1. `templates/devices.html` - Add form validation script
2. `templates/add_plant.html` - Add form validation script
3. `templates/plants.html` - Add form validation script
4. `templates/units.html` - Add form validation script
5. `templates/energy_analytics.html` - Add chart integration script
6. `templates/ml_dashboard.html` - Add chart integration script
7. `templates/dashboard.html` - Add chart integration script
8. `static/js/energy-analytics/ui-manager.js` - Use chart helper
9. `static/js/ml-dashboard/ui-manager.js` - Use chart helper
10. `static/js/dashboard/ui-manager.js` - Use chart helper

---

**Estimated Time:**
- Form validations: 2-3 hours (4 files × 30-45 min each)
- Chart integrations: 3-4 hours (4 files × 45-60 min each)
- Testing: 1-2 hours
- **Total: 6-9 hours**

**Priority Order:**
1. Devices form validation (most critical for hardware config)
2. Energy analytics charts (high visibility)
3. Plants form validation
4. ML dashboard charts
5. Units form validation
6. Dashboard charts
