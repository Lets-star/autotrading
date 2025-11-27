import pandas as pd
import numpy as np
from typing import Dict, Any
from trading_bot.scoring.base import ScoringComponent, ComponentScore

class TechnicalIndicators(ScoringComponent):
    def __init__(self, rsi_period: int = 14, ema_short: int = 9, ema_long: int = 21):
        self.rsi_period = rsi_period
        self.ema_short = ema_short
        self.ema_long = ema_long

    @property
    def name(self) -> str:
        return "technical_indicators"

    def _calculate_rsi(self, close: pd.Series, period: int) -> pd.Series:
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))

    def _calculate_ema(self, close: pd.Series, period: int) -> pd.Series:
        return close.ewm(span=period, adjust=False).mean()

    def _calculate_atr(self, high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
        tr1 = high - low
        tr2 = (high - close.shift()).abs()
        tr3 = (low - close.shift()).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        return tr.rolling(window=period).mean()

    def calculate(self, data: Dict[str, Any]) -> ComponentScore:
        df = data.get('candles')
        if df is None or df.empty:
            return ComponentScore(score=0.0, confidence=0.0, metadata={"error": "No data"})

        close = df['close']
        
        # Calculate Indicators
        rsi = self._calculate_rsi(close, self.rsi_period)
        ema_s = self._calculate_ema(close, self.ema_short)
        ema_l = self._calculate_ema(close, self.ema_long)
        
        if rsi.empty or ema_s.empty or ema_l.empty:
             return ComponentScore(score=0.0, confidence=0.0, metadata={"error": "Insufficient data"})

        current_rsi = rsi.iloc[-1]
        current_ema_s = ema_s.iloc[-1]
        current_ema_l = ema_l.iloc[-1]
        
        if pd.isna(current_rsi) or pd.isna(current_ema_s) or pd.isna(current_ema_l):
            return ComponentScore(score=0.0, confidence=0.0, metadata={"error": "Insufficient data for indicators"})
        
        # Simple Logic: 
        # RSI > 70 -> Overbought (-1)
        # RSI < 30 -> Oversold (+1)
        # EMA Short > EMA Long -> Bullish (+1)
        # EMA Short < EMA Long -> Bearish (-1)
        
        score_rsi = 0.0
        if current_rsi > 70:
            score_rsi = -1.0
        elif current_rsi < 30:
            score_rsi = 1.0
            
        score_ema = 1.0 if current_ema_s > current_ema_l else -1.0
        
        # Combine scores
        final_score = (score_rsi + score_ema) / 2.0
        
        # Confidence could be based on volatility or indicator agreement
        confidence = 0.5 
        if (score_rsi > 0 and score_ema > 0) or (score_rsi < 0 and score_ema < 0):
            confidence = 0.8
            
        return ComponentScore(
            score=final_score,
            confidence=confidence,
            metadata={
                "rsi": current_rsi,
                "ema_short": current_ema_s,
                "ema_long": current_ema_l
            }
        )
