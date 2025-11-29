import pytest
from unittest.mock import MagicMock, patch
import pandas as pd
from trading_bot.data_feeds.bybit_fetcher import BybitDataFetcher

@pytest.fixture
def fetcher():
    fetcher = BybitDataFetcher("key", "secret")
    yield fetcher

def test_fetch_history_success(fetcher):
    # Mock session
    mock_response = {
        'retCode': 0,
        'result': {
            'list': [
                ["1600000000000", "100", "110", "90", "105", "10", "1000"]
            ]
        }
    }
    fetcher.session.get_kline = MagicMock(return_value=mock_response)
    
    df = fetcher.fetch_history("BTCUSDT", "1m", 1)
    
    assert len(df) == 1
    assert df.iloc[0]['close'] == 105.0
    assert df.iloc[0]['open'] == 100.0

def test_fetch_history_fail(fetcher):
    mock_response = {
        'retCode': 10001,
        'retMsg': 'Error'
    }
    fetcher.session.get_kline = MagicMock(return_value=mock_response)
    
    df = fetcher.fetch_history("BTCUSDT", "1m", 1)
    
    assert df.empty
    assert fetcher.status == "Failed"

def test_fetch_orderbook_success(fetcher):
    mock_response = {
        'retCode': 0,
        'result': {
            's': 'BTCUSDT',
            'b': [],
            'a': []
        }
    }
    fetcher.session.get_orderbook = MagicMock(return_value=mock_response)
    
    ob = fetcher.fetch_orderbook("BTCUSDT")
    assert ob['s'] == 'BTCUSDT'

def test_fetch_orderbook_fail(fetcher):
    mock_response = {
        'retCode': 10001,
        'retMsg': 'Error'
    }
    fetcher.session.get_orderbook = MagicMock(return_value=mock_response)
    
    ob = fetcher.fetch_orderbook("BTCUSDT")
    assert ob == {}
