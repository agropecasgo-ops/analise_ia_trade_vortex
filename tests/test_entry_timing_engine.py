import unittest

import pandas as pd

from ia.entry_timing_engine import ENTRY_EARLY, ENTRY_LATE, NO_ENTRY, build_entry_timing


def candles(last_close=101.0, last_open=100.6, last_high=101.2, last_low=100.4, volume=1800):
    rows = []
    price = 100.0
    for index in range(50):
        rows.append({
            "open": price,
            "high": price + 0.4,
            "low": price - 0.4,
            "close": price + 0.05,
            "volume": 1000,
        })
        price += 0.02
    rows[-1] = {
        "open": last_open,
        "high": last_high,
        "low": last_low,
        "close": last_close,
        "volume": volume,
    }
    return pd.DataFrame(rows, index=pd.date_range("2026-01-01", periods=50, freq="min"))


class EntryTimingEngineTests(unittest.TestCase):
    def test_detects_early_entry_without_waiting_for_candle_close(self):
        result = build_entry_timing(
            candles(),
            "BUY",
            timeframe="1m",
            score=72,
            min_score=70,
            trade_plan={"entry": 100.8, "riskReward": 1.4},
            risk={"allowed": True},
            structure={
                "bos": {"detected": True, "direction": "BUY", "level": 100.7},
                "liquidity_sweep": {"detected": True, "direction": "BUY", "level": 100.5},
            },
            confirmation={"valid": False, "volume": {"strong": True}},
            volume={"signal": "BULLISH_VOLUME", "dominant_side": "BUYER", "metrics": {"volume_ratio": 1.8}},
            flow={"order_flow_bias": "BUY_FLOW", "flow_score": 70},
            macro={"direction": "BUY", "blocked": False},
        )

        self.assertEqual(result["status"], ENTRY_EARLY)
        self.assertTrue(result["entry_allowed"])

    def test_marks_late_entry_and_blocks_chasing_price(self):
        result = build_entry_timing(
            candles(last_close=104.0, last_open=103.0, last_high=104.2, last_low=102.9, volume=2200),
            "BUY",
            timeframe="1m",
            score=90,
            min_score=70,
            trade_plan={"entry": 100.0, "riskReward": 2.0},
            risk={"allowed": True},
            structure={"bos": {"detected": True, "direction": "BUY", "level": 100.0}},
            confirmation={"valid": True, "volume": {"strong": True}},
            volume={"signal": "BULLISH_VOLUME", "dominant_side": "BUYER", "metrics": {"volume_ratio": 2.0}},
            flow={"order_flow_bias": "BUY_FLOW", "flow_score": 80},
            macro={"direction": "BUY", "blocked": False},
        )

        self.assertEqual(result["status"], ENTRY_LATE)
        self.assertFalse(result["entry_allowed"])
        self.assertTrue(result["do_not_chase"])

    def test_indicator_context_without_institutional_direction_does_not_enter(self):
        result = build_entry_timing(
            candles(),
            "NEUTRAL",
            score=90,
            volume={"signal": "BULLISH_VOLUME", "dominant_side": "BUYER", "metrics": {"volume_ratio": 2.0}},
            flow={"order_flow_bias": "BUY_FLOW", "flow_score": 80},
        )

        self.assertEqual(result["status"], NO_ENTRY)
        self.assertFalse(result["entry_allowed"])


if __name__ == "__main__":
    unittest.main()
