import 'package:flutter/material.dart';
import '../../../../core/constants/app_colors.dart';

class ConfluenceChecklist extends StatelessWidget {
  final Map<String, dynamic> features;
  final bool isDark;

  const ConfluenceChecklist({
    super.key,
    required this.features,
    required this.isDark,
  });

  @override
  Widget build(BuildContext context) {
    final items = [
      {'key': 'trend', 'label': 'Trend EMA200', 'pass': features['trend_aligned'] == true || features['trend'] == 'BULLISH'},
      {'key': 'structure', 'label': 'Structure BOS', 'pass': features['structure_bos'] == true},
      {'key': 'ob', 'label': 'Order Block', 'pass': features['near_ob'] == true},
      {'key': 'fvg', 'label': 'Fair Value Gap', 'pass': features['fvg_confluence'] == true},
      {'key': 'liq', 'label': 'Liquidity Sweep', 'pass': features['liquidity_sweep'] == true},
      {'key': 'kz', 'label': 'Kill Zone', 'pass': features['in_kill_zone'] == true},
      {'key': 'candle', 'label': 'Price Action', 'pass': features['candlestick_pattern'] == true},
      {'key': 'news', 'label': 'Forex News Filter', 'pass': features['news_safe'] == true || features['news'] == 'CLEAR'},
    ];

    final cardBg = isDark ? AppColors.darkSurface : AppColors.lightSurface;
    final borderCol = isDark ? AppColors.darkCardBorder : AppColors.lightCardBorder;
    final textColor = isDark ? AppColors.darkTextPrimary : AppColors.lightTextPrimary;

    return GridView.builder(
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
        crossAxisCount: 2,
        childAspectRatio: 3.2,
        crossAxisSpacing: 8,
        mainAxisSpacing: 8,
      ),
      itemCount: items.length,
      itemBuilder: (ctx, idx) {
        final it = items[idx];
        final pass = it['pass'] as bool;
        return Container(
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
          decoration: BoxDecoration(
            color: cardBg,
            borderRadius: BorderRadius.circular(6),
            border: Border.all(color: borderCol, width: 0.6),
          ),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(it['label'] as String, style: TextStyle(fontSize: 11, color: textColor)),
              Icon(
                pass ? Icons.check_circle_rounded : Icons.radio_button_unchecked_rounded,
                size: 16,
                color: pass ? AppColors.buyGreen : Colors.grey.withOpacity(0.5),
              ),
            ],
          ),
        );
      },
    );
  }
}
