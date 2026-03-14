#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include "sensor_co.h"

#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64
#define OLED_RESET -1
Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET);

void setupOLED() {
    if (!display.begin(SSD1306_SWITCHCAPVCC, 0x3C)) {
        Serial.println("❌ OLED Display Failed!");
    }
    display.clearDisplay();
    display.setTextSize(1);
    display.setTextColor(WHITE);
    Serial.println("✅ OLED Initialized");
}

void updateOLED(float coLevel) {
    display.clearDisplay();
    display.setCursor(0, 10);
    display.print("CO Level: ");
    display.print(coLevel);
    display.println(" ppm");
    display.display();
}
