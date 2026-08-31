import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';
import '../../../core/constants/app_colors.dart';
import '../../../domain/state/trading_state_notifier.dart';

class ActionableBanner extends StatelessWidget {
  const ActionableBanner({super.key});

  @override
  Widget build(BuildContext context) {
    final stateNotifier = context.watch<TradingStateNotifier>();
    final state = stateNotifier.state;
    if (state == null) return const SizedBox.shrink();

    final sig = state.signal;
    if (!sig.actionable || (!sig.isBuy && !sig.isSell)) {
      return const SizedBox.shrink();
    }

    final isBuy = sig.isBuy;
    final r = sig.risk;
    final entry = r != null ? r.entry.toStringAsFixed(2) : state.price.toStringAsFixed(2);
    final sl = r != null ? r.stopLoss.toStringAsFixed(2) : '—';
    final tp1 = r != null ? r.takeProfit1.toStringAsFixed(2) : '—';

    final copyText = '🚨 ${state.pair} ${sig.direction}\nEntry: $entry\nSL: $sl\nTP1: $tp1\nConf: ${sig.confidence.toStringAsFixed(0)}%';

    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: isBuy ? AppColors.buyGreenBg : AppColors.sellRedBg,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(
          color: isBuy ? AppColors.buyGreen : AppColors.sellRed,
          width: 1.0,
        ),
      ),
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
            decoration: BoxDecoration(
              color: isBuy ? AppColors.buyGreen : AppColors.sellRed,
              borderRadius: BorderRadius.circular(4),
            ),
            child: Text(
              sig.direction,
              style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w900, color: Colors.white),
            ),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Entry @ $entry · SL: $sl · TP1: $tp1',
                  style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w700),
                ),
                Text(
                  'Confidence ${sig.confidence.toStringAsFixed(0)}% · Mode: ${state.mode.toUpperCase()}',
                  style: const TextStyle(fontSize: 9, color: Colors.grey),
                ),
              ],
            ),
          ),
          IconButton(
            icon: const Icon(Icons.copy_rounded, size: 18),
            onPressed: () {
              Clipboard.setData(ClipboardData(text: copyText));
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(content: Text('Signal copied to clipboard!'), duration: Duration(seconds: 1)),
              );
            },
            tooltip: 'Copy Signal',
          ),
        ],
      ),
    );
  }
}
