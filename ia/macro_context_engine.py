"""
Macro context layer for live trading signals.

Uses price action, volatility and session context. H1 and M15 define the
primary direction, M5 confirms context, and lower timeframes are only entry
triggers.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import pandas as pd


def _clean(candles: pd.DataFrame) -> pd.DataFrame:
    if candles is None or candles.empty:
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
    return candles.copy().dropna(subset=["open", "high", "low", "close", "volume"])


def _pct(value: float, base: float) -> float:
    return (value / max(abs(base), 0.00000001)) * 100


class MacroContextEngine:
    def __init__(self, candles_by_timeframe: dict[str, pd.DataFrame], symbol: str) -> None:
        self.candles = {key: _clean(value) for key, value in (candles_by_timeframe or {}).items()}
        self.symbol = symbol

    def analyze(self) -> dict[str, Any]:
        h1 = self._trend_snapshot("1h")
        m15 = self._trend_snapshot("15m")
        m5 = self._trend_snapshot("5m")
        primary_direction = self._primary_direction(h1, m15)
        confirmed = primary_direction in ["BUY", "SELL"] and m5["direction"] in [primary_direction, "NEUTRAL"]
        lateral = self._is_lateral(h1, m15, m5)
        volatility = self._volatility_snapshot()
        session = self._session()
        blockers = []

        if lateral:
            blockers.append("Mercado lateral: H1/M15 sem direcao limpa.")
        if volatility["state"] == "LOW":
            blockers.append("Volatilidade baixa: sem expansao suficiente para entrada.")
        if not confirmed:
            blockers.append("M5 nao confirma o contexto macro.")

        return {
            "layer": "macro_context",
            "symbol": self.symbol,
            "direction": primary_direction if confirmed and not lateral else "NEUTRAL",
            "htf_direction": primary_direction,
            "trend": {
                "h1": h1,
                "m15": m15,
                "m5": m5,
                "aligned": primary_direction in ["BUY", "SELL"] and h1["direction"] == m15["direction"],
                "confirmed_by_m5": confirmed,
            },
            "volatility": volatility,
            "session": session,
            "lateral": lateral,
            "blocked": bool(blockers),
            "blockers": blockers,
        }

    def _trend_snapshot(self, timeframe: str) -> dict[str, Any]:
        df = self.candles.get(timeframe)
        if df is None or len(df) < 30:
            return {"direction": "NEUTRAL", "strength": 0, "reason": f"{timeframe} sem candles suficientes."}

        recent = df.tail(48)
        first = float(recent["close"].iloc[0])
        last = float(recent["close"].iloc[-1])
        slope_pct = _pct(last - first, first)
        highs = recent["high"].tail(20)
        lows = recent["low"].tail(20)
        higher_high = float(highs.iloc[-1]) >= float(highs.iloc[:10].max())
        higher_low = float(lows.iloc[-1]) >= float(lows.iloc[:10].min())
        lower_low = float(lows.iloc[-1]) <= float(lows.iloc[:10].min())
        lower_high = float(highs.iloc[-1]) <= float(highs.iloc[:10].max())
        atr_pct = self._atr_pct(recent)

        direction = "NEUTRAL"
        if slope_pct > 0.18 and higher_high and higher_low:
            direction = "BUY"
        elif slope_pct < -0.18 and lower_low and lower_high:
            direction = "SELL"

        strength = min(100, int(abs(slope_pct) * 35 + atr_pct * 14 + (25 if direction != "NEUTRAL" else 0)))
        return {
            "direction": direction,
            "strength": strength,
            "slope_pct": round(slope_pct, 3),
            "atr_pct": round(atr_pct, 3),
            "reason": f"{timeframe}: {direction} slope={slope_pct:.2f}% atr={atr_pct:.2f}%",
        }

    def _primary_direction(self, h1: dict[str, Any], m15: dict[str, Any]) -> str:
        if h1["direction"] == m15["direction"] and h1["direction"] in ["BUY", "SELL"]:
            return h1["direction"]
        if h1["strength"] >= 65 and h1["direction"] in ["BUY", "SELL"] and m15["direction"] == "NEUTRAL":
            return h1["direction"]
        return "NEUTRAL"

    def _is_lateral(self, h1: dict[str, Any], m15: dict[str, Any], m5: dict[str, Any]) -> bool:
        no_direction = h1["direction"] == "NEUTRAL" and m15["direction"] == "NEUTRAL"
        conflict = h1["direction"] in ["BUY", "SELL"] and m15["direction"] in ["BUY", "SELL"] and h1["direction"] != m15["direction"]
        weak = max(h1["strength"], m15["strength"], m5["strength"]) < 38
        return bool(no_direction or conflict or weak)

    def _volatility_snapshot(self) -> dict[str, Any]:
        df = self.candles.get("5m")
        if df is None or df.empty:
            df = self.candles.get("15m")
        if df is None or df.empty:
            df = self.candles.get("1h")
        if df is None or len(df) < 20:
            return {"state": "LOW", "atr_pct": 0, "good": False}
        atr_pct = self._atr_pct(df.tail(40))
        state = "LOW" if atr_pct < 0.12 else "GOOD" if atr_pct <= 1.4 else "HIGH"
        return {"state": state, "atr_pct": round(atr_pct, 3), "good": state in ["GOOD", "HIGH"]}

    def _atr_pct(self, df: pd.DataFrame) -> float:
        high_low = df["high"] - df["low"]
        high_close = (df["high"] - df["close"].shift(1)).abs()
        low_close = (df["low"] - df["close"].shift(1)).abs()
        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1).dropna()
        if true_range.empty:
            return 0.0
        return _pct(float(true_range.tail(14).mean()), float(df["close"].iloc[-1]))

    def _session(self) -> dict[str, Any]:
        brt = timezone(timedelta(hours=-3), name="BRT")
        hour = datetime.now(brt).hour
        if 9 <= hour <= 12:
            name, quality = "abertura_brasil_ny", "HIGH"
        elif 14 <= hour <= 17:
            name, quality = "tarde_ny", "HIGH"
        elif 4 <= hour <= 8:
            name, quality = "londres", "MEDIUM"
        else:
            name, quality = "baixa_liquidez", "LOW"
        return {"timezone": "BRT", "hour": hour, "name": name, "quality": quality}
