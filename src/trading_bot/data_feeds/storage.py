import pandas as pd
import asyncio
from collections import deque, defaultdict
from typing import Dict, List, Optional
from .models import Kline, Trade, OrderBook

class DataStorage:
    def __init__(self, max_history: int = 1000):
        self._trades: Dict[str, deque] = defaultdict(lambda: deque(maxlen=max_history))
        # symbol -> interval -> deque of Kline
        self._klines: Dict[str, Dict[str, deque]] = defaultdict(lambda: defaultdict(lambda: deque(maxlen=max_history)))
        self._orderbooks: Dict[str, OrderBook] = {}
        self._lock = asyncio.Lock()
        self.max_history = max_history

    async def add_trade(self, trade: Trade):
        async with self._lock:
            self._trades[trade.symbol].append(trade)

    async def add_kline(self, kline: Kline):
        async with self._lock:
            # We only store closed klines for history, or maybe update the last one if open?
            # Typically for analysis we want closed klines, but for realtime we might want the current incomplete one.
            # Strategy: Store closed klines. Maintain a separate "current_kline" if needed.
            # But the deque approach is simple. If the new kline has the same start time as the last one, replace it.
            
            dq = self._klines[kline.symbol][kline.interval]
            if dq and dq[-1].start_time == kline.start_time:
                dq[-1] = kline
            else:
                dq.append(kline)

    async def update_orderbook(self, orderbook: OrderBook):
        async with self._lock:
            self._orderbooks[orderbook.symbol] = orderbook

    async def get_klines_df(self, symbol: str, interval: str) -> pd.DataFrame:
        async with self._lock:
            data = list(self._klines[symbol][interval])
            if not data:
                return pd.DataFrame()
            return pd.DataFrame([k.model_dump() for k in data])

    async def get_trades_df(self, symbol: str) -> pd.DataFrame:
        async with self._lock:
            data = list(self._trades[symbol])
            if not data:
                return pd.DataFrame()
            return pd.DataFrame([t.model_dump() for t in data])
    
    async def get_latest_orderbook(self, symbol: str) -> Optional[OrderBook]:
         async with self._lock:
             return self._orderbooks.get(symbol)

    async def get_rolling_stats(self, symbol: str, interval: str, window: int, column: str = 'close', metric: str = 'mean') -> float:
        """
        Computes rolling statistics for a given symbol and interval.
        """
        async with self._lock:
            data = list(self._klines[symbol][interval])
            
        if not data or len(data) < window:
            return 0.0
            
        df = pd.DataFrame([k.model_dump() for k in data])
        
        if column not in df.columns:
            return 0.0
            
        if metric == 'mean':
            return df[column].rolling(window).mean().iloc[-1]
        elif metric == 'std':
            return df[column].rolling(window).std().iloc[-1]
        elif metric == 'max':
             return df[column].rolling(window).max().iloc[-1]
        elif metric == 'min':
             return df[column].rolling(window).min().iloc[-1]
             
        return 0.0

    async def aggregate_klines(self, symbol: str, source_interval: str, target_interval_minutes: int) -> List[Kline]:
        """
        Aggregates klines from a source interval to a target interval (in minutes).
        Assumes source_interval is '1m'.
        """
        # This is a simplified aggregation logic
        # In a real scenario, parsing interval strings to timedeltas would be better.
        if source_interval != '1m':
             # For now only supporting 1m aggregation
             return []

        async with self._lock:
            data = list(self._klines[symbol][source_interval])
        
        if not data:
            return []
            
        df = pd.DataFrame([k.model_dump() for k in data])
        df['timestamp'] = pd.to_datetime(df['start_time'], unit='ms')
        df.set_index('timestamp', inplace=True)
        
        # Resample
        resampled = df.resample(f'{target_interval_minutes}min').agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum',
            'quote_volume': 'sum',
            'start_time': 'first',
            'close_time': 'last',
            'trades_count': 'sum',
            'symbol': 'first',
            'is_closed': 'last' # Approximation
        }).dropna()

        # Convert back to Klines
        result = []
        for _, row in resampled.iterrows():
             # We need to handle potential NaNs if logic was complex, but dropna handles it.
             # Construct Kline object
             k = Kline(
                 symbol=row['symbol'],
                 interval=f"{target_interval_minutes}m",
                 open=row['open'],
                 high=row['high'],
                 low=row['low'],
                 close=row['close'],
                 volume=row['volume'],
                 quote_volume=row['quote_volume'],
                 start_time=int(row['start_time']),
                 close_time=int(row['close_time']),
                 is_closed=True, # Aggregated bars are usually considered closed
                 trades_count=int(row['trades_count'])
             )
             result.append(k)
        return result
