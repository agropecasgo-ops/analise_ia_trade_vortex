import unittest

from ia.institutional_mode_engine import build_institutional_mode
from ia.institutional_narrator import build_institutional_narrative


def payload(**overrides):
    base = {
        "direction": "BUY",
        "score": 92,
        "confidence": 88,
        "status": "HIGH_PROBABILITY",
        "macroContext": {
            "direction": "BUY",
            "lateral": False,
            "volatility": {"state": "GOOD"},
        },
        "news": {"impact": "UNKNOWN", "blocking": False},
        "liquidity": {
            "nearest": {"side": "sell_side", "price": 100},
            "sweep": {"detected": True, "side": "sell_side", "level": 99},
        },
        "marketStructure": {"valid": True, "direction": "BUY"},
        "timing": {"confirmed": True},
        "risk": {"allowed": True, "rejections": []},
        "tradePlan": {
            "entry": 101,
            "stopLoss": 98,
            "riskReward": 1.8,
            "entryCondition": "Confirmar candle gatilho.",
            "cancelCondition": "Cancelar se perder estrutura.",
        },
        "institutionalBehavior": {
            "smartMoneyBias": "bullish",
            "falseBreakout": {"detected": False},
            "inducement": {"detected": False},
        },
    }
    base.update(overrides)
    return base


class InstitutionalModeAndNarratorTests(unittest.TestCase):
    def test_strict_mode_allows_only_high_quality_context(self):
        result = build_institutional_mode(payload())

        self.assertEqual(result["status"], "OPERAR")
        self.assertTrue(result["canOperate"])

    def test_strict_mode_blocks_lateral_market(self):
        data = payload(macroContext={"direction": "NEUTRAL", "lateral": True, "volatility": {"state": "GOOD"}})

        result = build_institutional_mode(data)

        self.assertEqual(result["status"], "MERCADO_PERIGOSO")
        self.assertFalse(result["canOperate"])
        self.assertIn("Mercado lateral bloqueado no Modo Institucional.", result["blockers"])

    def test_strict_mode_blocks_low_score(self):
        result = build_institutional_mode(payload(score=70))

        self.assertEqual(result["status"], "AGUARDAR")
        self.assertFalse(result["canOperate"])

    def test_narrator_returns_required_sections(self):
        mode = build_institutional_mode(payload())
        narrative = build_institutional_narrative(payload(), mode)

        self.assertEqual(narrative["status"], "OPERAR")
        self.assertIn("probableDirection", narrative["sections"])
        self.assertIn("relevantLiquidity", narrative["sections"])
        self.assertIn("operationRisk", narrative["sections"])
        self.assertIn("cancelCondition", narrative["sections"])


if __name__ == "__main__":
    unittest.main()
