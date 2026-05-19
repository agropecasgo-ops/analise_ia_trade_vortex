"""
Compatibility facade for the institutional flow AI.

The real institutional analysis lives in the engines under ``ia/``.  This
class keeps the legacy ``FlowInstitucionalIA`` entrypoint while delegating the
market reading to ``institutional_unified_engine``.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

try:
    from .ai_narrative_engine import build_institutional_ai_narrative
    from .institutional_unified_engine import build_institutional_unified_analysis
    from .multi_timeframe_context import build_multi_timeframe_context
    from .order_flow_engine import build_order_flow_context
except ImportError:  # Allows direct execution/import from inside the ia folder.
    from ai_narrative_engine import build_institutional_ai_narrative
    from institutional_unified_engine import build_institutional_unified_analysis
    from multi_timeframe_context import build_multi_timeframe_context
    from order_flow_engine import build_order_flow_context


class FlowInstitucionalIA:
    def __init__(
        self,
        asset: str = "UNKNOWN",
        timeframe: str = "1m",
        asset_type: str = "",
        candles_by_timeframe: dict[str, Any] | None = None,
        news: dict[str, Any] | None = None,
        risk_status: dict[str, Any] | None = None,
        operational_mode: str = "moderado",
    ) -> None:
        self.asset = asset
        self.timeframe = timeframe
        self.asset_type = asset_type
        self.operational_mode = operational_mode
        self.candles_by_timeframe = candles_by_timeframe or {}
        self.news = news
        self.risk_status = risk_status

        self.direction = "NEUTRAL"
        self.score = 0
        self.confidence = "LOW"
        self.confidence_value = 0
        self.flow_strength = 0
        self.trend = "NONE"
        self.entry_allowed = False
        self.analysis: dict[str, Any] = {}

    def analyze_market(self, candles: Any) -> dict[str, Any]:
        df = self._to_dataframe(candles)
        candles_by_timeframe = self._build_timeframe_map(candles, df)

        self.analysis = build_institutional_unified_analysis(
            candles=df,
            asset=self.asset,
            timeframe=self.timeframe,
            asset_type=self.asset_type,
            candles_by_timeframe=candles_by_timeframe,
            news=self.news,
            risk_status=self.risk_status,
            operational_mode=self.operational_mode,
        )
        self._attach_order_flow_context(df)
        self._attach_multi_timeframe_context(candles_by_timeframe)
        self._attach_ai_narrative_context()

        self._sync_state(self.analysis)
        return self.analysis

    def generate_signal(self) -> dict[str, Any]:
        if not self.analysis:
            return self._empty_signal("Analise ainda nao executada.")

        trade_plan = self.analysis.get("tradePlan") or {}
        timing = self.analysis.get("timing") or {}
        entry_timing = self.analysis.get("entryTiming") or {}
        risk = self.analysis.get("risk") or {}
        direction = self.analysis.get("direction", "NEUTRAL")

        return {
            "direction": self._legacy_direction(direction),
            "direction_code": direction,
            "score": self.score,
            "confidence": self.confidence,
            "confidence_value": self.confidence_value,
            "flow_strength": self.flow_strength,
            "trend": self.trend,
            "entry_allowed": self.entry_allowed,
            "status": self.analysis.get("status", "WAIT_CONFIRMATION"),
            "entry_status": entry_timing.get("label") or self.analysis.get("entryStatus"),
            "entry_timing": entry_timing,
            "do_not_chase": bool(entry_timing.get("do_not_chase")),
            "entry": trade_plan.get("entry"),
            "stop_loss": trade_plan.get("stopLoss"),
            "take_profit_1": trade_plan.get("takeProfit1"),
            "take_profit_2": trade_plan.get("takeProfit2"),
            "risk_reward": trade_plan.get("riskReward"),
            "reason": entry_timing.get("reason") or timing.get("reason") or self.analysis.get("aiExplanation"),
            "risk": risk,
            "analysis": self.analysis,
        }

    def _sync_state(self, analysis: dict[str, Any]) -> None:
        self.score = round(float(analysis.get("score") or 0), 2)
        self.confidence_value = round(float(analysis.get("confidence") or 0), 2)
        self.confidence = self._confidence_label(self.confidence_value)
        self.direction = analysis.get("direction", "NEUTRAL")
        self.flow_strength = self._flow_strength(analysis)
        self.trend = self._trend_label(analysis)
        self.entry_allowed = bool(
            analysis.get("status") in {"HIGH_PROBABILITY", "ENTRY_EARLY", "ENTRY_CONFIRMED"}
            and self.direction in {"BUY", "SELL"}
            and (analysis.get("risk") or {}).get("allowed")
            and not (analysis.get("entryTiming") or {}).get("do_not_chase")
        )

    def _attach_order_flow_context(self, df: pd.DataFrame) -> None:
        order_flow = build_order_flow_context(df)
        self.analysis["orderFlowContext"] = order_flow
        behavior = self.analysis.setdefault("institutionalBehavior", {})
        behavior["orderFlowContext"] = order_flow

    def _attach_multi_timeframe_context(self, candles_by_timeframe: dict[str, pd.DataFrame]) -> None:
        self.analysis["multiTimeframeContext"] = build_multi_timeframe_context(candles_by_timeframe)

    def _attach_ai_narrative_context(self) -> None:
        behavior = self.analysis.get("institutionalBehavior") or {}
        self.analysis["aiNarrativeContext"] = build_institutional_ai_narrative(
            fluxo=behavior.get("flow"),
            liquidez=self.analysis.get("liquidity"),
            estrutura=self.analysis.get("marketStructure"),
            multi_timeframe=self.analysis.get("multiTimeframeContext"),
            orderflow=self.analysis.get("orderFlowContext"),
            contexto_macro=self.analysis.get("macroContext"),
        )

    def _build_timeframe_map(self, candles: Any, df: pd.DataFrame) -> dict[str, pd.DataFrame]:
        frames = {
            key: self._to_dataframe(value)
            for key, value in self.candles_by_timeframe.items()
            if value is not None
        }
        if isinstance(candles, dict) and not self._looks_like_ohlcv(candles):
            frames.update({key: self._to_dataframe(value) for key, value in candles.items()})
        frames.setdefault(self.timeframe, df)
        for timeframe in ("1m", "5m", "15m", "1h"):
            frames.setdefault(timeframe, df)
        return frames

    def _to_dataframe(self, candles: Any) -> pd.DataFrame:
        if isinstance(candles, pd.DataFrame):
            df = candles.copy()
        elif isinstance(candles, dict) and self._looks_like_ohlcv(candles):
            df = pd.DataFrame(candles)
        elif isinstance(candles, dict):
            first_frame = next((value for value in candles.values() if value is not None), [])
            df = self._to_dataframe(first_frame)
        else:
            df = pd.DataFrame(candles or [])

        df = df.rename(columns={column: str(column).lower() for column in df.columns})
        for column in ("open", "high", "low", "close"):
            if column not in df.columns:
                df[column] = 0.0
        if "volume" not in df.columns:
            df["volume"] = 0.0

        required = ["open", "high", "low", "close", "volume"]
        df = df[required].apply(pd.to_numeric, errors="coerce")
        return df.dropna(subset=required).reset_index(drop=True)

    def _looks_like_ohlcv(self, value: dict[str, Any]) -> bool:
        keys = {str(key).lower() for key in value.keys()}
        return bool({"open", "high", "low", "close"} & keys)

    def _flow_strength(self, analysis: dict[str, Any]) -> float:
        behavior = analysis.get("institutionalBehavior") or {}
        volume = behavior.get("volume") or {}
        flow = behavior.get("flow") or {}
        candidates = [
            analysis.get("score"),
            volume.get("confidence"),
            flow.get("confidence"),
        ]
        values = [float(value) for value in candidates if isinstance(value, (int, float))]
        return round(sum(values) / len(values), 2) if values else 0

    def _trend_label(self, analysis: dict[str, Any]) -> str:
        macro = analysis.get("macroContext") or {}
        direction = macro.get("direction") or analysis.get("direction")
        return {"BUY": "ALTA", "SELL": "BAIXA", "NEUTRAL": "LATERAL"}.get(direction, "NONE")

    def _confidence_label(self, confidence: float) -> str:
        if confidence >= 75:
            return "ALTA"
        if confidence >= 50:
            return "MEDIA"
        return "BAIXA"

    def _legacy_direction(self, direction: str) -> str:
        return {"BUY": "COMPRA", "SELL": "VENDA", "NEUTRAL": "AGUARDAR"}.get(direction, "AGUARDAR")

    def _empty_signal(self, reason: str) -> dict[str, Any]:
        return {
            "direction": "AGUARDAR",
            "direction_code": "NEUTRAL",
            "score": self.score,
            "confidence": self.confidence,
            "confidence_value": self.confidence_value,
            "flow_strength": self.flow_strength,
            "trend": self.trend,
            "entry_allowed": False,
            "status": "NO_TRADE",
            "entry": None,
            "stop_loss": None,
            "take_profit_1": None,
            "take_profit_2": None,
            "risk_reward": None,
            "reason": reason,
            "risk": {"allowed": False, "rejections": [reason]},
            "analysis": {},
        }
