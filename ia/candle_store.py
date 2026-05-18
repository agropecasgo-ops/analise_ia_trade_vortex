"""
Cache local persistente de candles OHLCV.

Mantem candles padronizados em SQLite para acelerar leituras recentes e oferecer
fallback quando um provider externo fica lento ou indisponivel.
"""

from __future__ import annotations

import os
import sqlite3
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterable

import pandas as pd


DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "platform.db")
CACHE_MAX_AGE_DAYS = int(os.getenv("CANDLE_STORE_MAX_AGE_DAYS", "30"))
TIMEFRAME_ALIASES = {
    "1": "1m",
    "1m": "1m",
    "5": "5m",
    "5m": "5m",
    "15": "15m",
    "15m": "15m",
    "60": "1h",
    "60m": "1h",
    "1h": "1h",
    "4h": "4h",
    "240": "4h",
    "240m": "4h",
    "1d": "1d",
    "d": "1d",
    "1w": "1w",
    "w": "1w",
}

_LOCK = threading.Lock()


@contextmanager
def _connect():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _init_db(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS candles (
            symbol TEXT NOT NULL,
            timeframe TEXT NOT NULL,
            time INTEGER NOT NULL,
            open REAL NOT NULL,
            high REAL NOT NULL,
            low REAL NOT NULL,
            close REAL NOT NULL,
            volume REAL NOT NULL DEFAULT 0,
            provider TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (symbol, timeframe, time)
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_candles_symbol_timeframe_time
        ON candles(symbol, timeframe, time DESC)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_candles_updated_at
        ON candles(updated_at)
    """)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_symbol(symbol: str) -> str:
    value = (symbol or "").replace("-", "").replace("/", "").upper().strip()
    if ":" in value:
        value = value.split(":")[-1]
    if value in {"WIN1!", "WIN1"}:
        return "WIN"
    if value in {"WDO1!", "WDO1"}:
        return "WDO"
    return value


def _normalize_timeframe(timeframe: str) -> str:
    value = str(timeframe or "1h").strip().lower().replace(" ", "")
    return TIMEFRAME_ALIASES.get(value, value or "1h")


def _to_epoch_seconds(value: Any) -> int | None:
    if value is None:
        return None
    try:
        if hasattr(value, "timestamp"):
            return int(value.timestamp())
        if isinstance(value, str):
            parsed = pd.to_datetime(value, utc=True, errors="coerce")
            if pd.isna(parsed):
                return None
            return int(parsed.timestamp())
        number = float(value)
        if number > 10_000_000_000:
            number = number / 1000
        return int(number)
    except (TypeError, ValueError, OverflowError):
        return None


def _records_from_dataframe(
    symbol: str,
    timeframe: str,
    candles: pd.DataFrame,
    provider: str,
    updated_at: str,
) -> list[tuple[Any, ...]]:
    records = []
    for idx, row in candles.iterrows():
        candle_time = _to_epoch_seconds(row.get("time") if hasattr(row, "get") and "time" in row else idx)
        if candle_time is None:
            continue
        record = _record_from_mapping(symbol, timeframe, row.to_dict(), provider, updated_at, candle_time)
        if record:
            records.append(record)
    return records


def _records_from_iterable(
    symbol: str,
    timeframe: str,
    candles: Iterable[dict[str, Any]],
    provider: str,
    updated_at: str,
) -> list[tuple[Any, ...]]:
    records = []
    for candle in candles:
        candle_time = _to_epoch_seconds(
            candle.get("time") or candle.get("open_time") or candle.get("timestamp")
        )
        record = _record_from_mapping(symbol, timeframe, candle, provider, updated_at, candle_time)
        if record:
            records.append(record)
    return records


def _record_from_mapping(
    symbol: str,
    timeframe: str,
    candle: dict[str, Any],
    provider: str,
    updated_at: str,
    candle_time: int | None,
) -> tuple[Any, ...] | None:
    if candle_time is None:
        return None
    try:
        return (
            symbol,
            timeframe,
            int(candle_time),
            float(candle["open"]),
            float(candle["high"]),
            float(candle["low"]),
            float(candle["close"]),
            float(candle.get("volume") or 0),
            str(candle.get("provider") or provider or "unknown"),
            updated_at,
        )
    except (KeyError, TypeError, ValueError):
        return None


def _empty_frame() -> pd.DataFrame:
    return pd.DataFrame(columns=[
        "symbol",
        "timeframe",
        "time",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "provider",
        "updated_at",
        "close_time",
        "quote_asset_volume",
        "number_of_trades",
        "taker_buy_base_volume",
        "taker_buy_quote_volume",
    ])


def _frame_from_rows(rows: list[sqlite3.Row]) -> pd.DataFrame:
    if not rows:
        return _empty_frame()
    df = pd.DataFrame([dict(row) for row in rows])
    df = df.sort_values("time")
    df["open_time"] = pd.to_datetime(df["time"], unit="s", utc=True)
    df["close_time"] = df["open_time"]
    df["quote_asset_volume"] = df["volume"]
    df["number_of_trades"] = 0
    df["taker_buy_base_volume"] = 0
    df["taker_buy_quote_volume"] = 0
    df = df.set_index("open_time")
    for column in ["open", "high", "low", "close", "volume"]:
        df[column] = pd.to_numeric(df[column], errors="coerce").astype(float)
    return df


def save_candles(symbol, timeframe, candles, provider):
    """Salva ou atualiza uma colecao de candles no cache local."""
    symbol = _normalize_symbol(symbol)
    timeframe = _normalize_timeframe(timeframe)
    provider = str(provider or "unknown")
    updated_at = _now_iso()
    if candles is None:
        return 0
    if isinstance(candles, pd.DataFrame):
        records = _records_from_dataframe(symbol, timeframe, candles, provider, updated_at)
    else:
        records = _records_from_iterable(symbol, timeframe, candles, provider, updated_at)
    if not records:
        return 0
    with _LOCK, _connect() as conn:
        _init_db(conn)
        conn.executemany("""
            INSERT INTO candles(
                symbol, timeframe, time, open, high, low, close, volume, provider, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(symbol, timeframe, time) DO UPDATE SET
                open = excluded.open,
                high = excluded.high,
                low = excluded.low,
                close = excluded.close,
                volume = excluded.volume,
                provider = excluded.provider,
                updated_at = excluded.updated_at
        """, records)
    return len(records)


def get_candles(symbol, timeframe, limit):
    """Retorna candles do cache como DataFrame OHLCV padronizado."""
    symbol = _normalize_symbol(symbol)
    timeframe = _normalize_timeframe(timeframe)
    limit = max(1, min(int(limit or 500), 5000))
    with _LOCK, _connect() as conn:
        _init_db(conn)
        rows = conn.execute("""
            SELECT symbol, timeframe, time, open, high, low, close, volume, provider, updated_at
            FROM candles
            WHERE symbol = ? AND timeframe = ?
            ORDER BY time DESC
            LIMIT ?
        """, (symbol, timeframe, limit)).fetchall()
    return _frame_from_rows(rows)


def upsert_candle(symbol, timeframe, candle):
    """Insere ou atualiza um unico candle OHLCV."""
    provider = candle.get("provider") if isinstance(candle, dict) else None
    return save_candles(symbol, timeframe, [candle], provider)


def clear_old_cache():
    """Remove candles que nao sao atualizados ha CANDLE_STORE_MAX_AGE_DAYS dias."""
    cutoff = datetime.fromtimestamp(
        time.time() - (CACHE_MAX_AGE_DAYS * 24 * 60 * 60),
        tz=timezone.utc,
    ).isoformat()
    with _LOCK, _connect() as conn:
        _init_db(conn)
        cursor = conn.execute("DELETE FROM candles WHERE updated_at < ?", (cutoff,))
    return cursor.rowcount
