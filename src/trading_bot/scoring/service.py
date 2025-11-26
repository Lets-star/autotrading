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

    # Legacy method adapter if needed, but the ticket implies a new design.
    def calculate_signals(self, market_data: pd.DataFrame) -> dict:
        """
        Adapter for legacy calls passing only market data.
        """
        data = {'candles': market_data}
        result = self.calculate_score(data)
        
        score = result['aggregated_score']
        action = "HOLD"
        if score > 0.5:
            action = "BUY"
        elif score < -0.5:
            action = "SELL"
            
        return {
            "action": action,
            "score": score,
            "details": result
        }
