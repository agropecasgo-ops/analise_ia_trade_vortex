"""
Motor institucional para a leitura grafica principal.

Nao substitui os engines existentes; consolida os resultados ja calculados em
uma decisao operacional com pesos, timing, risco estrutural e narrativa.
"""

from __future__ import annotations

from typing import Any


def _num(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if number == number else default


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def _zone_price(zone: dict[str, Any] | None, side: str, fallback: float | None = None) -> float | None:
    if not zone:
        return fallback
    if side == "low":
        return _num(zone.get("low", zone.get("price", zone.get("mid"))), fallback or 0) or fallback
    if side == "high":
        return _num(zone.get("high", zone.get("price", zone.get("mid"))), fallback or 0) or fallback
    return _num(zone.get("mid", zone.get("price", zone.get("high", zone.get("low")))), fallback or 0) or fallback


class InstitutionalDecisionEngine:
    WEIGHTS = {
        "smart_money": 0.22,
        "wyckoff": 0.10,
        "elliott": 0.07,
        "flow": 0.17,
        "vwap": 0.08,
        "ema": 0.09,
        "rsi": 0.06,
        "macd": 0.06,
        "multi_timeframe": 0.11,
        "risk_reward": 0.04,
    }

    def __init__(
        self,
        technical: dict[str, Any],
        smc: dict[str, Any],
        volume: dict[str, Any],
        wyckoff: dict[str, Any],
        elliott_wave: dict[str, Any],
        tape_reading: dict[str, Any],
        mtf_confluence: dict[str, Any],
        levels: dict[str, Any],
        current_price: float,
    ) -> None:
        self.technical = technical or {}
        self.smc = smc or {}
        self.volume = volume or {}
        self.wyckoff = wyckoff or {}
        self.elliott = elliott_wave or {}
        self.tape = tape_reading or {}
        self.mtf = mtf_confluence or {}
        self.levels = levels or {}
        self.price = _num(current_price)

    def analyze(self) -> dict[str, Any]:
        components = self._components()
        buy_force = sum(item["buy"] * self.WEIGHTS[key] for key, item in components.items())
        sell_force = sum(item["sell"] * self.WEIGHTS[key] for key, item in components.items())
        wait_force = sum(item["wait"] * self.WEIGHTS[key] for key, item in components.items())
        neutral_force = _clamp(100 - abs(buy_force - sell_force) - max(buy_force, sell_force) * 0.35)

        risk_plan = self._risk_plan("BUY" if buy_force >= sell_force else "SELL")
        timing = self._timing()
        invalidations = self._invalidations(risk_plan)
        score = _clamp(max(buy_force, sell_force) * 0.76 + (100 - wait_force) * 0.18 + risk_plan["score"] * 0.06)
        confidence = _clamp(score + abs(buy_force - sell_force) * 0.25 - len(invalidations) * 5)
        decision = self._decision(buy_force, sell_force, wait_force, neutral_force, score, timing, risk_plan, invalidations)

        return {
            "score": round(score, 2),
            "confidence": round(confidence, 2),
            "bias": decision["bias"],
            "signal": decision["signal"],
            "direction": decision["direction"],
            "forces": {
                "buy": round(_clamp(buy_force), 1),
                "sell": round(_clamp(sell_force), 1),
                "wait": round(_clamp(wait_force), 1),
                "neutral": round(_clamp(neutral_force), 1),
            },
            "components": components,
            "weights": self.WEIGHTS,
            "risk_plan": risk_plan,
            "timing": timing,
            "invalidations": invalidations,
            "confirmations": self._confirmations(components, timing),
            "narrative": self._narrative(decision, risk_plan, timing, invalidations),
            "liquidity": self._liquidity_text(),
        }

    def _components(self) -> dict[str, dict[str, Any]]:
        return {
            "smart_money": self._smart_money(),
            "wyckoff": self._wyckoff(),
            "elliott": self._elliott(),
            "flow": self._flow(),
            "vwap": self._vwap(),
            "ema": self._ema(),
            "rsi": self._rsi(),
            "macd": self._macd(),
            "multi_timeframe": self._mtf(),
            "risk_reward": self._risk_reward(),
        }

    def _component(self, buy=0, sell=0, wait=30, reason="") -> dict[str, Any]:
        return {"buy": _clamp(buy), "sell": _clamp(sell), "wait": _clamp(wait), "reason": reason}

    def _smart_money(self):
        bias = self.smc.get("institutional_bias")
        score = _num(self.smc.get("smc_score"), 50)
        if self.smc.get("false_breakout", {}).get("detected") or self.smc.get("invalidated"):
            return self._component(15, 15, 88, "SMC detectou falso rompimento ou invalidacao.")
        if bias == "bullish":
            return self._component(score, 18, 25, "SMC comprador.")
        if bias == "bearish":
            return self._component(18, score, 25, "SMC vendedor.")
        structure = self.smc.get("structure", {})
        if structure.get("bos") == "bullish" or structure.get("choch") == "bullish":
            return self._component(68, 28, 30, "BOS/CHOCH bullish.")
        if structure.get("bos") == "bearish" or structure.get("choch") == "bearish":
            return self._component(28, 68, 30, "BOS/CHOCH bearish.")
        return self._component(38, 38, 46, "SMC neutro.")

    def _wyckoff(self):
        phase = self.wyckoff.get("wyckoff_phase") or self.wyckoff.get("phase")
        if phase == "acumulacao" or self.wyckoff.get("spring"):
            return self._component(72, 22, 30, "Wyckoff favorece acumulacao/spring.")
        if phase == "distribuicao" or self.wyckoff.get("upthrust"):
            return self._component(22, 72, 30, "Wyckoff favorece distribuicao/upthrust.")
        return self._component(42, 42, 42, "Wyckoff indefinido.")

    def _elliott(self):
        bias = self.elliott.get("wave_bias")
        quality = _num(self.elliott.get("confidence"), 45)
        if bias == "bullish":
            return self._component(quality, 28, 35, "Elliott bullish.")
        if bias == "bearish":
            return self._component(28, quality, 35, "Elliott bearish.")
        return self._component(40, 40, 44, "Elliott neutro.")

    def _flow(self):
        buy = _num(self.tape.get("buy_aggression"), 45)
        sell = _num(self.tape.get("sell_aggression"), 45)
        if self.volume.get("dominant_side") in ["BUYER", "BUYERS"]:
            buy += 10
        if self.volume.get("dominant_side") in ["SELLER", "SELLERS"]:
            sell += 10
        if self.tape.get("absorption", {}).get("detected"):
            return self._component(buy, sell, 70, "Absorcao detectada; exige confirmacao.")
        return self._component(buy, sell, 30 if abs(buy - sell) >= 12 else 52, "Fluxo/tape reading.")

    def _vwap(self):
        details = self.technical.get("details", {})
        vwap = _num(details.get("vwap") or self.technical.get("vwap"))
        if not vwap:
            return self._component(42, 42, 42, "VWAP indisponivel.")
        if self.price > vwap:
            return self._component(66, 28, 30, "Preco acima da VWAP.")
        if self.price < vwap:
            return self._component(28, 66, 30, "Preco abaixo da VWAP.")
        return self._component(42, 42, 42, "Preco na VWAP.")

    def _ema(self):
        trend = self.technical.get("trend", {})
        direction = trend.get("direction")
        if direction in ["STRONG_BULLISH", "BULLISH"]:
            return self._component(74, 24, 24, "EMAs favorecem alta.")
        if direction in ["STRONG_BEARISH", "BEARISH"]:
            return self._component(24, 74, 24, "EMAs favorecem baixa.")
        return self._component(42, 42, 45, "EMAs sem empilhamento claro.")

    def _rsi(self):
        rsi = _num(self.technical.get("details", {}).get("rsi"), 50)
        if 50 <= rsi <= 68:
            return self._component(64, 32, 28, "RSI comprador saudavel.")
        if 32 <= rsi < 50:
            return self._component(32, 64, 28, "RSI vendedor saudavel.")
        if rsi > 72 or rsi < 28:
            return self._component(34, 34, 68, "RSI em extremo; evitar entrada atrasada.")
        return self._component(45, 45, 42, "RSI neutro.")

    def _macd(self):
        macd = self.technical.get("details", {}).get("macd", {})
        hist = _num(macd.get("histogram"))
        if hist > 0:
            return self._component(62, 35, 32, "MACD positivo.")
        if hist < 0:
            return self._component(35, 62, 32, "MACD negativo.")
        return self._component(42, 42, 45, "MACD neutro.")

    def _mtf(self):
        direction = self.mtf.get("dominant_direction")
        strength = _num(self.mtf.get("average_strength"), 45)
        confirmed = _num(self.mtf.get("confirmed_timeframes"), 0)
        if direction == "BULLISH":
            return self._component(strength + confirmed * 4, 25, 28 if confirmed >= 3 else 56, "MTF bullish.")
        if direction == "BEARISH":
            return self._component(25, strength + confirmed * 4, 28 if confirmed >= 3 else 56, "MTF bearish.")
        return self._component(38, 38, 58, "MTF sem direcao.")

    def _risk_reward(self):
        rr = _num(self.levels.get("risco_retorno"))
        if rr >= 1.5:
            return self._component(62, 62, 20, f"RR favoravel 1:{rr:.2f}.")
        if rr >= 1:
            return self._component(52, 52, 35, f"RR aceitavel 1:{rr:.2f}.")
        return self._component(20, 20, 80, "RR abaixo do minimo.")

    def _risk_plan(self, direction: str) -> dict[str, Any]:
        entry = _num(self.levels.get("entrada"), self.price)
        rr = _num(self.levels.get("risco_retorno"))
        ob = self.smc.get("relevant_order_block") or self.smc.get("nearest_order_block")
        fvg = self.smc.get("relevant_fvg")
        liquidity = self.smc.get("liquidity_zone")
        if direction == "BUY":
            structural_stop = _zone_price(ob, "low") or _zone_price(fvg, "low") or _num(self.levels.get("stop_loss"))
            structural_target = _zone_price(liquidity, "high") or _num(self.levels.get("alvo_1"))
            invalidation = structural_stop
        else:
            structural_stop = _zone_price(ob, "high") or _zone_price(fvg, "high") or _num(self.levels.get("stop_loss"))
            structural_target = _zone_price(liquidity, "low") or _num(self.levels.get("alvo_1"))
            invalidation = structural_stop
        risk = abs(entry - structural_stop) if structural_stop else 0
        reward = abs(structural_target - entry) if structural_target else 0
        structural_rr = reward / risk if risk else rr
        return {
            "entry": round(entry, 8) if entry else None,
            "stop": round(structural_stop, 8) if structural_stop else self.levels.get("stop_loss"),
            "take_profit_1": round(structural_target, 8) if structural_target else self.levels.get("alvo_1"),
            "take_profit_partial": self.levels.get("alvo_1"),
            "take_profit_2": self.levels.get("alvo_2"),
            "risk_reward": round(structural_rr or rr, 2),
            "minimum_rr": 1.15,
            "invalidation": round(invalidation, 8) if invalidation else self.levels.get("stop_loss"),
            "score": 82 if (structural_rr or rr) >= 1.5 else 62 if (structural_rr or rr) >= 1.15 else 24,
        }

    def _timing(self) -> dict[str, Any]:
        details = self.technical.get("details", {})
        sweep = self.smc.get("liquidity_sweep", {})
        absorption = self.tape.get("absorption", {})
        breakout = details.get("breakout", {})
        pullback = details.get("pullback", {})
        candle = details.get("candle_strength", {})
        triggers = []
        if sweep.get("detected"):
            triggers.append("sweep")
        if absorption.get("detected"):
            triggers.append("absorcao")
        if breakout.get("detected"):
            triggers.append("rompimento")
        if pullback.get("detected"):
            triggers.append("reteste")
        if candle.get("strong"):
            triggers.append("candle_gatilho")
        confirmed = bool({"sweep", "rompimento", "reteste", "candle_gatilho"} & set(triggers)) and not absorption.get("detected")
        return {
            "confirmed": confirmed,
            "triggers": triggers,
            "waiting_for": [] if confirmed else ["confirmacao", "candle_gatilho", "reteste", "fluxo"],
            "avoid_late_entry": self._rsi()["wait"] >= 65,
        }

    def _invalidations(self, risk_plan):
        invalidations = []
        rr = _num(risk_plan.get("risk_reward"))
        if rr and rr < risk_plan["minimum_rr"]:
            invalidations.append("Risco/retorno estrutural abaixo do minimo.")
        if self.smc.get("false_breakout", {}).get("detected"):
            invalidations.append("Falso rompimento detectado.")
        if self.smc.get("invalidated"):
            invalidations.append("SMC invalidou a leitura.")
        return invalidations

    def _decision(self, buy, sell, wait, neutral, score, timing, risk_plan, invalidations):
        if invalidations:
            return {"signal": "AGUARDAR", "direction": "NEUTRAL", "bias": "WAIT"}
        if neutral >= 52 and max(buy, sell) < 48:
            return {"signal": "NEUTRO", "direction": "NEUTRAL", "bias": "NEUTRAL"}
        if wait >= 58 or not timing.get("confirmed"):
            return {"signal": "AGUARDAR", "direction": "NEUTRAL", "bias": "WAIT"}
        if buy >= sell + 10 and score >= 55:
            return {"signal": "COMPRA", "direction": "BUY", "bias": "BUY"}
        if sell >= buy + 10 and score >= 55:
            return {"signal": "VENDA", "direction": "SELL", "bias": "SELL"}
        return {"signal": "AGUARDAR", "direction": "NEUTRAL", "bias": "WAIT"}

    def _confirmations(self, components, timing):
        confirmations = [item["reason"] for item in components.values() if max(item["buy"], item["sell"]) >= 62]
        if timing.get("confirmed"):
            confirmations.append(f"Timing confirmado por {', '.join(timing.get('triggers') or [])}.")
        return confirmations[:12]

    def _liquidity_text(self):
        zone = self.smc.get("liquidity_zone")
        if not zone:
            return "Sem liquidez proxima mapeada."
        return f"Liquidez {zone.get('type')} em {_zone_price(zone, 'mid')}."

    def _narrative(self, decision, risk_plan, timing, invalidations):
        if invalidations:
            return f"IA evita entrada: {invalidations[0]} Invalida em {risk_plan.get('invalidation')}."
        if decision["signal"] in ["COMPRA", "VENDA"]:
            return (
                f"IA libera {decision['signal']} por confluencia institucional e timing confirmado. "
                f"Entrada {risk_plan.get('entry')}, stop {risk_plan.get('stop')}, parcial {risk_plan.get('take_profit_partial')}."
            )
        missing = ", ".join(timing.get("waiting_for") or ["confirmacao"])
        return f"IA aguarda: falta {missing}. {self._liquidity_text()}"


def build_institutional_decision(**kwargs):
    return InstitutionalDecisionEngine(**kwargs).analyze()
