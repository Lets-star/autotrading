import asyncio
from binance import AsyncClient, BinanceSocketManager
from typing import List, Optional
from .models import Kline, Trade, OrderBook, OrderBookLevel
from .storage import DataStorage
from trading_bot.logger import get_logger

logger = get_logger(__name__)

class BinanceDataFeed:
    def __init__(self, api_key: Optional[str], api_secret: Optional[str], storage: DataStorage, symbols: List[str], intervals: List[str]):
        self.api_key = api_key
        self.api_secret = api_secret
        self.storage = storage
        self.symbols = symbols
        self.intervals = intervals
        self.client = None
        self.bm = None
        self._running = False

    async def start(self):
        self._running = True
        logger.info(f"Starting BinanceDataFeed for symbols: {self.symbols}")
        
        while self._running:
            try:
                self.client = await AsyncClient.create(self.api_key, self.api_secret)
                self.bm = BinanceSocketManager(self.client)
                
                streams = []
                for symbol in self.symbols:
                    s = symbol.lower()
                    streams.append(f"{s}@depth20@100ms") # More frequent updates, slightly deeper
                    streams.append(f"{s}@trade")
                    for interval in self.intervals:
                        streams.append(f"{s}@kline_{interval}")
                
                logger.info(f"Subscribing to streams: {streams}")
                
                ts = self.bm.multiplex_socket(streams)
                
                async with ts as tscm:
                    while self._running:
                        try:
                            res = await tscm.recv()
                            if res:
                                await self._handle_message(res)
                        except asyncio.CancelledError:
                            raise
                        except Exception as e:
                            logger.error(f"Error receiving message: {e}")
                            # Break inner loop to trigger reconnection
                            break
            except asyncio.CancelledError:
                self._running = False
                logger.info("BinanceDataFeed cancelled")
            except Exception as e:
                logger.error(f"Connection error in BinanceDataFeed: {e}")
                await asyncio.sleep(5) # Backoff before reconnecting
            finally:
                if self.client:
                    await self.client.close_connection()

    async def _handle_message(self, msg):
        try:
            stream = msg.get('stream')
            data = msg.get('data')
            
            if not stream or not data:
                return

            if 'depth' in stream:
                await self._process_depth(stream, data)
            elif 'kline' in stream:
                await self._process_kline(data)
            elif 'trade' in stream:
                await self._process_trade(data)
        except Exception as e:
            logger.error(f"Error processing message: {e} - Data: {msg}")

    async def _process_depth(self, stream, data):
        # Extract symbol from stream name (e.g. btcusdt@depth20@100ms)
        # Or from data if available? Binance partial depth data doesn't always contain symbol inside 'data' payload for multiplex?
        # Check payload structure.
        # For multiplex, stream name is provided.
        
        # stream name format: <symbol>@depth<levels>@<speed>
        symbol_lower = stream.split('@')[0]
        symbol = symbol_lower.upper()
        
        bids = [OrderBookLevel(price=float(p), quantity=float(q)) for p, q in data['bids']]
        asks = [OrderBookLevel(price=float(p), quantity=float(q)) for p, q in data['asks']]
        
        # Partial depth payload has 'lastUpdateId'
        # Regular depth update has 'u' and 'U'.
        # Since we use depth20 (partial book), it is a snapshot.
        
        ob = OrderBook(
            symbol=symbol,
            bids=bids,
            asks=asks,
            timestamp=asyncio.get_running_loop().time(), # Local timestamp or derive?
            # Binance doesn't send event time in partial depth sometimes, let's check docs.
            # Usually partial depth has no event time E.
            # We can use update_id.
            update_id=data.get('lastUpdateId', 0)
        )
        
        # We need timestamp. Let's use current time if not provided.
        ob.timestamp = int(asyncio.get_running_loop().time() * 1000)
        
        await self.storage.update_orderbook(ob)

    async def _process_kline(self, data):
        # Payload:
        # {
        #   "e": "kline",     // Event type
        #   "E": 123456789,   // Event time
        #   "s": "BNBBTC",    // Symbol
        #   "k": {
        #     "t": 123400000, // Kline start time
        #     "T": 123460000, // Kline close time
        #     "s": "BNBBTC",  // Symbol
        #     "i": "1m",      // Interval
        #     "f": 100,       // First trade ID
        #     "L": 200,       // Last trade ID
        #     "o": "0.0010",  // Open price
        #     "c": "0.0020",  // Close price
        #     "h": "0.0025",  // High price
        #     "l": "0.0015",  // Low price
        #     "v": "1000",    // Base asset volume
        #     "n": 100,       // Number of trades
        #     "x": false,     // Is this kline closed?
        #     "q": "1.0000",  // Quote asset volume
        #     ...
        #   }
        # }
        k = data['k']
        kline = Kline(
            symbol=k['s'],
            interval=k['i'],
            open=float(k['o']),
            high=float(k['h']),
            low=float(k['l']),
            close=float(k['c']),
            volume=float(k['v']),
            quote_volume=float(k['q']),
            start_time=k['t'],
            close_time=k['T'],
            is_closed=k['x'],
            trades_count=k['n']
        )
        await self.storage.add_kline(kline)

    async def _process_trade(self, data):
        # Payload:
        # {
        #   "e": "trade",     // Event type
        #   "E": 123456789,   // Event time
        #   "s": "BNBBTC",    // Symbol
        #   "t": 12345,       // Trade ID
        #   "p": "0.001",     // Price
        #   "q": "100",       // Quantity
        #   "b": 88,          // Buyer order ID
        #   "a": 50,          // Seller order ID
        #   "T": 123456785,   // Trade time
        #   "m": true,        // Is the buyer the market maker?
        #   "M": true         // Ignore
        # }
        trade = Trade(
            symbol=data['s'],
            price=float(data['p']),
            quantity=float(data['q']),
            timestamp=data['T'],
            is_buyer_maker=data['m'],
            trade_id=data['t']
        )
        await self.storage.add_trade(trade)

    async def stop(self):
        self._running = False
        if self.client:
            await self.client.close_connection()
