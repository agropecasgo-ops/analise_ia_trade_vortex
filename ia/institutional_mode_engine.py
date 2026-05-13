"""
Strict institutional mode for the institutional analysis desk.

This layer consumes the unified institutional payload and applies more selective
requirements. It does not generate signals by itself and does not affect live
trading or realtime signal state unless explicitly consumed by a caller.
"""

from __future__ import annotations

from typing import Any


def _num(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if number == number else default


class InstitutionalModeEngine:
    MIN_SCORE = 88
    MIN_CONFIDENCE = 82
    MIN_RR = 1.5

    def __init__(self, institutional_payload: dict[str, Any]) -> None:
        self.payload = institutional_payload or {}

    def analyze(self) -> dict[str, Any]:
        blockers = self._blockers()
        score = _num(self.payload.get("score"))
        confidence = _num(self.payload.get("confidence"))
        direction = self.payload.get("direction", "NEUTRAL")
        ready = direction in {"BUY", "SELL"} and not blockers
        status = "OPERAR" if ready else "MERCADO_PERIGOSO" if self._dangerous(blockers) else "AGUARDAR"
        return {
            "enabled": True,
            "mode": "INSTITUTIONAL_STRICT",
            "status": status,
            "direction": direction if ready else "NEUTRAL",
            "canOperate": ready,
            "score": round(score, 2),
            "confidence": round(confidence, 2),
            "minimums": {
                "score": self.MIN_SCORE,
                "confidence": self.MIN_CONFIDENCE,
                "riskReward": self.MIN_RR,
            },
            "blockers": blockers,
            "priorities": {
                "liquidity": self._has_liquidity(),
                "structure": self._has_structure(),
                "timing": self._has_timing(),
                "risk": self._risk_valid(),
            },
            "reason": self._reason(status, blockers),
        }

    def _blockers(self) -> list[str]:
        blockers = []
        macro = self.payload.get("macroContext") or {}
        volatility = macro.get("volatility") or {}
        news = self.payload.get("news") or {}
        risk = self.payload.get("risk") or {}
        plan = self.payload.get("tradePlan") or {}
        status = self.payload.get("status")

        if self.payload.get("direction") not in {"BUY", "SELL"}:
            blockers.append("Sem direcao institucional executavel.")
        if _num(self.payload.get("score")) < self.MIN_SCORE:
            blockers.append(f"Score institucional abaixo de {self.MIN_SCORE}.")
        if _num(self.payload.get("confidence")) < self.MIN_CONFIDENCE:
            blockers.append(f"Confianca institucional abaixo de {self.MIN_CONFIDENCE}%.")
        if macro.get("lateral"):
            blockers.append("Mercado lateral bloqueado no Modo Institucional.")
        if volatility.get("state") == "LOW":
            blockers.append("Volatilidade baixa bloqueada no Modo Institucional.")
        if news.get("impact") == "HIGH" and news.get("blocking", True):
            blockers.append("Noticia perigosa bloqueia operacao institucional.")
        if status in {"DANGEROUS_MARKET", "NO_TRADE"}:
            blockers.append("Payload institucional classificado como mercado perigoso ou sem trade.")
        if not self._has_liquidity():
            blockers.append("Liquidez relevante nao validada.")
        if not self._has_structure():
            blockers.append("Estrutura institucional nao validada.")
        if not self._has_timing():
            blockers.append("Timing operacional nao confirmado.")
        if not self._risk_valid():
            blockers.extend(risk.get("rejections") or ["Risco nao aprovado."])
        if _num(plan.get("riskReward")) < self.MIN_RR:
            blockers.append(f"Risco/retorno abaixo do minimo institucional 1:{self.MIN_RR:.2f}.")
        return list(dict.fromkeys([item for item in blockers if item]))

    def _has_liquidity(self) -> bool:
        liquidity = self.payload.get("liquidity") or {}
        sweep = liquidity.get("sweep") or {}
        return bool(sweep.get("detected") or liquidity.get("nearest") or liquidity.get("internal") or liquidity.get("external"))

    def _has_structure(self) -> bool:
        structure = self.payload.get("marketStructure") or {}
        return bool(structure.get("valid") and structure.get("direction") in {"BUY", "SELL"})

    def _has_timing(self) -> bool:
        timing = self.payload.get("timing") or {}
        return bool(timing.get("confirmed"))

    def _risk_valid(self) -> bool:
        risk = self.payload.get("risk") or {}
        return bool(risk.get("allowed"))

    def _dangerous(self, blockers: list[str]) -> bool:
        text = " ".join(blockers).lower()
        return any(term in text for term in ["perigosa", "perigoso", "lateral", "volatilidade baixa", "noticia", "risco nao aprovado"])

    def _reason(self, status: str, blockers: list[str]) -> str:
        if status == "OPERAR":
            return "Modo Institucional liberou somente porque score, liquidez, estrutura, timing e risco estao alinhados."
        if blockers:
            return blockers[0]
        return "Modo Institucional aguarda confluencia superior."


def build_institutional_mode(institutional_payload: dict[str, Any]) -> dict[str, Any]:
    return InstitutionalModeEngine(institutional_payload).analyze()
