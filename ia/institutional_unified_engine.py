"""
Unified institutional AI analysis contract.

This module is intentionally additive. It orchestrates the existing engines and
normalizes their outputs into one institutional payload without changing Live
Trading, realtime signals, providers or websocket flows.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable

import pandas as pd

try:
    from .confirmation_engine import ConfirmationEngine
    from .layered_signal_engine import build_layered_signal
    from .macro_context_engine import MacroContextEngine
    from .market_structure_engine import MarketStructureEngine
except Exception:  # pragma: no cover - protected by runtime safe calls
    ConfirmationEngine = None
    MacroContextEngine = None
    MarketStructureEngine = None
    build_layered_signal = None

try:
    from .narrative_engine import build_operational_narrative
    from .risk_guard import RiskGuard
    from .smart_money import analyze_smart_money
    from .smc_engine import build_smc_context
    from .tape_reading import read_tape
    from .technical_reader import read_technical
    from .volume_reader import read_volume
    from .wyckoff_engine import build_wyckoff_context
except Exception:  # pragma: no cover - protected by runtime safe calls
    build_operational_narrative = None
    RiskGuard = None
    analyze_smart_money = None
    build_smc_context = None
    read_tape = None
    read_technical = None
    read_volume = None
    build_wyckoff_context = None


VALID_DIRECTIONS = {"BUY", "SELL", "NEUTRAL"}
VALID_STATUSES = {"HIGH_PROBABILITY", "WAIT_CONFIRMATION", "DANGEROUS_MARKET", "NO_TRADE"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _num(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if number == number else default


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def _clean(candles: pd.DataFrame | None) -> pd.DataFrame:
    if candles is None or candles.empty:
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
    df = candles.copy()
    if "volume" not in df.columns:
        df["volume"] = 0
    return df.dropna(subset=["open", "high", "low", "close", "volume"])


def _direction_from_smc(smc: dict[str, Any]) -> str:
    bias = smc.get("institutional_bias")
    if bias == "bullish":
        return "BUY"
    if bias == "bearish":
        return "SELL"
    structure = smc.get("structure") or {}
    if structure.get("bos") == "bullish" or structure.get("choch") == "bullish":
        return "BUY"
    if structure.get("bos") == "bearish" or structure.get("choch") == "bearish":
        return "SELL"
    return "NEUTRAL"


class InstitutionalUnifiedEngine:
    """Builds the canonical institutional payload from existing local engines."""

    CORE_LAYERS = ("layered_signal", "macro_context", "market_structure", "confirmation")
    AUXILIARY_LAYERS = ("technical_reader", "volume_reader", "tape_reading", "wyckoff_engine")

    def __init__(
        self,
        candles: pd.DataFrame,
        asset: str,
        timeframe: str,
        asset_type: str = "",
        candles_by_timeframe: dict[str, pd.DataFrame] | None = None,
        news: dict[str, Any] | None = None,
        risk_status: dict[str, Any] | None = None,
    ) -> None:
        self.df = _clean(candles)
        self.asset = asset
        self.asset_type = asset_type
        self.timeframe = timeframe
        self.news = news or {"available": False, "impact": "UNKNOWN", "items": []}
        self.risk_status = risk_status or {}
        self.candles_by_timeframe = self._candles_by_timeframe(candles_by_timeframe)
        self.layers_used: list[str] = []
        self.errors: dict[str, str] = {}

    def analyze(self) -> dict[str, Any]:
        if self.df.empty:
            return self._payload(
                direction="NEUTRAL",
                score=0,
                confidence=0,
                status="NO_TRADE",
                ai_explanation="Sem candles suficientes para a analise institucional.",
                market_structure={},
                liquidity={},
                institutional_behavior={},
                macro_context={},
                probabilities={"buy": 0, "sell": 0, "sideways": 100},
                trade_plan=self._empty_trade_plan("Aguardar candles suficientes.", "Sem dados de mercado."),
                risk={"allowed": False, "rejections": ["Sem candles suficientes."]},
                timing={"confirmed": False, "reason": "Sem leitura de timing."},
            )

        technical = self._safe_layer("technical_reader", lambda: read_technical(self.df) if read_technical else {})
        volume = self._safe_layer("volume_reader", lambda: read_volume(self.df) if read_volume else {})
        tape = self._safe_layer("tape_reading", lambda: read_tape(self.df) if read_tape else {})
        smart_money = self._safe_layer("smart_money", lambda: analyze_smart_money(self.df, "neutro") if analyze_smart_money else {})
        smc = self._safe_layer("smc_engine", lambda: build_smc_context(self.df, "neutro") if build_smc_context else smart_money)
        wyckoff = self._safe_layer("wyckoff_engine", lambda: build_wyckoff_context(self.df, volume, tape) if build_wyckoff_context else {})

        macro = self._safe_layer("macro_context", self._macro_context)
        structure = self._safe_layer("market_structure", lambda: self._market_structure(macro))
        confirmation = self._safe_layer("confirmation", lambda: self._confirmation(macro, structure))
        layered = self._safe_layer(
            "layered_signal",
            lambda: self._layered_signal(technical, volume, smc or smart_money, wyckoff, tape),
        )

        decision = self._decision(
            layered=layered,
            macro=macro,
            structure=structure,
            confirmation=confirmation,
            smc=smc or smart_money,
            technical=technical,
            volume=volume,
            tape=tape,
            wyckoff=wyckoff,
        )
        trade_plan = self._trade_plan(decision["direction"], layered, structure)
        risk = self._risk(decision, trade_plan)
        status = self._status(decision, risk, macro, structure, confirmation, smc or smart_money)
        if status in {"NO_TRADE", "DANGEROUS_MARKET"}:
            decision["direction"] = "NEUTRAL"
            trade_plan = self._empty_trade_plan(
                "Aguardar nova confluencia institucional.",
                self._first_reason(risk.get("rejections"), structure.get("blockers"), confirmation.get("blockers")),
            )

        timing = self._timing(confirmation, layered, status)
        explanation = self._explanation(decision, status, macro, structure, confirmation, smc or smart_money, risk)
        narrative = self._narrative(decision, smc or smart_money, tape, risk, explanation)

        return self._payload(
            direction=decision["direction"],
            score=decision["score"],
            confidence=decision["confidence"],
            status=status,
            market_structure=self._market_structure_contract(structure, smc or smart_money),
            liquidity=self._liquidity_contract(structure, smc or smart_money),
            institutional_behavior=self._institutional_behavior(smc or smart_money, wyckoff, tape, volume),
            macro_context=macro,
            probabilities=decision["probabilities"],
            trade_plan=trade_plan,
            risk=risk,
            timing=timing,
            ai_explanation=narrative,
        )

    def _safe_layer(self, name: str, fn: Callable[[], dict[str, Any]]) -> dict[str, Any]:
        try:
            result = fn() or {}
            self.layers_used.append(name)
            return result
        except Exception as error:
            self.errors[name] = str(error)
            return {"error": str(error), "available": False}

    def _candles_by_timeframe(self, provided: dict[str, pd.DataFrame] | None) -> dict[str, pd.DataFrame]:
        candles = {key: _clean(value) for key, value in (provided or {}).items()}
        candles.setdefault(self.timeframe, self.df)
        for timeframe in ["1m", "5m", "15m", "1h"]:
            candles.setdefault(timeframe, self.df)
        return candles

    def _macro_context(self) -> dict[str, Any]:
        if MacroContextEngine is None:
            return {}
        return MacroContextEngine(self.candles_by_timeframe, self.asset).analyze()

    def _market_structure(self, macro: dict[str, Any]) -> dict[str, Any]:
        if MarketStructureEngine is None:
            return {}
        return MarketStructureEngine(self.df, macro).analyze()

    def _confirmation(self, macro: dict[str, Any], structure: dict[str, Any]) -> dict[str, Any]:
        if ConfirmationEngine is None:
            return {}
        return ConfirmationEngine(self.df, macro, structure).analyze()

    def _layered_signal(
        self,
        technical: dict[str, Any],
        volume: dict[str, Any],
        smc: dict[str, Any],
        wyckoff: dict[str, Any],
        tape: dict[str, Any],
    ) -> dict[str, Any]:
        if build_layered_signal is None:
            return {}
        return build_layered_signal(
            self.asset,
            self.candles_by_timeframe,
            entry_timeframe="1m" if self.timeframe not in {"1m", "2m"} else self.timeframe,
            legacy_filters={
                "role": "auxiliary_filter_only",
                "can_generate_signal": False,
                "technical": technical,
                "volume": volume,
                "smc": smc,
                "wyckoff": wyckoff,
                "tape_reading": tape,
            },
        )

    def _decision(
        self,
        *,
        layered: dict[str, Any],
        macro: dict[str, Any],
        structure: dict[str, Any],
        confirmation: dict[str, Any],
        smc: dict[str, Any],
        technical: dict[str, Any],
        volume: dict[str, Any],
        tape: dict[str, Any],
        wyckoff: dict[str, Any],
    ) -> dict[str, Any]:
        core_votes = [
            macro.get("direction"),
            structure.get("direction"),
            confirmation.get("direction") if confirmation.get("valid") else "NEUTRAL",
            ((layered.get("signal") or {}).get("direction_code") if (layered.get("signal") or {}).get("generated") else "NEUTRAL"),
        ]
        buy_core = core_votes.count("BUY")
        sell_core = core_votes.count("SELL")
        core_direction = "BUY" if buy_core >= 2 and buy_core > sell_core else "SELL" if sell_core >= 2 and sell_core > buy_core else "NEUTRAL"

        layered_score = _num((layered.get("ai_score") or {}).get("score"))
        macro_score = 18 if macro.get("direction") in {"BUY", "SELL"} and not macro.get("blocked") else 0
        structure_score = 24 if structure.get("valid") and structure.get("direction") in {"BUY", "SELL"} else 0
        confirmation_score = 18 if confirmation.get("valid") else 0
        layered_points = min(30, layered_score * 0.30) if (layered.get("signal") or {}).get("generated") else min(18, layered_score * 0.18)
        base_score = macro_score + structure_score + confirmation_score + layered_points
        aux = self._auxiliary_filter_effect(core_direction, technical, volume, tape, wyckoff, smc)
        score = _clamp(base_score + aux["adjustment"])

        if core_direction == "NEUTRAL":
            direction = "NEUTRAL"
        elif score >= 70 and (layered.get("signal") or {}).get("generated"):
            direction = core_direction
        else:
            direction = "NEUTRAL"

        aux_buy_weight = 2.0 if core_direction != "SELL" else 0.8
        aux_sell_weight = 2.0 if core_direction != "BUY" else 0.8
        buy = _clamp((buy_core / 4) * 72 + aux["buy"] * aux_buy_weight + (score * 0.18 if direction == "BUY" else 0))
        sell = _clamp((sell_core / 4) * 72 + aux["sell"] * aux_sell_weight + (score * 0.18 if direction == "SELL" else 0))
        sideways = _clamp(100 - max(buy, sell))
        confidence = _clamp(score + abs(buy - sell) * 0.14 - len(aux["blockers"]) * 4)

        return {
            "direction": direction if direction in VALID_DIRECTIONS else "NEUTRAL",
            "score": round(score, 2),
            "confidence": round(confidence, 2),
            "probabilities": {
                "buy": round(buy, 1),
                "sell": round(sell, 1),
                "sideways": round(sideways, 1),
            },
            "core_direction": core_direction,
            "core_votes": {"buy": buy_core, "sell": sell_core, "neutral": core_votes.count("NEUTRAL")},
            "auxiliary_filters": aux,
            "smc_direction": _direction_from_smc(smc),
        }

    def _auxiliary_filter_effect(
        self,
        core_direction: str,
        technical: dict[str, Any],
        volume: dict[str, Any],
        tape: dict[str, Any],
        wyckoff: dict[str, Any],
        smc: dict[str, Any],
    ) -> dict[str, Any]:
        confirmations: list[str] = []
        blockers: list[str] = []
        adjustment = 0
        buy = 0
        sell = 0

        technical_signal = technical.get("signal")
        if technical_signal in {"BUY", "SELL"}:
            if technical_signal == core_direction:
                confirmations.append("Indicador tecnico confirmou a direcao principal.")
                adjustment += 3
            elif core_direction in {"BUY", "SELL"}:
                blockers.append("Indicador tecnico contra a direcao institucional.")
                adjustment -= 6
            buy += 4 if technical_signal == "BUY" else 0
            sell += 4 if technical_signal == "SELL" else 0

        dominant_side = str(volume.get("dominant_side") or "").upper()
        volume_direction = "BUY" if volume.get("signal") in {"BULLISH_VOLUME", "BUY_FLOW"} or dominant_side in {"BUYER", "COMPRADOR"} else "SELL" if volume.get("signal") in {"BEARISH_VOLUME", "SELL_FLOW"} or dominant_side in {"SELLER", "VENDEDOR"} else "NEUTRAL"
        if volume_direction == core_direction:
            confirmations.append("Volume confirmou a direcao principal.")
            adjustment += 3
        elif volume_direction in {"BUY", "SELL"} and core_direction in {"BUY", "SELL"}:
            blockers.append("Volume contra a direcao institucional.")
            adjustment -= 7
        buy += 5 if volume_direction == "BUY" else 0
        sell += 5 if volume_direction == "SELL" else 0

        pressure = str(tape.get("pressure") or "").upper()
        flow_direction = "BUY" if tape.get("order_flow_bias") == "BUY_FLOW" or pressure in {"BUYER", "COMPRADORA", "COMPRADOR"} else "SELL" if tape.get("order_flow_bias") == "SELL_FLOW" or pressure in {"SELLER", "VENDEDORA", "VENDEDOR"} else "NEUTRAL"
        if flow_direction == core_direction:
            confirmations.append("Tape/fluxo confirmou a direcao principal.")
            adjustment += 3
        elif flow_direction in {"BUY", "SELL"} and core_direction in {"BUY", "SELL"}:
            blockers.append("Tape/fluxo contra a direcao institucional.")
            adjustment -= 6
        buy += 5 if flow_direction == "BUY" else 0
        sell += 5 if flow_direction == "SELL" else 0

        wyckoff_direction = "BUY" if wyckoff.get("spring") or wyckoff.get("phase") == "acumulacao" or wyckoff.get("wyckoff_phase") == "acumulacao" else "SELL" if wyckoff.get("upthrust") or wyckoff.get("phase") == "distribuicao" or wyckoff.get("wyckoff_phase") == "distribuicao" else "NEUTRAL"
        if wyckoff_direction == core_direction:
            confirmations.append("Wyckoff favorece a direcao principal.")
            adjustment += 2
        elif wyckoff_direction in {"BUY", "SELL"} and core_direction in {"BUY", "SELL"}:
            blockers.append("Wyckoff contra a direcao institucional.")
            adjustment -= 4
        buy += 4 if wyckoff_direction == "BUY" else 0
        sell += 4 if wyckoff_direction == "SELL" else 0

        if smc.get("invalidated") or (smc.get("false_breakout") or {}).get("detected"):
            blockers.append("Smart Money marcou invalidacao ou falso rompimento.")
            adjustment -= 15

        if core_direction == "NEUTRAL":
            adjustment = min(adjustment, 0)

        return {
            "role": "auxiliary_filter_only",
            "can_generate_signal": False,
            "adjustment": max(-30, min(10, adjustment)),
            "buy": buy,
            "sell": sell,
            "confirmations": list(dict.fromkeys(confirmations)),
            "blockers": list(dict.fromkeys(blockers)),
        }

    def _trade_plan(self, direction: str, layered: dict[str, Any], structure: dict[str, Any]) -> dict[str, Any]:
        signal = layered.get("signal") or {}
        if direction not in {"BUY", "SELL"} or not signal.get("generated"):
            return self._empty_trade_plan("Aguardar confirmacao das camadas.", signal.get("reason") or "Sem confluencia suficiente.")
        entry = signal.get("entry_price")
        stop = signal.get("stop_loss")
        tp1 = signal.get("take_profit_1")
        tp2 = signal.get("take_profit_2")
        return {
            "entry": entry,
            "stopLoss": stop,
            "takeProfit1": tp1,
            "takeProfit2": tp2,
            "takeProfitFinal": tp2,
            "riskReward": signal.get("risk_reward"),
            "entryCondition": signal.get("reason") or "Entrada somente apos confirmacao institucional.",
            "cancelCondition": self._first_reason(structure.get("blockers"), signal.get("risk_gate", {}).get("blockers")) or "Cancelar se perder estrutura, liquidez ou score minimo.",
        }

    def _empty_trade_plan(self, entry_condition: str, cancel_condition: str) -> dict[str, Any]:
        return {
            "entry": None,
            "stopLoss": None,
            "takeProfit1": None,
            "takeProfit2": None,
            "takeProfitFinal": None,
            "riskReward": None,
            "entryCondition": entry_condition,
            "cancelCondition": cancel_condition,
        }

    def _risk(self, decision: dict[str, Any], trade_plan: dict[str, Any]) -> dict[str, Any]:
        if RiskGuard is None:
            return {"allowed": False, "rejections": ["RiskGuard indisponivel."], "reason": "RiskGuard indisponivel."}
        signal = {
            "symbol": self.asset,
            "side": "buy" if decision["direction"] == "BUY" else "sell" if decision["direction"] == "SELL" else "neutral",
            "entry": trade_plan.get("entry"),
            "stop_loss": trade_plan.get("stopLoss"),
            "take_profit": trade_plan.get("takeProfit1"),
            "risk_reward": trade_plan.get("riskReward") or 0,
            "score": decision["score"],
            "quantity": 1,
        }
        risk = RiskGuard({"min_ai_score": 70, "min_rr": 1.2}).validate(signal, self.risk_status)
        risk["educationalOnly"] = True
        return risk

    def _status(
        self,
        decision: dict[str, Any],
        risk: dict[str, Any],
        macro: dict[str, Any],
        structure: dict[str, Any],
        confirmation: dict[str, Any],
        smc: dict[str, Any],
    ) -> str:
        smc_false_breakout = (smc.get("false_breakout") or {}).get("detected")
        confirmation_false_breakout = (confirmation.get("false_breakout") or {}).get("detected")
        dangerous = bool(smc_false_breakout or confirmation_false_breakout)
        if dangerous:
            return "DANGEROUS_MARKET"
        if decision["score"] < 45 or (macro.get("blocked") and not structure.get("valid")):
            return "NO_TRADE"
        if decision["direction"] in {"BUY", "SELL"} and decision["score"] >= 70 and decision["confidence"] >= 68 and risk.get("allowed"):
            return "HIGH_PROBABILITY"
        return "WAIT_CONFIRMATION"

    def _timing(self, confirmation: dict[str, Any], layered: dict[str, Any], status: str) -> dict[str, Any]:
        signal = layered.get("signal") or {}
        return {
            "confirmed": status == "HIGH_PROBABILITY",
            "layer": "confirmation",
            "validatedLayer": signal.get("validated_layer"),
            "confirmation": confirmation,
            "reason": signal.get("reason") or self._first_reason(confirmation.get("blockers")) or "Aguardando timing institucional.",
        }

    def _market_structure_contract(self, structure: dict[str, Any], smc: dict[str, Any]) -> dict[str, Any]:
        return {
            "direction": structure.get("direction", "NEUTRAL"),
            "valid": bool(structure.get("valid")),
            "bos": structure.get("bos") or (smc.get("structure") or {}).get("bos"),
            "choch": structure.get("choch") or (smc.get("structure") or {}).get("choch"),
            "swings": structure.get("swings", {}),
            "orderBlock": structure.get("order_block") or smc.get("relevant_order_block") or smc.get("nearest_order_block"),
            "fvg": structure.get("fvg") or smc.get("relevant_fvg"),
            "blockers": structure.get("blockers", []),
        }

    def _liquidity_contract(self, structure: dict[str, Any], smc: dict[str, Any]) -> dict[str, Any]:
        return {
            "zones": (structure.get("liquidity") or {}).get("zones") or smc.get("liquidity", []),
            "nearest": (structure.get("liquidity") or {}).get("nearest") or smc.get("liquidity_zone"),
            "sweep": structure.get("liquidity_sweep") or smc.get("liquidity_sweep", {}),
            "internal": smc.get("internal_liquidity") or smc.get("liquidity_zone"),
            "external": smc.get("external_liquidity") or smc.get("liquidity_zone"),
        }

    def _institutional_behavior(self, smc: dict[str, Any], wyckoff: dict[str, Any], tape: dict[str, Any], volume: dict[str, Any]) -> dict[str, Any]:
        return {
            "smartMoneyBias": smc.get("institutional_bias", "neutral"),
            "wyckoff": wyckoff,
            "flow": tape,
            "volume": volume,
            "falseBreakout": smc.get("false_breakout", {"detected": False}),
            "inducement": smc.get("inducement", {"detected": False}),
        }

    def _explanation(
        self,
        decision: dict[str, Any],
        status: str,
        macro: dict[str, Any],
        structure: dict[str, Any],
        confirmation: dict[str, Any],
        smc: dict[str, Any],
        risk: dict[str, Any],
    ) -> str:
        if status == "HIGH_PROBABILITY":
            return (
                f"IA institucional encontrou confluencia {decision['direction']} com score {decision['score']:.0f}. "
                "Ainda assim, nao ha promessa de acerto; o plano depende de stop, alvo e confirmacao do mercado."
            )
        reason = self._first_reason(
            risk.get("rejections"),
            macro.get("blockers"),
            structure.get("blockers"),
            confirmation.get("blockers"),
            decision.get("auxiliary_filters", {}).get("blockers"),
        )
        if status == "DANGEROUS_MARKET":
            return f"IA institucional evita operar por risco elevado: {reason or 'invalidacao ou falso rompimento detectado'}. Nao ha promessa de acerto."
        if status == "NO_TRADE":
            return f"IA institucional nao encontrou confluencia suficiente. {reason or 'Estrutura e timing ainda nao validaram.'}"
        smc_direction = _direction_from_smc(smc)
        return f"IA institucional aguarda confirmacao. Direcao preliminar SMC: {smc_direction}; motivo: {reason or 'camadas incompletas'}."

    def _narrative(self, decision: dict[str, Any], smc: dict[str, Any], tape: dict[str, Any], risk: dict[str, Any], fallback: str) -> str:
        if build_operational_narrative is None:
            return fallback
        signal_text = "COMPRA" if decision["direction"] == "BUY" else "VENDA" if decision["direction"] == "SELL" else "AGUARDAR"
        narrative = build_operational_narrative(
            {"signal": signal_text, "reason": fallback},
            smc,
            tape,
            {"narrative": "Multi-timeframe institucional em leitura."},
            {"invalidation": self._first_reason(risk.get("rejections"))},
        )
        return narrative.get("summary") or fallback

    def _payload(
        self,
        *,
        direction: str,
        score: float,
        confidence: float,
        status: str,
        market_structure: dict[str, Any],
        liquidity: dict[str, Any],
        institutional_behavior: dict[str, Any],
        macro_context: dict[str, Any],
        probabilities: dict[str, float],
        trade_plan: dict[str, Any],
        risk: dict[str, Any],
        timing: dict[str, Any],
        ai_explanation: str,
    ) -> dict[str, Any]:
        return {
            "asset": self.asset,
            "assetType": self.asset_type,
            "timeframe": self.timeframe,
            "direction": direction if direction in VALID_DIRECTIONS else "NEUTRAL",
            "confidence": round(_clamp(confidence), 2),
            "score": round(_clamp(score), 2),
            "status": status if status in VALID_STATUSES else "WAIT_CONFIRMATION",
            "marketStructure": market_structure,
            "liquidity": liquidity,
            "institutionalBehavior": institutional_behavior,
            "macroContext": macro_context,
            "probabilities": {
                "buy": round(_clamp(_num(probabilities.get("buy"))), 2),
                "sell": round(_clamp(_num(probabilities.get("sell"))), 2),
                "sideways": round(_clamp(_num(probabilities.get("sideways"))), 2),
            },
            "tradePlan": trade_plan,
            "risk": risk,
            "timing": timing,
            "news": self.news,
            "aiExplanation": ai_explanation,
            "layersUsed": list(dict.fromkeys(self.layers_used)),
            "createdAt": _now(),
            "diagnostics": {"errors": self.errors} if self.errors else {},
        }

    def _first_reason(self, *groups: Any) -> str:
        for group in groups:
            if isinstance(group, str) and group:
                return group
            if isinstance(group, list):
                for item in group:
                    if item:
                        return str(item)
        return ""


def build_institutional_unified_analysis(
    candles: pd.DataFrame,
    asset: str,
    timeframe: str,
    asset_type: str = "",
    candles_by_timeframe: dict[str, pd.DataFrame] | None = None,
    news: dict[str, Any] | None = None,
    risk_status: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return InstitutionalUnifiedEngine(
        candles=candles,
        asset=asset,
        timeframe=timeframe,
        asset_type=asset_type,
        candles_by_timeframe=candles_by_timeframe,
        news=news,
        risk_status=risk_status,
    ).analyze()
