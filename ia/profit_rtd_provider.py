"""
Provider local para Profit/Nelogica via RTD do Excel.

O Profit expoe dados em tempo real por RTD/DDE. Este provider usa a interface
RTD oficial atraves do Excel, le campos de mercado e agrega os ticks em candles
na memoria do backend. Ele nao acessa endpoints internos nem faz scraping.
"""

from __future__ import annotations

from datetime import datetime, timezone
import math
import os
import queue
import threading
import time
from typing import Any

import pandas as pd

try:  # pragma: no cover - depende do Windows/Office local do usuario
    import pythoncom
    import win32com.client
except Exception:  # pragma: no cover
    pythoncom = None
    win32com = None


TIMEFRAME_SECONDS = {
    "1m": 60,
    "5m": 300,
    "15m": 900,
    "1h": 3600,
    "4h": 14400,
    "1d": 86400,
}


class ProfitRTDProvider:
    DEFAULT_SYMBOLS = {
        "WIN": ["WINFUT_F_0", "WINFUT", "WINM26_F_0", "WINM26", "WIN_F_0"],
        "WIN1": ["WINFUT_F_0", "WINFUT", "WINM26_F_0", "WINM26", "WIN_F_0"],
        "WIN1!": ["WINFUT_F_0", "WINFUT", "WINM26_F_0", "WINM26", "WIN_F_0"],
        "WDO": ["WDOFUT_F_0", "WDOFUT", "WDOM26_F_0", "WDOM26", "WDO_F_0"],
        "WDO1": ["WDOFUT_F_0", "WDOFUT", "WDOM26_F_0", "WDOM26", "WDO_F_0"],
        "WDO1!": ["WDOFUT_F_0", "WDOFUT", "WDOM26_F_0", "WDOM26", "WDO_F_0"],
    }

    ATTRIBUTES = {
        "last": "ULT",
        "open": "ABE",
        "high": "MAX",
        "low": "MIN",
        "volume": "VOL",
        "change_percent": "VAR",
        "change_points": "VARPTS",
        "bid": "OCP",
        "ask": "OVD",
        "last_quantity": "QUL",
        "trades": "NEG",
        "date": "DAT",
        "time": "HOR",
    }

    def __init__(self, enabled: bool | None = None, poll_delay: float | None = None):
        self.enabled = self._env_enabled() if enabled is None else enabled
        self.poll_delay = poll_delay if poll_delay is not None else float(os.getenv("PROFIT_RTD_POLL_DELAY", "0.12"))
        self.visible_excel = os.getenv("PROFIT_RTD_EXCEL_VISIBLE", "0").lower() in {"1", "true", "yes", "sim"}
        self.available = pythoncom is not None and win32com is not None
        self.symbols = self._build_symbol_map()
        self.last_error = None
        self._requests: queue.Queue = queue.Queue()
        self._worker = None
        self._worker_lock = threading.Lock()
        self._candle_lock = threading.Lock()
        self._candles: dict[tuple[str, str], list[dict[str, Any]]] = {}
        self._last_session_volume: dict[str, float] = {}

    def is_enabled(self) -> bool:
        return self.enabled and self.available

    def normalize_symbol(self, symbol: str) -> str:
        value = (symbol or "").replace("-", "").replace("/", "").upper().strip()
        if ":" in value:
            value = value.split(":")[-1]
        if value in {"WIN1!", "WIN1"}:
            return "WIN"
        if value in {"WDO1!", "WDO1"}:
            return "WDO"
        return value

    def get_tick(self, symbol: str) -> dict[str, Any]:
        if not self.enabled:
            raise RuntimeError("Profit RTD desativado. Defina PROFIT_RTD_ENABLED=1 para usar.")
        if not self.available:
            raise RuntimeError("Dependencia pywin32 indisponivel. Instale pywin32 para usar o Profit RTD.")

        symbol = self.normalize_symbol(symbol)
        candidates = self.symbols.get(symbol)
        if not candidates:
            raise ValueError(f"Simbolo Profit RTD nao mapeado: {symbol}")

        profit_symbol = None
        values = None
        errors = []
        for candidate in candidates:
            candidate_values = self._read_symbol(candidate)
            candidate_last = self._number(candidate_values.get("last"))
            candidate_bid = self._number(candidate_values.get("bid"))
            candidate_ask = self._number(candidate_values.get("ask"))
            if candidate_last or candidate_bid or candidate_ask:
                profit_symbol = candidate
                values = candidate_values
                break
            errors.append(candidate)
        if values is None or profit_symbol is None:
            raise ValueError(f"Profit RTD sem ultimo preco para {symbol}. Tentativas: {', '.join(errors)}")

        last = self._number(values.get("last"))
        bid = self._number(values.get("bid"))
        ask = self._number(values.get("ask"))
        if not last and bid and ask:
            last = (bid + ask) / 2
        if not last:
            raise ValueError(f"Profit RTD sem ultimo preco para {symbol}.")

        now = int(time.time())
        volume = self._number(values.get("volume"))
        last_quantity = self._number(values.get("last_quantity"))
        return {
            "symbol": symbol,
            "provider_symbol": profit_symbol,
            "bid": bid or last,
            "ask": ask or last,
            "last": last,
            "open": self._number(values.get("open")),
            "high": self._number(values.get("high")),
            "low": self._number(values.get("low")),
            "volume": volume,
            "last_quantity": last_quantity,
            "trades": int(self._number(values.get("trades")) or 0),
            "priceChangePercent": self._number(values.get("change_percent")),
            "priceChange": self._number(values.get("change_points")),
            "spread": abs((ask or last) - (bid or last)),
            "time": now,
            "source": "profit_rtd",
        }

    def get_klines(self, symbol: str, interval: str = "1m", limit: int = 500) -> pd.DataFrame:
        symbol = self.normalize_symbol(symbol)
        tick = self.get_tick(symbol)
        self._update_candle(symbol, interval, tick)
        candles = self._candles.get((symbol, interval), [])[-max(1, min(int(limit or 500), 2000)):]
        if not candles:
            raise ValueError(f"Profit RTD ainda nao formou candles para {symbol}.")
        return self._to_dataframe(candles)

    def get_24h_ticker(self, symbol: str) -> dict[str, Any]:
        tick = self.get_tick(symbol)
        return {
            "lastPrice": tick["last"],
            "priceChangePercent": tick.get("priceChangePercent") or 0,
            "priceChange": tick.get("priceChange") or 0,
            "quoteVolume": tick.get("volume") or 0,
            "volume": tick.get("volume") or 0,
            "count": tick.get("trades") or 0,
            "bid": tick.get("bid"),
            "ask": tick.get("ask"),
            "spread": tick.get("spread"),
            "provider_symbol": tick.get("provider_symbol"),
        }

    def _env_enabled(self) -> bool:
        value = os.getenv("PROFIT_RTD_ENABLED", "1").lower()
        return value in {"1", "true", "yes", "sim", "on"}

    def _build_symbol_map(self) -> dict[str, list[str]]:
        symbols = {key: list(values) for key, values in self.DEFAULT_SYMBOLS.items()}
        env_win = os.getenv("PROFIT_RTD_WIN_SYMBOL")
        env_wdo = os.getenv("PROFIT_RTD_WDO_SYMBOL")
        if env_win:
            for key in ("WIN", "WIN1", "WIN1!"):
                symbols[key].insert(0, env_win.strip().upper())
        if env_wdo:
            for key in ("WDO", "WDO1", "WDO1!"):
                symbols[key].insert(0, env_wdo.strip().upper())
        return symbols

    def _read_symbol(self, profit_symbol: str) -> dict[str, Any]:
        self._ensure_worker()
        response: queue.Queue = queue.Queue(maxsize=1)
        self._requests.put((profit_symbol, response))
        ok, payload = response.get(timeout=float(os.getenv("PROFIT_RTD_TIMEOUT", "4")))
        if ok:
            return payload
        raise RuntimeError(payload)

    def _ensure_worker(self):
        with self._worker_lock:
            if self._worker and self._worker.is_alive():
                return
            self._worker = threading.Thread(target=self._worker_loop, name="ProfitRTDWorker", daemon=True)
            self._worker.start()

    def _worker_loop(self):
        pythoncom.CoInitialize()
        excel = None
        workbook = None
        sheet = None
        rows_by_symbol = {}
        try:
            excel = win32com.client.DispatchEx("Excel.Application")
            excel.Visible = self.visible_excel
            excel.DisplayAlerts = False
            workbook = excel.Workbooks.Add()
            sheet = workbook.Worksheets(1)
            while True:
                profit_symbol, response = self._requests.get()
                try:
                    row = rows_by_symbol.get(profit_symbol)
                    if row is None:
                        row = len(rows_by_symbol) + 1
                        rows_by_symbol[profit_symbol] = row
                        for column, attr in enumerate(self.ATTRIBUTES.values(), start=1):
                            cell = sheet.Cells(row, column)
                            try:
                                cell.FormulaLocal = f'=RTD("RTDTrading.RTDServer";;"{profit_symbol}";"{attr}")'
                            except Exception:
                                cell.Formula = f'=RTD("RTDTrading.RTDServer",,"{profit_symbol}","{attr}")'

                    time.sleep(max(0.05, self.poll_delay))
                    values = {
                        key: sheet.Cells(row, column).Value
                        for column, key in enumerate(self.ATTRIBUTES.keys(), start=1)
                    }
                    response.put((True, values))
                except Exception as error:
                    response.put((False, str(error)))
        except Exception as error:
            self.last_error = str(error)
            while True:
                try:
                    _, response = self._requests.get(timeout=0.5)
                    response.put((False, self.last_error))
                except queue.Empty:
                    break

    def _update_candle(self, symbol: str, interval: str, tick: dict[str, Any]):
        interval_seconds = TIMEFRAME_SECONDS.get(interval, 3600)
        timestamp = int(tick.get("time") or time.time())
        candle_time = timestamp - (timestamp % interval_seconds)
        price = float(tick["last"])
        session_volume = float(tick.get("volume") or 0)
        last_session_volume = self._last_session_volume.get(symbol)
        if last_session_volume is None or session_volume < last_session_volume:
            volume_delta = float(tick.get("last_quantity") or 0)
        else:
            volume_delta = max(0.0, session_volume - last_session_volume)
        self._last_session_volume[symbol] = session_volume

        with self._candle_lock:
            key = (symbol, interval)
            candles = self._candles.setdefault(key, [])
            if not candles or candles[-1]["time"] != candle_time:
                candles.append({
                    "time": candle_time,
                    "open": price,
                    "high": price,
                    "low": price,
                    "close": price,
                    "volume": volume_delta,
                })
                del candles[:-2000]
                return

            current = candles[-1]
            current["high"] = max(float(current["high"]), price)
            current["low"] = min(float(current["low"]), price)
            current["close"] = price
            current["volume"] = float(current.get("volume") or 0) + volume_delta

    def _to_dataframe(self, candles: list[dict[str, Any]]) -> pd.DataFrame:
        df = pd.DataFrame(candles)
        df["open_time"] = pd.to_datetime(df["time"], unit="s", utc=True)
        df["close_time"] = df["open_time"]
        df["quote_asset_volume"] = df["volume"]
        df["number_of_trades"] = 0
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

    def _number(self, value: Any) -> float:
        if value is None:
            return 0.0
        if isinstance(value, int) and value <= -2146820000:
            return 0.0
        if isinstance(value, (int, float)) and math.isfinite(float(value)):
            return float(value)
        text = str(value).strip()
        if not text or text.startswith("#"):
            return 0.0
        text = text.replace(".", "").replace(",", ".") if "," in text else text
        try:
            return float(text)
        except ValueError:
            return 0.0
