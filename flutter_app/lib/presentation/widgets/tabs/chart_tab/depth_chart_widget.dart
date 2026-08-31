import 'package:flutter/material.dart';
import '../../../../core/constants/app_colors.dart';
import '../../../../data/models/order_book_model.dart';

class DepthChartWidget extends StatelessWidget {
  final OrderBookModel book;
  final bool isDark;

  const DepthChartWidget({
    super.key,
    required this.book,
    required this.isDark,
  });

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        return CustomPaint(
          size: Size(constraints.maxWidth, constraints.maxHeight),
          painter: _DepthChartPainter(book: book, isDark: isDark),
        );
      },
    );
  }
}

class _DepthChartPainter extends CustomPainter {
  final OrderBookModel book;
  final bool isDark;

  _DepthChartPainter({required this.book, required this.isDark});

  @override
  void paint(Canvas canvas, Size size) {
    final bids = book.bids;
    final asks = book.asks;
    if (bids.isEmpty && asks.isEmpty) return;

    final textColor = isDark ? AppColors.darkTextSecondary : AppColors.lightTextSecondary;
    final halfWidth = size.width / 2;
    double maxDepth = 1;
    for (final b in bids) {
      if (b.depth > maxDepth) maxDepth = b.depth;
    }
    for (final a in asks) {
      if (a.depth > maxDepth) maxDepth = a.depth;
    }

    if (bids.isNotEmpty) {
      final bidPath = Path()..moveTo(halfWidth, size.height);
      for (int i = 0; i < bids.length; i++) {
        final x = halfWidth - ((i + 1) / bids.length) * halfWidth;
        final y = size.height - (bids[i].depth / maxDepth) * (size.height * 0.88);
        bidPath.lineTo(x, y);
      }
      bidPath.lineTo(0, size.height);
      bidPath.close();
      canvas.drawPath(bidPath, Paint()..color = AppColors.buyGreen.withOpacity(0.22));
      canvas.drawPath(
        bidPath,
        Paint()
          ..color = AppColors.buyGreen
          ..style = PaintingStyle.stroke
          ..strokeWidth = 1.4,
      );
    }

    if (asks.isNotEmpty) {
      final askPath = Path()..moveTo(halfWidth, size.height);
      for (int i = 0; i < asks.length; i++) {
        final x = halfWidth + ((i + 1) / asks.length) * halfWidth;
        final y = size.height - (asks[i].depth / maxDepth) * (size.height * 0.88);
        askPath.lineTo(x, y);
      }
      askPath.lineTo(size.width, size.height);
      askPath.close();
      canvas.drawPath(askPath, Paint()..color = AppColors.sellRed.withOpacity(0.22));
      canvas.drawPath(
        askPath,
        Paint()
          ..color = AppColors.sellRed
          ..style = PaintingStyle.stroke
          ..strokeWidth = 1.4,
      );
    }

    final mid = Paint()
      ..color = AppColors.goldAccent.withOpacity(0.7)
      ..strokeWidth = 1;
    canvas.drawLine(Offset(halfWidth, 8), Offset(halfWidth, size.height), mid);

    final tp = TextPainter(
      text: TextSpan(
        text: 'Spread ${book.spread.toStringAsFixed(2)}',
        style: TextStyle(color: textColor, fontSize: 10, fontWeight: FontWeight.w600),
      ),
      textDirection: TextDirection.ltr,
    )..layout();
    tp.paint(canvas, Offset((size.width - tp.width) / 2, 10));
  }

  @override
  bool shouldRepaint(covariant _DepthChartPainter oldDelegate) => true;
}
