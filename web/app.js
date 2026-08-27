/**
 * XAUUSD Signal Desk Pro — Android & Web Client Application
 * Includes Light / Dark Mode Shifter, High-Contrast Sharp Text, and Android Chart Optimization
 */

const $ = (id) => document.getElementById(id);
const $$ = (sel) => document.querySelectorAll(sel);

// App State
let state = {
  activeTab: "chart",
  activeTf: "M15",
  activeView: "original",
  activeMode: "swing",
  soundEnabled: true,
  theme: localStorage.getItem("desk_theme") || "dark",
  lastPrice: null,
  lastSignalFingerprint: null,
  lastChartData: null,
};

// ==========================================================================
// THEME SWITCHER (Light / Dark Mode)
// ==========================================================================
const SUN_PATH = "M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z";
const MOON_PATH = "M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z";

function applyTheme(themeName) {
  state.theme = themeName;
  document.documentElement.setAttribute("data-theme", themeName);
  localStorage.setItem("desk_theme", themeName);

  const iconPath = $("themeIconPath");
  if (iconPath) {
    iconPath.setAttribute("d", themeName === "light" ? MOON_PATH : SUN_PATH);
  }

  const themeLabel = $("themeLabel");
  if (themeLabel) {
    themeLabel.textContent = themeName === "light" ? "Light Theme" : "Dark Theme";
  }

  const themeToggle = $("themeToggle");
  if (themeToggle) {
    themeToggle.checked = themeName === "light";
  }

  // Re-render chart with new theme colors
  if (state.lastChartData) {
    paintChart(state.lastChartData);
  }
}

function toggleTheme() {
  const next = state.theme === "dark" ? "light" : "dark";
  applyTheme(next);
  showToast(`Switched to ${next.toUpperCase()} Mode`);
}

// ==========================================================================
// AUDIO SYNTHESIZER (Web Audio API)
// ==========================================================================
class SoundAlerts {
  constructor() {
    this.ctx = null;
  }
  init() {
    if (!this.ctx) {
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      if (AudioCtx) this.ctx = new AudioCtx();
    }
  }
  playSignalChime(isBuy = true) {
    if (!state.soundEnabled) return;
    try {
      this.init();
      if (!this.ctx) return;
      if (this.ctx.state === "suspended") this.ctx.resume();

      const now = this.ctx.currentTime;
      const osc1 = this.ctx.createOscillator();
      const osc2 = this.ctx.createOscillator();
      const gain = this.ctx.createGain();

      osc1.type = "sine";
      osc2.type = "triangle";

      if (isBuy) {
        osc1.frequency.setValueAtTime(587.33, now); // D5
        osc1.frequency.exponentialRampToValueAtTime(880.00, now + 0.15); // A5
        osc2.frequency.setValueAtTime(1174.66, now + 0.15); // D6
      } else {
        osc1.frequency.setValueAtTime(880.00, now); // A5
        osc1.frequency.exponentialRampToValueAtTime(587.33, now + 0.15); // D5
        osc2.frequency.setValueAtTime(440.00, now + 0.15); // A4
      }

      gain.gain.setValueAtTime(0.3, now);
      gain.gain.exponentialRampToValueAtTime(0.001, now + 0.4);

      osc1.connect(gain);
      osc2.connect(gain);
      gain.connect(this.ctx.destination);

      osc1.start(now);
      osc2.start(now + 0.04);
      osc1.stop(now + 0.4);
      osc2.stop(now + 0.4);
    } catch (e) {
      console.warn("Audio chime error:", e);
    }
  }
}
const audioAlerts = new SoundAlerts();

// ==========================================================================
// TOAST NOTIFICATIONS
// ==========================================================================
function showToast(msg, type = "gold", duration = 2500) {
  const container = $("toastContainer");
  if (!container) return;
  const el = document.createElement("div");
  el.className = `toast ${type}`;
  el.innerHTML = `<span>${msg}</span>`;
  container.appendChild(el);
  setTimeout(() => {
    el.style.opacity = "0";
    el.style.transform = "translateY(-6px)";
    setTimeout(() => el.remove(), 250);
  }, duration);
}

function fmt(n, d = 2) {
  if (n == null || Number.isNaN(Number(n))) return "—";
  return Number(n).toLocaleString(undefined, { minimumFractionDigits: d, maximumFractionDigits: d });
}

// ==========================================================================
// ANDROID OPTIMIZED PLOTLY CHART RENDERING
// ==========================================================================
function paintChart(chart) {
  state.lastChartData = chart;
  const el = $("chart");
  const loading = $("chartLoading");
  if (!el) return;

  if (!window.Plotly) {
    // Wait for local Plotly bundle
    setTimeout(() => {
      if (window.Plotly && state.lastChartData) paintChart(state.lastChartData);
    }, 100);
    return;
  }

  if (!chart || (!chart.ohlc?.x?.length && chart.mode !== "depth")) {
    if (loading) {
      loading.classList.add("show");
      loading.style.display = "flex";
    }
    return;
  }

  if (loading) {
    loading.classList.remove("show");
    loading.style.display = "none";
  }

  const isLight = state.theme === "light";
  const paperBg = isLight ? "#ffffff" : "#181a20";
  const gridColor = isLight ? "#f1f5f9" : "#23272e";
  const textColor = isLight ? "#64748b" : "#9ca3af";

  // Depth Chart Mode
  if (chart.mode === "depth") {
    Plotly.react(
      "chart",
      [
        {
          x: chart.bids?.x || [],
          y: chart.bids?.y || [],
          type: "scatter",
          mode: "lines",
          fill: "tozerox",
          name: "Bids",
          line: { color: "#0ecb81", width: 2 },
          fillcolor: isLight ? "rgba(5, 150, 105, 0.15)" : "rgba(14, 203, 129, 0.2)",
        },
        {
          x: chart.asks?.x || [],
          y: chart.asks?.y || [],
          type: "scatter",
          mode: "lines",
          fill: "tozerox",
          name: "Asks",
          line: { color: "#f6465d", width: 2 },
          fillcolor: isLight ? "rgba(220, 38, 38, 0.15)" : "rgba(246, 70, 93, 0.2)",
        },
      ],
      {
        margin: { t: 8, r: 35, l: 30, b: 24 },
        paper_bgcolor: paperBg,
        plot_bgcolor: paperBg,
        font: { color: textColor, family: "system-ui, sans-serif", size: 10 },
        xaxis: { gridcolor: gridColor, title: { text: "Total Size", font: { size: 10 } } },
        yaxis: { gridcolor: gridColor, side: "right", title: { text: "Price", font: { size: 10 } } },
        showlegend: false,
      },
      { responsive: true, displayModeBar: false }
    );
    return;
  }

  // OHLC Candlestick Mode
  const ohlc = chart.ohlc || {};
  const traces = [];

  // Main Candlesticks
  if (ohlc.x && ohlc.x.length > 0) {
    traces.push({
      type: "candlestick",
      x: ohlc.x,
      open: ohlc.open,
      high: ohlc.high,
      low: ohlc.low,
      close: ohlc.close,
      increasing: { line: { color: "#0ecb81", width: 1 }, fillcolor: "#0ecb81" },
      decreasing: { line: { color: "#f6465d", width: 1 }, fillcolor: "#f6465d" },
      name: "OHLC",
    });
  }

  // Moving Averages
  if (chart.ma7?.x) {
    traces.push({
      x: chart.ma7.x,
      y: chart.ma7.y,
      type: "scatter",
      mode: "lines",
      name: "MA 7",
      line: { color: "#f0b90b", width: 1.2 },
    });
  }
  if (chart.ma25?.x) {
    traces.push({
      x: chart.ma25.x,
      y: chart.ma25.y,
      type: "scatter",
      mode: "lines",
      name: "MA 25",
      line: { color: "#e040fb", width: 1.2 },
    });
  }
  if (chart.ma99?.x) {
    traces.push({
      x: chart.ma99.x,
      y: chart.ma99.y,
      type: "scatter",
      mode: "lines",
      name: "MA 99",
      line: { color: isLight ? "#7c3aed" : "#a78bfa", width: 1.2 },
    });
  }

  // TradingView EMAs
  if (chart.ema20?.x) {
    traces.push({
      x: chart.ema20.x,
      y: chart.ema20.y,
      type: "scatter",
      mode: "lines",
      name: "EMA 20",
      line: { color: "#2563eb", width: 1.4 },
    });
  }
  if (chart.ema50?.x) {
    traces.push({
      x: chart.ema50.x,
      y: chart.ema50.y,
      type: "scatter",
      mode: "lines",
      name: "EMA 50",
      line: { color: "#ea580c", width: 1.4 },
    });
  }
  if (chart.ema200?.x) {
    traces.push({
      x: chart.ema200.x,
      y: chart.ema200.y,
      type: "scatter",
      mode: "lines",
      name: "EMA 200",
      line: { color: isLight ? "#0f172a" : "#ffffff", width: 1.8 },
    });
  }

  // AI Forecast Path Mode
  if (chart.forecast?.active && chart.forecast.path_x) {
    traces.push({
      x: chart.forecast.path_x,
      y: chart.forecast.path_y,
      type: "scatter",
      mode: "lines+markers",
      name: "AI Forecast",
      line: { color: chart.forecast.color || "#f0b90b", width: 2, dash: "dot" },
    });
  }

  // Active Signal Targets & Session Levels Overlay
  const sig = chart.signal;
  const shapes = [];
  const annotations = [];

  // Session Reference Lines (Asian High/Low, London High/Low, NY High/Low)
  const ict = state.analysis?.ict;
  const sessions = [
    { name: "Asia H", val: ict?.asia_high, col: "#c99400" },
    { name: "Asia L", val: ict?.asia_low, col: "#c99400" },
    { name: "London H", val: chart.accuracy?.london_high, col: "#2563eb" },
    { name: "London L", val: chart.accuracy?.london_low, col: "#2563eb" },
    { name: "NY H", val: chart.accuracy?.ny_high, col: "#e040fb" },
    { name: "NY L", val: chart.accuracy?.ny_low, col: "#e040fb" },
  ];

  sessions.forEach(s => {
    if (s.val) {
      shapes.push({
        type: "line",
        xref: "paper",
        x0: 0,
        x1: 1,
        y0: s.val,
        y1: s.val,
        line: { color: s.col, width: 1.1, dash: "dash" },
      });
      annotations.push({
        xref: "paper",
        x: 0.98,
        xanchor: "right",
        y: s.val,
        yanchor: "bottom",
        text: `${s.name}: ${Number(s.val).toFixed(2)}`,
        showarrow: false,
        font: { color: s.col, size: 9, family: "system-ui, sans-serif" },
        bgcolor: isLight ? "rgba(255,255,255,0.85)" : "rgba(15,23,42,0.85)",
        bordercolor: s.col,
        borderwidth: 1,
        borderpad: 2,
      });
    }
  });

  if (sig && sig.active) {
    const x0 = ohlc.x ? ohlc.x[0] : undefined;
    const x1 = sig.flow_x ? sig.flow_x[sig.flow_x.length - 1] : (ohlc.x ? ohlc.x[ohlc.x.length - 1] : undefined);

    if (x0 && x1) {
      shapes.push({
        type: "line",
        x0: x0,
        x1: x1,
        y0: sig.entry,
        y1: sig.entry,
        line: { color: "#f0b90b", width: 1.5, dash: "dash" },
      });
      shapes.push({
        type: "line",
        x0: x0,
        x1: x1,
        y0: sig.sl,
        y1: sig.sl,
        line: { color: "#f6465d", width: 1.5, dash: "dash" },
      });
      shapes.push({
        type: "line",
        x0: x0,
        x1: x1,
        y0: sig.tp1,
        y1: sig.tp1,
        line: { color: "#0ecb81", width: 1.5, dash: "dash" },
      });
    }

    if (sig.flow_x && sig.flow_y) {
      traces.push({
        x: sig.flow_x,
        y: sig.flow_y,
        type: "scatter",
        mode: "lines+markers",
        name: "Signal Flow",
        line: { color: sig.side === "BUY" ? "#0ecb81" : "#f6465d", width: 2, dash: "dot" },
      });
    }
  }

  const layout = {
    margin: { t: 8, r: 38, l: 4, b: 22 },
    paper_bgcolor: paperBg,
    plot_bgcolor: paperBg,
    font: { color: textColor, family: "system-ui, sans-serif", size: 10 },
    xaxis: {
      gridcolor: gridColor,
      rangeslider: { visible: false },
      type: "date",
      tickformat: chart.tickformat || "%H:%M",
      tickfont: { size: 9.5 },
      automargin: true,
    },
    yaxis: {
      gridcolor: gridColor,
      side: "right",
      tickformat: ".2f",
      tickfont: { size: 9.5 },
      nticks: 6,
      autorange: true,
      automargin: true,
    },
    showlegend: false,
    shapes: shapes,
    annotations: annotations,
    dragmode: "pan",
  };

  // Update floating OHLC overlay text
  const ohlcEl = $("chartOhlcText");
  const maEl = $("chartMaText");
  if (ohlcEl && ohlc.close && ohlc.close.length > 0) {
    const len = ohlc.close.length;
    const o = ohlc.open[len - 1];
    const h = ohlc.high[len - 1];
    const l = ohlc.low[len - 1];
    const c = ohlc.close[len - 1];
    const chg = c - o;
    const pct = o ? (chg / o * 100).toFixed(2) : "0.00";
    const isUp = chg >= 0;
    const sign = isUp ? "+" : "";
    const colClass = isUp ? "up" : "dn";
    ohlcEl.innerHTML = `O:<span>${o.toFixed(2)}</span> H:<span>${h.toFixed(2)}</span> L:<span>${l.toFixed(2)}</span> C:<span class="${colClass}">${c.toFixed(2)} (${sign}${pct}%)</span>`;
  }
  if (maEl) {
    let maHtml = "";
    if (chart.ma7?.y?.length) {
      const v = chart.ma7.y[chart.ma7.y.length - 1];
      if (v != null) maHtml += `<span class="ma7">MA7:${v.toFixed(2)}</span> `;
    }
    if (chart.ma25?.y?.length) {
      const v = chart.ma25.y[chart.ma25.y.length - 1];
      if (v != null) maHtml += `<span class="ma25">MA25:${v.toFixed(2)}</span> `;
    }
    if (chart.ma99?.y?.length) {
      const v = chart.ma99.y[chart.ma99.y.length - 1];
      if (v != null) maHtml += `<span class="ma99">MA99:${v.toFixed(2)}</span> `;
    }
    if (chart.ema20?.y?.length) {
      const v = chart.ema20.y[chart.ema20.y.length - 1];
      if (v != null) maHtml += `<span class="ema20">EMA20:${v.toFixed(2)}</span> `;
    }
    if (chart.ema50?.y?.length) {
      const v = chart.ema50.y[chart.ema50.y.length - 1];
      if (v != null) maHtml += `<span class="ema50">EMA50:${v.toFixed(2)}</span> `;
    }
    if (chart.ema200?.y?.length) {
      const v = chart.ema200.y[chart.ema200.y.length - 1];
      if (v != null) maHtml += `<span class="ema200">EMA200:${v.toFixed(2)}</span> `;
    }
    maEl.innerHTML = maHtml || "Moving Averages —";
  }

  Plotly.react("chart", traces, layout, {
    responsive: true,
    displayModeBar: false,
    scrollZoom: true,
    doubleClick: "reset",
  });
}

// ==========================================================================
// ORDER BOOK LADDER RENDERING
// ==========================================================================
function paintBook(book, currentPrice) {
  const el = $("book");
  if (!el) return;
  if (!book || (!book.asks?.length && !book.bids?.length)) {
    el.innerHTML = '<div class="book-loading muted text-center">No order book stream available</div>';
    return;
  }

  const maxTotal = Math.max(
    ...(book.asks || []).map((x) => x.t || x.total || 0),
    ...(book.bids || []).map((x) => x.t || x.total || 0),
    1
  );

  const formatRow = (lvl, side) => {
    const p = lvl.p || lvl.price || 0;
    const a = lvl.a || lvl.amount || lvl.volume || 0;
    const t = lvl.t || lvl.total || 0;
    const pct = Math.min(100, Math.round((t / maxTotal) * 100));
    return `
      <div class="book-row ${side}">
        <div class="book-depth-bg" style="width: ${pct}%;"></div>
        <span>${fmt(p)}</span>
        <span style="color:var(--text-sub);">${fmt(a, 3)}</span>
        <span style="color:var(--text-muted);">${fmt(t, 3)}</span>
      </div>
    `;
  };

  const asks = (book.asks || []).slice(0, 7).reverse().map((x) => formatRow(x, "ask")).join("");
  const bids = (book.bids || []).slice(0, 7).map((x) => formatRow(x, "bid")).join("");

  const midHtml = currentPrice ? `<div class="book-mid-price">${fmt(currentPrice)}</div>` : '<hr style="border-color:var(--border);margin:3px 0;"/>';

  el.innerHTML = `
    <div class="book-row header">
      <span>Price (USD)</span>
      <span>Size</span>
      <span>Total</span>
    </div>
    ${asks}
    ${midHtml}
    ${bids}
  `;

  // Imbalance
  const totalBids = (book.bids || []).reduce((acc, x) => acc + (x.a || x.amount || 0), 0);
  const totalAsks = (book.asks || []).reduce((acc, x) => acc + (x.a || x.amount || 0), 0);
  const sum = totalBids + totalAsks;
  if (sum > 0) {
    const bidPct = Math.round((totalBids / sum) * 100);
    const askPct = 100 - bidPct;
    if ($("imbalanceBids")) $("imbalanceBids").style.width = `${bidPct}%`;
    if ($("imbalanceAsks")) $("imbalanceAsks").style.width = `${askPct}%`;
    if ($("bidDominance")) $("bidDominance").textContent = `Bids ${bidPct}%`;
    if ($("askDominance")) $("askDominance").textContent = `Asks ${askPct}%`;
  }
}

// ==========================================================================
// STATE APPLIER (Binds incoming API JSON to DOM)
// ==========================================================================
function applyState(s) {
  if (!s) return;

  // Metadata
  if ($("meta")) $("meta").textContent = `${s.source || "MT5"} · ${(s.mode || "SWING").toUpperCase()} · ${s.clock || ""}`;
  if ($("pair")) $("pair").textContent = s.pair || "XAU/USD";
  if ($("drawerSource")) $("drawerSource").textContent = (s.source || "MT5").toUpperCase();
  if ($("drawerClock")) $("drawerClock").textContent = s.clock || "—";
  if ($("drawerStatus")) $("drawerStatus").textContent = s.status || "Active";
  if ($("drawerSpread")) $("drawerSpread").textContent = `${fmt(s.spread)} USD`;

  // Price Flash
  const last = s.stats?.last ?? s.price;
  const up = (s.stats?.change || 0) >= 0;
  const pricePill = $("pricePill");

  if (state.lastPrice !== null && last !== state.lastPrice) {
    pricePill?.classList.remove("flash-up", "flash-dn");
    void pricePill?.offsetWidth;
    pricePill?.classList.add(last > state.lastPrice ? "flash-up" : "flash-dn");
    setTimeout(() => pricePill?.classList.remove("flash-up", "flash-dn"), 500);
  }
  state.lastPrice = last;

  if ($("last")) {
    $("last").textContent = fmt(last);
    $("last").className = "price-val " + (up ? "up" : "dn");
  }

  const sign = up ? "+" : "";
  if ($("change")) {
    $("change").textContent = `${sign}${fmt(s.stats?.change)}  (${sign}${fmt(s.stats?.pct)}%)`;
    $("change").className = "price-chg " + (up ? "up" : "dn");
  }

  // Quick Stats
  if ($("high")) $("high").textContent = fmt(s.stats?.high);
  if ($("low")) $("low").textContent = fmt(s.stats?.low);
  if ($("spread")) $("spread").textContent = fmt(s.spread);
  if ($("vol")) $("vol").textContent = fmt(s.stats?.vol_base, 2);
  if ($("bookSpread")) $("bookSpread").textContent = fmt(s.spread);

  // Confluences in Chart Tab
  const sig = s.signal || {};
  if ($("chartTrend")) $("chartTrend").textContent = sig.trend || "—";
  if ($("chartStructure")) $("chartStructure").textContent = sig.structure || "—";
  if ($("chartSession")) $("chartSession").textContent = sig.session || "—";
  if ($("chartNews")) $("chartNews").textContent = sig.news || "—";

  // Signal Tab & Hero Card
  const isActionable = Boolean(sig.actionable);
  const label = sig.label || "NO TRADE";
  if ($("sigLabel")) {
    $("sigLabel").textContent = label;
    $("sigLabel").className = "sig-direction-tag " + (label === "BUY" ? "up" : label === "SELL" ? "dn" : "");
  }
  if ($("sigModeTag")) $("sigModeTag").textContent = (s.mode || "SWING").toUpperCase();

  const conf = Math.round(sig.confidence || 0);
  const thr = Math.round(sig.threshold || 85);
  if ($("confText")) $("confText").textContent = `Confidence ${conf}%`;
  if ($("confReqText")) $("confReqText").textContent = `Need ≥ ${thr}%`;

  if ($("confBar")) {
    $("confBar").style.width = `${Math.min(100, Math.max(0, conf))}%`;
    $("confBar").className = "conf-progress-fill " + (conf >= thr ? "success" : "");
  }
  if ($("confPin")) $("confPin").style.left = `${thr}%`;

  // Trade Plan Values
  const r = sig.risk;
  if ($("entry")) $("entry").textContent = r ? fmt(r.entry) : "—";
  if ($("sl")) $("sl").textContent = r ? fmt(r.sl) : "—";
  if ($("tp1")) $("tp1").textContent = r ? fmt(r.tp1) : "—";
  if ($("tp2")) $("tp2").textContent = r ? fmt(r.tp2) : "—";
  if ($("tp3")) $("tp3").textContent = r ? fmt(r.tp3) : "—";
  if ($("rr")) $("rr").textContent = r ? `1 : ${fmt(r.rr)}` : "—";
  if ($("lots")) $("lots").textContent = r ? fmt(r.lots, 2) : "—";
  if ($("atrVal")) $("atrVal").textContent = fmt(sig.atr);

  // Confluence Verification Checklist
  updateConfluenceItem("cfTrend", sig.trend, sig.features?.trend_aligned);
  updateConfluenceItem("cfStruct", sig.structure, sig.features?.structure_aligned);
  updateConfluenceItem("cfOB", sig.features?.ob_mitigated ? "Hit OB Zone" : "Near OB", sig.features?.ob_confluence);
  updateConfluenceItem("cfFVG", sig.features?.fvg_entry ? "FVG Active" : "No FVG", sig.features?.fvg_confluence);
  updateConfluenceItem("cfLiq", sig.features?.liquidity_swept ? "Swept" : "Untested", sig.features?.liquidity_confluence);
  updateConfluenceItem("cfKZ", sig.session, sig.features?.session_confluence);
  updateConfluenceItem("cfCandle", sig.features?.price_action || "Neutral", sig.features?.candle_confluence);
  updateConfluenceItem("cfNews", sig.news || "Clean", sig.features?.news_clear);

  // Reasons Log
  if ($("reasons")) {
    $("reasons").textContent = (sig.lines || []).join("\n") || "No signal log available.";
  }

  // Floating Actionable Signal Banner
  const banner = $("banner");
  const tabBadge = $("sigTabBadge");
  const fp = `${s.mode}:${sig.direction}:${Math.round(last || 0)}:${conf}`;

  if (isActionable && r) {
    if (banner) {
      banner.className = "action-banner " + (sig.direction === "BUY" ? "buy" : "sell");
      if ($("bannerBadge")) $("bannerBadge").textContent = sig.direction;
      if ($("bannerText")) {
        $("bannerText").innerHTML = `<b>${sig.direction} Signal (${conf}%)</b> · Entry: <b>${fmt(r.entry)}</b> | SL: <b>${fmt(r.sl)}</b> | TP1: <b>${fmt(r.tp1)}</b>`;
      }
    }
    tabBadge?.classList.remove("hidden");

    if (state.lastSignalFingerprint !== fp) {
      state.lastSignalFingerprint = fp;
      audioAlerts.playSignalChime(sig.direction === "BUY");
      showToast(`⚡ New ${sig.direction} Signal @ ${fmt(r.entry)} (${conf}%)`, sig.direction === "BUY" ? "success" : "danger");
    }
  } else {
    if (banner) banner.className = "action-banner hidden";
    tabBadge?.classList.add("hidden");
  }

  // Top-Down Matrix
  if (s.analysis?.mtf && $("mtfBody")) {
    renderMtfTable(s.analysis.mtf);
  }

  // ICT Details
  if (s.analysis?.ict) {
    if ($("ictSession")) $("ictSession").textContent = s.analysis.ict.session || "—";
    if ($("ictKZ")) $("ictKZ").textContent = s.analysis.ict.killzone || "Outside KZ";
    if ($("ictAsiaH")) $("ictAsiaH").textContent = fmt(s.analysis.ict.asia_high);
    if ($("ictAsiaL")) $("ictAsiaL").textContent = fmt(s.analysis.ict.asia_low);
  }

  // SMC Zones
  if (s.analysis?.smc) {
    if ($("smcBullOB")) $("smcBullOB").textContent = fmt(s.analysis.smc.bull_ob);
    if ($("smcBearOB")) $("smcBearOB").textContent = fmt(s.analysis.smc.bear_ob);
    if ($("smcFVG")) $("smcFVG").textContent = s.analysis.smc.fvg || "None in Range";
    if ($("smcPools")) $("smcPools").textContent = s.analysis.smc.sweeps || "Clean";
  }

  // Performance & History
  if (s.performance) {
    if ($("perfSwing")) $("perfSwing").textContent = `${s.performance.swing?.winrate || 0}% (${s.performance.swing?.wins || 0}W/${s.performance.swing?.losses || 0}L)`;
    if ($("perfIntraday")) $("perfIntraday").textContent = `${s.performance.intraday?.winrate || 0}% (${s.performance.intraday?.wins || 0}W/${s.performance.intraday?.losses || 0}L)`;
    if ($("perfScalp")) $("perfScalp").textContent = `${s.performance.scalp?.winrate || 0}% (${s.performance.scalp?.wins || 0}W/${s.performance.scalp?.losses || 0}L)`;
    if ($("perfPredict")) $("perfPredict").textContent = `${s.performance.predict?.winrate || 0}%`;
  }
  if (s.history && $("historyBody")) {
    renderHistoryTable(s.history);
  }

  if (s.learner && $("drawerLearner")) {
    $("drawerLearner").textContent = s.learner;
  }

  // Order Book & Chart Painting
  paintBook(s.book, last);
  paintChart(s.chart);
}

function updateConfluenceItem(id, text, isPass) {
  const el = $(id);
  if (!el) return;
  if (text) el.querySelector("b").textContent = text;
  el.classList.remove("pass", "fail");
  if (isPass === true) el.classList.add("pass");
  else if (isPass === false) el.classList.add("fail");
}

function renderMtfTable(mtfList) {
  const body = $("mtfBody");
  if (!body) return;
  body.innerHTML = mtfList
    .map(
      (m) => `
    <tr>
      <td><b>${m.tf}</b></td>
      <td class="${m.trend === 'BULLISH' ? 'up' : m.trend === 'BEARISH' ? 'dn' : 'muted'}">${m.trend || '—'}</td>
      <td>${m.structure || '—'}</td>
      <td>${fmt(m.rsi, 1)}</td>
      <td class="${m.macd >= 0 ? 'up' : 'dn'}">${fmt(m.macd, 2)}</td>
      <td>${m.smc || '—'}</td>
    </tr>
  `
    )
    .join("");
}

function renderHistoryTable(historyList) {
  const body = $("historyBody");
  if (!body) return;
  if (!historyList.length) {
    body.innerHTML = '<tr><td colspan="8" class="muted text-center">No trades logged yet</td></tr>';
    return;
  }
  body.innerHTML = historyList
    .slice(0, 15)
    .map(
      (h) => `
    <tr>
      <td class="muted">${h.time || '—'}</td>
      <td>${(h.mode || '').toUpperCase()}</td>
      <td class="${h.side === 'BUY' ? 'up' : 'dn'}"><b>${h.side}</b></td>
      <td class="font-mono">${fmt(h.entry)}</td>
      <td class="font-mono dn">${fmt(h.sl)}</td>
      <td class="font-mono up">${fmt(h.tp1)}</td>
      <td>${Math.round(h.confidence || 0)}%</td>
      <td><span class="conf-chip ${h.outcome === 'WIN' ? 'pass' : h.outcome === 'LOSS' ? 'fail' : ''}">${h.outcome || 'PENDING'}</span></td>
    </tr>
  `
    )
    .join("");
}

// ==========================================================================
// POLLING API
// ==========================================================================
async function poll() {
  try {
    const res = await fetch("/api/state");
    if (!res.ok) throw new Error("HTTP error " + res.status);
    const data = await res.json();
    applyState(data);
    const dot = $("liveDot");
    if (dot) dot.style.background = "#0ecb81";
  } catch (err) {
    console.warn("Polling error:", err);
    const dot = $("liveDot");
    if (dot) dot.style.background = "#f6465d";
    if ($("meta")) $("meta").textContent = "Reconnecting to server…";
  }
}

// ==========================================================================
// EVENT LISTENERS & USER INTERACTIONS
// ==========================================================================

// Tab Switching
function switchTab(tabId) {
  state.activeTab = tabId;
  $$(".tab-panel").forEach((p) => p.classList.toggle("active", p.id === `tab-${tabId}`));
  $$(".app-bottom-nav .nav-tab").forEach((t) => t.classList.toggle("active", t.dataset.tab === tabId));

  if (tabId === "chart" && window.Plotly) {
    setTimeout(() => Plotly.Plots.resize("chart"), 40);
  }
  closeDrawer();
}

$$(".app-bottom-nav .nav-tab").forEach((btn) => {
  btn.addEventListener("click", () => switchTab(btn.dataset.tab));
});
$$(".drawer-nav-item").forEach((btn) => {
  btn.addEventListener("click", () => switchTab(btn.dataset.tab));
});

// Burger Drawer Open/Close
function openDrawer() {
  $("drawer")?.classList.add("open");
  $("drawerBackdrop")?.classList.add("open");
}
function closeDrawer() {
  $("drawer")?.classList.remove("open");
  $("drawerBackdrop")?.classList.remove("open");
}
$("burgerBtn")?.addEventListener("click", openDrawer);
$("drawerClose")?.addEventListener("click", closeDrawer);
$("drawerBackdrop")?.addEventListener("click", closeDrawer);

// Theme Toggle Handlers
$("themeBtn")?.addEventListener("click", toggleTheme);
$("themeToggle")?.addEventListener("change", (e) => {
  applyTheme(e.target.checked ? "light" : "dark");
});

// Timeframe Selection
$$("#tfRow .tf-btn").forEach((btn) => {
  btn.addEventListener("click", async () => {
    $$("#tfRow .tf-btn").forEach((b) => b.classList.remove("on"));
    btn.classList.add("on");
    state.activeTf = btn.dataset.tf;
    $("chartLoading")?.classList.add("show");
    try {
      await fetch("/api/tf", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tf: btn.dataset.tf }),
      });
      poll();
    } catch (e) {
      console.warn("TF change failed:", e);
    }
  });
});

// Chart View Mode Selection
$$("#chartViewRow .view-chip").forEach((btn) => {
  btn.addEventListener("click", async () => {
    $$("#chartViewRow .view-chip").forEach((b) => b.classList.remove("on"));
    btn.classList.add("on");
    state.activeView = btn.dataset.view;
    $("chartLoading")?.classList.add("show");
    try {
      await fetch("/api/view", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ view: btn.dataset.view }),
      });
      poll();
    } catch (e) {
      console.warn("View mode change failed:", e);
    }
  });
});

// Trading Profile Mode
$$("#drawerModes .mode-chip").forEach((btn) => {
  btn.addEventListener("click", async () => {
    $$("#drawerModes .mode-chip").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    state.activeMode = btn.dataset.mode;
    showToast(`Profile: ${btn.dataset.mode.toUpperCase()}`);
    try {
      await fetch("/api/mode", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mode: btn.dataset.mode }),
      });
      poll();
    } catch (e) {
      console.warn("Mode change failed:", e);
    }
  });
});

// Settings Handlers
$("confSlider")?.addEventListener("input", (e) => {
  if ($("confThresholdVal")) $("confThresholdVal").textContent = `${e.target.value}%`;
});
$("confSlider")?.addEventListener("change", async (e) => {
  try {
    await fetch("/api/settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ min_confidence: Number(e.target.value) }),
    });
    showToast(`Threshold: ${e.target.value}%`);
    poll();
  } catch (e) {
    console.warn("Settings change failed:", e);
  }
});

$("riskSelect")?.addEventListener("change", async (e) => {
  try {
    await fetch("/api/settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ max_risk_percent: Number(e.target.value) }),
    });
    if ($("riskVal")) $("riskVal").textContent = `${e.target.value}%`;
    showToast(`Risk per trade: ${e.target.value}%`);
    poll();
  } catch (e) {
    console.warn("Risk change failed:", e);
  }
});

// Sound Toggle
$("soundToggle")?.addEventListener("change", (e) => {
  state.soundEnabled = e.target.checked;
  $("soundBtn")?.classList.toggle("muted", !state.soundEnabled);
  showToast(state.soundEnabled ? "Sound Alerts Enabled" : "Sound Alerts Muted");
});
$("soundBtn")?.addEventListener("click", () => {
  state.soundEnabled = !state.soundEnabled;
  if ($("soundToggle")) $("soundToggle").checked = state.soundEnabled;
  $("soundBtn")?.classList.toggle("muted", !state.soundEnabled);
  showToast(state.soundEnabled ? "Sound Alerts Enabled" : "Sound Alerts Muted");
});

// Force Refresh
$("refreshBtn")?.addEventListener("click", () => {
  showToast("Refreshing market feed…");
  poll();
});

// Clear Stats & History
$("clearStatsBtn")?.addEventListener("click", async () => {
  if (confirm("Clear all signals history and reset learning stats?")) {
    try {
      const res = await fetch("/api/clear", { method: "POST" });
      const data = await res.json();
      if (data.ok) {
        showToast(`Cleared ${data.cleared || 0} signals`, "success");
        poll();
      }
    } catch (err) {
      console.warn("Clear stats failed:", err);
    }
  }
});

// Copy Signal Button
$("bannerCopyBtn")?.addEventListener("click", () => {
  const label = $("bannerBadge")?.textContent || "BUY";
  const entry = $("entry")?.textContent || "—";
  const sl = $("sl")?.textContent || "—";
  const tp1 = $("tp1")?.textContent || "—";
  const tp2 = $("tp2")?.textContent || "—";
  const text = `🚨 ${label} XAUUSD @ ${entry}\n🛑 Stop Loss: ${sl}\n🎯 TP1: ${tp1}\n🎯 TP2: ${tp2}\n⚖️ R:R: ${$("rr")?.textContent || '1:2'}\nDesk: XAUUSD Signal Desk Pro`;

  if (navigator.clipboard?.writeText) {
    navigator.clipboard.writeText(text);
  }
  showToast("📋 Signal copied!", "success");
});

// Window Resize / Orientation Change for Android Plotly Chart
window.addEventListener("resize", () => {
  if (window.Plotly && state.activeTab === "chart") {
    Plotly.Plots.resize("chart");
  }
});
window.addEventListener("orientationchange", () => {
  setTimeout(() => {
    if (window.Plotly && state.activeTab === "chart") {
      Plotly.Plots.resize("chart");
    }
  }, 100);
});

// ==========================================================================
// MOBILE TOUCH & 2-FINGER PINCH ZOOM GESTURES
// ==========================================================================
function setupChartTouchGestures() {
  const wrapper = document.querySelector(".chart-wrapper");
  if (!wrapper) return;

  let initialDistance = 0;
  let initialRange = null;
  let lastTapTime = 0;

  wrapper.addEventListener("touchstart", (e) => {
    if (e.touches.length === 2) {
      e.preventDefault();
      const t1 = e.touches[0];
      const t2 = e.touches[1];
      initialDistance = Math.hypot(t1.clientX - t2.clientX, t1.clientY - t2.clientY);
      const gd = document.getElementById("chart");
      if (gd && gd.layout && gd.layout.xaxis && gd.layout.xaxis.range) {
        initialRange = [...gd.layout.xaxis.range];
      }
    } else if (e.touches.length === 1) {
      // Double tap reset detection (< 300ms)
      const now = Date.now();
      if (now - lastTapTime < 300) {
        e.preventDefault();
        Plotly.relayout("chart", {
          "xaxis.autorange": true,
          "yaxis.autorange": true
        });
        showToast("Chart View Reset");
      }
      lastTapTime = now;
    }
  }, { passive: false });

  wrapper.addEventListener("touchmove", (e) => {
    if (e.touches.length === 2 && initialDistance > 0 && initialRange) {
      e.preventDefault();
      const t1 = e.touches[0];
      const t2 = e.touches[1];
      const currentDistance = Math.hypot(t1.clientX - t2.clientX, t1.clientY - t2.clientY);
      if (currentDistance > 10) {
        const scale = initialDistance / currentDistance;
        const minDate = new Date(initialRange[0]).getTime();
        const maxDate = new Date(initialRange[1]).getTime();
        if (!isNaN(minDate) && !isNaN(maxDate)) {
          const span = maxDate - minDate;
          const mid = (minDate + maxDate) / 2;
          const newSpan = Math.max(span * scale, 60000 * 5); // Minimum 5 min span
          const newMin = new Date(mid - newSpan / 2).toISOString();
          const newMax = new Date(mid + newSpan / 2).toISOString();

          Plotly.relayout("chart", {
            "xaxis.range": [newMin, newMax]
          });
        }
      }
    }
  }, { passive: false });

  wrapper.addEventListener("touchend", (e) => {
    if (e.touches.length < 2) {
      initialDistance = 0;
      initialRange = null;
    }
  });

  // Floating touch zoom buttons
  $("chartZoomIn")?.addEventListener("click", (e) => {
    e.stopPropagation();
    const gd = document.getElementById("chart");
    if (!gd || !gd.layout || !gd.layout.xaxis || !gd.layout.xaxis.range) return;
    const minD = new Date(gd.layout.xaxis.range[0]).getTime();
    const maxD = new Date(gd.layout.xaxis.range[1]).getTime();
    if (isNaN(minD) || isNaN(maxD)) return;
    const mid = (minD + maxD) / 2;
    const span = Math.max((maxD - minD) * 0.7, 60000 * 5);
    Plotly.relayout("chart", {
      "xaxis.range": [new Date(mid - span / 2).toISOString(), new Date(mid + span / 2).toISOString()]
    });
  });

  $("chartZoomOut")?.addEventListener("click", (e) => {
    e.stopPropagation();
    const gd = document.getElementById("chart");
    if (!gd || !gd.layout || !gd.layout.xaxis || !gd.layout.xaxis.range) return;
    const minD = new Date(gd.layout.xaxis.range[0]).getTime();
    const maxD = new Date(gd.layout.xaxis.range[1]).getTime();
    if (isNaN(minD) || isNaN(maxD)) return;
    const mid = (minD + maxD) / 2;
    const span = (maxD - minD) * 1.4;
    Plotly.relayout("chart", {
      "xaxis.range": [new Date(mid - span / 2).toISOString(), new Date(mid + span / 2).toISOString()]
    });
  });

  $("chartZoomReset")?.addEventListener("click", (e) => {
    e.stopPropagation();
    Plotly.relayout("chart", {
      "xaxis.autorange": true,
      "yaxis.autorange": true
    });
    showToast("Chart View Reset");
  });
}

// Initialize Theme, Touch Gestures & Start Polling Loop
applyTheme(state.theme);
setupChartTouchGestures();
poll();
setInterval(poll, 1500);
