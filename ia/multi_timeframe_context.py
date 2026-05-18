"""
Contexto multi-timeframe institucional.

Camada auxiliar: H1 define macro, M15 direcao principal, M5 confirma e M1
refina entrada. Nao gera sinais nem altera score final.
"""

from __future__ import annotations

from typing import Any

import pandas as pd


TIMEFRAME_ROLES = {
    "1h": "macro",
    "15m": "main",
    "5m": "confirmation",
    "1m": "entry",
}

ROLE_WEIGHTS = {
    "macro": 30,
    "main": 35,
    "confirmation": 25,
    "entry": 10,
}


def _num(value: Any, default: float = 0.0) -> float:
    try:
        if pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def _pct(value: float, base: float) -> float:
    return value / max(abs(base), 1e-9) * 100


class MultiTimeframeContext:
    def __init__(self, candles_by_timeframe: dict[str, Any] | None):
        self.candles = {
            self._normalize_timeframe(timeframe): self._to_dataframe(candles)
            for timeframe, candles in (candles_by_timeframe or {}).items()
        }

    def analyze(self) -> dict[str, Any]:
        frames = {timeframe: self._snapshot(timeframe) for timeframe in TIMEFRAME_ROLES}
        macro = frames["1h"]
        main = frames["15m"]
        confirmation = frames["5m"]
        entry = frames["1m"]

        main_direction = main["direction"]
        reference_direction = main_direction if main_direction in {"BUY", "SELL"} else macro["direction"]
        conflicting_timeframes = self._conflicts(frames, reference_direction)
        alignment_score = self._alignment_score(frames, reference_direction)
        confirmation_status = self._confirmation_status(main_direction, confirmation, conflicting_timeframes)
        entry_bias = self._entry_bias(reference_direction, entry, confirmation_status)

        return {
            "layer": "multi_timeframe_context",
            "can_generate_signal": False,
            "macro_trend": macro,
            "main_direction": main_direction,
            "confirmation_status": confirmation_status,
            "entry_bias": entry_bias,
            "alignment_score": round(alignment_score, 2),
            "conflicting_timeframes": conflicting_timeframes,
            "timeframes": frames,
            "summary": self._summary(
                macro,
                main_direction,
                confirmation_status,
                entry_bias,
                alignment_score,
                conflicting_timeframes,
            ),
        }

    def _snapshot(self, timeframe: str) -> dict[str, Any]:
        df = self.candles.get(timeframe)
        if df is None or len(df) < 30:
            return {
                "timeframe": timeframe,
                "role": TIMEFRAME_ROLES[timeframe],
                "direction": "NEUTRAL",
                "strength": 0,
                "slope_pct": 0,
                "structure": "INSUFFICIENT_DATA",
                "reason": f"{timeframe} sem candles suficientes.",
            }

        recent = df.tail(60)
        close = recent["close"]
        first = _num(close.iloc[0])
        last = _num(close.iloc[-1])
        slope_pct = _pct(last - first, first)
        ema_fast = close.ewm(span=9, adjust=False).mean()
        ema_slow = close.ewm(span=21, adjust=False).mean()
        ema_spread = _pct(_num(ema_fast.iloc[-1]) - _num(ema_slow.iloc[-1]), last)
        swing = self._swing_structure(recent)
        atr_pct = self._atr_pct(recent)

        direction = "NEUTRAL"
        if slope_pct > 0.12 and ema_spread > 0 and swing in {"HIGHER_HIGH", "HIGHER_LOW", "UP_STRUCTURE"}:
            direction = "BUY"
        elif slope_pct < -0.12 and ema_spread < 0 and swing in {"LOWER_LOW", "LOWER_HIGH", "DOWN_STRUCTURE"}:
            direction = "SELL"

        strength = _clamp(abs(slope_pct) * 24 + abs(ema_spread) * 18 + atr_pct * 10 + (28 if direction != "NEUTRAL" else 0))
        return {
            "timeframe": timeframe,
            "role": TIMEFRAME_ROLES[timeframe],
            "direction": direction,
            "strength": round(strength, 2),
            "slope_pct": round(slope_pct, 3),
            "ema_spread_pct": round(ema_spread, 3),
            "atr_pct": round(atr_pct, 3),
            "structure": swing,
            "reason": f"{timeframe} {direction} slope={slope_pct:.2f}% ema={ema_spread:.2f}%.",
        }

    def _alignment_score(self, frames: dict[str, dict[str, Any]], reference_direction: str) -> float:
        if reference_direction not in {"BUY", "SELL"}:
            return 0.0
        score = 0.0
        for timeframe, frame in frames.items():
            role = TIMEFRAME_ROLES[timeframe]
            direction = frame["direction"]
            weight = ROLE_WEIGHTS[role]
            strength_factor = _clamp(frame.get("strength", 0), 0, 100) / 100
            if direction == reference_direction:
                score += weight * max(0.55, strength_factor)
            elif direction == "NEUTRAL":
                score += weight * 0.25
        return _clamp(score)

    def _conflicts(self, frames: dict[str, dict[str, Any]], reference_direction: str) -> list[dict[str, Any]]:
        if reference_direction not in {"BUY", "SELL"}:
            return []
        conflicts = []
        opposite = "SELL" if reference_direction == "BUY" else "BUY"
        for timeframe, frame in frames.items():
            if frame["direction"] == opposite:
                conflicts.append({
                    "timeframe": timeframe,
                    "role": frame["role"],
                    "direction": frame["direction"],
                    "strength": frame["strength"],
                })
        return conflicts

    def _confirmation_status(
        self,
        main_direction: str,
        confirmation: dict[str, Any],
        conflicting_timeframes: list[dict[str, Any]],
    ) -> str:
        if main_direction not in {"BUY", "SELL"}:
            return "NO_MAIN_DIRECTION"
        if conflicting_timeframes:
            return "CONFLICT"
        if confirmation["direction"] == main_direction and confirmation["strength"] >= 35:
            return "CONFIRMED"
        if confirmation["direction"] == "NEUTRAL":
            return "WAITING_CONFIRMATION"
        return "WEAK_CONFIRMATION"

    def _entry_bias(self, reference_direction: str, entry: dict[str, Any], confirmation_status: str) -> str:
        if reference_direction not in {"BUY", "SELL"}:
            return "WAIT"
        if confirmation_status == "CONFLICT":
            return "WAIT"
        if entry["direction"] == reference_direction and entry["strength"] >= 30:
            return "BUY_REFINEMENT" if reference_direction == "BUY" else "SELL_REFINEMENT"
        if entry["direction"] == "NEUTRAL" and confirmation_status in {"CONFIRMED", "WAITING_CONFIRMATION"}:
            return "WAIT_PULLBACK"
        return "WAIT"

    def _summary(
        self,
        macro: dict[str, Any],
        main_direction: str,
        confirmation_status: str,
        entry_bias: str,
        alignment_score: float,
        conflicting_timeframes: list[dict[str, Any]],
    ) -> str:
        if conflicting_timeframes:
            frames = ", ".join(item["timeframe"] for item in conflicting_timeframes)
            return f"Conflito multi-timeframe em {frames}; contexto deve ser apenas observado."
        if alignment_score >= 70:
            return f"H1 {macro['direction']}, M15 {main_direction}, M5 {confirmation_status}; M1 {entry_bias}."
        if main_direction in {"BUY", "SELL"}:
            return f"M15 aponta {main_direction}, mas confirmacao ainda esta {confirmation_status}; entrada {entry_bias}."
        return "Sem direcao principal limpa entre H1 e M15; contexto multi-timeframe neutro."

    def _swing_structure(self, df: pd.DataFrame) -> str:
        highs = df["high"].tail(20)
        lows = df["low"].tail(20)
        first_high = _num(highs.iloc[:10].max())
        last_high = _num(highs.iloc[10:].max())
        first_low = _num(lows.iloc[:10].min())
        last_low = _num(lows.iloc[10:].min())
        higher_high = last_high > first_high
        higher_low = last_low >= first_low
        lower_low = last_low < first_low
        lower_high = last_high <= first_high
        if higher_high and higher_low:
            return "UP_STRUCTURE"
        if lower_low and lower_high:
            return "DOWN_STRUCTURE"
        if higher_high:
            return "HIGHER_HIGH"
        if higher_low:
            return "HIGHER_LOW"
        if lower_low:
            return "LOWER_LOW"
        if lower_high:
            return "LOWER_HIGH"
        return "RANGE"

    def _atr_pct(self, df: pd.DataFrame) -> float:
        high_low = df["high"] - df["low"]
        high_close = (df["high"] - df["close"].shift(1)).abs()
        low_close = (df["low"] - df["close"].shift(1)).abs()
        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1).dropna()
        if true_range.empty:
            return 0.0
        return _pct(_num(true_range.tail(14).mean()), _num(df["close"].iloc[-1]))

    def _to_dataframe(self, candles: Any) -> pd.DataFrame:
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

    def _normalize_timeframe(self, timeframe: str) -> str:
        value = str(timeframe or "").strip().lower().replace(" ", "")
        aliases = {"60m": "1h", "1h": "1h", "15m": "15m", "5m": "5m", "1m": "1m"}
        return aliases.get(value, value)


def build_multi_timeframe_context(candles_by_timeframe: dict[str, Any] | None) -> dict[str, Any]:
    return MultiTimeframeContext(candles_by_timeframe).analyze()
