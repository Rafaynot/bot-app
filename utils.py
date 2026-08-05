"""
Shared utilities: logging setup, time helpers, price math, and enums.
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime, timezone
from enum import Enum
from functools import lru_cache
from typing import Any

import pytz
from dateutil import tz

from config import LOG_DIR


class Direction(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    WAIT = "WAIT"


class TrendBias(str, Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"


class StructureType(str, Enum):
    HH = "Higher High"
    HL = "Higher Low"
    LH = "Lower High"
    LL = "Lower Low"
    BOS = "BOS"
    CHOCH = "CHOCH"
    MSS = "MSS"
    RANGE = "Range"
    CONSOLIDATION = "Consolidation"
    EXPANSION = "Expansion"
    COMPRESSION = "Compression"
    TREND = "Trend"


class SessionName(str, Enum):
    ASIAN = "Asian"
    LONDON = "London"
    NEW_YORK = "New York"
    LONDON_NY_OVERLAP = "London/NY Overlap"
    OFF_HOURS = "Off Hours"


def setup_logging(level: str = "INFO") -> logging.Logger:
    """Configure root logger with console + rotating file handlers."""
    logger = logging.getLogger("xauusd")
    if logger.handlers:
        return logger

    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(fmt)
    logger.addHandler(console)

    log_file = LOG_DIR / "app.log"
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)

    return logger


@lru_cache(maxsize=1)
def get_logger() -> logging.Logger:
    return setup_logging()


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def to_ny_time(dt: datetime | None = None) -> datetime:
    """Convert to America/New_York (handles DST)."""
    ny = pytz.timezone("America/New_York")
    if dt is None:
        return datetime.now(ny)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(ny)


def to_london_time(dt: datetime | None = None) -> datetime:
    london = pytz.timezone("Europe/London")
    if dt is None:
        return datetime.now(london)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(london)


def format_price(price: float, digits: int = 2) -> str:
    return f"{price:.{digits}f}"


def pct_change(a: float, b: float) -> float:
    if a == 0:
        return 0.0
    return ((b - a) / a) * 100.0


def almost_equal(a: float, b: float, tol_pct: float = 0.05) -> bool:
    """True if prices are within tol_pct percent of each other."""
    mid = (abs(a) + abs(b)) / 2.0
    if mid == 0:
        return a == b
    return abs(a - b) / mid * 100.0 <= tol_pct


def safe_div(n: float, d: float, default: float = 0.0) -> float:
    return n / d if d else default


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def round_lot(lots: float, step: float = 0.01) -> float:
    if step <= 0:
        return lots
    return round(lots / step) * step


def serialize_reasons(reasons: list[str]) -> str:
    return " | ".join(reasons)


def as_dict(obj: Any) -> dict[str, Any]:
    """Best-effort conversion of dataclass / object to dict."""
    if hasattr(obj, "__dataclass_fields__"):
        from dataclasses import asdict

        return asdict(obj)
    if hasattr(obj, "__dict__"):
        return dict(obj.__dict__)
    return {"value": obj}


# Re-export tz for callers
UTC = timezone.utc
LOCAL_TZ = tz.tzlocal()
