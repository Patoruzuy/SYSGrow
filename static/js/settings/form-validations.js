/**
 * Form Validations for Settings Page
 * Provides client-side validation for all settings forms using FormValidator utility
 */

class SettingsFormValidations {
  constructor() {
    this.validationSchemas = this.defineSchemas();
    this.init();
  }

  defineSchemas() {
    return {
      // Environment form validation schema
      environment: {
        temperature_threshold: {
          required: true,
          numeric: true,
          range: { min: -20, max: 60 },
          message: 'Temperature must be between -20°C and 60°C'
        },
        humidity_threshold: {
          required: true,
          numeric: true,
          range: { min: 0, max: 100 },
          message: 'Humidity must be between 0% and 100%'
        },
        co2_threshold: {
          numeric: true,
          min: 0,
          max: 5000,
          message: 'CO₂ must be a positive number up to 5000 ppm'
        },
        voc_threshold: {
          numeric: true,
          min: 0,
          max: 10000,
          message: 'VOC must be a positive number up to 10000 ppb'
        },
        lux_threshold: {
          numeric: true,
          min: 0,
          max: 100000,
          message: 'Lux must be a positive number up to 100000'
        },
        aqi_threshold: {
          numeric: true,
          range: { min: 0, max: 500 },
          message: 'AQI must be between 0 and 500'
        }
      },

      // Hotspot form validation schema
      hotspot: {
        ssid: {
          required: true,
          minLength: 1,
          maxLength: 32,
          message: 'SSID must be between 1 and 32 characters'
        },
        password: {
          minLength: 8,
          maxLength: 63,
          message: 'Password must be between 8 and 63 characters (or leave empty)'
        }
      },

      // Throttle form validation schema
      throttle: {
        sensor_rate_limit: {
          required: true,
          integer: true,
          positive: true,
          message: 'Sensor rate limit must be a positive integer'
        },
        sensor_time_window: {
          required: true,
          integer: true,
          positive: true,
          message: 'Sensor time window must be a positive integer'
        },
        action_rate_limit: {
          required: true,
          integer: true,
          positive: true,
          message: 'Action rate limit must be a positive integer'
        },
        action_time_window: {
          required: true,
          integer: true,
          positive: true,
          message: 'Action time window must be a positive integer'
        }
      },

      // Energy cost form validation schema
      energy: {
        electricity_rate: {
          required: true,
          numeric: true,
          positive: true,
          message: 'Electricity rate must be a positive number'
        },
        currency: {
          required: true,
          minLength: 1,
          maxLength: 10,
          message: 'Currency must be specified (1-10 characters)'
        }
      },

      // Schedule form validation schema
      schedule: {
        device_type: {
          required: true,
          message: 'Device type is required'
        },
        schedule_type: {
          required: true,
          oneOf: ['simple', 'photoperiod', 'interval', 'automatic'],
          message: 'Schedule type must be simple, photoperiod, interval, or automatic'
        },
        start_time: {
          required: true,
          time: true,
          message: 'Start time must be in HH:MM format'
        },
        end_time: {
          required: false,
          time: true,
          message: 'End time must be in HH:MM format'
        },
        interval_minutes: {
          required: false,
          numeric: true,
          positive: true,
          message: 'Interval minutes must be a positive number'
        },
        duration_minutes: {
          required: false,
          numeric: true,
          positive: true,
          message: 'Duration minutes must be a positive number'
        },
        priority: {
          integer: true,
          range: { min: 0, max: 100 },
          message: 'Priority must be between 0 and 100'
        }
      }
    };
  }

  init() {
    this.attachValidators();
  }

  attachValidators() {
    // Environment form
    const environmentForm = document.getElementById('environment-form');
    if (environmentForm) {
      environmentForm.addEventListener('submit', (e) => this.validateEnvironmentForm(e));
    }

    // Hotspot form
    const hotspotForm = document.getElementById('hotspot-form');
    if (hotspotForm) {
      hotspotForm.addEventListener('submit', (e) => this.validateHotspotForm(e));
    }

    // Throttle form
    const throttleForm = document.getElementById('throttle-form');
    if (throttleForm) {
      throttleForm.addEventListener('submit', (e) => this.validateThrottleForm(e));
    }

    // Energy form
    const energyForm = document.getElementById('energy-form');
    if (energyForm) {
      energyForm.addEventListener('submit', (e) => this.validateEnergyForm(e));
    }

    // Schedule form (v3)
    const scheduleForm = document.getElementById('device-schedule-form');
    if (scheduleForm) {
      scheduleForm.addEventListener('submit', (e) => this.validateScheduleForm(e));
    }
  }

  validateEnvironmentForm(event) {
    const form = event.target;
    const isValid = window.FormValidator.validateForm(form, this.validationSchemas.environment);
    
    if (!isValid) {
      event.preventDefault();
      event.stopPropagation();
      
      // Show error message
      if (window.NotificationUtils) {
        window.NotificationUtils.show('Please fix the validation errors before submitting', 'error');
      }
    }
    
    return isValid;
  }

  validateHotspotForm(event) {
    const form = event.target;
    const isValid = window.FormValidator.validateForm(form, this.validationSchemas.hotspot);
    
    if (!isValid) {
      event.preventDefault();
      event.stopPropagation();
      
      if (window.NotificationUtils) {
        window.NotificationUtils.show('Please fix the validation errors before submitting', 'error');
      }
    }
    
    return isValid;
  }

  validateThrottleForm(event) {
    const form = event.target;
    const isValid = window.FormValidator.validateForm(form, this.validationSchemas.throttle);
    
    if (!isValid) {
      event.preventDefault();
      event.stopPropagation();
      
      if (window.NotificationUtils) {
        window.NotificationUtils.show('Please fix the validation errors before submitting', 'error');
      }
    }
    
    return isValid;
  }

  validateEnergyForm(event) {
    const form = event.target;
    const isValid = window.FormValidator.validateForm(form, this.validationSchemas.energy);
    
    if (!isValid) {
      event.preventDefault();
      event.stopPropagation();
      
      if (window.NotificationUtils) {
        window.NotificationUtils.show('Please fix the validation errors before submitting', 'error');
      }
    }
    
    return isValid;
  }

  validateScheduleForm(event) {
    const form = event.target;
    const isValid = window.FormValidator.validateForm(form, this.validationSchemas.schedule);
    
    if (!isValid) {
      event.preventDefault();
      event.stopPropagation();
      
      if (window.NotificationUtils) {
        window.NotificationUtils.show('Please fix the validation errors before submitting', 'error');
      }
    }
    
    return isValid;
  }
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => {
    new SettingsFormValidations();
  });
} else {
  new SettingsFormValidations();
}

// Export for module usage
if (typeof window !== 'undefined') {
  window.SettingsFormValidations = SettingsFormValidations;
}
