import pandas as pd
from abc import ABC, abstractmethod

class BaseProvider(ABC):
    @abstractmethod
    def get_klines(self, symbol: str, interval: str, limit: int) -> pd.DataFrame:
        """Retrieve OHLCV candles as a DataFrame."""
        pass