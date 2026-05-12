"""
AI score layer for the layered live signal engine.
"""

from __future__ import annotations

from typing import Any


class AIScoreEngine:
    WEIGHTS = {
        "trend_aligned": 25,
        "liquidity_sweep": 20,
        "strong_volume": 15,
        "valid_ob_or_fvg": 20,
        "good_volatility": 10,
    }

    def score(self, macro_context: dict[str, Any], structure: dict[str, Any], confirmation: dict[str, Any]) -> dict[str, Any]:
        components = {
            "trend_aligned": bool(macro_context.get("trend", {}).get("aligned") and macro_context.get("trend", {}).get("confirmed_by_m5")),
            "liquidity_sweep": bool(structure.get("liquidity_sweep", {}).get("detected")),
            "strong_volume": bool(confirmation.get("volume", {}).get("strong")),
            "valid_ob_or_fvg": bool((structure.get("order_block") or {}).get("valid") or (structure.get("fvg") or {}).get("valid")),
            "good_volatility": bool(macro_context.get("volatility", {}).get("good")),
        }
        score = sum(self.WEIGHTS[key] for key, enabled in components.items() if enabled)
        blockers = []
        if macro_context.get("blocked"):
            blockers.extend(macro_context.get("blockers", []))
        if confirmation.get("blockers"):
            blockers.extend(confirmation.get("blockers", []))
        if score < 80:
            blockers.append(f"Score {score}/90 abaixo do minimo 80.")
        return {
            "layer": "ai_score",
            "score": score,
            "max_score": sum(self.WEIGHTS.values()),
            "threshold": 80,
            "components": components,
            "weights": self.WEIGHTS,
            "approved": score >= 80 and not macro_context.get("blocked") and confirmation.get("valid"),
            "blockers": list(dict.fromkeys(blockers)),
        }
