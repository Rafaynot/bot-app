/// Confluence verification and weight calculation algorithm.
class ConfluenceCalculator {
  ConfluenceCalculator._();

  static Map<String, bool> evaluateConfluences(Map<String, dynamic> features) {
    return {
      'trend': features['trend_aligned'] == true || features['trend'] == 'BULLISH' || features['trend'] == 'BEARISH',
      'structure': features['structure_bos'] == true || features['structure_chob'] == true,
      'order_block': features['near_ob'] == true || features['ob_confluence'] == true,
      'fvg': features['fvg_confluence'] == true || features['fvg_retest'] == true,
      'liquidity': features['liquidity_sweep'] == true || features['sweep'] == true,
      'kill_zone': features['in_kill_zone'] == true || features['session_open'] == true,
      'price_action': features['candlestick_pattern'] == true || features['rejection'] == true,
      'news': features['news_safe'] == true || features['news'] == 'CLEAR',
    };
  }

  static double calculateConfluenceScore(Map<String, bool> confluences) {
    if (confluences.isEmpty) return 0.0;
    int passed = confluences.values.where((v) => v).length;
    return (passed / confluences.length) * 100.0;
  }
}
