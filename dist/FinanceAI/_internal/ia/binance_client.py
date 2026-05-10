"""
Cliente publico da Binance para dados reais de mercado.
"""

from datetime import datetime, timezone
import time

import pandas as pd
import requests


class BinanceMarketData:
    """Acessa endpoints publicos da Binance Spot."""

    BASE_URL = "https://api.binance.com"
    DATA_URL = "https://data-api.binance.vision"

    DEFAULT_SYMBOLS = [
        {"symbol": "BTCUSDT", "name": "Bitcoin / USDT"},
        {"symbol": "ETHUSDT", "name": "Ethereum / USDT"},
        {"symbol": "BNBUSDT", "name": "BNB / USDT"},
        {"symbol": "SOLUSDT", "name": "Solana / USDT"},
        {"symbol": "XRPUSDT", "name": "XRP / USDT"},
        {"symbol": "ADAUSDT", "name": "Cardano / USDT"},
        {"symbol": "DOGEUSDT", "name": "Dogecoin / USDT"},
        {"symbol": "LINKUSDT", "name": "Chainlink / USDT"},
    ]

    def __init__(self, timeout=10):
        self.timeout = timeout
        self.session = requests.Session()

    def _get(self, path, params=None, data_api=False):
        base_url = self.DATA_URL if data_api else self.BASE_URL
        response = self.session.get(
            f"{base_url}{path}",
            params=params or {},
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()

    def get_klines(self, symbol, interval="1h", limit=500):
        """Retorna candles OHLCV como DataFrame."""
        params = {
            "symbol": symbol.upper(),
            "interval": interval,
            "limit": max(50, min(int(limit), 1000)),
        }
        rows = self._get("/api/v3/klines", params=params, data_api=True)
        columns = [
            "open_time",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "close_time",
            "quote_asset_volume",
            "number_of_trades",
            "taker_buy_base_volume",
            "taker_buy_quote_volume",
            "ignore",
        ]
        df = pd.DataFrame(rows, columns=columns)
        numeric_columns = [
            "open",
            "high",
            "low",
            "close",
            "volume",
            "quote_asset_volume",
            "taker_buy_base_volume",
            "taker_buy_quote_volume",
        ]
        for column in numeric_columns:
            df[column] = pd.to_numeric(df[column], errors="coerce")

        df["open_time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
        df["close_time"] = pd.to_datetime(df["close_time"], unit="ms", utc=True)
        df["number_of_trades"] = pd.to_numeric(df["number_of_trades"], errors="coerce")
        df = df.set_index("open_time")
        return df[[
            "open",
            "high",
            "low",
            "close",
            "volume",
            "close_time",
            "quote_asset_volume",
            "number_of_trades",
            "taker_buy_base_volume",
            "taker_buy_quote_volume",
        ]].dropna()

    def get_24h_ticker(self, symbol):
        return self._get("/api/v3/ticker/24hr", {"symbol": symbol.upper()})

    def get_assets(self):
        return self.DEFAULT_SYMBOLS

    @staticmethod
    def server_timestamp():
        return int(datetime.now(timezone.utc).timestamp())


class TimedCache:
    """Cache simples com TTL para reduzir chamadas repetidas."""

    def __init__(self, ttl_seconds=20):
        self.ttl_seconds = ttl_seconds
        self._values = {}

    def get(self, key):
        value = self._values.get(key)
        if not value:
            return None
        expires_at, payload = value
        if expires_at <= time.time():
            self._values.pop(key, None)
            return None
        return payload

    def set(self, key, payload):
        self._values[key] = (time.time() + self.ttl_seconds, payload)
        return payload
