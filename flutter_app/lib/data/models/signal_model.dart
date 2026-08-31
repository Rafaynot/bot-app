class RiskModel {
  final double entry;
  final double stopLoss;
  final double takeProfit1;
  final double takeProfit2;
  final double takeProfit3;
  final double riskReward;
  final double lotSize;
  final double riskPercent;

  RiskModel({
    required this.entry,
    required this.stopLoss,
    required this.takeProfit1,
    required this.takeProfit2,
    required this.takeProfit3,
    required this.riskReward,
    required this.lotSize,
    required this.riskPercent,
  });

  factory RiskModel.fromJson(Map<String, dynamic> json) {
    return RiskModel(
      entry: (json['entry'] as num?)?.toDouble() ?? 0.0,
      stopLoss: (json['sl'] as num?)?.toDouble() ?? 0.0,
      takeProfit1: (json['tp1'] as num?)?.toDouble() ?? 0.0,
      takeProfit2: (json['tp2'] as num?)?.toDouble() ?? 0.0,
      takeProfit3: (json['tp3'] as num?)?.toDouble() ?? 0.0,
      riskReward: (json['rr'] as num?)?.toDouble() ?? 0.0,
      lotSize: (json['lots'] as num?)?.toDouble() ?? 0.0,
      riskPercent: (json['risk_pct'] as num?)?.toDouble() ?? 1.0,
    );
  }
}

class SignalModel {
  final String label;
  final String direction;
  final double confidence;
  final double threshold;
  final bool actionable;
  final String trend;
  final String structure;
  final String session;
  final String news;
  final double atr;
  final Map<String, dynamic> features;
  final RiskModel? risk;
  final List<String> lines;

  SignalModel({
    required this.label,
    required this.direction,
    required this.confidence,
    required this.threshold,
    required this.actionable,
    required this.trend,
    required this.structure,
    required this.session,
    required this.news,
    required this.atr,
    required this.features,
    this.risk,
    required this.lines,
  });

  bool get isBuy => direction.toUpperCase().contains('BUY');
  bool get isSell => direction.toUpperCase().contains('SELL');

  factory SignalModel.fromJson(Map<String, dynamic> json) {
    return SignalModel(
      label: json['label'] as String? ?? 'NO TRADE',
      direction: json['direction'] as String? ?? 'HOLD',
      confidence: (json['confidence'] as num?)?.toDouble() ?? 0.0,
      threshold: (json['threshold'] as num?)?.toDouble() ?? 85.0,
      actionable: json['actionable'] as bool? ?? false,
      trend: json['trend'] as String? ?? '—',
      structure: json['structure'] as String? ?? '—',
      session: json['session'] as String? ?? '—',
      news: json['news'] as String? ?? '—',
      atr: (json['atr'] as num?)?.toDouble() ?? 0.0,
      features: (json['features'] as Map<String, dynamic>?) ?? {},
      risk: json['risk'] != null ? RiskModel.fromJson(json['risk'] as Map<String, dynamic>) : null,
      lines: (json['lines'] as List<dynamic>? ?? []).map((e) => e.toString()).toList(),
    );
  }
}
