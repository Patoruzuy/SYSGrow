import 'package:mqtt_client/mqtt_client.dart';
import 'package:mqtt_client/mqtt_server_client.dart';

class MQTTService {
  final String broker = "mqtt-broker.local";
  final int port = 1883;
  MqttServerClient? client;

  Future<void> connect() async {
    client = MqttServerClient(broker, "flutter_client");
    client!.port = port;
    client!.onConnected = () => print("Connected to MQTT");
    await client!.connect();
  }

  void sendRelayCommand(int pin, bool state) {
    final pubTopic = "zigbee2mqtt/ESP32-C6-Relay/$pin";
    final builder = MqttClientPayloadBuilder();
    builder.addString(state ? "ON" : "OFF");
    client!.publishMessage(pubTopic, MqttQos.atMostOnce, builder.payload!);
  }
}
