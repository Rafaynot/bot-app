import 'package:shared_preferences/shared_preferences.dart';

class AppStorageKeys {
  static const String baseUrl = 'app_base_url';
  static const String isDarkMode = 'app_is_dark_mode';
  static const String soundAlertsEnabled = 'app_sound_alerts_enabled';
  static const String notificationsEnabled = 'app_notifications_enabled';
  static const String minConfidence = 'app_min_confidence';
  static const String maxRiskPercent = 'app_max_risk_percent';
  static const String selectedMode = 'app_selected_mode';
  static const String selectedTimeframe = 'app_selected_timeframe';
  static const String selectedChartView = 'app_selected_chart_view';
}

class AppStorageService {
  final SharedPreferences _prefs;

  AppStorageService(this._prefs);

  static Future<AppStorageService> init() async {
    final prefs = await SharedPreferences.getInstance();
    return AppStorageService(prefs);
  }

  String getString(String key, {String defaultValue = ''}) {
    return _prefs.getString(key) ?? defaultValue;
  }

  Future<bool> setString(String key, String value) async {
    return _prefs.setString(key, value);
  }

  bool getBool(String key, {bool defaultValue = false}) {
    return _prefs.getBool(key) ?? defaultValue;
  }

  Future<bool> setBool(String key, bool value) async {
    return _prefs.setBool(key, value);
  }

  double getDouble(String key, {double defaultValue = 0.0}) {
    return _prefs.getDouble(key) ?? defaultValue;
  }

  Future<bool> setDouble(String key, double value) async {
    return _prefs.setDouble(key, value);
  }

  int getInt(String key, {int defaultValue = 0}) {
    return _prefs.getInt(key) ?? defaultValue;
  }

  Future<bool> setInt(String key, int value) async {
    return _prefs.setInt(key, value);
  }

  Future<bool> remove(String key) async {
    return _prefs.remove(key);
  }

  Future<bool> clear() async {
    return _prefs.clear();
  }
}
