"""
Ferramentas institucionais: SMC, validacao operacional e backtest profissional.
"""

import math

import numpy as np
import pandas as pd

from .analysis import AISignalGenerator, RiskManagement, TechnicalAnalysis


def _ts(index):
    return int(pd.Timestamp(index).timestamp())


class SmartMoneyConcepts:
    """Detecta BOS, CHOCH, order blocks, liquidez e fair value gaps."""

    def __init__(self, data):
        self.data = data.copy()

    def swing_points(self, window=3):
        highs = []
        lows = []
        if len(self.data) < window * 2 + 1:
            return highs, lows
        for i in range(window, len(self.data) - window):
            area = self.data.iloc[i - window:i + window + 1]
            candle = self.data.iloc[i]
            if candle["high"] == area["high"].max():
                highs.append({"index": i, "time": _ts(self.data.index[i]), "price": float(candle["high"])})
            if candle["low"] == area["low"].min():
                lows.append({"index": i, "time": _ts(self.data.index[i]), "price": float(candle["low"])})
        return highs, lows

    def detect_bos_choch(self):
        highs, lows = self.swing_points()
        close = float(self.data["close"].iloc[-1])
        previous_close = float(self.data["close"].iloc[-2]) if len(self.data) > 1 else close
        last_high = highs[-1] if highs else None
        last_low = lows[-1] if lows else None

        trend = "neutral"
        if len(highs) >= 2 and len(lows) >= 2:
            higher_high = highs[-1]["price"] > highs[-2]["price"]
            higher_low = lows[-1]["price"] > lows[-2]["price"]
            lower_high = highs[-1]["price"] < highs[-2]["price"]
            lower_low = lows[-1]["price"] < lows[-2]["price"]
            if higher_high and higher_low:
                trend = "bullish"
            elif lower_high and lower_low:
                trend = "bearish"

        bos = "none"
        choch = "none"
        if last_high and previous_close <= last_high["price"] < close:
            bos = "bullish"
            if trend == "bearish":
                choch = "bullish"
        if last_low and previous_close >= last_low["price"] > close:
            bos = "bearish"
            if trend == "bullish":
                choch = "bearish"

        return {"trend": trend, "bos": bos, "choch": choch, "last_high": last_high, "last_low": last_low}

    def detect_order_blocks(self, lookback=80):
        blocks = []
        frame = self.data.tail(lookback)
        atr = TechnicalAnalysis(self.data).calculate_atr(14).iloc[-1]
        atr = atr if pd.notna(atr) and atr > 0 else self.data["close"].iloc[-1] * 0.01

        for i in range(2, len(frame) - 2):
            candle = frame.iloc[i]
            next_move = frame.iloc[i + 1:i + 4]
            body = abs(candle["close"] - candle["open"])
            impulse = abs(next_move["close"].iloc[-1] - candle["close"])
            if body < atr * 0.9 and impulse > atr * 1.2:
                bullish = candle["close"] < candle["open"] and next_move["close"].iloc[-1] > candle["high"]
                bearish = candle["close"] > candle["open"] and next_move["close"].iloc[-1] < candle["low"]
                if bullish or bearish:
                    blocks.append({
                        "type": "bullish" if bullish else "bearish",
                        "time": _ts(frame.index[i]),
                        "high": float(candle["high"]),
                        "low": float(candle["low"]),
                        "mid": float((candle["high"] + candle["low"]) / 2),
                    })
        return blocks[-6:]

    def detect_liquidity(self, tolerance=0.0015):
        highs, lows = self.swing_points()
        pools = []

        def clustered(points, pool_type):
            for i, point in enumerate(points):
                nearby = [
                    other for other in points[i + 1:]
                    if abs(other["price"] - point["price"]) / point["price"] <= tolerance
                ]
                if nearby:
                    prices = [point["price"]] + [item["price"] for item in nearby]
                    pools.append({
                        "type": pool_type,
                        "price": float(np.mean(prices)),
                        "touches": len(prices),
                        "time": point["time"],
                    })

        clustered(highs[-12:], "buy_side")
        clustered(lows[-12:], "sell_side")
        return sorted(pools[-8:], key=lambda item: item["touches"], reverse=True)

    def detect_fair_value_gaps(self, lookback=120):
        gaps = []
        frame = self.data.tail(lookback)
        for i in range(2, len(frame)):
            c1 = frame.iloc[i - 2]
            c3 = frame.iloc[i]
            if c1["high"] < c3["low"]:
                gaps.append({
                    "type": "bullish",
                    "time": _ts(frame.index[i]),
                    "low": float(c1["high"]),
                    "high": float(c3["low"]),
                    "mid": float((c1["high"] + c3["low"]) / 2),
                })
            elif c1["low"] > c3["high"]:
                gaps.append({
                    "type": "bearish",
                    "time": _ts(frame.index[i]),
                    "low": float(c3["high"]),
                    "high": float(c1["low"]),
                    "mid": float((c3["high"] + c1["low"]) / 2),
                })
        return gaps[-8:]

    def analyze(self):
        return {
            "structure": self.detect_bos_choch(),
            "order_blocks": self.detect_order_blocks(),
            "liquidity": self.detect_liquidity(),
            "fair_value_gaps": self.detect_fair_value_gaps(),
        }


class OperationalValidator:
    """Valida entradas e invalida cenarios ruins."""

    def __init__(self, data, signal, levels, smc):
        self.data = data
        self.signal = signal
        self.levels = levels
        self.smc = smc
        self.ta = TechnicalAnalysis(data)

    def detect_false_breakout(self, lookback=20):
        previous = self.data.iloc[-lookback - 1:-1]
        last = self.data.iloc[-1]
        resistance = previous["high"].max()
        support = previous["low"].min()
        upper_reject = last["high"] > resistance and last["close"] < resistance
        lower_reject = last["low"] < support and last["close"] > support
        if upper_reject:
            return {"detected": True, "side": "bull_trap", "level": float(resistance)}
        if lower_reject:
            return {"detected": True, "side": "bear_trap", "level": float(support)}
        return {"detected": False, "side": "none", "level": None}

    def detect_lateralization(self):
        atr = self.ta.calculate_atr(14).iloc[-1]
        close = self.data["close"].iloc[-1]
        recent = self.data.tail(24)
        range_pct = (recent["high"].max() - recent["low"].min()) / close
        ema9 = self.ta.calculate_ema(9).iloc[-1]
        ema21 = self.ta.calculate_ema(21).iloc[-1]
        compressed = range_pct < 0.025 and abs(ema9 - ema21) / close < 0.003
        return {"detected": bool(compressed), "range_pct": float(range_pct * 100), "atr_pct": float(atr / close * 100)}

    def detect_pullback(self):
        structure = self.ta.identify_breakout_pullback()
        return {
            "detected": structure.get("pullback") != "none",
            "side": structure.get("pullback", "none"),
            "strength": structure.get("strength", 0),
        }

    def classify_entry_quality(self):
        confidence = self.signal.get("confidence", 50)
        rr = self.levels.get("risco_retorno", 0)
        smc_structure = self.smc.get("structure", {})
        signal_type = self.signal.get("signal_type", "neutro")
        is_buy = any(word in signal_type for word in ["compra", "entrada"])
        is_sell = "venda" in signal_type
        aligned = (
            (is_buy and smc_structure.get("bos") in ["bullish", "none"] and smc_structure.get("choch") != "bearish")
            or (is_sell and smc_structure.get("bos") in ["bearish", "none"] and smc_structure.get("choch") != "bullish")
            or signal_type == "neutro"
        )
        false_breakout = self.detect_false_breakout()
        lateral = self.detect_lateralization()

        probability = 0.35 + (confidence / 100) * 0.35 + min(rr, 2) * 0.08
        if aligned:
            probability += 0.08
        if false_breakout["detected"]:
            probability -= 0.18
        if lateral["detected"]:
            probability -= 0.12
        probability = max(0.05, min(probability, 0.92))

        if probability >= 0.72:
            quality = "institucional"
        elif probability >= 0.58:
            quality = "boa"
        elif probability >= 0.45:
            quality = "media"
        else:
            quality = "ruim"

        invalidated = false_breakout["detected"] or lateral["detected"] or quality == "ruim"
        return {
            "quality": quality,
            "probability": round(probability * 100, 1),
            "invalidated": bool(invalidated),
            "aligned_with_smc": bool(aligned),
        }

    def validate(self):
        return {
            "entry_quality": self.classify_entry_quality(),
            "false_breakout": self.detect_false_breakout(),
            "pullback": self.detect_pullback(),
            "lateralization": self.detect_lateralization(),
        }


class ProfessionalBacktest:
    """Backtest com equity curve, drawdown, profit factor e win rate."""

    def __init__(self, data, initial_capital=10000, risk_per_trade=0.01):
        self.data = data.copy()
        self.initial_capital = initial_capital
        self.risk_per_trade = risk_per_trade

    def run(self):
        capital = self.initial_capital
        equity = []
        trades = []
        position = None
        ta = TechnicalAnalysis(self.data)
        ema9 = ta.calculate_ema(9)
        ema21 = ta.calculate_ema(21)
        ema200 = ta.calculate_ema(200)
        atr = ta.calculate_atr(14)

        for i in range(210, len(self.data)):
            candle = self.data.iloc[i]
            previous = self.data.iloc[i - 1]
            bullish_cross = ema9.iloc[i] > ema21.iloc[i] and ema9.iloc[i - 1] <= ema21.iloc[i - 1]
            bearish_cross = ema9.iloc[i] < ema21.iloc[i] and ema9.iloc[i - 1] >= ema21.iloc[i - 1]

            if position:
                exit_price = None
                reason = None
                if position["side"] == "long":
                    if candle["low"] <= position["stop"]:
                        exit_price = position["stop"]
                        reason = "stop"
                    elif candle["high"] >= position["target"]:
                        exit_price = position["target"]
                        reason = "target"
                    elif bearish_cross:
                        exit_price = candle["close"]
                        reason = "signal"
                else:
                    if candle["high"] >= position["stop"]:
                        exit_price = position["stop"]
                        reason = "stop"
                    elif candle["low"] <= position["target"]:
                        exit_price = position["target"]
                        reason = "target"
                    elif bullish_cross:
                        exit_price = candle["close"]
                        reason = "signal"

                if exit_price:
                    pnl = (exit_price - position["entry"]) * position["qty"]
                    if position["side"] == "short":
                        pnl *= -1
                    capital += pnl
                    trades.append({**position, "exit": float(exit_price), "pnl": float(pnl), "reason": reason, "exit_time": _ts(self.data.index[i])})
                    position = None

            if not position:
                risk_cash = capital * self.risk_per_trade
                current_atr = atr.iloc[i] if pd.notna(atr.iloc[i]) and atr.iloc[i] > 0 else candle["close"] * 0.01
                if bullish_cross and candle["close"] > ema200.iloc[i]:
                    stop = candle["close"] - current_atr * 1.5
                    target = candle["close"] + current_atr * 2.2
                    qty = risk_cash / max(candle["close"] - stop, 0.000001)
                    position = {"side": "long", "entry": float(candle["close"]), "stop": float(stop), "target": float(target), "qty": float(qty), "entry_time": _ts(self.data.index[i])}
                elif bearish_cross and candle["close"] < ema200.iloc[i]:
                    stop = candle["close"] + current_atr * 1.5
                    target = candle["close"] - current_atr * 2.2
                    qty = risk_cash / max(stop - candle["close"], 0.000001)
                    position = {"side": "short", "entry": float(candle["close"]), "stop": float(stop), "target": float(target), "qty": float(qty), "entry_time": _ts(self.data.index[i])}

            floating = 0
            if position:
                floating = (candle["close"] - position["entry"]) * position["qty"]
                if position["side"] == "short":
                    floating *= -1
            equity.append({"time": _ts(self.data.index[i]), "value": float(capital + floating)})

        values = [point["value"] for point in equity] or [capital]
        peaks = np.maximum.accumulate(values)
        drawdowns = [(value - peak) / peak * 100 for value, peak in zip(values, peaks)]
        wins = [trade for trade in trades if trade["pnl"] > 0]
        losses = [trade for trade in trades if trade["pnl"] <= 0]
        gross_profit = sum(trade["pnl"] for trade in wins)
        gross_loss = abs(sum(trade["pnl"] for trade in losses))
        profit_factor = gross_profit / gross_loss if gross_loss else (gross_profit if gross_profit else 0)
        total_return = (values[-1] - self.initial_capital) / self.initial_capital * 100

        return {
            "total_trades": len(trades),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": len(wins) / len(trades) * 100 if trades else 0,
            "total_return": float(total_return),
            "final_capital": float(values[-1]),
            "profit_factor": float(profit_factor),
            "max_drawdown": float(min(drawdowns) if drawdowns else 0),
            "equity_curve": equity[-250:],
            "trades": trades[-50:],
        }


class PatternLearner:
    """Aprendizado leve por estatistica de setups recentes."""

    def summarize(self, backtest_result):
        trades = backtest_result.get("trades", [])
        if not trades:
            return {"sample_size": 0, "bias": "sem_amostra", "message": "Aguardando mais trades para aprender padroes."}
        long_trades = [trade for trade in trades if trade["side"] == "long"]
        short_trades = [trade for trade in trades if trade["side"] == "short"]

        def win_rate(items):
            return sum(1 for item in items if item["pnl"] > 0) / len(items) * 100 if items else 0

        long_wr = win_rate(long_trades)
        short_wr = win_rate(short_trades)
        bias = "comprador" if long_wr > short_wr + 5 else "vendedor" if short_wr > long_wr + 5 else "equilibrado"
        return {
            "sample_size": len(trades),
            "bias": bias,
            "long_win_rate": round(long_wr, 1),
            "short_win_rate": round(short_wr, 1),
            "message": "Padroes recalculados pelo historico recente do ativo.",
        }
