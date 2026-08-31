import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../../../core/constants/app_colors.dart';
import '../../../../core/theme/theme_provider.dart';
import '../../../../core/utils/formatters.dart';
import '../../../../domain/state/trading_state_notifier.dart';

class AnalysisTabView extends StatelessWidget {
  const AnalysisTabView({super.key});

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
        child: Text('Loading SMC & ICT Confluences…', style: TextStyle(color: textSec, fontSize: 12)),
      );
    }

    final mtfList = state.analysis.mtf;
    final ict = state.analysis.ict;
    final smc = state.analysis.smc;

    return RefreshIndicator(
      onRefresh: () => stateNotifier.fetchLatestState(),
      color: AppColors.goldAccent,
      child: ListView(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        children: [
          // Top-Down Multi-Timeframe Matrix
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
                    Icon(Icons.table_chart_outlined, size: 16, color: AppColors.goldAccent),
                    SizedBox(width: 6),
                    Text('Top-Down Multi-Timeframe Bias', style: TextStyle(fontSize: 12, fontWeight: FontWeight.w800)),
                  ],
                ),
                const SizedBox(height: 10),
                SingleChildScrollView(
                  scrollDirection: Axis.horizontal,
                  child: DataTable(
                    columnSpacing: 16,
                    horizontalMargin: 8,
                    headingRowHeight: 32,
                    dataRowHeight: 34,
                    columns: const [
                      DataColumn(label: Text('TF', style: TextStyle(fontSize: 10, fontWeight: FontWeight.bold))),
                      DataColumn(label: Text('Trend', style: TextStyle(fontSize: 10, fontWeight: FontWeight.bold))),
                      DataColumn(label: Text('Structure', style: TextStyle(fontSize: 10, fontWeight: FontWeight.bold))),
                      DataColumn(label: Text('RSI 14', style: TextStyle(fontSize: 10, fontWeight: FontWeight.bold))),
                      DataColumn(label: Text('MACD', style: TextStyle(fontSize: 10, fontWeight: FontWeight.bold))),
                      DataColumn(label: Text('SMC Zone', style: TextStyle(fontSize: 10, fontWeight: FontWeight.bold))),
                    ],
                    rows: mtfList.map((row) {
                      final isBull = row.trend.toUpperCase().contains('BULL');
                      return DataRow(
                        cells: [
                          DataCell(Text(row.timeframe, style: const TextStyle(fontSize: 10, fontWeight: FontWeight.bold))),
                          DataCell(Text(
                            row.trend,
                            style: TextStyle(
                              fontSize: 10,
                              fontWeight: FontWeight.w700,
                              color: isBull ? AppColors.buyGreen : AppColors.sellRed,
                            ),
                          )),
                          DataCell(Text(row.structure, style: const TextStyle(fontSize: 10))),
                          DataCell(Text(row.rsi.toStringAsFixed(1), style: const TextStyle(fontSize: 10))),
                          DataCell(Text(row.macd, style: const TextStyle(fontSize: 10))),
                          DataCell(Text(row.smcZone, style: const TextStyle(fontSize: 10))),
                        ],
                      );
                    }).toList(),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 12),

          // ICT Session & Kill Zone Radar
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
                    Icon(Icons.radar_outlined, size: 16, color: AppColors.goldAccent),
                    SizedBox(width: 6),
                    Text('ICT Session & Kill Zone Radar', style: TextStyle(fontSize: 12, fontWeight: FontWeight.w800)),
                  ],
                ),
                const SizedBox(height: 10),
                GridView.count(
                  shrinkWrap: true,
                  physics: const NeverScrollableScrollPhysics(),
                  crossAxisCount: 2,
                  childAspectRatio: 2.3,
                  crossAxisSpacing: 8,
                  mainAxisSpacing: 8,
                  children: [
                    _buildInfoCard('Active Session', ict.session, textColor, isDark),
                    _buildInfoCard('Kill Zone Window', ict.killZone, ict.inKillZone ? AppColors.buyGreen : textColor, isDark),
                    _buildInfoCard('Asian Range High', Formatters.formatPrice(ict.asianHigh), textColor, isDark),
                    _buildInfoCard('Asian Range Low', Formatters.formatPrice(ict.asianLow), textColor, isDark),
                  ],
                ),
              ],
            ),
          ),
          const SizedBox(height: 12),

          // Smart Money Concepts Blocks
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
                    Icon(Icons.account_balance_outlined, size: 16, color: AppColors.goldAccent),
                    SizedBox(width: 6),
                    Text('SMC Liquidity & Institutional Zones', style: TextStyle(fontSize: 12, fontWeight: FontWeight.w800)),
                  ],
                ),
                const SizedBox(height: 10),
                GridView.count(
                  shrinkWrap: true,
                  physics: const NeverScrollableScrollPhysics(),
                  crossAxisCount: 2,
                  childAspectRatio: 2.3,
                  crossAxisSpacing: 8,
                  mainAxisSpacing: 8,
                  children: [
                    _buildInfoCard('Nearest Bullish OB', Formatters.formatPrice(smc.nearestBullishOb), AppColors.buyGreen, isDark),
                    _buildInfoCard('Nearest Bearish OB', Formatters.formatPrice(smc.nearestBearishOb), AppColors.sellRed, isDark),
                    _buildInfoCard('Active Fair Value Gap', smc.activeFvg ?? 'None active', textColor, isDark),
                    _buildInfoCard('Liquidity Pool Sweeps', smc.liquidityPools ?? 'Protected', textColor, isDark),
                  ],
                ),
              ],
            ),
          ),
          const SizedBox(height: 16),
        ],
      ),
    );
  }

  Widget _buildInfoCard(String label, String value, Color valColor, bool isDark) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
      decoration: BoxDecoration(
        color: isDark ? AppColors.darkSurface : AppColors.lightSurface,
        borderRadius: BorderRadius.circular(8),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Text(label, style: const TextStyle(fontSize: 9, color: Colors.grey)),
          const SizedBox(height: 3),
          Text(
            value,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: TextStyle(fontSize: 11, fontWeight: FontWeight.w800, color: valColor),
          ),
        ],
      ),
    );
  }
}
