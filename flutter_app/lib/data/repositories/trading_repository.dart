import '../datasources/trading_api_client.dart';
import '../models/market_state_model.dart';
import '../models/history_signal_model.dart';

class TradingRepository {
  final TradingApiClient _apiClient;

  TradingRepository(this._apiClient);

  Future<MarketStateModel> getMarketState() async {
    final data = await _apiClient.fetchState();
    return MarketStateModel.fromJson(data);
  }

  Future<List<HistorySignalModel>> getHistory() async {
    final rawList = await _apiClient.fetchHistory();
    return rawList
        .map((e) => HistorySignalModel.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  Future<bool> changeTimeframe(String tf) => _apiClient.setTimeframe(tf);
  Future<bool> changeChartView(String view) => _apiClient.setChartView(view);
  Future<bool> changeTradingMode(String mode) => _apiClient.setTradingMode(mode);
  Future<bool> clearStatistics() => _apiClient.clearStats();
  Future<bool> updateRiskSettings({double? minConfidence, double? maxRiskPercent}) =>
      _apiClient.updateSettings(
        minConfidence: minConfidence,
        maxRiskPercent: maxRiskPercent,
      );
}
