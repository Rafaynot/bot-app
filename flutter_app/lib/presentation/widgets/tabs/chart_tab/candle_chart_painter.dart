import 'dart:math' as math;
import 'package:flutter/material.dart';
import '../../../../core/constants/app_colors.dart';
import '../../../../data/models/candle_model.dart';

class CandleChartPainter extends CustomPainter {
  final List<CandleData> candles;
  final List<double> forecastY;
  final String? forecastColor;
  final Map<String, dynamic>? signalOverlay;
  final bool isDark;
  final int startIndex;
  final int visibleCount;
  final int? selectedIndex;
  final Offset? crosshair;

  CandleChartPainter({
    required this.candles,
    this.forecastY = const [],
    this.forecastColor,
    this.signalOverlay,
    required this.isDark,
    required this.startIndex,
    required this.visibleCount,
    this.selectedIndex,
    this.crosshair,
  });

  static const double _axisW = 58;
  static const double _timeH = 18;

  @override
  void paint(Canvas canvas, Size size) {
    if (candles.isEmpty || size.width <= 0 || size.height <= 0) return;

    final textColor = isDark ? AppColors.darkTextSecondary : AppColors.lightTextSecondary;
    final gridColor = (isDark ? AppColors.darkCardBorder : AppColors.lightCardBorder).withOpacity( 0.7);
    final bg = isDark ? AppColors.darkBg : AppColors.lightBg;

    canvas.drawRect(Offset.zero & size, Paint()..color = bg);

    final chartW = math.max(1.0, size.width - _axisW);
    final volH = size.height * 0.18;
    final priceH = math.max(1.0, size.height - volH - _timeH);
    final volTop = priceH;

    final end = math.min(candles.length, startIndex + visibleCount);
    final start = startIndex.clamp(0, math.max(0, candles.length - 1));
    if (start >= end) return;

    final window = candles.sublist(start, end);
    double minPrice = double.infinity;
    double maxPrice = -double.infinity;
    double maxVolume = 0;

    for (final c in window) {
      minPrice = math.min(minPrice, c.low);
      maxPrice = math.max(maxPrice, c.high);
      maxVolume = math.max(maxVolume, c.volume);
      for (final ma in [c.ma7, c.ma25, c.ma99]) {
        if (ma != null) {
          minPrice = math.min(minPrice, ma);
          maxPrice = math.max(maxPrice, ma);
        }
      }
    }

    for (final fy in forecastY) {
      if (fy > 0) {
        minPrice = math.min(minPrice, fy);
        maxPrice = math.max(maxPrice, fy);
      }
    }

    if (!minPrice.isFinite || !maxPrice.isFinite || minPrice == maxPrice) {
      minPrice = (minPrice.isFinite ? minPrice : 0) - 1;
      maxPrice = (maxPrice.isFinite ? maxPrice : 0) + 1;
    }

    final pad = (maxPrice - minPrice) * 0.06;
    minPrice -= pad;
    maxPrice += pad;
    final priceRange = maxPrice - minPrice;

    double priceY(double p) => priceH - ((p - minPrice) / priceRange) * priceH;

    final gridPaint = Paint()
      ..color = gridColor
      ..strokeWidth = 0.6;

    final axisStyle = TextStyle(color: textColor, fontSize: 9, fontWeight: FontWeight.w500);

    for (int i = 0; i <= 4; i++) {
      final y = (priceH / 4) * i;
      canvas.drawLine(Offset(0, y), Offset(chartW, y), gridPaint);
      final price = maxPrice - (priceRange / 4) * i;
      _drawText(canvas, price.toStringAsFixed(2), Offset(chartW + 4, y - 6), axisStyle);
    }

    canvas.drawLine(Offset(0, volTop), Offset(chartW, volTop), gridPaint);

    final n = window.length;
    final candleW = chartW / n;
    final bodyW = (candleW * 0.72).clamp(1.2, 14.0);

    final buy = AppColors.buyGreen;
    final sell = AppColors.sellRed;

    for (int i = 0; i < n; i++) {
      final c = window[i];
      final x = i * candleW + candleW / 2;
      final isBull = c.isBullish;
      final wick = Paint()
        ..color = isBull ? buy : sell
        ..strokeWidth = math.max(1.0, bodyW * 0.12)
        ..strokeCap = StrokeCap.round;
      canvas.drawLine(Offset(x, priceY(c.high)), Offset(x, priceY(c.low)), wick);

      final yOpen = priceY(c.open);
      final yClose = priceY(c.close);
      final top = math.min(yOpen, yClose);
      final h = math.max(1.2, (yOpen - yClose).abs());
      canvas.drawRRect(
        RRect.fromRectAndRadius(
          Rect.fromCenter(center: Offset(x, top + h / 2), width: bodyW, height: h),
          const Radius.circular(0.5),
        ),
        Paint()..color = isBull ? buy : sell,
      );

      if (maxVolume > 0) {
        final vh = (c.volume / maxVolume) * (volH - 4);
        canvas.drawRect(
          Rect.fromLTWH(x - bodyW / 2, size.height - _timeH - vh, bodyW, vh),
          Paint()..color = (isBull ? buy : sell).withOpacity( 0.38),
        );
      }
    }

    _drawMa(canvas, window, candleW, (v) => priceY(v), AppColors.ma7, 1.2);
    _drawMa(canvas, window, candleW, (v) => priceY(v), AppColors.ma25, 1.2, use: (c) => c.ma25);
    _drawMa(canvas, window, candleW, (v) => priceY(v), AppColors.ma99, 1.2, use: (c) => c.ma99);

    if (forecastY.isNotEmpty) {
      final paint = Paint()
        ..color = AppColors.goldAccent
        ..strokeWidth = 1.6
        ..style = PaintingStyle.stroke;
      final path = Path();
      bool moved = false;
      final startFc = math.max(0, candles.length - forecastY.length);
      for (int i = 0; i < forecastY.length; i++) {
        final absIdx = startFc + i;
        if (absIdx < start || absIdx >= end) continue;
        final x = (absIdx - start) * candleW + candleW / 2;
        final y = priceY(forecastY[i]);
        if (!moved) {
          path.moveTo(x, y);
          moved = true;
        } else {
          path.lineTo(x, y);
        }
      }
      if (moved) canvas.drawPath(path, paint);
    }

    if (signalOverlay != null && signalOverlay!['active'] == true) {
      void line(double? p, Color color, String label) {
        if (p == null) return;
        final y = priceY(p);
        canvas.drawLine(
          Offset(0, y),
          Offset(chartW, y),
          Paint()
            ..color = color.withOpacity( 0.85)
            ..strokeWidth = 1
            ..style = PaintingStyle.stroke,
        );
        _drawTag(canvas, label, Offset(4, y - 8), color);
      }

      line((signalOverlay!['entry'] as num?)?.toDouble(), AppColors.goldAccent, 'ENTRY');
      line((signalOverlay!['sl'] as num?)?.toDouble(), AppColors.sellRed, 'SL');
      line((signalOverlay!['tp1'] as num?)?.toDouble(), AppColors.buyGreen, 'TP1');
    }

    final last = candles.last;
    final lastY = priceY(last.close);
    if (lastY >= 0 && lastY <= priceH) {
      final lc = last.isBullish ? buy : sell;
      final dash = Paint()
        ..color = lc.withOpacity( 0.7)
        ..strokeWidth = 0.8;
      _dashedHLine(canvas, lastY, chartW, dash);
      _drawTag(
        canvas,
        last.close.toStringAsFixed(2),
        Offset(chartW + 2, lastY - 7),
        lc,
        fill: true,
      );
    }

    final step = math.max(1, (n / 5).floor());
    for (int i = 0; i < n; i += step) {
      final t = window[i].timestamp;
      final label = '${t.hour.toString().padLeft(2, '0')}:${t.minute.toString().padLeft(2, '0')}';
      _drawText(canvas, label, Offset(i * candleW, size.height - 14), axisStyle);
    }

    if (crosshair != null) {
      final cx = crosshair!.dx.clamp(0.0, chartW);
      final cy = crosshair!.dy.clamp(0.0, priceH);
      final chPaint = Paint()
        ..color = textColor.withOpacity( 0.55)
        ..strokeWidth = 0.8;
      canvas.drawLine(Offset(cx, 0), Offset(cx, priceH + volH), chPaint);
      canvas.drawLine(Offset(0, cy), Offset(chartW, cy), chPaint);

      final idx = ((cx / candleW).floor()).clamp(0, n - 1);
      final c = window[idx];
      final hoverPrice = maxPrice - (cy / priceH) * priceRange;
      _drawTag(canvas, hoverPrice.toStringAsFixed(2), Offset(chartW + 2, cy - 7), AppColors.goldAccent, fill: true);
      _drawTag(
        canvas,
        '${c.close.toStringAsFixed(1)}',
        Offset(cx - 18, priceH + volH - 16),
        isDark ? AppColors.darkTextPrimary : AppColors.lightTextPrimary,
        fill: true,
        bg: isDark ? AppColors.darkSurface : AppColors.lightSurface,
      );
    }
  }

  void _drawMa(
    Canvas canvas,
    List<CandleData> window,
    double candleW,
    double Function(double) priceY,
    Color color,
    double width, {
    double? Function(CandleData)? use,
  }) {
    final getter = use ?? (CandleData c) => c.ma7;
    final paint = Paint()
      ..color = color
      ..strokeWidth = width
      ..style = PaintingStyle.stroke
      ..strokeJoin = StrokeJoin.round;
    final path = Path();
    bool moved = false;
    for (int i = 0; i < window.length; i++) {
      final v = getter(window[i]);
      if (v == null) continue;
      final x = i * candleW + candleW / 2;
      final y = priceY(v);
      if (!moved) {
        path.moveTo(x, y);
        moved = true;
      } else {
        path.lineTo(x, y);
      }
    }
    if (moved) canvas.drawPath(path, paint);
  }

  void _dashedHLine(Canvas canvas, double y, double w, Paint paint) {
    const dash = 4.0;
    const gap = 3.0;
    double x = 0;
    while (x < w) {
      canvas.drawLine(Offset(x, y), Offset(math.min(x + dash, w), y), paint);
      x += dash + gap;
    }
  }

  void _drawTag(
    Canvas canvas,
    String text,
    Offset pos,
    Color color, {
    bool fill = false,
    Color? bg,
  }) {
    final tp = TextPainter(
      text: TextSpan(
        text: text,
        style: TextStyle(color: fill ? Colors.black : color, fontSize: 8, fontWeight: FontWeight.w700),
      ),
      textDirection: TextDirection.ltr,
    )..layout();
    final rect = Rect.fromLTWH(pos.dx, pos.dy, tp.width + 6, tp.height + 3);
    canvas.drawRRect(
      RRect.fromRectAndRadius(rect, const Radius.circular(2)),
      Paint()..color = bg ?? color,
    );
    tp.paint(canvas, Offset(pos.dx + 3, pos.dy + 1.5));
  }

  void _drawText(Canvas canvas, String text, Offset pos, TextStyle style) {
    final tp = TextPainter(
      text: TextSpan(text: text, style: style),
      textDirection: TextDirection.ltr,
    )..layout();
    tp.paint(canvas, pos);
  }

  @override
  bool shouldRepaint(covariant CandleChartPainter old) => true;
}
