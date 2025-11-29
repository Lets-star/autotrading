import asyncio
import time
from typing import List, Optional
from pybit.unified_trading import WebSocket
from .models import Kline, Trade, OrderBook, OrderBookLevel
from .storage import DataStorage
from trading_bot.logger import get_logger

logger = get_logger(__name__)

class BybitDataFeed:
    def __init__(self, api_key: Optional[str], api_secret: Optional[str], storage: DataStorage, symbols: List[str], intervals: List[str]):
        self.api_key = api_key
        self.api_secret = api_secret
        self.storage = storage
        self.symbols = symbols
        self.intervals = intervals
        self.ws = None
        self._running = False
        
        # Map bot intervals to Bybit intervals
        # 1m, 3m, 5m, 15m, 30m, 60, 120, 240, 360, 720, D, M, W
        self.interval_map = {
            "1m": 1,
            "5m": 5,
            "15m": 15,
            "30m": 30,
            "1h": 60,
            "4h": 240,
            "1d": "D"
        }

    async def start(self):
        self._running = True
        logger.info(f"Starting BybitDataFeed for symbols: {self.symbols}")
        
        # Start WebSocket
        # Note: Pybit WebSocket runs in a separate thread. We need to bridge it to asyncio if we want async storage updates.
        # But for now, we can just run storage updates in the callback (which might be in a thread), 
        # but since storage uses asyncio.Lock, we need to be careful.
        # Ideally, we should use loop.call_soon_threadsafe or run_coroutine_threadsafe.
        
        try:
            self.loop = asyncio.get_running_loop()
            
            self.ws = WebSocket(
                testnet=False,
                channel_type="linear",
                api_key=self.api_key,
                api_secret=self.api_secret
            )
            
            for symbol in self.symbols:
                # Orderbook
                self.ws.orderbook_stream(
                    depth=50,
                    symbol=symbol,
                    callback=self._handle_orderbook
                )
                
                # Trades
                self.ws.trade_stream(
                    symbol=symbol,
                    callback=self._handle_trade
                )
                
                # Klines
                for interval in self.intervals:
                    bybit_interval = self.interval_map.get(interval)
                    if bybit_interval:
                        self.ws.kline_stream(
                            interval=bybit_interval,
                            symbol=symbol,
                            callback=lambda msg, i=interval: self._handle_kline(msg, i)
                        )
                        
            while self._running:
                await asyncio.sleep(1)
                
        except Exception as e:
            logger.error(f"Error in BybitDataFeed: {e}")
            
    async def stop(self):
        self._running = False
        logger.info("Stopping BybitDataFeed...")
        # Pybit WebSocket doesn't have a clean explicit close/stop method in some versions or it's just exit.
        # Usually garbage collection or simple exit handles it.
        pass

    def _handle_orderbook(self, message):
        try:
            # {
            #     "topic": "orderbook.50.BTCUSDT",
            #     "type": "snapshot",
            #     "ts": 1672304484978,
            #     "data": {
            #         "s": "BTCUSDT",
            #         "b": [["16628.00", "0.01"], ...],
            #         "a": [["16628.50", "0.01"], ...],
            #         ...
            #     }
            # }
            data = message.get('data')
            if not data: return

            symbol = data.get('s')
            bids = [OrderBookLevel(price=float(p), quantity=float(q)) for p, q in data.get('b', [])]
            asks = [OrderBookLevel(price=float(p), quantity=float(q)) for p, q in data.get('a', [])]
            
            ob = OrderBook(
                symbol=symbol,
                bids=bids,
                asks=asks,
                timestamp=message.get('ts'),
                update_id=data.get('u', 0)
            )
            
            asyncio.run_coroutine_threadsafe(self.storage.update_orderbook(ob), self.loop)
            
        except Exception as e:
            logger.error(f"Error processing Bybit orderbook: {e}")

    def _handle_trade(self, message):
        try:
            # {
            #     "topic": "publicTrade.BTCUSDT",
            #     "data": [
            #         {
            #             "T": 1672304486866,
            #             "s": "BTCUSDT",
            #             "S": "Buy",
            #             "v": "0.001",
            #             "p": "16578.50",
            #             ...
            #         }
            #     ]
            # }
            data_list = message.get('data', [])
            for item in data_list:
                trade = Trade(
                    symbol=item.get('s'),
                    price=float(item.get('p')),
                    quantity=float(item.get('v')),
                    timestamp=item.get('T'),
                    is_buyer_maker=(item.get('S') == 'Sell'), # If side is Sell, then maker was... wait. 
                    # Bybit: S is "Buy" or "Sell" (Taker side).
                    # If Taker is Buy, then Maker was Sell.
                    # Binance: is_buyer_maker = True if maker was buyer.
                    # If Taker Side is "Buy", then Taker is Buyer. Maker is Seller. is_buyer_maker = False.
                    # If Taker Side is "Sell", then Taker is Seller. Maker is Buyer. is_buyer_maker = True.
                    trade_id=0 # Bybit trade ID is uuid string 'i', model expects int
                )
                # Hack for trade_id being int in model
                # We can just generate one or hash it.
                # Or just use timestamp.
                
                asyncio.run_coroutine_threadsafe(self.storage.add_trade(trade), self.loop)
                
        except Exception as e:
            logger.error(f"Error processing Bybit trade: {e}")

    def _handle_kline(self, message, interval_str):
        try:
            # {
            #     "data": [
            #         {
            #             "start": 1672324800000,
            #             "end": 1672324859999,
            #             "interval": "1",
            #             "open": "16656.0",
            #             ...
            #             "confirm": false
            #         }
            #     ]
            # }
            data_list = message.get('data', [])
            for item in data_list:
                # symbol is in topic: kline.1.BTCUSDT
                topic = message.get('topic', '')
                parts = topic.split('.')
                symbol = parts[-1] if len(parts) > 0 else ""
                
                kline = Kline(
                    symbol=symbol,
                    interval=interval_str,
                    open=float(item.get('open')),
                    high=float(item.get('high')),
                    low=float(item.get('low')),
                    close=float(item.get('close')),
                    volume=float(item.get('volume')),
                    quote_volume=float(item.get('turnover')),
                    start_time=int(item.get('start')),
                    close_time=int(item.get('end')),
                    is_closed=item.get('confirm', False),
                    trades_count=0 # Bybit kline stream doesn't give trade count
                )
                
                asyncio.run_coroutine_threadsafe(self.storage.add_kline(kline), self.loop)
                
        except Exception as e:
            logger.error(f"Error processing Bybit kline: {e}")
