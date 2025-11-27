import pandas as pd
from typing import Dict, Any, Optional
from trading_bot.logger import get_logger
from trading_bot.scoring.engine import CompositeScoreEngine
from trading_bot.scoring.components.technical import TechnicalIndicators
from trading_bot.scoring.components.orderbook import OrderbookImbalance
from trading_bot.scoring.components.market_structure import MarketStructure
from trading_bot.scoring.components.sentiment import SentimentAnalysis
from trading_bot.scoring.components.multi_timeframe import MultiTimeframeAlignment

logger = get_logger(__name__)

class ScoringService:
    def __init__(self):
        self.engine = CompositeScoreEngine()
        self._register_default_components()
        logger.info("Initialized ScoringService with CompositeScoreEngine")

    def _register_default_components(self):
        self.engine.register_component(TechnicalIndicators(), initial_weight=1.2)
        self.engine.register_component(OrderbookImbalance(), initial_weight=1.0)
        self.engine.register_component(MarketStructure(), initial_weight=1.5)
        self.engine.register_component(SentimentAnalysis(), initial_weight=0.8)
        self.engine.register_component(MultiTimeframeAlignment(), initial_weight=1.1)

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

    def calculate_signals(self, market_data: pd.DataFrame) -> dict:
        """
        Adapter for calls passing only market data (e.g. from backtester).
        """
        if market_data.empty:
            return {"action": "HOLD", "score": 0.0}

        latest = market_data.iloc[-1]
        
        # We only have market_data (candles) here, so other components 
        # like orderbook, sentiment, mtf might yield 0 score or errors, 
        # but that's expected if data isn't provided.
        data = {'candles': market_data}
        result = self.calculate_score(data)
        
        score = result['aggregated_score']
        action = "HOLD"
        
        # Thresholds
        if score > 0.5:
            action = "BUY"
        elif score < -0.5:
            action = "SELL"
            
        return {
            "action": action,
            "score": score,
            "price": float(latest['close']),
            "timestamp": latest.get('timestamp'),
            "details": result
        }
