"""
Smart Money Concepts para o FinanceAI.

Detecta BOS, CHOCH, order blocks, zonas de liquidez, fair value gaps,
sweep de liquidez, falso rompimento e zonas institucionais.
"""

import numpy as np
import pandas as pd


def _time(index):
    return int(pd.Timestamp(index).timestamp())


class SmartMoneyAnalyzer:
    def __init__(self, candles, swing_window=3):
        self.df = candles.copy().dropna(subset=["open", "high", "low", "close", "volume"])
        self.swing_window = swing_window
        if len(self.df) < swing_window * 2 + 20:
            raise ValueError("smart_money_requires_more_candles")

    def analyze(self, signal_type="neutro"):
        swings = self._swings()
        structure = self._structure(swings)
        order_blocks = self._order_blocks()
        liquidity_zones = self._liquidity_zones(swings)
        fair_value_gaps = self._fair_value_gaps()
        liquidity_sweep = self._liquidity_sweep(liquidity_zones)
        false_breakout = self._false_breakout()
        institutional_zones = self._institutional_zones(order_blocks, fair_value_gaps, liquidity_zones)
        nearest_order_block = self._nearest_zone(order_blocks)
        relevant_fvg = self._nearest_zone(fair_value_gaps)
        nearest_liquidity_zone = self._nearest_zone(liquidity_zones)
        inducement = self._inducement(liquidity_zones, structure)
        institutional_bias = self._institutional_bias(structure, nearest_order_block, relevant_fvg, liquidity_sweep, false_breakout)
        score_adjustment = self._score_adjustment(
            signal_type,
            structure,
            nearest_order_block,
            relevant_fvg,
            nearest_liquidity_zone,
            liquidity_sweep,
            false_breakout,
            institutional_bias,
            inducement,
        )
        confirmed = score_adjustment["confirmed"]
        invalidated = score_adjustment["invalidated"]
        smc_score = int(max(0, min(100, 50 + score_adjustment["value"] * 2)))
        confirmations = score_adjustment["confirmations"]
        invalidations = score_adjustment["invalidations"]
        explanation = self._explanation(institutional_bias, structure, nearest_order_block, relevant_fvg, nearest_liquidity_zone, liquidity_sweep, false_breakout)

        return {
            "smc_score": smc_score,
            "institutional_bias": institutional_bias,
            "has_bos": structure["bos"] != "none",
            "bos": structure["bos"],
            "has_choch": structure["choch"] != "none",
            "choch": structure["choch"],
            "liquidity_zone": nearest_liquidity_zone,
            "nearest_order_block": nearest_order_block,
            "relevant_order_block": nearest_order_block,
            "relevant_fvg": relevant_fvg,
            "liquidity_sweep": liquidity_sweep,
            "false_breakout": false_breakout,
            "inducement": inducement,
            "institutional_zone": institutional_zones[0] if institutional_zones else None,
            "institutional_zones": institutional_zones,
            "confirmed": confirmed,
            "invalidated": invalidated,
            "score_adjustment": score_adjustment["value"],
            "reasons": score_adjustment["reasons"],
            "confirmations": confirmations,
            "invalidations": invalidations,
            "explanation": explanation,
            "structure": structure,
            "order_blocks": order_blocks,
            "liquidity": liquidity_zones,
            "fair_value_gaps": fair_value_gaps,
        }

    def _swings(self):
        highs = []
        lows = []
        w = self.swing_window
        for i in range(w, len(self.df) - w):
            window = self.df.iloc[i - w:i + w + 1]
            candle = self.df.iloc[i]
            if candle["high"] == window["high"].max():
                highs.append({"index": i, "time": _time(self.df.index[i]), "price": float(candle["high"])})
            if candle["low"] == window["low"].min():
                lows.append({"index": i, "time": _time(self.df.index[i]), "price": float(candle["low"])})
        return {"highs": highs, "lows": lows}

    def _structure(self, swings):
        highs = swings["highs"]
        lows = swings["lows"]
        close = float(self.df["close"].iloc[-1])
        previous_close = float(self.df["close"].iloc[-2])
        last_high = highs[-1] if highs else None
        last_low = lows[-1] if lows else None

        trend = "neutral"
        if len(highs) >= 2 and len(lows) >= 2:
            if highs[-1]["price"] > highs[-2]["price"] and lows[-1]["price"] > lows[-2]["price"]:
                trend = "bullish"
            elif highs[-1]["price"] < highs[-2]["price"] and lows[-1]["price"] < lows[-2]["price"]:
                trend = "bearish"

        bos = "none"
        choch = "none"
        break_level = None
        if last_high and previous_close <= last_high["price"] < close:
            bos = "bullish"
            break_level = last_high["price"]
            if trend == "bearish":
                choch = "bullish"
        elif last_low and previous_close >= last_low["price"] > close:
            bos = "bearish"
            break_level = last_low["price"]
            if trend == "bullish":
                choch = "bearish"

        return {
            "trend": trend,
            "bos": bos,
            "choch": choch,
            "break_level": float(break_level) if break_level else None,
            "last_high": last_high,
            "last_low": last_low,
        }

    def _atr(self, period=14):
        high_low = self.df["high"] - self.df["low"]
        high_close = (self.df["high"] - self.df["close"].shift()).abs()
        low_close = (self.df["low"] - self.df["close"].shift()).abs()
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        return tr.rolling(period).mean().bfill()

    def _order_blocks(self, lookback=120):
        blocks = []
        frame = self.df.tail(lookback)
        atr = float(self._atr().iloc[-1])
        atr = atr if atr > 0 else float(self.df["close"].iloc[-1]) * 0.01
        for i in range(2, len(frame) - 3):
            candle = frame.iloc[i]
            impulse = frame.iloc[i + 1:i + 4]
            move = float(impulse["close"].iloc[-1] - candle["close"])
            body = abs(float(candle["close"] - candle["open"]))
            is_bullish_ob = candle["close"] < candle["open"] and move > atr * 1.2
            is_bearish_ob = candle["close"] > candle["open"] and move < -atr * 1.2
            if body <= atr * 1.1 and (is_bullish_ob or is_bearish_ob):
                high = float(candle["high"])
                low = float(candle["low"])
                blocks.append({
                    "type": "bullish" if is_bullish_ob else "bearish",
                    "time": _time(frame.index[i]),
                    "high": high,
                    "low": low,
                    "mid": float((high + low) / 2),
                    "strength": round(min(abs(move) / atr, 3.0), 3),
                })
        return blocks[-10:]

    def _liquidity_zones(self, swings, tolerance=0.0018):
        zones = []

        def build(points, zone_type):
            used = set()
            for i, point in enumerate(points):
                if i in used:
                    continue
                cluster = [point]
                for j, other in enumerate(points[i + 1:], start=i + 1):
                    if abs(other["price"] - point["price"]) / point["price"] <= tolerance:
                        cluster.append(other)
                        used.add(j)
                if len(cluster) >= 2:
                    prices = [item["price"] for item in cluster]
                    zones.append({
                        "type": zone_type,
                        "price": float(np.mean(prices)),
                        "low": float(min(prices)),
                        "high": float(max(prices)),
                        "touches": len(cluster),
                        "time": cluster[-1]["time"],
                    })

        build(swings["highs"][-20:], "buy_side")
        build(swings["lows"][-20:], "sell_side")
        return sorted(zones[-12:], key=lambda item: item["touches"], reverse=True)

    def _fair_value_gaps(self, lookback=160):
        gaps = []
        frame = self.df.tail(lookback)
        for i in range(2, len(frame)):
            c1 = frame.iloc[i - 2]
            c3 = frame.iloc[i]
            if c1["high"] < c3["low"]:
                gaps.append({
                    "type": "bullish",
                    "time": _time(frame.index[i]),
                    "low": float(c1["high"]),
                    "high": float(c3["low"]),
                    "mid": float((c1["high"] + c3["low"]) / 2),
                })
            elif c1["low"] > c3["high"]:
                gaps.append({
                    "type": "bearish",
                    "time": _time(frame.index[i]),
                    "low": float(c3["high"]),
                    "high": float(c1["low"]),
                    "mid": float((c3["high"] + c1["low"]) / 2),
                })
        return gaps[-12:]

    def _liquidity_sweep(self, liquidity_zones):
        if not liquidity_zones:
            return {"detected": False, "side": "none", "zone": None}
        last = self.df.iloc[-1]
        for zone in liquidity_zones:
            if zone["type"] == "buy_side" and last["high"] > zone["high"] and last["close"] < zone["price"]:
                return {"detected": True, "side": "buy_side_sweep", "zone": zone}
            if zone["type"] == "sell_side" and last["low"] < zone["low"] and last["close"] > zone["price"]:
                return {"detected": True, "side": "sell_side_sweep", "zone": zone}
        return {"detected": False, "side": "none", "zone": None}

    def _false_breakout(self, lookback=24):
        frame = self.df.iloc[-lookback - 1:-1]
        last = self.df.iloc[-1]
        resistance = float(frame["high"].max())
        support = float(frame["low"].min())
        if last["high"] > resistance and last["close"] < resistance:
            return {"detected": True, "direction": "bullish_failed", "level": resistance}
        if last["low"] < support and last["close"] > support:
            return {"detected": True, "direction": "bearish_failed", "level": support}
        return {"detected": False, "direction": "none", "level": None}

    def _inducement(self, liquidity_zones, structure):
        if not liquidity_zones:
            return {"detected": False, "side": "none", "zone": None}
        last = self.df.iloc[-1]
        body_high = max(float(last["open"]), float(last["close"]))
        body_low = min(float(last["open"]), float(last["close"]))
        for zone in liquidity_zones:
            distance = self._distance_to_price(zone)
            near_zone = distance <= 0.006
            if zone["type"] == "buy_side" and near_zone and body_high < zone["price"] and structure["bos"] != "bullish":
                return {"detected": True, "side": "buy_side_inducement", "zone": zone}
            if zone["type"] == "sell_side" and near_zone and body_low > zone["price"] and structure["bos"] != "bearish":
                return {"detected": True, "side": "sell_side_inducement", "zone": zone}
        return {"detected": False, "side": "none", "zone": None}

    def _institutional_bias(self, structure, order_block, fvg, sweep, false_breakout):
        score = 0
        if structure["trend"] == "bullish":
            score += 2
        elif structure["trend"] == "bearish":
            score -= 2
        if structure["bos"] == "bullish" or structure["choch"] == "bullish":
            score += 2
        elif structure["bos"] == "bearish" or structure["choch"] == "bearish":
            score -= 2
        if order_block:
            score += 1 if order_block["type"] == "bullish" else -1
        if fvg:
            score += 1 if fvg["type"] == "bullish" else -1
        if sweep.get("side") == "sell_side_sweep":
            score += 2
        elif sweep.get("side") == "buy_side_sweep":
            score -= 2
        if false_breakout.get("direction") == "bullish_failed":
            score -= 3
        elif false_breakout.get("direction") == "bearish_failed":
            score += 3
        if score >= 4:
            return "bullish"
        if score <= -4:
            return "bearish"
        return "neutral"

    def _institutional_zones(self, order_blocks, fair_value_gaps, liquidity_zones):
        zones = []
        for block in order_blocks[-5:]:
            zones.append({**block, "kind": "order_block"})
        for gap in fair_value_gaps[-5:]:
            zones.append({**gap, "kind": "fair_value_gap"})
        for liquidity in liquidity_zones[:5]:
            zones.append({**liquidity, "kind": "liquidity"})
        return sorted(zones, key=lambda item: self._distance_to_price(item))[:10]

    def _nearest_zone(self, zones):
        if not zones:
            return None
        return sorted(zones, key=lambda item: self._distance_to_price(item))[0]

    def _distance_to_price(self, zone):
        price = float(self.df["close"].iloc[-1])
        reference = zone.get("mid", zone.get("price", (zone.get("high", price) + zone.get("low", price)) / 2))
        return abs(float(reference) - price) / price

    def _score_adjustment(self, signal_type, structure, order_block, fvg, liquidity_zone, sweep, false_breakout, institutional_bias, inducement):
        signal = signal_type.lower()
        is_buy = any(word in signal for word in ["compra", "entrada", "buy"])
        is_sell = any(word in signal for word in ["venda", "sell"])
        value = 0
        reasons = []
        confirmations = []
        invalidations = []

        if structure["bos"] == "bullish":
            value += 8 if is_buy else -5 if is_sell else 2
            text = "BOS comprador detectado."
            reasons.append(text)
            (confirmations if is_buy or not is_sell else invalidations).append(text)
        elif structure["bos"] == "bearish":
            value += 8 if is_sell else -5 if is_buy else 2
            text = "BOS vendedor detectado."
            reasons.append(text)
            (confirmations if is_sell or not is_buy else invalidations).append(text)

        if structure["choch"] == "bullish":
            value += 10 if is_buy else -8
            text = "CHOCH comprador detectado."
            reasons.append(text)
            (confirmations if is_buy else invalidations).append(text)
        elif structure["choch"] == "bearish":
            value += 10 if is_sell else -8
            text = "CHOCH vendedor detectado."
            reasons.append(text)
            (confirmations if is_sell else invalidations).append(text)

        if order_block:
            if order_block["type"] == "bullish":
                value += 6 if is_buy else -3
                text = "Order block comprador proximo."
                reasons.append(text)
                (confirmations if is_buy else invalidations if is_sell else confirmations).append(text)
            elif order_block["type"] == "bearish":
                value += 6 if is_sell else -3
                text = "Order block vendedor proximo."
                reasons.append(text)
                (confirmations if is_sell else invalidations if is_buy else confirmations).append(text)

        if fvg:
            if fvg["type"] == "bullish":
                value += 4 if is_buy else -2
                text = "FVG comprador relevante."
                reasons.append(text)
                (confirmations if is_buy else invalidations if is_sell else confirmations).append(text)
            elif fvg["type"] == "bearish":
                value += 4 if is_sell else -2
                text = "FVG vendedor relevante."
                reasons.append(text)
                (confirmations if is_sell else invalidations if is_buy else confirmations).append(text)

        if liquidity_zone:
            text = f"Zona de liquidez {liquidity_zone['type']} proxima."
            reasons.append(text)
            confirmations.append(text)

        if sweep["detected"]:
            if sweep["side"] == "sell_side_sweep":
                value += 8 if is_buy else -5
                text = "Sweep de liquidez vendedora favorece reversao compradora."
                reasons.append(text)
                (confirmations if is_buy else invalidations).append(text)
            elif sweep["side"] == "buy_side_sweep":
                value += 8 if is_sell else -5
                text = "Sweep de liquidez compradora favorece reversao vendedora."
                reasons.append(text)
                (confirmations if is_sell else invalidations).append(text)

        if inducement["detected"]:
            text = f"Inducement detectado em {inducement['side']}."
            reasons.append(text)
            invalidations.append(text)
            value -= 4

        if institutional_bias == "bullish" and is_buy:
            confirmations.append("Vies institucional comprador alinhado ao sinal.")
            value += 5
        elif institutional_bias == "bearish" and is_sell:
            confirmations.append("Vies institucional vendedor alinhado ao sinal.")
            value += 5
        elif institutional_bias in ["bullish", "bearish"] and (is_buy or is_sell):
            invalidations.append("Vies institucional contra o sinal.")
            value -= 7

        if false_breakout["detected"]:
            value -= 15
            text = "Falso rompimento invalida a leitura direcional."
            reasons.append(text)
            invalidations.append(text)

        confirmed = value >= 8 and not false_breakout["detected"]
        invalidated = value <= -8 or false_breakout["detected"]
        return {
            "value": int(max(-25, min(25, value))),
            "confirmed": bool(confirmed),
            "invalidated": bool(invalidated),
            "reasons": reasons,
            "confirmations": confirmations[:8],
            "invalidations": invalidations[:8],
        }

    def _explanation(self, bias, structure, order_block, fvg, liquidity_zone, sweep, false_breakout):
        parts = [f"Vies institucional {bias} com estrutura {structure['trend']}."]
        if structure["bos"] != "none":
            parts.append(f"BOS {structure['bos']} no nivel {structure.get('break_level')}.")
        if structure["choch"] != "none":
            parts.append(f"CHOCH {structure['choch']} indica possivel mudanca de carater.")
        if order_block:
            parts.append(f"Order block {order_block['type']} relevante entre {order_block['low']} e {order_block['high']}.")
        if fvg:
            parts.append(f"FVG {fvg['type']} relevante entre {fvg['low']} e {fvg['high']}.")
        if liquidity_zone:
            parts.append(f"Liquidez {liquidity_zone['type']} proxima em {liquidity_zone['price']}.")
        if sweep.get("detected"):
            parts.append(f"Sweep detectado: {sweep['side']}.")
        if false_breakout.get("detected"):
            parts.append(f"Rompimento falso em {false_breakout['level']}.")
        return " ".join(parts)


def analyze_smart_money(candles, signal_type="neutro"):
    return SmartMoneyAnalyzer(candles).analyze(signal_type)
