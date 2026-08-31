import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../../../core/constants/app_colors.dart';
import '../../../../core/theme/theme_provider.dart';
import '../../../../core/utils/formatters.dart';
import '../../../../domain/state/trading_state_notifier.dart';
import '../../../../data/models/order_book_model.dart';

class OrderBookTabView extends StatelessWidget {
  const OrderBookTabView({super.key});

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
        child: Text('Connecting to Order Book Feed…', style: TextStyle(color: textSec, fontSize: 12)),
      );
    }

    final book = state.book;
    final bids = book.bids;
    final asks = book.asks;
    final maxVol = (book.totalBidVolume > book.totalAskVolume ? book.totalBidVolume : book.totalAskVolume).clamp(1.0, double.infinity);

    final bidDominance = (book.bidDominancePct / 100.0).clamp(0.05, 0.95);

    return RefreshIndicator(
      onRefresh: () => stateNotifier.fetchLatestState(),
      color: AppColors.goldAccent,
      child: ListView(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        children: [
          // Order Book Card
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
                    const Text('Live Order Book & Depth Ladder', style: TextStyle(fontSize: 12, fontWeight: FontWeight.w800)),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                      decoration: BoxDecoration(
                        color: isDark ? AppColors.darkSurface : AppColors.lightSurface,
                        borderRadius: BorderRadius.circular(4),
                      ),
                      child: Text('Spread: ${book.spread.toStringAsFixed(2)}', style: TextStyle(fontSize: 10, fontWeight: FontWeight.w700, color: textSec)),
                    ),
                  ],
                ),
                const SizedBox(height: 12),

                // Imbalance Dominance Meter
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text('Bids ${book.bidDominancePct.toStringAsFixed(1)}%', style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w700, color: AppColors.buyGreen)),
                    Text('Asks ${book.askDominancePct.toStringAsFixed(1)}%', style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w700, color: AppColors.sellRed)),
                  ],
                ),
                const SizedBox(height: 4),
                ClipRRect(
                  borderRadius: BorderRadius.circular(4),
                  child: Row(
                    children: [
                      Expanded(
                        flex: (bidDominance * 100).toInt(),
                        child: Container(height: 6, color: AppColors.buyGreen),
                      ),
                      Expanded(
                        flex: ((1.0 - bidDominance) * 100).toInt(),
                        child: Container(height: 6, color: AppColors.sellRed),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 14),

                // Order Ladder Column Headers
                Row(
                  children: [
                    Expanded(child: Text('Bid Vol', style: TextStyle(fontSize: 10, fontWeight: FontWeight.bold, color: textSec))),
                    Expanded(child: Text('Price', textAlign: TextAlign.center, style: TextStyle(fontSize: 10, fontWeight: FontWeight.bold, color: textSec))),
                    Expanded(child: Text('Ask Vol', textAlign: TextAlign.right, style: TextStyle(fontSize: 10, fontWeight: FontWeight.bold, color: textSec))),
                  ],
                ),
                const Divider(height: 12),

                // Ladder Rows
                ...List.generate(
                  bids.length > asks.length ? bids.length : asks.length,
                  (index) {
                    final OrderBookEntry? b = index < bids.length ? bids[index] : null;
                    final OrderBookEntry? a = index < asks.length ? asks[index] : null;

                    return Padding(
                      padding: const EdgeInsets.symmetric(vertical: 2.5),
                      child: Row(
                        children: [
                          // Bid side
                          Expanded(
                            child: Stack(
                              alignment: Alignment.centerLeft,
                              children: [
                                if (b != null)
                                  FractionallySizedBox(
                                    widthFactor: (b.volume / maxVol).clamp(0.0, 1.0),
                                    child: Container(height: 18, color: AppColors.buyGreen.withOpacity(0.18)),
                                  ),
                                Text(
                                  b != null ? Formatters.formatVolume(b.volume) : '—',
                                  style: const TextStyle(fontSize: 10, fontWeight: FontWeight.w600, color: AppColors.buyGreen),
                                ),
                              ],
                            ),
                          ),

                          // Mid Price
                          Expanded(
                            child: Text(
                              b != null ? Formatters.formatPrice(b.price) : (a != null ? Formatters.formatPrice(a.price) : '—'),
                              textAlign: TextAlign.center,
                              style: TextStyle(fontSize: 10, fontWeight: FontWeight.w700, color: textColor),
                            ),
                          ),

                          // Ask side
                          Expanded(
                            child: Stack(
                              alignment: Alignment.centerRight,
                              children: [
                                if (a != null)
                                  FractionallySizedBox(
                                    alignment: Alignment.centerRight,
                                    widthFactor: (a.volume / maxVol).clamp(0.0, 1.0),
                                    child: Container(height: 18, color: AppColors.sellRed.withOpacity(0.18)),
                                  ),
                                Text(
                                  a != null ? Formatters.formatVolume(a.volume) : '—',
                                  textAlign: TextAlign.right,
                                  style: const TextStyle(fontSize: 10, fontWeight: FontWeight.w600, color: AppColors.sellRed),
                                ),
                              ],
                            ),
                          ),
                        ],
                      ),
                    );
                  },
                ),
              ],
            ),
          ),
          const SizedBox(height: 16),
        ],
      ),
    );
  }
}
