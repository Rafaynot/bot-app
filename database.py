"""
SQLite persistence for trade signals + learning outcomes.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from config import DB_PATH
from signals import TradeSignal
from utils import get_logger, serialize_reasons, utc_now

logger = get_logger()


@dataclass
class SignalRow:
    id: int
    date: str
    time: str
    price: float
    direction: str
    confidence: float
    reason: str
    result: str
    mode: str = ""


@dataclass
class PendingSignal:
    id: int
    direction: str
    entry: float
    sl: float
    tp1: float
    features: dict[str, bool]
    mode: str
    created_at: str


@dataclass
class ModePerformance:
    mode: str
    wins: int
    losses: int
    pending: int
    expired: int
    total_resolved: int

    @property
    def win_rate(self) -> float:
        if self.total_resolved <= 0:
            return 0.0
        return 100.0 * self.wins / self.total_resolved


class SignalDatabase:
    """Store and query generated signals."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or DB_PATH
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS signals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL,
                    time TEXT NOT NULL,
                    price REAL NOT NULL,
                    direction TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    reason TEXT NOT NULL,
                    result TEXT DEFAULT 'PENDING',
                    entry REAL,
                    sl REAL,
                    tp1 REAL,
                    tp2 REAL,
                    tp3 REAL,
                    risk_reward REAL,
                    created_at TEXT NOT NULL,
                    mode TEXT,
                    features_json TEXT
                )
                """
            )
            cols = {r[1] for r in conn.execute("PRAGMA table_info(signals)").fetchall()}
            if "mode" not in cols:
                conn.execute("ALTER TABLE signals ADD COLUMN mode TEXT")
            if "features_json" not in cols:
                conn.execute("ALTER TABLE signals ADD COLUMN features_json TEXT")

    def save_signal(self, signal: TradeSignal, result: str = "PENDING") -> int:
        ts = signal.timestamp or utc_now()
        date_s = ts.strftime("%Y-%m-%d")
        time_s = ts.strftime("%H:%M:%S")
        reason = serialize_reasons(signal.reasons)
        risk = signal.risk
        mode = signal.mode or ""
        feat_json = json.dumps(getattr(signal, "features", {}) or {})
        with self._conn() as conn:
            cur = conn.execute(
                """
                INSERT INTO signals (
                    date, time, price, direction, confidence, reason, result,
                    entry, sl, tp1, tp2, tp3, risk_reward, created_at, mode, features_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    date_s,
                    time_s,
                    signal.price,
                    signal.direction.value,
                    signal.confidence,
                    reason,
                    result,
                    risk.entry if risk else None,
                    risk.stop_loss if risk else None,
                    risk.take_profit_1 if risk else None,
                    risk.take_profit_2 if risk else None,
                    risk.take_profit_3 if risk else None,
                    risk.risk_reward if risk else None,
                    utc_now().isoformat(),
                    mode,
                    feat_json,
                ),
            )
            row_id = int(cur.lastrowid)
        logger.info(
            "Saved signal #%s [%s] %s @ %.2f (%.0f%%)",
            row_id,
            mode or "-",
            signal.direction.value,
            signal.price,
            signal.confidence,
        )
        return row_id

    def update_result(self, signal_id: int, result: str) -> None:
        with self._conn() as conn:
            conn.execute("UPDATE signals SET result = ? WHERE id = ?", (result, signal_id))

    def pending_for_learning(self, limit: int = 100) -> list[PendingSignal]:
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT id, direction, entry, sl, tp1, features_json, mode, created_at
                FROM signals
                WHERE result = 'PENDING'
                  AND entry IS NOT NULL AND sl IS NOT NULL AND tp1 IS NOT NULL
                ORDER BY id ASC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        out: list[PendingSignal] = []
        for r in rows:
            try:
                feats = json.loads(r["features_json"] or "{}")
            except Exception:  # noqa: BLE001
                feats = {}
            out.append(
                PendingSignal(
                    id=int(r["id"]),
                    direction=str(r["direction"]),
                    entry=float(r["entry"]),
                    sl=float(r["sl"]),
                    tp1=float(r["tp1"]),
                    features={str(k): bool(v) for k, v in feats.items()},
                    mode=str(r["mode"] or "swing"),
                    created_at=str(r["created_at"] or ""),
                )
            )
        return out

    def performance_by_mode(self) -> list[ModePerformance]:
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT
                    COALESCE(NULLIF(mode, ''), 'unknown') AS mode,
                    SUM(CASE WHEN result = 'WIN' THEN 1 ELSE 0 END) AS wins,
                    SUM(CASE WHEN result = 'LOSS' THEN 1 ELSE 0 END) AS losses,
                    SUM(CASE WHEN result = 'PENDING' THEN 1 ELSE 0 END) AS pending,
                    SUM(CASE WHEN result = 'EXPIRED' THEN 1 ELSE 0 END) AS expired
                FROM signals
                GROUP BY COALESCE(NULLIF(mode, ''), 'unknown')
                """
            ).fetchall()
        out: list[ModePerformance] = []
        for r in rows:
            wins = int(r["wins"] or 0)
            losses = int(r["losses"] or 0)
            out.append(
                ModePerformance(
                    mode=str(r["mode"]),
                    wins=wins,
                    losses=losses,
                    pending=int(r["pending"] or 0),
                    expired=int(r["expired"] or 0),
                    total_resolved=wins + losses,
                )
            )
        return out

    def clear_all(self) -> int:
        """Delete all stored signals. Returns rows removed."""
        with self._conn() as conn:
            cur = conn.execute("SELECT COUNT(*) AS n FROM signals")
            n = int(cur.fetchone()["n"])
            conn.execute("DELETE FROM signals")
            try:
                conn.execute("DELETE FROM sqlite_sequence WHERE name='signals'")
            except Exception:  # noqa: BLE001
                pass
        logger.info("Cleared %s signals from database", n)
        return n

    def recent(self, limit: int = 50) -> list[SignalRow]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT id, date, time, price, direction, confidence, reason, result, mode "
                "FROM signals ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            SignalRow(
                id=r["id"],
                date=r["date"],
                time=r["time"],
                price=r["price"],
                direction=r["direction"],
                confidence=r["confidence"],
                reason=r["reason"],
                result=r["result"],
                mode=str(r["mode"] or ""),
            )
            for r in rows
        ]


def resolve_pending_outcomes(
    db: SignalDatabase,
    price: float,
    learner: Any,
    max_age_hours: float = 48.0,
) -> list[tuple[int, str]]:
    """Mark PENDING signals WIN/LOSS/EXPIRED from live price; feed learner."""
    resolved: list[tuple[int, str]] = []
    now = utc_now()
    for row in db.pending_for_learning():
        try:
            created = datetime.fromisoformat(row.created_at)
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            age_h = (now - created).total_seconds() / 3600.0
            if age_h > max_age_hours:
                db.update_result(row.id, "EXPIRED")
                resolved.append((row.id, "EXPIRED"))
                continue
        except Exception:  # noqa: BLE001
            pass

        outcome: str | None = None
        if row.direction == "BUY":
            if price <= row.sl:
                outcome = "LOSS"
            elif price >= row.tp1:
                outcome = "WIN"
        elif row.direction == "SELL":
            if price >= row.sl:
                outcome = "LOSS"
            elif price <= row.tp1:
                outcome = "WIN"

        if outcome is None:
            continue
        db.update_result(row.id, outcome)
        if row.features:
            learner.learn_from_outcome(row.features, outcome, mode=row.mode)
        resolved.append((row.id, outcome))
        logger.info("Resolved signal #%s [%s] -> %s @ %.2f", row.id, row.mode, outcome, price)
    return resolved
