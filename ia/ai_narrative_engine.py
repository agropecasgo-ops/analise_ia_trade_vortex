"""
Feed narrativo da IA para a Live Trading e narrativa institucional contextual.
"""

from __future__ import annotations

from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Any


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class AINarrativeEngine:
    def __init__(self, max_items: int = 80) -> None:
        self.max_items = max_items
        self._feeds: dict[str, deque[dict[str, Any]]] = defaultdict(lambda: deque(maxlen=max_items))
        self._seen: dict[str, set[str]] = defaultdict(set)

    def update(self, symbol: str, timeframe: str, context: dict[str, Any], status: dict[str, Any]) -> list[dict[str, Any]]:
        key = f"{symbol}:{timeframe}"
        feed = self._feeds[key]
        if not feed:
            self._append(key, "SYSTEM", f"Mesa IA conectada em {symbol} {timeframe}", "info")

        for event in context.get("events", [])[-8:]:
            self._append(key, event.get("kind", "EVENT"), event.get("text", ""), event.get("severity", "info"), event.get("level"))

        for message in (status.get("messages") or [])[:4]:
            self._append(key, "IA", message, self._severity_from_status(status))

        if context.get("invalidation"):
            self._append(key, "INVALIDACAO", f"Cenario invalidado se perder {context['invalidation']}", "warning", context.get("invalidation"))

        return list(feed)[-30:]

    def build_institutional_narrative(
        self,
        *,
        fluxo: dict[str, Any] | None = None,
        liquidez: dict[str, Any] | None = None,
        estrutura: dict[str, Any] | None = None,
        multi_timeframe: dict[str, Any] | None = None,
        orderflow: dict[str, Any] | None = None,
        contexto_macro: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        fluxo = fluxo or {}
        liquidez = liquidez or {}
        estrutura = estrutura or {}
        multi_timeframe = multi_timeframe or {}
        orderflow = orderflow or {}
        contexto_macro = contexto_macro or {}

        institutional_bias = self._institutional_bias(fluxo, estrutura, multi_timeframe, orderflow, contexto_macro)
        risk_context = self._risk_context(liquidez, estrutura, multi_timeframe, orderflow, contexto_macro)
        execution_quality = self._execution_quality(fluxo, estrutura, multi_timeframe, orderflow, risk_context)
        wait_or_trade = self._wait_or_trade(institutional_bias, execution_quality, risk_context)
        invalidation_context = self._invalidation_context(liquidez, estrutura, multi_timeframe, orderflow, contexto_macro)
        narrative = self._institutional_text(
            institutional_bias,
            risk_context,
            execution_quality,
            wait_or_trade,
            invalidation_context,
            fluxo,
            liquidez,
            estrutura,
            multi_timeframe,
            orderflow,
            contexto_macro,
        )

        return {
            "narrative": narrative,
            "institutional_bias": institutional_bias,
            "risk_context": risk_context,
            "execution_quality": execution_quality,
            "wait_or_trade": wait_or_trade,
            "invalidation_context": invalidation_context,
            "can_generate_signal": False,
            "created_at": _now_iso(),
        }

    def _append(self, key: str, kind: str, text: str, severity: str = "info", level: float | None = None) -> None:
        text = str(text or "").strip()
        if not text:
            return
        signature = f"{kind}:{text}:{round(float(level or 0), 4)}"
        if signature in self._seen[key]:
            return
        self._seen[key].add(signature)
        if len(self._seen[key]) > self.max_items * 2:
            self._seen[key] = set(list(self._seen[key])[-self.max_items:])
        self._feeds[key].append({
            "timestamp": _now_iso(),
            "kind": kind,
            "text": text,
            "severity": severity,
            "level": level,
        })

    def _severity_from_status(self, status: dict[str, Any]) -> str:
        state = status.get("state")
        if state in ["BUY_CONFIRMED", "SELL_CONFIRMED", "AGGRESSIVE_ENTRY", "CONSERVATIVE_ENTRY"]:
            return "positive"
        if state in ["INVALIDATED", "HIGH_RISK"]:
            return "negative"
        if state in ["WAITING_CONFIRMATION", "WAIT_NEXT_CANDLE", "WEAK_VOLUME"]:
            return "warning"
        return "info"

    def _institutional_bias(
        self,
        fluxo: dict[str, Any],
        estrutura: dict[str, Any],
        multi_timeframe: dict[str, Any],
        orderflow: dict[str, Any],
        contexto_macro: dict[str, Any],
    ) -> str:
        votes = [
            self._direction_from_value(fluxo.get("pressure") or fluxo.get("order_flow_bias") or fluxo.get("flow_direction")),
            self._direction_from_value(estrutura.get("direction")),
            self._direction_from_value(multi_timeframe.get("main_direction") or (multi_timeframe.get("macro_trend") or {}).get("direction")),
            self._direction_from_value(orderflow.get("flow_direction")),
            self._direction_from_value(contexto_macro.get("direction") or contexto_macro.get("htf_direction")),
        ]
        buy = votes.count("BUY")
        sell = votes.count("SELL")
        if buy >= 3 and buy > sell:
            return "BUY_CONTEXT"
        if sell >= 3 and sell > buy:
            return "SELL_CONTEXT"
        if buy > sell:
            return "BUY_LEANING"
        if sell > buy:
            return "SELL_LEANING"
        return "NEUTRAL_CONTEXT"

    def _risk_context(
        self,
        liquidez: dict[str, Any],
        estrutura: dict[str, Any],
        multi_timeframe: dict[str, Any],
        orderflow: dict[str, Any],
        contexto_macro: dict[str, Any],
    ) -> dict[str, Any]:
        risks = []
        if (liquidez.get("sweep") or {}).get("detected") or liquidez.get("liquidity_sweep", {}).get("detected"):
            risks.append("liquidity_sweep")
        if estrutura.get("valid") is False or estrutura.get("blockers"):
            risks.append("weak_structure")
        if multi_timeframe.get("conflicting_timeframes"):
            risks.append("timeframe_conflict")
        if (orderflow.get("absorption_signal") or {}).get("detected"):
            risks.append("absorption")
        if (orderflow.get("exhaustion_signal") or {}).get("detected"):
            risks.append("exhaustion")
        if contexto_macro.get("blocked") or contexto_macro.get("lateral"):
            risks.append("macro_blocked")
        level = "HIGH" if len(risks) >= 3 else "MEDIUM" if risks else "LOW"
        return {"level": level, "factors": risks, "risk_active": bool(risks)}

    def _execution_quality(
        self,
        fluxo: dict[str, Any],
        estrutura: dict[str, Any],
        multi_timeframe: dict[str, Any],
        orderflow: dict[str, Any],
        risk_context: dict[str, Any],
    ) -> dict[str, Any]:
        alignment = self._num(multi_timeframe.get("alignment_score"))
        flow_strength = self._num(orderflow.get("flow_strength"), self._num(fluxo.get("intensity")))
        structure_bonus = 18 if estrutura.get("valid") else 0
        risk_penalty = {"LOW": 0, "MEDIUM": 16, "HIGH": 34}.get(risk_context.get("level"), 12)
        score = max(0, min(100, alignment * 0.45 + flow_strength * 0.35 + structure_bonus - risk_penalty))
        quality = "HIGH" if score >= 72 else "MEDIUM" if score >= 45 else "LOW"
        return {"quality": quality, "score": round(score, 2), "context_only": True}

    def _wait_or_trade(self, institutional_bias: str, execution_quality: dict[str, Any], risk_context: dict[str, Any]) -> str:
        if risk_context.get("level") == "HIGH":
            return "WAIT_RISK"
        if institutional_bias == "NEUTRAL_CONTEXT":
            return "WAIT_DIRECTION"
        if execution_quality.get("quality") == "HIGH":
            return "CONTEXT_FAVORABLE"
        if execution_quality.get("quality") == "MEDIUM":
            return "WAIT_CONFIRMATION"
        return "WAIT"

    def _invalidation_context(
        self,
        liquidez: dict[str, Any],
        estrutura: dict[str, Any],
        multi_timeframe: dict[str, Any],
        orderflow: dict[str, Any],
        contexto_macro: dict[str, Any],
    ) -> dict[str, Any]:
        items = []
        nearest = liquidez.get("nearest") or liquidez.get("nearest_liquidity") or liquidez.get("internal")
        if nearest:
            items.append({"type": "liquidity_reference", "value": nearest})
        if estrutura.get("bos"):
            items.append({"type": "structure_bos", "value": estrutura.get("bos")})
        if estrutura.get("choch"):
            items.append({"type": "structure_choch", "value": estrutura.get("choch")})
        if multi_timeframe.get("conflicting_timeframes"):
            items.append({"type": "timeframe_conflict", "value": multi_timeframe.get("conflicting_timeframes")})
        if (orderflow.get("exhaustion_signal") or {}).get("detected"):
            items.append({"type": "orderflow_exhaustion", "value": orderflow.get("exhaustion_signal")})
        if contexto_macro.get("blockers"):
            items.append({"type": "macro_blocker", "value": contexto_macro.get("blockers")})
        return {"items": items, "summary": self._invalidation_summary(items)}

    def _institutional_text(
        self,
        institutional_bias: str,
        risk_context: dict[str, Any],
        execution_quality: dict[str, Any],
        wait_or_trade: str,
        invalidation_context: dict[str, Any],
        fluxo: dict[str, Any],
        liquidez: dict[str, Any],
        estrutura: dict[str, Any],
        multi_timeframe: dict[str, Any],
        orderflow: dict[str, Any],
        contexto_macro: dict[str, Any],
    ) -> str:
        mtf_summary = multi_timeframe.get("summary") or "multi-timeframe sem leitura consolidada"
        flow_text = orderflow.get("flow_direction") or fluxo.get("pressure") or fluxo.get("order_flow_bias") or "fluxo neutro"
        structure_text = estrutura.get("direction") or "estrutura neutra"
        liquidity_text = "liquidez monitorada" if liquidez else "liquidez sem destaque"
        macro_text = contexto_macro.get("direction") or contexto_macro.get("htf_direction") or "macro neutro"
        return (
            f"Leitura institucional {institutional_bias}: macro {macro_text}, estrutura {structure_text}, "
            f"fluxo {flow_text} e {liquidity_text}. {mtf_summary}. "
            f"Qualidade de execucao {execution_quality['quality']} ({execution_quality['score']:.0f}/100), "
            f"risco {risk_context['level']}. Conduta contextual: {wait_or_trade}. "
            f"Invalidacao: {invalidation_context['summary']}."
        )

    def _direction_from_value(self, value: Any) -> str:
        text = str(value or "").upper()
        if text in {"BUY", "BULLISH", "BUYER", "COMPRADOR", "COMPRADORA", "BUY_FLOW", "BUY_PRESSURE", "BUY_CONTEXT", "BUY_LEANING"}:
            return "BUY"
        if text in {"SELL", "BEARISH", "SELLER", "VENDEDOR", "VENDEDORA", "SELL_FLOW", "SELL_PRESSURE", "SELL_CONTEXT", "SELL_LEANING"}:
            return "SELL"
        return "NEUTRAL"

    def _invalidation_summary(self, items: list[dict[str, Any]]) -> str:
        if not items:
            return "sem invalidacao objetiva detectada; manter observacao do contexto."
        labels = {
            "liquidity_reference": "zona de liquidez",
            "structure_bos": "BOS/estrutura",
            "structure_choch": "CHOCH",
            "timeframe_conflict": "conflito entre timeframes",
            "orderflow_exhaustion": "exaustao no orderflow",
            "macro_blocker": "bloqueio macro",
        }
        names = [labels.get(item["type"], item["type"]) for item in items[:3]]
        return ", ".join(names)

    def _num(self, value: Any, default: float = 0.0) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return default
        return number if number == number else default


def build_institutional_ai_narrative(
    *,
    fluxo: dict[str, Any] | None = None,
    liquidez: dict[str, Any] | None = None,
    estrutura: dict[str, Any] | None = None,
    multi_timeframe: dict[str, Any] | None = None,
    orderflow: dict[str, Any] | None = None,
    contexto_macro: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return AINarrativeEngine(max_items=1).build_institutional_narrative(
        fluxo=fluxo,
        liquidez=liquidez,
        estrutura=estrutura,
        multi_timeframe=multi_timeframe,
        orderflow=orderflow,
        contexto_macro=contexto_macro,
    )
