import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../../../core/constants/app_colors.dart';
import '../../../../core/theme/theme_provider.dart';
import '../../../../core/utils/formatters.dart';
import '../../../../domain/state/trading_state_notifier.dart';
import 'confluence_checklist.dart';

class SignalsTabView extends StatelessWidget {
  const SignalsTabView({super.key});

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
        child: Text('Connecting to Signal Engine…', style: TextStyle(color: textSec, fontSize: 12)),
      );
    }

    final sig = state.signal;
    final isBuy = sig.isBuy;
    final isSell = sig.isSell;
    final r = sig.risk;

    final badgeColor = isBuy
        ? AppColors.buyGreen
        : isSell
            ? AppColors.sellRed
            : textSec;

    final confPct = (sig.confidence / 100.0).clamp(0.0, 1.0);
    final reqPct = (sig.threshold / 100.0).clamp(0.0, 1.0);

    return RefreshIndicator(
      onRefresh: () => stateNotifier.fetchLatestState(),
      color: AppColors.goldAccent,
      child: ListView(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        children: [
          // Hero Signal Card
          Container(
            padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(
              color: cardBg,
              borderRadius: BorderRadius.circular(10),
              border: Border.all(color: borderCol, width: 0.8),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Row(
                      children: [
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                          decoration: BoxDecoration(
                            color: badgeColor.withOpacity(0.15),
                            borderRadius: BorderRadius.circular(6),
                            border: Border.all(color: badgeColor.withOpacity(0.4)),
                          ),
                          child: Text(
                            sig.label,
                            style: TextStyle(fontSize: 14, fontWeight: FontWeight.w900, color: badgeColor),
                          ),
                        ),
                        const SizedBox(width: 8),
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                          decoration: BoxDecoration(
                            color: isDark ? AppColors.darkSurface : AppColors.lightSurface,
                            borderRadius: BorderRadius.circular(4),
                          ),
                          child: Text(
                            state.mode.toUpperCase(),
                            style: TextStyle(fontSize: 10, fontWeight: FontWeight.w700, color: textColor),
                          ),
                        ),
                      ],
                    ),
                    Column(
                      crossAxisAlignment: CrossAxisAlignment.end,
                      children: [
                        Text(
                          'Confidence ${sig.confidence.toStringAsFixed(0)}%',
                          style: TextStyle(fontSize: 13, fontWeight: FontWeight.w800, color: textColor),
                        ),
                        Text(
                          'Need ≥ ${sig.threshold.toStringAsFixed(0)}%',
                          style: TextStyle(fontSize: 10, color: textSec),
                        ),
                      ],
                    ),
                  ],
                ),
                const SizedBox(height: 14),

                // Confidence Gauge Track with threshold pin
                LayoutBuilder(
                  builder: (ctx, constraints) {
                    final width = constraints.maxWidth;
                    return Stack(
                      clipBehavior: Clip.none,
                      children: [
                        Container(
                          height: 8,
                          width: width,
                          decoration: BoxDecoration(
                            color: (isDark ? Colors.white : Colors.black).withOpacity(0.08),
                            borderRadius: BorderRadius.circular(4),
                          ),
                        ),
                        Container(
                          height: 8,
                          width: width * confPct,
                          decoration: BoxDecoration(
                            color: sig.confidence >= sig.threshold ? AppColors.buyGreen : AppColors.goldAccent,
                            borderRadius: BorderRadius.circular(4),
                          ),
                        ),
                        Positioned(
                          left: width * reqPct - 1,
                          top: -3,
                          child: Container(
                            width: 2,
                            height: 14,
                            color: Colors.redAccent,
                          ),
                        ),
                      ],
                    );
                  },
                ),
                const SizedBox(height: 16),

                // Trade Setup Grid (Entry, SL, TP1-3, R:R, Lots, ATR)
                GridView.count(
                  shrinkWrap: true,
                  physics: const NeverScrollableScrollPhysics(),
                  crossAxisCount: 4,
                  childAspectRatio: 1.5,
                  crossAxisSpacing: 6,
                  mainAxisSpacing: 6,
                  children: [
                    _buildPlanBox('Entry', r != null ? Formatters.formatPrice(r.entry) : Formatters.formatPrice(state.price), textColor, isDark),
                    _buildPlanBox('Stop Loss', r != null ? Formatters.formatPrice(r.stopLoss) : '—', AppColors.sellRed, isDark),
                    _buildPlanBox('TP1', r != null ? Formatters.formatPrice(r.takeProfit1) : '—', AppColors.buyGreen, isDark),
                    _buildPlanBox('TP2', r != null ? Formatters.formatPrice(r.takeProfit2) : '—', AppColors.buyGreen, isDark),
                    _buildPlanBox('TP3', r != null ? Formatters.formatPrice(r.takeProfit3) : '—', AppColors.buyGreen, isDark),
                    _buildPlanBox('R : R', r != null ? '1 : ${r.riskReward.toStringAsFixed(1)}' : '—', AppColors.goldAccent, isDark),
                    _buildPlanBox('Lots (1%)', r != null ? Formatters.formatLots(r.lotSize) : '—', textColor, isDark),
                    _buildPlanBox('ATR (14)', sig.atr.toStringAsFixed(2), textColor, isDark),
                  ],
                ),
              ],
            ),
          ),
          const SizedBox(height: 12),

          // Confluence Verification Card
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: cardBg,
              borderRadius: BorderRadius.circular(10),
              border: Border.all(color: borderCol, width: 0.8),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: const [
                    Icon(Icons.verified_outlined, size: 16, color: AppColors.goldAccent),
                    SizedBox(width: 6),
                    Text('Confluence Verification Checklist', style: TextStyle(fontSize: 12, fontWeight: FontWeight.w800)),
                  ],
                ),
                const SizedBox(height: 10),
                ConfluenceChecklist(features: sig.features, isDark: isDark),
              ],
            ),
          ),
          const SizedBox(height: 12),

          // Reasoning Log Card
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: cardBg,
              borderRadius: BorderRadius.circular(10),
              border: Border.all(color: borderCol, width: 0.8),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text('Engine Output & Decision Log', style: TextStyle(fontSize: 12, fontWeight: FontWeight.w800)),
                const SizedBox(height: 8),
                Container(
                  width: double.infinity,
                  padding: const EdgeInsets.all(10),
                  decoration: BoxDecoration(
                    color: isDark ? AppColors.darkSurface : AppColors.lightSurface,
                    borderRadius: BorderRadius.circular(6),
                  ),
                  child: Text(
                    sig.lines.isNotEmpty ? sig.lines.join('\n') : 'Market analysis cycle running normally.',
                    style: TextStyle(
                      fontFamily: 'monospace',
                      fontSize: 10,
                      color: textColor,
                      height: 1.4,
                    ),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 16),
        ],
      ),
    );
  }

  Widget _buildPlanBox(String label, String value, Color valColor, bool isDark) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 4),
      decoration: BoxDecoration(
        color: isDark ? AppColors.darkSurface : AppColors.lightSurface,
        borderRadius: BorderRadius.circular(6),
      ),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label, style: const TextStyle(fontSize: 8, color: Colors.grey)),
          const SizedBox(height: 2),
          Text(
            value,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: TextStyle(fontSize: 10, fontWeight: FontWeight.w800, color: valColor),
          ),
        ],
      ),
    );
  }
}
