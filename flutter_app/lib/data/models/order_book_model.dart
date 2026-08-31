class OrderBookEntry {
  final double price;
  final double volume;
  final double depth;

  OrderBookEntry({
    required this.price,
    required this.volume,
    required this.depth,
  });

  factory OrderBookEntry.fromList(List<dynamic> list) {
    return OrderBookEntry(
      price: (list[0] as num).toDouble(),
      volume: (list[1] as num).toDouble(),
      depth: list.length > 2 ? (list[2] as num).toDouble() : 0.0,
    );
  }
}

class OrderBookModel {
  final List<OrderBookEntry> bids;
  final List<OrderBookEntry> asks;
  final double totalBidVolume;
  final double totalAskVolume;
  final double bidDominancePct;
  final double askDominancePct;
  final double spread;

  OrderBookModel({
    required this.bids,
    required this.asks,
    required this.totalBidVolume,
    required this.totalAskVolume,
    required this.bidDominancePct,
    required this.askDominancePct,
    required this.spread,
  });

  factory OrderBookModel.fromJson(Map<String, dynamic> json) {
    final rawBids = json['bids'] as List<dynamic>? ?? [];
    final rawAsks = json['asks'] as List<dynamic>? ?? [];

    final bids = rawBids.map((e) => OrderBookEntry.fromList(e as List<dynamic>)).toList();
    final asks = rawAsks.map((e) => OrderBookEntry.fromList(e as List<dynamic>)).toList();

    final totalBid = (json['total_bid'] as num?)?.toDouble() ?? 0.0;
    final totalAsk = (json['total_ask'] as num?)?.toDouble() ?? 0.0;
    final total = totalBid + totalAsk;

    final bidDominance = total > 0 ? (totalBid / total) * 100.0 : 50.0;
    final askDominance = total > 0 ? (totalAsk / total) * 100.0 : 50.0;
    final spread = (json['spread'] as num?)?.toDouble() ?? 0.0;

    return OrderBookModel(
      bids: bids,
      asks: asks,
      totalBidVolume: totalBid,
      totalAskVolume: totalAsk,
      bidDominancePct: bidDominance,
      askDominancePct: askDominance,
      spread: spread,
    );
  }
}
