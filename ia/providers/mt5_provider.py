import pandas as pd
from ia.providers.base_provider import BaseProvider
from ia.mt5_connection import initialize_mt5_attach_only

try:
    import MetaTrader5 as mt5
except Exception:  # pragma: no cover - depende do terminal local do usuario
    mt5 = None

class MT5Provider(BaseProvider):
    SYMBOL_MAP = {
        "WIN": "WIN$N",
        "WDO": "WDO$N",
        "XAUUSD": "XAUUSD",
        "EURUSD": "EURUSD",
        "GBPUSD": "GBPUSD",
        "USDJPY": "USDJPY",
    }

    TIMEFRAME_MAP = {
        "1m": "TIMEFRAME_M1",
        "5m": "TIMEFRAME_M5",
        "15m": "TIMEFRAME_M15",
        "30m": "TIMEFRAME_M30",
        "1h": "TIMEFRAME_H1",
        "4h": "TIMEFRAME_H4",
        "1d": "TIMEFRAME_D1",
    }

    def __init__(self):
        self.available = mt5 is not None
        self.initialized = False
        self.last_error = None

    def initialize(self):
        if not self.available:
            self.last_error = "MetaTrader5 Python API nao instalada."
            return False
        if self.initialized and mt5.terminal_info() is not None:
            return True
        self.initialized, self.last_error = initialize_mt5_attach_only(mt5)
        return self.initialized

    def get_klines(self, symbol: str, interval: str, limit: int) -> pd.DataFrame:
        if not self.initialize():
            raise RuntimeError(self.last_error or "MT5 indisponivel")
        mt5_symbol = self.SYMBOL_MAP.get(symbol, symbol)
        mt5_timeframe = getattr(mt5, self.TIMEFRAME_MAP.get(interval, "TIMEFRAME_H1"))
        rates = mt5.copy_rates_from_pos(mt5_symbol, mt5_timeframe, 0, limit)
        if rates is None or len(rates) == 0:
            return pd.DataFrame(columns=['open', 'high', 'low', 'close', 'volume'])
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s', utc=True)
        df.set_index('time', inplace=True)
        return df[['open', 'high', 'low', 'close', 'tick_volume']].rename(columns={'tick_volume': 'volume'})
