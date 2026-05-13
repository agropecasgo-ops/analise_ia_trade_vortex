"""
Human-readable institutional narration.

The narrator explains context and risk without promising outcomes. It consumes
the unified payload plus strict institutional mode decision.
"""

from __future__ import annotations

from typing import Any


def _fmt(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "--"
    if number == 0 or number != number:
        return "--"
    return f"{number:.2f}" if abs(number) >= 100 else f"{number:.6f}".rstrip("0").rstrip(".")


class InstitutionalNarrator:
    def __init__(self, institutional_payload: dict[str, Any], mode_payload: dict[str, Any] | None = None) -> None:
        self.payload = institutional_payload or {}
        self.mode = mode_payload or {}

    def narrate(self) -> dict[str, Any]:
        direction = self.payload.get("direction", "NEUTRAL")
        plan = self.payload.get("tradePlan") or {}
        risk = self.payload.get("risk") or {}
        status = self.mode.get("status") or self.payload.get("status")
        sections = {
            "probableDirection": self._direction_text(direction, status),
            "analysisReason": self._analysis_reason(),
            "relevantLiquidity": self._liquidity_text(),
            "institutionalBehavior": self._behavior_text(),
            "operationRisk": self._risk_text(risk, plan),
            "entryCondition": plan.get("entryCondition") or "Aguardar confirmacao objetiva de timing.",
            "cancelCondition": plan.get("cancelCondition") or "Cancelar se estrutura, liquidez ou risco forem invalidados.",
        }
        return {
            "status": status,
            "voice": "institutional_narrator",
            "summary": self._summary(sections),
            "sections": sections,
            "messages": list(sections.values()),
            "disclaimer": "Narrativa educativa. Nao constitui recomendacao financeira e nao promete acerto.",
        }

    def _direction_text(self, direction: str, status: str) -> str:
        labels = {"BUY": "compra", "SELL": "venda", "NEUTRAL": "neutra"}
        if status == "OPERAR":
            return f"Direcao provavel de {labels.get(direction, 'neutra')} em Modo Institucional."
        if status == "MERCADO_PERIGOSO":
            return "Direcao operacional bloqueada; o mercado exige cautela."
        return f"Direcao provavel ainda {labels.get(direction, 'neutra')}; IA aguarda confirmacao."

    def _analysis_reason(self) -> str:
        score = self.payload.get("score", 0)
        confidence = self.payload.get("confidence", 0)
        mode_reason = self.mode.get("reason")
        if mode_reason:
            return f"Score {score}/100, confianca {confidence}%. {mode_reason}"
        return self.payload.get("aiExplanation") or f"Score {score}/100 com confluencia ainda em avaliacao."

    def _liquidity_text(self) -> str:
        liquidity = self.payload.get("liquidity") or {}
        sweep = liquidity.get("sweep") or {}
        nearest = liquidity.get("nearest") or liquidity.get("internal") or liquidity.get("external") or {}
        if sweep.get("detected"):
            return f"Liquidez varrida em {sweep.get('side') or 'zona institucional'} perto de {_fmt(sweep.get('level'))}."
        if isinstance(nearest, dict) and nearest:
            price = nearest.get("price", nearest.get("mid", nearest.get("level")))
            return f"Liquidez relevante em {nearest.get('side') or nearest.get('type') or 'zona'} perto de {_fmt(price)}."
        return "Sem liquidez relevante suficiente para liberar uma operacao institucional."

    def _behavior_text(self) -> str:
        behavior = self.payload.get("institutionalBehavior") or {}
        smart_money = behavior.get("smartMoneyBias", "neutral")
        false_breakout = behavior.get("falseBreakout") or {}
        inducement = behavior.get("inducement") or {}
        if false_breakout.get("detected"):
            return "Comportamento institucional sugere falso rompimento; a IA reduz permissao operacional."
        if inducement.get("detected"):
            return "Ha indicio de inducement/liquidez sendo usada para atrair entradas atrasadas."
        return f"Comportamento institucional predominante: {smart_money}."

    def _risk_text(self, risk: dict[str, Any], plan: dict[str, Any]) -> str:
        rr = plan.get("riskReward")
        if not risk.get("allowed"):
            reasons = risk.get("rejections") or ["risco nao aprovado"]
            return f"Risco bloqueado: {reasons[0]}."
        return f"Risco aprovado com R/R estimado em 1:{float(rr or 0):.2f}, entrada {_fmt(plan.get('entry'))}, stop {_fmt(plan.get('stopLoss'))}."

    def _summary(self, sections: dict[str, str]) -> str:
        return " ".join([
            sections["probableDirection"],
            sections["analysisReason"],
            sections["relevantLiquidity"],
            sections["operationRisk"],
        ])


def build_institutional_narrative(
    institutional_payload: dict[str, Any],
    mode_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return InstitutionalNarrator(institutional_payload, mode_payload).narrate()
