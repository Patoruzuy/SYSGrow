import 'package:flutter/material.dart';
import 'ui/screens/relay_screen.dart';
import 'ui/screens/settings_screen.dart';
import 'services/discover_devices.dart';
import 'services/wifi_screen.dart';

void main() {
  runApp(const MyApp());
}

class MyApp extends StatelessWidget {
  const MyApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'SYSGrow Control',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(primarySwatch: Colors.blue),
      initialRoute: '/relays',
      routes: {
        '/relays': (context) => RelayScreen(),
        '/settings': (context) => SettingsScreen(),
        '/wifi': (context) => WiFiScreen(),
        '/discover': (context) => DiscoverDevicesScreen(),
      },
    );
  }
}
