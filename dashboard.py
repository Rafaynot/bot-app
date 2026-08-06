"""
PySide6 dashboard — live XAUUSD analysis UI with embedded Plotly chart.

Updates run on a QThread worker so the GUI never freezes.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import plotly.graph_objects as go
from plotly.subplots import make_subplots
from PySide6.QtCore import Qt, QThread, QTimer, QUrl, Signal
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from analysis import TopDownAnalysis, run_top_down
from alerts import AlertManager
from config import CONFIG, DataSource, TimeFrame, TradingMode, apply_trading_mode
from data import DataProvider, MT5Provider, MarketSnapshot, NewsCalendar, create_provider
from database import SignalDatabase, resolve_pending_outcomes
from learning import LEARNER
from signals import SignalEngine, TradeSignal
from utils import Direction, get_logger, utc_now

logger = get_logger()

# Optional WebEngine for Plotly; fall back to static image path / HTML file open
try:
    from PySide6.QtWebEngineWidgets import QWebEngineView

    HAS_WEBENGINE = True
except ImportError:
    HAS_WEBENGINE = False
    QWebEngineView = None  # type: ignore


DARK_QSS = """
QMainWindow, QWidget {
    background-color: #0b0e12;
    color: #e8edf2;
    font-family: 'Segoe UI Semibold', 'Segoe UI', 'Cascadia Code', sans-serif;
}
QLabel#title {
    font-size: 26px;
    font-weight: 800;
    color: #f3d48a;
    letter-spacing: 2.5px;
}
QLabel#subtitle {
    color: #8a96a5;
    font-size: 12px;
    letter-spacing: 0.3px;
}
QLabel#brandMark {
    font-size: 11px;
    font-weight: 700;
    color: #c9a44a;
    letter-spacing: 3px;
}
QFrame#card {
    background-color: #12171f;
    border: 1px solid #243041;
    border-radius: 12px;
}
QFrame#card:hover {
    border: 1px solid #3a4d63;
}
QFrame#heroCard {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #141a22, stop:1 #1a1520);
    border: 1px solid #3a3220;
    border-radius: 16px;
}
QFrame#statsCard {
    background-color: #10151c;
    border: 1px solid #2a3848;
    border-radius: 12px;
}
QLabel#metricName {
    color: #7f8b9a;
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 0.8px;
    text-transform: uppercase;
}
QLabel#metricValue {
    font-size: 17px;
    font-weight: 700;
    color: #eef2f6;
}
QLabel#signalBuy {
    font-size: 34px;
    font-weight: 900;
    color: #3dd68c;
    letter-spacing: 4px;
}
QLabel#signalSell {
    font-size: 34px;
    font-weight: 900;
    color: #f07178;
    letter-spacing: 4px;
}
QLabel#signalWait {
    font-size: 30px;
    font-weight: 800;
    color: #e0bf74;
    letter-spacing: 3px;
}
QLabel#statTitle {
    color: #9aa6b5;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 1px;
}
QLabel#statValue {
    color: #f3d48a;
    font-size: 14px;
    font-weight: 700;
}
QTextEdit {
    background-color: #0e1319;
    border: 1px solid #243041;
    border-radius: 12px;
    padding: 12px;
    font-size: 12px;
    color: #d5dde6;
    selection-background-color: #3a3220;
}
QProgressBar {
    border: 1px solid #243041;
    border-radius: 8px;
    background: #0e1319;
    text-align: center;
    color: #e8edf2;
    height: 22px;
    font-size: 11px;
    font-weight: 600;
}
QProgressBar::chunk {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #c9a44a, stop:1 #e6c97a);
    border-radius: 7px;
}
QPushButton {
    background-color: #1a2330;
    border: 1px solid #334556;
    border-radius: 8px;
    padding: 9px 16px;
    font-weight: 700;
    color: #e8edf2;
}
QPushButton:hover {
    background-color: #243144;
    border-color: #4a6078;
}
QPushButton#refreshBtn {
    background-color: #1c2e24;
    border-color: #3d6b52;
    color: #9fefc0;
}
QPushButton#refreshBtn:hover {
    background-color: #254033;
}
QPushButton#clearBtn {
    background-color: #2a1c1c;
    border-color: #6b3d3d;
    color: #f0a8a8;
}
QPushButton#clearBtn:hover {
    background-color: #3a2424;
}
QComboBox {
    background-color: #151b24;
    border: 1px solid #334556;
    border-radius: 8px;
    padding: 8px 12px;
    min-width: 110px;
    font-weight: 700;
    color: #f3d48a;
}
QComboBox:hover {
    border-color: #c9a44a;
}
QComboBox::drop-down {
    border: none;
    width: 24px;
}
QComboBox QAbstractItemView {
    background-color: #151b24;
    border: 1px solid #334556;
    selection-background-color: #2a3848;
    color: #e8edf2;
}
QSplitter::handle {
    background: #1c2633;
    width: 2px;
}
QScrollBar:vertical {
    background: #0b0e12;
    width: 10px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background: #2a3848;
    border-radius: 4px;
    min-height: 30px;
}
"""


class InitProviderWorker(QThread):
    """Background MT5 / market data provider connection worker."""

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
    """Background fetch + analysis cycle."""

    finished_ok = Signal(object, object)  # TopDownAnalysis, TradeSignal
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
            # Demo/MT5 both honor primary for XAU
            if CONFIG.data_source.value != "binance":
                symbol = CONFIG.primary_symbol
                if hasattr(self.provider, "_resolved_symbol") and self.provider._resolved_symbol:
                    symbol = self.provider._resolved_symbol

            snap: MarketSnapshot = self.provider.fetch_snapshot(symbol)
            analysis = run_top_down(snap)
            signal = self.engine.generate(analysis)
            # Attach snapshot frames for charting
            analysis._snapshot = snap  # type: ignore[attr-defined]
            self.finished_ok.emit(analysis, signal)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Analysis worker failed")
            self.failed.emit(str(exc))


def build_chart(analysis: TopDownAnalysis, signal: TradeSignal, tf: TimeFrame) -> go.Figure:
    """Plotly candlestick with EMA, OB, FVG, S/R, entry/SL/TP overlays."""
    snap: MarketSnapshot | None = getattr(analysis, "_snapshot", None)
    df = None
    if snap and tf in snap.frames:
        df = snap.frames[tf].tail(CONFIG.ui.chart_candles)
    elif tf in analysis.frames:
        # Reconstruct limited view from indicators index only — need OHLC from snapshot
        pass
    if df is None or df.empty:
        fig = go.Figure()
        fig.update_layout(title="Waiting for chart data…", template="plotly_dark")
        return fig

    tf_an = analysis.frames.get(tf)
    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.75, 0.25],
    )

    fig.add_trace(
        go.Candlestick(
            x=df.index,
            open=df["open"],
            high=df["high"],
            low=df["low"],
            close=df["close"],
            name="OHLC",
            increasing_line_color="#3dd68c",
            decreasing_line_color="#f07178",
        ),
        row=1,
        col=1,
    )

    if tf_an:
        for name, series, color in (
            ("EMA20", tf_an.indicators.ema20, "#e6c07b"),
            ("EMA50", tf_an.indicators.ema50, "#61afef"),
            ("EMA200", tf_an.indicators.ema200, "#c678dd"),
        ):
            s = series.reindex(df.index).dropna()
            fig.add_trace(
                go.Scatter(x=s.index, y=s.values, name=name, line=dict(width=1.2, color=color)),
                row=1,
                col=1,
            )

        # Order blocks
        for ob in tf_an.smc.order_blocks[-6:]:
            color = "rgba(61,214,140,0.18)" if ob.bullish else "rgba(240,113,120,0.18)"
            fig.add_shape(
                type="rect",
                x0=ob.start_time,
                x1=df.index[-1],
                y0=ob.bottom,
                y1=ob.top,
                fillcolor=color,
                line=dict(width=0),
                row=1,
                col=1,
            )

        # FVGs
        for fvg in [f for f in tf_an.smc.fvgs if not f.filled][-5:]:
            color = "rgba(97,175,239,0.15)" if fvg.bullish else "rgba(230,192,123,0.15)"
            fig.add_shape(
                type="rect",
                x0=fvg.start_time,
                x1=df.index[-1],
                y0=fvg.bottom,
                y1=fvg.top,
                fillcolor=color,
                line=dict(width=0),
                row=1,
                col=1,
            )

        # S/R horizontals
        for lvl in tf_an.sr_levels[-8:]:
            fig.add_hline(
                y=lvl.price,
                line=dict(color="#4a5568", width=1, dash="dot"),
                row=1,
                col=1,
            )

        # RSI subplot
        rsi = tf_an.indicators.rsi.reindex(df.index).dropna()
        fig.add_trace(
            go.Scatter(x=rsi.index, y=rsi.values, name="RSI", line=dict(color="#56b6c2", width=1.2)),
            row=2,
            col=1,
        )
        fig.add_hline(y=70, line=dict(color="#f07178", width=1, dash="dash"), row=2, col=1)
        fig.add_hline(y=30, line=dict(color="#3dd68c", width=1, dash="dash"), row=2, col=1)

    # Entry / SL / TP
    if signal.risk and signal.is_actionable:
        r = signal.risk
        for y, name, color in (
            (r.entry, "Entry", "#61afef"),
            (r.stop_loss, "SL", "#f07178"),
            (r.take_profit_1, "TP1", "#3dd68c"),
            (r.take_profit_2, "TP2", "#98c379"),
            (r.take_profit_3, "TP3", "#7fdbca"),
        ):
            fig.add_hline(y=y, line=dict(color=color, width=1.5), annotation_text=name, row=1, col=1)

    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="#0f1419",
        plot_bgcolor="#121820",
        height=560,
        margin=dict(l=40, r=20, t=40, b=20),
        xaxis_rangeslider_visible=False,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        title=dict(text=f"{analysis.symbol} · {tf.value}", font=dict(color="#f0d78c", size=14)),
    )
    fig.update_yaxes(gridcolor="#1f2a36")
    fig.update_xaxes(gridcolor="#1f2a36")
    return fig


class MetricCard(QFrame):
    def __init__(self, name: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(4)
        self.name_lbl = QLabel(name.upper())
        self.name_lbl.setObjectName("metricName")
        self.value_lbl = QLabel("—")
        self.value_lbl.setObjectName("metricValue")
        self.value_lbl.setWordWrap(True)
        layout.addWidget(self.name_lbl)
        layout.addWidget(self.value_lbl)

    def set_value(self, text: str, color: str | None = None) -> None:
        self.value_lbl.setText(text)
        if color:
            self.value_lbl.setStyleSheet(
                f"color: {color}; font-size: 17px; font-weight: 700;"
            )
        else:
            self.value_lbl.setStyleSheet("")


class Dashboard(QMainWindow):
    """Main application window."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"XAUUSD Signal Desk — {CONFIG.trading_mode.value.upper()}")
        self.resize(CONFIG.ui.window_width, CONFIG.ui.window_height)
        self.setStyleSheet(DARK_QSS)

        self.provider: DataProvider | None = None
        self._source_detail = self._format_source_label()
        self.news = NewsCalendar()
        self.engine = SignalEngine(self.news)
        self.db = SignalDatabase()
        self.alerts = AlertManager()
        self.alerts.bind_window(self)
        self._worker: AnalysisWorker | None = None
        self._init_worker: InitProviderWorker | None = None
        self._chart_path = Path(tempfile.gettempdir()) / "xauusd_chart.html"
        self._last_analysis: TopDownAnalysis | None = None
        self._last_signal: TradeSignal | None = None
        self._saved_fingerprint: str | None = None

        self._build_ui()

        self.timer = QTimer(self)
        self.timer.setInterval(CONFIG.ui.refresh_ms)
        self.timer.timeout.connect(self.refresh)

        # Connect data provider asynchronously so GUI initializes instantly without freezing
        self._start_provider_init()

    def _build_ui(self) -> None:
        root = QWidget()
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(20, 18, 20, 18)
        outer.setSpacing(14)

        # Header
        header = QHBoxLayout()
        header.setSpacing(12)
        titles = QVBoxLayout()
        titles.setSpacing(2)
        brand = QLabel("XAUUSD")
        brand.setObjectName("brandMark")
        title = QLabel("SIGNAL DESK")
        title.setObjectName("title")
        self.sub_lbl = QLabel(self._mode_subtitle())
        self.sub_lbl.setObjectName("subtitle")
        titles.addWidget(brand)
        titles.addWidget(title)
        titles.addWidget(self.sub_lbl)
        header.addLayout(titles)
        header.addStretch()

        mode_lbl = QLabel("MODE")
        mode_lbl.setObjectName("metricName")
        mode_box = QComboBox()
        mode_box.addItem("Swing", TradingMode.SWING.value)
        mode_box.addItem("Scalp", TradingMode.SCALP.value)
        idx = 0 if CONFIG.trading_mode == TradingMode.SWING else 1
        mode_box.setCurrentIndex(idx)
        mode_box.setToolTip(
            "Swing = full HTF confluence M15 · Scalp = M5 entry + M1 confirm, kill-zone, spread filter"
        )
        mode_box.currentIndexChanged.connect(self._on_mode_changed)
        self.mode_box = mode_box
        header.addWidget(mode_lbl)
        header.addWidget(mode_box)

        self.source_lbl = QLabel(self._source_detail)
        self.source_lbl.setObjectName("subtitle")
        self.clock_lbl = QLabel("")
        self.clock_lbl.setObjectName("subtitle")
        header.addWidget(self.source_lbl)
        header.addWidget(self.clock_lbl)

        self.clear_btn = QPushButton("Clear Stats")
        self.clear_btn.setObjectName("clearBtn")
        self.clear_btn.setToolTip("Reset win/loss history and learning weights")
        self.clear_btn.clicked.connect(self._clear_stats)
        header.addWidget(self.clear_btn)

        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.setObjectName("refreshBtn")
        self.refresh_btn.clicked.connect(self.refresh)
        header.addWidget(self.refresh_btn)
        outer.addLayout(header)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left panel
        left = QWidget()
        left_l = QVBoxLayout(left)
        left_l.setContentsMargins(0, 0, 8, 0)
        left_l.setSpacing(12)

        hero = QFrame()
        hero.setObjectName("heroCard")
        hero_l = QVBoxLayout(hero)
        hero_l.setContentsMargins(18, 16, 18, 16)
        hero_l.setSpacing(10)
        self.signal_lbl = QLabel("WAIT")
        self.signal_lbl.setObjectName("signalWait")
        self.signal_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hero_l.addWidget(self.signal_lbl)
        self.conf_bar = QProgressBar()
        self.conf_bar.setRange(0, 100)
        self.conf_bar.setValue(0)
        self.conf_bar.setFormat("Confidence: %v%")
        hero_l.addWidget(self.conf_bar)
        left_l.addWidget(hero)

        stats = QFrame()
        stats.setObjectName("statsCard")
        stats_l = QVBoxLayout(stats)
        stats_l.setContentsMargins(14, 12, 14, 12)
        stats_l.setSpacing(4)
        st_title = QLabel("PERFORMANCE")
        st_title.setObjectName("statTitle")
        self.wr_lbl = QLabel(LEARNER.summary_both())
        self.wr_lbl.setObjectName("statValue")
        self.wr_lbl.setWordWrap(True)
        stats_l.addWidget(st_title)
        stats_l.addWidget(self.wr_lbl)
        left_l.addWidget(stats)

        grid = QGridLayout()
        grid.setSpacing(10)
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
            grid.addWidget(card, i // 2, i % 2)
        left_l.addLayout(grid)

        reasons_lbl = QLabel("SIGNAL REASONS")
        reasons_lbl.setObjectName("statTitle")
        left_l.addWidget(reasons_lbl)
        self.reasons_box = QTextEdit()
        self.reasons_box.setReadOnly(True)
        self.reasons_box.setMinimumHeight(170)
        left_l.addWidget(self.reasons_box, stretch=1)

        # Right — chart
        right = QWidget()
        right_l = QVBoxLayout(right)
        right_l.setContentsMargins(8, 0, 0, 0)
        chart_wrap = QFrame()
        chart_wrap.setObjectName("card")
        chart_inner = QVBoxLayout(chart_wrap)
        chart_inner.setContentsMargins(8, 8, 8, 8)
        if HAS_WEBENGINE:
            self.chart_view = QWebEngineView()
            self.chart_view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            chart_inner.addWidget(self.chart_view)
        else:
            self.chart_view = None
            self.chart_fallback = QLabel(
                "Install PySide6-WebEngine for live Plotly chart.\n"
                "Chart HTML is still written to temp on each refresh."
            )
            self.chart_fallback.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.chart_fallback.setWordWrap(True)
            chart_inner.addWidget(self.chart_fallback)
        right_l.addWidget(chart_wrap, stretch=1)

        status = QLabel("Status: idle")
        status.setObjectName("subtitle")
        self.status_lbl = status
        right_l.addWidget(status)

        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)
        outer.addWidget(splitter)

    def _clear_stats(self) -> None:
        n = self.db.clear_all()
        LEARNER.reset()
        self.wr_lbl.setText(LEARNER.summary_both())
        self.status_lbl.setText(f"Status: cleared {n} signals · learning reset")
        logger.info("UI clear stats: removed %s rows", n)

    def _mode_subtitle(self) -> str:
        if CONFIG.trading_mode == TradingMode.SCALP:
            confirm = CONFIG.confirm_timeframe.value if CONFIG.confirm_timeframe else "-"
            return (
                f"SCALP · Entry {CONFIG.entry_timeframe.value} + {confirm} confirm · "
                f"KZ required · thr {CONFIG.signal.min_confidence:.0f}% · "
                f"R:R >= {CONFIG.risk.min_risk_reward:.1f}"
            )
        return (
            f"SWING · Entry {CONFIG.entry_timeframe.value} · full confluence · "
            f"thr {CONFIG.signal.min_confidence:.0f}% · "
            f"R:R >= {CONFIG.risk.min_risk_reward:.1f}"
        )

    def _on_mode_changed(self, index: int) -> None:
        mode_val = self.mode_box.itemData(index)
        if not mode_val:
            return
        apply_trading_mode(mode_val)
        self.setWindowTitle(
            f"XAUUSD Signal Desk — {CONFIG.trading_mode.value.upper()}"
        )
        self.sub_lbl.setText(self._mode_subtitle())
        self.timer.setInterval(CONFIG.ui.refresh_ms)
        self._saved_fingerprint = None  # allow new alerts under new profile
        logger.info(
            "Switched to %s mode (entry=%s thr=%.0f RR=%.1f)",
            CONFIG.trading_mode.value,
            CONFIG.entry_timeframe.value,
            CONFIG.signal.min_confidence,
            CONFIG.risk.min_risk_reward,
        )
        self.refresh()

    def _format_source_label(self) -> str:
        src = CONFIG.data_source.value.upper()
        mode = CONFIG.trading_mode.value.upper()
        if self.provider and isinstance(self.provider, MT5Provider) and self.provider.is_connected():
            sym = self.provider._resolved_symbol or CONFIG.primary_symbol
            return f"Source: MT5 LIVE · {sym} · {mode}"
        if self.provider is None:
            return f"Source: {src} (Connecting...) · {mode}"
        return f"Source: {src} · {mode}"

    def _start_provider_init(self) -> None:
        self.status_lbl.setText("Status: Connecting to MT5 / market data provider...")
        self.refresh_btn.setEnabled(False)
        self._init_worker = InitProviderWorker(CONFIG.data_source)
        self._init_worker.connected.connect(self._on_provider_connected)
        self._init_worker.failed.connect(self._on_provider_failed)
        self._init_worker.start()

    def _on_provider_connected(self, provider: DataProvider) -> None:
        self.provider = provider
        self._source_detail = self._format_source_label()
        self.source_lbl.setText(self._source_detail)
        self.status_lbl.setText("Status: Provider connected · analyzing initial data...")
        self.timer.start()
        self.refresh()

    def _on_provider_failed(self, msg: str) -> None:
        self.status_lbl.setText(f"Status: Connection failed — {msg}")
        self.refresh_btn.setEnabled(True)
        self.clock_lbl.setText(utc_now().strftime("%Y-%m-%d %H:%M:%S UTC"))

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
        self.clock_lbl.setText(utc_now().strftime("%Y-%m-%d %H:%M:%S UTC"))

    def _on_result(self, analysis: TopDownAnalysis, signal: TradeSignal) -> None:
        self._last_analysis = analysis
        self._last_signal = signal
        self.refresh_btn.setEnabled(True)
        self.clock_lbl.setText(utc_now().strftime("%Y-%m-%d %H:%M:%S UTC"))
        self.source_lbl.setText(
            f"Source: {CONFIG.data_source.value.upper()} · {CONFIG.trading_mode.value.upper()}"
        )

        # Signal label styling
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
        color_conf = "#3dd68c" if signal.confidence >= thr else "#e6c07b"
        self.conf_bar.setStyleSheet(
            f"QProgressBar::chunk {{ background-color: {color_conf}; border-radius: 5px; }}"
        )
        self.conf_bar.setFormat(f"Confidence: %v% (need >={thr}%)")

        self.cards["price"].set_value(f"{analysis.price:.2f}", "#f0d78c")
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
            self.cards["sl"].set_value(f"{r.stop_loss:.2f}", "#f07178")
            self.cards["tp1"].set_value(f"{r.take_profit_1:.2f}", "#3dd68c")
            self.cards["tp2"].set_value(f"{r.take_profit_2:.2f}", "#3dd68c")
            self.cards["tp3"].set_value(f"{r.take_profit_3:.2f}", "#3dd68c")
            self.cards["rr"].set_value(f"1 : {r.risk_reward:.2f}")
            self.cards["lots"].set_value(f"{r.lot_size:.2f}")
        else:
            for k in ("entry", "sl", "tp1", "tp2", "tp3", "rr", "lots"):
                self.cards[k].set_value("—")

        if signal.is_actionable:
            text = "\n".join(signal.summary_lines())
        else:
            text = "NO TRADE\nWait for better confirmation.\n\n" + "\n".join(
                signal.summary_lines()
            )
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

        # Persist actionable signals; alert+screenshot after chart so UI is current
        pending_alert = False
        if signal.is_actionable:
            fp = f"{signal.mode}:{signal.direction.value}:{round(signal.price, 1)}:{int(signal.confidence)}"
            if fp != self._saved_fingerprint:
                self.db.save_signal(signal)
                pending_alert = True
                self._saved_fingerprint = fp

        # Chart
        try:
            fig = build_chart(analysis, signal, CONFIG.ui.chart_timeframe)
            fig.write_html(str(self._chart_path), include_plotlyjs="directory", full_html=True)
            if self.chart_view is not None:
                self.chart_view.load(QUrl.fromLocalFile(str(self._chart_path)))
            else:
                self.chart_fallback.setText(
                    f"Chart saved: {self._chart_path}\n"
                    f"Price {analysis.price:.2f} · {signal.direction.value} · {signal.confidence:.0f}%"
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Chart update failed: %s", exc)

        if pending_alert:
            from PySide6.QtWidgets import QApplication

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
