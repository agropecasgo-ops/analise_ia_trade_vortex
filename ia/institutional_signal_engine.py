"""
Signal Engine institucional.
"""

from __future__ import annotations

from typing import Any


def build_institutional_signal(confluence: dict[str, Any], timing: dict[str, Any], risk: dict[str, Any]) -> dict[str, Any]:
    bias = confluence.get("bias", "NEUTRAL")
    score = float(confluence.get("score", 0) or 0)
    classification = confluence.get("classification", "nao_operar")
    invalid = not risk.get("valid") or bool(timing.get("avoid_late_entry"))
    if invalid:
        signal = "AGUARDAR"
        reason = "Risco estrutural ou entrada atrasada impede execucao."
    elif score <= 40:
        signal = "NEUTRO"
        reason = "Score institucional abaixo de 40."
    elif score <= 60 or not timing.get("confirmed"):
        signal = "AGUARDAR"
        reason = "Aguardando sweep, reteste, candle gatilho ou fluxo."
    elif bias == "BUY":
        signal = "COMPRA"
        reason = "Confluencia institucional compradora validada."
    elif bias == "SELL":
        signal = "VENDA"
        reason = "Confluencia institucional vendedora validada."
    else:
        signal = "NEUTRO"
        reason = "Sem vies institucional dominante."
    return {
        "signal": signal,
        "direction": "BUY" if signal == "COMPRA" else "SELL" if signal == "VENDA" else "NEUTRAL",
        "classification": classification,
        "entry": risk.get("entry"),
        "stop_loss": risk.get("stop_loss"),
        "take_profit": risk.get("take_profit"),
        "take_partial": risk.get("take_partial"),
        "risk_reward": risk.get("risk_reward"),
        "invalidation": risk.get("invalidation"),
        "reason": reason,
        "high_quality": signal in ["COMPRA", "VENDA"] and score >= 61 and timing.get("confirmed") and risk.get("valid"),
    }
