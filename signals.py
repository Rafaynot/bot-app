"""
Signal engine — confluence scoring for BUY / SELL / WAIT.

Swing: full SMC/ICT checklist (classic desk).
Scalp: lighter LTF checklist + kill-zone + spread + optional M1 confirm.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from analysis import CandlePattern, TopDownAnalysis
from config import CONFIG, TradingMode
from data import NewsCalendar
from learning import LEARNER
from risk import RiskPlan, build_risk_plan
from smc import nearest_fvg, nearest_unmitigated_ob, price_in_zone
from utils import Direction, TrendBias, clamp, utc_now


@dataclass
class TradeSignal:
    direction: Direction
    confidence: float
    reasons: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    risk: RiskPlan | None = None
    price: float = 0.0
    trend: str = ""
    structure: str = ""
    session: str = ""
    news_status: str = ""
    atr: float = 0.0
    spread: float = 0.0
    timestamp: datetime = field(default_factory=utc_now)
    timeframe: str = ""
    mode: str = ""
    features: dict[str, bool] = field(default_factory=dict)
    learning_note: str = ""

    @property
    def is_actionable(self) -> bool:
        thr = LEARNER.adaptive_threshold(
            self.mode or CONFIG.trading_mode.value,
            CONFIG.signal.min_confidence,
        )
        return (
            self.direction in {Direction.BUY, Direction.SELL}
            and self.confidence >= thr
            and self.risk is not None
            and self.risk.valid
        )

    def summary_lines(self) -> list[str]:
        mode = self.mode or CONFIG.trading_mode.value
        thr = LEARNER.adaptive_threshold(mode, CONFIG.signal.min_confidence)
        lines = [
            f"{self.direction.value}  [{mode.upper()}]",
            f"Confidence: {self.confidence:.0f}% (need ≥{thr:.0f}%)",
            f"Entry TF: {self.timeframe or CONFIG.entry_timeframe.value}",
            "",
            "Reasons:",
        ]
        for r in self.reasons:
            lines.append(f"[OK] {r}")
        if self.failed:
            lines.append("")
            lines.append("Missing:")
            for f in self.failed:
                lines.append(f"[--] {f}")
        if self.learning_note:
            lines.extend(["", self.learning_note])
        return lines


class SignalEngine:
    """Mode-aware confluence signal generator (analysis only)."""

    def __init__(self, news: NewsCalendar | None = None) -> None:
        self.news = news or NewsCalendar()
        self.learner = LEARNER
        self._last_signal_key: str | None = None

    def _mode(self) -> TradingMode:
        return CONFIG.trading_mode

    def _p(self, feature: str, base: float) -> float:
        return self.learner.pts(feature, base, self._mode().value)

    def _thr(self) -> float:
        return self.learner.adaptive_threshold(
            self._mode().value, CONFIG.signal.min_confidence
        )

    def _base_meta(
        self,
        analysis: TopDownAnalysis,
        tf_data,
        atr: float,
        session_name: str,
        structure_desc: str,
        news_reason: str,
        confidence: float = 0.0,
        reasons: list[str] | None = None,
        failed: list[str] | None = None,
        direction: Direction = Direction.WAIT,
        risk: RiskPlan | None = None,
        features: dict[str, bool] | None = None,
    ) -> TradeSignal:
        return TradeSignal(
            direction=direction,
            confidence=confidence,
            reasons=reasons or [],
            failed=failed or [],
            risk=risk,
            price=analysis.price,
            trend=tf_data.ema_bias if tf_data else "",
            structure=structure_desc,
            session=session_name,
            news_status=news_reason,
            atr=atr,
            spread=analysis.spread,
            timeframe=CONFIG.entry_timeframe.value,
            mode=CONFIG.trading_mode.value,
            features=features or {},
            learning_note=self.learner.status_line(CONFIG.trading_mode.value),
        )

    def generate(self, analysis: TopDownAnalysis) -> TradeSignal:
        entry_tf = CONFIG.entry_timeframe
        tf_data = analysis.frames.get(entry_tf) or next(iter(analysis.frames.values()), None)
        if tf_data is None:
            return TradeSignal(
                direction=Direction.WAIT,
                confidence=0,
                failed=["Insufficient market data"],
                price=analysis.price,
                news_status="N/A",
                mode=CONFIG.trading_mode.value,
            )

        ind = tf_data.indicators
        smc = tf_data.smc
        ict = tf_data.ict
        price = analysis.price
        atr = float(ind.atr.iloc[-1])
        rsi = float(ind.rsi.iloc[-1])
        macd_hist = float(ind.macd_hist.iloc[-1])
        macd_hist_prev = float(ind.macd_hist.iloc[-2]) if len(ind.macd_hist) > 1 else 0.0
        obv_rising = float(ind.obv.iloc[-1]) > float(ind.obv.iloc[-5]) if len(ind.obv) > 5 else False
        obv_falling = float(ind.obv.iloc[-1]) < float(ind.obv.iloc[-5]) if len(ind.obv) > 5 else False

        blocked, news_reason = self.news.is_news_blocked()
        session_name = ict.session.name.value if ict else "Unknown"
        structure_desc = smc.regime.value
        if smc.structure_events:
            structure_desc = smc.structure_events[-1].description

        # Scalp spread gate (before scoring waste)
        if self._mode() == TradingMode.SCALP:
            atr_stop = atr * CONFIG.risk.atr_sl_multiplier
            max_spread = atr_stop * CONFIG.signal.scalp_max_spread_atr_frac
            if atr_stop > 0 and analysis.spread > max_spread:
                return self._base_meta(
                    analysis,
                    tf_data,
                    atr,
                    session_name,
                    structure_desc,
                    news_reason,
                    confidence=max(0.0, 100.0 * (1.0 - analysis.spread / max(atr_stop, 1e-9))),
                    reasons=[f"Spread {analysis.spread:.2f} vs max {max_spread:.2f}"],
                    failed=["Spread too wide for scalp"],
                )

        if self._mode() == TradingMode.SCALP:
            bull_score, bull_reasons, bull_fail, bull_feat = self._score_buy_scalp(
                analysis, tf_data, price, rsi, macd_hist, macd_hist_prev, obv_rising, blocked
            )
            bear_score, bear_reasons, bear_fail, bear_feat = self._score_sell_scalp(
                analysis, tf_data, price, rsi, macd_hist, macd_hist_prev, obv_falling, blocked
            )
        else:
            bull_score, bull_reasons, bull_fail, bull_feat = self._score_buy(
                analysis, tf_data, price, rsi, macd_hist, macd_hist_prev, obv_rising, blocked
            )
            bear_score, bear_reasons, bear_fail, bear_feat = self._score_sell(
                analysis, tf_data, price, rsi, macd_hist, macd_hist_prev, obv_falling, blocked
            )

        thr = self._thr()

        if blocked:
            return self._base_meta(
                analysis,
                tf_data,
                atr,
                session_name,
                structure_desc,
                news_reason,
                confidence=max(bull_score, bear_score),
                reasons=[news_reason],
                failed=["News filter active — no trade"],
            )

        # Clear scalp kill-zone wait messaging
        prefer_bull = bull_score >= bear_score
        top_fail = bull_fail if prefer_bull else bear_fail
        if (
            self._mode() == TradingMode.SCALP
            and CONFIG.signal.scalp_require_killzone
            and any("Kill Zone" in f for f in top_fail)
            and max(bull_score, bear_score) < thr
        ):
            return self._base_meta(
                analysis,
                tf_data,
                atr,
                session_name,
                structure_desc,
                news_reason,
                confidence=max(bull_score, bear_score),
                reasons=["WAITING: Kill Zone (London/NY) — scalp pauses outside session"],
                failed=top_fail,
                features=bull_feat if prefer_bull else bear_feat,
            )

        if bull_score >= bear_score and bull_score >= thr:
            direction = Direction.BUY
            confidence = bull_score
            reasons, failed, features = bull_reasons, bull_fail, bull_feat
        elif bear_score > bull_score and bear_score >= thr:
            direction = Direction.SELL
            confidence = bear_score
            reasons, failed, features = bear_reasons, bear_fail, bear_feat
        else:
            return self._base_meta(
                analysis,
                tf_data,
                atr,
                session_name,
                structure_desc,
                news_reason,
                confidence=max(bull_score, bear_score),
                reasons=["NO TRADE", "Wait for better confirmation."],
                failed=bull_fail if bull_score >= bear_score else bear_fail,
                features=bull_feat if bull_score >= bear_score else bear_feat,
            )

        # Optional M1 confirmation for scalp (entry is M5)
        if (
            self._mode() == TradingMode.SCALP
            and CONFIG.signal.scalp_require_m1_confirm
            and CONFIG.confirm_timeframe is not None
        ):
            ok, note = self._m1_confirms(analysis, direction)
            if ok:
                reasons.append(note)
                features["M1_Confirm"] = True
            else:
                features["M1_Confirm"] = False
                return self._base_meta(
                    analysis,
                    tf_data,
                    atr,
                    session_name,
                    structure_desc,
                    news_reason,
                    confidence=confidence * 0.85,
                    reasons=reasons,
                    failed=failed + [note],
                    features=features,
                )

        sl_override = None
        ob = nearest_unmitigated_ob(smc, bullish=(direction == Direction.BUY), price=price)
        if ob:
            sl_override = ob.bottom - atr * 0.2 if direction == Direction.BUY else ob.top + atr * 0.2

        risk = build_risk_plan(direction, price, atr, sl_override=sl_override)
        if not risk.valid:
            return self._base_meta(
                analysis,
                tf_data,
                atr,
                session_name,
                structure_desc,
                news_reason,
                confidence=confidence,
                reasons=reasons,
                failed=failed + [risk.message or "Invalid risk plan"],
                features=features,
            )

        reasons = [
            f"Risk Reward 1:{risk.risk_reward:.1f}" if "Risk Reward" in r else r
            for r in reasons
        ]
        if not any("Risk Reward 1:" in r for r in reasons):
            reasons.append(f"Risk Reward 1:{risk.risk_reward:.1f}")
        features["Risk_Reward"] = True

        return self._base_meta(
            analysis,
            tf_data,
            atr,
            session_name,
            structure_desc,
            news_reason,
            confidence=round(confidence, 1),
            reasons=reasons,
            failed=failed,
            direction=direction,
            risk=risk,
            features=features,
        )

    def _m1_confirms(self, analysis: TopDownAnalysis, direction: Direction) -> tuple[bool, str]:
        ctf = CONFIG.confirm_timeframe
        frame = analysis.frames.get(ctf) if ctf else None
        if frame is None:
            return False, f"{ctf.value if ctf else 'M1'} confirm missing"
        # Prefer last candle direction from patterns / SuperTrend
        st = float(frame.indicators.supertrend_dir.iloc[-1])
        if direction == Direction.BUY:
            if st > 0 or frame.trend == TrendBias.BULLISH:
                return True, "M1 confirm bullish"
            # Soft: last pattern bullish
            if any(p.bullish for p in frame.patterns[-3:]):
                return True, "M1 bullish candle confirm"
            return False, "M1 not confirming BUY"
        if st < 0 or frame.trend == TrendBias.BEARISH:
            return True, "M1 confirm bearish"
        if any((not p.bullish) for p in frame.patterns[-3:]):
            return True, "M1 bearish candle confirm"
        return False, "M1 not confirming SELL"

    def _in_kill_zone(self, ict) -> bool:
        return bool(ict and (ict.session.in_london_kz or ict.session.in_ny_kz))

    # ------------------------------------------------------------------ SCALP
    def _score_buy_scalp(
        self,
        analysis: TopDownAnalysis,
        tf_data,
        price: float,
        rsi: float,
        macd_hist: float,
        macd_hist_prev: float,
        vol_ok: bool,
        news_blocked: bool,
    ) -> tuple[float, list[str], list[str], dict[str, bool]]:
        """Lighter checklist: bias + structure + momentum + kill zone."""
        reasons: list[str] = []
        failed: list[str] = []
        features: dict[str, bool] = {}
        score = 0.0
        smc = tf_data.smc
        ict = tf_data.ict
        ind = tf_data.indicators
        cfg = CONFIG.signal

        kz = self._in_kill_zone(ict)
        features["Kill_Zone"] = kz
        if cfg.scalp_require_killzone and not kz:
            failed.append("Kill Zone required (London/NY)")
            if news_blocked:
                return 0.0, reasons, failed, features
        elif kz:
            score += self._p("Kill_Zone", 18)
            reasons.append("Kill Zone Session")

        above_ema = price > float(ind.ema50.iloc[-1])
        bias_ok = analysis.aligned_bullish or (
            analysis.higher_tf_bias == TrendBias.BULLISH and above_ema
        )
        features["Bias"] = bool(bias_ok)
        if bias_ok:
            score += self._p("Bias", 20)
            reasons.append("HTF/M5 bullish bias")
        else:
            failed.append("Bullish bias alignment")

        struct_ok = smc.trend == TrendBias.BULLISH or smc.last_bos_bullish is True
        features["Market_Structure"] = bool(struct_ok)
        if struct_ok:
            score += self._p("Market_Structure", 16)
            reasons.append("Bullish structure / BOS")
        else:
            failed.append("Bullish structure")

        sweep_ok = bool(smc.liquidity_sweep_bullish or (ict and ict.judas_swing_bullish))
        features["Liquidity_Sweep"] = sweep_ok
        if sweep_ok:
            score += self._p("Liquidity_Sweep", 14)
            reasons.append("Liquidity / Judas sweep")
        else:
            failed.append("Liquidity sweep")

        bullish_patterns = {
            CandlePattern.ENGULFING,
            CandlePattern.PIN_BAR,
            CandlePattern.HAMMER,
            CandlePattern.MORNING_STAR,
            CandlePattern.TWEEZER_BOTTOM,
        }
        pat_ok = any(p.bullish and p.pattern in bullish_patterns for p in tf_data.patterns[-5:])
        features["Candle"] = bool(pat_ok)
        if pat_ok:
            score += self._p("Candle", 12)
            reasons.append("Bullish candle")
        else:
            failed.append("Bullish candle")

        rsi_ok = rsi <= cfg.rsi_oversold or (rsi < 55 and rsi > float(ind.rsi.iloc[-3]))
        features["RSI"] = bool(rsi_ok)
        if rsi_ok:
            score += self._p("RSI", 10)
            reasons.append("RSI confirmation")
        else:
            failed.append("RSI confirmation")

        macd_ok = macd_hist > 0 or macd_hist > macd_hist_prev
        features["MACD"] = macd_ok
        if macd_ok:
            score += self._p("MACD", 6)
            reasons.append("MACD turning up")
        features["Volume"] = bool(vol_ok)
        if vol_ok:
            score += self._p("Volume", 4)
            reasons.append("Volume up")
        fvg = nearest_fvg(smc, True, price)
        features["FVG"] = fvg is not None
        if fvg is not None:
            score += self._p("FVG", 4)
            reasons.append("Nearby bullish FVG")
        st = float(ind.supertrend_dir.iloc[-1]) > 0
        features["SuperTrend"] = st
        if st:
            score += self._p("SuperTrend", 3)
            reasons.append("SuperTrend bullish")

        score += self._p("Risk_Reward", 5)
        features["Risk_Reward"] = True
        reasons.append("Risk Reward ≥ 1:1.2 (pending plan)")

        if cfg.scalp_require_killzone and not kz:
            score *= 0.35
        if news_blocked:
            score = 0
        return clamp(score, 0, 100), reasons, failed, features

    def _score_sell_scalp(
        self,
        analysis: TopDownAnalysis,
        tf_data,
        price: float,
        rsi: float,
        macd_hist: float,
        macd_hist_prev: float,
        vol_ok: bool,
        news_blocked: bool,
    ) -> tuple[float, list[str], list[str], dict[str, bool]]:
        reasons: list[str] = []
        failed: list[str] = []
        features: dict[str, bool] = {}
        score = 0.0
        smc = tf_data.smc
        ict = tf_data.ict
        ind = tf_data.indicators
        cfg = CONFIG.signal

        kz = self._in_kill_zone(ict)
        features["Kill_Zone"] = kz
        if cfg.scalp_require_killzone and not kz:
            failed.append("Kill Zone required (London/NY)")
        elif kz:
            score += self._p("Kill_Zone", 18)
            reasons.append("Kill Zone Session")

        below_ema = price < float(ind.ema50.iloc[-1])
        bias_ok = analysis.aligned_bearish or (
            analysis.higher_tf_bias == TrendBias.BEARISH and below_ema
        )
        features["Bias"] = bool(bias_ok)
        if bias_ok:
            score += self._p("Bias", 20)
            reasons.append("HTF/M5 bearish bias")
        else:
            failed.append("Bearish bias alignment")

        struct_ok = smc.trend == TrendBias.BEARISH or smc.last_bos_bullish is False
        features["Market_Structure"] = bool(struct_ok)
        if struct_ok:
            score += self._p("Market_Structure", 16)
            reasons.append("Bearish structure / BOS")
        else:
            failed.append("Bearish structure")

        sweep_ok = bool(smc.liquidity_sweep_bearish or (ict and ict.judas_swing_bearish))
        features["Liquidity_Sweep"] = sweep_ok
        if sweep_ok:
            score += self._p("Liquidity_Sweep", 14)
            reasons.append("Liquidity / Judas sweep")
        else:
            failed.append("Liquidity sweep")

        bearish_patterns = {
            CandlePattern.ENGULFING,
            CandlePattern.PIN_BAR,
            CandlePattern.SHOOTING_STAR,
            CandlePattern.EVENING_STAR,
            CandlePattern.TWEEZER_TOP,
        }
        pat_ok = any((not p.bullish) and p.pattern in bearish_patterns for p in tf_data.patterns[-5:])
        features["Candle"] = bool(pat_ok)
        if pat_ok:
            score += self._p("Candle", 12)
            reasons.append("Bearish candle")
        else:
            failed.append("Bearish candle")

        rsi_ok = rsi >= cfg.rsi_overbought or (rsi > 45 and rsi < float(ind.rsi.iloc[-3]))
        features["RSI"] = bool(rsi_ok)
        if rsi_ok:
            score += self._p("RSI", 10)
            reasons.append("RSI confirmation")
        else:
            failed.append("RSI confirmation")

        macd_ok = macd_hist < 0 or macd_hist < macd_hist_prev
        features["MACD"] = macd_ok
        if macd_ok:
            score += self._p("MACD", 6)
            reasons.append("MACD turning down")
        features["Volume"] = bool(vol_ok)
        if vol_ok:
            score += self._p("Volume", 4)
            reasons.append("Volume up")
        fvg = nearest_fvg(smc, False, price)
        features["FVG"] = fvg is not None
        if fvg is not None:
            score += self._p("FVG", 4)
            reasons.append("Nearby bearish FVG")
        st = float(ind.supertrend_dir.iloc[-1]) < 0
        features["SuperTrend"] = st
        if st:
            score += self._p("SuperTrend", 3)
            reasons.append("SuperTrend bearish")

        score += self._p("Risk_Reward", 5)
        features["Risk_Reward"] = True
        reasons.append("Risk Reward ≥ 1:1.2 (pending plan)")

        if cfg.scalp_require_killzone and not kz:
            score *= 0.35
        if news_blocked:
            score = 0
        return clamp(score, 0, 100), reasons, failed, features

    # ------------------------------------------------------------------ SWING (full)
    def _score_buy(
        self,
        analysis: TopDownAnalysis,
        tf_data,
        price: float,
        rsi: float,
        macd_hist: float,
        macd_hist_prev: float,
        vol_ok: bool,
        news_blocked: bool,
    ) -> tuple[float, list[str], list[str], dict[str, bool]]:
        reasons: list[str] = []
        failed: list[str] = []
        features: dict[str, bool] = {}
        score = 0.0
        smc = tf_data.smc
        ict = tf_data.ict
        ind = tf_data.indicators
        cfg = CONFIG.signal

        above_200 = price > float(ind.ema200.iloc[-1])
        trend_ok = analysis.aligned_bullish or (
            analysis.higher_tf_bias == TrendBias.BULLISH and above_200
        )
        feat = bool(trend_ok and above_200)
        features["EMA_HTF_Trend"] = feat
        if feat:
            score += self._p("EMA_HTF_Trend", 12)
            reasons.append("EMA Trend (above EMA200)")
        else:
            failed.append("Trend confirmation / above EMA200")

        bos_ok = smc.last_bos_bullish is True or (
            smc.structure_events
            and smc.structure_events[-1].bullish
            and smc.structure_events[-1].event_type.value in {"BOS", "CHOCH", "MSS"}
        )
        struct_ok = smc.trend == TrendBias.BULLISH or bos_ok
        features["Market_Structure"] = bool(struct_ok)
        if struct_ok:
            score += self._p("Market_Structure", 12)
            reasons.append("Bullish BOS / Structure" if bos_ok else "Bullish Market Structure")
        else:
            failed.append("Market Structure confirmation")

        sweep_ok = bool(smc.liquidity_sweep_bullish or (ict and ict.judas_swing_bullish))
        features["Liquidity_Sweep"] = sweep_ok
        if smc.liquidity_sweep_bullish:
            score += self._p("Liquidity_Sweep", 12)
            reasons.append("Liquidity Grab (buy-side sweep)")
        elif ict and ict.judas_swing_bullish:
            score += self._p("Liquidity_Sweep", 12)
            reasons.append("Bullish Judas Swing")
        else:
            failed.append("Liquidity sweep")

        ob = nearest_unmitigated_ob(smc, True, price)
        ob_ok = ob is not None and price_in_zone(price, ob, pad=float(ind.atr.iloc[-1]) * 0.5)
        features["Order_Block"] = bool(ob_ok)
        if ob_ok:
            score += self._p("Order_Block", 12)
            reasons.append("Bullish Order Block")
        else:
            failed.append("Order Block")

        fvg = nearest_fvg(smc, True, price)
        fvg_ok = fvg is not None and fvg.bottom <= price <= fvg.top * 1.002
        if not fvg_ok and fvg is not None:
            fvg_ok = abs((fvg.top + fvg.bottom) / 2 - price) < float(ind.atr.iloc[-1]) * 2
        features["FVG"] = bool(fvg_ok)
        if fvg_ok:
            score += self._p("FVG", 10)
            reasons.append("Bullish FVG")
        else:
            failed.append("Fair Value Gap")

        bullish_patterns = {
            CandlePattern.ENGULFING,
            CandlePattern.PIN_BAR,
            CandlePattern.HAMMER,
            CandlePattern.MORNING_STAR,
            CandlePattern.TWEEZER_BOTTOM,
        }
        pat_ok = any(p.bullish and p.pattern in bullish_patterns for p in tf_data.patterns[-8:])
        features["Candle"] = bool(pat_ok)
        if pat_ok:
            score += self._p("Candle", 8)
            reasons.append("Bullish candle pattern")
        else:
            failed.append("Bullish candle")

        rsi_ok = rsi <= cfg.rsi_oversold or (rsi < 55 and rsi > float(ind.rsi.iloc[-3]))
        features["RSI"] = bool(rsi_ok)
        if rsi_ok:
            score += self._p("RSI", 8)
            reasons.append("RSI Oversold" if rsi <= cfg.rsi_oversold else "RSI Confirmation")
        else:
            failed.append("RSI confirmation")

        macd_ok = macd_hist > 0 or macd_hist > macd_hist_prev
        features["MACD"] = bool(macd_ok)
        if macd_ok:
            score += self._p("MACD", 8)
            reasons.append("MACD Bullish" if macd_hist > 0 else "MACD Turning Up")
        else:
            failed.append("MACD confirmation")

        features["Volume"] = bool(vol_ok)
        if vol_ok:
            score += self._p("Volume", 6)
            reasons.append("Volume Increased")
        else:
            failed.append("Volume confirmation")

        ote = bool(ict and ict.ote_active_bullish)
        features["OTE"] = ote
        if ote:
            score += self._p("OTE", 5)
            reasons.append("OTE Retracement Zone")
        kz = self._in_kill_zone(ict)
        features["Kill_Zone"] = kz
        if kz:
            score += self._p("Kill_Zone", 3)
            reasons.append("Kill Zone Session")
        po3 = bool(ict and "Bullish" in (ict.power_of_three or ""))
        features["Po3"] = po3
        if po3:
            score += self._p("Po3", 3)
            reasons.append("Power of Three Bullish")
        disc = bool(smc.discount and price <= smc.equilibrium)
        features["Discount_Premium"] = disc
        if disc:
            score += self._p("Discount_Premium", 3)
            reasons.append("Discount Zone")
        st = float(ind.supertrend_dir.iloc[-1]) > 0
        features["SuperTrend"] = st
        if st:
            score += self._p("SuperTrend", 2)
            reasons.append("SuperTrend Bullish")

        critical_fail = sum(
            1
            for k in ("EMA_HTF_Trend", "Market_Structure", "Liquidity_Sweep", "Order_Block", "FVG")
            if not features.get(k)
        )
        if critical_fail >= 3:
            score *= 0.5
        if news_blocked:
            score = 0

        score += self._p("Risk_Reward", 6)
        features["Risk_Reward"] = True
        reasons.append("Risk Reward ≥ 1:2 (pending plan)")
        return clamp(score, 0, 100), reasons, failed, features

    def _score_sell(
        self,
        analysis: TopDownAnalysis,
        tf_data,
        price: float,
        rsi: float,
        macd_hist: float,
        macd_hist_prev: float,
        vol_ok: bool,
        news_blocked: bool,
    ) -> tuple[float, list[str], list[str], dict[str, bool]]:
        reasons: list[str] = []
        failed: list[str] = []
        features: dict[str, bool] = {}
        score = 0.0
        smc = tf_data.smc
        ict = tf_data.ict
        ind = tf_data.indicators
        cfg = CONFIG.signal

        below_200 = price < float(ind.ema200.iloc[-1])
        reversal = smc.last_choch_bullish is False
        trend_ok = (analysis.aligned_bearish or analysis.higher_tf_bias == TrendBias.BEARISH) and (
            below_200 or reversal
        )
        features["EMA_HTF_Trend"] = bool(trend_ok)
        if trend_ok:
            score += self._p("EMA_HTF_Trend", 12)
            reasons.append("EMA Trend (below EMA200)" if below_200 else "Reversal Confirmation")
        else:
            failed.append("Trend confirmation / below EMA200")

        bos_ok = smc.last_bos_bullish is False or (
            smc.structure_events and not smc.structure_events[-1].bullish
        )
        struct_ok = smc.trend == TrendBias.BEARISH or bos_ok
        features["Market_Structure"] = bool(struct_ok)
        if struct_ok:
            score += self._p("Market_Structure", 12)
            reasons.append("Bearish BOS / Structure" if bos_ok else "Bearish Market Structure")
        else:
            failed.append("Market Structure confirmation")

        sweep_ok = bool(smc.liquidity_sweep_bearish or (ict and ict.judas_swing_bearish))
        features["Liquidity_Sweep"] = sweep_ok
        if smc.liquidity_sweep_bearish:
            score += self._p("Liquidity_Sweep", 12)
            reasons.append("Liquidity Grab (sell-side sweep)")
        elif ict and ict.judas_swing_bearish:
            score += self._p("Liquidity_Sweep", 12)
            reasons.append("Bearish Judas Swing")
        else:
            failed.append("Liquidity sweep")

        ob = nearest_unmitigated_ob(smc, False, price)
        ob_ok = ob is not None and price_in_zone(price, ob, pad=float(ind.atr.iloc[-1]) * 0.5)
        features["Order_Block"] = bool(ob_ok)
        if ob_ok:
            score += self._p("Order_Block", 12)
            reasons.append("Bearish Order Block")
        else:
            failed.append("Order Block")

        fvg = nearest_fvg(smc, False, price)
        fvg_ok = fvg is not None and abs((fvg.top + fvg.bottom) / 2 - price) < float(ind.atr.iloc[-1]) * 2
        features["FVG"] = bool(fvg_ok)
        if fvg_ok:
            score += self._p("FVG", 10)
            reasons.append("Bearish FVG")
        else:
            failed.append("Fair Value Gap")

        bearish_patterns = {
            CandlePattern.ENGULFING,
            CandlePattern.PIN_BAR,
            CandlePattern.SHOOTING_STAR,
            CandlePattern.EVENING_STAR,
            CandlePattern.TWEEZER_TOP,
        }
        pat_ok = any((not p.bullish) and p.pattern in bearish_patterns for p in tf_data.patterns[-8:])
        features["Candle"] = bool(pat_ok)
        if pat_ok:
            score += self._p("Candle", 8)
            reasons.append("Bearish candle pattern")
        else:
            failed.append("Bearish candle")

        rsi_ok = rsi >= cfg.rsi_overbought or (rsi > 45 and rsi < float(ind.rsi.iloc[-3]))
        features["RSI"] = bool(rsi_ok)
        if rsi_ok:
            score += self._p("RSI", 8)
            reasons.append("RSI Overbought" if rsi >= cfg.rsi_overbought else "RSI Confirmation")
        else:
            failed.append("RSI confirmation")

        macd_ok = macd_hist < 0 or macd_hist < macd_hist_prev
        features["MACD"] = bool(macd_ok)
        if macd_ok:
            score += self._p("MACD", 8)
            reasons.append("MACD Bearish" if macd_hist < 0 else "MACD Turning Down")
        else:
            failed.append("MACD confirmation")

        features["Volume"] = bool(vol_ok)
        if vol_ok:
            score += self._p("Volume", 6)
            reasons.append("Volume Increased")
        else:
            failed.append("Volume confirmation")

        ote = bool(ict and ict.ote_active_bearish)
        features["OTE"] = ote
        if ote:
            score += self._p("OTE", 5)
            reasons.append("OTE Retracement Zone")
        kz = self._in_kill_zone(ict)
        features["Kill_Zone"] = kz
        if kz:
            score += self._p("Kill_Zone", 3)
            reasons.append("Kill Zone Session")
        po3 = bool(ict and "Bearish" in (ict.power_of_three or ""))
        features["Po3"] = po3
        if po3:
            score += self._p("Po3", 3)
            reasons.append("Power of Three Bearish")
        prem = bool(smc.premium and price >= smc.equilibrium)
        features["Discount_Premium"] = prem
        if prem:
            score += self._p("Discount_Premium", 3)
            reasons.append("Premium Zone")
        st = float(ind.supertrend_dir.iloc[-1]) < 0
        features["SuperTrend"] = st
        if st:
            score += self._p("SuperTrend", 2)
            reasons.append("SuperTrend Bearish")

        critical_missing = sum(
            1
            for k in ("EMA_HTF_Trend", "Market_Structure", "Liquidity_Sweep", "Order_Block", "FVG")
            if not features.get(k)
        )
        if critical_missing >= 3:
            score *= 0.5
        if news_blocked:
            score = 0

        score += self._p("Risk_Reward", 6)
        features["Risk_Reward"] = True
        reasons.append("Risk Reward ≥ 1:2 (pending plan)")
        return clamp(score, 0, 100), reasons, failed, features
