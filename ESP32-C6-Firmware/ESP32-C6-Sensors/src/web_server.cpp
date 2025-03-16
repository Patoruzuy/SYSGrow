#include "web_server.h"
#include "config.h"
#include <WiFi.h>
#include <WebServer.h>

WebServer server(WEB_SERVER_PORT);

void handleRoot() {
    server.send(200, "text/html", "<h1>ESP32-C6 Sensor Web UI</h1>");
}

void setupWebServer() {
    server.on("/", handleRoot);
    server.begin();
    Serial.println("Web Server Started...");
}

void webServerLoop() {
    server.handleClient();
}