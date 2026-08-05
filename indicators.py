"""
Technical indicators used for signal confirmation only.

Indicators never drive entries alone — they confirm SMC/ICT structure.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from config import CONFIG


@dataclass
class IndicatorBundle:
    """Computed indicator series attached to an OHLC frame."""

    ema20: pd.Series
    ema50: pd.Series
    ema100: pd.Series
    ema200: pd.Series
    rsi: pd.Series
    macd: pd.Series
    macd_signal: pd.Series
    macd_hist: pd.Series
    atr: pd.Series
    adx: pd.Series
    plus_di: pd.Series
    minus_di: pd.Series
    vwap: pd.Series
    bb_upper: pd.Series
    bb_mid: pd.Series
    bb_lower: pd.Series
    stoch_k: pd.Series
    stoch_d: pd.Series
    obv: pd.Series
    supertrend: pd.Series
    supertrend_dir: pd.Series  # 1 bullish, -1 bearish
    volume_sma: pd.Series


def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(period, min_periods=1).mean()


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return (100 - (100 / (1 + rs))).fillna(50.0)


def macd(
    close: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    line = ema(close, fast) - ema(close, slow)
    sig = ema(line, signal)
    hist = line - sig
    return line, sig, hist


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high, low, close = df["high"], df["low"], df["close"]
    prev_close = close.shift(1)
    tr = pd.concat(
        [
            (high - low),
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()


def adx(df: pd.DataFrame, period: int = 14) -> tuple[pd.Series, pd.Series, pd.Series]:
    high, low, close = df["high"], df["low"], df["close"]
    up = high.diff()
    down = -low.diff()
    plus_dm = np.where((up > down) & (up > 0), up, 0.0)
    minus_dm = np.where((down > up) & (down > 0), down, 0.0)
    tr = atr(df, 1)  # raw true range proxy via period-1 ATR ewm later
    # Recalculate TR properly
    prev_close = close.shift(1)
    tr = pd.concat(
        [(high - low), (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    ).max(axis=1)

    atr_n = tr.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    plus_di = 100 * pd.Series(plus_dm, index=df.index).ewm(
        alpha=1 / period, min_periods=period, adjust=False
    ).mean() / atr_n.replace(0, np.nan)
    minus_di = 100 * pd.Series(minus_dm, index=df.index).ewm(
        alpha=1 / period, min_periods=period, adjust=False
    ).mean() / atr_n.replace(0, np.nan)
    dx = (100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)).fillna(0)
    adx_line = dx.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    return adx_line.fillna(0), plus_di.fillna(0), minus_di.fillna(0)


def vwap(df: pd.DataFrame) -> pd.Series:
    typical = (df["high"] + df["low"] + df["close"]) / 3.0
    vol = df["volume"].replace(0, np.nan)
    # Session-agnostic cumulative VWAP reset daily when possible
    if isinstance(df.index, pd.DatetimeIndex):
        day = df.index.normalize()
        cum_tp_vol = (typical * vol).groupby(day).cumsum()
        cum_vol = vol.groupby(day).cumsum()
        return (cum_tp_vol / cum_vol).ffill().fillna(typical)
    cum_tp_vol = (typical * vol).cumsum()
    cum_vol = vol.cumsum()
    return (cum_tp_vol / cum_vol).fillna(typical)


def bollinger(
    close: pd.Series, period: int = 20, std_mult: float = 2.0
) -> tuple[pd.Series, pd.Series, pd.Series]:
    mid = sma(close, period)
    std = close.rolling(period, min_periods=1).std().fillna(0)
    upper = mid + std_mult * std
    lower = mid - std_mult * std
    return upper, mid, lower


def stochastic_rsi(
    close: pd.Series,
    rsi_period: int = 14,
    stoch_period: int = 14,
    k_smooth: int = 3,
    d_smooth: int = 3,
) -> tuple[pd.Series, pd.Series]:
    r = rsi(close, rsi_period)
    lowest = r.rolling(stoch_period, min_periods=1).min()
    highest = r.rolling(stoch_period, min_periods=1).max()
    stoch = 100 * (r - lowest) / (highest - lowest).replace(0, np.nan)
    k = stoch.rolling(k_smooth, min_periods=1).mean().fillna(50)
    d = k.rolling(d_smooth, min_periods=1).mean().fillna(50)
    return k, d


def obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    direction = np.sign(close.diff()).fillna(0)
    return (direction * volume).cumsum()


def supertrend(
    df: pd.DataFrame, period: int = 10, multiplier: float = 3.0
) -> tuple[pd.Series, pd.Series]:
    atr_v = atr(df, period)
    hl2 = (df["high"] + df["low"]) / 2.0
    upper = hl2 + multiplier * atr_v
    lower = hl2 - multiplier * atr_v

    st = pd.Series(index=df.index, dtype=float)
    direction = pd.Series(index=df.index, dtype=float)
    st.iloc[0] = upper.iloc[0]
    direction.iloc[0] = -1.0

    for i in range(1, len(df)):
        if df["close"].iloc[i] > st.iloc[i - 1]:
            direction.iloc[i] = 1.0
        elif df["close"].iloc[i] < st.iloc[i - 1]:
            direction.iloc[i] = -1.0
        else:
            direction.iloc[i] = direction.iloc[i - 1]

        if direction.iloc[i] == 1.0:
            st.iloc[i] = max(lower.iloc[i], st.iloc[i - 1]) if direction.iloc[i - 1] == 1.0 else lower.iloc[i]
        else:
            st.iloc[i] = min(upper.iloc[i], st.iloc[i - 1]) if direction.iloc[i - 1] == -1.0 else upper.iloc[i]

    return st, direction


def compute_indicators(df: pd.DataFrame) -> IndicatorBundle:
    """Compute full indicator set for one timeframe."""
    close = df["close"]
    e20, e50, e100, e200 = CONFIG.signal.ema_periods
    macd_line, macd_sig, macd_hist = macd(close)
    adx_line, plus_di, minus_di = adx(df)
    bb_u, bb_m, bb_l = bollinger(close)
    sk, sd = stochastic_rsi(close)
    st, st_dir = supertrend(df)

    return IndicatorBundle(
        ema20=ema(close, e20),
        ema50=ema(close, e50),
        ema100=ema(close, e100),
        ema200=ema(close, e200),
        rsi=rsi(close),
        macd=macd_line,
        macd_signal=macd_sig,
        macd_hist=macd_hist,
        atr=atr(df),
        adx=adx_line,
        plus_di=plus_di,
        minus_di=minus_di,
        vwap=vwap(df),
        bb_upper=bb_u,
        bb_mid=bb_m,
        bb_lower=bb_l,
        stoch_k=sk,
        stoch_d=sd,
        obv=obv(close, df["volume"]),
        supertrend=st,
        supertrend_dir=st_dir,
        volume_sma=sma(df["volume"], 20),
    )


def fibonacci_levels(swing_low: float, swing_high: float) -> dict[str, float]:
    """
    Retracement levels from swing_high → swing_low (bearish impulse)
    or swing_low → swing_high (bullish impulse). Always returns absolute prices.
    """
    diff = swing_high - swing_low
    ratios = (0.0, 0.236, 0.382, 0.5, 0.618, 0.705, 0.786, 1.0)
    # Standard retracement from high toward low
    return {f"{r:.3f}".rstrip("0").rstrip("."): swing_high - diff * r for r in ratios}


def ote_zone(swing_low: float, swing_high: float, bullish: bool = True) -> tuple[float, float]:
    """
    Optimal Trade Entry zone: 0.618 – 0.786 retracement.
    For bullish setups: discount zone after upward impulse.
    For bearish setups: premium zone after downward impulse.
    """
    diff = swing_high - swing_low
    if bullish:
        # Retrace from high toward low
        upper = swing_high - diff * 0.618
        lower = swing_high - diff * 0.786
        return min(lower, upper), max(lower, upper)
    # Bearish: retrace from low toward high
    lower = swing_low + diff * 0.618
    upper = swing_low + diff * 0.786
    return min(lower, upper), max(lower, upper)


def ema_trend_bias(ind: IndicatorBundle, price: float) -> str:
    """
    Determine trend from EMA stack.
    Only take buys above EMA200; sells below EMA200 unless reversal.
    """
    e200 = float(ind.ema200.iloc[-1])
    e50 = float(ind.ema50.iloc[-1])
    e20 = float(ind.ema20.iloc[-1])
    if price > e200 and e20 > e50 > e200:
        return "BULLISH"
    if price < e200 and e20 < e50 < e200:
        return "BEARISH"
    if price > e200:
        return "BULLISH_WEAK"
    if price < e200:
        return "BEARISH_WEAK"
    return "NEUTRAL"
