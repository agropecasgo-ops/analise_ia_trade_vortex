"""
Roteador unico de dados de mercado para o FinanceAI.

Mantem Binance como fonte principal de cripto e usa Yahoo Finance para
acoes, Forex, commodities e indices, padronizando candles OHLCV.
"""

from datetime import datetime, timezone
import time

import pandas as pd
import requests

from .binance_client import BinanceMarketData


MARKETS = {
    "crypto": {
        "label": "Criptomoedas",
        "source": "binance",
        "streaming": True,
        "assets": [
            {"symbol": "BTCUSDT", "name": "Bitcoin / USDT"},
            {"symbol": "ETHUSDT", "name": "Ethereum / USDT"},
            {"symbol": "SOLUSDT", "name": "Solana / USDT"},
            {"symbol": "XRPUSDT", "name": "XRP / USDT"},
            {"symbol": "DOGEUSDT", "name": "Dogecoin / USDT"},
        ],
    },
    "br_stock": {
        "label": "Acoes brasileiras",
        "source": "yahoo",
        "streaming": False,
        "assets": [
            {"symbol": "PETR4.SA", "name": "Petrobras PN"},
            {"symbol": "VALE3.SA", "name": "Vale ON"},
            {"symbol": "ITUB4.SA", "name": "Itau Unibanco PN"},
            {"symbol": "BBDC4.SA", "name": "Bradesco PN"},
            {"symbol": "WEGE3.SA", "name": "WEG ON"},
            {"symbol": "MGLU3.SA", "name": "Magazine Luiza ON"},
            {"symbol": "BBAS3.SA", "name": "Banco do Brasil ON"},
            {"symbol": "ABEV3.SA", "name": "Ambev ON"},
        ],
    },
    "us_stock": {
        "label": "Acoes americanas",
        "source": "yahoo",
        "streaming": False,
        "assets": [
            {"symbol": "AAPL", "name": "Apple"},
            {"symbol": "MSFT", "name": "Microsoft"},
            {"symbol": "TSLA", "name": "Tesla"},
            {"symbol": "NVDA", "name": "Nvidia"},
            {"symbol": "AMZN", "name": "Amazon"},
            {"symbol": "META", "name": "Meta"},
            {"symbol": "GOOGL", "name": "Alphabet"},
        ],
    },
    "forex": {
        "label": "Forex",
        "source": "yahoo",
        "streaming": False,
        "assets": [
            {"symbol": "EURUSD", "name": "Euro / Dolar"},
            {"symbol": "GBPUSD", "name": "Libra / Dolar"},
            {"symbol": "USDJPY", "name": "Dolar / Iene"},
            {"symbol": "AUDUSD", "name": "Dolar australiano / Dolar"},
            {"symbol": "USDCAD", "name": "Dolar / Dolar canadense"},
            {"symbol": "USDCHF", "name": "Dolar / Franco suico"},
        ],
    },
    "commodity": {
        "label": "Commodities",
        "source": "yahoo",
        "streaming": False,
        "assets": [
            {"symbol": "XAUUSD", "name": "Ouro spot"},
            {"symbol": "GOLD", "name": "Ouro futuro"},
            {"symbol": "WTI", "name": "Petroleo WTI"},
            {"symbol": "SILVER", "name": "Prata"},
            {"symbol": "NATGAS", "name": "Gas natural"},
        ],
    },
    "index": {
        "label": "Indices",
        "source": "yahoo",
        "streaming": False,
        "assets": [
            {"symbol": "IBOV", "name": "Ibovespa"},
            {"symbol": "SP500", "name": "S&P 500"},
            {"symbol": "NASDAQ", "name": "Nasdaq Composite"},
            {"symbol": "DOWJONES", "name": "Dow Jones"},
            {"symbol": "DXY", "name": "US Dollar Index"},
        ],
    },
}


YAHOO_SYMBOLS = {
    "EURUSD": "EURUSD=X",
    "GBPUSD": "GBPUSD=X",
    "USDJPY": "JPY=X",
    "AUDUSD": "AUDUSD=X",
    "USDCAD": "CAD=X",
    "USDCHF": "CHF=X",
    "XAUUSD": "GC=F",
    "GOLD": "GC=F",
    "WTI": "CL=F",
    "SILVER": "SI=F",
    "NATGAS": "NG=F",
    "IBOV": "^BVSP",
    "SP500": "^GSPC",
    "NASDAQ": "^IXIC",
    "DOWJONES": "^DJI",
    "DXY": "DX-Y.NYB",
}


YAHOO_INTERVALS = {
    "1m": ("1m", "7d"),
    "5m": ("5m", "30d"),
    "15m": ("15m", "60d"),
    "1h": ("60m", "730d"),
    "4h": ("60m", "730d"),
    "1d": ("1d", "5y"),
    "1w": ("1wk", "10y"),
}


TIMEFRAME_SECONDS = {
    "1m": 60,
    "5m": 300,
    "15m": 900,
    "1h": 3600,
    "4h": 14400,
    "1d": 86400,
    "1w": 604800,
}


class MarketDataRouter:
    def __init__(self, timeout=10):
        self.binance = BinanceMarketData(timeout=timeout)
        self.session = requests.Session()
        self.timeout = timeout
        self._last_meta = {}

    def normalize_symbol(self, symbol):
        value = (symbol or "BTCUSDT").replace("-", "").replace("/", "").upper().strip()
        return value or "BTCUSDT"

    def identify_market(self, symbol):
        symbol = self.normalize_symbol(symbol)
        for market_key, config in MARKETS.items():
            if any(asset["symbol"] == symbol for asset in config["assets"]):
                return market_key
        if symbol.endswith(".SA"):
            return "br_stock"
        if symbol.endswith("USDT"):
            return "crypto"
        if len(symbol) == 6 and symbol.isalpha():
            return "forex"
        return "us_stock"

    def get_assets(self, market=None):
        if market and market in MARKETS:
            return [self._asset_payload(asset, market) for asset in MARKETS[market]["assets"]]
        assets = []
        for market_key, config in MARKETS.items():
            assets.extend(self._asset_payload(asset, market_key) for asset in config["assets"])
        return assets

    def get_markets(self):
        return [
            {
                "key": key,
                "label": config["label"],
                "source": config["source"],
                "streaming": config["streaming"],
                "assets": self.get_assets(key),
            }
            for key, config in MARKETS.items()
        ]

    def get_klines(self, symbol, interval="1h", limit=500):
        symbol = self.normalize_symbol(symbol)
        market = self.identify_market(symbol)
        limit = max(60, min(int(limit or 500), 1000))
        if market == "crypto":
            return self._binance_klines(symbol, interval, limit, market)
        return self._yahoo_klines(symbol, interval, limit, market)

    def get_24h_ticker(self, symbol):
        symbol = self.normalize_symbol(symbol)
        market = self.identify_market(symbol)
        if market == "crypto":
            ticker = self.binance.get_24h_ticker(symbol)
            ticker.update(self._meta(symbol))
            return ticker
        df = self.get_klines(symbol, "1d", 120)
        close = float(df["close"].iloc[-1])
        previous = float(df["close"].iloc[-2]) if len(df) > 1 else close
        change = ((close - previous) / previous * 100) if previous else 0
        meta = self._meta(symbol)
        return {
            "lastPrice": close,
            "priceChangePercent": change,
            "quoteVolume": float(df["volume"].tail(20).sum()),
            "volume": float(df["volume"].iloc[-1]),
            "count": 0,
            **meta,
        }

    def last_meta(self, symbol):
        return self._last_meta.get(self.normalize_symbol(symbol), self._meta(symbol))

    def _binance_klines(self, symbol, interval, limit, market):
        try:
            df = self.binance.get_klines(symbol, interval, limit)
            self._set_meta(symbol, market, "binance", "open", None, len(df), True)
            return df
        except Exception as error:
            self._set_meta(symbol, market, "binance", "no_data", f"Binance indisponivel para {symbol}.", 0, False)
            raise error

    def _yahoo_klines(self, symbol, interval, limit, market):
        yahoo_symbol = self._yahoo_symbol(symbol)
        yahoo_interval, range_value = YAHOO_INTERVALS.get(interval, ("60m", "730d"))
        params = {
            "interval": yahoo_interval,
            "range": range_value,
            "includePrePost": "false",
            "events": "div,splits",
        }
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{yahoo_symbol}"
        response = self.session.get(url, params=params, timeout=self.timeout, headers={"User-Agent": "FinanceAI/1.0"})
        response.raise_for_status()
        payload = response.json()
        result = (payload.get("chart", {}).get("result") or [None])[0]
        if not result:
            self._set_meta(symbol, market, "yahoo", "no_data", f"Sem dados para {symbol}.", 0, False)
            raise ValueError(f"Sem dados para {symbol}.")
        timestamps = result.get("timestamp") or []
        quote = ((result.get("indicators") or {}).get("quote") or [{}])[0]
        if not timestamps or not quote:
            self._set_meta(symbol, market, "yahoo", "no_data", f"Sem candles para {symbol}.", 0, False)
            raise ValueError(f"Sem candles para {symbol}.")
        df = pd.DataFrame({
            "open": quote.get("open"),
            "high": quote.get("high"),
            "low": quote.get("low"),
            "close": quote.get("close"),
            "volume": quote.get("volume"),
        }, index=pd.to_datetime(timestamps, unit="s", utc=True))
        df = df.dropna(subset=["open", "high", "low", "close"])
        df["volume"] = pd.to_numeric(df["volume"], errors="coerce").fillna(0)
        df = df.astype({"open": float, "high": float, "low": float, "close": float, "volume": float})
        if interval == "4h":
            df = self._resample_4h(df)
        df = df.tail(limit)
        if df.empty:
            self._set_meta(symbol, market, "yahoo", "no_data", f"Sem candles para {symbol}.", 0, False)
            raise ValueError(f"Sem candles para {symbol}.")
        status = self._market_status(df, interval, market)
        message = "Mercado fechado; exibindo o ultimo historico disponivel." if status == "closed" else None
        self._set_meta(symbol, market, "yahoo", status, message, len(df), False)
        return df

    def _resample_4h(self, df):
        return df.resample("4h").agg({
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum",
        }).dropna(subset=["open", "high", "low", "close"])

    def _market_status(self, df, interval, market):
        if market == "crypto":
            return "open"
        now = datetime.now(timezone.utc)
        if market == "forex":
            if now.weekday() == 5 or (now.weekday() == 6 and now.hour < 21) or (now.weekday() == 4 and now.hour >= 22):
                return "closed"
            return "open"
        if now.weekday() >= 5:
            return "closed"
        last_ts = df.index[-1]
        max_age = TIMEFRAME_SECONDS.get(interval, 3600) * 2.5
        if interval in ["1d", "1w"]:
            max_age = 60 * 60 * 24 * 5
        age = max(0, now.timestamp() - last_ts.timestamp())
        return "closed" if age > max_age else "open"

    def _yahoo_symbol(self, symbol):
        if symbol in YAHOO_SYMBOLS:
            return YAHOO_SYMBOLS[symbol]
        return symbol

    def _asset_payload(self, asset, market_key):
        config = MARKETS[market_key]
        return {
            **asset,
            "market": market_key,
            "market_label": config["label"],
            "source": config["source"],
            "streaming": config["streaming"],
        }

    def _meta(self, symbol):
        symbol = self.normalize_symbol(symbol)
        market = self.identify_market(symbol)
        config = MARKETS.get(market, MARKETS["us_stock"])
        return {
            "symbol": symbol,
            "market": market,
            "market_label": config["label"],
            "source": config["source"],
            "market_status": "unknown",
            "streaming": config["streaming"],
            "message": None,
            "fallback": False,
            "candles_count": 0,
        }

    def _set_meta(self, symbol, market, source, status, message, candles_count, streaming):
        self._last_meta[self.normalize_symbol(symbol)] = {
            "symbol": self.normalize_symbol(symbol),
            "market": market,
            "market_label": MARKETS.get(market, {}).get("label", market),
            "source": source,
            "market_status": status,
            "streaming": streaming,
            "message": message,
            "fallback": False,
            "candles_count": candles_count,
            "updated_at": int(time.time()),
        }
