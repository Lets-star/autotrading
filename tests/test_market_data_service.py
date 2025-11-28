import time
import pytest
import pandas as pd
from trading_bot.data_feeds.market_data_service import MarketDataService

def test_market_data_service_initialization():
    service = MarketDataService(
        api_key="test",
        api_secret="test",
        symbol="BTCUSDT",
        timeframes=["1m"]
    )
    assert service.symbol == "BTCUSDT"
    assert service.timeframes == ["1m"]
    assert service.data["status"] == "Disconnected"

def test_market_data_service_thread():
    # We can't easily test the thread connecting to real API without keys or mocks.
    # But we can start and stop it.
    service = MarketDataService(
        api_key="test",
        api_secret="test",
        symbol="BTCUSDT",
        timeframes=["1m"]
    )
    
    # Mock fetcher to avoid real calls and speed up test
    class MockFetcher:
        def fetch_history(self, *args, **kwargs):
            return pd.DataFrame({
                'start_time': [1000, 2000],
                'open': [100, 101],
                'high': [102, 103],
                'low': [99, 100],
                'close': [101, 102],
                'volume': [10, 10],
                'turnover': [1000, 1000],
                'timestamp': [1000, 2000]
            })
        def fetch_orderbook(self, *args, **kwargs):
            return {'bids': [], 'asks': []}
            
    service.fetcher = MockFetcher()
    
    service.start()
    time.sleep(3) # Let it run, it sleeps 1s inside
    
    data = service.get_data()
    assert data["status"] == "Connected"
    assert data["update_count"] >= 1
    
    service.stop()
    # Thread might take up to 1s + join timeout to stop
    time.sleep(0.5)
    assert not service._thread.is_alive()
