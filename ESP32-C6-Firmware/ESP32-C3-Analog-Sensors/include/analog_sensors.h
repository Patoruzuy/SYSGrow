#ifndef ANALOG_SENSORS_H
#define ANALOG_SENSORS_H

#include <Arduino.h>
#include <ArduinoJson.h>
#include <Wire.h>
#include "config.h"

// Include advanced lux sensor library
#include <Adafruit_TSL2591.h>

// Soil moisture sensor structure
struct SoilMoistureSensor {
    uint8_t pin;
    String name;
    float moisture_percentage;
    uint16_t raw_value;
    bool is_active;
    bool is_calibrated;
    uint16_t dry_value;
    uint16_t wet_value;
    unsigned long last_read;
    float filtered_readings[FILTER_SIZE];
    uint8_t filter_index;
};

// Lux sensor structure
struct LuxSensor {
    uint8_t analog_pin;
    String name;
    float lux_value;
    uint16_t raw_value;
    bool is_active;
    bool is_calibrated;
    bool is_digital_sensor;
    unsigned long last_read;
    float filtered_readings[FILTER_SIZE];
    uint8_t filter_index;
    // Digital sensor specific
    Adafruit_TSL2591* tsl2591;
    uint16_t integration_time;
    tsl2591Gain_t gain;
};

// Function prototypes for sensor management
void setupAnalogSensors();
void initializeSoilSensors();
void initializeLuxSensor();
void powerControlSensors(bool power_on);

// Soil moisture sensor functions
float readSoilMoisture(uint8_t sensor_index);
float readRawSoilMoisture(uint8_t sensor_index);
void calibrateSoilSensor(uint8_t sensor_index, bool dry_calibration = true);
void autoCalibrateSoilSensors();
bool isSoilSensorCalibrated(uint8_t sensor_index);
void setSoilSensorCalibration(uint8_t sensor_index, uint16_t dry_val, uint16_t wet_val);
String getSoilMoistureStatus(uint8_t sensor_index);

// Lux sensor functions  
float readLuxLevel();
float readRawLuxLevel();
void calibrateLuxSensor();
void switchLuxSensorType(uint8_t sensor_type);
bool isLuxSensorCalibrated();
void setLuxSensorCalibration(uint16_t dark_val, uint16_t bright_val, float factor);
String getLuxStatus();

// Digital lux sensor (TSL2591) functions
bool initializeDigitalLuxSensor();
float readDigitalLux();
void configureLuxSensorGain(tsl2591Gain_t gain);
void configureLuxSensorIntegration(tsl2591IntegrationTime_t time);
uint32_t getLuxSensorID();

// Sensor array management
void readAllSoilSensors();
void updateSensorFilters();
bool validateAllSensorReadings();
void resetSensorFilters();
bool areSensorsHealthy();

// Data formatting and export
JsonDocument getAllSensorData();
JsonDocument getSoilSensorData();
JsonDocument getLuxSensorData();
String formatSensorDataCSV();
void printAllSensorData();
void printSensorDiagnostics();

// Calibration management
void startCalibrationMode();
void stopCalibrationMode();
bool isInCalibrationMode();
void saveAllCalibrationData();
void loadAllCalibrationData();
void resetAllCalibrations();

// Advanced sensor features
void enableSensorAlerts(bool enable);
void setSoilMoistureThresholds(uint8_t sensor_index, float low_threshold, float high_threshold);
void setLuxThresholds(float low_threshold, float high_threshold);
bool checkSensorAlerts();
void handleSensorAlert(const String& alert_type, uint8_t sensor_index, float value);

// Sensor statistics
struct SensorStats {
    float min_value;
    float max_value;
    float avg_value;
    uint32_t reading_count;
    unsigned long last_reset;
};

void updateSensorStats();
SensorStats getSoilSensorStats(uint8_t sensor_index);
SensorStats getLuxSensorStats();
void resetSensorStats();

// Error handling and diagnostics
enum SensorError {
    SENSOR_OK = 0,
    SENSOR_NOT_CONNECTED = 1,
    SENSOR_VALUE_OUT_OF_RANGE = 2,
    SENSOR_NOT_CALIBRATED = 3,
    SENSOR_POWER_FAILURE = 4,
    SENSOR_I2C_ERROR = 5
};

SensorError diagnoseSoilSensor(uint8_t sensor_index);
SensorError diagnoseLuxSensor();
String getSensorErrorDescription(SensorError error);
void handleSensorError(SensorError error, uint8_t sensor_index = 255);

// Constants for sensor calculations
extern const float SOIL_MOISTURE_VOLTAGE_FACTOR;
extern const float LUX_VOLTAGE_FACTOR;
extern const uint16_t ADC_MAX_VALUE;
extern const float REFERENCE_VOLTAGE;

// Global sensor instances
extern SoilMoistureSensor soil_sensors[SOIL_SENSOR_COUNT];
extern LuxSensor lux_sensor;
extern bool sensors_initialized;
extern bool calibration_mode_active;
extern unsigned long calibration_start_time;

#endif // ANALOG_SENSORS_H