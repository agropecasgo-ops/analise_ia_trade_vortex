"""
Multi-timeframe Engine institucional.
"""

from __future__ import annotations

from typing import Any


INSTITUTIONAL_TIMEFRAMES = {
    "1h": "context",
    "15m": "structure",
    "5m": "setup",
    "1m": "timing",
}


def build_institutional_mtf_context(analysis: dict[str, Any] | None, confluence: dict[str, Any] | None) -> dict[str, Any]:
    analysis = analysis or {}
    confluence = confluence or {}
    layers = {}
    alignment_score = 0
    dominant = confluence.get("dominant_direction", "NEUTRAL")
    for timeframe, role in INSTITUTIONAL_TIMEFRAMES.items():
        item = analysis.get(timeframe, {})
        direction = item.get("direction", "NEUTRAL")
        strength = float(item.get("strength", 0) or 0)
        aligned = dominant != "NEUTRAL" and direction == dominant
        if aligned:
            alignment_score += 25
        layers[role] = {
            "timeframe": timeframe,
            "direction": direction,
            "strength": strength,
            "aligned": aligned,
            "signal": item.get("signal"),
        }
    return {
        "dominant_direction": dominant,
        "layers": layers,
        "alignment_score": min(100, alignment_score),
        "confirmed": alignment_score >= 75,
        "required_alignment": "1H contexto, 15M estrutura, 5M setup, 1M timing",
        "narrative": _narrative(dominant, layers, alignment_score),
        **confluence,
    }


def _narrative(dominant: str, layers: dict[str, Any], score: float) -> str:
    if score >= 75:
        return f"Multi-timeframe alinhado para {dominant}."
    missing = [value["timeframe"] for value in layers.values() if not value["aligned"]]
    return f"Multi-timeframe ainda sem alinhamento completo; falta {', '.join(missing) or 'confirmacao'}."
