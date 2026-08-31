import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../../core/constants/app_colors.dart';
import '../../../core/theme/theme_provider.dart';
import '../../../core/utils/formatters.dart';
import '../../../domain/state/trading_state_notifier.dart';

class CustomAppBar extends StatelessWidget implements PreferredSizeWidget {
  const CustomAppBar({super.key});

  @override
  Size get preferredSize => const Size.fromHeight(52.0);

  @override
  Widget build(BuildContext context) {
    final stateNotifier = context.watch<TradingStateNotifier>();
    final themeProvider = context.watch<ThemeProvider>();
    final isDark = themeProvider.isDarkMode;
    final state = stateNotifier.state;

    final isConnected = stateNotifier.isConnected;
    final price = state?.price;
    final change = state?.stats.change;
    final pct = state?.stats.pct;
    final isBullish = (change ?? 0.0) >= 0;

    return AppBar(
      titleSpacing: 0,
      leading: Builder(
        builder: (ctx) => IconButton(
          icon: const Icon(Icons.menu_rounded),
          onPressed: () => Scaffold.of(ctx).openDrawer(),
        ),
      ),
      title: Row(
        children: [
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Row(
                children: [
                  Text(
                    state?.pair ?? 'XAU/USD',
                    style: TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.w800,
                      color: isDark ? AppColors.darkTextPrimary : AppColors.lightTextPrimary,
                    ),
                  ),
                  const SizedBox(width: 6),
                  Container(
                    width: 7,
                    height: 7,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      color: isConnected ? AppColors.buyGreen : AppColors.sellRed,
                    ),
                  ),
                ],
              ),
              Text(
                isConnected ? (state?.source ?? 'MT5 LIVE') : 'Connecting…',
                style: TextStyle(
                  fontSize: 10,
                  fontWeight: FontWeight.w500,
                  color: isDark ? AppColors.darkTextSecondary : AppColors.lightTextSecondary,
                ),
              ),
            ],
          ),
          const Spacer(),
          if (price != null)
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
              decoration: BoxDecoration(
                color: isBullish ? AppColors.buyGreenBg : AppColors.sellRedBg,
                borderRadius: BorderRadius.circular(8),
                border: Border.all(
                  color: isBullish ? AppColors.buyGreen.withOpacity(0.3) : AppColors.sellRed.withOpacity(0.3),
                  width: 0.8,
                ),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  Text(
                    Formatters.formatPrice(price),
                    style: TextStyle(
                      fontSize: 13,
                      fontWeight: FontWeight.w800,
                      color: isBullish ? AppColors.buyGreen : AppColors.sellRed,
                    ),
                  ),
                  Text(
                    Formatters.formatChange(change, pct),
                    style: TextStyle(
                      fontSize: 9,
                      fontWeight: FontWeight.w600,
                      color: isBullish ? AppColors.buyGreen : AppColors.sellRed,
                    ),
                  ),
                ],
              ),
            ),
        ],
      ),
      actions: [
        IconButton(
          icon: Icon(
            isDark ? Icons.light_mode_outlined : Icons.dark_mode_outlined,
            size: 20,
          ),
          onPressed: () => themeProvider.toggleTheme(),
          tooltip: 'Toggle Theme',
        ),
        IconButton(
          icon: const Icon(Icons.refresh_rounded, size: 20),
          onPressed: () => stateNotifier.fetchLatestState(),
          tooltip: 'Refresh',
        ),
        const SizedBox(width: 4),
      ],
    );
  }
}
