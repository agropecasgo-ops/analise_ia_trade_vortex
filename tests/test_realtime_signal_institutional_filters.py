import unittest

from ia.live_signals import SignalScoreService


def approved_live_status():
    return {
        "state": "BUY_CONFIRMED",
        "confluence_score": 90,
        "probable_direction": "BUY",
        "layered_signal": {
            "macro_context": {"blocked": False, "blockers": []},
            "confirmation": {"valid": True, "blockers": []},
            "signal": {
                "generated": True,
                "direction_code": "BUY",
                "risk_gate": {"allowed": True, "blockers": []},
            },
            "ai_score": {"score": 90, "blockers": []},
        },
    }


def scored_live_status(score):
    status = approved_live_status()
    status["confluence_score"] = score
    status["layered_signal"]["ai_score"]["score"] = score
    status["layered_signal"]["signal"]["score"] = score
    return status


class RealtimeSignalInstitutionalFilterTests(unittest.TestCase):
    def test_without_institutional_payload_keeps_existing_allowed_behavior(self):
        allowed, reasons = SignalScoreService().allowed(approved_live_status())

        self.assertTrue(allowed)
        self.assertEqual(reasons, [])

    def test_sideways_market_blocks_signal_when_institutional_payload_exists(self):
        status = approved_live_status()
        status["institutional_unified"] = {
            "direction": "BUY",
            "status": "WAIT_CONFIRMATION",
            "macroContext": {"lateral": True, "volatility": {"state": "GOOD"}},
            "news": {"impact": "UNKNOWN"},
            "risk": {"allowed": True},
        }

        allowed, reasons = SignalScoreService().allowed(status)

        self.assertFalse(allowed)
        self.assertIn("Mercado lateral bloqueado pela IA institucional.", reasons)

    def test_low_volatility_blocks_signal_when_institutional_payload_exists(self):
        status = approved_live_status()
        status["institutional_unified"] = {
            "direction": "BUY",
            "status": "WAIT_CONFIRMATION",
            "macroContext": {"lateral": False, "volatility": {"state": "LOW"}},
            "news": {"impact": "UNKNOWN"},
            "risk": {"allowed": True},
        }

        allowed, reasons = SignalScoreService().allowed(status)

        self.assertFalse(allowed)
        self.assertIn("Volatilidade baixa bloqueada pela IA institucional.", reasons)

    def test_high_impact_news_blocks_signal_when_flagged_as_blocking(self):
        status = approved_live_status()
        status["institutional_unified"] = {
            "direction": "BUY",
            "status": "WAIT_CONFIRMATION",
            "macroContext": {"lateral": False, "volatility": {"state": "GOOD"}},
            "news": {"impact": "HIGH", "blocking": True},
            "risk": {"allowed": True},
        }

        allowed, reasons = SignalScoreService().allowed(status)

        self.assertFalse(allowed)
        self.assertIn("Noticia forte bloqueia novo sinal.", reasons)

    def test_operational_mode_thresholds_control_minimum_score(self):
        service = SignalScoreService()

        conservador_allowed, conservador_reasons = service.allowed(scored_live_status(70), "conservador")
        moderado_allowed, moderado_reasons = service.allowed(scored_live_status(70), "moderado")
        agressivo_allowed, agressivo_reasons = service.allowed(scored_live_status(55), "agressivo")

        self.assertFalse(conservador_allowed)
        self.assertIn("Score 70 abaixo do minimo 80 no modo Conservador.", conservador_reasons)
        self.assertTrue(moderado_allowed)
        self.assertEqual(moderado_reasons, [])
        self.assertTrue(agressivo_allowed)
        self.assertEqual(agressivo_reasons, [])


if __name__ == "__main__":
    unittest.main()
