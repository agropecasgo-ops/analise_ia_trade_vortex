"""
Leitura Wyckoff simplificada para contexto operacional.
"""

import pandas as pd


class WyckoffReader:
    def __init__(self, candles):
        self.df = candles.copy().dropna(subset=["open", "high", "low", "close", "volume"])
        if len(self.df) < 60:
            raise ValueError("wyckoff_requires_at_least_60_candles")

    def read(self):
        recent = self.df.tail(80)
        previous_range = self.df.iloc[-81:-1] if len(self.df) > 81 else self.df.iloc[:-1]
        last = self.df.iloc[-1]
        volume = self.df["volume"]
        avg_volume = volume.rolling(20).mean().bfill().iloc[-1]
        range_high = float(previous_range["high"].max()) if len(previous_range) else float(recent["high"].max())
        range_low = float(previous_range["low"].min()) if len(previous_range) else float(recent["low"].min())
        range_mid = (range_high + range_low) / 2
        close = float(last["close"])
        range_pct = (range_high - range_low) / max(close, 0.00000001) * 100
        volume_ratio = float(last["volume"] / max(avg_volume, 0.00000001))
        candle_range = max(float(last["high"] - last["low"]), 0.00000001)
        body_ratio = abs(float(last["close"] - last["open"])) / candle_range

        spring = last["low"] < range_low and close > range_low and volume_ratio >= 1.2
        upthrust = last["high"] > range_high and close < range_high and volume_ratio >= 1.2
        climax = volume_ratio >= 2.2 and body_ratio >= 0.55
        selling_climax = bool(climax and close < last["open"] and close <= range_mid)
        buying_climax = bool(climax and close > last["open"] and close >= range_mid)
        test = volume_ratio < 0.85 and range_low < close < range_high

        if spring:
            phase = "spring"
            bias = "bullish"
        elif upthrust:
            phase = "upthrust"
            bias = "bearish"
        elif close < range_mid and range_pct < 9:
            phase = "acumulacao"
            bias = "bullish_neutral"
        elif close > range_mid and range_pct < 9:
            phase = "distribuicao"
            bias = "bearish_neutral"
        elif buying_climax:
            phase = "buying_climax"
            bias = "caution_bullish"
        elif selling_climax:
            phase = "selling_climax"
            bias = "caution_bearish"
        elif test:
            phase = "teste"
            bias = "neutral"
        else:
            phase = "markup" if close > range_mid else "markdown"
            bias = "bullish" if close > range_mid else "bearish"

        confirmations, invalidations = self._context_lists(phase, bias, spring, upthrust, selling_climax, buying_climax, test)

        return {
            "phase": phase,
            "wyckoff_phase": phase,
            "probable_market_phase": phase,
            "bias": bias,
            "accumulation": phase == "acumulacao",
            "distribution": phase == "distribuicao",
            "spring": bool(spring),
            "upthrust": bool(upthrust),
            "climax": bool(climax),
            "selling_climax": selling_climax,
            "buying_climax": buying_climax,
            "test": bool(test),
            "range": {
                "high": range_high,
                "low": range_low,
                "mid": range_mid,
                "range_pct": round(float(range_pct), 3),
            },
            "volume_ratio": round(volume_ratio, 3),
            "score_adjustment": self._score_adjustment(phase),
            "confirmations": confirmations,
            "invalidations": invalidations,
            "explanation": self._explanation(phase, bias, volume_ratio, range_low, range_high),
        }

    def _score_adjustment(self, phase):
        if phase in ["spring", "acumulacao"]:
            return 6
        if phase in ["upthrust", "distribuicao"]:
            return -6
        if phase in ["selling_climax", "buying_climax"]:
            return -3
        if phase == "teste":
            return 2
        return 0

    def _context_lists(self, phase, bias, spring, upthrust, selling_climax, buying_climax, test):
        confirmations = []
        invalidations = []
        if spring:
            confirmations.append("Wyckoff spring: varredura abaixo do range com fechamento de retorno.")
        if upthrust:
            invalidations.append("Wyckoff upthrust: rompimento acima do range rejeitado.")
        if phase == "acumulacao":
            confirmations.append("Wyckoff sugere acumulacao em faixa comprimida.")
        if phase == "distribuicao":
            invalidations.append("Wyckoff sugere distribuicao em faixa superior.")
        if selling_climax:
            confirmations.append("Selling climax detectado; possivel exaustao vendedora.")
        if buying_climax:
            invalidations.append("Buying climax detectado; risco de exaustao compradora.")
        if test:
            confirmations.append("Teste de Wyckoff em volume reduzido.")
        if not confirmations and not invalidations:
            confirmations.append(f"Wyckoff em fase provavel {phase} com vies {bias}.")
        return confirmations[:6], invalidations[:6]

    def _explanation(self, phase, bias, volume_ratio, range_low, range_high):
        return (
            f"Wyckoff indica fase provavel {phase} com vies {bias}. "
            f"Range observado entre {range_low} e {range_high}; volume relativo {volume_ratio:.2f}x."
        )


def read_wyckoff(candles):
    return WyckoffReader(candles).read()
