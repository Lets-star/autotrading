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

    def validate_order(self, order_params: dict, market_data: dict = None) -> Tuple[bool, str]:
        """
        Validate an order against risk parameters.
        order_params: {'amount': float, 'symbol': str, ...}
        market_data: {'volume_24h': float, 'atr': float, ...}
        """
        amount = order_params.get("amount", 0.0)
        
        # 1. Check Max Position Size
        if amount > self.max_position_size_usd:
            msg = f"Order amount {amount} exceeds risk limit {self.max_position_size_usd}"
            logger.warning(msg)
            return False, msg
            
        # 2. Check Liquidity (if data available)
        if market_data:
            volume_24h = market_data.get('volume_24h', 0)
            # Simple rule: Don't take position > 1% of 24h volume
            if volume_24h > 0 and amount > (volume_24h * 0.01):
                msg = f"Order amount {amount} exceeds 1% of 24h volume {volume_24h}"
                logger.warning(msg)
                return False, msg
                
            # 3. Check Volatility (if data available)
            atr = market_data.get('atr', 0)
            current_price = market_data.get('close', 1)
            if atr > 0 and current_price > 0:
                volatility_pct = (atr / current_price) * 100
                if volatility_pct > 5.0: # Example threshold: >5% volatility is too high
                    msg = f"Volatility {volatility_pct:.2f}% is too high (ATR: {atr})"
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
