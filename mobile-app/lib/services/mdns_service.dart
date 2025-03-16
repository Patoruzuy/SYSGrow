import 'package:flutter_mdns_plugin/flutter_mdns_plugin.dart';

class MDNSService {
  final FlutterMdnsPlugin _mdns = FlutterMdnsPlugin();

  void startDiscovery(Function(String, String) onDeviceFound) {
    _mdns.onDiscoveryStarted.listen((_) => print("Discovery started"));
    _mdns.onDiscoveryStopped.listen((_) => print("Discovery stopped"));

    _mdns.onServiceFound.listen((service) {
      print("Service Found: ${service.name}");
      _mdns.resolve(service.name, service.type);
    });

    _mdns.onServiceResolved.listen((service) {
      if (service.hostName.contains("esp32")) {
        String ip = service.addresses.first;
        onDeviceFound(service.name, ip);
      }
    });

    _mdns.startDiscovery("_http._tcp");
  }

  void stopDiscovery() {
    _mdns.stopDiscovery();
  }
}
