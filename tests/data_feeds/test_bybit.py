import pytest
import asyncio
from trading_bot.data_feeds.bybit import BybitDataFeed
from trading_bot.data_feeds.storage import DataStorage
from unittest.mock import MagicMock

@pytest.mark.asyncio
async def test_process_bybit_trade():
    storage = DataStorage()
    feed = BybitDataFeed("key", "secret", storage, ["BTCUSDT"], ["1m"])
    
    # Needs loop for run_coroutine_threadsafe inside feed._handle_trade
    # Since we are in async test, we can just run it.
    # But feed._handle_trade uses asyncio.run_coroutine_threadsafe(..., self.loop)
    # So we need self.loop to be set.
    feed.loop = asyncio.get_running_loop()
    
    msg = {
        "topic": "publicTrade.BTCUSDT",
        "data": [
            {
                "T": 1672304486866,
                "s": "BTCUSDT",
                "S": "Buy",
                "v": "0.001",
                "p": "16578.50",
                "L": "PlusTick",
                "i": "20f43950-d8dd-5b31-9112-a178eb6023af",
                "BT": False
            }
        ]
    }
    
    feed._handle_trade(msg)
    
    # Wait a bit for the task to complete on loop
    await asyncio.sleep(0.1)
    
    df = await storage.get_trades_df("BTCUSDT")
    assert len(df) == 1
    assert df.iloc[0]['price'] == 16578.50
    # S="Buy" means Taker Buy -> Maker Sell -> is_buyer_maker=False?
    # Binance: is_buyer_maker=True if maker is buyer.
    # If Taker Buy, Maker Sell. is_buyer_maker=False.
    # My implementation: is_buyer_maker = (item.get('S') == 'Sell')
    # If S="Buy", is_buyer_maker = False. Correct.
    assert df.iloc[0]['is_buyer_maker'] == False

@pytest.mark.asyncio
async def test_process_bybit_kline():
    storage = DataStorage()
    feed = BybitDataFeed("key", "secret", storage, ["BTCUSDT"], ["1m"])
    feed.loop = asyncio.get_running_loop()
    
    msg = {
        "topic": "kline.1.BTCUSDT",
        "data": [
            {
                "start": 1672324800000,
                "end": 1672324859999,
                "interval": "1",
                "open": "16656.0",
                "close": "16656.5",
                "high": "16656.5",
                "low": "16656.0",
                "volume": "100.000",
                "turnover": "1665625.0000",
                "confirm": False
            }
        ]
    }
    
    feed._handle_kline(msg, "1m")
    
    await asyncio.sleep(0.1)
    
    df = await storage.get_klines_df("BTCUSDT", "1m")
    assert len(df) == 1
    assert df.iloc[0]['close'] == 16656.5
    assert df.iloc[0]['volume'] == 100.0
