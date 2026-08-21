# XAUUSD Technical Analysis Signal Desk

Professional **analysis-only** Python application for real-time XAUUSD (Gold) technical analysis.
It generates **BUY / SELL / WAIT** signals with explanations — it does **not** place trades.

## Features

- **Data**: MetaTrader 5 (preferred), Binance (crypto testing), Demo synthetic feed
- **Top-down**: MN1 → W1 → D1 → H4 → H1 → M30 → M15 → M5 → M1
- **Market structure**: HH/HL/LH/LL, BOS, CHOCH, MSS, Trend/Range/Consolidation/Expansion/Compression
- **SMC**: Order Blocks, Breakers, Mitigation, FVG / Inverse FVG, Liquidity sweeps, Equal H/L, Premium/Discount
- **ICT**: Judas Swing, Po3/AMD, London & NY Kill Zones, Asian range, ORB, SMT, OTE
- **Price action**: Pin Bar, Engulfing, Doji, Inside/Outside, Stars, Hammer, Shooting Star, Tweezers
- **Indicators** (confirmation only): EMA 20/50/100/200, RSI, MACD, ATR, ADX, VWAP, Bollinger, Stoch RSI, OBV, SuperTrend
- **Risk**: Entry, ATR SL, TP1–TP3, R:R, 1% lot sizing
- **News filter**: Forex Factory calendar (blocks FOMC / CPI / NFP / high-impact USD)
- **Dashboard**: PySide6 GUI + Plotly chart, 1s async refresh
- **Alerts**: Desktop notification, sound, optional Telegram
- **Logging**: SQLite signal history

Signals only fire when **confidence ≥ 85%**.

## Requirements

- Python 3.11+ (3.13 recommended)
- MetaTrader 5 terminal installed (for live XAUUSD)
- Windows recommended for MT5 + desktop alerts

## Install

```bash
cd XAUUSD_Analyzer
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Optional (live Plotly inside the GUI):

```bash
pip install PySide6-WebEngine
```

## Run

```bash
# Prefer MT5; auto-falls back to demo if MT5 is unavailable
python main.py

# Explicit demo mode (no broker needed)
python main.py --source demo

# Live MT5
python main.py --source mt5 --mt5-login 123456 --mt5-password SECRET --mt5-server YourBroker-Demo

# Binance crypto testing
python main.py --source binance --symbol BTCUSDT

# Headless one-shot (CLI)
python main.py --source demo --headless

# Telegram alerts
python main.py --source demo --telegram-token BOT_TOKEN --telegram-chat CHAT_ID --balance 10000
```

## Project layout

| Module | Role |
|--------|------|
| `main.py` | Entry point / CLI |
| `config.py` | All tunables |
| `data.py` | MT5 / Binance / Demo + news calendar |
| `indicators.py` | Technical indicators + Fibonacci / OTE |
| `smc.py` | Smart Money Concepts |
| `ict.py` | ICT sessions & concepts |
| `analysis.py` | Price action, S/R, top-down orchestration |
| `risk.py` | Stops, targets, lot size |
| `signals.py` | Confluence scoring engine |
| `dashboard.py` | PySide6 UI + Plotly |
| `alerts.py` | Desktop / sound / Telegram |
| `database.py` | SQLite signal log |
| `utils.py` | Logging & helpers |

## Signal rules (summary)

**BUY** needs confluence of: HTF/EMA trend (price above EMA200), bullish structure, liquidity sweep, order block, FVG, bullish candle, RSI, MACD, volume, and R:R ≥ 1:2.

**SELL** is the mirror image (price below EMA200 unless reversal CHOCH is confirmed).

## Disclaimer

This software is for educational and analytical purposes only. It does not execute trades and does not constitute financial advice. Trading precious metals involves substantial risk of loss.
"# BOTPYTHON" 
