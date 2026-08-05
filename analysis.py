"""
Price action patterns, support/resistance, and top-down multi-timeframe analysis.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

import pandas as pd

from config import CONFIG, TimeFrame
from data import MarketSnapshot
from ict import ICTResult, analyze_ict
from indicators import IndicatorBundle, compute_indicators, ema_trend_bias, fibonacci_levels
from smc import SMCResult, analyze_smc
from utils import TrendBias, almost_equal


class CandlePattern(str, Enum):
    PIN_BAR = "Pin Bar"
    ENGULFING = "Engulfing"
    DOJI = "Doji"
    INSIDE_BAR = "Inside Bar"
    OUTSIDE_BAR = "Outside Bar"
    MORNING_STAR = "Morning Star"
    EVENING_STAR = "Evening Star"
    HAMMER = "Hammer"
    SHOOTING_STAR = "Shooting Star"
    TWEEZER_TOP = "Tweezer Top"
    TWEEZER_BOTTOM = "Tweezer Bottom"


@dataclass
class PatternHit:
    pattern: CandlePattern
    bullish: bool
    index: int
    time: pd.Timestamp
    strength: float = 1.0


@dataclass
class SRLevel:
    price: float
    kind: str  # swing_high, swing_low, daily, weekly, monthly, psychological
    strength: float = 1.0
    timeframe: str = ""


@dataclass
class TimeframeAnalysis:
    timeframe: TimeFrame
    indicators: IndicatorBundle
    smc: SMCResult
    ict: ICTResult | None
    patterns: list[PatternHit]
    sr_levels: list[SRLevel]
    fib: dict[str, float]
    ema_bias: str
    trend: TrendBias


@dataclass
class TopDownAnalysis:
    symbol: str
    price: float
    spread: float
    frames: dict[TimeFrame, TimeframeAnalysis] = field(default_factory=dict)
    higher_tf_bias: TrendBias = TrendBias.NEUTRAL
    aligned_bullish: bool = False
    aligned_bearish: bool = False
    daily_levels: list[SRLevel] = field(default_factory=list)
    weekly_levels: list[SRLevel] = field(default_factory=list)
    monthly_levels: list[SRLevel] = field(default_factory=list)
    psychological: list[SRLevel] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Candle patterns
# ---------------------------------------------------------------------------

def _body(o: float, c: float) -> float:
    return abs(c - o)


def _range(h: float, l: float) -> float:
    return max(h - l, 1e-12)


def detect_patterns(df: pd.DataFrame, lookback: int = 5) -> list[PatternHit]:
    hits: list[PatternHit] = []
    if len(df) < 5:
        return hits
    start = max(2, len(df) - lookback - 2)
    for i in range(start, len(df)):
        o, h, l, c = map(float, df.iloc[i][["open", "high", "low", "close"]])
        po, ph, pl, pc = map(float, df.iloc[i - 1][["open", "high", "low", "close"]])
        body = _body(o, c)
        rng = _range(h, l)
        upper = h - max(o, c)
        lower = min(o, c) - l
        t = df.index[i]
        bullish_candle = c > o

        # Doji
        if body / rng < 0.1:
            hits.append(PatternHit(CandlePattern.DOJI, bullish_candle, i, t, 0.6))

        # Pin bar / hammer / shooting star
        if lower > 2 * body and upper < body and bullish_candle:
            hits.append(PatternHit(CandlePattern.HAMMER, True, i, t))
            hits.append(PatternHit(CandlePattern.PIN_BAR, True, i, t))
        if upper > 2 * body and lower < body and not bullish_candle:
            hits.append(PatternHit(CandlePattern.SHOOTING_STAR, False, i, t))
            hits.append(PatternHit(CandlePattern.PIN_BAR, False, i, t))

        # Engulfing
        if c > o and pc < po and c >= po and o <= pc and body > _body(po, pc):
            hits.append(PatternHit(CandlePattern.ENGULFING, True, i, t))
        if c < o and pc > po and c <= po and o >= pc and body > _body(po, pc):
            hits.append(PatternHit(CandlePattern.ENGULFING, False, i, t))

        # Inside / Outside
        if h < ph and l > pl:
            hits.append(PatternHit(CandlePattern.INSIDE_BAR, bullish_candle, i, t, 0.7))
        if h > ph and l < pl:
            hits.append(PatternHit(CandlePattern.OUTSIDE_BAR, bullish_candle, i, t, 0.8))

        # Tweezers
        if almost_equal(h, ph, 0.03) and c < o and pc > po:
            hits.append(PatternHit(CandlePattern.TWEEZER_TOP, False, i, t))
        if almost_equal(l, pl, 0.03) and c > o and pc < po:
            hits.append(PatternHit(CandlePattern.TWEEZER_BOTTOM, True, i, t))

        # Morning / Evening star (3-candle)
        if i >= 2:
            o2, h2, l2, c2 = map(float, df.iloc[i - 2][["open", "high", "low", "close"]])
            mid_body = _body(po, pc)
            if (
                c2 < o2
                and mid_body / _range(ph, pl) < 0.3
                and c > o
                and c > (o2 + c2) / 2
            ):
                hits.append(PatternHit(CandlePattern.MORNING_STAR, True, i, t, 1.2))
            if (
                c2 > o2
                and mid_body / _range(ph, pl) < 0.3
                and c < o
                and c < (o2 + c2) / 2
            ):
                hits.append(PatternHit(CandlePattern.EVENING_STAR, False, i, t, 1.2))
    return hits


# ---------------------------------------------------------------------------
# Support & Resistance
# ---------------------------------------------------------------------------

def psychological_levels(price: float, step: float = 50.0, count: int = 6) -> list[SRLevel]:
    base = round(price / step) * step
    levels: list[SRLevel] = []
    for i in range(-count // 2, count // 2 + 1):
        p = base + i * step
        if p > 0:
            kind = "psychological" if p % 100 else "round_number"
            # round numbers every 100; psychological every 50
            if abs(p % 100) < 1e-6:
                kind = "round_number"
            levels.append(SRLevel(p, kind, strength=1.2 if kind == "round_number" else 1.0))
    return levels


def swing_sr(smc: SMCResult, timeframe: str) -> list[SRLevel]:
    levels: list[SRLevel] = []
    for s in smc.swings[-12:]:
        kind = "swing_high" if s.kind == "high" else "swing_low"
        levels.append(SRLevel(s.price, kind, strength=1.0, timeframe=timeframe))
    return levels


def period_levels(df: pd.DataFrame, kind: str) -> list[SRLevel]:
    if df is None or df.empty:
        return []
    return [
        SRLevel(float(df["high"].iloc[-1]), f"{kind}_high", 1.3, kind),
        SRLevel(float(df["low"].iloc[-1]), f"{kind}_low", 1.3, kind),
        SRLevel(float(df["close"].iloc[-2]) if len(df) > 1 else float(df["close"].iloc[-1]), f"{kind}_close", 1.0, kind),
    ]


# ---------------------------------------------------------------------------
# Top-down analysis
# ---------------------------------------------------------------------------

HTF = (TimeFrame.MN1, TimeFrame.W1, TimeFrame.D1, TimeFrame.H4)
MTF = (TimeFrame.H1, TimeFrame.M30)
LTF = (TimeFrame.M15, TimeFrame.M5, TimeFrame.M1)


def _bias_from_ema(ema_bias: str) -> TrendBias:
    if ema_bias.startswith("BULLISH"):
        return TrendBias.BULLISH
    if ema_bias.startswith("BEARISH"):
        return TrendBias.BEARISH
    return TrendBias.NEUTRAL


def analyze_timeframe(tf: TimeFrame, df: pd.DataFrame) -> TimeframeAnalysis:
    ind = compute_indicators(df)
    atr_val = float(ind.atr.iloc[-1])
    smc = analyze_smc(df, atr_val)
    swing_high = smc.range_high or float(df["high"].iloc[-50:].max())
    swing_low = smc.range_low or float(df["low"].iloc[-50:].min())
    ict = analyze_ict(df, swing_low=swing_low, swing_high=swing_high)
    patterns = detect_patterns(df)
    price = float(df["close"].iloc[-1])
    ema_bias = ema_trend_bias(ind, price)
    trend = smc.trend if smc.trend != TrendBias.NEUTRAL else _bias_from_ema(ema_bias)
    fib = fibonacci_levels(swing_low, swing_high) if swing_high > swing_low else {}
    sr = swing_sr(smc, tf.value) + psychological_levels(price)
    return TimeframeAnalysis(
        timeframe=tf,
        indicators=ind,
        smc=smc,
        ict=ict,
        patterns=patterns,
        sr_levels=sr,
        fib=fib,
        ema_bias=ema_bias,
        trend=trend,
    )


def run_top_down(snapshot: MarketSnapshot) -> TopDownAnalysis:
    price = snapshot.quote.mid if snapshot.quote else 0.0
    spread = snapshot.quote.spread if snapshot.quote else 0.0
    if price == 0 and snapshot.frames:
        any_df = next(iter(snapshot.frames.values()))
        price = float(any_df["close"].iloc[-1])

    result = TopDownAnalysis(symbol=snapshot.symbol, price=price, spread=spread)
    for tf, df in snapshot.frames.items():
        if df is None or len(df) < 30:
            continue
        result.frames[tf] = analyze_timeframe(tf, df)

    # Higher-timeframe confluence (mode-aware: swing uses MN1→H4, scalp uses H1/M15)
    htf = CONFIG.htf_timeframes or HTF
    htf_biases = [result.frames[tf].trend for tf in htf if tf in result.frames]
    if htf_biases:
        bull = sum(1 for b in htf_biases if b == TrendBias.BULLISH)
        bear = sum(1 for b in htf_biases if b == TrendBias.BEARISH)
        if bull > bear:
            result.higher_tf_bias = TrendBias.BULLISH
        elif bear > bull:
            result.higher_tf_bias = TrendBias.BEARISH

    entry_tf = CONFIG.entry_timeframe
    if entry_tf in result.frames:
        entry_bias = result.frames[entry_tf].trend
        result.aligned_bullish = (
            result.higher_tf_bias == TrendBias.BULLISH and entry_bias == TrendBias.BULLISH
        )
        result.aligned_bearish = (
            result.higher_tf_bias == TrendBias.BEARISH and entry_bias == TrendBias.BEARISH
        )

    if TimeFrame.D1 in snapshot.frames:
        result.daily_levels = period_levels(snapshot.frames[TimeFrame.D1], "daily")
    if TimeFrame.W1 in snapshot.frames:
        result.weekly_levels = period_levels(snapshot.frames[TimeFrame.W1], "weekly")
    if TimeFrame.MN1 in snapshot.frames:
        result.monthly_levels = period_levels(snapshot.frames[TimeFrame.MN1], "monthly")
    result.psychological = psychological_levels(price)
    return result
