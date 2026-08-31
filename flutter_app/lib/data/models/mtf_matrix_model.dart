class MtfRowModel {
  final String timeframe;
  final String trend;
  final String structure;
  final double rsi;
  final String macd;
  final String smcZone;

  MtfRowModel({
    required this.timeframe,
    required this.trend,
    required this.structure,
    required this.rsi,
    required this.macd,
    required this.smcZone,
  });

  factory MtfRowModel.fromJson(Map<String, dynamic> json) {
    return MtfRowModel(
      timeframe: json['tf'] as String? ?? '—',
      trend: json['trend'] as String? ?? '—',
      structure: json['structure'] as String? ?? '—',
      rsi: (json['rsi'] as num?)?.toDouble() ?? 50.0,
      macd: json['macd'] as String? ?? '—',
      smcZone: json['smc_zone'] as String? ?? '—',
    );
  }
}
