"""
Leitura Operacional Institucional.

Este modulo substitui a leitura grafica antiga por uma leitura candle a candle
baseada em liquidez, stops provaveis, 50% do movimento, gatilhos, manipulacao,
falha de pullback e obrigacao atual do preco. Nao usa indicadores classicos nem
gera sinal seco.
"""

from __future__ import annotations

from typing import Any

import pandas as pd


def _num(value: Any, default: float = 0.0) -> float:
    try:
        if pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def _round(value: Any, digits: int = 5) -> float:
    return round(_num(value), digits)


def _pct(part: float, whole: float) -> float:
    return (part / whole * 100.0) if whole else 0.0


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


class PriceObligationEngine:
    def evaluate(self, current, fib, triggers, liquidity, manipulation, pullback, behavior) -> dict[str, Any]:
        base = self._base_obligation(current, fib, triggers, liquidity, manipulation, pullback, behavior)
        state = self._state(current, triggers, pullback, behavior, base["kind"])
        base.update(state)
        return base

    def _base_obligation(self, current, fib, triggers, liquidity, manipulation, pullback, behavior) -> dict[str, str]:
        if manipulation["detected"]:
            return {
                "kind": "validar ou rejeitar manipulacao",
                "text": "Preco capturou liquidez; obrigacao atual e confirmar continuidade ou devolver o movimento.",
                "timing": "Nao operar seco: aguardar fechamento fora da zona manipulada.",
            }
        if pullback["pullback_failure"]:
            return {
                "kind": "reverter movimento",
                "text": "Pullback falhou; obrigacao muda para romper o lado contrario ou entrar em reversao.",
                "timing": "Aguardar rompimento contrario com fechamento alem de 50%.",
            }
        if triggers["direction"] == "alta" and current["close_50"] == "ACIMA_50":
            return {
                "kind": "continuar subindo",
                "text": "Rompimento de maxima com fechamento acima de 50%; obrigacao e buscar liquidez acima.",
                "timing": "Entrada so faz sentido no teste/defesa do gatilho, com stop abaixo da manipulacao.",
            }
        if triggers["direction"] == "baixa" and current["close_50"] == "ABAIXO_50":
            return {
                "kind": "continuar descendo",
                "text": "Rompimento de minima com fechamento abaixo de 50%; obrigacao e buscar liquidez abaixo.",
                "timing": "Entrada so faz sentido no teste/defesa do gatilho, com stop acima da manipulacao.",
            }
        if behavior.get("loss_of_strength"):
            return {
                "kind": "provar continuidade",
                "text": "Movimento perdeu forca; obrigacao e renovar maxima/minima ou aceitar reversao.",
                "timing": "Aguardar candle de aceitacao e renovacao estrutural.",
            }
        if fib["micro_50"]["return_to_50"]:
            return {
                "kind": "decidir no pullback",
                "text": "Preco retornou ao 50% micro; obrigacao e defender pullback ou inverter.",
                "timing": "Regiao de decisao: observar candle atual e proximo fechamento.",
            }
        if not liquidity["movement_has_fuel"]:
            return {
                "kind": "sem combustivel",
                "text": "Movimento sem buscar nova liquidez; obrigacao enfraquecida e risco de lateralizacao.",
                "timing": "Nao operar ate surgir nova liquidez/gatilho.",
            }
        return {
            "kind": "buscar liquidez",
            "text": f"Preco deve buscar {liquidity['fuel_target']} antes de uma decisao mais limpa.",
            "timing": "Aguardar aproximacao da liquidez ou rompimento com fechamento.",
        }

    def _state(self, current, triggers, pullback, behavior, kind: str) -> dict[str, Any]:
        fulfilled = (
            kind == "continuar subindo" and current.get("closed_above_previous_high")
            or kind == "continuar descendo" and current.get("closed_below_previous_low")
        )
        failed = bool(
            pullback.get("pullback_failure")
            or behavior.get("loss_of_strength")
            or behavior.get("continuity_quality") in {"fraca", "artificial"}
        )
        invalidated = bool(current.get("violation_without_close") and triggers.get("direction") in {"alta", "baixa"})
        status = "cumprida" if fulfilled else "invalidada" if invalidated else "falhada" if failed else "ativa"
        return {
            "status": status,
            "fulfilled": fulfilled,
            "failed": failed,
            "invalidated": invalidated,
        }


class ThreeCandlePatternEngine:
    def __init__(
        self,
        *,
        candles: list[dict[str, Any]],
        movements: dict[str, Any],
        fib: dict[str, Any],
        liquidity: dict[str, Any],
        triggers: dict[str, Any],
        manipulation: dict[str, Any],
        pullback: dict[str, Any],
        obligation: dict[str, Any],
        fractal: dict[str, Any],
        risk: dict[str, Any],
    ) -> None:
        self.candles = candles[-3:]
        self.movements = movements
        self.fib = fib
        self.liquidity = liquidity
        self.triggers = triggers
        self.manipulation = manipulation
        self.pullback = pullback
        self.obligation = obligation
        self.fractal = fractal
        self.risk = risk

    def analyze(self) -> dict[str, Any]:
        if len(self.candles) < 3:
            return self._empty("Padrao de 3 candles exige ao menos tres candles recentes.")

        candle_1, candle_2, candle_3 = self.candles
        target = self._target_role(candle_1)
        denial = self._denial_role(candle_1, candle_2)
        test = self._test_role(candle_1, candle_2, candle_3, target)
        direction = self._direction(candle_1, candle_2, candle_3, denial, test)
        plan = self._trade_plan(direction, candle_1, candle_2, candle_3)
        invalidations = self._invalidations(target, test, direction, plan)
        score = self._score(target, denial, test, direction, plan, invalidations)
        status = self._status(score, invalidations, test)
        classification = self._classification(score)
        region = self._region(target, candle_1, candle_3)
        explanation = self._explanation(target, denial, test, direction, plan, status, invalidations)

        return {
            "detected": score >= 40 or target["detected"] or denial["detected"] or test["detected"],
            "status": status,
            "direction": direction,
            "score": score,
            "classification": classification,
            "candle1": target,
            "candle2": denial,
            "candle3": test,
            "region": region,
            "liquidity": self.liquidity.get("classification", {}),
            "entry": plan["entry"],
            "stop": plan["stop"],
            "target": plan["target"],
            "riskReward": plan["riskReward"],
            "invalidation": plan["invalidation"],
            "invalidations": invalidations,
            "messages": self._messages(target, denial, test, status, direction, plan, invalidations),
            "explanation": explanation,
        }

    def _target_role(self, candle: dict[str, Any]) -> dict[str, Any]:
        close = _num(candle.get("close"))
        high = _num(candle.get("high"))
        low = _num(candle.get("low"))
        macro_50 = _num(self.fib["macro_50"]["level"])
        micro_50 = _num(self.fib["micro_50"]["level"])
        upper = _num(self.liquidity.get("seller_stops_above"))
        lower = _num(self.liquidity.get("buyer_stops_below"))
        tolerance = max(abs(close) * 0.0012, abs(upper - lower) * 0.025)
        regions = []
        checks = [
            ("liquidez acima", upper, high),
            ("liquidez abaixo", lower, low),
            ("50% macro", macro_50, close),
            ("50% micro", micro_50, close),
            ("topo relevante", _num(self.triggers.get("relevant_high")), high),
            ("fundo relevante", _num(self.triggers.get("relevant_low")), low),
        ]
        for label, level, touched in checks:
            if level and abs(_num(touched) - level) <= tolerance:
                regions.append({"label": label, "level": _round(level), "distance": _round(abs(_num(touched) - level), 6)})
        consumed_stops = bool(high >= upper or low <= lower)
        return {
            "role": "CANDLE_1_ALVO",
            "detected": bool(regions or consumed_stops),
            "time": candle.get("time"),
            "high": candle.get("high"),
            "low": candle.get("low"),
            "close": candle.get("close"),
            "regions": regions,
            "consumedStops": consumed_stops,
            "reading": "Candle 1 deu alvo em regiao institucional." if regions or consumed_stops else "Padrao fraco: Candle 1 nao deu alvo confirmado.",
        }

    def _denial_role(self, candle_1: dict[str, Any], candle_2: dict[str, Any]) -> dict[str, Any]:
        opposite_close = (
            candle_1.get("direction") == "comprador" and candle_2.get("direction") == "vendedor"
            or candle_1.get("direction") == "vendedor" and candle_2.get("direction") == "comprador"
        )
        wick_rejection = _num(candle_2.get("upper_wick_pct")) >= 42 or _num(candle_2.get("lower_wick_pct")) >= 42
        force_loss = candle_2.get("failure") or _num(candle_2.get("body_strength")) <= 35 or candle_2.get("violation_without_close")
        detected = bool(opposite_close or wick_rejection or force_loss)
        return {
            "role": "CANDLE_2_NEGACAO",
            "detected": detected,
            "time": candle_2.get("time"),
            "high": candle_2.get("high"),
            "low": candle_2.get("low"),
            "close": candle_2.get("close"),
            "oppositeClose": bool(opposite_close),
            "wickRejection": bool(wick_rejection),
            "forceLoss": bool(force_loss),
            "reading": "Candle 2 negou o movimento com rejeicao/perda de forca." if detected else "Candle 2 ainda nao negou a regiao.",
        }

    def _test_role(self, candle_1: dict[str, Any], candle_2: dict[str, Any], candle_3: dict[str, Any], target: dict[str, Any]) -> dict[str, Any]:
        region_levels = [_num(item.get("level")) for item in target.get("regions", []) if _num(item.get("level"))]
        if not region_levels:
            region_levels = [_num(candle_1.get("high")), _num(candle_1.get("low"))]
        high = _num(candle_3.get("high"))
        low = _num(candle_3.get("low"))
        close = _num(candle_3.get("close"))
        tolerance = max(abs(close) * 0.0014, abs(_num(candle_1.get("high")) - _num(candle_1.get("low"))) * 0.18)
        tested_levels = [level for level in region_levels if min(abs(high - level), abs(low - level), abs(close - level)) <= tolerance]
        failed_test = bool(tested_levels and (candle_3.get("failure") or candle_3.get("violation_without_close")))
        induced = bool(tested_levels and (self.manipulation.get("detected") or candle_3.get("violation_without_close")))
        return {
            "role": "CANDLE_3_TESTE",
            "detected": bool(tested_levels),
            "time": candle_3.get("time"),
            "high": candle_3.get("high"),
            "low": candle_3.get("low"),
            "close": candle_3.get("close"),
            "testedLevels": [_round(item) for item in tested_levels],
            "failedTest": failed_test,
            "induction": induced,
            "reading": "Candle 3 testou a regiao e criou ponto tecnico." if tested_levels else "Padrao invalido: sem teste objetivo da regiao.",
        }

    def _direction(self, candle_1, candle_2, candle_3, denial, test) -> str:
        if not denial.get("detected") or not test.get("detected"):
            return "NEUTRO"
        if candle_1.get("direction") == "comprador" and (candle_2.get("direction") == "vendedor" or test.get("failedTest")):
            return "VENDA"
        if candle_1.get("direction") == "vendedor" and (candle_2.get("direction") == "comprador" or test.get("failedTest")):
            return "COMPRA"
        if self.obligation.get("kind") == "continuar subindo":
            return "COMPRA"
        if self.obligation.get("kind") == "continuar descendo":
            return "VENDA"
        return "NEUTRO"

    def _trade_plan(self, direction: str, candle_1, candle_2, candle_3) -> dict[str, Any]:
        offset = max(abs(_num(candle_3.get("close"))) * 0.0008, 0.0001)
        high = max(_num(candle_1.get("high")), _num(candle_2.get("high")), _num(candle_3.get("high")))
        low = min(_num(candle_1.get("low")), _num(candle_2.get("low")), _num(candle_3.get("low")))
        if direction == "VENDA":
            entry = _num(candle_3.get("low")) - offset
            stop = high + offset
            target = self._sell_target(entry)
        elif direction == "COMPRA":
            entry = _num(candle_3.get("high")) + offset
            stop = low - offset
            target = self._buy_target(entry)
        else:
            entry = _num(candle_3.get("close"))
            stop = low if entry >= self.fib["micro_50"]["level"] else high
            target = self.fib["micro_50"]["level"]
        risk = abs(entry - stop)
        reward = abs(target - entry)
        return {
            "entry": _round(entry),
            "stop": _round(stop),
            "target": _round(target),
            "riskReward": _round(reward / risk if risk else 0, 2),
            "invalidation": "Perda da regiao de teste ou fechamento contra o 50% micro.",
        }

    def _sell_target(self, entry: float) -> float:
        candidates = [_num(self.fib["micro_50"]["level"]), _num(self.fib["macro_50"]["level"]), _num(self.liquidity.get("buyer_stops_below"))]
        below = [item for item in candidates if item and item < entry]
        return max(below) if below else _num(self.liquidity.get("buyer_stops_below"), entry)

    def _buy_target(self, entry: float) -> float:
        candidates = [_num(self.fib["micro_50"]["level"]), _num(self.fib["macro_50"]["level"]), _num(self.liquidity.get("seller_stops_above"))]
        above = [item for item in candidates if item and item > entry]
        return min(above) if above else _num(self.liquidity.get("seller_stops_above"), entry)

    def _invalidations(self, target, test, direction: str, plan: dict[str, Any]) -> list[str]:
        invalidations = []
        if self.pullback.get("pullback_detected") and not target.get("consumedStops"):
            invalidations.append("Padrao ignorado: vindo de pullback")
        if not target.get("detected"):
            invalidations.append("Padrao fraco: sem alvo confirmado")
        if not test.get("detected"):
            invalidations.append("Padrao invalido: sem teste")
        if direction == "COMPRA" and self.movements["macro"]["trend"] == "baixa":
            invalidations.append("Padrao contra contexto macro")
        if direction == "VENDA" and self.movements["macro"]["trend"] == "alta":
            invalidations.append("Padrao contra contexto macro")
        if not self.liquidity.get("movement_has_fuel"):
            invalidations.append("Padrao sem liquidez relevante")
        if not target.get("regions"):
            invalidations.append("Padrao sem regiao institucional")
        if _num(plan.get("riskReward")) < 1.1:
            invalidations.append("Risco retorno improprio")
        if self.obligation.get("kind") == "sem combustivel":
            invalidations.append("Padrao visual sem contexto")
        return list(dict.fromkeys(invalidations))

    def _score(self, target, denial, test, direction: str, plan: dict[str, Any], invalidations: list[str]) -> int:
        score = 0
        if target.get("detected"):
            score += 20
        if denial.get("detected") and (denial.get("forceLoss") or denial.get("wickRejection")):
            score += 15
        if test.get("detected"):
            score += 15
        if target.get("regions"):
            score += 15
        if self.liquidity.get("movement_has_fuel") and self.liquidity.get("classification", {}).get("dominant") in {"alvo", "aceleracao", "manipulacao"}:
            score += 10
        if direction == "COMPRA" and self.movements["macro"]["trend"] == "alta" or direction == "VENDA" and self.movements["macro"]["trend"] == "baixa":
            score += 10
        if self.fib["macro_50"]["bias"] == self.fib["micro_50"]["bias"] and self.fib["macro_50"]["bias"] in {"compradora", "vendedora"}:
            score += 10
        if _num(plan.get("riskReward")) >= 1.3:
            score += 5
        score -= min(35, len(invalidations) * 7)
        return round(_clamp(score))

    def _classification(self, score: int) -> str:
        if score <= 39:
            return "Padrao fraco / ignorar"
        if score <= 59:
            return "Atencao"
        if score <= 74:
            return "Padrao possivel"
        if score <= 89:
            return "Padrao forte"
        return "Padrao institucional de alta confluencia"

    def _status(self, score: int, invalidations: list[str], test: dict[str, Any]) -> str:
        if invalidations and score < 60:
            return "IGNORAR"
        if score >= 75 and test.get("detected"):
            return "CONFIRMADO"
        if score >= 40:
            return "EM_FORMACAO"
        return "FRACO"

    def _region(self, target, candle_1, candle_3) -> dict[str, Any]:
        levels = [_num(item.get("level")) for item in target.get("regions", []) if _num(item.get("level"))]
        if levels:
            low = min(levels)
            high = max(levels)
        else:
            low = min(_num(candle_1.get("low")), _num(candle_3.get("low")))
            high = max(_num(candle_1.get("high")), _num(candle_3.get("high")))
        return {"low": _round(low), "high": _round(high), "mid": _round((low + high) / 2), "reading": "Regiao vale mais que a linha exata."}

    def _messages(self, target, denial, test, status, direction, plan, invalidations) -> list[str]:
        messages = [
            target["reading"],
            denial["reading"],
            test["reading"],
            f"Padrao de 3 candles {status.lower()} com direcao {direction}.",
        ]
        if direction in {"COMPRA", "VENDA"}:
            side = "acima da maxima" if direction == "COMPRA" else "abaixo da minima"
            messages.append(f"Entrada tecnica {side} do candle de teste; stop na extremidade do movimento.")
            messages.append(f"Alvo provavel em {plan['target']}; R/R {plan['riskReward']}.")
        messages.extend(invalidations[:4])
        return messages

    def _explanation(self, target, denial, test, direction, plan, status, invalidations) -> str:
        detail = " ".join(self._messages(target, denial, test, status, direction, plan, invalidations)[:5])
        return f"{detail} A leitura prioriza regiao, liquidez e movimento, nao desenho perfeito dos candles."


class InstitutionalContextEngine:
    def __init__(
        self,
        candles: pd.DataFrame,
        symbol: str = "BTCUSDT",
        timeframe: str = "15m",
        candles_by_timeframe: dict[str, pd.DataFrame] | None = None,
    ):
        self.df = self._prepare(candles)
        self.symbol = symbol
        self.timeframe = timeframe
        self.candles_by_timeframe = {
            key: self._prepare(value)
            for key, value in (candles_by_timeframe or {}).items()
            if value is not None and not value.empty
        }
        self.candles_by_timeframe.setdefault(timeframe, self.df)

    def analyze(self) -> dict[str, Any]:
        if len(self.df) < 30:
            return self._empty("Candles insuficientes para leitura institucional candle a candle.")

        candles = self._candle_flow()
        current = candles[-1]
        previous = candles[-2]
        swings = self._swings()
        movements = self._movements(swings)
        fractal = self._fractal_context(movements)
        fib = self._fibonacci(movements)
        liquidity = self._liquidity(swings, current)
        triggers = self._triggers(swings, liquidity, current)
        manipulation = self._manipulation(liquidity, triggers, current)
        pullback = self._pullback_failure(movements, fib, current)
        behavior = self._behavioral_reading(current, previous, movements, fib, liquidity, triggers, manipulation, pullback)
        liquidity["classification"] = self._classify_liquidity(liquidity, triggers, manipulation, current, behavior)
        obligation = self._price_obligation(current, previous, fib, triggers, liquidity, manipulation, pullback, behavior)
        context = self._context(movements, fib, obligation, manipulation, liquidity, fractal, behavior)
        risk = self._risk_plan(context, fib, liquidity, triggers, manipulation)
        three_candle = self._three_candle_pattern(candles, movements, fib, liquidity, triggers, manipulation, pullback, obligation, fractal, risk)
        raw_score = self._institutional_score(context, movements, fib, liquidity, triggers, manipulation, pullback, current, risk, fractal, behavior, three_candle)
        operation_blockers = self._operation_blockers(context, fib, liquidity, triggers, manipulation, pullback, obligation, risk, current, fractal, behavior, three_candle)
        score = self._calibrated_score(raw_score, operation_blockers)
        context["quality"] = score
        classification = self._score_classification(score)
        probabilities = self._probabilities(score, context, obligation, manipulation, pullback, behavior)
        confirmations, invalidations = self._confirmations(context, fib, liquidity, triggers, manipulation, pullback, obligation, risk, current, fractal, behavior, three_candle, operation_blockers)
        signal = self._signal_payload(context, score, classification, risk, obligation, triggers, liquidity, fib, confirmations, invalidations, behavior, three_candle, operation_blockers)
        chart = self._chart_marks(fib, liquidity, triggers, manipulation, risk, three_candle)
        narrative = self._narrative(context, current, previous, fib, liquidity, triggers, manipulation, pullback, obligation, risk, score, classification, fractal, behavior, three_candle)
        live = self._live_messages(current, previous, context, liquidity, triggers, manipulation, pullback, obligation, signal, fractal, behavior, three_candle)
        calibration = self._calibration_log(candles, score, liquidity, obligation, risk, signal)

        return {
            "success": True,
            "module": "operacional_leitura_grafica",
            "isolated": True,
            "methodology": "institucional_candle_a_candle_liquidez_50_stops_gatilhos",
            "excluded_modules": [
                "rsi", "macd", "medias_moveis", "bollinger", "suporte_resistencia_comum",
                "compra_venda_generica", "sinal_seco", "score_tecnico_padrao",
            ],
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "operacional_context": context,
            "operacional_score": score,
            "score_classification": classification,
            "probabilities": probabilities,
            "operacional_trend": {
                "bias": context["directional_bias"],
                "macro": movements["macro"]["trend"],
                "micro": movements["micro"]["trend"],
                "strength": score,
                "strength_label": classification,
                "structure": context["summary"],
            },
            "operacional_zones": self._zones_payload(fib, liquidity, triggers, risk),
            "operacional_liquidity": liquidity,
            "operacional_breakout": triggers["breakout"],
            "operacional_pullback": pullback,
            "operacional_fibonacci": fib,
            "institutional_map": {
                "macro_trend": movements["macro"],
                "micro_trend": movements["micro"],
                "fibonacci": fib,
                "liquidity": liquidity,
                "triggers": triggers,
                "manipulation": manipulation,
                "fractal": fractal,
                "behavior": behavior,
                "three_candle_pattern": three_candle,
                "price_obligation": obligation,
                "probabilities": probabilities,
                "operation_blockers": operation_blockers,
                "calibration": calibration,
            },
            "operacional_behavior": behavior,
            "three_candle_pattern": three_candle,
            "three_candle_pattern_score": three_candle.get("score", 0),
            "operation_blockers": operation_blockers,
            "operacional_calibration": calibration,
            "apostila_operacional": {
                "source": "Nova estrutura institucional",
                "reading": obligation["text"],
                "execution": {"mode": signal["status"], "direction": signal["direction"], "reason": signal["operational_reason"]},
                "no_trade_filters": invalidations if score < 60 else [],
            },
            "operacional_candle_flow": candles[-12:],
            "operacional_current_candle": current,
            "operacional_previous_candle": previous,
            "operacional_confirmations": confirmations,
            "operacional_invalidations": invalidations,
            "operacional_risk": risk,
            "operacional_trade_plan": risk.get("trade_plan", {}),
            "operacional_signal": signal,
            "operacional_live": live,
            "operacional_chart": chart,
            "timing": obligation["timing"],
            "operational_recommendation": signal["explanation"],
            "narrative": narrative,
            "disclaimer": "Leitura grafica educativa. Nao constitui recomendacao financeira.",
        }

    def context_only(self) -> dict[str, Any]:
        full = self.analyze()
        return {
            "success": full.get("success", False),
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "operacional_context": full.get("operacional_context"),
            "operacional_trend": full.get("operacional_trend"),
            "operacional_zones": full.get("operacional_zones"),
            "operacional_liquidity": full.get("operacional_liquidity"),
            "narrative": full.get("narrative"),
        }

    def candle_flow_only(self) -> dict[str, Any]:
        full = self.analyze()
        return {
            "success": full.get("success", False),
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "operacional_current_candle": full.get("operacional_current_candle"),
            "operacional_previous_candle": full.get("operacional_previous_candle"),
            "operacional_candle_flow": full.get("operacional_candle_flow", []),
            "narrative": full.get("narrative", [])[-4:],
        }

    def _prepare(self, candles: pd.DataFrame) -> pd.DataFrame:
        df = candles.copy()
        for column in ["open", "high", "low", "close", "volume"]:
            if column not in df.columns:
                df[column] = 0
            df[column] = pd.to_numeric(df[column], errors="coerce")
        return df.dropna(subset=["open", "high", "low", "close"]).tail(600)

    def _empty(self, message: str) -> dict[str, Any]:
        return {
            "success": False,
            "module": "operacional_leitura_grafica",
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "narrative": [message],
            "operacional_context": {"label": "Sem contexto", "quality": 0, "risk": "alto", "directional_bias": "NEUTRO"},
            "operacional_score": 0,
            "score_classification": "sem contexto",
            "operacional_candle_flow": [],
            "operacional_confirmations": [],
            "operacional_invalidations": [message],
            "operacional_risk": {"scenario_risk": "alto", "entry_quality": "baixa"},
            "operacional_signal": {"status": "sem contexto", "direction": "NAO OPERAR"},
            "operacional_live": [message],
            "operacional_chart": {"price_lines": [], "zones": [], "events": {}},
        }

    def _read_candle(self, index: int) -> dict[str, Any]:
        row = self.df.iloc[index]
        prev = self.df.iloc[index - 1] if index > 0 else row
        open_price = float(row.open)
        high = float(row.high)
        low = float(row.low)
        close = float(row.close)
        rng = max(high - low, abs(close) * 0.00001, 0.00001)
        body = abs(close - open_price)
        upper = high - max(open_price, close)
        lower = min(open_price, close) - low
        midpoint = low + rng * 0.5
        close_50 = "ACIMA_50" if close > midpoint else "ABAIXO_50" if close < midpoint else "NO_50"
        direction = "comprador" if close > open_price else "vendedor" if close < open_price else "neutro"
        broke_prev_high = high > float(prev.high)
        broke_prev_low = low < float(prev.low)
        close_above_prev_high = close > float(prev.high)
        close_below_prev_low = close < float(prev.low)
        violation_no_close = (
            (broke_prev_high and not close_above_prev_high)
            or (broke_prev_low and not close_below_prev_low)
        )
        vol_avg = float(self.df["volume"].iloc[max(0, index - 20): index + 1].mean() or 0)
        volume_ratio = float(row.volume) / vol_avg if vol_avg else 1.0

        body_pct = _pct(body, rng)
        upper_pct = _pct(upper, rng)
        lower_pct = _pct(lower, rng)
        strength = "forte" if body_pct >= 58 and close_50 != "NO_50" else "fraco" if body_pct <= 28 or violation_no_close else "moderado"
        continuation = (direction == "comprador" and close_above_prev_high) or (direction == "vendedor" and close_below_prev_low)
        failure = violation_no_close or (direction == "comprador" and close_50 == "ABAIXO_50") or (direction == "vendedor" and close_50 == "ACIMA_50")
        tags = []
        if close_50 == "ACIMA_50":
            tags.append("fechou acima de 50%")
        elif close_50 == "ABAIXO_50":
            tags.append("fechou abaixo de 50%")
        if continuation:
            tags.append("continuidade")
        if failure:
            tags.append("falha / violacao sem fechamento")
        if upper_pct >= 42:
            tags.append("pavio superior dominante")
        if lower_pct >= 42:
            tags.append("pavio inferior dominante")
        if volume_ratio >= 1.5:
            tags.append("volume acima da media")

        return {
            "time": int(self.df.index[index].timestamp()) if hasattr(self.df.index[index], "timestamp") else index,
            "direction": direction,
            "open": _round(open_price),
            "high": _round(high),
            "low": _round(low),
            "close": _round(close),
            "midpoint_50": _round(midpoint),
            "close_50": close_50,
            "body_strength": round(body_pct),
            "upper_wick_pct": round(upper_pct),
            "lower_wick_pct": round(lower_pct),
            "volume_ratio": _round(volume_ratio, 2),
            "broke_previous_high": broke_prev_high,
            "broke_previous_low": broke_prev_low,
            "closed_above_previous_high": close_above_prev_high,
            "closed_below_previous_low": close_below_prev_low,
            "violation_without_close": violation_no_close,
            "strength": strength,
            "continuation": continuation,
            "failure": failure,
            "tags": tags,
            "reading": self._candle_reading(direction, close_50, strength, continuation, failure, upper_pct, lower_pct),
        }

    def _candle_reading(self, direction, close_50, strength, continuation, failure, upper_pct, lower_pct) -> str:
        side = "compradora" if direction == "comprador" else "vendedora" if direction == "vendedor" else "neutra"
        if failure:
            return f"Candle {side} com falha: violou regiao, mas nao confirmou fechamento institucional."
        if continuation:
            return f"Candle {side} de continuidade, fechando {close_50.lower()} e mantendo obrigacao direcional."
        if upper_pct >= 42:
            return "Candle rejeitou topo; possivel defesa de vendedores ou captura de compradores."
        if lower_pct >= 42:
            return "Candle rejeitou fundo; possivel defesa de compradores ou captura de vendedores."
        return f"Candle {side} de forca {strength}, leitura dependente do 50% e da liquidez proxima."

    def _candle_flow(self) -> list[dict[str, Any]]:
        start = max(0, len(self.df) - 40)
        flow = [self._read_candle(i) for i in range(start, len(self.df))]
        for i, item in enumerate(flow):
            if i >= 1:
                prev = flow[i - 1]
                if item["continuation"] and prev["continuation"] and item["direction"] == prev["direction"]:
                    item["tags"].append("sequencia institucional")
                if item["failure"] and prev["continuation"]:
                    item["tags"].append("mudanca de contexto")
        return flow

    def _swings(self, window: int = 3) -> dict[str, list[dict[str, Any]]]:
        highs: list[dict[str, Any]] = []
        lows: list[dict[str, Any]] = []
        for i in range(window, len(self.df) - window):
            hi = float(self.df["high"].iloc[i])
            lo = float(self.df["low"].iloc[i])
            if hi >= float(self.df["high"].iloc[i - window:i + window + 1].max()):
                highs.append(self._swing_item(i, hi))
            if lo <= float(self.df["low"].iloc[i - window:i + window + 1].min()):
                lows.append(self._swing_item(i, lo))
        if not highs:
            highs.append(self._price_item(self.df["high"].tail(80).idxmax(), float(self.df["high"].tail(80).max())))
        if not lows:
            lows.append(self._price_item(self.df["low"].tail(80).idxmin(), float(self.df["low"].tail(80).min())))
        return {"highs": highs[-12:], "lows": lows[-12:]}

    def _swing_item(self, index: int, price: float) -> dict[str, Any]:
        idx = self.df.index[index] if isinstance(index, int) and 0 <= index < len(self.df) else self.df.index[-1]
        return self._price_item(idx, price)

    def _price_item(self, idx: Any, price: float) -> dict[str, Any]:
        return {"time": int(idx.timestamp()) if hasattr(idx, "timestamp") else 0, "price": _round(price)}

    def _movements(self, swings: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
        close = float(self.df["close"].iloc[-1])
        macro_df = self._macro_slice()
        micro_df = self.df.tail(28)
        macro = self._movement_payload(macro_df, close, swings, "macro")
        micro = self._movement_payload(micro_df, close, swings, "micro")
        return {"macro": macro, "micro": micro}

    def _fractal_context(self, movements: dict[str, Any]) -> dict[str, Any]:
        ordered = ["1m", "5m", "15m"]
        frames = {}
        for timeframe in ordered:
            data = self.candles_by_timeframe.get(timeframe)
            if data is None or len(data) < 12:
                continue
            scoped = data.tail(80)
            close = float(scoped["close"].iloc[-1])
            high = float(scoped["high"].max())
            low = float(scoped["low"].min())
            start = float(scoped["close"].iloc[0])
            midpoint = low + (high - low) * 0.5
            trend = "alta" if close > start and close > midpoint else "baixa" if close < start and close < midpoint else "equilibrio"
            frames[timeframe] = {
                "timeframe": timeframe,
                "trend": trend,
                "dominance": self._timeframe_weight(timeframe),
                "midpoint_50": _round(midpoint),
                "position_50": "acima" if close > midpoint else "abaixo" if close < midpoint else "decisao",
                "range": _round(high - low),
                "impulse_pct": _round(((close - start) / start * 100) if start else 0, 3),
            }

        if self.timeframe not in frames:
            frames[self.timeframe] = {
                "timeframe": self.timeframe,
                "trend": movements["micro"]["trend"],
                "dominance": self._timeframe_weight(self.timeframe),
                "midpoint_50": None,
                "position_50": "decisao",
                "range": movements["micro"]["range"],
                "impulse_pct": movements["micro"]["impulse_pct"],
            }

        directional = [item["trend"] for item in frames.values() if item["trend"] in {"alta", "baixa"}]
        aligned = bool(directional) and len(set(directional)) == 1 and len(directional) >= 2
        conflict = len(set(directional)) > 1
        dominant_frame = max(frames.values(), key=lambda item: item["dominance"], default=None)
        dominant_trend = dominant_frame["trend"] if dominant_frame else "equilibrio"
        return {
            "frames": frames,
            "aligned": aligned,
            "conflict": conflict,
            "dominant_timeframe": dominant_frame["timeframe"] if dominant_frame else self.timeframe,
            "dominant_trend": dominant_trend,
            "reading": self._fractal_reading(aligned, conflict, dominant_frame, frames),
        }

    def _timeframe_weight(self, timeframe: str) -> int:
        return {"1m": 1, "5m": 2, "15m": 3}.get(timeframe, 2)

    def _fractal_reading(self, aligned: bool, conflict: bool, dominant_frame: dict[str, Any] | None, frames: dict[str, Any]) -> str:
        if aligned:
            trend = next((item["trend"] for item in frames.values() if item["trend"] in {"alta", "baixa"}), "equilibrio")
            return f"Alinhamento fractal em {trend}; 1m/5m/15m favorecem continuidade se houver liquidez."
        if conflict:
            dom = dominant_frame or {}
            return f"Conflito fractal; {dom.get('timeframe', self.timeframe)} domina em {dom.get('trend', 'equilibrio')}."
        return "Fractal em equilibrio; leitura exige gatilho e aceitacao do preco."

    def _macro_slice(self) -> pd.DataFrame:
        if hasattr(self.df.index[-1], "date"):
            today = self.df.index[-1].date()
            day_df = self.df[self.df.index.map(lambda item: getattr(item, "date", lambda: None)() == today)]
            if len(day_df) >= 12:
                return day_df
        return self.df.tail(120)

    def _movement_payload(self, data: pd.DataFrame, close: float, swings: dict[str, list[dict[str, Any]]], scope: str) -> dict[str, Any]:
        high = float(data["high"].max())
        low = float(data["low"].min())
        start = float(data["close"].iloc[0])
        impulse_pct = ((close - start) / start * 100) if start else 0
        trend = "alta" if close > start and close > (high + low) / 2 else "baixa" if close < start and close < (high + low) / 2 else "equilibrio"
        return {
            "scope": scope,
            "high": _round(high),
            "low": _round(low),
            "start": _round(start),
            "close": _round(close),
            "trend": trend,
            "impulse_pct": _round(impulse_pct, 3),
            "range": _round(high - low),
            "last_high": swings["highs"][-1] if swings["highs"] else None,
            "last_low": swings["lows"][-1] if swings["lows"] else None,
        }

    def _fibonacci(self, movements: dict[str, Any]) -> dict[str, Any]:
        close = float(self.df["close"].iloc[-1])
        macro = self._fib_one(movements["macro"], close)
        micro = self._fib_one(movements["micro"], close)
        return {
            "macro_50": macro,
            "micro_50": micro,
            "reading": f"Macro: {macro['reading']} Micro: {micro['reading']}",
            "primary_bias": macro["bias"],
            "micro_bias": micro["bias"],
        }

    def _fib_one(self, movement: dict[str, Any], close: float) -> dict[str, Any]:
        high = float(movement["high"])
        low = float(movement["low"])
        midpoint = low + (high - low) * 0.5
        tolerance = max((high - low) * 0.015, abs(close) * 0.0005)
        distance = close - midpoint
        if abs(distance) <= tolerance:
            bias = "decisao"
            reading = "preco no 50%, regiao de decisao"
        elif distance > 0:
            bias = "compradora"
            reading = "preco acima dos 50%, pressao compradora"
        else:
            bias = "vendedora"
            reading = "preco abaixo dos 50%, pressao vendedora"
        returned = abs(float(self.df["low"].iloc[-1]) - midpoint) <= tolerance or abs(float(self.df["high"].iloc[-1]) - midpoint) <= tolerance
        broke = (float(self.df["close"].iloc[-2]) <= midpoint < close) or (float(self.df["close"].iloc[-2]) >= midpoint > close)
        return {
            "level": _round(midpoint),
            "bias": bias,
            "reading": reading,
            "return_to_50": bool(returned),
            "break_50": bool(broke),
            "distance_pct": _round((distance / close * 100) if close else 0, 3),
        }

    def _liquidity(self, swings: dict[str, list[dict[str, Any]]], current: dict[str, Any]) -> dict[str, Any]:
        close = float(current["close"])
        highs = swings["highs"]
        lows = swings["lows"]
        equal_highs = self._equal_levels(highs)
        equal_lows = self._equal_levels(lows)
        above = [item for item in highs if float(item["price"]) > close]
        below = [item for item in lows if float(item["price"]) < close]
        nearest_above = min(above, key=lambda item: abs(float(item["price"]) - close), default=(highs[-1] if highs else None))
        nearest_below = min(below, key=lambda item: abs(float(item["price"]) - close), default=(lows[-1] if lows else None))
        upper_price = float(nearest_above["price"]) if nearest_above else float(self.df["high"].tail(80).max())
        lower_price = float(nearest_below["price"]) if nearest_below else float(self.df["low"].tail(80).min())
        fuel_up = abs(upper_price - close)
        fuel_down = abs(close - lower_price)
        no_fuel = min(fuel_up, fuel_down) < max(abs(close) * 0.001, (float(self.df["high"].tail(40).max()) - float(self.df["low"].tail(40).min())) * 0.06)
        return {
            "upper_zone": _round(upper_price),
            "lower_zone": _round(lower_price),
            "liquidity_above": {"price": _round(upper_price), "meaning": "liquidez acima de topo; stops de vendedores"},
            "liquidity_below": {"price": _round(lower_price), "meaning": "liquidez abaixo de fundo; stops de compradores"},
            "seller_stops_above": _round(upper_price),
            "buyer_stops_below": _round(lower_price),
            "equal_highs": equal_highs,
            "equal_lows": equal_lows,
            "institutional_zones": self._institutional_zones(upper_price, lower_price, equal_highs, equal_lows),
            "fuel_target": "liquidez acima" if fuel_up > fuel_down else "liquidez abaixo",
            "movement_has_fuel": not no_fuel,
            "induced_region": self._induced_region(highs, lows, close),
            "sweep": False,
            "sweep_side": "nenhum",
            "reading": "Movimento com combustivel ate a proxima liquidez." if not no_fuel else "Movimento sem combustivel claro; preco perto de liquidez ja consumida.",
        }

    def _equal_levels(self, points: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if len(points) < 2:
            return []
        prices = [float(item["price"]) for item in points[-8:]]
        tolerance = max((max(prices) - min(prices)) * 0.035, abs(prices[-1]) * 0.0007)
        levels = []
        used = set()
        for index, price in enumerate(prices):
            if index in used:
                continue
            cluster = [other for other in prices[index:] if abs(other - price) <= tolerance]
            if len(cluster) >= 2:
                level = sum(cluster) / len(cluster)
                levels.append({"price": _round(level), "touches": len(cluster), "type": "equal_level"})
                used.update(i for i, other in enumerate(prices) if abs(other - price) <= tolerance)
        return levels[:3]

    def _institutional_zones(self, upper: float, lower: float, equal_highs: list[dict[str, Any]], equal_lows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        zones = [
            {"type": "buy_side_liquidity", "label": "Liquidez compradora acima", "price": _round(upper)},
            {"type": "sell_side_liquidity", "label": "Liquidez vendedora abaixo", "price": _round(lower)},
        ]
        zones.extend({"type": "equal_highs", "label": "Equal highs / stops", "price": item["price"], "touches": item["touches"]} for item in equal_highs)
        zones.extend({"type": "equal_lows", "label": "Equal lows / stops", "price": item["price"], "touches": item["touches"]} for item in equal_lows)
        return zones

    def _induced_region(self, highs, lows, close: float) -> dict[str, Any]:
        last_high = highs[-1] if highs else None
        last_low = lows[-1] if lows else None
        if last_high and close > float(last_high["price"]):
            return {"side": "vendedores induzidos", "price": last_high["price"], "description": "Rompimento de topo pode ter acionado stops de vendedores."}
        if last_low and close < float(last_low["price"]):
            return {"side": "compradores induzidos", "price": last_low["price"], "description": "Rompimento de fundo pode ter acionado stops de compradores."}
        return {"side": "sem inducao dominante", "price": None, "description": "Preco ainda dentro das ultimas liquidez relevantes."}

    def _classify_liquidity(self, liquidity, triggers, manipulation, current, behavior) -> dict[str, Any]:
        consumed = []
        pending = []
        if current["high"] >= liquidity["seller_stops_above"]:
            consumed.append({"side": "acima", "price": liquidity["seller_stops_above"], "role": "liquidez consumida"})
        else:
            pending.append({"side": "acima", "price": liquidity["seller_stops_above"], "role": "liquidez pendente"})
        if current["low"] <= liquidity["buyer_stops_below"]:
            consumed.append({"side": "abaixo", "price": liquidity["buyer_stops_below"], "role": "liquidez consumida"})
        else:
            pending.append({"side": "abaixo", "price": liquidity["buyer_stops_below"], "role": "liquidez pendente"})

        if manipulation.get("detected"):
            dominant = "manipulacao"
            quality = "armadilha"
        elif triggers.get("acceleration") and liquidity.get("movement_has_fuel"):
            dominant = "aceleracao"
            quality = "forte"
        elif behavior.get("absorption"):
            dominant = "defesa"
            quality = "defensiva"
        elif pending:
            dominant = "alvo"
            quality = "boa" if liquidity.get("movement_has_fuel") else "fraca"
        else:
            dominant = "consumida"
            quality = "insuficiente"

        return {
            "dominant": dominant,
            "quality": quality,
            "target": pending[0] if pending else None,
            "acceleration": triggers.get("stop_activation_zone") if triggers.get("acceleration") else None,
            "defense": liquidity.get("buyer_stops_below") if current.get("lower_wick_pct", 0) >= 42 else liquidity.get("seller_stops_above") if current.get("upper_wick_pct", 0) >= 42 else None,
            "manipulation": manipulation.get("zone") if manipulation.get("detected") else None,
            "pending": pending,
            "consumed": consumed,
            "reading": self._liquidity_classification_reading(dominant, quality),
        }

    def _liquidity_classification_reading(self, dominant: str, quality: str) -> str:
        readings = {
            "manipulacao": "Liquidez virou armadilha; preco consumiu contraparte e voltou.",
            "aceleracao": "Liquidez de aceleracao detectada; stops podem alimentar continuidade.",
            "defesa": "Regiao de defesa institucional; pavio indica absorcao ou contraparte forte.",
            "alvo": "Liquidez pendente funciona como alvo e combustivel potencial.",
            "consumida": "Liquidez principal ja foi consumida; movimento pode perder combustivel.",
        }
        return f"{readings.get(dominant, 'Liquidez em leitura.')} Qualidade: {quality}."

    def _triggers(self, swings, liquidity, current) -> dict[str, Any]:
        highs = swings["highs"]
        lows = swings["lows"]
        relevant_high = float(highs[-1]["price"]) if highs else float(self.df["high"].tail(20).max())
        relevant_low = float(lows[-1]["price"]) if lows else float(self.df["low"].tail(20).min())
        higher_low = len(lows) >= 2 and float(lows[-1]["price"]) > float(lows[-2]["price"])
        lower_high = len(highs) >= 2 and float(highs[-1]["price"]) < float(highs[-2]["price"])
        close = float(current["close"])
        broke_high = close > relevant_high
        broke_low = close < relevant_low
        active = "rompimento de maxima relevante" if broke_high else "rompimento de minima relevante" if broke_low else "aguardando gatilho"
        acceleration = current["body_strength"] >= 58 and (broke_high or broke_low)
        return {
            "active": active,
            "direction": "alta" if broke_high else "baixa" if broke_low else "neutra",
            "relevant_high": _round(relevant_high),
            "relevant_low": _round(relevant_low),
            "higher_low": higher_low,
            "lower_high": lower_high,
            "stop_activation_zone": liquidity["seller_stops_above"] if broke_high else liquidity["buyer_stops_below"] if broke_low else None,
            "acceleration": acceleration,
            "breakout": {
                "valid_breakout": bool((broke_high or broke_low) and current["strength"] == "forte"),
                "direction": "alta" if broke_high else "baixa" if broke_low else "nenhuma",
                "false_breakout": False,
                "reading": "Gatilho acionado com aceleracao." if acceleration else "Gatilho ainda sem confirmacao de aceleracao.",
            },
        }

    def _manipulation(self, liquidity, triggers, current) -> dict[str, Any]:
        high = float(current["high"])
        low = float(current["low"])
        close = float(current["close"])
        upper = float(liquidity["upper_zone"])
        lower = float(liquidity["lower_zone"])
        upper_sweep = high > upper and close < upper
        lower_sweep = low < lower and close > lower
        induced_buyers = high > upper and current["violation_without_close"]
        induced_sellers = low < lower and current["violation_without_close"]
        side = "compradores induzidos" if upper_sweep or induced_buyers else "vendedores induzidos" if lower_sweep or induced_sellers else "nenhuma"
        detected = upper_sweep or lower_sweep or induced_buyers or induced_sellers
        liquidity["sweep"] = bool(upper_sweep or lower_sweep)
        liquidity["sweep_side"] = "superior" if upper_sweep else "inferior" if lower_sweep else "nenhum"
        return {
            "detected": bool(detected),
            "type": "sweep de liquidez" if upper_sweep or lower_sweep else "inducao sem fechamento" if detected else "nenhuma",
            "side": side,
            "zone": _round(upper if upper_sweep or induced_buyers else lower if lower_sweep or induced_sellers else close),
            "fuel": "sem combustivel" if not liquidity["movement_has_fuel"] else "com combustivel",
            "reading": "Preco capturou liquidez e voltou; risco de armadilha institucional." if detected else "Sem manipulacao objetiva no candle atual.",
        }

    def _behavioral_reading(self, current, previous, movements, fib, liquidity, triggers, manipulation, pullback) -> dict[str, Any]:
        macro = movements["macro"]
        micro = movements["micro"]
        same_direction = macro["trend"] == micro["trend"] and macro["trend"] in {"alta", "baixa"}
        renewed_high = current["closed_above_previous_high"]
        renewed_low = current["closed_below_previous_low"]
        no_renewal = (
            micro["trend"] == "alta" and not renewed_high
            or micro["trend"] == "baixa" and not renewed_low
        )
        acceleration = bool(triggers.get("acceleration") or current["volume_ratio"] >= 1.45 and current["body_strength"] >= 58)
        deceleration = bool(current["body_strength"] <= 30 or current["volume_ratio"] < 0.72 or no_renewal)
        exhaustion = bool((current["upper_wick_pct"] >= 48 and micro["trend"] == "alta") or (current["lower_wick_pct"] >= 48 and micro["trend"] == "baixa"))
        absorption = bool(current["upper_wick_pct"] >= 42 or current["lower_wick_pct"] >= 42)
        artificial = bool((not liquidity.get("movement_has_fuel") and current["continuation"]) or manipulation.get("detected"))
        continuity_quality = "saudavel" if same_direction and current["continuation"] and liquidity.get("movement_has_fuel") and not artificial else "artificial" if artificial else "fraca" if deceleration or no_renewal else "em construcao"
        intention = self._movement_intention(macro, micro, fib, liquidity, triggers, manipulation)
        readings = [
            intention,
            "Continuidade saudavel." if continuity_quality == "saudavel" else "Movimento sem continuidade limpa." if continuity_quality == "fraca" else "Continuidade artificial; exige cautela." if continuity_quality == "artificial" else "Continuidade ainda em construcao.",
        ]
        if no_renewal:
            readings.append("Subiu sem romper maxima ou desceu sem romper minima; estrutura perdendo forca.")
        if absorption:
            readings.append("Absorcao institucional sugerida pelo pavio dominante.")
        if exhaustion:
            readings.append("Exaustao detectada; movimento pode estar realizando lucro ou encontrando defesa.")
        if acceleration:
            readings.append("Aceleracao operacional detectada.")
        if manipulation.get("detected"):
            readings.append("Possivel manipulacao institucional.")
        if pullback.get("pullback_failure"):
            readings.append("Falha de pullback institucional.")
        return {
            "intention": intention,
            "force_real": self._force_real(current, liquidity, same_direction),
            "loss_of_strength": bool(no_renewal or deceleration or exhaustion),
            "continuity_quality": continuity_quality,
            "exhaustion": exhaustion,
            "absorption": absorption,
            "induction": manipulation.get("side", "nenhuma"),
            "acceleration": acceleration,
            "deceleration": deceleration,
            "artificial_movement": artificial,
            "acceptance": current["close_50"],
            "readings": readings,
        }

    def _movement_intention(self, macro, micro, fib, liquidity, triggers, manipulation) -> str:
        if manipulation.get("detected"):
            return "Intencao aparente: induzir entradas e capturar liquidez."
        if triggers.get("direction") in {"alta", "baixa"}:
            return "Intencao aparente: acelerar apos gatilho estrutural."
        if fib["macro_50"]["bias"] == fib["micro_50"]["bias"] and fib["macro_50"]["bias"] in {"compradora", "vendedora"}:
            return f"Intencao aparente: manter pressao {fib['macro_50']['bias']} respeitando o 50%."
        if not liquidity.get("movement_has_fuel"):
            return "Intencao aparente: movimento sem combustivel suficiente."
        if macro["trend"] != micro["trend"]:
            return "Intencao aparente: micro movimento testando o macro."
        return f"Intencao aparente: buscar {liquidity['fuel_target']}."

    def _force_real(self, current, liquidity, same_direction: bool) -> str:
        if current["strength"] == "forte" and current["continuation"] and liquidity.get("movement_has_fuel") and same_direction:
            return "forte"
        if current["strength"] == "fraco" or not liquidity.get("movement_has_fuel"):
            return "fraca"
        return "moderada"

    def _three_candle_pattern(self, candles, movements, fib, liquidity, triggers, manipulation, pullback, obligation, fractal, risk) -> dict[str, Any]:
        return ThreeCandlePatternEngine(
            candles=candles,
            movements=movements,
            fib=fib,
            liquidity=liquidity,
            triggers=triggers,
            manipulation=manipulation,
            pullback=pullback,
            obligation=obligation,
            fractal=fractal,
            risk=risk,
        ).analyze()

    def _pullback_failure(self, movements, fib, current) -> dict[str, Any]:
        closes = self.df["close"].tail(16)
        initial_up = float(closes.iloc[6]) > float(closes.iloc[0])
        initial_down = float(closes.iloc[6]) < float(closes.iloc[0])
        micro_50 = float(fib["micro_50"]["level"])
        returned = fib["micro_50"]["return_to_50"]
        close = float(current["close"])
        attempted_continue = (initial_up and float(self.df["high"].iloc[-1]) > float(self.df["high"].tail(8).iloc[:-1].max())) or (initial_down and float(self.df["low"].iloc[-1]) < float(self.df["low"].tail(8).iloc[:-1].min()))
        failed = (initial_up and returned and close < micro_50) or (initial_down and returned and close > micro_50)
        opposite_break = (initial_up and current["closed_below_previous_low"]) or (initial_down and current["closed_above_previous_high"])
        return {
            "initial_move": "alta" if initial_up else "baixa" if initial_down else "neutro",
            "pullback_detected": bool(returned),
            "attempted_continuation": bool(attempted_continue),
            "pullback_failure": bool(failed or opposite_break),
            "opposite_break": bool(opposite_break),
            "reading": "Falha de pullback com rompimento contrario; possivel reversao institucional." if failed or opposite_break else "Pullback ainda sem falha confirmada." if returned else "Sem pullback tecnico no 50% micro.",
        }

    def _price_obligation(self, current, previous, fib, triggers, liquidity, manipulation, pullback, behavior) -> dict[str, Any]:
        return PriceObligationEngine().evaluate(current, fib, triggers, liquidity, manipulation, pullback, behavior)

    def _context(self, movements, fib, obligation, manipulation, liquidity, fractal, behavior) -> dict[str, Any]:
        macro = movements["macro"]["trend"]
        micro = movements["micro"]["trend"]
        if macro == "alta" and micro == "alta":
            bias = "COMPRA CONTEXTUAL"
        elif macro == "baixa" and micro == "baixa":
            bias = "VENDA CONTEXTUAL"
        elif manipulation["detected"]:
            bias = "MANIPULACAO"
        else:
            bias = "NEUTRO"
        risk = "alto" if manipulation["detected"] or obligation["kind"] == "sem combustivel" or fractal.get("conflict") or behavior.get("artificial_movement") else "moderado"
        label = "Confluencia institucional" if bias in {"COMPRA CONTEXTUAL", "VENDA CONTEXTUAL"} and not fractal.get("conflict") and behavior.get("continuity_quality") != "artificial" else "Movimento artificial" if behavior.get("artificial_movement") else "Conflito fractal" if fractal.get("conflict") else "Regiao de decisao" if obligation["kind"] == "decidir no pullback" else "Sem contexto"
        return {
            "label": label,
            "directional_bias": bias,
            "quality": 0,
            "risk": risk,
            "macro_trend": macro,
            "micro_trend": micro,
            "fractal_alignment": "alinhado" if fractal.get("aligned") else "conflito" if fractal.get("conflict") else "equilibrio",
            "dominant_timeframe": fractal.get("dominant_timeframe"),
            "dominant_timeframe_trend": fractal.get("dominant_trend"),
            "behavioral_intention": behavior.get("intention"),
            "force_real": behavior.get("force_real"),
            "continuity_quality": behavior.get("continuity_quality"),
            "position_50": f"Macro {fib['macro_50']['bias']} / Micro {fib['micro_50']['bias']}",
            "summary": f"Macro {macro}, micro {micro}, obrigacao: {obligation['kind']}.",
        }

    def _risk_plan(self, context, fib, liquidity, triggers, manipulation) -> dict[str, Any]:
        close = float(self.df["close"].iloc[-1])
        direction = context["directional_bias"]
        offset = self._offset(close)
        if direction == "COMPRA CONTEXTUAL":
            entry = max(float(triggers["relevant_high"]), close)
            stop = min(float(fib["micro_50"]["level"]), float(liquidity["buyer_stops_below"])) - offset
            target1 = float(liquidity["seller_stops_above"])
            target2 = target1 + abs(target1 - entry)
        elif direction == "VENDA CONTEXTUAL":
            entry = min(float(triggers["relevant_low"]), close)
            stop = max(float(fib["micro_50"]["level"]), float(liquidity["seller_stops_above"])) + offset
            target1 = float(liquidity["buyer_stops_below"])
            target2 = target1 - abs(entry - target1)
        else:
            entry = close
            stop = float(liquidity["buyer_stops_below"]) if close >= float(fib["micro_50"]["level"]) else float(liquidity["seller_stops_above"])
            target1 = float(liquidity["seller_stops_above"]) if close >= float(fib["micro_50"]["level"]) else float(liquidity["buyer_stops_below"])
            target2 = target1
        risk = abs(entry - stop)
        reward = abs(target1 - entry)
        rr = reward / risk if risk else 0
        scenario_risk = "alto" if rr < 1.1 or manipulation["detected"] else "moderado" if rr < 1.8 else "baixo"
        best_entry = "teste do 50% micro" if fib["micro_50"]["return_to_50"] else "rompimento e reteste do gatilho ativo"
        return {
            "reference_price": _round(close),
            "entry": _round(entry),
            "technical_stop": _round(stop),
            "partial_target": _round(target1),
            "take_profit_1": _round(target1),
            "take_profit_2": _round(target2),
            "risk_reward": _round(rr, 2),
            "scenario_risk": scenario_risk,
            "entry_quality": "alta" if rr >= 1.8 and not manipulation["detected"] else "media" if rr >= 1.1 else "baixa",
            "best_entry_region": best_entry,
            "invalidation_region": _round(stop),
            "invalidation": "Fechamento contra o 50% micro ou perda da zona manipulada/gatilho.",
            "trade_plan": {
                "entry": _round(entry),
                "stop": _round(stop),
                "take_profit_1": _round(target1),
                "take_profit_2": _round(target2),
                "best_entry_region": best_entry,
                "invalidation_region": _round(stop),
            },
        }

    def _offset(self, price: float) -> float:
        symbol = self.symbol.upper()
        if symbol.startswith("WIN"):
            return 25.0
        if symbol.startswith("WDO"):
            return 1.0
        return max(abs(price) * 0.0008, 0.0001)

    def _institutional_score(self, context, movements, fib, liquidity, triggers, manipulation, pullback, current, risk, fractal, behavior, three_candle) -> int:
        score = 12
        if movements["macro"]["trend"] in {"alta", "baixa"}:
            score += 16
        if movements["micro"]["trend"] == movements["macro"]["trend"] and movements["micro"]["trend"] in {"alta", "baixa"}:
            score += 16
        elif movements["micro"]["trend"] in {"alta", "baixa"} and movements["macro"]["trend"] in {"alta", "baixa"}:
            score -= 12
        if liquidity["movement_has_fuel"]:
            score += 14
        else:
            score -= 16
        liquidity_quality = (liquidity.get("classification") or {}).get("quality")
        if liquidity_quality in {"forte", "boa"}:
            score += 8
        elif liquidity_quality in {"fraca", "insuficiente"}:
            score -= 10
        if triggers["direction"] in {"alta", "baixa"} or triggers["higher_low"] or triggers["lower_high"]:
            score += 10
        if current["strength"] == "forte" and not current.get("violation_without_close"):
            score += 14
        elif current.get("violation_without_close"):
            score -= 18
        if current.get("close_50") in {"ACIMA_50", "ABAIXO_50"}:
            score += 6
        if behavior.get("force_real") == "forte":
            score += 12
        elif behavior.get("force_real") == "fraca":
            score -= 12
        if behavior.get("continuity_quality") == "saudavel":
            score += 12
        elif behavior.get("continuity_quality") in {"fraca", "artificial"}:
            score -= 14
        if behavior.get("absorption"):
            score -= 4
        if behavior.get("exhaustion"):
            score -= 10
        if fib["macro_50"]["bias"] == fib["micro_50"]["bias"] and fib["macro_50"]["bias"] in {"compradora", "vendedora"}:
            score += 14
        if fractal.get("aligned"):
            score += 14
        if fractal.get("conflict"):
            score -= 18
        if manipulation["detected"]:
            score -= 18
        if pullback["pullback_failure"]:
            score -= 16
        elif pullback["pullback_detected"]:
            score += 6
        if risk["risk_reward"] >= 1.8:
            score += 12
        elif risk["risk_reward"] < 1.1:
            score -= 18
        pattern_score = _num(three_candle.get("score"))
        if three_candle.get("status") == "CONFIRMADO" and pattern_score >= 75:
            score += 10
        elif three_candle.get("status") == "IGNORAR":
            score -= 12
        return round(_clamp(score))

    def _operation_blockers(self, context, fib, liquidity, triggers, manipulation, pullback, obligation, risk, current, fractal, behavior, three_candle) -> list[str]:
        blockers = []
        if context.get("directional_bias") == "NEUTRO" or context.get("label") == "Sem contexto":
            blockers.append("Operacao bloqueada: sem contexto")
        if not liquidity.get("movement_has_fuel") or obligation.get("kind") == "sem combustivel":
            blockers.append("Operacao bloqueada: sem combustivel")
        if _num(risk.get("risk_reward")) < 1.1 or _num(risk.get("technical_stop")) == _num(risk.get("take_profit_1")):
            blockers.append("Operacao bloqueada: risco improprio")
        if current.get("violation_without_close") or (
            triggers.get("direction") in {"alta", "baixa"} and not triggers.get("breakout", {}).get("valid_breakout")
        ):
            blockers.append("Operacao bloqueada: rompimento sem aceitacao")
        if fractal.get("conflict") and context.get("dominant_timeframe_trend") not in {context.get("micro_trend"), "equilibrio"}:
            blockers.append("Operacao bloqueada: conflito forte entre timeframes")
        if behavior.get("artificial_movement"):
            blockers.append("Operacao bloqueada: movimento artificial")
        if three_candle.get("status") == "IGNORAR" or "Padrao visual sem contexto" in (three_candle.get("invalidations") or []):
            blockers.append("Operacao bloqueada: padrao apenas visual")
        if manipulation.get("detected") and not liquidity.get("movement_has_fuel"):
            blockers.append("Operacao bloqueada: sweep sem continuidade")
        return list(dict.fromkeys(blockers))

    def _calibrated_score(self, score: int, blockers: list[str]) -> int:
        if not blockers:
            return round(_clamp(score))
        penalty = min(42, 12 + (len(blockers) - 1) * 6)
        return round(_clamp(score - penalty))

    def _score_classification(self, score: int) -> str:
        if score <= 39:
            return "sem contexto"
        if score <= 59:
            return "atencao"
        if score <= 74:
            return "possivel oportunidade"
        if score <= 89:
            return "oportunidade forte"
        return "confluencia institucional alta"

    def _probabilities(self, score, context, obligation, manipulation, pullback, behavior):
        continuation = score
        reversal = 100 - score
        if obligation["kind"] in {"continuar subindo", "continuar descendo", "buscar liquidez"}:
            continuation += 8
            reversal -= 8
        if manipulation["detected"] or pullback["pullback_failure"]:
            continuation -= 18
            reversal += 18
        if behavior.get("loss_of_strength") or behavior.get("exhaustion"):
            continuation -= 12
            reversal += 12
        if behavior.get("continuity_quality") == "saudavel":
            continuation += 10
            reversal -= 10
        return {
            "continuation": round(_clamp(continuation)),
            "reversal": round(_clamp(reversal)),
        }

    def _confirmations(self, context, fib, liquidity, triggers, manipulation, pullback, obligation, risk, current, fractal, behavior, three_candle, operation_blockers=None):
        operation_blockers = operation_blockers or []
        confirmations = []
        invalidations = []
        if context["macro_trend"] == context["micro_trend"] and context["macro_trend"] in {"alta", "baixa"}:
            confirmations.append("Macro e micro movimento apontam para a mesma direcao.")
        if fib["macro_50"]["bias"] == fib["micro_50"]["bias"] and fib["macro_50"]["bias"] in {"compradora", "vendedora"}:
            confirmations.append("50% macro e 50% micro alinhados.")
        if liquidity["movement_has_fuel"]:
            confirmations.append("Ha liquidez proxima para servir de combustivel.")
        if liquidity.get("equal_highs"):
            confirmations.append("Equal highs mapeados como liquidez acima.")
        if liquidity.get("equal_lows"):
            confirmations.append("Equal lows mapeados como liquidez abaixo.")
        if fractal.get("aligned"):
            confirmations.append(fractal.get("reading"))
        if triggers["acceleration"]:
            confirmations.append("Gatilho rompeu com candle de aceleracao.")
        if behavior.get("continuity_quality") == "saudavel":
            confirmations.append("Continuidade saudavel com contexto, aceitacao e liquidez.")
        if behavior.get("force_real") == "forte":
            confirmations.append("Forca real do movimento validada por candle, contexto e combustivel.")
        if three_candle.get("status") in {"CONFIRMADO", "EM_FORMACAO"}:
            confirmations.append(f"Padrao de 3 candles: {three_candle.get('classification')}.")
        if current["strength"] == "forte":
            confirmations.append("Candle atual tem corpo e fechamento institucional.")
        if risk["risk_reward"] >= 1.8:
            confirmations.append("Risco/retorno favorece acompanhamento.")
        if manipulation["detected"]:
            invalidations.append(manipulation["reading"])
        if pullback["pullback_failure"]:
            invalidations.append(pullback["reading"])
        if not liquidity["movement_has_fuel"]:
            invalidations.append("Movimento sem combustivel claro ate nova liquidez.")
        if fib["macro_50"]["bias"] != fib["micro_50"]["bias"]:
            invalidations.append("50% macro e micro em conflito.")
        if fractal.get("conflict"):
            invalidations.append(fractal.get("reading"))
        if risk["risk_reward"] < 1.1:
            invalidations.append("Risco/retorno insuficiente para entrada contextual.")
        if current["violation_without_close"]:
            invalidations.append("Candle violou maxima/minima, mas nao confirmou fechamento.")
        if behavior.get("loss_of_strength"):
            invalidations.append("Estrutura perdendo forca; preco precisa renovar maxima/minima.")
        if behavior.get("artificial_movement"):
            invalidations.append("Movimento artificial ou sem combustivel suficiente.")
        if obligation.get("invalidated"):
            invalidations.append("Obrigacao do preco invalidada pelo fechamento atual.")
        invalidations.extend(three_candle.get("invalidations") or [])
        invalidations.extend(operation_blockers)
        return confirmations[:10], invalidations[:10]

    def _signal_payload(self, context, score, classification, risk, obligation, triggers, liquidity, fib, confirmations, invalidations, behavior, three_candle, operation_blockers=None):
        operation_blockers = operation_blockers or []
        direction = context["directional_bias"]
        if operation_blockers:
            status = "operacao bloqueada"
        elif score < 60 or invalidations:
            status = "aguardar contexto"
        elif score < 75:
            status = "alerta de possivel entrada"
        else:
            status = "entrada contextual em observacao"
        explanation = (
            f"{status}: {obligation['text']} Liquidez alvo: {liquidity['fuel_target']}. "
            f"Gatilho: {triggers['active']}. 50%: {fib['reading']} Stop provavel em {risk['invalidation_region']}."
        )
        return {
            "asset": self.symbol,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "direction": direction,
            "status": status,
            "score": score,
            "classification": classification,
            "entry": risk["entry"],
            "stop": risk["technical_stop"],
            "take_profit_1": risk["take_profit_1"],
            "take_profit_2": risk["take_profit_2"],
            "risk_reward": risk["risk_reward"],
            "liquidity_target": liquidity["fuel_target"],
            "trigger": triggers["active"],
            "behavior": behavior.get("continuity_quality"),
            "price_obligation_status": obligation.get("status"),
            "operation_blockers": operation_blockers,
            "blocked": bool(operation_blockers),
            "three_candle_pattern": {
                "status": three_candle.get("status"),
                "score": three_candle.get("score"),
                "classification": three_candle.get("classification"),
            },
            "operational_reason": explanation,
            "explanation": explanation,
            "confirmation": confirmations,
            "invalidation": invalidations or [risk["invalidation"]],
        }

    def _calibration_log(self, candles, score, liquidity, obligation, risk, signal) -> dict[str, Any]:
        records = []
        flow = candles[-12:]
        for index, candle in enumerate(flow):
            next_candle = flow[index + 1] if index + 1 < len(flow) else None
            predicted = self._predicted_move(candle, liquidity, obligation)
            realized = self._realized_move(candle, next_candle)
            matched = bool(next_candle and predicted == realized and predicted in {"alta", "baixa"})
            records.append({
                "time": candle.get("time"),
                "candle": candle.get("reading"),
                "score": self._candle_calibration_score(candle, liquidity),
                "liquidity": liquidity.get("classification", {}).get("dominant") or liquidity.get("fuel_target"),
                "price_obligation": obligation.get("kind"),
                "entry": signal.get("entry") if index == len(flow) - 1 else None,
                "stop": signal.get("stop") if index == len(flow) - 1 else None,
                "target": signal.get("take_profit_1") if index == len(flow) - 1 else None,
                "predicted": predicted,
                "realized": realized,
                "result": "alinhou" if matched else "divergiu" if next_candle else "aguardando proximo candle",
            })
        compared = [item for item in records if item["result"] in {"alinhou", "divergiu"}]
        hits = sum(1 for item in compared if item["result"] == "alinhou")
        return {
            "mode": "calibracao_operacional",
            "description": "Registro candle a candle para comparar leitura prevista contra movimento real.",
            "current_score": score,
            "records": records,
            "summary": {
                "samples": len(compared),
                "aligned": hits,
                "diverged": len(compared) - hits,
                "alignment_rate": round(_pct(hits, len(compared))) if compared else 0,
            },
        }

    def _predicted_move(self, candle, liquidity, obligation) -> str:
        kind = obligation.get("kind")
        if kind == "continuar subindo":
            return "alta"
        if kind == "continuar descendo":
            return "baixa"
        if candle.get("direction") == "comprador" and candle.get("close_50") == "ACIMA_50" and liquidity.get("movement_has_fuel"):
            return "alta"
        if candle.get("direction") == "vendedor" and candle.get("close_50") == "ABAIXO_50" and liquidity.get("movement_has_fuel"):
            return "baixa"
        return "neutro"

    def _realized_move(self, candle, next_candle) -> str:
        if not next_candle:
            return "pendente"
        close = _num(candle.get("close"))
        next_close = _num(next_candle.get("close"))
        tolerance = max(abs(close) * 0.0002, 0.00001)
        if next_close > close + tolerance:
            return "alta"
        if next_close < close - tolerance:
            return "baixa"
        return "neutro"

    def _candle_calibration_score(self, candle, liquidity) -> int:
        score = 30
        if candle.get("strength") == "forte":
            score += 22
        if candle.get("continuation"):
            score += 18
        if candle.get("close_50") in {"ACIMA_50", "ABAIXO_50"}:
            score += 10
        if liquidity.get("movement_has_fuel"):
            score += 12
        if candle.get("violation_without_close"):
            score -= 25
        if candle.get("failure"):
            score -= 12
        return round(_clamp(score))

    def _chart_marks(self, fib, liquidity, triggers, manipulation, risk, three_candle):
        zones = []
        if manipulation["detected"]:
            zones.append({
                "label": "Manipulacao",
                "type": "manipulation",
                "low": manipulation["zone"] - self._offset(float(manipulation["zone"])),
                "high": manipulation["zone"] + self._offset(float(manipulation["zone"])),
                "color": "#F97316",
                "opacity": 0.28,
                "active": True,
            })
        zones.append({
            "label": "Zona Entrada",
            "type": "entry",
            "low": min(float(risk["entry"]), float(fib["micro_50"]["level"])),
            "high": max(float(risk["entry"]), float(fib["micro_50"]["level"])),
            "color": "#38BDF8",
            "opacity": 0.18,
            "active": True,
        })
        pattern_region = three_candle.get("region") or {}
        if three_candle.get("detected") and pattern_region.get("low") and pattern_region.get("high"):
            zones.append({
                "label": "Padrao 3C Regiao",
                "type": "three_candle_region",
                "low": pattern_region["low"],
                "high": pattern_region["high"],
                "color": "#D4AF37",
                "opacity": 0.16,
                "active": True,
            })
        return {
            "price_lines": [
                {"type": "liquidity_buy", "label": "Liq. acima / stops vendedores", "price": liquidity["seller_stops_above"], "color": "#22C55E"},
                {"type": "liquidity_sell", "label": "Liq. abaixo / stops compradores", "price": liquidity["buyer_stops_below"], "color": "#EF4444"},
                {"type": "trigger_high", "label": "Gatilho max.", "price": triggers["relevant_high"], "color": "#F59E0B"},
                {"type": "trigger_low", "label": "Gatilho min.", "price": triggers["relevant_low"], "color": "#F59E0B"},
                {"type": "equal_highs", "label": "Equal highs", "price": (liquidity.get("equal_highs") or [{}])[0].get("price"), "color": "#34D399"},
                {"type": "equal_lows", "label": "Equal lows", "price": (liquidity.get("equal_lows") or [{}])[0].get("price"), "color": "#FB7185"},
                {"type": "fib_macro", "label": "50% macro", "price": fib["macro_50"]["level"], "color": "#A78BFA"},
                {"type": "fib_micro", "label": "50% micro", "price": fib["micro_50"]["level"], "color": "#38BDF8"},
                {"type": "entry", "label": "Zona entrada", "price": risk["entry"], "color": "#D4AF37"},
                {"type": "stop", "label": "Invalidacao", "price": risk["technical_stop"], "color": "#EF4444"},
                {"type": "take_profit", "label": "Alvo provavel", "price": risk["take_profit_1"], "color": "#22C55E"},
                {"type": "three_candle_entry", "label": "3C Entrada", "price": three_candle.get("entry"), "color": "#38BDF8"},
                {"type": "three_candle_stop", "label": "3C Stop", "price": three_candle.get("stop"), "color": "#EF4444"},
                {"type": "three_candle_target", "label": "3C Alvo", "price": three_candle.get("target"), "color": "#22C55E"},
            ],
            "zones": zones,
            "events": {
                "sweep": liquidity["sweep"],
                "manipulation": manipulation["detected"],
                "trigger": triggers["active"],
                "three_candle_pattern": three_candle.get("status"),
            },
        }

    def _zones_payload(self, fib, liquidity, triggers, risk):
        return {
            "support": liquidity["buyer_stops_below"],
            "resistance": liquidity["seller_stops_above"],
            "range_high": liquidity["seller_stops_above"],
            "range_low": liquidity["buyer_stops_below"],
            "midpoint": fib["micro_50"]["level"],
            "upper_liquidity": liquidity["seller_stops_above"],
            "lower_liquidity": liquidity["buyer_stops_below"],
            "macro_50": fib["macro_50"]["level"],
            "micro_50": fib["micro_50"]["level"],
            "trigger_high": triggers["relevant_high"],
            "trigger_low": triggers["relevant_low"],
            "entry_zone": risk["entry"],
            "invalidation": risk["technical_stop"],
            "targets": [risk["take_profit_1"], risk["take_profit_2"]],
        }

    def _narrative(self, context, current, previous, fib, liquidity, triggers, manipulation, pullback, obligation, risk, score, classification, fractal, behavior, three_candle):
        return [
            f"Tendencia macro {context['macro_trend']} e micro {context['micro_trend']}; leitura dominante: {context['directional_bias']}.",
            behavior.get("intention", "Intencao do movimento em leitura."),
            f"Forca real {behavior.get('force_real', '--')}; continuidade {behavior.get('continuity_quality', '--')}; aceitacao {behavior.get('acceptance', '--')}.",
            fractal.get("reading", "Fractal ainda sem leitura dominante."),
            f"Candle atual: {current['reading']} Candle anterior: {previous['reading']}",
            fib["reading"],
            f"Liquidez acima em {liquidity['seller_stops_above']} e liquidez abaixo em {liquidity['buyer_stops_below']}. {liquidity.get('classification', {}).get('reading', '')}",
            f"Gatilho ativo: {triggers['active']}; zona de stops provavel: {triggers['stop_activation_zone'] or '--'}.",
            manipulation["reading"],
            pullback["reading"],
            f"Obrigacao atual do preco: {obligation['text']} Estado: {obligation.get('status', 'ativa')}.",
            f"Padrao de 3 candles: {three_candle.get('classification')} ({three_candle.get('score')}/100). {three_candle.get('explanation')}",
            f"Score institucional {score}/100 ({classification}). Melhor entrada: {risk['best_entry_region']}; invalidacao: {risk['invalidation_region']}.",
        ]

    def _live_messages(self, current, previous, context, liquidity, triggers, manipulation, pullback, obligation, signal, fractal, behavior, three_candle):
        messages = [
            f"Candle atual: {current['reading']}",
            behavior.get("intention", "Intencao em leitura."),
            f"Forca real {behavior.get('force_real', '--')} e continuidade {behavior.get('continuity_quality', '--')}.",
            f"Candle anterior: {previous['reading']}",
            f"Mudanca de contexto: {context['summary']}",
            fractal.get("reading", "Fractal em leitura."),
            liquidity.get("classification", {}).get("reading", f"Liquidez acima {liquidity['seller_stops_above']} / abaixo {liquidity['buyer_stops_below']}."),
            f"Gatilho: {triggers['active']}.",
            f"Obrigacao {obligation.get('status', 'ativa')}: {obligation['text']}",
        ]
        messages.extend(three_candle.get("messages", [])[:4])
        if behavior.get("loss_of_strength"):
            messages.append("Estrutura perdendo forca; preco precisa renovar maxima/minima.")
        if behavior.get("artificial_movement"):
            messages.append("Movimento artificial ou sem combustivel.")
        if manipulation["detected"]:
            messages.append(f"Sweep/manipulacao: {manipulation['reading']}")
        if pullback["pullback_failure"]:
            messages.append("Falha de pullback detectada; nao operar sem confirmacao contraria.")
        if signal["status"] == "aguardar contexto":
            messages.append("Alerta: nao operar quando o movimento estiver sem contexto ou sem combustivel.")
        else:
            messages.append(signal["explanation"])
        return messages[:12]


class OperacionalReader(InstitutionalContextEngine):
    pass


def build_operacional_reading(
    candles: pd.DataFrame,
    symbol: str = "BTCUSDT",
    timeframe: str = "15m",
    candles_by_timeframe: dict[str, pd.DataFrame] | None = None,
) -> dict[str, Any]:
    return InstitutionalContextEngine(candles, symbol, timeframe, candles_by_timeframe).analyze()


def build_operacional_context(
    candles: pd.DataFrame,
    symbol: str = "BTCUSDT",
    timeframe: str = "15m",
    candles_by_timeframe: dict[str, pd.DataFrame] | None = None,
) -> dict[str, Any]:
    return InstitutionalContextEngine(candles, symbol, timeframe, candles_by_timeframe).context_only()


def build_candle_flow(
    candles: pd.DataFrame,
    symbol: str = "BTCUSDT",
    timeframe: str = "15m",
    candles_by_timeframe: dict[str, pd.DataFrame] | None = None,
) -> dict[str, Any]:
    return InstitutionalContextEngine(candles, symbol, timeframe, candles_by_timeframe).candle_flow_only()
