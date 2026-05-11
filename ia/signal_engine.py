"""
Normalizacao do sinal operacional exibido na Live Trading.
"""

from __future__ import annotations

from typing import Any


def build_signal_snapshot(status: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    direction = status.get("probable_direction", "NEUTRAL")
    state = status.get("state", "ANALYZING")
    return {
        "state": state,
        "direction": direction,
        "bias": context.get("operational_bias", direction),
        "score": status.get("confluence_score", 0),
        "confidence": status.get("confidence", 0),
        "entry": status.get("entry_aggressive") or status.get("entry_conservative"),
        "entry_aggressive": status.get("entry_aggressive"),
        "entry_conservative": status.get("entry_conservative"),
        "stop": status.get("stop_loss"),
        "take": status.get("take_profit"),
        "risk_reward": status.get("risk_reward"),
        "invalidation": context.get("invalidation"),
        "summary": context.get("narrative") or status.get("message"),
        "status": status.get("status"),
    }
