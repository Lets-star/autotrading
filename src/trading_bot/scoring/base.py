from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from pydantic import BaseModel

class ComponentScore(BaseModel):
    score: float  # Normalized score (e.g., -1.0 to 1.0 for directional, or 0.0 to 1.0)
    confidence: float # 0.0 to 1.0
    category: str = "Uncategorized"
    metadata: Dict[str, Any] = {}

class ScoringComponent(ABC):
    @property
    def category(self) -> str:
        """Category of the component"""
        return "Uncategorized"

    @abstractmethod
    def calculate(self, data: Dict[str, Any]) -> ComponentScore:
        """
        Calculate score based on provided data.
        data: A dictionary containing market data, orderbook, sentiment etc.
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the component"""
        pass
