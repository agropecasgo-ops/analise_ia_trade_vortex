"""
Painel operacional da Live Trading.
"""

from __future__ import annotations

from typing import Any

from .signal_engine import build_signal_snapshot


def build_operational_panel(status: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    signal = build_signal_snapshot(status, context)
    return {
        "asset": status.get("symbol"),
        "timeframe": status.get("timeframe"),
        "live": True,
        "bias": signal["bias"],
        "confidence_score": signal["confidence"],
        "trend": context.get("trend"),
        "structure": context.get("market_structure"),
        "liquidity": _liquidity_label(context),
        "context": context.get("narrative"),
        "entry": signal["entry"],
        "entry_aggressive": signal["entry_aggressive"],
        "entry_conservative": signal["entry_conservative"],
        "stop": signal["stop"],
        "take": signal["take"],
        "risk_reward": signal["risk_reward"],
        "invalidation": signal["invalidation"],
        "pressure": context.get("pressure"),
        "last_bos": context.get("last_bos"),
        "last_choch": context.get("last_choch"),
        "summary": signal["summary"],
    }


def _liquidity_label(context: dict[str, Any]) -> str:
    sweep = context.get("liquidity_sweep") or {}
    if sweep.get("detected"):
        return f"Sweep {sweep.get('side')}"
    zones = context.get("liquidity_zones") or []
    if zones:
        return f"{len(zones)} zonas monitoradas"
    return "Sem liquidez proxima"
