"""
Confluence Engine institucional com pesos dinamicos.
"""

from __future__ import annotations

from typing import Any


def _num(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if number == number else default


def classify_score(score: float) -> str:
    if score <= 40:
        return "nao_operar"
    if score <= 60:
        return "aguardar"
    if score <= 75:
        return "entrada_moderada"
    if score <= 90:
        return "entrada_forte"
    return "entrada_premium"


def build_institutional_confluence(
    smc: dict[str, Any],
    wyckoff: dict[str, Any],
    elliott: dict[str, Any],
    flow: dict[str, Any],
    mtf: dict[str, Any],
    technical: dict[str, Any],
    risk: dict[str, Any],
) -> dict[str, Any]:
    details = technical.get("details", {})
    components = {
        "smc": _num(smc.get("smc_score"), 50),
        "wyckoff": max(_num(wyckoff.get("strength"), 50), 100 - _num(wyckoff.get("weakness"), 50)),
        "elliott": _num(elliott.get("confidence"), 40),
        "flow": _num(flow.get("intensity"), 45),
        "vwap": 70 if _num(details.get("vwap")) and _num(technical.get("entry_price")) >= _num(details.get("vwap")) else 45,
        "ema": 76 if technical.get("trend", {}).get("direction") in ["BULLISH", "STRONG_BULLISH", "BEARISH", "STRONG_BEARISH"] else 42,
        "rsi": _rsi_score(details.get("rsi")),
        "macd": 68 if abs(_num((details.get("macd") or {}).get("histogram"))) > 0 else 45,
        "multi_timeframe": _num(mtf.get("alignment_score"), _num(mtf.get("average_strength"), 45)),
        "volatility": 68 if _num(details.get("atr")) > 0 else 45,
        "momentum": _num(technical.get("score"), 50),
        "risk_reward": 82 if risk.get("valid") else 32,
    }
    weights = _dynamic_weights(smc, flow, mtf)
    score = sum(components[key] * weights[key] for key in weights)
    confidence = max(5, min(95, score + abs(_num(flow.get("imbalance"))) * 0.08 - (0 if risk.get("valid") else 8)))
    return {
        "score": round(max(0, min(100, score)), 2),
        "confidence": round(confidence, 2),
        "classification": classify_score(score),
        "components": {key: round(value, 2) for key, value in components.items()},
        "weights": weights,
        "setup_strength": round(max(components["smc"], components["flow"], components["multi_timeframe"]), 2),
        "probability": round(confidence, 2),
        "bias": _bias(smc, flow, mtf),
    }


def _dynamic_weights(smc: dict[str, Any], flow: dict[str, Any], mtf: dict[str, Any]) -> dict[str, float]:
    weights = {
        "smc": 0.18,
        "wyckoff": 0.09,
        "elliott": 0.05,
        "flow": 0.15,
        "vwap": 0.07,
        "ema": 0.08,
        "rsi": 0.05,
        "macd": 0.05,
        "multi_timeframe": 0.12,
        "volatility": 0.04,
        "momentum": 0.07,
        "risk_reward": 0.05,
    }
    if smc.get("manipulation", {}).get("detected") or smc.get("liquidity_sweep", {}).get("detected"):
        weights["smc"] += 0.04
        weights["flow"] += 0.02
        weights["rsi"] -= 0.02
        weights["macd"] -= 0.02
        weights["ema"] -= 0.02
    if flow.get("pressure") != "BALANCED":
        weights["flow"] += 0.03
        weights["momentum"] += 0.01
        weights["rsi"] -= 0.01
        weights["macd"] -= 0.01
        weights["volatility"] -= 0.02
    if mtf.get("confirmed"):
        weights["multi_timeframe"] += 0.03
        weights["risk_reward"] += 0.01
        weights["vwap"] -= 0.01
        weights["ema"] -= 0.01
        weights["volatility"] -= 0.02
    total = sum(weights.values())
    return {key: round(value / total, 4) for key, value in weights.items()}


def _rsi_score(rsi: Any) -> float:
    value = _num(rsi, 50)
    if 42 <= value <= 68:
        return 68
    if value > 76 or value < 24:
        return 28
    return 48


def _bias(smc: dict[str, Any], flow: dict[str, Any], mtf: dict[str, Any]) -> str:
    votes = []
    if smc.get("institutional_bias") == "bullish":
        votes.append("BUY")
    if smc.get("institutional_bias") == "bearish":
        votes.append("SELL")
    if flow.get("pressure") == "BUYER":
        votes.append("BUY")
    if flow.get("pressure") == "SELLER":
        votes.append("SELL")
    if mtf.get("dominant_direction") == "BULLISH":
        votes.append("BUY")
    if mtf.get("dominant_direction") == "BEARISH":
        votes.append("SELL")
    return "BUY" if votes.count("BUY") > votes.count("SELL") else "SELL" if votes.count("SELL") > votes.count("BUY") else "NEUTRAL"
