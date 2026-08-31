import 'package:flutter/material.dart';
import '../../services/storage/app_storage_service.dart';

class ThemeProvider extends ChangeNotifier {
  final AppStorageService _storageService;
  bool _isDarkMode = true;

  ThemeProvider(this._storageService) {
    _loadTheme();
  }

  bool get isDarkMode => _isDarkMode;
  ThemeMode get themeMode => _isDarkMode ? ThemeMode.dark : ThemeMode.light;

  void _loadTheme() {
    _isDarkMode = _storageService.getBool(AppStorageKeys.isDarkMode, defaultValue: true);
    notifyListeners();
  }

  Future<void> toggleTheme() async {
    _isDarkMode = !_isDarkMode;
    await _storageService.setBool(AppStorageKeys.isDarkMode, _isDarkMode);
    notifyListeners();
  }

  Future<void> setDarkMode(bool isDark) async {
    if (_isDarkMode == isDark) return;
    _isDarkMode = isDark;
    await _storageService.setBool(AppStorageKeys.isDarkMode, _isDarkMode);
    notifyListeners();
  }
}
