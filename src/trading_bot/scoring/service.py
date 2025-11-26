import pandas as pd
import numpy as np
# import talib # Requires C library
from trading_bot.logger import get_logger
from trading_bot.config import settings

logger = get_logger(__name__)

class ScoringService:
    def __init__(self):
        logger.info("Initialized ScoringService")

    def calculate_signals(self, market_data: pd.DataFrame) -> dict:
        """
        Calculate trading signals based on market data.
        """
        # logger.debug("Calculating signals...")
        if market_data.empty or len(market_data) < 21:
            return {"action": "HOLD", "score": 0.0}
        
        # Simple Moving Average Crossover Strategy
        # Use .copy() to avoid SettingWithCopyWarning if a slice is passed
        df = market_data.copy()
        df['sma_fast'] = df['close'].rolling(window=5).mean()
        df['sma_slow'] = df['close'].rolling(window=20).mean()
        
        latest = df.iloc[-1]
        prev = df.iloc[-2]
        
        action = "HOLD"
        score = 0.0
        
        if pd.notna(latest['sma_fast']) and pd.notna(latest['sma_slow']) and \
           pd.notna(prev['sma_fast']) and pd.notna(prev['sma_slow']):
            
            if latest['sma_fast'] > latest['sma_slow'] and prev['sma_fast'] <= prev['sma_slow']:
                action = "BUY"
                score = 0.8
            elif latest['sma_fast'] < latest['sma_slow'] and prev['sma_fast'] >= prev['sma_slow']:
                action = "SELL"
                score = -0.8
        
        return {
            "action": action, 
            "score": score, 
            "price": float(latest['close']),
            "timestamp": latest.get('timestamp')
        }
