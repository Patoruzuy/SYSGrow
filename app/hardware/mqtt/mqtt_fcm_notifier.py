import json

import requests

from app.hardware.mqtt.client_factory import create_mqtt_client

# MQTT Configuration
MQTT_BROKER = "mqtt-broker.local"
MQTT_TOPIC = "zigbee2mqtt/ESP32-C6-Relay/battery_warning"

# Firebase Cloud Messaging (FCM) Configuration
FCM_SERVER_KEY = "YOUR_FIREBASE_SERVER_KEY"
FCM_DEVICE_TOKEN = "USER_DEVICE_FCM_TOKEN"

def send_firebase_notification(voltage):
    """Send a Firebase push notification for low battery."""
    url = "https://fcm.googleapis.com/fcm/send"
    headers = {
        "Content-Type": "application/json",
        "Authorization": "key=" + FCM_SERVER_KEY,
    }
    payload = {
        "to": FCM_DEVICE_TOKEN,
        "notification": {
            "title": "⚠️ Low Battery Alert",
            "body": f"ESP32-C6 battery is low: {voltage}V. Recharge soon!",
        },
    }
    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload), timeout=5)
        print(f"FCM Response: {response.text}")
    except requests.RequestException as e:
        # Log and continue; notification failure should not crash MQTT processing
        print(f"Failed to send FCM notification: {e}")

def on_message(client, userdata, message):
    """Handle incoming MQTT messages."""
    payload = json.loads(message.payload.decode())
    voltage = payload["voltage"]
    print(f"🔋 Low Battery Alert Received: {voltage}V")
    send_firebase_notification(voltage)

# Connect to MQTT Broker
client = create_mqtt_client()
client.on_message = on_message
client.connect(MQTT_BROKER, 1883, 60)
client.subscribe(MQTT_TOPIC)
client.loop_forever()
