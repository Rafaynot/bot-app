import 'dart:async';
import 'package:flutter/foundation.dart';
import '../../data/models/market_state_model.dart';
import '../../data/repositories/trading_repository.dart';
import '../../services/storage/app_storage_service.dart';
import '../../services/notifications/local_notification_service.dart';

class TradingStateNotifier extends ChangeNotifier {
  final TradingRepository _repository;
  final AppStorageService _storageService;
  final LocalNotificationService _notificationService;

  Timer? _pollTimer;
  MarketStateModel? _state;
  bool _isLoading = false;
  String? _errorMessage;
  bool _isConnected = false;

  String _currentTimeframe = 'M15';
  String _currentView = 'original';
  String _currentMode = 'swing';

  String? _lastNotifiedSignalKey;

  TradingStateNotifier(
    this._repository,
    this._storageService,
    this._notificationService,
  ) {
    _loadPersistedPreferences();
    startPolling();
  }

  MarketStateModel? get state => _state;
  bool get isLoading => _isLoading;
  String? get errorMessage => _errorMessage;
  bool get isConnected => _isConnected;

  String get currentTimeframe => _currentTimeframe;
  String get currentView => _currentView;
  String get currentMode => _currentMode;

  void _loadPersistedPreferences() {
    _currentTimeframe = _storageService.getString(AppStorageKeys.selectedTimeframe, defaultValue: 'M15');
    _currentView = _storageService.getString(AppStorageKeys.selectedChartView, defaultValue: 'original');
    _currentMode = _storageService.getString(AppStorageKeys.selectedMode, defaultValue: 'swing');
  }

  void startPolling({Duration interval = const Duration(seconds: 2)}) {
    _pollTimer?.cancel();
    fetchLatestState();
    _pollTimer = Timer.periodic(interval, (_) => fetchLatestState());
  }

  void stopPolling() {
    _pollTimer?.cancel();
  }

  Future<void> fetchLatestState() async {
    try {
      final newState = await _repository.getMarketState();
      _state = newState;
      _isConnected = true;
      _errorMessage = null;

      // Sync active timeframe & mode from server if they match
      if (newState.tf.isNotEmpty) _currentTimeframe = newState.tf;
      if (newState.mode.isNotEmpty) _currentMode = newState.mode.toLowerCase();

      _checkAndTriggerSignalNotification(newState);
      notifyListeners();
    } catch (e) {
      _isConnected = false;
      _errorMessage = e.toString();
      notifyListeners();
    }
  }

  void _checkAndTriggerSignalNotification(MarketStateModel state) {
    final sig = state.signal;
    final notificationsEnabled = _storageService.getBool(AppStorageKeys.notificationsEnabled, defaultValue: true);

    if (!notificationsEnabled) return;

    if (sig.actionable && (sig.isBuy || sig.isSell) && sig.confidence >= sig.threshold) {
      final key = '${sig.direction}_${state.price}_${sig.confidence}';
      if (_lastNotifiedSignalKey != key) {
        _lastNotifiedSignalKey = key;
        
        final r = sig.risk;
        final entryStr = r != null ? r.entry.toStringAsFixed(2) : state.price.toStringAsFixed(2);
        final slStr = r != null ? r.stopLoss.toStringAsFixed(2) : '—';
        final tpStr = r != null ? r.takeProfit1.toStringAsFixed(2) : '—';

        _notificationService.showSignalNotification(
          id: DateTime.now().millisecondsSinceEpoch ~/ 1000,
          title: '🚨 Actionable ${sig.direction} Signal (${sig.confidence.toStringAsFixed(0)}%)',
          body: 'Entry: $entryStr | SL: $slStr | TP1: $tpStr\nMode: ${state.mode.toUpperCase()}',
        );
      }
    }
  }

  Future<void> setTimeframe(String tf) async {
    _currentTimeframe = tf;
    await _storageService.setString(AppStorageKeys.selectedTimeframe, tf);
    notifyListeners();
    try {
      await _repository.changeTimeframe(tf);
      await fetchLatestState();
    } catch (e) {
      _errorMessage = e.toString();
      notifyListeners();
    }
  }

  Future<void> setChartView(String view) async {
    _currentView = view;
    await _storageService.setString(AppStorageKeys.selectedChartView, view);
    notifyListeners();
    try {
      await _repository.changeChartView(view);
      await fetchLatestState();
    } catch (e) {
      _errorMessage = e.toString();
      notifyListeners();
    }
  }

  Future<void> setTradingMode(String mode) async {
    _currentMode = mode.toLowerCase();
    await _storageService.setString(AppStorageKeys.selectedMode, _currentMode);
    notifyListeners();
    try {
      await _repository.changeTradingMode(_currentMode);
      await fetchLatestState();
    } catch (e) {
      _errorMessage = e.toString();
      notifyListeners();
    }
  }

  Future<void> clearStatistics() async {
    try {
      await _repository.clearStatistics();
      await fetchLatestState();
    } catch (e) {
      _errorMessage = e.toString();
      notifyListeners();
    }
  }

  Future<void> updateSettings({double? minConfidence, double? maxRiskPercent}) async {
    try {
      if (minConfidence != null) {
        await _storageService.setDouble(AppStorageKeys.minConfidence, minConfidence);
      }
      if (maxRiskPercent != null) {
        await _storageService.setDouble(AppStorageKeys.maxRiskPercent, maxRiskPercent);
      }
      await _repository.updateRiskSettings(
        minConfidence: minConfidence,
        maxRiskPercent: maxRiskPercent,
      );
      await fetchLatestState();
    } catch (e) {
      _errorMessage = e.toString();
      notifyListeners();
    }
  }

  @override
  void dispose() {
    _pollTimer?.cancel();
    super.dispose();
  }
}
