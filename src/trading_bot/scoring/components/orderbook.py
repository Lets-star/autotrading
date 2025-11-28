from typing import Dict, Any, List
from trading_bot.scoring.base import ScoringComponent, ComponentScore

class OrderbookComponent(ScoringComponent):
    @property
    def category(self) -> str:
        return "Orderbook & Volume"

class OrderImbalance(OrderbookComponent):
    @property
    def name(self) -> str:
        return "ob_imbalance"

    def calculate(self, data: Dict[str, Any]) -> ComponentScore:
        orderbook = data.get('orderbook')
        if not orderbook:
            return ComponentScore(score=0.0, confidence=0.0, category=self.category, metadata={"error": "No orderbook data"})

        bids = orderbook.get('bids', [])
        asks = orderbook.get('asks', [])

        if not bids or not asks:
            return ComponentScore(score=0.0, confidence=0.0, category=self.category)

        # Calculate volume imbalance for top N levels
        depth = 10
        bid_vol = sum(float(b[1]) for b in bids[:depth])
        ask_vol = sum(float(a[1]) for a in asks[:depth])
        
        total_vol = bid_vol + ask_vol
        if total_vol == 0:
            return ComponentScore(score=0.0, confidence=0.0, category=self.category)
            
        imbalance = (bid_vol - ask_vol) / total_vol
        
        return ComponentScore(
            score=imbalance,
            confidence=0.7,
            category=self.category,
            metadata={
                "bid_vol": bid_vol,
                "ask_vol": ask_vol,
                "imbalance": imbalance
            }
        )

class Liquidity(OrderbookComponent):
    @property
    def name(self) -> str:
        return "ob_liquidity"

    def calculate(self, data: Dict[str, Any]) -> ComponentScore:
        orderbook = data.get('orderbook')
        if not orderbook:
            return ComponentScore(score=0.0, confidence=0.0, category=self.category, metadata={"error": "No data"})

        bids = orderbook.get('bids', [])
        asks = orderbook.get('asks', [])
        
        # Simple liquidity metric: total volume in top 20 levels
        depth = 20
        bid_vol = sum(float(b[1]) for b in bids[:depth])
        ask_vol = sum(float(a[1]) for a in asks[:depth])
        total_liquidity = bid_vol + ask_vol
        
        # Normalize? Hard without historical context. 
        # For now, we return 0 score (neutral) but use it as a metric.
        # High liquidity might mean higher confidence in price stability or harder to move price.
        
        return ComponentScore(
            score=0.0, 
            confidence=0.5,
            category=self.category,
            metadata={"liquidity": total_liquidity}
        )

class SmartMoney(OrderbookComponent):
    @property
    def name(self) -> str:
        return "ob_smart_money"

    def calculate(self, data: Dict[str, Any]) -> ComponentScore:
        # Placeholder for Smart Money Tracking (e.g. large orders)
        return ComponentScore(
            score=0.0,
            confidence=0.1,
            category=self.category,
            metadata={"info": "Not implemented"}
        )

class MarketMaker(OrderbookComponent):
    @property
    def name(self) -> str:
        return "ob_mm"
        
    def calculate(self, data: Dict[str, Any]) -> ComponentScore:
        # Placeholder for MM activity
        return ComponentScore(
            score=0.0,
            confidence=0.1,
            category=self.category,
            metadata={"info": "Not implemented"}
        )
