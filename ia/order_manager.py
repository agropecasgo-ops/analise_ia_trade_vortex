"""
Gerenciador de ordens paper trading.
"""

from datetime import datetime, timezone
from uuid import uuid4


class OrderManager:
    def __init__(self):
        self.orders = []

    def paper_order(self, signal, risk_result):
        order = {
            "id": f"PAPER-{uuid4().hex[:10].upper()}",
            "mode": "paper",
            "symbol": signal.get("symbol"),
            "side": signal.get("side"),
            "entry": signal.get("entry"),
            "stop_loss": signal.get("stop_loss"),
            "take_profit": signal.get("take_profit"),
            "quantity": signal.get("quantity", 1),
            "score": signal.get("score"),
            "risk_guard": risk_result,
            "status": "simulated",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "reason": signal.get("reason"),
        }
        self.orders.append(order)
        return order

    def history(self, limit=50):
        return self.orders[-limit:]

    def trades_today(self):
        today = datetime.now(timezone.utc).date().isoformat()
        return len([order for order in self.orders if str(order.get("created_at", "")).startswith(today)])

    def last_order(self):
        return self.orders[-1] if self.orders else None
