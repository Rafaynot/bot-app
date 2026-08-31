import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../../../core/constants/app_colors.dart';
import '../../../../core/theme/theme_provider.dart';
import '../../../../core/utils/formatters.dart';
import '../../../../domain/state/trading_state_notifier.dart';
import '../../../../data/models/history_signal_model.dart';

class HistoryTabView extends StatelessWidget {
  const HistoryTabView({super.key});

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
        child: Text('Loading Historical Signals…', style: TextStyle(color: textSec, fontSize: 12)),
      );
    }

    final perf = state.performance;
    final history = state.history;

    final swingWinrate = perf['swing']?.winRate ?? 0.0;
    final intraWinrate = perf['intraday']?.winRate ?? 0.0;
    final scalpWinrate = perf['scalp']?.winRate ?? 0.0;
    final predictWinrate = perf['predict']?.winRate ?? 0.0;

    return RefreshIndicator(
      onRefresh: () => stateNotifier.fetchLatestState(),
      color: AppColors.goldAccent,
      child: ListView(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        children: [
          // Win-rate Statistics Grid
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
                    Icon(Icons.military_tech_outlined, size: 16, color: AppColors.goldAccent),
                    SizedBox(width: 6),
                    Text('Performance & Verified Win Rates', style: TextStyle(fontSize: 12, fontWeight: FontWeight.w800)),
                  ],
                ),
                const SizedBox(height: 10),
                GridView.count(
                  shrinkWrap: true,
                  physics: const NeverScrollableScrollPhysics(),
                  crossAxisCount: 2,
                  childAspectRatio: 2.2,
                  crossAxisSpacing: 8,
                  mainAxisSpacing: 8,
                  children: [
                    _buildWinRateBox('Swing Mode', swingWinrate, perf['swing'], textColor, isDark),
                    _buildWinRateBox('Intraday Mode', intraWinrate, perf['intraday'], textColor, isDark),
                    _buildWinRateBox('Scalp Mode', scalpWinrate, perf['scalp'], textColor, isDark),
                    _buildWinRateBox('AI Predictions', predictWinrate, perf['predict'], textColor, isDark),
                  ],
                ),
              ],
            ),
          ),
          const SizedBox(height: 12),

          // Signals Track Record Table
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
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    const Text('Recent Signals Track Record', style: TextStyle(fontSize: 12, fontWeight: FontWeight.w800)),
                    InkWell(
                      onTap: () async {
                        final confirm = await showDialog<bool>(
                          context: context,
                          builder: (ctx) => AlertDialog(
                            title: const Text('Clear Track Record?'),
                            content: const Text('This will reset your local performance history and machine learner cache.'),
                            actions: [
                              TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
                              TextButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('Clear', style: TextStyle(color: AppColors.sellRed))),
                            ],
                          ),
                        );
                        if (confirm == true) {
                          stateNotifier.clearStatistics();
                        }
                      },
                      borderRadius: BorderRadius.circular(4),
                      child: Container(
                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                        decoration: BoxDecoration(
                          color: AppColors.sellRedBg,
                          borderRadius: BorderRadius.circular(4),
                          border: Border.all(color: AppColors.sellRed.withOpacity(0.5)),
                        ),
                        child: const Text('Clear Stats', style: TextStyle(fontSize: 10, fontWeight: FontWeight.w700, color: AppColors.sellRed)),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 10),

                if (history.isEmpty)
                  Padding(
                    padding: const EdgeInsets.all(16.0),
                    child: Center(child: Text('No recorded signals yet', style: TextStyle(color: textSec, fontSize: 11))),
                  )
                else
                  SingleChildScrollView(
                    scrollDirection: Axis.horizontal,
                    child: DataTable(
                      columnSpacing: 14,
                      horizontalMargin: 8,
                      headingRowHeight: 32,
                      dataRowHeight: 34,
                      columns: const [
                        DataColumn(label: Text('Time', style: TextStyle(fontSize: 10, fontWeight: FontWeight.bold))),
                        DataColumn(label: Text('Mode', style: TextStyle(fontSize: 10, fontWeight: FontWeight.bold))),
                        DataColumn(label: Text('Side', style: TextStyle(fontSize: 10, fontWeight: FontWeight.bold))),
                        DataColumn(label: Text('Entry', style: TextStyle(fontSize: 10, fontWeight: FontWeight.bold))),
                        DataColumn(label: Text('SL', style: TextStyle(fontSize: 10, fontWeight: FontWeight.bold))),
                        DataColumn(label: Text('TP1', style: TextStyle(fontSize: 10, fontWeight: FontWeight.bold))),
                        DataColumn(label: Text('Conf', style: TextStyle(fontSize: 10, fontWeight: FontWeight.bold))),
                        DataColumn(label: Text('Outcome', style: TextStyle(fontSize: 10, fontWeight: FontWeight.bold))),
                      ],
                      rows: history.map((s) {
                        final isBuy = s.side.toUpperCase().contains('BUY');
                        final isWin = s.isWin;
                        final isLoss = s.isLoss;

                        final outcomeCol = isWin
                            ? AppColors.buyGreen
                            : isLoss
                                ? AppColors.sellRed
                                : AppColors.goldAccent;

                        return DataRow(
                          cells: [
                            DataCell(Text(s.time, style: const TextStyle(fontSize: 9))),
                            DataCell(Text(s.mode.toUpperCase(), style: const TextStyle(fontSize: 9, fontWeight: FontWeight.w600))),
                            DataCell(Text(
                              s.side,
                              style: TextStyle(
                                fontSize: 9,
                                fontWeight: FontWeight.w800,
                                color: isBuy ? AppColors.buyGreen : AppColors.sellRed,
                              ),
                            )),
                            DataCell(Text(Formatters.formatPrice(s.entry), style: const TextStyle(fontSize: 9))),
                            DataCell(Text(Formatters.formatPrice(s.sl), style: const TextStyle(fontSize: 9, color: AppColors.sellRed))),
                            DataCell(Text(Formatters.formatPrice(s.tp1), style: const TextStyle(fontSize: 9, color: AppColors.buyGreen))),
                            DataCell(Text('${s.confidence.toStringAsFixed(0)}%', style: const TextStyle(fontSize: 9))),
                            DataCell(Container(
                              padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                              decoration: BoxDecoration(
                                color: outcomeCol.withOpacity(0.15),
                                borderRadius: BorderRadius.circular(3),
                              ),
                              child: Text(
                                s.outcome,
                                style: TextStyle(fontSize: 9, fontWeight: FontWeight.w800, color: outcomeCol),
                              ),
                            )),
                          ],
                        );
                      }).toList(),
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

  Widget _buildWinRateBox(String label, double winRate, ModePerformanceModel? perf, Color textColor, bool isDark) {
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
          const SizedBox(height: 2),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                '${winRate.toStringAsFixed(0)}%',
                style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w900, color: AppColors.buyGreen),
              ),
              if (perf != null)
                Text(
                  '${perf.wins}W / ${perf.losses}L',
                  style: const TextStyle(fontSize: 9, fontWeight: FontWeight.w600, color: Colors.grey),
                ),
            ],
          ),
        ],
      ),
    );
  }
}
