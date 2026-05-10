"""
Score operacional final da IA em escala 0-10.
"""


class FinalOperationalScore:
    def __init__(self, technical, ai_signal, levels, smc, volume, mtf_analysis, mtf_confluence, wyckoff=None, elliott_wave=None, tape_reading=None):
        self.technical = technical
        self.ai_signal = ai_signal
        self.levels = levels
        self.smc = smc
        self.volume = volume
        self.mtf_analysis = mtf_analysis
        self.mtf_confluence = mtf_confluence
        self.wyckoff = wyckoff or {}
        self.elliott_wave = elliott_wave or {}
        self.tape_reading = tape_reading or {}

    def calculate(self):
        components = {}
        confirmations = []
        invalidations = []

        components["trend"] = self._trend(confirmations, invalidations)
        components["rsi"] = self._rsi(confirmations, invalidations)
        components["macd"] = self._macd(confirmations, invalidations)
        components["ema"] = self._ema(confirmations, invalidations)
        components["bollinger"] = self._bollinger(confirmations, invalidations)
        components["vwap"] = self._vwap(confirmations, invalidations)
        components["atr"] = self._atr(confirmations, invalidations)
        components["support_resistance"] = self._support_resistance(confirmations, invalidations)
        components["volume"] = self._volume(confirmations, invalidations)
        components["tape_reading"] = self._tape_reading(confirmations, invalidations)
        components["smart_money"] = self._smart_money(confirmations, invalidations)
        components["wyckoff"] = self._wyckoff(confirmations, invalidations)
        components["elliott_wave"] = self._elliott_wave(confirmations, invalidations)
        components["multi_timeframe"] = self._multi_timeframe(confirmations, invalidations)
        components["confirmation_candle"] = self._confirmation_candle(confirmations, invalidations)
        components["risk_reward"] = self._risk_reward(confirmations, invalidations)

        weighted = self._weighted_score(components)
        if invalidations:
            weighted -= min(len(invalidations) * 0.18, 0.9)
        score = round(max(0, min(10, weighted)), 1)
        classification = self._classification(score)
        signal = self._final_signal(score)
        confidence = int(max(10, min(95, 40 + score * 5 + len(confirmations) * 2 - len(invalidations) * 2)))

        return {
            "score": score,
            "confidence": confidence,
            "signal": signal,
            "classification": classification,
            "entry_aggressive": score >= 9 and signal in ["BUY", "SELL"],
            "entry_conservative": 7 <= score < 9 and signal in ["BUY", "SELL"],
            "stop_loss": self.levels.get("stop_loss"),
            "take_profit_1": self.levels.get("alvo_1"),
            "take_profit_2": self.levels.get("alvo_2"),
            "take_profit_3": self._take_profit_3(signal),
            "technical_reasons": confirmations[:10],
            "invalidation_reasons": invalidations[:10],
            "components": components,
            "explanation": self._explanation(score, signal, classification, confirmations, invalidations),
        }

    def _weighted_score(self, components):
        weights = {
            "trend": 0.70,
            "rsi": 0.32,
            "macd": 0.38,
            "ema": 0.48,
            "bollinger": 0.26,
            "vwap": 0.32,
            "atr": 0.22,
            "support_resistance": 0.32,
            "volume": 0.65,
            "tape_reading": 0.55,
            "smart_money": 1.20,
            "wyckoff": 0.60,
            "elliott_wave": 0.30,
            "multi_timeframe": 0.90,
            "confirmation_candle": 0.32,
            "risk_reward": 0.30,
        }
        total_weight = sum(weights.values())
        raw = sum(components[key] * weights[key] for key in weights) / total_weight
        return raw * 10

    def _trend(self, confirmations, invalidations):
        direction = self.technical.get("trend", {}).get("direction", "SIDEWAYS")
        if direction == "STRONG_BULLISH":
            confirmations.append("Tendencia forte de alta por alinhamento estrutural.")
            return 1.0
        if direction == "STRONG_BEARISH":
            confirmations.append("Tendencia forte de baixa por alinhamento estrutural.")
            return 1.0
        if direction in ["BULLISH", "BEARISH"]:
            confirmations.append(f"Tendencia {direction.lower()} ativa.")
            return 0.72
        invalidations.append("Tendencia lateral ou sem alinhamento claro.")
        return 0.35

    def _rsi(self, confirmations, invalidations):
        rsi = self.technical.get("details", {}).get("rsi", 50)
        if 42 <= rsi <= 68:
            confirmations.append(f"RSI em zona operacional saudavel: {rsi}.")
            return 0.82
        if rsi > 76 or rsi < 24:
            invalidations.append(f"RSI extremo: {rsi}.")
            return 0.25
        return 0.55

    def _macd(self, confirmations, invalidations):
        macd = self.technical.get("details", {}).get("macd", {})
        histogram = macd.get("histogram", 0)
        if abs(histogram) > 0:
            confirmations.append("MACD confirma momentum direcional.")
            return 0.72
        invalidations.append("MACD sem momentum relevante.")
        return 0.42

    def _ema(self, confirmations, invalidations):
        stack = self.technical.get("trend", {}).get("ema_stack", {})
        aligned = sum(1 for value in stack.values() if value)
        if aligned >= 2:
            confirmations.append("EMAs com alinhamento favoravel.")
            return 0.82
        invalidations.append("EMAs sem alinhamento suficiente.")
        return 0.38

    def _bollinger(self, confirmations, invalidations):
        position = self.technical.get("details", {}).get("bollinger_bands", {}).get("position", 0.5)
        if 0.15 <= position <= 0.9:
            confirmations.append("Preco dentro de faixa aceitavel das Bandas de Bollinger.")
            return 0.72
        invalidations.append("Preco esticado nas Bandas de Bollinger.")
        return 0.32

    def _vwap(self, confirmations, invalidations):
        details = self.technical.get("details", {})
        price = self.technical.get("entry_price", 0)
        vwap = details.get("vwap", price)
        signal = self.technical.get("signal")
        if (signal == "BUY" and price >= vwap) or (signal == "SELL" and price <= vwap):
            confirmations.append("VWAP confirma o lado do sinal.")
            return 0.82
        invalidations.append("VWAP nao confirma o lado do sinal.")
        return 0.38

    def _atr(self, confirmations, invalidations):
        atr_pct = self.technical.get("details", {}).get("atr", 0) / max(self.technical.get("entry_price", 1), 0.00000001) * 100
        if 0.15 <= atr_pct <= 4.5:
            confirmations.append(f"ATR operacional: {atr_pct:.2f}% do preco.")
            return 0.72
        invalidations.append(f"ATR fora da zona operacional: {atr_pct:.2f}%.")
        return 0.35

    def _support_resistance(self, confirmations, invalidations):
        sr = self.technical.get("details", {}).get("support_resistance", {})
        if sr.get("nearest_support") or sr.get("nearest_resistance"):
            confirmations.append("Suporte/resistencia mapeados para gestao da entrada.")
            return 0.7
        invalidations.append("Sem suporte/resistencia proximo confiavel.")
        return 0.4

    def _volume(self, confirmations, invalidations):
        signal = self.volume.get("signal", "NEUTRAL_VOLUME")
        if signal == "BULLISH_VOLUME" or signal == "BEARISH_VOLUME":
            confirmations.extend(self.volume.get("reasons", [])[:2])
            return 0.88
        if self.volume.get("abnormal_volume"):
            confirmations.append("Volume anormal presente, mas sem direcao limpa.")
            return 0.62
        invalidations.append("Volume nao confirma a entrada.")
        return 0.42

    def _tape_reading(self, confirmations, invalidations):
        confirmations.extend(self.tape_reading.get("confirmations", [])[:2])
        invalidations.extend(self.tape_reading.get("invalidations", [])[:2])
        flow_score = self.tape_reading.get("flow_score")
        if flow_score is not None:
            return max(0, min(100, float(flow_score))) / 100
        bias = self.tape_reading.get("order_flow_bias")
        if bias in ["BUY_FLOW", "SELL_FLOW"]:
            return 0.78
        return 0.48

    def _smart_money(self, confirmations, invalidations):
        if self.smc.get("invalidated"):
            invalidations.extend(self.smc.get("reasons", [])[:3] or ["Smart Money invalidou o sinal."])
            return 0.15
        if self.smc.get("confirmed"):
            confirmations.extend(self.smc.get("reasons", [])[:3] or ["Smart Money confirmou o sinal."])
            return 0.95
        if self.smc.get("smc_score") is not None:
            score = max(0, min(100, float(self.smc.get("smc_score", 50)))) / 100
            confirmations.extend(self.smc.get("confirmations", [])[:2])
            invalidations.extend(self.smc.get("invalidations", [])[:2])
            return score
        if self.smc.get("has_bos") or self.smc.get("has_choch") or self.smc.get("nearest_order_block"):
            confirmations.append("Smart Money tem estrutura relevante proxima.")
            return 0.68
        return 0.45

    def _wyckoff(self, confirmations, invalidations):
        confirmations.extend(self.wyckoff.get("confirmations", [])[:2])
        invalidations.extend(self.wyckoff.get("invalidations", [])[:2])
        phase = self.wyckoff.get("wyckoff_phase") or self.wyckoff.get("phase", "indefinida")
        if self.wyckoff.get("spring") or phase == "acumulacao":
            return 0.78
        if self.wyckoff.get("upthrust") or phase == "distribuicao":
            return 0.38
        if self.wyckoff.get("test"):
            return 0.64
        if self.wyckoff.get("selling_climax") or self.wyckoff.get("buying_climax"):
            return 0.48
        if self.wyckoff.get("institutional_manipulation"):
            return 0.56
        return 0.52

    def _elliott_wave(self, confirmations, invalidations):
        confirmations.extend(self.elliott_wave.get("confirmations", [])[:2])
        invalidations.extend(self.elliott_wave.get("invalidations", [])[:2])
        confidence = self.elliott_wave.get("confidence")
        if confidence is not None:
            base = max(0, min(100, float(confidence))) / 100
        else:
            base = 0.42
        if self.elliott_wave.get("reversal_risk") == "alto":
            return max(0.15, base - 0.25)
        if self.elliott_wave.get("impulse_structure", {}).get("detected"):
            return min(1.0, base + 0.12)
        return base

    def _multi_timeframe(self, confirmations, invalidations):
        confluence = self.mtf_confluence or {}
        confirmed = confluence.get("confirmed_timeframes", 0)
        required = confluence.get("required_confirmations", 3)
        if confluence.get("strong_signal_allowed"):
            confirmations.append(f"Multi-timeframe confirmou {confirmed}/{required}+ timeframes.")
            return 1.0
        invalidations.append(f"Multi-timeframe insuficiente: {confirmed}/{required} confirmacoes.")
        return 0.28

    def _confirmation_candle(self, confirmations, invalidations):
        candle = self.technical.get("details", {}).get("candle_strength", {})
        if candle.get("strong"):
            confirmations.append(f"Candle de confirmacao {candle.get('direction')} com forca.")
            return 0.82
        invalidations.append("Sem candle de confirmacao forte.")
        return 0.38

    def _risk_reward(self, confirmations, invalidations):
        rr = self.levels.get("risco_retorno", 0)
        if rr >= 1.5:
            confirmations.append(f"Risco/retorno favoravel: 1:{rr:.2f}.")
            return 0.92
        if rr >= 1:
            confirmations.append(f"Risco/retorno aceitavel: 1:{rr:.2f}.")
            return 0.65
        invalidations.append(f"Risco/retorno ruim: 1:{rr:.2f}.")
        return 0.2

    def _classification(self, score):
        if score <= 3:
            return "Nao operar"
        if score <= 6:
            return "Aguardar confirmacao"
        if score <= 8:
            return "Entrada moderada"
        return "Entrada forte"

    def _final_signal(self, score):
        if score <= 3:
            return "NEUTRAL"
        direction = self.mtf_confluence.get("dominant_direction", "NEUTRAL") if self.mtf_confluence else "NEUTRAL"
        if direction == "BULLISH":
            return "BUY"
        if direction == "BEARISH":
            return "SELL"
        return self.technical.get("signal", "NEUTRAL")

    def _take_profit_3(self, signal):
        entry = self.levels.get("entrada", 0)
        stop = self.levels.get("stop_loss", entry)
        risk = abs(entry - stop)
        if signal == "SELL":
            return entry - risk * 3
        return entry + risk * 3

    def _explanation(self, score, signal, classification, confirmations, invalidations):
        reason = confirmations[0] if confirmations else "Sem confluencia dominante."
        invalidation = invalidations[0] if invalidations else "Sem invalidacao critica."
        return f"{classification} ({signal}) com score {score}/10. Motivo tecnico: {reason} Principal invalidacao: {invalidation}"


def calculate_final_score(technical, ai_signal, levels, smc, volume, mtf_analysis, mtf_confluence, wyckoff=None, elliott_wave=None, tape_reading=None):
    return FinalOperationalScore(
        technical=technical,
        ai_signal=ai_signal,
        levels=levels,
        smc=smc,
        volume=volume,
        mtf_analysis=mtf_analysis,
        mtf_confluence=mtf_confluence,
        wyckoff=wyckoff,
        elliott_wave=elliott_wave,
        tape_reading=tape_reading,
    ).calculate()
