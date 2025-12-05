
import sys
import os
import time
import logging
from datetime import datetime

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
# Add scripts to path (for local imports when running from root or elsewhere)
sys.path.append(os.path.dirname(__file__))

from trading_bot.config import settings
from trading_bot.data_feeds.bybit_fetcher import BybitDataFetcher
from trading_bot.scoring.service import ScoringService
from trading_bot.risk.service import RiskService

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
        
        # Load API keys and testnet setting
        self.api_key = settings.api_key
        self.api_secret = settings.api_secret
        self.testnet = settings.bybit_testnet
        
        logger.info(f"Initializing BotDaemon with Bybit {'testnet' if self.testnet else 'mainnet'}")
        
        self.fetcher = BybitDataFetcher(self.api_key, self.api_secret, testnet=self.testnet)
        self.scoring = ScoringService(active_timeframes=self.timeframes)
        self.risk = RiskService()
        
        self.signal_handler = SignalHandler()
        self.tracker = PositionTracker(self.fetcher)
        
        self.last_trade_time = None
        self.total_pnl = 0.0 # This would need persistent storage or fetching from account

    def execute_logic(self):
        # 1. Fetch Data
        logger.debug(f"Fetching data for {self.symbol}")
        df = self.fetcher.fetch_history(self.symbol, "1h", limit=100) # Use 1h as primary
        
        if df.empty:
            logger.warning("No data received")
            return

        # 2. Calculate Signals
        # We need MTF data for scoring
        mtf_data = {}
        for tf in self.timeframes:
            if tf == "1h":
                mtf_data[tf] = df
            else:
                mtf_data[tf] = self.fetcher.fetch_history(self.symbol, tf, limit=100)
        
        signal = self.scoring.calculate_signals(df, mtf_data=mtf_data)
        
        # 3. Execution Logic (Simplified for now)
        action = signal.get('action', 'NEUTRAL')
        score = signal.get('score', 0.0)
        
        # Only log if it's a significant signal change or periodically?
        # For now log every logic execution might be too noisy, but requirement says "Log all events".
        # Let's log if action is not NEUTRAL.
        if action != 'NEUTRAL':
            logger.info(f"Signal calculated: {action} (Score: {score:.2f})")
        
        # TODO: Implement actual trade execution based on signal
        if "BUY" in action or "SELL" in action:
             # logger.info(f"OPEN POSITION: {action} - Position entry logic would go here.")
             pass

    def run(self):
        logger.info("Bot daemon initialized")
        
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
                        # Implement close logic here
                        # For now, we can try to use the fetcher session if it supports it, or just log
                        # self.fetcher.session.place_order(...)
                        # Since we don't have a dedicated execution service yet in this scope, 
                        # I'll just log it as a TODO or attempt a market close if I can.
                        pass
                
                # Fetch positions (Always, for monitoring)
                positions = self.tracker.fetch_positions()
                
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
                    "pid": os.getpid(),
                    "testnet": self.testnet
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
