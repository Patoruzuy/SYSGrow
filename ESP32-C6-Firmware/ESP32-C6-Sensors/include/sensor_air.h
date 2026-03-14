#ifndef SENSOR_AIR_H
#define SENSOR_AIR_H

#include <Arduino.h>
#include <ArduinoJson.h>
#include "config.h"

// ============================================================================
// Sensor Air Module - Environmental Sensors
// ============================================================================
// Supports:
//   - ENS160 + AHT21 (Temperature, Humidity, CO2, AQI, VOC)
//   - TSL2591 (Lux, Full Spectrum, Infrared, Visible)
//   - MQ2 (Smoke/Gas) - via sensor_co.h
// ============================================================================

// ============================================================================
// Setup and Initialization
// ============================================================================

/**
 * Initialize all environmental sensors (ENS160+AHT21, TSL2591).
 * Sets up I2C bus and configures sensors.
 */
void setupAirSensors();

/**
 * Alias for setupAirSensors() - called from main.cpp
 */
void setupSensors();

/**
 * Initialize sensor filters for smoothing readings.
 */
void initializeSensorFilters();

// ============================================================================
// ENS160 + AHT21 Sensor Functions
// ============================================================================

/**
 * Read temperature from AHT21 sensor.
 * @return Temperature in Celsius, or NAN if error
 */
float readTemperature();

/**
 * Read humidity from AHT21 sensor.
 * @return Relative humidity percentage (0-100%), or NAN if error
 */
float readHumidity();

/**
 * Read eCO2 (equivalent CO2) from ENS160 sensor.
 * @return CO2 concentration in ppm, or -1 if error
 */
int readCO2();

/**
 * Read Air Quality Index from ENS160 sensor.
 * @return AQI value (1-5), where 1=Excellent, 5=Unhealthy, or -1 if error
 */
int readAirQualityIndex();

/**
 * Read Total Volatile Organic Compounds (TVOC) from ENS160 sensor.
 * @return TVOC in ppb, or -1 if error
 */
int readVOC();

// ============================================================================
// TSL2591 Light Sensor Functions
// ============================================================================

/**
 * Read light level in lux from TSL2591.
 * @return Lux value, or NAN if error
 */
float readLightLevel();

/**
 * Read full spectrum (visible + infrared) raw value.
 * @return Full spectrum count, or 0 if error
 */
uint16_t readFullSpectrum();

/**
 * Read infrared spectrum raw value.
 * @return Infrared count, or 0 if error
 */
uint16_t readInfrared();

/**
 * Read visible spectrum (full - infrared) raw value.
 * @return Visible count, or 0 if error
 */
uint16_t readVisible();

// ============================================================================
// Raw Sensor Reading Functions (no filtering/calibration)
// ============================================================================

/**
 * Read raw temperature without filtering or calibration.
 */
float readRawTemperature();

/**
 * Read raw humidity without filtering.
 */
float readRawHumidity();

/**
 * Read raw soil moisture (if connected).
 * @return Soil moisture percentage, or NAN if not available
 */
float readRawSoilMoisture();

/**
 * Read raw light level without filtering.
 */
float readRawLightLevel();

// ============================================================================
// Legacy Compatibility Functions
// ============================================================================

/**
 * Read soil moisture sensor (returns NAN for this device type).
 * Kept for payload compatibility - future expansion.
 */
float readSoilMoisture();

// ============================================================================
// Sensor Management Functions
// ============================================================================

/**
 * Update sensor filters with new readings.
 * Call this after each sensor read cycle.
 */
void updateSensorFilters();

/**
 * Check if all sensors are functioning correctly.
 * @return true if sensors are healthy
 */
bool areSensorsHealthy();

/**
 * Get all sensor data as a JSON document.
 * @return JsonDocument containing all sensor readings
 */
JsonDocument getSensorData();

/**
 * Print all sensor readings to Serial (debug).
 */
void printSensorData();

/**
 * Main sensor loop - performs a complete read cycle.
 * Updates filters and checks sensor health.
 */
void sensorLoop();

// ============================================================================
// Calibration Functions
// ============================================================================

/**
 * Calibrate temperature sensor with a known reference.
 * @param known_temp Known temperature value in Celsius
 */
void calibrateTemperatureSensor(float known_temp);

/**
 * Calibrate humidity sensor with a known reference.
 * @param known_humidity Known humidity value (0-100%)
 */
void calibrateHumiditySensor(float known_humidity);

/**
 * Apply calibration offsets to raw readings.
 * Uses values from global calibration_data structure.
 */
float applyTemperatureCalibration(float raw_temp);
float applyHumidityCalibration(float raw_humidity);

// ============================================================================
// Sensor Status
// ============================================================================

/**
 * Check if ENS160+AHT21 combo sensor is available.
 * @return true if sensor responds on I2C
 */
bool isENS160Available();

/**
 * Check if TSL2591 light sensor is available.
 * @return true if sensor responds on I2C
 */
bool isTSL2591Available();

/**
 * Get sensor error count since last reset.
 * @return Number of sensor read errors
 */
int getSensorErrorCount();

/**
 * Reset sensor error count.
 */
void resetSensorErrorCount();

#endif // SENSOR_AIR_H
