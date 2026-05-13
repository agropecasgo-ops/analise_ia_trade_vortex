"""
Visual liquidity map for the institutional desk.

Maps liquidity pools, sweeps, order blocks, FVGs and likely manipulation areas
from candle data using the existing structure and SMC readers.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from .market_structure_engine import MarketStructureEngine
from .smart_money import analyze_smart_money


def _clean(candles: pd.DataFrame | None) -> pd.DataFrame:
    if candles is None or candles.empty:
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
    df = candles.copy()
    if "volume" not in df.columns:
        df["volume"] = 0
    return df.dropna(subset=["open", "high", "low", "close", "volume"])


def _num(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if number == number else default


def _time(value: Any) -> int:
    try:
        return int(pd.Timestamp(value).timestamp())
    except Exception:
        return 0


class LiquidityVisualEngine:
    def __init__(self, candles: pd.DataFrame, symbol: str, timeframe: str) -> None:
        self.df = _clean(candles)
        self.symbol = symbol
        self.timeframe = timeframe

    def build(self) -> dict[str, Any]:
        if len(self.df) < 40:
            return {
                "success": True,
                "symbol": self.symbol,
                "timeframe": self.timeframe,
                "zones": [],
                "markers": [],
                "summary": "Candles insuficientes para mapa de liquidez.",
            }
        structure = MarketStructureEngine(self.df, {}).analyze()
        smc = analyze_smart_money(self.df, "neutro")
        zones = []
        zones.extend(self._top_bottom_liquidity(structure))
        zones.extend(self._smc_liquidity(smc))
        zones.extend(self._order_blocks(structure, smc))
        zones.extend(self._fvgs(structure, smc))
        zones.extend(self._manipulation_regions(structure, smc))
        markers = self._markers(structure, smc)
        return {
            "success": True,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "zones": self._dedupe_zones(zones)[:24],
            "markers": markers[-40:],
            "sweep": structure.get("liquidity_sweep") or smc.get("liquidity_sweep", {}),
            "summary": self._summary(zones, markers),
            "raw": {
                "structure": structure,
                "smc": smc,
            },
        }

    def _top_bottom_liquidity(self, structure: dict[str, Any]) -> list[dict[str, Any]]:
        zones = []
        swings = structure.get("swings") or {}
        for item in (swings.get("highs") or [])[-6:]:
            price = _num(item.get("price"))
            zones.append(self._zone("Liquidez acima dos topos", "buy_side_liquidity", price, price, "#EF4444", item.get("index")))
        for item in (swings.get("lows") or [])[-6:]:
            price = _num(item.get("price"))
            zones.append(self._zone("Liquidez abaixo dos fundos", "sell_side_liquidity", price, price, "#22C55E", item.get("index")))
        return [zone for zone in zones if zone]

    def _smc_liquidity(self, smc: dict[str, Any]) -> list[dict[str, Any]]:
        zones = []
        for item in smc.get("liquidity", [])[:8]:
            low = _num(item.get("low", item.get("price")))
            high = _num(item.get("high", item.get("price")))
            zones.append(self._zone("Liquidez SMC", item.get("type", "liquidity"), low, high, "#38BDF8", item.get("time")))
        sweep_zone = (smc.get("liquidity_sweep") or {}).get("zone") or {}
        if sweep_zone:
            low = _num(sweep_zone.get("low", sweep_zone.get("price")))
            high = _num(sweep_zone.get("high", sweep_zone.get("price")))
            zones.append(self._zone("Sweep detectado", "sweep", low, high, "#F59E0B", sweep_zone.get("time"), 0.36))
        return [zone for zone in zones if zone]

    def _order_blocks(self, structure: dict[str, Any], smc: dict[str, Any]) -> list[dict[str, Any]]:
        zones = []
        for item in [structure.get("order_block"), smc.get("relevant_order_block"), smc.get("nearest_order_block")]:
            if not isinstance(item, dict) or not item.get("valid", True):
                continue
            zones.append(self._zone("Order Block", item.get("direction", item.get("type", "order_block")), item.get("low"), item.get("high"), "#D4AF37", item.get("time"), 0.24))
        for item in smc.get("order_blocks", [])[-6:]:
            zones.append(self._zone("Order Block", item.get("type", "order_block"), item.get("low"), item.get("high"), "#D4AF37", item.get("time"), 0.18))
        return [zone for zone in zones if zone]

    def _fvgs(self, structure: dict[str, Any], smc: dict[str, Any]) -> list[dict[str, Any]]:
        zones = []
        for item in [structure.get("fvg"), smc.get("relevant_fvg")]:
            if not isinstance(item, dict) or not item.get("valid", True):
                continue
            zones.append(self._zone("FVG", item.get("direction", item.get("type", "fvg")), item.get("low"), item.get("high"), "#A78BFA", item.get("time"), 0.20))
        for item in smc.get("fair_value_gaps", [])[-8:]:
            zones.append(self._zone("FVG", item.get("type", "fvg"), item.get("low"), item.get("high"), "#A78BFA", item.get("time"), 0.16))
        return [zone for zone in zones if zone]

    def _manipulation_regions(self, structure: dict[str, Any], smc: dict[str, Any]) -> list[dict[str, Any]]:
        zones = []
        false_breakout = smc.get("false_breakout") or {}
        sweep = structure.get("liquidity_sweep") or smc.get("liquidity_sweep") or {}
        if false_breakout.get("detected"):
            level = _num(false_breakout.get("level"))
            zones.append(self._zone("Possivel manipulacao", "false_breakout", level, level, "#F97316", false_breakout.get("time"), 0.42))
        if sweep.get("detected"):
            level = _num(sweep.get("level", (sweep.get("zone") or {}).get("price")))
            zones.append(self._zone("Possivel manipulacao", "liquidity_sweep", level, level, "#F97316", (sweep.get("zone") or {}).get("time"), 0.42))
        return [zone for zone in zones if zone]

    def _markers(self, structure: dict[str, Any], smc: dict[str, Any]) -> list[dict[str, Any]]:
        markers = []
        last_time = _time(self.df.index[-1])
        sweep = structure.get("liquidity_sweep") or {}
        if sweep.get("detected"):
            markers.append(self._marker(last_time, "SWEEP", sweep.get("level"), "#F59E0B"))
        false_breakout = smc.get("false_breakout") or {}
        if false_breakout.get("detected"):
            markers.append(self._marker(last_time, "TRAP", false_breakout.get("level"), "#F97316"))
        bos = structure.get("bos") or {}
        if bos.get("detected"):
            markers.append(self._marker(last_time, "BOS", bos.get("level"), "#22C55E"))
        choch = structure.get("choch") or {}
        if choch.get("detected"):
            markers.append(self._marker(last_time, "CHOCH", choch.get("level"), "#A78BFA"))
        return markers

    def _zone(self, label: str, zone_type: str, low: Any, high: Any, color: str, time_value: Any = None, opacity: float = 0.18) -> dict[str, Any] | None:
        low_value = _num(low)
        high_value = _num(high)
        if not low_value and not high_value:
            return None
        if not high_value:
            high_value = low_value
        if not low_value:
            low_value = high_value
        return {
            "label": label,
            "type": zone_type,
            "low": min(low_value, high_value),
            "high": max(low_value, high_value),
            "mid": round((low_value + high_value) / 2, 8),
            "color": color,
            "opacity": opacity,
            "time": str(time_value) if time_value is not None else None,
            "active": True,
        }

    def _marker(self, time_value: int, text: str, price: Any, color: str) -> dict[str, Any]:
        return {
            "time": time_value,
            "position": "aboveBar",
            "shape": "circle",
            "color": color,
            "text": text,
            "price": _num(price) or None,
        }

    def _dedupe_zones(self, zones: list[dict[str, Any]]) -> list[dict[str, Any]]:
        deduped = []
        seen = set()
        for zone in zones:
            key = f"{zone.get('label')}:{zone.get('type')}:{round(_num(zone.get('low')), 6)}:{round(_num(zone.get('high')), 6)}"
            if key in seen:
                continue
            seen.add(key)
            deduped.append(zone)
        return deduped

    def _summary(self, zones: list[dict[str, Any]], markers: list[dict[str, Any]]) -> str:
        sweeps = sum(1 for zone in zones if "sweep" in str(zone.get("type")).lower())
        manipulation = sum(1 for zone in zones if "manip" in str(zone.get("label")).lower())
        return f"{len(zones)} zonas mapeadas, {sweeps} sweep(s), {manipulation} regiao(oes) de possivel manipulacao."


def build_liquidity_visual_map(candles: pd.DataFrame, symbol: str, timeframe: str) -> dict[str, Any]:
    return LiquidityVisualEngine(candles, symbol, timeframe).build()
