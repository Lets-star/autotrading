import pandas as pd
import numpy as np
from typing import Dict, Any, List, Tuple
from trading_bot.scoring.base import ScoringComponent, ComponentScore

class MarketStructure(ScoringComponent):
    def __init__(self, window: int = 5):
        self.window = window

    @property
    def name(self) -> str:
        return "market_structure"

    def _find_pivots(self, high: pd.Series, low: pd.Series, window: int) -> Tuple[pd.Series, pd.Series]:
        # High pivot: High is max in window * 2 + 1
        high_pivot = high.iloc[window:-window].copy()
        for i in range(1, window + 1):
            upper_neighbor = high.shift(i).reindex(high_pivot.index)
            lower_neighbor = high.shift(-i).reindex(high_pivot.index)
            high_pivot = high_pivot[(high_pivot > upper_neighbor) & (high_pivot > lower_neighbor)]
        
        # Low pivot: Low is min in window * 2 + 1
        low_pivot = low.iloc[window:-window].copy()
        for i in range(1, window + 1):
            upper_neighbor = low.shift(i).reindex(low_pivot.index)
            lower_neighbor = low.shift(-i).reindex(low_pivot.index)
            low_pivot = low_pivot[(low_pivot < upper_neighbor) & (low_pivot < lower_neighbor)]
            
        return high_pivot, low_pivot

    def calculate(self, data: Dict[str, Any]) -> ComponentScore:
        df = data.get('candles')
        if df is None or df.empty or len(df) < self.window * 2 + 1:
            return ComponentScore(score=0.0, confidence=0.0, metadata={"error": "Insufficient data"})

        highs, lows = self._find_pivots(df['high'], df['low'], self.window)
        
        if highs.empty or lows.empty:
            return ComponentScore(score=0.0, confidence=0.0)

        last_high = highs.index[-1]
        last_low = lows.index[-1]
        
        prev_high = highs.index[-2] if len(highs) > 1 else None
        prev_low = lows.index[-2] if len(lows) > 1 else None
        
        score = 0.0
        trend = "NEUTRAL"
        
        # Detect Trend
        if prev_high and prev_low:
            curr_h_val = highs[last_high]
            curr_l_val = lows[last_low]
            prev_h_val = highs[prev_high]
            prev_l_val = lows[prev_low]
            
            # HH and HL -> Bullish
            if curr_h_val > prev_h_val and curr_l_val > prev_l_val:
                score = 1.0
                trend = "BULLISH"
            # LH and LL -> Bearish
            elif curr_h_val < prev_h_val and curr_l_val < prev_l_val:
                score = -1.0
                trend = "BEARISH"
                
        # If the most recent pivot is very recent, confidence is higher
        confidence = 0.5
        
        return ComponentScore(
            score=score,
            confidence=confidence,
            metadata={
                "trend": trend,
                "last_high_idx": str(last_high),
                "last_low_idx": str(last_low)
            }
        )
