import threading
import time
import pandas as pd
from typing import Dict, Any, List, Optional
from trading_bot.data_feeds.bybit_fetcher import BybitDataFetcher
from trading_bot.scoring.service import ScoringService
from trading_bot.logger import get_logger

logger = get_logger(__name__)

class MarketDataService:
    def __init__(self, api_key: str, api_secret: str, symbol: str, timeframes: List[str]):
        self.api_key = api_key
        self.api_secret = api_secret
        self.symbol = symbol
        self.timeframes = timeframes
        
        # Initialize fetcher
        self.fetcher = BybitDataFetcher(api_key=api_key, api_secret=api_secret)
        self.scoring = ScoringService(active_timeframes=timeframes)
        
        self._data_lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        
        self.data = {
            "price_history": pd.DataFrame(),
            "mtf_data": {},
            "orderbook": {},
            "signal": {},
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
                
                # Fetch history (1m)
                df = self.fetcher.fetch_history(self.symbol, "1m", limit=50)
                
                if df.empty:
                     # If data is empty, maybe connection issue
                     # But we don't want to spam errors if it's just one missed call
                     pass

                # Fetch MTF
                mtf_data = {}
                for tf in self.timeframes:
                     tf_df = self.fetcher.fetch_history(self.symbol, tf, limit=50)
                     if not tf_df.empty:
                         mtf_data[tf] = tf_df
                
                # Fetch Orderbook
                ob = self.fetcher.fetch_orderbook(self.symbol)
                
                # Calculate Signals
                signal = {}
                if not df.empty:
                    # signal keys: 'score', 'action'
                    signal = self.scoring.calculate_signals(df, mtf_data=mtf_data)
                
                # Update State
                with self._data_lock:
                    self.data["price_history"] = df
                    self.data["mtf_data"] = mtf_data
                    self.data["orderbook"] = ob
                    self.data["signal"] = signal
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
