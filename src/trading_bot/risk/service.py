from trading_bot.logger import get_logger
from trading_bot.config import settings
from typing import Tuple, List

logger = get_logger(__name__)

class RiskService:
    def __init__(self):
        self.max_position_size_usd = settings.risk_limit_amount
        self.max_risk_per_trade_pct = 0.01
        self.leverage = 1
        self.tp_multipliers = [1.5, 3.0, 5.0]
        self.sl_multiplier = settings.atr_multiplier
        self.atr_multiplier = self.sl_multiplier # For backward compatibility
        logger.info("Initialized RiskService")

    def update_parameters(self, 
                          max_pos_size: float, 
                          max_risk_pct: float, 
                          leverage: int, 
                          tp_mults: List[float], 
                          sl_mult: float):
        self.max_position_size_usd = max_pos_size
        self.max_risk_per_trade_pct = max_risk_pct
        self.leverage = leverage
        self.tp_multipliers = tp_mults
        self.sl_multiplier = sl_mult
        self.atr_multiplier = sl_mult
        logger.info(f"Updated Risk Parameters: {self.__dict__}")

    def validate_order(self, order_params: dict) -> Tuple[bool, str]:
        amount = order_params.get("amount", 0.0)
        if amount > self.max_position_size_usd:
            msg = f"Order amount {amount} exceeds risk limit {self.max_position_size_usd}"
            logger.warning(msg)
            return False, msg
        return True, "OK"

    def calculate_stop_loss(self, entry_price: float, atr: float) -> float:
        # Legacy support
        return entry_price - (atr * self.sl_multiplier)

    def calculate_risk_levels(self, entry_price: float, atr: float, side: str = "long") -> dict:
        """
        Calculate SL and multiple TP levels based on parameters.
        """
        levels = {}
        sl_dist = atr * self.sl_multiplier
        
        if side.lower() == "long":
            sl_price = entry_price - sl_dist
            tps = [entry_price + (sl_dist * m) for m in self.tp_multipliers]
        else:
            sl_price = entry_price + sl_dist
            tps = [entry_price - (sl_dist * m) for m in self.tp_multipliers]
            
        levels['sl'] = sl_price
        for i, tp in enumerate(tps):
            levels[f'tp{i+1}'] = tp
            
        return levels
