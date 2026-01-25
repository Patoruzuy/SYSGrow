# Form Validator & Chart Service - Quick Reference

## Form Validator Usage

### Basic Example
```javascript
// Define validation schema
const schema = {
  email: {
    required: true,
    email: true,
    message: 'Valid email required'
  },
  age: {
    required: true,
    integer: true,
    range: { min: 18, max: 120 },
    message: 'Age must be between 18 and 120'
  }
};

// Validate on submit
form.addEventListener('submit', (e) => {
  const isValid = FormValidator.validateForm(form, schema);
  if (!isValid) {
    e.preventDefault();
    e.stopPropagation();
  }
});
```

### Available Validation Rules

| Rule | Description | Example |
|------|-------------|---------|
| `required` | Field must have value | `{ required: true }` |
| `minLength` | Minimum string length | `{ minLength: 8 }` |
| `maxLength` | Maximum string length | `{ maxLength: 50 }` |
| `min` | Minimum numeric value | `{ min: 0 }` |
| `max` | Maximum numeric value | `{ max: 100 }` |
| `range` | Value between min/max | `{ range: { min: 0, max: 100 } }` |
| `email` | Valid email format | `{ email: true }` |
| `url` | Valid URL format | `{ url: true }` |
| `ip` | Valid IP address | `{ ip: true }` |
| `numeric` | Must be number | `{ numeric: true }` |
| `integer` | Must be integer | `{ integer: true }` |
| `positive` | Must be positive | `{ positive: true }` |
| `pattern` | Match regex | `{ pattern: /^[A-Z]+$/ }` |
| `matches` | Match another field | `{ matches: 'password' }` |
| `oneOf` | One of allowed values | `{ oneOf: ['yes', 'no'] }` |
| `time` | Valid HH:MM format | `{ time: true }` |
| `date` | Valid date format | `{ date: true }` |

### Custom Messages
```javascript
const schema = {
  username: {
    required: true,
    minLength: 3,
    maxLength: 20,
    pattern: /^[a-zA-Z0-9_]+$/,
    message: 'Username must be 3-20 alphanumeric characters or underscores'
  }
};
```

### Extract Form Data
```javascript
// Get all form data as object
const data = FormValidator.getFormData(form);
// Returns: { field1: 'value1', field2: 'value2', ... }

// Get validated data (only fields that pass validation)
const validatedData = FormValidator.getValidatedData(form, schema);
```

### Manual Field Validation
```javascript
// Validate single field
const isValid = FormValidator.validateField(input, rules);

// Show error on field
FormValidator.showError(input, 'Custom error message');

// Show success on field
FormValidator.showSuccess(input);

// Clear validation state
FormValidator.clearValidation(input);
```

### Real-time Validation
```javascript
// Validate on blur
inputs.forEach(input => {
  input.addEventListener('blur', () => {
    const rules = schema[input.name];
    if (rules) {
      FormValidator.validateField(input, rules);
    }
  });
});
```

## Chart Service Usage

### Create Charts

#### Line Chart
```javascript
const chart = ChartService.createLineChart(canvas, {
  data: {
    labels: ['Jan', 'Feb', 'Mar'],
    datasets: [{
      label: 'Temperature',
      data: [20, 22, 21],
      borderColor: ChartService.getSensorColor('temperature')
    }]
  },
  options: {
    responsive: true,
    scales: {
      y: { beginAtZero: false }
    }
  }
});
```

#### Bar Chart
```javascript
const chart = ChartService.createBarChart(canvas, {
  data: {
    labels: ['Device 1', 'Device 2', 'Device 3'],
    datasets: [{
      label: 'Energy Usage (kWh)',
      data: [45, 67, 52],
      backgroundColor: ChartService.colors.primary
    }]
  }
});
```

#### Doughnut Chart
```javascript
const chart = ChartService.createDoughnutChart(canvas, {
  data: {
    labels: ['Active', 'Inactive', 'Error'],
    datasets: [{
      data: [75, 20, 5],
      backgroundColor: [
        ChartService.colors.success,
        ChartService.colors.secondary,
        ChartService.colors.danger
      ]
    }]
  }
});
```

### Update Charts
```javascript
// Update chart data
chart.data.labels = newLabels;
chart.data.datasets[0].data = newData;
ChartService.updateChart(chart);

// Or manually
chart.update();
```

### Destroy Charts
```javascript
// Safe destruction
ChartService.destroyChart(chart);

// Destroy multiple charts
charts.forEach(chart => ChartService.destroyChart(chart));
```

### Available Colors

#### Theme Colors
```javascript
ChartService.colors.primary   // #6366f1 (Indigo)
ChartService.colors.success   // #22c55e (Green)
ChartService.colors.warning   // #f59e0b (Amber)
ChartService.colors.danger    // #ef4444 (Red)
ChartService.colors.info      // #3b82f6 (Blue)
ChartService.colors.secondary // #64748b (Slate)
```

#### Sensor Colors
```javascript
ChartService.getSensorColor('temperature')   // #ef4444 (Red)
ChartService.getSensorColor('humidity')      // #3b82f6 (Blue)
ChartService.getSensorColor('soil_moisture') // #8b4513 (Brown)
ChartService.getSensorColor('light')         // #fbbf24 (Yellow)
ChartService.getSensorColor('co2')           // #22c55e (Green)
ChartService.getSensorColor('voc')           // #a855f7 (Purple)
```

#### Color Arrays
```javascript
// Get array of colors for multiple datasets
const colors = ChartService.getColorArray(5);
// Returns: ['#6366f1', '#22c55e', '#f59e0b', '#ef4444', '#3b82f6']
```

### Multi-Axis Charts
```javascript
const chart = ChartService.createLineChart(canvas, {
  data: {
    labels: timestamps,
    datasets: [
      {
        label: 'Temperature',
        data: tempData,
        yAxisID: 'temperature',
        borderColor: ChartService.getSensorColor('temperature')
      },
      {
        label: 'Humidity',
        data: humidityData,
        yAxisID: 'humidity',
        borderColor: ChartService.getSensorColor('humidity')
      }
    ]
  },
  options: {
    scales: {
      temperature: {
        type: 'linear',
        position: 'left',
        title: { display: true, text: 'Temperature (°C)' }
      },
      humidity: {
        type: 'linear',
        position: 'right',
        title: { display: true, text: 'Humidity (%)' }
      }
    }
  }
});
```

### Time-Series Charts
```javascript
const chart = ChartService.createLineChart(canvas, {
  data: {
    datasets: [{
      label: 'Sensor Reading',
      data: dataPoints.map(d => ({ x: d.timestamp, y: d.value }))
    }]
  },
  options: {
    scales: {
      x: {
        type: 'time',
        time: {
          unit: 'hour'
        }
      }
    }
  }
});
```

## Complete Integration Example

### HTML Template
```html
<form id="sensor-config-form" novalidate>
  <input type="text" name="sensor_name" class="form-control" required>
  <input type="number" name="gpio_pin" class="form-control" min="0" max="39">
  <button type="submit">Save</button>
</form>

<canvas id="sensor-data-chart"></canvas>
```

### JavaScript
```javascript
class SensorPage {
  constructor() {
    this.charts = new Map();
    this.validationSchemas = this.defineSchemas();
    this.init();
  }

  defineSchemas() {
    return {
      sensorConfig: {
        sensor_name: {
          required: true,
          minLength: 1,
          maxLength: 50,
          message: 'Sensor name required (1-50 chars)'
        },
        gpio_pin: {
          required: true,
          integer: true,
          range: { min: 0, max: 39 },
          message: 'GPIO pin must be 0-39'
        }
      }
    };
  }

  init() {
    this.setupValidation();
    this.setupCharts();
  }

  setupValidation() {
    const form = document.getElementById('sensor-config-form');
    form.addEventListener('submit', (e) => {
      const isValid = FormValidator.validateForm(
        form, 
        this.validationSchemas.sensorConfig
      );
      
      if (!isValid) {
        e.preventDefault();
        e.stopPropagation();
        NotificationUtils.show('Please fix validation errors', 'error');
        return;
      }
      
      // Form is valid, get data
      const data = FormValidator.getFormData(form);
      this.submitForm(data);
    });
  }

  setupCharts() {
    const canvas = document.getElementById('sensor-data-chart');
    const chart = ChartService.createLineChart(canvas, {
      data: {
        labels: [],
        datasets: [{
          label: 'Sensor Reading',
          data: [],
          borderColor: ChartService.getSensorColor('temperature')
        }]
      },
      options: {
        responsive: true,
        scales: {
          y: { beginAtZero: true }
        }
      }
    });
    
    this.charts.set('sensorData', chart);
  }

  updateChart(labels, data) {
    const chart = this.charts.get('sensorData');
    if (chart) {
      chart.data.labels = labels;
      chart.data.datasets[0].data = data;
      ChartService.updateChart(chart);
    }
  }

  destroy() {
    this.charts.forEach(chart => ChartService.destroyChart(chart));
    this.charts.clear();
  }
}

// Initialize
const sensorPage = new SensorPage();
```

## Bootstrap Integration

The utilities are designed to work seamlessly with Bootstrap 5:

### Validation Classes
- Form Validator automatically adds `.is-valid` and `.is-invalid` classes
- Error messages use `.invalid-feedback` divs
- Success messages use `.valid-feedback` divs

### HTML Structure
```html
<div class="mb-3">
  <label for="email" class="form-label">Email</label>
  <input type="email" id="email" name="email" class="form-control">
  <div class="invalid-feedback">Please enter a valid email</div>
</div>
```

### Chart Responsive Design
Charts automatically respond to container size changes with Bootstrap's grid system:

```html
<div class="row">
  <div class="col-md-6">
    <canvas id="chart1"></canvas>
  </div>
  <div class="col-md-6">
    <canvas id="chart2"></canvas>
  </div>
</div>
```

## Common Patterns

### Loading State
```javascript
// Disable form during submission
form.classList.add('was-validated');
submitButton.disabled = true;

try {
  await submitData(data);
  NotificationUtils.show('Saved successfully', 'success');
} catch (error) {
  NotificationUtils.show('Save failed', 'error');
} finally {
  submitButton.disabled = false;
}
```

### Chart Loading State
```javascript
// Show loading spinner
chartContainer.innerHTML = '<div class="spinner-border"></div>';

try {
  const data = await fetchChartData();
  chartContainer.innerHTML = '<canvas id="chart"></canvas>';
  const canvas = chartContainer.querySelector('canvas');
  ChartService.createLineChart(canvas, { data });
} catch (error) {
  chartContainer.innerHTML = '<p class="text-danger">Failed to load chart</p>';
}
```

---

**Documentation Version**: 1.0  
**Last Updated**: 2025-01-XX  
**Related Files**:
- [static/js/utils/form-validator.js](static/js/utils/form-validator.js)
- [static/js/utils/chart-service.js](static/js/utils/chart-service.js)
