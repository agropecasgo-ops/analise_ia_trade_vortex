"""
Helper de contrato para streams websocket usados pelo frontend.
"""

from __future__ import annotations


BINANCE_WS_BASE = "wss://stream.binance.com:9443/ws"


def build_binance_kline_stream(symbol: str, timeframe: str) -> dict[str, str]:
    stream = f"{symbol.lower()}@kline_{timeframe}"
    return {
        "provider": "binance",
        "stream": stream,
        "url": f"{BINANCE_WS_BASE}/{stream}",
    }
