"""
Flow Engine institucional.
"""

from __future__ import annotations

from typing import Any


def _num(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if number == number else default


def build_flow_context(volume: dict[str, Any] | None, tape: dict[str, Any] | None) -> dict[str, Any]:
    volume = volume or {}
    tape = tape or {}
    buyer_volume = _num(volume.get("buyer_volume"))
    seller_volume = _num(volume.get("seller_volume"))
    total_volume = max(buyer_volume + seller_volume, 0.00000001)
    volume_delta = (buyer_volume - seller_volume) / total_volume * 100
    buy_aggression = _num(tape.get("buy_aggression"), max(0, volume_delta))
    sell_aggression = _num(tape.get("sell_aggression"), max(0, -volume_delta))
    imbalance = _num(tape.get("imbalance"), buy_aggression - sell_aggression)
    pressure = "BUYER" if imbalance >= 12 or volume_delta >= 12 else "SELLER" if imbalance <= -12 or volume_delta <= -12 else "BALANCED"
    intensity = min(100, abs(imbalance) * 0.65 + _num(volume.get("metrics", {}).get("volume_ratio"), 1) * 22)
    absorption = (volume.get("absorption") or {}).get("detected") or (tape.get("absorption") or {}).get("detected")
    return {
        "pressure": pressure,
        "delta": round(volume_delta, 2),
        "imbalance": round(imbalance, 2),
        "buy_aggression": round(buy_aggression, 2),
        "sell_aggression": round(sell_aggression, 2),
        "intensity": round(intensity, 2),
        "absorption": {
            "detected": bool(absorption),
            "side": (volume.get("absorption") or {}).get("side") or (tape.get("absorption") or {}).get("side") or "NONE",
        },
        "movement_intensity": "alta" if intensity >= 70 else "moderada" if intensity >= 45 else "baixa",
        "narrative": _narrative(pressure, intensity, absorption),
    }


def _narrative(pressure: str, intensity: float, absorption: bool) -> str:
    if absorption:
        return "Absorcao detectada; fluxo exige confirmacao."
    if pressure == "BUYER":
        return f"Fluxo comprador dominante com intensidade {intensity:.0f}."
    if pressure == "SELLER":
        return f"Fluxo vendedor dominante com intensidade {intensity:.0f}."
    return "Fluxo equilibrado; sem agressao dominante."
