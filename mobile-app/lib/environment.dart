class EnvironmentConfig {
  static const String apiBaseUrl = String.fromEnvironment(
    'SYSGROW_API_BASE',
    defaultValue: 'http://10.0.2.2:8000',
  );
}
