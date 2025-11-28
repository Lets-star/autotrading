import unittest
from unittest.mock import MagicMock, patch
import asyncio
from trading_bot.risk.service import RiskService
from trading_bot.execution.service import ExecutionService
from trading_bot.execution.bybit_client import BybitExecutionClient

class TestIntegration(unittest.TestCase):
    def setUp(self):
        self.risk_service = RiskService()
        
        # Mock settings for Risk
        self.risk_service.settings.risk_per_trade_percent = 1.0
        self.risk_service.settings.max_position_size_usd = 5000.0
        self.risk_service.settings.atr_multiplier_sl = 2.0
        self.risk_service.settings.atr_multiplier_tp = 3.0
        
        # Execution Service with Mocked Client
        self.execution_service = ExecutionService()
        self.execution_service.exchange_id = "bybit" # Force bybit
        self.mock_client = MagicMock(spec=BybitExecutionClient)
        self.execution_service.client = self.mock_client

    def test_risk_to_execution_flow(self):
        # 1. Market Data (Simulated)
        entry_price = 50000.0
        atr = 500.0
        balance = 100000.0
        
        # 2. Risk Calculation
        stops = self.risk_service.calculate_stops(entry_price, atr, side='buy')
        
        # Expected SL: 50000 - 2*500 = 49000
        # Expected TP: 50000 + 3*500 = 51500
        self.assertEqual(stops['stop_loss'], 49000.0)
        self.assertEqual(stops['take_profit'], 51500.0)
        
        qty = self.risk_service.calculate_position_size(balance, entry_price, stops['stop_loss'])
        
        # Risk Amount = 1% of 100000 = 1000
        # Diff = 1000
        # Qty = 1000 / 1000 = 1.0 BTC
        # BUT: Max Position Size is 5000 USD. 
        # 1.0 BTC * 50000 = 50000 USD > 5000 USD.
        # So it caps at 5000 / 50000 = 0.1 BTC.
        self.assertAlmostEqual(qty, 0.1)
        
        # 3. Execution
        order_params = {
            "symbol": "BTCUSDT",
            "side": "Buy",
            "qty": qty,
            "price": entry_price,
            "stop_loss": stops['stop_loss'],
            "take_profit": stops['take_profit'],
            "order_type": "Limit"
        }
        
        # Run async execution
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self.execution_service.execute_order(order_params))
        loop.close()
        
        # Verify client called correctly
        self.mock_client.place_order.assert_called_once()
        call_args = self.mock_client.place_order.call_args[1]
        
        self.assertEqual(call_args['symbol'], "BTCUSDT")
        self.assertEqual(call_args['side'], "Buy")
        self.assertEqual(call_args['qty'], 0.1)
        self.assertEqual(call_args['stop_loss'], 49000.0)
        self.assertEqual(call_args['take_profit'], 51500.0)

if __name__ == '__main__':
    unittest.main()
