import os
from pybit.unified_trading import HTTP
from typing import Optional
from trading_bot.logger import get_logger

logger = get_logger(__name__)

def get_bybit_public_mainnet_client() -> HTTP:
    """
    Create a Bybit HTTP client for public mainnet data (symbols, candles, etc.)
    No authentication required.
    """
    logger.info("Creating Bybit public mainnet client")
    return HTTP(testnet=False)

def get_bybit_private_testnet_client(api_key: Optional[str] = None, api_secret: Optional[str] = None) -> HTTP:
    """
    Create a Bybit HTTP client for private testnet operations (positions, orders, etc.)
    Reads testnet API keys from environment variables if not provided:
    - BYBIT_TESTNET_API_KEY
    - BYBIT_TESTNET_API_SECRET
    """
    if not api_key:
        api_key = os.environ.get("BYBIT_TESTNET_API_KEY")
    if not api_secret:
        api_secret = os.environ.get("BYBIT_TESTNET_API_SECRET")
    
    if not api_key or not api_secret:
        logger.error("Bybit testnet API keys not found. Please set BYBIT_TESTNET_API_KEY and BYBIT_TESTNET_API_SECRET environment variables.")
        raise ValueError("Bybit testnet API keys are required for private operations")
    
    logger.info("Creating Bybit private testnet client (endpoint: https://api-testnet.bybit.com)")
    return HTTP(
        api_key=api_key,
        api_secret=api_secret,
        testnet=True
    )

def get_bybit_private_mainnet_client(api_key: Optional[str] = None, api_secret: Optional[str] = None) -> HTTP:
    """
    Create a Bybit HTTP client for private mainnet operations.
    Useful when using mainnet for actual trading.
    """
    if not api_key:
        api_key = os.environ.get("BYBIT_API_KEY")
    if not api_secret:
        api_secret = os.environ.get("BYBIT_API_SECRET")
    
    if not api_key or not api_secret:
        logger.error("Bybit mainnet API keys not found. Please set BYBIT_API_KEY and BYBIT_API_SECRET environment variables.")
        raise ValueError("Bybit mainnet API keys are required for private operations")
    
    logger.info("Creating Bybit private mainnet client (endpoint: https://api.bybit.com)")
    return HTTP(
        api_key=api_key,
        api_secret=api_secret,
        testnet=False
    )
