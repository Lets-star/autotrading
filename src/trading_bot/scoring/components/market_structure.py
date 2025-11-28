import pandas as pd
import numpy as np
from typing import Dict, Any, List, Tuple
from trading_bot.scoring.base import ScoringComponent, ComponentScore

class MarketStructureComponent(ScoringComponent):
    @property
    def category(self) -> str:
        return "Market Structure"

class HighsLows(MarketStructureComponent):
    def __init__(self, window: int = 5):
        self.window = window

    @property
    def name(self) -> str:
        return "ms_hh_ll"

    def _find_pivots(self, high: pd.Series, low: pd.Series, window: int) -> Tuple[pd.Series, pd.Series]:
        high_pivot = high.iloc[window:-window].copy()
        for i in range(1, window + 1):
            upper_neighbor = high.shift(i).reindex(high_pivot.index)
            lower_neighbor = high.shift(-i).reindex(high_pivot.index)
            high_pivot = high_pivot[(high_pivot > upper_neighbor) & (high_pivot > lower_neighbor)]
        
        low_pivot = low.iloc[window:-window].copy()
        for i in range(1, window + 1):
            upper_neighbor = low.shift(i).reindex(low_pivot.index)
            lower_neighbor = low.shift(-i).reindex(low_pivot.index)
            low_pivot = low_pivot[(low_pivot < upper_neighbor) & (low_pivot < lower_neighbor)]
            
        return high_pivot, low_pivot

    def calculate(self, data: Dict[str, Any]) -> ComponentScore:
        df = data.get('candles')
        if df is None or df.empty or len(df) < self.window * 2 + 1:
            return ComponentScore(score=0.0, confidence=0.0, category=self.category, metadata={"error": "Insufficient data"})

        highs, lows = self._find_pivots(df['high'], df['low'], self.window)
        
        if highs.empty or lows.empty:
            return ComponentScore(score=0.0, confidence=0.0, category=self.category)

        last_high = highs.index[-1]
        last_low = lows.index[-1]
        
        prev_high = highs.index[-2] if len(highs) > 1 else None
        prev_low = lows.index[-2] if len(lows) > 1 else None
        
        score = 0.0
        trend = "NEUTRAL"
        
        if prev_high and prev_low:
            curr_h_val = highs[last_high]
            curr_l_val = lows[last_low]
            prev_h_val = highs[prev_high]
            prev_l_val = lows[prev_low]
            
            if curr_h_val > prev_h_val and curr_l_val > prev_l_val:
                score = 1.0
                trend = "BULLISH"
            elif curr_h_val < prev_h_val and curr_l_val < prev_l_val:
                score = -1.0
                trend = "BEARISH"
                
        return ComponentScore(
            score=score,
            confidence=0.6,
            category=self.category,
            metadata={
                "trend": trend,
                "structure": "HH/HL" if trend == "BULLISH" else "LH/LL" if trend == "BEARISH" else "Range"
            }
        )

class BreakOfStructure(MarketStructureComponent):
    @property
    def name(self) -> str:
        return "ms_bos"

    def calculate(self, data: Dict[str, Any]) -> ComponentScore:
        # Placeholder for BoS logic. 
        # Typically requires identifying a key level and checking if price closed beyond it.
        return ComponentScore(
            score=0.0,
            confidence=0.2,
            category=self.category,
            metadata={"info": "Not implemented"}
        )
