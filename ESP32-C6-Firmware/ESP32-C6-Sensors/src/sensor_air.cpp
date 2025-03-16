#include "sensor_air.h"
void setupAirSensors() {
    Serial.println("Initializing Air Quality Sensors...");
}
float readTemperature() {
    return analogRead(A1) * 0.05;  // Simulated temperature
}
float readHumidity() {
    return analogRead(A2) * 0.02;  // Simulated humidity
}