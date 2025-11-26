import pytest
import asyncio
from trading_bot.data_feeds.binance import BinanceDataFeed
from trading_bot.data_feeds.storage import DataStorage

@pytest.mark.asyncio
async def test_process_trade():
    storage = DataStorage()
    feed = BinanceDataFeed("key", "secret", storage, ["BTCUSDT"], ["1m"])
    
    data = {
      "e": "trade",
      "E": 123456789,
      "s": "BTCUSDT",
      "t": 12345,
      "p": "0.001",
      "q": "100",
      "b": 88,
      "a": 50,
      "T": 123456785,
      "m": True,
      "M": True
    }
    
    await feed._process_trade(data)
    df = await storage.get_trades_df("BTCUSDT")
    assert len(df) == 1
    assert df.iloc[0]['price'] == 0.001
    assert df.iloc[0]['is_buyer_maker'] == True

@pytest.mark.asyncio
async def test_process_kline():
    storage = DataStorage()
    feed = BinanceDataFeed("key", "secret", storage, ["BTCUSDT"], ["1m"])
    
    data = {
      "e": "kline",
      "E": 123456789,
      "s": "BTCUSDT",
      "k": {
        "t": 123400000,
        "T": 123460000,
        "s": "BTCUSDT",
        "i": "1m",
        "f": 100,
        "L": 200,
        "o": "0.0010",
        "c": "0.0020",
        "h": "0.0025",
        "l": "0.0015",
        "v": "1000",
        "n": 100,
        "x": False,
        "q": "1.0000"
      }
    }
    
    await feed._process_kline(data)
    df = await storage.get_klines_df("BTCUSDT", "1m")
    assert len(df) == 1
    assert df.iloc[0]['close'] == 0.0020
