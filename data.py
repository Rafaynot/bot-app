"""
Market data providers: MetaTrader 5, Binance, and demo/synthetic feed.

Prefer MT5 for live XAUUSD. Binance is available for crypto testing.
Demo mode generates realistic OHLC for offline GUI development.
"""

from __future__ import annotations

import glob
import os
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


def find_mt5_terminal() -> str | None:
    """Locate terminal64.exe for MetaTrader 5 (broker installs vary)."""
    candidates: list[str] = []

    env_path = os.getenv("MT5_PATH")
    if env_path and os.path.isfile(env_path):
        return env_path

    candidates.extend(
        [
            r"C:\Program Files\MetaTrader 5\terminal64.exe",
            r"C:\Program Files (x86)\MetaTrader 5\terminal64.exe",
        ]
    )

    appdata = os.environ.get("APPDATA", "")
    if appdata:
        candidates.extend(
            glob.glob(os.path.join(appdata, "MetaQuotes", "Terminal", "*", "terminal64.exe"))
        )

    localappdata = os.environ.get("LOCALAPPDATA", "")
    if localappdata:
        candidates.extend(
            glob.glob(
                os.path.join(localappdata, "Programs", "**", "terminal64.exe"),
                recursive=True,
            )
        )

    seen: set[str] = set()
    for path in candidates:
        norm = os.path.normcase(os.path.abspath(path))
        if norm in seen or not os.path.isfile(path):
            continue
        seen.add(norm)
        return path
    return None


class MT5ConnectionError(RuntimeError):
    """Raised when live MT5 data cannot be reached."""


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
class BookLevel:
    """Single order-book price level."""

    price: float
    amount: float
    total: float = 0.0


@dataclass
class OrderBookSnapshot:
    """Bids (high→low) and asks (low→high) for the depth panel."""

    bids: list[BookLevel] = field(default_factory=list)
    asks: list[BookLevel] = field(default_factory=list)


def _with_cumulative(levels: list[BookLevel]) -> list[BookLevel]:
    running = 0.0
    out: list[BookLevel] = []
    for lvl in levels:
        running += lvl.amount
        out.append(BookLevel(price=lvl.price, amount=lvl.amount, total=running))
    return out


def synthetic_order_book(bid: float, ask: float, depth: int = 20, tick: float = 0.01) -> OrderBookSnapshot:
    """Ladder around the spread so the UI always has a Binance-style book."""
    rng = np.random.default_rng()
    asks: list[BookLevel] = []
    bids: list[BookLevel] = []
    for i in range(depth):
        asks.append(
            BookLevel(
                price=round(ask + (i + 1) * tick, 8),
                amount=float(max(0.01, rng.uniform(0.04, 1.6) * (1.0 + i * 0.04))),
            )
        )
        bids.append(
            BookLevel(
                price=round(bid - (i + 1) * tick, 8),
                amount=float(max(0.01, rng.uniform(0.04, 1.6) * (1.0 + i * 0.04))),
            )
        )
    return OrderBookSnapshot(
        bids=_with_cumulative(bids),
        asks=_with_cumulative(asks),
    )


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
    keep = ["open", "high", "low", "close", "volume"]
    for extra in ("taker_buy", "trades"):
        if extra in out.columns:
            keep.append(extra)
            out[extra] = out[extra].astype(float)
    return out[keep].astype({c: float for c in keep if c in out.columns})


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

    def get_order_book(self, symbol: str, depth: int = 20) -> OrderBookSnapshot:
        """Best-effort depth; falls back to a synthetic ladder from the quote."""
        quote = self.get_quote(symbol)
        tick = 0.01 if quote.mid < 50_000 else 0.01
        if quote.mid >= 10_000:
            tick = 0.01
        elif quote.mid >= 100:
            tick = 0.01
        else:
            tick = 0.0001
        return synthetic_order_book(quote.bid, quote.ask, depth, tick)

    def get_accuracy_feed(
        self,
        symbol: str,
        df: pd.DataFrame | None = None,
        book: OrderBookSnapshot | None = None,
    ) -> object:
        from accuracy import compute_ohlc_accuracy

        if df is None:
            try:
                df = self.get_ohlcv(symbol, TimeFrame.M5, 400)
            except Exception:  # noqa: BLE001
                df = pd.DataFrame()
        return compute_ohlc_accuracy(df, book)

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
        self.terminal_path: str | None = None

    def connect(self) -> bool:
        try:
            import MetaTrader5 as mt5
        except ImportError:
            logger.error("MetaTrader5 package not installed. pip install MetaTrader5")
            return False

        self._mt5 = mt5
        kwargs: dict[str, Any] = {}
        terminal_path = self.cfg.path
        if not terminal_path and self.cfg.auto_discover_path:
            terminal_path = find_mt5_terminal()
        if terminal_path:
            kwargs["path"] = terminal_path
            self.terminal_path = terminal_path
        if self.cfg.login is not None:
            kwargs["login"] = self.cfg.login
        if self.cfg.password:
            kwargs["password"] = self.cfg.password
        if self.cfg.server:
            kwargs["server"] = self.cfg.server

        ok = mt5.initialize(**kwargs) if kwargs else mt5.initialize()
        if not ok:
            err = mt5.last_error()
            if terminal_path:
                logger.error("MT5 initialize failed (%s): %s", terminal_path, err)
            else:
                logger.error(
                    "MT5 initialize failed: %s — install MetaTrader 5 and log in, "
                    "or set MT5_PATH / --mt5-path",
                    err,
                )
            return False

        self._resolved_symbol = self._resolve_symbol(self.cfg.symbol)
        if self._resolved_symbol is None:
            logger.error("Could not resolve XAUUSD symbol on this broker")
            mt5.shutdown()
            return False

        mt5.symbol_select(self._resolved_symbol, True)
        self._connected = True
        info = mt5.account_info()
        acct = f"{info.login}@{info.server}" if info else "unknown account"
        logger.info(
            "MT5 connected — symbol=%s account=%s terminal=%s",
            self._resolved_symbol,
            acct,
            terminal_path or "default",
        )
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

    def get_order_book(self, symbol: str, depth: int = 20) -> OrderBookSnapshot:
        if not self.is_connected():
            raise RuntimeError("MT5 not connected")
        sym = self._resolved_symbol or symbol
        try:
            self._mt5.market_book_add(sym)
            raw = self._mt5.market_book_get(sym)
        except Exception:  # noqa: BLE001
            raw = None
        if not raw:
            return super().get_order_book(symbol, depth)
        asks: list[BookLevel] = []
        bids: list[BookLevel] = []
        for item in raw:
            kind = int(item.type)
            price = float(item.price)
            amount = float(getattr(item, "volume_dbl", 0) or item.volume or 0)
            if kind in (1, 3):  # sell / sell market
                asks.append(BookLevel(price=price, amount=amount))
            elif kind in (2, 4):  # buy / buy market
                bids.append(BookLevel(price=price, amount=amount))
        asks.sort(key=lambda x: x.price)
        bids.sort(key=lambda x: x.price, reverse=True)
        if not asks or not bids:
            return super().get_order_book(symbol, depth)
        return OrderBookSnapshot(
            bids=_with_cumulative(bids[:depth]),
            asks=_with_cumulative(asks[:depth]),
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
                "taker_buy": float(k[9]) if len(k) > 9 else 0.0,
                "trades": float(k[8]) if len(k) > 8 else 0.0,
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

    def get_order_book(self, symbol: str, depth: int = 20) -> OrderBookSnapshot:
        if not self.is_connected():
            raise RuntimeError("Binance not connected")
        sym = symbol or self.cfg.symbol
        limit = 20 if depth <= 20 else 50 if depth <= 50 else 100
        try:
            r = self._session.get(
                f"{self.cfg.base_url}{self._api_prefix()}/depth",
                params={"symbol": sym, "limit": limit},
                timeout=10,
            )
            r.raise_for_status()
            data = r.json()
            asks = [
                BookLevel(price=float(p), amount=float(a))
                for p, a in data.get("asks", [])[:depth]
            ]
            bids = [
                BookLevel(price=float(p), amount=float(a))
                for p, a in data.get("bids", [])[:depth]
            ]
            if asks and bids:
                return OrderBookSnapshot(
                    bids=_with_cumulative(bids),
                    asks=_with_cumulative(asks),
                )
        except Exception as exc:  # noqa: BLE001
            logger.debug("Binance depth fallback: %s", exc)
        return super().get_order_book(symbol, depth)

    def _get_json(self, url: str, params: dict | None = None, timeout: int = 8) -> object | None:
        try:
            r = self._session.get(url, params=params or {}, timeout=timeout)
            r.raise_for_status()
            return r.json()
        except Exception as exc:  # noqa: BLE001
            logger.debug("Binance extra feed skip %s: %s", url, exc)
            return None

    def get_accuracy_feed(
        self,
        symbol: str,
        df: pd.DataFrame | None = None,
        book: OrderBookSnapshot | None = None,
    ) -> object:
        from accuracy import LiqCluster, compute_ohlc_accuracy

        sym = symbol or self.cfg.symbol
        feed = compute_ohlc_accuracy(df if df is not None else pd.DataFrame(), book)
        if self.cfg.market != "futures" or not self.is_connected():
            return feed
        feed.source = "binance-futures"
        prem = self._get_json(
            f"{self.cfg.futures_url}/fapi/v1/premiumIndex", {"symbol": sym}
        )
        if isinstance(prem, dict):
            try:
                feed.funding_rate = float(prem.get("lastFundingRate") or 0)
                feed.mark_price = float(prem.get("markPrice") or 0) or None
                nft = prem.get("nextFundingTime")
                if nft:
                    feed.next_funding_ts = datetime.fromtimestamp(int(nft) / 1000, tz=timezone.utc)
                feed.notes.append(f"Funding {feed.funding_rate * 100:.4f}%")
            except Exception:  # noqa: BLE001
                pass
        oi = self._get_json(f"{self.cfg.futures_url}/fapi/v1/openInterest", {"symbol": sym})
        hist = self._get_json(
            f"{self.cfg.futures_url}/futures/data/openInterestHist",
            {"symbol": sym, "period": "5m", "limit": 30},
        )
        if isinstance(oi, dict):
            try:
                feed.open_interest = float(oi.get("openInterest") or 0)
            except Exception:  # noqa: BLE001
                pass
        if isinstance(hist, list) and len(hist) >= 2:
            try:
                first = float(hist[0].get("sumOpenInterest") or 0)
                last = float(hist[-1].get("sumOpenInterest") or 0)
                if feed.open_interest is None:
                    feed.open_interest = last
                if first:
                    feed.oi_change_pct = (last - first) / first * 100.0
                    feed.notes.append(f"OI Δ {feed.oi_change_pct:+.2f}%")
            except Exception:  # noqa: BLE001
                pass
        lsr = self._get_json(
            f"{self.cfg.futures_url}/futures/data/globalLongShortAccountRatio",
            {"symbol": sym, "period": "5m", "limit": 1},
        )
        if isinstance(lsr, list) and lsr:
            try:
                feed.long_short_ratio = float(lsr[-1].get("longShortRatio") or 0)
            except Exception:  # noqa: BLE001
                pass
        taker = self._get_json(
            f"{self.cfg.futures_url}/futures/data/takerlongshortRatio",
            {"symbol": sym, "period": "5m", "limit": 12},
        )
        if isinstance(taker, list) and taker:
            try:
                last_ratio = float(taker[-1].get("buySellRatio") or 0)
                feed.taker_buy_sell = last_ratio or None
                if feed.taker_buy_sell:
                    feed.notes.append(f"Taker {feed.taker_buy_sell:.2f}")
            except Exception:  # noqa: BLE001
                pass
        force = self._get_json(
            f"{self.cfg.futures_url}/fapi/v1/allForceOrders",
            {"symbol": sym, "limit": 50},
        )
        if isinstance(force, list) and force:
            buckets: dict[float, float] = {}
            for item in force:
                try:
                    px = float(item.get("price") or item.get("avgPrice") or 0)
                    qty = float(item.get("origQty") or item.get("executedQty") or 0)
                    if px <= 0 or qty <= 0:
                        continue
                    key = round(px, 1)
                    buckets[key] = buckets.get(key, 0.0) + qty
                except Exception:  # noqa: BLE001
                    continue
            top = sorted(buckets.items(), key=lambda kv: kv[1], reverse=True)[:6]
            for px, qty in top:
                feed.clusters.append(
                    LiqCluster(price=px, volume=qty, side="liq", label="Liq")
                )
            feed.notes.append(f"{len(force)} liquidations clustered")
        return feed


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
        n = 10_000  # M1 bars — enough for top-down timeframes
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

            r = requests.get(CONFIG.news.calendar_url, timeout=3)
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
    """Connect market data provider. MT5 fails loudly unless demo fallback is enabled."""
    src = source or CONFIG.data_source
    if src == DataSource.MT5:
        provider: DataProvider = MT5Provider()
        if provider.connect():
            CONFIG.data_source = DataSource.MT5
            return provider
        if CONFIG.mt5_demo_fallback:
            logger.warning("MT5 unavailable — falling back to demo data")
            demo = DemoProvider()
            demo.connect()
            CONFIG.data_source = DataSource.DEMO
            return demo
        terminal = find_mt5_terminal()
        hint = (
            f"Found terminal: {terminal}" if terminal else "MetaTrader 5 terminal not found on this PC"
        )
        raise MT5ConnectionError(
            "Could not connect to MetaTrader 5 for live XAUUSD. "
            f"{hint}. Install MT5 from your broker, log in, enable XAUUSD in Market Watch, "
            "then run: python main.py --source mt5"
        )
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
    CONFIG.data_source = DataSource.DEMO
    return demo
