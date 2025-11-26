import unittest
from unittest.mock import MagicMock
from trading_bot.risk.service import RiskService
from trading_bot.config import settings

class TestRiskService(unittest.TestCase):
    def setUp(self):
        self.service = RiskService()
        # Mock settings
        self.service.settings.risk_per_trade_percent = 1.0
        self.service.settings.max_position_size_usd = 1000.0
        self.service.settings.max_concurrent_trades = 5
        self.service.settings.max_volatility_threshold = 5.0
        self.service.settings.min_liquidity_threshold = 10000.0
        self.service.settings.atr_multiplier_sl = 2.0
        self.service.settings.atr_multiplier_tp = 3.0

    def test_calculate_position_size(self):
        balance = 10000.0
        entry = 100.0
        sl = 95.0 # 5 distance
        
        # Risk amount = 1% of 10000 = 100
        # Position size = 100 / 5 = 20 units
        # Value = 20 * 100 = 2000 USD
        # Max limit is 1000 USD
        
        # Should be capped at 1000 USD / 100 = 10 units
        size = self.service.calculate_position_size(balance, entry, sl)
        self.assertEqual(size, 10.0)
        
        # Test uncapped
        self.service.settings.max_position_size_usd = 5000.0
        size = self.service.calculate_position_size(balance, entry, sl)
        self.assertEqual(size, 20.0)

    def test_validate_trade_setup(self):
        # Good setup
        self.assertTrue(self.service.validate_trade_setup(
            current_open_trades=0, atr_value=1.0, liquidity=50000.0
        ))
        
        # Max trades
        self.assertFalse(self.service.validate_trade_setup(
            current_open_trades=5, atr_value=1.0, liquidity=50000.0
        ))
        
        # High Volatility
        self.assertFalse(self.service.validate_trade_setup(
            current_open_trades=0, atr_value=10.0, liquidity=50000.0
        ))
        
        # Low Liquidity
        self.assertFalse(self.service.validate_trade_setup(
            current_open_trades=0, atr_value=1.0, liquidity=100.0
        ))

    def test_calculate_stops(self):
        entry = 100.0
        atr = 2.0
        
        stops = self.service.calculate_stops(entry, atr, side='buy')
        # SL = 100 - 2*2 = 96
        # TP = 100 + 2*3 = 106
        self.assertEqual(stops['stop_loss'], 96.0)
        self.assertEqual(stops['take_profit'], 106.0)
        
        stops = self.service.calculate_stops(entry, atr, side='sell')
        # SL = 100 + 2*2 = 104
        # TP = 100 - 2*3 = 94
        self.assertEqual(stops['stop_loss'], 104.0)
        self.assertEqual(stops['take_profit'], 94.0)

if __name__ == '__main__':
    unittest.main()
