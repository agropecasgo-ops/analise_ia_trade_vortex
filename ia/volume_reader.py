"""
Leitura de volume institucional para o FinanceAI.

Detecta volume acima da media, pressao compradora/vendedora, volume anormal,
exaustao, absorcao, confirmacao de rompimento e divergencia preco-volume.
"""

import numpy as np
import pandas as pd


class VolumeReader:
    def __init__(self, candles):
        self.df = candles.copy().dropna(subset=["open", "high", "low", "close", "volume"])
        if len(self.df) < 30:
            raise ValueError("volume_reader_requires_at_least_30_candles")

    def read(self):
        volume = self.df["volume"]
        close = self.df["close"]
        last = self.df.iloc[-1]
        volume_sma = volume.rolling(20).mean().bfill()
        volume_std = volume.rolling(20).std().bfill().replace(0, np.nan)
        current_volume = float(last["volume"])
        avg_volume = float(volume_sma.iloc[-1])
        volume_ratio = current_volume / max(avg_volume, 0.00000001)
        zscore = (current_volume - avg_volume) / max(float(volume_std.iloc[-1]), 0.00000001)

        buy_sell = self._buy_sell_volume(last)
        abnormal = volume_ratio >= 1.8 or zscore >= 2.0
        above_average = volume_ratio >= 1.2
        exhaustion = self._exhaustion(volume_ratio)
        absorption = self._absorption(volume_ratio)
        breakout_confirmation = self._breakout_confirmation(volume_ratio)
        divergence = self._price_volume_divergence(close, volume)
        score_adjustment, signal, reasons = self._score(
            above_average,
            buy_sell,
            abnormal,
            exhaustion,
            absorption,
            breakout_confirmation,
            divergence,
        )

        return {
            "volume_above_average": bool(above_average),
            "buyer_volume": buy_sell["buyer_volume"],
            "seller_volume": buy_sell["seller_volume"],
            "dominant_side": buy_sell["dominant_side"],
            "abnormal_volume": bool(abnormal),
            "exhaustion": exhaustion,
            "absorption": absorption,
            "breakout_confirmation": breakout_confirmation,
            "price_volume_divergence": divergence,
            "score_adjustment": int(score_adjustment),
            "signal": signal,
            "confidence": self._confidence(volume_ratio, zscore, reasons),
            "reasons": reasons,
            "metrics": {
                "current_volume": round(current_volume, 6),
                "average_volume_20": round(avg_volume, 6),
                "volume_ratio": round(float(volume_ratio), 3),
                "volume_zscore": round(float(zscore), 3),
                "close_position": buy_sell["close_position"],
            },
        }

    def _buy_sell_volume(self, candle):
        total = float(candle["volume"])
        if "taker_buy_base_volume" in self.df.columns and pd.notna(candle.get("taker_buy_base_volume")):
            buyer = float(candle["taker_buy_base_volume"])
            seller = max(total - buyer, 0.0)
        else:
            candle_range = max(float(candle["high"] - candle["low"]), 0.00000001)
            close_position = (float(candle["close"] - candle["low"]) / candle_range)
            buyer = total * close_position
            seller = total - buyer

        close_position = buyer / max(total, 0.00000001)
        if close_position >= 0.58:
            dominant = "BUYER"
        elif close_position <= 0.42:
            dominant = "SELLER"
        else:
            dominant = "BALANCED"
        return {
            "buyer_volume": round(buyer, 6),
            "seller_volume": round(seller, 6),
            "dominant_side": dominant,
            "close_position": round(float(close_position), 3),
        }

    def _exhaustion(self, volume_ratio):
        last = self.df.iloc[-1]
        previous = self.df.iloc[-2]
        body = abs(float(last["close"] - last["open"]))
        candle_range = max(float(last["high"] - last["low"]), 0.00000001)
        upper_wick = float(last["high"] - max(last["open"], last["close"]))
        lower_wick = float(min(last["open"], last["close"]) - last["low"])
        body_ratio = body / candle_range
        close_change = abs(float(last["close"] - previous["close"])) / max(float(previous["close"]), 0.00000001)
        detected = volume_ratio >= 1.8 and (body_ratio <= 0.35 or close_change <= 0.0025) and max(upper_wick, lower_wick) > body
        side = "BUYER_EXHAUSTION" if upper_wick > lower_wick else "SELLER_EXHAUSTION" if detected else "NONE"
        return {
            "detected": bool(detected),
            "side": side,
            "body_ratio": round(float(body_ratio), 3),
        }

    def _absorption(self, volume_ratio):
        last = self.df.iloc[-1]
        candle_range = max(float(last["high"] - last["low"]), 0.00000001)
        body = abs(float(last["close"] - last["open"]))
        upper_wick = float(last["high"] - max(last["open"], last["close"]))
        lower_wick = float(min(last["open"], last["close"]) - last["low"])
        detected = volume_ratio >= 1.5 and body / candle_range <= 0.45 and max(upper_wick, lower_wick) >= candle_range * 0.35
        if not detected:
            side = "NONE"
        elif lower_wick > upper_wick:
            side = "BUYER_ABSORPTION"
        else:
            side = "SELLER_ABSORPTION"
        return {
            "detected": bool(detected),
            "side": side,
            "wick_ratio": round(float(max(upper_wick, lower_wick) / candle_range), 3),
        }

    def _breakout_confirmation(self, volume_ratio, lookback=24):
        previous = self.df.iloc[-lookback - 1:-1]
        last = self.df.iloc[-1]
        resistance = float(previous["high"].max())
        support = float(previous["low"].min())
        if last["close"] > resistance and volume_ratio >= 1.25:
            return {"confirmed": True, "direction": "BULLISH", "level": resistance}
        if last["close"] < support and volume_ratio >= 1.25:
            return {"confirmed": True, "direction": "BEARISH", "level": support}
        return {"confirmed": False, "direction": "NONE", "level": None}

    def _price_volume_divergence(self, close, volume, lookback=20):
        price_now = float(close.iloc[-1])
        price_then = float(close.iloc[-lookback])
        volume_now = float(volume.rolling(5).mean().iloc[-1])
        volume_then = float(volume.rolling(5).mean().iloc[-lookback])
        price_change = (price_now - price_then) / max(price_then, 0.00000001)
        volume_change = (volume_now - volume_then) / max(volume_then, 0.00000001)

        if price_change > 0.015 and volume_change < -0.15:
            return {"detected": True, "type": "BEARISH_DIVERGENCE", "price_change_pct": round(price_change * 100, 3), "volume_change_pct": round(volume_change * 100, 3)}
        if price_change < -0.015 and volume_change < -0.15:
            return {"detected": True, "type": "BULLISH_DIVERGENCE", "price_change_pct": round(price_change * 100, 3), "volume_change_pct": round(volume_change * 100, 3)}
        return {"detected": False, "type": "NONE", "price_change_pct": round(price_change * 100, 3), "volume_change_pct": round(volume_change * 100, 3)}

    def _score(self, above_average, buy_sell, abnormal, exhaustion, absorption, breakout_confirmation, divergence):
        score = 0
        reasons = []
        dominant = buy_sell["dominant_side"]

        if above_average:
            score += 3
            reasons.append("Volume acima da media de 20 candles.")
        if dominant == "BUYER":
            score += 5
            reasons.append("Volume comprador dominante.")
        elif dominant == "SELLER":
            score -= 5
            reasons.append("Volume vendedor dominante.")
        if abnormal:
            score += 2 if dominant == "BUYER" else -2 if dominant == "SELLER" else 0
            reasons.append("Candle com volume anormal.")
        if exhaustion["detected"]:
            score += -7 if exhaustion["side"] == "BUYER_EXHAUSTION" else 7
            reasons.append(f"Exaustao detectada: {exhaustion['side']}.")
        if absorption["detected"]:
            score += 6 if absorption["side"] == "BUYER_ABSORPTION" else -6
            reasons.append(f"Absorcao detectada: {absorption['side']}.")
        if breakout_confirmation["confirmed"]:
            score += 8 if breakout_confirmation["direction"] == "BULLISH" else -8
            reasons.append(f"Rompimento {breakout_confirmation['direction']} confirmado por volume.")
        if divergence["detected"]:
            score += -6 if divergence["type"] == "BEARISH_DIVERGENCE" else 6
            reasons.append(f"Divergencia preco-volume: {divergence['type']}.")

        if score >= 6:
            signal = "BULLISH_VOLUME"
        elif score <= -6:
            signal = "BEARISH_VOLUME"
        else:
            signal = "NEUTRAL_VOLUME"
        return max(-20, min(20, score)), signal, reasons

    def _confidence(self, volume_ratio, zscore, reasons):
        confidence = 45 + min(volume_ratio, 3) * 10 + min(abs(zscore), 3) * 5 + len(reasons) * 3
        return int(max(20, min(95, round(confidence))))


def read_volume(candles):
    return VolumeReader(candles).read()
