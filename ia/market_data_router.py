"""
Roteador unico de dados de mercado para o FinanceAI.

Mantem Bybit como fonte principal de cripto, Binance como fallback, MT5 para
Forex/indices/commodities e Yahoo Finance como fallback historico.
"""

from datetime import datetime, timezone
import time

import pandas as pd
import requests

from .binance_client import BinanceMarketData
from .bybit_provider import BybitMarketData
from .mt5_provider import MT5Provider
from .profit_rtd_provider import ProfitRTDProvider


MARKETS = {
    "crypto": {
        "label": "Criptomoedas",
        "source": "bybit",
        "streaming": True,
        "assets": [
            {"symbol": "BTCUSDT", "name": "Bitcoin / USDT"},
            {"symbol": "ETHUSDT", "name": "Ethereum / USDT"},
            {"symbol": "SOLUSDT", "name": "Solana / USDT"},
            {"symbol": "XRPUSDT", "name": "XRP / USDT"},
            {"symbol": "BNBUSDT", "name": "BNB / USDT"},
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
        "source": "mt5",
        "streaming": True,
        "assets": [
            {"symbol": "EURUSD", "name": "Euro / Dolar"},
            {"symbol": "GBPUSD", "name": "Libra / Dolar"},
            {"symbol": "USDJPY", "name": "Dolar / Iene"},
            {"symbol": "USDBRL", "name": "Dolar / Real brasileiro"},
            {"symbol": "AUDUSD", "name": "Dolar australiano / Dolar"},
            {"symbol": "USDCAD", "name": "Dolar / Dolar canadense"},
            {"symbol": "USDCHF", "name": "Dolar / Franco suico"},
            {"symbol": "XAUUSD", "name": "Ouro / Dolar"},
        ],
    },
    "futures_b3": {
        "label": "Futuros B3",
        "source": "profit_rtd",
        "streaming": True,
        "assets": [
            {"symbol": "WIN", "name": "Mini Indice atual", "tv_symbol": "BMFBOVESPA:WIN1!", "aliases": ["WIN1!", "WIN1"]},
            {"symbol": "WDO", "name": "Mini Dolar atual", "tv_symbol": "BMFBOVESPA:WDO1!", "aliases": ["WDO1!", "WDO1"]},
        ],
    },
    "commodity": {
        "label": "Commodities",
        "source": "mt5",
        "streaming": True,
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
        "source": "mt5",
        "streaming": True,
        "assets": [
            {"symbol": "IBOV", "name": "Ibovespa"},
            {"symbol": "SP500", "name": "S&P 500"},
            {"symbol": "NASDAQ", "name": "Nasdaq Composite"},
            {"symbol": "DOWJONES", "name": "Dow Jones"},
            {"symbol": "DXY", "name": "US Dollar Index"},
            {"symbol": "US30", "name": "Dow Jones CFD"},
            {"symbol": "NAS100", "name": "Nasdaq 100 CFD"},
        ],
    },
}


YAHOO_SYMBOLS = {
    "EURUSD": "EURUSD=X",
    "GBPUSD": "GBPUSD=X",
    "USDJPY": "JPY=X",
    "USDBRL": "BRL=X",
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
    "US30": "^DJI",
    "NAS100": "^IXIC",
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
        self.bybit = BybitMarketData(timeout=timeout)
        self.binance = BinanceMarketData(timeout=timeout)
        self.mt5 = MT5Provider()
        self.profit_rtd = ProfitRTDProvider()
        self.session = requests.Session()
        self.timeout = timeout
        self._last_meta = {}

    def normalize_symbol(self, symbol):
        value = (symbol or "BTCUSDT").replace("-", "").replace("/", "").upper().strip()
        if ":" in value:
            value = value.split(":")[-1]
        if value in {"WIN1!", "WIN1"}:
            return "WIN"
        if value in {"WDO1!", "WDO1"}:
            return "WDO"
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
        if symbol.startswith(("WIN", "WDO")):
            return "futures_b3"
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
            return self._crypto_klines(symbol, interval, limit, market)
        if market == "futures_b3":
            return self._profit_or_mt5_klines(symbol, interval, limit, market)
        if market in {"forex", "commodity", "index"}:
            return self._mt5_or_yahoo_klines(symbol, interval, limit, market)
        return self._yahoo_klines(symbol, interval, limit, market)

    def get_24h_ticker(self, symbol):
        symbol = self.normalize_symbol(symbol)
        market = self.identify_market(symbol)
        if market == "crypto":
            try:
                ticker = self.bybit.get_24h_ticker(symbol)
                self._set_meta(symbol, market, "bybit", "open", None, 0, True)
            except Exception:
                ticker = self.binance.get_24h_ticker(symbol)
                self._set_meta(symbol, market, "binance", "open", "Bybit indisponivel; usando Binance fallback.", 0, True, True)
            ticker.update(self.last_meta(symbol))
            return ticker
        if market == "futures_b3":
            try:
                ticker = self.profit_rtd.get_24h_ticker(symbol)
                tick = self.profit_rtd.get_tick(symbol)
                self._set_meta(symbol, market, "profit_rtd", "open", "Dados em tempo real via Profit RTD; candles sao agregados localmente.", 0, True, False, tick)
                ticker.update(self.last_meta(symbol))
                return ticker
            except Exception as profit_error:
                try:
                    ticker = self.mt5.get_24h_ticker(symbol)
                    self._set_meta(symbol, market, "mt5", self._market_status(None, "1m", market), f"Profit RTD indisponivel; usando MT5. {profit_error}", 0, True, True, self._safe_tick(symbol))
                    ticker.update(self.last_meta(symbol))
                    return ticker
                except Exception as mt5_error:
                    self._set_meta(symbol, market, "profit_rtd", "no_data", f"Profit RTD e MT5 indisponiveis para {symbol}. Profit: {profit_error}. MT5: {mt5_error}", 0, False, False)
        if market in {"forex", "futures_b3", "commodity", "index"}:
            try:
                ticker = self.mt5.get_24h_ticker(symbol)
                self._set_meta(symbol, market, "mt5", self._market_status(None, "1m", market), None, 0, True, False, self._safe_tick(symbol))
                ticker.update(self.last_meta(symbol))
                return ticker
            except Exception as error:
                self._set_meta(symbol, market, "yahoo", "fallback", f"MT5 indisponivel; usando Yahoo fallback. {error}", 0, False, True)
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

    def get_realtime_quote(self, symbol):
        symbol = self.normalize_symbol(symbol)
        market = self.identify_market(symbol)
        if market == "futures_b3":
            try:
                tick = self.profit_rtd.get_tick(symbol)
                self._set_meta(symbol, market, "profit_rtd", "open", "Dados em tempo real via Profit RTD.", 0, True, False, tick)
                return {**tick, **self.last_meta(symbol)}
            except Exception as profit_error:
                try:
                    tick = self.mt5.get_tick(symbol)
                    self._set_meta(symbol, market, "mt5", self._market_status(None, "1m", market), f"Profit RTD indisponivel; usando MT5. {profit_error}", 0, True, True, tick)
                    return {**tick, **self.last_meta(symbol)}
                except Exception as mt5_error:
                    self._set_meta(symbol, market, "profit_rtd", "no_data", f"Profit RTD e MT5 indisponiveis para {symbol}. Profit: {profit_error}. MT5: {mt5_error}", 0, False, False)
                    raise mt5_error
        if market in {"forex", "futures_b3", "commodity", "index"}:
            tick = self.mt5.get_tick(symbol)
            self._set_meta(symbol, market, "mt5", self._market_status(None, "1m", market), None, 0, True, False, tick)
            return {**tick, **self.last_meta(symbol)}
        ticker = self.get_24h_ticker(symbol)
        return {
            "symbol": symbol,
            "bid": float(ticker.get("bid") or ticker.get("lastPrice") or 0),
            "ask": float(ticker.get("ask") or ticker.get("lastPrice") or 0),
            "last": float(ticker.get("lastPrice") or 0),
            "spread": float(ticker.get("spread") or 0),
            "volume": float(ticker.get("volume") or 0),
            "source": ticker.get("source"),
            **self.last_meta(symbol),
        }

    def _crypto_klines(self, symbol, interval, limit, market):
        try:
            df = self.bybit.get_klines(symbol, interval, limit)
            self._set_meta(symbol, market, "bybit", "open", None, len(df), True)
            return df
        except Exception:
            return self._binance_klines(symbol, interval, limit, market, fallback=True)

    def _binance_klines(self, symbol, interval, limit, market, fallback=False):
        try:
            df = self.binance.get_klines(symbol, interval, limit)
            message = "Bybit indisponivel; usando Binance fallback." if fallback else None
            self._set_meta(symbol, market, "binance", "open", message, len(df), True, fallback)
            return df
        except Exception as error:
            message = "Bybit e Binance indisponiveis." if fallback else f"Binance indisponivel para {symbol}."
            self._set_meta(symbol, market, "binance", "no_data", message, 0, False, fallback)
            raise error

    def _profit_or_mt5_klines(self, symbol, interval, limit, market):
        try:
            df = self.profit_rtd.get_klines(symbol, interval, limit)
            tick = self.profit_rtd.get_tick(symbol)
            message = "Profit RTD conectado. Historico de candles e agregado localmente a partir dos ticks recebidos."
            self._set_meta(symbol, market, "profit_rtd", self._market_status(df, interval, market), message, len(df), True, False, tick)
            return df
        except Exception as profit_error:
            try:
                df = self.mt5.get_klines(symbol, interval, limit)
                tick = self._safe_tick(symbol)
                message = f"Profit RTD indisponivel; usando MT5. {profit_error}"
                self._set_meta(symbol, market, "mt5", self._market_status(df, interval, market), message, len(df), True, True, tick)
                return df
            except Exception as mt5_error:
                message = f"Profit RTD e MT5 indisponiveis para {symbol}. Profit: {profit_error}. MT5: {mt5_error}"
                self._set_meta(symbol, market, "profit_rtd", "no_data", message, 0, False, False)
                raise ValueError(message) from mt5_error

    def _mt5_or_yahoo_klines(self, symbol, interval, limit, market):
        try:
            df = self.mt5.get_klines(symbol, interval, limit)
            tick = self._safe_tick(symbol)
            self._set_meta(symbol, market, "mt5", self._market_status(df, interval, market), None, len(df), True, False, tick)
            return df
        except Exception as error:
            if market == "futures_b3":
                message = f"MT5 indisponivel para {symbol}. Verifique se o contrato atual esta no Market Watch do MetaTrader 5. {error}"
                self._set_meta(symbol, market, "mt5", "no_data", message, 0, False, False)
                raise ValueError(message) from error
            message = f"MT5 indisponivel; usando Yahoo fallback. {error}"
            try:
                df = self._yahoo_klines(symbol, interval, limit, market)
                self._set_meta(symbol, market, "yahoo", self._market_status(df, interval, market), message, len(df), False, True)
                return df
            except Exception:
                self._set_meta(symbol, market, "mt5", "no_data", message, 0, False, True)
                raise

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
        if df is None or len(df) == 0:
            return "open"
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

    def _safe_tick(self, symbol):
        try:
            return self.mt5.get_tick(symbol)
        except Exception:
            return None

    def _set_meta(self, symbol, market, source, status, message, candles_count, streaming, fallback=False, tick=None):
        self._last_meta[self.normalize_symbol(symbol)] = {
            "symbol": self.normalize_symbol(symbol),
            "market": market,
            "market_label": MARKETS.get(market, {}).get("label", market),
            "source": source,
            "market_status": status,
            "streaming": streaming,
            "message": message,
            "fallback": fallback,
            "candles_count": candles_count,
            "tick": tick,
            "bid": tick.get("bid") if isinstance(tick, dict) else None,
            "ask": tick.get("ask") if isinstance(tick, dict) else None,
            "spread": tick.get("spread") if isinstance(tick, dict) else None,
            "provider_symbol": tick.get("provider_symbol") if isinstance(tick, dict) else None,
            "updated_at": int(time.time()),
        }
