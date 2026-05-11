from ia.providers.binance_provider import BinanceProvider
from ia.providers.mt5_provider import MT5Provider

class ProviderManager:
    def __init__(self):
        self.providers = {
            "crypto": BinanceProvider(),
            # Future providers can be added here
"forex": MT5Provider(),
"futures_b3": MT5Provider(),
        }

    def get_provider(self, asset_type: str):
        return self.providers.get(asset_type)