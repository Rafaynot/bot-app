"""
Risk management: entry, ATR stops, multi-TP, R:R, and lot sizing.
"""

from __future__ import annotations

from dataclasses import dataclass

from config import CONFIG, RiskConfig
from utils import Direction, clamp, round_lot, safe_div


@dataclass
class RiskPlan:
    direction: Direction
    entry: float
    stop_loss: float
    take_profit_1: float
    take_profit_2: float
    take_profit_3: float
    risk_reward: float
    lot_size: float
    atr_stop: float
    risk_amount: float
    risk_percent: float
    valid: bool
    message: str = ""


def calculate_lot_size(
    balance: float,
    risk_percent: float,
    entry: float,
    stop: float,
    contract_size: float = 100.0,
) -> float:
    """
    Lot size so that loss at SL ≈ risk_percent of balance.
    For XAUUSD: PnL ≈ lot * contract_size * price_move.
    """
    risk_amount = balance * (risk_percent / 100.0)
    stop_distance = abs(entry - stop)
    if stop_distance <= 0 or contract_size <= 0:
        return 0.0
    lots = risk_amount / (stop_distance * contract_size)
    return round_lot(clamp(lots, 0.01, 50.0), 0.01)


def build_risk_plan(
    direction: Direction,
    entry: float,
    atr: float,
    balance: float | None = None,
    sl_override: float | None = None,
    cfg: RiskConfig | None = None,
) -> RiskPlan:
    """
    Construct SL / TP ladder from ATR with minimum R:R enforcement.
    """
    cfg = cfg or CONFIG.risk
    balance = balance if balance is not None else cfg.account_balance
    atr_stop = atr * cfg.atr_sl_multiplier

    if direction == Direction.BUY:
        stop = sl_override if sl_override is not None else entry - atr_stop
        risk = entry - stop
        tp1 = entry + risk * cfg.tp1_rr
        tp2 = entry + risk * cfg.tp2_rr
        tp3 = entry + risk * cfg.tp3_rr
    elif direction == Direction.SELL:
        stop = sl_override if sl_override is not None else entry + atr_stop
        risk = stop - entry
        tp1 = entry - risk * cfg.tp1_rr
        tp2 = entry - risk * cfg.tp2_rr
        tp3 = entry - risk * cfg.tp3_rr
    else:
        return RiskPlan(
            direction=Direction.WAIT,
            entry=entry,
            stop_loss=entry,
            take_profit_1=entry,
            take_profit_2=entry,
            take_profit_3=entry,
            risk_reward=0.0,
            lot_size=0.0,
            atr_stop=atr_stop,
            risk_amount=0.0,
            risk_percent=0.0,
            valid=False,
            message="No trade direction",
        )

    rr = safe_div(abs(tp1 - entry), abs(entry - stop))
    valid = rr >= cfg.min_risk_reward and abs(entry - stop) > 0
    lots = calculate_lot_size(balance, cfg.max_risk_percent, entry, stop, cfg.contract_size)
    risk_amount = balance * (cfg.max_risk_percent / 100.0)

    msg = ""
    if not valid:
        msg = f"R:R {rr:.2f} below minimum {cfg.min_risk_reward:.1f}"

    return RiskPlan(
        direction=direction,
        entry=round(entry, 2),
        stop_loss=round(stop, 2),
        take_profit_1=round(tp1, 2),
        take_profit_2=round(tp2, 2),
        take_profit_3=round(tp3, 2),
        risk_reward=round(rr, 2),
        lot_size=lots,
        atr_stop=round(atr_stop, 2),
        risk_amount=round(risk_amount, 2),
        risk_percent=cfg.max_risk_percent,
        valid=valid,
        message=msg,
    )
