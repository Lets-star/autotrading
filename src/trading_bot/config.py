from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from typing import Optional

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8')

    api_key: Optional[str] = Field(None, description="Exchange API Key")
    api_secret: Optional[str] = Field(None, description="Exchange API Secret")
    
    bybit_testnet_api_key: Optional[str] = Field(None, description="Bybit Testnet API Key")
    bybit_testnet_api_secret: Optional[str] = Field(None, description="Bybit Testnet API Secret")
    
    exchange_id: str = Field("bybit", description="Exchange ID (binance, bybit)")
    binance_tld: str = Field("us", description="Binance TLD (us or com)")
    proxy_url: Optional[str] = Field(None, description="Proxy URL (e.g. http://user:pass@host:port)")
    bybit_testnet: bool = Field(False, description="Use Bybit testnet instead of mainnet")
    
    risk_limit_amount: float = Field(100.0, description="Max amount per trade")
    atr_multiplier: float = Field(2.0, description="Multiplier for ATR stop loss")
    
    active_timeframes: list[str] = Field(["1h", "4h", "1d"], description="Active timeframes for analysis")
    
    log_level: str = Field("INFO", description="Logging level")

settings = Settings()
