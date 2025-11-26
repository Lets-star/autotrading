from pydantic import BaseModel, Field
from typing import List, Optional

class Trade(BaseModel):
    symbol: str
    price: float
    quantity: float
    timestamp: int
    is_buyer_maker: bool
    trade_id: int

class OrderBookLevel(BaseModel):
    price: float
    quantity: float

class OrderBook(BaseModel):
    symbol: str
    bids: List[OrderBookLevel]
    asks: List[OrderBookLevel]
    timestamp: int
    update_id: int

class Kline(BaseModel):
    symbol: str
    interval: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    quote_volume: float
    start_time: int
    close_time: int
    is_closed: bool
    trades_count: int
