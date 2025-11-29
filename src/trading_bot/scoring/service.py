import pandas as pd
from typing import Dict, Any, Optional
from trading_bot.logger import get_logger
from trading_bot.scoring.engine import CompositeScoreEngine
from trading_bot.scoring.components.technical import RSI, MACD, ATR, BollingerBands, Divergences
from trading_bot.scoring.components.orderbook import OrderImbalance, Liquidity, SmartMoney, MarketMaker
from trading_bot.scoring.components.market_structure import HighsLows, BreakOfStructure
from trading_bot.scoring.components.sentiment import SentimentAnalysis
from trading_bot.scoring.components.multi_timeframe import MultiTimeframeAlignment

logger = get_logger(__name__)

class ScoringService:
    def __init__(self, active_timeframes: Optional[list] = None):
        self.active_timeframes = active_timeframes or ['5m', '15m', '1h']
        self.engine = CompositeScoreEngine()
        self._register_default_components()
        logger.info(f"Initialized ScoringService with timeframes: {self.active_timeframes}")

    def _register_default_components(self):
        # Technical
        self.engine.register_component(RSI(), initial_weight=1.0)
        self.engine.register_component(MACD(), initial_weight=1.2)
        self.engine.register_component(ATR(), initial_weight=0.5)
        self.engine.register_component(BollingerBands(), initial_weight=1.0)
        self.engine.register_component(Divergences(), initial_weight=1.5)
        
        # Orderbook
        self.engine.register_component(OrderImbalance(), initial_weight=1.2)
        self.engine.register_component(Liquidity(), initial_weight=0.8)
        self.engine.register_component(SmartMoney(), initial_weight=1.0)
        self.engine.register_component(MarketMaker(), initial_weight=0.5)
        
        # Market Structure
        self.engine.register_component(HighsLows(), initial_weight=1.5)
        self.engine.register_component(BreakOfStructure(), initial_weight=1.5)
        
        # Sentiment
        self.engine.register_component(SentimentAnalysis(), initial_weight=0.8)
        
        # Multi-timeframe
        self.engine.register_component(MultiTimeframeAlignment(timeframes=self.active_timeframes), initial_weight=1.1)

    def calculate_score(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Unified API to calculate composite score.
        data: Dictionary containing 'candles', 'orderbook', 'sentiment', 'mtf_candles' etc.
        """
        return self.engine.calculate_score(data)

    def update_weights(self, signal_context: Dict[str, Any], outcome: float):
        """
        Update weights based on realized outcome.
        outcome: >0 for Win, <0 for Loss
        """
        self.engine.update_weights(signal_context, outcome)

    def calculate_signals(self, market_data: pd.DataFrame, mtf_data: Optional[Dict[str, pd.DataFrame]] = None) -> dict:
        """
        Adapter for legacy calls passing only market data.
        """
        data = {'candles': market_data}
        if mtf_data:
            data['mtf_candles'] = mtf_data
            
        result = self.calculate_score(data)
        
        score = result['aggregated_score']
        action = "NEUTRAL"
        
        if score >= 0.7:
            action = "STRONG BUY"
        elif score >= 0.6:
            action = "BUY"
        elif score <= 0.3:
            action = "STRONG SELL"
        elif score <= 0.4:
            action = "SELL"
            
        return {
            "action": action,
            "score": score,
            "details": result
        }
