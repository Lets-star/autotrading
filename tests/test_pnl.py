import unittest
from trading_bot.utils.pnl import calculate_realized_pnl

class TestPnL(unittest.TestCase):
    def test_calculate_realized_pnl(self):
        # Long: Entry 100, Exit 110, Qty 1, Fee 0.1
        # (110 - 100) * 1 - 0.1 = 9.9
        pnl = calculate_realized_pnl(100, 110, 1, 'buy', 0.1)
        self.assertAlmostEqual(pnl, 9.9)
        
        # Short: Entry 100, Exit 90, Qty 1, Fee 0.1
        # (100 - 90) * 1 - 0.1 = 9.9
        pnl = calculate_realized_pnl(100, 90, 1, 'sell', 0.1)
        self.assertAlmostEqual(pnl, 9.9)
        
        # Loss Long: Entry 100, Exit 90
        # (90 - 100) * 1 - 0.1 = -10.1
        pnl = calculate_realized_pnl(100, 90, 1, 'buy', 0.1)
        self.assertAlmostEqual(pnl, -10.1)

if __name__ == '__main__':
    unittest.main()
