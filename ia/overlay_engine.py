"""
Overlays leves para o grafico da Live Trading.
"""

from __future__ import annotations

from typing import Any


class OverlayEngine:
    def build(self, context: dict[str, Any], status: dict[str, Any]) -> dict[str, Any]:
        smc = context.get("smc", {})
        return {
            "markers": self._markers(context, status),
            "zones": self._zones(context, smc),
            "levels": self._levels(context, status),
        }

    def _markers(self, context: dict[str, Any], status: dict[str, Any]) -> list[dict[str, Any]]:
        markers = []
        for event in (context.get("events") or [])[-12:]:
            kind = event.get("kind")
            if kind in ["BOS", "CHOCH", "SWEEP", "TRAP", "FVG", "TIMING"]:
                markers.append({
                    "time": event.get("time") or context.get("last_candle_time"),
                    "position": "belowBar" if event.get("severity") == "positive" else "aboveBar",
                    "shape": "arrowUp" if event.get("severity") == "positive" else "arrowDown" if event.get("severity") == "negative" else "circle",
                    "color": self._color(event.get("severity")),
                    "text": self._compact(event.get("text")),
                    "kind": kind,
                })
        current_time = context.get("last_candle_time")
        state = status.get("state")
        if state in ["BUY_CONFIRMED", "SELL_CONFIRMED", "AGGRESSIVE_ENTRY", "CONSERVATIVE_ENTRY", "INVALIDATED"]:
            markers.append({
                "time": current_time,
                "position": "belowBar" if status.get("probable_direction") == "BUY" else "aboveBar",
                "shape": "arrowUp" if status.get("probable_direction") == "BUY" else "arrowDown" if status.get("probable_direction") == "SELL" else "circle",
                "color": "#22c55e" if status.get("probable_direction") == "BUY" else "#ef4444",
                "text": self._compact(status.get("status")),
                "kind": "SIGNAL",
            })
        return markers[-18:]

    def _zones(self, context: dict[str, Any], smc: dict[str, Any]) -> list[dict[str, Any]]:
        zones = []
        for zone in context.get("active_fvgs", [])[:4]:
            zones.append(self._zone(zone, "FVG", 0.38 if zone.get("active") else 0.22))
        for zone in context.get("order_blocks", [])[-4:]:
            zones.append(self._zone(zone, "OB", 0.18))
        for zone in context.get("liquidity_zones", [])[:4]:
            zones.append(self._zone(zone, "LIQ", 0.16))
        sweep_zone = (context.get("liquidity_sweep") or {}).get("zone")
        if sweep_zone:
            zones.append(self._zone(sweep_zone, "SWEEP", 0.44))
        return [zone for zone in zones if zone][-12:]

    def _zone(self, zone: dict[str, Any], label: str, opacity: float) -> dict[str, Any] | None:
        low = zone.get("low", zone.get("price"))
        high = zone.get("high", zone.get("price"))
        if low is None or high is None:
            return None
        side = zone.get("type", zone.get("side", "neutral"))
        return {
            "label": label,
            "type": side,
            "low": low,
            "high": high,
            "mid": zone.get("mid", zone.get("price", (float(low) + float(high)) / 2)),
            "time": zone.get("time"),
            "opacity": opacity,
            "active": bool(zone.get("active")),
            "color": self._zone_color(side, label),
        }

    def _levels(self, context: dict[str, Any], status: dict[str, Any]) -> list[dict[str, Any]]:
        items = [
            ("ENTRY", status.get("entry_aggressive"), "#38bdf8"),
            ("ENTRY+", status.get("entry_conservative"), "#f59e0b"),
            ("STOP", status.get("stop_loss"), "#ef4444"),
            ("TAKE", status.get("take_profit"), "#22c55e"),
            ("INVALID", context.get("invalidation"), "#f97316"),
        ]
        return [
            {"label": label, "price": price, "color": color}
            for label, price, color in items
            if price is not None
        ]

    def _color(self, severity: str | None) -> str:
        return {
            "positive": "#22c55e",
            "negative": "#ef4444",
            "warning": "#f59e0b",
            "info": "#38bdf8",
        }.get(severity or "info", "#38bdf8")

    def _zone_color(self, side: str, label: str) -> str:
        text = f"{side}:{label}".lower()
        if "bear" in text or "buy_side" in text:
            return "#ef4444"
        if "bull" in text or "sell_side" in text:
            return "#22c55e"
        if "sweep" in text:
            return "#a78bfa"
        return "#38bdf8"

    def _compact(self, text: Any, limit: int = 28) -> str:
        value = str(text or "").strip()
        return value if len(value) <= limit else f"{value[:limit - 1]}..."
