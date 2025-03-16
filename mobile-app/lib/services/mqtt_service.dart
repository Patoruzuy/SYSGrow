import 'package:mqtt_client/mqtt_client.dart';
import 'package:mqtt_client/mqtt_server_client.dart';

class MQTTService {
  final String broker = "mqtt-broker.local";  // Auto-discovered MQTT broker
  final int port = 1883;
  final String clientId = "flutter_client";
  MqttServerClient? client;

  Future<void> connect() async {
    client = MqttServerClient(broker, clientId);
    client!.port = port;
    client!.onConnected = () => print("Connected to MQTT");
    client!.onDisconnected = () => print("Disconnected from MQTT");

    try {
      await client!.connect();
      print("MQTT Connected");
    } catch (e) {
      print("MQTT Connection Failed: $e");
    }
  }

  void sendRelayCommand(int pin, bool state) {
    final pubTopic = "zigbee2mqtt/ESP32-C6-Relay/$pin";
    final builder = MqttClientPayloadBuilder();
    builder.addString(state ? "ON" : "OFF");
    client!.publishMessage(pubTopic, MqttQos.atMostOnce, builder.payload!);
  }

  void disconnect() {
    client?.disconnect();
  }
}
