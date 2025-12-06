
import sys
import os
import time
import logging
import math
from datetime import datetime, timedelta
import pandas as pd

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
# Add scripts to path (for local imports when running from root or elsewhere)
sys.path.append(os.path.dirname(__file__))

from trading_bot.config import settings
from trading_bot.data_feeds.bybit_fetcher import BybitDataFetcher
from trading_bot.scoring.service import ScoringService
from trading_bot.risk.service import RiskService
from trading_bot.bybit_clients import (
    get_bybit_public_mainnet_client,
    get_bybit_private_testnet_client,
    get_bybit_private_mainnet_client,
)

try:
    from signal_handler import SignalHandler
    from position_tracker import PositionTracker
except ImportError:
    from scripts.signal_handler import SignalHandler
    from scripts.position_tracker import PositionTracker

# Setup logging
log_file = 'logs/bot.log'
os.makedirs(os.path.dirname(log_file), exist_ok=True)
logging.basicConfig(
    filename=log_file,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class BotDaemon:
    def __init__(self):
        self.running = False
        self.paused = False
        self.symbol = "BTCUSDT" 
        self.timeframes = ["1h", "4h", "1d"]
        
        self.api_key = settings.api_key
        self.api_secret = settings.api_secret
        self.testnet = bool(settings.bybit_testnet)
        self.testnet_api_key = settings.bybit_testnet_api_key
        self.testnet_api_secret = settings.bybit_testnet_api_secret
        
        logger.info("Initializing BotDaemon")
        logger.info(f"Environment: BYBIT_TESTNET={os.environ.get('BYBIT_TESTNET', 'not set')}")
        logger.info(f"Environment: BYBIT_TESTNET_API_KEY={'set' if os.environ.get('BYBIT_TESTNET_API_KEY') else 'not set'}")
        logger.info(f"Environment: BYBIT_TESTNET_API_SECRET={'set' if os.environ.get('BYBIT_TESTNET_API_SECRET') else 'not set'}")
        logger.info(f"Settings: bybit_testnet={settings.bybit_testnet}")
        logger.info(f"Settings: testnet_api_key={'set' if self.testnet_api_key else 'not set'}")
        logger.info(f"Settings: testnet_api_secret={'set' if self.testnet_api_secret else 'not set'}")
        logger.info("  - Public market data will use Bybit mainnet endpoints")
        if self.testnet:
            logger.info("  - Private operations configured for Bybit testnet endpoints")
        else:
            logger.info("  - Private operations configured for Bybit mainnet endpoints")
        
        # Create public mainnet fetcher for market data
        public_client = get_bybit_public_mainnet_client()
        self.public_fetcher = BybitDataFetcher(api_key=None, api_secret=None, testnet=False)
        self.public_fetcher.session = public_client
        
        # Create private client for trading operations (testnet when enabled)
        self.private_fetcher = None
        try:
            if self.testnet:
                logger.info("Creating testnet private client...")
                private_client = get_bybit_private_testnet_client(
                    api_key=self.testnet_api_key,
                    api_secret=self.testnet_api_secret,
                )
                logger.info("Testnet private client created successfully")
            else:
                logger.info("Creating mainnet private client...")
                private_client = get_bybit_private_mainnet_client(
                    api_key=self.api_key,
                    api_secret=self.api_secret,
                )
                logger.info("Mainnet private client created successfully")
            
            self.private_fetcher = BybitDataFetcher(api_key=None, api_secret=None, testnet=self.testnet)
            self.private_fetcher.session = private_client
            logger.info(f"Private {'testnet' if self.testnet else 'mainnet'} client initialized and assigned to fetcher")
        except ValueError as e:
            logger.error(f"Failed to initialize private {'testnet' if self.testnet else 'mainnet'} client: {e}")
            logger.error("Position tracking and order execution will not be available.")
        
        self.scoring = ScoringService(active_timeframes=self.timeframes)
        self.risk = RiskService()
        
        self.signal_handler = SignalHandler()
        self.tracker = PositionTracker(self.private_fetcher) if self.private_fetcher else None
        self.current_positions = []
        
        self.last_trade_time = None
        self.last_trade_action = None
        self.total_pnl = 0.0 # This would need persistent storage or fetching from account
        
        # Trade management
        self.trade_cooldown = timedelta(minutes=5)
        self.order_category = "linear"
        self.position_idx = 0  # Bybit one-way mode
        self.min_order_qty = 0.001

    def _execute_trade(self, action: str, signal: dict, df: pd.DataFrame):
        """
        Execute a trade based on the signal.
        
        Args:
            action: Signal action (BUY, SELL, STRONG BUY, STRONG SELL)
            signal: Full signal dictionary with score and details
            df: Market data DataFrame
        """
        try:
            # Check if we should rate-limit trades
            now = datetime.now()
            if self.last_trade_time and (now - self.last_trade_time) < self.trade_cooldown:
                time_left = (self.trade_cooldown - (now - self.last_trade_time)).total_seconds()
                logger.debug(f"Skipping trade - cooldown active ({time_left:.0f}s remaining)")
                return
            
            # Don't trade if we're reversing direction too quickly
            action_type = "BUY" if "BUY" in action else "SELL"
            if self.last_trade_action and self.last_trade_action != action_type:
                if self.last_trade_time and (now - self.last_trade_time) < timedelta(minutes=30):
                    logger.info(f"Skipping trade - signal reversal too soon (last: {self.last_trade_action}, now: {action_type})")
                    return
            
            # Check for existing positions and enforce risk constraints
            current_positions = self.current_positions or []
            
            # Determine trade direction
            if "BUY" in action:
                new_side = "Buy"
                new_direction = "long"
            else:
                new_side = "Sell"
                new_direction = "short"
            
            # Check position constraints
            long_positions = [p for p in current_positions if p.get('side') == 'Buy']
            short_positions = [p for p in current_positions if p.get('side') == 'Sell']
            
            # Risk constraint 1: Max 3 positions per direction
            if new_direction == "long" and len(long_positions) >= 3:
                logger.info(f"Skipping BUY trade - already have 3 LONG positions (risk limit)")
                return
            
            if new_direction == "short" and len(short_positions) >= 3:
                logger.info(f"Skipping SELL trade - already have 3 SHORT positions (risk limit)")
                return
            
            # Risk constraint 2: No opposite directions simultaneously
            if new_direction == "long" and len(short_positions) > 0:
                logger.info(f"Skipping BUY trade - already have SHORT positions open (risk limit: no opposite directions)")
                return
            
            if new_direction == "short" and len(long_positions) > 0:
                logger.info(f"Skipping SELL trade - already have LONG positions open (risk limit: no opposite directions)")
                return
            
            # Get current price and ATR for risk calculation
            latest = df.iloc[-1]
            current_price = float(latest['close'])
            
            # Calculate ATR for risk levels
            if 'atr' in latest and not pd.isna(latest['atr']):
                atr = float(latest['atr'])
            else:
                # Calculate ATR if not in data
                high = df['high'].astype(float)
                low = df['low'].astype(float)
                prev_close = df['close'].astype(float).shift(1)
                tr1 = high - low
                tr2 = (high - prev_close).abs()
                tr3 = (low - prev_close).abs()
                tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
                atr = tr.rolling(window=14).mean().iloc[-1]
            
            if atr is None or pd.isna(atr) or atr <= 0:
                atr = max(current_price * 0.01, 1.0)
            
            # Determine side (already done above, but keep for clarity)
            side = new_side
            trade_side = new_direction
            
            # Calculate risk levels
            risk_levels = self.risk.calculate_risk_levels(
                entry_price=current_price,
                atr=atr,
                side=trade_side
            )
            
            sl_price = risk_levels['sl']
            tp_price = risk_levels.get('tp1', None)  # Use first TP target
            
            # Calculate position size
            # Use a percentage of max position size based on signal strength
            score = signal.get('score', 0.5)
            if "STRONG" in action:
                size_multiplier = 1.0  # Full size for strong signals
            else:
                size_multiplier = 0.5  # Half size for normal signals
            
            # Calculate quantity in base currency (e.g., BTC)
            # position_size_usd is from risk service
            position_size_usd = self.risk.max_position_size_usd * size_multiplier
            qty = position_size_usd / current_price
            
            # Round to appropriate precision (Bybit typically uses different precision for different pairs)
            # For BTCUSDT, typically 3 decimal places for qty
            qty = round(qty, 3)
            
            # Validate minimum order size
            if qty < self.min_order_qty:
                logger.warning(f"Order quantity {qty} is below minimum {self.min_order_qty}. Skipping trade.")
                return
            
            logger.info("=" * 60)
            logger.info(f"EXECUTING TRADE")
            logger.info("=" * 60)
            logger.info(f"Signal: {action} (Score: {score:.2f})")
            logger.info(f"Symbol: {self.symbol}")
            logger.info(f"Side: {side} ({trade_side})")
            logger.info(f"Entry Price: {current_price:.2f}")
            logger.info(f"Quantity: {qty}")
            logger.info(f"Position Size: ${position_size_usd:.2f}")
            logger.info(f"ATR: {atr:.2f}")
            logger.info(f"Stop Loss: {sl_price:.2f}")
            if tp_price:
                logger.info(f"Take Profit: {tp_price:.2f}")
            logger.info("=" * 60)
            
            # Place the order
            result = self.private_fetcher.place_order(
                symbol=self.symbol,
                side=side,
                qty=qty,
                order_type="Market",
                stop_loss=sl_price,
                take_profit=tp_price,
                category=self.order_category,
                position_idx=self.position_idx  # One-way mode
            )
            
            if "error" in result:
                logger.error(f"Failed to place order: {result['error']}")
            else:
                logger.info(f"Order placed successfully!")
                logger.info(f"Order ID: {result.get('orderId', 'N/A')}")
                logger.info(f"Order Link ID: {result.get('orderLinkId', 'N/A')}")
                self.last_trade_time = now
                self.last_trade_action = action_type
                
                # Wait a moment for the order to be reflected in positions
                time.sleep(2)
                if self.tracker:
                    self.current_positions = self.tracker.fetch_positions(symbol=self.symbol)
            
        except Exception as e:
            logger.error(f"Error executing trade: {e}", exc_info=True)

    def execute_logic(self):
        # 1. Fetch Data from mainnet (public data)
        logger.debug(f"Fetching market data for {self.symbol} from mainnet")
        df = self.public_fetcher.fetch_history(self.symbol, "1h", limit=100)
        
        if df.empty:
            logger.warning("No data received from mainnet")
            return

        # 2. Calculate Signals
        # We need MTF data for scoring - all from mainnet
        mtf_data = {}
        for tf in self.timeframes:
            if tf == "1h":
                mtf_data[tf] = df
            else:
                mtf_data[tf] = self.public_fetcher.fetch_history(self.symbol, tf, limit=100)
        
        signal = self.scoring.calculate_signals(df, mtf_data=mtf_data)
        
        # 3. Execution Logic
        action = signal.get('action', 'NEUTRAL')
        score = signal.get('score', 0.0)
        
        # Log non-NEUTRAL signals
        if action != 'NEUTRAL':
            logger.info(f"Signal calculated: {action} (Score: {score:.2f})")
        
        # Execute trades based on signal
        if ("BUY" in action or "SELL" in action) and self.private_fetcher:
            self._execute_trade(action, signal, df)

    def run(self):
        logger.info("=" * 60)
        logger.info("BOT DAEMON STARTING")
        logger.info("=" * 60)
        logger.info(f"Configuration Summary:")
        logger.info(f"  - Symbol: {self.symbol}")
        logger.info(f"  - Timeframes: {self.timeframes}")
        logger.info(f"  - Testnet mode: {self.testnet}")
        logger.info(f"  - Public data endpoint: Bybit Mainnet")
        logger.info(f"  - Private operations endpoint: Bybit {'Testnet' if self.testnet else 'Mainnet'}")
        logger.info(f"  - Position tracker: {'Enabled' if self.tracker else 'Disabled (no API keys)'}")
        logger.info("=" * 60)
        
        while True:
            try:
                # Check control signals
                cmd_raw = self.signal_handler.check_signal()
                if cmd_raw:
                    parts = cmd_raw.split()
                    cmd = parts[0]
                    args = parts[1:]
                    
                    if cmd == "START":
                        self.running = True
                        self.paused = False
                        logger.info("START signal received. Bot running.")
                    elif cmd == "STOP":
                        self.running = False
                        self.paused = False
                        logger.info("STOP signal received. Bot stopped.")
                    elif cmd == "PAUSE":
                        self.paused = True
                        logger.info("PAUSE signal received. Bot paused.")
                    elif cmd == "CLOSE" and args:
                        symbol_to_close = args[0]
                        logger.info(f"CLOSE signal received for {symbol_to_close}")
                        if self.private_fetcher:
                            try:
                                result = self.private_fetcher.close_position(
                                    symbol=symbol_to_close,
                                    category="linear"
                                )
                                if "error" in result:
                                    logger.error(f"Failed to close position: {result['error']}")
                                else:
                                    logger.info(f"Position closed successfully for {symbol_to_close}")
                                    logger.info(f"Close order ID: {result.get('orderId', 'N/A')}")
                                    if self.tracker:
                                        self.current_positions = self.tracker.fetch_positions(symbol=self.symbol)
                            except Exception as e:
                                logger.error(f"Exception closing position: {e}", exc_info=True)
                        else:
                            logger.error("Cannot close position - private fetcher not initialized")
                
                # Fetch positions (Always, for monitoring)
                positions = self.tracker.fetch_positions(symbol=self.symbol) if self.tracker else []
                self.current_positions = positions
                
                # Calculate PnL from positions (unrealized)
                # current_pnl = sum([float(p.get('unrealisedPnl', 0)) for p in positions])
                
                # Update Status
                status_data = {
                    "running": self.running,
                    "paused": self.paused,
                    "symbol": self.symbol,
                    "last_update": datetime.now().isoformat(),
                    "total_pnl": self.total_pnl, # Placeholder
                    "position_count": len(positions),
                    "positions": positions,
                    "pid": os.getpid(),
                    "testnet": self.testnet,
                    "public_endpoint": "mainnet",  # Using mainnet for public data
                    "private_endpoint": "testnet" if self.testnet else "mainnet"
                }
                self.signal_handler.update_status("Running" if self.running and not self.paused else "Paused" if self.paused else "Stopped", status_data)
                
                if self.running and not self.paused:
                    self.execute_logic()
                
                time.sleep(1)
                
            except KeyboardInterrupt:
                logger.info("Keyboard interrupt received. Shutting down gracefully...")
                break
            except Exception as e:
                error_str = str(e).lower()
                # Don't exit on authentication or HTTP errors - just log and continue
                if any(keyword in error_str for keyword in ["401", "unauthorized", "http status code is not 200"]):
                    logger.error(f"Recoverable error in daemon loop: {e}. Continuing operation...")
                else:
                    logger.error(f"Error in daemon loop: {e}", exc_info=True)
                    self.signal_handler.update_status("Error", {"error": str(e)})
                
                time.sleep(5) # Backoff on error

if __name__ == "__main__":
    bot = BotDaemon()
    bot.run()
