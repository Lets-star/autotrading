import unittest
import pandas as pd
import numpy as np
from trading_bot.scoring.service import ScoringService
from trading_bot.scoring.components.technical import TechnicalIndicators
from trading_bot.scoring.components.orderbook import OrderbookImbalance
from trading_bot.scoring.components.market_structure import MarketStructure

class TestScoringEngine(unittest.TestCase):
    def setUp(self):
        dates = pd.date_range(start='2023-01-01', periods=100, freq='1H')
        data = {
            'open': np.random.rand(100) * 100,
            'high': np.random.rand(100) * 100,
            'low': np.random.rand(100) * 100,
            'close': np.random.rand(100) * 100,
            'volume': np.random.rand(100) * 1000
        }
        # Ensure high >= low, high >= close, high >= open, low <= close, low <= open
        data['low'] = np.minimum(data['low'], np.minimum(data['open'], data['close']))
        data['high'] = np.maximum(data['high'], np.maximum(data['open'], data['close']))
        
        self.sample_market_data = pd.DataFrame(data, index=dates)
        
        self.sample_orderbook = {
            'bids': [[100.0, 1.0], [99.0, 2.0]],
            'asks': [[101.0, 1.0], [102.0, 0.5]]
        }

    def test_technical_indicators(self):
        component = TechnicalIndicators(rsi_period=14)
        # Create a trend to force a signal
        # Upward trend
        df = self.sample_market_data.copy()
        for i in range(1, 100):
            df.iloc[i, df.columns.get_loc('close')] = df.iloc[i-1, df.columns.get_loc('close')] * 1.01
            
        data = {'candles': df}
        result = component.calculate(data)
        
        self.assertIn('rsi', result.metadata)
        self.assertIn('ema_short', result.metadata)
        self.assertTrue(-1.0 <= result.score <= 1.0)

    def test_orderbook_imbalance(self):
        component = OrderbookImbalance()
        data = {'orderbook': self.sample_orderbook}
        result = component.calculate(data)
        
        # Bids: 1*100 + 2*99 (ignored price, just volume) -> 1 + 2 = 3
        # Asks: 1 + 0.5 = 1.5
        # Total: 4.5
        # Imbalance: (3 - 1.5) / 4.5 = 1.5 / 4.5 = 0.333
        
        self.assertTrue(result.score > 0) # Bullish
        self.assertAlmostEqual(result.metadata['imbalance'], 0.333, delta=0.01)

    def test_market_structure(self):
        component = MarketStructure(window=2)
        
        data = {'candles': self.sample_market_data}
        result = component.calculate(data)
        self.assertTrue(-1.0 <= result.score <= 1.0)
        self.assertIn('trend', result.metadata)

    def test_composite_scoring_engine(self):
        service = ScoringService()
        
        # Mock data
        market_data = pd.DataFrame({
            'close': np.linspace(100, 200, 100), # Upward trend
            'high': np.linspace(101, 201, 100),
            'low': np.linspace(99, 199, 100),
            'open': np.linspace(100, 200, 100),
            'volume': np.ones(100) * 1000
        })
        
        data = {
            'candles': market_data,
            'orderbook': {'bids': [[100, 10]], 'asks': [[101, 1]]}, # Bullish imbalance
            'sentiment': {'score': 0.8, 'source': 'test'}, # Bullish sentiment
            'mtf_candles': {'5m': market_data} # Alignment
        }
        
        result = service.calculate_score(data)
        
        self.assertTrue(result['aggregated_score'] > 0) # Should be bullish overall
        self.assertIn('technical_indicators', result['components'])
        self.assertIn('orderbook_imbalance', result['components'])

    def test_adaptive_weighting(self):
        service = ScoringService()
        engine = service.engine
        
        component_name = 'technical_indicators'
        initial_weight = engine.weights[component_name]
        
        # Simulate a calculation where technicals gave a POSITIVE score
        fake_signal_context = {
            "components": {
                component_name: {"score": 1.0, "confidence": 1.0}
            }
        }
        
        # Scenario 1: Prediction was CORRECT (Outcome +1.0) -> Weight should INCREASE
        service.update_weights(fake_signal_context, outcome=1.0)
        self.assertTrue(engine.weights[component_name] > initial_weight)
        
        # Scenario 2: Prediction was INCORRECT (Outcome -1.0) -> Weight should DECREASE
        current_weight = engine.weights[component_name]
        service.update_weights(fake_signal_context, outcome=-1.0)
        self.assertTrue(engine.weights[component_name] < current_weight)

if __name__ == '__main__':
    unittest.main()


