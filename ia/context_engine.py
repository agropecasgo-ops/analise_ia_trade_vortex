"""
Context engine persistente para a Live Trading.

Mantem uma leitura estrutural por ativo/timeframe e atualiza o estado somente
quando chega um novo candle, preservando eventos importantes para a narrativa.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import pandas as pd

from .smart_money import analyze_smart_money


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number else None


def _zone_signature(zone: dict[str, Any] | None) -> str:
    if not zone:
        return "none"
    level = zone.get("price", zone.get("mid", zone.get("high", zone.get("low"))))
    return f"{zone.get('kind', zone.get('type'))}:{round(float(level or 0), 4)}"


@dataclass
class MarketContextState:
    last_candle_time: int | None = None
    trend: str = "neutral"
    macro_trend: str = "neutral"
    intraday_trend: str = "neutral"
    market_structure: str = "Sem estrutura dominante"
    operational_bias: str = "NEUTRAL"
    last_bos: dict[str, Any] | None = None
    last_choch: dict[str, Any] | None = None
    active_fvgs: list[dict[str, Any]] = field(default_factory=list)
    liquidity_zones: list[dict[str, Any]] = field(default_factory=list)
    order_blocks: list[dict[str, Any]] = field(default_factory=list)
    liquidity_sweep: dict[str, Any] = field(default_factory=dict)
    wyckoff_context: dict[str, Any] = field(default_factory=dict)
    pressure: str = "BALANCED"
    invalidation: float | None = None
    narrative: str = "IA aguardando contexto estrutural."
    events: deque[dict[str, Any]] = field(default_factory=lambda: deque(maxlen=80))
    snapshot: dict[str, Any] = field(default_factory=dict)


class ContextEngine:
    def __init__(self) -> None:
        self._states: dict[str, MarketContextState] = {}

    def update(self, candles: pd.DataFrame, symbol: str, timeframe: str, live_status: dict[str, Any]) -> dict[str, Any]:
        key = f"{symbol}:{timeframe}"
        state = self._states.setdefault(key, MarketContextState())
        df = candles.copy().dropna(subset=["open", "high", "low", "close", "volume"])
        if df.empty:
            return state.snapshot

        last_time = int(pd.Timestamp(df.index[-1]).timestamp())
        if state.last_candle_time == last_time and state.snapshot:
            return state.snapshot

        technical_signal = (live_status.get("technical") or {}).get("signal") or live_status.get("probable_direction", "NEUTRAL")
        smc = live_status.get("smc_context") or analyze_smart_money(df.tail(260), technical_signal)
        last = df.iloc[-1]
        previous_snapshot = dict(state.snapshot)

        structure = smc.get("structure", {})
        state.last_candle_time = last_time
        state.trend = structure.get("trend", "neutral")
        mtf_context = live_status.get("institutional_mtf") or live_status.get("multi_timeframe") or {}
        layers = mtf_context.get("layers", {}) if isinstance(mtf_context, dict) else {}
        state.macro_trend = (layers.get("macro_direction") or {}).get("direction", state.trend)
        state.intraday_trend = (layers.get("main_structure") or {}).get("direction", state.trend)
        state.market_structure = self._structure_label(structure)
        state.operational_bias = self._bias(live_status, smc)
        state.active_fvgs = self._active_zones(smc.get("fair_value_gaps", []), last["close"])[:6]
        state.liquidity_zones = smc.get("liquidity", [])[:8]
        state.order_blocks = smc.get("order_blocks", [])[-8:]
        state.liquidity_sweep = smc.get("liquidity_sweep", {"detected": False, "side": "none", "zone": None})
        state.wyckoff_context = live_status.get("wyckoff") or {}
        state.pressure = self._pressure(live_status)
        state.invalidation = self._invalidation(live_status, smc)

        if structure.get("bos") != "none":
            state.last_bos = {
                "side": structure.get("bos"),
                "level": structure.get("break_level"),
                "time": last_time,
            }
        if structure.get("choch") != "none":
            state.last_choch = {
                "side": structure.get("choch"),
                "level": structure.get("break_level"),
                "time": last_time,
            }

        new_events = self._detect_events(previous_snapshot, state, live_status, smc, last_time)
        state.events.extend(new_events)
        state.narrative = self._narrative(state, live_status)
        state.snapshot = {
            "symbol": symbol,
            "timeframe": timeframe,
            "updated_at": _utc_now(),
            "last_candle_time": last_time,
            "trend": state.trend,
            "macro_trend": state.macro_trend,
            "intraday_trend": state.intraday_trend,
            "market_structure": state.market_structure,
            "operational_bias": state.operational_bias,
            "last_bos": state.last_bos,
            "last_choch": state.last_choch,
            "active_fvgs": state.active_fvgs,
            "liquidity_zones": state.liquidity_zones,
            "order_blocks": state.order_blocks,
            "liquidity_sweep": state.liquidity_sweep,
            "wyckoff_context": state.wyckoff_context,
            "pressure": state.pressure,
            "invalidation": state.invalidation,
            "narrative": state.narrative,
            "events": list(state.events)[-30:],
            "smc": smc,
        }
        return state.snapshot

    def _active_zones(self, zones: list[dict[str, Any]], price: float) -> list[dict[str, Any]]:
        price = float(price)
        active = []
        for zone in zones[-12:]:
            low = _safe_float(zone.get("low"))
            high = _safe_float(zone.get("high"))
            if low is None or high is None:
                continue
            if low <= price <= high or abs(((low + high) / 2) - price) / max(price, 0.00000001) <= 0.012:
                active.append({**zone, "active": low <= price <= high})
        return sorted(active, key=lambda item: abs(float(item.get("mid", price)) - price))

    def _bias(self, live_status: dict[str, Any], smc: dict[str, Any]) -> str:
        direction = live_status.get("probable_direction")
        if direction in ["BUY", "SELL"]:
            return direction
        bias = smc.get("institutional_bias")
        if bias == "bullish":
            return "BUY"
        if bias == "bearish":
            return "SELL"
        return "NEUTRAL"

    def _pressure(self, live_status: dict[str, Any]) -> str:
        volume = live_status.get("volume") or {}
        tape = live_status.get("tape_reading") or {}
        if tape.get("order_flow_bias") == "BUY_FLOW" or volume.get("dominant_side") == "BUYER":
            return "BUYER"
        if tape.get("order_flow_bias") == "SELL_FLOW" or volume.get("dominant_side") == "SELLER":
            return "SELLER"
        return "BALANCED"

    def _invalidation(self, live_status: dict[str, Any], smc: dict[str, Any]) -> float | None:
        stop = _safe_float(live_status.get("stop_loss"))
        if stop:
            return stop
        sweep_zone = (smc.get("liquidity_sweep") or {}).get("zone") or {}
        return _safe_float(sweep_zone.get("price"))

    def _structure_label(self, structure: dict[str, Any]) -> str:
        trend = structure.get("trend", "neutral")
        bos = structure.get("bos", "none")
        choch = structure.get("choch", "none")
        if choch != "none":
            return f"CHOCH {choch}"
        if bos != "none":
            return f"BOS {bos}"
        if trend == "bullish":
            return "Alta estrutural"
        if trend == "bearish":
            return "Baixa estrutural"
        return "Compressao / lateral"

    def _detect_events(self, previous: dict[str, Any], state: MarketContextState, live_status: dict[str, Any], smc: dict[str, Any], event_time: int) -> list[dict[str, Any]]:
        events = []

        def add(kind: str, text: str, severity: str = "info", level: float | None = None) -> None:
            events.append({"time": event_time, "kind": kind, "text": text, "severity": severity, "level": level})

        if _zone_signature(previous.get("last_bos")) != _zone_signature(state.last_bos) and state.last_bos:
            add("BOS", f"BOS {state.last_bos['side']} confirmado", "positive" if state.last_bos["side"] == "bullish" else "negative", state.last_bos.get("level"))
        if _zone_signature(previous.get("last_choch")) != _zone_signature(state.last_choch) and state.last_choch:
            add("CHOCH", f"CHOCH {state.last_choch['side']} confirmado", "positive" if state.last_choch["side"] == "bullish" else "negative", state.last_choch.get("level"))

        sweep = smc.get("liquidity_sweep", {})
        previous_sweep = previous.get("liquidity_sweep", {})
        if sweep.get("detected") and _zone_signature(sweep.get("zone")) != _zone_signature(previous_sweep.get("zone")):
            add("SWEEP", f"Sweep de liquidez detectado em {sweep.get('side')}", "warning")

        if smc.get("false_breakout", {}).get("detected"):
            add("TRAP", "Falha de rompimento / armadilha detectada", "warning", smc.get("false_breakout", {}).get("level"))

        first_fvg = state.active_fvgs[0] if state.active_fvgs else None
        if first_fvg and _zone_signature(first_fvg) != _zone_signature((previous.get("active_fvgs") or [None])[0]):
            add("FVG", f"Preco reage em FVG {first_fvg.get('type')}", "info", first_fvg.get("mid"))

        if live_status.get("state") in ["BUY_CONFIRMED", "SELL_CONFIRMED", "AGGRESSIVE_ENTRY", "CONSERVATIVE_ENTRY"]:
            add("TIMING", live_status.get("status", "Timing operacional ativo"), "positive")
        if live_status.get("state") in ["INVALIDATED", "HIGH_RISK"]:
            add("RISK", live_status.get("status", "Cenario exige cautela"), "negative")
        return events

    def _narrative(self, state: MarketContextState, live_status: dict[str, Any]) -> str:
        bias = {"BUY": "comprador", "SELL": "vendedor"}.get(state.operational_bias, "neutro")
        pressure = {"BUYER": "pressao compradora", "SELLER": "pressao vendedora"}.get(state.pressure, "fluxo equilibrado")
        return f"Vies {bias}, {state.market_structure.lower()}, {pressure}. {live_status.get('message', 'Aguardando candle de confirmacao')}"
