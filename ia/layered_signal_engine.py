"""
Layered signal engine for Live Trading IA.

Flow:
Candles -> Macro Context -> Market Structure -> Confirmation -> AI Score -> Signal
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from .ai_score_engine import AIScoreEngine
from .confirmation_engine import ConfirmationEngine
from .macro_context_engine import MacroContextEngine
from .market_structure_engine import MarketStructureEngine


class LayeredSignalEngine:
    def __init__(
        self,
        symbol: str,
        candles_by_timeframe: dict[str, pd.DataFrame],
        entry_timeframe: str = "1m",
        legacy_filters: dict[str, Any] | None = None,
    ) -> None:
        self.symbol = symbol
        self.candles_by_timeframe = candles_by_timeframe or {}
        self.entry_timeframe = entry_timeframe
        self.legacy_filters = legacy_filters or {}

    def analyze(self) -> dict[str, Any]:
        entry_df = self._entry_candles()
        macro = MacroContextEngine(self.candles_by_timeframe, self.symbol).analyze()
        structure = MarketStructureEngine(entry_df, macro).analyze()
        confirmation = ConfirmationEngine(entry_df, macro, structure).analyze()
        direction = self._direction(macro, structure, confirmation)
        score = AIScoreEngine().score(macro, structure, confirmation, {**self.legacy_filters, "direction": direction})
        signal = self._signal(entry_df, macro, structure, confirmation, score)

        return {
            "success": True,
            "engine": "layered_signal_engine",
            "flow": ["candles", "macro_context", "market_structure", "confirmation", "ai_score", "signal"],
            "symbol": self.symbol,
            "entry_timeframe": self.entry_timeframe,
            "macro_context": macro,
            "market_structure": structure,
            "confirmation": confirmation,
            "ai_score": score,
            "legacy_filters": score.get("legacy_filters", {}),
            "signal": signal,
        }

    def _entry_candles(self) -> pd.DataFrame:
        for key in [self.entry_timeframe, "1m", "2m", "5m", "15m"]:
            df = self.candles_by_timeframe.get(key)
            if df is not None and not df.empty:
                return df.copy().dropna(subset=["open", "high", "low", "close", "volume"])
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

    def _signal(
        self,
        entry_df: pd.DataFrame,
        macro: dict[str, Any],
        structure: dict[str, Any],
        confirmation: dict[str, Any],
        score: dict[str, Any],
    ) -> dict[str, Any]:
        direction = self._direction(macro, structure, confirmation)
        if entry_df.empty:
            return self._empty_signal("Sem candles para entrada.", score)
        if macro.get("blocked") or macro.get("direction") not in ["BUY", "SELL"]:
            reason = (macro.get("blockers") or ["Contexto macro nao aprovado."])[0]
            return self._empty_signal(reason, score, direction)
        if not structure.get("valid") or structure.get("direction") not in ["BUY", "SELL"]:
            reason = (structure.get("blockers") or ["Estrutura nao aprovada."])[0]
            return self._empty_signal(reason, score, direction)
        if not confirmation.get("valid") or confirmation.get("direction") not in ["BUY", "SELL"]:
            reason = (confirmation.get("blockers") or ["Confirmacao nao aprovada."])[0]
            return self._empty_signal(reason, score, direction)
        if not score.get("approved") or direction not in ["BUY", "SELL"]:
            reason = score.get("blockers", ["Score insuficiente para sinal."])[0]
            return self._empty_signal(reason, score, direction)

        entry = float(entry_df["close"].iloc[-1])
        levels = self._levels(entry_df, direction, structure, entry)
        risk = self._risk_gate(levels)
        if not risk["allowed"]:
            reason = risk["blockers"][0]
            blocked = self._empty_signal(reason, score, direction)
            blocked["risk_gate"] = risk
            return blocked
        reason = self._reason(macro, structure, confirmation, score)
        return {
            "generated": True,
            "asset": self.symbol,
            "direction": "compra" if direction == "BUY" else "venda",
            "direction_code": direction,
            "entry_price": levels["entry_price"],
            "stop_loss": levels["stop_loss"],
            "take_profit_1": levels["take_profit_1"],
            "take_profit_2": levels["take_profit_2"],
            "risk_reward": levels["risk_reward"],
            "score": score["score"],
            "reason": reason,
            "validated_layer": "ai_score",
            "validated_layers": ["macro_context", "market_structure", "confirmation", "ai_score"],
            "risk_gate": risk,
        }

    def _empty_signal(self, reason: str, score: dict[str, Any], direction: str = "NEUTRAL") -> dict[str, Any]:
        return {
            "generated": False,
            "asset": self.symbol,
            "direction": "aguardar",
            "direction_code": direction,
            "entry_price": None,
            "stop_loss": None,
            "take_profit_1": None,
            "take_profit_2": None,
            "risk_reward": 0,
            "score": score.get("score", 0),
            "reason": reason,
            "validated_layer": None,
            "validated_layers": [],
            "risk_gate": {"allowed": False, "blockers": [reason]},
        }

    def _direction(self, macro: dict[str, Any], structure: dict[str, Any], confirmation: dict[str, Any]) -> str:
        votes = [macro.get("direction"), structure.get("direction"), confirmation.get("direction")]
        buy = votes.count("BUY")
        sell = votes.count("SELL")
        if buy >= 2 and buy > sell:
            return "BUY"
        if sell >= 2 and sell > buy:
            return "SELL"
        return "NEUTRAL"

    def _levels(self, df: pd.DataFrame, direction: str, structure: dict[str, Any], entry: float) -> dict[str, Any]:
        swing_low = self._last_swing_price(structure, "lows")
        swing_high = self._last_swing_price(structure, "highs")
        zone = structure.get("institutional_zone") or {}
        atr = self._atr(df)
        if direction == "BUY":
            stop = min([value for value in [swing_low, zone.get("low"), entry - atr * 1.4] if value is not None])
            risk = max(entry - stop, atr * 0.6)
            tp1 = entry + risk * 1.5
            tp2 = entry + risk * 2.5
        else:
            stop = max([value for value in [swing_high, zone.get("high"), entry + atr * 1.4] if value is not None])
            risk = max(stop - entry, atr * 0.6)
            tp1 = entry - risk * 1.5
            tp2 = entry - risk * 2.5
        rr = abs(tp1 - entry) / max(abs(entry - stop), 0.00000001)
        return {
            "entry_price": round(entry, 8),
            "stop_loss": round(stop, 8),
            "take_profit_1": round(tp1, 8),
            "take_profit_2": round(tp2, 8),
            "risk_reward": round(rr, 2),
        }

    def _risk_gate(self, levels: dict[str, Any]) -> dict[str, Any]:
        blockers = []
        required = ["entry_price", "stop_loss", "take_profit_1"]
        if any(levels.get(key) is None for key in required):
            blockers.append("Plano de risco incompleto.")
        if float(levels.get("risk_reward") or 0) < 1.2:
            blockers.append(f"Risco/retorno abaixo do minimo: 1:{float(levels.get('risk_reward') or 0):.2f}.")
        return {
            "allowed": not blockers,
            "blockers": blockers,
            "min_rr": 1.2,
        }

    def _last_swing_price(self, structure: dict[str, Any], side: str) -> float | None:
        items = structure.get("swings", {}).get(side, [])
        if not items:
            return None
        return float(items[-1]["price"])

    def _atr(self, df: pd.DataFrame) -> float:
        if len(df) < 3:
            return float(df["close"].iloc[-1]) * 0.006
        high_low = df["high"] - df["low"]
        high_close = (df["high"] - df["close"].shift(1)).abs()
        low_close = (df["low"] - df["close"].shift(1)).abs()
        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1).dropna()
        return float(true_range.tail(14).mean()) if not true_range.empty else float(df["close"].iloc[-1]) * 0.006

    def _reason(self, macro: dict[str, Any], structure: dict[str, Any], confirmation: dict[str, Any], score: dict[str, Any]) -> str:
        parts = []
        if macro.get("trend", {}).get("aligned"):
            parts.append("tendencia H1/M15 alinhada")
        if structure.get("liquidity_sweep", {}).get("detected"):
            parts.append("sweep de liquidez")
        if confirmation.get("volume", {}).get("strong"):
            parts.append("volume forte")
        if (structure.get("order_block") or {}).get("valid"):
            parts.append("order block valido")
        elif (structure.get("fvg") or {}).get("valid"):
            parts.append("FVG valido")
        if macro.get("volatility", {}).get("good"):
            parts.append("volatilidade boa")
        return f"Sinal liberado por {', '.join(parts)}. Score {score.get('score')}/{score.get('max_score')}."


def build_layered_signal(
    symbol: str,
    candles_by_timeframe: dict[str, pd.DataFrame],
    entry_timeframe: str = "1m",
    legacy_filters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return LayeredSignalEngine(symbol, candles_by_timeframe, entry_timeframe, legacy_filters).analyze()


def build_layered_signal_from_provider(
    provider_manager: Any,
    asset_type: str,
    symbol: str,
    entry_timeframe: str = "1m",
    limit: int = 260,
) -> dict[str, Any]:
    provider = provider_manager.get_provider(asset_type)
    if provider is None:
        raise ValueError(f"provider_not_found:{asset_type}")
    candles = {
        "1h": provider.get_klines(symbol, "1h", limit),
        "15m": provider.get_klines(symbol, "15m", limit),
        "5m": provider.get_klines(symbol, "5m", limit),
        entry_timeframe: provider.get_klines(symbol, entry_timeframe, limit),
    }
    return build_layered_signal(symbol, candles, entry_timeframe)
