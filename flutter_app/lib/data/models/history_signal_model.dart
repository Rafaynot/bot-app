class HistorySignalModel {
  final String time;
  final String mode;
  final String side;
  final double entry;
  final double sl;
  final double tp1;
  final double confidence;
  final String outcome;

  HistorySignalModel({
    required this.time,
    required this.mode,
    required this.side,
    required this.entry,
    required this.sl,
    required this.tp1,
    required this.confidence,
    required this.outcome,
  });

  bool get isWin => outcome.toUpperCase() == 'WIN';
  bool get isLoss => outcome.toUpperCase() == 'LOSS';
  bool get isPending => outcome.toUpperCase() == 'PENDING';

  factory HistorySignalModel.fromJson(Map<String, dynamic> json) {
    return HistorySignalModel(
      time: json['time'] as String? ?? '—',
      mode: json['mode'] as String? ?? 'SWING',
      side: json['side'] as String? ?? 'BUY',
      entry: (json['entry'] as num?)?.toDouble() ?? 0.0,
      sl: (json['sl'] as num?)?.toDouble() ?? 0.0,
      tp1: (json['tp1'] as num?)?.toDouble() ?? 0.0,
      confidence: (json['confidence'] as num?)?.toDouble() ?? 0.0,
      outcome: json['outcome'] as String? ?? 'PENDING',
    );
  }
}

class ModePerformanceModel {
  final double winRate;
  final int wins;
  final int losses;
  final int pending;

  ModePerformanceModel({
    required this.winRate,
    required this.wins,
    required this.losses,
    required this.pending,
  });

  factory ModePerformanceModel.fromJson(Map<String, dynamic> json) {
    return ModePerformanceModel(
      winRate: (json['winrate'] as num?)?.toDouble() ?? 0.0,
      wins: (json['wins'] as num?)?.toInt() ?? 0,
      losses: (json['losses'] as num?)?.toInt() ?? 0,
      pending: (json['pending'] as num?)?.toInt() ?? 0,
    );
  }
}
