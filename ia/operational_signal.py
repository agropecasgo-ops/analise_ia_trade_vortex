"""
Sinais operacionais prontos para o FinanceAI.
"""


DISCLAIMER = "Sinal probabilistico e educativo. Nao ha promessa de lucro ou assertividade fixa."


class OperationalSignalBuilder:
    def __init__(self, confluence_ai, technical, volume, smc, mtf_confluence, levels, operational_state):
        self.ai = confluence_ai or {}
        self.technical = technical or {}
        self.volume = volume or {}
        self.smc = smc or {}
        self.mtf = mtf_confluence or {}
        self.levels = levels or {}
        self.state = operational_state or {}

    def build(self):
        lateral = self._is_lateral()
        rr = float(self.levels.get("risco_retorno") or 0)
        confluence_ok = bool(self.mtf.get("strong_signal_allowed"))
        score = int(max(0, min(100, round(self.ai.get("score", 0)))))
        invalidations = list(self.ai.get("invalidations", []))
        confirmations = list(self.ai.get("confirmations", []))

        if rr < 1:
            invalidations.append(f"Risco/retorno ruim: 1:{rr:.2f}.")

        if lateral:
            signal = "NEUTRO"
            status = "Mercado lateralizado; sem entrada operacional."
        elif rr < 1:
            signal = "NEUTRO"
            status = "Entrada invalidada por risco/retorno ruim."
        elif not confluence_ok:
            signal = "AGUARDAR CONFIRMAÇÃO"
            status = "Pouca confirmacao entre timeframes."
        else:
            signal = self.ai.get("signal", "NEUTRO")
            if signal not in ["COMPRA", "VENDA"]:
                signal = "AGUARDAR CONFIRMAÇÃO" if score >= 41 else "NEUTRO"
            status = self.ai.get("classification", "Aguardar confirmacao")

        if score < 41 and signal not in ["NEUTRO"]:
            signal = "AGUARDAR CONFIRMAÇÃO"
            status = "Score baixo; aguardar confirmacao."

        direction = "BUY" if signal == "COMPRA" else "SELL" if signal == "VENDA" else "NEUTRAL"
        entry = self.levels.get("entrada")
        stop = self.levels.get("stop_loss")

        return {
            "signal": signal,
            "status": status,
            "direction": direction,
            "score": score,
            "confidence": int(max(0, min(95, round(self.ai.get("confidence", 0))))),
            "entry_aggressive": entry if signal in ["COMPRA", "VENDA"] and score >= 76 else None,
            "entry_conservative": self._conservative_entry(direction, entry, stop) if signal in ["COMPRA", "VENDA"] and score >= 61 else None,
            "stop_loss": stop,
            "take_profit_1": self.levels.get("alvo_1"),
            "take_profit_2": self.levels.get("alvo_2"),
            "take_profit_3": self.ai.get("take_profit_3"),
            "risk_reward": rr,
            "technical_reason": self.ai.get("technical_reason") or (confirmations[0] if confirmations else status),
            "confirmations": confirmations[:12],
            "invalidations": invalidations[:12],
            "cancellation_scenario": self.ai.get("cancellation_scenario") or self._cancel_text(direction),
            "confluence_required": 3,
            "confluence_confirmed": self.mtf.get("confirmed_timeframes", 0),
            "estimated_probability": self.ai.get("estimated_probability", self.ai.get("confidence", 0)),
            "disclaimer": DISCLAIMER,
        }

    def _is_lateral(self):
        lateral = self.technical.get("details", {}).get("lateralization", {})
        return bool(lateral.get("detected")) or self.state.get("state") == "neutral"

    def _conservative_entry(self, direction, entry, stop):
        if entry is None or stop is None:
            return entry
        risk = abs(entry - stop)
        if direction == "BUY":
            return entry - risk * 0.25
        if direction == "SELL":
            return entry + risk * 0.25
        return None

    def _cancel_text(self, direction):
        if direction == "BUY":
            return "Cancelar se perder suporte, VWAP ou aparecer CHOCH bearish com volume vendedor."
        if direction == "SELL":
            return "Cancelar se romper resistencia, VWAP ou aparecer CHOCH bullish com volume comprador."
        return "Sem entrada ativa; aguardar nova confluencia."


def build_operational_signal(confluence_ai, technical, volume, smc, mtf_confluence, levels, operational_state):
    return OperationalSignalBuilder(confluence_ai, technical, volume, smc, mtf_confluence, levels, operational_state).build()
