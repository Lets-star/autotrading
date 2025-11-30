
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

try:
    import pandas_ta as ta
except ImportError:
    pass

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
        
        # Load API keys
        self.api_key = settings.api_key
        self.api_secret = settings.api_secret
        
        self.fetcher = BybitDataFetcher(self.api_key, self.api_secret)
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
        
        # 3. Execution Logic
        action = signal.get('action', 'NEUTRAL')
        score = signal.get('score', 0.0)
        
        if action != 'NEUTRAL':
            logger.info(f"Signal Generated: {action} @ Score {score:.2f}")
            logger.info(f"Thresholds -> Long: {self.scoring.long_threshold}, Short: {self.scoring.short_threshold}")
        
        if "BUY" in action or "SELL" in action:
            # Check if we already have a position
            positions = self.tracker.fetch_positions() 
            if any(p['symbol'] == self.symbol for p in positions):
                logger.info(f"Position already open for {self.symbol}. Skipping.")
                return

            # Prepare Market Data for Risk
            current_close = float(df.iloc[-1]['close'])
            volume_24h = float(df['volume'].sum()) # Approx
            
            atr_val = 0.0
            try:
                if 'ta' in globals() and ta is not None:
                    atr_series = df.ta.atr(length=14)
                    if atr_series is not None and not atr_series.empty:
                        atr_val = float(atr_series.iloc[-1])
                else:
                    atr_val = float((df['high'] - df['low']).mean())
            except Exception as e:
                logger.warning(f"ATR calculation failed: {e}")

            market_data = {
                'volume_24h': volume_24h,
                'atr': atr_val,
                'close': current_close
            }
            
            # Use settings for risk limit amount if available, otherwise default to 1000
            amount = getattr(settings, 'risk_limit_amount', 1000.0)
            
            order_params = {
                "amount": amount,
                "symbol": self.symbol
            }
            
            logger.info(f"Checking Risk for {action} with amount {amount}...")
            allowed, reason = self.risk.validate_order(order_params, market_data)
            
            if not allowed:
                logger.warning(f"❌ Risk rejected: {reason}")
                return
                
            logger.info(f"✅ Risk approved. Opening position...")
            
            # Execute
            side = "Buy" if "BUY" in action else "Sell"
            if current_close > 0:
                qty = amount / current_close 
                qty = round(qty, 3) 
                
                result = self.fetcher.place_order(
                    symbol=self.symbol,
                    side=side,
                    qty=qty
                )
                
                if result.get('success'):
                    logger.info(f"Position opened: {self.symbol} {side} entry={current_close} size={qty}")
                    # Update status immediately
                    self.signal_handler.update_status("Running", {
                        "last_trade": f"{side} {self.symbol} @ {current_close}",
                        "last_trade_time": datetime.now().isoformat()
                    })
                else:
                    logger.error(f"Failed to open position: {result.get('error')}")

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
                    "pid": os.getpid()
                }
                self.signal_handler.update_status("Running" if self.running and not self.paused else "Paused" if self.paused else "Stopped", status_data)
                
                if self.running and not self.paused:
                    self.execute_logic()
                
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"Error in daemon loop: {e}", exc_info=True)
                self.signal_handler.update_status("Error", {"error": str(e)})
                time.sleep(5) # Backoff on error

if __name__ == "__main__":
    bot = BotDaemon()
    bot.run()
