import pytest
from unittest.mock import MagicMock, patch
import pandas as pd
from trading_bot.data_feeds.binance_fetcher import BinanceDataFetcher
from binance.exceptions import BinanceAPIException
import os
import shutil

@pytest.fixture
def fetcher():
    fetcher = BinanceDataFetcher("key", "secret")
    yield fetcher
    # Cleanup cache
    if os.path.exists(fetcher.cache_dir):
        shutil.rmtree(fetcher.cache_dir)

def test_fetch_history_success(fetcher):
    # Mock client
    mock_klines = [
        [
            1600000000000, "100", "110", "90", "105", "10", 
            1600000060000, "1000", 5, "5", "50", "0"
        ]
    ]
    fetcher.client.get_klines = MagicMock(return_value=mock_klines)
    
    df = fetcher.fetch_history("BTCUSDT", "1m", 1)
    
    assert len(df) == 1
    assert df.iloc[0]['close'] == 105.0
    # Check cache file created
    assert os.path.exists(os.path.join(fetcher.cache_dir, "BTCUSDT_1m_1.csv"))

def test_fetch_history_retry(fetcher):
    # Mock client to fail then succeed
    mock_klines = [
        [
            1600000000000, "100", "110", "90", "105", "10", 
            1600000060000, "1000", 5, "5", "50", "0"
        ]
    ]
    
    fetcher.client.get_klines = MagicMock(side_effect=[Exception("Fail 1"), Exception("Fail 2"), mock_klines])
    
    # Speed up backoff for test
    with patch('time.sleep') as mock_sleep:
        df = fetcher.fetch_history("BTCUSDT", "1m", 1)
        
        assert mock_sleep.call_count == 2
        assert len(df) == 1
        assert df.iloc[0]['close'] == 105.0

def test_fetch_history_cache_fallback(fetcher):
    # Create dummy cache file
    cache_file = os.path.join(fetcher.cache_dir, "BTCUSDT_1m_1.csv")
    if not os.path.exists(fetcher.cache_dir):
        os.makedirs(fetcher.cache_dir)
        
    pd.DataFrame({
        'timestamp': [1600000000000],
        'open': [100.0],
        'high': [100.0],
        'low': [100.0],
        'close': [200.0],
        'volume': [100.0],
        'turnover': [100.0]
    }).to_csv(cache_file, index=False)
    
    # Mock client to fail completely
    fetcher.client.get_klines = MagicMock(side_effect=Exception("All attempts failed"))
    
    with patch('time.sleep'): # skip sleep
        df = fetcher.fetch_history("BTCUSDT", "1m", 1)
        
        assert len(df) == 1
        assert df.iloc[0]['close'] == 200.0
