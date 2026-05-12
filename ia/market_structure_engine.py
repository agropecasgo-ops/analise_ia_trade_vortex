"""
Market structure layer: BOS, CHOCH, swings, liquidity, sweeps, OB and FVG.
"""

from __future__ import annotations

from typing import Any

import pandas as pd


def _clean(candles: pd.DataFrame) -> pd.DataFrame:
    if candles is None or candles.empty:
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
    return candles.copy().dropna(subset=["open", "high", "low", "close", "volume"])


class MarketStructureEngine:
    def __init__(self, candles: pd.DataFrame, macro_context: dict[str, Any] | None = None) -> None:
        self.df = _clean(candles)
        self.macro = macro_context or {}

    def analyze(self) -> dict[str, Any]:
        if len(self.df) < 40:
            return {"layer": "market_structure", "valid": False, "blockers": ["Candles insuficientes para estrutura."]}

        swings = self._swings()
        bos = self._bos(swings)
        choch = self._choch(swings, bos)
        liquidity = self._liquidity(swings)
        sweep = self._sweep(swings)
        order_block = self._order_block(bos, sweep)
        fvg = self._fvg()
        direction = self._direction(bos, choch, sweep)

        return {
            "layer": "market_structure",
            "valid": direction in ["BUY", "SELL"],
            "direction": direction,
            "swings": swings,
            "bos": bos,
            "choch": choch,
            "liquidity": liquidity,
            "liquidity_sweep": sweep,
            "order_block": order_block,
            "fvg": fvg,
            "institutional_zone": order_block if order_block.get("valid") else fvg if fvg.get("valid") else None,
            "blockers": [] if direction in ["BUY", "SELL"] else ["Estrutura sem BOS/CHOCH acionavel."],
        }

    def _swings(self, window: int = 2) -> dict[str, list[dict[str, Any]]]:
        highs = []
        lows = []
        frame = self.df.tail(120)
        for pos in range(window, len(frame) - window):
            row = frame.iloc[pos]
            high_slice = frame["high"].iloc[pos - window:pos + window + 1]
            low_slice = frame["low"].iloc[pos - window:pos + window + 1]
            index_value = frame.index[pos]
            if float(row["high"]) >= float(high_slice.max()):
                highs.append({"index": str(index_value), "position": pos, "price": float(row["high"])})
            if float(row["low"]) <= float(low_slice.min()):
                lows.append({"index": str(index_value), "position": pos, "price": float(row["low"])})
        return {"highs": highs[-8:], "lows": lows[-8:]}

    def _bos(self, swings: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
        close = float(self.df["close"].iloc[-1])
        previous_close = float(self.df["close"].iloc[-2])
        last_high = swings["highs"][-1] if swings["highs"] else None
        last_low = swings["lows"][-1] if swings["lows"] else None
        if last_high and previous_close <= last_high["price"] < close:
            return {"detected": True, "direction": "BUY", "level": last_high["price"]}
        if last_low and previous_close >= last_low["price"] > close:
            return {"detected": True, "direction": "SELL", "level": last_low["price"]}
        return {"detected": False, "direction": "NEUTRAL", "level": None}

    def _choch(self, swings: dict[str, list[dict[str, Any]]], bos: dict[str, Any]) -> dict[str, Any]:
        if not bos.get("detected"):
            return {"detected": False, "direction": "NEUTRAL", "level": None}
        macro_direction = self.macro.get("htf_direction") or self.macro.get("direction")
        detected = macro_direction in ["BUY", "SELL"] and bos["direction"] != macro_direction
        return {"detected": detected, "direction": bos["direction"] if detected else "NEUTRAL", "level": bos.get("level")}

    def _liquidity(self, swings: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
        highs = swings["highs"][-4:]
        lows = swings["lows"][-4:]
        price = float(self.df["close"].iloc[-1])
        zones = []
        for side, items in [("buy_side", highs), ("sell_side", lows)]:
            for item in items:
                distance_pct = abs(item["price"] - price) / max(price, 0.00000001) * 100
                if distance_pct <= 1.2:
                    zones.append({"side": side, "price": item["price"], "distance_pct": round(distance_pct, 3)})
        return {"zones": zones, "nearest": min(zones, key=lambda item: item["distance_pct"]) if zones else None}

    def _sweep(self, swings: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
        candle = self.df.iloc[-1]
        high = float(candle["high"])
        low = float(candle["low"])
        close = float(candle["close"])
        last_high = swings["highs"][-1] if swings["highs"] else None
        last_low = swings["lows"][-1] if swings["lows"] else None
        if last_high and high > last_high["price"] and close < last_high["price"]:
            return {"detected": True, "direction": "SELL", "side": "buy_side", "level": last_high["price"]}
        if last_low and low < last_low["price"] and close > last_low["price"]:
            return {"detected": True, "direction": "BUY", "side": "sell_side", "level": last_low["price"]}
        return {"detected": False, "direction": "NEUTRAL", "side": None, "level": None}

    def _order_block(self, bos: dict[str, Any], sweep: dict[str, Any]) -> dict[str, Any]:
        direction = sweep.get("direction") if sweep.get("detected") else bos.get("direction")
        if direction not in ["BUY", "SELL"]:
            return {"valid": False}
        frame = self.df.tail(30)
        if direction == "BUY":
            candidates = frame[frame["close"] < frame["open"]]
        else:
            candidates = frame[frame["close"] > frame["open"]]
        if candidates.empty:
            return {"valid": False}
        candle = candidates.iloc[-1]
        return {
            "valid": True,
            "direction": direction,
            "low": float(candle["low"]),
            "high": float(candle["high"]),
            "mid": round((float(candle["low"]) + float(candle["high"])) / 2, 8),
        }

    def _fvg(self) -> dict[str, Any]:
        frame = self.df.tail(40)
        for index in range(len(frame) - 1, 1, -1):
            left = frame.iloc[index - 2]
            right = frame.iloc[index]
            if float(left["high"]) < float(right["low"]):
                return {"valid": True, "direction": "BUY", "low": float(left["high"]), "high": float(right["low"])}
            if float(left["low"]) > float(right["high"]):
                return {"valid": True, "direction": "SELL", "low": float(right["high"]), "high": float(left["low"])}
        return {"valid": False}

    def _direction(self, bos: dict[str, Any], choch: dict[str, Any], sweep: dict[str, Any]) -> str:
        if sweep.get("detected"):
            return sweep["direction"]
        if choch.get("detected"):
            return choch["direction"]
        if bos.get("detected"):
            return bos["direction"]
        return "NEUTRAL"
