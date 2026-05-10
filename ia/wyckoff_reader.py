"""
Leitura Wyckoff avancada para a IA Completa.

Este modulo pertence ao fluxo principal de IA Completa. Nao deve ser usado
pela area Operacional Leitura Grafica.
"""

from __future__ import annotations

from typing import Any

import pandas as pd


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def _round(value: float, digits: int = 4) -> float:
    return round(_safe_float(value), digits)


class WyckoffAdvancedReader:
    def __init__(self, candles):
        self.df = candles.copy().dropna(subset=["open", "high", "low", "close", "volume"])
        if len(self.df) < 60:
            raise ValueError("wyckoff_reader_requires_at_least_60_candles")

    def read(self) -> dict[str, Any]:
        recent = self.df.tail(90)
        close = recent["close"]
        high = recent["high"]
        low = recent["low"]
        volume = recent["volume"]
        current = recent.iloc[-1]
        previous = recent.iloc[-2]

        range_high = float(high.max())
        range_low = float(low.min())
        span = max(range_high - range_low, float(current.close) * 0.00001)
        close_position = (float(current.close) - range_low) / span
        volume_ratio = float(current.volume) / max(float(volume.tail(20).mean()), 1e-9)
        spread = (float(current.high) - float(current.low)) / max(float(current.close), 1e-9) * 100
        avg_spread = ((recent["high"] - recent["low"]) / recent["close"] * 100).tail(20).mean()
        result = abs(float(current.close) - float(current.open)) / max(float(current.high) - float(current.low), 1e-9)
        effort_vs_result = self._effort_vs_result(volume_ratio, spread, avg_spread, result)

        selling_climax = close_position <= 0.18 and volume_ratio >= 1.65 and float(current.close) > float(current.open)
        buying_climax = close_position >= 0.82 and volume_ratio >= 1.65 and float(current.close) < float(current.open)
        spring = float(current.low) < range_low + span * 0.08 and float(current.close) > range_low + span * 0.16 and volume_ratio >= 1.15
        upthrust = float(current.high) > range_high - span * 0.08 and float(current.close) < range_high - span * 0.16 and volume_ratio >= 1.15
        test = volume_ratio < 0.85 and result < 0.42 and (close_position <= 0.35 or close_position >= 0.65)

        accumulation_score = self._accumulation_score(close_position, volume_ratio, spring, selling_climax, test, effort_vs_result)
        distribution_score = self._distribution_score(close_position, volume_ratio, upthrust, buying_climax, test, effort_vs_result)
        phase = self._phase(accumulation_score, distribution_score, close_position)
        manipulation = spring or upthrust or (volume_ratio >= 1.8 and result < 0.32)
        confirmations, invalidations = self._lists(
            phase, manipulation, spring, upthrust, selling_climax, buying_climax, test, effort_vs_result
        )

        bias = "bullish" if accumulation_score > distribution_score + 12 else "bearish" if distribution_score > accumulation_score + 12 else "neutral"
        score_adjustment = int(max(-8, min(8, (accumulation_score - distribution_score) / 8)))

        return {
            "wyckoff_phase": phase,
            "phase": phase,
            "bias": bias,
            "institutional_manipulation": bool(manipulation),
            "accumulation_score": int(accumulation_score),
            "distribution_score": int(distribution_score),
            "accumulation": phase == "acumulacao",
            "distribution": phase == "distribuicao",
            "spring": bool(spring),
            "upthrust": bool(upthrust),
            "selling_climax": bool(selling_climax),
            "buying_climax": bool(buying_climax),
            "test": bool(test),
            "effort_vs_result": effort_vs_result,
            "volume_ratio": _round(volume_ratio, 2),
            "important_volume_zone": self._volume_zone(close_position, range_low, range_high),
            "score_adjustment": score_adjustment,
            "confirmations": confirmations,
            "invalidations": invalidations,
            "explanation": self._explanation(phase, manipulation, effort_vs_result, previous, current),
        }

    def _effort_vs_result(self, volume_ratio, spread, avg_spread, result):
        if volume_ratio >= 1.5 and result < 0.35:
            return "alto esforco com pouco resultado"
        if volume_ratio >= 1.25 and spread > avg_spread * 1.15 and result >= 0.55:
            return "esforco confirma deslocamento"
        if volume_ratio < 0.8 and result < 0.35:
            return "baixo esforco em teste"
        return "equilibrado"

    def _accumulation_score(self, position, volume_ratio, spring, selling_climax, test, effort):
        score = 35
        if position <= 0.35:
            score += 18
        if spring:
            score += 24
        if selling_climax:
            score += 18
        if test and position <= 0.45:
            score += 12
        if effort == "alto esforco com pouco resultado" and position <= 0.45:
            score += 10
        if volume_ratio < 0.75 and position <= 0.45:
            score += 6
        return max(0, min(100, score))

    def _distribution_score(self, position, volume_ratio, upthrust, buying_climax, test, effort):
        score = 35
        if position >= 0.65:
            score += 18
        if upthrust:
            score += 24
        if buying_climax:
            score += 18
        if test and position >= 0.55:
            score += 12
        if effort == "alto esforco com pouco resultado" and position >= 0.55:
            score += 10
        if volume_ratio < 0.75 and position >= 0.55:
            score += 6
        return max(0, min(100, score))

    def _phase(self, accumulation, distribution, position):
        if accumulation >= 68 and accumulation > distribution:
            return "acumulacao"
        if distribution >= 68 and distribution > accumulation:
            return "distribuicao"
        if abs(accumulation - distribution) <= 8:
            return "range / equilibrio"
        if position < 0.5:
            return "possivel reacumulacao"
        return "possivel redistribuicao"

    def _volume_zone(self, position, low, high):
        zone = "inferior" if position <= 0.35 else "superior" if position >= 0.65 else "meio da faixa"
        return {"zone": zone, "range_low": _round(low), "range_high": _round(high)}

    def _lists(self, phase, manipulation, spring, upthrust, selling_climax, buying_climax, test, effort):
        confirmations = []
        invalidations = []
        if phase == "acumulacao":
            confirmations.append("Wyckoff sugere acumulacao em zona inferior.")
        if phase == "distribuicao":
            confirmations.append("Wyckoff sugere distribuicao em zona superior.")
        if spring:
            confirmations.append("Spring detectado: varredura abaixo da faixa com recuperacao.")
        if upthrust:
            invalidations.append("Upthrust detectado: varredura acima da faixa com rejeicao.")
        if selling_climax:
            confirmations.append("Selling climax possivel por volume elevado em fundo.")
        if buying_climax:
            invalidations.append("Buying climax possivel por volume elevado em topo.")
        if test:
            confirmations.append("Teste com menor esforco detectado.")
        if manipulation:
            confirmations.append("Possivel manipulacao institucional no range.")
        if effort == "alto esforco com pouco resultado":
            invalidations.append("Alto esforco com pouco resultado pode indicar absorcao/manipulacao.")
        return confirmations[:8], invalidations[:8]

    def _explanation(self, phase, manipulation, effort, previous, current):
        direction = "alta" if float(current.close) > float(previous.close) else "baixa"
        manipulation_text = " com suspeita de manipulacao institucional" if manipulation else ""
        return f"Fase Wyckoff provavel: {phase}{manipulation_text}. Esforco vs resultado: {effort}. Ultimo deslocamento de {direction}."


def read_wyckoff_advanced(candles):
    return WyckoffAdvancedReader(candles).read()
