import unittest

from ia.adaptive_learning_engine import build_adaptive_status
from ia.performance_stats_engine import build_performance_stats


def signal(status, asset="BTCUSDT", timeframe="15m", rr=1.5, hour="10"):
    return {
        "asset": asset,
        "timeframe": timeframe,
        "direction": "BUY",
        "status": status,
        "riskReward": rr,
        "partial_result": f"{rr if 'Alvo' in status else -1}%",
        "createdAt": f"2026-05-12T{hour}:00:00+00:00",
        "closedAt": f"2026-05-12T{hour}:10:00+00:00",
        "breakEven": {"enabled": status == "Break Even ativado"},
        "liquidityUsed": {"type": "sell_side"},
        "macroContext": {"volatility": "GOOD"},
    }


class PerformanceAndAdaptiveTests(unittest.TestCase):
    def test_performance_returns_core_metrics(self):
        history = [
            signal("Alvo final atingido", rr=2.0),
            signal("Stop atingido", rr=1.2),
            signal("Alvo 1 atingido", asset="ETHUSDT", timeframe="5m", rr=1.5),
        ]

        result = build_performance_stats(history, [])

        self.assertEqual(result["totalSignals"], 3)
        self.assertAlmostEqual(result["winRate"], 66.67)
        self.assertIn("BTCUSDT", result["winRateByAsset"])
        self.assertIn("15m", result["winRateByTimeframe"])
        self.assertIn("byAssetTimeframe", result)

    def test_adaptive_reduces_aggressiveness_after_losses(self):
        history = [
            signal("Alvo final atingido", rr=2.0),
            signal("Stop atingido", rr=1.2),
            signal("Stop atingido", rr=1.1),
            signal("Stop atingido", rr=1.0),
        ]
        performance = build_performance_stats(history, [])

        adaptive = build_adaptive_status(performance, history)

        self.assertEqual(adaptive["aggressiveness"], "REDUZIDA")
        self.assertGreaterEqual(adaptive["minimumScoreAdjustment"], 6)
        self.assertTrue(adaptive["filters"]["reduceAfterLosingStreak"])

    def test_adaptive_contextual_fields_are_available(self):
        history = [
            signal("Alvo final atingido", asset="BTCUSDT", timeframe="15m", rr=2.0, hour="10"),
            signal("Stop atingido", asset="BTCUSDT", timeframe="15m", rr=1.2, hour="11"),
            signal("Alvo final atingido", asset="ETHUSDT", timeframe="5m", rr=1.5, hour="10"),
            signal("Stop atingido", asset="ETHUSDT", timeframe="5m", rr=1.0, hour="11"),
        ]
        performance = build_performance_stats(history, [])
        adaptive = build_adaptive_status(performance, history)

        self.assertIn("winRateContextual", adaptive)
        self.assertIn("bestTimeframes", adaptive)
        self.assertIn("bestAssets", adaptive)
        self.assertIn("weakContexts", adaptive)
        self.assertIn("strongContexts", adaptive)
        self.assertIn("adaptiveRecommendation", adaptive)
        self.assertIsInstance(adaptive["contextSamples"], list)
        self.assertGreaterEqual(len(adaptive["contextSamples"]), 1)


if __name__ == "__main__":
    unittest.main()
