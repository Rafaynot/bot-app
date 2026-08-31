class CandleData {
  final DateTime timestamp;
  final double open;
  final double high;
  final double low;
  final double close;
  final double volume;
  final double? ma7;
  final double? ma25;
  final double? ma99;
  final double? ema20;
  final double? ema50;
  final double? ema200;

  CandleData({
    required this.timestamp,
    required this.open,
    required this.high,
    required this.low,
    required this.close,
    required this.volume,
    this.ma7,
    this.ma25,
    this.ma99,
    this.ema20,
    this.ema50,
    this.ema200,
  });

  bool get isBullish => close >= open;
}

class ChartPayload {
  final String mode;
  final String tickformat;
  final List<CandleData> candles;
  final List<String> forecastX;
  final List<double> forecastY;
  final String? forecastColor;
  final Map<String, dynamic>? signalOverlay;

  ChartPayload({
    required this.mode,
    required this.tickformat,
    required this.candles,
    this.forecastX = const [],
    this.forecastY = const [],
    this.forecastColor,
    this.signalOverlay,
  });

  factory ChartPayload.fromJson(Map<String, dynamic> json) {
    final mode = json['mode'] as String? ?? 'original';
    final tickformat = json['tickformat'] as String? ?? '%H:%M';

    final ohlc = json['ohlc'] as Map<String, dynamic>?;
    if (ohlc == null) {
      return ChartPayload(mode: mode, tickformat: tickformat, candles: []);
    }

    final xs = (ohlc['x'] as List<dynamic>? ?? []).map((e) => e.toString()).toList();
    final opens = (ohlc['open'] as List<dynamic>? ?? []).map((e) => (e as num).toDouble()).toList();
    final highs = (ohlc['high'] as List<dynamic>? ?? []).map((e) => (e as num).toDouble()).toList();
    final lows = (ohlc['low'] as List<dynamic>? ?? []).map((e) => (e as num).toDouble()).toList();
    final closes = (ohlc['close'] as List<dynamic>? ?? []).map((e) => (e as num).toDouble()).toList();
    
    final volObj = json['vol'] as Map<String, dynamic>?;
    final vols = (volObj?['y'] as List<dynamic>? ?? []).map((e) => (e as num).toDouble()).toList();

    final ma7List = (json['ma7']?['y'] as List<dynamic>? ?? []).map((e) => e == null ? null : (e as num).toDouble()).toList();
    final ma25List = (json['ma25']?['y'] as List<dynamic>? ?? []).map((e) => e == null ? null : (e as num).toDouble()).toList();
    final ma99List = (json['ma99']?['y'] as List<dynamic>? ?? []).map((e) => e == null ? null : (e as num).toDouble()).toList();

    final List<CandleData> candles = [];
    for (int i = 0; i < xs.length; i++) {
      DateTime dt;
      try {
        dt = DateTime.parse(xs[i]);
      } catch (_) {
        dt = DateTime.now();
      }

      candles.add(CandleData(
        timestamp: dt,
        open: i < opens.length ? opens[i] : 0.0,
        high: i < highs.length ? highs[i] : 0.0,
        low: i < lows.length ? lows[i] : 0.0,
        close: i < closes.length ? closes[i] : 0.0,
        volume: i < vols.length ? vols[i] : 0.0,
        ma7: i < ma7List.length ? ma7List[i] : null,
        ma25: i < ma25List.length ? ma25List[i] : null,
        ma99: i < ma99List.length ? ma99List[i] : null,
      ));
    }

    final fc = json['forecast'] as Map<String, dynamic>?;
    final fcX = (fc?['path_x'] as List<dynamic>? ?? []).map((e) => e.toString()).toList();
    final fcY = (fc?['path_y'] as List<dynamic>? ?? []).map((e) => (e as num).toDouble()).toList();

    return ChartPayload(
      mode: mode,
      tickformat: tickformat,
      candles: candles,
      forecastX: fcX,
      forecastY: fcY,
      forecastColor: fc?['color'] as String?,
      signalOverlay: json['signal'] as Map<String, dynamic>?,
    );
  }
}
