"""
Contratos de broker para execucao.

As implementacoes reais ficam isoladas dos motores de analise. O modo padrao
do FinanceAI usa paper trading e nao envia ordens reais.
"""

from dataclasses import dataclass


@dataclass
class OrderRequest:
    symbol: str
    side: str
    quantity: float
    entry: float
    stop_loss: float
    take_profit: float
    reason: str
    mode: str = "paper"
    broker: str = "paper"
    market: str = ""


class BrokerAdapter:
    name = "base"

    def send_order(self, order: OrderRequest):
        raise NotImplementedError

    def close_position(self, symbol: str):
        raise NotImplementedError

    def positions(self):
        return []

    def account(self):
        return {"balance": 0, "equity": 0}

    def spread(self, symbol: str):
        return None
