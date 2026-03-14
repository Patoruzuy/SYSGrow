#include "analog_sensors.h"
#include "config.h"

// Constants for sensor calculations
const float SOIL_MOISTURE_VOLTAGE_FACTOR = REFERENCE_VOLTAGE / ADC_MAX_VALUE;
const float LUX_VOLTAGE_FACTOR = REFERENCE_VOLTAGE / ADC_MAX_VALUE;
const uint16_t ADC_MAX_VALUE = 4095;  // 12-bit ADC
const float REFERENCE_VOLTAGE = 3.3;

// Global sensor instances
SoilMoistureSensor soil_sensors[SOIL_SENSOR_COUNT];
LuxSensor lux_sensor;
bool sensors_initialized = false;
bool calibration_mode_active = false;
unsigned long calibration_start_time = 0;

// Sensor pins mapping
const uint8_t soil_pins[SOIL_SENSOR_COUNT] = {
    SOIL_MOISTURE_PIN_1,
    SOIL_MOISTURE_PIN_2,
    SOIL_MOISTURE_PIN_3,
    SOIL_MOISTURE_PIN_4
};

void setupAnalogSensors() {
    LOG_INFO("Initializing analog sensors...");
    
    // Initialize soil moisture sensors
    initializeSoilSensors();
    
    // Initialize lux sensor
    initializeLuxSensor();
    
    // Power on sensors
    powerControlSensors(true);
    
    // Allow sensors to stabilize
    delay(SENSOR_STABILIZATION_TIME);
    
    // Load calibration data
    loadAllCalibrationData();
    
    // Perform initial readings to populate filters
    resetSensorFilters();
    
    sensors_initialized = true;
    sensors_active = true;
    
    LOG_INFO("Analog sensors initialized successfully");
    printSensorDiagnostics();
}

void initializeSoilSensors() {
    LOG_INFO("Initializing " + String(SOIL_SENSOR_COUNT) + " soil moisture sensors...");
    
    for (uint8_t i = 0; i < SOIL_SENSOR_COUNT; i++) {
        soil_sensors[i].pin = soil_pins[i];
        soil_sensors[i].name = "Soil_" + String(i + 1);
        soil_sensors[i].moisture_percentage = 0.0;
        soil_sensors[i].raw_value = 0;
        soil_sensors[i].is_active = true;
        soil_sensors[i].is_calibrated = false;
        soil_sensors[i].dry_value = SOIL_DRY_VALUE;
        soil_sensors[i].wet_value = SOIL_WET_VALUE;
        soil_sensors[i].last_read = 0;
        soil_sensors[i].filter_index = 0;
        
        // Initialize filter array
        for (uint8_t j = 0; j < FILTER_SIZE; j++) {
            soil_sensors[i].filtered_readings[j] = 0.0;
        }
        
        // Configure pin
        pinMode(soil_sensors[i].pin, INPUT);
        
        LOG_DEBUG("Soil sensor " + String(i + 1) + " initialized on pin " + String(soil_sensors[i].pin));
    }
}

void initializeLuxSensor() {
    LOG_INFO("Initializing lux sensor...");
    
    lux_sensor.analog_pin = LUX_SENSOR_PIN;
    lux_sensor.name = "Lux_Sensor";
    lux_sensor.lux_value = 0.0;
    lux_sensor.raw_value = 0;
    lux_sensor.is_active = true;
    lux_sensor.is_calibrated = false;
    lux_sensor.is_digital_sensor = false;
    lux_sensor.last_read = 0;
    lux_sensor.filter_index = 0;
    lux_sensor.tsl2591 = nullptr;
    lux_sensor.integration_time = 100;
    lux_sensor.gain = TSL2591_GAIN_MED;
    
    // Initialize filter array
    for (uint8_t j = 0; j < FILTER_SIZE; j++) {
        lux_sensor.filtered_readings[j] = 0.0;
    }
    
    // Configure analog pin
    pinMode(lux_sensor.analog_pin, INPUT);
    
    // Try to initialize digital sensor if I2C is available
    if (initializeDigitalLuxSensor()) {
        lux_sensor.is_digital_sensor = true;
        active_lux_sensor_type = LUX_SENSOR_TYPE_TSL2591;
        LOG_INFO("Digital lux sensor (TSL2591) initialized successfully");
    } else {
        lux_sensor.is_digital_sensor = false;
        active_lux_sensor_type = LUX_SENSOR_TYPE_ANALOG;
        LOG_INFO("Using analog lux sensor (photoresistor)");
    }
}

bool initializeDigitalLuxSensor() {
    LOG_DEBUG("Attempting to initialize digital lux sensor...");
    
    // Initialize I2C
    Wire.begin(SDA_PIN, SCL_PIN);
    Wire.setClock(100000);  // 100kHz I2C clock
    
    // Create TSL2591 instance
    lux_sensor.tsl2591 = new Adafruit_TSL2591(2591);
    
    if (lux_sensor.tsl2591->begin()) {
        // Configure sensor
        lux_sensor.tsl2591->setGain(TSL2591_GAIN_MED);
        lux_sensor.tsl2591->setTiming(TSL2591_INTEGRATIONTIME_300MS);
        
        // Verify sensor ID
        uint32_t sensor_id = getLuxSensorID();
        if (sensor_id != 0) {
            LOG_INFO("TSL2591 sensor found with ID: 0x" + String(sensor_id, HEX));
            return true;
        }
    }
    
    // Clean up on failure
    if (lux_sensor.tsl2591) {
        delete lux_sensor.tsl2591;
        lux_sensor.tsl2591 = nullptr;
    }
    
    LOG_DEBUG("Digital lux sensor not found or failed to initialize");
    return false;
}

void powerControlSensors(bool power_on) {
    digitalWrite(SENSOR_POWER_PIN, power_on ? HIGH : LOW);
    
    if (power_on) {
        LOG_DEBUG("Sensors powered ON");
        delay(SENSOR_STABILIZATION_TIME);
    } else {
        LOG_DEBUG("Sensors powered OFF");
    }
}

float readSoilMoisture(uint8_t sensor_index) {
    if (sensor_index >= SOIL_SENSOR_COUNT || !soil_sensors[sensor_index].is_active) {
        return NAN;
    }
    
    // Read raw value
    float raw_reading = readRawSoilMoisture(sensor_index);
    
    // Update filter
    soil_sensors[sensor_index].filtered_readings[soil_sensors[sensor_index].filter_index] = raw_reading;
    soil_sensors[sensor_index].filter_index = (soil_sensors[sensor_index].filter_index + 1) % FILTER_SIZE;
    
    // Calculate filtered average
    float sum = 0;
    for (uint8_t i = 0; i < FILTER_SIZE; i++) {
        sum += soil_sensors[sensor_index].filtered_readings[i];
    }
    float filtered_raw = sum / FILTER_SIZE;
    
    // Store raw value
    soil_sensors[sensor_index].raw_value = (uint16_t)filtered_raw;
    
    // Convert to percentage if calibrated
    float percentage;
    if (soil_sensors[sensor_index].is_calibrated) {
        uint16_t dry_val = soil_sensors[sensor_index].dry_value;
        uint16_t wet_val = soil_sensors[sensor_index].wet_value;
        
        // Ensure wet value is less than dry value (lower resistance = more moisture)
        if (wet_val >= dry_val) {
            LOG_WARN("Invalid calibration for sensor " + String(sensor_index + 1));
            percentage = 0.0;
        } else {
            // Calculate percentage (inverted scale for resistive sensors)
            percentage = 100.0 * (dry_val - filtered_raw) / (dry_val - wet_val);
            percentage = constrain(percentage, 0.0, 100.0);
        }
    } else {
        // Default conversion without calibration
        percentage = 100.0 * (SOIL_DRY_VALUE - filtered_raw) / (SOIL_DRY_VALUE - SOIL_WET_VALUE);
        percentage = constrain(percentage, 0.0, 100.0);
    }
    
    soil_sensors[sensor_index].moisture_percentage = percentage;
    soil_sensors[sensor_index].last_read = millis();
    
    return percentage;
}

float readRawSoilMoisture(uint8_t sensor_index) {
    if (sensor_index >= SOIL_SENSOR_COUNT) {
        return 0;
    }
    
    // Take multiple samples for stability
    uint32_t sum = 0;
    for (uint8_t i = 0; i < ADC_SAMPLES; i++) {
        sum += analogRead(soil_sensors[sensor_index].pin);
        delayMicroseconds(100);
    }
    
    return sum / ADC_SAMPLES;
}

float readLuxLevel() {
    if (!lux_sensor.is_active) {
        return NAN;
    }
    
    float raw_reading;
    
    if (lux_sensor.is_digital_sensor && lux_sensor.tsl2591) {
        raw_reading = readDigitalLux();
    } else {
        raw_reading = readRawLuxLevel();
    }
    
    // Update filter
    lux_sensor.filtered_readings[lux_sensor.filter_index] = raw_reading;
    lux_sensor.filter_index = (lux_sensor.filter_index + 1) % FILTER_SIZE;
    
    // Calculate filtered average
    float sum = 0;
    for (uint8_t i = 0; i < FILTER_SIZE; i++) {
        sum += lux_sensor.filtered_readings[i];
    }
    float filtered_lux = sum / FILTER_SIZE;
    
    lux_sensor.lux_value = filtered_lux;
    lux_sensor.last_read = millis();
    
    return filtered_lux;
}

float readRawLuxLevel() {
    // Take multiple samples for stability
    uint32_t sum = 0;
    for (uint8_t i = 0; i < ADC_SAMPLES; i++) {
        sum += analogRead(lux_sensor.analog_pin);
        delayMicroseconds(100);
    }
    
    float raw_value = sum / ADC_SAMPLES;
    lux_sensor.raw_value = (uint16_t)raw_value;
    
    // Convert to approximate lux value
    // This is a simplified conversion for photoresistor
    float voltage = raw_value * LUX_VOLTAGE_FACTOR;
    float resistance = (REFERENCE_VOLTAGE - voltage) / voltage * 10000;  // Assuming 10k pullup
    
    // Convert resistance to lux (approximate formula for typical photoresistor)
    float lux = 500000.0 / resistance;
    
    return constrain(lux, 0, LUX_MAX_LUX_VALUE);
}

float readDigitalLux() {
    if (!lux_sensor.tsl2591) {
        return 0;
    }
    
    uint32_t lum = lux_sensor.tsl2591->getFullLuminosity();
    uint16_t ir = lum >> 16;
    uint16_t full = lum & 0xFFFF;
    
    float lux = lux_sensor.tsl2591->calculateLux(full, ir);
    
    // Handle invalid readings
    if (lux < 0 || isnan(lux) || isinf(lux)) {
        LOG_WARN("Invalid lux reading from digital sensor");
        return 0;
    }
    
    return lux;
}

void readAllSoilSensors() {
    LOG_DEBUG("Reading all soil moisture sensors...");
    
    for (uint8_t i = 0; i < SOIL_SENSOR_COUNT; i++) {
        if (soil_sensors[i].is_active) {
            float moisture = readSoilMoisture(i);
            LOG_DEBUG("Soil " + String(i + 1) + ": " + String(moisture) + "% (Raw: " + String(soil_sensors[i].raw_value) + ")");
        }
    }
}

bool validateAllSensorReadings() {
    bool all_valid = true;
    
    // Validate soil sensors
    for (uint8_t i = 0; i < SOIL_SENSOR_COUNT; i++) {
        if (soil_sensors[i].is_active) {
            SensorError error = diagnoseSoilSensor(i);
            if (error != SENSOR_OK) {
                LOG_WARN("Soil sensor " + String(i + 1) + " error: " + getSensorErrorDescription(error));
                all_valid = false;
            }
        }
    }
    
    // Validate lux sensor
    if (lux_sensor.is_active) {
        SensorError error = diagnoseLuxSensor();
        if (error != SENSOR_OK) {
            LOG_WARN("Lux sensor error: " + getSensorErrorDescription(error));
            all_valid = false;
        }
    }
    
    return all_valid;
}

JsonDocument getAllSensorData() {
    DynamicJsonDocument doc(2048);
    
    doc["timestamp"] = millis();
    doc["device_id"] = device_id;
    doc["unit_id"] = unit_id;
    
    // Soil moisture sensors
    JsonArray soil_array = doc.createNestedArray("soil_moisture");
    for (uint8_t i = 0; i < SOIL_SENSOR_COUNT; i++) {
        if (soil_sensors[i].is_active) {
            JsonObject soil_obj = soil_array.createNestedObject();
            soil_obj["sensor_id"] = i + 1;
            soil_obj["name"] = soil_sensors[i].name;
            soil_obj["moisture_percentage"] = round(soil_sensors[i].moisture_percentage * 100) / 100.0;
            soil_obj["raw_value"] = soil_sensors[i].raw_value;
            soil_obj["is_calibrated"] = soil_sensors[i].is_calibrated;
            soil_obj["status"] = getSoilMoistureStatus(i);
        }
    }
    
    // Lux sensor
    JsonObject lux_obj = doc.createNestedObject("light_level");
    lux_obj["lux_value"] = round(lux_sensor.lux_value * 100) / 100.0;
    lux_obj["raw_value"] = lux_sensor.raw_value;
    lux_obj["sensor_type"] = lux_sensor.is_digital_sensor ? "digital" : "analog";
    lux_obj["is_calibrated"] = lux_sensor.is_calibrated;
    lux_obj["status"] = getLuxStatus();
    
    // System information
    JsonObject system = doc.createNestedObject("system");
    system["battery_voltage"] = readBatteryVoltage();
    system["battery_percentage"] = calculateBatteryPercentage(readBatteryVoltage());
    system["rssi"] = WiFi.RSSI();
    system["free_heap"] = ESP.getFreeHeap();
    system["uptime"] = millis() / 1000;
    system["power_mode"] = power_mode;
    
    return doc;
}

void printAllSensorData() {
    LOG_INFO("=== Current Sensor Readings ===");
    
    // Soil moisture sensors
    for (uint8_t i = 0; i < SOIL_SENSOR_COUNT; i++) {
        if (soil_sensors[i].is_active) {
            LOG_INFO("Soil " + String(i + 1) + " (" + soil_sensors[i].name + "): " + 
                    String(soil_sensors[i].moisture_percentage) + "% (Raw: " + 
                    String(soil_sensors[i].raw_value) + ")");
        }
    }
    
    // Lux sensor
    LOG_INFO("Lux: " + String(lux_sensor.lux_value) + " lux (Raw: " + 
            String(lux_sensor.raw_value) + ", Type: " + 
            (lux_sensor.is_digital_sensor ? "Digital" : "Analog") + ")");
    
    // System status
    LOG_INFO("Battery: " + String(readBatteryVoltage()) + "V (" + 
            String(calculateBatteryPercentage(readBatteryVoltage())) + "%)");
    LOG_INFO("WiFi RSSI: " + String(WiFi.RSSI()) + " dBm");
    LOG_INFO("Free Heap: " + String(ESP.getFreeHeap()) + " bytes");
    
    LOG_INFO("==============================");
}

String getSoilMoistureStatus(uint8_t sensor_index) {
    if (sensor_index >= SOIL_SENSOR_COUNT || !soil_sensors[sensor_index].is_active) {
        return "inactive";
    }
    
    float moisture = soil_sensors[sensor_index].moisture_percentage;
    
    if (moisture < 20) {
        return "dry";
    } else if (moisture < 40) {
        return "low";
    } else if (moisture < 70) {
        return "optimal";
    } else if (moisture < 90) {
        return "high";
    } else {
        return "saturated";
    }
}

String getLuxStatus() {
    if (!lux_sensor.is_active) {
        return "inactive";
    }
    
    float lux = lux_sensor.lux_value;
    
    if (lux < 10) {
        return "dark";
    } else if (lux < 100) {
        return "low";
    } else if (lux < 1000) {
        return "moderate";
    } else if (lux < 10000) {
        return "bright";
    } else {
        return "very_bright";
    }
}

void printSensorDiagnostics() {
    LOG_INFO("=== Sensor Diagnostics ===");
    
    for (uint8_t i = 0; i < SOIL_SENSOR_COUNT; i++) {
        SensorError error = diagnoseSoilSensor(i);
        LOG_INFO("Soil " + String(i + 1) + ": " + getSensorErrorDescription(error));
    }
    
    SensorError lux_error = diagnoseLuxSensor();
    LOG_INFO("Lux Sensor: " + getSensorErrorDescription(lux_error));
    
    LOG_INFO("=========================");
}

SensorError diagnoseSoilSensor(uint8_t sensor_index) {
    if (sensor_index >= SOIL_SENSOR_COUNT) {
        return SENSOR_NOT_CONNECTED;
    }
    
    if (!soil_sensors[sensor_index].is_active) {
        return SENSOR_NOT_CONNECTED;
    }
    
    uint16_t raw_value = soil_sensors[sensor_index].raw_value;
    
    // Check for sensor disconnection (max value indicates open circuit)
    if (raw_value >= ADC_MAX_VALUE - 10) {
        return SENSOR_NOT_CONNECTED;
    }
    
    // Check for short circuit (very low values)
    if (raw_value < 10) {
        return SENSOR_VALUE_OUT_OF_RANGE;
    }
    
    // Check calibration status
    if (!soil_sensors[sensor_index].is_calibrated) {
        return SENSOR_NOT_CALIBRATED;
    }
    
    return SENSOR_OK;
}

SensorError diagnoseLuxSensor() {
    if (!lux_sensor.is_active) {
        return SENSOR_NOT_CONNECTED;
    }
    
    if (lux_sensor.is_digital_sensor) {
        if (!lux_sensor.tsl2591) {
            return SENSOR_I2C_ERROR;
        }
        
        // Try to read sensor ID
        if (getLuxSensorID() == 0) {
            return SENSOR_I2C_ERROR;
        }
    } else {
        // Analog sensor checks
        uint16_t raw_value = lux_sensor.raw_value;
        
        if (raw_value >= ADC_MAX_VALUE - 10) {
            return SENSOR_NOT_CONNECTED;
        }
    }
    
    return SENSOR_OK;
}

String getSensorErrorDescription(SensorError error) {
    switch (error) {
        case SENSOR_OK:
            return "OK";
        case SENSOR_NOT_CONNECTED:
            return "Not Connected";
        case SENSOR_VALUE_OUT_OF_RANGE:
            return "Value Out of Range";
        case SENSOR_NOT_CALIBRATED:
            return "Not Calibrated";
        case SENSOR_POWER_FAILURE:
            return "Power Failure";
        case SENSOR_I2C_ERROR:
            return "I2C Communication Error";
        default:
            return "Unknown Error";
    }
}

uint32_t getLuxSensorID() {
    if (lux_sensor.tsl2591) {
        return lux_sensor.tsl2591->readRegister(TSL2591_REGISTER_DEVICE_ID);
    }
    return 0;
}

void resetSensorFilters() {
    LOG_DEBUG("Resetting sensor filters...");
    
    // Reset soil sensor filters
    for (uint8_t i = 0; i < SOIL_SENSOR_COUNT; i++) {
        float initial_reading = readRawSoilMoisture(i);
        for (uint8_t j = 0; j < FILTER_SIZE; j++) {
            soil_sensors[i].filtered_readings[j] = initial_reading;
        }
        soil_sensors[i].filter_index = 0;
    }
    
    // Reset lux sensor filter
    float initial_lux = readRawLuxLevel();
    for (uint8_t j = 0; j < FILTER_SIZE; j++) {
        lux_sensor.filtered_readings[j] = initial_lux;
    }
    lux_sensor.filter_index = 0;
    
    LOG_DEBUG("Sensor filters reset complete");
}