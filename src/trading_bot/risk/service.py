from trading_bot.logger import get_logger
from trading_bot.config import settings
from typing import Optional, Dict

logger = get_logger(__name__)

class RiskService:
    def __init__(self):
        self.settings = settings
        logger.info("Initialized RiskService")

    def calculate_position_size(self, account_balance: float, entry_price: float, stop_loss_price: float) -> float:
        """
        Calculate position size (in base asset) based on risk percentage and stop loss distance.
        Enforces max position size in USD.
        """
        if entry_price <= 0 or stop_loss_price <= 0:
            logger.error(f"Invalid prices: entry={entry_price}, sl={stop_loss_price}")
            return 0.0

        risk_amount = account_balance * (self.settings.risk_per_trade_percent / 100.0)
        price_diff = abs(entry_price - stop_loss_price)
        
        if price_diff == 0:
            logger.warning("Stop loss same as entry price")
            return 0.0
        
        # Size based on risk per trade
        position_size = risk_amount / price_diff
        
        # Check against max position size in USD
        position_value_usd = position_size * entry_price
        
        if position_value_usd > self.settings.max_position_size_usd:
            logger.info(f"Position size {position_value_usd:.2f} USD exceeds limit {self.settings.max_position_size_usd:.2f} USD. Capping.")
            position_size = self.settings.max_position_size_usd / entry_price
            
        return position_size

    def validate_trade_setup(self, 
                             current_open_trades: int, 
                             atr_value: Optional[float] = None, 
                             liquidity: Optional[float] = None) -> bool:
        """
        Validate if a trade can be taken based on concurrency, volatility (ATR), and liquidity.
        """
        if current_open_trades >= self.settings.max_concurrent_trades:
            logger.warning(f"Max concurrent trades reached: {current_open_trades}/{self.settings.max_concurrent_trades}")
            return False
            
        if atr_value is not None and atr_value > self.settings.max_volatility_threshold:
             logger.warning(f"Volatility (ATR) too high: {atr_value} > {self.settings.max_volatility_threshold}")
             return False
             
        if liquidity is not None and liquidity < self.settings.min_liquidity_threshold:
             logger.warning(f"Liquidity too low: {liquidity} < {self.settings.min_liquidity_threshold}")
             return False
             
        return True

    def calculate_stops(self, entry_price: float, atr: float, side: str = 'buy') -> Dict[str, float]:
        """
        Calculate Stop Loss and Take Profit levels based on ATR.
        """
        if side.lower() == 'buy':
            sl = entry_price - (atr * self.settings.atr_multiplier_sl)
            tp = entry_price + (atr * self.settings.atr_multiplier_tp)
        else:
            sl = entry_price + (atr * self.settings.atr_multiplier_sl)
            tp = entry_price - (atr * self.settings.atr_multiplier_tp)
            
        return {'stop_loss': sl, 'take_profit': tp}
