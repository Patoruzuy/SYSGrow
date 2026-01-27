/**
 * Form Validator Utility
 * ============================================================================
 * Provides standardized form validation with support for common validation
 * rules, custom validators, and integration with the notification system.
 */
(function() {
  'use strict';

  /**
   * Built-in validation rules
   */
  const RULES = {
    /**
     * Required field validation
     */
    required: (value, params, fieldName) => {
      const isEmpty = value === null || value === undefined || value === '' ||
                     (Array.isArray(value) && value.length === 0);
      return isEmpty
        ? { valid: false, message: `${fieldName} is required` }
        : { valid: true };
    },

    /**
     * Minimum length validation
     */
    minLength: (value, minLen, fieldName) => {
      if (!value) return { valid: true };
      return value.length >= minLen
        ? { valid: true }
        : { valid: false, message: `${fieldName} must be at least ${minLen} characters` };
    },

    /**
     * Maximum length validation
     */
    maxLength: (value, maxLen, fieldName) => {
      if (!value) return { valid: true };
      return value.length <= maxLen
        ? { valid: true }
        : { valid: false, message: `${fieldName} must be at most ${maxLen} characters` };
    },

    /**
     * Minimum numeric value validation
     */
    min: (value, minVal, fieldName) => {
      if (value === null || value === undefined || value === '') return { valid: true };
      const num = parseFloat(value);
      return !isNaN(num) && num >= minVal
        ? { valid: true }
        : { valid: false, message: `${fieldName} must be at least ${minVal}` };
    },

    /**
     * Maximum numeric value validation
     */
    max: (value, maxVal, fieldName) => {
      if (value === null || value === undefined || value === '') return { valid: true };
      const num = parseFloat(value);
      return !isNaN(num) && num <= maxVal
        ? { valid: true }
        : { valid: false, message: `${fieldName} must be at most ${maxVal}` };
    },

    /**
     * Numeric range validation
     */
    range: (value, { min, max }, fieldName) => {
      if (value === null || value === undefined || value === '') return { valid: true };
      const num = parseFloat(value);
      return !isNaN(num) && num >= min && num <= max
        ? { valid: true }
        : { valid: false, message: `${fieldName} must be between ${min} and ${max}` };
    },

    /**
     * Email format validation
     */
    email: (value, params, fieldName) => {
      if (!value) return { valid: true };
      const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
      return emailRegex.test(value)
        ? { valid: true }
        : { valid: false, message: `${fieldName} must be a valid email address` };
    },

    /**
     * URL format validation
     */
    url: (value, params, fieldName) => {
      if (!value) return { valid: true };
      try {
        new URL(value);
        return { valid: true };
      } catch (e) {
        return { valid: false, message: `${fieldName} must be a valid URL` };
      }
    },

    /**
     * IP address validation
     */
    ip: (value, params, fieldName) => {
      if (!value) return { valid: true };
      const ipv4Regex = /^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$/;
      return ipv4Regex.test(value)
        ? { valid: true }
        : { valid: false, message: `${fieldName} must be a valid IP address` };
    },

    /**
     * Numeric value validation
     */
    numeric: (value, params, fieldName) => {
      if (value === null || value === undefined || value === '') return { valid: true };
      return !isNaN(parseFloat(value)) && isFinite(value)
        ? { valid: true }
        : { valid: false, message: `${fieldName} must be a number` };
    },

    /**
     * Integer validation
     */
    integer: (value, params, fieldName) => {
      if (value === null || value === undefined || value === '') return { valid: true };
      return Number.isInteger(Number(value))
        ? { valid: true }
        : { valid: false, message: `${fieldName} must be a whole number` };
    },

    /**
     * Positive number validation
     */
    positive: (value, params, fieldName) => {
      if (value === null || value === undefined || value === '') return { valid: true };
      const num = parseFloat(value);
      return !isNaN(num) && num > 0
        ? { valid: true }
        : { valid: false, message: `${fieldName} must be a positive number` };
    },

    /**
     * Pattern matching validation (regex)
     */
    pattern: (value, regex, fieldName) => {
      if (!value) return { valid: true };
      const pattern = typeof regex === 'string' ? new RegExp(regex) : regex;
      return pattern.test(value)
        ? { valid: true }
        : { valid: false, message: `${fieldName} format is invalid` };
    },

    /**
     * Value must match another field
     */
    matches: (value, otherFieldValue, fieldName, otherFieldName) => {
      return value === otherFieldValue
        ? { valid: true }
        : { valid: false, message: `${fieldName} must match ${otherFieldName || 'the other field'}` };
    },

    /**
     * Value must be in a list of allowed values
     */
    oneOf: (value, allowedValues, fieldName) => {
      if (!value) return { valid: true };
      return allowedValues.includes(value)
        ? { valid: true }
        : { valid: false, message: `${fieldName} must be one of: ${allowedValues.join(', ')}` };
    },

    /**
     * Time format validation (HH:MM)
     */
    time: (value, params, fieldName) => {
      if (!value) return { valid: true };
      const timeRegex = /^([01]?[0-9]|2[0-3]):([0-5][0-9])$/;
      return timeRegex.test(value)
        ? { valid: true }
        : { valid: false, message: `${fieldName} must be in HH:MM format` };
    },

    /**
     * Date validation
     */
    date: (value, params, fieldName) => {
      if (!value) return { valid: true };
      const date = new Date(value);
      return !isNaN(date.getTime())
        ? { valid: true }
        : { valid: false, message: `${fieldName} must be a valid date` };
    }
  };

  /**
   * FormValidator class
   */
  class FormValidator {
    constructor(options = {}) {
      this.showNotifications = options.showNotifications !== false;
      this.highlightErrors = options.highlightErrors !== false;
      this.errorClass = options.errorClass || 'is-invalid';
      this.successClass = options.successClass || 'is-valid';
      this.customRules = {};
    }

    /**
     * Add a custom validation rule
     * @param {string} name - Rule name
     * @param {Function} validator - Validator function (value, params, fieldName) => { valid, message }
     */
    addRule(name, validator) {
      this.customRules[name] = validator;
    }

    /**
     * Validate a single field
     * @param {*} value - Field value
     * @param {Object} rules - Validation rules
     * @param {string} fieldName - Field name for error messages
     * @returns {Object} { valid, errors }
     */
    validateField(value, rules, fieldName = 'Field') {
      const errors = [];

      for (const [ruleName, ruleParams] of Object.entries(rules)) {
        // Skip if rule is disabled (false)
        if (ruleParams === false) continue;

        const validator = this.customRules[ruleName] || RULES[ruleName];
        if (!validator) {
          console.warn(`[FormValidator] Unknown rule: ${ruleName}`);
          continue;
        }

        const result = validator(value, ruleParams, fieldName);
        if (!result.valid) {
          errors.push(result.message);
        }
      }

      return {
        valid: errors.length === 0,
        errors
      };
    }

    /**
     * Validate a form or data object
     * @param {Object|HTMLFormElement} formOrData - Form element or data object
     * @param {Object} schema - Validation schema { fieldName: { rules } }
     * @returns {Object} { valid, errors, data }
     */
    validate(formOrData, schema) {
      const isForm = formOrData instanceof HTMLFormElement;
      const data = isForm ? this._extractFormData(formOrData) : formOrData;
      const errors = {};
      let isValid = true;

      // Clear previous error states
      if (isForm && this.highlightErrors) {
        this._clearErrorStates(formOrData);
      }

      for (const [fieldName, fieldRules] of Object.entries(schema)) {
        const value = data[fieldName];
        const displayName = fieldRules._displayName || this._humanize(fieldName);
        const rules = { ...fieldRules };
        delete rules._displayName;

        const result = this.validateField(value, rules, displayName);

        if (!result.valid) {
          isValid = false;
          errors[fieldName] = result.errors;

          // Highlight error on form element
          if (isForm && this.highlightErrors) {
            this._highlightError(formOrData, fieldName, result.errors[0]);
          }
        }
      }

      // Show notification if there are errors
      if (!isValid && this.showNotifications) {
        const firstError = Object.values(errors)[0]?.[0] || 'Please fix the errors in the form';
        if (window.showToast) {
          window.showToast(firstError, 'error');
        } else if (window.showNotification) {
          window.showNotification(firstError, 'error');
        }
      }

      return {
        valid: isValid,
        errors,
        data
      };
    }

    /**
     * Validate a form and return only the data if valid
     * @param {Object|HTMLFormElement} formOrData - Form element or data object
     * @param {Object} schema - Validation schema
     * @returns {Object|null} Data if valid, null if invalid
     */
    validateAndGet(formOrData, schema) {
      const result = this.validate(formOrData, schema);
      return result.valid ? result.data : null;
    }

    /**
     * Validate a single value against a schema
     * @param {*} value - Value to validate
     * @param {Object} rules - Validation rules
     * @param {string} fieldName - Field name
     * @returns {boolean} True if valid
     */
    isValid(value, rules, fieldName = 'Field') {
      return this.validateField(value, rules, fieldName).valid;
    }

    /**
     * Quick check for required and non-empty
     * @param {*} value - Value to check
     * @returns {boolean} True if value exists and is not empty
     */
    hasValue(value) {
      return value !== null && value !== undefined && value !== '' &&
             !(Array.isArray(value) && value.length === 0);
    }

    /**
     * Extract data from form element
     * @private
     */
    _extractFormData(form) {
      const formData = new FormData(form);
      const data = {};

      for (const [key, value] of formData.entries()) {
        // Handle multiple values (checkboxes, multi-select)
        if (data[key] !== undefined) {
          if (!Array.isArray(data[key])) {
            data[key] = [data[key]];
          }
          data[key].push(value);
        } else {
          data[key] = value;
        }
      }

      // Also check for unchecked checkboxes
      form.querySelectorAll('input[type="checkbox"]').forEach(checkbox => {
        if (!formData.has(checkbox.name)) {
          data[checkbox.name] = false;
        }
      });

      return data;
    }

    /**
     * Clear error states from form
     * @private
     */
    _clearErrorStates(form) {
      form.querySelectorAll(`.${this.errorClass}`).forEach(el => {
        el.classList.remove(this.errorClass);
      });
      form.querySelectorAll('.invalid-feedback').forEach(el => {
        el.remove();
      });
    }

    /**
     * Highlight error on form field
     * @private
     */
    _highlightError(form, fieldName, message) {
      const field = form.querySelector(`[name="${fieldName}"]`);
      if (!field) return;

      field.classList.add(this.errorClass);

      // Add error message
      const existingFeedback = field.parentElement.querySelector('.invalid-feedback');
      if (!existingFeedback) {
        const feedback = document.createElement('div');
        feedback.className = 'invalid-feedback';
        feedback.textContent = message;
        field.parentElement.appendChild(feedback);
      }
    }

    /**
     * Convert field name to human-readable format
     * @private
     */
    _humanize(fieldName) {
      return fieldName
        .replace(/([A-Z])/g, ' $1')
        .replace(/[_-]/g, ' ')
        .replace(/^\s/, '')
        .replace(/\b\w/g, c => c.toUpperCase())
        .trim();
    }
  }

  // Create singleton instance with default options
  const formValidator = new FormValidator();

  // Export to window
  window.FormValidator = formValidator;
  window.FormValidatorClass = FormValidator;
  window.ValidationRules = RULES;

  // Convenience methods
  window.validateForm = (formOrData, schema) => formValidator.validate(formOrData, schema);
  window.isValidField = (value, rules, name) => formValidator.isValid(value, rules, name);
})();
