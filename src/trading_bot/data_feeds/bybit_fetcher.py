import pandas as pd
from pybit.unified_trading import HTTP
from typing import Optional, Dict, Any, List
import time
from trading_bot.logger import get_logger

logger = get_logger(__name__)

class BybitDataFetcher:
    def __init__(self, api_key: Optional[str] = None, api_secret: Optional[str] = None, testnet: bool = False):
        self.testnet = testnet
        self.session = HTTP(
            testnet=testnet,
            api_key=api_key,
            api_secret=api_secret
        )
        self.status = "Idle"
        logger.info(f"BybitDataFetcher initialized with testnet={testnet} (endpoint: {'https://api-testnet.bybit.com' if testnet else 'https://api.bybit.com'})")

    def _map_interval(self, interval: str) -> str:
        mapping = {
            "1m": "1",
            "5m": "5",
            "15m": "15",
            "30m": "30",
            "1h": "60",
            "4h": "240",
            "1d": "D",
        }
        return mapping.get(interval, interval)

    def fetch_orderbook(self, symbol: str, category: str = "linear", limit: int = 10) -> Dict[str, Any]:
        """
        Fetch current order book for a symbol.
        """
        try:
            response = self.session.get_orderbook(
                category=category,
                symbol=symbol,
                limit=limit
            )
            if response['retCode'] != 0:
                ret_code = response['retCode']
                ret_msg = response.get('retMsg', 'Unknown error')
                
                if ret_code == 401:
                    logger.error(f"Authentication error fetching orderbook: {ret_msg}. Please check API keys and testnet/mainnet configuration.")
                else:
                    logger.error(f"Bybit API Error (Orderbook code {ret_code}): {ret_msg}")
                return {}
            
            return response['result']
        except Exception as e:
            error_str = str(e).lower()
            if "401" in error_str or "unauthorized" in error_str:
                logger.error(f"Authentication exception fetching orderbook: {e}. Please check API keys and testnet/mainnet configuration.")
            else:
                logger.error(f"Error fetching orderbook from Bybit: {e}")
            return {}

    def fetch_history(self, symbol: str, interval: str, limit: int = 200, category: str = "linear") -> pd.DataFrame:
        """
        Fetch historical kline data.
        """
        bybit_interval = self._map_interval(interval)
        
        # Bybit API usually returns latest first.
        try:
            response = self.session.get_kline(
                category=category,
                symbol=symbol,
                interval=bybit_interval,
                limit=limit
            )
            
            if response['retCode'] != 0:
                ret_code = response['retCode']
                ret_msg = response.get('retMsg', 'Unknown error')
                
                if ret_code == 401:
                    logger.error(f"Authentication error fetching history: {ret_msg}. Please check API keys and testnet/mainnet configuration.")
                else:
                    logger.error(f"Bybit API Error (History code {ret_code}): {ret_msg}")
                self.status = "Failed"
                return pd.DataFrame()
            
            self.status = "Connected"
            # response['result']['list'] is a list of lists: 
            # [startTime, openPrice, highPrice, lowPrice, closePrice, volume, turnover]
            
            data = response['result']['list']
            
            if not data:
                return pd.DataFrame()

            df = pd.DataFrame(data, columns=['start_time', 'open', 'high', 'low', 'close', 'volume', 'turnover'])
            
            # Convert types
            df['start_time'] = pd.to_numeric(df['start_time'])
            for col in ['open', 'high', 'low', 'close', 'volume', 'turnover']:
                df[col] = pd.to_numeric(df[col])
                
            # Convert timestamp to datetime
            df['timestamp'] = pd.to_datetime(df['start_time'], unit='ms')
            
            # Sort by time (oldest first)
            df = df.sort_values('timestamp').reset_index(drop=True)
            
            return df
            
        except Exception as e:
            error_str = str(e).lower()
            if "401" in error_str or "unauthorized" in error_str:
                logger.error(f"Authentication exception fetching history: {e}. Please check API keys and testnet/mainnet configuration.")
            elif "http status code is not 200" in error_str:
                logger.error(f"HTTP error fetching history: {e}. This may indicate incorrect testnet/mainnet settings.")
            else:
                logger.error(f"Error fetching history from Bybit: {e}")
            self.status = "Failed"
            return pd.DataFrame()
