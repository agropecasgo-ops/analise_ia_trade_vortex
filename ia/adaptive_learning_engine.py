"""
Adaptive learning status for institutional AI.

This module produces conservative parameter recommendations from performance
statistics. It adjusts weights and context recommendations only as guidance;
it does not retrain or replace the core AI engines.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any


def _num(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if number == number else default


def _text(value: Any, default: str = "unknown") -> str:
    if value is None:
        return default
    if isinstance(value, dict):
        return str(value.get("label") or value.get("type") or value.get("status") or list(value.values())[:1] or default)
    return str(value)


def _score_bucket(value: Any) -> str:
    score = _num(value)
    if score >= 80:
        return "score_alto"
    if score >= 60:
        return "score_medio"
    return "score_baixo"


class AdaptiveLearningEngine:
    CONTEXT_KEYS = {
        "operationalMode": ("operationalMode",),
        "scoreBucket": (),
        "entryTiming": ("entryTiming",),
        "direction": ("direction",),
        "orderFlowContext": ("orderFlowContext",),
        "multiTimeframeContext": ("multiTimeframeContext",),
        "liquidity": ("liquidity",),
        "marketStructure": ("marketStructure",),
    }

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
        closed = self._closed_signals()
        win_rate_contextual = self._win_rate_contextual(closed)
        best_timeframes = self._best_timeframes()
        best_assets = self._best_assets()
        strong_contexts = self._strong_contexts(win_rate_contextual)
        weak_contexts = self._weak_contexts(win_rate_contextual)
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
            "winRateContextual": win_rate_contextual,
            "bestTimeframes": best_timeframes,
            "bestAssets": best_assets,
            "strongContexts": strong_contexts,
            "weakContexts": weak_contexts,
            "adaptiveRecommendation": self._adaptive_recommendation(strong_contexts, weak_contexts, best_timeframes, best_assets),
            "contextSamples": self._context_samples(closed),
            "explanation": self._explanation(losing_streak, market_quality, score_adjustment),
        }

    def _closed_signals(self) -> list[dict[str, Any]]:
        return [signal for signal in self.history if signal.get("status") in {
            "Alvo final atingido", "Alvo 2 atingido", "Alvo 1 atingido", "Stop atingido", "Cancelado"
        }]

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

    def _best_timeframes(self) -> list[dict[str, Any]]:
        timeframes = self.performance.get("winRateByTimeframe") or {}
        return sorted(
            [
                {
                    "timeframe": key,
                    "signals": int(value.get("signals", 0)),
                    "wins": int(value.get("wins", 0)),
                    "winRate": _num(value.get("winRate")),
                    "averageRR": _num(value.get("averageRR")),
                }
                for key, value in timeframes.items()
            ],
            key=lambda item: (item["winRate"], item["signals"]),
            reverse=True,
        )[:5]

    def _best_assets(self) -> list[dict[str, Any]]:
        assets = self.performance.get("winRateByAsset") or {}
        return sorted(
            [
                {
                    "asset": key,
                    "signals": int(value.get("signals", 0)),
                    "wins": int(value.get("wins", 0)),
                    "winRate": _num(value.get("winRate")),
                    "averageRR": _num(value.get("averageRR")),
                }
                for key, value in assets.items()
            ],
            key=lambda item: (item["winRate"], item["signals"]),
            reverse=True,
        )[:5]

    def _win_rate_contextual(self, signals: list[dict[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for dimension, path in self.CONTEXT_KEYS.items():
            groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
            for signal in signals:
                if dimension == "scoreBucket":
                    key = _score_bucket(signal.get("score") or signal.get("confluence_score") or signal.get("signalStrength"))
                else:
                    key = self._extract_context_value(signal, path)
                groups[key].append(signal)
            result[dimension] = {
                key: self._context_metrics(items)
                for key, items in groups.items()
                if key != "unknown"
            }
        return result

    def _extract_context_value(self, signal: dict[str, Any], path: tuple[str, ...]) -> str:
        current: Any = signal
        for part in path:
            if not isinstance(current, dict):
                return "unknown"
            current = current.get(part)
        return _text(current)

    def _context_metrics(self, signals: list[dict[str, Any]]) -> dict[str, Any]:
        wins = sum(1 for signal in signals if signal.get("status") in {"Alvo final atingido", "Alvo 2 atingido", "Alvo 1 atingido"})
        losses = sum(1 for signal in signals if signal.get("status") in {"Stop atingido", "Cancelado"})
        total = len(signals)
        return {
            "signals": total,
            "wins": wins,
            "losses": losses,
            "winRate": round((wins / total * 100), 2) if total else 0.0,
            "averageRR": round(self._average([_num(signal.get("riskReward")) for signal in signals]), 2),
        }

    def _strong_contexts(self, contextual: dict[str, Any]) -> list[dict[str, Any]]:
        contexts = []
        for dimension, groups in contextual.items():
            for value, report in groups.items():
                if report["signals"] >= 3 and report["winRate"] >= 62:
                    contexts.append({"dimension": dimension, "value": value, **report})
        return sorted(contexts, key=lambda item: (item["winRate"], item["signals"]), reverse=True)[:8]

    def _weak_contexts(self, contextual: dict[str, Any]) -> list[dict[str, Any]]:
        contexts = []
        for dimension, groups in contextual.items():
            for value, report in groups.items():
                if report["signals"] >= 3 and report["winRate"] <= 45:
                    contexts.append({"dimension": dimension, "value": value, **report})
        return sorted(contexts, key=lambda item: (item["winRate"], item["signals"]))[:8]

    def _adaptive_recommendation(
        self,
        strong_contexts: list[dict[str, Any]],
        weak_contexts: list[dict[str, Any]],
        best_timeframes: list[dict[str, Any]],
        best_assets: list[dict[str, Any]],
    ) -> dict[str, Any]:
        recommendations = []
        if strong_contexts:
            recommendations.append(
                {
                    "type": "focus",
                    "message": "Considere priorizar estes contextos de alta eficácia.",
                    "contexts": [f"{item['dimension']}={item['value']}" for item in strong_contexts[:3]],
                }
            )
        if weak_contexts:
            recommendations.append(
                {
                    "type": "caution",
                    "message": "Atenção a contextos com desempenho inferior.",
                    "contexts": [f"{item['dimension']}={item['value']}" for item in weak_contexts[:3]],
                }
            )
        if best_timeframes:
            recommendations.append(
                {
                    "type": "timeframes",
                    "message": "Timeframes com melhor histórico de vitória.",
                    "values": [item["timeframe"] for item in best_timeframes[:3]],
                }
            )
        if best_assets:
            recommendations.append(
                {
                    "type": "assets",
                    "message": "Ativos com melhor histórico de vitória.",
                    "values": [item["asset"] for item in best_assets[:3]],
                }
            )
        if not recommendations:
            recommendations.append(
                {
                    "type": "neutral",
                    "message": "Ainda não há dados contextuais robustos suficientes para recomendação.",
                    "contexts": [],
                }
            )
        return {
            "summary": "; ".join(item["message"] for item in recommendations),
            "details": recommendations,
            "note": "Nao altera sinais automaticamente; apenas orienta validacao e monitoramento.",
        }

    def _context_samples(self, signals: list[dict[str, Any]]) -> list[dict[str, Any]]:
        samples = []
        for signal in signals[-80:]:
            samples.append({
                "asset": _text(signal.get("asset") or signal.get("symbol")),
                "timeframe": _text(signal.get("timeframe")),
                "operationalMode": _text(signal.get("operationalMode")),
                "score": _num(signal.get("score") or signal.get("confluence_score") or signal.get("signalStrength")),
                "entryTiming": _text(signal.get("entryTiming") or (signal.get("entry_timing") or {}).get("label") or signal.get("entryStatus")),
                "direction": _text(signal.get("direction")),
                "orderFlowContext": _text(signal.get("orderFlowContext")),
                "multiTimeframeContext": _text(signal.get("multiTimeframeContext")),
                "liquidity": _text(signal.get("liquidity")),
                "marketStructure": _text(signal.get("marketStructure")),
                "priceResult": _text(signal.get("partial_result")),
                "status": _text(signal.get("status")),
            })
        return samples

    def _context_metrics(self, signals: list[dict[str, Any]]) -> dict[str, Any]:
        wins = sum(1 for signal in signals if signal.get("status") in {"Alvo final atingido", "Alvo 2 atingido", "Alvo 1 atingido"})
        losses = sum(1 for signal in signals if signal.get("status") in {"Stop atingido", "Cancelado"})
        total = len(signals)
        return {
            "signals": total,
            "wins": wins,
            "losses": losses,
            "winRate": round((wins / total * 100), 2) if total else 0.0,
            "averageRR": round(self._average([_num(signal.get("riskReward")) for signal in signals]), 2),
        }

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

    def _average(self, values: list[float]) -> float:
        clean = [value for value in values if value == value]
        return round(sum(clean) / len(clean), 2) if clean else 0.0


def build_adaptive_status(performance: dict[str, Any], history: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return AdaptiveLearningEngine(performance, history).status()
