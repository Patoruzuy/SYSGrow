#include "web_server.h"
#include "logging.h"

AsyncWebServer server(80);
const char* username = "admin";
const char* password = "esp32pass";

void handleLogin(AsyncWebServerRequest *request) {
    if (!request->hasParam("user") || !request->hasParam("pass")) {
        request->send(401, "text/plain", "Unauthorized");
        return;
    }
    
    String user = request->getParam("user")->value();
    String pass = request->getParam("pass")->value();

    if (user == username && pass == password) {
        request->send(200, "text/html", "<h2>Login Successful</h2>");
    } else {
        request->send(401, "text/plain", "Invalid Credentials");
    }
}

void startWebServer() {
    server.on("/", HTTP_GET, [](AsyncWebServerRequest *request) {
        request->send(200, "text/html", "<h2>ESP32 Relay Control</h2><p>Use /login to authenticate.</p>");
    });

    server.on("/login", HTTP_POST, handleLogin);
    server.begin();
}
