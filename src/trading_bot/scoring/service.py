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
        
        # Signal parameters
        self.long_threshold = 0.6
        self.short_threshold = 0.4
        self.confidence_threshold = 0.5
        
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

    def update_weights_from_groups(self, groups: Dict[str, float], sub_weights: Dict[str, float]):
        """
        Update engine weights based on normalized group weights and sub-weights.
        groups: {'Technical': 0.2, 'Orderbook': 0.2, ...}
        sub_weights: {'technical_rsi': 0.2, 'technical_macd': 0.2, ...} (Sum to 1 within group)
        """
        # Technical
        tech_w = groups.get('Technical', 0.2)
        self.engine.weights['technical_rsi'] = tech_w * sub_weights.get('technical_rsi', 0.2)
        self.engine.weights['technical_macd'] = tech_w * sub_weights.get('technical_macd', 0.2)
        self.engine.weights['technical_atr'] = tech_w * sub_weights.get('technical_atr', 0.2)
        self.engine.weights['technical_bb'] = tech_w * sub_weights.get('technical_bb', 0.2)
        self.engine.weights['technical_divergences'] = tech_w * sub_weights.get('technical_divergences', 0.2)
        
        # Orderbook
        ob_w = groups.get('Orderbook', 0.2)
        # Distribute equally (4 components)
        ob_comp_w = ob_w / 4.0
        self.engine.weights['ob_imbalance'] = ob_comp_w
        self.engine.weights['ob_liquidity'] = ob_comp_w
        self.engine.weights['ob_smart_money'] = ob_comp_w
        self.engine.weights['ob_mm'] = ob_comp_w
        
        # Market Structure
        ms_w = groups.get('MarketStructure', 0.2)
        # Distribute equally (2 components)
        ms_comp_w = ms_w / 2.0
        self.engine.weights['ms_hh_ll'] = ms_comp_w
        self.engine.weights['ms_bos'] = ms_comp_w
        
        # Sentiment
        sent_w = groups.get('Sentiment', 0.2)
        self.engine.weights['sentiment'] = sent_w
        
        # MTF
        mtf_w = groups.get('MultiTimeframe', 0.2)
        self.engine.weights['multi_timeframe'] = mtf_w
        
        logger.info("Weights updated from groups")

    def update_signal_parameters(self, long_th: float, short_th: float, confidence_th: float):
        self.long_threshold = long_th
        self.short_threshold = short_th
        self.confidence_threshold = confidence_th
        logger.info(f"Signal parameters updated: L>{long_th}, S<{short_th}, Conf>{confidence_th}")

    def calculate_signals(self, market_data: pd.DataFrame, mtf_data: Optional[Dict[str, pd.DataFrame]] = None) -> dict:
        """
        Adapter for legacy calls passing only market data.
        """
        data = {'candles': market_data}
        if mtf_data:
            data['mtf_candles'] = mtf_data
            
        result = self.calculate_score(data)
        
        score = result['aggregated_score']
        
        # Check overall confidence? result['components']...
        # We don't have a top-level confidence metric in engine output yet, 
        # but we can infer or it might be needed.
        # For now, we rely on score.
        
        action = "NEUTRAL"
        
        if score >= self.long_threshold:
            action = "BUY"
            if score >= self.long_threshold + 0.1: # Heuristic for STRONG
                action = "STRONG BUY"
        elif score <= self.short_threshold:
            action = "SELL"
            if score <= self.short_threshold - 0.1:
                action = "STRONG SELL"
            
        return {
            "action": action,
            "score": score,
            "details": result
        }
