"""
Adaptador de execucao MT5.

Executa somente quando o ExecutionEngine liberar modo real. Por padrao o robô
continua em paper trading.
"""

import os

from .broker_adapter import BrokerAdapter

try:
    import MetaTrader5 as mt5
except Exception:  # pragma: no cover
    mt5 = None


class MT5ExecutionAdapter(BrokerAdapter):
    name = "mt5"

    def send_order(self, order):
        if mt5 is None:
            return {"success": False, "blocked": True, "reason": "MetaTrader5 Python API nao instalada."}
        if not mt5.initialize():
            return {"success": False, "blocked": True, "reason": f"MT5 nao inicializado: {mt5.last_error()}"}
        account = mt5.account_info()
        if os.getenv("EXECUTION_REQUIRE_DEMO", "true").lower() == "true":
            demo_mode = getattr(mt5, "ACCOUNT_TRADE_MODE_DEMO", 0)
            if not account or getattr(account, "trade_mode", None) != demo_mode:
                return {"success": False, "blocked": True, "reason": "Conta MT5 real bloqueada. Use conta demo ou desative EXECUTION_REQUIRE_DEMO conscientemente."}
        symbol = order.symbol.upper()
        if not mt5.symbol_select(symbol, True):
            return {"success": False, "blocked": True, "reason": f"Simbolo MT5 indisponivel: {symbol}"}
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            return {"success": False, "blocked": True, "reason": "Tick MT5 indisponivel."}
        is_buy = order.side.lower() == "buy"
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": float(order.quantity),
            "type": mt5.ORDER_TYPE_BUY if is_buy else mt5.ORDER_TYPE_SELL,
            "price": float(tick.ask if is_buy else tick.bid),
            "sl": float(order.stop_loss),
            "tp": float(order.take_profit),
            "deviation": int(os.getenv("MT5_MAX_DEVIATION", "20")),
            "magic": int(os.getenv("MT5_MAGIC", "50501")),
            "comment": "FinanceAI IA",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        result = mt5.order_send(request)
        if result is None:
            return {"success": False, "reason": f"MT5 order_send retornou vazio: {mt5.last_error()}"}
        payload = result._asdict() if hasattr(result, "_asdict") else {"retcode": getattr(result, "retcode", None)}
        return {"success": getattr(result, "retcode", None) == mt5.TRADE_RETCODE_DONE, "broker": self.name, "result": payload}

    def close_position(self, symbol):
        return {"success": False, "blocked": True, "reason": "Fechamento MT5 em massa nao habilitado nesta etapa."}

    def positions(self):
        if mt5 is None or not mt5.initialize():
            return []
        return [item._asdict() for item in (mt5.positions_get() or [])]

    def account(self):
        if mt5 is None or not mt5.initialize():
            return {"balance": 0, "equity": 0, "source": "mt5_unavailable"}
        account = mt5.account_info()
        return account._asdict() if hasattr(account, "_asdict") else {"balance": 0, "equity": 0}
