"""
ICT concepts: sessions, Judas Swing, Power of Three / AMD, ORB, SMT, OTE.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time, timedelta, timezone

import pandas as pd

from config import CONFIG
from indicators import ote_zone
from utils import SessionName, utc_now


@dataclass
class SessionInfo:
    name: SessionName
    in_london_kz: bool = False
    in_ny_kz: bool = False
    asian_high: float | None = None
    asian_low: float | None = None
    orb_high: float | None = None
    orb_low: float | None = None
    orb_broken_up: bool = False
    orb_broken_down: bool = False


@dataclass
class ICTResult:
    session: SessionInfo
    judas_swing_bullish: bool = False
    judas_swing_bearish: bool = False
    amd_phase: str = "Unknown"  # Accumulation | Manipulation | Distribution
    power_of_three: str = "Neutral"
    ote_active_bullish: bool = False
    ote_active_bearish: bool = False
    ote_low: float | None = None
    ote_high: float | None = None
    smt_bullish: bool = False
    smt_bearish: bool = False
    notes: list[str] = field(default_factory=list)


def _hm(h: int, m: int) -> time:
    return time(h, m)


def current_session(now: datetime | None = None) -> SessionName:
    now = now or utc_now()
    t = now.timetz().replace(tzinfo=None) if now.tzinfo else now.time()
    # Rough UTC session map
    if _hm(0, 0) <= t < _hm(7, 0):
        return SessionName.ASIAN
    if _hm(7, 0) <= t < _hm(12, 0):
        return SessionName.LONDON
    if _hm(12, 0) <= t < _hm(16, 0):
        return SessionName.LONDON_NY_OVERLAP
    if _hm(16, 0) <= t < _hm(21, 0):
        return SessionName.NEW_YORK
    return SessionName.OFF_HOURS


def in_kill_zone(now: datetime | None = None) -> tuple[bool, bool]:
    cfg = CONFIG.session
    now = now or utc_now()
    t = now.time().replace(tzinfo=None) if hasattr(now.time(), "tzinfo") else now.time()
    # Strip tz
    t = time(now.hour, now.minute)

    def between(start: tuple[int, int], end: tuple[int, int]) -> bool:
        return _hm(*start) <= t < _hm(*end)

    london = between(cfg.london_kz_start, cfg.london_kz_end)
    ny = between(cfg.ny_kz_start, cfg.ny_kz_end)
    return london, ny


def asian_range(df: pd.DataFrame, now: datetime | None = None) -> tuple[float | None, float | None]:
    """High/low of Asian session for the current trading day (UTC)."""
    if df.empty or not isinstance(df.index, pd.DatetimeIndex):
        return None, None
    now = now or utc_now()
    day = now.date()
    start = datetime.combine(day, _hm(*CONFIG.session.asian_start), tzinfo=timezone.utc)
    end = datetime.combine(day, _hm(*CONFIG.session.asian_end), tzinfo=timezone.utc)
    mask = (df.index >= start) & (df.index < end)
    window = df.loc[mask]
    if window.empty:
        # Previous day fallback
        start -= timedelta(days=1)
        end -= timedelta(days=1)
        mask = (df.index >= start) & (df.index < end)
        window = df.loc[mask]
    if window.empty:
        return None, None
    return float(window["high"].max()), float(window["low"].min())


def opening_range(
    df: pd.DataFrame, session_open: time, minutes: int | None = None, now: datetime | None = None
) -> tuple[float | None, float | None, bool, bool]:
    """ORB high/low and whether price has broken either side."""
    if df.empty or not isinstance(df.index, pd.DatetimeIndex):
        return None, None, False, False
    now = now or utc_now()
    mins = minutes or CONFIG.session.orb_minutes
    day = now.date()
    start = datetime.combine(day, session_open, tzinfo=timezone.utc)
    end = start + timedelta(minutes=mins)
    window = df.loc[(df.index >= start) & (df.index < end)]
    if window.empty:
        return None, None, False, False
    hi, lo = float(window["high"].max()), float(window["low"].min())
    after = df.loc[df.index >= end]
    broken_up = bool(len(after) and after["close"].iloc[-1] > hi)
    broken_down = bool(len(after) and after["close"].iloc[-1] < lo)
    return hi, lo, broken_up, broken_down


def detect_judas_swing(
    df: pd.DataFrame, asian_high: float | None, asian_low: float | None, now: datetime | None = None
) -> tuple[bool, bool]:
    """
    Judas Swing: false move at London open against intended direction —
    sweep Asian high then reverse down (bearish), or sweep Asian low then reverse up (bullish).
    """
    if asian_high is None or asian_low is None or df.empty:
        return False, False
    now = now or utc_now()
    london, _ = in_kill_zone(now)
    if not london and current_session(now) not in {SessionName.LONDON, SessionName.LONDON_NY_OVERLAP}:
        # Still detect on today's London window bars
        pass

    day = now.date()
    start = datetime.combine(day, _hm(*CONFIG.session.london_kz_start), tzinfo=timezone.utc)
    end = datetime.combine(day, _hm(11, 0), tzinfo=timezone.utc)
    window = df.loc[(df.index >= start) & (df.index <= end)]
    if window.empty:
        return False, False

    swept_high = bool(window["high"].max() > asian_high)
    swept_low = bool(window["low"].min() < asian_low)
    last = float(window["close"].iloc[-1])
    bullish = swept_low and last > asian_low and last > (asian_high + asian_low) / 2
    bearish = swept_high and last < asian_high and last < (asian_high + asian_low) / 2
    return bullish, bearish


def detect_amd(df: pd.DataFrame) -> tuple[str, str]:
    """
    AMD / Power of Three: Accumulation → Manipulation → Distribution.
    Heuristic based on overnight range, morning sweep, then directional expansion.
    """
    if len(df) < 50:
        return "Unknown", "Neutral"
    recent = df.iloc[-48:]  # ~12h on M15
    atr = float((recent["high"] - recent["low"]).mean())
    first = recent.iloc[:16]
    mid = recent.iloc[16:32]
    last = recent.iloc[32:]
    first_range = float(first["high"].max() - first["low"].min())
    mid_ext = float(max(mid["high"].max() - first["high"].max(), first["low"].min() - mid["low"].min()))
    last_move = float(last["close"].iloc[-1] - mid["close"].iloc[0])

    if first_range < 1.2 * atr and mid_ext > 0.8 * atr:
        if last_move > atr:
            return "Distribution", "Bullish Po3"
        if last_move < -atr:
            return "Distribution", "Bearish Po3"
        return "Manipulation", "Neutral"
    if first_range < atr:
        return "Accumulation", "Neutral"
    if abs(last_move) > 1.5 * atr:
        return "Distribution", "Bullish Po3" if last_move > 0 else "Bearish Po3"
    return "Accumulation", "Neutral"


def detect_smt(
    primary: pd.DataFrame, correlated: pd.DataFrame | None
) -> tuple[bool, bool]:
    """
    SMT Divergence: primary makes new low while correlated does not (bullish),
    or primary new high while correlated does not (bearish).
    Without a correlated series, returns False.
    """
    if correlated is None or len(primary) < 20 or len(correlated) < 20:
        return False, False
    p = primary.iloc[-20:]
    c = correlated.iloc[-20:]
    # Align lengths
    n = min(len(p), len(c))
    p, c = p.iloc[-n:], c.iloc[-n:]
    p_new_low = float(p["low"].iloc[-1]) <= float(p["low"].iloc[:-1].min())
    c_new_low = float(c["low"].iloc[-1]) <= float(c["low"].iloc[:-1].min())
    p_new_high = float(p["high"].iloc[-1]) >= float(p["high"].iloc[:-1].max())
    c_new_high = float(c["high"].iloc[-1]) >= float(c["high"].iloc[:-1].max())
    bullish = p_new_low and not c_new_low
    bearish = p_new_high and not c_new_high
    return bullish, bearish


def analyze_ict(
    df: pd.DataFrame,
    swing_low: float | None = None,
    swing_high: float | None = None,
    correlated: pd.DataFrame | None = None,
    now: datetime | None = None,
) -> ICTResult:
    now = now or utc_now()
    london_kz, ny_kz = in_kill_zone(now)
    a_hi, a_lo = asian_range(df, now)
    orb_hi, orb_lo, orb_up, orb_dn = opening_range(df, _hm(7, 0), now=now)
    judas_b, judas_s = detect_judas_swing(df, a_hi, a_lo, now)
    amd, po3 = detect_amd(df)
    smt_b, smt_s = detect_smt(df, correlated)

    session = SessionInfo(
        name=current_session(now),
        in_london_kz=london_kz,
        in_ny_kz=ny_kz,
        asian_high=a_hi,
        asian_low=a_lo,
        orb_high=orb_hi,
        orb_low=orb_lo,
        orb_broken_up=orb_up,
        orb_broken_down=orb_dn,
    )
    result = ICTResult(session=session, amd_phase=amd, power_of_three=po3)
    result.judas_swing_bullish = judas_b
    result.judas_swing_bearish = judas_s
    result.smt_bullish = smt_b
    result.smt_bearish = smt_s

    price = float(df["close"].iloc[-1])
    if swing_low is not None and swing_high is not None and swing_high > swing_low:
        ote_lo, ote_hi = ote_zone(swing_low, swing_high, bullish=True)
        result.ote_low, result.ote_high = ote_lo, ote_hi
        result.ote_active_bullish = ote_lo <= price <= ote_hi
        ote_lo_b, ote_hi_b = ote_zone(swing_low, swing_high, bullish=False)
        result.ote_active_bearish = ote_lo_b <= price <= ote_hi_b

    notes: list[str] = []
    if london_kz:
        notes.append("London Kill Zone active")
    if ny_kz:
        notes.append("New York Kill Zone active")
    if judas_b:
        notes.append("Bullish Judas Swing detected")
    if judas_s:
        notes.append("Bearish Judas Swing detected")
    if orb_up:
        notes.append("Opening Range broken upward")
    if orb_dn:
        notes.append("Opening Range broken downward")
    if result.ote_active_bullish:
        notes.append("Price in bullish OTE (0.618–0.786)")
    if result.ote_active_bearish:
        notes.append("Price in bearish OTE (0.618–0.786)")
    result.notes = notes
    return result
