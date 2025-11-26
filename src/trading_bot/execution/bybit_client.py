from pybit.unified_trading import HTTP, WebSocket
from trading_bot.config import settings
from trading_bot.logger import get_logger
from typing import Optional, Dict, Any, Callable
import time

logger = get_logger(__name__)

class BybitExecutionClient:
    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.testnet = settings.bybit_testnet
        self.api_key = settings.api_key
        self.api_secret = settings.api_secret
        
        self.session = None
        self.ws = None
        
        if not self.dry_run:
            if not self.api_key or not self.api_secret:
                logger.warning("API Key/Secret not provided. Forcing Dry Run.")
                self.dry_run = True
            else:
                self.session = HTTP(
                    testnet=self.testnet,
                    api_key=self.api_key,
                    api_secret=self.api_secret
                )
        
        if self.dry_run:
            logger.info("Bybit Execution Client initialized in DRY RUN mode")
        else:
            logger.info(f"Bybit Execution Client initialized (Testnet: {self.testnet})")

    def place_order(self, 
                    symbol: str, 
                    side: str, 
                    qty: float, 
                    price: Optional[float] = None, 
                    order_type: str = "Market", 
                    stop_loss: Optional[float] = None, 
                    take_profit: Optional[float] = None,
                    reduce_only: bool = False) -> Dict[str, Any]:
        """
        Place an order on Bybit.
        """
        side = side.capitalize()
        
        if self.dry_run:
            logger.info(f"[DRY RUN] Placing {side} order for {qty} {symbol} @ {price or 'Market'}. SL: {stop_loss}, TP: {take_profit}")
            # Simulate a successful response
            return {
                "retCode": 0,
                "retMsg": "OK",
                "result": {
                    "orderId": f"sim_{int(time.time())}",
                    "orderLinkId": f"sim_link_{int(time.time())}"
                }
            }
            
        try:
            order_params = {
                "category": "linear",
                "symbol": symbol,
                "side": side,
                "orderType": order_type,
                "qty": str(qty),
                "reduceOnly": reduce_only
            }
            
            if price:
                 order_params["price"] = str(price)
            
            if stop_loss:
                order_params["stopLoss"] = str(stop_loss)
            
            if take_profit:
                order_params["takeProfit"] = str(take_profit)

            logger.info(f"Placing order: {order_params}")
            response = self.session.place_order(**order_params)
            
            if response['retCode'] != 0:
                logger.error(f"Bybit Error: {response['retMsg']}")
            else:
                logger.info(f"Order placed successfully: {response['result']['orderId']}")
                
            return response
            
        except Exception as e:
            logger.error(f"Exception placing order: {e}")
            raise e

    def amend_order(self,
                    symbol: str,
                    order_id: str,
                    qty: Optional[float] = None,
                    price: Optional[float] = None,
                    stop_loss: Optional[float] = None,
                    take_profit: Optional[float] = None) -> Dict[str, Any]:
        
        if self.dry_run:
            logger.info(f"[DRY RUN] Amending order {order_id} for {symbol}. New Price: {price}, New SL: {stop_loss}")
            return {"retCode": 0, "result": {}}

        try:
            params = {
                "category": "linear",
                "symbol": symbol,
                "orderId": order_id
            }
            if qty: params["qty"] = str(qty)
            if price: params["price"] = str(price)
            if stop_loss: params["stopLoss"] = str(stop_loss)
            if take_profit: params["takeProfit"] = str(take_profit)
            
            logger.info(f"Amending order: {params}")
            response = self.session.amend_order(**params)
            return response
        except Exception as e:
            logger.error(f"Exception amending order: {e}")
            raise e

    def cancel_order(self, symbol: str, order_id: str) -> Dict[str, Any]:
        if self.dry_run:
            logger.info(f"[DRY RUN] Cancelling order {order_id} for {symbol}")
            return {"retCode": 0, "result": {}}

        try:
            params = {
                "category": "linear",
                "symbol": symbol,
                "orderId": order_id
            }
            logger.info(f"Cancelling order: {params}")
            response = self.session.cancel_order(**params)
            return response
        except Exception as e:
            logger.error(f"Exception cancelling order: {e}")
            raise e

    def get_open_positions(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        if self.dry_run:
            # Return empty positions or simulated ones if state was tracked
            return {"retCode": 0, "result": {"list": []}}
            
        try:
            params = {
                "category": "linear",
                "settleCoin": "USDT",
            }
            if symbol:
                params["symbol"] = symbol
                
            response = self.session.get_positions(**params)
            return response
        except Exception as e:
            logger.error(f"Exception getting positions: {e}")
            raise e
            
    def start_websocket(self, callback: Callable):
        """
        Start the private websocket for order and position updates.
        """
        if self.dry_run:
            logger.info("[DRY RUN] Websocket not started.")
            return

        self.ws = WebSocket(
            testnet=self.testnet,
            channel_type="private",
            api_key=self.api_key,
            api_secret=self.api_secret,
        )
        
        def handle_message(message):
            # Log raw message or process it
            # logger.debug(f"WS Message: {message}")
            callback(message)
            
        # Subscribe to order and position channels
        self.ws.order_stream(callback=handle_message)
        self.ws.position_stream(callback=handle_message)
        self.ws.execution_stream(callback=handle_message)
        
        logger.info("Bybit Private Websocket started.")

