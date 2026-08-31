import 'dart:math' as math;
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../../../core/constants/app_colors.dart';
import '../../../../core/theme/theme_provider.dart';
import '../../../../core/utils/formatters.dart';
import '../../../../domain/state/trading_state_notifier.dart';
import 'candle_chart_painter.dart';
import 'depth_chart_widget.dart';

class ChartTabView extends StatefulWidget {
  const ChartTabView({super.key});

  @override
  State<ChartTabView> createState() => _ChartTabViewState();
}

class _ChartTabViewState extends State<ChartTabView> {
  double _scale = 1.0;
  double _baseScale = 1.0;
  double _pan = 0;
  Offset? _crosshair;

  @override
  Widget build(BuildContext context) {
    final stateNotifier = context.watch<TradingStateNotifier>();
    final themeProvider = context.watch<ThemeProvider>();
    final isDark = themeProvider.isDarkMode;
    final state = stateNotifier.state;

    final cardBg = isDark ? AppColors.darkCard : AppColors.lightCard;
    final borderCol = isDark ? AppColors.darkCardBorder : AppColors.lightCardBorder;
    final textColor = isDark ? AppColors.darkTextPrimary : AppColors.lightTextPrimary;
    final textSec = isDark ? AppColors.darkTextSecondary : AppColors.lightTextSecondary;

    if (state == null) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const CircularProgressIndicator(color: AppColors.goldAccent, strokeWidth: 2),
            const SizedBox(height: 12),
            Text('Connecting to Live Market Feed…', style: TextStyle(color: textSec, fontSize: 12)),
          ],
        ),
      );
    }

    final stats = state.stats;
    final candles = state.chart.candles;
    final isDepthView = stateNotifier.currentView == 'depth';
    final last = candles.isNotEmpty ? candles.last : null;
    final isBull = last == null ? true : last.isBullish;

    final count = candles.length;
    final visible = math.max(20, (80 / _scale).round()).clamp(12, math.max(12, count));
    final maxStart = math.max(0, count - visible);
    final start = (maxStart - _pan.round()).clamp(0, maxStart);

    return ColoredBox(
      color: isDark ? AppColors.darkBg : AppColors.lightBg,
      child: Column(
        children: [
          Container(
            padding: const EdgeInsets.fromLTRB(12, 8, 12, 6),
            color: cardBg,
            child: Row(
              children: [
                _stat('24h High', Formatters.formatPrice(stats.high), textColor, textSec),
                _stat('24h Low', Formatters.formatPrice(stats.low), textColor, textSec),
                _stat('Spread', state.spread.toStringAsFixed(1), textColor, textSec),
                _stat('24h Vol', Formatters.formatVolume(stats.volBase), textColor, textSec),
              ],
            ),
          ),
          Container(height: 0.8, color: borderCol),
          Padding(
            padding: const EdgeInsets.fromLTRB(12, 6, 12, 4),
            child: Row(
              children: [
                Expanded(
                  child: Text(
                    last == null
                        ? 'O —  H —  L —  C —'
                        : 'O ${last.open.toStringAsFixed(1)}  H ${last.high.toStringAsFixed(1)}  L ${last.low.toStringAsFixed(1)}  C ${last.close.toStringAsFixed(1)}',
                    style: TextStyle(
                      fontSize: 10,
                      fontWeight: FontWeight.w600,
                      color: isBull ? AppColors.buyGreen : AppColors.sellRed,
                    ),
                  ),
                ),
                _ma('MA7', AppColors.ma7),
                const SizedBox(width: 6),
                _ma('MA25', AppColors.ma25),
                const SizedBox(width: 6),
                _ma('MA99', AppColors.ma99),
              ],
            ),
          ),
          Expanded(
            child: Container(
              color: isDark ? AppColors.darkBg : AppColors.lightBg,
              child: isDepthView
                  ? DepthChartWidget(book: state.book, isDark: isDark)
                  : LayoutBuilder(
                      builder: (context, constraints) {
                        return GestureDetector(
                          onScaleStart: (_) => _baseScale = _scale,
                          onScaleUpdate: (d) {
                            setState(() {
                              _scale = (_baseScale * d.scale).clamp(0.6, 6.0);
                              _pan += d.focalPointDelta.dx / 8;
                              _crosshair = d.pointerCount == 1 ? d.localFocalPoint : null;
                            });
                          },
                          onTapDown: (d) => setState(() => _crosshair = d.localPosition),
                          onTapUp: (_) => setState(() => _crosshair = null),
                          onDoubleTap: () => setState(() {
                            _scale = 1;
                            _pan = 0;
                            _crosshair = null;
                          }),
                          child: CustomPaint(
                            size: Size(constraints.maxWidth, constraints.maxHeight),
                            painter: CandleChartPainter(
                              candles: candles,
                              forecastY: state.chart.forecastY,
                              forecastColor: state.chart.forecastColor,
                              signalOverlay: state.chart.signalOverlay,
                              isDark: isDark,
                              startIndex: start,
                              visibleCount: visible,
                              crosshair: _crosshair,
                            ),
                          ),
                        );
                      },
                    ),
            ),
          ),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
            decoration: BoxDecoration(
              color: cardBg,
              border: Border(top: BorderSide(color: borderCol, width: 0.8)),
            ),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceAround,
              children: [
                _chip('Trend', state.signal.trend, textColor, textSec),
                _chip('Structure', state.signal.structure, textColor, textSec),
                _chip('Session', state.signal.session, textColor, textSec),
                _chip('News', state.signal.news, textColor, textSec),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _stat(String label, String value, Color textCol, Color secCol) {
    return Expanded(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label, style: TextStyle(fontSize: 9, color: secCol)),
          const SizedBox(height: 2),
          Text(value, style: TextStyle(fontSize: 11, fontWeight: FontWeight.w700, color: textCol)),
        ],
      ),
    );
  }

  Widget _ma(String label, Color color) {
    return Row(
      children: [
        Container(width: 8, height: 2, color: color),
        const SizedBox(width: 3),
        Text(label, style: TextStyle(fontSize: 9, fontWeight: FontWeight.w700, color: color)),
      ],
    );
  }

  Widget _chip(String label, String value, Color textCol, Color secCol) {
    return Column(
      children: [
        Text(label, style: TextStyle(fontSize: 9, color: secCol)),
        Text(value, style: TextStyle(fontSize: 10, fontWeight: FontWeight.w700, color: textCol)),
      ],
    );
  }
}
