"""
Market data providers: MetaTrader 5, Binance, and demo/synthetic feed.

Prefer MT5 for live XAUUSD. Binance is available for crypto testing.
Demo mode generates realistic OHLC for offline GUI development.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

import numpy as np
import pandas as pd

from config import CONFIG, BinanceConfig, DataSource, MT5Config, TimeFrame
from utils import get_logger, utc_now

logger = get_logger()

# MT5 timeframe constants mapped when MetaTrader5 is available
TF_MINUTES: dict[TimeFrame, int] = {
    TimeFrame.M1: 1,
    TimeFrame.M5: 5,
    TimeFrame.M15: 15,
    TimeFrame.M30: 30,
    TimeFrame.H1: 60,
    TimeFrame.H4: 240,
    TimeFrame.D1: 1440,
    TimeFrame.W1: 10080,
    TimeFrame.MN1: 43200,
}

BINANCE_INTERVAL: dict[TimeFrame, str] = {
    TimeFrame.M1: "1m",
    TimeFrame.M5: "5m",
    TimeFrame.M15: "15m",
    TimeFrame.M30: "30m",
    TimeFrame.H1: "1h",
    TimeFrame.H4: "4h",
    TimeFrame.D1: "1d",
    TimeFrame.W1: "1w",
    TimeFrame.MN1: "1M",
}


@dataclass
class TickQuote:
    """Latest bid/ask quote."""

    symbol: str
    bid: float
    ask: float
    time: datetime
    volume: float = 0.0

    @property
    def mid(self) -> float:
        return (self.bid + self.ask) / 2.0

    @property
    def spread(self) -> float:
        return self.ask - self.bid


@dataclass
class MarketSnapshot:
    """Multi-timeframe OHLCV bundle plus live quote."""

    symbol: str
    frames: dict[TimeFrame, pd.DataFrame] = field(default_factory=dict)
    quote: TickQuote | None = None
    source: DataSource = DataSource.DEMO
    fetched_at: datetime = field(default_factory=utc_now)


def normalize_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure standard column names and datetime index."""
    colmap = {
        "time": "time",
        "Open": "open",
        "High": "high",
        "Low": "low",
        "Close": "close",
        "Volume": "volume",
        "tick_volume": "volume",
        "real_volume": "real_volume",
        "open": "open",
        "high": "high",
        "low": "low",
        "close": "close",
        "volume": "volume",
    }
    renamed = {c: colmap[c] for c in df.columns if c in colmap}
    out = df.rename(columns=renamed).copy()
    required = ["open", "high", "low", "close"]
    for col in required:
        if col not in out.columns:
            raise ValueError(f"Missing column: {col}")
    if "volume" not in out.columns:
        out["volume"] = 0.0
    if "time" in out.columns:
        out["time"] = pd.to_datetime(out["time"], utc=True)
        out = out.set_index("time")
    out = out.sort_index()
    out = out[~out.index.duplicated(keep="last")]
    return out[["open", "high", "low", "close", "volume"]].astype(float)


class DataProvider(ABC):
    """Abstract market data interface."""

    @abstractmethod
    def connect(self) -> bool:
        ...

    @abstractmethod
    def disconnect(self) -> None:
        ...

    @abstractmethod
    def is_connected(self) -> bool:
        ...

    @abstractmethod
    def get_ohlcv(self, symbol: str, timeframe: TimeFrame, count: int) -> pd.DataFrame:
        ...

    @abstractmethod
    def get_quote(self, symbol: str) -> TickQuote:
        ...

    def fetch_snapshot(
        self,
        symbol: str,
        timeframes: tuple[TimeFrame, ...] | None = None,
        count: int | None = None,
    ) -> MarketSnapshot:
        tfs = timeframes or CONFIG.analysis_timeframes
        n = count or CONFIG.mt5.candles_per_tf
        frames: dict[TimeFrame, pd.DataFrame] = {}
        for tf in tfs:
            try:
                frames[tf] = self.get_ohlcv(symbol, tf, n)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to fetch %s %s: %s", symbol, tf.value, exc)
        quote = None
        try:
            quote = self.get_quote(symbol)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to fetch quote %s: %s", symbol, exc)
        return MarketSnapshot(
            symbol=symbol,
            frames=frames,
            quote=quote,
            source=CONFIG.data_source,
            fetched_at=utc_now(),
        )


class MT5Provider(DataProvider):
    """Live XAUUSD via MetaTrader 5 Python API."""

    def __init__(self, cfg: MT5Config | None = None) -> None:
        self.cfg = cfg or CONFIG.mt5
        self._mt5: Any = None
        self._connected = False
        self._resolved_symbol: str | None = None

    def connect(self) -> bool:
        try:
            import MetaTrader5 as mt5
        except ImportError:
            logger.error("MetaTrader5 package not installed. pip install MetaTrader5")
            return False

        self._mt5 = mt5
        kwargs: dict[str, Any] = {}
        if self.cfg.path:
            kwargs["path"] = self.cfg.path
        if self.cfg.login is not None:
            kwargs["login"] = self.cfg.login
        if self.cfg.password:
            kwargs["password"] = self.cfg.password
        if self.cfg.server:
            kwargs["server"] = self.cfg.server

        ok = mt5.initialize(**kwargs) if kwargs else mt5.initialize()
        if not ok:
            logger.error("MT5 initialize failed: %s", mt5.last_error())
            return False

        self._resolved_symbol = self._resolve_symbol(self.cfg.symbol)
        if self._resolved_symbol is None:
            logger.error("Could not resolve XAUUSD symbol on this broker")
            mt5.shutdown()
            return False

        mt5.symbol_select(self._resolved_symbol, True)
        self._connected = True
        logger.info("MT5 connected — symbol=%s", self._resolved_symbol)
        return True

    def _resolve_symbol(self, preferred: str) -> str | None:
        assert self._mt5 is not None
        for name in [preferred, *self.cfg.symbol_aliases]:
            info = self._mt5.symbol_info(name)
            if info is not None:
                return name
        # Fuzzy search
        symbols = self._mt5.symbols_get()
        if symbols:
            for s in symbols:
                if "XAU" in s.name.upper() and "USD" in s.name.upper():
                    return s.name
        return None

    def disconnect(self) -> None:
        if self._mt5 and self._connected:
            self._mt5.shutdown()
        self._connected = False

    def is_connected(self) -> bool:
        return self._connected and self._mt5 is not None

    def _tf_const(self, timeframe: TimeFrame) -> int:
        assert self._mt5 is not None
        mapping = {
            TimeFrame.M1: self._mt5.TIMEFRAME_M1,
            TimeFrame.M5: self._mt5.TIMEFRAME_M5,
            TimeFrame.M15: self._mt5.TIMEFRAME_M15,
            TimeFrame.M30: self._mt5.TIMEFRAME_M30,
            TimeFrame.H1: self._mt5.TIMEFRAME_H1,
            TimeFrame.H4: self._mt5.TIMEFRAME_H4,
            TimeFrame.D1: self._mt5.TIMEFRAME_D1,
            TimeFrame.W1: self._mt5.TIMEFRAME_W1,
            TimeFrame.MN1: self._mt5.TIMEFRAME_MN1,
        }
        return mapping[timeframe]

    def get_ohlcv(self, symbol: str, timeframe: TimeFrame, count: int) -> pd.DataFrame:
        if not self.is_connected():
            raise RuntimeError("MT5 not connected")
        sym = self._resolved_symbol or symbol
        rates = self._mt5.copy_rates_from_pos(sym, self._tf_const(timeframe), 0, count)
        if rates is None or len(rates) == 0:
            raise RuntimeError(f"No rates for {sym} {timeframe}: {self._mt5.last_error()}")
        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
        return normalize_ohlcv(df)

    def get_quote(self, symbol: str) -> TickQuote:
        if not self.is_connected():
            raise RuntimeError("MT5 not connected")
        sym = self._resolved_symbol or symbol
        tick = self._mt5.symbol_info_tick(sym)
        if tick is None:
            raise RuntimeError(f"No tick for {sym}")
        return TickQuote(
            symbol=sym,
            bid=float(tick.bid),
            ask=float(tick.ask),
            time=datetime.fromtimestamp(tick.time, tz=timezone.utc),
            volume=float(getattr(tick, "volume", 0) or 0),
        )


# Binance symbols that exist on USDT-M futures but not spot
BINANCE_FUTURES_SYMBOLS: frozenset[str] = frozenset({"XAUUSDT"})


class BinanceProvider(DataProvider):
    """Binance klines — spot or USDT-M futures (e.g. XAUUSDT gold perpetual)."""

    def __init__(self, cfg: BinanceConfig | None = None) -> None:
        self.cfg = cfg or CONFIG.binance
        self._session: Any = None
        self._connected = False
        self._resolve_market()

    def _resolve_market(self) -> None:
        sym = (self.cfg.symbol or "").upper()
        if sym in BINANCE_FUTURES_SYMBOLS:
            self.cfg.market = "futures"
            self.cfg.symbol = sym

    def _api_prefix(self) -> str:
        return "/fapi/v1" if self.cfg.market == "futures" else "/api/v3"

    def connect(self) -> bool:
        import requests

        self._resolve_market()
        self._session = requests.Session()
        try:
            r = self._session.get(f"{self.cfg.base_url}{self._api_prefix()}/ping", timeout=10)
            r.raise_for_status()
            self._connected = True
            logger.info(
                "Binance connected — market=%s symbol=%s",
                self.cfg.market,
                self.cfg.symbol,
            )
            return True
        except Exception as exc:  # noqa: BLE001
            logger.error("Binance connect failed: %s", exc)
            return False

    def disconnect(self) -> None:
        if self._session:
            self._session.close()
        self._connected = False

    def is_connected(self) -> bool:
        return self._connected

    def get_ohlcv(self, symbol: str, timeframe: TimeFrame, count: int) -> pd.DataFrame:
        if not self.is_connected():
            raise RuntimeError("Binance not connected")
        interval = BINANCE_INTERVAL[timeframe]
        params = {"symbol": symbol or self.cfg.symbol, "interval": interval, "limit": min(count, 1000)}
        r = self._session.get(
            f"{self.cfg.base_url}{self._api_prefix()}/klines",
            params=params,
            timeout=15,
        )
        r.raise_for_status()
        raw = r.json()
        rows = [
            {
                "time": datetime.fromtimestamp(k[0] / 1000, tz=timezone.utc),
                "open": float(k[1]),
                "high": float(k[2]),
                "low": float(k[3]),
                "close": float(k[4]),
                "volume": float(k[5]),
            }
            for k in raw
        ]
        return normalize_ohlcv(pd.DataFrame(rows))

    def get_quote(self, symbol: str) -> TickQuote:
        if not self.is_connected():
            raise RuntimeError("Binance not connected")
        sym = symbol or self.cfg.symbol
        r = self._session.get(
            f"{self.cfg.base_url}{self._api_prefix()}/ticker/bookTicker",
            params={"symbol": sym},
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()
        return TickQuote(
            symbol=sym,
            bid=float(data["bidPrice"]),
            ask=float(data["askPrice"]),
            time=utc_now(),
        )


class DemoProvider(DataProvider):
    """
    Synthetic XAUUSD-like random-walk OHLC for offline testing.
    Produces correlated multi-timeframe bars from a shared M1 seed.
    """

    def __init__(self, seed: int = 42, start_price: float = 2650.0) -> None:
        self.seed = seed
        self.start_price = start_price
        self._connected = False
        self._m1: pd.DataFrame | None = None
        self._rng = np.random.default_rng(seed)

    def connect(self) -> bool:
        self._rebuild()
        self._connected = True
        logger.info("Demo provider ready (synthetic XAUUSD)")
        return True

    def disconnect(self) -> None:
        self._connected = False

    def is_connected(self) -> bool:
        return self._connected

    def _rebuild(self) -> None:
        n = 60_000  # ~40 trading days of M1 — enough for D1/W1 aggregates
        now = utc_now().replace(second=0, microsecond=0)
        times = [now - timedelta(minutes=n - i) for i in range(n)]
        # Geometric Brownian motion with mild mean reversion
        rets = self._rng.normal(0.00002, 0.00035, size=n)
        prices = self.start_price * np.exp(np.cumsum(rets))
        # Intrabar noise
        highs = prices * (1 + np.abs(self._rng.normal(0, 0.00025, n)))
        lows = prices * (1 - np.abs(self._rng.normal(0, 0.00025, n)))
        opens = np.roll(prices, 1)
        opens[0] = self.start_price
        volumes = self._rng.integers(50, 500, size=n).astype(float)
        self._m1 = pd.DataFrame(
            {
                "open": opens,
                "high": np.maximum(highs, np.maximum(opens, prices)),
                "low": np.minimum(lows, np.minimum(opens, prices)),
                "close": prices,
                "volume": volumes,
            },
            index=pd.DatetimeIndex(times, tz="UTC"),
        )

    def _aggregate(self, minutes: int, count: int) -> pd.DataFrame:
        assert self._m1 is not None
        # Slight price drift each refresh so GUI looks live
        drift = 1.0 + float(self._rng.normal(0, 0.00005))
        df = self._m1.copy()
        df[["open", "high", "low", "close"]] *= drift
        rule = f"{minutes}min"
        if minutes >= 1440:
            # Daily+ use calendar rules
            rule_map = {1440: "1D", 10080: "1W", 43200: "MS"}
            rule = rule_map[minutes]
        ohlc = df.resample(rule).agg(
            {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
        ).dropna()
        return ohlc.tail(count)

    def get_ohlcv(self, symbol: str, timeframe: TimeFrame, count: int) -> pd.DataFrame:
        if not self.is_connected() or self._m1 is None:
            raise RuntimeError("Demo provider not connected")
        return self._aggregate(TF_MINUTES[timeframe], count)

    def get_quote(self, symbol: str) -> TickQuote:
        if self._m1 is None:
            raise RuntimeError("Demo provider not connected")
        # Advance last close slightly
        last = float(self._m1["close"].iloc[-1])
        noise = float(self._rng.normal(0, 0.15))
        mid = last + noise
        spread = 0.25
        return TickQuote(
            symbol=symbol,
            bid=mid - spread / 2,
            ask=mid + spread / 2,
            time=utc_now(),
            volume=float(self._rng.integers(10, 100)),
        )


class NewsCalendar:
    """
    Forex Factory economic calendar client.

    Uses the public JSON mirror (ff_calendar_thisweek.json). Falls back to
    an empty calendar if the network is unavailable.
    """

    def __init__(self) -> None:
        self._events: list[dict[str, Any]] = []
        self._last_fetch: float = 0.0
        self._cache_ttl = 300.0  # 5 minutes

    def refresh(self, force: bool = False) -> list[dict[str, Any]]:
        if not CONFIG.news.enabled:
            return []
        now = time.time()
        if not force and self._events and (now - self._last_fetch) < self._cache_ttl:
            return self._events
        try:
            import requests

            r = requests.get(CONFIG.news.calendar_url, timeout=15)
            r.raise_for_status()
            self._events = r.json()
            self._last_fetch = now
            logger.info("Loaded %d calendar events", len(self._events))
        except Exception as exc:  # noqa: BLE001
            logger.warning("News calendar fetch failed: %s", exc)
            if not self._events:
                self._events = []
        return self._events

    def is_news_blocked(self, when: datetime | None = None) -> tuple[bool, str]:
        """
        Return (blocked, reason) if high-impact USD news is imminent.
        """
        if not CONFIG.news.enabled:
            return False, "News filter disabled"
        events = self.refresh()
        when = when or utc_now()
        before = timedelta(minutes=CONFIG.news.block_minutes_before)
        after = timedelta(minutes=CONFIG.news.block_minutes_after)

        for ev in events:
            try:
                title = str(ev.get("title", ""))
                country = str(ev.get("country", "")).upper()
                impact = str(ev.get("impact", "")).lower()
                date_str = ev.get("date") or ev.get("dateUtc") or ""
                if country not in {c.upper() for c in CONFIG.news.currencies}:
                    continue
                if CONFIG.news.high_impact_only and impact not in {"high", "red"}:
                    # Still check keyword list for FOMC/CPI/NFP etc.
                    if not any(k.lower() in title.lower() for k in CONFIG.news.keywords):
                        continue
                else:
                    # High impact OR keyword match
                    keyword_hit = any(k.lower() in title.lower() for k in CONFIG.news.keywords)
                    if impact not in {"high", "red"} and not keyword_hit:
                        continue

                # Parse date — FF JSON often uses ISO with timezone offset
                event_dt = pd.to_datetime(date_str, utc=True).to_pydatetime()
                if when - before <= event_dt <= when + after:
                    return True, f"High-impact news: {title} @ {event_dt.isoformat()}"
            except Exception:  # noqa: BLE001
                continue
        return False, "Clear — no blocking USD news"

    def upcoming(self, limit: int = 5) -> list[dict[str, Any]]:
        events = self.refresh()
        now = utc_now()
        upcoming: list[tuple[datetime, dict[str, Any]]] = []
        for ev in events:
            try:
                date_str = ev.get("date") or ev.get("dateUtc") or ""
                event_dt = pd.to_datetime(date_str, utc=True).to_pydatetime()
                if event_dt >= now:
                    upcoming.append((event_dt, ev))
            except Exception:  # noqa: BLE001
                continue
        upcoming.sort(key=lambda x: x[0])
        return [e for _, e in upcoming[:limit]]


def create_provider(source: DataSource | None = None) -> DataProvider:
    """Factory — prefer MT5, fall back to demo on failure."""
    src = source or CONFIG.data_source
    if src == DataSource.MT5:
        provider: DataProvider = MT5Provider()
        if provider.connect():
            return provider
        logger.warning("MT5 unavailable — falling back to demo data")
        demo = DemoProvider()
        demo.connect()
        CONFIG.data_source = DataSource.DEMO
        return demo
    if src == DataSource.BINANCE:
        provider = BinanceProvider()
        if provider.connect():
            return provider
        logger.warning("Binance unavailable — falling back to demo data")
        demo = DemoProvider()
        demo.connect()
        CONFIG.data_source = DataSource.DEMO
        return demo
    demo = DemoProvider()
    demo.connect()
    return demo
