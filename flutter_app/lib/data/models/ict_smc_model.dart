class IctDataModel {
  final String session;
  final String killZone;
  final double? asianHigh;
  final double? asianLow;
  final bool inKillZone;

  IctDataModel({
    required this.session,
    required this.killZone,
    this.asianHigh,
    this.asianLow,
    required this.inKillZone,
  });

  factory IctDataModel.fromJson(Map<String, dynamic> json) {
    return IctDataModel(
      session: json['session'] as String? ?? '—',
      killZone: json['kill_zone'] as String? ?? '—',
      asianHigh: (json['asia_high'] as num?)?.toDouble(),
      asianLow: (json['asia_low'] as num?)?.toDouble(),
      inKillZone: json['in_kz'] as bool? ?? false,
    );
  }
}

class SmcDataModel {
  final double? nearestBullishOb;
  final double? nearestBearishOb;
  final String? activeFvg;
  final String? liquidityPools;

  SmcDataModel({
    this.nearestBullishOb,
    this.nearestBearishOb,
    this.activeFvg,
    this.liquidityPools,
  });

  factory SmcDataModel.fromJson(Map<String, dynamic> json) {
    return SmcDataModel(
      nearestBullishOb: (json['bull_ob'] as num?)?.toDouble(),
      nearestBearishOb: (json['bear_ob'] as num?)?.toDouble(),
      activeFvg: json['fvg'] as String?,
      liquidityPools: json['pools'] as String?,
    );
  }
}

class ConfluenceAnalysisModel {
  final List<MtfRowModel> mtf;
  final IctDataModel ict;
  final SmcDataModel smc;

  ConfluenceAnalysisModel({
    required this.mtf,
    required this.ict,
    required this.smc,
  });

  factory ConfluenceAnalysisModel.fromJson(Map<String, dynamic> json) {
    final rawMtf = json['mtf'] as List<dynamic>? ?? [];
    final mtfList = rawMtf.map((e) => MtfRowModel.fromJson(e as Map<String, dynamic>)).toList();
    final ict = IctDataModel.fromJson((json['ict'] as Map<String, dynamic>?) ?? {});
    final smc = SmcDataModel.fromJson((json['smc'] as Map<String, dynamic>?) ?? {});

    return ConfluenceAnalysisModel(
      mtf: mtfList,
      ict: ict,
      smc: smc,
    );
  }
}
