"""
Provider institucional para MetaTrader 5.

O MetaTrader5 Python API e opcional no ambiente. Quando nao estiver instalado,
ou quando o terminal MT5 nao estiver conectado, o roteador cai para o provider
historico configurado sem interromper a Live Trading.
"""

from datetime import datetime, timezone

import pandas as pd

try:
    import MetaTrader5 as mt5
except Exception:  # pragma: no cover - depende do terminal local do usuario
    mt5 = None


class MT5Provider:
    TIMEFRAMES = {
        "1m": "TIMEFRAME_M1",
        "5m": "TIMEFRAME_M5",
        "15m": "TIMEFRAME_M15",
        "1h": "TIMEFRAME_H1",
        "4h": "TIMEFRAME_H4",
        "1d": "TIMEFRAME_D1",
        "1w": "TIMEFRAME_W1",
    }

    SYMBOL_ALIASES = {
        "GOLD": ["XAUUSD", "GOLD"],
        "XAUUSD": ["XAUUSD", "GOLD"],
        "WTI": ["WTI", "USOIL", "XTIUSD", "CL"],
        "SILVER": ["XAGUSD", "SILVER"],
        "NATGAS": ["NATGAS", "NGAS", "XNGUSD"],
        "SP500": ["US500", "SPX500", "SP500"],
        "NASDAQ": ["USTEC", "NAS100", "NASDAQ"],
        "DOWJONES": ["US30", "DJ30", "DOWJONES"],
        "DXY": ["DXY", "USDX"],
        "IBOV": ["IBOV", "BRA50"],
    }

    def __init__(self):
        self.available = mt5 is not None
        self.initialized = False
        self.last_error = None

    def initialize(self):
        if not self.available:
            self.last_error = "MetaTrader5 Python API nao instalada."
            return False
        if self.initialized:
            return True
        self.initialized = bool(mt5.initialize())
        if not self.initialized:
            self.last_error = str(mt5.last_error())
        return self.initialized

    def resolve_symbol(self, symbol):
        candidates = self.SYMBOL_ALIASES.get(symbol.upper(), [symbol.upper()])
        if not self.initialize():
            raise RuntimeError(self.last_error or "MT5 indisponivel")
        available = mt5.symbols_get()
        names = {item.name.upper(): item.name for item in available or []}
        for candidate in candidates:
            if candidate.upper() in names:
                resolved = names[candidate.upper()]
                mt5.symbol_select(resolved, True)
                return resolved
        for candidate in candidates:
            match = next((item.name for item in available or [] if candidate.upper() in item.name.upper()), None)
            if match:
                mt5.symbol_select(match, True)
                return match
        raise ValueError(f"Simbolo MT5 nao encontrado: {symbol}")

    def get_klines(self, symbol, interval="1h", limit=500):
        resolved = self.resolve_symbol(symbol)
        timeframe_name = self.TIMEFRAMES.get(interval, "TIMEFRAME_H1")
        timeframe = getattr(mt5, timeframe_name)
        rows = mt5.copy_rates_from_pos(resolved, timeframe, 0, max(60, min(int(limit), 2000)))
        if rows is None or len(rows) == 0:
            raise ValueError(f"Sem candles MT5 para {symbol}.")
        df = pd.DataFrame(rows)
        df["open_time"] = pd.to_datetime(df["time"], unit="s", utc=True)
        df = df.rename(columns={"tick_volume": "volume"})
        df["close_time"] = df["open_time"]
        df["quote_asset_volume"] = df["real_volume"] if "real_volume" in df else df["volume"]
        df["number_of_trades"] = df["spread"] if "spread" in df else 0
        df["taker_buy_base_volume"] = 0
        df["taker_buy_quote_volume"] = 0
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
        ]].astype({
            "open": float,
            "high": float,
            "low": float,
            "close": float,
            "volume": float,
        })

    def get_tick(self, symbol):
        resolved = self.resolve_symbol(symbol)
        tick = mt5.symbol_info_tick(resolved)
        info = mt5.symbol_info(resolved)
        if tick is None or info is None:
            raise ValueError(f"Sem tick MT5 para {symbol}.")
        bid = float(tick.bid or 0)
        ask = float(tick.ask or 0)
        spread_points = float(getattr(info, "spread", 0) or 0)
        point = float(getattr(info, "point", 0) or 0)
        spread = (ask - bid) if bid and ask else spread_points * point
        return {
            "symbol": symbol.upper(),
            "provider_symbol": resolved,
            "bid": bid,
            "ask": ask,
            "last": float(tick.last or bid or ask or 0),
            "spread": spread,
            "spread_points": spread_points,
            "volume": float(tick.volume or 0),
            "time": int(getattr(tick, "time", 0) or datetime.now(timezone.utc).timestamp()),
            "source": "mt5",
        }

    def get_24h_ticker(self, symbol):
        tick = self.get_tick(symbol)
        df = self.get_klines(symbol, "1d", 3)
        last = tick["last"] or float(df["close"].iloc[-1])
        previous = float(df["close"].iloc[-2]) if len(df) > 1 else last
        change = ((last - previous) / previous * 100) if previous else 0
        return {
            "lastPrice": last,
            "priceChangePercent": change,
            "quoteVolume": float(df["quote_asset_volume"].tail(2).sum()),
            "volume": tick["volume"] or float(df["volume"].iloc[-1]),
            "count": int(tick["spread_points"]),
            "bid": tick["bid"],
            "ask": tick["ask"],
            "spread": tick["spread"],
            "spread_points": tick["spread_points"],
            "provider_symbol": tick["provider_symbol"],
        }
