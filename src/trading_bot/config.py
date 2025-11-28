from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from typing import Optional

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8')

    api_key: Optional[str] = Field(None, description="Exchange API Key")
    api_secret: Optional[str] = Field(None, description="Exchange API Secret")
    exchange_id: str = Field("binance", description="Exchange ID (binance, bybit)")
    bybit_testnet: bool = Field(True, description="Use Bybit Testnet")
    
    # Risk Management Settings
    max_position_size_usd: float = Field(1000.0, description="Max position size in USD")
    risk_per_trade_percent: float = Field(1.0, description="Risk per trade in percent")
    leverage: int = Field(1, description="Leverage to use")
    max_concurrent_trades: int = Field(5, description="Maximum number of concurrent trades")
    min_liquidity_threshold: float = Field(0.0, description="Minimum liquidity threshold")
    max_volatility_threshold: float = Field(100.0, description="Maximum volatility threshold")
    
    # ATR Settings
    atr_period: int = Field(7, description="ATR Period")
    atr_multiplier_sl: float = Field(2.0, description="Multiplier for ATR Stop Loss")
    atr_multiplier_tp: float = Field(3.0, description="Multiplier for ATR Take Profit")
    
    log_level: str = Field("INFO", description="Logging level")

settings = Settings()
