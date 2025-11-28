import pandas as pd
from binance.client import Client
from typing import Optional, Dict, Any
from trading_bot.logger import get_logger
from datetime import datetime

logger = get_logger(__name__)

class BinanceDataFetcher:
    def __init__(self, api_key: Optional[str] = None, api_secret: Optional[str] = None):
        self.client = Client(api_key, api_secret, tld='us')

    def fetch_history(self, symbol: str, interval: str, limit: int = 500) -> pd.DataFrame:
        """
        Fetch historical kline data from Binance.
        """
        # Map interval to Binance format if necessary (they are mostly same)
        # 1m, 3m, 5m, 15m, 30m, 1h, 2h, 4h, 6h, 8h, 12h, 1d, 3d, 1w, 1M
        
        try:
            # client.get_klines returns:
            # [
            #   [
            #     1499040000000,      // Open time
            #     "0.01634790",       // Open
            #     "0.80000000",       // High
            #     "0.01575800",       // Low
            #     "0.01577100",       // Close
            #     "148976.11427815",  // Volume
            #     1499644799999,      // Close time
            #     "2434.19055334",    // Quote asset volume
            #     308,                // Number of trades
            #     "1756.87402397",    // Taker buy base asset volume
            #     "28.46694368",      // Taker buy quote asset volume
            #     "17928899.62484339" // Ignore.
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
            
            return df
            
        except Exception as e:
            logger.error(f"Error fetching history from Binance: {e}")
            return pd.DataFrame()
