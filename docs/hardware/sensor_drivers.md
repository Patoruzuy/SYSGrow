# Sensor Drivers Overview

This document describes the hardware sensor drivers implemented in the SYSGrow backend. Each driver is responsible for low-level communication with a specific sensor type, providing raw readings for use by higher-level adapters and services. These drivers are not intended for direct use by application code.

## General Notes
- All drivers inherit from `BaseSensorDriver` and provide a standard interface.
- All drivers support Raspberry Pi hardware and provide mock data if hardware is unavailable.
- Each driver exposes a `read()` method returning a dictionary with sensor data, a timestamp, and a status field.
- Cleanup methods are provided where necessary for GPIO or hardware resource management.

---

## Supported Sensor Drivers

### 1. ENS160 + AHT21 (CO₂, TVOC, Temp, Humidity)
- **File:** `co2_sensor.py`
- **Sensors:** ENS160 (air quality), AHT21 (temperature/humidity)
- **Interface:** I2C
- **Readings:**
  - `eco2` (equivalent CO₂, ppm)
  - `tvoc` (total volatile organic compounds, ppb)
  - `temperature` (°C)
  - `humidity` (%)
  - `status` (sensor status)
- **Characteristics:**
  - ENS160: eCO₂ range 400–65000 ppm, TVOC 0–65000 ppb
  - AHT21: Temp -40–85°C, Humidity 0–100%
- **Notes:**
  - Used for air quality and environmental monitoring.

- **Class:** `ENS160_AHT21Sensor`
  ```python
  {
    'eco2': <ppm>,
    'tvoc': <ppb>,
    'temperature': <°C>,
    'humidity': <percent>,
    'status': 'OK' | 'MOCK' | 'ERROR',
    'timestamp': <iso8601>
  }
  ```

### 2. DHT11 (Temperature & Humidity)
- **File:** `dht11_sensor.py`
- **Sensor:** DHT11
- **Interface:** GPIO
- **Readings:**
  - `temperature` (°C)
  - `humidity` (%)
  - `status` (OK/MOCK)
- **Characteristics:**
  - Temp: 0–50°C, ±2°C accuracy
  - Humidity: 20–90%, ±5% accuracy
- **Notes:**
  - Simple, low-cost sensor. Retry logic and thread safety included.

- **Class:** `DHT11Sensor`
  ```python
  {
    'temperature': <°C>,
    'humidity': <percent>,
    'status': 'OK' | 'MOCK' | 'ERROR',
    'timestamp': <iso8601>
  }
  ```
  
### 3. TSL2591 (Light Intensity)
- **File:** `light_sensor.py`
- **Sensor:** TSL2591
- **Interface:** I2C
- **Readings:**
  - `lux` (illuminance)
  - `full_spectrum`, `infrared`, `visible` (raw counts)
  - `status` (OK/MOCK)
- **Characteristics:**
  - Range: 188 µlux to 88,000 lux
  - High dynamic range, suitable for plant lighting
- **Notes:**
  - Used for monitoring grow light and sunlight levels.

- **Class:** `TSL2591Sensor`
  ```python
  {
    'lux': <lux>,
    'full_spectrum': <raw count>,
    'infrared': <raw count>,
    'visible': <raw count>,
    'status': 'OK' | 'MOCK' | 'ERROR',
    'timestamp': <iso8601>
  }
  ```
  
### 4. MQ2 (Gas/Smoke Sensor)
- **File:** `mq2_sensor.py`
- **Sensor:** MQ2
- **Interface:** Digital GPIO or Analog (via ADS1115)
- **Readings:**
  - `smoke` (digital: 0/1, analog: raw ADC value)
  - `mode` (digital/analog)
  - `status` (OK/MOCK)
- **Characteristics:**
  - Detects LPG, smoke, methane, CO, alcohol, propane, hydrogen
  - Analog output: 0–5V (requires ADC)
- **Notes:**
  - Can be used for air quality/safety monitoring.

- **Class:** `MQ2Sensor`
  ```python
  {
    'smoke': <0|1> | <raw ADC value>,
    'mode': 'digital' | 'analog',
    'status': 'OK' | 'MOCK' | 'ERROR',
    'timestamp': <iso8601>
  }
  ```
  
### 5. Soil Moisture Sensor (Analog)
- **File:** `soil_moisture_sensor.py`
- **Sensor:** Generic analog soil moisture probe
- **Interface:** Analog (via ADS1115)
- **Readings:**
  - `soil_moisture` (%)
  - `adc_raw` (raw ADC value)
  - `voltage` (V)
  - `status` (OK/MOCK)
- **Characteristics:**
  - Output: 0–3.3V or 0–5V (mapped to 0–100% moisture)
  - Calibration required for accurate readings
- **Notes:**
  - Used for irrigation and soil monitoring.

- **Class:** `SoilMoistureSensor`
```python
  {
    'soil_moisture': <percent>,
    'adc_raw': <raw ADC value>,
    'voltage': <V>,
    'status': 'OK' | 'MOCK' | 'ERROR',
    'timestamp': <iso8601>
  }
```
  
### 6. BME280 (Temperature, Humidity, Pressure)
- **File:** `temp_humidity_sensor.py`
- **Sensor:** BME280
- **Interface:** I2C
- **Readings:**
  - `temperature` (°C)
  - `humidity` (%)
  - `pressure` (hPa)
  - `altitude` (m, optional)
  - `status` (OK/MOCK)
- **Characteristics:**
  - Temp: -40–85°C, Humidity: 0–100%, Pressure: 300–1100 hPa
  - Altitude calculated from pressure (requires sea-level calibration)
- **Notes:**
  - Suitable for environmental and weather monitoring.

- **Class:** `BME280Sensor`
  ```python
  {
    'temperature': <°C>,
    'humidity': <percent>,
    'pressure': <hPa>,
    'altitude': <m> | None,
    'status': 'OK' | 'MOCK' | 'ERROR',
    'timestamp': <iso8601>
  }
  ```

## Usage Example

Drivers are used by sensor adapters, not directly by application code. Example usage:

```python
from app.hardware.sensors.drivers.co2_sensor import ENS160_AHT21Sensor
sensor = ENS160_AHT21Sensor(unit_id="1")
data = sensor.read()
print(data)
```

---

## References
- [Adafruit ENS160](https://www.adafruit.com/product/5187)
- [Adafruit AHT21](https://www.adafruit.com/product/4566)
- [Adafruit DHT11](https://www.adafruit.com/product/386)
- [Adafruit TSL2591](https://www.adafruit.com/product/1980)
- [MQ2 Gas Sensor](https://components101.com/sensors/mq2-gas-sensor)
- [Generic Soil Moisture Sensor](https://www.adafruit.com/product/4026)
- [Adafruit BME280](https://www.adafruit.com/product/2652)

---

For more details, see the driver source files in `app/hardware/sensors/drivers/`.
