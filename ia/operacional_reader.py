"""
Leitura Operacional Grafica independente.

Este modulo nao usa score geral, smart_money, technical_reader, live trading
ou sinais automaticos. Ele transforma OHLCV em uma leitura contextual inspirada
em Dow, pullbacks, suportes/resistencias, rompimentos, rejeicao, liquidez,
candle a candle e gerenciamento de risco.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def _pct(current: float, previous: float) -> float:
    return ((current - previous) / previous * 100.0) if previous else 0.0


def _round(value: float, digits: int = 4) -> float:
    return round(_safe_float(value), digits)


@dataclass
class CandleRead:
    direction: str
    body_pct: float
    upper_wick_pct: float
    lower_wick_pct: float
    range_pct: float
    volume_ratio: float


class OperacionalReader:
    def __init__(self, candles: pd.DataFrame, symbol: str = "BTCUSDT", timeframe: str = "15m"):
        self.df = self._prepare(candles)
        self.symbol = symbol
        self.timeframe = timeframe

    def analyze(self) -> dict[str, Any]:
        if len(self.df) < 30:
            return self._empty("Candles insuficientes para leitura operacional.")

        trend = self._trend_context()
        zones = self._zones()
        candle_flow = self._candle_flow()
        current = candle_flow[-1]
        breakout = self._breakout_context(zones, current)
        pullback = self._pullback_context(zones, trend)
        liquidity = self._liquidity_context(zones, current)
        fib = self._fibonacci_context()
        apostila = self._apostila_operacional_context(trend, zones, candle_flow, breakout, pullback, liquidity, fib)
        risk = self._risk_context(zones, trend, current, breakout, apostila)
        confirmations, invalidations = self._confirmations(trend, current, breakout, pullback, liquidity, risk, apostila)
        context = self._context_label(trend, current, breakout, pullback)
        narrative = self._narrative(context, trend, current, breakout, pullback, liquidity, risk, apostila)
        recommendation = self._recommendation(context, confirmations, invalidations, risk)
        score = self._operational_score(context, confirmations, invalidations, current, pullback, breakout, liquidity, risk, apostila)
        signal = self._signal_payload(context, trend, confirmations, invalidations, risk, score)

        operational_live = self._live_messages(context, trend, breakout, pullback, liquidity, signal)
        operational_chart = self._chart_marks(zones, risk, breakout, pullback, liquidity, apostila)

        return {
            "success": True,
            "module": "operacional_leitura_grafica",
            "isolated": True,
            "methodology": "apostila_operacional_dow_pullback_prior_cote_3_candles",
            "excluded_modules": [
                "ema", "rsi", "macd", "bollinger", "vwap", "atr",
                "smart_money_padrao", "bos_padrao", "choch_padrao", "order_blocks_padrao", "fvg_padrao",
                "volume_reader", "momentum_tecnico_padrao", "multi_timeframe_padrao",
                "score_geral_padrao", "risco_retorno_padrao", "sinais_ia_padrao",
                "live_trading_ia_padrao", "technical_reader", "smart_money", "general_score",
                "operational_signal_padrao",
            ],
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "operacional_context": context,
            "operacional_score": score,
            "operacional_trend": trend,
            "operacional_zones": zones,
            "operacional_liquidity": liquidity,
            "operacional_breakout": breakout,
            "operacional_pullback": pullback,
            "operacional_fibonacci": fib,
            "apostila_operacional": apostila,
            "operacional_candle_flow": candle_flow[-8:],
            "operacional_current_candle": current,
            "operacional_confirmations": confirmations,
            "operacional_invalidations": invalidations,
            "operacional_risk": risk,
            "operacional_trade_plan": risk.get("trade_plan", {}),
            "operacional_signal": signal,
            "operacional_live": operational_live,
            "operacional_chart": operational_chart,
            "timing": self._timing(context, current, breakout, pullback),
            "operational_recommendation": recommendation,
            "narrative": narrative,
            "disclaimer": "Leitura grafica educativa. Nao constitui recomendacao financeira.",
        }

    def context_only(self) -> dict[str, Any]:
        full = self.analyze()
        return {
            "success": full.get("success", False),
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "operacional_context": full.get("operacional_context"),
            "operacional_trend": full.get("operacional_trend"),
            "operacional_zones": full.get("operacional_zones"),
            "operacional_liquidity": full.get("operacional_liquidity"),
            "narrative": full.get("narrative"),
        }

    def candle_flow_only(self) -> dict[str, Any]:
        full = self.analyze()
        return {
            "success": full.get("success", False),
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "operacional_current_candle": full.get("operacional_current_candle"),
            "operacional_candle_flow": full.get("operacional_candle_flow", []),
            "narrative": full.get("narrative", [])[-4:],
        }

    def _prepare(self, candles: pd.DataFrame) -> pd.DataFrame:
        df = candles.copy()
        for column in ["open", "high", "low", "close", "volume"]:
            df[column] = pd.to_numeric(df[column], errors="coerce")
        return df.dropna(subset=["open", "high", "low", "close"]).tail(500)

    def _empty(self, message: str) -> dict[str, Any]:
        return {
            "success": False,
            "module": "operacional_leitura_grafica",
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "narrative": [message],
            "operacional_context": {"label": "Mercado sem clareza", "quality": 0, "risk": "alto"},
            "operacional_score": 0,
            "operacional_candle_flow": [],
            "operacional_confirmations": [],
            "operacional_invalidations": [message],
            "operacional_risk": {"scenario_risk": "alto", "quality": "baixa"},
            "operacional_signal": {"status": "analisando", "direction": "NEUTRO"},
            "operacional_live": [message],
            "operacional_chart": {"price_lines": [], "events": {}},
        }

    def _trend_context(self) -> dict[str, Any]:
        close = self.df["close"]
        last = float(close.iloc[-1])
        impulse = _pct(last, float(close.iloc[-18]))
        swings = self._swing_points()
        highs = swings["highs"]
        lows = swings["lows"]
        last_highs = highs[-3:]
        last_lows = lows[-3:]
        higher_high = len(last_highs) >= 2 and last_highs[-1]["price"] > last_highs[-2]["price"]
        higher_low = len(last_lows) >= 2 and last_lows[-1]["price"] > last_lows[-2]["price"]
        lower_high = len(last_highs) >= 2 and last_highs[-1]["price"] < last_highs[-2]["price"]
        lower_low = len(last_lows) >= 2 and last_lows[-1]["price"] < last_lows[-2]["price"]
        range_pct = (float(self.df["high"].tail(28).max()) - float(self.df["low"].tail(28).min())) / last * 100 if last else 0
        close_position = (last - float(self.df["low"].tail(28).min())) / max(float(self.df["high"].tail(28).max()) - float(self.df["low"].tail(28).min()), last * 0.00001)

        if higher_high and higher_low:
            bias = "alta"
            structure = "Dow comprador: topos e fundos ascendentes"
        elif lower_high and lower_low:
            bias = "baixa"
            structure = "Dow vendedor: topos e fundos descendentes"
        elif range_pct < 1.4 or 0.32 <= close_position <= 0.68:
            bias = "lateral"
            structure = "Faixa lateral com alternancia entre suporte e resistencia"
        else:
            bias = "neutro"
            structure = "Estrutura em transicao, sem sequencia limpa"

        directional_points = int(higher_high) + int(higher_low) + int(lower_high) + int(lower_low)
        strength = min(100, max(0, int(abs(impulse) * 12 + directional_points * 18 + max(range_pct - 0.8, 0) * 4)))
        if strength >= 70:
            strength_label = "forte"
        elif strength >= 38:
            strength_label = "moderada"
        else:
            strength_label = "fraca"

        return {
            "bias": bias,
            "structure": structure,
            "impulse_pct": _round(impulse, 3),
            "range_pct": _round(range_pct, 3),
            "strength": strength,
            "strength_label": strength_label,
            "dow": {
                "higher_high": higher_high,
                "higher_low": higher_low,
                "lower_high": lower_high,
                "lower_low": lower_low,
            },
            "swings": {
                "highs": last_highs,
                "lows": last_lows,
            },
        }

    def _swing_points(self, window: int = 3) -> dict[str, list[dict[str, Any]]]:
        highs = []
        lows = []
        limit = len(self.df) - window
        for i in range(window, limit):
            slice_high = self.df["high"].iloc[i - window: i + window + 1]
            slice_low = self.df["low"].iloc[i - window: i + window + 1]
            high = float(self.df["high"].iloc[i])
            low = float(self.df["low"].iloc[i])
            ts = self.df.index[i]
            time_value = int(ts.timestamp()) if hasattr(ts, "timestamp") else i
            if high >= float(slice_high.max()):
                highs.append({"time": time_value, "price": _round(high)})
            if low <= float(slice_low.min()):
                lows.append({"time": time_value, "price": _round(low)})
        return {"highs": highs[-8:], "lows": lows[-8:]}

    def _zones(self) -> dict[str, Any]:
        recent = self.df.tail(80)
        supports = recent["low"].rolling(5, center=True).min().dropna().tail(12)
        resistances = recent["high"].rolling(5, center=True).max().dropna().tail(12)
        current = float(self.df["close"].iloc[-1])
        support = float(supports[supports <= current].max()) if len(supports[supports <= current]) else float(recent["low"].min())
        resistance = float(resistances[resistances >= current].min()) if len(resistances[resistances >= current]) else float(recent["high"].max())
        range_high = float(recent["high"].max())
        range_low = float(recent["low"].min())
        return {
            "support": _round(support),
            "resistance": _round(resistance),
            "range_high": _round(range_high),
            "range_low": _round(range_low),
            "midpoint": _round((range_high + range_low) / 2),
            "upper_liquidity": _round(range_high),
            "lower_liquidity": _round(range_low),
            "important_zones": [
                {"type": "suporte", "price": _round(support), "role": "defesa de fundo / possivel pullback"},
                {"type": "resistencia", "price": _round(resistance), "role": "topo operacional / validacao de rompimento"},
                {"type": "liquidez superior", "price": _round(range_high), "role": "stops acima da faixa"},
                {"type": "liquidez inferior", "price": _round(range_low), "role": "stops abaixo da faixa"},
            ],
        }

    def _read_candle(self, index: int) -> dict[str, Any]:
        row = self.df.iloc[index]
        open_price = float(row.open)
        high = float(row.high)
        low = float(row.low)
        close = float(row.close)
        total = max(high - low, close * 0.00001)
        body = abs(close - open_price)
        upper = high - max(open_price, close)
        lower = min(open_price, close) - low
        vol_mean = float(self.df["volume"].iloc[max(0, index - 20): index + 1].mean() or 0)
        volume_ratio = float(row.volume) / vol_mean if vol_mean else 1.0
        direction = "comprador" if close > open_price else "vendedor" if close < open_price else "neutro"
        body_pct = body / total
        upper_pct = upper / total
        lower_pct = lower / total

        tags = []
        if body_pct >= 0.62:
            tags.append("candle de decisao")
        if upper_pct >= 0.42:
            tags.append("rejeicao superior")
        if lower_pct >= 0.42:
            tags.append("rejeicao inferior")
        if volume_ratio >= 1.45 and body_pct < 0.38:
            tags.append("absorucao")
        if body_pct < 0.24:
            tags.append("indecisao")
        if volume_ratio >= 1.7 and body_pct >= 0.55:
            tags.append("agressao " + ("compradora" if direction == "comprador" else "vendedora"))

        previous_close = float(self.df["close"].iloc[index - 1]) if index > 0 else open_price
        return {
            "time": int(self.df.index[index].timestamp()) if hasattr(self.df.index[index], "timestamp") else index,
            "direction": direction,
            "open": _round(open_price),
            "high": _round(high),
            "low": _round(low),
            "close": _round(close),
            "variation_pct": _round(_pct(close, previous_close), 3),
            "body_strength": int(body_pct * 100),
            "upper_wick_pct": int(upper_pct * 100),
            "lower_wick_pct": int(lower_pct * 100),
            "volume_ratio": _round(volume_ratio, 2),
            "range_pct": _round(total / close * 100 if close else 0, 3),
            "tags": tags or ["candle comum"],
            "reading": self._candle_sentence(direction, body_pct, upper_pct, lower_pct, volume_ratio),
        }

    def _candle_sentence(self, direction: str, body: float, upper: float, lower: float, volume_ratio: float) -> str:
        if volume_ratio >= 1.45 and body < 0.38:
            return "Volume alto com corpo limitado sugere absorcao e disputa institucional."
        if direction == "comprador" and body >= 0.58:
            return "Candle comprador com corpo dominante indica agressao compradora."
        if direction == "vendedor" and body >= 0.58:
            return "Candle vendedor com corpo dominante indica agressao vendedora."
        if upper >= 0.42:
            return "Pavio superior relevante mostra rejeicao de topo."
        if lower >= 0.42:
            return "Pavio inferior relevante mostra defesa de fundo."
        return "Candle sem dominancia extrema; leitura depende do contexto."

    def _candle_flow(self) -> list[dict[str, Any]]:
        start = max(0, len(self.df) - 14)
        flow = [self._read_candle(i) for i in range(start, len(self.df))]
        for idx, item in enumerate(flow):
            if idx >= 2:
                last_three = flow[idx - 2: idx + 1]
                same_direction = len({c["direction"] for c in last_three}) == 1 and item["direction"] != "neutro"
                if same_direction:
                    item["tags"].append("padrao de 3 candles")
                    item["reading"] += " Ha sequencia de 3 candles na mesma direcao."
        return flow

    def _breakout_context(self, zones: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
        close = float(self.df["close"].iloc[-1])
        prev_close = float(self.df["close"].iloc[-2])
        support = zones["support"]
        resistance = zones["resistance"]
        range_high = zones["range_high"]
        range_low = zones["range_low"]
        valid_up = prev_close <= resistance and close > resistance and current["body_strength"] >= 48
        valid_down = prev_close >= support and close < support and current["body_strength"] >= 48
        false_up = float(self.df["high"].iloc[-1]) > range_high and close < range_high
        false_down = float(self.df["low"].iloc[-1]) < range_low and close > range_low
        return {
            "valid_breakout": bool(valid_up or valid_down),
            "direction": "alta" if valid_up else "baixa" if valid_down else "nenhuma",
            "false_breakout": bool(false_up or false_down),
            "false_breakout_side": "acima" if false_up else "abaixo" if false_down else "nenhum",
            "reading": self._breakout_sentence(valid_up, valid_down, false_up, false_down),
        }

    def _breakout_sentence(self, valid_up: bool, valid_down: bool, false_up: bool, false_down: bool) -> str:
        if false_up:
            return "Liquidez capturada acima da resistencia; possivel falso rompimento."
        if false_down:
            return "Liquidez capturada abaixo do suporte; possivel falso rompimento."
        if valid_up:
            return "Rompimento comprador com fechamento acima da resistencia."
        if valid_down:
            return "Rompimento vendedor com fechamento abaixo do suporte."
        return "Rompimento ainda sem confirmacao operacional."

    def _pullback_context(self, zones: dict[str, Any], trend: dict[str, Any]) -> dict[str, Any]:
        close = float(self.df["close"].iloc[-1])
        low = float(self.df["low"].iloc[-1])
        high = float(self.df["high"].iloc[-1])
        support = zones["support"]
        resistance = zones["resistance"]
        tolerance = max(close * 0.004, (zones["range_high"] - zones["range_low"]) * 0.06)
        valid = False
        failure = False
        side = "nenhum"
        if trend["bias"] == "alta":
            valid = abs(low - support) <= tolerance and close > support
            failure = close < support
            side = "pullback comprador"
        elif trend["bias"] == "baixa":
            valid = abs(high - resistance) <= tolerance and close < resistance
            failure = close > resistance
            side = "pullback vendedor"
        return {
            "type": side,
            "valid_pullback": bool(valid),
            "pullback_failure": bool(failure),
            "reading": "Pullback respeitando contexto." if valid else "Possivel falha de pullback." if failure else "Sem pullback tecnico claro no candle atual.",
        }

    def _liquidity_context(self, zones: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
        close = float(self.df["close"].iloc[-1])
        high = float(self.df["high"].iloc[-1])
        low = float(self.df["low"].iloc[-1])
        upper_sweep = high > zones["upper_liquidity"] and close < zones["upper_liquidity"]
        lower_sweep = low < zones["lower_liquidity"] and close > zones["lower_liquidity"]
        return {
            "upper_zone": zones["upper_liquidity"],
            "lower_zone": zones["lower_liquidity"],
            "sweep": bool(upper_sweep or lower_sweep),
            "sweep_side": "superior" if upper_sweep else "inferior" if lower_sweep else "nenhum",
            "absorption": "absorucao" in current.get("tags", []),
            "reading": "Liquidez capturada e preco voltou para dentro da faixa." if upper_sweep or lower_sweep else "Liquidez principal ainda preservada.",
        }

    def _fibonacci_context(self) -> dict[str, Any]:
        lookback = self.df.tail(80)
        high = float(lookback["high"].max())
        low = float(lookback["low"].min())
        close = float(self.df["close"].iloc[-1])
        span = max(high - low, close * 0.00001)
        levels = {
            "0.382": high - span * 0.382,
            "0.5": high - span * 0.5,
            "0.618": high - span * 0.618,
        }
        nearest_key, nearest_value = min(levels.items(), key=lambda item: abs(close - item[1]))
        return {
            "swing_high": _round(high),
            "swing_low": _round(low),
            "levels": {key: _round(value) for key, value in levels.items()},
            "nearest_level": nearest_key,
            "nearest_price": _round(nearest_value),
            "reading": f"Preco mais proximo da retracao {nearest_key}, zona util para observar pullback e rejeicao.",
        }

    def _apostila_operacional_context(self, trend, zones, candle_flow, breakout, pullback, liquidity, fib) -> dict[str, Any]:
        last = candle_flow[-1] if candle_flow else {}
        close = float(self.df["close"].iloc[-1])
        prior_cote = self._prior_cote_context(zones)
        dow_50 = self._dow_50_context(trend, zones, fib)
        market_phase = self._market_phase_context(trend, zones, candle_flow)
        trigger = self._trigger_context(last, zones, fib)
        three_candles = self._three_candle_pattern(candle_flow, zones, fib, trend)
        execution = self._execution_context(three_candles, breakout, pullback, trigger, trend)
        no_trade = []
        if market_phase["phase"] in ["distribuicao", "acumulacao"] and not breakout.get("valid_breakout"):
            no_trade.append("Mercado em acumulacao/distribuicao; evitar clicar no meio da faixa.")
        if three_candles.get("exception"):
            no_trade.append(three_candles["exception_reason"])
        if dow_50.get("against_primary_bias"):
            no_trade.append("Preco contra a referencia dos 50%; evitar operacao contra tendencia primaria.")
        if breakout.get("false_breakout") or liquidity.get("sweep"):
            no_trade.append("Risco de armadilha apos captura de liquidez.")

        return {
            "source": "Apostila do Operacional",
            "rules": [
                "Dow define tendencia por topos e fundos.",
                "50% do movimento separa contexto primario de compra/venda.",
                "Rompimento so vale com fechamento alem do nivel.",
                "Padrao de 3 candles: alvo, negacao e teste para buscar liquidez.",
                "Nao bater a mercado; planejar ordem atras do ponto de parada.",
                "Stop tecnico fica na maxima/minima do movimento.",
            ],
            "current_price": _round(close),
            "dow_50": dow_50,
            "prior_cote": prior_cote,
            "market_phase": market_phase,
            "trigger": trigger,
            "three_candle_pattern": three_candles,
            "execution": execution,
            "no_trade_filters": list(dict.fromkeys(no_trade))[:8],
            "reading": self._apostila_sentence(dow_50, market_phase, trigger, three_candles, execution, no_trade),
        }

    def _prior_cote_context(self, zones) -> dict[str, Any]:
        daily = self.df.tail(min(len(self.df), 96))
        high = float(daily["high"].max())
        low = float(daily["low"].min())
        close = float(self.df["close"].iloc[-1])
        previous_close = float(self.df["close"].iloc[-2]) if len(self.df) > 1 else close
        adjustment = (high + low + previous_close) / 3
        levels = [
            {"type": "prior_maxima", "label": "Prior cote max.", "price": _round(high), "role": "resistencia de diario/hora"},
            {"type": "prior_minima", "label": "Prior cote min.", "price": _round(low), "role": "suporte de diario/hora"},
            {"type": "prior_ajuste", "label": "Prior cote ajuste", "price": _round(adjustment), "role": "media operacional da sessao"},
            {"type": "prior_fechamento", "label": "Prior cote fech.", "price": _round(previous_close), "role": "referencia do fechamento anterior"},
        ]
        nearest = min(levels, key=lambda item: abs(close - float(item["price"])))
        return {
            "levels": levels,
            "nearest": nearest,
            "distance_pct": _round(abs(close - float(nearest["price"])) / close * 100 if close else 0, 3),
            "reading": f"Preco proximo de {nearest['label']}." if close else "Prior cote indisponivel.",
        }

    def _dow_50_context(self, trend, zones, fib) -> dict[str, Any]:
        close = float(self.df["close"].iloc[-1])
        midpoint = float(zones.get("midpoint") or fib.get("nearest_price") or close)
        side = "acima_50" if close >= midpoint else "abaixo_50"
        primary_bias = "compra" if side == "acima_50" else "venda"
        against = (trend.get("bias") == "alta" and side == "abaixo_50") or (trend.get("bias") == "baixa" and side == "acima_50")
        return {
            "midpoint": _round(midpoint),
            "side": side,
            "primary_bias": primary_bias,
            "against_primary_bias": bool(against),
            "reading": "Preco acima dos 50%, prioridade operacional para compras." if side == "acima_50" else "Preco abaixo dos 50%, prioridade operacional para vendas.",
        }

    def _market_phase_context(self, trend, zones, candle_flow) -> dict[str, Any]:
        recent = self.df.tail(24)
        close = float(self.df["close"].iloc[-1])
        amplitude = (float(recent["high"].max()) - float(recent["low"].min())) / max(close, 0.00001) * 100
        body_avg = sum(float(c.get("body_strength", 0)) for c in candle_flow[-8:]) / max(len(candle_flow[-8:]), 1)
        decision_count = sum(1 for c in candle_flow[-8:] if c.get("body_strength", 0) >= 55)
        rejection_count = sum(1 for c in candle_flow[-8:] if c.get("upper_wick_pct", 0) >= 42 or c.get("lower_wick_pct", 0) >= 42)
        if trend.get("bias") == "lateral" or amplitude < 0.45:
            phase = "acumulacao"
            reading = "Topos e fundos semelhantes; mercado acumulando contratos."
        elif decision_count >= 3 and trend.get("bias") in ["alta", "baixa"]:
            phase = "movimentacao"
            reading = "Sequencia direcional; mercado em movimentacao."
        elif rejection_count >= 3 and body_avg < 48:
            phase = "distribuicao"
            reading = "Muitas rejeicoes e pouco progresso; risco de distribuicao."
        else:
            phase = "transicao"
            reading = "Fase operacional em transicao."
        return {
            "phase": phase,
            "amplitude_pct": _round(amplitude, 3),
            "decision_candles": decision_count,
            "rejections": rejection_count,
            "reading": reading,
        }

    def _trigger_context(self, current, zones, fib) -> dict[str, Any]:
        close = float(current.get("close") or self.df["close"].iloc[-1])
        body = int(current.get("body_strength", 0) or 0)
        upper = int(current.get("upper_wick_pct", 0) or 0)
        lower = int(current.get("lower_wick_pct", 0) or 0)
        levels = [
            zones.get("support"),
            zones.get("resistance"),
            zones.get("midpoint"),
            fib.get("nearest_price"),
        ]
        finite_levels = [float(level) for level in levels if level is not None]
        nearest = min(finite_levels, key=lambda price: abs(close - price)) if finite_levels else close
        tolerance = max(close * 0.0015, abs(float(zones.get("range_high", close)) - float(zones.get("range_low", close))) * 0.03)
        is_doji_trigger = body <= 32 and (upper >= 35 or lower >= 35) and abs(close - nearest) <= tolerance
        side = "rejeicao_superior" if upper >= lower and is_doji_trigger else "rejeicao_inferior" if is_doji_trigger else "nenhum"
        return {
            "active": bool(is_doji_trigger),
            "side": side,
            "level": _round(nearest),
            "reading": "Gatilho operacional em ponto de parada." if is_doji_trigger else "Sem gatilho operacional claro.",
        }

    def _three_candle_pattern(self, candle_flow, zones, fib, trend) -> dict[str, Any]:
        if len(candle_flow) < 3:
            return {"active": False, "stage": "insuficiente", "direction": "NEUTRO"}
        c1, c2, c3 = candle_flow[-3:]
        close = float(c3.get("close", 0))
        levels = [zones.get("support"), zones.get("resistance"), zones.get("midpoint"), fib.get("nearest_price")]
        finite_levels = [float(level) for level in levels if level is not None]
        nearest = min(finite_levels, key=lambda price: abs(float(c1.get("close", close)) - price)) if finite_levels else close
        tolerance = max(close * 0.0018, abs(float(zones.get("range_high", close)) - float(zones.get("range_low", close))) * 0.04)
        c1_hit_target = abs(float(c1.get("high", 0)) - nearest) <= tolerance or abs(float(c1.get("low", 0)) - nearest) <= tolerance
        c2_denies_up = c1.get("direction") == "comprador" and (c2.get("direction") == "vendedor" or c2.get("upper_wick_pct", 0) >= 40)
        c2_denies_down = c1.get("direction") == "vendedor" and (c2.get("direction") == "comprador" or c2.get("lower_wick_pct", 0) >= 40)
        c2_denies = c2_denies_up or c2_denies_down
        direction = "VENDA" if c2_denies_up else "COMPRA" if c2_denies_down else "NEUTRO"
        c3_tests = False
        if direction == "COMPRA":
            c3_tests = float(c3.get("low", close)) <= float(c2.get("low", close)) or c3.get("lower_wick_pct", 0) >= 30
        elif direction == "VENDA":
            c3_tests = float(c3.get("high", close)) >= float(c2.get("high", close)) or c3.get("upper_wick_pct", 0) >= 30
        active = bool(c1_hit_target and c2_denies and c3_tests)
        came_from_breakout = bool(c1.get("body_strength", 0) >= 58 and c2.get("body_strength", 0) >= 42 and trend.get("strength_label") == "forte")
        came_from_pullback = bool(abs(float(c1.get("close", close)) - float(zones.get("midpoint", close))) <= tolerance and trend.get("bias") in ["alta", "baixa"])
        exception = active and (came_from_breakout or came_from_pullback)
        stop = float(c3.get("low" if direction == "COMPRA" else "high", close)) if direction != "NEUTRO" else None
        entry = None
        if direction == "COMPRA":
            entry = float(c3.get("high", close))
        elif direction == "VENDA":
            entry = float(c3.get("low", close))
        return {
            "active": active,
            "stage": "alvo_negacao_teste" if active else "aguardando_padrao",
            "direction": direction,
            "target_level": _round(nearest),
            "entry_reference": _round(entry) if entry is not None else None,
            "stop_reference": _round(stop) if stop is not None else None,
            "exception": bool(exception),
            "exception_reason": "Padrao de 3 candles aparece vindo de pullback/rompimento; apostila orienta evitar." if exception else None,
            "reading": "Padrao de 3 candles completo: alvo, negacao e teste." if active else "Padrao de 3 candles ainda incompleto.",
        }

    def _execution_context(self, three_candles, breakout, pullback, trigger, trend) -> dict[str, Any]:
        mode = "aguardar"
        direction = "NEUTRO"
        reason = "Aguardar ponto de parada e confirmacao."
        if three_candles.get("active") and not three_candles.get("exception"):
            mode = "padrao_3_candles"
            direction = three_candles.get("direction", "NEUTRO")
            reason = "Executar somente com ordem atras do terceiro candle."
        elif pullback.get("valid_pullback") and trigger.get("active"):
            mode = "pullback_50"
            direction = "COMPRA" if trend.get("bias") == "alta" else "VENDA" if trend.get("bias") == "baixa" else "NEUTRO"
            reason = "Pullback nos 50% com gatilho em ponto de parada."
        elif breakout.get("valid_breakout"):
            mode = "rompimento_confirmado"
            direction = "COMPRA" if breakout.get("direction") == "alta" else "VENDA" if breakout.get("direction") == "baixa" else "NEUTRO"
            reason = "Rompimento fechado; aguardar teste da regiao rompida."
        return {"mode": mode, "direction": direction, "reason": reason}

    def _apostila_sentence(self, dow_50, market_phase, trigger, three_candles, execution, no_trade):
        if no_trade:
            return no_trade[0]
        if three_candles.get("active"):
            return three_candles.get("reading")
        if trigger.get("active"):
            return "Gatilho em ponto de parada; observar terceiro candle/teste de liquidez."
        if market_phase.get("phase") == "movimentacao":
            return "Mercado em movimentacao; evitar perseguir preco e aguardar teste."
        return f"{dow_50.get('reading')} {execution.get('reason')}"

    def _risk_context(self, zones: dict[str, Any], trend: dict[str, Any], current: dict[str, Any], breakout: dict[str, Any], apostila: dict[str, Any] | None = None) -> dict[str, Any]:
        close = float(self.df["close"].iloc[-1])
        apostila = apostila or {}
        three_candles = apostila.get("three_candle_pattern", {})
        execution = apostila.get("execution", {})
        direction = execution.get("direction")
        offset = self._point_offset(close)
        if direction == "COMPRA" and three_candles.get("entry_reference"):
            entry = float(three_candles["entry_reference"]) + offset
            stop = float(three_candles.get("stop_reference") or self.df["low"].tail(8).min()) - offset
            partial = max(float(zones["resistance"]), float(self.df["high"].tail(24).max()))
        elif direction == "VENDA" and three_candles.get("entry_reference"):
            entry = float(three_candles["entry_reference"]) - offset
            stop = float(three_candles.get("stop_reference") or self.df["high"].tail(8).max()) + offset
            partial = min(float(zones["support"]), float(self.df["low"].tail(24).min()))
        elif trend["bias"] == "alta":
            entry = close
            stop = min(zones["support"], float(self.df["low"].tail(8).min())) - offset
            partial = zones["resistance"] if zones["resistance"] > close else close + (close - stop) * 1.5
        elif trend["bias"] == "baixa":
            entry = close
            stop = max(zones["resistance"], float(self.df["high"].tail(8).max())) + offset
            partial = zones["support"] if zones["support"] < close else close - (stop - close) * 1.5
        else:
            entry = close
            stop = zones["range_low"]
            partial = zones["range_high"]
        risk = abs(entry - stop)
        reward = abs(partial - entry)
        rr = reward / risk if risk else 0
        risk_label = "baixo" if rr >= 1.8 and not breakout["false_breakout"] else "moderado" if rr >= 1.1 else "alto"
        quality = "alta" if rr >= 1.8 and current["body_strength"] >= 45 else "media" if rr >= 1.1 else "baixa"
        return {
            "reference_price": _round(close),
            "entry": _round(entry),
            "technical_stop": _round(stop),
            "partial_target": _round(partial),
            "take_profit_1": _round(partial),
            "take_profit_2": _round(close + (partial - close) * 1.6 if partial >= close else close - (close - partial) * 1.6),
            "risk_reward": _round(rr, 2),
            "invalidation": "Perda da maxima/minima tecnica do movimento ou fechamento contra o contexto.",
            "scenario_risk": risk_label,
            "entry_quality": quality,
            "positioning": "Aguardar confirmacao; foco em leitura contextual, nao em sinal automatico.",
            "trade_plan": {
                "entry": _round(entry),
                "stop": _round(stop),
                "take_profit_1": _round(partial),
                "take_profit_2": _round(close + (partial - close) * 1.6 if partial >= close else close - (close - partial) * 1.6),
                "oco": {
                    "enabled": True,
                    "description": "Plano OCO educativo: stop tecnico na invalidação e alvos parciais na zona operacional seguinte.",
                },
            },
        }

    def _point_offset(self, price: float) -> float:
        symbol = str(self.symbol).upper()
        if symbol.startswith("WIN"):
            return 25.0
        if symbol.startswith("WDO"):
            return 1.0
        return max(price * 0.0008, 0.0001)

    def _confirmations(self, trend, current, breakout, pullback, liquidity, risk, apostila=None):
        apostila = apostila or {}
        execution = apostila.get("execution", {})
        three_candles = apostila.get("three_candle_pattern", {})
        trigger = apostila.get("trigger", {})
        dow_50 = apostila.get("dow_50", {})
        phase = apostila.get("market_phase", {})
        confirmations = []
        invalidations = []
        if trend["bias"] in ["alta", "baixa"] and trend["strength_label"] in ["forte", "moderada"]:
            confirmations.append("Teoria de Dow alinhada com a direcao dominante.")
        if not dow_50.get("against_primary_bias") and dow_50.get("primary_bias"):
            confirmations.append("Preco respeita a leitura dos 50% do movimento.")
        if trigger.get("active"):
            confirmations.append("Gatilho operacional em ponto de parada.")
        if three_candles.get("active") and not three_candles.get("exception"):
            confirmations.append("Padrao de 3 candles completo: alvo, negacao e teste.")
        if execution.get("mode") == "rompimento_confirmado":
            confirmations.append("Rompimento fechado; aguardar teste da regiao rompida.")
        if phase.get("phase") == "movimentacao" and trend.get("bias") in ["alta", "baixa"]:
            confirmations.append("Fase de movimentacao alinhada a tendencia.")
        if current["body_strength"] >= 55:
            confirmations.append("Candle atual mostra corpo dominante e agressao direcional.")
        if pullback["valid_pullback"]:
            confirmations.append("Pullback respeitou zona tecnica.")
        if breakout["valid_breakout"]:
            confirmations.append("Rompimento com fechamento alem da zona operacional.")
        if liquidity["absorption"]:
            confirmations.append("Volume alto com corpo limitado sugere absorcao.")
        if breakout["false_breakout"]:
            invalidations.append("Possivel falso rompimento apos captura de liquidez.")
        if pullback["pullback_failure"]:
            invalidations.append("Falha de pullback contra o contexto anterior.")
        if current["body_strength"] < 25:
            invalidations.append("Candle atual sem decisao, timing fraco.")
        if risk["scenario_risk"] == "alto":
            invalidations.append("Risco/retorno desfavoravel para acao operacional.")
        if trend["bias"] in ["lateral", "neutro"]:
            invalidations.append("Estrutura sem tendencia limpa.")
        if dow_50.get("against_primary_bias"):
            invalidations.append("Preco contra a referencia operacional dos 50%.")
        if phase.get("phase") in ["acumulacao", "distribuicao"] and not breakout.get("valid_breakout"):
            invalidations.append("Mercado em acumulacao/distribuicao sem rompimento confirmado.")
        if three_candles.get("exception"):
            invalidations.append(three_candles.get("exception_reason"))
        return confirmations[:8], invalidations[:8]

    def _context_label(self, trend, current, breakout, pullback):
        if breakout["false_breakout"]:
            label = "Contexto perigoso"
            quality = 38
            risk = "alto"
        elif trend["bias"] == "lateral":
            label = "Lateralizacao"
            quality = 45
            risk = "moderado"
        elif abs(float(self.df["close"].iloc[-1]) - float(self.df["close"].iloc[-10])) / float(self.df["close"].iloc[-1]) < 0.004:
            label = "Compressao"
            quality = 48
            risk = "moderado"
        elif current["body_strength"] >= 65 and trend["strength_label"] == "forte":
            label = "Expansao"
            quality = 76
            risk = "moderado"
        elif pullback["valid_pullback"]:
            label = "Contexto favoravel"
            quality = 72
            risk = "moderado"
        elif trend["strength_label"] == "forte":
            label = "Tendencia forte"
            quality = 70
            risk = "moderado"
        elif trend["strength_label"] == "moderada":
            label = "Tendencia moderada"
            quality = 62
            risk = "moderado"
        elif current["volume_ratio"] >= 1.7 and current["body_strength"] < 35:
            label = "Exaustao"
            quality = 42
            risk = "alto"
        else:
            label = "Mercado sem clareza"
            quality = 35
            risk = "alto"
        return {"label": label, "quality": quality, "risk": risk}

    def _timing(self, context, current, breakout, pullback):
        if context["risk"] == "alto":
            return "Aguardar novo candle e confirmacao da defesa/rompimento."
        if breakout["valid_breakout"]:
            return "Aguardar reteste ou fechamento de continuidade para reduzir falso rompimento."
        if pullback["valid_pullback"]:
            return "Timing melhora se o proximo candle defender a zona do pullback."
        if current["body_strength"] >= 60:
            return "Candle de decisao; observar continuidade sem perseguir preco esticado."
        return "Timing neutro; leitura ainda depende do proximo candle."

    def _recommendation(self, context, confirmations, invalidations, risk):
        if context["risk"] == "alto" or len(invalidations) > len(confirmations):
            return "Aguardar. Contexto nao favorece decisao operacional imediata."
        if risk["entry_quality"] == "alta" and len(confirmations) >= 2:
            return "Contexto bom para acompanhamento proximo, priorizando confirmacao e stop tecnico."
        return "Manter leitura ativa e buscar confirmacao antes de qualquer plano."

    def _operational_score(self, context, confirmations, invalidations, current, pullback, breakout, liquidity, risk, apostila=None):
        apostila = apostila or {}
        score = int(context.get("quality", 0))
        score += min(18, len(confirmations) * 6)
        score -= min(24, len(invalidations) * 8)
        if current.get("body_strength", 0) >= 55:
            score += 7
        if pullback.get("valid_pullback"):
            score += 8
        if breakout.get("valid_breakout"):
            score += 6
        if liquidity.get("sweep"):
            score -= 10
        if risk.get("scenario_risk") == "alto":
            score -= 14
        elif risk.get("entry_quality") == "alta":
            score += 8
        execution_mode = apostila.get("execution", {}).get("mode")
        if execution_mode in ["padrao_3_candles", "pullback_50", "rompimento_confirmado"]:
            score += 12
        if apostila.get("three_candle_pattern", {}).get("exception"):
            score -= 18
        if apostila.get("dow_50", {}).get("against_primary_bias"):
            score -= 14
        if apostila.get("market_phase", {}).get("phase") == "distribuicao":
            score -= 10
        return int(max(0, min(100, score)))

    def _signal_payload(self, context, trend, confirmations, invalidations, risk, score):
        if risk.get("scenario_risk") == "alto" or len(invalidations) > len(confirmations):
            status = "aguardando confirmacao" if context.get("label") not in ["Contexto perigoso"] else "invalidado"
        elif score >= 78 and len(confirmations) >= 3:
            status = "entrada confirmada"
        elif score >= 62 and len(confirmations) >= 2:
            status = "entrada possivel"
        else:
            status = "aguardando confirmacao"

        if trend.get("bias") == "alta" and status not in ["invalidado"]:
            direction = "COMPRA"
        elif trend.get("bias") == "baixa" and status not in ["invalidado"]:
            direction = "VENDA"
        else:
            direction = "NEUTRO"

        return {
            "asset": self.symbol,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "direction": direction,
            "context": context.get("label"),
            "entry": risk.get("entry"),
            "stop": risk.get("technical_stop"),
            "take_profit_1": risk.get("take_profit_1"),
            "take_profit_2": risk.get("take_profit_2"),
            "risk_reward": risk.get("risk_reward"),
            "operational_reason": confirmations[0] if confirmations else "Aguardar confirmacao do proximo candle.",
            "confirmation": confirmations,
            "invalidation": invalidations or [risk.get("invalidation")],
            "status": status,
            "score": score,
        }

    def _live_messages(self, context, trend, breakout, pullback, liquidity, signal):
        messages = []
        if trend.get("bias") == "alta":
            messages.append("Contexto de alta por topos e fundos.")
        elif trend.get("bias") == "baixa":
            messages.append("Contexto de baixa por topos e fundos.")
        elif trend.get("bias") == "lateral":
            messages.append("Mercado lateralizado. Evitar entrada.")
        if pullback.get("valid_pullback"):
            messages.append("Pullback valido em regiao operacional.")
        if pullback.get("pullback_failure"):
            messages.append("Falha de pullback detectada.")
        if breakout.get("false_breakout"):
            messages.append("Falso rompimento identificado.")
        if liquidity.get("sweep"):
            messages.append("Liquidez capturada.")
        if signal.get("status") == "entrada possivel":
            messages.append("Entrada operacional possivel.")
        elif signal.get("status") == "invalidado":
            messages.append("Entrada invalidada pela perda do contexto.")
        else:
            messages.append("Aguardar confirmacao do proximo candle.")
        return messages[:8]

    def _chart_marks(self, zones, risk, breakout, pullback, liquidity, apostila=None):
        apostila = apostila or {}
        prior_lines = [
            {
                "type": level.get("type"),
                "label": level.get("label"),
                "price": level.get("price"),
                "color": "#F59E0B" if level.get("type") == "prior_ajuste" else "#94A3B8",
            }
            for level in apostila.get("prior_cote", {}).get("levels", [])
        ]
        return {
            "price_lines": [
                {"type": "support", "label": "Suporte", "price": zones.get("support"), "color": "#22C55E"},
                {"type": "resistance", "label": "Resistencia", "price": zones.get("resistance"), "color": "#EF4444"},
                {"type": "midpoint", "label": "50% Mov.", "price": zones.get("midpoint"), "color": "#A78BFA"},
                {"type": "liquidity_upper", "label": "Liquidez sup.", "price": zones.get("upper_liquidity"), "color": "#D4AF37"},
                {"type": "liquidity_lower", "label": "Liquidez inf.", "price": zones.get("lower_liquidity"), "color": "#38BDF8"},
                {"type": "entry", "label": "Entrada", "price": risk.get("entry"), "color": "#38BDF8"},
                {"type": "stop", "label": "Stop", "price": risk.get("technical_stop"), "color": "#EF4444"},
                {"type": "take_profit", "label": "Take", "price": risk.get("take_profit_1"), "color": "#22C55E"},
            ] + prior_lines,
            "events": {
                "false_breakout": breakout.get("false_breakout"),
                "pullback": pullback.get("valid_pullback"),
                "pullback_failure": pullback.get("pullback_failure"),
                "liquidity_sweep": liquidity.get("sweep"),
                "apostila_phase": apostila.get("market_phase", {}).get("phase"),
                "apostila_execution": apostila.get("execution", {}).get("mode"),
                "three_candle_pattern": apostila.get("three_candle_pattern", {}).get("active"),
            },
        }

    def _narrative(self, context, trend, current, breakout, pullback, liquidity, risk, apostila=None):
        apostila = apostila or {}
        lines = [f"{context['label']}: {trend['structure']}."]
        if apostila.get("reading"):
            lines.append(apostila["reading"])
        lines.append(current["reading"])
        lines.append(breakout["reading"])
        lines.append(pullback["reading"])
        if liquidity["sweep"]:
            lines.append("Liquidez capturada; avaliar armadilha antes de assumir continuidade.")
        if risk["scenario_risk"] == "alto":
            lines.append("Contexto desfavoravel para entrada; risco operacional elevado.")
        elif risk["entry_quality"] == "alta":
            lines.append("Qualidade do contexto acima da media, mas a leitura continua dependente de confirmacao.")
        return lines[:8]


def build_operacional_reading(candles: pd.DataFrame, symbol: str = "BTCUSDT", timeframe: str = "15m") -> dict[str, Any]:
    return OperacionalReader(candles, symbol, timeframe).analyze()


def build_operacional_context(candles: pd.DataFrame, symbol: str = "BTCUSDT", timeframe: str = "15m") -> dict[str, Any]:
    return OperacionalReader(candles, symbol, timeframe).context_only()


def build_candle_flow(candles: pd.DataFrame, symbol: str = "BTCUSDT", timeframe: str = "15m") -> dict[str, Any]:
    return OperacionalReader(candles, symbol, timeframe).candle_flow_only()
