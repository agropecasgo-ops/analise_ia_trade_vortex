"""
Risk Engine institucional.
"""

from __future__ import annotations

from typing import Any


def _num(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if number == number else default


def _zone(zone: dict[str, Any] | None, key: str) -> float | None:
    if not zone:
        return None
    return _num(zone.get(key, zone.get("price", zone.get("mid")))) or None


def build_risk_plan(direction: str, price: float, levels: dict[str, Any], smc: dict[str, Any], atr: float | None = None) -> dict[str, Any]:
    direction = direction if direction in ["BUY", "SELL"] else "NEUTRAL"
    entry = _num(levels.get("entrada"), price)
    atr = _num(atr, max(entry * 0.006, 0.00000001))
    ob = smc.get("relevant_order_block") or smc.get("nearest_order_block")
    fvg = smc.get("relevant_fvg")
    sweep_zone = (smc.get("liquidity_sweep") or {}).get("zone")
    liquidity = smc.get("liquidity_zone")
    if direction == "BUY":
        stop = _zone(sweep_zone, "low") or _zone(ob, "low") or _zone(fvg, "low") or entry - atr * 1.6
        take = _zone(liquidity, "high") or entry + abs(entry - stop) * 1.8
    elif direction == "SELL":
        stop = _zone(sweep_zone, "high") or _zone(ob, "high") or _zone(fvg, "high") or entry + atr * 1.6
        take = _zone(liquidity, "low") or entry - abs(entry - stop) * 1.8
    else:
        stop = levels.get("stop_loss")
        take = levels.get("alvo_1")
    risk = abs(entry - _num(stop, entry))
    reward = abs(_num(take, entry) - entry)
    rr = reward / risk if risk else _num(levels.get("risco_retorno"))
    partial = entry + (take - entry) * 0.5 if direction == "BUY" else entry - (entry - take) * 0.5 if direction == "SELL" else levels.get("alvo_1")
    return {
        "entry": round(entry, 8),
        "stop_loss": round(_num(stop), 8) if stop is not None else None,
        "take_profit": round(_num(take), 8) if take is not None else None,
        "take_partial": round(_num(partial), 8) if partial is not None else None,
        "risk_reward": round(rr, 2),
        "minimum_rr": 1.15,
        "invalidation": round(_num(stop), 8) if stop is not None else None,
        "volatility_buffer": round(atr, 8),
        "valid": rr >= 1.15 if rr else False,
        "basis": "estrutura+sweep+OB+FVG",
    }
