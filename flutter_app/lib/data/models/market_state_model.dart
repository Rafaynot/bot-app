import 'candle_model.dart';
import 'signal_model.dart';
import 'order_book_model.dart';
import 'ict_smc_model.dart';
import 'history_signal_model.dart';

class MarketStatsModel {
  final double last;
  final double change;
  final double pct;
  final double high;
  final double low;
  final double volBase;
  final double volQuote;

  MarketStatsModel({
    required this.last,
    required this.change,
    required this.pct,
    required this.high,
    required this.low,
    required this.volBase,
    required this.volQuote,
  });

  factory MarketStatsModel.fromJson(Map<String, dynamic> json) {
    return MarketStatsModel(
      last: (json['last'] as num?)?.toDouble() ?? 0.0,
      change: (json['change'] as num?)?.toDouble() ?? 0.0,
      pct: (json['pct'] as num?)?.toDouble() ?? 0.0,
      high: (json['high'] as num?)?.toDouble() ?? 0.0,
      low: (json['low'] as num?)?.toDouble() ?? 0.0,
      volBase: (json['vol_base'] as num?)?.toDouble() ?? 0.0,
      volQuote: (json['vol_quote'] as num?)?.toDouble() ?? 0.0,
    );
  }
}

class MarketStateModel {
  final bool ok;
  final String status;
  final String pair;
  final String source;
  final String mode;
  final String tf;
  final double price;
  final double spread;
  final String clock;
  final MarketStatsModel stats;
  final SignalModel signal;
  final ConfluenceAnalysisModel analysis;
  final OrderBookModel book;
  final ChartPayload chart;
  final Map<String, ModePerformanceModel> performance;
  final List<HistorySignalModel> history;
  final Map<String, dynamic>? learner;

  MarketStateModel({
    required this.ok,
    required this.status,
    required this.pair,
    required this.source,
    required this.mode,
    required this.tf,
    required this.price,
    required this.spread,
    required this.clock,
    required this.stats,
    required this.signal,
    required this.analysis,
    required this.book,
    required this.chart,
    required this.performance,
    required this.history,
    this.learner,
  });

  factory MarketStateModel.fromJson(Map<String, dynamic> json) {
    final rawPerf = json['performance'] as Map<String, dynamic>? ?? {};
    final Map<String, ModePerformanceModel> perfMap = {};
    rawPerf.forEach((k, v) {
      if (v is Map<String, dynamic>) {
        perfMap[k] = ModePerformanceModel.fromJson(v);
      }
    });

    final rawHistory = json['history'] as List<dynamic>? ?? [];
    final historyList = rawHistory
        .map((e) => HistorySignalModel.fromJson(e as Map<String, dynamic>))
        .toList();

    return MarketStateModel(
      ok: json['ok'] as bool? ?? false,
      status: json['status'] as String? ?? 'offline',
      pair: json['pair'] as String? ?? 'XAU/USD',
      source: json['source'] as String? ?? 'MT5',
      mode: json['mode'] as String? ?? 'SWING',
      tf: json['tf'] as String? ?? 'M15',
      price: (json['price'] as num?)?.toDouble() ?? 0.0,
      spread: (json['spread'] as num?)?.toDouble() ?? 0.0,
      clock: json['clock'] as String? ?? '—',
      stats: MarketStatsModel.fromJson((json['stats'] as Map<String, dynamic>?) ?? {}),
      signal: SignalModel.fromJson((json['signal'] as Map<String, dynamic>?) ?? {}),
      analysis: ConfluenceAnalysisModel.fromJson((json['analysis'] as Map<String, dynamic>?) ?? {}),
      book: OrderBookModel.fromJson((json['book'] as Map<String, dynamic>?) ?? {}),
      chart: ChartPayload.fromJson((json['chart'] as Map<String, dynamic>?) ?? {}),
      performance: perfMap,
      history: historyList,
      learner: json['learner'] as Map<String, dynamic>?,
    );
  }
}
