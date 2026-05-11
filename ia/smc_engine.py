"""
SMC Engine institucional.

Enriquece o SmartMoneyAnalyzer existente com MSS, mitigacao,
premium/discount e manipulacao institucional sem alterar o contrato antigo.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from .smart_money import analyze_smart_money


def _num(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if number == number else default


class SMCEngine:
    def __init__(self, candles: pd.DataFrame, signal_type: str = "neutro") -> None:
        self.df = candles.copy().dropna(subset=["open", "high", "low", "close", "volume"])
        self.signal_type = signal_type

    def analyze(self) -> dict[str, Any]:
        smc = analyze_smart_money(self.df, self.signal_type)
        premium_discount = self._premium_discount(smc)
        mitigation = self._mitigation(smc)
        mss = self._mss(smc)
        manipulation = self._manipulation(smc, premium_discount)
        smc.update({
            "mss": mss,
            "premium_discount": premium_discount,
            "mitigation": mitigation,
            "manipulation": manipulation,
            "institutional_intent": self._intent(smc, manipulation, premium_discount),
        })
        smc["confirmations"] = list(dict.fromkeys((smc.get("confirmations") or []) + self._confirmations(smc)))
        smc["invalidations"] = list(dict.fromkeys((smc.get("invalidations") or []) + self._invalidations(smc)))
        return smc

    def _premium_discount(self, smc: dict[str, Any]) -> dict[str, Any]:
        structure = smc.get("structure", {})
        last_high = _num((structure.get("last_high") or {}).get("price"))
        last_low = _num((structure.get("last_low") or {}).get("price"))
        price = float(self.df["close"].iloc[-1])
        if not last_high or not last_low or last_high <= last_low:
            frame = self.df.tail(80)
            last_high = float(frame["high"].max())
            last_low = float(frame["low"].min())
        equilibrium = (last_high + last_low) / 2
        zone = "premium" if price > equilibrium else "discount" if price < equilibrium else "equilibrium"
        return {
            "high": round(last_high, 8),
            "low": round(last_low, 8),
            "equilibrium": round(equilibrium, 8),
            "zone": zone,
            "distance_pct": round(abs(price - equilibrium) / max(price, 0.00000001) * 100, 3),
        }

    def _mitigation(self, smc: dict[str, Any]) -> dict[str, Any]:
        price = float(self.df["close"].iloc[-1])

        def touched(zone: dict[str, Any] | None) -> bool:
            if not zone:
                return False
            low = _num(zone.get("low", zone.get("price")))
            high = _num(zone.get("high", zone.get("price")))
            return bool(low and high and low <= price <= high)

        order_block = smc.get("relevant_order_block") or smc.get("nearest_order_block")
        fvg = smc.get("relevant_fvg")
        return {
            "order_block_mitigated": touched(order_block),
            "fvg_filled": touched(fvg),
            "active_zone": "order_block" if touched(order_block) else "fvg" if touched(fvg) else None,
        }

    def _mss(self, smc: dict[str, Any]) -> dict[str, Any]:
        structure = smc.get("structure", {})
        bos = structure.get("bos")
        choch = structure.get("choch")
        detected = choch in ["bullish", "bearish"] and bos == choch
        return {
            "detected": bool(detected),
            "side": choch if detected else "none",
            "level": structure.get("break_level"),
        }

    def _manipulation(self, smc: dict[str, Any], premium_discount: dict[str, Any]) -> dict[str, Any]:
        sweep = smc.get("liquidity_sweep", {})
        false_breakout = smc.get("false_breakout", {})
        inducement = smc.get("inducement", {})
        detected = bool(sweep.get("detected") or false_breakout.get("detected") or inducement.get("detected"))
        kind = "none"
        if false_breakout.get("detected"):
            kind = "false_breakout"
        elif sweep.get("detected"):
            kind = "liquidity_sweep"
        elif inducement.get("detected"):
            kind = "inducement"
        return {
            "detected": detected,
            "type": kind,
            "zone": premium_discount.get("zone"),
            "description": "Captura/manipulacao institucional detectada." if detected else "Sem manipulacao institucional clara.",
        }

    def _intent(self, smc: dict[str, Any], manipulation: dict[str, Any], premium_discount: dict[str, Any]) -> str:
        bias = smc.get("institutional_bias", "neutral")
        if manipulation.get("type") == "false_breakout":
            direction = (smc.get("false_breakout") or {}).get("direction")
            if direction == "bullish_failed":
                return "sell_trap_reversal"
            if direction == "bearish_failed":
                return "buy_trap_reversal"
        if bias == "bullish" and premium_discount.get("zone") == "discount":
            return "accumulation_to_markup"
        if bias == "bearish" and premium_discount.get("zone") == "premium":
            return "distribution_to_markdown"
        return bias

    def _confirmations(self, smc: dict[str, Any]) -> list[str]:
        items = []
        if smc.get("mss", {}).get("detected"):
            items.append(f"MSS {smc['mss']['side']} detectado.")
        if smc.get("mitigation", {}).get("active_zone"):
            items.append(f"Mitigacao em {smc['mitigation']['active_zone']}.")
        if smc.get("premium_discount", {}).get("zone") in ["premium", "discount"]:
            items.append(f"Preco em zona {smc['premium_discount']['zone']}.")
        return items

    def _invalidations(self, smc: dict[str, Any]) -> list[str]:
        items = []
        if smc.get("manipulation", {}).get("type") == "inducement":
            items.append("Inducement ativo; evitar entrada sem confirmacao.")
        return items


def build_smc_context(candles: pd.DataFrame, signal_type: str = "neutro") -> dict[str, Any]:
    return SMCEngine(candles, signal_type).analyze()
