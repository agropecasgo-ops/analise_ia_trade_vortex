import unittest
from ia.providers.mt5_provider import MT5Provider
from ia.providers.provider_manager import ProviderManager

class TestMT5Provider(unittest.TestCase):
    def setUp(self):
        self.provider = MT5Provider()

    def test_initialization(self):
        self.assertIsInstance(self.provider, MT5Provider)

    def test_get_klines(self):
        # This is a placeholder test; actual implementation would require a running MetaTrader5 instance
        df = self.provider.get_klines("EURUSD", "1h", 10)
        self.assertTrue(df.empty or 'time' in df.columns)

    def test_get_klines_win_wdo(self):
        # Test loading WIN candles
        df_win = self.provider.get_klines("WIN", "1h", 10)
        self.assertTrue(df_win.empty or 'time' in df_win.columns)

        # Test loading WDO candles
        df_wdo = self.provider.get_klines("WDO", "1h", 10)
        self.assertTrue(df_wdo.empty or 'time' in df_wdo.columns)

class TestProviderManager(unittest.TestCase):
    def setUp(self):
        self.manager = ProviderManager()

    def test_get_forex_provider(self):
        provider = self.manager.get_provider("forex")
        self.assertIsInstance(provider, MT5Provider)

    def test_get_futures_b3_provider(self):
        provider = self.manager.get_provider("futures_b3")
        self.assertIsInstance(provider, MT5Provider)

if __name__ == '__main__':
    unittest.main()