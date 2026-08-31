/// Position sizing and dynamic risk calculator.
class RiskCalculator {
  RiskCalculator._();

  static double calculateLotSize({
    required double accountBalance,
    required double riskPercent,
    required double entryPrice,
    required double stopLossPrice,
    double contractSize = 100.0, // XAUUSD standard contract size: 100 oz
  }) {
    if (accountBalance <= 0 || riskPercent <= 0) return 0.01;
    final riskAmount = accountBalance * (riskPercent / 100.0);
    final stopLossDistance = (entryPrice - stopLossPrice).abs();
    if (stopLossDistance <= 0) return 0.01;

    final lotSize = riskAmount / (stopLossDistance * contractSize);
    return double.parse(lotSize.toStringAsFixed(2)).clamp(0.01, 50.0);
  }

  static double calculateRiskReward({
    required double entryPrice,
    required double stopLossPrice,
    required double takeProfitPrice,
  }) {
    final risk = (entryPrice - stopLossPrice).abs();
    final reward = (takeProfitPrice - entryPrice).abs();
    if (risk <= 0) return 0.0;
    return double.parse((reward / risk).toStringAsFixed(2));
  }
}
