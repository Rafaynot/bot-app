import 'package:intl/intl.dart';

class Formatters {
  Formatters._();

  static final NumberFormat _priceFormat = NumberFormat('#,##0.00', 'en_US');
  static final NumberFormat _lotsFormat = NumberFormat('0.00', 'en_US');
  static final NumberFormat _volFormat = NumberFormat('#,##0', 'en_US');
  static final NumberFormat _pctFormat = NumberFormat('+0.00;-0.00', 'en_US');

  static String formatPrice(double? price) {
    if (price == null || price == 0) return '—';
    return _priceFormat.format(price);
  }

  static String formatChange(double? change, double? pct) {
    if (change == null || pct == null) return '—';
    final sign = change >= 0 ? '+' : '';
    return '$sign${_priceFormat.format(change)} (${_pctFormat.format(pct)}%)';
  }

  static String formatPercent(double? pct) {
    if (pct == null) return '0%';
    return '${pct.toStringAsFixed(0)}%';
  }

  static String formatLots(double? lots) {
    if (lots == null || lots == 0) return '—';
    return _lotsFormat.format(lots);
  }

  static String formatVolume(double? vol) {
    if (vol == null) return '—';
    if (vol >= 1000000) {
      return '${(vol / 1000000).toStringAsFixed(1)}M';
    } else if (vol >= 1000) {
      return '${(vol / 1000).toStringAsFixed(1)}K';
    }
    return _volFormat.format(vol);
  }
}
