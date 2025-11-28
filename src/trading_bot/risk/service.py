from trading_bot.logger import get_logger
from trading_bot.config import settings

logger = get_logger(__name__)

from typing import Tuple

class RiskService:
    def __init__(self):
        self.risk_limit_amount = settings.risk_limit_amount
        self.atr_multiplier = settings.atr_multiplier
        logger.info("Initialized RiskService")

    def validate_order(self, order_params: dict) -> Tuple[bool, str]:
        amount = order_params.get("amount", 0.0)
        if amount > self.risk_limit_amount:
            msg = f"Order amount {amount} exceeds risk limit {self.risk_limit_amount}"
            logger.warning(msg)
            return False, msg
        return True, "OK"

    def calculate_stop_loss(self, entry_price: float, atr: float) -> float:
        stop_loss = entry_price - (atr * self.atr_multiplier)
        return stop_loss
