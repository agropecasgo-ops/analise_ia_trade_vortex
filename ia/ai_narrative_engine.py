"""
Feed narrativo da IA para a Live Trading.
"""

from __future__ import annotations

from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Any


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class AINarrativeEngine:
    def __init__(self, max_items: int = 80) -> None:
        self.max_items = max_items
        self._feeds: dict[str, deque[dict[str, Any]]] = defaultdict(lambda: deque(maxlen=max_items))
        self._seen: dict[str, set[str]] = defaultdict(set)

    def update(self, symbol: str, timeframe: str, context: dict[str, Any], status: dict[str, Any]) -> list[dict[str, Any]]:
        key = f"{symbol}:{timeframe}"
        feed = self._feeds[key]
        if not feed:
            self._append(key, "SYSTEM", f"Mesa IA conectada em {symbol} {timeframe}", "info")

        for event in context.get("events", [])[-8:]:
            self._append(key, event.get("kind", "EVENT"), event.get("text", ""), event.get("severity", "info"), event.get("level"))

        for message in (status.get("messages") or [])[:4]:
            self._append(key, "IA", message, self._severity_from_status(status))

        if context.get("invalidation"):
            self._append(key, "INVALIDACAO", f"Cenario invalidado se perder {context['invalidation']}", "warning", context.get("invalidation"))

        return list(feed)[-30:]

    def _append(self, key: str, kind: str, text: str, severity: str = "info", level: float | None = None) -> None:
        text = str(text or "").strip()
        if not text:
            return
        signature = f"{kind}:{text}:{round(float(level or 0), 4)}"
        if signature in self._seen[key]:
            return
        self._seen[key].add(signature)
        if len(self._seen[key]) > self.max_items * 2:
            self._seen[key] = set(list(self._seen[key])[-self.max_items:])
        self._feeds[key].append({
            "timestamp": _now_iso(),
            "kind": kind,
            "text": text,
            "severity": severity,
            "level": level,
        })

    def _severity_from_status(self, status: dict[str, Any]) -> str:
        state = status.get("state")
        if state in ["BUY_CONFIRMED", "SELL_CONFIRMED", "AGGRESSIVE_ENTRY", "CONSERVATIVE_ENTRY"]:
            return "positive"
        if state in ["INVALIDATED", "HIGH_RISK"]:
            return "negative"
        if state in ["WAITING_CONFIRMATION", "WAIT_NEXT_CANDLE", "WEAK_VOLUME"]:
            return "warning"
        return "info"
