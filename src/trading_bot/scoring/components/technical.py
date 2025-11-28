import pandas as pd
import numpy as np
from typing import Dict, Any
from trading_bot.scoring.base import ScoringComponent, ComponentScore

class TechnicalComponent(ScoringComponent):
    @property
    def category(self) -> str:
        return "Technical"

class RSI(TechnicalComponent):
    def __init__(self, period: int = 14):
        self.period = period

    @property
    def name(self) -> str:
        return "technical_rsi"

    def _calculate(self, close: pd.Series) -> pd.Series:
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=self.period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=self.period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))

    def calculate(self, data: Dict[str, Any]) -> ComponentScore:
        df = data.get('candles')
        if df is None or df.empty:
            return ComponentScore(score=0.0, confidence=0.0, category=self.category, metadata={"error": "No data"})

        rsi = self._calculate(df['close'])
        current_rsi = rsi.iloc[-1]
        
        score = 0.0
        if current_rsi > 70:
            score = -1.0 # Overbought
        elif current_rsi < 30:
            score = 1.0 # Oversold
            
        return ComponentScore(
            score=score,
            confidence=0.8,
            category=self.category,
            metadata={"value": current_rsi}
        )

class MACD(TechnicalComponent):
    def __init__(self, fast: int = 12, slow: int = 26, signal: int = 9):
        self.fast = fast
        self.slow = slow
        self.signal = signal

    @property
    def name(self) -> str:
        return "technical_macd"

    def calculate(self, data: Dict[str, Any]) -> ComponentScore:
        df = data.get('candles')
        if df is None or df.empty:
            return ComponentScore(score=0.0, confidence=0.0, category=self.category, metadata={"error": "No data"})
        
        close = df['close']
        ema_fast = close.ewm(span=self.fast, adjust=False).mean()
        ema_slow = close.ewm(span=self.slow, adjust=False).mean()
        macd = ema_fast - ema_slow
        signal_line = macd.ewm(span=self.signal, adjust=False).mean()
        hist = macd - signal_line
        
        current_hist = hist.iloc[-1]
        prev_hist = hist.iloc[-2] if len(hist) > 1 else 0
        
        score = 0.0
        # Histogram crossing above 0 -> Bullish
        if current_hist > 0:
            score = 0.5
            if current_hist > prev_hist: # Expanding bullish momentum
                score = 1.0
        else:
            score = -0.5
            if current_hist < prev_hist: # Expanding bearish momentum
                score = -1.0
                
        return ComponentScore(
            score=score,
            confidence=0.7,
            category=self.category,
            metadata={"macd": macd.iloc[-1], "signal": signal_line.iloc[-1], "hist": current_hist}
        )

class ATR(TechnicalComponent):
    def __init__(self, period: int = 14):
        self.period = period

    @property
    def name(self) -> str:
        return "technical_atr"

    def calculate(self, data: Dict[str, Any]) -> ComponentScore:
        df = data.get('candles')
        if df is None or df.empty:
            return ComponentScore(score=0.0, confidence=0.0, category=self.category, metadata={"error": "No data"})
            
        high = df['high']
        low = df['low']
        close = df['close']
        
        tr1 = high - low
        tr2 = (high - close.shift()).abs()
        tr3 = (low - close.shift()).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=self.period).mean()
        
        current_atr = atr.iloc[-1]
        
        # ATR itself is not directional, but low ATR might precede a move (squeeze)
        # For scoring, we might treat it neutrally or use it for confidence.
        # Here we'll return 0 score but high confidence if ATR is populated.
        
        return ComponentScore(
            score=0.0,
            confidence=0.5,
            category=self.category,
            metadata={"value": current_atr}
        )

class BollingerBands(TechnicalComponent):
    def __init__(self, period: int = 20, std_dev: int = 2):
        self.period = period
        self.std_dev = std_dev

    @property
    def name(self) -> str:
        return "technical_bb"

    def calculate(self, data: Dict[str, Any]) -> ComponentScore:
        df = data.get('candles')
        if df is None or df.empty:
            return ComponentScore(score=0.0, confidence=0.0, category=self.category, metadata={"error": "No data"})
        
        close = df['close']
        sma = close.rolling(window=self.period).mean()
        std = close.rolling(window=self.period).std()
        upper = sma + (std * self.std_dev)
        lower = sma - (std * self.std_dev)
        
        curr_price = close.iloc[-1]
        curr_upper = upper.iloc[-1]
        curr_lower = lower.iloc[-1]
        
        score = 0.0
        # Price > Upper -> Overbought/Momentum? Usually mean reversion -> Short
        if curr_price > curr_upper:
            score = -0.8
        # Price < Lower -> Oversold -> Long
        elif curr_price < curr_lower:
            score = 0.8
            
        return ComponentScore(
            score=score,
            confidence=0.6,
            category=self.category,
            metadata={"upper": curr_upper, "lower": curr_lower, "price": curr_price}
        )

class Divergences(TechnicalComponent):
    @property
    def name(self) -> str:
        return "technical_divergences"

    def calculate(self, data: Dict[str, Any]) -> ComponentScore:
        # Placeholder for complex divergence logic
        # Requires finding peaks/troughs in price and indicator (e.g. RSI)
        return ComponentScore(
            score=0.0,
            confidence=0.2,
            category=self.category,
            metadata={"info": "Not implemented"}
        )
