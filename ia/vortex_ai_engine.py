"""
Vortex AI institutional decision layer.

This module is intentionally a guard layer: it consumes the existing FinanceAI
engines and only upgrades a setup to action when institutional context, flow,
timing, risk and multi-timeframe alignment agree.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo


def _num(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if number == number else default


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def _bool(value: Any) -> bool:
    return bool(value) if value is not None else False


class VortexAIEngine:
    MIN_SCORE = 65
    MIN_CONFIDENCE = 65
    MIN_RR = 2.0

    def __init__(
        self,
        *,
        symbol: str,
        timeframe: str,
        current_price: float,
        technical: dict[str, Any],
        smc: dict[str, Any],
        wyckoff: dict[str, Any],
        volume: dict[str, Any],
        flow: dict[str, Any],
        mtf_analysis: dict[str, Any],
        mtf_confluence: dict[str, Any],
        institutional_mtf: dict[str, Any],
        risk_plan: dict[str, Any],
        institutional_decision: dict[str, Any],
        market_meta: dict[str, Any] | None = None,
        candle_reading: dict[str, Any] | None = None,
        min_score: int | None = None,
    ) -> None:
        self.symbol = symbol
        self.timeframe = timeframe
        self.price = _num(current_price)
        self.technical = technical or {}
        self.smc = smc or {}
        self.wyckoff = wyckoff or {}
        self.volume = volume or {}
        self.flow = flow or {}
        self.mtf_analysis = mtf_analysis or {}
        self.mtf_confluence = mtf_confluence or {}
        self.institutional_mtf = institutional_mtf or {}
        self.risk_plan = risk_plan or {}
        self.institutional_decision = institutional_decision or {}
        self.market_meta = market_meta or {}
        self.candle_reading = candle_reading or {}
        if min_score is not None:
            self.MIN_SCORE = int(max(0, min(100, min_score)))
            self.MIN_CONFIDENCE = max(50, min(80, self.MIN_SCORE))

    def analyze(self) -> dict[str, Any]:
        macro = self._macro_context()
        smart_money = self._smart_money()
        wyckoff = self._wyckoff()
        flow = self._flow()
        mtf = self._multi_timeframe()
        risk = self._risk()
        confirmation = self._confirmation()
        candle_reading = self._candle_reading()
        anti_fake = self._anti_fake(macro, smart_money, flow, mtf, confirmation)

        layers = {
            "macro": macro,
            "smart_money": smart_money,
            "wyckoff": wyckoff,
            "flow": flow,
            "multi_timeframe": mtf,
            "risk": risk,
            "confirmation": confirmation,
            "candle_reading": candle_reading,
            "anti_fake": anti_fake,
        }
        bias = self._bias(layers)
        score = self._score(layers, bias)
        confidence = self._confidence(layers, score, bias)
        blockers = self._blockers(layers, score, confidence, bias)
        signal = self._signal(bias, blockers)
        risk_payload = self._risk_payload(signal)

        return {
            "mode": "VORTEX_AI",
            "priority": "operar_menos_com_mais_qualidade",
            "signal": signal,
            "direction": "BUY" if signal == "COMPRA" else "SELL" if signal == "VENDA" else "NEUTRAL",
            "score": round(score, 2),
            "confidence": round(confidence, 2),
            "bias": bias,
            "layers": layers,
            "requirements": {
                "minimum_score": self.MIN_SCORE,
                "minimum_confidence": self.MIN_CONFIDENCE,
                "minimum_rr": self.MIN_RR,
                "stop_structural_required": True,
                "confirmation_candle_required": True,
                "compatible_flow_required": True,
                "favorable_time_required": True,
            },
            "blockers": blockers,
            "confirmations": self._confirmations(layers, bias),
            "risk": risk_payload,
            "entry": risk_payload.get("entry"),
            "stop_loss": risk_payload.get("stop_loss"),
            "take_profit": risk_payload.get("take_profit"),
            "invalidation": risk_payload.get("invalidation"),
            "reason": self._entry_reason(signal, layers, blockers, bias),
            "wait_reason": self._wait_reason(signal, blockers, layers),
            "narrative": self._narrative(signal, layers, blockers, bias, risk_payload),
            "liquidity_map": self._liquidity_map(),
        }

    def _macro_context(self) -> dict[str, Any]:
        trend = self.technical.get("trend", {})
        details = self.technical.get("details", {})
        lateral = details.get("lateralization", {})
        atr = _num(details.get("atr"))
        atr_pct = _num(details.get("atr_pct"))
        session = self._session()
        direction = trend.get("direction", "SIDEWAYS")
        bullish = "BULLISH" in direction
        bearish = "BEARISH" in direction
        return {
            "trend": direction,
            "direction": "BUY" if bullish else "SELL" if bearish else "NEUTRAL",
            "market_structure": (self.smc.get("structure") or {}).get("bos") or (self.smc.get("structure") or {}).get("choch") or "none",
            "lateralization": {"detected": _bool(lateral.get("detected")), "range_pct": _num(lateral.get("range_pct"))},
            "volatility": {
                "atr": atr,
                "atr_pct": atr_pct,
                "state": "baixa" if atr_pct and atr_pct < 0.25 else "alta" if atr_pct >= 1.5 else "normal",
            },
            "session": session,
            "score": 76 if "STRONG" in direction else 62 if bullish or bearish else 38,
        }

    def _smart_money(self) -> dict[str, Any]:
        structure = self.smc.get("structure", {})
        sweep = self.smc.get("liquidity_sweep") or {}
        false_breakout = self.smc.get("false_breakout") or {}
        inducement = self.smc.get("inducement") or {}
        mitigation = self.smc.get("mitigation") or {}
        bias = self.smc.get("institutional_bias", "neutral")
        direction = "BUY" if bias == "bullish" else "SELL" if bias == "bearish" else "NEUTRAL"
        confirmations = [
            _bool(structure.get("bos")),
            _bool(structure.get("choch")),
            _bool(sweep.get("detected")),
            _bool(mitigation.get("active_zone")),
            _bool(self.smc.get("relevant_order_block") or self.smc.get("nearest_order_block")),
            _bool(self.smc.get("relevant_fvg")),
        ]
        raw = 38 + sum(8 for item in confirmations if item) + _num(self.smc.get("smc_score"), 50) * 0.18
        if false_breakout.get("detected") or self.smc.get("invalidated"):
            raw -= 28
        if inducement.get("detected"):
            raw -= 12
        return {
            "direction": direction,
            "bos": structure.get("bos"),
            "choch": structure.get("choch"),
            "liquidity_sweep": sweep,
            "inducement": inducement,
            "order_block": self.smc.get("relevant_order_block") or self.smc.get("nearest_order_block"),
            "fvg": self.smc.get("relevant_fvg"),
            "mitigation": mitigation,
            "internal_liquidity": self.smc.get("internal_liquidity") or self.smc.get("liquidity_zone"),
            "external_liquidity": self.smc.get("external_liquidity") or self.smc.get("liquidity_zone"),
            "false_breakout": false_breakout,
            "score": _clamp(raw),
        }

    def _wyckoff(self) -> dict[str, Any]:
        intent = self.wyckoff.get("institutional_intent") or self.wyckoff.get("bias") or "neutral"
        direction = "BUY" if intent in ["accumulation", "bullish"] or self.wyckoff.get("spring") else "SELL" if intent in ["distribution", "bearish"] or self.wyckoff.get("upthrust") else "NEUTRAL"
        score = 45
        if direction != "NEUTRAL":
            score += 18
        if self.wyckoff.get("absorption_confirmed") or self.wyckoff.get("spring") or self.wyckoff.get("upthrust"):
            score += 12
        if self.wyckoff.get("climax") or self.wyckoff.get("selling_climax") or self.wyckoff.get("buying_climax"):
            score += 6
        return {
            "direction": direction,
            "phase": self.wyckoff.get("wyckoff_phase") or self.wyckoff.get("phase"),
            "accumulation": self.wyckoff.get("accumulation") or intent == "accumulation",
            "distribution": self.wyckoff.get("distribution") or intent == "distribution",
            "spring": self.wyckoff.get("spring"),
            "upthrust": self.wyckoff.get("upthrust"),
            "climax": self.wyckoff.get("climax") or self.wyckoff.get("selling_climax") or self.wyckoff.get("buying_climax"),
            "effort_vs_result": self.wyckoff.get("effort_vs_result_context") or self.wyckoff.get("effort_vs_result"),
            "absorption": self.wyckoff.get("absorption_confirmed"),
            "score": _clamp(score),
        }

    def _flow(self) -> dict[str, Any]:
        pressure = self.flow.get("pressure", "BALANCED")
        direction = "BUY" if pressure == "BUYER" else "SELL" if pressure == "SELLER" else "NEUTRAL"
        intensity = _num(self.flow.get("intensity"), 35)
        absorption = self.flow.get("absorption") or {}
        volume_ratio = _num((self.volume.get("metrics") or {}).get("volume_ratio"), 1)
        low_liquidity = volume_ratio < 0.55
        score = intensity + (12 if direction != "NEUTRAL" else 0) + min(volume_ratio * 7, 16)
        if low_liquidity:
            score -= 24
        return {
            "direction": direction,
            "volume": self.volume,
            "pressure": pressure,
            "imbalance": _num(self.flow.get("imbalance")),
            "absorption": absorption,
            "aggression": {
                "buy": _num(self.flow.get("buy_aggression")),
                "sell": _num(self.flow.get("sell_aggression")),
            },
            "low_liquidity": low_liquidity,
            "score": _clamp(score),
        }

    def _multi_timeframe(self) -> dict[str, Any]:
        layers = self.institutional_mtf.get("layers") or {}
        role_map = {
            "context": layers.get("context") or layers.get("main_context") or layers.get("main_structure") or {},
            "structure": layers.get("structure") or layers.get("operational_structure") or {},
            "setup": layers.get("setup") or layers.get("operational_setup") or {},
            "timing": layers.get("timing") or layers.get("entry_timing") or {},
        }
        dominant = self.institutional_mtf.get("dominant_direction") or self.mtf_confluence.get("dominant_direction", "NEUTRAL")
        direction = "BUY" if dominant == "BULLISH" else "SELL" if dominant == "BEARISH" else "NEUTRAL"
        aligned_roles = sum(1 for item in role_map.values() if item.get("aligned"))
        conflicts = [role for role, item in role_map.items() if item and not item.get("aligned")]
        return {
            "direction": direction,
            "layers": role_map,
            "alignment_score": _num(self.institutional_mtf.get("alignment_score"), aligned_roles * 25),
            "aligned_roles": aligned_roles,
            "conflicts": conflicts,
            "score": _clamp(aligned_roles * 24 + (8 if direction != "NEUTRAL" else 0)),
        }

    def _risk(self) -> dict[str, Any]:
        rr = _num(self.risk_plan.get("risk_reward") or self.institutional_decision.get("risk_plan", {}).get("risk_reward"))
        stop = self.risk_plan.get("stop_loss") or self.risk_plan.get("stop") or self.institutional_decision.get("risk_plan", {}).get("stop")
        entry = self.risk_plan.get("entry") or self.institutional_decision.get("risk_plan", {}).get("entry")
        target = self.risk_plan.get("take_profit") or self.risk_plan.get("take_profit_1") or self.institutional_decision.get("risk_plan", {}).get("take_profit_1")
        structural = bool(stop and entry and abs(_num(entry) - _num(stop)) > 0)
        valid = rr >= self.MIN_RR and structural
        return {
            "entry": entry,
            "stop_loss": stop,
            "take_profit": target,
            "invalidation": self.risk_plan.get("invalidation") or stop,
            "risk_reward": rr,
            "structural_stop_valid": structural,
            "valid": valid,
            "score": 92 if valid else 55 if structural else 20,
        }

    def _confirmation(self) -> dict[str, Any]:
        candle = (self.technical.get("details") or {}).get("candle_strength") or {}
        timing = self.institutional_decision.get("timing") or {}
        candle_ok = bool(self.candle_reading.get("setup_validated"))
        confirmed = bool((candle.get("strong") and timing.get("confirmed")) or candle_ok)
        return {
            "candle": candle,
            "timing": timing,
            "candle_reading_confirmed": candle_ok,
            "confirmed": confirmed,
            "avoid_late_entry": bool(timing.get("avoid_late_entry")),
            "score": max(86 if confirmed else 42, _num(self.candle_reading.get("score"), 0) if candle_ok else 0),
        }

    def _candle_reading(self) -> dict[str, Any]:
        direction = self.candle_reading.get("direction") or self.candle_reading.get("raw_direction") or "NEUTRAL"
        score = _num(self.candle_reading.get("score"), 0)
        confidence = _num(self.candle_reading.get("confidence"), 0)
        setup = bool(self.candle_reading.get("setup_validated"))
        anti_fake = self.candle_reading.get("anti_fake") or {}
        return {
            "direction": direction,
            "setup_validated": setup,
            "current_candle": self.candle_reading.get("current_candle", {}),
            "sequence": self.candle_reading.get("sequence", {}),
            "panel": self.candle_reading.get("panel", {}),
            "score": _clamp(score),
            "confidence": _clamp(confidence),
            "anti_fake": anti_fake,
            "blockers": self.candle_reading.get("blockers", []),
            "narrative": self.candle_reading.get("narrative", []),
        }

    def _anti_fake(self, macro, smart_money, flow, mtf, confirmation) -> dict[str, Any]:
        filters = []
        if smart_money.get("false_breakout", {}).get("detected"):
            filters.append("rompimento_falso")
        if macro.get("lateralization", {}).get("detected"):
            filters.append("lateralizacao")
        if flow.get("low_liquidity"):
            filters.append("baixa_liquidez")
        if confirmation.get("avoid_late_entry"):
            filters.append("entrada_atrasada")
        if mtf.get("conflicts"):
            filters.append("conflito_timeframes")
        if not confirmation.get("confirmed"):
            filters.append("candle_sem_confirmacao")
        filters.extend((self.candle_reading.get("anti_fake") or {}).get("filters", []))
        return {
            "blocked": bool(filters),
            "filters": filters,
            "score": 100 - len(filters) * 16,
        }

    def _bias(self, layers) -> str:
        votes = [
            layers["macro"].get("direction"),
            layers["smart_money"].get("direction"),
            layers["wyckoff"].get("direction"),
            layers["flow"].get("direction"),
            layers["multi_timeframe"].get("direction"),
        ]
        buy = votes.count("BUY")
        sell = votes.count("SELL")
        if buy >= 3 and buy > sell:
            return "BUY"
        if sell >= 3 and sell > buy:
            return "SELL"
        return "NEUTRAL"

    def _score(self, layers, bias: str) -> float:
        if bias == "NEUTRAL":
            return min(74, sum(layer["score"] for layer in layers.values()) / len(layers))
        weights = {
            "macro": 0.13,
            "smart_money": 0.20,
            "wyckoff": 0.10,
            "flow": 0.15,
            "multi_timeframe": 0.17,
            "risk": 0.10,
            "confirmation": 0.05,
            "candle_reading": 0.10,
        }
        score = sum(layers[key]["score"] * weight for key, weight in weights.items())
        if layers["anti_fake"]["blocked"]:
            score -= min(24, len(layers["anti_fake"]["filters"]) * 7)
        return _clamp(score)

    def _confidence(self, layers, score: float, bias: str) -> float:
        aligned = sum(1 for key in ["macro", "smart_money", "wyckoff", "flow", "multi_timeframe"] if layers[key].get("direction") == bias)
        confidence = score * 0.72 + aligned * 6 + (10 if layers["risk"]["valid"] else -10)
        confidence -= len(layers["anti_fake"]["filters"]) * 5
        return _clamp(confidence)

    def _blockers(self, layers, score: float, confidence: float, bias: str) -> list[str]:
        blockers = []
        if bias == "NEUTRAL":
            blockers.append("Sem vies institucional dominante.")
        if score < self.MIN_SCORE:
            blockers.append(f"Score abaixo de {self.MIN_SCORE}.")
        if confidence < self.MIN_CONFIDENCE:
            blockers.append(f"Confianca abaixo de {self.MIN_CONFIDENCE}.")
        if not layers["risk"]["valid"]:
            blockers.append("RR minimo 2:1 ou stop estrutural ainda invalido.")
        if not layers["confirmation"]["confirmed"]:
            blockers.append("Candle de confirmacao/timing ainda ausente.")
        if not layers["candle_reading"].get("setup_validated"):
            blockers.extend(layers["candle_reading"].get("blockers") or ["Aguardando candle gatilho."])
        if layers["candle_reading"].get("score", 0) < self.MIN_SCORE:
            blockers.append("Leitura candle-a-candle abaixo do score minimo.")
        if layers["candle_reading"].get("confidence", 0) < self.MIN_CONFIDENCE:
            blockers.append("Confianca candle-a-candle abaixo do minimo.")
        if layers["flow"].get("direction") not in [bias, "NEUTRAL"]:
            blockers.append("Fluxo contra a direcao do setup.")
        if not layers["macro"]["session"]["favorable"]:
            blockers.append("Horario operacional desfavoravel.")
        blockers.extend(self._filter_text(item) for item in layers["anti_fake"]["filters"])
        return list(dict.fromkeys(blockers))

    def _signal(self, bias: str, blockers: list[str]) -> str:
        hard_blocks = [item for item in blockers if any(term in item for term in ["lateralizacao", "baixa liquidez", "conflito", "desfavoravel", "RR minimo"])]
        if hard_blocks:
            return "NÃO OPERAR"
        if blockers:
            return "AGUARDAR"
        return "COMPRA" if bias == "BUY" else "VENDA" if bias == "SELL" else "AGUARDAR"

    def _risk_payload(self, signal: str) -> dict[str, Any]:
        return {
            "entry": self.risk_plan.get("entry") or self.institutional_decision.get("risk_plan", {}).get("entry"),
            "stop_loss": self.risk_plan.get("stop_loss") or self.risk_plan.get("stop") or self.institutional_decision.get("risk_plan", {}).get("stop"),
            "take_profit": self.risk_plan.get("take_profit") or self.risk_plan.get("take_profit_1") or self.institutional_decision.get("risk_plan", {}).get("take_profit_1"),
            "invalidation": self.risk_plan.get("invalidation") or self.risk_plan.get("stop_loss") or self.risk_plan.get("stop"),
            "risk_reward": self.risk_plan.get("risk_reward"),
            "active": signal in ["COMPRA", "VENDA"],
        }

    def _confirmations(self, layers, bias: str) -> list[str]:
        items = []
        for key in ["macro", "smart_money", "wyckoff", "flow", "multi_timeframe"]:
            if layers[key].get("direction") == bias:
                items.append(f"{key} alinhado para {bias}.")
        if layers["risk"]["valid"]:
            items.append("Risco estrutural com RR minimo 2:1.")
        if layers["confirmation"]["confirmed"]:
            items.append("Candle e timing confirmados.")
        if layers["candle_reading"].get("setup_validated"):
            items.append("Leitura candle-a-candle validou gatilho, confirmacao e sequencia.")
        return items

    def _entry_reason(self, signal, layers, blockers, bias):
        if signal in ["COMPRA", "VENDA"]:
            return f"{signal} liberada por contexto institucional completo, liquidez mapeada, fluxo {bias} e RR valido."
        return ""

    def _wait_reason(self, signal, blockers, layers):
        if signal in ["COMPRA", "VENDA"]:
            return ""
        return blockers[0] if blockers else "Aguardando multiplas confirmacoes institucionais."

    def _narrative(self, signal, layers, blockers, bias, risk):
        liquidity = self._liquidity_map()
        seeing = (
            f"Vortex AI ve tendencia {layers['macro']['trend']}, SMC {layers['smart_money']['direction']}, "
            f"Wyckoff {layers['wyckoff']['direction']} e fluxo {layers['flow']['pressure']}."
        )
        liq = f"Liquidez interna/externa: {liquidity.get('internal')} / {liquidity.get('external')}."
        candle = " ".join(layers["candle_reading"].get("narrative") or [])
        if signal in ["COMPRA", "VENDA"]:
            action = f"Entrada validada em {risk.get('entry')}, stop {risk.get('stop_loss')}, alvo {risk.get('take_profit')}."
        else:
            action = f"IA aguarda: {self._wait_reason(signal, blockers, layers)}"
        invalidation = f"Invalida se perder {risk.get('invalidation')} ou se fluxo/MTF virarem contra {bias}."
        return {
            "summary": f"{seeing} {action}",
            "what_ai_sees": seeing,
            "candle_reading": candle,
            "liquidity": liq,
            "why_enter": self._entry_reason(signal, layers, blockers, bias),
            "why_wait": self._wait_reason(signal, blockers, layers),
            "invalidation": invalidation,
        }

    def _liquidity_map(self) -> dict[str, Any]:
        return {
            "internal": self.smc.get("internal_liquidity") or self.smc.get("liquidity_zone"),
            "external": self.smc.get("external_liquidity") or self.smc.get("liquidity_zone"),
            "sweep": self.smc.get("liquidity_sweep"),
            "order_block": self.smc.get("relevant_order_block") or self.smc.get("nearest_order_block"),
            "fvg": self.smc.get("relevant_fvg"),
        }

    def _session(self) -> dict[str, Any]:
        now = datetime.now(ZoneInfo("America/Sao_Paulo"))
        minutes = now.hour * 60 + now.minute
        market = self.market_meta.get("market")
        if market == "crypto":
            favorable = True
            label = "crypto_24h"
        elif market == "futures_b3":
            favorable = 9 * 60 <= minutes <= 18 * 60
            label = "b3_regular" if favorable else "fora_b3"
        else:
            favorable = 8 * 60 <= minutes <= 18 * 60
            label = "regular" if favorable else "fora_horario"
        return {
            "label": label,
            "hour": now.strftime("%H:%M"),
            "weekday": now.weekday(),
            "favorable": favorable and now.weekday() < 5,
        }

    def _filter_text(self, item: str) -> str:
        labels = {
            "rompimento_falso": "Filtro anti-fake: rompimento falso.",
            "lateralizacao": "Filtro anti-fake: lateralizacao.",
            "baixa_liquidez": "Filtro anti-fake: baixa liquidez.",
            "entrada_atrasada": "Filtro anti-fake: entrada atrasada.",
            "conflito_timeframes": "Filtro anti-fake: conflito entre timeframes.",
            "candle_sem_confirmacao": "Filtro anti-fake: candle sem confirmacao.",
        }
        return labels.get(item, item)


def build_vortex_ai_decision(**kwargs: Any) -> dict[str, Any]:
    return VortexAIEngine(**kwargs).analyze()
