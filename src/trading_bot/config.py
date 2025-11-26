from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from typing import Optional

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8')

    api_key: Optional[str] = Field(None, description="Exchange API Key")
    api_secret: Optional[str] = Field(None, description="Exchange API Secret")
    exchange_id: str = Field("binance", description="Exchange ID (binance, bybit)")
    
    risk_limit_amount: float = Field(100.0, description="Max amount per trade")
    atr_multiplier: float = Field(2.0, description="Multiplier for ATR stop loss")
    
    log_level: str = Field("INFO", description="Logging level")

settings = Settings()
