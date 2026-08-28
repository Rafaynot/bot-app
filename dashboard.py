"""
PySide6 dashboard — Binance-style XAUUSD desk with Original / TradingView / Depth charts.

Updates run on a QThread worker so the GUI never freezes.
"""

from __future__ import annotations

import json

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from PySide6.QtCore import QPoint, Qt, QThread, QTimer, QUrl, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QMenu,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from analysis import TopDownAnalysis, run_top_down
from alerts import AlertManager
from config import CONFIG, DATA_DIR, DataSource, TimeFrame, TradingMode, apply_trading_mode
from data import (
    BookLevel,
    DataProvider,
    MT5Provider,
    MarketSnapshot,
    NewsCalendar,
    OrderBookSnapshot,
    create_provider,
    synthetic_order_book,
)
from database import SignalDatabase, resolve_pending_outcomes
from indicators import sma
from learning import LEARNER
from prediction import MarketForecast, build_forecast
from signals import SignalEngine, TradeSignal
from utils import Direction, get_logger, utc_now

logger = get_logger()

try:
    from PySide6.QtWebEngineWidgets import QWebEngineView

    HAS_WEBENGINE = True
except ImportError:
    HAS_WEBENGINE = False
    QWebEngineView = None  # type: ignore


# Binance light-spot palette
BN_BG = "#ffffff"
BN_PAGE = "#f5f5f5"
BN_BORDER = "#eaecef"
BN_TEXT = "#1e2329"
BN_MUTED = "#707a8a"
BN_GREEN = "#0ecb81"
BN_RED = "#f6465d"
BN_YELLOW = "#f0b90b"
MA7_COLOR = "#f0b90b"
MA25_COLOR = "#e040fb"
MA99_COLOR = "#7c4dff"

CHART_DIR = DATA_DIR / "chart"
CHART_PATH = CHART_DIR / "xauusd_chart.html"
CHART_SHELL = CHART_DIR / "live_chart.html"

TF_BUTTONS: list[tuple[str, TimeFrame | None]] = [
    ("Time", None),
    ("1s", TimeFrame.M1),
    ("15m", TimeFrame.M15),
    ("1H", TimeFrame.H1),
    ("4H", TimeFrame.H4),
    ("1D", TimeFrame.D1),
    ("1W", TimeFrame.W1),
]

BINANCE_QSS = f"""
QMainWindow, QWidget {{
    background-color: {BN_BG};
    color: {BN_TEXT};
    font-family: 'IBM Plex Sans', 'Segoe UI', 'Arial', sans-serif;
    font-size: 13px;
}}
QLabel#pairTitle {{
    font-size: 20px;
    font-weight: 700;
    color: {BN_TEXT};
}}
QLabel#lastPrice {{
    font-size: 20px;
    font-weight: 700;
}}
QLabel#statCaption {{
    color: {BN_MUTED};
    font-size: 11px;
}}
QLabel#statValue {{
    color: {BN_TEXT};
    font-size: 12px;
    font-weight: 600;
}}
QLabel#muted {{
    color: {BN_MUTED};
    font-size: 12px;
}}
QLabel#linkish {{
    color: {BN_MUTED};
    font-size: 12px;
}}
QLabel#bookTitle {{
    font-size: 14px;
    font-weight: 600;
    color: {BN_TEXT};
}}
QLabel#colHead {{
    color: {BN_MUTED};
    font-size: 11px;
}}
QLabel#tag {{
    background: #fef6d5;
    color: #c99400;
    font-size: 10px;
    font-weight: 700;
    padding: 1px 5px;
    border-radius: 2px;
}}
QFrame#hairline {{
    background: {BN_BORDER};
    max-height: 1px;
    min-height: 1px;
}}
QFrame#panel {{
    background: {BN_BG};
    border: none;
}}
QPushButton {{
    background: transparent;
    border: none;
    color: {BN_MUTED};
    padding: 6px 10px;
    font-weight: 500;
}}
QPushButton:hover {{
    color: {BN_TEXT};
}}
QPushButton:checked {{
    color: {BN_TEXT};
    font-weight: 600;
}}
QPushButton#navTab {{
    border-radius: 0;
    padding: 10px 14px;
    font-size: 13px;
}}
QPushButton#navTab:checked {{
    border-bottom: 2px solid {BN_YELLOW};
    color: {BN_TEXT};
}}
QPushButton#tfBtn {{
    padding: 4px 8px;
    font-size: 12px;
    border-radius: 2px;
}}
QPushButton#tfBtn:checked {{
    color: {BN_YELLOW};
    font-weight: 700;
}}
QPushButton#viewBtn {{
    padding: 4px 10px;
    font-size: 12px;
}}
QPushButton#viewBtn:checked {{
    border-bottom: 2px solid {BN_YELLOW};
    color: {BN_TEXT};
}}
QPushButton#iconBtn {{
    padding: 2px 8px;
    font-size: 13px;
    min-width: 28px;
}}
QPushButton#iconBtn:checked {{
    color: {BN_YELLOW};
}}
QPushButton#footerTab {{
    padding: 8px 16px;
    font-size: 13px;
}}
QPushButton#footerTab:checked {{
    color: {BN_TEXT};
    border-bottom: 2px solid {BN_YELLOW};
}}
QLabel#signalBanner {{
    padding: 8px 16px;
    font-size: 13px;
    font-weight: 700;
    color: #ffffff;
}}
QPushButton#menuBtn {{
    padding: 4px 10px;
    font-size: 12px;
    color: {BN_MUTED};
}}
QPushButton#menuBtn:hover {{
    color: {BN_TEXT};
}}
QMenu {{
    background: {BN_BG};
    border: 1px solid {BN_BORDER};
    color: {BN_TEXT};
    padding: 4px 0;
}}
QMenu::item {{
    padding: 6px 18px;
    font-size: 12px;
}}
QMenu::item:selected {{
    background: #f5f5f5;
    color: {BN_TEXT};
}}
QPushButton#refreshBtn, QPushButton#clearBtn, QPushButton#resetBtn {{
    background: #ffffff;
    color: #474d57;
    border: 1px solid #d0d5dd;
    border-radius: 4px;
    padding: 5px 12px;
    font-size: 12px;
    font-weight: 600;
}}
QPushButton#refreshBtn:hover, QPushButton#resetBtn:hover {{
    background: #f0f2f5;
    color: #0b0e11;
    border-color: #98a2b3;
}}
QPushButton#clearBtn {{
    color: #c53030;
    border-color: #feb2b2;
    background: #fff5f5;
}}
QPushButton#clearBtn:hover {{
    color: #ffffff;
    background: #e53e3e;
    border-color: #e53e3e;
}}
QComboBox {{
    background: {BN_BG};
    border: 1px solid {BN_BORDER};
    border-radius: 2px;
    padding: 3px 8px;
    min-width: 72px;
    color: {BN_TEXT};
    font-size: 12px;
}}
QComboBox QAbstractItemView {{
    background: {BN_BG};
    border: 1px solid {BN_BORDER};
    selection-background-color: #f5f5f5;
    color: {BN_TEXT};
}}
QProgressBar {{
    border: 1px solid {BN_BORDER};
    border-radius: 2px;
    background: #fafafa;
    text-align: center;
    color: {BN_TEXT};
    height: 18px;
    font-size: 11px;
}}
QProgressBar::chunk {{
    background-color: {BN_YELLOW};
}}
QTextEdit {{
    background: #fafafa;
    border: 1px solid {BN_BORDER};
    border-radius: 2px;
    padding: 10px;
    font-size: 12px;
    color: {BN_TEXT};
}}
QTableWidget {{
    background: {BN_BG};
    border: none;
    gridline-color: {BN_BORDER};
    font-size: 12px;
}}
QHeaderView::section {{
    background: {BN_BG};
    color: {BN_MUTED};
    border: none;
    border-bottom: 1px solid {BN_BORDER};
    padding: 6px;
    font-size: 11px;
}}
QTableWidget::item {{
    padding: 4px;
}}
QSplitter::handle {{
    background: {BN_BORDER};
    width: 1px;
}}
QScrollBar:vertical {{
    background: {BN_BG};
    width: 8px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: #d8dce1;
    border-radius: 4px;
    min-height: 24px;
}}
QLabel#signalBuy {{
    font-size: 28px;
    font-weight: 800;
    color: {BN_GREEN};
    letter-spacing: 3px;
}}
QLabel#signalSell {{
    font-size: 28px;
    font-weight: 800;
    color: {BN_RED};
    letter-spacing: 3px;
}}
QLabel#signalWait {{
    font-size: 22px;
    font-weight: 700;
    color: {BN_YELLOW};
    letter-spacing: 2px;
}}
QLabel#metricName {{
    color: {BN_MUTED};
    font-size: 11px;
}}
QLabel#metricValue {{
    font-size: 15px;
    font-weight: 700;
    color: {BN_TEXT};
}}
QLabel#predDir {{
    font-size: 32px;
    font-weight: 800;
    letter-spacing: 1px;
    padding: 2px 0 4px 0;
}}
QLabel#predCap {{
    color: {BN_MUTED};
    font-size: 11px;
}}
QLabel#predVal {{
    font-size: 16px;
    font-weight: 700;
    color: {BN_TEXT};
}}
QFrame#predCard {{
    background: #fafafa;
    border: 1px solid {BN_BORDER};
    border-radius: 8px;
}}
QLabel#predHead {{
    font-size: 13px;
    font-weight: 600;
    color: {BN_MUTED};
}}
QWidget#predSide {{
    background: {BN_BG};
    border-left: 1px solid {BN_BORDER};
}}
QFrame#predRow {{
    background: #fafafa;
    border: 1px solid {BN_BORDER};
    border-radius: 8px;
}}
QLabel#predRowName {{
    font-size: 13px;
    font-weight: 700;
    color: {BN_TEXT};
}}
QLabel#predRowDir {{
    font-size: 13px;
    font-weight: 800;
}}
QTableWidget#predData {{
    background: {BN_BG};
    border: 1px solid {BN_BORDER};
    border-radius: 6px;
    font-size: 13px;
    gridline-color: {BN_BORDER};
}}
QTableWidget#predData::item {{
    padding: 8px 12px;
}}
QTextEdit#predReport {{
    background: #fafafa;
    border: 1px solid {BN_BORDER};
    border-radius: 8px;
    padding: 12px;
    font-size: 13px;
    line-height: 1.45;
}}
"""


def display_pair(symbol: str) -> tuple[str, str, str]:
    s = (symbol or "XAUUSD").upper().replace("/", "")
    for quote in ("USDT", "USDC", "USD", "EUR"):
        if s.endswith(quote) and len(s) > len(quote):
            base = s[: -len(quote)]
            return f"{base}/{quote}", base, quote
    return symbol, symbol, "USD"


def _fmt(value: float, digits: int = 2) -> str:
    return f"{value:,.{digits}f}"


def _iso_index(index) -> list[str]:
    return [pd.Timestamp(t).isoformat() for t in index]


def _xy(series: pd.Series) -> dict:
    return {
        "x": _iso_index(series.index),
        "y": [None if pd.isna(v) else float(v) for v in series.to_numpy()],
    }


def _ohlc_overlay(df: pd.DataFrame, ma7: pd.Series, ma25: pd.Series, ma99: pd.Series) -> tuple[str, float, str]:
    last = df.iloc[-1]
    last_close = float(last["close"])
    last_open = float(last["open"])
    up = last_close >= last_open
    tag = BN_GREEN if up else BN_RED
    chg = last_close - last_open
    pct = (chg / last_open * 100.0) if last_open else 0.0
    amp = (float(last["high"]) - float(last["low"])) / last_open * 100.0 if last_open else 0.0
    cls = "up" if up else "dn"
    overlay = (
        f"<div class='ohlc {cls}'>"
        f"<span>Open: {_fmt(float(last['open']))}</span>"
        f"<span>High: {_fmt(float(last['high']))}</span>"
        f"<span>Low: {_fmt(float(last['low']))}</span>"
        f"<span>Close: {_fmt(last_close)}</span>"
        f"<span>Change: {chg:+.2f} ({pct:+.2f}%)</span>"
        f"<span>Amplitude: {amp:.2f}%</span>"
        f"</div>"
        f"<div>"
        f"<span class='ma7'>MA(7): {_fmt(float(ma7.iloc[-1]))}</span> &nbsp;"
        f"<span class='ma25'>MA(25): {_fmt(float(ma25.iloc[-1]))}</span> &nbsp;"
        f"<span class='ma99'>MA(99): {_fmt(float(ma99.iloc[-1]))}</span>"
        f"</div>"
        f"<div>Vol: {_fmt(float(last['volume']), 2)}</div>"
    )
    return overlay, last_close, tag


def _market_stats(analysis: TopDownAnalysis) -> dict[str, float]:
    snap: MarketSnapshot | None = getattr(analysis, "_snapshot", None)
    if snap:
        # 1. Direct 24h Daily candle if available
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

        # 2. Rolling 24-hour window from H1 / H4 / M15
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


def _wrap_chart_html(fig: go.Figure, overlay: str, show_modebar: bool) -> str:
    inner = fig.to_html(
        include_plotlyjs="directory",
        full_html=False,
        config={
            "displayModeBar": show_modebar,
            "displaylogo": False,
            "responsive": True,
            "scrollZoom": True,
        },
    )
    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8"/>
<style>
  html, body {{ margin:0; padding:0; height:100%; width:100%; background:#fff; overflow:hidden; }}
  .wrap {{ position:relative; height:100%; width:100%; }}
  .overlay {{
    position:absolute; top:8px; left:12px; z-index:50; pointer-events:none;
    font: 12px/1.5 'IBM Plex Sans','Segoe UI',sans-serif; color:#707a8a;
    background: rgba(255,255,255,0.97);
    border: 1px solid #eaecef;
    border-radius: 4px;
    padding: 6px 10px;
    max-width: min(72%, 780px);
  }}
  .overlay .ohlc span {{ margin-right:10px; }}
  .ma7 {{ color:{MA7_COLOR}; }} .ma25 {{ color:{MA25_COLOR}; }} .ma99 {{ color:{MA99_COLOR}; }}
  .up {{ color:{BN_GREEN}; }} .dn {{ color:{BN_RED}; }}
  .plotly-graph-div, .js-plotly-plot, .plot-container, .svg-container {{
    height:100% !important; width:100% !important;
  }}
</style>
</head>
<body>
<div class="wrap">
  <div class="overlay">{overlay}</div>
  {inner}
</div>
</body>
</html>
"""


def _base_layout(fig: go.Figure, tickformat: str) -> None:
    fig.update_layout(
        paper_bgcolor="#ffffff",
        plot_bgcolor="#ffffff",
        font=dict(family="Segoe UI, IBM Plex Sans, Arial", color="#707a8a", size=11),
        margin=dict(l=8, r=56, t=8, b=8),
        showlegend=False,
        hovermode="x unified",
        xaxis_rangeslider_visible=False,
        autosize=True,
    )
    fig.update_xaxes(rangeslider_visible=False)
    fig.update_xaxes(
        showgrid=True,
        gridcolor="#f0f1f2",
        linecolor="#eaecef",
        tickformat=tickformat,
        showspikes=True,
        spikemode="across",
        spikesnap="cursor",
        spikecolor="#c5cbd3",
        spikethickness=1,
        spikedash="dot",
    )
    fig.update_yaxes(
        showgrid=True,
        gridcolor="#f0f1f2",
        linecolor="#eaecef",
        side="right",
        showspikes=True,
        spikemode="across",
        spikecolor="#c5cbd3",
        spikethickness=1,
        spikedash="dot",
        tickfont=dict(color="#707a8a", size=11),
    )


def build_original_chart(
    df: pd.DataFrame, tf: TimeFrame, analysis: TopDownAnalysis | None = None
) -> tuple[go.Figure, str]:
    """Candles + MA7/25/99 + Asian/London/NY Session Levels (No volume bars)."""
    fig = go.Figure()
    fig.add_trace(
        go.Candlestick(
            x=df.index,
            open=df["open"],
            high=df["high"],
            low=df["low"],
            close=df["close"],
            name="OHLC",
            increasing_line_color=BN_GREEN,
            increasing_fillcolor=BN_GREEN,
            decreasing_line_color=BN_RED,
            decreasing_fillcolor=BN_RED,
            whiskerwidth=0.8,
            hoverinfo="skip",
        )
    )
    ma7 = sma(df["close"], 7)
    ma25 = sma(df["close"], 25)
    ma99 = sma(df["close"], 99)
    for series, color, name in (
        (ma7, MA7_COLOR, "MA(7)"),
        (ma25, MA25_COLOR, "MA(25)"),
        (ma99, MA99_COLOR, "MA(99)"),
    ):
        fig.add_trace(
            go.Scatter(
                x=series.index,
                y=series.values,
                name=name,
                line=dict(width=1.1, color=color),
                hoverinfo="skip",
            )
        )

    # Add Session Levels (Asian High/Low, London High/Low, NY High/Low)
    if analysis is not None:
        acc = getattr(analysis, "_accuracy", None)
        ict_res = analysis.frames[TimeFrame.M15].ict if TimeFrame.M15 in analysis.frames else None
        asia_h = getattr(acc, "asia_high", None) or (getattr(ict_res.session, "asian_high", None) if ict_res else None)
        asia_l = getattr(acc, "asia_low", None) or (getattr(ict_res.session, "asian_low", None) if ict_res else None)
        london_h = getattr(acc, "london_high", None)
        london_l = getattr(acc, "london_low", None)
        ny_h = getattr(acc, "ny_high", None)
        ny_l = getattr(acc, "ny_low", None)

        session_levels = [
            ("Asia H", asia_h, "#c99400"),
            ("Asia L", asia_l, "#c99400"),
            ("London H", london_h, "#2962ff"),
            ("London L", london_l, "#2962ff"),
            ("NY H", ny_h, "#e040fb"),
            ("NY L", ny_l, "#e040fb"),
        ]
        for s_name, s_val, s_col in session_levels:
            if s_val:
                fig.add_hline(
                    y=float(s_val),
                    line=dict(color=s_col, width=1.1, dash="dash"),
                    annotation_text=f"{s_name}: {float(s_val):.2f}",
                    annotation_font_color=s_col,
                    annotation_font_size=10,
                )

    last = df.iloc[-1]
    last_close = float(last["close"])
    last_open = float(last["open"])
    up = last_close >= last_open
    tag = BN_GREEN if up else BN_RED
    fig.add_hline(y=last_close, line=dict(color=tag, width=1, dash="dot"))
    fig.add_annotation(
        x=df.index[-1],
        y=last_close,
        text=f" {last_close:,.2f} ",
        showarrow=False,
        xanchor="left",
        yanchor="middle",
        bgcolor=tag,
        font=dict(color="#ffffff", size=11, family="Segoe UI"),
        xshift=8,
    )
    tickformat = "%m/%d" if tf in (TimeFrame.D1, TimeFrame.W1, TimeFrame.MN1) else "%H:%M"
    _base_layout(fig, tickformat)
    overlay, _, _ = _ohlc_overlay(df, ma7, ma25, ma99)
    return fig, overlay


def build_tradingview_chart(
    df: pd.DataFrame, analysis: TopDownAnalysis, signal: TradeSignal, tf: TimeFrame
) -> tuple[go.Figure, str]:
    """TradingView-style pane with EMAs and optional entry/SL/TP."""
    fig, overlay = build_original_chart(df, tf, analysis)
    tf_an = analysis.frames.get(tf)
    if tf_an:
        for series, color, name in (
            (tf_an.indicators.ema20, "#2962ff", "EMA20"),
            (tf_an.indicators.ema50, "#ff6d00", "EMA50"),
            (tf_an.indicators.ema200, "#7b1fa2", "EMA200"),
        ):
            s = series.reindex(df.index).dropna()
            fig.add_trace(
                go.Scatter(x=s.index, y=s.values, name=name, line=dict(width=1.15, color=color)),
            )
    if signal.risk and signal.is_actionable:
        r = signal.risk
        for y, name, color in (
            (r.entry, "Entry", "#2962ff"),
            (r.stop_loss, "SL", BN_RED),
            (r.take_profit_1, "TP1", BN_GREEN),
        ):
            fig.add_hline(
                y=y,
                line=dict(color=color, width=1.2, dash="dash"),
                annotation_text=name,
                annotation_font_color=color,
            )
    overlay += (
        "<div style='margin-top:4px;color:#707a8a'>TradingView layout · EMA20/50/200"
        + (" · Entry/SL/TP" if signal.risk and signal.is_actionable else "")
        + "</div>"
    )
    return fig, overlay


def build_depth_chart(book: OrderBookSnapshot, last: float) -> tuple[go.Figure, str]:
    fig = go.Figure()
    if book.bids:
        bid_px = [b.price for b in book.bids]
        bid_tot = [b.total for b in book.bids]
        fig.add_trace(
            go.Scatter(
                x=bid_tot,
                y=bid_px,
                fill="tozerox",
                mode="lines",
                line=dict(color=BN_GREEN, width=1.5),
                fillcolor="rgba(14,203,129,0.18)",
                name="Bids",
            )
        )
    if book.asks:
        ask_px = [a.price for a in book.asks]
        ask_tot = [a.total for a in book.asks]
        fig.add_trace(
            go.Scatter(
                x=ask_tot,
                y=ask_px,
                fill="tozerox",
                mode="lines",
                line=dict(color=BN_RED, width=1.5),
                fillcolor="rgba(246,70,93,0.18)",
                name="Asks",
            )
        )
    fig.update_layout(
        paper_bgcolor="#ffffff",
        plot_bgcolor="#ffffff",
        margin=dict(l=16, r=56, t=28, b=32),
        legend=dict(orientation="h", y=1.08, x=0, font=dict(size=11, color=BN_MUTED)),
        xaxis=dict(title="Amount", gridcolor="#f0f1f2", showgrid=True),
        yaxis=dict(title="", side="right", gridcolor="#f0f1f2", showgrid=True),
        font=dict(color=BN_MUTED, size=11),
        autosize=True,
    )
    overlay = f"<div>Depth · Last {_fmt(last)}</div>"
    return fig, overlay


def build_chart(
    analysis: TopDownAnalysis,
    signal: TradeSignal,
    tf: TimeFrame,
    view: str = "original",
    book: OrderBookSnapshot | None = None,
) -> tuple[go.Figure, str, bool]:
    snap: MarketSnapshot | None = getattr(analysis, "_snapshot", None)
    df = None
    if snap and tf in snap.frames:
        df = snap.frames[tf].tail(CONFIG.ui.chart_candles)
    if view == "depth":
        ob = book or getattr(analysis, "_order_book", None)
        if ob is None:
            ob = synthetic_order_book(analysis.price, analysis.price, 20, 0.01)
        fig, overlay = build_depth_chart(ob, analysis.price)
        return fig, overlay, False
    if df is None or df.empty:
        fig = go.Figure()
        fig.update_layout(title="Waiting for chart data…", paper_bgcolor="#fff", plot_bgcolor="#fff")
        return fig, "Waiting for chart data…", False
    if view == "tradingview":
        fig, overlay = build_tradingview_chart(df, analysis, signal, tf)
        return fig, overlay, True
    fig, overlay = build_original_chart(df, tf, analysis)
    return fig, overlay, False


def chart_payload(
    analysis: TopDownAnalysis,
    signal: TradeSignal,
    tf: TimeFrame,
    view: str = "original",
    book: OrderBookSnapshot | None = None,
) -> dict | None:
    """JSON payload for in-place Plotly restyle — page is never reloaded."""
    snap: MarketSnapshot | None = getattr(analysis, "_snapshot", None)
    df = None
    if snap and tf in snap.frames:
        df = snap.frames[tf].tail(CONFIG.ui.chart_candles)
    tickformat = "%m/%d" if tf in (TimeFrame.D1, TimeFrame.W1, TimeFrame.MN1) else "%H:%M"
    uirev = f"{view}-{tf.value}"
    if view == "depth":
        ob = book or getattr(analysis, "_order_book", None)
        if ob is None:
            ob = synthetic_order_book(analysis.price, analysis.price, 20, 0.01)
        return {
            "mode": "depth",
            "uirev": uirev,
            "tickformat": tickformat,
            "overlay": f"<div>Depth · Last {_fmt(analysis.price)}</div>",
            "last": float(analysis.price),
            "tag_color": BN_GREEN,
            "bids": {
                "x": [float(b.total) for b in ob.bids],
                "y": [float(b.price) for b in ob.bids],
            },
            "asks": {
                "x": [float(a.total) for a in ob.asks],
                "y": [float(a.price) for a in ob.asks],
            },
        }
    if df is None or df.empty:
        return None
    ma7 = sma(df["close"], 7)
    ma25 = sma(df["close"], 25)
    ma99 = sma(df["close"], 99)
    overlay, last_close, tag = _ohlc_overlay(df, ma7, ma25, ma99)
    xs = _iso_index(df.index)
    payload: dict = {
        "mode": view,
        "uirev": uirev,
        "tickformat": tickformat,
        "overlay": overlay,
        "last": last_close,
        "tag_color": tag,
        "ohlc": {
            "x": xs,
            "open": [float(v) for v in df["open"]],
            "high": [float(v) for v in df["high"]],
            "low": [float(v) for v in df["low"]],
            "close": [float(v) for v in df["close"]],
        },
        "ma7": _xy(ma7),
        "ma25": _xy(ma25),
        "ma99": _xy(ma99),
        "vol": {
            "x": xs,
            "y": [float(v) for v in df["volume"]],
            "colors": [BN_GREEN if c >= o else BN_RED for o, c in zip(df["open"], df["close"])],
        },
    }
    if view == "tradingview":
        tf_an = analysis.frames.get(tf)
        if tf_an:
            payload["ema20"] = _xy(tf_an.indicators.ema20.reindex(df.index))
            payload["ema50"] = _xy(tf_an.indicators.ema50.reindex(df.index))
            payload["ema200"] = _xy(tf_an.indicators.ema200.reindex(df.index))
        if signal.risk and signal.is_actionable:
            payload["overlay"] += (
                "<div style='margin-top:4px;color:#707a8a'>TradingView · EMA20/50/200 · Entry/SL/TP</div>"
            )
        else:
            payload["overlay"] += (
                "<div style='margin-top:4px;color:#707a8a'>TradingView · EMA20/50/200</div>"
            )
    payload["signal"] = _signal_pack(analysis, signal, df)
    payload["accuracy"] = _accuracy_pack(analysis)
    payload["forecast"] = _forecast_pack(analysis)
    return payload


def _signal_pack(analysis: TopDownAnalysis, signal: TradeSignal, df: pd.DataFrame) -> dict:
    """Levels + projected flow for the live chart overlay."""
    if not (signal.is_actionable and signal.risk):
        return {"active": False}
    r = signal.risk
    last_ts = df.index[-1]
    delta = (df.index[-1] - df.index[-2]) if len(df) >= 2 else pd.Timedelta(minutes=15)
    if pd.Timedelta(delta) <= pd.Timedelta(0):
        delta = pd.Timedelta(minutes=15)
    buy = signal.direction == Direction.BUY
    if buy:
        flow = (
            f"BUY flow: hold above {r.entry:.2f}. "
            f"Path TP1 {r.take_profit_1:.2f} → TP2 {r.take_profit_2:.2f} → TP3 {r.take_profit_3:.2f}. "
            f"Invalid if SL {r.stop_loss:.2f} breaks."
        )
    else:
        flow = (
            f"SELL flow: hold below {r.entry:.2f}. "
            f"Path TP1 {r.take_profit_1:.2f} → TP2 {r.take_profit_2:.2f} → TP3 {r.take_profit_3:.2f}. "
            f"Invalid if SL {r.stop_loss:.2f} breaks."
        )
    return {
        "active": True,
        "side": signal.direction.value,
        "confidence": float(signal.confidence),
        "entry": float(r.entry),
        "sl": float(r.stop_loss),
        "tp1": float(r.take_profit_1),
        "tp2": float(r.take_profit_2),
        "tp3": float(r.take_profit_3),
        "rr": float(r.risk_reward),
        "flow": flow,
        "flow_x": [
            pd.Timestamp(last_ts).isoformat(),
            pd.Timestamp(last_ts + delta * 6).isoformat(),
            pd.Timestamp(last_ts + delta * 14).isoformat(),
            pd.Timestamp(last_ts + delta * 24).isoformat(),
        ],
        "flow_y": [
            float(r.entry),
            float(r.take_profit_1),
            float(r.take_profit_2),
            float(r.take_profit_3),
        ],
        "mark_x": pd.Timestamp(last_ts).isoformat(),
        "mark_y": float(df["close"].iloc[-1]),
        "price": float(analysis.price),
    }


def _accuracy_pack(analysis: TopDownAnalysis) -> dict:
    acc = getattr(analysis, "_accuracy", None)
    if acc is None:
        return {"active": False}
    sessions = []
    for name, y, color in (
        ("Asia H", getattr(acc, "asia_high", None), "#c99400"),
        ("Asia L", getattr(acc, "asia_low", None), "#c99400"),
        ("London H", getattr(acc, "london_high", None), "#2962ff"),
        ("London L", getattr(acc, "london_low", None), "#2962ff"),
        ("NY H", getattr(acc, "ny_high", None), "#e040fb"),
        ("NY L", getattr(acc, "ny_low", None), "#e040fb"),
    ):
        if y:
            sessions.append({"name": name, "y": float(y), "color": color})
    clusters = []
    for c in list(getattr(acc, "clusters", []) or [])[:8]:
        color = "#9b59b6"
        if getattr(c, "side", "") == "bid":
            color = BN_GREEN
        elif getattr(c, "side", "") in {"ask", "liq"}:
            color = BN_RED
        clusters.append({"y": float(c.price), "label": str(c.label), "color": color})
    return {
        "active": True,
        "funding": getattr(acc, "funding_rate", None),
        "oi_change": getattr(acc, "oi_change_pct", None),
        "cvd_delta": getattr(acc, "cvd_delta", None),
        "taker": getattr(acc, "taker_buy_sell", None),
        "ls": getattr(acc, "long_short_ratio", None),
        "sessions": sessions,
        "clusters": clusters,
        "notes": list(getattr(acc, "notes", []) or [])[:8],
    }


def _forecast_pack(analysis: TopDownAnalysis) -> dict:
    fc = getattr(analysis, "_forecast", None)
    if fc is None or not getattr(fc, "active", False):
        return {"active": False}
    if isinstance(fc, MarketForecast):
        return fc.to_dict()
    return {"active": False}


class InitProviderWorker(QThread):
    connected = Signal(object)
    failed = Signal(str)

    def __init__(self, source: DataSource, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.source = source

    def run(self) -> None:
        try:
            provider = create_provider(self.source)
            self.connected.emit(provider)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Provider initialization failed")
            self.failed.emit(str(exc))


class AnalysisWorker(QThread):
    finished_ok = Signal(object, object)
    failed = Signal(str)

    def __init__(
        self,
        provider: DataProvider,
        engine: SignalEngine,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.provider = provider
        self.engine = engine

    def run(self) -> None:
        try:
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

            snap: MarketSnapshot = self.provider.fetch_snapshot(symbol)
            chart_tf = CONFIG.ui.chart_timeframe
            if chart_tf not in snap.frames:
                try:
                    snap.frames[chart_tf] = self.provider.get_ohlcv(
                        symbol, chart_tf, CONFIG.ui.chart_candles
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.debug("Extra chart TF fetch skipped: %s", exc)
            analysis = run_top_down(snap)
            book = None
            try:
                book = self.provider.get_order_book(symbol)
            except Exception as exc:  # noqa: BLE001
                logger.debug("Order book skipped: %s", exc)
            acc_df = None
            for tf in (TimeFrame.M5, TimeFrame.M15, TimeFrame.H1, TimeFrame.M1):
                if tf in snap.frames and snap.frames[tf] is not None and not snap.frames[tf].empty:
                    acc_df = snap.frames[tf]
                    break
            try:
                acc = self.provider.get_accuracy_feed(symbol, acc_df, book)
            except Exception as exc:  # noqa: BLE001
                logger.debug("Accuracy feed skipped: %s", exc)
                acc = None
            analysis._snapshot = snap  # type: ignore[attr-defined]
            analysis._order_book = book  # type: ignore[attr-defined]
            analysis._accuracy = acc  # type: ignore[attr-defined]
            analysis._forecast = build_forecast(analysis)  # type: ignore[attr-defined]
            signal = self.engine.generate(analysis)
            self.finished_ok.emit(analysis, signal)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Analysis worker failed")
            self.failed.emit(str(exc))


class MetricCard(QFrame):
    def __init__(self, name: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(2)
        self.name_lbl = QLabel(name)
        self.name_lbl.setObjectName("metricName")
        self.value_lbl = QLabel("—")
        self.value_lbl.setObjectName("metricValue")
        self.value_lbl.setWordWrap(True)
        layout.addWidget(self.name_lbl)
        layout.addWidget(self.value_lbl)

    def set_value(self, text: str, color: str | None = None) -> None:
        self.value_lbl.setText(text)
        if color:
            self.value_lbl.setStyleSheet(f"color: {color}; font-size: 15px; font-weight: 700;")
        else:
            self.value_lbl.setStyleSheet("")


class OrderBookCanvas(QWidget):
    """Binance-style book: price / amount / total with depth bars from the right."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.asks: list[BookLevel] = []
        self.bids: list[BookLevel] = []
        self.last_price = 0.0
        self.prev_price = 0.0
        self.spread = 0.0
        self.side_mode = "both"
        self.tick = 0.01
        self.setMinimumWidth(250)

    def set_book(self, book: OrderBookSnapshot, last: float, spread: float, tick: float) -> None:
        self.prev_price = self.last_price or last
        self.last_price = last
        self.spread = spread
        self.tick = tick
        self.asks = self._aggregate(book.asks, tick)
        self.bids = self._aggregate(book.bids, tick)
        self.update()

    def _aggregate(self, levels: list[BookLevel], tick: float) -> list[BookLevel]:
        if tick <= 0 or not levels:
            return levels
        buckets: dict[float, float] = {}
        for lvl in levels:
            key = round(round(lvl.price / tick) * tick, 8)
            buckets[key] = buckets.get(key, 0.0) + lvl.amount
        items = [BookLevel(price=p, amount=a) for p, a in buckets.items()]
        if levels and levels[0].price <= (levels[-1].price if levels else 0):
            items.sort(key=lambda x: x.price)
        else:
            items.sort(key=lambda x: x.price, reverse=True)
        running = 0.0
        out: list[BookLevel] = []
        for lvl in items:
            running += lvl.amount
            out.append(BookLevel(price=lvl.price, amount=lvl.amount, total=running))
        return out

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        painter.fillRect(self.rect(), QColor(BN_BG))
        w, h = self.width(), self.height()
        if w < 10 or h < 10:
            return

        show_asks = self.side_mode in ("both", "asks")
        show_bids = self.side_mode in ("both", "bids")
        spread_h = 28 if self.side_mode == "both" else 0
        body = h - spread_h
        ask_h = body if not show_bids else (body // 2 if show_asks else 0)
        bid_h = body - ask_h if show_bids else 0

        asks_l2h = sorted(self.asks, key=lambda x: x.price)
        bids_h2l = sorted(self.bids, key=lambda x: x.price, reverse=True)
        max_total = max([lvl.total for lvl in asks_l2h + bids_h2l] or [1.0])

        def draw_rows(
            levels: list[BookLevel], y0: int, height: int, color: QColor, bar: QColor
        ) -> None:
            if height <= 0 or not levels:
                return
            row_h = max(16, height / max(len(levels), 1))
            digits = 2 if self.tick >= 0.01 else 4
            painter.setFont(QFont("Segoe UI", 9))
            for i, lvl in enumerate(levels):
                y = int(y0 + i * row_h)
                rh = int(row_h)
                bar_w = int((lvl.total / max_total) * w * 0.92) if max_total else 0
                painter.fillRect(w - bar_w, y, bar_w, rh, bar)
                painter.setPen(QPen(color))
                painter.drawText(8, y, 90, rh, int(Qt.AlignmentFlag.AlignVCenter), f"{lvl.price:,.{digits}f}")
                painter.setPen(QPen(QColor(BN_TEXT)))
                painter.drawText(
                    100, y, 80, rh, int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight), f"{lvl.amount:.4f}"
                )
                painter.drawText(
                    186, y, w - 194, rh, int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight), f"{lvl.total:.4f}"
                )

        if show_asks:
            n = max(1, ask_h // 18)
            visible_asks = list(reversed(asks_l2h[:n]))
            draw_rows(visible_asks, 0, ask_h, QColor(BN_RED), QColor(255, 236, 239))
        if self.side_mode == "both":
            y = ask_h
            painter.fillRect(0, y, w, spread_h, QColor("#ffffff"))
            up = self.last_price >= self.prev_price
            painter.setPen(QPen(QColor(BN_GREEN if up else BN_RED)))
            font = QFont("Segoe UI", 12, QFont.Weight.Bold)
            painter.setFont(font)
            painter.drawText(
                8, y, 160, spread_h, int(Qt.AlignmentFlag.AlignVCenter), f"{self.last_price:,.2f}"
            )
            painter.setPen(QPen(QColor(BN_MUTED)))
            painter.setFont(QFont("Segoe UI", 9))
            painter.drawText(
                150, y, w - 158, spread_h,
                int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight),
                f"Spread {self.spread:.2f}",
            )
        if show_bids:
            n = max(1, bid_h // 18)
            draw_rows(bids_h2l[:n], ask_h + spread_h, bid_h, QColor(BN_GREEN), QColor(232, 248, 240))


class Dashboard(QMainWindow):
    """Binance-style main window."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"XAUUSD Signal Desk — {CONFIG.trading_mode.value.upper()}")
        self.resize(max(CONFIG.ui.window_width, 1440), max(CONFIG.ui.window_height, 900))
        self.setStyleSheet(BINANCE_QSS)

        self.provider: DataProvider | None = None
        self._source_detail = self._format_source_label()
        self.news = NewsCalendar()
        self.engine = SignalEngine(self.news)
        self.db = SignalDatabase()
        self.alerts = AlertManager()
        self.alerts.bind_window(self)
        self._worker: AnalysisWorker | None = None
        self._init_worker: InitProviderWorker | None = None
        self._chart_path = CHART_PATH
        self._last_analysis: TopDownAnalysis | None = None
        self._last_signal: TradeSignal | None = None
        self._saved_fingerprint: str | None = None
        self._chart_view_mode = "original"
        self._chart_tf = CONFIG.ui.chart_timeframe
        self._chart_ready = False
        self._pred_chart_ready = False
        self._chart_fp: tuple | None = None
        self._chart_reset = True
        self._pred_chart_reset = True
        self._book_tick = 0.01
        self._book_side = "both"
        self._quote = "USD"
        self._base = "XAU"

        CHART_DIR.mkdir(parents=True, exist_ok=True)
        self._build_ui()

        self.timer = QTimer(self)
        self.timer.setInterval(CONFIG.ui.refresh_ms)
        self.timer.timeout.connect(self.refresh)
        self._start_provider_init()

    def _hairline(self) -> QFrame:
        line = QFrame()
        line.setObjectName("hairline")
        line.setFrameShape(QFrame.Shape.HLine)
        return line

    def _stat_block(self, caption: str) -> tuple[QWidget, QLabel]:
        box = QWidget()
        lay = QVBoxLayout(box)
        lay.setContentsMargins(10, 0, 10, 0)
        lay.setSpacing(0)
        cap = QLabel(caption)
        cap.setObjectName("statCaption")
        val = QLabel("—")
        val.setObjectName("statValue")
        lay.addWidget(cap)
        lay.addWidget(val)
        return box, val

    def _build_ui(self) -> None:
        root = QWidget()
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        outer.addWidget(self._build_header())
        outer.addWidget(self._hairline())
        self.signal_banner = QLabel("")
        self.signal_banner.setObjectName("signalBanner")
        self.signal_banner.setWordWrap(True)
        self.signal_banner.hide()
        outer.addWidget(self.signal_banner)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._build_order_book())
        splitter.addWidget(self._build_main_stage())
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([280, 1160])
        outer.addWidget(splitter, stretch=1)

        outer.addWidget(self._hairline())
        outer.addWidget(self._build_footer())

    def _build_header(self) -> QWidget:
        header = QWidget()
        header.setFixedHeight(64)
        row = QHBoxLayout(header)
        row.setContentsMargins(16, 8, 16, 8)
        row.setSpacing(8)

        pair_col = QVBoxLayout()
        pair_col.setSpacing(2)
        pair_row = QHBoxLayout()
        pair_row.setSpacing(8)
        self.pair_lbl = QLabel("XAU/USD")
        self.pair_lbl.setObjectName("pairTitle")
        pair_row.addWidget(self.pair_lbl)
        self.tag_metal = QLabel("METAL")
        self.tag_metal.setObjectName("tag")
        self.tag_vol = QLabel("Vol")
        self.tag_vol.setObjectName("tag")
        self.tag_fee = QLabel("Spread")
        self.tag_fee.setObjectName("tag")
        self.tag_fund = QLabel("Fund")
        self.tag_fund.setObjectName("tag")
        self.tag_oi = QLabel("OI")
        self.tag_oi.setObjectName("tag")
        self.tag_cvd = QLabel("CVD")
        self.tag_cvd.setObjectName("tag")
        pair_row.addWidget(self.tag_metal)
        pair_row.addWidget(self.tag_vol)
        pair_row.addWidget(self.tag_fee)
        pair_row.addWidget(self.tag_fund)
        pair_row.addWidget(self.tag_oi)
        pair_row.addWidget(self.tag_cvd)
        pair_row.addStretch()
        pair_col.addLayout(pair_row)
        self.usd_lbl = QLabel("$—")
        self.usd_lbl.setObjectName("muted")
        pair_col.addWidget(self.usd_lbl)
        row.addLayout(pair_col)

        self.last_lbl = QLabel("—")
        self.last_lbl.setObjectName("lastPrice")
        row.addWidget(self.last_lbl)

        change_box, self.change_lbl = self._stat_block("24h Change")
        row.addWidget(change_box)
        high_box, self.high_lbl = self._stat_block("24h High")
        row.addWidget(high_box)
        low_box, self.low_lbl = self._stat_block("24h Low")
        row.addWidget(low_box)
        vol_b_box, self.vol_base_lbl = self._stat_block("24h Volume")
        self._vol_base_cap = vol_b_box.findChildren(QLabel)[0]
        row.addWidget(vol_b_box)
        vol_q_box, self.vol_quote_lbl = self._stat_block("24h Volume")
        self._vol_quote_cap = vol_q_box.findChildren(QLabel)[0]
        row.addWidget(vol_q_box)

        row.addStretch()

        mode_lbl = QLabel("Mode")
        mode_lbl.setObjectName("statCaption")
        self.mode_box = QComboBox()
        self.mode_box.addItem("Swing", TradingMode.SWING.value)
        self.mode_box.addItem("Intraday", TradingMode.INTRADAY.value)
        self.mode_box.addItem("Scalp", TradingMode.SCALP.value)
        self.mode_box.addItem("Predict", TradingMode.PREDICT.value)
        idx = self.mode_box.findData(CONFIG.trading_mode.value)
        self.mode_box.setCurrentIndex(idx if idx >= 0 else 0)
        self.mode_box.currentIndexChanged.connect(self._on_mode_changed)
        row.addWidget(mode_lbl)
        row.addWidget(self.mode_box)

        self.source_lbl = QLabel(self._source_detail)
        self.source_lbl.setObjectName("linkish")
        row.addWidget(self.source_lbl)

        reset_btn = QPushButton("Reset Chart")
        reset_btn.setObjectName("resetBtn")
        reset_btn.setCursor(Qt.PointingHandCursor)
        reset_btn.setToolTip("Restore original zoom / pan after accidental zoom")
        reset_btn.clicked.connect(self._reset_chart_view)
        row.addWidget(reset_btn)

        self.clear_btn = QPushButton("Clear Stats")
        self.clear_btn.setObjectName("clearBtn")
        self.clear_btn.setCursor(Qt.PointingHandCursor)
        self.clear_btn.setToolTip("Clear signals history and reset machine learning stats")
        self.clear_btn.clicked.connect(self._clear_stats)
        row.addWidget(self.clear_btn)

        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.setObjectName("refreshBtn")
        self.refresh_btn.setCursor(Qt.PointingHandCursor)
        self.refresh_btn.clicked.connect(self.refresh)
        row.addWidget(self.refresh_btn)
        return header

    def _reset_chart_view(self) -> None:
        if self.chart_view is not None and self._chart_ready:
            self.chart_view.page().runJavaScript(
                "if (window.resetView) { window.resetView(); }"
            )
        self.status_lbl.setText("Status: chart view reset to original")

    def _build_order_book(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("panel")
        panel.setFixedWidth(278)
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(6)

        top = QHBoxLayout()
        title = QLabel("Order Book")
        title.setObjectName("bookTitle")
        top.addWidget(title)
        top.addStretch()
        more = QLabel("⋯")
        more.setObjectName("muted")
        top.addWidget(more)
        lay.addLayout(top)

        tools = QHBoxLayout()
        tools.setSpacing(2)
        self.book_side_group = QButtonGroup(self)
        self.book_side_group.setExclusive(True)
        for key, label in (("both", "⇅"), ("asks", "↑"), ("bids", "↓")):
            btn = QPushButton(label)
            btn.setObjectName("iconBtn")
            btn.setCheckable(True)
            btn.setChecked(key == "both")
            btn.setToolTip({"both": "Both", "asks": "Asks", "bids": "Bids"}[key])
            btn.clicked.connect(lambda _=False, k=key: self._set_book_side(k))
            self.book_side_group.addButton(btn)
            tools.addWidget(btn)
        tools.addStretch()
        self.tick_box = QComboBox()
        for t in ("0.01", "0.1", "1", "10"):
            self.tick_box.addItem(t)
        self.tick_box.currentTextChanged.connect(self._on_tick_changed)
        tools.addWidget(self.tick_box)
        lay.addLayout(tools)

        heads = QHBoxLayout()
        self.head_price = QLabel("Price(USD)")
        self.head_price.setObjectName("colHead")
        self.head_amt = QLabel("Amount")
        self.head_amt.setObjectName("colHead")
        self.head_tot = QLabel("Total")
        self.head_tot.setObjectName("colHead")
        heads.addWidget(self.head_price, 3)
        heads.addWidget(self.head_amt, 2, Qt.AlignmentFlag.AlignRight)
        heads.addWidget(self.head_tot, 2, Qt.AlignmentFlag.AlignRight)
        lay.addLayout(heads)

        self.book_canvas = OrderBookCanvas()
        lay.addWidget(self.book_canvas, stretch=1)
        return panel

    def _build_main_stage(self) -> QWidget:
        stage = QWidget()
        lay = QVBoxLayout(stage)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        tabs = QHBoxLayout()
        tabs.setContentsMargins(8, 0, 8, 0)
        tabs.setSpacing(0)
        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        self._nav_btns: dict[str, QPushButton] = {}
        for key, label in (
            ("chart", "Chart"),
            ("info", "Info"),
            ("data", "Trading Data"),
            ("analysis", "Trading Analysis"),
            ("predict", "Prediction"),
            ("square", "Square"),
        ):
            btn = QPushButton(label)
            btn.setObjectName("navTab")
            btn.setCheckable(True)
            btn.setChecked(key == "chart")
            btn.clicked.connect(lambda _=False, k=key: self._set_main_tab(k))
            self.nav_group.addButton(btn)
            self._nav_btns[key] = btn
            tabs.addWidget(btn)
        tabs.addStretch()
        lay.addLayout(tabs)
        lay.addWidget(self._hairline())

        self.chart_toolbar = self._build_chart_toolbar()
        lay.addWidget(self.chart_toolbar)

        self.stack = QStackedWidget()
        self.stack.addWidget(self._build_chart_page())       # 0 chart
        self.stack.addWidget(self._build_info_page())        # 1 info
        self.stack.addWidget(self._build_data_page())        # 2 data
        self.stack.addWidget(self._build_analysis_page())    # 3 analysis
        self.stack.addWidget(self._build_prediction_page())  # 4 predict
        self.stack.addWidget(self._build_square_page())      # 5 square
        lay.addWidget(self.stack, stretch=1)

        self.status_lbl = QLabel("Status: idle")
        self.status_lbl.setObjectName("muted")
        self.status_lbl.setContentsMargins(12, 4, 12, 4)
        lay.addWidget(self.status_lbl)
        return stage

    def _build_chart_toolbar(self) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(36)
        row = QHBoxLayout(bar)
        row.setContentsMargins(8, 0, 12, 0)
        row.setSpacing(2)

        self.tf_group = QButtonGroup(self)
        self.tf_group.setExclusive(True)
        self._tf_btns: dict[str, QPushButton] = {}
        for label, tf in TF_BUTTONS:
            btn = QPushButton(label)
            btn.setObjectName("tfBtn")
            btn.setCheckable(True)
            if label == "Time":
                btn.clicked.connect(self._open_time_menu)
            else:
                btn.clicked.connect(lambda _=False, t=tf: self._set_chart_tf(t))
            self.tf_group.addButton(btn)
            self._tf_btns[label] = btn
            row.addWidget(btn)
        self._sync_tf_buttons()

        row.addSpacing(8)
        ind = QLabel("ƒ MA")
        ind.setObjectName("muted")
        row.addWidget(ind)

        marks_btn = QPushButton("Marks ▾")
        marks_btn.setObjectName("menuBtn")
        marks_btn.setToolTip("Lines, arrows, text — same drawing marks as Binance")
        marks_btn.clicked.connect(self._open_marks_menu)
        row.addWidget(marks_btn)

        shapes_btn = QPushButton("Shapes ▾")
        shapes_btn.setObjectName("menuBtn")
        shapes_btn.setToolTip("Rectangle, circle, fibonacci, brush")
        shapes_btn.clicked.connect(self._open_shapes_menu)
        row.addWidget(shapes_btn)

        reset_tf = QPushButton("Reset")
        reset_tf.setObjectName("menuBtn")
        reset_tf.setToolTip("Reset chart to original position")
        reset_tf.clicked.connect(self._reset_chart_view)
        row.addWidget(reset_tf)

        row.addStretch()

        self.view_group = QButtonGroup(self)
        self.view_group.setExclusive(True)
        self._view_btns: dict[str, QPushButton] = {}
        for key, label in (
            ("original", "Original"),
            ("tradingview", "TradingView"),
            ("depth", "Depth"),
        ):
            btn = QPushButton(label)
            btn.setObjectName("viewBtn")
            btn.setCheckable(True)
            btn.setChecked(key == "original")
            btn.clicked.connect(lambda _=False, k=key: self._set_chart_view(k))
            self.view_group.addButton(btn)
            self._view_btns[key] = btn
            row.addWidget(btn)
        return bar

    def _build_chart_page(self) -> QWidget:
        page = QFrame()
        page.setObjectName("panel")
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        if HAS_WEBENGINE:
            self.chart_view = QWebEngineView()
            self.chart_view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            self.chart_view.page().setBackgroundColor(QColor("#ffffff"))
            self.chart_view.loadFinished.connect(self._on_chart_loaded)
            self.chart_view.setUrl(QUrl.fromLocalFile(str(CHART_SHELL.resolve())))
            lay.addWidget(self.chart_view)
        else:
            self.chart_view = None
            self.chart_fallback = QLabel(
                "Install PySide6-WebEngine for the live Original chart.\n"
                "HTML is still written to data/chart on each refresh."
            )
            self.chart_fallback.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.chart_fallback.setWordWrap(True)
            lay.addWidget(self.chart_fallback)
        return page

    def _build_info_page(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(20, 16, 20, 16)
        title = QLabel("Token information")
        title.setObjectName("pairTitle")
        lay.addWidget(title)
        self.info_body = QLabel("Waiting for market data…")
        self.info_body.setObjectName("muted")
        self.info_body.setWordWrap(True)
        self.info_body.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        lay.addWidget(self.info_body)
        lay.addStretch()
        return page

    def _build_data_page(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(8, 8, 8, 8)
        self.ohlc_table = QTableWidget(0, 6)
        self.ohlc_table.setHorizontalHeaderLabels(["Time", "Open", "High", "Low", "Close", "Volume"])
        self.ohlc_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.ohlc_table.verticalHeader().setVisible(False)
        self.ohlc_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.ohlc_table.setAlternatingRowColors(True)
        lay.addWidget(self.ohlc_table)
        return page

    def _build_analysis_page(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(10)

        self.signal_lbl = QLabel("WAIT")
        self.signal_lbl.setObjectName("signalWait")
        self.signal_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self.signal_lbl)

        self.conf_bar = QProgressBar()
        self.conf_bar.setRange(0, 100)
        self.conf_bar.setValue(0)
        self.conf_bar.setFormat("Confidence: %v%")
        lay.addWidget(self.conf_bar)

        grid = QGridLayout()
        grid.setSpacing(8)
        self.cards: dict[str, MetricCard] = {}
        metrics = [
            ("price", "Current Price"),
            ("trend", "Trend"),
            ("structure", "Market Structure"),
            ("entry", "Entry"),
            ("sl", "Stop Loss"),
            ("tp1", "Take Profit 1"),
            ("tp2", "Take Profit 2"),
            ("tp3", "Take Profit 3"),
            ("rr", "Risk : Reward"),
            ("lots", "Lot Size (1% risk)"),
            ("atr", "ATR"),
            ("spread", "Spread"),
            ("session", "Current Session"),
            ("news", "Economic News"),
            ("time", "Current Time (UTC)"),
        ]
        for i, (key, name) in enumerate(metrics):
            card = MetricCard(name)
            self.cards[key] = card
            grid.addWidget(card, i // 3, i % 3)
        lay.addLayout(grid)

        reasons_lbl = QLabel("Signal reasons")
        reasons_lbl.setObjectName("statCaption")
        lay.addWidget(reasons_lbl)
        self.reasons_box = QTextEdit()
        self.reasons_box.setReadOnly(True)
        lay.addWidget(self.reasons_box, stretch=1)
        return page

    # def _build_prediction_page(self) -> QWidget:
    #     page = QWidget()
    #     root = QHBoxLayout(page)
    #     root.setContentsMargins(0, 0, 0, 0)
    #     root.setSpacing(0)
    #     split = QSplitter(Qt.Orientation.Horizontal)

    #     chart_wrap = QFrame()
    #     chart_wrap.setObjectName("panel")
    #     c_lay = QVBoxLayout(chart_wrap)
    #     c_lay.setContentsMargins(0, 0, 0, 0)
    #     c_lay.setSpacing(0)
    #     pred_tf = QHBoxLayout()
    #     pred_tf.setContentsMargins(8, 4, 8, 4)
    #     pred_tf.setSpacing(4)
    #     for label, tf in (
    #         ("15m", TimeFrame.M15),
    #         ("1H", TimeFrame.H1),
    #         ("4H", TimeFrame.H4),
    #         ("1D", TimeFrame.D1),
    #     ):
    #         btn = QPushButton(label)
    #         btn.setObjectName("tfBtn")
    #         btn.clicked.connect(lambda _=False, t=tf: self._set_chart_tf(t))
    #         pred_tf.addWidget(btn)
    #     pred_tf.addStretch()
    #     c_lay.addLayout(pred_tf)
    #     if HAS_WEBENGINE:
    #         self.pred_chart_view = QWebEngineView()
    #         self.pred_chart_view.setSizePolicy(
    #             QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
    #         )
    #         self.pred_chart_view.page().setBackgroundColor(QColor("#ffffff"))
    #         self._pred_chart_ready = False
    #         self.pred_chart_view.loadFinished.connect(self._on_pred_chart_loaded)
    #         url = QUrl.fromLocalFile(str(CHART_SHELL.resolve()))
    #         url.setQuery(f"v={int(CHART_SHELL.stat().st_mtime) if CHART_SHELL.exists() else 0}")
    #         self.pred_chart_view.setUrl(url)
    #         c_lay.addWidget(self.pred_chart_view, stretch=1)
    #     else:
    #         self.pred_chart_view = None
    #         self._pred_chart_ready = False
    #         fallback = QLabel("Install PySide6-WebEngine for the prediction chart.")
    #         fallback.setAlignment(Qt.AlignmentFlag.AlignCenter)
    #         c_lay.addWidget(fallback)
    #     chart_wrap.setMinimumWidth(380)
    #     split.addWidget(chart_wrap)

    #     side = QWidget()
    #     side.setObjectName("predSide")
    #     side.setMinimumWidth(460)
    #     scroll = QScrollArea()
    #     scroll.setWidgetResizable(True)
    #     scroll.setFrameShape(QFrame.Shape.NoFrame)
    #     scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    #     inner = QWidget()
    #     lay = QVBoxLayout(inner)
    #     lay.setContentsMargins(18, 16, 18, 18)
    #     lay.setSpacing(14)

    #     kicker = QLabel("PREDICTION REPORT")
    #     kicker.setObjectName("predHead")
    #     lay.addWidget(kicker)

    #     self.pred_dir = QLabel("WAITING")
    #     self.pred_dir.setObjectName("predDir")
    #     self.pred_dir.setWordWrap(True)
    #     lay.addWidget(self.pred_dir)

    #     self.pred_headline = QLabel("Bot will show UP / DOWN, how far, and until when.")
    #     self.pred_headline.setWordWrap(True)
    #     self.pred_headline.setObjectName("muted")
    #     lay.addWidget(self.pred_headline)

    #     self.pred_conf = QProgressBar()
    #     self.pred_conf.setRange(0, 100)
    #     self.pred_conf.setValue(0)
    #     self.pred_conf.setFixedHeight(22)
    #     self.pred_conf.setFormat("Confidence: %v%")
    #     lay.addWidget(self.pred_conf)

    #     grid = QGridLayout()
    #     grid.setHorizontalSpacing(10)
    #     grid.setVerticalSpacing(10)
    #     self.pred_cards: dict[str, MetricCard] = {}
    #     for i, (key, name) in enumerate(
    #         (
    #             ("target", "Target"),
    #             ("move", "How far"),
    #             ("until", "Until when"),
    #             ("invalid", "Invalid if"),
    #             ("now", "Now"),
    #             ("session", "Session"),
    #         )
    #     ):
    #         card = MetricCard(name)
    #         card.setObjectName("predCard")
    #         card.layout().setContentsMargins(12, 10, 12, 10)
    #         card.layout().setSpacing(4)
    #         self.pred_cards[key] = card
    #         grid.addWidget(card, i // 2, i % 2)
    #     lay.addLayout(grid)

    #     hz_lbl = QLabel("Time windows")
    #     hz_lbl.setObjectName("statCaption")
    #     lay.addWidget(hz_lbl)
    #     self.pred_hz_widgets: list[tuple[QFrame, QLabel, QLabel, QLabel]] = []
    #     for _ in range(3):
    #         row = QFrame()
    #         row.setObjectName("predRow")
    #         rv = QVBoxLayout(row)
    #         rv.setContentsMargins(14, 10, 14, 10)
    #         rv.setSpacing(4)
    #         top = QHBoxLayout()
    #         name = QLabel("—")
    #         name.setObjectName("predRowName")
    #         direc = QLabel("")
    #         direc.setObjectName("predRowDir")
    #         top.addWidget(name)
    #         top.addStretch()
    #         top.addWidget(direc)
    #         meta = QLabel("Waiting…")
    #         meta.setObjectName("muted")
    #         meta.setWordWrap(True)
    #         rv.addLayout(top)
    #         rv.addWidget(meta)
    #         lay.addWidget(row)
    #         self.pred_hz_widgets.append((row, name, direc, meta))

    #     data_lbl = QLabel("Clean market data")
    #     data_lbl.setObjectName("statCaption")
    #     lay.addWidget(data_lbl)
    #     self.pred_data = QTableWidget(0, 2)
    #     self.pred_data.setObjectName("predData")
    #     self.pred_data.setHorizontalHeaderLabels(["Field", "Value"])
    #     hdr = self.pred_data.horizontalHeader()
    #     hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
    #     hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
    #     self.pred_data.verticalHeader().setVisible(False)
    #     self.pred_data.verticalHeader().setDefaultSectionSize(32)
    #     self.pred_data.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    #     self.pred_data.setWordWrap(True)
    #     self.pred_data.setTextElideMode(Qt.TextElideMode.ElideNone)
    #     self.pred_data.setShowGrid(False)
    #     self.pred_data.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    #     self.pred_data.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
    #     lay.addWidget(self.pred_data)

    #     report_lbl = QLabel("Clear report")
    #     report_lbl.setObjectName("statCaption")
    #     lay.addWidget(report_lbl)
    #     self.pred_report = QTextEdit()
    #     self.pred_report.setObjectName("predReport")
    #     self.pred_report.setReadOnly(True)
    #     self.pred_report.setMinimumHeight(160)
    #     lay.addWidget(self.pred_report, stretch=1)

    #     scroll.setWidget(inner)
    #     side_lay = QVBoxLayout(side)
    #     side_lay.setContentsMargins(0, 0, 0, 0)
    #     side_lay.addWidget(scroll)
    #     split.addWidget(side)
    #     split.setStretchFactor(0, 3)
    #     split.setStretchFactor(1, 2)
    #     split.setSizes([720, 560])
    #     root.addWidget(split)
    #     return page
    def _build_prediction_page(self) -> QWidget:
        page = QWidget()
        root = QHBoxLayout(page)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        split = QSplitter(Qt.Orientation.Horizontal)

        # --- LEFT PANEL: CHART ---
        chart_wrap = QFrame()
        chart_wrap.setObjectName("panel")
        c_lay = QVBoxLayout(chart_wrap)
        c_lay.setContentsMargins(0, 0, 0, 0)
        c_lay.setSpacing(0)
        
        pred_tf = QHBoxLayout()
        pred_tf.setContentsMargins(8, 4, 8, 4)
        pred_tf.setSpacing(4)
        for label, tf in (
            ("15m", TimeFrame.M15),
            ("1H", TimeFrame.H1),
            ("4H", TimeFrame.H4),
            ("1D", TimeFrame.D1),
        ):
            btn = QPushButton(label)
            btn.setObjectName("tfBtn")
            btn.clicked.connect(lambda _=False, t=tf: self._set_chart_tf(t))
            pred_tf.addWidget(btn)
        pred_tf.addStretch()
        c_lay.addLayout(pred_tf)

        if HAS_WEBENGINE:
            self.pred_chart_view = QWebEngineView()
            self.pred_chart_view.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
            )
            self.pred_chart_view.page().setBackgroundColor(QColor("#ffffff"))
            self._pred_chart_ready = False
            self.pred_chart_view.loadFinished.connect(self._on_pred_chart_loaded)
            url = QUrl.fromLocalFile(str(CHART_SHELL.resolve()))
            url.setQuery(f"v={int(CHART_SHELL.stat().st_mtime) if CHART_SHELL.exists() else 0}")
            self.pred_chart_view.setUrl(url)
            c_lay.addWidget(self.pred_chart_view, stretch=1)
        else:
            self.pred_chart_view = None
            self._pred_chart_ready = False
            fallback = QLabel("Install PySide6-WebEngine for the prediction chart.")
            fallback.setAlignment(Qt.AlignmentFlag.AlignCenter)
            c_lay.addWidget(fallback)
            
        chart_wrap.setMinimumWidth(380)
        split.addWidget(chart_wrap)

        # --- RIGHT PANEL: BINANCE STYLE REPORT ---
        side = QWidget()
        side.setObjectName("predSide")
        side.setMinimumWidth(400)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        inner = QWidget()
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(12)

        # 1. Binance Style Header Block
        header_box = QFrame()
        header_box.setObjectName("binanceHeaderBox")
        hb_lay = QVBoxLayout(header_box)
        hb_lay.setContentsMargins(10, 10, 10, 10)
        hb_lay.setSpacing(6)

        kicker = QLabel("PREDICTION REPORT")
        kicker.setObjectName("predHead")
        hb_lay.addWidget(kicker)

        # Signal Header Row (LONG / SHORT Badge Style)
        sig_row = QHBoxLayout()
        self.pred_dir = QLabel("WAITING")
        self.pred_dir.setObjectName("predDir")
        sig_row.addWidget(self.pred_dir)
        sig_row.addStretch()
        hb_lay.addLayout(sig_row)

        self.pred_headline = QLabel("Bot will show UP / DOWN, how far, and until when.")
        self.pred_headline.setWordWrap(True)
        self.pred_headline.setObjectName("muted")
        hb_lay.addWidget(self.pred_headline)

        # Binance Style Slim Progress Bar
        self.pred_conf = QProgressBar()
        self.pred_conf.setRange(0, 100)
        self.pred_conf.setValue(0)
        self.pred_conf.setFixedHeight(12)
        self.pred_conf.setFormat("Confidence: %v%")
        hb_lay.addWidget(self.pred_conf)

        lay.addWidget(header_box)

        # 2. Binance Data Grid (Key-Value Row Structure)
        grid_frame = QFrame()
        grid_frame.setObjectName("binanceGrid")
        grid = QGridLayout(grid_frame)
        grid.setContentsMargins(10, 10, 10, 10)
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(8)

        self.pred_cards: dict[str, MetricCard] = {}
        for i, (key, name) in enumerate(
            (
                ("target", "Target Price"),
                ("move", "Expected Move"),
                ("until", "Target Time"),
                ("invalid", "Invalidation"),
                ("now", "Current Price"),
                ("session", "Session"),
            )
        ):
            # Key Label (Left)
            lbl_name = QLabel(name)
            lbl_name.setObjectName("binanceLabel")
            
            # Value Label (Right)
            card = MetricCard("")
            card.setObjectName("binanceValue")
            self.pred_cards[key] = card

            row = i
            grid.addWidget(lbl_name, row, 0, Qt.AlignmentFlag.AlignLeft)
            grid.addWidget(card, row, 1, Qt.AlignmentFlag.AlignRight)

        lay.addWidget(grid_frame)

        # 3. Compact Time Horizon Table
        hz_lbl = QLabel("TIME WINDOWS")
        hz_lbl.setObjectName("statCaption")
        lay.addWidget(hz_lbl)

        self.pred_hz_widgets: list[tuple[QFrame, QLabel, QLabel, QLabel]] = []
        for _ in range(3):
            row = QFrame()
            row.setObjectName("binanceHzRow")
            rv = QVBoxLayout(row)
            rv.setContentsMargins(10, 8, 10, 8)
            rv.setSpacing(2)

            top = QHBoxLayout()
            name = QLabel("—")
            name.setObjectName("predRowName")
            direc = QLabel("")
            direc.setObjectName("predRowDir")
            top.addWidget(name)
            top.addStretch()
            top.addWidget(direc)

            meta = QLabel("Waiting…")
            meta.setObjectName("muted")
            meta.setWordWrap(True)

            rv.addLayout(top)
            rv.addWidget(meta)
            lay.addWidget(row)
            self.pred_hz_widgets.append((row, name, direc, meta))

        # 4. Market Data Table
        data_lbl = QLabel("MARKET DATA")
        data_lbl.setObjectName("statCaption")
        lay.addWidget(data_lbl)

        self.pred_data = QTableWidget(0, 2)
        self.pred_data.setObjectName("predData")
        self.pred_data.setHorizontalHeaderLabels(["Field", "Value"])
        hdr = self.pred_data.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.pred_data.verticalHeader().setVisible(False)
        self.pred_data.verticalHeader().setDefaultSectionSize(26)  # Binance compact height
        self.pred_data.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.pred_data.setWordWrap(True)
        self.pred_data.setTextElideMode(Qt.TextElideMode.ElideNone)
        self.pred_data.setShowGrid(False)
        self.pred_data.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.pred_data.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        lay.addWidget(self.pred_data)

        # 5. Technical Report Summary
        report_lbl = QLabel("ANALYSIS REPORT")
        report_lbl.setObjectName("statCaption")
        lay.addWidget(report_lbl)

        self.pred_report = QTextEdit()
        self.pred_report.setObjectName("predReport")
        self.pred_report.setReadOnly(True)
        self.pred_report.setMinimumHeight(120)
        lay.addWidget(self.pred_report, stretch=1)

        scroll.setWidget(inner)
        side_lay = QVBoxLayout(side)
        side_lay.setContentsMargins(0, 0, 0, 0)
        side_lay.addWidget(scroll)

        split.addWidget(side)
        split.setStretchFactor(0, 3)
        split.setStretchFactor(1, 1)
        split.setSizes([800, 400])

        root.addWidget(split)
        return page

    def _build_square_page(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(20, 16, 20, 16)
        title = QLabel("Performance")
        title.setObjectName("pairTitle")
        lay.addWidget(title)
        self.wr_lbl = QLabel(LEARNER.summary_both())
        self.wr_lbl.setObjectName("statValue")
        self.wr_lbl.setWordWrap(True)
        lay.addWidget(self.wr_lbl)
        self.clock_lbl = QLabel("")
        self.clock_lbl.setObjectName("muted")
        lay.addWidget(self.clock_lbl)
        lay.addStretch()
        return page

    def _build_footer(self) -> QWidget:
        footer = QWidget()
        footer.setFixedHeight(40)
        row = QHBoxLayout(footer)
        row.setContentsMargins(8, 0, 16, 0)
        row.setSpacing(0)
        self.footer_group = QButtonGroup(self)
        self.footer_group.setExclusive(True)
        for i, label in enumerate(("Spot", "Cross", "Isolated", "Grid")):
            btn = QPushButton(label)
            btn.setObjectName("footerTab")
            btn.setCheckable(True)
            btn.setChecked(i == 0)
            btn.clicked.connect(lambda _=False, k=label.lower(): self._on_footer(k))
            self.footer_group.addButton(btn)
            row.addWidget(btn)
        row.addStretch()
        fee = QLabel("% Fee Level")
        fee.setObjectName("linkish")
        row.addWidget(fee)
        return footer

    def _set_main_tab(self, key: str) -> None:
        idx = {
            "chart": 0,
            "info": 1,
            "data": 2,
            "analysis": 3,
            "predict": 4,
            "square": 5,
        }[key]
        self.stack.setCurrentIndex(idx)
        self.chart_toolbar.setVisible(key == "chart")

    def _set_chart_view(self, view: str) -> None:
        self._chart_view_mode = view
        self._chart_reset = True
        self._pred_chart_reset = True
        self._render_chart()

    def _set_chart_tf(self, tf: TimeFrame | None) -> None:
        if tf is None:
            return
        self._chart_tf = tf
        CONFIG.ui.chart_timeframe = tf
        self._chart_reset = True
        self._pred_chart_reset = True
        self._sync_tf_buttons()
        if self._last_analysis is not None:
            self._render_chart()
            self._fill_ohlc_table()
        self.refresh()

    def _sync_tf_buttons(self) -> None:
        tf = self._chart_tf
        matched = False
        self._tf_btns["Time"].setText("Time")
        for label, mapped in TF_BUTTONS:
            btn = self._tf_btns[label]
            if mapped is tf:
                btn.setChecked(True)
                matched = True
            elif label != "Time":
                btn.setChecked(False)
        if not matched:
            self._tf_btns["Time"].setChecked(True)
            self._tf_btns["Time"].setText(tf.value)

    def _open_marks_menu(self) -> None:
        menu = QMenu(self)
        items = [
            ("cursor", "Crosshair / Zoom"),
            ("pan", "Pan"),
            ("trend", "Trend line"),
            ("hline", "Horizontal line"),
            ("vline", "Vertical line"),
            ("ray", "Ray"),
            ("arrow", "Arrow mark"),
            ("text", "Text"),
            ("erase", "Erase last"),
            ("clear", "Clear all drawings"),
        ]
        for key, label in items:
            act = menu.addAction(label)
            act.triggered.connect(lambda _=False, k=key: self._set_draw_tool(k))
        btn = self.sender()
        if isinstance(btn, QPushButton):
            menu.exec(btn.mapToGlobal(QPoint(0, btn.height())))

    def _open_shapes_menu(self) -> None:
        menu = QMenu(self)
        items = [
            ("rect", "Rectangle"),
            ("circle", "Circle"),
            ("triangle", "Triangle"),
            ("brush", "Brush / pen"),
            ("fib", "Fibonacci retracement"),
        ]
        for key, label in items:
            act = menu.addAction(label)
            act.triggered.connect(lambda _=False, k=key: self._set_draw_tool(k))
        btn = self.sender()
        if isinstance(btn, QPushButton):
            menu.exec(btn.mapToGlobal(QPoint(0, btn.height())))

    def _set_draw_tool(self, tool: str) -> None:
        if self.chart_view is None or not self._chart_ready:
            return
        self.chart_view.page().runJavaScript(f"window.setTool({json.dumps(tool)})")

    def _open_time_menu(self) -> None:
        menu = QMenu(self)
        for tf in (TimeFrame.M1, TimeFrame.M5, TimeFrame.M15, TimeFrame.M30, TimeFrame.H1):
            act = menu.addAction(tf.value)
            act.triggered.connect(lambda _=False, t=tf: self._set_chart_tf(t))
        btn = self._tf_btns["Time"]
        menu.exec(btn.mapToGlobal(QPoint(0, btn.height())))

    def _set_book_side(self, mode: str) -> None:
        self._book_side = mode
        self.book_canvas.side_mode = mode
        self.book_canvas.update()

    def _on_tick_changed(self, text: str) -> None:
        try:
            self._book_tick = float(text)
        except ValueError:
            self._book_tick = 0.01
        if self._last_analysis is not None:
            self._update_order_book(self._last_analysis)

    def _on_footer(self, key: str) -> None:
        tab = {"spot": "chart", "cross": "analysis", "isolated": "data", "grid": "square"}.get(key, "chart")
        self._nav_btns[tab].setChecked(True)
        self._set_main_tab(tab)

    def _clear_stats(self) -> None:
        n = self.db.clear_all()
        LEARNER.reset()
        self.wr_lbl.setText(LEARNER.summary_both())
        self.status_lbl.setText(f"Status: cleared {n} signals · learning reset")
        logger.info("UI clear stats: removed %s rows", n)

    def _on_mode_changed(self, index: int) -> None:
        mode_val = self.mode_box.itemData(index)
        if not mode_val:
            return
        apply_trading_mode(mode_val)
        self._chart_tf = CONFIG.ui.chart_timeframe
        self._sync_tf_buttons()
        self.setWindowTitle(f"XAUUSD Signal Desk — {CONFIG.trading_mode.value.upper()}")
        self.timer.setInterval(CONFIG.ui.refresh_ms)
        self._saved_fingerprint = None
        if mode_val == TradingMode.PREDICT.value and "predict" in self._nav_btns:
            self._nav_btns["predict"].setChecked(True)
            self._set_main_tab("predict")
        self.refresh()

    def _format_source_label(self) -> str:
        src = CONFIG.data_source.value.upper()
        if self.provider and isinstance(self.provider, MT5Provider) and self.provider.is_connected():
            sym = self.provider._resolved_symbol or CONFIG.primary_symbol
            return f"Source: MT5 · {sym}"
        if self.provider is None:
            return f"Source: {src} (Connecting…)"
        return f"Source: {src}"

    def _start_provider_init(self) -> None:
        self.status_lbl.setText("Status: Connecting to market data…")
        self.refresh_btn.setEnabled(False)
        self._init_worker = InitProviderWorker(CONFIG.data_source)
        self._init_worker.connected.connect(self._on_provider_connected)
        self._init_worker.failed.connect(self._on_provider_failed)
        self._init_worker.start()

    def _on_provider_connected(self, provider: DataProvider) -> None:
        self.provider = provider
        self._source_detail = self._format_source_label()
        self.source_lbl.setText(self._source_detail)
        self.status_lbl.setText("Status: Provider connected · analyzing…")
        self.timer.start()
        self.refresh()

    def _on_provider_failed(self, msg: str) -> None:
        self.status_lbl.setText(f"Status: Connection failed — {msg}")
        self.refresh_btn.setEnabled(True)

    def refresh(self) -> None:
        if self.provider is None:
            if not self._init_worker or not self._init_worker.isRunning():
                self._start_provider_init()
            return
        if self._worker and self._worker.isRunning():
            return
        self.status_lbl.setText("Status: analyzing…")
        self.refresh_btn.setEnabled(False)
        self._worker = AnalysisWorker(self.provider, self.engine, self)
        self._worker.finished_ok.connect(self._on_result)
        self._worker.failed.connect(self._on_error)
        self._worker.start()

    def _on_error(self, msg: str) -> None:
        self.status_lbl.setText(f"Status: error — {msg}")
        self.refresh_btn.setEnabled(True)

    def _update_header(self, analysis: TopDownAnalysis) -> None:
        pretty, base, quote = display_pair(analysis.symbol)
        self._base, self._quote = base, quote
        self.pair_lbl.setText(pretty)
        stats = _market_stats(analysis)
        last = stats["last"]
        up = stats["change"] >= 0
        color = BN_GREEN if up else BN_RED
        self.last_lbl.setText(_fmt(last))
        self.last_lbl.setStyleSheet(f"color: {color}; font-size: 20px; font-weight: 700;")
        self.usd_lbl.setText(f"${_fmt(last)}")
        sign = "+" if up else ""
        self.change_lbl.setText(f"{sign}{_fmt(stats['change'])} {sign}{stats['pct']:.2f}%")
        self.change_lbl.setStyleSheet(f"color: {color}; font-size: 12px; font-weight: 600;")
        self.high_lbl.setText(_fmt(stats["high"]))
        self.low_lbl.setText(_fmt(stats["low"]))
        self.vol_base_lbl.setText(_fmt(stats["vol_base"], 2))
        self._vol_base_cap.setText(f"24h Volume({base})")
        self._vol_quote_cap.setText(f"24h Volume({quote})")
        self.vol_quote_lbl.setText(_fmt(stats["vol_quote"], 2))
        self.tag_fee.setText(f"Spread {analysis.spread:.2f}")
        acc = getattr(analysis, "_accuracy", None)
        if acc is not None:
            fr = getattr(acc, "funding_rate", None)
            oi = getattr(acc, "oi_change_pct", None)
            cvd = getattr(acc, "cvd_delta", None)
            self.tag_fund.setText(f"Fund {fr * 100:.3f}%" if fr is not None else "Fund —")
            self.tag_oi.setText(f"OI {oi:+.2f}%" if oi is not None else "OI —")
            if cvd is None:
                self.tag_cvd.setText("CVD —")
            else:
                self.tag_cvd.setText("CVD " + ("Buy" if cvd > 0 else "Sell"))
        self.head_price.setText(f"Price({quote})")
        self.head_amt.setText(f"Amount({base})")

    def _update_order_book(self, analysis: TopDownAnalysis) -> None:
        book: OrderBookSnapshot | None = getattr(analysis, "_order_book", None)
        if book is None or not (book.asks or book.bids):
            book = synthetic_order_book(analysis.price, analysis.price + max(analysis.spread, 0.01), 20, self._book_tick)
        self.book_canvas.side_mode = self._book_side
        self.book_canvas.set_book(book, analysis.price, analysis.spread, self._book_tick)

    def _fill_ohlc_table(self) -> None:
        if self._last_analysis is None:
            return
        snap: MarketSnapshot | None = getattr(self._last_analysis, "_snapshot", None)
        if not snap or self._chart_tf not in snap.frames:
            return
        df = snap.frames[self._chart_tf].tail(80).iloc[::-1]
        self.ohlc_table.setRowCount(len(df))
        for i, (ts, row) in enumerate(df.iterrows()):
            vals = [
                ts.strftime("%Y-%m-%d %H:%M") if hasattr(ts, "strftime") else str(ts),
                _fmt(float(row["open"])),
                _fmt(float(row["high"])),
                _fmt(float(row["low"])),
                _fmt(float(row["close"])),
                _fmt(float(row["volume"]), 2),
            ]
            for c, val in enumerate(vals):
                item = QTableWidgetItem(val)
                if c == 4:
                    up = float(row["close"]) >= float(row["open"])
                    item.setForeground(QColor(BN_GREEN if up else BN_RED))
                self.ohlc_table.setItem(i, c, item)

    def _fill_info(self, analysis: TopDownAnalysis, signal: TradeSignal) -> None:
        pretty, base, quote = display_pair(analysis.symbol)
        lines = [
            f"{pretty}  ·  {CONFIG.data_source.value.upper()}  ·  {CONFIG.trading_mode.value.upper()}",
            f"Last {analysis.price:.2f} {quote}   Spread {analysis.spread:.2f}",
            f"Session: {signal.session or '—'}    News: {signal.news_status or '—'}",
            f"Trend: {signal.trend or '—'}    Structure: {signal.structure or '—'}",
            f"ATR: {signal.atr:.2f}",
            "",
        ]
        acc = getattr(analysis, "_accuracy", None)
        if acc is not None:
            fr = getattr(acc, "funding_rate", None)
            oi = getattr(acc, "oi_change_pct", None)
            cvd = getattr(acc, "cvd_delta", None)
            taker = getattr(acc, "taker_buy_sell", None)
            ls = getattr(acc, "long_short_ratio", None)
            lines.append("Accuracy feed")
            if fr is not None:
                lines.append(f"Funding: {fr * 100:.4f}%")
            if oi is not None:
                lines.append(f"Open interest Δ: {oi:+.2f}%")
            if cvd is not None:
                lines.append(f"CVD delta: {cvd:+.2f} ({'buy' if cvd > 0 else 'sell'})")
            if taker is not None:
                lines.append(f"Taker buy/sell: {taker:.2f}")
            if ls is not None:
                lines.append(f"Long/short ratio: {ls:.2f}")
            if getattr(acc, "london_high", None) and getattr(acc, "london_low", None):
                lines.append(f"London H/L: {acc.london_high:.2f} / {acc.london_low:.2f}")
            if getattr(acc, "ny_high", None) and getattr(acc, "ny_low", None):
                lines.append(f"NY H/L: {acc.ny_high:.2f} / {acc.ny_low:.2f}")
            if getattr(acc, "asia_high", None) and getattr(acc, "asia_low", None):
                lines.append(f"Asia H/L: {acc.asia_high:.2f} / {acc.asia_low:.2f}")
            for n in list(getattr(acc, "notes", []) or [])[:6]:
                lines.append(f"· {n}")
            lines.append("")
        lines.extend(
            [
                "Spot desk layout matches Original / TradingView / Depth chart views.",
                f"Base {base}  ·  Quote {quote}",
            ]
        )
        self.info_body.setText("\n".join(lines))
        self.info_body.setStyleSheet(f"color: {BN_TEXT}; font-size: 13px;")

    def _update_signal_banner(self, signal: TradeSignal) -> None:
        if signal.is_actionable and signal.risk:
            r = signal.risk
            buy = signal.direction == Direction.BUY
            bg = BN_GREEN if buy else BN_RED
            side = "▲ BUY NOW" if buy else "▼ SELL NOW"
            self.signal_banner.setText(
                f"{side}  ·  {signal.confidence:.0f}%  ·  "
                f"Entry {r.entry:.2f}   SL {r.stop_loss:.2f}  ·  "
                f"Flow TP1 {r.take_profit_1:.2f} → TP2 {r.take_profit_2:.2f} → TP3 {r.take_profit_3:.2f}  "
                f"(R:R 1:{r.risk_reward:.2f})"
            )
            self.signal_banner.setStyleSheet(
                f"QLabel#signalBanner {{ background:{bg}; color:#ffffff; "
                f"padding:8px 16px; font-size:13px; font-weight:700; }}"
            )
            self.signal_banner.show()
        else:
            self.signal_banner.hide()

    def _on_chart_loaded(self, ok: bool) -> None:
        if not ok:
            return
        first = not self._chart_ready
        self._chart_ready = True
        if not first:
            return
        try:
            self.chart_view.loadFinished.disconnect(self._on_chart_loaded)
        except Exception:  # noqa: BLE001
            pass
        self._chart_reset = True
        self._render_chart(force=True, target="main")

    def _on_pred_chart_loaded(self, ok: bool) -> None:
        if not ok:
            return
        first = not self._pred_chart_ready
        self._pred_chart_ready = True
        if not first:
            return
        try:
            self.pred_chart_view.loadFinished.disconnect(self._on_pred_chart_loaded)
        except Exception:  # noqa: BLE001
            pass
        self._pred_chart_reset = True
        self._render_chart(force=True, target="pred")

    def _render_chart(self, force: bool = False, target: str = "both") -> None:
        if self._last_analysis is None or self._last_signal is None:
            return
        try:
            payload = chart_payload(
                self._last_analysis,
                self._last_signal,
                self._chart_tf,
                self._chart_view_mode,
                getattr(self._last_analysis, "_order_book", None),
            )
            if payload is None:
                return
            ohlc = payload.get("ohlc") or {}
            sig = payload.get("signal") or {}
            fc = payload.get("forecast") or {}
            fp = (
                payload["mode"],
                payload["uirev"],
                (ohlc.get("x") or [None])[-1],
                (ohlc.get("open") or [None])[-1],
                (ohlc.get("high") or [None])[-1],
                (ohlc.get("low") or [None])[-1],
                (ohlc.get("close") or [None])[-1],
                payload.get("last"),
                sig.get("active"),
                sig.get("side"),
                sig.get("entry"),
                sig.get("sl"),
                sig.get("tp1"),
                fc.get("direction"),
                fc.get("confidence"),
                (fc.get("path_y") or [None])[-1],
            )
            if not force and fp == self._chart_fp:
                return
            self._chart_fp = fp
            if target in {"both", "main"} and self.chart_view is not None and self._chart_ready:
                main_p = dict(payload)
                main_p["reset"] = bool(self._chart_reset or force)
                if CONFIG.trading_mode != TradingMode.PREDICT:
                    main_p["forecast"] = {"active": False}
                self._chart_reset = False
                self.chart_view.page().runJavaScript(f"window.updateChart({json.dumps(main_p)})")
            if target in {"both", "pred"} and getattr(self, "pred_chart_view", None) is not None and self._pred_chart_ready:
                pred_p = dict(payload)
                pred_p["reset"] = bool(self._pred_chart_reset or force)
                self._pred_chart_reset = False
                self.pred_chart_view.page().runJavaScript(f"window.updateChart({json.dumps(pred_p)})")
            if self.chart_view is None:
                fig, overlay, modebar = build_chart(
                    self._last_analysis,
                    self._last_signal,
                    self._chart_tf,
                    self._chart_view_mode,
                    getattr(self._last_analysis, "_order_book", None),
                )
                html = _wrap_chart_html(fig, overlay, modebar)
                self._chart_path.write_text(html, encoding="utf-8")
                self.chart_fallback.setText(f"Chart saved: {self._chart_path}")
        except Exception as exc:  # noqa: BLE001
            logger.warning("Chart update failed: %s", exc)

    def _update_prediction_page(self, analysis: TopDownAnalysis) -> None:
        fc: MarketForecast | None = getattr(analysis, "_forecast", None)
        if fc is None or not fc.active:
            self.pred_dir.setText("WAITING")
            self.pred_dir.setStyleSheet(f"color: {BN_YELLOW};")
            self.pred_headline.setText("Waiting for a clean forecast…")
            self.pred_conf.setValue(0)
            for _, name, direc, meta in self.pred_hz_widgets:
                name.setText("—")
                direc.setText("")
                meta.setText("Waiting…")
            self.pred_data.setRowCount(0)
            self.pred_report.setPlainText(getattr(fc, "summary", "") or "No forecast yet.")
            return
        color = fc.color or BN_YELLOW
        label = {"UP": "▲  MARKET UP", "DOWN": "▼  MARKET DOWN"}.get(fc.direction, "◆  RANGE")
        self.pred_dir.setText(label)
        self.pred_dir.setStyleSheet(f"color: {color};")
        mid = fc.horizons[1] if len(fc.horizons) > 1 else (fc.horizons[0] if fc.horizons else None)
        if mid:
            self.pred_headline.setText(f"Until {mid.until}")
        else:
            self.pred_headline.setText(fc.headline)
        self.pred_conf.setValue(int(fc.confidence))
        self.pred_conf.setStyleSheet(f"QProgressBar::chunk {{ background-color: {color}; }}")
        self.pred_conf.setFormat(f"Confidence: %v%")
        self.pred_cards["now"].set_value(_fmt(fc.price), BN_YELLOW)
        if mid:
            move_col = BN_GREEN if mid.move >= 0 else BN_RED
            self.pred_cards["target"].set_value(_fmt(mid.target), color)
            self.pred_cards["move"].set_value(f"{mid.move:+.2f}  ({mid.move_pct:+.2f}%)", move_col)
            self.pred_cards["until"].set_value(mid.until)
        else:
            self.pred_cards["target"].set_value("—")
            self.pred_cards["move"].set_value("—")
            self.pred_cards["until"].set_value("—")
        self.pred_cards["invalid"].set_value(_fmt(fc.invalidation), BN_RED)
        session = "—"
        tf = next(iter(analysis.frames.values()), None)
        if tf and tf.ict:
            session = tf.ict.session.name.value
        self.pred_cards["session"].set_value(session)

        for i, (row, name, direc, meta) in enumerate(self.pred_hz_widgets):
            if i >= len(fc.horizons):
                row.hide()
                continue
            row.show()
            h = fc.horizons[i]
            hcol = BN_GREEN if h.direction == "UP" else BN_RED if h.direction == "DOWN" else BN_YELLOW
            name.setText(h.name)
            direc.setText(h.direction)
            direc.setStyleSheet(f"color: {hcol};")
            meta.setText(
                f"Target  {_fmt(h.target)}     Move  {h.move:+.2f} ({h.move_pct:+.2f}%)\n"
                f"Until  {h.until}"
            )

        self.pred_data.setRowCount(len(fc.data_rows))
        for i, (k, v) in enumerate(fc.data_rows):
            key_item = QTableWidgetItem(k)
            val_item = QTableWidgetItem(v)
            key_item.setForeground(QColor(BN_MUTED))
            self.pred_data.setItem(i, 0, key_item)
            self.pred_data.setItem(i, 1, val_item)
        self.pred_data.resizeRowsToContents()
        rows = max(1, self.pred_data.rowCount())
        self.pred_data.setFixedHeight(min(38 * rows + 36, 360))
        self.pred_report.setPlainText(fc.summary)

    def _on_result(self, analysis: TopDownAnalysis, signal: TradeSignal) -> None:
        self._last_analysis = analysis
        self._last_signal = signal
        self.refresh_btn.setEnabled(True)
        self.clock_lbl.setText(utc_now().strftime("%Y-%m-%d %H:%M:%S UTC"))
        self.source_lbl.setText(self._format_source_label())

        self._update_header(analysis)
        self._update_order_book(analysis)
        self._fill_info(analysis, signal)
        self._fill_ohlc_table()
        self._update_signal_banner(signal)
        self._update_prediction_page(analysis)

        if signal.direction == Direction.BUY and signal.is_actionable:
            self.signal_lbl.setText("BUY")
            self.signal_lbl.setObjectName("signalBuy")
        elif signal.direction == Direction.SELL and signal.is_actionable:
            self.signal_lbl.setText("SELL")
            self.signal_lbl.setObjectName("signalSell")
        else:
            self.signal_lbl.setText("NO TRADE")
            self.signal_lbl.setObjectName("signalWait")
        self.signal_lbl.style().unpolish(self.signal_lbl)
        self.signal_lbl.style().polish(self.signal_lbl)

        self.conf_bar.setValue(int(signal.confidence))
        thr = int(
            LEARNER.adaptive_threshold(
                signal.mode or CONFIG.trading_mode.value,
                CONFIG.signal.min_confidence,
            )
        )
        color_conf = BN_GREEN if signal.confidence >= thr else BN_YELLOW
        self.conf_bar.setStyleSheet(
            f"QProgressBar::chunk {{ background-color: {color_conf}; }}"
        )
        self.conf_bar.setFormat(f"Confidence: %v% (need >={thr}%)")

        self.cards["price"].set_value(f"{analysis.price:.2f}", BN_YELLOW)
        self.cards["trend"].set_value(signal.trend or "—")
        self.cards["structure"].set_value(signal.structure or "—")
        self.cards["session"].set_value(signal.session or "—")
        self.cards["news"].set_value(signal.news_status or "—")
        self.cards["time"].set_value(utc_now().strftime("%H:%M:%S"))
        self.cards["atr"].set_value(f"{signal.atr:.2f}")
        self.cards["spread"].set_value(f"{signal.spread:.2f}")

        if signal.risk and signal.is_actionable:
            r = signal.risk
            self.cards["entry"].set_value(f"{r.entry:.2f}")
            self.cards["sl"].set_value(f"{r.stop_loss:.2f}", BN_RED)
            self.cards["tp1"].set_value(f"{r.take_profit_1:.2f}", BN_GREEN)
            self.cards["tp2"].set_value(f"{r.take_profit_2:.2f}", BN_GREEN)
            self.cards["tp3"].set_value(f"{r.take_profit_3:.2f}", BN_GREEN)
            self.cards["rr"].set_value(f"1 : {r.risk_reward:.2f}")
            self.cards["lots"].set_value(f"{r.lot_size:.2f}")
        else:
            for k in ("entry", "sl", "tp1", "tp2", "tp3", "rr", "lots"):
                self.cards[k].set_value("—")

        if signal.is_actionable:
            text = "\n".join(signal.summary_lines())
        else:
            text = "NO TRADE\nWait for better confirmation.\n\n" + "\n".join(signal.summary_lines())
        self.reasons_box.setPlainText(text)

        try:
            resolve_pending_outcomes(self.db, analysis.price, LEARNER)
        except Exception as exc:  # noqa: BLE001
            logger.debug("Outcome resolution skipped: %s", exc)

        try:
            parts = []
            for perf in self.db.performance_by_mode():
                parts.append(
                    f"{perf.mode[:5].upper()} WR {perf.win_rate:.0f}% "
                    f"({perf.wins}W/{perf.losses}L · pend {perf.pending})"
                )
            if not parts:
                parts = [LEARNER.summary_both()]
            learn = getattr(signal, "learning_note", "") or LEARNER.status_line(
                CONFIG.trading_mode.value
            )
            self.wr_lbl.setText(" · ".join(parts) + f"\n{learn}")
        except Exception:  # noqa: BLE001
            self.wr_lbl.setText(LEARNER.summary_both())

        pending_alert = False
        if signal.is_actionable:
            fp = f"{signal.mode}:{signal.direction.value}:{round(signal.price, 1)}:{int(signal.confidence)}"
            if fp != self._saved_fingerprint:
                self.db.save_signal(signal)
                pending_alert = True
                self._saved_fingerprint = fp
                self._nav_btns["chart"].setChecked(True)
                self._set_main_tab("chart")

        self._render_chart()

        if pending_alert:
            QApplication.processEvents()
            self.alerts.maybe_alert(signal)

        self.status_lbl.setText(
            f"Status: ok · {len(analysis.frames)} TFs · "
            f"{'ACTIONABLE' if signal.is_actionable else 'waiting'} · "
            f"{signal.mode or CONFIG.trading_mode.value}"
        )

    def closeEvent(self, event) -> None:  # noqa: N802
        self.timer.stop()
        if self._worker and self._worker.isRunning():
            self._worker.quit()
            self._worker.wait(1000)
        if self._init_worker and self._init_worker.isRunning():
            self._init_worker.quit()
            self._init_worker.wait(1000)
        if self.provider:
            try:
                self.provider.disconnect()
            except Exception:  # noqa: BLE001
                pass
        super().closeEvent(event)


def run_dashboard() -> int:
    import sys

    app = QApplication(sys.argv)
    app.setApplicationName("XAUUSD Analyzer")
    win = Dashboard()
    win.show()
    return app.exec()
