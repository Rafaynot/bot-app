"""
Adaptive learning — adjusts factor multipliers from live WIN/LOSS outcomes.

Separate memory per trading mode (swing / scalp). Explainable, not a black box.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from config import DATA_DIR, TradingMode
from utils import get_logger, utc_now

logger = get_logger()

LEARNING_PATH: Path = DATA_DIR / "learned_weights.json"

FEATURES: tuple[str, ...] = (
    "EMA_HTF_Trend",
    "Market_Structure",
    "Liquidity_Sweep",
    "Order_Block",
    "FVG",
    "Candle",
    "RSI",
    "MACD",
    "Volume",
    "Kill_Zone",
    "OTE",
    "Po3",
    "Discount_Premium",
    "SuperTrend",
    "Risk_Reward",
    "M1_Confirm",
    "Bias",
)

WEIGHT_MIN = 0.4
WEIGHT_MAX = 2.0
LEARN_RATE = 0.07


@dataclass
class ModeStats:
    wins: int = 0
    losses: int = 0
    resolved: int = 0
    recent: list[str] = field(default_factory=list)
    mult: dict[str, float] = field(default_factory=dict)

    def ensure(self) -> None:
        for f in FEATURES:
            self.mult.setdefault(f, 1.0)


class MarketLearner:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or LEARNING_PATH
        self.modes: dict[str, ModeStats] = {
            TradingMode.SWING.value: ModeStats(),
            TradingMode.SCALP.value: ModeStats(),
        }
        for m in self.modes.values():
            m.ensure()
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            self._save()
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            for key, blob in (raw.get("modes") or {}).items():
                st = ModeStats(
                    wins=int(blob.get("wins", 0)),
                    losses=int(blob.get("losses", 0)),
                    resolved=int(blob.get("resolved", 0)),
                    recent=list(blob.get("recent", []))[-50:],
                    mult=dict(blob.get("mult", {})),
                )
                st.ensure()
                self.modes[key] = st
            logger.info(
                "Loaded learning swing=%s/%s scalp=%s/%s",
                self.modes["swing"].wins,
                self.modes["swing"].resolved,
                self.modes["scalp"].wins,
                self.modes["scalp"].resolved,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Learning load failed: %s", exc)

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "updated_at": utc_now().isoformat(),
            "modes": {
                k: {
                    "wins": v.wins,
                    "losses": v.losses,
                    "resolved": v.resolved,
                    "recent": v.recent[-50:],
                    "mult": v.mult,
                }
                for k, v in self.modes.items()
            },
        }
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _stats(self, mode: str) -> ModeStats:
        st = self.modes.setdefault(mode, ModeStats())
        st.ensure()
        return st

    def mult(self, feature: str, mode: str | None = None) -> float:
        mode = mode or TradingMode.SWING.value
        st = self._stats(mode)
        m = st.mult.get(feature, 1.0)
        return max(WEIGHT_MIN, min(WEIGHT_MAX, m))

    def pts(self, feature: str, base: float, mode: str | None = None) -> float:
        return base * self.mult(feature, mode)

    def adaptive_threshold(self, mode: str, default: float = 85.0) -> float:
        recent = self._stats(mode).recent[-20:]
        if len(recent) < 5:
            return default
        wr = sum(1 for x in recent if x == "WIN") / len(recent)
        if wr >= 0.6:
            return max(80.0, default - 3.0)
        if wr <= 0.35:
            return min(90.0, default + 4.0)
        return default

    def win_rate(self, mode: str) -> tuple[int, int, float]:
        st = self._stats(mode)
        if st.resolved <= 0:
            return 0, 0, 0.0
        return st.wins, st.resolved, 100.0 * st.wins / st.resolved

    def status_line(self, mode: str | None = None) -> str:
        mode = mode or TradingMode.SWING.value
        w, n, wr = self.win_rate(mode)
        thr = self.adaptive_threshold(mode)
        return f"Learn[{mode}] n={n} WR={wr:.0f}% thr~{thr:.0f}"

    def summary_both(self) -> str:
        parts = []
        for mode in (TradingMode.SWING.value, TradingMode.SCALP.value):
            w, n, wr = self.win_rate(mode)
            parts.append(f"{mode[:2].upper()} {w}/{n} ({wr:.0f}%)")
        return "WR " + " | ".join(parts)

    def reset(self) -> None:
        """Wipe all learned weights and win/loss memory."""
        self.modes = {
            TradingMode.SWING.value: ModeStats(),
            TradingMode.SCALP.value: ModeStats(),
        }
        for m in self.modes.values():
            m.ensure()
        self._save()
        logger.info("Learning stats reset")

    def learn_from_outcome(
        self,
        features: dict[str, bool],
        result: str,
        mode: str,
    ) -> None:
        if result not in {"WIN", "LOSS"}:
            return
        st = self._stats(mode or TradingMode.SWING.value)
        delta = LEARN_RATE if result == "WIN" else -LEARN_RATE
        touched = 0
        for feat, active in features.items():
            if not active or feat not in FEATURES:
                continue
            cur = st.mult.get(feat, 1.0)
            st.mult[feat] = max(WEIGHT_MIN, min(WEIGHT_MAX, cur + delta))
            touched += 1
        st.resolved += 1
        if result == "WIN":
            st.wins += 1
        else:
            st.losses += 1
        st.recent.append(result)
        st.recent = st.recent[-50:]
        self._save()
        logger.info(
            "Learned %s mode=%s features=%s -> %s",
            result,
            mode,
            touched,
            self.status_line(mode),
        )


LEARNER = MarketLearner()
