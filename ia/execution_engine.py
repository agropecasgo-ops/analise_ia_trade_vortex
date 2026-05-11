"""
Execution Engine seguro.

Paper trading e o padrao. Execucao real exige variaveis de ambiente explicitas
e continua passando pelo Risk Guard.
"""

import os

from .broker_adapter import OrderRequest
from .bybit_execution_adapter import BybitExecutionAdapter
from .mt5_execution_adapter import MT5ExecutionAdapter
from .order_manager import OrderManager
from .risk_guard import RiskGuard


class ExecutionEngine:
    MODES = {"alert", "semi_auto", "auto"}

    def __init__(self, risk_config=None):
        self.order_manager = OrderManager()
        self.risk_guard = RiskGuard(risk_config)
        self.enabled = False
        self.mode = "alert"
        self.kill_switch = True
        self.daily_loss_pct = 0
        self.last_rejection = ""
        self.real_enabled = os.getenv("EXECUTION_REAL_ENABLED", "false").lower() == "true"
        self.allow_auto = os.getenv("EXECUTION_ALLOW_AUTO", "false").lower() == "true"
        self.paper_only = not self.real_enabled
        self.adapters = {
            "bybit": BybitExecutionAdapter(),
            "mt5": MT5ExecutionAdapter(),
        }

    def configure(self, enabled=None, mode=None):
        if mode in self.MODES:
            self.mode = mode
        if enabled is not None:
            self.enabled = bool(enabled)
            self.kill_switch = not self.enabled
        if self.mode == "auto" and not self.allow_auto:
            self.enabled = False
            self.kill_switch = True
            self.last_rejection = "Modo automatico bloqueado por padrao. Configure EXECUTION_ALLOW_AUTO=true."
        return self.status()

    def kill(self):
        self.enabled = False
        self.kill_switch = True
        self.last_rejection = "Kill switch acionado."
        return self.status()

    def evaluate(self, live_status):
        signal = self._signal_from_live_status(live_status)
        status = self.status()
        risk_result = self.risk_guard.validate(signal, status)
        decision = {
            "action": "alert",
            "allowed": risk_result["allowed"],
            "reason": risk_result["reason"],
            "risk": risk_result,
            "signal": signal,
        }
        if not self.enabled or self.kill_switch:
            decision.update({"allowed": False, "reason": "Robo desligado. Apenas alerta visual."})
            return decision
        if self.mode == "alert":
            decision.update({"allowed": False, "reason": "Modo alerta: ordem nao enviada."})
            return decision
        if self.mode == "semi_auto":
            decision.update({"action": "requires_confirmation", "reason": "Semi-automatico: aguardando confirmacao manual."})
            return decision
        if self.mode == "auto":
            decision.update({"action": "execute", "reason": "Automatico aprovado pelo Risk Guard."})
            return decision
        return decision

    def execute_paper(self, live_status):
        decision = self.evaluate(live_status)
        if not decision["allowed"]:
            self.last_rejection = decision["reason"]
            return {"success": False, "decision": decision, "status": self.status()}
        order = self.order_manager.paper_order(decision["signal"], decision["risk"])
        return {"success": True, "order": order, "decision": decision, "status": self.status()}

    def confirm(self, live_status, real=False):
        decision = self.evaluate(live_status)
        if decision["action"] not in {"requires_confirmation", "execute"}:
            self.last_rejection = decision["reason"]
            return {"success": False, "decision": decision, "status": self.status()}
        if not decision["risk"]["allowed"]:
            self.last_rejection = decision["risk"]["reason"]
            return {"success": False, "decision": decision, "status": self.status()}
        if not real or self.paper_only:
            order = self.order_manager.paper_order(decision["signal"], decision["risk"])
            return {"success": True, "paper": True, "order": order, "decision": decision, "status": self.status()}
        broker = self._broker_for_signal(decision["signal"])
        request = self._order_request(decision["signal"], broker)
        result = self.adapters[broker].send_order(request)
        if result.get("success"):
            order = self.order_manager.paper_order({**decision["signal"], "broker": broker}, decision["risk"])
            order["status"] = "sent"
            order["broker_result"] = result
            return {"success": True, "paper": False, "order": order, "broker_result": result, "decision": decision, "status": self.status()}
        self.last_rejection = result.get("reason") or "Broker rejeitou a ordem."
        return {"success": False, "broker_result": result, "decision": decision, "status": self.status()}

    def status(self):
        return {
            "enabled": self.enabled,
            "mode": self.mode,
            "kill_switch": self.kill_switch,
            "paper_trading": True,
            "real_enabled": self.real_enabled,
            "paper_only": self.paper_only,
            "auto_real_blocked": not self.allow_auto,
            "trades_today": self.order_manager.trades_today(),
            "daily_loss_pct": self.daily_loss_pct,
            "last_order": self.order_manager.last_order(),
            "last_rejection": self.last_rejection,
            "risk": self.risk_guard.config,
            "message": "Execucao pronta. Padrao: paper trading; real exige EXECUTION_REAL_ENABLED=true.",
        }

    def history(self):
        return self.order_manager.history()

    def _signal_from_live_status(self, live_status):
        direction = live_status.get("probable_direction")
        side = "buy" if direction == "BUY" else "sell" if direction == "SELL" else "wait"
        entry = live_status.get("entry_aggressive") or live_status.get("entry_conservative") or live_status.get("current_price")
        take = live_status.get("take_profit") or live_status.get("take_profit_2")
        price = live_status.get("current_price") or entry
        spread = ((live_status.get("market_data") or {}).get("spread") or 0)
        spread_pct = abs(float(spread or 0) / float(price or 1) * 100) if price else 0
        return {
            "symbol": live_status.get("symbol"),
            "side": side,
            "entry": entry,
            "stop_loss": live_status.get("stop_loss"),
            "take_profit": take,
            "risk_reward": live_status.get("risk_reward"),
            "score": live_status.get("confluence_score"),
            "confidence": live_status.get("confidence"),
            "spread_pct": spread_pct,
            "quantity": self.risk_guard.config.get("fixed_quantity", 1),
            "market": live_status.get("market"),
            "source": live_status.get("source"),
            "reason": live_status.get("reason") or live_status.get("message"),
        }

    def _broker_for_signal(self, signal):
        symbol = str(signal.get("symbol") or "")
        if symbol.endswith("USDT") or signal.get("market") == "crypto":
            return "bybit"
        return "mt5"

    def _order_request(self, signal, broker):
        return OrderRequest(
            symbol=signal["symbol"],
            side=signal["side"],
            quantity=float(signal.get("quantity") or 1),
            entry=float(signal["entry"]),
            stop_loss=float(signal["stop_loss"]),
            take_profit=float(signal["take_profit"]),
            reason=signal.get("reason") or "",
            mode="real" if self.real_enabled else "paper",
            broker=broker,
            market=signal.get("market") or "",
        )
