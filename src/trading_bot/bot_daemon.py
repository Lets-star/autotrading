"""
Bot Daemon Module - Internal Bybit Trading Bot

This module can be run as a standalone daemon using:
    python -m trading_bot.bot_daemon

The daemon monitors signals, tracks positions, and executes trading logic.
"""

import sys
import os
import time
import logging
from datetime import datetime
from pathlib import Path

from trading_bot.config import settings
from trading_bot.data_feeds.bybit_fetcher import BybitDataFetcher
from trading_bot.scoring.service import ScoringService
from trading_bot.risk.service import RiskService

# Import scripts helpers (signal handler and position tracker)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

try:
    from signal_handler import SignalHandler
    from position_tracker import PositionTracker
except ImportError as e:
    logging.error(f"Failed to import signal_handler or position_tracker: {e}")
    # Provide minimal fallbacks
    class SignalHandler:
        def check_signal(self):
            return None
        def update_status(self, status, data):
            pass
    
    class PositionTracker:
        def __init__(self, fetcher):
            self.fetcher = fetcher
        def fetch_positions(self):
            return []

# Setup logging
log_file = PROJECT_ROOT / 'logs' / 'bot.log'
log_file.parent.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    filename=str(log_file),
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Also log to console
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(console_handler)


class BotDaemon:
    """Main bot daemon class that handles trading logic and signals."""
    
    def __init__(self):
        self.running = False
        self.paused = False
        self.symbol = "BTCUSDT" 
        self.timeframes = ["1h", "4h", "1d"]
        
        # Load API keys
        self.api_key = settings.api_key
        self.api_secret = settings.api_secret
        
        self.fetcher = BybitDataFetcher(self.api_key, self.api_secret)
        self.scoring = ScoringService(active_timeframes=self.timeframes)
        self.risk = RiskService()
        
        self.signal_handler = SignalHandler()
        self.tracker = PositionTracker(self.fetcher)
        
        self.last_trade_time = None
        self.total_pnl = 0.0
        
        logger.info("BotDaemon initialized successfully")

    def execute_logic(self):
        """Execute trading logic: fetch data, calculate signals, and potentially trade."""
        try:
            logger.debug(f"Fetching data for {self.symbol}")
            df = self.fetcher.fetch_history(self.symbol, "1h", limit=100)
            
            if df.empty:
                logger.warning("No data received")
                return

            # Calculate signals with MTF data
            mtf_data = {}
            for tf in self.timeframes:
                if tf == "1h":
                    mtf_data[tf] = df
                else:
                    mtf_data[tf] = self.fetcher.fetch_history(self.symbol, tf, limit=100)
            
            signal = self.scoring.calculate_signals(df, mtf_data=mtf_data)
            
            # Log significant signals
            action = signal.get('action', 'NEUTRAL')
            score = signal.get('score', 0.0)
            
            if action != 'NEUTRAL':
                logger.info(f"Signal calculated: {action} (Score: {score:.2f})")
            
            # TODO: Implement actual trade execution based on signal
            # This would involve calling execution service to place orders
            
        except Exception as e:
            logger.error(f"Error in execute_logic: {e}", exc_info=True)

    def run(self):
        """Main daemon loop."""
        logger.info("=" * 60)
        logger.info("Bot daemon starting up...")
        logger.info(f"Process ID: {os.getpid()}")
        logger.info(f"Project root: {PROJECT_ROOT}")
        logger.info(f"Symbol: {self.symbol}")
        logger.info(f"Timeframes: {self.timeframes}")
        logger.info("=" * 60)
        
        heartbeat_counter = 0
        
        while True:
            try:
                # Heartbeat logging (every 60 iterations = ~1 minute)
                heartbeat_counter += 1
                if heartbeat_counter % 60 == 0:
                    logger.info(f"Daemon heartbeat - Running: {self.running}, Paused: {self.paused}")
                    heartbeat_counter = 0
                
                # Check control signals
                cmd_raw = self.signal_handler.check_signal()
                if cmd_raw:
                    parts = cmd_raw.split()
                    cmd = parts[0]
                    args = parts[1:]
                    
                    if cmd == "START":
                        self.running = True
                        self.paused = False
                        logger.info("START signal received. Bot now running.")
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
                        # TODO: Implement close position logic
                        pass
                    elif cmd == "SHUTDOWN":
                        logger.info("SHUTDOWN signal received. Exiting daemon.")
                        break
                
                # Fetch positions (always monitor)
                positions = self.tracker.fetch_positions()
                
                # Update Status
                status_data = {
                    "running": self.running,
                    "paused": self.paused,
                    "symbol": self.symbol,
                    "last_update": datetime.now().isoformat(),
                    "total_pnl": self.total_pnl,
                    "position_count": len(positions),
                    "pid": os.getpid()
                }
                
                status_str = "Running" if self.running and not self.paused else "Paused" if self.paused else "Stopped"
                self.signal_handler.update_status(status_str, status_data)
                
                # Execute trading logic if running and not paused
                if self.running and not self.paused:
                    self.execute_logic()
                
                time.sleep(1)
                
            except KeyboardInterrupt:
                logger.info("Keyboard interrupt received. Shutting down gracefully...")
                break
            except Exception as e:
                logger.error(f"Error in daemon loop: {e}", exc_info=True)
                try:
                    self.signal_handler.update_status("Error", {"error": str(e), "pid": os.getpid()})
                except:
                    pass
                time.sleep(5)
        
        logger.info("Bot daemon shut down.")


def run_daemon():
    """Entry point for running the daemon."""
    try:
        daemon = BotDaemon()
        daemon.run()
    except Exception as e:
        logger.error(f"Fatal error starting daemon: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    run_daemon()
