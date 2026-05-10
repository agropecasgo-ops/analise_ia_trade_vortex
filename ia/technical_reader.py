"""
Leitor tecnico consolidado para o FinanceAI.

Recebe um DataFrame OHLCV com colunas open, high, low, close e volume.
Retorna uma leitura operacional em JSON serializavel.
"""

import numpy as np
import pandas as pd


class TechnicalReader:
    def __init__(self, candles):
        self.df = candles.copy().dropna(subset=["open", "high", "low", "close", "volume"])
        if len(self.df) < 60:
            raise ValueError("technical_reader_requires_at_least_60_candles")

    def read(self):
        indicators = self._indicators()
        trend = self._trend(indicators)
        ma_cross = self._moving_average_cross(indicators)
        support_resistance = self._support_resistance()
        candle_strength = self._candle_strength(indicators)
        breakout = self._breakout(support_resistance, indicators)
        pullback = self._pullback(indicators)
        lateralization = self._lateralization(indicators)

        confirmations = []
        invalidations = []
        score = 0.0

        score += self._score_trend(trend, confirmations, invalidations)
        score += self._score_cross(ma_cross, confirmations)
        score += self._score_rsi(indicators["rsi"], confirmations, invalidations)
        score += self._score_macd(indicators, confirmations, invalidations)
        score += self._score_vwap(indicators, confirmations, invalidations)
        score += self._score_bollinger(indicators, confirmations, invalidations)
        score += self._score_candle_strength(candle_strength, confirmations, invalidations)
        score += self._score_breakout_pullback(breakout, pullback, confirmations, invalidations)

        if lateralization["detected"]:
            score *= 0.55
            invalidations.append(f"Lateralizacao detectada: range de {lateralization['range_pct']:.2f}%.")

        signal = self._signal_from_score(score)
        entry_price = float(self.df["close"].iloc[-1])
        levels = self._risk_levels(signal, entry_price, indicators["atr"])
        confidence = self._confidence(score, confirmations, invalidations, lateralization)

        return {
            "signal": signal,
            "score": round(float(score), 3),
            "confidence": confidence,
            "trend": trend,
            "confirmations": confirmations,
            "invalidations": invalidations,
            "entry_price": round(entry_price, 8),
            "stop_loss": levels["stop_loss"],
            "take_profit_1": levels["take_profit_1"],
            "take_profit_2": levels["take_profit_2"],
            "take_profit_3": levels["take_profit_3"],
            "explanation": self._explanation(signal, trend, confirmations, invalidations),
            "details": {
                "ema": {
                    "ema9": round(indicators["ema9"], 8),
                    "ema21": round(indicators["ema21"], 8),
                    "ema50": round(indicators["ema50"], 8),
                    "ema200": round(indicators["ema200"], 8),
                },
                "moving_average_cross": ma_cross,
                "rsi": round(indicators["rsi"], 3),
                "macd": {
                    "macd": round(indicators["macd"], 8),
                    "signal": round(indicators["macd_signal"], 8),
                    "histogram": round(indicators["macd_histogram"], 8),
                },
                "bollinger_bands": {
                    "upper": round(indicators["bb_upper"], 8),
                    "middle": round(indicators["bb_middle"], 8),
                    "lower": round(indicators["bb_lower"], 8),
                    "position": indicators["bb_position"],
                },
                "vwap": round(indicators["vwap"], 8),
                "atr": round(indicators["atr"], 8),
                "support_resistance": support_resistance,
                "candle_strength": candle_strength,
                "breakout": breakout,
                "pullback": pullback,
                "lateralization": lateralization,
            },
        }

    def _indicators(self):
        close = self.df["close"]
        high = self.df["high"]
        low = self.df["low"]
        volume = self.df["volume"]

        ema9 = close.ewm(span=9, adjust=False).mean()
        ema21 = close.ewm(span=21, adjust=False).mean()
        ema50 = close.ewm(span=50, adjust=False).mean()
        ema200 = close.ewm(span=200, adjust=False).mean()
        rsi = self._rsi(close)
        macd_line, macd_signal, macd_hist = self._macd(close)
        bb_upper, bb_middle, bb_lower = self._bollinger(close)
        atr = self._atr(high, low, close)
        vwap = self._vwap(high, low, close, volume)
        volume_sma = volume.rolling(20).mean().bfill()

        last_close = close.iloc[-1]
        bb_width = max(bb_upper.iloc[-1] - bb_lower.iloc[-1], 0.00000001)
        bb_position = (last_close - bb_lower.iloc[-1]) / bb_width

        return {
            "ema9_series": ema9,
            "ema21_series": ema21,
            "ema50_series": ema50,
            "ema200_series": ema200,
            "ema9": float(ema9.iloc[-1]),
            "ema21": float(ema21.iloc[-1]),
            "ema50": float(ema50.iloc[-1]),
            "ema200": float(ema200.iloc[-1]),
            "rsi": float(rsi.iloc[-1]),
            "macd": float(macd_line.iloc[-1]),
            "macd_signal": float(macd_signal.iloc[-1]),
            "macd_histogram": float(macd_hist.iloc[-1]),
            "macd_histogram_prev": float(macd_hist.iloc[-2]),
            "bb_upper": float(bb_upper.iloc[-1]),
            "bb_middle": float(bb_middle.iloc[-1]),
            "bb_lower": float(bb_lower.iloc[-1]),
            "bb_position": round(float(bb_position), 3),
            "atr": float(atr.iloc[-1]),
            "atr_pct": float(atr.iloc[-1] / last_close * 100),
            "vwap": float(vwap.iloc[-1]),
            "volume_sma": float(volume_sma.iloc[-1]),
            "last_close": float(last_close),
            "last_volume": float(volume.iloc[-1]),
        }

    def _rsi(self, close, period=14):
        delta = close.diff()
        gain = delta.where(delta > 0, 0).rolling(period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
        rs = gain / loss.replace(0, np.nan)
        return (100 - (100 / (1 + rs))).fillna(50)

    def _macd(self, close, fast=12, slow=26, signal=9):
        ema_fast = close.ewm(span=fast, adjust=False).mean()
        ema_slow = close.ewm(span=slow, adjust=False).mean()
        macd = ema_fast - ema_slow
        macd_signal = macd.ewm(span=signal, adjust=False).mean()
        return macd, macd_signal, macd - macd_signal

    def _bollinger(self, close, period=20, std_dev=2):
        middle = close.rolling(period).mean()
        std = close.rolling(period).std()
        return middle + std * std_dev, middle, middle - std * std_dev

    def _atr(self, high, low, close, period=14):
        high_low = high - low
        high_close = (high - close.shift()).abs()
        low_close = (low - close.shift()).abs()
        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        return true_range.rolling(period).mean().bfill()

    def _vwap(self, high, low, close, volume):
        typical = (high + low + close) / 3
        cumulative_volume = volume.cumsum().replace(0, np.nan)
        return ((typical * volume).cumsum() / cumulative_volume).ffill()

    def _trend(self, indicators):
        price = indicators["last_close"]
        ema9 = indicators["ema9"]
        ema21 = indicators["ema21"]
        ema50 = indicators["ema50"]
        ema200 = indicators["ema200"]

        if price > ema9 > ema21 > ema50 > ema200:
            direction = "STRONG_BULLISH"
        elif price < ema9 < ema21 < ema50 < ema200:
            direction = "STRONG_BEARISH"
        elif price > ema50 and ema9 > ema21:
            direction = "BULLISH"
        elif price < ema50 and ema9 < ema21:
            direction = "BEARISH"
        else:
            direction = "SIDEWAYS"

        return {
            "direction": direction,
            "price_above_ema200": bool(price > ema200),
            "ema_stack": {
                "ema9_gt_ema21": bool(ema9 > ema21),
                "ema21_gt_ema50": bool(ema21 > ema50),
                "ema50_gt_ema200": bool(ema50 > ema200),
            },
        }

    def _moving_average_cross(self, indicators):
        ema9 = indicators["ema9_series"]
        ema21 = indicators["ema21_series"]
        ema50 = indicators["ema50_series"]
        bullish_9_21 = ema9.iloc[-1] > ema21.iloc[-1] and ema9.iloc[-2] <= ema21.iloc[-2]
        bearish_9_21 = ema9.iloc[-1] < ema21.iloc[-1] and ema9.iloc[-2] >= ema21.iloc[-2]
        bullish_21_50 = ema21.iloc[-1] > ema50.iloc[-1] and ema21.iloc[-2] <= ema50.iloc[-2]
        bearish_21_50 = ema21.iloc[-1] < ema50.iloc[-1] and ema21.iloc[-2] >= ema50.iloc[-2]

        if bullish_9_21 or bullish_21_50:
            direction = "BULLISH_CROSS"
        elif bearish_9_21 or bearish_21_50:
            direction = "BEARISH_CROSS"
        else:
            direction = "NONE"

        return {
            "direction": direction,
            "ema9_ema21": "bullish" if bullish_9_21 else "bearish" if bearish_9_21 else "none",
            "ema21_ema50": "bullish" if bullish_21_50 else "bearish" if bearish_21_50 else "none",
        }

    def _support_resistance(self, lookback=60):
        frame = self.df.tail(lookback)
        supports = []
        resistances = []
        for i in range(2, len(frame) - 2):
            local = frame.iloc[i - 2:i + 3]
            candle = frame.iloc[i]
            if candle["low"] == local["low"].min():
                supports.append(float(candle["low"]))
            if candle["high"] == local["high"].max():
                resistances.append(float(candle["high"]))

        price = float(self.df["close"].iloc[-1])
        supports = sorted([value for value in supports if value < price], reverse=True)[:3]
        resistances = sorted([value for value in resistances if value > price])[:3]
        return {
            "supports": [round(value, 8) for value in supports],
            "resistances": [round(value, 8) for value in resistances],
            "nearest_support": round(supports[0], 8) if supports else None,
            "nearest_resistance": round(resistances[0], 8) if resistances else None,
        }

    def _candle_strength(self, indicators):
        candle = self.df.iloc[-1]
        full_range = max(float(candle["high"] - candle["low"]), 0.00000001)
        body = abs(float(candle["close"] - candle["open"]))
        body_ratio = body / full_range
        volume_ratio = indicators["last_volume"] / max(indicators["volume_sma"], 0.00000001)
        direction = "bullish" if candle["close"] > candle["open"] else "bearish" if candle["close"] < candle["open"] else "neutral"
        strong = body_ratio >= 0.58 and volume_ratio >= 1.15
        return {
            "direction": direction,
            "strong": bool(strong),
            "body_ratio": round(float(body_ratio), 3),
            "volume_ratio": round(float(volume_ratio), 3),
        }

    def _breakout(self, support_resistance, indicators):
        price = indicators["last_close"]
        previous = self.df.iloc[-25:-1]
        prior_high = float(previous["high"].max())
        prior_low = float(previous["low"].min())
        atr = max(indicators["atr"], 0.00000001)
        if price > prior_high:
            return {"detected": True, "direction": "bullish", "level": round(prior_high, 8), "strength": round(min((price - prior_high) / atr, 2), 3)}
        if price < prior_low:
            return {"detected": True, "direction": "bearish", "level": round(prior_low, 8), "strength": round(min((prior_low - price) / atr, 2), 3)}
        return {"detected": False, "direction": "none", "level": None, "strength": 0}

    def _pullback(self, indicators):
        candle = self.df.iloc[-1]
        ema21 = indicators["ema21"]
        ema50 = indicators["ema50"]
        bullish = indicators["ema9"] > indicators["ema21"] and candle["low"] <= ema21 <= candle["close"]
        bearish = indicators["ema9"] < indicators["ema21"] and candle["high"] >= ema21 >= candle["close"]
        deep_bullish = indicators["last_close"] > indicators["ema200"] and candle["low"] <= ema50 <= candle["close"]
        deep_bearish = indicators["last_close"] < indicators["ema200"] and candle["high"] >= ema50 >= candle["close"]
        if bullish or deep_bullish:
            return {"detected": True, "direction": "bullish", "reference": "EMA21" if bullish else "EMA50"}
        if bearish or deep_bearish:
            return {"detected": True, "direction": "bearish", "reference": "EMA21" if bearish else "EMA50"}
        return {"detected": False, "direction": "none", "reference": None}

    def _lateralization(self, indicators):
        frame = self.df.tail(30)
        price = indicators["last_close"]
        range_pct = (frame["high"].max() - frame["low"].min()) / price * 100
        ema_spread = abs(indicators["ema9"] - indicators["ema50"]) / price * 100
        detected = range_pct < max(2.4, indicators["atr_pct"] * 2.2) and ema_spread < 0.55
        return {
            "detected": bool(detected),
            "range_pct": round(float(range_pct), 3),
            "ema_spread_pct": round(float(ema_spread), 3),
        }

    def _score_trend(self, trend, confirmations, invalidations):
        direction = trend["direction"]
        if direction == "STRONG_BULLISH":
            confirmations.append("Tendencia forte de alta: preco e EMAs 9/21/50/200 alinhadas.")
            return 2.0
        if direction == "BULLISH":
            confirmations.append("Tendencia de alta moderada acima da EMA50.")
            return 1.1
        if direction == "STRONG_BEARISH":
            confirmations.append("Tendencia forte de baixa: preco e EMAs 9/21/50/200 alinhadas.")
            return -2.0
        if direction == "BEARISH":
            confirmations.append("Tendencia de baixa moderada abaixo da EMA50.")
            return -1.1
        invalidations.append("Tendencia sem alinhamento claro.")
        return 0.0

    def _score_cross(self, cross, confirmations):
        if cross["direction"] == "BULLISH_CROSS":
            confirmations.append("Cruzamento de medias comprador detectado.")
            return 0.9
        if cross["direction"] == "BEARISH_CROSS":
            confirmations.append("Cruzamento de medias vendedor detectado.")
            return -0.9
        return 0.0

    def _score_rsi(self, rsi, confirmations, invalidations):
        if 45 <= rsi <= 65:
            confirmations.append(f"RSI saudavel para compra: {rsi:.1f}.")
            return 0.55
        if 35 <= rsi < 45:
            confirmations.append(f"RSI favorece repique vendedor/controlado: {rsi:.1f}.")
            return -0.35
        if rsi > 74:
            invalidations.append(f"RSI sobrecomprado: {rsi:.1f}.")
            return -0.45
        if rsi < 26:
            invalidations.append(f"RSI sobrevendido: {rsi:.1f}.")
            return 0.45
        return 0.0

    def _score_macd(self, indicators, confirmations, invalidations):
        hist = indicators["macd_histogram"]
        prev = indicators["macd_histogram_prev"]
        if indicators["macd"] > indicators["macd_signal"] and hist > prev:
            confirmations.append("MACD comprador e histograma acelerando.")
            return 0.75
        if indicators["macd"] < indicators["macd_signal"] and hist < prev:
            confirmations.append("MACD vendedor e histograma acelerando.")
            return -0.75
        invalidations.append("MACD sem aceleracao favoravel.")
        return 0.0

    def _score_vwap(self, indicators, confirmations, invalidations):
        if indicators["last_close"] > indicators["vwap"]:
            confirmations.append("Preco acima do VWAP.")
            return 0.45
        invalidations.append("Preco abaixo do VWAP.")
        return -0.45

    def _score_bollinger(self, indicators, confirmations, invalidations):
        pos = indicators["bb_position"]
        if 0.45 <= pos <= 0.85:
            confirmations.append("Preco em zona construtiva dentro das Bandas de Bollinger.")
            return 0.25
        if pos > 1.03:
            invalidations.append("Preco esticado acima da Banda de Bollinger superior.")
            return -0.35
        if pos < -0.03:
            invalidations.append("Preco esticado abaixo da Banda de Bollinger inferior.")
            return 0.2
        return 0.0

    def _score_candle_strength(self, candle_strength, confirmations, invalidations):
        if candle_strength["strong"] and candle_strength["direction"] == "bullish":
            confirmations.append("Candle de forca comprador com volume acima da media.")
            return 0.8
        if candle_strength["strong"] and candle_strength["direction"] == "bearish":
            confirmations.append("Candle de forca vendedor com volume acima da media.")
            return -0.8
        invalidations.append("Ultimo candle sem forca institucional relevante.")
        return 0.0

    def _score_breakout_pullback(self, breakout, pullback, confirmations, invalidations):
        score = 0.0
        if breakout["detected"] and breakout["direction"] == "bullish":
            confirmations.append(f"Rompimento comprador acima de {breakout['level']}.")
            score += 0.8
        elif breakout["detected"] and breakout["direction"] == "bearish":
            confirmations.append(f"Rompimento vendedor abaixo de {breakout['level']}.")
            score -= 0.8

        if pullback["detected"] and pullback["direction"] == "bullish":
            confirmations.append(f"Pullback comprador na {pullback['reference']}.")
            score += 0.65
        elif pullback["detected"] and pullback["direction"] == "bearish":
            confirmations.append(f"Pullback vendedor na {pullback['reference']}.")
            score -= 0.65

        if not breakout["detected"] and not pullback["detected"]:
            invalidations.append("Sem rompimento ou pullback claro.")
        return score

    def _signal_from_score(self, score):
        if score >= 1.45:
            return "BUY"
        if score <= -1.45:
            return "SELL"
        return "NEUTRAL"

    def _risk_levels(self, signal, entry_price, atr):
        atr = max(float(atr), entry_price * 0.002)
        if signal == "SELL":
            stop = entry_price + atr * 1.5
            risk = stop - entry_price
            targets = [entry_price - risk * multiple for multiple in (1.0, 1.8, 2.8)]
        else:
            stop = entry_price - atr * 1.5
            risk = entry_price - stop
            targets = [entry_price + risk * multiple for multiple in (1.0, 1.8, 2.8)]
        return {
            "stop_loss": round(float(stop), 8),
            "take_profit_1": round(float(targets[0]), 8),
            "take_profit_2": round(float(targets[1]), 8),
            "take_profit_3": round(float(targets[2]), 8),
        }

    def _confidence(self, score, confirmations, invalidations, lateralization):
        raw = 45 + abs(score) * 8 + len(confirmations) * 3 - len(invalidations) * 2
        if lateralization["detected"]:
            raw -= 12
        return int(max(10, min(95, round(raw))))

    def _explanation(self, signal, trend, confirmations, invalidations):
        direction = trend["direction"]
        if signal == "BUY":
            bias = "Leitura favorece compra."
        elif signal == "SELL":
            bias = "Leitura favorece venda."
        else:
            bias = "Leitura neutra, sem assimetria suficiente."

        positive = " ".join(confirmations[:4]) if confirmations else "Sem confirmacoes fortes."
        negative = " ".join(invalidations[:3]) if invalidations else "Sem invalidacoes criticas."
        return f"{bias} Tendencia: {direction}. Confirmacoes: {positive} Invalidacoes: {negative}"


def read_technical(candles):
    return TechnicalReader(candles).read()
