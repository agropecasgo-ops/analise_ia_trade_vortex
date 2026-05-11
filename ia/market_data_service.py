"""
Contrato leve para dados de mercado da Live.

O roteador existente continua sendo a fonte principal; este modulo formaliza o
payload consumido pela tela sem acoplar a Live diretamente ao provedor.
"""

from __future__ import annotations

from typing import Any


def build_market_data_snapshot(meta: dict[str, Any], ticker: dict[str, Any]) -> dict[str, Any]:
    return {
        "market": meta.get("market"),
        "market_label": meta.get("market_label"),
        "source": meta.get("source"),
        "status": meta.get("market_status"),
        "message": meta.get("message"),
        "streaming": meta.get("streaming", False),
        "last_price": ticker.get("lastPrice"),
        "change_percent": ticker.get("priceChangePercent", 0),
        "quote_volume": ticker.get("quoteVolume", 0),
    }
