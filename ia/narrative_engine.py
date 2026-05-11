"""
Narrative Engine operacional.
"""

from __future__ import annotations

from typing import Any


def build_operational_narrative(
    signal: dict[str, Any],
    smc: dict[str, Any],
    flow: dict[str, Any],
    mtf: dict[str, Any],
    risk: dict[str, Any],
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    context = context or {}
    feed = []
    if smc.get("liquidity_sweep", {}).get("detected"):
        feed.append("Sweep de liquidez detectado.")
    if smc.get("mss", {}).get("detected"):
        feed.append(f"MSS {smc['mss']['side']} confirmado.")
    if smc.get("choch") and smc.get("choch") != "none":
        feed.append(f"CHOCH {smc.get('choch')} confirmado.")
    if smc.get("relevant_fvg"):
        feed.append(f"Preco monitora FVG {smc['relevant_fvg'].get('type')}.")
    if flow.get("pressure") == "BUYER":
        feed.append("Fluxo comprador aumenta.")
    elif flow.get("pressure") == "SELLER":
        feed.append("Fluxo vendedor aumenta.")
    if signal.get("signal") == "AGUARDAR":
        feed.append("Aguardando confirmacao operacional.")
    if signal.get("signal") in ["COMPRA", "VENDA"]:
        feed.append(f"IA entrou em {signal.get('signal')} por confluencia institucional.")
    feed.append(f"Invalida em {risk.get('invalidation')}.")
    feed.append(mtf.get("narrative", "Multi-timeframe em leitura."))
    return {
        "summary": signal.get("reason") or context.get("narrative") or feed[0],
        "feed": list(dict.fromkeys([item for item in feed if item])),
        "liquidity": smc.get("liquidity_zone"),
        "invalidation": risk.get("invalidation"),
        "institutional_intent": smc.get("institutional_intent"),
    }
