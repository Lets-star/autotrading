import pytest
import asyncio
from trading_bot.data_feeds.storage import DataStorage
from trading_bot.data_feeds.models import Kline

@pytest.mark.asyncio
async def test_storage_add_kline():
    storage = DataStorage()
    kline = Kline(
        symbol="BTCUSDT", interval="1m",
        open=100.0, high=110.0, low=90.0, close=105.0,
        volume=1000.0, quote_volume=105000.0,
        start_time=1000, close_time=1999,
        is_closed=True, trades_count=10
    )
    await storage.add_kline(kline)
    df = await storage.get_klines_df("BTCUSDT", "1m")
    assert len(df) == 1
    assert df.iloc[0]['close'] == 105.0

@pytest.mark.asyncio
async def test_aggregation():
    storage = DataStorage()
    # Add 5 1m klines
    # timestamps: 0, 60000, 120000, 180000, 240000
    # 5m bucket: 0-300000 (0-5min)
    for i in range(5):
        kline = Kline(
            symbol="BTCUSDT", interval="1m",
            open=100.0 + i, high=100.0 + i + 1, low=100.0 + i - 0.5, close=100.0 + i + 0.5,
            volume=10.0, quote_volume=1000.0,
            start_time=i*60000, close_time=(i+1)*60000 - 1,
            is_closed=True, trades_count=1
        )
        await storage.add_kline(kline)
        
    aggregated = await storage.aggregate_klines("BTCUSDT", "1m", 5)
    
    # Debug info if fails
    if not aggregated:
        print("Aggregation returned empty list")
        df = await storage.get_klines_df("BTCUSDT", "1m")
        print(df)

    assert len(aggregated) == 1
    agg = aggregated[0]
    assert agg.interval == "5m"
    assert agg.open == 100.0 # First open (i=0 -> 100.0)
    assert agg.close == 104.5 # Last close (i=4 -> 100+4+0.5 = 104.5)
    assert agg.high == 105.0 # Max high (i=4 -> 100+4+1 = 105.0)
    assert agg.low == 99.5 # Min low (i=0 -> 100-0.5 = 99.5)
    assert agg.volume == 50.0 # Sum volume (10 * 5)
