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

    def __init__(self, candles: pd.DataFrame, symbol: str, timeframe: str):
        self.df = candles.copy().dropna(subset=["open", "high", "low", "close"])
        self.symbol = symbol
        self.timeframe = timeframe
        self.reading = build_operacional_reading(self.df, symbol, timeframe)

    def analyze(self) -> dict[str, Any]:
        if not self.reading.get("success"):
            return self._warming_up()
        context = self.reading.get("operacional_context", {})
        trend = self.reading.get("operacional_trend", {})
        signal = self.reading.get("operacional_signal", {})
        risk = self.reading.get("operacional_risk", {})
        candle = self.reading.get("operacional_current_candle", {})
        breakout = self.reading.get("operacional_breakout", {})
        pullback = self.reading.get("operacional_pullback", {})
        liquidity = self.reading.get("operacional_liquidity", {})
        confirmations = self.reading.get("operacional_confirmations", [])
        invalidations = self.reading.get("operacional_invalidations", [])
        apostila = self.reading.get("apostila_operacional", {})

        decision = self._decision(context, trend, signal, risk, candle, breakout, pullback, liquidity, confirmations, invalidations, apostila)
        live_messages = self._messages(decision, context, trend, candle, breakout, pullback, liquidity, confirmations, invalidations, apostila)
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
            "market_status": self._market_status(context, trend, candle),
            "movement_strength": trend.get("strength_label", "--"),
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
            "apostila_operacional": apostila,
            "reading": self.reading,
            "signal": self._signal_payload(decision, levels, context),
            "chart_marks": self.reading.get("operacional_chart", {}),
            "current_price": round(float(self.df["close"].iloc[-1]), 8),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "disclaimer": DISCLAIMER,
        }

    def _warming_up(self):
        last_price = round(float(self.df["close"].iloc[-1]), 8) if len(self.df) else None
        message = self.reading.get("narrative", ["Aguardando candles suficientes para aplicar a apostila operacional."])[0]
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
            "timing": "Aguardar formacao de candles para Dow, 50%, prior cote e padrao de 3 candles.",
            "risk_reward": None,
            "entry_aggressive": None,
            "entry_conservative": None,
            "stop_loss": None,
            "take_profit_1": None,
            "take_profit_2": None,
            "reason": message,
            "messages": [message, "Apostila operacional exige contexto minimo antes de executar."],
            "confirmations": [],
            "invalidations": self.reading.get("operacional_invalidations", []),
            "reading": self.reading,
            "signal": {"symbol": self.symbol, "timeframe": self.timeframe, "direction": "NEUTRO", "status": self.STATES["ANALISANDO"], "confidence": 0},
            "chart_marks": self.reading.get("operacional_chart", {}),
            "current_price": last_price,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "disclaimer": DISCLAIMER,
        }

    def _decision(self, context, trend, signal, risk, candle, breakout, pullback, liquidity, confirmations, invalidations, apostila=None):
        apostila = apostila or {}
        score = int(self.reading.get("operacional_score", signal.get("score", 0)) or 0)
        bias = trend.get("bias", "neutro")
        rr = float(risk.get("risk_reward") or signal.get("risk_reward") or 0)
        execution = apostila.get("execution", {})
        no_trade_filters = apostila.get("no_trade_filters", [])
        strong_candle = int(candle.get("body_strength", 0) or 0) >= 55
        false_breakout = breakout.get("false_breakout")
        pullback_failure = pullback.get("pullback_failure")
        lateral = bias == "lateral" or context.get("label") == "Lateralizacao"
        high_risk = context.get("risk") == "alto" or risk.get("scenario_risk") == "alto" or rr < 1

        if no_trade_filters or false_breakout or pullback_failure or high_risk:
            return {
                "state": "NAO_OPERAR",
                "status": self.STATES["NAO_OPERAR"],
                "direction": "NEUTRO",
                "confidence": max(35, min(88, score)),
                "reason": no_trade_filters[0] if no_trade_filters else "Armadilha, falso rompimento, falha de pullback ou risco operacional elevado.",
            }
        if lateral or len(invalidations) > len(confirmations):
            return {
                "state": "AGUARDAR",
                "status": self.STATES["AGUARDAR"],
                "direction": "NEUTRO",
                "confidence": max(35, min(82, score)),
                "reason": "Mercado sem contexto direcional suficiente para executar.",
            }
        if execution.get("direction") == "COMPRA" and score >= 58 and execution.get("mode") != "aguardar":
            return {
                "state": "COMPRA",
                "status": self.STATES["COMPRA"],
                "direction": "COMPRA",
                "confidence": min(92, max(score, 58)),
                "reason": execution.get("reason") or "Contexto comprador com timing operacional favoravel.",
            }
        if execution.get("direction") == "VENDA" and score >= 58 and execution.get("mode") != "aguardar":
            return {
                "state": "VENDA",
                "status": self.STATES["VENDA"],
                "direction": "VENDA",
                "confidence": min(92, max(score, 58)),
                "reason": execution.get("reason") or "Contexto vendedor com timing operacional favoravel.",
            }
        if bias == "alta" and score >= 70 and (pullback.get("valid_pullback") or breakout.get("valid_breakout") or strong_candle):
            return {"state": "COMPRA", "status": self.STATES["COMPRA"], "direction": "COMPRA", "confidence": min(88, max(score, 70)), "reason": "Contexto comprador, mas manter ordem atras do ponto de parada."}
        if bias == "baixa" and score >= 70 and (pullback.get("valid_pullback") or breakout.get("valid_breakout") or strong_candle):
            return {"state": "VENDA", "status": self.STATES["VENDA"], "direction": "VENDA", "confidence": min(88, max(score, 70)), "reason": "Contexto vendedor, mas manter ordem atras do ponto de parada."}
        return {
            "state": "AGUARDAR",
            "status": self.STATES["AGUARDAR"],
            "direction": "NEUTRO",
            "confidence": max(30, min(76, score)),
            "reason": "Aguardando candle de confirmacao e melhor assimetria.",
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

    def _market_status(self, context, trend, candle):
        if context.get("risk") == "alto":
            return "RISCO OPERACIONAL"
        if trend.get("bias") == "lateral":
            return "LATERALIZADO"
        if int(candle.get("body_strength", 0) or 0) >= 65:
            return "CANDLE DE DECISAO"
        return "EM LEITURA"

    def _messages(self, decision, context, trend, candle, breakout, pullback, liquidity, confirmations, invalidations, apostila=None):
        apostila = apostila or {}
        messages = []
        if apostila.get("reading"):
            messages.append(apostila["reading"])
        phase = apostila.get("market_phase", {}).get("phase")
        if phase:
            messages.append(f"Fase pela apostila: {phase}.")
        if apostila.get("dow_50", {}).get("reading"):
            messages.append(apostila["dow_50"]["reading"])
        if apostila.get("three_candle_pattern", {}).get("active"):
            messages.append("Padrao de 3 candles detectado: alvo, negacao e teste.")
        if trend.get("bias") == "alta":
            messages.append("Contexto de alta por topos e fundos.")
        elif trend.get("bias") == "baixa":
            messages.append("Contexto de baixa por topos e fundos.")
        elif trend.get("bias") == "lateral":
            messages.append("Mercado lateralizado. Evitar entrada.")
        if pullback.get("valid_pullback"):
            messages.append("Pullback saudavel na tendencia.")
        if pullback.get("pullback_failure"):
            messages.append("Falha de pullback detectada.")
        if breakout.get("valid_breakout"):
            messages.append("Rompimento valido em regiao operacional.")
        if breakout.get("false_breakout"):
            messages.append("Rompimento sem continuidade. Possivel armadilha.")
        if liquidity.get("sweep"):
            messages.append("Liquidez capturada. Aguardar confirmacao.")
        if int(candle.get("body_strength", 0) or 0) >= 60:
            messages.append("Candle de decisao confirmado.")
        if int(candle.get("upper_wick_pct", 0) or 0) >= 42:
            messages.append("Rejeicao forte na resistencia.")
        if int(candle.get("lower_wick_pct", 0) or 0) >= 42:
            messages.append("Mercado mostrando rejeicao em fundo.")
        messages.append(decision["reason"])
        messages.extend(confirmations[:2])
        messages.extend(invalidations[:2])
        return list(dict.fromkeys(messages))[:10]

    def _signal_payload(self, decision, levels, context):
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
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


def build_operacional_live_status(candles, symbol, timeframe):
    return OperacionalLiveEngine(candles, symbol, timeframe).analyze()
