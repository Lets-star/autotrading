import unittest
from unittest.mock import MagicMock, patch
from trading_bot.execution.bybit_client import BybitExecutionClient

class TestBybitExecutionClient(unittest.TestCase):
    def test_dry_run_mode(self):
        client = BybitExecutionClient(dry_run=True)
        response = client.place_order("BTCUSDT", "Buy", 0.1, 50000)
        self.assertEqual(response['retCode'], 0)
        self.assertIn("sim_", response['result']['orderId'])
        
        response = client.amend_order("BTCUSDT", "ord1", price=50100)
        self.assertEqual(response['retCode'], 0)
        
        response = client.cancel_order("BTCUSDT", "ord1")
        self.assertEqual(response['retCode'], 0)

    @patch('trading_bot.execution.bybit_client.settings')
    @patch('trading_bot.execution.bybit_client.HTTP')
    def test_real_client_interaction(self, mock_http, mock_settings):
        # Setup mock settings
        mock_settings.api_key = "test_key"
        mock_settings.api_secret = "test_secret"
        mock_settings.bybit_testnet = True
        
        mock_session = MagicMock()
        mock_http.return_value = mock_session
        
        # Configure mock response
        mock_session.place_order.return_value = {"retCode": 0, "result": {"orderId": "123"}}
        
        client = BybitExecutionClient(dry_run=False)
        # Verify dry_run didn't get forced to True
        self.assertFalse(client.dry_run)
        
        response = client.place_order("BTCUSDT", "Buy", 0.1, 50000)
        
        mock_session.place_order.assert_called_once()
        self.assertEqual(response['result']['orderId'], "123")
        
        # Test error handling
        mock_session.place_order.return_value = {"retCode": 10001, "retMsg": "Params Error"}
        response = client.place_order("BTCUSDT", "Buy", 0.1, 50000)
        self.assertEqual(response['retCode'], 10001)

if __name__ == '__main__':
    unittest.main()
