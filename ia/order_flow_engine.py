"""
Order Flow Engine baseado em candles OHLCV normalizados.

Este modulo nao gera sinais de compra/venda. Ele estima contexto de fluxo para
as camadas institucionais quando nao ha times & trades ou livro de ofertas.
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


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


class OrderFlowEngine:
    """Estima leitura de fluxo sem substituir a logica institucional atual."""

    MIN_CANDLES = 12

    def __init__(self, candles: Any):
        self.df = self._prepare(candles)

    def analyze(self) -> dict[str, Any]:
        if len(self.df) < self.MIN_CANDLES:
            return self._empty("Candles insuficientes para leitura de order flow.")

        recent = self.df.tail(30)
        current = recent.iloc[-1]
        prev = recent.iloc[-2]
        volume_mean = max(_safe_float(recent["volume"].tail(20).mean(), 0.0), 1e-9)
        current_volume = max(_safe_float(current.volume), 0.0)
        volume_ratio = current_volume / volume_mean

        spread = max(_safe_float(current.high) - _safe_float(current.low), abs(_safe_float(current.close)) * 0.00001, 1e-9)
        body = _safe_float(current.close) - _safe_float(current.open)
        body_ratio = min(1.0, abs(body) / spread)
        close_position = (_safe_float(current.close) - _safe_float(current.low)) / spread
        close_position = max(0.0, min(1.0, close_position))
        sequence = self._sequence(recent.tail(6))

        buy_pressure = _clamp(
            close_position * 54
            + body_ratio * (18 if body >= 0 else 6)
            + min(volume_ratio, 3.0) * 8
            + sequence["buy"] * 2.5
        )
        sell_pressure = _clamp(
            (1 - close_position) * 54
            + body_ratio * (18 if body <= 0 else 6)
            + min(volume_ratio, 3.0) * 8
            + sequence["sell"] * 2.5
        )
        delta_estimado = buy_pressure - sell_pressure
        imbalance = _clamp(abs(delta_estimado), 0, 100)
        volume_aggression = _clamp((min(volume_ratio, 3.0) / 3.0) * 55 + body_ratio * 35 + imbalance * 0.1)
        absorption_signal = self._absorption_signal(volume_ratio, body_ratio, close_position, body)
        exhaustion_signal = self._exhaustion_signal(recent, volume_ratio, body_ratio, close_position, body)
        flow_direction = self._flow_direction(delta_estimado)
        flow_strength = self._flow_strength(imbalance, volume_aggression, absorption_signal, exhaustion_signal)

        return {
            "source": "ohlcv_candle_store",
            "can_generate_signal": False,
            "buy_pressure": round(buy_pressure, 2),
            "sell_pressure": round(sell_pressure, 2),
            "delta_estimado": round(delta_estimado, 2),
            "flow_direction": flow_direction,
            "flow_strength": round(flow_strength, 2),
            "imbalance": round(imbalance, 2),
            "volume_aggression": round(volume_aggression, 2),
            "absorption_signal": absorption_signal,
            "exhaustion_signal": exhaustion_signal,
            "metrics": {
                "volume_ratio": round(volume_ratio, 2),
                "close_position": round(close_position, 3),
                "body_ratio": round(body_ratio, 3),
                "sequence": sequence,
                "previous_change_pct": round(
                    (_safe_float(current.close) - _safe_float(prev.close)) / max(abs(_safe_float(prev.close)), 1e-9) * 100,
                    3,
                ),
            },
        }

    def _prepare(self, candles: Any) -> pd.DataFrame:
        if isinstance(candles, pd.DataFrame):
            df = candles.copy()
        else:
            df = pd.DataFrame(candles or [])
        df = df.rename(columns={column: str(column).lower() for column in df.columns})
        for column in ("open", "high", "low", "close", "volume"):
            if column not in df.columns:
                df[column] = 0.0
        df = df[["open", "high", "low", "close", "volume"]].apply(pd.to_numeric, errors="coerce")
        return df.dropna(subset=["open", "high", "low", "close", "volume"]).reset_index(drop=True)

    def _sequence(self, candles: pd.DataFrame) -> dict[str, int]:
        return {
            "buy": int((candles["close"] > candles["open"]).sum()),
            "sell": int((candles["close"] < candles["open"]).sum()),
            "neutral": int((candles["close"] == candles["open"]).sum()),
        }

    def _flow_direction(self, delta_estimado: float) -> str:
        if delta_estimado >= 12:
            return "BUY_PRESSURE"
        if delta_estimado <= -12:
            return "SELL_PRESSURE"
        return "BALANCED"

    def _flow_strength(
        self,
        imbalance: float,
        volume_aggression: float,
        absorption_signal: dict[str, Any],
        exhaustion_signal: dict[str, Any],
    ) -> float:
        strength = imbalance * 0.55 + volume_aggression * 0.45
        if absorption_signal.get("detected"):
            strength *= 0.82
        if exhaustion_signal.get("detected"):
            strength *= 0.75
        return _clamp(strength)

    def _absorption_signal(
        self,
        volume_ratio: float,
        body_ratio: float,
        close_position: float,
        body: float,
    ) -> dict[str, Any]:
        detected = volume_ratio >= 1.45 and body_ratio <= 0.35
        if not detected:
            return {"detected": False, "side": "NONE", "confidence": 0}
        side = "SELL_ABSORPTION" if body >= 0 and close_position >= 0.55 else "BUY_ABSORPTION" if body <= 0 and close_position <= 0.45 else "BALANCED_ABSORPTION"
        confidence = _clamp((volume_ratio - 1.0) * 35 + (0.35 - body_ratio) * 80)
        return {"detected": True, "side": side, "confidence": round(confidence, 2)}

    def _exhaustion_signal(
        self,
        recent: pd.DataFrame,
        volume_ratio: float,
        body_ratio: float,
        close_position: float,
        body: float,
    ) -> dict[str, Any]:
        last_three = recent.tail(3)
        directional_run = int((last_three["close"] > last_three["open"]).sum()) == 3 or int((last_three["close"] < last_three["open"]).sum()) == 3
        weak_close_after_run = (body > 0 and close_position < 0.58) or (body < 0 and close_position > 0.42)
        detected = directional_run and volume_ratio >= 1.25 and body_ratio <= 0.45 and weak_close_after_run
        if not detected:
            return {"detected": False, "side": "NONE", "confidence": 0}
        side = "BUY_EXHAUSTION" if body > 0 else "SELL_EXHAUSTION" if body < 0 else "BALANCED_EXHAUSTION"
        confidence = _clamp((volume_ratio - 1.0) * 30 + (0.45 - body_ratio) * 70)
        return {"detected": True, "side": side, "confidence": round(confidence, 2)}

    def _empty(self, reason: str) -> dict[str, Any]:
        return {
            "source": "ohlcv_candle_store",
            "can_generate_signal": False,
            "buy_pressure": 0,
            "sell_pressure": 0,
            "delta_estimado": 0,
            "flow_direction": "UNKNOWN",
            "flow_strength": 0,
            "imbalance": 0,
            "volume_aggression": 0,
            "absorption_signal": {"detected": False, "side": "NONE", "confidence": 0},
            "exhaustion_signal": {"detected": False, "side": "NONE", "confidence": 0},
            "reason": reason,
        }


def build_order_flow_context(candles: Any) -> dict[str, Any]:
    return OrderFlowEngine(candles).analyze()
