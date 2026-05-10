"""
Gerenciamento de Sinais IA em Tempo Real.
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4


DISCLAIMER = "Analise educativa. Nao constitui recomendacao financeira. Toda operacao envolve risco."


class LiveSignalManager:
    def __init__(self, min_score=78, min_rr=1.5, min_confidence=70):
        self.min_score = min_score
        self.min_rr = min_rr
        self.min_confidence = min_confidence
        self.active = {}
        self.history = []

    def update_from_live_status(self, live_status, market_meta=None, mtf_confluence=None):
        market_meta = market_meta or {}
        mtf_confluence = mtf_confluence or {}
        key = self._key(live_status)
        current_price = float(live_status.get("current_price") or 0)

        signal = self.active.get(key)
        if signal:
            self._update_existing(signal, live_status, current_price)
            if signal["status"] in ["invalidated", "stopped", "tp3_hit", "closed"]:
                self._archive_signal(signal)
            return signal

        if not self._should_create(live_status, mtf_confluence):
            return self._waiting_payload(live_status, market_meta)

        signal = self._create_signal(live_status, market_meta, mtf_confluence)
        self.active[key] = signal
        return signal

    def list_active(self):
        return sorted(self.active.values(), key=lambda item: item["timestamp"], reverse=True)

    def list_history(self, limit=100):
        return self.history[-limit:][::-1]

    def stats(self):
        return {
            "active_count": len(self.active),
            "history_count": len(self.history),
            "open_buy": sum(1 for item in self.active.values() if item["direction"] == "BUY"),
            "open_sell": sum(1 for item in self.active.values() if item["direction"] == "SELL"),
        }

    def _should_create(self, status, mtf):
        direction = status.get("probable_direction")
        score = float(status.get("confluence_score") or 0)
        confidence = float(status.get("confidence") or 0)
        rr = float(status.get("risk_reward") or 0)
        state = status.get("state")
        volume_signal = status.get("volume", {}).get("signal")
        smc_score = float(status.get("smc", {}).get("score") or 0)
        trend = status.get("technical", {}).get("trend", {}).get("direction", "")
        mtf_ok = mtf.get("strong_signal_allowed", True)

        volume_aligned = (
            (direction == "BUY" and volume_signal == "BULLISH_VOLUME")
            or (direction == "SELL" and volume_signal == "BEARISH_VOLUME")
        )

        return (
            direction in ["BUY", "SELL"]
            and state in ["BUY_CONFIRMED", "SELL_CONFIRMED", "AGGRESSIVE_ENTRY"]
            and score >= self.min_score
            and confidence >= self.min_confidence
            and rr >= self.min_rr
            and volume_aligned
            and smc_score >= 60
            and trend in ["STRONG_BULLISH", "STRONG_BEARISH", "BULLISH", "BEARISH"]
            and mtf_ok
            and not status.get("smc", {}).get("false_breakout", {}).get("detected")
        )

    def _create_signal(self, status, market_meta, mtf):
        now = datetime.now(timezone.utc)
        direction = status.get("probable_direction", "WAIT")
        entry = status.get("entry_aggressive") or status.get("current_price")
        signal = {
            "id": uuid4().hex[:12],
            "asset": status.get("symbol"),
            "symbol": status.get("symbol"),
            "market": market_meta.get("market") or status.get("market"),
            "market_label": market_meta.get("market_label") or status.get("market_label"),
            "timeframe": status.get("timeframe"),
            "direction": direction,
            "entry": entry,
            "entry_aggressive": status.get("entry_aggressive") or entry,
            "entry_conservative": status.get("entry_conservative"),
            "stop_loss": status.get("stop_loss"),
            "take_profit_1": status.get("take_profit"),
            "take_profit_2": status.get("take_profit_2"),
            "take_profit_3": status.get("take_profit_3"),
            "risk_reward": status.get("risk_reward"),
            "confluence_score": status.get("confluence_score"),
            "confidence": status.get("confidence"),
            "status": "active",
            "timestamp": now.isoformat(),
            "expires_at": (now + timedelta(hours=6)).isoformat(),
            "technical_reason": status.get("reason"),
            "confirmations": status.get("confirmations", []),
            "invalidations": status.get("invalidations", []),
            "explanation": self._explanation(status),
            "partial_result": "0.00%",
            "last_price": status.get("current_price"),
            "mtf_aligned": bool(mtf.get("strong_signal_allowed", True)),
            "alerts": ["signal_created", direction.lower()],
            "disclaimer": DISCLAIMER,
        }
        return signal

    def _update_existing(self, signal, status, current_price):
        signal["last_price"] = current_price
        signal["confluence_score"] = status.get("confluence_score", signal["confluence_score"])
        signal["confidence"] = status.get("confidence", signal["confidence"])
        signal["confirmations"] = status.get("confirmations", signal.get("confirmations", []))
        signal["invalidations"] = status.get("invalidations", signal.get("invalidations", []))
        signal["technical_reason"] = status.get("reason", signal.get("technical_reason"))
        signal["partial_result"] = self._partial_result(signal, current_price)
        signal["alerts"] = []

        if status.get("state") in ["INVALIDATED", "HIGH_RISK"] or status.get("smc", {}).get("false_breakout", {}).get("detected"):
            signal["status"] = "invalidated"
            signal["alerts"].append("signal_invalidated")
            return

        direction = signal["direction"]
        stop = float(signal.get("stop_loss") or 0)
        tp1 = float(signal.get("take_profit_1") or 0)
        tp2 = float(signal.get("take_profit_2") or 0)
        tp3 = float(signal.get("take_profit_3") or 0)

        if direction == "BUY":
            if stop and current_price <= stop:
                signal["status"] = "stopped"
            elif tp3 and current_price >= tp3:
                signal["status"] = "tp3_hit"
            elif tp2 and current_price >= tp2:
                signal["status"] = "tp2_hit"
            elif tp1 and current_price >= tp1:
                signal["status"] = "tp1_hit"
            else:
                signal["status"] = "confirmed" if status.get("state") == "BUY_CONFIRMED" else "active"
        elif direction == "SELL":
            if stop and current_price >= stop:
                signal["status"] = "stopped"
            elif tp3 and current_price <= tp3:
                signal["status"] = "tp3_hit"
            elif tp2 and current_price <= tp2:
                signal["status"] = "tp2_hit"
            elif tp1 and current_price <= tp1:
                signal["status"] = "tp1_hit"
            else:
                signal["status"] = "confirmed" if status.get("state") == "SELL_CONFIRMED" else "active"

        if signal["status"] in ["tp1_hit", "tp2_hit", "tp3_hit", "stopped"]:
            signal["alerts"].append(signal["status"])

    def _waiting_payload(self, status, market_meta):
        return {
            "id": None,
            "asset": status.get("symbol"),
            "symbol": status.get("symbol"),
            "market": market_meta.get("market") or status.get("market"),
            "timeframe": status.get("timeframe"),
            "direction": "WAIT" if status.get("probable_direction") == "NEUTRAL" else status.get("probable_direction", "WAIT"),
            "status": "waiting_confirmation",
            "confluence_score": status.get("confluence_score", 0),
            "confidence": status.get("confidence", 0),
            "technical_reason": status.get("reason", "Aguardando confluencia forte."),
            "confirmations": status.get("confirmations", []),
            "invalidations": status.get("invalidations", []),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "disclaimer": DISCLAIMER,
        }

    def _partial_result(self, signal, price):
        entry = float(signal.get("entry") or 0)
        if not entry:
            return "0.00%"
        if signal["direction"] == "SELL":
            value = (entry - price) / entry * 100
        else:
            value = (price - entry) / entry * 100
        return f"{value:.2f}%"

    def _archive_signal(self, signal):
        if signal.get("archived"):
            return
        signal["closed_at"] = datetime.now(timezone.utc).isoformat()
        signal["archived"] = True
        self.history.append(signal.copy())

    def _key(self, status):
        return f"{status.get('symbol')}:{status.get('timeframe')}"

    def _explanation(self, status):
        confirmations = status.get("confirmations", [])[:4]
        if confirmations:
            return " + ".join(confirmations)
        return status.get("reason") or "Confluencia operacional forte detectada pela IA."
