import unittest
from unittest.mock import patch

import pandas as pd

from ia.institutional_unified_engine import build_institutional_unified_analysis


REQUIRED_FIELDS = {
    "asset",
    "assetType",
    "timeframe",
    "operationalMode",
    "operationalContext",
    "direction",
    "confidence",
    "score",
    "status",
    "marketStructure",
    "liquidity",
    "institutionalBehavior",
    "macroContext",
    "probabilities",
    "tradePlan",
    "risk",
    "timing",
    "news",
    "aiExplanation",
    "layersUsed",
    "createdAt",
}


def candles(close=100.0):
    rows = []
    price = close - 3
    for index in range(80):
        open_price = price
        close_price = price + 0.1
        rows.append({
            "open": open_price,
            "high": max(open_price, close_price) + 0.25,
            "low": min(open_price, close_price) - 0.25,
            "close": close_price,
            "volume": 1000 + index,
        })
        price = close_price
    return pd.DataFrame(rows, index=pd.date_range("2026-01-01", periods=80, freq="min"))


def macro(direction="BUY", blocked=False):
    return {
        "direction": "NEUTRAL" if blocked else direction,
        "htf_direction": direction,
        "blocked": blocked,
        "blockers": ["Mercado lateral: H1/M15 sem direcao limpa."] if blocked else [],
        "trend": {"aligned": not blocked, "confirmed_by_m5": not blocked},
        "volatility": {"state": "GOOD", "good": True},
    }


def structure(direction="BUY", valid=True):
    return {
        "valid": valid,
        "direction": direction if valid else "NEUTRAL",
        "blockers": [] if valid else ["Estrutura sem BOS/CHOCH acionavel."],
        "liquidity": {"zones": [{"side": "sell_side", "price": 98.0}], "nearest": {"side": "sell_side", "price": 98.0}},
        "liquidity_sweep": {"detected": valid, "direction": direction, "side": "sell_side", "level": 98.0},
        "order_block": {"valid": valid, "direction": direction, "low": 97.0, "high": 98.5},
        "fvg": {"valid": False},
        "institutional_zone": {"valid": valid, "low": 97.0, "high": 98.5},
        "swings": {"lows": [{"price": 97.0}], "highs": [{"price": 105.0}]},
    }


def confirmation(direction="BUY", valid=True):
    return {
        "valid": valid,
        "direction": direction if valid else "NEUTRAL",
        "volume": {"strong": valid},
        "candle": {"strong": valid, "direction": direction if valid else "NEUTRAL"},
        "false_breakout": {"detected": False},
        "blockers": [] if valid else ["Candle gatilho fraco."],
    }


def layered(direction="BUY", generated=True, score=86):
    return {
        "signal": {
            "generated": generated,
            "direction_code": direction if generated else "NEUTRAL",
            "entry_price": 100.0,
            "stop_loss": 97.0,
            "take_profit_1": 105.0,
            "take_profit_2": 110.0,
            "risk_reward": 1.67,
            "reason": "Sinal liberado por camadas institucionais.",
            "risk_gate": {"allowed": True, "blockers": []},
            "validated_layer": "ai_score",
        },
        "ai_score": {"score": score, "blockers": [] if score >= 80 else ["Score abaixo do minimo."]},
    }


class InstitutionalUnifiedEngineTests(unittest.TestCase):
    def analyze(self, **overrides):
        with patch("ia.institutional_unified_engine.MacroContextEngine") as macro_cls, \
             patch("ia.institutional_unified_engine.MarketStructureEngine") as structure_cls, \
             patch("ia.institutional_unified_engine.ConfirmationEngine") as confirmation_cls, \
             patch("ia.institutional_unified_engine.build_layered_signal") as layered_fn, \
             patch("ia.institutional_unified_engine.read_technical") as technical_fn, \
             patch("ia.institutional_unified_engine.read_volume") as volume_fn, \
             patch("ia.institutional_unified_engine.read_tape") as tape_fn, \
             patch("ia.institutional_unified_engine.analyze_smart_money") as smart_money_fn, \
             patch("ia.institutional_unified_engine.build_smc_context") as smc_fn, \
             patch("ia.institutional_unified_engine.build_wyckoff_context") as wyckoff_fn:
            macro_cls.return_value.analyze.return_value = overrides.get("macro", macro())
            structure_cls.return_value.analyze.return_value = overrides.get("structure", structure())
            confirmation_cls.return_value.analyze.return_value = overrides.get("confirmation", confirmation())
            layered_fn.return_value = overrides.get("layered", layered())
            technical_fn.side_effect = overrides.get("technical_error")
            if not overrides.get("technical_error"):
                technical_fn.return_value = overrides.get("technical", {"signal": "NEUTRAL"})
            volume_fn.return_value = overrides.get("volume", {"signal": "NEUTRAL_VOLUME", "dominant_side": "BALANCED"})
            tape_fn.return_value = overrides.get("tape", {"order_flow_bias": "BALANCED_FLOW"})
            smart_money_fn.return_value = overrides.get("smart_money", {"institutional_bias": "neutral", "false_breakout": {"detected": False}})
            smc_fn.return_value = overrides.get("smc", {"institutional_bias": "neutral", "false_breakout": {"detected": False}, "liquidity_sweep": {"detected": False}})
            wyckoff_fn.return_value = overrides.get("wyckoff", {})
            return build_institutional_unified_analysis(
                candles(),
                "TEST",
                "1m",
                "crypto",
                operational_mode=overrides.get("operational_mode", "moderado"),
            )

    def test_payload_always_returns_required_fields(self):
        result = self.analyze()

        self.assertTrue(REQUIRED_FIELDS.issubset(result.keys()))
        self.assertTrue({"buy", "sell", "sideways"}.issubset(result["probabilities"].keys()))
        self.assertTrue({
            "entry",
            "stopLoss",
            "takeProfit1",
            "takeProfit2",
            "takeProfitFinal",
            "riskReward",
            "entryCondition",
            "cancelCondition",
        }.issubset(result["tradePlan"].keys()))

    def test_low_score_returns_no_trade_or_wait_confirmation(self):
        result = self.analyze(
            macro=macro("BUY", blocked=True),
            structure=structure("BUY", valid=False),
            confirmation=confirmation("BUY", valid=False),
            layered=layered("BUY", generated=False, score=20),
        )

        self.assertIn(result["status"], {"NO_TRADE", "WAIT_CONFIRMATION"})
        self.assertEqual(result["direction"], "NEUTRAL")

    def test_direction_is_limited_to_contract_values(self):
        result = self.analyze()

        self.assertIn(result["direction"], {"BUY", "SELL", "NEUTRAL"})

    def test_auxiliary_module_error_does_not_break_engine(self):
        result = self.analyze(technical_error=RuntimeError("technical_reader_failed"))

        self.assertTrue(REQUIRED_FIELDS.issubset(result.keys()))
        self.assertEqual(result["diagnostics"]["errors"]["technical_reader"], "technical_reader_failed")

    def test_auxiliary_indicators_do_not_generate_signal_alone(self):
        result = self.analyze(
            macro=macro("BUY", blocked=True),
            structure=structure("BUY", valid=False),
            confirmation=confirmation("BUY", valid=False),
            layered=layered("BUY", generated=False, score=0),
            technical={"signal": "BUY"},
            volume={"signal": "BULLISH_VOLUME", "dominant_side": "BUYER"},
            tape={"order_flow_bias": "BUY_FLOW"},
            wyckoff={"phase": "acumulacao"},
        )

        self.assertEqual(result["direction"], "NEUTRAL")
        self.assertNotEqual(result["status"], "HIGH_PROBABILITY")
        self.assertFalse(result["institutionalBehavior"]["volume"].get("can_generate_signal", False))
        self.assertGreater(result["probabilities"]["buy"], 0)

    def test_smc_invalidated_without_false_breakout_is_not_dangerous_market(self):
        result = self.analyze(
            macro=macro("BUY", blocked=True),
            structure=structure("BUY", valid=False),
            confirmation=confirmation("BUY", valid=False),
            smc={"institutional_bias": "neutral", "invalidated": True, "false_breakout": {"detected": False}},
        )

        self.assertNotEqual(result["status"], "DANGEROUS_MARKET")
        self.assertIn(result["status"], {"NO_TRADE", "WAIT_CONFIRMATION"})

    def test_false_breakout_remains_dangerous_market(self):
        result = self.analyze(
            smc={"institutional_bias": "neutral", "invalidated": True, "false_breakout": {"detected": True, "level": 100}},
        )

        self.assertEqual(result["status"], "DANGEROUS_MARKET")

    def test_inducement_alone_is_not_dangerous_market(self):
        result = self.analyze(
            macro=macro("BUY", blocked=True),
            structure=structure("BUY", valid=False),
            confirmation=confirmation("BUY", valid=False),
            smc={
                "institutional_bias": "neutral",
                "invalidated": True,
                "false_breakout": {"detected": False},
                "manipulation": {"detected": True, "type": "inducement"},
            },
        )

        self.assertNotEqual(result["status"], "DANGEROUS_MARKET")

    def test_aggressive_mode_reduces_entry_thresholds(self):
        result = self.analyze(
            operational_mode="agressivo",
            layered=layered("BUY", generated=True, score=58),
            confirmation=confirmation("BUY", valid=False),
            volume={"signal": "BULLISH_VOLUME", "dominant_side": "BUYER"},
            tape={"order_flow_bias": "BUY_FLOW"},
        )

        self.assertEqual(result["operationalMode"], "agressivo")
        self.assertEqual(result["status"], "HIGH_PROBABILITY")
        self.assertEqual(result["direction"], "BUY")
        self.assertFalse(result["operationalContext"]["thresholds"]["requireStructure"])

    def test_moderate_mode_keeps_balanced_confirmation(self):
        result = self.analyze(
            operational_mode="moderado",
            layered=layered("BUY", generated=True, score=58),
            confirmation=confirmation("BUY", valid=False),
            volume={"signal": "BULLISH_VOLUME", "dominant_side": "BUYER"},
            tape={"order_flow_bias": "BUY_FLOW"},
        )

        self.assertEqual(result["operationalMode"], "moderado")
        self.assertEqual(result["status"], "WAIT_CONFIRMATION")
        self.assertEqual(result["direction"], "NEUTRAL")

    def test_conservative_mode_requires_maximum_confluence(self):
        result = self.analyze(
            operational_mode="conservador",
            layered=layered("BUY", generated=True, score=55),
        )

        self.assertEqual(result["operationalMode"], "conservador")
        self.assertEqual(result["status"], "WAIT_CONFIRMATION")
        self.assertEqual(result["direction"], "NEUTRAL")
        self.assertTrue(result["operationalContext"]["thresholds"]["requireConfirmation"])


if __name__ == "__main__":
    unittest.main()
