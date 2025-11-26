import pandas as pd
from pybit.unified_trading import HTTP
from typing import Optional
import time

class BybitDataFetcher:
    def __init__(self, api_key: Optional[str] = None, api_secret: Optional[str] = None, testnet: bool = False):
        self.session = HTTP(
            testnet=testnet,
            api_key=api_key,
            api_secret=api_secret
        )

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

    def fetch_orderbook(self, symbol: str, category: str = "linear", limit: int = 10) -> dict:
        try:
            response = self.session.get_orderbook(
                category=category,
                symbol=symbol,
                limit=limit
            )
            if response['retCode'] != 0:
                return {}
            
            return response['result']
        except Exception as e:
            print(f"Error fetching orderbook: {e}")
            return {}

    def fetch_history(self, symbol: str, interval: str, limit: int = 1000, category: str = "linear") -> pd.DataFrame:
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
                raise Exception(f"Bybit API Error: {response['retMsg']}")
            
            # response['result']['list'] is a list of lists: 
            # [startTime, openPrice, highPrice, lowPrice, closePrice, volume, turnover]
            
            data = response['result']['list']
            
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
            print(f"Error fetching data from Bybit: {e}")
            return pd.DataFrame()
