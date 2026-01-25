# Controlling Mars Hydro Lights via ESP32 & SYSGrow

This guide explains how to integrate **Mars Hydro (FC/FC-E Series)** grow lights with the SYSGrow ecosystem using an ESP32 and a PWM-to-Analog converter.

---

## 1. Hardware Requirements

| Component | Description |
| :--- | :--- |
| **ESP32** | C3, C6, or S3 (3.3V Logic) |
| **0-10V PWM Converter** | Module to convert 3.3V PWM to 10V Analog (e.g., LC-3.3V-10V) |
| **DC Power Supply** | 12V-24V DC to power the converter module |
| **RJ11/RJ12 Cable** | Standard telephone/data cable for the Mars Hydro dimming port |
| **Resistors/Optoc** | (Optional) If building a custom level-shifter circuit |

---

## 2. Wiring Diagram

The Mars Hydro dimming port uses an RJ11/RJ12 connector. The critical pins are typically the center ones:

### RJ11/RJ12 Pinout (Mars Hydro)
- **Pin 2 (Black/Green):** DIM- (Ground / Negative)
- **Pin 3 (Red/Yellow):** DIM+ (0-10V Positive Signal)

### Connection to ESP32
1. **Power:** Connect 12V VCC and GND to the Converter Module.
2. **Signal:** Connect ESP32 **GPIO (e.g., GPIO 18)** to the Converter **PWM Input**.
3. **Common Ground:** Ensure ESP32 GND is connected to the Converter's Signal GND.
4. **Light Output:** Connect Converter **VOUT** to RJ11 **Pin 3**, and Converter **GND** to RJ11 **Pin 2**.

---

## 3. ESP32 Firmware Implementation (C++)

Using the `ledc` library for precise PWM control.

```cpp
#include <Arduino.h>

const int DIM_PIN = 18;  // PWM Output Pin
const int freq = 1000;   // 1kHz Frequency
const int ledChannel = 0;
const int resolution = 8; // 8-bit resolution (0-255)

void setup() {
    ledcSetup(ledChannel, freq, resolution);
    ledcAttachPin(DIM_PIN, ledChannel);
}

// Function called when MQTT message received: {"brightness": 191}
void setLightIntensity(int brightness) {
    // brightness 0-255 matches 0-100%
    ledcWrite(ledChannel, brightness); 
}
```

---

## 4. MQTT Payload Format

The SYSGrow backend `MQTTActuatorAdapter` sends the following JSON payload to the light's command topic:

**Topic:** `unit/1/actuator/{id}/set`
**Payload:**
```json
{
  "state": "ON",
  "brightness": 128
}
```
*Note: `brightness` is calculated as `(percentage / 100) * 255`.*

---

## 5. Backend Configuration (Python)

To register the light in the SYSGrow system, use the following configuration in your `ActuatorManager`:

```python
manager.register_actuator(
    actuator_id=10,
    name="Mars Hydro FC-3000",
    actuator_type=ActuatorType.LIGHT,
    protocol=Protocol.MQTT,
    config={
        "mqtt_topic": "unit/1/light/dimmer",
        "min_value": 0,
        "max_value": 100,
        "power_watts": 300
    }
)
```

### PID Control logic
The `ControlLogic` will automatically compute the required intensity based on the `Lux` sensor feedback and update the `brightness` via MQTT.

---

## 6. Safety Notes
- **Never** connect 10V or 12V directly to ESP32 GPIO pins; it will destroy the chip.
- Ensure the Mars Hydro dimmer knob is set to **"EXT"** (External) mode for the ESP32 to take control.
- If the light flickers, increase the PWM frequency to 2kHz or 5kHz.
