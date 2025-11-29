import pandas as pd
from typing import Dict, Any, List, Optional
from trading_bot.scoring.base import ScoringComponent, ComponentScore
from trading_bot.logger import get_logger

logger = get_logger(__name__)

class CompositeScoreEngine:
    def __init__(self):
        self.components: Dict[str, ScoringComponent] = {}
        self.weights: Dict[str, float] = {}
        self.performance_history: List[Dict] = [] # Stores predictions and outcomes
        self.target_win_rate = 0.6
        self.learning_rate = 0.05
        
    def register_component(self, component: ScoringComponent, initial_weight: float = 1.0):
        self.components[component.name] = component
        self.weights[component.name] = initial_weight
        logger.info(f"Registered component {component.name} with weight {initial_weight}")

    def calculate_score(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculates the aggregated score.
        """
        component_results = {}
        weighted_sum = 0.0
        total_weight = 0.0
        
        for name, component in self.components.items():
            try:
                result: ComponentScore = component.calculate(data)
                component_results[name] = result
                
                weight = self.weights.get(name, 1.0)
                # We assume score is -1 to 1.
                weighted_sum += result.score * weight * result.confidence
                total_weight += weight * result.confidence
                
            except Exception as e:
                logger.error(f"Error in component {name}: {e}")
                component_results[name] = ComponentScore(score=0.5, confidence=0.0, metadata={"error": str(e)})

        final_score = 0.5
        if total_weight > 0:
            final_score = weighted_sum / total_weight
            
        # Store context for later update (this would need to be persisted or tracked by ID in a real system)
        # For now, we return the details and let the caller handle the feedback loop connection
        
        return {
            "aggregated_score": final_score,
            "components": {k: v.model_dump() for k, v in component_results.items()},
            "weights": self.weights.copy()
        }

    def update_weights(self, signal_context: Dict[str, Any], actual_outcome: float):
        """
        Update weights based on outcome.
        actual_outcome: 1.0 (Win/Bullish), -1.0 (Loss/Bearish) relative to the signal?
        
        Let's assume actual_outcome is the realized return direction: 1.0 (Up), -1.0 (Down).
        We want to reward components that predicted this direction.
        """
        components_data = signal_context.get("components", {})
        
        for name, data in components_data.items():
            score = data.get('score', 0.5)
            
            # If score and outcome have same sign, it was a good prediction
            # Score 0-1, outcome -1/1
            is_bullish = score > 0.5
            is_bearish = score < 0.5
            
            prediction_correct = (is_bullish and actual_outcome > 0) or (is_bearish and actual_outcome < 0)
            
            # Adjust weight
            current_weight = self.weights.get(name, 1.0)
            
            if prediction_correct:
                # Increase weight slightly
                new_weight = current_weight * (1 + self.learning_rate)
            else:
                # Decrease weight, but keep it bounded
                if abs(score - 0.5) > 0.01: # Only penalize if it had an opinion
                    new_weight = current_weight * (1 - self.learning_rate)
                else:
                    new_weight = current_weight
            
            # Clamp weights to sensible range e.g. 0.1 to 10.0
            new_weight = max(0.1, min(10.0, new_weight))
            self.weights[name] = new_weight
            
        logger.info(f"Updated weights: {self.weights}")
