from typing import Dict, Any
from trading_bot.scoring.base import ScoringComponent, ComponentScore

class SentimentAnalysis(ScoringComponent):
    @property
    def category(self) -> str:
        return "Sentiment/Fundamentals"

    @property
    def name(self) -> str:
        return "sentiment"

    def calculate(self, data: Dict[str, Any]) -> ComponentScore:
        sentiment_data = data.get('sentiment')
        
        if not sentiment_data:
            # If no sentiment data provided, return neutral
            return ComponentScore(score=0.0, confidence=0.0, category=self.category, metadata={"status": "no_data"})
            
        # Expecting sentiment_data to be a dict like {"score": 0.5, "source": "news_api"}
        # Score assumed to be -1 to 1
        raw_score = sentiment_data.get('score', 0.0)
        source = sentiment_data.get('source', 'unknown')
        
        # Validate range
        score = max(-1.0, min(1.0, float(raw_score)))
        
        return ComponentScore(
            score=score,
            confidence=0.6, # Static confidence for external data
            category=self.category,
            metadata={
                "source": source
            }
        )
