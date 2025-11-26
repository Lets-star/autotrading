from typing import Dict, Any, List
from trading_bot.scoring.base import ScoringComponent, ComponentScore

class OrderbookImbalance(ScoringComponent):
    @property
    def name(self) -> str:
        return "orderbook_imbalance"

    def calculate(self, data: Dict[str, Any]) -> ComponentScore:
        orderbook = data.get('orderbook')
        if not orderbook:
            return ComponentScore(score=0.0, confidence=0.0, metadata={"error": "No orderbook data"})

        bids = orderbook.get('bids', [])
        asks = orderbook.get('asks', [])

        if not bids or not asks:
            return ComponentScore(score=0.0, confidence=0.0)

        # Calculate volume imbalance for top N levels
        depth = 10
        bid_vol = sum(float(b[1]) for b in bids[:depth])
        ask_vol = sum(float(a[1]) for a in asks[:depth])
        
        total_vol = bid_vol + ask_vol
        if total_vol == 0:
            return ComponentScore(score=0.0, confidence=0.0)
            
        imbalance = (bid_vol - ask_vol) / total_vol
        
        # Imbalance is typically -1 to 1. 
        # Positive means more bids (Bullish)
        # Negative means more asks (Bearish)
        
        # Confidence increases as total volume increases (simple heuristic)
        # or if the imbalance is significant.
        confidence = min(total_vol / 10.0, 1.0) # Placeholder normalization for confidence
        
        return ComponentScore(
            score=imbalance,
            confidence=0.7, # Static confidence for now or use depth metrics
            metadata={
                "bid_vol": bid_vol,
                "ask_vol": ask_vol,
                "imbalance": imbalance
            }
        )
