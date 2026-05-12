"""
Confirmation layer for layered live signals.
"""

from __future__ import annotations

from typing import Any

import pandas as pd


def _clean(candles: pd.DataFrame) -> pd.DataFrame:
    if candles is None or candles.empty:
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
    return candles.copy().dropna(subset=["open", "high", "low", "close", "volume"])


class ConfirmationEngine:
    def __init__(self, candles: pd.DataFrame, macro_context: dict[str, Any], structure: dict[str, Any]) -> None:
        self.df = _clean(candles)
        self.macro = macro_context or {}
        self.structure = structure or {}

    def analyze(self) -> dict[str, Any]:
        if len(self.df) < 30:
            return {"layer": "confirmation", "valid": False, "blockers": ["Candles insuficientes para confirmar."]}

        volume = self._volume()
        candle = self._candle()
        breakout = self._breakout(volume, candle)
        rejection = self._rejection()
        false_breakout = self._false_breakout(volume, candle)
        direction = self.structure.get("direction", "NEUTRAL")
        valid = all([
            direction in ["BUY", "SELL"],
            volume["strong"],
            candle["strong"],
            breakout["valid"] or rejection["valid"],
            not false_breakout["detected"],
        ])
        blockers = []
        if not volume["strong"]:
            blockers.append("Volume ainda nao confirma.")
        if not candle["strong"]:
            blockers.append("Candle gatilho fraco.")
        if not breakout["valid"] and not rejection["valid"]:
            blockers.append("Sem rompimento valido ou rejeicao institucional.")
        if false_breakout["detected"]:
            blockers.append("Falso rompimento detectado.")

        return {
            "layer": "confirmation",
            "valid": valid,
            "direction": direction if valid else "NEUTRAL",
            "volume": volume,
            "candle": candle,
            "breakout": breakout,
            "rejection": rejection,
            "false_breakout": false_breakout,
            "blockers": blockers,
        }

    def _volume(self) -> dict[str, Any]:
        recent_volume = float(self.df["volume"].iloc[-1])
        average = float(self.df["volume"].tail(30).mean())
        ratio = recent_volume / max(average, 0.00000001)
        return {"strong": ratio >= 1.25, "ratio": round(ratio, 2)}

    def _candle(self) -> dict[str, Any]:
        candle = self.df.iloc[-1]
        body = abs(float(candle["close"]) - float(candle["open"]))
        full_range = max(float(candle["high"]) - float(candle["low"]), 0.00000001)
        body_ratio = body / full_range
        direction = "BUY" if candle["close"] > candle["open"] else "SELL" if candle["close"] < candle["open"] else "NEUTRAL"
        expected = self.structure.get("direction")
        return {
            "strong": body_ratio >= 0.52 and direction == expected,
            "direction": direction,
            "body_ratio": round(body_ratio, 3),
        }

    def _breakout(self, volume: dict[str, Any], candle: dict[str, Any]) -> dict[str, Any]:
        bos = self.structure.get("bos", {})
        if not bos.get("detected"):
            return {"valid": False, "level": None}
        close = float(self.df["close"].iloc[-1])
        level = bos.get("level")
        direction = self.structure.get("direction")
        valid = bool(
            level is not None
            and volume["strong"]
            and candle["strong"]
            and ((direction == "BUY" and close > level) or (direction == "SELL" and close < level))
        )
        return {"valid": valid, "level": level}

    def _rejection(self) -> dict[str, Any]:
        zone = self.structure.get("institutional_zone") or {}
        if not zone or not zone.get("valid"):
            return {"valid": False, "zone": None}
        candle = self.df.iloc[-1]
        direction = self.structure.get("direction")
        touched = float(candle["low"]) <= float(zone["high"]) and float(candle["high"]) >= float(zone["low"])
        if direction == "BUY":
            wick = min(float(candle["open"]), float(candle["close"])) - float(candle["low"])
            body = abs(float(candle["close"]) - float(candle["open"]))
            valid = touched and wick > body * 0.8 and candle["close"] > candle["open"]
        else:
            wick = float(candle["high"]) - max(float(candle["open"]), float(candle["close"]))
            body = abs(float(candle["close"]) - float(candle["open"]))
            valid = touched and wick > body * 0.8 and candle["close"] < candle["open"]
        return {"valid": bool(valid), "zone": zone}

    def _false_breakout(self, volume: dict[str, Any], candle: dict[str, Any]) -> dict[str, Any]:
        sweep = self.structure.get("liquidity_sweep", {})
        detected = bool(sweep.get("detected") and (not volume["strong"] or not candle["strong"]))
        return {"detected": detected, "reason": "Sweep sem volume/candle confirmador." if detected else None}
