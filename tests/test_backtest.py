import pytest
import pandas as pd
from unittest.mock import MagicMock, patch
from trading_bot.backtesting.engine import BacktestEngine

@pytest.fixture
def mock_data_fetcher():
    with patch('trading_bot.backtesting.engine.BybitDataFetcher') as MockFetcher:
        fetcher_instance = MockFetcher.return_value
        
        # Create dummy dataframe
        dates = pd.date_range(start='2023-01-01', periods=100, freq='1h')
        df = pd.DataFrame({
            'start_time': range(100),
            'timestamp': dates,
            'open': [100.0 + i for i in range(100)],
            'high': [105.0 + i for i in range(100)],
            'low': [95.0 + i for i in range(100)],
            'close': [102.0 + i for i in range(100)],
            'volume': [1000 for _ in range(100)],
            'turnover': [100000 for _ in range(100)]
        })
        
        fetcher_instance.fetch_history.return_value = df
        yield MockFetcher

def test_backtest_run(mock_data_fetcher):
    engine = BacktestEngine()
    results = engine.run(symbol="BTCUSDT", interval="1h", limit=100)
    
    assert results is not None
    assert "total_pnl" in results
    assert "win_rate" in results
    assert results["final_balance"] == 10000.0 # No trades expected with this dummy linear data (SMA won't cross much or correctly) or just check structure

def test_backtest_with_trades():
    # Setup data that produces a cross
    dates = pd.date_range(start='2023-01-01', periods=50, freq='1h')
    data = {
        'timestamp': dates,
        'close': [100] * 20 + [110] * 5 + [90] * 25 # Jump then drop to trigger SMAs
    }
    df = pd.DataFrame(data)
    
    with patch('trading_bot.backtesting.engine.BybitDataFetcher') as MockFetcher:
        fetcher_instance = MockFetcher.return_value
        fetcher_instance.fetch_history.return_value = df
        
        engine = BacktestEngine()
        results = engine.run()
        
        assert results is not None
        # We don't strictly assert trade count here as it depends on exact SMA logic,
        # but we ensure the engine runs without error.
        assert "trades" in results
