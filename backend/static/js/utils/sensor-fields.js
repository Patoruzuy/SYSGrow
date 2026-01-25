/**
 * Sensor Fields Standards Utility
 * ============================================================================
 * Centralized tool for mapping various sensor field name variations to
 * standardized system names.
 *
 * Mirrors the Python backend (app/domain/sensors/fields.py).
 */
(function() {
  'use strict';

  /**
   * Standardized sensor reading field names.
   */
  const SensorField = {
    TEMPERATURE: "temperature",
    HUMIDITY: "humidity",
    SOIL_MOISTURE: "soil_moisture",
    CO2: "co2",
    AIR_QUALITY: "air_quality",
    EC: "ec",
    PH: "ph",
    SMOKE: "smoke",
    VOC: "voc",
    PRESSURE: "pressure",
    LUX: "lux",
    FULL_SPECTRUM: "full_spectrum",
    INFRARED: "infrared",
    VISIBLE: "visible",
    BATTERY: "battery",
    LINK_QUALITY: "linkquality"
  };

  /**
   * Mapping: alias -> standard_field
   */
  const FIELD_ALIASES = {
    // Temperature
    "temp": SensorField.TEMPERATURE,
    "temp_c": SensorField.TEMPERATURE,
    "Temperature": SensorField.TEMPERATURE,
    
    // Humidity
    "humidity_percent": SensorField.HUMIDITY,
    "relative_humidity": SensorField.HUMIDITY,
    "Humidity": SensorField.HUMIDITY,
    "rh": SensorField.HUMIDITY,
    
    // Soil Moisture
    "moisture": SensorField.SOIL_MOISTURE,
    "moisture_level": SensorField.SOIL_MOISTURE,
    "Soil Moisture": SensorField.SOIL_MOISTURE,
    
    // CO2
    "co2_ppm": SensorField.CO2,
    "CO2": SensorField.CO2,
    "eco2": SensorField.CO2,
    "co2_level": SensorField.CO2,
    
    // VOC
    "tvoc": SensorField.VOC,
    "VOC": SensorField.VOC,
    "voc_ppb": SensorField.VOC,
    "Formaldehyde": SensorField.VOC,
    
    // Light / LUX
    "light": SensorField.LUX,
    "light_lux": SensorField.LUX,
    "light_level": SensorField.LUX,
    "light_intensity": SensorField.LUX,
    "illuminance": SensorField.LUX,
    "illuminance_lux": SensorField.LUX,
    "Lux": SensorField.LUX,
    
    // Smoke
    "smoke_ppm": SensorField.SMOKE,
    "smoke_level": SensorField.SMOKE,
    
    // Pressure
    "pressure_hpa": SensorField.PRESSURE,
    
    // EC
    "ec_us_cm": SensorField.EC,
    
    // Air Quality
    "aqi": SensorField.AIR_QUALITY,
    
    // Battery
    "battery_percent": SensorField.BATTERY,
    "Battery": SensorField.BATTERY,
    
    // Link Quality
    "link_quality": SensorField.LINK_QUALITY,
    "rssi": SensorField.LINK_QUALITY,
  };

  const SensorFields = {
    Field: SensorField,

    /**
     * Gets the standardized field name for a given alias.
     * @param {string} fieldName - Incoming field name/alias
     * @returns {string} Standardized field name
     */
    getStandard(fieldName) {
      return FIELD_ALIASES[fieldName] || fieldName;
    },

    /**
     * Maps a whole data object to standardized field names.
     * @param {Object} data - Raw sensor data
     * @returns {Object} Standardized data
     */
    standardize(data) {
      if (!data || typeof data !== 'object') return data;
      const result = {};
      for (const [key, value] of Object.entries(data)) {
        result[this.getStandard(key)] = value;
      }
      return result;
    }
  };

  // Export to global scope if needed (matching project pattern)
  if (typeof window !== 'undefined') {
    window.SensorFields = SensorFields;
  }

  // Export for modules if available
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = SensorFields;
  }
})();
