import pandas as pd
from binance.client import Client
from binance.exceptions import BinanceAPIException
from typing import Optional, Dict, Any
from trading_bot.logger import get_logger
from trading_bot.config import settings
from datetime import datetime
import time
import os

logger = get_logger(__name__)

class BinanceDataFetcher:
    def __init__(self, api_key: Optional[str] = None, api_secret: Optional[str] = None, tld: Optional[str] = None, proxies: Optional[Dict] = None):
        # 1. Add User-Agent and headers
        # Set User-Agent via class attribute to avoid requests conflict
        Client.USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        
        if tld is None:
            tld = settings.binance_tld
        
        self.requests_params = {
            'timeout': 30  # Add timeout
        }
        
        # 4. Add support for proxy
        if proxies:
            self.requests_params['proxies'] = proxies
            
        self.client = Client(api_key, api_secret, tld=tld, requests_params=self.requests_params)
        
        # Ensure cache directory exists
        self.cache_dir = "data_cache"
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir)

    def fetch_orderbook(self, symbol: str, limit: int = 10) -> Dict[str, Any]:
        """
        Fetch current order book for a symbol.
        """
        try:
            return self.client.get_order_book(symbol=symbol, limit=limit)
        except Exception as e:
            logger.error(f"Error fetching orderbook from Binance: {e}")
            return {}

    def fetch_history(self, symbol: str, interval: str, limit: int = 500) -> pd.DataFrame:
        """
        Fetch historical kline data from Binance with retry logic and caching.
        """
        # 6. Fallback: Check cache first (simple caching strategy)
        cache_file = os.path.join(self.cache_dir, f"{symbol}_{interval}_{limit}.csv")
        
        try:
            return self._fetch_from_api_with_retry(symbol, interval, limit)
        except Exception as e:
            logger.error(f"API fetch failed: {e}. Trying fallback to cache.")
            if os.path.exists(cache_file):
                try:
                    df = pd.read_csv(cache_file)
                    # Restore timestamp type
                    if 'timestamp' in df.columns:
                        df['timestamp'] = pd.to_datetime(df['timestamp'])
                    
                    logger.info(f"Loaded {len(df)} candles from cache: {cache_file}")
                    return df
                except Exception as cache_e:
                    logger.error(f"Failed to read cache: {cache_e}")
            
            return pd.DataFrame()

    def _fetch_from_api_with_retry(self, symbol: str, interval: str, limit: int) -> pd.DataFrame:
        # 2. Add retry logic with backoff
        retries = 5
        
        for attempt in range(retries):
            try:
                # client.get_klines returns:
                # [
                #   [
                #     1499040000000,      // Open time
                #     "0.01634790",       // Open
                #     ...
                #   ]
                # ]
                
                # Using get_klines (latest data)
                klines = self.client.get_klines(symbol=symbol, interval=interval, limit=limit)
                
                if not klines:
                    return pd.DataFrame()

                data = []
                for k in klines:
                    data.append({
                        'timestamp': k[0],
                        'open': float(k[1]),
                        'high': float(k[2]),
                        'low': float(k[3]),
                        'close': float(k[4]),
                        'volume': float(k[5]),
                        'turnover': float(k[7]) # Quote volume
                    })
                
                df = pd.DataFrame(data)
                
                # Convert timestamp
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                
                # Sort by time
                df = df.sort_values('timestamp').reset_index(drop=True)
                
                # Save to cache
                cache_file = os.path.join(self.cache_dir, f"{symbol}_{interval}_{limit}.csv")
                df.to_csv(cache_file, index=False)
                
                return df
                
            except Exception as e:
                logger.warning(f"Attempt {attempt + 1}/{retries} failed: {e}")
                
                if attempt == retries - 1:
                    raise e
                
                # Backoff: 2s, 4s, 8s, 16s...
                sleep_time = 2 * (2 ** attempt)
                logger.info(f"Retrying in {sleep_time} seconds...")
                time.sleep(sleep_time)
                
        return pd.DataFrame()
