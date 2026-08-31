/// API Endpoints for communication with Python Web Server.
class ApiEndpoints {
  ApiEndpoints._();

  static const String defaultBaseUrl = 'http://127.0.0.1:8000';

  static const String state = '/api/state';
  static const String history = '/api/history';
  static const String setTimeframe = '/api/tf';
  static const String setView = '/api/view';
  static const String setMode = '/api/mode';
  static const String clearStats = '/api/clear';
  static const String updateSettings = '/api/settings';
}
