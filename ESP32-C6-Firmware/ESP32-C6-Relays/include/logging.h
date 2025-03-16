#ifndef LOGGING_H
#define LOGGING_H

#include <Arduino.h>

#define LOG_INFO(msg) Serial.println(String(" INFO: ") + msg)
#define LOG_WARN(msg) Serial.println(String(" WARNING: ") + msg)
#define LOG_ERROR(msg) Serial.println(String(" ERROR: ") + msg)

#endif
