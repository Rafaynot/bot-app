"""
XAUUSD Technical Analysis Application
=====================================

Real-time multi-timeframe analysis with SMC / ICT confluence signals.
Does NOT execute trades — analysis and alerts only.

Usage:
    python main.py
    python main.py --source mt5
    python main.py --source demo
    python main.py --source binance
    python main.py --balance 5000 --telegram-token TOKEN --telegram-chat CHAT_ID
"""

from __future__ import annotations

import argparse
import sys

from config import CONFIG, DataSource, TradingMode, apply_trading_mode, load_env_overrides
from utils import setup_logging


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="XAUUSD Technical Analysis Signal Desk")
    p.add_argument(
        "--source",
        choices=["mt5", "binance", "demo"],
        default=None,
        help="Market data source (default: mt5 live, no demo fallback)",
    )
    p.add_argument(
        "--demo-fallback",
        action="store_true",
        help="If MT5 fails, use synthetic demo data instead of exiting",
    )
    p.add_argument("--symbol", default=None, help="Override symbol (e.g. XAUUSD, XAUUSDT, BTCUSDT)")
    p.add_argument(
        "--binance-market",
        choices=["spot", "futures"],
        default=None,
        help="Binance market type (XAUUSDT auto-uses futures)",
    )
    p.add_argument(
        "--mode",
        choices=["swing", "intraday", "scalp", "predict"],
        default=None,
        help="Trading profile: swing (default), intraday, or scalp",
    )
    p.add_argument("--balance", type=float, default=None, help="Account balance for lot sizing")
    p.add_argument("--risk", type=float, default=None, help="Max risk percent (default 1.0)")
    p.add_argument("--min-confidence", type=float, default=None, help="Signal threshold override")
    p.add_argument("--refresh", type=int, default=None, help="UI refresh interval ms override")
    p.add_argument("--telegram-token", default=None, help="Telegram bot token")
    p.add_argument("--telegram-chat", default=None, help="Telegram chat id")
    p.add_argument("--mt5-login", type=int, default=None)
    p.add_argument("--mt5-password", default=None)
    p.add_argument("--mt5-server", default=None)
    p.add_argument("--mt5-path", default=None, help="Path to terminal64.exe")
    p.add_argument("--web", action="store_true", help="Launch responsive Android/web server instead of PySide GUI")
    p.add_argument("--web-port", type=int, default=8000, help="Web server port (default 8000)")
    p.add_argument("--headless", action="store_true", help="Run one analysis cycle without GUI")
    p.add_argument("--log-level", default="INFO")
    return p.parse_args(argv)


def apply_args(args: argparse.Namespace) -> None:
    load_env_overrides()
    # Mode first so later flags (min-confidence, refresh) can override profile defaults
    if args.mode:
        apply_trading_mode(args.mode)
    if args.source:
        CONFIG.data_source = DataSource(args.source)
    if args.demo_fallback:
        CONFIG.mt5_demo_fallback = True
    elif args.source == "demo":
        CONFIG.mt5_demo_fallback = True
    if args.symbol:
        CONFIG.primary_symbol = args.symbol
        CONFIG.mt5.symbol = args.symbol
        CONFIG.binance.symbol = args.symbol
    if args.binance_market:
        CONFIG.binance.market = args.binance_market
    elif args.symbol and args.symbol.upper() == "XAUUSDT":
        CONFIG.binance.market = "futures"
    if args.balance is not None:
        CONFIG.risk.account_balance = args.balance
    if args.risk is not None:
        CONFIG.risk.max_risk_percent = args.risk
    if args.min_confidence is not None:
        CONFIG.signal.min_confidence = args.min_confidence
    if args.refresh is not None:
        CONFIG.ui.refresh_ms = args.refresh
    if args.telegram_token and args.telegram_chat:
        CONFIG.telegram.enabled = True
        CONFIG.telegram.bot_token = args.telegram_token
        CONFIG.telegram.chat_id = args.telegram_chat
    if args.mt5_login is not None:
        CONFIG.mt5.login = args.mt5_login
    if args.mt5_password:
        CONFIG.mt5.password = args.mt5_password
    if args.mt5_server:
        CONFIG.mt5.server = args.mt5_server
    if args.mt5_path:
        CONFIG.mt5.path = args.mt5_path
    CONFIG.log_level = args.log_level


def run_headless() -> int:
    """Single-shot analysis for CLI / CI testing."""
    from analysis import run_top_down
    from data import NewsCalendar, create_provider
    from database import SignalDatabase
    from signals import SignalEngine

    logger = setup_logging(CONFIG.log_level)
    provider = create_provider(CONFIG.data_source)
    engine = SignalEngine(NewsCalendar())
    db = SignalDatabase()

    symbol = CONFIG.primary_symbol
    if CONFIG.data_source == DataSource.BINANCE:
        symbol = CONFIG.binance.symbol

    logger.info("Fetching snapshot for %s via %s", symbol, CONFIG.data_source.value)
    snap = provider.fetch_snapshot(symbol)
    analysis = run_top_down(snap)
    signal = engine.generate(analysis)

    print("=" * 60)
    print(f"Symbol: {analysis.symbol}  Price: {analysis.price:.2f}")
    print(f"HTF Bias: {analysis.higher_tf_bias.value}")
    print(f"Timeframes analyzed: {len(analysis.frames)}")
    print("-" * 60)
    for line in signal.summary_lines():
        print(line)
    if signal.risk and signal.is_actionable:
        r = signal.risk
        print("-" * 60)
        print(f"Entry {r.entry} | SL {r.stop_loss} | TP1 {r.take_profit_1} | TP2 {r.take_profit_2} | TP3 {r.take_profit_3}")
        print(f"R:R 1:{r.risk_reward} | Lots {r.lot_size} | Risk {r.risk_percent}%")
        db.save_signal(signal)
    print("=" * 60)

    provider.disconnect()
    return 0


def is_android() -> bool:
    import os
    return "ANDROID_ARGUMENT" in os.environ or "PYTHON_SERVICE_ARGUMENT" in os.environ or "KIVY_BUILD" in os.environ


def main(argv: list[str] | None = None) -> int:
    if is_android():
        import android_main
        android_main.main()
        return 0

    args = parse_args(argv)
    apply_args(args)
    setup_logging(CONFIG.log_level)

    if args.headless:
        return run_headless()

    if args.web:
        from web_server import start_server

        return start_server(port=args.web_port)

    from dashboard import run_dashboard

    try:
        return run_dashboard()
    except Exception as exc:
        from data import MT5ConnectionError

        if isinstance(exc, MT5ConnectionError):
            print(f"MT5 connection failed:\n{exc}", file=sys.stderr)
            return 1
        raise


if __name__ == "__main__":
    sys.exit(main())
