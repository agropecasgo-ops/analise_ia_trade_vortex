"""
Adaptive learning status for institutional AI.

This module produces conservative parameter recommendations from performance
statistics. It adjusts weights/filtros only as guidance; it does not retrain or
replace the core AI engines.
"""

from __future__ import annotations

from typing import Any


def _num(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if number == number else default


class AdaptiveLearningEngine:
    def __init__(self, performance: dict[str, Any], history: list[dict[str, Any]] | None = None) -> None:
        self.performance = performance or {}
        self.history = history or []

    def status(self) -> dict[str, Any]:
        losing_streak = self._losing_streak()
        market_quality = self._market_quality()
        score_adjustment = self._score_adjustment(losing_streak, market_quality)
        bad_hours = self._bad_hours()
        preferred = self._preferred_asset_timeframes(best=True)
        avoided = self._preferred_asset_timeframes(best=False)
        weights = self._weights()
        return {
            "success": True,
            "mode": "ADAPTIVE_FILTERS_ONLY",
            "aggressiveness": self._aggressiveness(losing_streak, market_quality),
            "minimumScoreAdjustment": score_adjustment,
            "recommendedMinimumScore": 88 + score_adjustment,
            "badHours": bad_hours,
            "preferredAssetTimeframes": preferred,
            "reducedAssetTimeframes": avoided,
            "confluenceWeights": weights,
            "filters": {
                "reduceAfterLosingStreak": losing_streak >= 2,
                "increaseScoreInPoorMarket": market_quality == "poor",
                "reduceSignalsInBadHours": bool(bad_hours),
                "prioritizeBetterAssets": bool(preferred),
            },
            "explanation": self._explanation(losing_streak, market_quality, score_adjustment),
        }

    def _losing_streak(self) -> int:
        streak = 0
        for signal in reversed(self.history or []):
            status = signal.get("status")
            if status in {"Stop atingido", "Cancelado"}:
                streak += 1
                continue
            if status in {"Alvo final atingido", "Alvo 2 atingido", "Alvo 1 atingido"}:
                break
        return streak

    def _market_quality(self) -> str:
        win_rate = _num(self.performance.get("winRate"))
        drawdown = _num((self.performance.get("drawdown") or {}).get("maxDrawdownPct"))
        if win_rate and win_rate < 42:
            return "poor"
        if drawdown >= 4:
            return "poor"
        if win_rate >= 58:
            return "good"
        return "neutral"

    def _score_adjustment(self, losing_streak: int, market_quality: str) -> int:
        adjustment = 0
        if losing_streak >= 2:
            adjustment += min(8, losing_streak * 2)
        if market_quality == "poor":
            adjustment += 5
        return min(12, adjustment)

    def _bad_hours(self) -> list[dict[str, Any]]:
        by_hour = self.performance.get("signalsByHour") or {}
        if not by_hour:
            return []
        losses_by_hour: dict[str, int] = {}
        total_by_hour: dict[str, int] = {hour: int(count) for hour, count in by_hour.items()}
        for signal in self.history:
            hour = self._hour(signal)
            if not hour:
                continue
            if signal.get("status") in {"Stop atingido", "Cancelado"}:
                losses_by_hour[hour] = losses_by_hour.get(hour, 0) + 1
        bad = []
        for hour, total in total_by_hour.items():
            losses = losses_by_hour.get(hour, 0)
            if total >= 2 and losses / max(total, 1) >= 0.6:
                bad.append({"hour": hour, "signals": total, "losses": losses, "action": "reduzir_sinais"})
        return bad[:6]

    def _preferred_asset_timeframes(self, best: bool) -> list[dict[str, Any]]:
        report = self.performance.get("byAssetTimeframe") or {}
        items = [
            {"key": key, **value}
            for key, value in report.items()
            if int(value.get("signals", 0)) >= 1
        ]
        if best:
            return sorted(items, key=lambda item: (item.get("winRate", 0), item.get("averageRR", 0)), reverse=True)[:5]
        return sorted(items, key=lambda item: (item.get("winRate", 0), item.get("averageRR", 0)))[:5]

    def _weights(self) -> dict[str, Any]:
        best_setups = self.performance.get("bestSetups") or []
        weakest_setups = self.performance.get("weakestSetups") or []
        weights = {
            "liquidity": 1.0,
            "structure": 1.0,
            "timing": 1.0,
            "riskReward": 1.0,
            "macroContext": 1.0,
        }
        if any("sem_liquidez" in item.get("setup", "") for item in weakest_setups):
            weights["liquidity"] = 1.15
        if any(_num(item.get("averageRR")) < 1.3 for item in weakest_setups):
            weights["riskReward"] = 1.12
        if best_setups:
            weights["timing"] = 1.05
            weights["structure"] = 1.05
        return {
            "role": "recommendation_only",
            "weights": weights,
            "note": "Ajustes consultivos para filtros/confluencia; nao recriam a IA.",
        }

    def _aggressiveness(self, losing_streak: int, market_quality: str) -> str:
        if losing_streak >= 3 or market_quality == "poor":
            return "REDUZIDA"
        if market_quality == "good":
            return "NORMAL"
        return "MODERADA"

    def _explanation(self, losing_streak: int, market_quality: str, adjustment: int) -> str:
        return (
            f"Sequencia ruim: {losing_streak}. Qualidade de mercado: {market_quality}. "
            f"Exigencia de score ajustada em +{adjustment} ponto(s)."
        )

    def _hour(self, signal: dict[str, Any]) -> str | None:
        value = signal.get("createdAt") or signal.get("timestamp")
        if not value:
            return None
        try:
            hour = str(value).split("T", 1)[1][:2]
            return f"{hour}:00"
        except Exception:
            return None


def build_adaptive_status(performance: dict[str, Any], history: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return AdaptiveLearningEngine(performance, history).status()
