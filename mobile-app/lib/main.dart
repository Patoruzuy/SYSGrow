import 'package:flutter/material.dart';
import 'wifi_screen.dart';
import 'discover_devices.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'providers/relay_provider.dart';
import 'providers/connection_provider.dart';
import 'ui/screens/relay_screen.dart';

void main() {
  runApp(
    MultiProvider(
      providers: [
        ChangeNotifierProvider(create: (_) => RelayProvider()),
        ChangeNotifierProvider(create: (_) => ConnectionProvider()),
      ],
      child: MyApp(),
    ),
  );
    runApp(MaterialApp(
    home: WiFiScreen(),
    routes: {
      "/discover": (context) => DiscoverDevicesScreen(),
    },
  ));
}

class MyApp extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'ESP32 Relay Control',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        primarySwatch: Colors.blue,
      ),
      home: RelayScreen(),
    );
  }
}
