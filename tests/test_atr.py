import unittest
import pandas as pd
from trading_bot.utils.atr import calculate_atr, ATRTrailingStop

class TestATR(unittest.TestCase):
    def setUp(self):
        self.data = pd.DataFrame({
            'high': [10, 11, 12, 11, 13, 14, 15, 16, 17, 18],
            'low': [9, 10, 11, 10, 12, 13, 14, 15, 16, 17],
            'close': [9.5, 10.5, 11.5, 10.5, 12.5, 13.5, 14.5, 15.5, 16.5, 17.5]
        })

    def test_calculate_atr_wilder(self):
        atr = calculate_atr(self.data, period=3, method='wilder')
        self.assertEqual(len(atr), 10)
        # First 3 should be NaN/invalid or smoothed initial
        # With min_periods=3, first 2 are NaN.
        self.assertTrue(pd.isna(atr.iloc[0]))
        self.assertTrue(pd.isna(atr.iloc[1]))
        self.assertFalse(pd.isna(atr.iloc[2]))
        
    def test_atr_trailing_stop(self):
        calculator = ATRTrailingStop(period=3, multiplier=2.0)
        
        # Feed data one by one
        for i, row in self.data.iterrows():
            result = calculator.update(row['high'], row['low'], row['close'])
            if i >= 2: # After period is full
                self.assertIn('stop_loss', result)
                self.assertIn('trend', result)
                
    def test_trend_switch(self):
         # Create a scenario where trend switches
        data = pd.DataFrame({
            'high': [100, 102, 104, 98, 90],
            'low': [98, 100, 102, 90, 80],
            'close': [99, 101, 103, 92, 85]
        })
        calculator = ATRTrailingStop(period=2, multiplier=1.0)
        
        results = []
        for i, row in data.iterrows():
            results.append(calculator.update(row['high'], row['low'], row['close']))
            
        # Check if trend switched from Up (1) to Down (-1)
        # 1st: Init
        # 2nd: Has ATR. Trend 1.
        # 3rd: Close 103. Trend 1.
        # 4th: Close 92. Big drop. Should break support.
        
        last_res = results[-1]
        self.assertEqual(last_res['trend'], -1)

if __name__ == '__main__':
    unittest.main()
