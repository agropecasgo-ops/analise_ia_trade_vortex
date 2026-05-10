"""
Motor Live Trading IA para leitura operacional em tempo quase real.
"""

from datetime import datetime, timezone

from .analysis import RiskManagement
from .elliott_wave import read_elliott_wave
from .smart_money import analyze_smart_money
from .tape_reading import read_tape
from .technical_reader import read_technical
from .volume_reader import read_volume
from .wyckoff_reader import read_wyckoff_advanced


DISCLAIMER = "Analise educativa. Nao e recomendacao financeira. Toda operacao envolve risco."


class LiveTradingIA:
    STATES = {
        "ANALYZING": "ANALISANDO",
        "WAITING_CONFIRMATION": "AGUARDANDO CONFIRMACAO",
        "AGGRESSIVE_ENTRY": "ENTRADA AGRESSIVA POSSIVEL",
        "CONSERVATIVE_ENTRY": "ENTRADA CONSERVADORA POSSIVEL",
        "BUY_CONFIRMED": "COMPRA CONFIRMADA",
        "SELL_CONFIRMED": "VENDA CONFIRMADA",
        "SIDEWAYS": "MERCADO LATERALIZADO",
        "WEAK_VOLUME": "VOLUME FRACO",
        "HIGH_RISK": "ALTO RISCO",
        "INVALIDATED": "ENTRADA INVALIDADA",
        "WAIT_NEXT_CANDLE": "AGUARDAR NOVO CANDLE",
    }

    def __init__(self, candles, symbol, timeframe, ticker=None):
        self.df = candles.copy().dropna(subset=["open", "high", "low", "close", "volume"])
        if len(self.df) < 80:
            raise ValueError("live_trading_requires_at_least_80_candles")
        self.symbol = symbol
        self.timeframe = timeframe
        self.ticker = ticker or {}
        self.current = self.df.iloc[-1]
        self.previous = self.df.iloc[-2]

    def analyze(self):
        technical = read_technical(self.df)
        volume = read_volume(self.df)
        smc = analyze_smart_money(self.df, technical.get("signal", "NEUTRAL"))
        try:
            wyckoff = read_wyckoff_advanced(self.df)
        except Exception:
            wyckoff = {"wyckoff_phase": "indefinida", "accumulation_score": 50, "distribution_score": 50, "confirmations": [], "invalidations": [], "explanation": "Wyckoff indisponivel."}
        try:
            elliott_wave = read_elliott_wave(self.df)
        except Exception:
            elliott_wave = {"current_wave": "indefinida", "wave_bias": "neutral", "confidence": 0, "impulse_structure": {}, "corrective_structure": {}, "confirmations": [], "invalidations": [], "explanation": "Elliott indisponivel."}
        try:
            tape_reading = read_tape(self.df)
        except Exception:
            tape_reading = {"order_flow_bias": "BALANCED_FLOW", "flow_score": 50, "absorption": {"detected": False}, "confirmations": [], "invalidations": [], "explanation": "Tape reading indisponivel."}
        levels = self._levels(technical)

        trend_score, trend_strength = self._trend_score(technical)
        momentum_score = self._momentum_score(technical)
        volume_score, volume_strength = self._volume_score(volume)
        smc_score = int(smc.get("smc_score", 50))
        wyckoff_score = self._wyckoff_score(wyckoff)
        elliott_score = int(elliott_wave.get("confidence", 35))
        tape_score = int(tape_reading.get("flow_score", 50))
        risk_score = self._risk_score(levels)
        timing_score = self._timing_score(technical, volume)
        candle_score = self._candle_score(technical)

        confluence_score = int(max(0, min(100, round(
            trend_score * 0.22
            + momentum_score * 0.14
            + ((volume_score * 0.45) + (tape_score * 0.55)) * 0.17
            + smc_score * 0.18
            + wyckoff_score * 0.08
            + elliott_score * 0.04
            + risk_score * 0.10
            + timing_score * 0.10
            + candle_score * 0.07
        ))))
        direction = self._direction(technical, smc, volume, tape_reading)
        invalidations = self._invalidations(technical, volume, smc, levels, wyckoff, elliott_wave, tape_reading)
        confirmations = self._confirmations(technical, volume, smc, wyckoff, elliott_wave, tape_reading)
        state = self._state(confluence_score, direction, technical, volume, smc, levels, invalidations)
        messages = self._messages(state, confluence_score, direction, technical, volume, smc, confirmations, invalidations, wyckoff, elliott_wave, tape_reading)
        confidence = int(max(10, min(95, confluence_score * 0.72 + len(confirmations) * 3 - len(invalidations) * 4)))

        return {
            "success": True,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "state": state,
            "status": self.STATES[state],
            "message": messages[0],
            "messages": messages[:8],
            "confluence_score": confluence_score,
            "confidence": confidence,
            "probable_direction": direction,
            "trend_strength": trend_strength,
            "volume_strength": volume_strength,
            "risk_reward": levels.get("risk_reward"),
            "entry_aggressive": levels.get("entry_aggressive") if state in ["AGGRESSIVE_ENTRY", "BUY_CONFIRMED", "SELL_CONFIRMED"] else None,
            "entry_conservative": levels.get("entry_conservative") if state in ["CONSERVATIVE_ENTRY", "BUY_CONFIRMED", "SELL_CONFIRMED"] else None,
            "stop_loss": levels.get("stop_loss"),
            "take_profit": levels.get("take_profit_1"),
            "take_profit_2": levels.get("take_profit_2"),
            "take_profit_3": levels.get("take_profit_3"),
            "reason": self._reason(technical, volume, smc, confirmations, invalidations),
            "confirmations": confirmations[:10],
            "invalidations": invalidations[:10],
            "market_status": self._market_status(volume),
            "current_price": round(float(self.current["close"]), 8),
            "previous_close": round(float(self.previous["close"]), 8),
            "current_candle": self._candle_payload(self.current),
            "previous_candle": self._candle_payload(self.previous),
            "support_resistance": technical.get("details", {}).get("support_resistance", {}),
            "smc": {
                "score": smc_score,
                "bias": smc.get("institutional_bias", "neutral"),
                "false_breakout": smc.get("false_breakout", {}),
                "liquidity_sweep": smc.get("liquidity_sweep", {}),
                "relevant_order_block": smc.get("relevant_order_block"),
                "relevant_fvg": smc.get("relevant_fvg"),
                "liquidity_zone": smc.get("liquidity_zone"),
            },
            "technical": {
                "signal": technical.get("signal"),
                "trend": technical.get("trend", {}),
                "breakout": technical.get("details", {}).get("breakout", {}),
                "pullback": technical.get("details", {}).get("pullback", {}),
                "lateralization": technical.get("details", {}).get("lateralization", {}),
            },
            "volume": {
                "signal": volume.get("signal"),
                "dominant_side": volume.get("dominant_side"),
                "confidence": volume.get("confidence"),
                "metrics": volume.get("metrics", {}),
                "breakout_confirmation": volume.get("breakout_confirmation", {}),
            },
            "wyckoff": wyckoff,
            "elliott_wave": elliott_wave,
            "tape_reading": tape_reading,
            "alerts": self._alerts(state, technical, smc, volume),
            "disclaimer": DISCLAIMER,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    def _levels(self, technical):
        entry = float(technical.get("entry_price") or self.current["close"])
        atr = float(technical.get("details", {}).get("atr") or entry * 0.01)
        signal = "compra" if technical.get("signal") == "BUY" else "venda" if technical.get("signal") == "SELL" else "neutro"
        raw = RiskManagement(entry, atr).calculate_levels(signal)
        rr = float(raw.get("risco_retorno") or 0)
        stop = raw.get("stop_loss")
        risk = abs(entry - stop) if stop is not None else atr
        if technical.get("signal") == "SELL":
            conservative = entry + risk * 0.25
        elif technical.get("signal") == "BUY":
            conservative = entry - risk * 0.25
        else:
            conservative = None
        return {
            "entry_aggressive": round(entry, 8),
            "entry_conservative": round(conservative, 8) if conservative else None,
            "stop_loss": raw.get("stop_loss"),
            "take_profit_1": raw.get("alvo_1"),
            "take_profit_2": raw.get("alvo_2"),
            "take_profit_3": raw.get("alvo_3") or self._take_profit_3(technical.get("signal"), entry, stop),
            "risk_reward": round(rr, 2),
        }

    def _take_profit_3(self, signal, entry, stop):
        risk = abs(entry - stop)
        if signal == "SELL":
            return round(entry - risk * 3, 8)
        return round(entry + risk * 3, 8)

    def _trend_score(self, technical):
        direction = technical.get("trend", {}).get("direction", "SIDEWAYS")
        mapping = {
            "STRONG_BULLISH": (92, 92),
            "STRONG_BEARISH": (92, 92),
            "BULLISH": (72, 68),
            "BEARISH": (72, 68),
            "SIDEWAYS": (35, 25),
        }
        return mapping.get(direction, (40, 30))

    def _momentum_score(self, technical):
        details = technical.get("details", {})
        rsi = float(details.get("rsi", 50))
        histogram = abs(float(details.get("macd", {}).get("histogram", 0)))
        score = 45 + min(histogram * 200, 20)
        if 42 <= rsi <= 68:
            score += 20
        elif rsi >= 76 or rsi <= 24:
            score -= 20
        return int(max(0, min(100, score)))

    def _volume_score(self, volume):
        metrics = volume.get("metrics", {})
        ratio = float(metrics.get("volume_ratio", 1))
        confidence = int(volume.get("confidence", 45))
        strength = int(max(0, min(100, ratio * 32)))
        if volume.get("signal") in ["BULLISH_VOLUME", "BEARISH_VOLUME"]:
            return min(100, confidence + 10), strength
        return max(15, confidence - 18), strength

    def _wyckoff_score(self, wyckoff):
        accumulation = float(wyckoff.get("accumulation_score", 50))
        distribution = float(wyckoff.get("distribution_score", 50))
        phase = wyckoff.get("wyckoff_phase") or wyckoff.get("phase")
        if phase == "acumulacao":
            return int(max(0, min(100, accumulation)))
        if phase == "distribuicao":
            return int(max(0, min(100, 100 - distribution * 0.35)))
        return int(max(0, min(100, (accumulation + (100 - distribution)) / 2)))

    def _risk_score(self, levels):
        rr = float(levels.get("risk_reward") or 0)
        if rr >= 1.8:
            return 88
        if rr >= 1.2:
            return 68
        if rr >= 1:
            return 52
        return 22

    def _timing_score(self, technical, volume):
        breakout = technical.get("details", {}).get("breakout", {})
        pullback = technical.get("details", {}).get("pullback", {})
        candle = technical.get("details", {}).get("candle_strength", {})
        score = 42
        if breakout.get("detected"):
            score += 18
        if pullback.get("detected"):
            score += 16
        if candle.get("strong"):
            score += 14
        if volume.get("breakout_confirmation", {}).get("confirmed"):
            score += 10
        return int(max(0, min(100, score)))

    def _candle_score(self, technical):
        candle = technical.get("details", {}).get("candle_strength", {})
        if candle.get("strong"):
            return 82
        if float(candle.get("body_ratio", 0)) >= 0.45:
            return 62
        return 38

    def _direction(self, technical, smc, volume, tape_reading):
        signal = technical.get("signal")
        bias = smc.get("institutional_bias")
        volume_signal = volume.get("signal")
        flow = tape_reading.get("order_flow_bias")
        bullish_votes = int(signal == "BUY") + int(bias == "bullish") + int(volume_signal == "BULLISH_VOLUME") + int(flow == "BUY_FLOW")
        bearish_votes = int(signal == "SELL") + int(bias == "bearish") + int(volume_signal == "BEARISH_VOLUME") + int(flow == "SELL_FLOW")
        if bullish_votes > bearish_votes:
            return "BUY"
        if bearish_votes > bullish_votes:
            return "SELL"
        return "NEUTRAL"

    def _state(self, score, direction, technical, volume, smc, levels, invalidations):
        lateral = technical.get("details", {}).get("lateralization", {}).get("detected")
        weak_volume = float(volume.get("metrics", {}).get("volume_ratio", 1)) < 0.72
        false_breakout = smc.get("false_breakout", {}).get("detected")
        rr = float(levels.get("risk_reward") or 0)
        breakout = technical.get("details", {}).get("breakout", {}).get("detected")

        if false_breakout or any("invalid" in item.lower() for item in invalidations):
            return "INVALIDATED"
        if rr < 1:
            return "HIGH_RISK"
        if lateral:
            return "SIDEWAYS"
        if weak_volume and score < 66:
            return "WEAK_VOLUME"
        if direction == "BUY" and score >= 78:
            return "BUY_CONFIRMED"
        if direction == "SELL" and score >= 78:
            return "SELL_CONFIRMED"
        if direction in ["BUY", "SELL"] and score >= 68 and breakout:
            return "AGGRESSIVE_ENTRY"
        if direction in ["BUY", "SELL"] and score >= 58:
            return "CONSERVATIVE_ENTRY"
        if score < 42:
            return "WAIT_NEXT_CANDLE"
        return "WAITING_CONFIRMATION"

    def _confirmations(self, technical, volume, smc, wyckoff, elliott_wave, tape_reading):
        items = []
        items.extend(technical.get("confirmations", [])[:4])
        items.extend(volume.get("reasons", [])[:3])
        items.extend(smc.get("confirmations", [])[:3])
        items.extend(wyckoff.get("confirmations", [])[:2])
        items.extend(elliott_wave.get("confirmations", [])[:2])
        items.extend(tape_reading.get("confirmations", [])[:2])
        if smc.get("institutional_bias") in ["bullish", "bearish"]:
            items.append(f"Vies institucional {smc.get('institutional_bias')}.")
        return items

    def _invalidations(self, technical, volume, smc, levels, wyckoff, elliott_wave, tape_reading):
        items = []
        items.extend(technical.get("invalidations", [])[:4])
        items.extend(smc.get("invalidations", [])[:3])
        items.extend(wyckoff.get("invalidations", [])[:2])
        items.extend(elliott_wave.get("invalidations", [])[:2])
        items.extend(tape_reading.get("invalidations", [])[:2])
        if smc.get("false_breakout", {}).get("detected"):
            items.append("Possivel falso rompimento. Nao entrar ainda.")
        if float(volume.get("metrics", {}).get("volume_ratio", 1)) < 0.72:
            items.append("Volume ainda insuficiente para confirmar entrada.")
        if float(levels.get("risk_reward") or 0) < 1:
            items.append("Risco/retorno abaixo de 1:1.")
        return items

    def _messages(self, state, score, direction, technical, volume, smc, confirmations, invalidations, wyckoff, elliott_wave, tape_reading):
        messages = ["Analisando estrutura do mercado..."]
        breakout = technical.get("details", {}).get("breakout", {})
        if breakout.get("detected"):
            messages.append("Rompimento detectado, aguardando confirmacao." if score < 78 else "Rompimento confirmado por confluencia.")
        if smc.get("false_breakout", {}).get("detected"):
            messages.append("Possivel falso rompimento. Nao entrar ainda.")
        if float(volume.get("metrics", {}).get("volume_ratio", 1)) < 0.72:
            messages.append("Volume ainda insuficiente para confirmar entrada.")
        if direction == "BUY" and score >= 55:
            messages.append("Confluencia compradora aumentando.")
        if direction == "SELL" and score >= 55:
            messages.append("Confluencia vendedora aumentando.")
        phase = wyckoff.get("wyckoff_phase") or wyckoff.get("phase")
        if phase == "acumulacao":
            messages.append("Possivel acumulacao detectada.")
        if phase == "distribuicao":
            messages.append("Distribuicao em andamento.")
        if wyckoff.get("institutional_manipulation"):
            messages.append("Manipulacao institucional suspeita.")
        if elliott_wave.get("impulse_structure", {}).get("detected") and elliott_wave.get("wave_bias") == "bullish":
            messages.append("Estrutura impulsiva de alta.")
        if elliott_wave.get("corrective_structure", {}).get("detected"):
            messages.append("Correcao ABC provavel.")
        if tape_reading.get("order_flow_bias") == "BUY_FLOW":
            messages.append("Agressao compradora aumentando.")
        if tape_reading.get("order_flow_bias") == "SELL_FLOW":
            messages.append("Fluxo vendedor dominante.")
        if tape_reading.get("absorption", {}).get("detected"):
            messages.append("Absorcao detectada.")

        state_messages = {
            "WAITING_CONFIRMATION": "Aguardando fechamento do candle.",
            "AGGRESSIVE_ENTRY": "Entrada agressiva possivel, risco moderado.",
            "CONSERVATIVE_ENTRY": "Entrada conservadora apenas apos pullback.",
            "BUY_CONFIRMED": "Compra confirmada pela leitura operacional.",
            "SELL_CONFIRMED": "Venda confirmada pela leitura operacional.",
            "SIDEWAYS": "Mercado lateralizado. Evitar entrada ate romper o range.",
            "WEAK_VOLUME": "Volume fraco. Aguardar participacao institucional.",
            "HIGH_RISK": "Alto risco. Risco/retorno nao compensa.",
            "INVALIDATED": "Cenario invalidado. Aguardar novo setup.",
            "WAIT_NEXT_CANDLE": "Aguardar novo candle.",
        }
        if state in state_messages:
            messages.insert(0, state_messages[state])
        messages.extend(confirmations[:2])
        messages.extend(invalidations[:2])
        return list(dict.fromkeys(messages))

    def _reason(self, technical, volume, smc, confirmations, invalidations):
        if invalidations:
            return invalidations[0]
        if confirmations:
            return confirmations[0]
        return technical.get("explanation") or smc.get("explanation") or "Sem assimetria suficiente no momento."

    def _market_status(self, volume):
        ratio = float(volume.get("metrics", {}).get("volume_ratio", 1))
        if ratio >= 1.8:
            return "VOLATILIDADE/FLUXO ELEVADO"
        if ratio <= 0.72:
            return "MERCADO LENTO"
        return "MERCADO ATIVO"

    def _alerts(self, state, technical, smc, volume):
        alerts = []
        if state in ["BUY_CONFIRMED", "SELL_CONFIRMED", "INVALIDATED", "HIGH_RISK"]:
            alerts.append(state)
        if technical.get("details", {}).get("breakout", {}).get("detected") and volume.get("breakout_confirmation", {}).get("confirmed"):
            alerts.append("BREAKOUT_CONFIRMED")
        if smc.get("false_breakout", {}).get("detected"):
            alerts.append("FALSE_BREAKOUT")
        return alerts

    def _candle_payload(self, candle):
        return {
            "time": int(candle.name.timestamp()),
            "open": round(float(candle["open"]), 8),
            "high": round(float(candle["high"]), 8),
            "low": round(float(candle["low"]), 8),
            "close": round(float(candle["close"]), 8),
            "volume": round(float(candle["volume"]), 6),
        }


def build_live_status(candles, symbol, timeframe, ticker=None):
    return LiveTradingIA(candles, symbol, timeframe, ticker).analyze()
