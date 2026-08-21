"""
Market forecast — direction, distance, and time window.

Uses the same SMC/ICT + accuracy feed as the desk. Does not replace
Swing / Intraday / Scalp trade signals.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from analysis import TopDownAnalysis, TimeframeAnalysis
from config import TimeFrame
from utils import TrendBias, utc_now


GREEN = "#0ecb81"
RED = "#f6465d"
YELLOW = "#f0b90b"


@dataclass
class HorizonCall:
    name: str
    until: str
    until_iso: str
    direction: str
    target: float
    move: float
    move_pct: float
    low: float
    high: float
    confidence: float
    note: str


@dataclass
class MarketForecast:
    active: bool = False
    direction: str = "RANGE"
    headline: str = "Waiting for market data"
    summary: str = ""
    confidence: float = 0.0
    price: float = 0.0
    invalidation: float = 0.0
    color: str = YELLOW
    path_x: list[str] = field(default_factory=list)
    path_y: list[float] = field(default_factory=list)
    path_text: list[str] = field(default_factory=list)
    levels: list[dict] = field(default_factory=list)
    horizons: list[HorizonCall] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    data_rows: list[tuple[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "active": self.active,
            "direction": self.direction,
            "headline": self.headline,
            "summary": self.summary,
            "confidence": self.confidence,
            "price": self.price,
            "invalidation": self.invalidation,
            "color": self.color,
            "path_x": self.path_x,
            "path_y": self.path_y,
            "path_text": self.path_text,
            "levels": self.levels,
            "horizons": [
                {
                    "name": h.name,
                    "until": h.until,
                    "until_iso": h.until_iso,
                    "direction": h.direction,
                    "target": h.target,
                    "move": h.move,
                    "move_pct": h.move_pct,
                    "low": h.low,
                    "high": h.high,
                    "confidence": h.confidence,
                    "note": h.note,
                }
                for h in self.horizons
            ],
            "reasons": self.reasons,
            "data_rows": [{"k": k, "v": v} for k, v in self.data_rows],
        }


def build_forecast(analysis: TopDownAnalysis) -> MarketForecast:
    price = float(analysis.price or 0.0)
    if price <= 0 or not analysis.frames:
        return MarketForecast(summary="Not enough candles yet to forecast.")

    tf_data = _pick_frame(
        analysis,
        (TimeFrame.H1, TimeFrame.M15, TimeFrame.H4, TimeFrame.M5, TimeFrame.D1),
    )
    if tf_data is None:
        return MarketForecast(summary="Not enough candles yet to forecast.")

    now = utc_now()
    ind = tf_data.indicators
    smc = tf_data.smc
    atr = _last(ind.atr, 8.0)
    rsi = _last(ind.rsi, 50.0)
    adx = _last(ind.adx, 18.0)
    macd_hist = _last(ind.macd_hist, 0.0)
    st_dir = _last(ind.supertrend_dir, 0.0)
    acc = getattr(analysis, "_accuracy", None)

    bull, bear, reasons = _score_sides(analysis, tf_data, price, atr, rsi, macd_hist, st_dir, acc)
    direction, confidence = _resolve_direction(bull, bear, adx)
    color = GREEN if direction == "UP" else RED if direction == "DOWN" else YELLOW

    above = _levels_above(analysis, tf_data, acc, price)
    below = _levels_below(analysis, tf_data, acc, price)
    res = above[0] if above else price + 1.6 * atr
    sup = below[0] if below else price - 1.6 * atr

    near_t = now + timedelta(minutes=90)
    mid_t = _session_end(now)
    if mid_t <= now + timedelta(minutes=20):
        mid_t = now + timedelta(hours=4)
    far_t = now + timedelta(hours=24)

    near = _horizon("Next 1–2 hours", near_t, direction, price, atr, 0.55, res, sup, confidence, "Near move")
    mid = _horizon("This session", mid_t, direction, price, atr, 1.15, res, sup, max(48.0, confidence - 6), "Session path")
    far = _horizon("Next 24 hours", far_t, direction, price, atr, 1.85, res, sup, max(42.0, confidence - 12), "Daily path")
    if direction == "RANGE":
        near = _horizon("Next 1–2 hours", near_t, "RANGE", price, atr, 0.35, res, sup, confidence, "Chop / mean revert")
        mid = _horizon("This session", mid_t, "RANGE", price, atr, 0.70, res, sup, confidence, "Hold the range")
        far = _horizon("Next 24 hours", far_t, "RANGE", price, atr, 1.10, res, sup, max(40.0, confidence - 8), "Range until break")

    if direction == "UP":
        invalid = min(sup, price - 1.15 * atr)
        target = mid.target
    elif direction == "DOWN":
        invalid = max(res, price + 1.15 * atr)
        target = mid.target
    else:
        invalid = sup if abs(price - sup) <= abs(res - price) else res
        target = (sup + res) / 2.0

    move = target - price
    move_pct = (move / price) * 100.0 if price else 0.0
    until = mid.until
    if direction == "UP":
        headline = (
            f"MARKET UP  ·  toward {_p(target)}  ·  until {until}"
        )
        lead = (
            f"Bot forecast: market is likely to go UP from {_p(price)} toward {_p(target)} "
            f"({move:+.2f} / {move_pct:+.2f}%) by {until}."
        )
    elif direction == "DOWN":
        headline = (
            f"MARKET DOWN  ·  toward {_p(target)}  ·  until {until}"
        )
        lead = (
            f"Bot forecast: market is likely to go DOWN from {_p(price)} toward {_p(target)} "
            f"({move:+.2f} / {move_pct:+.2f}%) by {until}."
        )
    else:
        headline = f"RANGE  ·  {_p(sup)} – {_p(res)}  ·  until {until}"
        lead = (
            f"Bot forecast: no clean trend. Price is likely to stay between {_p(sup)} and {_p(res)} "
            f"until {until}."
        )

    summary = "\n".join(
        [
            lead,
            "",
            f"Now: {_p(price)}",
            f"How far: {move:+.2f} ({move_pct:+.2f}%) → {_p(target)}",
            f"Until: {until}",
            f"Invalid if price crosses {_p(invalid)}",
            f"Confidence: {confidence:.0f}%",
            "",
            "Why:",
            *[f"• {r}" for r in reasons[:8]],
        ]
    )

    path_x = [now.isoformat(), near.until_iso, mid.until_iso, far.until_iso]
    path_y = [price, near.target, mid.target, far.target]
    path_text = [
        f"Now {_p(price)}",
        f"{near.name}: {_p(near.target)}",
        f"{mid.name}: {_p(mid.target)}",
        f"{far.name}: {_p(far.target)}",
    ]
    levels = [
        {"y": near.target, "label": f"  {near.direction} {_p(near.target)} · {near.name}  "},
        {"y": mid.target, "label": f"  {mid.direction} {_p(mid.target)} · {mid.name}  "},
        {"y": invalid, "label": f"  Invalid {_p(invalid)}  "},
    ]

    data_rows = _data_rows(analysis, tf_data, acc, price, atr, rsi, adx, smc)

    return MarketForecast(
        active=True,
        direction=direction,
        headline=headline,
        summary=summary,
        confidence=confidence,
        price=price,
        invalidation=invalid,
        color=color,
        path_x=path_x,
        path_y=path_y,
        path_text=path_text,
        levels=levels,
        horizons=[near, mid, far],
        reasons=reasons,
        data_rows=data_rows,
    )


def _pick_frame(analysis: TopDownAnalysis, order: tuple[TimeFrame, ...]) -> TimeframeAnalysis | None:
    for tf in order:
        if tf in analysis.frames:
            return analysis.frames[tf]
    return next(iter(analysis.frames.values()), None)


def _last(series, default: float) -> float:
    try:
        val = float(series.iloc[-1])
        if val != val:  # NaN
            return default
        return val
    except Exception:  # noqa: BLE001
        return default


def _p(value: float) -> str:
    return f"{value:,.2f}"


def _fmt_when(ts: datetime) -> str:
    return ts.strftime("%d %b %H:%M UTC")


def _session_end(now: datetime) -> datetime:
    h = now.hour
    base = now.replace(minute=0, second=0, microsecond=0)
    if h < 8:
        return base.replace(hour=8)
    if h < 12:
        return base.replace(hour=12)
    if h < 21:
        return base.replace(hour=21)
    nxt = now + timedelta(days=1)
    return nxt.replace(hour=8, minute=0, second=0, microsecond=0)


def _score_sides(
    analysis: TopDownAnalysis,
    tf_data: TimeframeAnalysis,
    price: float,
    atr: float,
    rsi: float,
    macd_hist: float,
    st_dir: float,
    acc,
) -> tuple[float, float, list[str]]:
    bull = 0.0
    bear = 0.0
    reasons: list[str] = []

    if analysis.aligned_bullish:
        bull += 18
        reasons.append("Higher timeframes aligned UP")
    elif analysis.aligned_bearish:
        bear += 18
        reasons.append("Higher timeframes aligned DOWN")
    elif analysis.higher_tf_bias == TrendBias.BULLISH:
        bull += 12
        reasons.append("Higher-timeframe bias is bullish")
    elif analysis.higher_tf_bias == TrendBias.BEARISH:
        bear += 12
        reasons.append("Higher-timeframe bias is bearish")
    else:
        reasons.append("Higher timeframes are mixed")

    if tf_data.trend == TrendBias.BULLISH:
        bull += 12
        reasons.append(f"{tf_data.timeframe.value} structure is bullish")
    elif tf_data.trend == TrendBias.BEARISH:
        bear += 12
        reasons.append(f"{tf_data.timeframe.value} structure is bearish")

    smc = tf_data.smc
    if smc.last_bos_bullish is True:
        bull += 8
        reasons.append("Last break of structure was UP")
    elif smc.last_bos_bullish is False:
        bear += 8
        reasons.append("Last break of structure was DOWN")
    if smc.last_choch_bullish is True:
        bull += 6
        reasons.append("Change of character to bullish")
    elif smc.last_choch_bullish is False:
        bear += 6
        reasons.append("Change of character to bearish")
    if smc.liquidity_sweep_bullish:
        bull += 5
        reasons.append("Liquidity sweep below, bounce setup")
    if smc.liquidity_sweep_bearish:
        bear += 5
        reasons.append("Liquidity sweep above, drop setup")

    bias = (tf_data.ema_bias or "").upper()
    if "BULLISH" in bias:
        bull += 8
        reasons.append(f"EMA stack {tf_data.ema_bias}")
    elif "BEARISH" in bias:
        bear += 8
        reasons.append(f"EMA stack {tf_data.ema_bias}")

    if rsi <= 40:
        bull += 5
        reasons.append(f"RSI {rsi:.0f} — room to bounce")
    elif rsi >= 60:
        bear += 5
        reasons.append(f"RSI {rsi:.0f} — stretched up")
    if macd_hist > 0:
        bull += 5
        reasons.append("MACD histogram positive")
    elif macd_hist < 0:
        bear += 5
        reasons.append("MACD histogram negative")
    if st_dir > 0:
        bull += 6
        reasons.append("Supertrend is up")
    elif st_dir < 0:
        bear += 6
        reasons.append("Supertrend is down")

    if acc is not None:
        cvd = getattr(acc, "cvd_delta", None)
        if cvd is not None:
            if cvd > 0:
                bull += 6
                reasons.append("CVD buy pressure")
            elif cvd < 0:
                bear += 6
                reasons.append("CVD sell pressure")
        taker = getattr(acc, "taker_buy_sell", None)
        if taker is not None:
            if taker >= 1.05:
                bull += 4
                reasons.append(f"Taker buy/sell {taker:.2f}")
            elif taker <= 0.95:
                bear += 4
                reasons.append(f"Taker buy/sell {taker:.2f}")
        oi = getattr(acc, "oi_change_pct", None)
        if oi is not None and abs(oi) >= 0.4:
            if oi > 0 and bull >= bear:
                bull += 3
                reasons.append(f"Open interest rising {oi:+.2f}%")
            elif oi > 0 and bear > bull:
                bear += 3
                reasons.append(f"Open interest rising {oi:+.2f}% (trend fuel)")
        fr = getattr(acc, "funding_rate", None)
        if fr is not None:
            if fr < 0:
                bull += 3
                reasons.append("Funding negative — shorts pay")
            elif fr > 0.0003:
                bear += 3
                reasons.append("Funding crowded long")
        for note in list(getattr(acc, "notes", []) or [])[:2]:
            reasons.append(str(note))

    ict = tf_data.ict
    if ict:
        reasons.append(f"Session: {ict.session.name.value}")
        if ict.amd_phase and ict.amd_phase != "Unknown":
            reasons.append(f"ICT phase: {ict.amd_phase}")

    return bull, bear, reasons


def _resolve_direction(bull: float, bear: float, adx: float) -> tuple[str, float]:
    spread = abs(bull - bear)
    top = max(bull, bear)
    conf = max(38.0, min(92.0, 42.0 + top * 0.45 + spread * 0.35))
    if adx < 16 or spread < 8:
        return "RANGE", max(40.0, min(conf, 62.0))
    if bull >= bear:
        return "UP", conf
    return "DOWN", conf


def _collect_levels(analysis: TopDownAnalysis, tf_data: TimeframeAnalysis, acc) -> list[float]:
    out: list[float] = []
    smc = tf_data.smc
    if smc.range_high:
        out.append(float(smc.range_high))
    if smc.range_low:
        out.append(float(smc.range_low))
    if smc.equilibrium:
        out.append(float(smc.equilibrium))
    for lvl in (
        list(analysis.daily_levels)
        + list(analysis.weekly_levels)
        + list(tf_data.sr_levels)
    ):
        try:
            out.append(float(lvl.price))
        except Exception:  # noqa: BLE001
            continue
    if acc is not None:
        for key in (
            "asia_high",
            "asia_low",
            "london_high",
            "london_low",
            "ny_high",
            "ny_low",
        ):
            val = getattr(acc, key, None)
            if val:
                out.append(float(val))
        for c in list(getattr(acc, "clusters", []) or [])[:8]:
            out.append(float(c.price))
    return out


def _levels_above(analysis, tf_data, acc, price: float) -> list[float]:
    vals = sorted({round(v, 2) for v in _collect_levels(analysis, tf_data, acc) if v > price + 0.05})
    return vals


def _levels_below(analysis, tf_data, acc, price: float) -> list[float]:
    vals = sorted({round(v, 2) for v in _collect_levels(analysis, tf_data, acc) if v < price - 0.05}, reverse=True)
    return vals


def _horizon(
    name: str,
    until: datetime,
    direction: str,
    price: float,
    atr: float,
    atr_mult: float,
    res: float,
    sup: float,
    confidence: float,
    note: str,
) -> HorizonCall:
    if direction == "UP":
        raw = price + atr * atr_mult
        target = min(raw, res) if res > price else raw
        low, high = price, max(target, price)
    elif direction == "DOWN":
        raw = price - atr * atr_mult
        target = max(raw, sup) if sup < price else raw
        low, high = min(target, price), price
    else:
        mid = (sup + res) / 2.0 if res > sup else price
        span = max(atr * atr_mult, abs(res - sup) * 0.25)
        target = mid
        low, high = min(price, mid) - span * 0.15, max(price, mid) + span * 0.15
        low = max(low, min(sup, price))
        high = min(high, max(res, price))
    move = target - price
    pct = (move / price) * 100.0 if price else 0.0
    return HorizonCall(
        name=name,
        until=_fmt_when(until),
        until_iso=until.isoformat(),
        direction=direction,
        target=float(target),
        move=float(move),
        move_pct=float(pct),
        low=float(low),
        high=float(high),
        confidence=float(confidence),
        note=note,
    )


def _data_rows(
    analysis: TopDownAnalysis,
    tf_data: TimeframeAnalysis,
    acc,
    price: float,
    atr: float,
    rsi: float,
    adx: float,
    smc,
) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = [
        ("Last price", _p(price)),
        ("Spread", f"{analysis.spread:.2f}"),
        ("ATR", f"{atr:.2f}"),
        ("RSI", f"{rsi:.1f}"),
        ("ADX", f"{adx:.1f}"),
        ("HTF bias", analysis.higher_tf_bias.value),
        ("Structure", smc.regime.value),
        ("EMA", tf_data.ema_bias or "—"),
        ("Timeframe", tf_data.timeframe.value),
    ]
    if acc is not None:
        fr = getattr(acc, "funding_rate", None)
        oi = getattr(acc, "oi_change_pct", None)
        cvd = getattr(acc, "cvd_delta", None)
        taker = getattr(acc, "taker_buy_sell", None)
        rows.append(("Funding", f"{fr * 100:.4f}%" if fr is not None else "—"))
        rows.append(("OI change", f"{oi:+.2f}%" if oi is not None else "—"))
        rows.append(("CVD delta", f"{cvd:+.2f}" if cvd is not None else "—"))
        rows.append(("Taker", f"{taker:.2f}" if taker is not None else "—"))
        if getattr(acc, "london_high", None):
            rows.append(("London H/L", f"{_p(acc.london_high)} / {_p(acc.london_low or 0)}"))
        if getattr(acc, "asia_high", None):
            rows.append(("Asia H/L", f"{_p(acc.asia_high)} / {_p(acc.asia_low or 0)}"))
    return rows
