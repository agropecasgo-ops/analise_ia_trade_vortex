import unittest
from unittest.mock import patch

import pandas as pd

from ia.layered_signal_engine import build_layered_signal
from ia.live_signals import BreakEvenManager, SignalRiskManager, SignalScoreService, STATUS_BE


def candles(close=100.0, direction="BUY"):
    rows = []
    price = close - 3 if direction == "BUY" else close + 3
    for index in range(60):
        step = 0.1 if direction == "BUY" else -0.1
        open_price = price
        close_price = price + step
        rows.append({
            "open": open_price,
            "high": max(open_price, close_price) + 0.25,
            "low": min(open_price, close_price) - 0.25,
            "close": close_price,
            "volume": 1000 + index,
        })
        price = close_price
    return pd.DataFrame(rows, index=pd.date_range("2026-01-01", periods=60, freq="min"))


def macro(direction="BUY", *, blocked=False, blocker=None, volatility="GOOD"):
    blockers = [blocker] if blocker else []
    return {
        "direction": "NEUTRAL" if blocked else direction,
        "htf_direction": direction,
        "blocked": blocked,
        "blockers": blockers,
        "trend": {"aligned": not blocked, "confirmed_by_m5": not blocked},
        "volatility": {"state": volatility, "good": volatility != "LOW"},
    }


def structure(direction="BUY", *, valid=True):
    return {
        "valid": valid,
        "direction": direction if valid else "NEUTRAL",
        "blockers": [] if valid else ["Estrutura sem BOS/CHOCH acionavel."],
        "liquidity_sweep": {"detected": valid, "direction": direction},
        "order_block": {"valid": valid, "direction": direction, "low": 94.0, "high": 96.0} if direction == "BUY" else {"valid": valid, "direction": direction, "low": 104.0, "high": 106.0},
        "fvg": {"valid": False},
        "institutional_zone": {"valid": valid, "low": 94.0, "high": 96.0} if direction == "BUY" else {"valid": valid, "low": 104.0, "high": 106.0},
        "swings": {
            "lows": [{"price": 95.0}],
            "highs": [{"price": 105.0}],
        },
    }


def confirmation(direction="BUY", *, valid=True, strong_volume=True):
    return {
        "valid": valid,
        "direction": direction if valid else "NEUTRAL",
        "volume": {"strong": strong_volume},
        "candle": {"strong": valid, "direction": direction if valid else "NEUTRAL"},
        "blockers": [] if valid else ["Candle gatilho fraco."],
    }


class LayeredSignalRuleTests(unittest.TestCase):
    def analyze(self, *, direction="BUY", macro_ctx=None, market_structure=None, confirm=None, legacy=None):
        return self.analyze_with_min_score(
            direction=direction,
            macro_ctx=macro_ctx,
            market_structure=market_structure,
            confirm=confirm,
            legacy=legacy,
        )

    def analyze_with_min_score(self, *, direction="BUY", min_score=80, macro_ctx=None, market_structure=None, confirm=None, legacy=None):
        macro_ctx = macro_ctx if macro_ctx is not None else macro(direction)
        market_structure = market_structure if market_structure is not None else structure(direction)
        confirm = confirm if confirm is not None else confirmation(direction)
        with patch("ia.layered_signal_engine.MacroContextEngine") as macro_cls, \
             patch("ia.layered_signal_engine.MarketStructureEngine") as structure_cls, \
             patch("ia.layered_signal_engine.ConfirmationEngine") as confirmation_cls:
            macro_cls.return_value.analyze.return_value = macro_ctx
            structure_cls.return_value.analyze.return_value = market_structure
            confirmation_cls.return_value.analyze.return_value = confirm
            return build_layered_signal(
                "TEST",
                {"1m": candles(direction=direction), "5m": candles(direction=direction), "15m": candles(direction=direction), "1h": candles(direction=direction)},
                "1m",
                legacy_filters=legacy,
                min_score=min_score,
            )

    def test_valid_buy_signal_requires_all_layers_and_score_80(self):
        result = self.analyze(direction="BUY")

        self.assertTrue(result["signal"]["generated"])
        self.assertEqual(result["signal"]["direction_code"], "BUY")
        self.assertGreaterEqual(result["ai_score"]["score"], 80)
        self.assertTrue(result["macro_context"]["direction"] == "BUY")
        self.assertTrue(result["market_structure"]["valid"])
        self.assertTrue(result["confirmation"]["valid"])

    def test_valid_sell_signal_requires_all_layers_and_score_80(self):
        result = self.analyze(direction="SELL")

        self.assertTrue(result["signal"]["generated"])
        self.assertEqual(result["signal"]["direction_code"], "SELL")
        self.assertGreaterEqual(result["ai_score"]["score"], 80)

    def test_entry_timing_no_entry_blocks_signal_even_with_confirmed_layers(self):
        with patch("ia.layered_signal_engine.build_entry_timing") as timing_fn:
            timing_fn.return_value = {
                "status": "NO_ENTRY",
                "label": "Não entrar",
                "entry_allowed": False,
                "reason": "Timing institucional nao liberou entrada.",
            }
            result = self.analyze(direction="BUY")

        self.assertFalse(result["signal"]["generated"])
        self.assertEqual(result["signal"]["entry_status"], "Não entrar")
        self.assertIn("Timing institucional", result["signal"]["reason"])

    def test_legacy_indicators_cannot_generate_signal_alone(self):
        result = self.analyze(
            direction="BUY",
            macro_ctx=macro("BUY", blocked=True, blocker="Mercado lateral: H1/M15 sem direcao limpa."),
            market_structure=structure("BUY", valid=False),
            confirm=confirmation("BUY", valid=False),
            legacy={
                "technical": {"signal": "BUY"},
                "volume": {"signal": "BULLISH_VOLUME"},
                "smc": {"institutional_bias": "bullish"},
                "tape_reading": {"order_flow_bias": "BUY_FLOW"},
            },
        )

        self.assertFalse(result["signal"]["generated"])
        self.assertEqual(result["legacy_filters"]["role"], "auxiliary_filter_only")
        self.assertFalse(result["legacy_filters"]["can_generate_signal"])

    def test_layered_engine_is_required_for_live_signal_service(self):
        allowed, reasons = SignalScoreService().allowed({
            "state": "BUY_CONFIRMED",
            "confluence_score": 95,
            "probable_direction": "BUY",
        })

        self.assertFalse(allowed)
        self.assertIn("Engine por camadas nao gerou sinal.", reasons)

    def test_score_below_80_blocks_signal(self):
        result = self.analyze(
            direction="BUY",
            market_structure={**structure("BUY"), "liquidity_sweep": {"detected": False}},
        )

        self.assertFalse(result["signal"]["generated"])
        self.assertLess(result["ai_score"]["base_score"], 80)

    def test_mode_min_score_can_release_layered_signal_without_indicator_only_generation(self):
        result = self.analyze_with_min_score(
            direction="BUY",
            min_score=65,
            market_structure={**structure("BUY"), "liquidity_sweep": {"detected": False}},
        )

        self.assertTrue(result["signal"]["generated"])
        self.assertEqual(result["ai_score"]["threshold"], 65)
        self.assertEqual(result["legacy_filters"]["role"], "auxiliary_filter_only")
        self.assertFalse(result["legacy_filters"]["can_generate_signal"])

    def test_sideways_market_blocks_signal(self):
        result = self.analyze(
            direction="BUY",
            macro_ctx=macro("BUY", blocked=True, blocker="Mercado lateral: H1/M15 sem direcao limpa."),
        )

        self.assertFalse(result["signal"]["generated"])
        self.assertIn("Mercado lateral", result["signal"]["reason"])

    def test_low_volatility_blocks_signal(self):
        result = self.analyze(
            direction="BUY",
            macro_ctx=macro("BUY", blocked=True, blocker="Volatilidade baixa: sem expansao suficiente para entrada.", volatility="LOW"),
        )

        self.assertFalse(result["signal"]["generated"])
        self.assertIn("Volatilidade baixa", result["signal"]["reason"])

    def test_missing_confirmation_blocks_signal(self):
        result = self.analyze(direction="BUY", confirm=confirmation("BUY", valid=False))

        self.assertFalse(result["signal"]["generated"])
        self.assertIn("Candle gatilho fraco", result["signal"]["reason"])

    def test_break_even_activates_at_70_percent_to_target(self):
        raw_signal = {
            "direction_code": "BUY",
            "entry_price": 100,
            "stop_loss": 95,
            "take_profit_1": 105,
            "take_profit_2": 110,
        }
        signal = {
            "direction": "BUY",
            "status": "Entrada acionada",
            "history": [],
            **SignalRiskManager().build(raw_signal),
        }

        activated = BreakEvenManager().update(signal, 107)

        self.assertTrue(activated)
        self.assertTrue(signal["breakEven"]["enabled"])
        self.assertEqual(signal["status"], STATUS_BE)
        self.assertAlmostEqual(signal["stopLoss"], 100.15)


if __name__ == "__main__":
    unittest.main()
