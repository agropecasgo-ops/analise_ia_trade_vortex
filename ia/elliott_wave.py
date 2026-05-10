"""
Leitura Elliott Wave para a IA Completa.
"""

from __future__ import annotations

from typing import Any

import pandas as pd


def _round(value, digits=4):
    try:
        return round(float(value), digits)
    except Exception:
        return 0.0


class ElliottWaveReader:
    def __init__(self, candles):
        self.df = candles.copy().dropna(subset=["open", "high", "low", "close"])
        if len(self.df) < 70:
            raise ValueError("elliott_wave_requires_at_least_70_candles")

    def read(self) -> dict[str, Any]:
        swings = self._swings()
        closes = self.df["close"].tail(55)
        trend_pct = (float(closes.iloc[-1]) - float(closes.iloc[0])) / max(float(closes.iloc[0]), 1e-9) * 100
        wave_bias = "bullish" if trend_pct > 1.2 else "bearish" if trend_pct < -1.2 else "neutral"
        impulse = self._impulse_structure(swings, wave_bias)
        corrective = self._corrective_structure(swings, wave_bias)
        wave_count, current_wave = self._wave_count(swings, wave_bias, impulse, corrective)
        reversal_risk = self._reversal_risk(current_wave, impulse, corrective, trend_pct)
        confidence = self._confidence(swings, impulse, corrective, wave_bias)

        return {
            "wave_count": wave_count,
            "current_wave": current_wave,
            "wave_bias": wave_bias,
            "impulse_structure": impulse,
            "corrective_structure": corrective,
            "confidence": confidence,
            "reversal_risk": reversal_risk,
            "possible_stage": current_wave,
            "confirmations": self._confirmations(wave_bias, impulse, corrective, current_wave),
            "invalidations": self._invalidations(wave_bias, impulse, corrective, reversal_risk),
            "score_adjustment": self._score_adjustment(wave_bias, impulse, corrective, reversal_risk),
            "explanation": self._explanation(wave_bias, current_wave, impulse, corrective, reversal_risk),
        }

    def _swings(self, window=3):
        highs = []
        lows = []
        for i in range(window, len(self.df) - window):
            row = self.df.iloc[i]
            local_high = self.df["high"].iloc[i - window: i + window + 1].max()
            local_low = self.df["low"].iloc[i - window: i + window + 1].min()
            ts = self.df.index[i]
            time_value = int(ts.timestamp()) if hasattr(ts, "timestamp") else i
            if float(row.high) >= float(local_high):
                highs.append({"type": "H", "time": time_value, "price": _round(row.high)})
            if float(row.low) <= float(local_low):
                lows.append({"type": "L", "time": time_value, "price": _round(row.low)})
        points = sorted(highs + lows, key=lambda item: item["time"])
        filtered = []
        for point in points:
            if filtered and filtered[-1]["type"] == point["type"]:
                replace = point["price"] > filtered[-1]["price"] if point["type"] == "H" else point["price"] < filtered[-1]["price"]
                if replace:
                    filtered[-1] = point
            else:
                filtered.append(point)
        return filtered[-9:]

    def _impulse_structure(self, swings, bias):
        if len(swings) < 6 or bias == "neutral":
            return {"detected": False, "quality": 0, "direction": bias}
        prices = [item["price"] for item in swings[-6:]]
        if bias == "bullish":
            advances = sum(1 for a, b in zip(prices, prices[1:]) if b > a)
        else:
            advances = sum(1 for a, b in zip(prices, prices[1:]) if b < a)
        quality = int(max(0, min(100, advances / 5 * 100)))
        return {"detected": quality >= 58, "quality": quality, "direction": bias, "swings": swings[-6:]}

    def _corrective_structure(self, swings, bias):
        if len(swings) < 4:
            return {"detected": False, "pattern": "indefinido", "quality": 0}
        last = swings[-4:]
        prices = [item["price"] for item in last]
        alternating = len({item["type"] for item in last}) == 2
        depth = abs(prices[-1] - prices[0]) / max(abs(prices[1] - prices[0]), 1e-9)
        detected = alternating and 0.25 <= depth <= 1.6
        return {
            "detected": detected,
            "pattern": "ABC provavel" if detected else "sem ABC claro",
            "quality": int(max(0, min(100, (1.6 - min(depth, 1.6)) / 1.6 * 100))) if detected else 25,
            "swings": last,
        }

    def _wave_count(self, swings, bias, impulse, corrective):
        if corrective.get("detected") and not impulse.get("detected"):
            return {"A": swings[-3] if len(swings) >= 3 else None, "B": swings[-2] if len(swings) >= 2 else None, "C": swings[-1] if swings else None}, "C"
        if impulse.get("detected"):
            stage = min(5, max(1, len(swings[-6:])))
            count = {str(idx + 1): point for idx, point in enumerate(swings[-5:])}
            return count, str(stage)
        return {}, "indefinida"

    def _reversal_risk(self, current_wave, impulse, corrective, trend_pct):
        if current_wave in ["5", "C"] and abs(trend_pct) > 3:
            return "alto"
        if corrective.get("detected"):
            return "moderado"
        if impulse.get("detected"):
            return "baixo"
        return "moderado"

    def _confidence(self, swings, impulse, corrective, bias):
        base = 32 + min(len(swings), 8) * 5
        if impulse.get("detected"):
            base += impulse.get("quality", 0) * 0.22
        if corrective.get("detected"):
            base += corrective.get("quality", 0) * 0.15
        if bias != "neutral":
            base += 8
        return int(max(5, min(92, base)))

    def _confirmations(self, bias, impulse, corrective, current_wave):
        items = []
        if impulse.get("detected"):
            items.append(f"Estrutura impulsiva {bias} com qualidade {impulse.get('quality')}%.")
        if corrective.get("detected"):
            items.append("Correcao ABC provavel detectada.")
        if current_wave in ["3", "5"]:
            items.append(f"Preco possivelmente em onda {current_wave}.")
        return items

    def _invalidations(self, bias, impulse, corrective, reversal_risk):
        items = []
        if bias == "neutral":
            items.append("Elliott sem tendencia predominante.")
        if not impulse.get("detected") and not corrective.get("detected"):
            items.append("Sem contagem Elliott confiavel.")
        if reversal_risk == "alto":
            items.append("Risco de reversao elevado pela fase da onda.")
        return items

    def _score_adjustment(self, bias, impulse, corrective, reversal_risk):
        score = 0
        if impulse.get("detected"):
            score += 4
        if corrective.get("detected"):
            score += 2
        if bias == "neutral":
            score -= 2
        if reversal_risk == "alto":
            score -= 4
        return int(max(-5, min(5, score)))

    def _explanation(self, bias, current_wave, impulse, corrective, reversal_risk):
        if impulse.get("detected"):
            structure = f"estrutura impulsiva {bias}"
        elif corrective.get("detected"):
            structure = "correcao ABC provavel"
        else:
            structure = "contagem ainda indefinida"
        return f"Elliott indica {structure}; onda atual estimada: {current_wave}; risco de reversao {reversal_risk}."


def read_elliott_wave(candles):
    return ElliottWaveReader(candles).read()
