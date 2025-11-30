import os
import sys
import time
import json
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime

# Add src to python path to import config
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '..'))
src_path = os.path.join(project_root, 'src')
sys.path.append(src_path)

from trading_bot.config import settings
from pybit.unified_trading import HTTP

# Constants
SIGNAL_FILE = os.path.join(project_root, 'signals', 'command.txt')
STATUS_FILE = os.path.join(project_root, 'signals', 'status.json')
POSITIONS_FILE = os.path.join(project_root, 'data', 'positions.json')
LOG_FILE = os.path.join(project_root, 'logs', 'daemon.log')

# Setup Logging
logger = logging.getLogger("BotDaemon")
logger.setLevel(logging.DEBUG)
handler = RotatingFileHandler(LOG_FILE, maxBytes=1024*1024, backupCount=5)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

class BotDaemon:
    def __init__(self):
        self.running = False
        self.positions = {}
        self.client = None
        self._init_client()
        self._load_positions()

    def _init_client(self):
        try:
            if settings.api_key and settings.api_secret:
                self.client = HTTP(
                    testnet=False,
                    api_key=settings.api_key,
                    api_secret=settings.api_secret
                )
                logger.info("Bybit client initialized")
            else:
                logger.warning("API Key/Secret not found. Running in simulation mode (no real trades).")
        except Exception as e:
            logger.error(f"Failed to init Bybit client: {e}")

    def _load_positions(self):
        if os.path.exists(POSITIONS_FILE):
            try:
                with open(POSITIONS_FILE, 'r') as f:
                    self.positions = json.load(f)
            except Exception as e:
                logger.error(f"Failed to load positions: {e}")
                self.positions = {}

    def save_positions(self):
        try:
            with open(POSITIONS_FILE, 'w') as f:
                json.dump(self.positions, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save positions: {e}")

    def update_status(self):
        try:
            status = {
                "pid": os.getpid(),
                "running": self.running,
                "last_update": datetime.utcnow().isoformat()
            }
            with open(STATUS_FILE, 'w') as f:
                json.dump(status, f)
        except Exception as e:
            logger.error(f"Failed to update status: {e}")

    def read_signal(self):
        if not os.path.exists(SIGNAL_FILE):
            return None
        
        try:
            with open(SIGNAL_FILE, 'r') as f:
                content = f.read()
            
            # Parse key-value pairs
            data = {}
            for line in content.splitlines():
                if '=' in line:
                    key, value = line.split('=', 1)
                    data[key.strip()] = value.strip()
            
            # Remove file after reading to avoid duplicate processing
            os.remove(SIGNAL_FILE)
            
            if 'ACTION' in data:
                return data
            return None
        except Exception as e:
            logger.error(f"Error reading signal file: {e}")
            return None

    def check_risk(self, signal):
        # Basic risk check
        # For now, just check if we have enough balance (mock check if client not available)
        # or check if we already have a position for this pair
        
        pair = signal.get('PAIR')
        if not pair:
            return False
        
        # Check if position already exists
        position_key = f"{pair}_LONG" # Assuming LONG for now as per example
        if signal.get('ACTION') == 'BUY' and position_key in self.positions:
            logger.warning(f"Position already exists for {pair}")
            return False
            
        return True

    def open_position(self, signal):
        pair = signal.get('PAIR')
        action = signal.get('ACTION')
        score = float(signal.get('SCORE', 0))
        
        logger.info(f"Opening position: {action} {pair} (Score: {score})")
        
        # Real execution
        if self.client:
            retries = 3
            for attempt in range(retries):
                try:
                    # Example: Market Buy
                    # For simplicity, using a fixed qty or calculated based on risk
                    # We need to fetch current price or use market order
                    
                    # Fetch ticker to get price
                    ticker = self.client.get_tickers(category="linear", symbol=pair)
                    price = float(ticker['result']['list'][0]['lastPrice'])
                    
                    # Calculate size based on risk_limit_amount (USD)
                    # size = USD / price
                    size_usd = settings.risk_limit_amount
                    qty = size_usd / price
                    # Round qty to valid precision (simplified here)
                    qty = round(qty, 3) 

                    side = "Buy" if action == "BUY" else "Sell"
                    
                    logger.info(f"Placing order: {side} {qty} {pair} at ~{price}")
                    
                    order = self.client.place_order(
                        category="linear",
                        symbol=pair,
                        side=side,
                        orderType="Market",
                        qty=str(qty),
                        # timeInForce="GTC"
                    )
                    logger.info(f"Order placed: {order}")
                    
                    # Assume filled for tracking
                    position_id = f"{pair}_{'LONG' if action == 'BUY' else 'SHORT'}"
                    self.positions[position_id] = {
                        "entry": price,
                        "size": qty,
                        "sl": price * 0.95, # Example SL
                        "tp1": price * 1.05, # Example TP
                        "tp2": price * 1.07,
                        "tp3": price * 1.10,
                        "opened_at": datetime.utcnow().isoformat() + "Z"
                    }
                    self.save_positions()
                    return self.positions[position_id]
                    
                except Exception as e:
                    logger.error(f"Bybit API Error (Attempt {attempt+1}/{retries}): {e}")
                    if attempt < retries - 1:
                        time.sleep(1)
                    else:
                        raise e
        else:
            # Simulation mode
            logger.info("Simulation: Position opened")
            position_id = f"{pair}_{'LONG' if action == 'BUY' else 'SHORT'}"
            self.positions[position_id] = {
                "entry": 45000, # Mock
                "size": 0.1,
                "sl": 44000,
                "tp1": 46000,
                "opened_at": datetime.utcnow().isoformat() + "Z",
                "simulated": True
            }
            self.save_positions()
            return self.positions[position_id]

    def process_command(self, data):
        action = data.get('ACTION')
        if action == 'START':
            self.running = True
            logger.info("Daemon STARTED processing signals")
        elif action == 'STOP':
            self.running = False
            logger.info("Daemon STOPPED processing signals")
        elif action == 'CLOSE_ALL':
            logger.info("Closing all positions...")
            self.positions = {} # Mock close
            self.save_positions()
        elif action == 'HEALTH_CHECK':
            logger.info("Health check: OK")
        elif action in ['BUY', 'SELL']:
            if self.running:
                if self.check_risk(data):
                    try:
                        self.open_position(data)
                    except Exception as e:
                        logger.error(f"Failed to open position: {e}")
            else:
                logger.info(f"Signal ignored (Daemon stopped): {data}")

    def run(self):
        logger.info("Bot Daemon started. Waiting for signals...")
        # Create positions file if not exists
        if not os.path.exists(POSITIONS_FILE):
             self.save_positions()

        while True:
            self.update_status()
            signal = self.read_signal()
            if signal:
                logger.info(f"Received command: {signal}")
                self.process_command(signal)
            
            time.sleep(1)

if __name__ == "__main__":
    daemon = BotDaemon()
    daemon.run()
