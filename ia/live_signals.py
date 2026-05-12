"""
Sinais IA em Tempo Real.

The live signal stack consumes the layered AI engine output and keeps a local
repository of active/finalized signals, including automatic break even updates.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


DISCLAIMER = "Analise educativa. Nao constitui recomendacao financeira. Toda operacao envolve risco."

STATUS_WAITING = "Aguardando entrada"
STATUS_TRIGGERED = "Entrada acionada"
STATUS_RUNNING = "Em andamento"
STATUS_BE = "Break Even ativado"
STATUS_TP1 = "Alvo 1 atingido"
STATUS_TP2 = "Alvo 2 atingido"
STATUS_FINAL = "Alvo final atingido"
STATUS_STOP = "Stop atingido"
STATUS_CANCELED = "Cancelado"

FINAL_STATUSES = {STATUS_FINAL, STATUS_STOP, STATUS_CANCELED}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _num(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if number == number else default


class SignalScoreService:
    def allowed(self, live_status: dict[str, Any]) -> tuple[bool, list[str]]:
        layered = live_status.get("layered_signal") or {}
        signal = layered.get("signal") or {}
        score = _num((layered.get("ai_score") or {}).get("score"), _num(live_status.get("confluence_score")))
        reasons = []
        if not signal.get("generated"):
            reasons.append(signal.get("reason") or "Engine por camadas nao gerou sinal.")
        if score < 80:
            reasons.append(f"Score {score:.0f} abaixo do minimo 80.")
        if live_status.get("state") not in ["BUY_CONFIRMED", "SELL_CONFIRMED"]:
            reasons.append("Sem confirmacao final das camadas.")
        if live_status.get("layered_signal", {}).get("macro_context", {}).get("blocked"):
            reasons.extend(live_status["layered_signal"]["macro_context"].get("blockers", []))
        if live_status.get("layered_signal", {}).get("confirmation", {}).get("blockers"):
            reasons.extend(live_status["layered_signal"]["confirmation"].get("blockers", []))
        return not reasons, list(dict.fromkeys(reasons))


class SignalRiskManager:
    def build(self, signal: dict[str, Any]) -> dict[str, Any]:
        direction = signal.get("direction_code")
        entry = _num(signal.get("entry_price"))
        stop = _num(signal.get("stop_loss"))
        tp1 = _num(signal.get("take_profit_1"))
        tp2 = _num(signal.get("take_profit_2"))
        final = _num(signal.get("take_profit_2"), tp2)
        risk = abs(entry - stop)
        reward = abs(tp1 - entry)
        rr = reward / max(risk, 0.00000001)
        protected_offset = risk * 0.03
        if direction == "BUY":
            trigger = entry + 0.7 * (final - entry)
            new_stop = entry + protected_offset
        else:
            trigger = entry - 0.7 * (entry - final)
            new_stop = entry - protected_offset
        return {
            "entryPrice": round(entry, 8),
            "stopLoss": round(stop, 8),
            "takeProfit1": round(tp1, 8),
            "takeProfit2": round(tp2, 8),
            "takeProfitFinal": round(final, 8),
            "riskReward": round(rr, 2),
            "breakEven": {
                "enabled": False,
                "triggerPrice": round(trigger, 8),
                "newStopLoss": round(new_stop, 8),
                "activatedAt": None,
            },
        }


class BreakEvenManager:
    def update(self, signal: dict[str, Any], current_price: float) -> bool:
        be = signal.get("breakEven") or {}
        if be.get("enabled"):
            return False
        direction = signal.get("direction")
        trigger = _num(be.get("triggerPrice"))
        reached = (direction == "BUY" and current_price >= trigger) or (direction == "SELL" and current_price <= trigger)
        if not reached:
            return False
        be["enabled"] = True
        be["activatedAt"] = _now()
        signal["breakEven"] = be
        signal["stopLoss"] = be.get("newStopLoss")
        signal["stop_loss"] = be.get("newStopLoss")
        signal["status"] = STATUS_BE
        self._event(signal, STATUS_BE, current_price)
        return True

    def _event(self, signal: dict[str, Any], status: str, price: float) -> None:
        signal.setdefault("history", []).append({"status": status, "price": round(price, 8), "at": _now()})


class SignalRepository:
    def __init__(self) -> None:
        self.active: dict[str, dict[str, Any]] = {}
        self.history: list[dict[str, Any]] = []

    def duplicate_key(self, signal: dict[str, Any]) -> str:
        zone = round(_num(signal.get("entryPrice")), 4)
        return f"{signal.get('asset')}:{signal.get('timeframe')}:{signal.get('direction')}:{zone}"

    def save(self, signal: dict[str, Any]) -> dict[str, Any]:
        self.active[self.duplicate_key(signal)] = signal
        return signal

    def find_duplicate(self, signal: dict[str, Any]) -> dict[str, Any] | None:
        return self.active.get(self.duplicate_key(signal))

    def list_active(self) -> list[dict[str, Any]]:
        return sorted(self.active.values(), key=lambda item: item["createdAt"], reverse=True)

    def list_history(self, limit: int = 100) -> list[dict[str, Any]]:
        return self.history[-limit:][::-1]

    def finalize(self, key: str, signal: dict[str, Any]) -> None:
        if key in self.active:
            self.active.pop(key, None)
        signal["closedAt"] = _now()
        self.history.append(signal.copy())

    def stats(self) -> dict[str, Any]:
        return {
            "active_count": len(self.active),
            "history_count": len(self.history),
            "open_buy": sum(1 for item in self.active.values() if item["direction"] == "BUY"),
            "open_sell": sum(1 for item in self.active.values() if item["direction"] == "SELL"),
        }


class SignalEngine:
    def __init__(self, repository: SignalRepository | None = None) -> None:
        self.repository = repository or SignalRepository()
        self.score_service = SignalScoreService()
        self.risk = SignalRiskManager()
        self.break_even = BreakEvenManager()

    def update_from_live_status(self, live_status: dict[str, Any], market_meta=None, mtf_confluence=None) -> dict[str, Any]:
        market_meta = market_meta or {}
        layered = live_status.get("layered_signal") or {}
        raw_signal = layered.get("signal") or {}
        current_price = _num(live_status.get("current_price"))

        for key, signal in list(self.repository.active.items()):
            if signal.get("asset") == live_status.get("symbol") and signal.get("timeframe") == live_status.get("timeframe"):
                self.update_price(signal, current_price, key)
                return signal

        allowed, blockers = self.score_service.allowed(live_status)
        if not allowed:
            return self.waiting_payload(live_status, blockers)

        signal = self.create_signal(live_status, raw_signal, market_meta)
        duplicate = self.repository.find_duplicate(signal)
        if duplicate:
            self.update_price(duplicate, current_price, self.repository.duplicate_key(duplicate))
            return duplicate
        return self.repository.save(signal)

    def create_signal(self, live_status: dict[str, Any], raw_signal: dict[str, Any], market_meta=None) -> dict[str, Any]:
        risk = self.risk.build(raw_signal)
        layered = live_status.get("layered_signal") or {}
        ai_score = layered.get("ai_score") or {}
        reasons = [raw_signal.get("reason") or live_status.get("reason")]
        reasons.extend(live_status.get("confirmations") or [])
        signal = {
            "id": uuid4().hex,
            "asset": live_status.get("symbol"),
            "symbol": live_status.get("symbol"),
            "direction": raw_signal.get("direction_code"),
            "signalStrength": int(_num(ai_score.get("score"), live_status.get("confluence_score"))),
            "entryPrice": risk["entryPrice"],
            "stopLoss": risk["stopLoss"],
            "takeProfit1": risk["takeProfit1"],
            "takeProfit2": risk["takeProfit2"],
            "takeProfitFinal": risk["takeProfitFinal"],
            "riskReward": risk["riskReward"],
            "status": STATUS_WAITING,
            "reasons": [item for item in dict.fromkeys(reasons) if item],
            "timeframe": live_status.get("timeframe"),
            "createdAt": _now(),
            "breakEven": risk["breakEven"],
            "layers": {
                "macroContext": not (layered.get("macro_context") or {}).get("blocked", True),
                "marketStructure": bool((layered.get("market_structure") or {}).get("valid")),
                "confirmation": bool((layered.get("confirmation") or {}).get("valid")),
                "aiScore": int(_num(ai_score.get("score"), live_status.get("confluence_score"))),
            },
            "market": (market_meta or {}).get("market") or live_status.get("market"),
            "lastPrice": live_status.get("current_price"),
            "history": [{"status": STATUS_WAITING, "price": live_status.get("current_price"), "at": _now()}],
            "disclaimer": DISCLAIMER,
        }
        signal.update({
            "entry": signal["entryPrice"],
            "entry_aggressive": signal["entryPrice"],
            "entry_conservative": signal["entryPrice"],
            "stop_loss": signal["stopLoss"],
            "take_profit_1": signal["takeProfit1"],
            "take_profit_2": signal["takeProfit2"],
            "take_profit_3": signal["takeProfitFinal"],
            "risk_reward": signal["riskReward"],
            "confluence_score": signal["signalStrength"],
            "confidence": signal["signalStrength"],
            "timestamp": signal["createdAt"],
            "technical_reason": signal["reasons"][0] if signal["reasons"] else "",
            "explanation": " ".join(signal["reasons"][:3]),
            "partial_result": "0.00%",
        })
        self.update_price(signal, _num(live_status.get("current_price")), None)
        return signal

    def update_price(self, signal: dict[str, Any], current_price: float, key: str | None = None) -> dict[str, Any]:
        if not current_price:
            return signal
        signal["lastPrice"] = round(current_price, 8)
        if signal["status"] in FINAL_STATUSES:
            return signal

        direction = signal.get("direction")
        entry = _num(signal.get("entryPrice"))
        stop = _num(signal.get("stopLoss"))
        tp1 = _num(signal.get("takeProfit1"))
        tp2 = _num(signal.get("takeProfit2"))
        final = _num(signal.get("takeProfitFinal"))

        if signal["status"] == STATUS_WAITING:
            triggered = (direction == "BUY" and current_price >= entry) or (direction == "SELL" and current_price <= entry)
            if triggered:
                signal["status"] = STATUS_TRIGGERED
                self._event(signal, STATUS_TRIGGERED, current_price)
        signal["partial_result"] = self._partial_result(signal, current_price)

        self.break_even.update(signal, current_price)

        if direction == "BUY":
            if stop and current_price <= stop:
                self._finish(signal, STATUS_STOP, current_price, key)
            elif final and current_price >= final:
                self._finish(signal, STATUS_FINAL, current_price, key)
            elif tp2 and current_price >= tp2:
                self._status(signal, STATUS_TP2, current_price)
            elif tp1 and current_price >= tp1:
                self._status(signal, STATUS_TP1, current_price)
            elif signal["status"] == STATUS_TRIGGERED:
                self._status(signal, STATUS_RUNNING, current_price)
        elif direction == "SELL":
            if stop and current_price >= stop:
                self._finish(signal, STATUS_STOP, current_price, key)
            elif final and current_price <= final:
                self._finish(signal, STATUS_FINAL, current_price, key)
            elif tp2 and current_price <= tp2:
                self._status(signal, STATUS_TP2, current_price)
            elif tp1 and current_price <= tp1:
                self._status(signal, STATUS_TP1, current_price)
            elif signal["status"] == STATUS_TRIGGERED:
                self._status(signal, STATUS_RUNNING, current_price)
        return signal

    def waiting_payload(self, live_status: dict[str, Any], blockers: list[str]) -> dict[str, Any]:
        return {
            "id": None,
            "asset": live_status.get("symbol"),
            "symbol": live_status.get("symbol"),
            "direction": live_status.get("probable_direction", "NEUTRAL"),
            "signalStrength": int(_num(live_status.get("confluence_score"))),
            "confluence_score": int(_num(live_status.get("confluence_score"))),
            "confidence": int(_num(live_status.get("confidence"))),
            "status": "waiting_confirmation",
            "reasons": blockers[:8] or ["Aguardando confluencia forte."],
            "technical_reason": (blockers[:1] or ["Aguardando confluencia forte."])[0],
            "explanation": " ".join(blockers[:3] or ["Aguardando confluencia forte."]),
            "timeframe": live_status.get("timeframe"),
            "createdAt": _now(),
            "timestamp": _now(),
            "layers": (live_status.get("layered_signal") or {}).get("ai_score", {}),
            "disclaimer": DISCLAIMER,
        }

    def list_active(self) -> list[dict[str, Any]]:
        return self.repository.list_active()

    def list_history(self, limit=100) -> list[dict[str, Any]]:
        return self.repository.list_history(limit)

    def stats(self) -> dict[str, Any]:
        return self.repository.stats()

    def _status(self, signal: dict[str, Any], status: str, price: float) -> None:
        if signal.get("status") == status:
            return
        signal["status"] = status
        self._event(signal, status, price)

    def _finish(self, signal: dict[str, Any], status: str, price: float, key: str | None) -> None:
        self._status(signal, status, price)
        if key:
            self.repository.finalize(key, signal)

    def _event(self, signal: dict[str, Any], status: str, price: float) -> None:
        signal.setdefault("history", []).append({"status": status, "price": round(price, 8), "at": _now()})

    def _partial_result(self, signal: dict[str, Any], price: float) -> str:
        entry = _num(signal.get("entryPrice"))
        if not entry:
            return "0.00%"
        value = (entry - price) / entry * 100 if signal.get("direction") == "SELL" else (price - entry) / entry * 100
        return f"{value:.2f}%"


class LiveSignalManager(SignalEngine):
    pass
