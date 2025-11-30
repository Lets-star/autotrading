import pandas as pd
from pybit.unified_trading import HTTP
from typing import Optional, Dict, Any, List
import time
from trading_bot.logger import get_logger

logger = get_logger(__name__)

class BybitDataFetcher:
    def __init__(self, api_key: Optional[str] = None, api_secret: Optional[str] = None, testnet: bool = False):
        self.session = HTTP(
            testnet=testnet,
            api_key=api_key,
            api_secret=api_secret
        )
        self.status = "Idle"

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
                logger.error(f"Bybit API Error (Orderbook): {response['retMsg']}")
                return {}
            
            return response['result']
        except Exception as e:
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
                logger.error(f"Bybit API Error (History): {response['retMsg']}")
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
            logger.error(f"Error fetching history from Bybit: {e}")
            self.status = "Failed"
            return pd.DataFrame()

    def place_order(self, symbol: str, side: str, qty: float, category: str = "linear", order_type: str = "Market") -> Dict[str, Any]:
        """
        Place an order on Bybit.
        """
        try:
            logger.info(f"Bybit: Placing {order_type} {side} order for {qty} {symbol}")
            response = self.session.place_order(
                category=category,
                symbol=symbol,
                side=side.capitalize(),
                orderType=order_type,
                qty=str(qty)
            )
            
            if response['retCode'] != 0:
                logger.error(f"Bybit API Error (Place Order): {response['retMsg']}")
                return {"success": False, "error": response['retMsg']}
            
            logger.info(f"Bybit: Order placed successfully: {response['result']}")
            return {"success": True, "result": response['result']}
        except Exception as e:
            logger.error(f"Error placing order on Bybit: {e}")
            return {"success": False, "error": str(e)}

    def get_positions(self, symbol: str = None, category: str = "linear") -> List[Dict[str, Any]]:
        """
        Get current positions.
        """
        try:
            kwargs = {"category": category, "settleCoin": "USDT"}
            if symbol:
                kwargs["symbol"] = symbol
                
            response = self.session.get_positions(**kwargs)
            
            if response['retCode'] != 0:
                logger.error(f"Bybit API Error (Get Positions): {response['retMsg']}")
                return []
            
            positions = response['result']['list']
            # Filter for active positions (size > 0)
            active_positions = [p for p in positions if float(p['size']) > 0]
            
            return active_positions
        except Exception as e:
            logger.error(f"Error getting positions from Bybit: {e}")
            return []
