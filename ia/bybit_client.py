"""
Cliente publico da Bybit para dados spot em tempo real.
"""

from datetime import datetime, timezone

import pandas as pd
import requests


class BybitMarketData:
    """Acessa endpoints publicos da Bybit V5 Spot."""

    BASE_URL = "https://api.bybit.com"

    INTERVALS = {
        "1m": "1",
        "5m": "5",
        "15m": "15",
        "1h": "60",
        "4h": "240",
        "1d": "D",
        "1w": "W",
    }

    def __init__(self, timeout=10):
        self.timeout = timeout
        self.session = requests.Session()

    def _get(self, path, params=None):
        response = self.session.get(
            f"{self.BASE_URL}{path}",
            params=params or {},
            timeout=self.timeout,
            headers={"User-Agent": "FinanceAI/1.0"},
        )
        response.raise_for_status()
        payload = response.json()
        if int(payload.get("retCode", -1)) != 0:
            raise ValueError(payload.get("retMsg") or "Bybit indisponivel")
        return payload.get("result") or {}

    def get_klines(self, symbol, interval="1h", limit=500):
        params = {
            "category": "spot",
            "symbol": symbol.upper(),
            "interval": self.INTERVALS.get(interval, "60"),
            "limit": max(50, min(int(limit), 1000)),
        }
        rows = self._get("/v5/market/kline", params).get("list") or []
        if not rows:
            raise ValueError(f"Sem candles Bybit para {symbol}.")
        df = pd.DataFrame(rows, columns=["open_time", "open", "high", "low", "close", "volume", "turnover"])
        for column in ["open", "high", "low", "close", "volume", "turnover"]:
            df[column] = pd.to_numeric(df[column], errors="coerce")
        df["open_time"] = pd.to_datetime(pd.to_numeric(df["open_time"], errors="coerce"), unit="ms", utc=True)
        df = df.dropna(subset=["open_time", "open", "high", "low", "close"])
        df = df.sort_values("open_time").set_index("open_time")
        df["quote_asset_volume"] = df["turnover"]
        df["number_of_trades"] = 0
        df["taker_buy_base_volume"] = 0
        df["taker_buy_quote_volume"] = 0
        df["close_time"] = df.index
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
        ]]

    def get_24h_ticker(self, symbol):
        rows = self._get("/v5/market/tickers", {"category": "spot", "symbol": symbol.upper()}).get("list") or []
        if not rows:
            raise ValueError(f"Ticker Bybit indisponivel para {symbol}.")
        ticker = rows[0]
        return {
            "lastPrice": float(ticker.get("lastPrice") or 0),
            "priceChangePercent": float(ticker.get("price24hPcnt") or 0) * 100,
            "quoteVolume": float(ticker.get("turnover24h") or 0),
            "volume": float(ticker.get("volume24h") or 0),
            "count": 0,
        }

    @staticmethod
    def server_timestamp():
        return int(datetime.now(timezone.utc).timestamp())
