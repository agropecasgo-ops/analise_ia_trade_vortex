"""
Motor de analise tecnica e sinais operacionais para trading.
"""

from datetime import datetime

import numpy as np
import pandas as pd


class TechnicalAnalysis:
    """Calcula indicadores, estrutura de candles e payloads para graficos."""

    def __init__(self, price_data):
        self.data = price_data.copy()

    def calculate_sma(self, period=20):
        return self.data["close"].rolling(window=period).mean()

    def calculate_ema(self, period=20):
        return self.data["close"].ewm(span=period, adjust=False).mean()

    def calculate_rsi(self, period=14):
        delta = self.data["close"].diff()
        gain = delta.where(delta > 0, 0).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss.replace(0, np.nan)
        return (100 - (100 / (1 + rs))).fillna(50)

    def calculate_macd(self, fast=12, slow=26, signal=9):
        ema_fast = self.data["close"].ewm(span=fast, adjust=False).mean()
        ema_slow = self.data["close"].ewm(span=slow, adjust=False).mean()
        macd = ema_fast - ema_slow
        signal_line = macd.ewm(span=signal, adjust=False).mean()
        histogram = macd - signal_line
        return macd, signal_line, histogram

    def calculate_bollinger_bands(self, period=20, std_dev=2):
        middle = self.calculate_sma(period)
        std = self.data["close"].rolling(window=period).std()
        upper = middle + std * std_dev
        lower = middle - std * std_dev
        return upper, middle, lower

    def calculate_atr(self, period=14):
        high_low = self.data["high"] - self.data["low"]
        high_close = (self.data["high"] - self.data["close"].shift()).abs()
        low_close = (self.data["low"] - self.data["close"].shift()).abs()
        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        return true_range.rolling(window=period).mean().bfill()

    def calculate_vwap(self):
        typical_price = (self.data["high"] + self.data["low"] + self.data["close"]) / 3
        cumulative_volume = self.data["volume"].cumsum().replace(0, np.nan)
        return ((typical_price * self.data["volume"]).cumsum() / cumulative_volume).ffill()

    def calculate_volume_sma(self, period=20):
        return self.data["volume"].rolling(window=period).mean().bfill()

    def calculate_volume_profile(self, bins=20):
        price_bins = pd.cut(self.data["close"], bins=bins)
        return self.data.groupby(price_bins, observed=False)["volume"].sum()

    def identify_support_resistance(self, lookback=20, num_levels=3):
        levels = []
        if len(self.data) < lookback * 2 + 1:
            return levels

        for i in range(lookback, len(self.data) - lookback):
            highs = self.data["high"].iloc[i - lookback:i + lookback + 1]
            lows = self.data["low"].iloc[i - lookback:i + lookback + 1]
            if self.data["high"].iloc[i] == highs.max():
                levels.append({
                    "type": "resistance",
                    "price": float(self.data["high"].iloc[i]),
                    "date": str(self.data.index[i]),
                })
            if self.data["low"].iloc[i] == lows.min():
                levels.append({
                    "type": "support",
                    "price": float(self.data["low"].iloc[i]),
                    "date": str(self.data.index[i]),
                })
        return sorted(levels[-num_levels:], key=lambda item: item["price"], reverse=True)

    def identify_candle_patterns(self):
        patterns = []
        if len(self.data) < 3:
            return patterns

        for index, candle in self.data.tail(3).iterrows():
            full_range = max(candle["high"] - candle["low"], 0.00000001)
            body = abs(candle["close"] - candle["open"])
            wick_upper = candle["high"] - max(candle["open"], candle["close"])
            wick_lower = min(candle["open"], candle["close"]) - candle["low"]

            if body < full_range * 0.1:
                patterns.append({"name": "Doji", "time": str(index), "strength": 0.45})
            if wick_lower > body * 2 and wick_upper < body * 0.7:
                patterns.append({"name": "Martelo", "time": str(index), "strength": 0.7})
            if wick_upper > body * 2 and wick_lower < body * 0.7:
                patterns.append({"name": "Enforcado", "time": str(index), "strength": 0.7})
        return patterns

    def read_latest_candles(self, count=5):
        candles = []
        for index, candle in self.data.tail(count).iterrows():
            direction = "alta" if candle["close"] >= candle["open"] else "baixa"
            body_pct = abs(candle["close"] - candle["open"]) / max(candle["open"], 0.00000001) * 100
            candles.append({
                "time": str(index),
                "direction": direction,
                "open": float(candle["open"]),
                "high": float(candle["high"]),
                "low": float(candle["low"]),
                "close": float(candle["close"]),
                "volume": float(candle["volume"]),
                "body_pct": float(body_pct),
            })
        return candles

    def identify_breakout_pullback(self, lookback=20):
        if len(self.data) < lookback + 3:
            return {"breakout": "none", "pullback": "none", "strength": 0.0}

        previous = self.data.iloc[-lookback - 1:-1]
        last = self.data.iloc[-1]
        resistance = previous["high"].max()
        support = previous["low"].min()
        atr = self.calculate_atr(14).iloc[-1]
        atr = atr if pd.notna(atr) and atr > 0 else max(last["close"] * 0.005, 0.0001)
        ema9 = self.calculate_ema(9).iloc[-1]
        ema21 = self.calculate_ema(21).iloc[-1]

        breakout = "none"
        strength = 0.0
        if last["close"] > resistance:
            breakout = "bullish"
            strength = min((last["close"] - resistance) / atr, 1.0)
        elif last["close"] < support:
            breakout = "bearish"
            strength = min((support - last["close"]) / atr, 1.0)

        pullback = "none"
        if ema9 > ema21 and last["low"] <= ema21 <= last["close"]:
            pullback = "bullish"
            strength = max(strength, 0.65)
        elif ema9 < ema21 and last["high"] >= ema21 >= last["close"]:
            pullback = "bearish"
            strength = max(strength, 0.65)

        return {
            "breakout": breakout,
            "pullback": pullback,
            "strength": float(strength),
            "support": float(support),
            "resistance": float(resistance),
        }

    def build_indicator_snapshot(self):
        macd, macd_signal, macd_hist = self.calculate_macd()
        bb_upper, bb_mid, bb_lower = self.calculate_bollinger_bands()
        return {
            "ema9": self.calculate_ema(9),
            "ema21": self.calculate_ema(21),
            "ema200": self.calculate_ema(200),
            "rsi": self.calculate_rsi(14),
            "macd": macd,
            "macd_signal": macd_signal,
            "macd_histogram": macd_hist,
            "bollinger_upper": bb_upper,
            "bollinger_middle": bb_mid,
            "bollinger_lower": bb_lower,
            "atr": self.calculate_atr(14),
            "vwap": self.calculate_vwap(),
            "volume_sma": self.calculate_volume_sma(20),
        }

    def chart_payload(self):
        snapshot = self.build_indicator_snapshot()

        def timestamp(index):
            return int(pd.Timestamp(index).timestamp())

        candles = []
        volumes = []
        for index, row in self.data.iterrows():
            time_value = timestamp(index)
            candles.append({
                "time": time_value,
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
            })
            volumes.append({
                "time": time_value,
                "value": float(row["volume"]),
                "color": "rgba(38, 166, 154, 0.45)" if row["close"] >= row["open"] else "rgba(239, 83, 80, 0.45)",
            })

        def line_series(name):
            values = snapshot[name].dropna()
            return [{"time": timestamp(index), "value": float(value)} for index, value in values.items()]

        return {
            "candles": candles,
            "volumes": volumes,
            "overlays": {
                "ema9": line_series("ema9"),
                "ema21": line_series("ema21"),
                "ema200": line_series("ema200"),
                "bollinger_upper": line_series("bollinger_upper"),
                "bollinger_middle": line_series("bollinger_middle"),
                "bollinger_lower": line_series("bollinger_lower"),
                "vwap": line_series("vwap"),
            },
        }


class AISignalGenerator:
    """Gera compra, venda, neutro e entradas a partir de confluencias reais."""

    def __init__(self, technical_analysis):
        self.ta = technical_analysis
        self.latest_candle = technical_analysis.data.iloc[-1]

    def generate_signal(self):
        snapshot = self.ta.build_indicator_snapshot()
        current_price = float(self.latest_candle["close"])
        rsi = snapshot["rsi"].iloc[-1]
        macd = snapshot["macd"].iloc[-1]
        macd_signal = snapshot["macd_signal"].iloc[-1]
        macd_hist = snapshot["macd_histogram"].iloc[-1]
        ema9 = snapshot["ema9"].iloc[-1]
        ema21 = snapshot["ema21"].iloc[-1]
        ema200 = snapshot["ema200"].iloc[-1]
        atr = snapshot["atr"].iloc[-1]
        vwap = snapshot["vwap"].iloc[-1]
        volume_sma = snapshot["volume_sma"].iloc[-1]
        bb_upper = snapshot["bollinger_upper"].iloc[-1]
        bb_mid = snapshot["bollinger_middle"].iloc[-1]
        bb_lower = snapshot["bollinger_lower"].iloc[-1]
        structure = self.ta.identify_breakout_pullback()

        components = {
            "rsi_signal": self._analyze_rsi(rsi),
            "macd_signal": self._analyze_macd(macd, macd_signal, macd_hist),
            "trend_signal": self._analyze_trend(ema9, ema21, ema200, current_price),
            "volume_signal": self._analyze_volume(volume_sma),
            "volatility_signal": self._analyze_volatility(atr, current_price),
            "confluence_signal": self._analyze_confluence(current_price, ema9, ema21, ema200, vwap, rsi, macd, macd_signal),
            "structure_signal": self._analyze_structure(structure),
            "pattern_signal": self._analyze_patterns(),
        }
        score = self._calculate_score(components)

        return {
            "signal_type": self._determine_signal_type(score),
            "score": float(score),
            "confidence": self._calculate_confidence(components),
            "components": components,
            "structure": structure,
            "timestamp": datetime.now().isoformat(),
            "price": current_price,
            "indicators": {
                "rsi": float(rsi),
                "macd": float(macd),
                "signal": float(macd_signal),
                "histogram": float(macd_hist),
                "ema9": float(ema9),
                "ema21": float(ema21),
                "ema200": float(ema200),
                "bollinger_upper": float(bb_upper),
                "bollinger_middle": float(bb_mid),
                "bollinger_lower": float(bb_lower),
                "atr": float(atr),
                "vwap": float(vwap),
                "volume": float(self.latest_candle["volume"]),
                "volume_sma": float(volume_sma),
            },
        }

    def _analyze_rsi(self, rsi):
        if rsi < 30:
            return {"value": "sobrevenda", "strength": min((30 - rsi) / 30, 1.0)}
        if rsi > 70:
            return {"value": "sobrecompra", "strength": min((rsi - 70) / 30, 1.0)}
        if 45 <= rsi <= 62:
            return {"value": "neutro_bullish", "strength": 0.4}
        if 38 <= rsi < 45:
            return {"value": "neutro_bearish", "strength": 0.4}
        return {"value": "neutro", "strength": 0.2}

    def _analyze_macd(self, macd, signal, histogram):
        if histogram > 0 and macd > signal:
            return {"value": "bullish", "strength": min(abs(histogram) * 20, 1.0)}
        if histogram < 0 and macd < signal:
            return {"value": "bearish", "strength": min(abs(histogram) * 20, 1.0)}
        return {"value": "neutro", "strength": 0.4}

    def _analyze_trend(self, ema9, ema21, ema200, price):
        if price > ema9 > ema21 > ema200:
            return {"value": "uptrend", "strength": 1.0}
        if price < ema9 < ema21 < ema200:
            return {"value": "downtrend", "strength": 1.0}
        if ema9 > ema21 and price > ema200:
            return {"value": "uptrend", "strength": 0.7}
        if ema9 < ema21 and price < ema200:
            return {"value": "downtrend", "strength": 0.7}
        return {"value": "sideways", "strength": 0.35}

    def _analyze_volume(self, volume_sma):
        current_volume = self.latest_candle["volume"]
        if pd.isna(volume_sma) or volume_sma <= 0:
            return {"value": "normal", "strength": 0.5}
        if current_volume > volume_sma * 1.5:
            return {"value": "alto", "strength": min(current_volume / (volume_sma * 2), 1.0)}
        if current_volume < volume_sma * 0.5:
            return {"value": "baixo", "strength": 0.3}
        return {"value": "normal", "strength": 0.6}

    def _analyze_volatility(self, atr, price):
        atr_pct = atr / price if price else 0
        if atr_pct > 0.045:
            return {"value": "alta", "strength": min(atr_pct / 0.08, 1.0)}
        if atr_pct < 0.008:
            return {"value": "baixa", "strength": 0.35}
        return {"value": "normal", "strength": 0.7}

    def _analyze_confluence(self, price, ema9, ema21, ema200, vwap, rsi, macd, signal):
        bullish = 0
        bearish = 0
        if price > ema9 > ema21:
            bullish += 1
        if price > ema200:
            bullish += 1
        if price > vwap:
            bullish += 1
        if macd > signal:
            bullish += 1
        if 45 <= rsi <= 68:
            bullish += 1
        if price < ema9 < ema21:
            bearish += 1
        if price < ema200:
            bearish += 1
        if price < vwap:
            bearish += 1
        if macd < signal:
            bearish += 1
        if 32 <= rsi <= 55:
            bearish += 1
        if bullish > bearish:
            return {"value": "bullish", "strength": bullish / 5}
        if bearish > bullish:
            return {"value": "bearish", "strength": bearish / 5}
        return {"value": "neutro", "strength": 0.4}

    def _analyze_structure(self, structure):
        if structure.get("breakout") == "bullish" or structure.get("pullback") == "bullish":
            return {"value": "bullish", "strength": structure.get("strength", 0.5)}
        if structure.get("breakout") == "bearish" or structure.get("pullback") == "bearish":
            return {"value": "bearish", "strength": structure.get("strength", 0.5)}
        return {"value": "neutro", "strength": 0.3}

    def _analyze_patterns(self):
        patterns = self.ta.identify_candle_patterns()
        if patterns:
            return {"value": patterns[0]["name"], "strength": 0.7}
        return {"value": "nenhum", "strength": 0}

    def _calculate_score(self, components):
        weights = {
            "rsi_signal": 0.12,
            "macd_signal": 0.18,
            "trend_signal": 0.24,
            "volume_signal": 0.10,
            "volatility_signal": 0.06,
            "confluence_signal": 0.20,
            "structure_signal": 0.05,
            "pattern_signal": 0.05,
        }
        score = 0
        for key, component in components.items():
            value = component["value"]
            if value in ["uptrend", "bullish", "sobrevenda", "alto", "normal", "neutro_bullish"]:
                score += component["strength"] * weights[key]
            elif value in ["downtrend", "bearish", "sobrecompra", "neutro_bearish"]:
                score -= component["strength"] * weights[key]
        return score

    def _determine_signal_type(self, score):
        if score > 0.55:
            return "entrada_agressiva"
        if score > 0.32:
            return "entrada_conservadora"
        if score > 0.12:
            return "compra"
        if score < -0.55:
            return "venda_agressiva"
        if score < -0.22:
            return "venda"
        return "neutro"

    def _calculate_confidence(self, components):
        strengths = [
            component["strength"]
            for component in components.values()
            if component["value"] not in ["neutro", "nenhum"]
        ]
        if not strengths:
            return 50.0
        return float(max(35, min(np.mean(strengths) * 100, 98)))


class RiskManagement:
    """Calcula entrada, stop, alvos e risco/retorno com base no ATR."""

    def __init__(self, entry_price, atr):
        self.entry_price = float(entry_price)
        self.atr = float(atr) if pd.notna(atr) and atr > 0 else max(self.entry_price * 0.01, 0.0001)

    def calculate_levels(self, signal_type="compra"):
        is_buy = any(word in signal_type.lower() for word in ["compra", "entrada"])
        if is_buy:
            stop_loss = self.entry_price - self.atr * 1.5
            target1 = self.entry_price + (self.entry_price - stop_loss)
            target2 = self.entry_price + (self.entry_price - stop_loss) * 2
        else:
            stop_loss = self.entry_price + self.atr * 1.5
            target1 = self.entry_price - (stop_loss - self.entry_price)
            target2 = self.entry_price - (stop_loss - self.entry_price) * 2

        risk = abs(self.entry_price - stop_loss)
        reward = abs(target1 - self.entry_price)
        return {
            "entrada": float(self.entry_price),
            "stop_loss": float(stop_loss),
            "alvo_1": float(target1),
            "alvo_2": float(target2),
            "risco_retorno": float(reward / risk) if risk else 0.0,
        }


class BacktestEngine:
    """Backtest simples por cruzamento EMA 9/21."""

    def __init__(self, data, initial_capital=10000):
        self.data = data
        self.initial_capital = initial_capital
        self.equity_curve = []

    def backtest_strategy(self, strategy_name="ema_cross"):
        capital = self.initial_capital
        position = False
        entry_price = 0
        trades = 0
        wins = 0
        ema9 = self.data["close"].ewm(span=9, adjust=False).mean()
        ema21 = self.data["close"].ewm(span=21, adjust=False).mean()

        for i in range(21, len(self.data)):
            close = self.data["close"].iloc[i]
            if not position and ema9.iloc[i] > ema21.iloc[i] and ema9.iloc[i - 1] <= ema21.iloc[i - 1]:
                position = True
                entry_price = close
                trades += 1
            elif position and ema9.iloc[i] < ema21.iloc[i]:
                profit = (close - entry_price) / entry_price
                capital *= 1 + profit
                wins += 1 if profit > 0 else 0
                position = False
            self.equity_curve.append(float(capital))

        total_return = (capital - self.initial_capital) / self.initial_capital * 100
        losses = trades - wins
        return {
            "strategy": strategy_name,
            "total_trades": trades,
            "wins": wins,
            "losses": losses,
            "win_rate": float(wins / trades * 100) if trades else 0.0,
            "total_return": float(total_return),
            "final_capital": float(capital),
            "profit_factor": float(wins / losses) if losses else float(wins),
            "equity_curve": self.equity_curve[-100:],
        }


class OperationalScore:
    """Score operacional de 0 a 100 baseado na saida da IA."""

    @staticmethod
    def calculate_score(indicators, patterns, trend, ai_score=0):
        score = 50 + ai_score * 45
        if trend == "uptrend":
            score += 8
        elif trend == "downtrend":
            score -= 8
        if patterns:
            score += 4
        rsi = indicators.get("rsi", 50)
        if 45 <= rsi <= 62:
            score += 5
        elif rsi > 76 or rsi < 24:
            score -= 5
        return int(max(0, min(100, round(score))))


def generate_ai_reasoning(signal):
    components = signal.get("components", {})
    indicators = signal.get("indicators", {})
    reasoning = []

    trend = components.get("trend_signal", {})
    if trend.get("value") == "uptrend":
        reasoning.append("Tendencia de alta: preco acima das EMAs 9, 21 e 200.")
    elif trend.get("value") == "downtrend":
        reasoning.append("Tendencia de baixa: preco abaixo das EMAs 9, 21 e 200.")
    else:
        reasoning.append("Tendencia lateral: medias ainda sem alinhamento limpo.")

    macd = components.get("macd_signal", {})
    if macd.get("value") == "bullish":
        reasoning.append("MACD confirma momentum comprador.")
    elif macd.get("value") == "bearish":
        reasoning.append("MACD confirma momentum vendedor.")

    volume = components.get("volume_signal", {})
    if volume.get("value") == "alto":
        reasoning.append("Volume real acima da media, validando o movimento.")
    elif volume.get("value") == "baixo":
        reasoning.append("Volume baixo reduz a qualidade do sinal.")

    confluence = components.get("confluence_signal", {})
    if confluence.get("value") == "bullish":
        reasoning.append("Confluencia compradora entre EMAs, VWAP, RSI e MACD.")
    elif confluence.get("value") == "bearish":
        reasoning.append("Confluencia vendedora entre EMAs, VWAP, RSI e MACD.")

    structure = components.get("structure_signal", {})
    if structure.get("value") == "bullish":
        reasoning.append("Estrutura favorece compra por rompimento ou pullback.")
    elif structure.get("value") == "bearish":
        reasoning.append("Estrutura favorece venda por perda de suporte ou pullback.")

    atr = indicators.get("atr")
    price = signal.get("price")
    if atr and price:
        reasoning.append(f"Volatilidade ATR: {(atr / price) * 100:.2f}% do preco.")
    return reasoning


def create_heatmap_data(assets, timeframes, data_loader=None):
    """Cria heatmap real quando recebe um loader de candles."""
    colors = {
        "entrada_agressiva": "#10b981",
        "entrada_conservadora": "#34d399",
        "compra": "#22c55e",
        "neutro": "#64748b",
        "venda": "#f97316",
        "venda_agressiva": "#ef4444",
    }
    heatmap = {}
    for asset in assets:
        symbol = asset["symbol"] if isinstance(asset, dict) else asset
        heatmap[symbol] = {}
        for timeframe in timeframes:
            try:
                if data_loader:
                    df = data_loader(symbol, timeframe)
                    signal = AISignalGenerator(TechnicalAnalysis(df)).generate_signal()
                    signal_type = signal["signal_type"]
                    confidence = signal["confidence"]
                else:
                    signal_type = "neutro"
                    confidence = 50
            except Exception:
                signal_type = "neutro"
                confidence = 0
            heatmap[symbol][timeframe] = {
                "signal": signal_type,
                "color": colors.get(signal_type, "#64748b"),
                "confidence": int(round(confidence)),
            }
    return heatmap
