import pandas as pd
from pybit.unified_trading import HTTP
from typing import Optional, Dict, Any, List
import time
from trading_bot.logger import get_logger

logger = get_logger(__name__)

class BybitDataFetcher:
    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        testnet: bool = False,
        session: Optional[HTTP] = None
    ):
        self.testnet = testnet
        if session is not None:
            self.session = session
            # When using a pre-configured session, log its actual endpoint
            endpoint_attr = getattr(session, 'endpoint', None) or getattr(session, 'base_url', None) or getattr(session, '_endpoint', None)
            logger.info(f"BybitDataFetcher initialized with pre-configured session (endpoint: {endpoint_attr})")
        else:
            self.session = HTTP(
                testnet=testnet,
                api_key=api_key,
                api_secret=api_secret
            )
            endpoint = 'https://api-testnet.bybit.com' if testnet else 'https://api.bybit.com'
            logger.info(f"BybitDataFetcher initialized with testnet={testnet} (endpoint: {endpoint})")
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

    def place_order(
        self,
        symbol: str,
        side: str,
        qty: float,
        order_type: str = "Market",
        category: str = "linear",
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        position_idx: int = 0,
        time_in_force: str = "GTC"
    ) -> Dict[str, Any]:
        """
        Place an order on Bybit.
        
        Args:
            symbol: Trading pair (e.g., "BTCUSDT")
            side: "Buy" or "Sell"
            qty: Quantity in base currency
            order_type: "Market" or "Limit"
            category: "linear" for USDT perpetuals, "spot" for spot
            stop_loss: Optional stop loss price
            take_profit: Optional take profit price
            position_idx: 0 for one-way mode, 1 for long hedge, 2 for short hedge
            time_in_force: "GTC", "IOC", "FOK"
            
        Returns:
            Response dictionary from Bybit API
        """
        try:
            params = {
                "category": category,
                "symbol": symbol,
                "side": side,
                "orderType": order_type,
                "qty": str(qty),
                "positionIdx": position_idx,
                "timeInForce": time_in_force
            }
            
            if stop_loss:
                params["stopLoss"] = str(stop_loss)
            if take_profit:
                params["takeProfit"] = str(take_profit)
            
            logger.info(f"Placing {order_type} order: {side} {qty} {symbol}")
            logger.info(f"Order parameters: {params}")
            
            response = self.session.place_order(**params)
            
            if response['retCode'] == 0:
                order_id = response['result'].get('orderId', 'N/A')
                logger.info(f"Order placed successfully. Order ID: {order_id}")
                return response['result']
            else:
                ret_code = response['retCode']
                ret_msg = response.get('retMsg', 'Unknown error')
                logger.error(f"Failed to place order (code {ret_code}): {ret_msg}")
                return {"error": ret_msg, "retCode": ret_code}
                
        except Exception as e:
            error_str = str(e).lower()
            if "401" in error_str or "unauthorized" in error_str:
                logger.error(f"Authentication exception placing order: {e}. Please check API keys and testnet/mainnet configuration.")
            else:
                logger.error(f"Exception placing order: {e}")
            return {"error": str(e)}

    def close_position(
        self,
        symbol: str,
        category: str = "linear",
        position_idx: int = 0
    ) -> Dict[str, Any]:
        """
        Close a position by fetching current position and placing opposing order.
        
        Args:
            symbol: Trading pair
            category: "linear" for USDT perpetuals
            position_idx: 0 for one-way mode
            
        Returns:
            Response dictionary from order placement
        """
        try:
            # Fetch current position
            params = {"category": category, "symbol": symbol}
            if category == "linear":
                params["settleCoin"] = "USDT"
            response = self.session.get_positions(**params)
            
            if response['retCode'] != 0:
                logger.error(f"Failed to fetch position: {response.get('retMsg', 'Unknown error')}")
                return {"error": "Failed to fetch position"}
            
            positions = response['result']['list']
            active_pos = [p for p in positions if float(p.get('size', 0)) > 0]
            
            if not active_pos:
                logger.warning(f"No active position found for {symbol}")
                return {"error": "No active position"}
            
            position = active_pos[0]
            size = float(position['size'])
            side = position['side']  # "Buy" or "Sell"
            
            # Close position by placing opposite order
            close_side = "Sell" if side == "Buy" else "Buy"
            
            logger.info(f"Closing {side} position of {size} {symbol} with {close_side} order")
            
            return self.place_order(
                symbol=symbol,
                side=close_side,
                qty=size,
                order_type="Market",
                category=category,
                position_idx=position_idx
            )
            
        except Exception as e:
            logger.error(f"Exception closing position: {e}")
            return {"error": str(e)}
