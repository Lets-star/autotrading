import pandas as pd
from typing import Dict, Any
from trading_bot.scoring.base import ScoringComponent, ComponentScore

class MultiTimeframeAlignment(ScoringComponent):
    def __init__(self, timeframes: list = ['5m', '15m', '1h']):
        self.timeframes = timeframes

    @property
    def name(self) -> str:
        return "multi_timeframe"

    def _get_trend(self, df: pd.DataFrame) -> int:
        # Simple trend: Close > SMA(20) -> 1, else -1
        if df.empty or len(df) < 20:
            return 0
        sma = df['close'].rolling(window=20).mean()
        
        current_sma = sma.iloc[-1]
        if pd.isna(current_sma):
            return 0
            
        if df['close'].iloc[-1] > current_sma:
            return 1
        return -1

    def calculate(self, data: Dict[str, Any]) -> ComponentScore:
        mtf_data = data.get('mtf_candles', {})
        
        if not mtf_data:
            return ComponentScore(score=0.0, confidence=0.0, metadata={"error": "No MTF data"})

        trends = []
        for tf in self.timeframes:
            df = mtf_data.get(tf)
            if df is not None:
                trends.append(self._get_trend(df))
        
        if not trends:
            return ComponentScore(score=0.0, confidence=0.0)

        # Alignment
        avg_trend = sum(trends) / len(trends)
        
        # Confidence is high if all agree
        agreement = abs(sum(trends)) / len(trends) # 1.0 if all agree, lower otherwise
        
        return ComponentScore(
            score=avg_trend,
            confidence=agreement,
            metadata={
                "timeframes": self.timeframes,
                "trends": trends
            }
        )
