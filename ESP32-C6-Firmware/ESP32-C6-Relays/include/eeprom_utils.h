#ifndef EEPROM_UTILS_H
#define EEPROM_UTILS_H

#define EEPROM_SIZE 128

void loadWiFiConfig(char* ssid, char* password);
void saveWiFiConfig(const char* ssid, const char* password);

#endif
