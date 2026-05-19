"""
Institutional entry timing classifier.

Classifies whether a setup is early, confirmed, late or unavailable without
letting a standalone indicator create a trade signal.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pandas as pd


ENTRY_EARLY = "ENTRY_EARLY"
ENTRY_CONFIRMED = "ENTRY_CONFIRMED"
ENTRY_LATE = "ENTRY_LATE"
NO_ENTRY = "NO_ENTRY"

ENTRY_STATUS_LABELS = {
    ENTRY_EARLY: "Entrada antecipada",
    ENTRY_CONFIRMED: "Entrada confirmada",
    ENTRY_LATE: "Entrada atrasada",
    NO_ENTRY: "Nao entrar",
}

LATE_WARNING = "ENTRADA ATRASADA / NAO PERSEGUIR PRECO"

_TIMEFRAME_SECONDS = {
    "1m": 60,
    "2m": 120,
    "3m": 180,
    "5m": 300,
    "15m": 900,
    "30m": 1800,
    "1h": 3600,
    "4h": 14400,
    "1d": 86400,
}


def _num(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if number == number else default


def _clean(candles: pd.DataFrame | None) -> pd.DataFrame:
    if candles is None or candles.empty:
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
    df = candles.copy()
    if "volume" not in df.columns:
        df["volume"] = 0.0
    return df.dropna(subset=["open", "high", "low", "close", "volume"])


def _atr(df: pd.DataFrame) -> float:
    if len(df) < 3:
        close = _num(df["close"].iloc[-1], 1.0) if not df.empty else 1.0
        return max(close * 0.006, 0.00000001)
    high_low = df["high"] - df["low"]
    high_close = (df["high"] - df["close"].shift(1)).abs()
    low_close = (df["low"] - df["close"].shift(1)).abs()
    true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1).dropna()
    value = _num(true_range.tail(14).mean())
    close = _num(df["close"].iloc[-1], 1.0)
    return max(value or close * 0.006, 0.00000001)


def _candle_progress(last_index: Any, timeframe: str) -> float:
    seconds = _TIMEFRAME_SECONDS.get(str(timeframe), 60)
    if not hasattr(last_index, "to_pydatetime"):
        return 1.0
    start = last_index.to_pydatetime()
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    elapsed = (datetime.now(timezone.utc) - start.astimezone(timezone.utc)).total_seconds()
    return max(0.0, min(1.0, elapsed / max(seconds, 1)))


def _direction_from_flow(flow: dict[str, Any], volume: dict[str, Any]) -> str:
    bias = str(flow.get("order_flow_bias") or flow.get("pressure") or "").upper()
    dominant = str(volume.get("dominant_side") or "").upper()
    signal = str(volume.get("signal") or "").upper()
    if bias in {"BUY_FLOW", "BUYER", "COMPRADOR", "COMPRADORA"} or dominant in {"BUYER", "COMPRADOR"} or signal == "BULLISH_VOLUME":
        return "BUY"
    if bias in {"SELL_FLOW", "SELLER", "VENDEDOR", "VENDEDORA"} or dominant in {"SELLER", "VENDEDOR"} or signal == "BEARISH_VOLUME":
        return "SELL"
    return "NEUTRAL"


def _timeframe_aligned(direction: str, macro: dict[str, Any], mtf: dict[str, Any] | None = None) -> bool:
    mtf = mtf or {}
    macro_direction = macro.get("direction") or macro.get("htf_direction")
    if macro_direction == direction and not macro.get("blocked"):
        return True
    dominant = mtf.get("dominant_direction")
    if dominant == "BULLISH":
        return direction == "BUY" and bool(mtf.get("strong_signal_allowed", True))
    if dominant == "BEARISH":
        return direction == "SELL" and bool(mtf.get("strong_signal_allowed", True))
    return False


def _ideal_price(direction: str, structure: dict[str, Any], trade_plan: dict[str, Any], fallback: float) -> float:
    sweep = structure.get("liquidity_sweep") or {}
    bos = structure.get("bos") or {}
    zone = structure.get("institutional_zone") or {}
    for value in [
        trade_plan.get("entry"),
        sweep.get("level"),
        bos.get("level"),
        zone.get("mid"),
        zone.get("high") if direction == "BUY" else zone.get("low"),
    ]:
        if value is not None:
            return _num(value, fallback)
    return fallback


def build_entry_timing(
    candles: pd.DataFrame,
    direction: str,
    *,
    timeframe: str = "1m",
    score: float = 0,
    min_score: float = 65,
    trade_plan: dict[str, Any] | None = None,
    risk: dict[str, Any] | None = None,
    structure: dict[str, Any] | None = None,
    confirmation: dict[str, Any] | None = None,
    volume: dict[str, Any] | None = None,
    flow: dict[str, Any] | None = None,
    macro: dict[str, Any] | None = None,
    mtf: dict[str, Any] | None = None,
    layered_signal: dict[str, Any] | None = None,
) -> dict[str, Any]:
    df = _clean(candles)
    trade_plan = trade_plan or {}
    risk = risk or {}
    structure = structure or {}
    confirmation = confirmation or {}
    volume = volume or {}
    flow = flow or {}
    macro = macro or {}
    layered_signal = layered_signal or {}

    if df.empty or direction not in {"BUY", "SELL"}:
        return _payload(NO_ENTRY, "Sem direcao institucional acionavel.", direction)

    current = df.iloc[-1]
    previous = df.iloc[-2] if len(df) >= 2 else current
    open_price = _num(current["open"])
    close = _num(current["close"])
    high = _num(current["high"])
    low = _num(current["low"])
    prev_close = _num(previous["close"], close)
    atr = _atr(df)
    candle_range = max(high - low, 0.00000001)
    body = abs(close - open_price)
    body_ratio = body / candle_range
    velocity_atr = body / atr
    impulse_atr = abs(close - prev_close) / atr
    volume_ratio = _num((volume.get("metrics") or {}).get("volume_ratio"), _num((confirmation.get("volume") or {}).get("ratio"), 1.0))
    ideal = _ideal_price(direction, structure, trade_plan, open_price)
    moved_atr = abs(close - ideal) / atr
    progress = _candle_progress(df.index[-1], timeframe)

    candle_direction = "BUY" if close > open_price else "SELL" if close < open_price else "NEUTRAL"
    candle_gaining_strength = candle_direction == direction and body_ratio >= 0.34 and velocity_atr >= 0.18
    flow_direction = _direction_from_flow(flow, volume)
    strong_flow = flow_direction == direction and (
        volume_ratio >= 1.12
        or _num(flow.get("flow_score"), _num(flow.get("intensity"), 0)) >= 58
        or str(flow.get("order_flow_bias") or "").upper() in {"BUY_FLOW", "SELL_FLOW"}
    )
    sweep = structure.get("liquidity_sweep") or {}
    sweep_ok = bool(sweep.get("detected") and sweep.get("direction") == direction)
    bos = structure.get("bos") or {}
    breakout_level = bos.get("level")
    initial_breakout = bool(
        breakout_level is not None
        and bos.get("direction") == direction
        and ((direction == "BUY" and high >= _num(breakout_level) and close >= _num(breakout_level))
             or (direction == "SELL" and low <= _num(breakout_level) and close <= _num(breakout_level)))
        and moved_atr <= 0.9
    )
    mtf_aligned = _timeframe_aligned(direction, macro, mtf)
    risk_allowed = risk.get("allowed", True) is not False
    rr = _num(trade_plan.get("riskReward") or trade_plan.get("risk_reward") or (layered_signal.get("risk_reward") if layered_signal else None), 0)
    risk_ok = risk_allowed and (rr == 0 or rr >= 1.0)
    score_ok = _num(score) >= max(35, _num(min_score) - 15)
    confirmed = bool(confirmation.get("valid") or layered_signal.get("generated"))

    reasons: list[str] = []
    if strong_flow:
        reasons.append("Fluxo forte alinhado.")
    if initial_breakout:
        reasons.append("Rompimento inicial detectado.")
    if sweep_ok:
        reasons.append("Liquidez varrida a favor do setup.")
    if candle_gaining_strength:
        reasons.append("Candle atual ganhando forca.")
    if mtf_aligned:
        reasons.append("Direcao MTF alinhada.")

    late = moved_atr >= 1.15 or (moved_atr >= 0.85 and progress >= 0.55 and impulse_atr >= 0.35)
    early_conditions = sum([strong_flow, initial_breakout or sweep_ok, candle_gaining_strength, mtf_aligned])

    if late:
        reasons.append(LATE_WARNING)
        return _payload(ENTRY_LATE, LATE_WARNING, direction, ideal, moved_atr, progress, reasons, risk_ok)
    if not risk_ok:
        return _payload(NO_ENTRY, (risk.get("reason") or "Gestao de risco bloqueou a entrada."), direction, ideal, moved_atr, progress, reasons, False)
    if confirmed and score_ok and mtf_aligned and strong_flow:
        return _payload(ENTRY_CONFIRMED, "Entrada confirmada por confluencia institucional, fluxo e risco.", direction, ideal, moved_atr, progress, reasons, True)
    if score_ok and early_conditions >= 3 and moved_atr <= 0.85:
        return _payload(ENTRY_EARLY, "Entrada antecipada: inicio do movimento detectado sem esperar sempre o fechamento do candle.", direction, ideal, moved_atr, progress, reasons, True)

    blockers = []
    if not strong_flow:
        blockers.append("Fluxo ainda nao forte o suficiente.")
    if not (initial_breakout or sweep_ok):
        blockers.append("Sem rompimento inicial ou liquidez varrida.")
    if not candle_gaining_strength:
        blockers.append("Candle atual ainda nao ganhou forca.")
    if not mtf_aligned:
        blockers.append("Direcao MTF ainda nao alinhada.")
    if not score_ok:
        blockers.append("Score abaixo da faixa minima para antecipacao.")
    return _payload(NO_ENTRY, blockers[0] if blockers else "Aguardar melhor assimetria.", direction, ideal, moved_atr, progress, reasons + blockers, risk_ok)


def _payload(
    status: str,
    reason: str,
    direction: str,
    ideal_entry: float | None = None,
    moved_atr: float = 0,
    candle_progress: float = 1,
    reasons: list[str] | None = None,
    risk_allowed: bool = False,
) -> dict[str, Any]:
    return {
        "status": status,
        "label": ENTRY_STATUS_LABELS[status],
        "action": ENTRY_STATUS_LABELS[status],
        "direction": direction,
        "entry_allowed": status in {ENTRY_EARLY, ENTRY_CONFIRMED} and risk_allowed,
        "late": status == ENTRY_LATE,
        "do_not_chase": status == ENTRY_LATE,
        "ideal_entry": round(ideal_entry, 8) if ideal_entry is not None else None,
        "movement_from_ideal_atr": round(moved_atr, 3),
        "candle_progress": round(candle_progress, 3),
        "reason": reason,
        "reasons": list(dict.fromkeys(reasons or [reason])),
        "warning": LATE_WARNING if status == ENTRY_LATE else None,
    }
