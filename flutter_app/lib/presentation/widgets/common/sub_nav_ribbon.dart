import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../../core/constants/app_colors.dart';
import '../../../core/theme/theme_provider.dart';
import '../../../domain/state/trading_state_notifier.dart';

class SubNavRibbon extends StatelessWidget {
  const SubNavRibbon({super.key});

  @override
  Widget build(BuildContext context) {
    final stateNotifier = context.watch<TradingStateNotifier>();
    final themeProvider = context.watch<ThemeProvider>();
    final isDark = themeProvider.isDarkMode;

    final currentTf = stateNotifier.currentTimeframe;
    final currentView = stateNotifier.currentView;

    final timeframes = ['M1', 'M5', 'M15', 'H1', 'H4', 'D1', 'W1'];
    final views = [
      {'id': 'original', 'label': 'Candles'},
      {'id': 'tradingview', 'label': 'TradingView'},
      {'id': 'depth', 'label': 'Depth'},
      {'id': 'predict', 'label': 'AI Path'},
    ];

    final bgCol = isDark ? AppColors.darkCard : AppColors.lightCard;
    final borderCol = isDark ? AppColors.darkCardBorder : AppColors.lightCardBorder;
    final textSec = isDark ? AppColors.darkTextSecondary : AppColors.lightTextSecondary;

    return Container(
      decoration: BoxDecoration(
        color: bgCol,
        border: Border(bottom: BorderSide(color: borderCol, width: 0.8)),
      ),
      child: Column(
        children: [
          // Timeframe Row
          SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
            child: Row(
              children: timeframes.map((tf) {
                final isSelected = currentTf.toUpperCase() == tf.toUpperCase();
                return Padding(
                  padding: const EdgeInsets.only(right: 6),
                  child: InkWell(
                    onTap: () => stateNotifier.setTimeframe(tf),
                    borderRadius: BorderRadius.circular(6),
                    child: Container(
                      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                      decoration: BoxDecoration(
                        color: isSelected ? AppColors.goldAccent : Colors.transparent,
                        borderRadius: BorderRadius.circular(6),
                      ),
                      child: Text(
                        tf,
                        style: TextStyle(
                          fontSize: 11,
                          fontWeight: isSelected ? FontWeight.w800 : FontWeight.w600,
                          color: isSelected ? Colors.black : textSec,
                        ),
                      ),
                    ),
                  ),
                );
              }).toList(),
            ),
          ),

          // Chart View Selector Row
          SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            padding: const EdgeInsets.fromLTRB(12, 0, 12, 6),
            child: Row(
              children: views.map((v) {
                final isSelected = currentView == v['id'];
                return Padding(
                  padding: const EdgeInsets.only(right: 6),
                  child: InkWell(
                    onTap: () => stateNotifier.setChartView(v['id']!),
                    borderRadius: BorderRadius.circular(12),
                    child: Container(
                      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 3),
                      decoration: BoxDecoration(
                        color: isSelected ? (isDark ? AppColors.darkSurface : AppColors.lightSurface) : Colors.transparent,
                        borderRadius: BorderRadius.circular(12),
                        border: Border.all(
                          color: isSelected ? AppColors.goldAccent : borderCol,
                          width: 0.8,
                        ),
                      ),
                      child: Text(
                        v['label']!,
                        style: TextStyle(
                          fontSize: 10,
                          fontWeight: isSelected ? FontWeight.w700 : FontWeight.w500,
                          color: isSelected ? AppColors.goldAccent : textSec,
                        ),
                      ),
                    ),
                  ),
                );
              }).toList(),
            ),
          ),
        ],
      ),
    );
  }
}
