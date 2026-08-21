"""
High-accuracy overlays: funding, open interest, CVD, liquidations, session H/L.

Binance USDT-M public endpoints when available; otherwise derived from OHLC + book.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

from config import CONFIG
from utils import Direction, get_logger, utc_now

logger = get_logger()


@dataclass
class LiqCluster:
    price: float
    volume: float
    side: str  # profile | bid | ask | liq
    label: str


@dataclass
class AccuracySnapshot:
    funding_rate: float | None = None
    next_funding_ts: datetime | None = None
    mark_price: float | None = None
    open_interest: float | None = None
    oi_change_pct: float | None = None
    long_short_ratio: float | None = None
    taker_buy_sell: float | None = None
    cvd: float | None = None
    cvd_delta: float | None = None
    asia_high: float | None = None
    asia_low: float | None = None
    london_high: float | None = None
    london_low: float | None = None
    ny_high: float | None = None
    ny_low: float | None = None
    clusters: list[LiqCluster] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    source: str = "ohlc"


def _session_hl(
    df: pd.DataFrame, start_hm: tuple[int, int], end_hm: tuple[int, int], now: datetime | None = None
) -> tuple[float | None, float | None]:
    if df is None or df.empty or not isinstance(df.index, pd.DatetimeIndex):
        return None, None
    now = now or utc_now()
    day = now.date()
    start = datetime.combine(day, datetime.min.time().replace(hour=start_hm[0], minute=start_hm[1]), tzinfo=timezone.utc)
    end = datetime.combine(day, datetime.min.time().replace(hour=end_hm[0], minute=end_hm[1]), tzinfo=timezone.utc)
    if end <= start:
        end += timedelta(days=1)
    mask = (df.index >= start) & (df.index < end)
    window = df.loc[mask]
    if window.empty:
        start -= timedelta(days=1)
        end -= timedelta(days=1)
        window = df.loc[(df.index >= start) & (df.index < end)]
    if window.empty:
        return None, None
    return float(window["high"].max()), float(window["low"].min())


def compute_cvd(df: pd.DataFrame) -> tuple[float | None, float | None]:
    if df is None or df.empty:
        return None, None
    if "taker_buy" in df.columns:
        delta = (2.0 * df["taker_buy"] - df["volume"]).astype(float)
    else:
        sign = np.sign(df["close"].diff().fillna(0.0))
        delta = sign * df["volume"].astype(float)
    cvd = delta.cumsum()
    last = float(cvd.iloc[-1])
    look = min(20, len(cvd))
    prev = float(cvd.iloc[-look])
    return last, last - prev


def volume_clusters(df: pd.DataFrame, bins: int = 36, top: int = 8) -> list[LiqCluster]:
    if df is None or len(df) < 20:
        return []
    px = (df["high"] + df["low"] + df["close"]) / 3.0
    vol = df["volume"].clip(lower=0.0)
    counts, edges = np.histogram(px.to_numpy(), bins=bins, weights=vol.to_numpy())
    mean = float(counts.mean()) if len(counts) else 0.0
    out: list[LiqCluster] = []
    for i in range(1, len(counts) - 1):
        if counts[i] >= counts[i - 1] and counts[i] >= counts[i + 1] and counts[i] > mean * 1.2:
            price = float(0.5 * (edges[i] + edges[i + 1]))
            out.append(LiqCluster(price=price, volume=float(counts[i]), side="profile", label="HVN"))
    out.sort(key=lambda c: c.volume, reverse=True)
    return out[:top]


def book_walls(book: object | None, multiple: float = 2.4) -> list[LiqCluster]:
    if book is None:
        return []
    bids = list(getattr(book, "bids", []) or [])
    asks = list(getattr(book, "asks", []) or [])
    amounts = [lvl.amount for lvl in bids + asks if getattr(lvl, "amount", 0) > 0]
    if not amounts:
        return []
    med = float(np.median(amounts))
    if med <= 0:
        return []
    out: list[LiqCluster] = []
    for lvl in bids:
        if lvl.amount >= med * multiple:
            out.append(LiqCluster(price=lvl.price, volume=lvl.amount, side="bid", label="Bid wall"))
    for lvl in asks:
        if lvl.amount >= med * multiple:
            out.append(LiqCluster(price=lvl.price, volume=lvl.amount, side="ask", label="Ask wall"))
    out.sort(key=lambda c: c.volume, reverse=True)
    return out[:8]


def compute_ohlc_accuracy(df: pd.DataFrame, book: object | None = None) -> AccuracySnapshot:
    feed = AccuracySnapshot(source="ohlc")
    if df is None or df.empty:
        return feed
    cvd, cvd_delta = compute_cvd(df)
    feed.cvd, feed.cvd_delta = cvd, cvd_delta
    feed.asia_high, feed.asia_low = _session_hl(df, CONFIG.session.asian_start, CONFIG.session.asian_end)
    feed.london_high, feed.london_low = _session_hl(df, (7, 0), (16, 0))
    feed.ny_high, feed.ny_low = _session_hl(df, (12, 0), (21, 0))
    clusters = volume_clusters(df) + book_walls(book)
    # de-dupe nearby prices
    merged: list[LiqCluster] = []
    for c in sorted(clusters, key=lambda x: x.price):
        if merged and abs(c.price - merged[-1].price) / max(c.price, 1e-9) < 0.0006:
            if c.volume > merged[-1].volume:
                merged[-1] = c
            continue
        merged.append(c)
    feed.clusters = merged[:10]
    if cvd_delta is not None:
        feed.notes.append("CVD " + ("buy" if cvd_delta > 0 else "sell") + " pressure")
    return feed


def score_accuracy(
    feed: AccuracySnapshot | None, direction: Direction, price: float, atr: float
) -> tuple[float, list[str], list[str], dict[str, bool]]:
    """Confirmation points (not a standalone entry)."""
    reasons: list[str] = []
    failed: list[str] = []
    feat: dict[str, bool] = {}
    if feed is None:
        return 0.0, reasons, failed, feat
    pts = 0.0
    buy = direction == Direction.BUY
    atr = max(atr, 1e-9)

    if feed.cvd_delta is not None:
        aligned = (feed.cvd_delta > 0) if buy else (feed.cvd_delta < 0)
        feat["CVD"] = aligned
        if aligned:
            pts += 6
            reasons.append("CVD " + ("buy" if buy else "sell") + " pressure")
        else:
            failed.append("CVD against trade")

    if feed.taker_buy_sell is not None:
        aligned = (feed.taker_buy_sell >= 1.05) if buy else (feed.taker_buy_sell <= 0.95)
        feat["Taker"] = aligned
        if aligned:
            pts += 5
            reasons.append(f"Taker buy/sell {feed.taker_buy_sell:.2f}")
        else:
            failed.append("Taker flow mixed")

    if feed.oi_change_pct is not None:
        # OI up with direction = new positions confirming
        aligned = (feed.oi_change_pct > 0.15 and buy) or (feed.oi_change_pct > 0.15 and not buy)
        # Rising OI is confirmation either side; falling OI = short covering / long unwind
        if feed.oi_change_pct > 0.15:
            pts += 4
            feat["OI"] = True
            reasons.append(f"OI rising {feed.oi_change_pct:+.2f}%")
        elif feed.oi_change_pct < -0.4:
            feat["OI"] = False
            failed.append(f"OI fading {feed.oi_change_pct:+.2f}%")
        else:
            feat["OI"] = True

    if feed.funding_rate is not None:
        # Positive funding = crowded longs. Helps SELL slightly; hurts BUY if extreme.
        fr = feed.funding_rate
        feat["Funding"] = True
        if buy and fr < 0:
            pts += 4
            reasons.append("Funding negative (shorts pay)")
        elif not buy and fr > 0:
            pts += 4
            reasons.append("Funding positive (longs crowded)")
        elif buy and fr > 0.0004:
            pts -= 3
            feat["Funding"] = False
            failed.append("Crowded longs (high funding)")
        elif not buy and fr < -0.0004:
            pts -= 3
            feat["Funding"] = False
            failed.append("Crowded shorts (negative funding)")

    if feed.long_short_ratio is not None:
        lsr = feed.long_short_ratio
        if buy and lsr < 0.9:
            pts += 3
            reasons.append(f"LS ratio {lsr:.2f} (short fuel)")
            feat["LS_Ratio"] = True
        elif not buy and lsr > 1.25:
            pts += 3
            reasons.append(f"LS ratio {lsr:.2f} (long fuel)")
            feat["LS_Ratio"] = True
        elif buy and lsr > 1.6:
            failed.append("Accounts very long")
            feat["LS_Ratio"] = False
        elif not buy and lsr < 0.7:
            failed.append("Accounts very short")
            feat["LS_Ratio"] = False

    sess_low = feed.london_low or feed.ny_low or feed.asia_low
    sess_high = feed.london_high or feed.ny_high or feed.asia_high
    if sess_low and buy and price >= sess_low:
        pts += 4
        feat["Session_HL"] = True
        reasons.append("Holding session low")
    elif sess_high and not buy and price <= sess_high:
        pts += 4
        feat["Session_HL"] = True
        reasons.append("Holding session high")
    elif sess_low and sess_high:
        feat["Session_HL"] = sess_low <= price <= sess_high

    magnet = None
    for c in feed.clusters:
        dist = c.price - price
        if buy and 0.15 * atr < dist < 2.2 * atr:
            magnet = c
            break
        if not buy and -2.2 * atr < dist < -0.15 * atr:
            magnet = c
            break
    if magnet:
        pts += 4
        feat["Liq_Magnet"] = True
        reasons.append(f"{magnet.label} magnet {magnet.price:.2f}")
    else:
        feat["Liq_Magnet"] = False

    return pts, reasons, failed, feat
