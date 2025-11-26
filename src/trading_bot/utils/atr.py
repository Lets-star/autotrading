import pandas as pd
import numpy as np
from typing import Tuple, Optional

def calculate_tr(df: pd.DataFrame) -> pd.Series:
    """Calculate True Range"""
    high = df['high']
    low = df['low']
    close = df['close']
    prev_close = close.shift()
    
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr

def calculate_atr(df: pd.DataFrame, period: int = 7, method: str = 'wilder') -> pd.Series:
    """
    Calculate ATR.
    method: 'simple' (SMA) or 'wilder' (RMA/EMA)
    PineScript ta.atr uses RMA (Wilder's).
    """
    tr = calculate_tr(df)
    
    if method == 'simple':
        return tr.rolling(window=period).mean()
    elif method == 'wilder':
        # Wilder's Smoothing (RMA) is equivalent to EMA with alpha = 1/period
        return tr.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    else:
        raise ValueError(f"Unknown method: {method}")

class ATRTrailingStop:
    """
    Stateful ATR Trailing Stop Calculator.
    Adapts to TrendUp/TrendDown logic.
    """
    def __init__(self, period: int = 7, multiplier: float = 3.0):
        self.period = period
        self.multiplier = multiplier
        self.prev_close: Optional[float] = None
        self.prev_atr: Optional[float] = None
        self.prev_trend: int = 1 # 1 for Up, -1 for Down
        self.prev_upper_band: Optional[float] = None
        self.prev_lower_band: Optional[float] = None
        
        # Buffer for TR calculation
        self.tr_buffer = []

    def update(self, high: float, low: float, close: float) -> dict:
        """
        Update with new candle and return current stop levels and trend.
        """
        # Calculate TR
        if self.prev_close is None:
            tr = high - low
        else:
            tr1 = high - low
            tr2 = abs(high - self.prev_close)
            tr3 = abs(low - self.prev_close)
            tr = max(tr1, tr2, tr3)
        
        # Calculate ATR (Wilder's)
        if self.prev_atr is None:
             # Need initial buffer to start
            self.tr_buffer.append(tr)
            if len(self.tr_buffer) < self.period:
                self.prev_close = close
                return {} # Not enough data
            
            # Initial SMA for first ATR
            atr = sum(self.tr_buffer) / self.period
        else:
            atr = (self.prev_atr * (self.period - 1) + tr) / self.period
            
        # Basic Bands
        hl2 = (high + low) / 2
        basic_upper = hl2 + (self.multiplier * atr)
        basic_lower = hl2 - (self.multiplier * atr)
        
        # Final Bands Logic (SuperTrend style)
        if self.prev_upper_band is None:
            upper_band = basic_upper
            lower_band = basic_lower
        else:
            # Upper Band: lower it if basic is lower, or keep it if price didn't break it
            if (basic_upper < self.prev_upper_band) or (self.prev_close > self.prev_upper_band):
                upper_band = basic_upper
            else:
                upper_band = self.prev_upper_band
                
            # Lower Band: raise it if basic is higher, or keep it if price didn't break it
            if (basic_lower > self.prev_lower_band) or (self.prev_close < self.prev_lower_band):
                lower_band = basic_lower
            else:
                lower_band = self.prev_lower_band
        
        # Trend Direction
        if self.prev_upper_band is None:
            trend = 1 # Default
        else:
            trend = self.prev_trend
            if trend == 1:
                if close < lower_band:
                    trend = -1
            else:
                if close > upper_band:
                    trend = 1
        
        stop_loss = lower_band if trend == 1 else upper_band
        
        # Update state
        self.prev_close = close
        self.prev_atr = atr
        self.prev_upper_band = upper_band
        self.prev_lower_band = lower_band
        self.prev_trend = trend
        
        return {
            'atr': atr,
            'upper_band': upper_band,
            'lower_band': lower_band,
            'trend': trend,
            'stop_loss': stop_loss
        }
