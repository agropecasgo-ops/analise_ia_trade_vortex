"""
Institutional force heatmap.

Builds a multi-timeframe / multi-asset force view from the unified
institutional engine. This is read-only and does not alter signal generation.
"""

from __future__ import annotations

from typing import Any, Callable

import pandas as pd

from .institutional_unified_engine import build_institutional_unified_analysis


def _num(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if number == number else default


class ForceHeatmapEngine:
    def __init__(
        self,
        symbols: list[str],
        timeframes: list[str],
        candle_loader: Callable[[str, str, int], pd.DataFrame],
        asset_type_resolver: Callable[[str], str] | None = None,
        limit: int = 220,
    ) -> None:
        self.symbols = [item for item in symbols if item]
        self.timeframes = [item for item in timeframes if item]
        self.candle_loader = candle_loader
        self.asset_type_resolver = asset_type_resolver or (lambda _symbol: "")
        self.limit = max(80, min(int(limit or 220), 400))

    def build(self) -> dict[str, Any]:
        assets: dict[str, Any] = {}
        cells: list[dict[str, Any]] = []

        for symbol in self.symbols:
            asset_cells = []
            for timeframe in self.timeframes:
                cell = self._cell(symbol, timeframe)
                cells.append(cell)
                asset_cells.append(cell)
            assets[symbol] = self._asset_summary(symbol, asset_cells)

        ranked = sorted(assets.values(), key=lambda item: item["netForce"], reverse=True)
        strongest = ranked[0] if ranked else None
        weakest = ranked[-1] if ranked else None
        return {
            "success": True,
            "symbols": self.symbols,
            "timeframes": self.timeframes,
            "cells": cells,
            "assets": assets,
            "strongestAsset": strongest,
            "weakestAsset": weakest,
            "summary": self._summary(strongest, weakest),
        }

    def _cell(self, symbol: str, timeframe: str) -> dict[str, Any]:
        try:
            df = self.candle_loader(symbol, timeframe, self.limit)
            payload = build_institutional_unified_analysis(
                candles=df,
                asset=symbol,
                timeframe=timeframe,
                asset_type=self.asset_type_resolver(symbol),
            )
            probabilities = payload.get("probabilities") or {}
            layers = payload.get("layersUsed") or []
            direction = payload.get("direction", "NEUTRAL")
            buy = _num(probabilities.get("buy"))
            sell = _num(probabilities.get("sell"))
            neutral = _num(probabilities.get("sideways"))
            score = _num(payload.get("score"))
            conflict = self._conflict(payload, buy, sell, neutral)
            return {
                "symbol": symbol,
                "timeframe": timeframe,
                "direction": direction,
                "buyForce": round(buy, 2),
                "sellForce": round(sell, 2),
                "neutralForce": round(neutral, 2),
                "score": round(score, 2),
                "confidence": round(_num(payload.get("confidence")), 2),
                "conflict": conflict,
                "status": payload.get("status"),
                "layersUsed": layers,
                "reason": payload.get("aiExplanation"),
            }
        except Exception as error:
            return {
                "symbol": symbol,
                "timeframe": timeframe,
                "direction": "NEUTRAL",
                "buyForce": 0,
                "sellForce": 0,
                "neutralForce": 100,
                "score": 0,
                "confidence": 0,
                "conflict": {"detected": True, "level": 100, "reason": str(error)},
                "status": "NO_DATA",
                "layersUsed": [],
                "reason": str(error),
            }

    def _asset_summary(self, symbol: str, cells: list[dict[str, Any]]) -> dict[str, Any]:
        if not cells:
            return {"symbol": symbol, "buyForce": 0, "sellForce": 0, "neutralForce": 100, "netForce": 0, "averageScore": 0}
        buy = sum(_num(item.get("buyForce")) for item in cells) / len(cells)
        sell = sum(_num(item.get("sellForce")) for item in cells) / len(cells)
        neutral = sum(_num(item.get("neutralForce")) for item in cells) / len(cells)
        score = sum(_num(item.get("score")) for item in cells) / len(cells)
        return {
            "symbol": symbol,
            "buyForce": round(buy, 2),
            "sellForce": round(sell, 2),
            "neutralForce": round(neutral, 2),
            "netForce": round(buy - sell, 2),
            "averageScore": round(score, 2),
            "dominantDirection": "BUY" if buy > sell and buy > neutral else "SELL" if sell > buy and sell > neutral else "NEUTRAL",
        }

    def _conflict(self, payload: dict[str, Any], buy: float, sell: float, neutral: float) -> dict[str, Any]:
        direction = payload.get("direction")
        macro = (payload.get("macroContext") or {}).get("direction")
        structure = (payload.get("marketStructure") or {}).get("direction")
        different = len({item for item in [direction, macro, structure] if item}) > 1
        force_conflict = abs(buy - sell) <= 12 and max(buy, sell) >= 30
        lateral = neutral >= 55
        level = min(100, abs(50 - abs(buy - sell)) + (20 if different else 0) + (15 if lateral else 0))
        return {
            "detected": bool(different or force_conflict or lateral),
            "level": round(level, 2),
            "reason": "Camadas divergentes ou mercado lateral." if different or lateral else "Forcas compradora e vendedora proximas.",
        }

    def _summary(self, strongest: dict[str, Any] | None, weakest: dict[str, Any] | None) -> str:
        if not strongest or not weakest:
            return "Heatmap sem ativos suficientes."
        return f"Ativo mais forte: {strongest['symbol']} ({strongest['netForce']}). Ativo mais fraco: {weakest['symbol']} ({weakest['netForce']})."


def build_force_heatmap(
    symbols: list[str],
    timeframes: list[str],
    candle_loader: Callable[[str, str, int], pd.DataFrame],
    asset_type_resolver: Callable[[str], str] | None = None,
    limit: int = 220,
) -> dict[str, Any]:
    return ForceHeatmapEngine(symbols, timeframes, candle_loader, asset_type_resolver, limit).build()
