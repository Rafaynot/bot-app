"""
Smart Money Concepts (SMC) detection.

Order blocks, FVGs, liquidity, market structure shifts, premium/discount.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

import numpy as np
import pandas as pd

from config import CONFIG
from utils import StructureType, TrendBias, almost_equal


class BlockKind(str, Enum):
    ORDER_BLOCK = "Order Block"
    BREAKER = "Breaker Block"
    MITIGATION = "Mitigation Block"


@dataclass
class SwingPoint:
    index: int
    time: pd.Timestamp
    price: float
    kind: str  # "high" | "low"
    structure: StructureType | None = None


@dataclass
class Zone:
    kind: str
    top: float
    bottom: float
    start_time: pd.Timestamp
    end_time: pd.Timestamp | None = None
    bullish: bool = True
    mitigated: bool = False
    strength: float = 1.0

    @property
    def mid(self) -> float:
        return (self.top + self.bottom) / 2.0


@dataclass
class FVG:
    top: float
    bottom: float
    start_idx: int
    start_time: pd.Timestamp
    bullish: bool
    filled: bool = False
    inverse: bool = False


@dataclass
class LiquidityLevel:
    price: float
    time: pd.Timestamp
    side: str  # "high" | "low"
    swept: bool = False
    equal: bool = False
    internal: bool = False


@dataclass
class StructureEvent:
    event_type: StructureType
    price: float
    time: pd.Timestamp
    bullish: bool
    description: str


@dataclass
class SMCResult:
    swings: list[SwingPoint] = field(default_factory=list)
    structure_events: list[StructureEvent] = field(default_factory=list)
    order_blocks: list[Zone] = field(default_factory=list)
    breaker_blocks: list[Zone] = field(default_factory=list)
    mitigation_blocks: list[Zone] = field(default_factory=list)
    fvgs: list[FVG] = field(default_factory=list)
    inverse_fvgs: list[FVG] = field(default_factory=list)
    liquidity: list[LiquidityLevel] = field(default_factory=list)
    equal_highs: list[float] = field(default_factory=list)
    equal_lows: list[float] = field(default_factory=list)
    trend: TrendBias = TrendBias.NEUTRAL
    regime: StructureType = StructureType.RANGE
    premium: float = 0.0
    equilibrium: float = 0.0
    discount: float = 0.0
    range_high: float = 0.0
    range_low: float = 0.0
    last_bos_bullish: bool | None = None
    last_choch_bullish: bool | None = None
    liquidity_sweep_bullish: bool = False
    liquidity_sweep_bearish: bool = False
    inducement: float | None = None


def find_swings(df: pd.DataFrame, lookback: int | None = None) -> list[SwingPoint]:
    lb = lookback or CONFIG.signal.swing_lookback
    highs = df["high"].values
    lows = df["low"].values
    times = df.index
    swings: list[SwingPoint] = []
    for i in range(lb, len(df) - lb):
        window_h = highs[i - lb : i + lb + 1]
        window_l = lows[i - lb : i + lb + 1]
        if highs[i] == window_h.max() and np.argmax(window_h) == lb:
            swings.append(SwingPoint(i, times[i], float(highs[i]), "high"))
        if lows[i] == window_l.min() and np.argmin(window_l) == lb:
            swings.append(SwingPoint(i, times[i], float(lows[i]), "low"))
    return swings


def label_structure(swings: list[SwingPoint]) -> list[SwingPoint]:
    """Assign HH/HL/LH/LL labels relative to prior same-type swing."""
    last_high: SwingPoint | None = None
    last_low: SwingPoint | None = None
    for s in swings:
        if s.kind == "high":
            if last_high is not None:
                s.structure = StructureType.HH if s.price > last_high.price else StructureType.LH
            last_high = s
        else:
            if last_low is not None:
                s.structure = StructureType.HL if s.price > last_low.price else StructureType.LL
            last_low = s
    return swings


def detect_bos_choch_mss(
    df: pd.DataFrame, swings: list[SwingPoint]
) -> tuple[list[StructureEvent], TrendBias, bool | None, bool | None]:
    """
    BOS: continuation break of prior swing in trend direction.
    CHOCH / MSS: first break against prior trend (change of character / market structure shift).
    """
    events: list[StructureEvent] = []
    bias = TrendBias.NEUTRAL
    last_bos: bool | None = None
    last_choch: bool | None = None

    swing_highs = [s for s in swings if s.kind == "high"]
    swing_lows = [s for s in swings if s.kind == "low"]
    if len(swing_highs) < 2 or len(swing_lows) < 2:
        return events, bias, last_bos, last_choch

    # Infer bias from last two HL/HH or LH/LL
    recent = swings[-6:]
    hh = sum(1 for s in recent if s.structure == StructureType.HH)
    hl = sum(1 for s in recent if s.structure == StructureType.HL)
    lh = sum(1 for s in recent if s.structure == StructureType.LH)
    ll = sum(1 for s in recent if s.structure == StructureType.LL)
    if hh + hl > lh + ll:
        bias = TrendBias.BULLISH
    elif lh + ll > hh + hl:
        bias = TrendBias.BEARISH

    close = df["close"]
    last_sh = swing_highs[-1]
    last_sl = swing_lows[-1]
    prev_sh = swing_highs[-2]
    prev_sl = swing_lows[-2]

    # Check last few bars for breaks
    for i in range(max(last_sh.index, last_sl.index) + 1, len(df)):
        t = df.index[i]
        c = float(close.iloc[i])
        # Bullish break of last swing high
        if c > last_sh.price:
            if bias == TrendBias.BEARISH:
                events.append(
                    StructureEvent(
                        StructureType.CHOCH,
                        last_sh.price,
                        t,
                        True,
                        "Bullish CHOCH / MSS — broke last swing high against bearish bias",
                    )
                )
                last_choch = True
                bias = TrendBias.BULLISH
            else:
                events.append(
                    StructureEvent(
                        StructureType.BOS,
                        last_sh.price,
                        t,
                        True,
                        "Bullish BOS — broke swing high",
                    )
                )
                last_bos = True
            last_sh = SwingPoint(i, t, float(df["high"].iloc[i]), "high")
        # Bearish break of last swing low
        if c < last_sl.price:
            if bias == TrendBias.BULLISH:
                events.append(
                    StructureEvent(
                        StructureType.CHOCH,
                        last_sl.price,
                        t,
                        False,
                        "Bearish CHOCH / MSS — broke last swing low against bullish bias",
                    )
                )
                last_choch = False
                bias = TrendBias.BEARISH
            else:
                events.append(
                    StructureEvent(
                        StructureType.BOS,
                        last_sl.price,
                        t,
                        False,
                        "Bearish BOS — broke swing low",
                    )
                )
                last_bos = False
            last_sl = SwingPoint(i, t, float(df["low"].iloc[i]), "low")

    # Also flag MSS synonym when CHOCH just occurred
    for e in list(events):
        if e.event_type == StructureType.CHOCH:
            events.append(
                StructureEvent(StructureType.MSS, e.price, e.time, e.bullish, "MSS (synonym of CHOCH)")
            )

    # Use prior swings for context if no recent break
    _ = prev_sh, prev_sl
    return events, bias, last_bos, last_choch


def detect_regime(df: pd.DataFrame, atr_series: pd.Series | None = None) -> StructureType:
    """Classify Trend / Range / Consolidation / Expansion / Compression."""
    if len(df) < 30:
        return StructureType.RANGE
    closes = df["close"].iloc[-30:]
    atr_now = float((df["high"] - df["low"]).iloc[-14:].mean())
    atr_prev = float((df["high"] - df["low"]).iloc[-40:-14].mean()) if len(df) > 40 else atr_now
    net = float(closes.iloc[-1] - closes.iloc[0])
    path = float(closes.diff().abs().sum())
    efficiency = abs(net) / path if path else 0.0

    if atr_prev > 0 and atr_now / atr_prev < 0.7 and efficiency < 0.2:
        return StructureType.COMPRESSION
    if atr_prev > 0 and atr_now / atr_prev > 1.4 and efficiency > 0.35:
        return StructureType.EXPANSION
    if efficiency > 0.4:
        return StructureType.TREND
    if efficiency < 0.15:
        return StructureType.CONSOLIDATION
    return StructureType.RANGE


def detect_fvgs(df: pd.DataFrame, atr_val: float) -> list[FVG]:
    """3-candle fair value gaps; mark inverse when price fills then reverses through."""
    fvgs: list[FVG] = []
    min_gap = atr_val * CONFIG.signal.fvg_min_gap_atr
    for i in range(2, len(df)):
        c0_high = float(df["high"].iloc[i - 2])
        c0_low = float(df["low"].iloc[i - 2])
        c2_high = float(df["high"].iloc[i])
        c2_low = float(df["low"].iloc[i])
        # Bullish FVG: candle0 high < candle2 low
        if c2_low > c0_high and (c2_low - c0_high) >= min_gap:
            fvgs.append(
                FVG(
                    top=c2_low,
                    bottom=c0_high,
                    start_idx=i - 1,
                    start_time=df.index[i - 1],
                    bullish=True,
                )
            )
        # Bearish FVG: candle0 low > candle2 high
        if c2_high < c0_low and (c0_low - c2_high) >= min_gap:
            fvgs.append(
                FVG(
                    top=c0_low,
                    bottom=c2_high,
                    start_idx=i - 1,
                    start_time=df.index[i - 1],
                    bullish=False,
                )
            )

    # Mark filled / inverse
    for fvg in fvgs:
        for j in range(fvg.start_idx + 2, len(df)):
            low = float(df["low"].iloc[j])
            high = float(df["high"].iloc[j])
            if fvg.bullish and low <= fvg.bottom:
                fvg.filled = True
                # Inverse if subsequent close below gap
                if float(df["close"].iloc[j]) < fvg.bottom:
                    fvg.inverse = True
                break
            if not fvg.bullish and high >= fvg.top:
                fvg.filled = True
                if float(df["close"].iloc[j]) > fvg.top:
                    fvg.inverse = True
                break
    return fvgs


def detect_order_blocks(df: pd.DataFrame, swings: list[SwingPoint]) -> list[Zone]:
    """
    Last opposing candle before impulsive move that breaks structure.
    Bullish OB: last down candle before strong rally.
    Bearish OB: last up candle before strong drop.
    """
    blocks: list[Zone] = []
    if len(df) < 10:
        return blocks
    body = (df["close"] - df["open"]).abs()
    avg_body = float(body.rolling(20, min_periods=1).mean().iloc[-1]) or 1e-9

    for i in range(3, len(df) - 1):
        # Bullish impulse: strong green after red candle
        if (
            df["close"].iloc[i] < df["open"].iloc[i]
            and df["close"].iloc[i + 1] > df["open"].iloc[i + 1]
            and (df["close"].iloc[i + 1] - df["open"].iloc[i + 1]) > 1.5 * avg_body
            and float(df["close"].iloc[i + 1]) > float(df["high"].iloc[i])
        ):
            blocks.append(
                Zone(
                    kind=BlockKind.ORDER_BLOCK.value,
                    top=float(df["high"].iloc[i]),
                    bottom=float(df["low"].iloc[i]),
                    start_time=df.index[i],
                    bullish=True,
                )
            )
        # Bearish impulse
        if (
            df["close"].iloc[i] > df["open"].iloc[i]
            and df["close"].iloc[i + 1] < df["open"].iloc[i + 1]
            and (df["open"].iloc[i + 1] - df["close"].iloc[i + 1]) > 1.5 * avg_body
            and float(df["close"].iloc[i + 1]) < float(df["low"].iloc[i])
        ):
            blocks.append(
                Zone(
                    kind=BlockKind.ORDER_BLOCK.value,
                    top=float(df["high"].iloc[i]),
                    bottom=float(df["low"].iloc[i]),
                    start_time=df.index[i],
                    bullish=False,
                )
            )

    # Mitigation / breaker: OB that was traded through then retested opposite
    mitigated: list[Zone] = []
    breakers: list[Zone] = []
    price = float(df["close"].iloc[-1])
    for ob in blocks:
        if ob.bullish and price < ob.bottom:
            ob.mitigated = True
            br = Zone(
                kind=BlockKind.BREAKER.value,
                top=ob.top,
                bottom=ob.bottom,
                start_time=ob.start_time,
                bullish=False,
            )
            breakers.append(br)
            mitigated.append(
                Zone(
                    kind=BlockKind.MITIGATION.value,
                    top=ob.top,
                    bottom=ob.bottom,
                    start_time=ob.start_time,
                    bullish=True,
                    mitigated=True,
                )
            )
        elif not ob.bullish and price > ob.top:
            ob.mitigated = True
            breakers.append(
                Zone(
                    kind=BlockKind.BREAKER.value,
                    top=ob.top,
                    bottom=ob.bottom,
                    start_time=ob.start_time,
                    bullish=True,
                )
            )
            mitigated.append(
                Zone(
                    kind=BlockKind.MITIGATION.value,
                    top=ob.top,
                    bottom=ob.bottom,
                    start_time=ob.start_time,
                    bullish=False,
                    mitigated=True,
                )
            )
    # Keep recent unmitigated OBs + derived blocks
    fresh = [b for b in blocks if not b.mitigated][-8:]
    return fresh + breakers[-4:] + mitigated[-4:]


def detect_liquidity(df: pd.DataFrame, swings: list[SwingPoint]) -> tuple[
    list[LiquidityLevel], list[float], list[float], bool, bool, float | None
]:
    """Equal highs/lows, sweeps, inducement, internal vs external liquidity."""
    tol = CONFIG.signal.equal_level_tolerance_pct
    highs = [s for s in swings if s.kind == "high"]
    lows = [s for s in swings if s.kind == "low"]
    levels: list[LiquidityLevel] = []
    eq_highs: list[float] = []
    eq_lows: list[float] = []

    for i, h in enumerate(highs):
        equal = any(
            almost_equal(h.price, o.price, tol) for j, o in enumerate(highs) if i != j
        )
        if equal:
            eq_highs.append(h.price)
        levels.append(
            LiquidityLevel(h.price, h.time, "high", equal=equal, internal=i >= len(highs) - 3)
        )
    for i, lo in enumerate(lows):
        equal = any(
            almost_equal(lo.price, o.price, tol) for j, o in enumerate(lows) if i != j
        )
        if equal:
            eq_lows.append(lo.price)
        levels.append(
            LiquidityLevel(lo.price, lo.time, "low", equal=equal, internal=i >= len(lows) - 3)
        )

    # Liquidity sweeps: wick beyond swing then close back inside
    lookback = CONFIG.signal.liquidity_sweep_lookback
    sweep_bull = False
    sweep_bear = False
    if len(df) > lookback and lows:
        recent_low = min(s.price for s in lows[-3:])
        window = df.iloc[-lookback:]
        for i in range(len(window)):
            if float(window["low"].iloc[i]) < recent_low and float(window["close"].iloc[i]) > recent_low:
                sweep_bull = True
                for lv in levels:
                    if lv.side == "low" and almost_equal(lv.price, recent_low, tol):
                        lv.swept = True
    if len(df) > lookback and highs:
        recent_high = max(s.price for s in highs[-3:])
        window = df.iloc[-lookback:]
        for i in range(len(window)):
            if float(window["high"].iloc[i]) > recent_high and float(window["close"].iloc[i]) < recent_high:
                sweep_bear = True
                for lv in levels:
                    if lv.side == "high" and almost_equal(lv.price, recent_high, tol):
                        lv.swept = True

    # Inducement: minor swing that lures traders before reverse toward liquidity
    inducement: float | None = None
    if len(highs) >= 2 and len(lows) >= 2:
        inducement = highs[-1].price if sweep_bull else (lows[-1].price if sweep_bear else None)

    return levels, eq_highs, eq_lows, sweep_bull, sweep_bear, inducement


def premium_discount(range_high: float, range_low: float) -> tuple[float, float, float]:
    """Return (premium_mid, equilibrium, discount_mid)."""
    eq = (range_high + range_low) / 2.0
    premium = (range_high + eq) / 2.0
    discount = (range_low + eq) / 2.0
    return premium, eq, discount


def analyze_smc(df: pd.DataFrame, atr_val: float | None = None) -> SMCResult:
    """Run full SMC pipeline on a single timeframe."""
    result = SMCResult()
    if df is None or len(df) < 30:
        return result

    atr_v = atr_val if atr_val is not None else float((df["high"] - df["low"]).iloc[-14:].mean())
    swings = label_structure(find_swings(df))
    result.swings = swings

    events, bias, last_bos, last_choch = detect_bos_choch_mss(df, swings)
    result.structure_events = events
    result.trend = bias
    result.last_bos_bullish = last_bos
    result.last_choch_bullish = last_choch
    result.regime = detect_regime(df)

    all_blocks = detect_order_blocks(df, swings)
    result.order_blocks = [b for b in all_blocks if b.kind == BlockKind.ORDER_BLOCK.value]
    result.breaker_blocks = [b for b in all_blocks if b.kind == BlockKind.BREAKER.value]
    result.mitigation_blocks = [b for b in all_blocks if b.kind == BlockKind.MITIGATION.value]

    fvgs = detect_fvgs(df, atr_v)
    result.fvgs = [f for f in fvgs if not f.inverse]
    result.inverse_fvgs = [f for f in fvgs if f.inverse]

    liq, eq_h, eq_l, sw_b, sw_s, inducement = detect_liquidity(df, swings)
    result.liquidity = liq
    result.equal_highs = eq_h
    result.equal_lows = eq_l
    result.liquidity_sweep_bullish = sw_b
    result.liquidity_sweep_bearish = sw_s
    result.inducement = inducement

    # Dealing range from last major swings
    highs = [s.price for s in swings if s.kind == "high"]
    lows = [s.price for s in swings if s.kind == "low"]
    if highs and lows:
        result.range_high = max(highs[-3:]) if len(highs) >= 3 else max(highs)
        result.range_low = min(lows[-3:]) if len(lows) >= 3 else min(lows)
        prem, eq, disc = premium_discount(result.range_high, result.range_low)
        result.premium = prem
        result.equilibrium = eq
        result.discount = disc

    return result


def price_in_zone(price: float, zone: Zone, pad: float = 0.0) -> bool:
    return zone.bottom - pad <= price <= zone.top + pad


def nearest_unmitigated_ob(result: SMCResult, bullish: bool, price: float) -> Zone | None:
    cands = [z for z in result.order_blocks if z.bullish == bullish and not z.mitigated]
    if not cands:
        return None
    return min(cands, key=lambda z: abs(z.mid - price))


def nearest_fvg(result: SMCResult, bullish: bool, price: float) -> FVG | None:
    cands = [f for f in result.fvgs if f.bullish == bullish and not f.filled]
    if not cands:
        return None
    return min(cands, key=lambda f: abs((f.top + f.bottom) / 2 - price))
