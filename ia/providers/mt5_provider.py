import pandas as pd
import MetaTrader5 as mt5
from ia.providers.base_provider import BaseProvider

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
        "1m": mt5.TIMEFRAME_M1,
        "5m": mt5.TIMEFRAME_M5,
        "15m": mt5.TIMEFRAME_M15,
        "30m": mt5.TIMEFRAME_M30,
        "1h": mt5.TIMEFRAME_H1,
        "4h": mt5.TIMEFRAME_H4,
        "1d": mt5.TIMEFRAME_D1,
    }

    def __init__(self):
        if not mt5.initialize():
            raise RuntimeError("MetaTrader5 initialization failed")

    def get_klines(self, symbol: str, interval: str, limit: int) -> pd.DataFrame:
        mt5_symbol = self.SYMBOL_MAP.get(symbol, symbol)
        mt5_timeframe = self.TIMEFRAME_MAP.get(interval)
        rates = mt5.copy_rates_from_pos(mt5_symbol, mt5_timeframe, 0, limit)
        if rates is None or len(rates) == 0:
            return pd.DataFrame(columns=['open', 'high', 'low', 'close', 'volume'])
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s', utc=True)
        df.set_index('time', inplace=True)
        return df[['open', 'high', 'low', 'close', 'tick_volume']].rename(columns={'tick_volume': 'volume'})
