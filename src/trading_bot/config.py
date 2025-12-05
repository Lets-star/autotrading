from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator
from typing import Optional, Any

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file='.env', 
        env_file_encoding='utf-8',
        case_sensitive=False  # Allow case-insensitive environment variable matching
    )

    api_key: Optional[str] = Field(None, description="Exchange API Key")
    api_secret: Optional[str] = Field(None, description="Exchange API Secret")
    
    bybit_testnet_api_key: Optional[str] = Field(None, description="Bybit Testnet API Key")
    bybit_testnet_api_secret: Optional[str] = Field(None, description="Bybit Testnet API Secret")
    
    exchange_id: str = Field("bybit", description="Exchange ID (binance, bybit)")
    binance_tld: str = Field("us", description="Binance TLD (us or com)")
    proxy_url: Optional[str] = Field(None, description="Proxy URL (e.g. http://user:pass@host:port)")
    bybit_testnet: bool = Field(False, description="Use Bybit testnet instead of mainnet")
    
    @field_validator('bybit_testnet', mode='before')
    @classmethod
    def parse_bybit_testnet(cls, v: Any) -> bool:
        """Parse BYBIT_TESTNET environment variable to boolean"""
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            return v.lower() in ('true', '1', 'yes', 'on', 't', 'y')
        if isinstance(v, int):
            return bool(v)
        return False
    
    risk_limit_amount: float = Field(100.0, description="Max amount per trade")
    atr_multiplier: float = Field(2.0, description="Multiplier for ATR stop loss")
    
    active_timeframes: list[str] = Field(["1h", "4h", "1d"], description="Active timeframes for analysis")
    
    log_level: str = Field("INFO", description="Logging level")

settings = Settings()
