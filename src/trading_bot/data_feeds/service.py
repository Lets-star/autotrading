import asyncio
import pandas as pd
from typing import List, Optional
from trading_bot.logger import get_logger
from trading_bot.config import settings
from .storage import DataStorage
from .binance import BinanceDataFeed

logger = get_logger(__name__)

class DataFeedService:
    def __init__(self):
        self.running = False
        self.exchange_id = settings.exchange_id
        self.storage = DataStorage()
        self.feed = None
        # Default symbols and intervals for now.
        self.symbols = ["BTCUSDT", "ETHUSDT"]
        self.intervals = ["1m", "5m", "15m"]
        
        if self.exchange_id == "binance":
            self.feed = BinanceDataFeed(
                api_key=settings.api_key,
                api_secret=settings.api_secret,
                storage=self.storage,
                symbols=self.symbols,
                intervals=self.intervals
            )
        else:
            logger.warning(f"Exchange {self.exchange_id} not supported yet.")

        logger.info(f"Initialized DataFeedService for {self.exchange_id}")

    async def start(self):
        self.running = True
        logger.info("Starting DataFeedService...")
        if self.feed:
             # We run the feed in a background task
             asyncio.create_task(self.feed.start())

    async def stop(self):
        self.running = False
        logger.info("Stopping DataFeedService...")
        if self.feed:
            await self.feed.stop()

    def get_storage(self) -> DataStorage:
        return self.storage

    async def get_latest_data(self, symbol: str = "BTCUSDT", interval: str = "1m") -> pd.DataFrame:
        """
        Returns the latest kline data as a DataFrame.
        Useful for the main loop or scoring service.
        """
        return await self.storage.get_klines_df(symbol, interval)
