"""
Tape Reading / Order Flow para a IA Completa.

Quando nao ha livro de ofertas ou times & trades, usa fallback por OHLCV:
volume relativo, fechamento no extremo do candle, spread e sequencia.
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


class TapeReading:
    def __init__(self, candles, trades=None, order_book=None):
        self.df = candles.copy().dropna(subset=["open", "high", "low", "close", "volume"])
        if len(self.df) < 25:
            raise ValueError("tape_reading_requires_at_least_25_candles")
        self.trades = trades or []
        self.order_book = order_book or {}

    def read(self):
        if self.trades or self.order_book:
            return self._from_realtime_data()
        return self._fallback_ohlcv()

    def _fallback_ohlcv(self):
        recent = self.df.tail(30)
        current = recent.iloc[-1]
        prev = recent.iloc[-2]
        vol_mean = float(recent["volume"].tail(20).mean() or 1)
        volume_ratio = float(current.volume) / max(vol_mean, 1e-9)
        spread = max(float(current.high) - float(current.low), float(current.close) * 0.00001)
        close_position = (float(current.close) - float(current.low)) / spread
        body_ratio = abs(float(current.close) - float(current.open)) / spread
        direction = "buy" if float(current.close) > float(current.open) else "sell" if float(current.close) < float(current.open) else "neutral"
        sequence = self._sequence(recent.tail(6))

        buy_aggression = int(max(0, min(100, (close_position * 55) + (volume_ratio * 18) + (body_ratio * 20) + (sequence["buy"] * 5))))
        sell_aggression = int(max(0, min(100, ((1 - close_position) * 55) + (volume_ratio * 18) + (body_ratio * 20) + (sequence["sell"] * 5))))
        absorption = volume_ratio >= 1.45 and body_ratio <= 0.35
        imbalance = buy_aggression - sell_aggression
        if imbalance > 12:
            bias = "BUY_FLOW"
        elif imbalance < -12:
            bias = "SELL_FLOW"
        else:
            bias = "BALANCED_FLOW"
        pressure = "compradora" if bias == "BUY_FLOW" else "vendedora" if bias == "SELL_FLOW" else "equilibrada"
        flow_score = int(max(0, min(100, 50 + imbalance * 0.55 + (8 if volume_ratio >= 1.2 else -5) - (10 if absorption else 0))))

        return {
            "source": "ohlcv_fallback",
            "order_flow_bias": bias,
            "buy_aggression": buy_aggression,
            "sell_aggression": sell_aggression,
            "absorption": {"detected": bool(absorption), "side": direction.upper(), "volume_ratio": round(volume_ratio, 2)},
            "imbalance": int(imbalance),
            "pressure": pressure,
            "aggressor_volume": round(float(current.volume) * max(body_ratio, 0.12), 4),
            "flow_score": flow_score,
            "confirmations": self._confirmations(bias, volume_ratio, absorption, sequence),
            "invalidations": self._invalidations(bias, volume_ratio, absorption),
            "score_adjustment": int(max(-8, min(8, (flow_score - 50) / 6))),
            "metrics": {
                "volume_ratio": round(volume_ratio, 2),
                "close_position": round(close_position, 3),
                "body_ratio": round(body_ratio, 3),
                "previous_change_pct": round((float(current.close) - float(prev.close)) / max(float(prev.close), 1e-9) * 100, 3),
                "sequence": sequence,
            },
            "explanation": self._explanation(bias, pressure, absorption, volume_ratio),
        }

    def _from_realtime_data(self):
        buy_volume = sum(float(item.get("qty", 0)) for item in self.trades if str(item.get("side", "")).lower() in ["buy", "comprador"])
        sell_volume = sum(float(item.get("qty", 0)) for item in self.trades if str(item.get("side", "")).lower() in ["sell", "vendedor"])
        total = max(buy_volume + sell_volume, 1e-9)
        buy_aggression = int(buy_volume / total * 100)
        sell_aggression = int(sell_volume / total * 100)
        imbalance = buy_aggression - sell_aggression
        bias = "BUY_FLOW" if imbalance > 10 else "SELL_FLOW" if imbalance < -10 else "BALANCED_FLOW"
        absorption = abs(imbalance) <= 8 and total > 0
        flow_score = int(max(0, min(100, 50 + imbalance * 0.7)))
        return {
            "source": "realtime",
            "order_flow_bias": bias,
            "buy_aggression": buy_aggression,
            "sell_aggression": sell_aggression,
            "absorption": {"detected": absorption, "side": "BALANCED"},
            "imbalance": imbalance,
            "pressure": "compradora" if bias == "BUY_FLOW" else "vendedora" if bias == "SELL_FLOW" else "equilibrada",
            "aggressor_volume": round(total, 4),
            "flow_score": flow_score,
            "confirmations": ["Tape reading com dados de trades em tempo real."],
            "invalidations": [],
            "score_adjustment": int(max(-8, min(8, (flow_score - 50) / 6))),
            "metrics": {"buy_volume": buy_volume, "sell_volume": sell_volume},
            "explanation": "Fluxo calculado por times & trades/livro quando disponivel.",
        }

    def _sequence(self, candles):
        buy = int((candles["close"] > candles["open"]).sum())
        sell = int((candles["close"] < candles["open"]).sum())
        return {"buy": buy, "sell": sell}

    def _confirmations(self, bias, volume_ratio, absorption, sequence):
        items = []
        if bias == "BUY_FLOW":
            items.append("Agressao compradora dominante no fluxo.")
        if bias == "SELL_FLOW":
            items.append("Agressao vendedora dominante no fluxo.")
        if volume_ratio >= 1.25:
            items.append("Volume relativo acima da media no candle atual.")
        if absorption:
            items.append("Absorcao detectada por volume alto e pouco deslocamento.")
        if sequence["buy"] >= 4:
            items.append("Sequencia recente favorece compradores.")
        if sequence["sell"] >= 4:
            items.append("Sequencia recente favorece vendedores.")
        return items[:8]

    def _invalidations(self, bias, volume_ratio, absorption):
        items = []
        if bias == "BALANCED_FLOW":
            items.append("Fluxo equilibrado; sem dominancia clara.")
        if volume_ratio < 0.72:
            items.append("Volume relativo baixo para validar fluxo.")
        if absorption:
            items.append("Absorcao pode travar continuidade imediata.")
        return items[:8]

    def _explanation(self, bias, pressure, absorption, volume_ratio):
        absorption_text = " Absorcao presente." if absorption else ""
        return f"Fluxo {pressure}; bias {bias}; volume relativo {volume_ratio:.2f}x.{absorption_text}"


def read_tape(candles, trades=None, order_book=None):
    return TapeReading(candles, trades=trades, order_book=order_book).read()
