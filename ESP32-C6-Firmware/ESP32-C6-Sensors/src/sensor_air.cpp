/**
 * Sensor Air Module - Environmental Sensors
 * ==========================================
 *
 * Handles reading from:
 *   - ENS160 + AHT21 combo sensor (Temperature, Humidity, CO2, AQI, VOC)
 *   - TSL2591 light sensor (Lux, Full Spectrum, Infrared, Visible)
 *
 * Uses I2C communication on pins defined in config.h
 *
 * Version: 2.0.0
 */

#include "sensor_air.h"
#include "config.h"
#include <Wire.h>

// Include sensor libraries (install via PlatformIO)
// - ScioSense ENS160: https://github.com/sciosense/ENS160_driver
// - Adafruit AHTX0: https://github.com/adafruit/Adafruit_AHTX0
// - Adafruit TSL2591: https://github.com/adafruit/Adafruit_TSL2591_Library

// Conditional includes based on available libraries
#if __has_include(<ScioSense_ENS160.h>)
    #include <ScioSense_ENS160.h>
    #define HAS_ENS160 1
#else
    #define HAS_ENS160 0
#endif

#if __has_include(<Adafruit_AHTX0.h>)
    #include <Adafruit_AHTX0.h>
    #define HAS_AHT21 1
#else
    #define HAS_AHT21 0
#endif

#if __has_include(<Adafruit_TSL2591.h>)
    #include <Adafruit_TSL2591.h>
    #define HAS_TSL2591 1
#else
    #define HAS_TSL2591 0
#endif

// ============================================================================
// Sensor Objects
// ============================================================================

#if HAS_ENS160
ScioSense_ENS160 ens160(ENS160_I2CADDR_1);  // Default I2C address 0x53
#endif

#if HAS_AHT21
Adafruit_AHTX0 aht;
#endif

#if HAS_TSL2591
Adafruit_TSL2591 tsl = Adafruit_TSL2591(2591);
#endif

// ============================================================================
// Sensor State
// ============================================================================

static bool ens160_available = false;
static bool aht21_available = false;
static bool tsl2591_available = false;
static bool sensors_initialized = false;

// Moving average filters
#define FILTER_SIZE 5
static float temp_readings[FILTER_SIZE] = {0};
static float humidity_readings[FILTER_SIZE] = {0};
static float light_readings[FILTER_SIZE] = {0};
static int filter_index = 0;
static bool filters_initialized = false;

// Sensor health tracking
static int error_count = 0;
static unsigned long last_read_time = 0;
static bool sensors_healthy = true;

// Cached TSL2591 readings (updated together)
static uint16_t cached_full_spectrum = 0;
static uint16_t cached_infrared = 0;
static uint16_t cached_visible = 0;
static float cached_lux = NAN;
static unsigned long last_tsl_read = 0;

// ENS160 cached readings
static int cached_co2 = -1;
static int cached_aqi = -1;
static int cached_voc = -1;
static unsigned long last_ens_read = 0;

// Read cache timeout (don't read sensors more than every 2 seconds)
#define SENSOR_CACHE_MS 2000

// ============================================================================
// Setup Functions
// ============================================================================

void setupSensors() {
    setupAirSensors();
}

void setupAirSensors() {
    LOG_INFO("Initializing Environmental Sensors...");

    // Initialize I2C
    Wire.begin(I2C_SDA_PIN, I2C_SCL_PIN);
    Wire.setClock(100000);  // 100kHz for better stability

    // Initialize ENS160
#if HAS_ENS160
    LOG_DEBUG("Initializing ENS160...");
    if (ens160.begin()) {
        ens160_available = true;
        ens160.setMode(ENS160_OPMODE_STD);  // Standard operation mode
        LOG_INFO("ENS160 initialized successfully");
    } else {
        LOG_WARN("ENS160 not found or initialization failed");
    }
#else
    LOG_WARN("ENS160 library not available");
#endif

    // Initialize AHT21
#if HAS_AHT21
    LOG_DEBUG("Initializing AHT21...");
    if (aht.begin()) {
        aht21_available = true;
        LOG_INFO("AHT21 initialized successfully");
    } else {
        LOG_WARN("AHT21 not found or initialization failed");
    }
#else
    LOG_WARN("AHT21 library not available");
#endif

    // Initialize TSL2591
#if HAS_TSL2591
    LOG_DEBUG("Initializing TSL2591...");
    if (tsl.begin()) {
        tsl2591_available = true;
        // Configure sensor for medium gain and integration time
        tsl.setGain(TSL2591_GAIN_MED);       // 25x gain
        tsl.setTiming(TSL2591_INTEGRATIONTIME_300MS);
        LOG_INFO("TSL2591 initialized successfully");
    } else {
        LOG_WARN("TSL2591 not found or initialization failed");
    }
#else
    LOG_WARN("TSL2591 library not available");
#endif

    // Initialize filters
    initializeSensorFilters();

    sensors_initialized = true;
    LOG_INFO("Sensor initialization complete");
    LOG_INFO("  ENS160: " + String(ens160_available ? "OK" : "Not found"));
    LOG_INFO("  AHT21: " + String(aht21_available ? "OK" : "Not found"));
    LOG_INFO("  TSL2591: " + String(tsl2591_available ? "OK" : "Not found"));
}

void initializeSensorFilters() {
    LOG_DEBUG("Initializing sensor filters...");

    // Take initial readings to populate filters
    for (int i = 0; i < FILTER_SIZE; i++) {
        temp_readings[i] = readRawTemperature();
        humidity_readings[i] = readRawHumidity();
        light_readings[i] = readRawLightLevel();
        delay(50);
    }

    filters_initialized = true;
    LOG_DEBUG("Sensor filters initialized");
}

// ============================================================================
// AHT21 Temperature & Humidity
// ============================================================================

float readRawTemperature() {
#if HAS_AHT21
    if (!aht21_available) {
        return NAN;
    }

    sensors_event_t humidity_event, temp_event;
    if (aht.getEvent(&humidity_event, &temp_event)) {
        return temp_event.temperature;
    }
#endif
    return NAN;
}

float readRawHumidity() {
#if HAS_AHT21
    if (!aht21_available) {
        return NAN;
    }

    sensors_event_t humidity_event, temp_event;
    if (aht.getEvent(&humidity_event, &temp_event)) {
        return humidity_event.relative_humidity;
    }
#endif
    return NAN;
}

float readTemperature() {
    if (!filters_initialized) {
        initializeSensorFilters();
    }

    float raw_temp = readRawTemperature();

    if (isnan(raw_temp)) {
        error_count++;
        return NAN;
    }

    // Update moving average
    temp_readings[filter_index] = raw_temp;

    // Calculate filtered value
    float sum = 0;
    int valid_count = 0;
    for (int i = 0; i < FILTER_SIZE; i++) {
        if (!isnan(temp_readings[i])) {
            sum += temp_readings[i];
            valid_count++;
        }
    }

    if (valid_count == 0) {
        return NAN;
    }

    float filtered_temp = sum / valid_count;

    // Apply calibration
    filtered_temp = applyTemperatureCalibration(filtered_temp);

    // Validate range
    if (filtered_temp < -40 || filtered_temp > 125) {
        LOG_ERROR("Temperature out of range: " + String(filtered_temp));
        error_count++;
        return NAN;
    }

    return filtered_temp;
}

float readHumidity() {
    if (!filters_initialized) {
        initializeSensorFilters();
    }

    float raw_humidity = readRawHumidity();

    if (isnan(raw_humidity)) {
        error_count++;
        return NAN;
    }

    // Update moving average
    humidity_readings[filter_index] = raw_humidity;

    // Calculate filtered value
    float sum = 0;
    int valid_count = 0;
    for (int i = 0; i < FILTER_SIZE; i++) {
        if (!isnan(humidity_readings[i])) {
            sum += humidity_readings[i];
            valid_count++;
        }
    }

    if (valid_count == 0) {
        return NAN;
    }

    float filtered_humidity = sum / valid_count;

    // Apply calibration
    filtered_humidity = applyHumidityCalibration(filtered_humidity);

    // Clamp to valid range
    filtered_humidity = constrain(filtered_humidity, 0, 100);

    return filtered_humidity;
}

// ============================================================================
// ENS160 Air Quality Sensor
// ============================================================================

void updateENS160Readings() {
#if HAS_ENS160
    if (!ens160_available) {
        cached_co2 = -1;
        cached_aqi = -1;
        cached_voc = -1;
        return;
    }

    unsigned long now = millis();
    if (now - last_ens_read < SENSOR_CACHE_MS && cached_co2 >= 0) {
        return;  // Use cached values
    }

    // Provide temperature and humidity compensation if available
    float temp = readTemperature();
    float hum = readHumidity();

    if (!isnan(temp) && !isnan(hum)) {
        ens160.set_envdata(temp, hum);
    }

    // Read sensor data
    if (ens160.measure()) {
        cached_co2 = ens160.geteCO2();
        cached_aqi = ens160.getAQI();
        cached_voc = ens160.getTVOC();
        last_ens_read = now;
    } else {
        error_count++;
        LOG_WARN("ENS160 measurement failed");
    }
#endif
}

int readCO2() {
    updateENS160Readings();
    return cached_co2;
}

int readAirQualityIndex() {
    updateENS160Readings();
    return cached_aqi;
}

int readVOC() {
    updateENS160Readings();
    return cached_voc;
}

// ============================================================================
// TSL2591 Light Sensor
// ============================================================================

void updateTSL2591Readings() {
#if HAS_TSL2591
    if (!tsl2591_available) {
        cached_full_spectrum = 0;
        cached_infrared = 0;
        cached_visible = 0;
        cached_lux = NAN;
        return;
    }

    unsigned long now = millis();
    if (now - last_tsl_read < SENSOR_CACHE_MS && cached_full_spectrum > 0) {
        return;  // Use cached values
    }

    // Get raw luminosity values
    uint32_t lum = tsl.getFullLuminosity();
    cached_infrared = lum >> 16;
    cached_full_spectrum = lum & 0xFFFF;
    cached_visible = cached_full_spectrum - cached_infrared;

    // Calculate lux
    cached_lux = tsl.calculateLux(cached_full_spectrum, cached_infrared);

    // Handle overflow (sensor saturated)
    if (cached_lux < 0) {
        cached_lux = 88000;  // Max lux for sensor
    }

    last_tsl_read = now;
#endif
}

float readRawLightLevel() {
    updateTSL2591Readings();
    return cached_lux;
}

float readLightLevel() {
    if (!filters_initialized) {
        initializeSensorFilters();
    }

    float raw_lux = readRawLightLevel();

    if (isnan(raw_lux)) {
        error_count++;
        return NAN;
    }

    // Update moving average
    light_readings[filter_index] = raw_lux;

    // Calculate filtered value
    float sum = 0;
    int valid_count = 0;
    for (int i = 0; i < FILTER_SIZE; i++) {
        if (!isnan(light_readings[i])) {
            sum += light_readings[i];
            valid_count++;
        }
    }

    if (valid_count == 0) {
        return NAN;
    }

    float filtered_lux = sum / valid_count;

    // Apply calibration factor
    filtered_lux *= calibration_data.lux_calibration_factor;

    return filtered_lux;
}

uint16_t readFullSpectrum() {
    updateTSL2591Readings();
    return cached_full_spectrum;
}

uint16_t readInfrared() {
    updateTSL2591Readings();
    return cached_infrared;
}

uint16_t readVisible() {
    updateTSL2591Readings();
    return cached_visible;
}

// ============================================================================
// Soil Moisture (Placeholder for future expansion)
// ============================================================================

float readSoilMoisture() {
    // This device type doesn't have soil moisture sensor
    // Return NAN for payload compatibility
    return NAN;
}

float readRawSoilMoisture() {
    return NAN;
}

// ============================================================================
// Sensor Management
// ============================================================================

void updateSensorFilters() {
    filter_index = (filter_index + 1) % FILTER_SIZE;
    last_read_time = millis();
}

void sensorLoop() {
    // Perform a complete read cycle
    readTemperature();
    readHumidity();
    readCO2();
    readLightLevel();

    // Update filter index
    updateSensorFilters();

    // Debug output
    if (config_flags & CONFIG_FLAG_DEBUG_MODE) {
        printSensorData();
    }
}

bool areSensorsHealthy() {
    // Reset error count periodically (every 5 minutes)
    if (millis() - last_read_time > 300000) {
        error_count = 0;
        sensors_healthy = true;
    }

    // Mark unhealthy if too many errors
    if (error_count > 10) {
        sensors_healthy = false;
    }

    // Also check if at least one primary sensor is available
    if (!aht21_available && !ens160_available && !tsl2591_available) {
        sensors_healthy = false;
    }

    return sensors_healthy;
}

bool isENS160Available() {
    return ens160_available;
}

bool isTSL2591Available() {
    return tsl2591_available;
}

int getSensorErrorCount() {
    return error_count;
}

void resetSensorErrorCount() {
    error_count = 0;
    sensors_healthy = true;
}

// ============================================================================
// Calibration Functions
// ============================================================================

float applyTemperatureCalibration(float raw_temp) {
    if (isnan(raw_temp)) {
        return NAN;
    }
    return raw_temp + calibration_data.temperature_offset;
}

float applyHumidityCalibration(float raw_humidity) {
    if (isnan(raw_humidity)) {
        return NAN;
    }
    return raw_humidity + calibration_data.humidity_offset;
}

void calibrateTemperatureSensor(float known_temp) {
    float raw_temp = readRawTemperature();
    if (!isnan(raw_temp)) {
        calibration_data.temperature_offset = known_temp - raw_temp;
        LOG_INFO("Temperature calibration offset set to: " + String(calibration_data.temperature_offset));
    }
}

void calibrateHumiditySensor(float known_humidity) {
    float raw_humidity = readRawHumidity();
    if (!isnan(raw_humidity)) {
        calibration_data.humidity_offset = known_humidity - raw_humidity;
        LOG_INFO("Humidity calibration offset set to: " + String(calibration_data.humidity_offset));
    }
}

// ============================================================================
// Data Export
// ============================================================================

JsonDocument getSensorData() {
    DynamicJsonDocument doc(1024);

    // Read all sensors
    float temp = readTemperature();
    float humidity = readHumidity();
    float lux = readLightLevel();
    int co2 = readCO2();
    int aqi = readAirQualityIndex();
    int voc = readVOC();

    // Timestamp and device info
    doc["timestamp"] = millis();
    doc["device_id"] = friendly_name;

    // Sensor readings
    JsonObject sensors = doc.createNestedObject("sensors");

    if (!isnan(temp)) {
        sensors["temperature"] = round(temp * 100) / 100.0;
    } else {
        sensors["temperature"] = nullptr;
    }

    if (!isnan(humidity)) {
        sensors["humidity"] = round(humidity * 100) / 100.0;
    } else {
        sensors["humidity"] = nullptr;
    }

    if (!isnan(lux)) {
        sensors["lux"] = round(lux);
    } else {
        sensors["lux"] = nullptr;
    }

    if (co2 > 0) {
        sensors["co2"] = co2;
    } else {
        sensors["co2"] = nullptr;
    }

    if (aqi > 0) {
        sensors["air_quality"] = aqi;
    } else {
        sensors["air_quality"] = nullptr;
    }

    if (voc >= 0) {
        sensors["voc"] = voc;
    } else {
        sensors["voc"] = nullptr;
    }

    // Extended light readings
    JsonObject light = doc.createNestedObject("light");
    light["full_spectrum"] = readFullSpectrum();
    light["infrared"] = readInfrared();
    light["visible"] = readVisible();

    // Metadata
    JsonObject metadata = doc.createNestedObject("metadata");
    metadata["sensors_healthy"] = areSensorsHealthy();
    metadata["error_count"] = error_count;
    metadata["ens160_available"] = ens160_available;
    metadata["aht21_available"] = aht21_available;
    metadata["tsl2591_available"] = tsl2591_available;

    // Update filter index
    updateSensorFilters();

    return doc;
}

void printSensorData() {
    LOG_INFO("=== Sensor Readings ===");
    LOG_INFO("Temperature: " + String(readTemperature()) + " C");
    LOG_INFO("Humidity: " + String(readHumidity()) + " %");
    LOG_INFO("CO2: " + String(readCO2()) + " ppm");
    LOG_INFO("AQI: " + String(readAirQualityIndex()));
    LOG_INFO("VOC: " + String(readVOC()) + " ppb");
    LOG_INFO("Lux: " + String(readLightLevel()));
    LOG_INFO("Full Spectrum: " + String(readFullSpectrum()));
    LOG_INFO("Infrared: " + String(readInfrared()));
    LOG_INFO("Visible: " + String(readVisible()));
    LOG_INFO("Sensors Healthy: " + String(areSensorsHealthy() ? "Yes" : "No"));
    LOG_INFO("=======================");
}
