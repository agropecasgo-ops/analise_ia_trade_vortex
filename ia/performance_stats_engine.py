"""
Performance statistics for institutional AI signals.

Consumes signal history snapshots and returns aggregate metrics without
changing execution or live signal behavior.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime
from typing import Any


def _num(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if number == number else default


def _parse_date(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None


class PerformanceStatsEngine:
    WIN_STATUSES = {"Alvo final atingido", "Alvo 2 atingido", "Alvo 1 atingido"}
    LOSS_STATUSES = {"Stop atingido", "Cancelado"}

    def __init__(self, history: list[dict[str, Any]], active: list[dict[str, Any]] | None = None) -> None:
        self.history = history or []
        self.active = active or []

    def calculate(self) -> dict[str, Any]:
        closed = [item for item in self.history if self._is_closed(item)]
        wins = [item for item in closed if self._is_win(item)]
        losses = [item for item in closed if self._is_loss(item)]
        return {
            "success": True,
            "totalSignals": len(closed),
            "activeSignals": len(self.active),
            "winRate": self._rate(len(wins), len(closed)),
            "winRateByAsset": self._win_rate_by("asset", closed),
            "winRateByTimeframe": self._win_rate_by("timeframe", closed),
            "payoff": self._payoff(wins, losses),
            "drawdown": self._drawdown(closed),
            "signalsByHour": self._signals_by_hour(closed + self.active),
            "bestSetups": self._setup_rank(closed, best=True),
            "weakestSetups": self._setup_rank(closed, best=False),
            "averageRiskReward": self._average([_num(item.get("riskReward")) for item in closed if _num(item.get("riskReward"))]),
            "breakEvenRate": self._break_even_rate(closed),
            "byAssetTimeframe": self._asset_timeframe_report(closed),
            "summary": self._summary(len(closed), len(wins), len(losses)),
        }

    def _is_closed(self, signal: dict[str, Any]) -> bool:
        return bool(signal.get("closedAt") or signal.get("status") in self.WIN_STATUSES | self.LOSS_STATUSES)

    def _is_win(self, signal: dict[str, Any]) -> bool:
        return signal.get("status") in self.WIN_STATUSES

    def _is_loss(self, signal: dict[str, Any]) -> bool:
        return signal.get("status") in self.LOSS_STATUSES

    def _rate(self, numerator: int, denominator: int) -> float:
        return round((numerator / denominator * 100), 2) if denominator else 0.0

    def _win_rate_by(self, key: str, signals: list[dict[str, Any]]) -> dict[str, Any]:
        buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for signal in signals:
            buckets[str(signal.get(key) or "--")].append(signal)
        return {
            bucket: {
                "signals": len(items),
                "wins": sum(1 for item in items if self._is_win(item)),
                "winRate": self._rate(sum(1 for item in items if self._is_win(item)), len(items)),
            }
            for bucket, items in buckets.items()
        }

    def _payoff(self, wins: list[dict[str, Any]], losses: list[dict[str, Any]]) -> float:
        avg_win = self._average([abs(self._result_pct(item)) for item in wins])
        avg_loss = self._average([abs(self._result_pct(item)) for item in losses])
        return round(avg_win / avg_loss, 2) if avg_loss else round(avg_win, 2)

    def _drawdown(self, signals: list[dict[str, Any]]) -> dict[str, Any]:
        equity = 0.0
        peak = 0.0
        max_drawdown = 0.0
        curve = []
        for signal in sorted(signals, key=lambda item: item.get("closedAt") or item.get("createdAt") or ""):
            equity += self._result_pct(signal)
            peak = max(peak, equity)
            max_drawdown = min(max_drawdown, equity - peak)
            curve.append(round(equity, 2))
        return {"maxDrawdownPct": round(abs(max_drawdown), 2), "equityCurve": curve[-80:]}

    def _signals_by_hour(self, signals: list[dict[str, Any]]) -> dict[str, int]:
        counts = Counter()
        for signal in signals:
            date = _parse_date(signal.get("createdAt") or signal.get("timestamp"))
            if date:
                counts[f"{date.hour:02d}:00"] += 1
        return dict(sorted(counts.items()))

    def _setup_rank(self, signals: list[dict[str, Any]], best: bool) -> list[dict[str, Any]]:
        buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for signal in signals:
            setup = self._setup_key(signal)
            buckets[setup].append(signal)
        ranked = []
        for setup, items in buckets.items():
            if len(items) < 1:
                continue
            win_rate = self._rate(sum(1 for item in items if self._is_win(item)), len(items))
            ranked.append({"setup": setup, "signals": len(items), "winRate": win_rate, "averageRR": self._average([_num(item.get("riskReward")) for item in items])})
        return sorted(ranked, key=lambda item: (item["winRate"], item["signals"]), reverse=best)[:5]

    def _asset_timeframe_report(self, signals: list[dict[str, Any]]) -> dict[str, Any]:
        buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for signal in signals:
            buckets[f"{signal.get('asset') or '--'}:{signal.get('timeframe') or '--'}"].append(signal)
        return {
            key: {
                "signals": len(items),
                "winRate": self._rate(sum(1 for item in items if self._is_win(item)), len(items)),
                "averageRR": self._average([_num(item.get("riskReward")) for item in items]),
                "breakEvenRate": self._break_even_rate(items),
            }
            for key, items in buckets.items()
        }

    def _break_even_rate(self, signals: list[dict[str, Any]]) -> float:
        if not signals:
            return 0.0
        count = sum(1 for item in signals if (item.get("breakEven") or {}).get("enabled") or item.get("status") == "Break Even ativado")
        return self._rate(count, len(signals))

    def _result_pct(self, signal: dict[str, Any]) -> float:
        text = str(signal.get("partial_result") or "0").replace("%", "")
        value = _num(text)
        if value:
            return value
        rr = _num(signal.get("riskReward"), 1)
        if self._is_win(signal):
            return rr
        if self._is_loss(signal):
            return -1.0
        return 0.0

    def _setup_key(self, signal: dict[str, Any]) -> str:
        direction = signal.get("direction") or "NEUTRAL"
        liquidity = (signal.get("liquidityUsed") or {}).get("type") or "sem_liquidez"
        macro = (signal.get("macroContext") or {}).get("volatility") or "vol"
        return f"{direction}:{liquidity}:{macro}"

    def _average(self, values: list[float]) -> float:
        clean = [value for value in values if value == value]
        return round(sum(clean) / len(clean), 2) if clean else 0.0

    def _summary(self, total: int, wins: int, losses: int) -> str:
        if not total:
            return "Ainda nao ha sinais finalizados suficientes para estatistica robusta."
        return f"{total} sinais finalizados, {wins} vencedores e {losses} perdedores."


def build_performance_stats(history: list[dict[str, Any]], active: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return PerformanceStatsEngine(history, active).calculate()
