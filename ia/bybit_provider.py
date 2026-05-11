"""
Provider crypto institucional.

Mantem o nome arquitetural bybit_provider e reaproveita o cliente publico
Bybit ja usado pelo roteador de mercado.
"""

from .bybit_client import BybitMarketData


__all__ = ["BybitMarketData"]
