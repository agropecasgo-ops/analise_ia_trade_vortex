"""
Motor central da IA de confluencia operacional do FinanceAI.
"""


DISCLAIMER = (
    "Esta analise e educativa e nao constitui recomendacao financeira. "
    "O sistema nao garante lucro. Toda operacao envolve risco."
)


class ConfluenceEngine:
    def __init__(self, technical, smc, volume, wyckoff, mtf, levels, final_score=None):
        self.technical = technical or {}
        self.smc = smc or {}
        self.volume = volume or {}
        self.wyckoff = wyckoff or {}
        self.mtf = mtf or {}
        self.levels = levels or {}
        self.final_score = final_score or {}

    def analyze(self):
        components = {
            "trend": self._trend(),
            "volume": self._volume(),
            "momentum": self._momentum(),
            "smart_money": self._smart_money(),
            "price_action": self._price_action(),
            "indicators": self._indicators(),
            "multi_timeframe": self._multi_timeframe(),
            "risk_reward": self._risk_reward(),
            "wyckoff": self._wyckoff(),
        }
        weights = {
            "trend": 0.13,
            "volume": 0.11,
            "momentum": 0.10,
            "smart_money": 0.17,
            "price_action": 0.12,
            "indicators": 0.13,
            "multi_timeframe": 0.14,
            "risk_reward": 0.07,
            "wyckoff": 0.03,
        }
        score = round(sum(components[key]["score"] * weights[key] for key in weights))
        confirmations = []
        invalidations = []
        for component in components.values():
            confirmations.extend(component.get("confirmations", []))
            invalidations.extend(component.get("invalidations", []))

        signal = self._signal(score)
        direction = self._direction(signal)
        entry = self.levels.get("entrada") or self.technical.get("entry_price")
        stop = self.levels.get("stop_loss")
        tp1 = self.levels.get("alvo_1")
        tp2 = self.levels.get("alvo_2")
        tp3 = self._tp3(direction, entry, stop)
        confidence = self._confidence(score, confirmations, invalidations)

        return {
            "score": int(max(0, min(100, score))),
            "classification": self._classification(score),
            "signal": signal,
            "direction": direction,
            "entry_aggressive": entry if score >= 76 and direction != "NEUTRAL" else None,
            "entry_conservative": self._conservative_entry(direction, entry, stop) if score >= 61 and direction != "NEUTRAL" else None,
            "stop_loss": stop,
            "take_profit_1": tp1,
            "take_profit_2": tp2,
            "take_profit_3": tp3,
            "risk_reward": self.levels.get("risco_retorno"),
            "confidence": confidence,
            "technical_reason": confirmations[0] if confirmations else "Sem confluencia operacional dominante.",
            "confirmations": confirmations[:12],
            "invalidations": invalidations[:12],
            "cancellation_scenario": self._cancellation(direction),
            "components": components,
            "estimated_probability": confidence,
            "disclaimer": DISCLAIMER,
        }

    def _trend(self):
        direction = self.technical.get("trend", {}).get("direction", "SIDEWAYS")
        if direction == "STRONG_BULLISH" or direction == "STRONG_BEARISH":
            return {"score": 88, "confirmations": [f"Tendencia forte: {direction}."], "invalidations": []}
        if direction in ["BULLISH", "BEARISH"]:
            return {"score": 72, "confirmations": [f"Tendencia ativa: {direction}."], "invalidations": []}
        return {"score": 38, "confirmations": [], "invalidations": ["Tendencia lateral ou indefinida."]}

    def _volume(self):
        signal = self.volume.get("signal", "NEUTRAL_VOLUME")
        if signal in ["BULLISH_VOLUME", "BEARISH_VOLUME"]:
            return {"score": 82, "confirmations": self.volume.get("reasons", ["Volume confirma movimento."])[:3], "invalidations": []}
        return {"score": 45, "confirmations": [], "invalidations": ["Volume sem confirmacao institucional."]}

    def _momentum(self):
        details = self.technical.get("details", {})
        macd = details.get("macd", {})
        rsi = details.get("rsi", 50)
        histogram = abs(macd.get("histogram", 0))
        if 42 <= rsi <= 68 and histogram > 0:
            return {"score": 78, "confirmations": ["Momentum saudavel por RSI e MACD."], "invalidations": []}
        if rsi > 76 or rsi < 24:
            return {"score": 35, "confirmations": [], "invalidations": ["Momentum em extremo, risco de reversao."]}
        return {"score": 52, "confirmations": [], "invalidations": ["Momentum ainda misto."]}

    def _smart_money(self):
        if self.smc.get("invalidated"):
            return {"score": 18, "confirmations": [], "invalidations": self.smc.get("reasons", ["SMC invalidou o cenario."])[:4]}
        if self.smc.get("confirmed"):
            return {"score": 90, "confirmations": self.smc.get("reasons", ["SMC confirma o cenario."])[:4], "invalidations": []}
        if self.smc.get("smc_score") is not None:
            score = int(max(0, min(100, self.smc.get("smc_score", 50))))
            return {
                "score": score,
                "confirmations": self.smc.get("confirmations", [])[:4],
                "invalidations": self.smc.get("invalidations", [])[:4],
            }
        if self.smc.get("has_bos") or self.smc.get("has_choch") or self.smc.get("nearest_order_block"):
            return {"score": 65, "confirmations": ["SMC possui zona/estrutura relevante."], "invalidations": []}
        return {"score": 45, "confirmations": [], "invalidations": ["SMC sem gatilho claro."]}

    def _price_action(self):
        details = self.technical.get("details", {})
        breakout = details.get("breakout", {})
        pullback = details.get("pullback", {})
        candle = details.get("candle_strength", {})
        confirmations = []
        if breakout.get("detected"):
            confirmations.append(f"Rompimento {breakout.get('direction')} detectado.")
        if pullback.get("detected"):
            confirmations.append(f"Pullback {pullback.get('direction')} em {pullback.get('reference')}.")
        if candle.get("strong"):
            confirmations.append("Candle de forca confirma price action.")
        return {"score": 78 if confirmations else 42, "confirmations": confirmations, "invalidations": [] if confirmations else ["Price action sem gatilho claro."]}

    def _indicators(self):
        confirmations = self.technical.get("confirmations", [])[:4]
        invalidations = self.technical.get("invalidations", [])[:4]
        base = 70 if len(confirmations) >= len(invalidations) else 45
        return {"score": base, "confirmations": confirmations, "invalidations": invalidations}

    def _multi_timeframe(self):
        confluence = self.mtf.get("confluence", self.mtf)
        if confluence.get("strong_signal_allowed"):
            count = confluence.get("confirmed_timeframes", 0)
            return {"score": 92, "confirmations": [f"Multi-timeframe confirmou {count}/5 tempos."], "invalidations": []}
        return {"score": 36, "confirmations": [], "invalidations": ["Multi-timeframe sem 3 confirmacoes na mesma direcao."]}

    def _risk_reward(self):
        rr = self.levels.get("risco_retorno") or 0
        if rr >= 1.5:
            return {"score": 82, "confirmations": [f"Risco/retorno favoravel: 1:{rr:.2f}."], "invalidations": []}
        if rr >= 1:
            return {"score": 62, "confirmations": [f"Risco/retorno aceitavel: 1:{rr:.2f}."], "invalidations": []}
        return {"score": 25, "confirmations": [], "invalidations": [f"Risco/retorno fraco: 1:{rr:.2f}."]}

    def _wyckoff(self):
        phase = self.wyckoff.get("phase", "indefinida")
        if self.wyckoff.get("invalidations"):
            return {"score": 42, "confirmations": self.wyckoff.get("confirmations", [])[:2], "invalidations": self.wyckoff.get("invalidations", [])[:3]}
        if self.wyckoff.get("spring") or self.wyckoff.get("upthrust"):
            return {"score": 78, "confirmations": [f"Wyckoff: {phase}."], "invalidations": []}
        if self.wyckoff.get("accumulation") or self.wyckoff.get("distribution"):
            return {"score": 62, "confirmations": [f"Wyckoff sugere {phase}."], "invalidations": []}
        return {"score": 50, "confirmations": [], "invalidations": []}

    def _classification(self, score):
        if score <= 40:
            return "Nao operar"
        if score <= 60:
            return "Aguardar confirmacao"
        if score <= 75:
            return "Entrada moderada"
        if score <= 90:
            return "Entrada forte"
        return "Entrada premium"

    def _signal(self, score):
        if score <= 40:
            return "NEUTRO"
        if score <= 60:
            return "AGUARDAR CONFIRMACAO"
        direction = self.mtf.get("confluence", self.mtf).get("dominant_direction", "NEUTRAL")
        if direction == "BULLISH":
            return "COMPRA"
        if direction == "BEARISH":
            return "VENDA"
        return "NEUTRO"

    def _direction(self, signal):
        if signal == "COMPRA":
            return "BUY"
        if signal == "VENDA":
            return "SELL"
        return "NEUTRAL"

    def _confidence(self, score, confirmations, invalidations):
        return int(max(5, min(95, score * 0.72 + len(confirmations) * 2 - len(invalidations) * 2)))

    def _conservative_entry(self, direction, entry, stop):
        if entry is None or stop is None:
            return entry
        distance = abs(entry - stop)
        if direction == "BUY":
            return entry - distance * 0.25
        if direction == "SELL":
            return entry + distance * 0.25
        return entry

    def _tp3(self, direction, entry, stop):
        if entry is None or stop is None:
            return None
        risk = abs(entry - stop)
        return entry - risk * 3 if direction == "SELL" else entry + risk * 3

    def _cancellation(self, direction):
        if direction == "BUY":
            return "Cancelar compra se perder suporte, VWAP ou houver CHOCH bearish com volume vendedor."
        if direction == "SELL":
            return "Cancelar venda se romper resistencia, VWAP ou houver CHOCH bullish com volume comprador."
        return "Sem entrada ativa; aguardar nova confluencia."


def build_confluence_analysis(technical, smc, volume, wyckoff, mtf, levels, final_score=None):
    return ConfluenceEngine(technical, smc, volume, wyckoff, mtf, levels, final_score).analyze()
