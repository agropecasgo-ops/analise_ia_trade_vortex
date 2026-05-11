"""
Wyckoff Engine contextual.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from .wyckoff_reader import read_wyckoff_advanced


def _num(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if number == number else default


def build_wyckoff_context(candles: pd.DataFrame, volume: dict[str, Any] | None = None, tape: dict[str, Any] | None = None) -> dict[str, Any]:
    volume = volume or {}
    tape = tape or {}
    try:
        wyckoff = read_wyckoff_advanced(candles)
    except Exception:
        wyckoff = {
            "wyckoff_phase": "indefinida",
            "phase": "indefinida",
            "bias": "neutral",
            "accumulation_score": 50,
            "distribution_score": 50,
            "confirmations": [],
            "invalidations": ["Wyckoff indisponivel."],
            "explanation": "Wyckoff sem leitura suficiente.",
        }

    accumulation = _num(wyckoff.get("accumulation_score"), 50)
    distribution = _num(wyckoff.get("distribution_score"), 50)
    absorption = bool((volume.get("absorption") or {}).get("detected") or (tape.get("absorption") or {}).get("detected"))
    effort_result = wyckoff.get("effort_vs_result") or wyckoff.get("effort_result") or {}
    intent = "neutral"
    if accumulation > distribution + 12 or wyckoff.get("spring"):
        intent = "accumulation"
    elif distribution > accumulation + 12 or wyckoff.get("upthrust"):
        intent = "distribution"
    if absorption and intent == "neutral":
        intent = "absorption"

    wyckoff.update({
        "institutional_intent": intent,
        "strength": round(max(accumulation, 100 - distribution), 2),
        "weakness": round(max(distribution, 100 - accumulation), 2),
        "absorption_confirmed": absorption,
        "effort_vs_result_context": effort_result,
        "manipulation_context": bool(wyckoff.get("institutional_manipulation") or wyckoff.get("spring") or wyckoff.get("upthrust")),
    })
    return wyckoff
