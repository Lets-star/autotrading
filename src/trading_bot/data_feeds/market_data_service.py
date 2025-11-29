import threading
import time
import pandas as pd
from typing import Dict, Any, List, Optional
from trading_bot.data_feeds.binance_fetcher import BinanceDataFetcher
from trading_bot.scoring.service import ScoringService
from trading_bot.risk.service import RiskService
from trading_bot.logger import get_logger

logger = get_logger(__name__)

class MarketDataService:
    def __init__(self, api_key: str, api_secret: str, symbol: str, timeframes: List[str], selected_timeframe: str = "1h"):
        self.api_key = api_key
        self.api_secret = api_secret
        self.symbol = symbol
        self.timeframes = timeframes
        self.selected_timeframe = selected_timeframe
        
        # Initialize fetcher
        self.fetcher = BinanceDataFetcher(api_key=api_key, api_secret=api_secret)
        self.scoring = ScoringService(active_timeframes=timeframes)
        self.risk = RiskService()
        
        self._data_lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        
        self.data = {
            "price_history": pd.DataFrame(),
            "mtf_data": {},
            "orderbook": {},
            "signal": {},
            "risk_metrics": {},
            "last_updated": 0,
            "update_count": 0,
            "status": "Disconnected",
            "error": None
        }

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info("MarketDataService started")

    def stop(self):
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2)
            logger.info("MarketDataService stopped")

    def _run_loop(self):
        self._update_status("Connecting")
        
        while not self._stop_event.is_set():
            start_time = time.time()
            try:
                # Fetch Data
                # We use a wrapper to enforce timeout if the library doesn't support it naturally
                # But here we rely on the fetcher. 
                # TODO: Ensure fetcher has timeouts.
                
                # Fetch history (Selected TF)
                current_tf = self.selected_timeframe
                logger.debug(f"Fetching data for timeframe: {current_tf}")
                
                df = self.fetcher.fetch_history(self.symbol, current_tf, limit=500)
                
                if df.empty:
                     # If data is empty, maybe connection issue
                     pass

                # Fetch MTF
                mtf_data = {}
                for tf in self.timeframes:
                     # Skip if same as current_tf to avoid duplicate fetch?
                     # But maybe we want it in mtf_data too.
                     if tf == current_tf:
                         mtf_data[tf] = df
                         continue
                         
                     tf_df = self.fetcher.fetch_history(self.symbol, tf, limit=500)
                     if not tf_df.empty:
                         mtf_data[tf] = tf_df
                
                # Fetch Orderbook
                ob = self.fetcher.fetch_orderbook(self.symbol)
                
                # Calculate Signals
                signal = {}
                risk_metrics = {}
                if not df.empty:
                    # signal keys: 'score', 'action'
                    signal = self.scoring.calculate_signals(df, mtf_data=mtf_data)
                    
                    # Calculate Risk Metrics
                    current_price = df.iloc[-1]['close']
                    details = signal.get('details', {})
                    components = details.get('components', {})
                    atr_comp = components.get('technical_atr', {})
                    atr_val = atr_comp.get('metadata', {}).get('value', 0.0)
                    
                    if atr_val > 0:
                        risk_metrics['atr'] = atr_val
                        action = signal.get('action', 'NEUTRAL')
                        
                        # Default SL logic using RiskService
                        # RiskService only supports LONG logic by default, so we adapt here
                        sl_long = self.risk.calculate_stop_loss(current_price, atr_val)
                        sl_short = current_price + (atr_val * self.risk.atr_multiplier)
                        
                        if 'BUY' in action:
                            risk_metrics['sl'] = sl_long
                            risk_metrics['tp'] = current_price + (current_price - sl_long) * 1.5 
                        elif 'SELL' in action:
                            risk_metrics['sl'] = sl_short
                            risk_metrics['tp'] = current_price - (sl_short - current_price) * 1.5
                        else:
                            # Show levels for both? or just ATR
                            pass
                
                # Update State
                with self._data_lock:
                    self.data["price_history"] = df
                    self.data["mtf_data"] = mtf_data
                    self.data["orderbook"] = ob
                    self.data["signal"] = signal
                    self.data["risk_metrics"] = risk_metrics
                    self.data["last_updated"] = time.time()
                    self.data["update_count"] += 1
                    self.data["status"] = "Connected"
                    self.data["error"] = None
                
            except Exception as e:
                logger.error(f"Error in MarketDataService loop: {e}")
                with self._data_lock:
                    self.data["status"] = "Error"
                    self.data["error"] = str(e)
            
            # Sleep to limit rate
            elapsed = time.time() - start_time
            sleep_time = max(1.0, 5.0 - elapsed) # Update every ~5 seconds or so, or 1s?
            # Ticket says: "st.rerun() called not more than 1 time per second"
            # And "Auto-refresh (15s)" was the original setting.
            # Let's target 1s update rate for responsiveness, or maybe 3s to be safe.
            # Let's use 1s as requested for "counter updates" etc.
            time.sleep(1)

    def _update_status(self, status):
        with self._data_lock:
            self.data["status"] = status

    def get_data(self) -> Dict[str, Any]:
        with self._data_lock:
            # Return a copy to avoid threading issues with mutable objects
            # Dataframes are mutable, but we are assigning new ones in the loop.
            # Shallow copy of dict is fine.
            return self.data.copy()
