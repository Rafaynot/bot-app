import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../../core/constants/app_colors.dart';
import '../../../domain/state/trading_state_notifier.dart';

class AppBottomNavbar extends StatelessWidget {
  final int currentIndex;
  final ValueChanged<int> onTap;

  const AppBottomNavbar({
    super.key,
    required this.currentIndex,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final stateNotifier = context.watch<TradingStateNotifier>();
    final sig = stateNotifier.state?.signal;
    final hasActiveSignal = (sig?.actionable ?? false) && ((sig?.isBuy ?? false) || (sig?.isSell ?? false));

    return BottomNavigationBar(
      currentIndex: currentIndex,
      onTap: onTap,
      selectedFontSize: 10,
      unselectedFontSize: 10,
      items: [
        const BottomNavigationBarItem(
          icon: Icon(Icons.candlestick_chart_outlined),
          activeIcon: Icon(Icons.candlestick_chart),
          label: 'Chart',
        ),
        BottomNavigationBarItem(
          icon: Stack(
            clipBehavior: Clip.none,
            children: [
              const Icon(Icons.bolt_outlined),
              if (hasActiveSignal)
                Positioned(
                  top: -2,
                  right: -4,
                  child: Container(
                    padding: const EdgeInsets.all(3),
                    decoration: const BoxDecoration(
                      color: AppColors.buyGreen,
                      shape: BoxShape.circle,
                    ),
                  ),
                ),
            ],
          ),
          activeIcon: const Icon(Icons.bolt),
          label: 'Signals',
        ),
        const BottomNavigationBarItem(
          icon: Icon(Icons.analytics_outlined),
          activeIcon: Icon(Icons.analytics),
          label: 'SMC / ICT',
        ),
        const BottomNavigationBarItem(
          icon: Icon(Icons.stacked_bar_chart),
          activeIcon: Icon(Icons.stacked_bar_chart),
          label: 'Depth',
        ),
        const BottomNavigationBarItem(
          icon: Icon(Icons.history_rounded),
          activeIcon: Icon(Icons.history),
          label: 'History',
        ),
      ],
    );
  }
}
