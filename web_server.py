"""
XAUUSD Signal Desk Pro — Mobile Android & Web Server
=====================================================

Serves the responsive Android PWA and REST API endpoints.
Runs real-time multi-timeframe SMC / ICT market analysis on background worker.

Usage:
    python web_server.py
    python web_server.py --port 8000 --source mt5
    python web_server.py --source demo
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import socket
import sys
import threading
import time
from datetime import datetime
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pandas as pd

from alerts import AlertManager
from analysis import TopDownAnalysis, run_top_down
from config import CONFIG, DataSource, TimeFrame, TradingMode, apply_trading_mode, load_env_overrides
from data import DataProvider, MarketSnapshot, NewsCalendar, create_provider, synthetic_order_book
from database import SignalDatabase, resolve_pending_outcomes
from indicators import sma
from learning import LEARNER
from prediction import MarketForecast, build_forecast
from signals import SignalEngine, TradeSignal
from utils import Direction, get_logger, setup_logging, utc_now

logger = get_logger()

WEB_DIR = Path(__file__).resolve().parent / "web"


def get_local_ip() -> str:
    """Detect local LAN IP for Android phone connection."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def _market_stats(analysis: TopDownAnalysis) -> dict[str, float]:
    snap: MarketSnapshot | None = getattr(analysis, "_snapshot", None)
    if snap:
        if TimeFrame.D1 in snap.frames and snap.frames[TimeFrame.D1] is not None and not snap.frames[TimeFrame.D1].empty:
            d_candle = snap.frames[TimeFrame.D1].iloc[-1]
            d_open = float(d_candle["open"])
            d_high = max(float(d_candle["high"]), float(analysis.price))
            d_low = min(float(d_candle["low"]), float(analysis.price))
            d_last = float(analysis.price)
            d_vol = float(d_candle["volume"])
            d_chg = d_last - d_open
            d_pct = (d_chg / d_open * 100.0) if d_open else 0.0
            return {
                "last": d_last,
                "change": d_chg,
                "pct": d_pct,
                "high": d_high,
                "low": d_low,
                "vol_base": d_vol,
                "vol_quote": d_vol * d_last,
            }

        for tf in (TimeFrame.H1, TimeFrame.H4, TimeFrame.M15, TimeFrame.M5, TimeFrame.M1):
            if tf in snap.frames and snap.frames[tf] is not None and not snap.frames[tf].empty:
                df = snap.frames[tf]
                cutoff = df.index[-1] - pd.Timedelta(hours=24)
                window = df[df.index >= cutoff]
                if window.empty:
                    window = df.tail(min(len(df), 24))
                open_p = float(window["open"].iloc[0])
                high = max(float(window["high"].max()), float(analysis.price))
                low = min(float(window["low"].min()), float(analysis.price))
                last = float(analysis.price)
                vol = float(window["volume"].sum())
                change = last - open_p
                pct = (change / open_p) * 100.0 if open_p else 0.0
                return {
                    "last": last,
                    "change": change,
                    "pct": pct,
                    "high": high,
                    "low": low,
                    "vol_base": vol,
                    "vol_quote": vol * last,
                }

    return {
        "last": float(analysis.price),
        "change": 0.0,
        "pct": 0.0,
        "high": float(analysis.price),
        "low": float(analysis.price),
        "vol_base": 0.0,
        "vol_quote": 0.0,
    }


class MarketStateHolder:
    """Thread-safe in-memory cache of live market analysis & signals."""

    def __init__(self, provider: DataProvider, engine: SignalEngine, db: SignalDatabase) -> None:
        self.provider = provider
        self.engine = engine
        self.db = db
        self.alerts = AlertManager()
        self.lock = threading.Lock()

        self.last_analysis: TopDownAnalysis | None = None
        self.last_signal: TradeSignal | None = None
        self.last_chart_tf: TimeFrame = TimeFrame.M15
        self.last_chart_view: str = "original"
        self.last_fingerprint: str = ""
        self.status: str = "Starting"
        self.error_msg: str = ""
        self.running: bool = True

    def update_cycle(self) -> None:
        symbol = (
            CONFIG.mt5.symbol
            if CONFIG.data_source.value == "mt5"
            else CONFIG.binance.symbol
            if CONFIG.data_source.value == "binance"
            else CONFIG.primary_symbol
        )
        if CONFIG.data_source.value != "binance":
            symbol = CONFIG.primary_symbol
            if hasattr(self.provider, "_resolved_symbol") and self.provider._resolved_symbol:
                symbol = self.provider._resolved_symbol

        try:
            snap: MarketSnapshot = self.provider.fetch_snapshot(symbol)
            chart_tf = CONFIG.ui.chart_timeframe
            if chart_tf not in snap.frames:
                try:
                    snap.frames[chart_tf] = self.provider.get_ohlcv(
                        symbol, chart_tf, CONFIG.ui.chart_candles
                    )
                except Exception as exc:
                    logger.debug("Extra chart TF fetch skipped: %s", exc)

            analysis = run_top_down(snap)

            book = None
            try:
                book = self.provider.get_order_book(symbol)
            except Exception as exc:
                logger.debug("Order book skipped: %s", exc)

            acc_df = None
            for tf in (TimeFrame.M5, TimeFrame.M15, TimeFrame.H1, TimeFrame.M1):
                if tf in snap.frames and snap.frames[tf] is not None and not snap.frames[tf].empty:
                    acc_df = snap.frames[tf]
                    break

            try:
                acc = self.provider.get_accuracy_feed(symbol, acc_df, book)
            except Exception as exc:
                logger.debug("Accuracy feed skipped: %s", exc)
                acc = None

            analysis._snapshot = snap
            analysis._order_book = book
            analysis._accuracy = acc
            analysis._forecast = build_forecast(analysis)

            signal = self.engine.generate(analysis)

            # Resolve outcomes in database
            try:
                resolve_pending_outcomes(self.db, analysis.price, LEARNER)
            except Exception:
                pass

            # Save & notify actionable signals
            if signal.is_actionable:
                fp = f"{signal.mode}:{signal.direction.value}:{round(signal.price, 1)}:{int(signal.confidence)}"
                if fp != self.last_fingerprint:
                    self.db.save_signal(signal)
                    self.last_fingerprint = fp
                    self.alerts.maybe_alert(signal)

            with self.lock:
                self.last_analysis = analysis
                self.last_signal = signal
                self.status = "ok"
                self.error_msg = ""
        except Exception as exc:
            with self.lock:
                self.status = "error"
                self.error_msg = str(exc)
            logger.warning("Market analysis cycle error: %s", exc)

    def set_timeframe(self, tf_str: str) -> None:
        with self.lock:
            try:
                self.last_chart_tf = TimeFrame(tf_str)
            except Exception:
                pass

    def set_view(self, view_str: str) -> None:
        with self.lock:
            self.last_chart_view = view_str

    def set_mode(self, mode_str: str) -> None:
        apply_trading_mode(mode_str)
        with self.lock:
            if self.last_analysis is not None:
                self.last_signal = self.engine.generate(self.last_analysis)

    def build_state_json(self) -> dict:
        with self.lock:
            analysis = self.last_analysis
            signal = self.last_signal
            tf = self.last_chart_tf
            view = self.last_chart_view
            status = self.status

        if analysis is None or signal is None:
            return {
                "ok": False,
                "status": status,
                "msg": self.error_msg or "Gathering market data...",
                "pair": CONFIG.primary_symbol,
                "source": CONFIG.data_source.value,
                "mode": CONFIG.trading_mode.value,
                "tf": tf.value,
            }

        # Format stats using true 24h market stats
        snap: MarketSnapshot | None = getattr(analysis, "_snapshot", None)
        df = snap.frames.get(tf) if (snap and tf in snap.frames) else None
        stats_24h = _market_stats(analysis)

        # Build chart payload
        chart_data = self._build_chart_payload(analysis, signal, tf, view, df)

        # Build order book
        ob = getattr(analysis, "_order_book", None)
        if ob is None:
            ob = synthetic_order_book(analysis.price, analysis.price, 20, 0.01)

        book_data = {
            "bids": [{"p": float(b.price), "a": float(getattr(b, "amount", 0.0)), "t": float(getattr(b, "total", 0.0))} for b in ob.bids[:10]],
            "asks": [{"p": float(a.price), "a": float(getattr(a, "amount", 0.0)), "t": float(getattr(a, "total", 0.0))} for a in ob.asks[:10]],
        }

        # Multi-timeframe summary
        mtf_rows = []
        for tf_item, an in analysis.frames.items():
            rsi_val = float(an.indicators.rsi.iloc[-1]) if not an.indicators.rsi.empty else 50.0
            macd_val = float(an.indicators.macd.iloc[-1]) if not an.indicators.macd.empty else 0.0
            smc_tag = "OB active" if an.smc.order_blocks else ("FVG" if an.smc.fvgs else "Range")
            last_event = an.smc.structure_events[-1].event_type.value if an.smc.structure_events else an.trend.value
            mtf_rows.append({
                "tf": tf_item.value,
                "trend": an.ema_bias or an.trend.value,
                "structure": last_event,
                "rsi": rsi_val,
                "macd": macd_val,
                "smc": smc_tag,
            })

        # ICT Summary
        ict_res = analysis.frames[TimeFrame.M15].ict if TimeFrame.M15 in analysis.frames else None
        is_kz = bool(ict_res.session.in_london_kz or ict_res.session.in_ny_kz) if ict_res else False
        ict_data = {
            "session": ict_res.session.name.value if ict_res else "—",
            "killzone": "Active KZ" if is_kz else "Outside KZ",
            "asia_high": float(ict_res.session.asian_high) if (ict_res and ict_res.session.asian_high is not None) else None,
            "asia_low": float(ict_res.session.asian_low) if (ict_res and ict_res.session.asian_low is not None) else None,
        }

        # SMC Summary
        smc_m15 = analysis.frames[TimeFrame.M15].smc if TimeFrame.M15 in analysis.frames else None
        sweeps_count = len([l for l in smc_m15.liquidity if l.swept]) if smc_m15 else 0
        smc_data = {
            "bull_ob": float(smc_m15.order_blocks[0].bottom) if (smc_m15 and smc_m15.order_blocks) else None,
            "bear_ob": float(smc_m15.order_blocks[0].top) if (smc_m15 and smc_m15.order_blocks) else None,
            "fvg": f"{len(smc_m15.fvgs)} active" if (smc_m15 and smc_m15.fvgs) else "None",
            "sweeps": f"{sweeps_count} swept" if sweeps_count else "Clean",
        }

        # Performance summary
        perf_data = {}
        for p in self.db.performance_by_mode():
            perf_data[p.mode.lower()] = {
                "winrate": round(p.win_rate),
                "wins": p.wins,
                "losses": p.losses,
                "pending": p.pending,
            }

        # Recent history
        history_rows = []
        try:
            for s_row in self.db.get_recent_signals(15):
                r_entry = s_row.risk.entry if s_row.risk else s_row.price
                r_sl = s_row.risk.stop_loss if s_row.risk else 0.0
                r_tp1 = s_row.risk.take_profit_1 if s_row.risk else 0.0
                history_rows.append({
                    "time": s_row.timestamp.strftime("%H:%M:%S") if hasattr(s_row.timestamp, "strftime") else str(s_row.timestamp),
                    "mode": s_row.mode,
                    "side": s_row.direction.value,
                    "entry": r_entry,
                    "sl": r_sl,
                    "tp1": r_tp1,
                    "confidence": s_row.confidence,
                    "outcome": getattr(s_row, "outcome", "PENDING") or "PENDING",
                })
        except Exception:
            pass

        # Risk breakdown
        r = signal.risk
        risk_data = None
        if r:
            risk_data = {
                "entry": float(r.entry),
                "sl": float(r.stop_loss),
                "tp1": float(r.take_profit_1),
                "tp2": float(r.take_profit_2),
                "tp3": float(r.take_profit_3),
                "rr": float(r.risk_reward),
                "lots": float(r.lot_size),
                "risk_pct": float(r.risk_percent),
            }

        thr = LEARNER.adaptive_threshold(signal.mode or CONFIG.trading_mode.value, CONFIG.signal.min_confidence)

        return {
            "ok": True,
            "status": "ok",
            "pair": CONFIG.primary_symbol,
            "source": CONFIG.data_source.value,
            "mode": signal.mode or CONFIG.trading_mode.value,
            "tf": tf.value,
            "price": float(analysis.price),
            "spread": float(signal.spread),
            "clock": utc_now().strftime("%Y-%m-%d %H:%M:%S UTC"),
            "stats": {
                "last": float(stats_24h["last"]),
                "change": float(stats_24h["change"]),
                "pct": float(stats_24h["pct"]),
                "high": float(stats_24h["high"]),
                "low": float(stats_24h["low"]),
                "vol_base": float(stats_24h["vol_base"]),
                "vol_quote": float(stats_24h["vol_quote"]),
            },
            "signal": {
                "label": signal.direction.value if signal.is_actionable else "NO TRADE",
                "direction": signal.direction.value,
                "confidence": float(signal.confidence),
                "threshold": float(thr),
                "actionable": bool(signal.is_actionable),
                "trend": signal.trend,
                "structure": signal.structure,
                "session": signal.session,
                "news": signal.news_status,
                "atr": float(signal.atr),
                "features": signal.features,
                "risk": risk_data,
                "lines": signal.summary_lines(),
            },
            "analysis": {
                "mtf": mtf_rows,
                "ict": ict_data,
                "smc": smc_data,
            },
            "book": book_data,
            "chart": chart_data,
            "performance": perf_data,
            "history": history_rows,
            "learner": LEARNER.summary_both(),
        }

    def _build_chart_payload(self, analysis: TopDownAnalysis, signal: TradeSignal, tf: TimeFrame, view: str, df: pd.DataFrame | None) -> dict:
        if df is None or df.empty:
            return {"mode": "original"}

        df_tail = df.tail(CONFIG.ui.chart_candles)
        xs = [ts.isoformat() if hasattr(ts, "isoformat") else str(ts) for ts in df_tail.index]

        ma7 = sma(df_tail["close"], 7)
        ma25 = sma(df_tail["close"], 25)
        ma99 = sma(df_tail["close"], 99)

        payload = {
            "mode": view,
            "tickformat": "%m/%d" if tf in (TimeFrame.D1, TimeFrame.W1, TimeFrame.MN1) else "%H:%M",
            "ohlc": {
                "x": xs,
                "open": [float(v) for v in df_tail["open"]],
                "high": [float(v) for v in df_tail["high"]],
                "low": [float(v) for v in df_tail["low"]],
                "close": [float(v) for v in df_tail["close"]],
            },
            "vol": {
                "x": xs,
                "y": [float(v) for v in df_tail["volume"]],
                "colors": ["#0ecb81" if c >= o else "#f6465d" for o, c in zip(df_tail["open"], df_tail["close"])],
            },
            "ma7": {"x": xs, "y": [None if pd.isna(v) else float(v) for v in ma7]},
            "ma25": {"x": xs, "y": [None if pd.isna(v) else float(v) for v in ma25]},
            "ma99": {"x": xs, "y": [None if pd.isna(v) else float(v) for v in ma99]},
        }

        if view == "tradingview":
            tf_an = analysis.frames.get(tf)
            if tf_an:
                payload["ema20"] = {"x": xs, "y": [None if pd.isna(v) else float(v) for v in tf_an.indicators.ema20.reindex(df_tail.index)]}
                payload["ema50"] = {"x": xs, "y": [None if pd.isna(v) else float(v) for v in tf_an.indicators.ema50.reindex(df_tail.index)]}
                payload["ema200"] = {"x": xs, "y": [None if pd.isna(v) else float(v) for v in tf_an.indicators.ema200.reindex(df_tail.index)]}

        acc = getattr(analysis, "_accuracy", None)
        if acc is not None:
            payload["accuracy"] = {
                "funding": getattr(acc, "funding_rate", None),
                "oi_change": getattr(acc, "oi_change_pct", None),
                "cvd_delta": getattr(acc, "cvd_delta", None),
                "taker": getattr(acc, "taker_buy_sell", None),
                "ls": getattr(acc, "long_short_ratio", None),
            }

        # Overlay signal levels
        if signal.is_actionable and signal.risk:
            r = signal.risk
            last_ts = df_tail.index[-1]
            delta = (df_tail.index[-1] - df_tail.index[-2]) if len(df_tail) >= 2 else pd.Timedelta(minutes=15)
            if delta <= pd.Timedelta(0):
                delta = pd.Timedelta(minutes=15)

            payload["signal"] = {
                "active": True,
                "side": signal.direction.value,
                "entry": float(r.entry),
                "sl": float(r.stop_loss),
                "tp1": float(r.take_profit_1),
                "tp2": float(r.take_profit_2),
                "tp3": float(r.take_profit_3),
                "flow_x": [
                    pd.Timestamp(last_ts).isoformat(),
                    pd.Timestamp(last_ts + delta * 4).isoformat(),
                    pd.Timestamp(last_ts + delta * 10).isoformat(),
                    pd.Timestamp(last_ts + delta * 18).isoformat(),
                ],
                "flow_y": [
                    float(r.entry),
                    float(r.take_profit_1),
                    float(r.take_profit_2),
                    float(r.take_profit_3),
                ],
            }

        # AI Path Forecast
        fc: MarketForecast | None = getattr(analysis, "_forecast", None)
        if fc and fc.active:
            payload["forecast"] = {
                "active": True,
                "color": fc.color or "#f0b90b",
                "path_x": [ts.isoformat() if hasattr(ts, "isoformat") else str(ts) for ts in fc.path_x],
                "path_y": [float(y) for y in fc.path_y],
            }

        return payload


class WebServerHandler(SimpleHTTPRequestHandler):
    """Handles HTTP requests for Android / Desktop Web UI."""

    holder: MarketStateHolder

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, directory=str(WEB_DIR), **kwargs)

    def do_GET(self) -> None:
        if self.path == "/api/state":
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.end_headers()
            data = self.holder.build_state_json()
            self.wfile.write(json.dumps(data).encode("utf-8"))
            return

        if self.path == "/api/history":
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            state = self.holder.build_state_json()
            self.wfile.write(json.dumps(state.get("history", [])).encode("utf-8"))
            return

        # Default static file handling
        if self.path in {"/", ""}:
            self.path = "/index.html"

        super().do_GET()

    def do_POST(self) -> None:
        content_len = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_len) if content_len > 0 else b"{}"
        try:
            req = json.loads(body.decode("utf-8"))
        except Exception:
            req = {}

        if self.path == "/api/tf":
            tf_val = req.get("tf", "M15")
            self.holder.set_timeframe(tf_val)
            self._send_json({"ok": True, "tf": tf_val})
            return

        if self.path == "/api/view":
            view_val = req.get("view", "original")
            self.holder.set_view(view_val)
            self._send_json({"ok": True, "view": view_val})
            return

        if self.path == "/api/mode":
            mode_val = req.get("mode", "swing")
            self.holder.set_mode(mode_val)
            self._send_json({"ok": True, "mode": mode_val})
            return

        if self.path == "/api/clear":
            n = self.holder.db.clear_all()
            LEARNER.reset()
            self._send_json({"ok": True, "cleared": n})
            return

        if self.path == "/api/settings":
            if "min_confidence" in req:
                CONFIG.signal.min_confidence = float(req["min_confidence"])
            if "max_risk_percent" in req:
                CONFIG.risk.max_risk_percent = float(req["max_risk_percent"])
            self._send_json({"ok": True})
            return

        self.send_error(HTTPStatus.NOT_FOUND, "Endpoint not found")

    def _send_json(self, payload: dict) -> None:
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(payload).encode("utf-8"))

    def log_message(self, format: str, *args) -> None:
        # Keep console output clean
        pass


def run_worker_loop(holder: MarketStateHolder) -> None:
    """Continuous market analysis loop."""
    logger.info("Market analysis worker loop started.")
    while holder.running:
        holder.update_cycle()
        time.sleep(CONFIG.ui.refresh_ms / 1000.0)


def start_server(port: int = 8000, host: str = "0.0.0.0") -> int:
    load_env_overrides()
    provider = create_provider(CONFIG.data_source)
    engine = SignalEngine(NewsCalendar())
    db = SignalDatabase()

    holder = MarketStateHolder(provider, engine, db)
    WebServerHandler.holder = holder

    server = ThreadingHTTPServer((host, port), WebServerHandler)
    local_ip = get_local_ip()

    # Start background polling thread
    worker = threading.Thread(target=run_worker_loop, args=(holder,), daemon=True)
    worker.start()

    print("\n" + "=" * 65)
    print("  [+] XAUUSD Signal Desk Pro - Mobile Android & Web Server")
    print("=" * 65)
    print(f"  * Local PC:      http://localhost:{port}")
    print(f"  * Android / LAN: http://{local_ip}:{port}")
    print(f"  * Symbol:        {CONFIG.primary_symbol}")
    print(f"  * Data Source:   {CONFIG.data_source.value}")
    print(f"  * Profile:       {CONFIG.trading_mode.value.upper()}")
    print("=" * 65)
    print(f"  -> Open http://{local_ip}:{port} on your Android phone browser!")
    print("  Press Ctrl+C to stop.\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server...")
    finally:
        holder.running = False
        server.server_close()
        provider.disconnect()
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="XAUUSD Signal Desk Mobile Web Server")
    p.add_argument("--port", type=int, default=8000, help="Web server port (default 8000)")
    p.add_argument("--source", choices=["mt5", "binance", "demo"], default=None)
    p.add_argument("--demo-fallback", action="store_true", help="Use synthetic demo if MT5 fails")
    p.add_argument("--symbol", default=None, help="Override symbol (e.g. XAUUSD, XAUUSDT, BTCUSDT)")
    p.add_argument("--binance-market", choices=["spot", "futures"], default=None, help="Binance market type")
    p.add_argument("--mode", choices=["swing", "intraday", "scalp", "predict"], default=None)
    p.add_argument("--balance", type=float, default=None)
    p.add_argument("--risk", type=float, default=None)
    p.add_argument("--min-confidence", type=float, default=None)
    p.add_argument("--refresh", type=int, default=None)
    p.add_argument("--telegram-token", default=None)
    p.add_argument("--telegram-chat", default=None)
    p.add_argument("--mt5-login", type=int, default=None)
    p.add_argument("--mt5-password", default=None)
    p.add_argument("--mt5-server", default=None)
    p.add_argument("--mt5-path", default=None)
    p.add_argument("--log-level", default="INFO")
    args = p.parse_args()

    setup_logging(args.log_level)
    load_env_overrides()

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

    return start_server(port=args.port)


if __name__ == "__main__":
    sys.exit(main())
