"""
Application configuration for XAUUSD Technical Analysis.

All tunable parameters live here so behaviour can be changed without
touching analysis logic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Final


class DataSource(str, Enum):
    """Supported market data providers."""

    MT5 = "mt5"
    BINANCE = "binance"
    DEMO = "demo"  # Synthetic data for offline testing


class TradingMode(str, Enum):
    """Strategy profile — swing keeps classic settings; scalp is LTF/fast."""

    SWING = "swing"
    SCALP = "scalp"


class TimeFrame(str, Enum):
    """Supported analysis timeframes (top-down order)."""

    MN1 = "MN1"
    W1 = "W1"
    D1 = "D1"
    H4 = "H4"
    H1 = "H1"
    M30 = "M30"
    M15 = "M15"
    M5 = "M5"
    M1 = "M1"


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT_DIR: Final[Path] = Path(__file__).resolve().parent
DATA_DIR: Final[Path] = ROOT_DIR / "data"
LOG_DIR: Final[Path] = ROOT_DIR / "logs"
SCREENSHOTS_DIR: Final[Path] = DATA_DIR / "screenshots"
DB_PATH: Final[Path] = DATA_DIR / "signals.db"
ALERT_SOUND_PATH: Final[Path] = ROOT_DIR / "assets" / "alert.wav"

DATA_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
(ROOT_DIR / "assets").mkdir(parents=True, exist_ok=True)


@dataclass
class MT5Config:
    """MetaTrader 5 connection settings."""

    symbol: str = "XAUUSD"
    # Common broker aliases — first match wins
    symbol_aliases: list[str] = field(
        default_factory=lambda: [
            "XAUUSD",
            "XAUUSDm",
            "XAUUSD.",
            "GOLD",
            "Gold",
            "XAUUSD.a",
        ]
    )
    login: int | None = None
    password: str | None = None
    server: str | None = None
    path: str | None = None  # Terminal path if not default
    auto_discover_path: bool = True
    candles_per_tf: int = 500


@dataclass
class BinanceConfig:
    """Binance spot / USDT-M futures API settings."""

    symbol: str = "BTCUSDT"
    # "spot" -> api.binance.com ; "futures" -> fapi.binance.com (e.g. XAUUSDT)
    market: str = "spot"
    spot_url: str = "https://api.binance.com"
    futures_url: str = "https://fapi.binance.com"
    candles_per_tf: int = 500

    @property
    def base_url(self) -> str:
        return self.futures_url if self.market == "futures" else self.spot_url


@dataclass
class TelegramConfig:
    """Telegram bot alert settings."""

    enabled: bool = False
    bot_token: str = ""
    chat_id: str = ""


@dataclass
class RiskConfig:
    """Risk management parameters."""

    max_risk_percent: float = 1.0
    min_risk_reward: float = 2.0
    atr_sl_multiplier: float = 1.5
    tp1_rr: float = 2.0
    tp2_rr: float = 3.0
    tp3_rr: float = 5.0
    account_balance: float = 10_000.0
    contract_size: float = 100.0  # Standard gold lot (ounces)
    point_value: float = 0.01  # Price point for XAUUSD


@dataclass
class SignalConfig:
    """Signal generation thresholds."""

    min_confidence: float = 85.0
    rsi_oversold: float = 35.0
    rsi_overbought: float = 65.0
    swing_lookback: int = 5
    equal_level_tolerance_pct: float = 0.05
    fvg_min_gap_atr: float = 0.1
    liquidity_sweep_lookback: int = 20
    ema_periods: tuple[int, int, int, int] = (20, 50, 100, 200)
    # Scalp-only gates
    scalp_require_killzone: bool = True
    scalp_max_spread_atr_frac: float = 0.25  # block if spread > frac * ATR stop distance
    scalp_require_m1_confirm: bool = True


@dataclass
class SessionConfig:
    """ICT session / kill-zone times (UTC)."""

    asian_start: tuple[int, int] = (0, 0)
    asian_end: tuple[int, int] = (8, 0)
    london_kz_start: tuple[int, int] = (7, 0)
    london_kz_end: tuple[int, int] = (10, 0)
    ny_kz_start: tuple[int, int] = (12, 0)
    ny_kz_end: tuple[int, int] = (15, 0)
    orb_minutes: int = 30


@dataclass
class NewsConfig:
    """Economic calendar / news filter."""

    enabled: bool = True
    calendar_url: str = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
    block_minutes_before: int = 30
    block_minutes_after: int = 30
    high_impact_only: bool = True
    currencies: tuple[str, ...] = ("USD",)
    keywords: tuple[str, ...] = (
        "FOMC",
        "CPI",
        "NFP",
        "Non-Farm",
        "Nonfarm",
        "Interest Rate",
        "Fed",
        "Federal Funds",
        "Core CPI",
        "Payroll",
    )


@dataclass
class UIConfig:
    """Dashboard refresh and display settings."""

    refresh_ms: int = 1000
    chart_candles: int = 150
    dark_theme: bool = True
    window_width: int = 1440
    window_height: int = 900
    chart_timeframe: TimeFrame = TimeFrame.M15
    screenshot_on_signal: bool = True


@dataclass
class AppConfig:
    """Root application configuration."""

    data_source: DataSource = DataSource.MT5
    # When False, MT5 connection failure raises instead of falling back to demo.
    mt5_demo_fallback: bool = False
    trading_mode: TradingMode = TradingMode.SWING
    primary_symbol: str = "XAUUSD"
    analysis_timeframes: tuple[TimeFrame, ...] = tuple(TimeFrame)
    # HTF stack used for bias alignment (swing uses monthly→H4)
    htf_timeframes: tuple[TimeFrame, ...] = (
        TimeFrame.MN1,
        TimeFrame.W1,
        TimeFrame.D1,
        TimeFrame.H4,
    )
    entry_timeframe: TimeFrame = TimeFrame.M15
    confirm_timeframe: TimeFrame | None = None  # e.g. M1 confirm for scalp M5 entries
    mt5: MT5Config = field(default_factory=MT5Config)
    binance: BinanceConfig = field(default_factory=BinanceConfig)
    telegram: TelegramConfig = field(default_factory=TelegramConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    signal: SignalConfig = field(default_factory=SignalConfig)
    session: SessionConfig = field(default_factory=SessionConfig)
    news: NewsConfig = field(default_factory=NewsConfig)
    ui: UIConfig = field(default_factory=UIConfig)
    log_level: str = "INFO"


# Singleton default config — import and mutate as needed
CONFIG = AppConfig()


def load_env_overrides() -> None:
    """Apply MT5 / Telegram credentials from environment variables."""
    import os

    login = os.getenv("MT5_LOGIN")
    if login:
        CONFIG.mt5.login = int(login)
    password = os.getenv("MT5_PASSWORD")
    if password:
        CONFIG.mt5.password = password
    server = os.getenv("MT5_SERVER")
    if server:
        CONFIG.mt5.server = server
    path = os.getenv("MT5_PATH")
    if path:
        CONFIG.mt5.path = path
    symbol = os.getenv("MT5_SYMBOL")
    if symbol:
        CONFIG.mt5.symbol = symbol
        CONFIG.primary_symbol = symbol
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat = os.getenv("TELEGRAM_CHAT_ID")
    if token and chat:
        CONFIG.telegram.enabled = True
        CONFIG.telegram.bot_token = token
        CONFIG.telegram.chat_id = chat


def apply_trading_mode(mode: TradingMode | str) -> None:
    """
    Switch Swing / Scalp profile.

    Swing restores the classic desk settings (unchanged behaviour).
    Scalp uses lower TFs, tighter stops, faster refresh, lower R:R.
    """
    mode = TradingMode(mode)
    CONFIG.trading_mode = mode

    if mode == TradingMode.SWING:
        CONFIG.analysis_timeframes = tuple(TimeFrame)
        CONFIG.htf_timeframes = (
            TimeFrame.MN1,
            TimeFrame.W1,
            TimeFrame.D1,
            TimeFrame.H4,
        )
        CONFIG.entry_timeframe = TimeFrame.M15
        CONFIG.confirm_timeframe = None
        CONFIG.ui.chart_timeframe = TimeFrame.M15
        CONFIG.ui.refresh_ms = 1000
        CONFIG.ui.chart_candles = 150
        CONFIG.risk.min_risk_reward = 2.0
        CONFIG.risk.atr_sl_multiplier = 1.5
        CONFIG.risk.tp1_rr = 2.0
        CONFIG.risk.tp2_rr = 3.0
        CONFIG.risk.tp3_rr = 5.0
        CONFIG.signal.min_confidence = 85.0
        CONFIG.signal.swing_lookback = 5
        CONFIG.signal.liquidity_sweep_lookback = 20
        CONFIG.signal.rsi_oversold = 35.0
        CONFIG.signal.rsi_overbought = 65.0
        CONFIG.signal.scalp_require_killzone = False
        CONFIG.signal.scalp_require_m1_confirm = False
        CONFIG.news.block_minutes_before = 30
        CONFIG.news.block_minutes_after = 30
    else:  # SCALP
        CONFIG.analysis_timeframes = (
            TimeFrame.H1,
            TimeFrame.M30,
            TimeFrame.M15,
            TimeFrame.M5,
            TimeFrame.M1,
        )
        CONFIG.htf_timeframes = (TimeFrame.H1, TimeFrame.M15)
        CONFIG.entry_timeframe = TimeFrame.M5
        CONFIG.confirm_timeframe = TimeFrame.M1
        CONFIG.ui.chart_timeframe = TimeFrame.M5
        CONFIG.ui.refresh_ms = 500
        CONFIG.ui.chart_candles = 120
        CONFIG.risk.min_risk_reward = 1.2
        CONFIG.risk.atr_sl_multiplier = 0.8
        CONFIG.risk.tp1_rr = 1.2
        CONFIG.risk.tp2_rr = 1.8
        CONFIG.risk.tp3_rr = 2.5
        CONFIG.signal.min_confidence = 85.0
        CONFIG.signal.swing_lookback = 3
        CONFIG.signal.liquidity_sweep_lookback = 12
        CONFIG.signal.rsi_oversold = 40.0
        CONFIG.signal.rsi_overbought = 60.0
        CONFIG.signal.scalp_require_killzone = True
        CONFIG.signal.scalp_require_m1_confirm = True
        CONFIG.signal.scalp_max_spread_atr_frac = 0.25
        CONFIG.news.block_minutes_before = 15
        CONFIG.news.block_minutes_after = 15

