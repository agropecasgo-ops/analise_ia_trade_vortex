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

    def score(
        self,
        macro_context: dict[str, Any],
        structure: dict[str, Any],
        confirmation: dict[str, Any],
        legacy_filters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        components = {
            "trend_aligned": bool(macro_context.get("trend", {}).get("aligned") and macro_context.get("trend", {}).get("confirmed_by_m5")),
            "liquidity_sweep": bool(structure.get("liquidity_sweep", {}).get("detected")),
            "strong_volume": bool(confirmation.get("volume", {}).get("strong")),
            "valid_ob_or_fvg": bool((structure.get("order_block") or {}).get("valid") or (structure.get("fvg") or {}).get("valid")),
            "good_volatility": bool(macro_context.get("volatility", {}).get("good")),
        }
        base_score = sum(self.WEIGHTS[key] for key, enabled in components.items() if enabled)
        legacy_input = legacy_filters or {}
        legacy = self._legacy_filter_effect(legacy_input, legacy_input.get("direction") or confirmation.get("direction", "NEUTRAL"))
        score = max(0, min(100, base_score + legacy["score_adjustment"]))
        blockers = []
        if macro_context.get("blocked"):
            blockers.extend(macro_context.get("blockers", []))
        if confirmation.get("blockers"):
            blockers.extend(confirmation.get("blockers", []))
        blockers.extend(legacy["blockers"])
        if base_score < 80:
            blockers.append(f"Score base por camadas {base_score}/90 abaixo do minimo 80.")
        if score < 80:
            blockers.append(f"Score {score}/100 abaixo do minimo 80.")
        return {
            "layer": "ai_score",
            "score": score,
            "base_score": base_score,
            "max_score": sum(self.WEIGHTS.values()),
            "threshold": 80,
            "components": components,
            "weights": self.WEIGHTS,
            "legacy_filters": legacy,
            "approved": (
                base_score >= 80
                and score >= 80
                and not macro_context.get("blocked")
                and confirmation.get("valid")
                and not legacy["blockers"]
            ),
            "blockers": list(dict.fromkeys(blockers)),
        }

    def _legacy_filter_effect(self, legacy_filters: dict[str, Any], layered_direction: str) -> dict[str, Any]:
        confirmations = []
        blockers = []
        adjustment = 0

        technical = legacy_filters.get("technical") or {}
        volume = legacy_filters.get("volume") or {}
        smc = legacy_filters.get("smc") or {}
        wyckoff = legacy_filters.get("wyckoff") or {}
        tape = legacy_filters.get("tape_reading") or legacy_filters.get("flow") or {}

        technical_signal = technical.get("signal")
        if technical_signal in ["BUY", "SELL"]:
            if technical_signal == layered_direction:
                confirmations.append("Indicador tecnico legado confirmou a direcao.")
                adjustment += 2
            elif layered_direction in ["BUY", "SELL"]:
                blockers.append("Indicador tecnico legado contra a direcao das camadas.")
                adjustment -= 6

        volume_signal = volume.get("signal")
        volume_direction = "BUY" if volume_signal in ["BULLISH_VOLUME", "BUY_FLOW"] else "SELL" if volume_signal in ["BEARISH_VOLUME", "SELL_FLOW"] else "NEUTRAL"
        if volume_direction == layered_direction:
            confirmations.append("Volume legado confirmou a direcao.")
            adjustment += 3
        elif volume_direction in ["BUY", "SELL"] and layered_direction in ["BUY", "SELL"]:
            blockers.append("Volume legado contra a direcao das camadas.")
            adjustment -= 7

        smc_bias = smc.get("institutional_bias")
        smc_direction = "BUY" if smc_bias == "bullish" else "SELL" if smc_bias == "bearish" else "NEUTRAL"
        if smc.get("invalidated") or (smc.get("false_breakout") or {}).get("detected"):
            blockers.append("Smart Money legado bloqueou por invalidacao/falso rompimento.")
            adjustment -= 10
        elif smc_direction == layered_direction:
            confirmations.append("Smart Money legado confirmou a direcao.")
            adjustment += 3
        elif smc_direction in ["BUY", "SELL"] and layered_direction in ["BUY", "SELL"]:
            blockers.append("Smart Money legado contra a direcao das camadas.")
            adjustment -= 7

        flow = tape.get("order_flow_bias") or tape.get("pressure")
        flow_direction = "BUY" if flow in ["BUY_FLOW", "BUYER"] else "SELL" if flow in ["SELL_FLOW", "SELLER"] else "NEUTRAL"
        if flow_direction == layered_direction:
            confirmations.append("Fluxo legado confirmou a direcao.")
            adjustment += 2
        elif flow_direction in ["BUY", "SELL"] and layered_direction in ["BUY", "SELL"]:
            blockers.append("Fluxo legado contra a direcao das camadas.")
            adjustment -= 5

        phase = wyckoff.get("wyckoff_phase") or wyckoff.get("phase")
        if layered_direction == "BUY" and phase == "acumulacao":
            confirmations.append("Wyckoff legado favorece compra.")
            adjustment += 1
        elif layered_direction == "SELL" and phase == "distribuicao":
            confirmations.append("Wyckoff legado favorece venda.")
            adjustment += 1

        return {
            "role": "auxiliary_filter_only",
            "can_generate_signal": False,
            "score_adjustment": max(-25, min(10, adjustment)),
            "confirmations": list(dict.fromkeys(confirmations)),
            "blockers": list(dict.fromkeys(blockers)),
        }
