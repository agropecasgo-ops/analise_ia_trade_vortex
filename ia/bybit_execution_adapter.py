"""
Adaptador de execucao Bybit.

Nao armazena chaves no codigo e nao envia ordens reais no modo atual.
Credenciais devem vir de .env quando a camada real for habilitada.
"""

import hashlib
import hmac
import json
import os
import time

import requests

from .broker_adapter import BrokerAdapter


class BybitExecutionAdapter(BrokerAdapter):
    name = "bybit"
    LIVE_URL = "https://api.bybit.com"
    TESTNET_URL = "https://api-testnet.bybit.com"

    def __init__(self):
        self.api_key = os.getenv("BYBIT_API_KEY", "")
        self.api_secret = os.getenv("BYBIT_API_SECRET", "")
        self.testnet = os.getenv("BYBIT_TESTNET", "true").lower() == "true"
        self.category = os.getenv("BYBIT_CATEGORY", "linear")
        self.session = requests.Session()

    @property
    def base_url(self):
        return self.TESTNET_URL if self.testnet else self.LIVE_URL

    def send_order(self, order):
        if not self.api_key or not self.api_secret:
            return {"success": False, "blocked": True, "reason": "Credenciais Bybit ausentes no .env."}
        if not self.testnet and os.getenv("EXECUTION_REQUIRE_DEMO", "true").lower() == "true":
            return {"success": False, "blocked": True, "reason": "Bybit live bloqueado. Use BYBIT_TESTNET=true."}
        payload = {
            "category": self.category,
            "symbol": order.symbol.upper(),
            "side": "Buy" if order.side.lower() == "buy" else "Sell",
            "orderType": "Market",
            "qty": str(order.quantity),
            "takeProfit": str(order.take_profit),
            "stopLoss": str(order.stop_loss),
            "timeInForce": "IOC",
            "reduceOnly": False,
        }
        return self._request("POST", "/v5/order/create", payload)

    def close_position(self, symbol):
        return {"success": False, "blocked": True, "reason": "Fechamento Bybit automatico nao habilitado nesta etapa."}

    def cancel_orders(self, symbol):
        return self._request("POST", "/v5/order/cancel-all", {"category": self.category, "symbol": symbol.upper()})

    def positions(self):
        response = self._request("GET", "/v5/position/list", {"category": self.category, "settleCoin": "USDT"})
        return response.get("result", {}).get("list", []) if response.get("success") else []

    def account(self):
        response = self._request("GET", "/v5/account/wallet-balance", {"accountType": os.getenv("BYBIT_ACCOUNT_TYPE", "UNIFIED")})
        return response.get("result", {}) if response.get("success") else {"balance": 0, "equity": 0}

    def _request(self, method, path, payload):
        if not self.api_key or not self.api_secret:
            return {"success": False, "blocked": True, "reason": "Credenciais Bybit ausentes no .env."}
        timestamp = str(int(time.time() * 1000))
        recv_window = os.getenv("BYBIT_RECV_WINDOW", "5000")
        body = json.dumps(payload, separators=(",", ":")) if method == "POST" else ""
        query = "" if method == "POST" else "&".join(f"{key}={value}" for key, value in sorted(payload.items()))
        raw = f"{timestamp}{self.api_key}{recv_window}{body or query}"
        signature = hmac.new(self.api_secret.encode(), raw.encode(), hashlib.sha256).hexdigest()
        headers = {
            "X-BAPI-API-KEY": self.api_key,
            "X-BAPI-SIGN": signature,
            "X-BAPI-SIGN-TYPE": "2",
            "X-BAPI-TIMESTAMP": timestamp,
            "X-BAPI-RECV-WINDOW": recv_window,
            "Content-Type": "application/json",
        }
        url = f"{self.base_url}{path}"
        response = self.session.request(method, url, params=payload if method == "GET" else None, data=body or None, headers=headers, timeout=10)
        data = response.json()
        ok = response.ok and int(data.get("retCode", -1)) == 0
        return {"success": ok, "broker": self.name, "testnet": self.testnet, "result": data, "reason": data.get("retMsg")}
