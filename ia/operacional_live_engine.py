"""
Live Operacional Grafico.

Engine exclusiva da area Operacional Leitura Grafica. Usa somente leitura
grafica operacional via operacional_reader; nao importa nem calcula os modulos
da IA Completa.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pandas as pd

from .operacional_reader import build_operacional_reading


DISCLAIMER = "Live operacional grafico educativo. Nao constitui recomendacao financeira."


class OperacionalLiveEngine:
    STATES = {
        "ANALISANDO": "ANALISANDO",
        "COMPRA": "COMPRA",
        "VENDA": "VENDA",
        "AGUARDAR": "AGUARDAR CONFIRMACAO",
        "NAO_OPERAR": "NAO OPERAR",
    }

    def __init__(
        self,
        candles: pd.DataFrame,
        symbol: str,
        timeframe: str,
        candles_by_timeframe: dict[str, pd.DataFrame] | None = None,
    ):
        self.df = candles.copy().dropna(subset=["open", "high", "low", "close"])
        self.symbol = symbol
        self.timeframe = timeframe
        self.reading = build_operacional_reading(self.df, symbol, timeframe, candles_by_timeframe)

    def analyze(self) -> dict[str, Any]:
        if not self.reading.get("success"):
            return self._warming_up()
        context = self.reading.get("operacional_context", {})
        signal = self.reading.get("operacional_signal", {})
        risk = self.reading.get("operacional_risk", {})
        candle = self.reading.get("operacional_current_candle", {})
        pullback = self.reading.get("operacional_pullback", {})
        liquidity = self.reading.get("operacional_liquidity", {})
        confirmations = self.reading.get("operacional_confirmations", [])
        invalidations = self.reading.get("operacional_invalidations", [])
        institutional_map = self.reading.get("institutional_map", {})
        obligation = institutional_map.get("price_obligation", {})
        triggers = institutional_map.get("triggers", {})
        manipulation = institutional_map.get("manipulation", {})
        fractal = institutional_map.get("fractal", {})
        behavior = institutional_map.get("behavior", {})
        three_candle = institutional_map.get("three_candle_pattern", self.reading.get("three_candle_pattern", {}))
        operation_blockers = self.reading.get("operation_blockers", institutional_map.get("operation_blockers", []))

        decision = self._decision(context, signal, risk, candle, pullback, liquidity, confirmations, invalidations, obligation, triggers, manipulation, operation_blockers)
        live_messages = self._messages(decision, context, candle, pullback, liquidity, confirmations, invalidations, obligation, triggers, manipulation, fractal, behavior, three_candle, operation_blockers)
        levels = self._levels(signal, risk)

        return {
            "success": True,
            "module": "live_operacional_grafico",
            "isolated": True,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "status": decision["status"],
            "state": decision["state"],
            "direction": decision["direction"],
            "confidence": decision["confidence"],
            "scenario": context.get("label", "Mercado sem clareza"),
            "context": context,
            "market_status": self._market_status(context, candle, manipulation),
            "movement_strength": self.reading.get("score_classification", "--"),
            "timing": self.reading.get("timing"),
            "risk_reward": levels.get("risk_reward"),
            "entry_aggressive": levels.get("entry_aggressive"),
            "entry_conservative": levels.get("entry_conservative"),
            "stop_loss": levels.get("stop_loss"),
            "take_profit_1": levels.get("take_profit_1"),
            "take_profit_2": levels.get("take_profit_2"),
            "reason": decision["reason"],
            "messages": live_messages,
            "confirmations": confirmations[:8],
            "invalidations": invalidations[:8],
            "institutional_map": institutional_map,
            "price_obligation": obligation,
            "active_trigger": triggers,
            "manipulation": manipulation,
            "fractal": fractal,
            "behavior": behavior,
            "three_candle_pattern": three_candle,
            "operation_blockers": operation_blockers,
            "calibration": self.reading.get("operacional_calibration", {}),
            "reading": self.reading,
            "signal": self._signal_payload(decision, levels, context, three_candle),
            "chart_marks": self.reading.get("operacional_chart", {}),
            "current_price": round(float(self.df["close"].iloc[-1]), 8),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "disclaimer": DISCLAIMER,
        }

    def _warming_up(self):
        last_price = round(float(self.df["close"].iloc[-1]), 8) if len(self.df) else None
        message = self.reading.get("narrative", ["Aguardando candles suficientes para leitura institucional."])[0]
        return {
            "success": True,
            "module": "live_operacional_grafico",
            "isolated": True,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "status": self.STATES["ANALISANDO"],
            "state": "ANALISANDO",
            "direction": "NEUTRO",
            "confidence": 0,
            "scenario": "Aquecendo leitura operacional",
            "context": self.reading.get("operacional_context", {}),
            "market_status": "AGUARDANDO CANDLES",
            "movement_strength": "--",
            "timing": "Aguardar formacao de candles para liquidez, 50%, gatilhos e obrigacao do preco.",
            "risk_reward": None,
            "entry_aggressive": None,
            "entry_conservative": None,
            "stop_loss": None,
            "take_profit_1": None,
            "take_profit_2": None,
            "reason": message,
            "messages": [message, "Leitura institucional exige contexto minimo antes de qualquer alerta."],
            "confirmations": [],
            "invalidations": self.reading.get("operacional_invalidations", []),
            "reading": self.reading,
            "signal": {"symbol": self.symbol, "timeframe": self.timeframe, "direction": "NEUTRO", "status": self.STATES["ANALISANDO"], "confidence": 0},
            "chart_marks": self.reading.get("operacional_chart", {}),
            "current_price": last_price,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "disclaimer": DISCLAIMER,
        }

    def _decision(self, context, signal, risk, candle, pullback, liquidity, confirmations, invalidations, obligation, triggers, manipulation, operation_blockers=None):
        operation_blockers = operation_blockers or []
        score = int(self.reading.get("operacional_score", signal.get("score", 0)) or 0)
        bias = context.get("directional_bias", "NEUTRO")
        rr = float(risk.get("risk_reward") or signal.get("risk_reward") or 0)
        pullback_failure = pullback.get("pullback_failure")
        high_risk = context.get("risk") == "alto" or risk.get("scenario_risk") == "alto" or rr < 1
        no_context = score < 40 or not liquidity.get("movement_has_fuel", True)

        if operation_blockers or manipulation.get("detected") or pullback_failure or high_risk or no_context:
            return {
                "state": "NAO_OPERAR",
                "status": self.STATES["NAO_OPERAR"],
                "direction": bias,
                "confidence": max(35, min(88, score)),
                "reason": (operation_blockers or [manipulation.get("reading") or pullback.get("reading") or obligation.get("text") or "Movimento sem contexto institucional suficiente."])[0],
            }
        if score < 60 or len(invalidations) > len(confirmations):
            return {
                "state": "AGUARDAR",
                "status": self.STATES["AGUARDAR"],
                "direction": bias,
                "confidence": max(35, min(82, score)),
                "reason": obligation.get("text") or "Mercado sem contexto direcional suficiente para executar.",
            }
        if bias == "COMPRA CONTEXTUAL" and score >= 60:
            return {
                "state": "COMPRA",
                "status": "ALERTA DE COMPRA CONTEXTUAL",
                "direction": bias,
                "confidence": min(92, max(score, 58)),
                "reason": signal.get("explanation") or obligation.get("text") or "Contexto comprador com liquidez e gatilho mapeados.",
            }
        if bias == "VENDA CONTEXTUAL" and score >= 60:
            return {
                "state": "VENDA",
                "status": "ALERTA DE VENDA CONTEXTUAL",
                "direction": bias,
                "confidence": min(92, max(score, 58)),
                "reason": signal.get("explanation") or obligation.get("text") or "Contexto vendedor com liquidez e gatilho mapeados.",
            }
        return {
            "state": "AGUARDAR",
            "status": self.STATES["AGUARDAR"],
            "direction": bias,
            "confidence": max(30, min(76, score)),
            "reason": obligation.get("text") or "Aguardando candle de confirmacao e melhor assimetria.",
        }

    def _levels(self, signal, risk):
        entry = signal.get("entry") or risk.get("entry") or risk.get("reference_price")
        stop = signal.get("stop") or risk.get("technical_stop")
        take_1 = signal.get("take_profit_1") or risk.get("take_profit_1") or risk.get("partial_target")
        take_2 = signal.get("take_profit_2") or risk.get("take_profit_2")
        return {
            "entry_aggressive": entry,
            "entry_conservative": self._conservative_entry(entry, stop),
            "stop_loss": stop,
            "take_profit_1": take_1,
            "take_profit_2": take_2,
            "risk_reward": signal.get("risk_reward") or risk.get("risk_reward"),
        }

    def _conservative_entry(self, entry, stop):
        try:
            entry = float(entry)
            stop = float(stop)
        except Exception:
            return None
        return round(entry - (entry - stop) * 0.25, 8)

    def _market_status(self, context, candle, manipulation):
        if manipulation.get("detected"):
            return "SWEEP / MANIPULACAO"
        if context.get("risk") == "alto":
            return "RISCO OPERACIONAL"
        if int(candle.get("body_strength", 0) or 0) >= 65:
            return "CANDLE DE DECISAO"
        return "EM LEITURA"

    def _messages(self, decision, context, candle, pullback, liquidity, confirmations, invalidations, obligation, triggers, manipulation, fractal, behavior, three_candle, operation_blockers=None):
        operation_blockers = operation_blockers or []
        messages = []
        messages.extend(operation_blockers[:3])
        messages.append((liquidity.get("classification") or {}).get("reading") or f"Liquidez acima {liquidity.get('seller_stops_above')} / abaixo {liquidity.get('buyer_stops_below')}.")
        messages.append(f"Preco {behavior.get('acceptance', '--')} / continuidade {behavior.get('continuity_quality', '--')}.")
        messages.append(f"Obrigacao {obligation.get('status', 'ativa')}: {obligation.get('text', '--')}")
        messages.append(fractal.get("reading", "Fractal em leitura."))
        messages.append(f"Gatilho ativo: {triggers.get('active', '--')}.")
        if three_candle.get("status") in {"CONFIRMADO", "EM_FORMACAO"}:
            messages.extend((three_candle.get("messages") or [])[:2])
        if behavior.get("loss_of_strength"):
            messages.append("Estrutura perdendo forca.")
        if behavior.get("artificial_movement"):
            messages.append("Movimento artificial; possivel manipulacao institucional.")
        if pullback.get("pullback_failure"):
            messages.append("Falha de pullback detectada.")
        if manipulation.get("detected"):
            messages.append(manipulation.get("reading"))
        if int(candle.get("body_strength", 0) or 0) >= 60:
            messages.append("Candle de decisao confirmado.")
        messages.append(decision["reason"])
        if not operation_blockers:
            messages.extend(confirmations[:2])
        messages.extend([item for item in invalidations if item.startswith("Operacao bloqueada")][:2])
        return list(dict.fromkeys([item for item in messages if item]))[:8]

    def _signal_payload(self, decision, levels, context, three_candle=None):
        three_candle = three_candle or {}
        operation_blockers = self.reading.get("operation_blockers", [])
        return {
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "direction": decision["direction"],
            "status": decision["status"],
            "confidence": decision["confidence"],
            "entry": levels.get("entry_aggressive"),
            "entry_conservative": levels.get("entry_conservative"),
            "stop_loss": levels.get("stop_loss"),
            "take_profit_1": levels.get("take_profit_1"),
            "take_profit_2": levels.get("take_profit_2"),
            "risk_reward": levels.get("risk_reward"),
            "reason": decision["reason"],
            "context": context.get("label"),
            "operation_blockers": operation_blockers,
            "blocked": bool(operation_blockers),
            "three_candle_pattern": {
                "status": three_candle.get("status"),
                "score": three_candle.get("score"),
                "classification": three_candle.get("classification"),
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


def build_operacional_live_status(candles, symbol, timeframe, candles_by_timeframe=None):
    return OperacionalLiveEngine(candles, symbol, timeframe, candles_by_timeframe).analyze()
