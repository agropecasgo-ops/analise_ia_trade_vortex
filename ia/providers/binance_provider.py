import pandas as pd
from ia.providers.base_provider import BaseProvider
from ia.binance_client import BinanceMarketData

class BinanceProvider(BaseProvider):
    def __init__(self):
        self.market_data = BinanceMarketData()

    def get_klines(self, symbol: str, interval: str, limit: int) -> pd.DataFrame:
        return self.market_data.get_klines(symbol, interval, limit)